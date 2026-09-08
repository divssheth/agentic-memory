"""Cosmos DB-backed semantic memory store with vector search.

Stores preferences as documents with embeddings. Supports lifecycle
properties (state, confidence, confirmation_count), SCD Type 2
supersession (valid_from / valid_to), and provenance (source_detail,
created_by). Used by Modules 2–4 and beyond.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from azure.cosmos.aio import CosmosClient, ContainerProxy

# Vector search requires Cosmos DB for NoSQL with DiskANN indexing.
# Container must be created with the vector embedding policy and
# composite indexes defined in create_container().

CONTAINER_ID = "semantic-memory"
DB_ID = "travel-memory"

# ---------------------------------------------------------------------------
# Container setup
# ---------------------------------------------------------------------------

async def create_container(cosmos: CosmosClient) -> ContainerProxy:
    """Create (or open) the semantic-memory container with vector index."""
    from azure.cosmos import PartitionKey

    db = await cosmos.create_database_if_not_exists(DB_ID)
    container = await db.create_container_if_not_exists(
        id=CONTAINER_ID,
        partition_key=PartitionKey(path="/user_id"),
        indexing_policy={
            "automatic": True,
            "includedPaths": [{"path": "/*"}],
            "excludedPaths": [{"path": "/embedding/*"}],
            "vectorIndexes": [{"path": "/embedding", "type": "diskANN"}],
        },
        vector_embedding_policy={
            "vectorEmbeddings": [{
                "path": "/embedding",
                "dataType": "float32",
                "distanceFunction": "cosine",
                "dimensions": 1536,
            }]
        },
    )
    return container


# ---------------------------------------------------------------------------
# Semantic Memory Store
# ---------------------------------------------------------------------------

class SemanticMemoryStore:
    """CRUD + vector search over preference documents in Cosmos DB.

    Every preference is a document with lifecycle properties that later
    modules (promotion, belief revision, retention, provenance) can
    update via partial patches.
    """

    def __init__(self, container: ContainerProxy, user_id: str,
                 embed_fn=None, scope_tag: str | None = None):
        self._c = container
        self._user_id = user_id
        self._embed = embed_fn  # async (text) -> list[float]
        self.scope_tag = scope_tag

    # ----- write -----

    async def add_preference(
        self,
        category: str,
        preference: str,
        confidence: float = 0.8,
        source_type: str = "user_assertion",
        state: str | None = None,
    ) -> dict:
        """Store a preference. Auto-supersedes any conflicting current
        value in the same category (SCD Type 2)."""
        if state is None:
            state = "provisional" if source_type == "user_assertion" else "candidate"

        # Supersede existing current preference in this category
        existing = await self._current_in_category(category)
        if existing and existing["preference"].lower() != preference.lower():
            await self._c.patch_item(
                item=existing["id"],
                partition_key=self._user_id,
                patch_operations=[
                    {"op": "set", "path": "/valid_to",
                     "value": datetime.now(timezone.utc).isoformat()},
                    {"op": "set", "path": "/superseded_by", "value": preference},
                ],
            )

        embedding = await self._embed(preference) if self._embed else []
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "id": str(uuid.uuid4()),
            "user_id": self._user_id,
            "category": category,
            "preference": preference,
            "confidence": confidence,
            "state": state,
            "source_type": source_type,
            "valid_from": now,
            "valid_to": None,
            "superseded_by": None,
            "confirmation_count": 0,
            "first_seen": now,
            "last_confirmed": now if source_type == "user_assertion" else None,
            "source_detail": None,
            "created_by": None,
            "scope_tag": self.scope_tag,
            "embedding": embedding,
        }
        await self._c.upsert_item(doc)
        return doc

    # ----- read -----

    async def search(self, query: str, *, top_k: int = 10,
                     current_only: bool = True,
                     states: list[str] | None = None) -> list[dict]:
        """Vector similarity search over preferences."""
        if not self._embed:
            raise RuntimeError("No embedding function provided")
        qv = await self._embed(query)
        where = ["c.user_id = @uid"]
        params = [{"name": "@uid", "value": self._user_id}]

        if current_only:
            where.append("IS_NULL(c.valid_to)")
        if states:
            placeholders = ", ".join(f"@s{i}" for i in range(len(states)))
            where.append(f"c.state IN ({placeholders})")
            for i, s in enumerate(states):
                params.append({"name": f"@s{i}", "value": s})
        if self.scope_tag:
            where.append("c.scope_tag = @scope")
            params.append({"name": "@scope", "value": self.scope_tag})

        sql = (
            "SELECT TOP @topK c.id, c.category, c.preference, c.confidence, "
            "c.state, c.source_type, c.source_detail, c.created_by, "
            "c.first_seen, c.last_confirmed, c.confirmation_count, "
            "c.valid_from, c.valid_to, c.superseded_by, "
            "VectorDistance(c.embedding, @qv) AS score "
            f"FROM c WHERE {' AND '.join(where)} "
            "ORDER BY VectorDistance(c.embedding, @qv)"
        )
        params.append({"name": "@topK", "value": top_k})
        params.append({"name": "@qv", "value": qv})

        return [item async for item in self._c.query_items(
            sql, parameters=params, partition_key=self._user_id,
        )]

    async def get_current(self, category: str) -> dict | None:
        """Return the current (non-superseded) preference in a category."""
        return await self._current_in_category(category)

    async def history(self, category: str) -> list[dict]:
        """Full SCD Type 2 audit trail for a category."""
        sql = (
            "SELECT c.id, c.preference, c.state, c.source_type, "
            "c.source_detail, c.valid_from, c.valid_to, c.superseded_by, "
            "c.confidence, c.confirmation_count "
            "FROM c WHERE c.user_id = @uid AND c.category = @cat "
            "ORDER BY c.valid_from"
        )
        params = [
            {"name": "@uid", "value": self._user_id},
            {"name": "@cat", "value": category},
        ]
        return [item async for item in self._c.query_items(
            sql, parameters=params, partition_key=self._user_id,
        )]

    async def snapshot(self, *, include_deprecated: bool = False) -> list[dict]:
        """All preferences for this user."""
        where = "c.user_id = @uid"
        params = [{"name": "@uid", "value": self._user_id}]
        if not include_deprecated:
            where += " AND (NOT IS_DEFINED(c.state) OR c.state != 'deprecated')"
        if self.scope_tag:
            where += " AND c.scope_tag = @scope"
            params.append({"name": "@scope", "value": self.scope_tag})

        sql = (
            "SELECT c.id, c.category, c.preference, c.state, c.confidence, "
            "c.source_type, c.source_detail, c.created_by, "
            "c.confirmation_count, c.first_seen, c.valid_from, c.valid_to, "
            "c.superseded_by "
            f"FROM c WHERE {where} ORDER BY c.valid_from"
        )
        return [item async for item in self._c.query_items(
            sql, parameters=params, partition_key=self._user_id,
        )]

    async def count(self, *, current_only: bool = True) -> int:
        """Count preferences."""
        where = "c.user_id = @uid"
        params = [{"name": "@uid", "value": self._user_id}]
        if current_only:
            where += " AND IS_NULL(c.valid_to) AND (NOT IS_DEFINED(c.state) OR c.state != 'deprecated')"
        if self.scope_tag:
            where += " AND c.scope_tag = @scope"
            params.append({"name": "@scope", "value": self.scope_tag})

        sql = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        rows = [r async for r in self._c.query_items(
            sql, parameters=params, partition_key=self._user_id,
        )]
        return rows[0] if rows else 0

    # ----- lifecycle updates (used by Modules 3-4) -----

    async def confirm(self, preference_text: str) -> dict | None:
        """Increment confirmation_count and advance state."""
        matches = await self.search(preference_text, top_k=1,
                                    current_only=True)
        if not matches:
            return None
        doc = matches[0]
        new_count = (doc.get("confirmation_count") or 0) + 1
        src = doc.get("source_type", "")
        old_state = doc.get("state", "candidate")

        if src == "user_assertion" and new_count >= 1:
            new_state = "trusted"
        elif new_count >= 2:
            new_state = "trusted"
        elif new_count >= 1:
            new_state = "provisional"
        else:
            new_state = old_state

        await self._c.patch_item(
            item=doc["id"],
            partition_key=self._user_id,
            patch_operations=[
                {"op": "set", "path": "/confirmation_count", "value": new_count},
                {"op": "set", "path": "/last_confirmed",
                 "value": datetime.now(timezone.utc).isoformat()},
                {"op": "set", "path": "/state", "value": new_state},
            ],
        )
        return {"preference": doc["preference"], "state": new_state,
                "confirmations": new_count}

    async def enrich(self, category: str, source_detail: str,
                     created_by: str = "TravelAssistant") -> dict | None:
        """Attach provenance evidence to an existing preference."""
        doc = await self._current_in_category(category)
        if not doc:
            return None
        await self._c.patch_item(
            item=doc["id"],
            partition_key=self._user_id,
            patch_operations=[
                {"op": "set", "path": "/source_detail", "value": source_detail},
                {"op": "set", "path": "/created_by", "value": created_by},
            ],
        )
        doc["source_detail"] = source_detail
        doc["created_by"] = created_by
        return doc

    async def set_state(self, doc_id: str, state: str) -> None:
        """Update the lifecycle state of a preference."""
        await self._c.patch_item(
            item=doc_id,
            partition_key=self._user_id,
            patch_operations=[
                {"op": "set", "path": "/state", "value": state},
            ],
        )

    # ----- reset -----

    async def reset(self) -> int:
        """Delete this user's preferences (scoped by scope_tag if set)."""
        where = "c.user_id = @uid"
        params = [{"name": "@uid", "value": self._user_id}]
        if self.scope_tag:
            where += " AND c.scope_tag = @scope"
            params.append({"name": "@scope", "value": self.scope_tag})

        sql = f"SELECT c.id FROM c WHERE {where}"
        ids = [item["id"] async for item in self._c.query_items(
            sql, parameters=params, partition_key=self._user_id,
        )]
        for doc_id in ids:
            await self._c.delete_item(doc_id, partition_key=self._user_id)
        return len(ids)

    # ----- internal -----

    async def _current_in_category(self, category: str) -> dict | None:
        sql = (
            "SELECT * FROM c WHERE c.user_id = @uid "
            "AND c.category = @cat AND IS_NULL(c.valid_to) "
            "ORDER BY c.valid_from DESC OFFSET 0 LIMIT 1"
        )
        params = [
            {"name": "@uid", "value": self._user_id},
            {"name": "@cat", "value": category},
        ]
        items = [item async for item in self._c.query_items(
            sql, parameters=params, partition_key=self._user_id,
        )]
        return items[0] if items else None

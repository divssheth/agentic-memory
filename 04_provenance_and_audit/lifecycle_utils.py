"""Neo4j-backed provenance and confidence utilities for Module 04.

This module deliberately keeps provenance separate from the lifecycle objects in
Module 03. It reuses the same Preference node properties and user-scoped graph,
but exposes only the operations needed to teach where a memory came from and
how that evidence should affect an agent's wording.
"""

from __future__ import annotations


class GraphProvenanceStore:
    """Store and recall beliefs with traceable provenance.

    Lifecycle state remains the visibility gate established in Module 03:
    candidate and deprecated beliefs are withheld. Confidence then controls how
    a visible belief is presented: assert, hedge, or ask.
    """

    MODULE_TAG = "module_04_provenance"
    VALID_SOURCE_TYPES = {
        "user_assertion",
        "llm_inference",
        "tool_output",
        "enterprise_kb",
    }

    def __init__(self, memory, user_id: str):
        self._m = memory
        self._user_id = user_id

    async def reset(self) -> None:
        """Delete only this user's Module 04 demo records."""
        await self._m._client.execute_write(
            "MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference) "
            "WHERE p.demo_module = $module DETACH DELETE p",
            {"uid": self._user_id, "module": self.MODULE_TAG},
        )

    async def store(
        self,
        category: str,
        preference: str,
        source_type: str,
        confidence: float,
        source_detail: str,
        created_by: str = "TravelAssistant",
    ) -> dict:
        """Store a belief and the evidence that caused it to exist.

        A replacement retires the previous value rather than deleting it, which
        preserves the temporal lineage introduced in Module 03. User assertions
        enter as provisional; all other sources enter as candidates.
        """
        if not category.strip() or not preference.strip():
            raise ValueError("category and preference must not be empty")
        if source_type not in self.VALID_SOURCE_TYPES:
            allowed = ", ".join(sorted(self.VALID_SOURCE_TYPES))
            raise ValueError(f"source_type must be one of: {allowed}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not source_detail.strip():
            raise ValueError("source_detail must describe the supporting interaction or evidence")

        existing = await self._m.query.cypher(
            "MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference) "
            "WHERE p.demo_module = $module AND p.category = $cat "
            "  AND p.valid_from IS NOT NULL AND p.valid_to IS NULL "
            "RETURN p.id AS id, p.preference AS preference, p.state AS state "
            "ORDER BY p.valid_from DESC LIMIT 1",
            params={
                "uid": self._user_id,
                "module": self.MODULE_TAG,
                "cat": category,
            },
        )

        if existing and existing[0]["preference"].casefold() == preference.casefold():
            return {
                "preference": existing[0]["preference"],
                "state": existing[0]["state"],
                "superseded": None,
                "already_current": True,
            }

        superseded = existing[0]["preference"] if existing else None
        if existing:
            await self._m._client.execute_write(
                "MATCH (p:Preference {id:$id}) "
                "SET p.valid_to = datetime(), p.superseded_by = $replacement "
                "REMOVE p.embedding",
                {"id": existing[0]["id"], "replacement": preference},
            )

        stored = await self._m.long_term.add_preference(
            category=category,
            preference=preference,
            confidence=confidence,
            user_identifier=self._user_id,
        )
        state = "provisional" if source_type == "user_assertion" else "candidate"
        await self._m._client.execute_write(
            """MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->
                     (p:Preference {id:$id})
               SET p.demo_module = $module,
                   p.category = $cat,
                   p.state = $state,
                   p.confidence = $confidence,
                   p.source_type = $source_type,
                   p.source_detail = $source_detail,
                   p.created_by = $created_by,
                   p.confirmation_count = 0,
                   p.first_seen = datetime(),
                   p.last_confirmed = null,
                   p.valid_from = datetime(),
                   p.valid_to = null,
                   p.superseded_by = null""",
            {
                "uid": self._user_id,
                "id": str(stored.id),
                "module": self.MODULE_TAG,
                "cat": category,
                "state": state,
                "confidence": confidence,
                "source_type": source_type,
                "source_detail": source_detail,
                "created_by": created_by,
            },
        )
        return {
            "preference": preference,
            "state": state,
            "superseded": superseded,
            "already_current": False,
        }

    async def confirm(self, preference: str) -> dict:
        """Confirm the closest matching belief and advance its established state.

        User assertions become trusted after one later confirmation. Other
        sources become provisional after one confirmation and trusted after two.
        """
        hits = await self._m.long_term.search_preferences(
            query=preference, threshold=0.0, limit=1
        )
        if not hits:
            return {
                "state": None,
                "confirmations": 0,
                "error": "preference_not_found",
            }

        rows = await self._m._client.execute_write(
            """MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference)
               WHERE p.id IN $ids AND p.demo_module = $module
                 AND p.valid_to IS NULL
               WITH p LIMIT 1
               SET p.confirmation_count = coalesce(p.confirmation_count, 0) + 1,
                   p.last_confirmed = datetime()
               WITH p
               SET p.state = CASE
                   WHEN p.source_type = 'user_assertion'
                        AND p.confirmation_count >= 1 THEN 'trusted'
                   WHEN p.source_type <> 'user_assertion'
                        AND p.confirmation_count >= 2 THEN 'trusted'
                   WHEN p.source_type <> 'user_assertion'
                        AND p.confirmation_count >= 1 THEN 'provisional'
                   ELSE p.state END
               RETURN p.preference AS preference, p.state AS state,
                      p.confirmation_count AS confirmations""",
            {
                "uid": self._user_id,
                "ids": [str(hit.id) for hit in hits],
                "module": self.MODULE_TAG,
            },
        )
        if rows:
            return rows[0]
        return {
            "state": None,
            "confirmations": 0,
            "error": "confirmation_failed",
        }

    async def recall_baseline(self, query: str) -> str:
        """Reproduce Module 03's state-tagged, provenance-lossy recall."""
        rows = await self._recall_rows(query)
        if not rows:
            return "No current beliefs found."
        return "\n".join(
            f"{'[KNOWN]' if row['state'] == 'trusted' else '[LIKELY]'} "
            f"{row['preference']}"
            for row in rows
        )

    async def recall_with_confidence(self, query: str) -> list[dict]:
        """Return visible beliefs with provenance and a response strategy."""
        rows = await self._recall_rows(query)
        for row in rows:
            row["presentation"] = self._presentation(
                row["state"], row.get("confidence") or 0.0
            )
        return rows

    async def explain(self, category: str) -> dict | None:
        """Return the current belief and the persisted reasons behind it."""
        current = await self._m.query.cypher(
            """MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference)
               WHERE p.demo_module = $module AND p.category = $cat
                 AND p.valid_from IS NOT NULL AND p.valid_to IS NULL
               RETURN p.preference AS preference, p.category AS category,
                      p.state AS state, p.confidence AS confidence,
                      p.source_type AS source_type,
                      p.source_detail AS source_detail,
                      p.created_by AS created_by,
                      toString(p.first_seen) AS first_seen,
                      toString(p.last_confirmed) AS last_confirmed,
                      p.confirmation_count AS confirmation_count
               ORDER BY p.valid_from DESC LIMIT 1""",
            params={
                "uid": self._user_id,
                "module": self.MODULE_TAG,
                "cat": category,
            },
        )
        if not current:
            return None

        history = await self._m.query.cypher(
            """MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference)
               WHERE p.demo_module = $module AND p.category = $cat
                 AND p.valid_from IS NOT NULL
               RETURN p.preference AS preference, p.state AS state,
                      p.source_type AS source_type,
                      p.source_detail AS source_detail,
                      toString(p.valid_from) AS valid_from,
                      toString(p.valid_to) AS valid_to,
                      p.superseded_by AS superseded_by
               ORDER BY p.valid_from""",
            params={
                "uid": self._user_id,
                "module": self.MODULE_TAG,
                "cat": category,
            },
        )
        result = current[0]
        result["history"] = history
        result["presentation"] = self._presentation(
            result["state"], result.get("confidence") or 0.0
        )
        return result

    async def snapshot(self) -> list[dict]:
        """Return this user's Module 04 records for notebook inspection."""
        return await self._m.query.cypher(
            """MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference)
               WHERE p.demo_module = $module
               RETURN p.preference AS preference, p.category AS category,
                      p.state AS state, p.confidence AS confidence,
                      p.source_type AS source_type,
                      p.source_detail AS source_detail,
                      p.created_by AS created_by,
                      p.confirmation_count AS confirmation_count,
                      toString(p.first_seen) AS first_seen,
                      toString(p.valid_from) AS valid_from,
                      toString(p.valid_to) AS valid_to
               ORDER BY p.valid_from""",
            params={"uid": self._user_id, "module": self.MODULE_TAG},
        )

    async def _recall_rows(self, query: str) -> list[dict]:
        hits = await self._m.long_term.search_preferences(
            query=query, threshold=0.0
        )
        if not hits:
            return []
        return await self._m.query.cypher(
            """MATCH (:User {identifier:$uid})-[:HAS_PREFERENCE]->(p:Preference)
               WHERE p.id IN $ids AND p.demo_module = $module
                 AND p.valid_to IS NULL
                 AND p.state IN ['trusted', 'provisional']
               RETURN p.preference AS preference, p.category AS category,
                      p.state AS state, p.confidence AS confidence,
                      p.source_type AS source_type,
                      p.source_detail AS source_detail,
                      p.created_by AS created_by,
                      toString(p.first_seen) AS first_seen,
                      p.confirmation_count AS confirmation_count""",
            params={
                "uid": self._user_id,
                "ids": [str(hit.id) for hit in hits],
                "module": self.MODULE_TAG,
            },
        )

    @staticmethod
    def _presentation(state: str, confidence: float) -> str:
        if state == "provisional":
            return "ask" if confidence < 0.5 else "hedge"
        if state == "trusted":
            if confidence >= 0.8:
                return "assert"
            return "hedge" if confidence >= 0.5 else "ask"
        return "withhold"

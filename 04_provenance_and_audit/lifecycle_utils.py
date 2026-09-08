"""Provenance and confidence views over Cosmos DB lifecycle memories."""

from __future__ import annotations


class CosmosProvenanceStore:
    """Enrich and recall lifecycle beliefs with traceable provenance.

    Wraps a SemanticMemoryStore from shared/semantic_store.py.
    Lifecycle state remains the visibility gate: candidate and deprecated
    beliefs are withheld. Confidence controls presentation: assert, hedge, ask.
    """

    def __init__(self, store):
        self._s = store  # SemanticMemoryStore

    async def prerequisite_count(self) -> int:
        """Count lifecycle memories available from earlier notebooks."""
        return await self._s.count(current_only=False)

    async def clear_provenance(self) -> int:
        """Remove provenance metadata without deleting lifecycle memories."""
        docs = await self._s.snapshot(include_deprecated=True)
        cleared = 0
        for d in docs:
            if d.get("source_detail") or d.get("created_by"):
                await self._s._c.patch_item(
                    item=d["id"],
                    partition_key=self._s._user_id,
                    patch_operations=[
                        {"op": "set", "path": "/source_detail", "value": None},
                        {"op": "set", "path": "/created_by", "value": None},
                    ],
                )
                cleared += 1
        return cleared

    async def enrich(
        self,
        category: str,
        source_detail: str,
        created_by: str = "TravelAssistant",
    ) -> dict | None:
        """Attach evidence to an existing current lifecycle memory."""
        if not category.strip():
            raise ValueError("category must not be empty")
        if not source_detail.strip():
            raise ValueError("source_detail must describe the supporting evidence")
        result = await self._s.enrich(category, source_detail, created_by)
        if not result:
            return {"error": "lifecycle_memory_not_found", "category": category}
        return result

    async def confirm(self, preference: str) -> dict:
        """Confirm the closest matching belief and advance its state."""
        result = await self._s.confirm(preference)
        if not result:
            return {"state": None, "confirmations": 0,
                    "error": "preference_not_found"}
        return result

    async def recall_baseline(self, query: str) -> str:
        """Reproduce the lifecycle-style state-tagged, provenance-lossy recall."""
        rows = await self._s.search(
            query, states=["trusted", "provisional"])
        if not rows:
            return "No current beliefs found."
        return "\n".join(
            f"{'[KNOWN]' if r['state'] == 'trusted' else '[LIKELY]'} "
            f"{r['preference']}"
            for r in rows
        )

    async def recall_with_confidence(self, query: str) -> list[dict]:
        """Return visible beliefs with provenance and a response strategy."""
        rows = await self._s.search(
            query, states=["trusted", "provisional"])
        for row in rows:
            row["presentation"] = self._presentation(
                row["state"], row.get("confidence") or 0.0)
        return rows

    async def explain(self, category: str) -> dict | None:
        """Return the current belief and the persisted reasons behind it."""
        current = await self._s.get_current(category)
        if not current:
            return None
        history = await self._s.history(category)
        result = {
            "preference": current["preference"],
            "category": current.get("category"),
            "state": current.get("state"),
            "confidence": current.get("confidence"),
            "source_type": current.get("source_type"),
            "source_detail": current.get("source_detail"),
            "created_by": current.get("created_by"),
            "first_seen": current.get("first_seen"),
            "last_confirmed": current.get("last_confirmed"),
            "confirmation_count": current.get("confirmation_count"),
            "history": history,
        }
        result["presentation"] = self._presentation(
            result["state"] or "candidate",
            result.get("confidence") or 0.0,
        )
        return result

    async def snapshot(self) -> list[dict]:
        """Return this user's existing lifecycle records for inspection."""
        return await self._s.snapshot(include_deprecated=True)

    @staticmethod
    def _presentation(state: str, confidence: float) -> str:
        if state == "provisional":
            return "ask" if confidence < 0.5 else "hedge"
        if state == "trusted":
            if confidence >= 0.8:
                return "assert"
            return "hedge" if confidence >= 0.5 else "ask"
        return "withhold"


# Backward-compatible alias
GraphProvenanceStore = CosmosProvenanceStore

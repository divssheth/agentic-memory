"""Agent-facing memory tools and presentation rules shared across modules.

Tools are built per user: the store passed to ``make_preference_tools`` is
already bound to one ``user_id`` (the Cosmos partition key), so the model can
never choose whose memories it reads or writes.
"""

import json

from agent_framework import tool


def presentation(state: str, confidence: float) -> str:
    """How the agent should voice a belief: assert, hedge, ask or withhold.

    Lifecycle state gates visibility first; confidence then sets the tone.
    """
    if state == "trusted":
        if confidence >= 0.8:
            return "assert"
        return "hedge" if confidence >= 0.5 else "ask"
    if state == "provisional":
        return "hedge" if confidence >= 0.5 else "ask"
    return "withhold"


def make_preference_tools(store) -> list:
    """Return recall/store preference tools bound to ``store``'s user."""

    @tool
    async def recall_preferences(query: str = "travel preferences", limit: int = 5) -> str:
        """Recall the current user's stored preferences from semantic memory."""
        results = await store.search(query, top_k=limit)
        if not results:
            return "No preferences found."
        return "\n".join(
            f"[{r['category']}] {r['preference']} (confidence: {r.get('confidence', 0):.2f})"
            for r in results
        )

    @tool
    async def store_preference(category: str, preference: str,
                               source_type: str = "user_assertion",
                               confidence: float = 0.8) -> str:
        """Store a personal preference for the current user. category: airline,
        hotel_chain, seating, dietary, home_city, budget, etc."""
        await store.add_preference(category, preference, confidence, source_type)
        return f"Stored [{category}]: {preference}"

    return [recall_preferences, store_preference]


TRUST_STATES = ["trusted", "provisional"]


async def retrieve(store, query: str, *, top_k: int = 5, pool: int = 20,
                   confidence_weight: float = 0.3) -> list[dict]:
    """Lifecycle-aware recall: current, trusted/provisional memories ranked by
    relevance and confidence, bounded to ``top_k``. Only returned memories
    are marked as accessed."""
    rows = await store.search(query, top_k=pool, current_only=True,
                              states=TRUST_STATES, track_access=False)
    if not rows:
        return []
    # Embedding similarities cluster in a narrow band; rescale to [0, 1] so
    # confidence breaks ties instead of overriding relevance.
    lo, hi = min(r["score"] for r in rows), max(r["score"] for r in rows)
    for r in rows:
        relevance = (r["score"] - lo) / (hi - lo) if hi > lo else 1.0
        r["rank"] = ((1 - confidence_weight) * relevance
                     + confidence_weight * (r.get("confidence") or 0.0))
        r["presentation"] = presentation(r["state"], r.get("confidence") or 0.0)
    ranked = sorted(rows, key=lambda r: r["rank"], reverse=True)[:top_k]
    await store.mark_accessed([r["id"] for r in ranked])
    return ranked


def make_retrieval_tool(store, top_k: int = 5):
    """Return a lifecycle-aware ``recall_current_beliefs`` tool bound to ``store``'s user."""

    @tool
    async def recall_current_beliefs(query: str) -> str:
        """Recall the current user's current, trusted or provisional preferences
        relevant to the query, each with how to present it: assert, hedge or ask."""
        rows = await retrieve(store, query, top_k=top_k)
        if not rows:
            return "No current beliefs are eligible for recall."
        return "\n".join(
            f"[{r['category']}] {r['preference']} -> {r['presentation']} "
            f"(state: {r['state']}, confidence: {r.get('confidence') or 0:.2f})"
            for r in rows
        )

    return recall_current_beliefs


def make_episodic_tool(container, user_id: str, scope_tag: str | None = None):
    """Return a ``recall_past_events`` tool over the episodic-events container,
    bound to one ``user_id`` partition."""

    @tool
    async def recall_past_events(event_type: str = "", limit: int = 5) -> str:
        """Recall what happened on the current user's past trips, most recent first.
        event_type: optional filter, one of trip, feedback, preference."""
        sql = "SELECT c.event_type, c.description, c.details, c.timestamp FROM c WHERE c.user_id = @uid"
        params = [{"name": "@uid", "value": user_id}]
        if event_type:
            sql += " AND c.event_type = @etype"
            params.append({"name": "@etype", "value": event_type})
        if scope_tag:
            sql += " AND c.scope_tag = @scope"
            params.append({"name": "@scope", "value": scope_tag})
        sql += " ORDER BY c.timestamp DESC OFFSET 0 LIMIT @lim"
        params.append({"name": "@lim", "value": limit})
        items = [i async for i in container.query_items(sql, parameters=params, partition_key=user_id)]
        return json.dumps(items, indent=2, default=str) if items else "No past events found."

    return recall_past_events


def make_policy_tool(search_client, embed_fn, top_k: int = 3):
    """Return a ``search_travel_policies`` tool over the Azure AI Search policy index."""
    from azure.search.documents.models import VectorizedQuery

    @tool
    async def search_travel_policies(query: str) -> str:
        """Search Contoso's corporate travel policies: budgets and limits by level,
        preferred vendors, safety, expenses and booking rules. Policy applies to
        everyone; it is not a personal preference."""
        results = search_client.search(
            search_text=query,
            vector_queries=[VectorizedQuery(vector=await embed_fn(query[:8000]),
                                            k_nearest_neighbors=top_k, fields="content_vector")],
            top=top_k,
            select=["title", "content", "version"],
        )
        docs = [{"title": r["title"], "content": r["content"][:1000], "version": r["version"]}
                for r in results]
        return json.dumps(docs, indent=2) if docs else "No matching policies found."

    return search_travel_policies

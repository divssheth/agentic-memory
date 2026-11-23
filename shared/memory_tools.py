"""Agent-facing memory tools and presentation rules shared across modules.

Tools are built per user: the store passed to ``make_preference_tools`` is
already bound to one ``user_id`` (the Cosmos partition key), so the model can
never choose whose memories it reads or writes.
"""

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

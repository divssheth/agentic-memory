# 04 Provenance & Confidence — Implementation Plan

## Module Narrative

> "Every memory must explain where it came from and how sure we are."

Provenance, audit trail, and confidence scoring are **not three separate systems** —
they are facets of the same metadata that already lives on every Preference node
in Neo4j. Module 3.3 stores `source_type` and `confidence`; Module 3.4 stores
`valid_from / valid_to` and full SCD Type 2 history. This module surfaces that
metadata to the user through agent tools and teaches the agent to *behave
differently* based on confidence level.

Maps to: FR-006 (Confidence Scoring), FR-013 (Audit Trail), FR-014 (Memory Provenance).

---

## Status: 🔨 TO IMPLEMENT

---

## Already Built (Module 3)

| Capability | Where | Method |
|---|---|---|
| Source tracking | `GraphPromotionStore.record()` | `source_type` param (`user_assertion`, `llm_inference`) |
| Confidence scoring | `GraphPromotionStore.record()` | `confidence` param (0–1) |
| Audit trail | `GraphBeliefStore.history()` | Full SCD Type 2 with `valid_from / valid_to` |
| Time-travel | `GraphBeliefStore.recall_at_time()` | Bi-temporal query by date |
| Trust state | `GraphPromotionStore` | `candidate → provisional → trusted` lifecycle |

**What's new in this notebook**: the agent can *explain* its beliefs (provenance tool),
and its *recall behaviour changes* based on confidence (assert / hedge / ask).

---

## Notebook: `01_provenance_and_confidence.ipynb`

### Objective

Extend the existing travel agent with two capabilities:
1. **Explain tool** — answer "Why do you believe X?" by surfacing provenance + history
2. **Confidence-aware recall** — agent asserts high-confidence beliefs, hedges medium, asks about low

### Builds On

- `GraphBeliefStore` (Module 3.4) — `history()`, `snapshot()`, `store()` with `source_type`
- `GraphPromotionStore` (Module 3.3) — `confidence`, `state`, `gated_recall()`
- Same Neo4j connection, same Foundry client, same travel agent

### New in `lifecycle_utils.py`

```python
# Add to GraphBeliefStore:
async def explain(self, category: str) -> str:
    # Provenance explanation: why we believe the current value for this category.
    # Returns: source_type, first stored date, confirmation count, confidence,
    # and the full SCD history showing how the belief evolved.

async def recall_with_confidence(self, query: str) -> list[dict]:
    # Recall beliefs annotated with confidence and presentation strategy.
    # Returns each belief with:
    #   presentation: "assert" (>=0.8) | "hedge" (>=0.5) | "ask" (<0.5)
    # Agent uses this to decide HOW to state the belief.
```

### Agent Tools (4 tools — same pattern as Module 3.4)

| Tool | Wraps | Purpose |
|------|-------|---------|
| `explain_belief` | `beliefs.explain(category)` | "Why do you believe I like Marriott?" → source, date, confidence |
| `remember_belief` | `beliefs.store(...)` | Same as 3.4 — store with source_type |
| `recall_beliefs` | `beliefs.recall_with_confidence(query)` | Recall with assert/hedge/ask annotation |
| `belief_history` | `beliefs.history(category)` | Same as 3.4 — full SCD audit trail |

### Demo Flow (5 turns)

1. **Turn 1** — User states preferences explicitly: "I prefer Marriott, aisle seats, vegetarian meals"
   → Agent stores all three as `user_assertion` with confidence 0.95

2. **Turn 2** — Agent infers from booking history: "Based on your last 3 trips, you seem to prefer morning flights"
   → Stored as `llm_inference` with confidence 0.55

3. **Turn 3** — User asks "What do you know about my preferences?"
   → Agent uses `recall_beliefs` → asserts Marriott (0.95), hedges morning flights (0.55):
   *"You prefer Marriott hotels and aisle seats. I also noticed you might prefer morning flights — should I prioritise those?"*

4. **Turn 4** — User asks "Why do you think I like Marriott?"
   → Agent uses `explain_belief("hotel_chain")` →
   *"You told me directly on [date]: 'I always stay at Marriott'. Source: user statement, confidence: 0.95."*

5. **Turn 5** — User asks "What about my flight time preference?"
   → `explain_belief("flight_time")` →
   *"I inferred this from your booking patterns (3 morning flights in a row). Source: inference, confidence: 0.55. This hasn't been confirmed by you."*

### Key Insight: Assert vs Hedge vs Ask

```
Confidence >= 0.8  →  ASSERT:  "You prefer Marriott."
Confidence >= 0.5  →  HEDGE:   "I believe you may prefer morning flights — should I prioritise those?"
Confidence < 0.5  →  ASK:     "Do you have a seating preference?"
```

The agent's instructions tell it to check the `presentation` field from `recall_beliefs`
and adjust its language accordingly. This is NOT a separate system — it's a behaviour
change driven by the confidence metadata that already exists on every Preference node.

### 📄 Reference Papers

**"Uncertainty Decomposition for Clarification Seeking in LLM Agents"** (arXiv:2606.19559)
> Separates "what the agent doesn't know" from "what the agent knows is uncertain" —
> enabling targeted clarification. Our assert/hedge/ask maps directly to this decomposition.

**"MEMPROBE: Probing Long-Term Agent Memory via Hidden User-State Recovery"** (arXiv:2606.24595)
> Evaluates memory as an auditable artifact. Our `explain_belief` tool makes the audit
> explicit — the user can probe any belief and get its full provenance chain.

---

## Prerequisites

- Module 3.3 (GraphPromotionStore — provides confidence + source_type)
- Module 3.4 (GraphBeliefStore — provides history + SCD Type 2)
- Neo4j + Foundry client setup (same .env as Module 3)

## Outputs for Later Modules

- `explain_belief` tool → reused in Module 06 (user control — users inspect their memories)
- Confidence-aware recall → reused in Module 08 (sycophancy evaluation)
- `recall_with_confidence()` → reused in Module 07 (defense — confidence ceiling enforcement)

# 05 Retention & Routing — Implementation Plan

## Module Narrative

> "Bounded memory: know what to keep, know where to look."

Memory grows without bound. This module addresses two problems:
1. **Retention** — the agent must actively manage its memory capacity, evicting
   low-value beliefs before the store becomes noisy
2. **Routing** — with four memory types available (chat history, episodic, semantic,
   procedural), the agent must pick the right store for each query

Both are implemented as agent tools, not standalone Python classes.
The LLM **is** the router — it picks which tools to call.

---

## Status: 🔨 TO IMPLEMENT

---

## Already Built (Module 3)

| Capability | Where | Method |
|---|---|---|
| Retention scoring | `RetentionScorer` class | `score()`, `rank()`, `select_for_eviction()` |
| Staleness sweep | `GraphPromotionStore.staleness_sweep()` | Deprecates stale preferences |
| Deprecation sweep | `GraphPromotionStore.deprecation_sweep()` | Deletes deprecated preferences |
| Gated recall | `GraphPromotionStore.gated_recall()` | Only returns trusted/provisional |
| Belief snapshot | `GraphBeliefStore.snapshot()` | Lists all current beliefs |

**What's new**: wiring `RetentionScorer` to Neo4j graph + agent tools for eviction,
and building a multi-store agent that routes queries to the right memory type.

---

## Notebook 01: `01_retention_and_decay.ipynb`

### Objective

Wire the existing `RetentionScorer` to the Neo4j graph and give the agent tools
to manage bounded memory — scoring beliefs, evicting low-value ones, and explaining
why each belief was kept or dropped.

### Builds On

- `RetentionScorer` (Module 3, lifecycle_utils.py) — scoring weights, eviction selection
- `GraphBeliefStore` (Module 3.4) — `snapshot()`, `store()`, SCD Type 2
- `GraphPromotionStore` (Module 3.3) — `staleness_sweep()`, `deprecation_sweep()`

### New in `lifecycle_utils.py`

```python
# Add to GraphBeliefStore or new class:
async def score_beliefs(self, scorer: RetentionScorer) -> list[dict]:
    # Score all current beliefs using RetentionScorer weights.
    # Returns: [{category, preference, score, breakdown: {recency, frequency, ...}}]

async def evict(self, scorer: RetentionScorer, count: int = None) -> list[dict]:
    # Evict lowest-scoring beliefs. Returns list of evicted beliefs with reasons.
    # Marks beliefs as superseded with valid_to = now, reason = "retention_eviction"
```

### Agent Tools

| Tool | Purpose |
|------|---------|
| `remember_belief` | Same as 3.4 — store preference |
| `recall_current_beliefs` | Same as 3.4 — retrieve current beliefs |
| `show_retention_scores` | Show all beliefs ranked by retention score with breakdown |
| `run_memory_cleanup` | Evict N lowest-scoring beliefs, return what was dropped and why |

### Demo Flow (6 turns)

1. **Populate** — Agent stores 15+ beliefs across categories (home_city, hotel, airline,
   diet, seat, airport, budget_tier, meal_time, loyalty_program, rental_car, etc.)
2. **Score** — User asks "How valuable is each of my preferences?"
   → Agent calls `show_retention_scores` → ranked list with breakdown
3. **Explain** — User asks "Why is my rental car preference scored so low?"
   → "Stored 6 months ago, never accessed, no confirmations, low specificity"
4. **Evict** — User says "Clean up my preferences, keep only the important ones"
   → Agent calls `run_memory_cleanup(count=5)` → drops 5 lowest-scoring beliefs
5. **Verify** — `recall_current_beliefs` shows reduced set; evicted ones are gone
6. **Audit** — `belief_history` for an evicted category shows it was superseded with
   reason "retention_eviction" — the eviction is recorded, not silently deleted

### Scoring Formula (from existing RetentionScorer)

```
score = w_age × recency_decay
      + w_freq × access_frequency
      + w_success × success_correlation
      + w_redundancy × (1 - redundancy_penalty)
      + w_specificity × specificity_score
```

### 📄 Reference Papers

**"Are We Ready For An Agent-Native Memory System?"** (arXiv:2606.24775)
> Localized maintenance is more cost-efficient than global reorganization.
> Our per-belief scoring aligns with this — evict individually, not batch-wipe.

**"Less Context, More Accuracy"** (arXiv:2606.09900)
> Lean retrieved context outperforms full history. Retention ensures the recall
> set stays lean by proactively dropping low-value entries.

---

## Notebook 02: `02_memory_routing.ipynb`

### Objective

Build a single agent with access to all four memory types (chat history, episodic,
semantic/graph, procedural/skills). The LLM routes queries to the right store by
choosing which tools to call — no separate MemoryRouter class needed.

### Builds On

- `create_baseline_agent()` — factory with `extra_tools`, `context_providers`, `middleware`
- Episodic memory (Module 2.2) — Cosmos DB event store
- Semantic memory (Module 2.3) — Neo4j graph (preferences + beliefs)
- Procedural memory (Module 2.4) — `SkillsProvider` for travel booking skills
- Chat history (Module 2.1) — `AgentSession` + `CompactionProvider`

### Agent Tools (multi-store)

| Tool | Store | Query Type |
|------|-------|-----------|
| `recall_current_beliefs` | Neo4j (semantic) | "What hotel do I prefer?" |
| `recall_past_events` | Cosmos DB (episodic) | "What happened on my last trip?" |
| `search_policies` | AI Search (procedural) | "What's the international booking process?" |
| `search_flights`, `search_hotels` | Local data | Operational queries |
| `remember_belief` | Neo4j (semantic) | Store new preferences |

Chat history is implicit via `AgentSession` + `CompactionProvider`.

### Demo Flow (5 turns)

1. **Semantic query** — "What hotel chain do I prefer?"
   → Agent calls `recall_current_beliefs` → Neo4j
2. **Episodic query** — "What happened on my trip to Chicago last month?"
   → Agent calls `recall_past_events` → Cosmos DB
3. **Procedural query** — "How do I book an international flight?"
   → Agent picks up skills from `SkillsProvider` → AI Search
4. **Compound query** — "Book me a hotel in Tokyo based on my usual preferences"
   → Agent calls `recall_current_beliefs` (preferences) THEN `search_hotels` (availability)
5. **Chat reference** — "What did I just ask about?"
   → Answered from `AgentSession` chat history (no tool call needed)

### Key Insight: The LLM Is the Router

There is no `MemoryRouter` class with `if classification == "factual"` logic.
The agent's system prompt describes each tool's purpose, and the LLM's tool-calling
capability naturally routes queries to the right store. This is the simplest correct
implementation — adding a classifier in front of the LLM is redundant.

### 📄 Reference Paper

**"Are We Ready For An Agent-Native Memory System?"** (arXiv:2606.24775)
> No single memory architecture dominates across all scenarios — effectiveness
> depends on how well memory structure aligns with workload. Our multi-tool
> approach lets the LLM match query type to the right store naturally.

---

## Prerequisites

- Module 2 (all four memory stores operational)
- Module 3 (lifecycle management — retention scoring, belief store)
- Module 4 (confidence-aware recall for ranking)
- Cosmos DB, Neo4j, AI Search provisioned

## Outputs for Later Modules

- Multi-store agent → foundation for Module 09 (multi-agent handoff)
- Retention eviction → used by Module 08 (evaluation — measure what's lost)
- Routing patterns → used by Module 10 (unified agent)

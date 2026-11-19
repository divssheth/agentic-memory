# 05 Retrieval & Routing — Implementation Plan

## Module Narrative

> "The agent has memory. Now it must know what to retrieve and where to look."

Modules 2–4 established four memory types, lifecycle management, and
confidence-aware recall. This module turns those capabilities into a bounded
retrieval path and gives one Microsoft Agent Framework (MAF) agent access to
the appropriate store for each request.

This module does **not** implement retention again. Module 3 already provides
`RetentionScorer` and `CosmosRetentionStore`; retention remains a scheduled
maintenance process. Here, lifecycle metadata controls which memories are
eligible to enter an agent's context.

Maps to: FR-008 (Retrieval), FR-009 (Routing), FR-013 (Bounded Context).

---

## Status: 🔨 TO IMPLEMENT

---

## Already Built

| Capability | Where | How Module 5 Uses It |
|------------|-------|----------------------|
| Vector retrieval | `SemanticMemoryStore.search()` | DiskANN candidate retrieval scoped by `/user_id` |
| Access tracking | `SemanticMemoryStore.search(track_access=True)` | Updates frequency and recency signals after recall |
| Trust gating | `CosmosPromotionStore.gated_recall()` | Excludes candidate and deprecated memories |
| Belief revision | `CosmosBeliefStore` | Excludes superseded versions from current recall |
| Retention scoring | `RetentionScorer`, `CosmosRetentionStore` | Scheduled scoring/deprecation keeps the serving set bounded |
| Provenance and confidence | `CosmosProvenanceStore` | Controls assert, hedge, ask, or withhold behavior |

**What's new:** composing these signals into a retrieval policy and exposing
all memory types as clearly described tools so the MAF agent can route requests.

---

## Notebook 01: `01_retrieval_and_ranking.ipynb`

### Objective

Compare naive vector-only retrieval with lifecycle-aware retrieval. A high
similarity score alone is insufficient: a result may be superseded, untrusted,
deprecated, outside the user's partition, or too low-value to spend context on.

### Retrieval Pipeline

```mermaid
flowchart LR
    Q[User query] --> V[Cosmos DiskANN search]
    V --> U[User and scope boundary]
    U --> C[Current versions only]
    C --> T[Trust-state gate]
    T --> R[Rank by relevance and confidence]
    R --> B[Bounded top-k context]
    B --> A[MAF agent]
```

The canonical implementation remains `SemanticMemoryStore.search()` with
explicit options rather than a second storage abstraction:

```python
results = await semantic_store.search(
    query,
    top_k=5,
    current_only=True,
    states=["trusted", "provisional"],
    track_access=True,
)
```

### Demo Flow

1. Seed current, superseded, candidate, trusted, provisional, and deprecated
   memories, including deliberately similar text.
2. Run an unrestricted diagnostic search to show why vector similarity alone
   returns unsafe or stale candidates.
3. Run lifecycle-aware recall and verify only current trusted/provisional
   records enter context.
4. Show confidence-aware presentation: assert, hedge, ask, or withhold.
5. Apply a strict `top_k` and compare context size without changing storage.
6. Verify successful recall increments `access_count` and `last_accessed` for
   future scheduled retention scoring.

### Key Insight: Retrieval Is Policy, Not Just Similarity

Vector search answers "what looks related?" Lifecycle-aware retrieval also asks
"is it current, trusted, authorized, useful, and worth the context budget?"

This notebook bounds the number of returned memories. Token-aware packing and
clustered memory compression are future optimizations, not claims of this module.

---

## Notebook 02: `02_memory_routing.ipynb`

### Objective

Build one MAF agent with access to session, episodic, semantic, procedural, and
policy knowledge. The LLM routes by selecting well-described tools; there is no
separate classifier or `MemoryRouter` class.

### Memory Surfaces

| Surface | Tool or Provider | Example Question |
|---------|------------------|------------------|
| Session history | `AgentSession` | "What did I just ask?" |
| Episodic memory | `recall_past_events` | "What happened on my last trip?" |
| Semantic memory | `recall_current_beliefs` | "Which hotel chain do I prefer?" |
| Procedural memory | `SkillsProvider` | "How should an international trip be booked?" |
| Policy grounding | `search_travel_policies` | "What is my hotel limit?" |
| Operational data | `search_flights`, `search_hotels` | "What can I book?" |

All persistent personal-memory tools are constructed with a fixed `user_id`;
the model never supplies or changes the Cosmos partition key.

### Demo Flow

1. Ask a semantic preference question and verify only the semantic tool runs.
2. Ask about a prior trip and verify episodic recall runs.
3. Ask for a booking procedure and verify the relevant skill is loaded.
4. Ask a policy question and verify Azure AI Search supplies grounded content.
5. Ask a compound booking question that requires semantic preferences, policy,
   and operational availability.
6. Ask a current-conversation question answered by `AgentSession` without a
   persistent-memory tool call.
7. Repeat a query under a second `user_id` and verify no cross-partition result
   reaches the agent.

### Key Insight: The LLM Is the Router

Tool schemas describe what each memory surface knows. MAF tool selection handles
single-store and compound queries without duplicating the model with a brittle
front-door classifier.

---

## Validation Criteria

| Check | Expected Result |
|-------|-----------------|
| Superseded memory | Never appears in current recall |
| Candidate/deprecated memory | Never enters agent context |
| Provisional memory | Returned with hedge/confirmation behavior |
| Context bound | No more than configured `top_k` memories |
| Access tracking | Recalled records increment access metadata |
| Store routing | Each query invokes the expected memory tool(s) |
| Compound routing | Agent combines stores without treating policy as preference |
| User isolation | A second `/user_id` partition returns no first-user memories |

---

## Reference Papers

**"Are We Ready For An Agent-Native Memory System?"** (arXiv:2606.24775)
> Memory structure should align with workload. Specialized tools let the agent
> select the appropriate memory surface for each request.

**"Less Context, More Accuracy"** (arXiv:2606.09900)
> Lean retrieved context can outperform full history. Lifecycle gates and a
> bounded result set prevent stale or low-value memories from filling context.

---

## Prerequisites

- Module 2 memory layers: session, episodic, semantic, and procedural
- Module 3 Cosmos lifecycle stores and retention scoring
- Module 4 provenance and confidence-aware recall
- Cosmos DB, Azure AI Search, Azure AI Foundry, and MAF configuration

## Outputs for Later Modules

- Lifecycle-aware retrieval tools → Module 6 governance and Module 8 evaluation
- Multi-store routing pattern → Module 9 handoff and Module 10 unified agent
- Retrieval traces → Module 8 routing and stale-memory metrics
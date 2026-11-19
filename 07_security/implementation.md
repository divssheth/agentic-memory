# 07 Security — Implementation Plan

## Module Narrative

> "Persistent memory and destructive memory operations are both security boundaries."

A poisoned write can influence future sessions. An unauthorized erase can
silently remove trusted user data. This module attacks both boundaries and then
adds enforcement that does not depend on the model following instructions.

Maps to: FR-016 (Cross-User Isolation), FR-017 (Memory Poisoning Detection),
FR-018 (Sensitive Data).

---

## Status: 🔨 TO IMPLEMENT

## Already Built

| Capability | Source |
|------------|--------|
| Candidate → provisional → trusted lifecycle | `CosmosPromotionStore` |
| Current and historical belief versions | `CosmosBeliefStore` |
| Source and confidence metadata | `SemanticMemoryStore`, `CosmosProvenanceStore` |
| User partition boundary | Cosmos `/user_id` partition key |
| Retirement and verified erasure contract | Module 6 |

---

## Notebook 01: `01_attack_surface.ipynb`

### Objective

Demonstrate how untrusted input can create durable memories or attempt durable
deletion. Each attack is replayed in a fresh `AgentSession` to prove persistence.

### Attack Channels

| Channel | Write Attack | Destructive Attack |
|---------|--------------|--------------------|
| Social engineering | User frames an unsupported budget claim as fact | User requests erasure outside their bound scope |
| Tool output injection | Tool metadata tells the agent to store a preference | Tool output tells the agent to call `erase_memory` |
| Summary laundering | Injected instruction survives compaction | Compacted text presents an old deletion request as current authorization |
| Cross-agent request | Another agent supplies an unverified belief | Another agent attempts to retire or erase a category it cannot govern |

### Demo Pattern

1. Deliver the attack through a normal agent conversation or tool response.
2. Inspect the Cosmos record, source metadata, and lifecycle state.
3. Start a fresh session and test whether the poisoned value reaches context.
4. Attempt the destructive action and inspect its authorization outcome.

No attack may use a caller-provided `user_id`; stores and governance tools are
bound to authenticated application context.

---

## Notebook 02: `02_defense_in_depth.ipynb`

### Objective

Compose write-time origin binding, staged trust, independent corroboration,
scoped tools, and explicit user authorization. Replay Notebook 01 and measure
both blocked attacks and false positives.

### Cosmos Security Metadata

```python
ORIGIN_CEILINGS = {
    "user_assertion": 0.95,
    "user_correction": 1.0,
    "llm_inference": 0.70,
    "tool_output": 0.30,
    "compaction_derived": 0.25,
}
```

Memory documents add non-content lineage fields such as `source_type`,
`source_id`, and `origin_session_id`. Confirmations carry their own source and
session identifiers. Cosmos patch operations update counters and states without
letting the model construct database queries.

### Defense Layers

| Layer | Enforcement |
|-------|-------------|
| Staged promotion | Unverified writes remain candidates |
| Gated retrieval | Candidate/deprecated records never reach context |
| Origin ceiling | Untrusted channels cannot promote themselves to authority |
| Independent corroboration | Confirmation must use a different trusted source/session |
| Fixed user binding | `/user_id` comes from authenticated context |
| Scoped governance tools | Agent roles expose only authorized categories and operations |
| Explicit erasure confirmation | Recalled text, tool output, and other agents cannot authorize erasure |
| Idempotency | Replayed erasure requests cannot widen scope or duplicate side effects |

### Erasure Security Rules

- `erase_memory` requires an authenticated user principal, precise scope, and
  explicit confirmation outside untrusted retrieved content.
- Authorization is checked before looking up the target, preventing existence
  disclosure across users or categories.
- Tombstones and repair records contain identifiers and outcomes only.
- Failed authorization creates no memory mutation and no content-bearing audit.
- A compromised projection adapter cannot mark the overall request complete;
  Module 6's coordinator returns `repair_required`.

### Security Drills

1. Replay all four poisoning channels and verify blocked candidates never enter context.
2. Inject an `erase_memory` instruction through tool output and compaction.
3. Attempt cross-user and cross-category erasure.
4. Replay a completed erasure request and verify idempotent outcomes.
5. Search tombstone/repair responses for the sensitive canary.
6. Verify unauthorized requests do not reveal whether the target exists.

### Scoreboard

| Metric | Target |
|--------|--------|
| Poisoning attack success | 0% |
| Unauthorized retirement/erasure | 0% |
| Cross-user existence disclosure | 0% |
| Tombstone content leakage | 0% |
| Legitimate memory false-positive block rate | <5% |

---

## Prerequisites

- Module 3 Cosmos promotion and revision
- Module 4 confidence and provenance
- Module 5 lifecycle-aware retrieval
- Module 6 governance and verified erasure

## Outputs for Later Modules

- Attack fixtures and enforcement traces → Module 8 evaluation
- Secured governance tools → Module 9 handoff and Module 10 capstone

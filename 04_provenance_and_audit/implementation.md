# 04 Provenance & Confidence — Implementation Plan

## Module Narrative

> "A usable memory must also be able to explain why it exists."

Module 03 completed the semantic-memory lifecycle:

- staged promotion decides whether a belief may influence the agent;
- belief revision decides which value is current and preserves older versions;
- retention decides which memories remain worth keeping.

One problem remains at the read boundary. `GraphPromotionStore.gated_recall()`
and `GraphBeliefStore.recall_current()` reduce a rich Neo4j node to a broad
state tag and its text:

```text
[KNOWN] Prefers Marriott
[LIKELY] Prefers morning flights
```

That output no longer says who or what created the memory, what evidence
supported it, when it was recorded, or its numeric confidence. The lifecycle
can answer *"may I use this?"* and *"which value is current?"*, but the agent
cannot reliably answer *"why do you believe this?"* or choose language that
reflects the strength of the evidence.

Module 04 solves that specific gap. It preserves provenance and confidence
through recall, exposes an explanation tool, and teaches the agent to assert,
hedge, or ask without changing the lifecycle rules from Module 03.

Maps to: FR-006 (Confidence Scoring), FR-013 (Audit Trail), FR-014 (Memory
Provenance).

---

## Status: 🧪 IMPLEMENTED — READY FOR USER TESTING

---

## What Provenance Means

**Provenance is the traceable origin and evidence chain of a memory.** It is
more than a label such as `user_assertion` or `llm_inference`. Useful provenance
answers:

1. **Who or what created it?** The user, an agent inference, a tool, or an
   enterprise source.
2. **Which evidence caused it?** For example, the exact user statement or the
   observation that three recent trips departed before 9 AM.
3. **When was it recorded?** The first-seen timestamp and later confirmation
   timestamps.
4. **How was it validated?** Confirmation count and lifecycle state.
5. **How did it change?** The lineage of superseded and current values.

These concepts are related but distinct:

| Concept | Question it answers |
|---|---|
| Provenance | Where did this memory come from, and what evidence supports it? |
| Confidence | How strongly should the system believe and communicate it? |
| Temporal history | How did the value change over time? |
| Trust state | Is the memory currently allowed to influence the agent? |

Persisting this information prevents the model from inventing a plausible
reason after the fact. It also gives users a basis for trusting, correcting, or
rejecting a memory and gives developers an auditable path for debugging it.

---

## Separation from Module 03

Module 04 has its own focused utility:

```text
04_provenance_and_audit/lifecycle_utils.py
└── GraphProvenanceStore
```

This follows Module 03's primary-object-per-concept pattern
(`GraphPromotionStore`, `GraphBeliefStore`, `GraphRetentionStore`) without
adding provenance APIs to those teaching objects. `GraphProvenanceStore` reuses
the same Neo4j `Preference` schema and lifecycle semantics, but does not import
or modify Module 03's Python classes.

### `GraphProvenanceStore` operations

| Method | Purpose |
|---|---|
| `store()` | Persist a belief together with source, evidence, creator, confidence, and timestamps |
| `confirm()` | Advance the established Module 03 trust state for the demo |
| `recall_baseline()` | Reproduce Module 03's state-tagged but provenance-lossy projection |
| `recall_with_confidence()` | Return visible beliefs with structured provenance and presentation strategy |
| `explain()` | Return the current belief's origin, evidence, validation, and compact lineage |
| `snapshot()` | Inspect persisted records during the notebook |
| `reset()` | Remove only the selected user's Module 04 demo records |

---

## Notebook: `01_provenance_and_confidence.ipynb`

### Objective

Extend the existing travel agent with two capabilities:

1. **Explain a belief** — answer "Why do you believe X?" from persisted
   provenance rather than generated rationale.
2. **Communicate uncertainty** — assert, hedge, or ask according to both the
   lifecycle state and numeric confidence.

### Problem-First Flow

1. Recreate the output boundary left by Module 03 with `recall_baseline()`.
2. Show two visible beliefs whose very different evidence collapses to the same
   broad state-level output.
3. Ask why the agent believes one of them and show that the recall result does
   not contain enough information to answer safely.
4. Explain provenance and distinguish it from confidence, history, and trust.
5. Introduce structured recall and `explain_belief`.
6. Replay the scenario and show evidence-backed, confidence-aware responses.

### State Before Confidence

Confidence never bypasses the lifecycle gate established in Module 03:

| State | Confidence | Presentation |
|---|---:|---|
| `candidate` / `deprecated` | any | Withhold |
| `provisional` | `< 0.5` | Ask the user |
| `provisional` | `>= 0.5` | Hedge and seek confirmation |
| `trusted` | `>= 0.8` | Assert |
| `trusted` | `0.5–0.79` | Hedge |
| `trusted` | `< 0.5` | Ask the user |

### Agent Tools

| Tool | Purpose |
|---|---|
| `remember_belief` | Store the value and the evidence that caused it |
| `confirm_belief` | Record a later user confirmation |
| `recall_beliefs` | Return visible beliefs with assert/hedge/ask annotations |
| `explain_belief` | Format only persisted origin, evidence, timestamps, confidence, confirmation, and lineage |

### Continuation Demo

1. A direct Marriott statement is high confidence but begins `provisional`, so
   it is hedged according to Module 3.3's anti-spoofing rule.
2. A later reaffirmation promotes Marriott to `trusted`, allowing an assertion.
3. A morning-flight pattern is stored as a medium-confidence inference with
   concrete evidence. It begins as `candidate` and remains hidden.
4. After confirmation it becomes `provisional`, so it is visible but hedged.
5. A low-confidence visible belief causes a clarification question.
6. "Why?" questions produce different explanations for direct statements and
   inferred patterns.
7. A revised value displays compact lineage, reusing Module 3.4 without
   reteaching SCD Type 2.

---

## Prerequisites

- Module 3.3 for staged trust and visibility semantics
- Module 3.4 for current values and temporal lineage
- The same Neo4j and Foundry configuration used in Module 03

## Outputs for Later Modules

- `explain_belief` can support user inspection and correction in Module 06.
- Confidence-aware recall can support evaluation in Module 08.
- Persisted evidence can support origin-based security controls in Module 07.

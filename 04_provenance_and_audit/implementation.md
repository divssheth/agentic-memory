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

Module 04 solves that specific gap by enriching the existing Module 03 nodes
with evidence metadata. It does not create a parallel set of memories. It
preserves provenance and confidence through recall, exposes an explanation
tool, and teaches the agent to assert, hedge, or ask without changing the
lifecycle rules from Module 03.

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

## Built Directly on Module 03

Module 04 has its own focused utility:

```text
04_provenance_and_audit/lifecycle_utils.py
└── GraphProvenanceStore
```

This follows Module 03's primary-object-per-concept pattern
(`GraphPromotionStore`, `GraphBeliefStore`, `GraphRetentionStore`) without
adding provenance APIs to those teaching objects. `GraphProvenanceStore` reads
the same Neo4j `Preference` nodes, attaches evidence metadata to them, and
preserves their lifecycle state, confidence, and temporal history.

### `GraphProvenanceStore` operations

| Method | Purpose |
|---|---|
| `prerequisite_count()` | Verify that Module 03 lifecycle memories exist |
| `enrich()` | Attach source evidence and creator metadata to an existing current memory |
| `recall_baseline()` | Reproduce Module 03's state-tagged but provenance-lossy projection |
| `recall_with_confidence()` | Return visible beliefs with structured provenance and presentation strategy |
| `explain()` | Return the current belief's origin, evidence, validation, and compact lineage |
| `snapshot()` | Inspect the existing lifecycle records during the notebook |
| `clear_provenance()` | Remove only enrichment properties without deleting memories |

---

## Notebook: `01_provenance_and_confidence.ipynb`

### Objective

Extend the existing travel agent with two capabilities:

1. **Explain a belief** — answer "Why do you believe X?" from persisted
   provenance rather than generated rationale.
2. **Communicate uncertainty** — assert, hedge, or ask according to both the
   lifecycle state and numeric confidence.

### Problem-First Flow

1. Verify that Module 03 lifecycle memories exist for the selected user.
2. Reproduce Module 03's output boundary with `recall_baseline()` over those
   existing nodes.
3. Ask why the agent believes one of them and show that the projection does not
   contain enough information to answer safely.
4. Explain provenance and distinguish it from confidence, history, and trust.
5. Enrich the same nodes with the evidence from the Module 03 interactions.
6. Recall and explain those nodes through a structured, confidence-aware view.

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
| `recall_beliefs` | Return visible beliefs with assert/hedge/ask annotations |
| `explain_belief` | Format only persisted origin, evidence, timestamps, confidence, confirmation, and lineage |

### Continuation Demo

1. Module 03's hotel and home-city memories are recalled without provenance.
2. `enrich()` attaches the known statements from the earlier notebook to those
   same nodes.
3. An invariant check proves the preference count did not change.
4. Structured recall applies assert/hedge/ask using the existing state and
   confidence values.
5. "Why?" questions use only the attached evidence.
6. A memory without attached evidence remains explicitly unexplained.
7. The home-city explanation reuses Module 3.4's revision lineage without
   creating another revision.

---

## Prerequisites

- Module 3.3 for staged trust and visibility semantics
- Module 3.4 for current values and temporal lineage
- The same Neo4j and Foundry configuration used in Module 03
- Module 03 must be executed first; the notebook fails fast if no lifecycle
   memories exist for the selected user

## Outputs for Later Modules

- `explain_belief` can support user inspection and correction in Module 06.
- Confidence-aware recall can support evaluation in Module 08.
- Persisted evidence can support origin-based security controls in Module 07.

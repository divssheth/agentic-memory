# 05 Retrieval — Implementation Plan

## Module Narrative

> "Retrieve the RIGHT memory at the right time with the right confidence."

With memory stored (02), lifecycle managed (03), and provenance tracked (04), this module focuses on the retrieval problem: given a user query, how does the agent decide WHICH memory store to query, and how does confidence influence what gets surfaced?

This module addresses retrieval routing across memory types and confidence-weighted ranking at query time.

---

## Status: 🔨 TO IMPLEMENT

---

## Notebook: `01_memory_router.ipynb`

### Objective

Build a memory router that determines which memory stores to query based on the nature of the user's request. Not every query needs all four memory types.

### Key Concepts

- Query classification: factual (→ semantic), temporal (→ episodic), procedural (→ skills), conversational (→ chat history)
- Multi-store queries: some questions require combining results from multiple stores
- Hierarchical retrieval: summary first, drill down to details if needed
- Cost-aware routing: don't query expensive stores for simple questions

### Implementation Steps

1. Build `MemoryRouter` that classifies incoming queries:
   ```
   "What hotel does Sarah prefer?" → semantic memory (knowledge graph)
   "What happened on her last trip?" → episodic memory (event store)
   "How do I book international flights?" → procedural memory (skills)
   "What did we discuss earlier?" → chat history
   "Book Sarah a hotel in NYC" → semantic (preferences) + procedural (booking steps)
   ```
2. Implement routing strategies:
   - **Single-store**: query only the most relevant store
   - **Fan-out**: query multiple stores, merge results
   - **Hierarchical**: query summary layer first, drill down if insufficient
3. Build result merging logic:
   - Deduplicate overlapping results
   - Rank by confidence × relevance × recency
   - Present with source attribution ("From your past trips..." vs "Based on your preferences...")
4. Demo: same query answered differently based on what's available in each store
5. Show cost comparison: fan-out (expensive, thorough) vs single-store (cheap, focused)

### Code Pattern

```python
class MemoryRouter:
    async def route(self, query: str, context: ConversationContext) -> RoutingPlan:
        """Determine which memory stores to query and in what order."""
        classification = await self.classify_query(query)

        if classification.type == "factual":
            return RoutingPlan(primary=MemoryStore.SEMANTIC, fallback=MemoryStore.EPISODIC)
        elif classification.type == "temporal":
            return RoutingPlan(primary=MemoryStore.EPISODIC)
        elif classification.type == "procedural":
            return RoutingPlan(primary=MemoryStore.PROCEDURAL)
        elif classification.type == "compound":
            return RoutingPlan(stores=classification.relevant_stores, strategy="fan_out")

    async def retrieve(self, query: str) -> list[RankedMemory]:
        """Route query and merge results with confidence-weighted ranking."""
        plan = await self.route(query)
        results = await self.execute_plan(plan, query)
        return self.rank_and_merge(results)
```

### 📄 Reference Paper

**"Are We Ready For An Agent-Native Memory System?"** (arXiv:2606.24775)

Authors: Zhou, Zhou, Han, Xu, Li, Li, Xiong, Wu (Jun 2026)

> Systematic experimental study decomposing agent memory into 4 core modules: representation/storage, extraction, retrieval/routing, and maintenance. Evaluates 12 representative memory systems across 5 benchmark workloads spanning 11 datasets. Key finding: **no single architecture dominates across all scenarios; effectiveness depends on how well memory structure aligns with workload bottleneck**. Localized maintenance is more cost-efficient than global reorganization. **Relevant here**: validates that routing is critical — the router must match query type to the right memory architecture.

---

## Notebook: `02_confidence_weighted_retrieval.ipynb`

### Objective

Implement retrieval that uses confidence scores (from Module 04) to influence ranking, presentation, and agent behaviour — surfacing high-confidence memories as facts and low-confidence ones as questions.

### Key Concepts

- Confidence-weighted ranking: don't just sort by relevance; factor in trust level
- Presentation strategy: assert (high), hedge (medium), ask (low), suppress (very low)
- Retrieval-time confidence adjustment: stored confidence × recency decay × query relevance
- Reflective loop: if initial retrieval is low-confidence, try broader/alternative queries

### Implementation Steps

1. Build `ConfidenceWeightedRetriever`:
   - Retrieve candidates by relevance (embedding similarity / graph traversal)
   - Adjust scores by retrieval-time confidence (from 04_confidence_scoring)
   - Apply presentation strategy based on final score
2. Implement reflective retrieval loop:
   - First attempt: standard retrieval
   - If all results < confidence threshold: broaden query (remove constraints)
   - If still insufficient: flag for user clarification rather than guessing
3. Demo scenario:
   - Query: "What's Sarah's dietary preference?"
   - Result A: "Vegetarian" (confidence 0.92, confirmed 4 times) → assert
   - Result B: "Avoids gluten" (confidence 0.45, inferred once) → hedge/ask
   - Agent says: "Sarah is vegetarian. I also have a note she may avoid gluten — should I filter for gluten-free options too?"
4. Show failure mode: what happens WITHOUT confidence weighting (agent asserts uncertain facts)
5. Compare strategies: always-assert vs confidence-aware vs always-ask

### Code Pattern

```python
class ConfidenceWeightedRetriever:
    async def retrieve(self, query: str, user_id: str) -> list[PresentableMemory]:
        candidates = await self.raw_retrieve(query, user_id)

        results = []
        for memory in candidates:
            confidence = self.confidence_calculator.compute_retrieval_confidence(memory)
            presentation = self.determine_presentation(confidence)
            results.append(PresentableMemory(
                content=memory.content,
                confidence=confidence,
                presentation=presentation,  # "assert" | "hedge" | "ask" | "suppress"
                source_attribution=memory.provenance.source_type
            ))

        return sorted(results, key=lambda r: r.confidence.composite, reverse=True)

    def determine_presentation(self, confidence: ConfidenceScore) -> str:
        if confidence.composite >= 0.85:
            return "assert"
        elif confidence.composite >= 0.55:
            return "hedge"
        elif confidence.composite >= 0.30:
            return "ask"
        else:
            return "suppress"
```

### 📄 Reference Paper

**"Less Context, More Accuracy: A Bi-Temporal Memory Engine for LLM Agents Where a Lean Retrieved Context Beats the Full History"** (arXiv:2606.09900)

Authors: Wang (Jun 2026)

> Shows that a lean, curated retrieval context outperforms dumping full history into the prompt. The bi-temporal engine maintains temporal validity and retrieves only currently-relevant facts. Key finding: **quality of retrieved context matters more than quantity** — aligns with confidence-weighted approach where we suppress low-confidence memories rather than surfacing everything.

---

## Prerequisites

- Module 02 (all four memory stores operational)
- Module 04 (confidence scoring and provenance available)

## Outputs for Later Modules

- `MemoryRouter` → used by 09_multi_agent for routing in multi-agent handoff
- Confidence-weighted retrieval → used by 08_evaluation for measuring retrieval quality
- Presentation strategies → used by 06_governance (user control interface)

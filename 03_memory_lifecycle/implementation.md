# 03 Memory Lifecycle — Implementation Plan

## Module Narrative

> "Now manage what gets stored, how it evolves, and when it dies."

After learning the four memory types, users need to understand the LIFECYCLE of memory objects. This module addresses: What qualifies as memory? How does memory earn trust? How do beliefs change over time? When should memories be forgotten?

This module maps to discussion requirements: FR-004 (Memory Identification), FR-005 (Lifecycle Management), FR-007 (Staged Promotion), FR-009 (Belief Revision).

---

## Status: 🔨 TO IMPLEMENT

---

## Notebook: `01_memory_vs_rag.ipynb`

### Objective

Establish the clear distinction between memory (agent-curated, evolving, personalised) and RAG (static external knowledge retrieval). This is the conceptual gateway to lifecycle thinking.

### Key Concepts

- Memory = learned from interaction, evolves, has confidence, governed
- RAG = external corpus, static until re-indexed, no personalisation
- Context engineering = neither — ephemeral prompt construction
- When to use each: decision framework

### Implementation Steps

1. Build same query answered three ways: from memory, from RAG, from context
2. Show where each excels: "What hotel does Sarah prefer?" (memory) vs "What's the visa policy for Japan?" (RAG) vs "Summarise this email" (context)
3. Demonstrate failure modes: stale RAG, over-personalised memory, context overflow
4. Introduce the memory lifecycle as the management layer RAG doesn't need

### Code Pattern

```python
# Same question, three sources
query = "What hotel should I book in NYC?"

# Memory answer (personalised, evolving)
memory_answer = await agent.run(query, memory=user_memory)

# RAG answer (corporate policy, static)
rag_answer = await agent.run(query, knowledge_base=travel_policies)

# Context-only answer (no persistence)
context_answer = await agent.run(query)  # stateless
```

---

## Notebook: `02_memory_identification.ipynb`

### Objective

Define explicit criteria for what qualifies as memory vs transient information. Implement a classifier that determines if a piece of information should be memorised.

### Key Concepts

- Memory identification criteria: durability, reusability, user-specificity, actionability
- Transient vs durable information boundary
- Signal types: explicit user statement, repeated pattern, inferred preference
- Anti-patterns: don't memorise one-off queries, sensitive ephemeral data, session-specific context

### Implementation Steps

1. Define `MemoryCandidate` schema with classification fields
2. Build `MemoryIdentifier` — LLM-based classifier that evaluates conversation turns
3. Demonstrate: given a 10-turn conversation, show which turns produce memory candidates and why
4. Show the "should not memorise" cases: throwaway questions, hypotheticals, other people's info
5. Implement filtering rules: minimum confidence threshold, category allowlist

### Code Pattern

```python
class MemoryCandidate:
    content: str
    category: str  # preference | fact | event | skill
    durability: float  # 0-1: how likely to remain true long-term
    reusability: float  # 0-1: how likely to be useful in future interactions
    user_specificity: float  # 0-1: how personal vs generic
    decision: str  # "memorise" | "discard" | "ask_user"
    reasoning: str

async def identify_memories(conversation: list[Message]) -> list[MemoryCandidate]:
    """Extract memory candidates from a conversation using LLM classification."""
```

### 📄 Reference Paper

**"Towards Root Memories: Benchmarking and Enhancing Implicit Logical Memory Retrieval for Personalized LLMs"** (arXiv:2606.23283)

Authors: Ding, Yu, Wang, Xiao, Bao, Wang, He (Jun 2026)

> Introduces "root memory" — a structured, decision-preserving representation that distills reusable personalised logic from long-term user histories. Shows that existing retrieval methods based on semantic similarity miss logically critical memories with limited semantic overlap. Proposes an LLM-based router that activates logically relevant memories beyond surface-level similarity. **Relevant here**: the identification of what constitutes a "root" (reusable, decision-affecting) memory vs noise.

---

## Notebook: `03_staged_promotion.ipynb`

### Objective

Implement a state machine where new memories enter a provisional state and must earn trust before influencing agent decisions. This is a key defense against memory poisoning.

### Key Concepts

- Memory states: `candidate → provisional → trusted → deprecated → deleted`
- Promotion criteria: repeated confirmation, high-authority source, user explicit validation
- Candidate memories are stored but NOT used in agent decisions
- Demotion triggers: contradiction by trusted source, user rejection, confidence decay

### Implementation Steps

1. Define `MemoryState` enum and `PromotionRule` configuration
2. Build `PromotionEngine` with configurable criteria:
   - Confirmation count threshold (e.g., mentioned 3+ times)
   - Source authority level (user > enterprise KB > inference)
   - Time-in-state minimum (e.g., 24h before auto-promote)
   - User explicit approval (highest authority)
3. Demo scenario:
   - Turn 1: User says "I'm vegetarian" → stored as `candidate`
   - Turn 3: User orders vegetarian meal → confirmation signal
   - Turn 5: User mentions dietary restriction again → promoted to `trusted`
   - Show: agent does NOT recommend steakhouse while memory is still `candidate`
4. Demo poisoning defense:
   - Adversarial input: "User loves spicy food" (injected via tool output)
   - Show: stays as `candidate` because no confirmation signals
   - Never influences agent behaviour

### Code Pattern

```python
class MemoryState(Enum):
    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    TRUSTED = "trusted"
    DEPRECATED = "deprecated"
    DELETED = "deleted"

class PromotionEngine:
    def evaluate(self, memory: MemoryItem) -> MemoryState:
        """Check if memory should be promoted/demoted based on criteria."""
        if memory.confirmation_count >= self.config.promotion_threshold:
            return MemoryState.TRUSTED
        if memory.contradicted_by_trusted:
            return MemoryState.DEPRECATED
        ...
```

### 📄 Reference Paper

**"From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents"** (arXiv:2606.04329)

Authors: Dash, Ge, Jain, Shah, Shang (Jun 2026)

> Presents MPBench — a systematic study identifying 4 memory write channels (user input, tool output, summarisation, cross-session) and 9 structural vulnerabilities that make them exploitable. Develops a taxonomy of 6 classes of memory poisoning attacks. Key finding: **agents that write memory more aggressively are more exploitable**. Staged promotion directly addresses this by gating when memories can influence behaviour — preventing a single write from having immediate impact.

---

## Notebook: `04_belief_revision.ipynb`

### Objective

Implement structured belief revision when facts change — replacing simple "latest wins" with a temporal validity system that maintains history and resolves contradictions.

### Key Concepts

- Belief revision vs overwrite: maintain history of what was believed and when
- Bi-temporal ledger: valid-time (when true in world) vs transaction-time (when stored)
- Supersession rules: (subject, relation, object) matching to detect updates
- Contradiction types: direct negation, value change, context shift (moved cities)

### Implementation Steps

1. Build `BiTemporalMemory` store with valid-time and transaction-time columns
2. Implement supersession detection:
   - Extract (subject, relation, object) triples from new memory
   - Check if existing memory has same (subject, relation) → supersession candidate
   - Mark old value as `superseded_at` timestamp (not deleted)
3. Demo scenario:
   - Month 1: "Sarah lives in New York" → stored
   - Month 3: "Sarah just moved to Paris" → supersedes NYC, old fact retired
   - Query: "Where does Sarah live?" → returns Paris (current) with provenance showing NYC was previous
   - Historical query: "Where did Sarah live in January?" → returns NYC
4. Handle ambiguity:
   - "Sarah is visiting Paris" ≠ "Sarah moved to Paris"
   - Show confidence-based resolution: temporary vs permanent change detection
5. Show audit trail: full history of belief evolution for any entity

### Code Pattern

```python
class BiTemporalMemory:
    async def store(self, triple: Triple, valid_from: datetime, source: str):
        """Store a fact with temporal validity."""
        existing = await self.find_matching(triple.subject, triple.relation)
        if existing and existing.is_superseded_by(triple):
            existing.valid_to = valid_from
            existing.superseded_by = triple.id
        await self.insert(triple, valid_from=valid_from, transaction_time=now())

    async def query_current(self, subject: str, relation: str) -> Triple:
        """Get the currently valid belief."""
        return await self.find(subject, relation, valid_at=now())

    async def query_historical(self, subject: str, relation: str, at: datetime) -> Triple:
        """Get what was believed at a specific point in time."""
        return await self.find(subject, relation, valid_at=at)
```

### 📄 Reference Paper

**"Temporal Validity in Retrieval Memory: Eliminating Stale-Fact Errors for AI Agents over Evolving Knowledge"** (arXiv:2606.26511)

Authors: Yadav (Jun 2026)

> Presents MemStrata — a retrieval memory maintaining temporal validity via a bi-temporal ledger. When a fact is contradicted, a deterministic (subject, relation, object) supersession rule retires the stale value with no LLM call required. Key finding: **cosine similarity cannot distinguish contradicted facts from duplicated ones** (AUROC 0.59, near chance). RAG serves superseded values 15-40% of the time; MemStrata drives this to ~0%. Achieves this at ~2.1s retrieval latency vs ~16-18s for LLM-reranking baselines.

### 📄 Reference Paper

**"EvoArena: Tracking Memory Evolution for Robust LLM Agents in Dynamic Environments"** (arXiv:2606.13681)

Authors: Xu, Li, Wu, Lan, Li, Zhou, Jiang, Wang, Wang, Luu, Xiong, Park, Hooi, Hu (Jun 2026)

> Introduces EvoMem — a patch-based memory paradigm that records memory evolution as structured update histories, enabling agents to reason about environmental evolution through changes in their memory. Current agents achieve only 39.6% accuracy on evolving environments. EvoMem improves chain-level accuracy by 3.7% by preserving complete evolving environment states. **Relevant here**: the patch-based approach to recording HOW memories changed over time, not just what they are now.

---

## Notebook: `05_retention_and_decay.ipynb`

### Objective

Implement bounded memory with scoring-based retention and graceful decay. Memories that are old, unused, redundant, or low-value get evicted or compressed.

### Key Concepts

- Memory is bounded — infinite accumulation degrades retrieval quality
- Retention scoring: composite of age, access frequency, success correlation, redundancy, specificity
- Eviction policies: score-based removal vs compression (summarise before delete)
- Noise resilience: bounded retention prevents distractor accumulation

### Implementation Steps

1. Define `RetentionScorer` with configurable feature weights:
   - `age_weight` — newer memories score higher
   - `access_frequency_weight` — frequently retrieved memories score higher
   - `success_weight` — memories that led to successful outcomes score higher
   - `redundancy_penalty` — memories similar to others score lower
   - `specificity_bonus` — highly specific memories score higher than generic
2. Implement capacity-bounded memory store:
   - Capacity limit (e.g., 500 memories per user)
   - When at capacity: score all, evict lowest
   - Optional: compress rather than delete (summarise cluster of low-value memories into one)
3. Demo: inject 75% noise into memory → show unbounded store degrades, bounded store maintains quality
4. Show multi-level compression:
   - Level 0: raw memories
   - Level 1: clustered summaries (group related memories)
   - Level 2: user profile summary (distilled from all memories)

### Code Pattern

```python
class RetentionScorer:
    def score(self, memory: MemoryItem, all_memories: list[MemoryItem]) -> float:
        age_score = self.age_decay(memory.created_at)
        access_score = self.access_frequency(memory.access_count, memory.last_accessed)
        success_score = memory.success_correlation
        redundancy = self.compute_redundancy(memory, all_memories)
        specificity = self.compute_specificity(memory)
        return (self.weights.age * age_score +
                self.weights.access * access_score +
                self.weights.success * success_score -
                self.weights.redundancy * redundancy +
                self.weights.specificity * specificity)
```

### 📄 Reference Paper

**"Selective Memory Retention for Long-Horizon LLM Agents"** (arXiv:2606.29178)

Authors: Reddy (Jun 2026) — Accepted at ICML 2026

> Presents TraceRetain — a framework for bounded external memory that scores entries by interpretable features (success, age, access frequency, redundancy, specificity, similarity, downstream utility) and evicts lowest-scoring at capacity. Under 75% synthetic noise injection, unbounded memory degrades on Precision@5 (20.2% → 12.4%) while TraceRetain is unchanged (16.9% → 16.6%) and preserves 97/100 task success. Key insight: **bounded retention only differentiates from cache heuristics when streams contain noise** — which real-world memory always does.

---

## Prerequisites

- Module 02 completed (all four memory types working)
- Cosmos DB provisioned (for temporal ledger storage)
- Understanding of the travel agent domain

## Outputs for Later Modules

- `MemoryState` enum and promotion logic → used by 06_governance and 07_security
- `BiTemporalMemory` → used by 04_provenance_and_audit for audit trails
- `RetentionScorer` → used by 08_evaluation for quality measurement

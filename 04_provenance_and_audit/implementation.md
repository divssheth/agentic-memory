# 04 Provenance & Audit — Implementation Plan

## Module Narrative

> "Every memory must explain where it came from and how confident we are."

This module establishes the metadata infrastructure that all later modules depend on. Before you can govern memory (06), detect attacks (07), or evaluate quality (08), every memory item needs provenance (where it came from), an audit trail (what happened to it), and confidence scoring (how much to trust it).

This module maps to discussion requirements: FR-006 (Confidence Scoring), FR-013 (Audit Trail), FR-014 (Memory Provenance), FR-023 (Confidence Measurement).

---

## Status: 🔨 TO IMPLEMENT

---

## Notebook: `01_memory_provenance.ipynb`

### Objective

Attach provenance metadata to every memory write — answering "Why does the system believe X?" for any stored memory.

### Key Concepts

- Provenance = origin tracking: who created it, from what interaction, through what channel
- Source types: `user_assertion`, `enterprise_knowledge`, `llm_inference`, `tool_output`, `web_source`
- Source authority hierarchy: user explicit > enterprise KB > repeated observation > single inference
- Provenance is immutable — once recorded, cannot be altered (append-only)

### Implementation Steps

1. Define `ProvenanceRecord` schema:
   ```python
   class ProvenanceRecord:
       memory_id: str
       source_type: SourceType  # user_assertion | enterprise_kb | llm_inference | tool_output
       source_authority: float  # 0-1 based on type hierarchy
       created_by: str  # agent_id or user_id
       created_at: datetime
       source_interaction_id: str  # link to originating conversation/turn
       extraction_method: str  # "explicit_statement" | "entity_extraction" | "inference"
       raw_evidence: str  # the actual text that produced this memory
   ```
2. Modify existing memory write functions (from Module 02) to require provenance
3. Build `ProvenanceQuery` — given any memory, retrieve its complete origin story
4. Demo: trace a preference back to the exact conversation turn that created it
5. Show authority scoring: "User said 'I prefer Marriott'" (authority=0.95) vs "Agent inferred from booking history" (authority=0.6)

### Code Pattern

```python
async def remember_with_provenance(
    memory_content: str,
    source_type: SourceType,
    interaction_id: str,
    raw_evidence: str
) -> MemoryItem:
    """Store memory with full provenance metadata."""
    provenance = ProvenanceRecord(
        source_type=source_type,
        source_authority=AUTHORITY_HIERARCHY[source_type],
        created_by=current_agent_id,
        source_interaction_id=interaction_id,
        raw_evidence=raw_evidence
    )
    return await memory_store.write(memory_content, provenance=provenance)

# Later: "Why do we believe Sarah prefers Marriott?"
trail = await provenance_store.explain(memory_id="mem_xyz")
# Returns: "Created from user statement in session abc123, turn 4:
#           'I always stay at Marriott when traveling for work'"
```

---

## Notebook: `02_audit_trail.ipynb`

### Objective

Implement an append-only audit log that records every operation on every memory — creation, reads, updates, promotions, deletions — enabling full reconstruction of memory history.

### Key Concepts

- Audit log is append-only (immutable) — separate from the memory store itself
- Records ALL operations: create, read, update, promote, demote, delete
- Supports compliance queries: "What did we know about user X at time T?"
- Enables forensic analysis: detect suspicious patterns of memory manipulation

### Implementation Steps

1. Define `AuditEvent` schema:
   ```python
   class AuditEvent:
       event_id: str
       timestamp: datetime
       memory_id: str
       operation: str  # "create" | "read" | "update" | "promote" | "demote" | "delete"
       actor: str  # agent_id, user_id, or system_id
       reason: str  # why this operation occurred
       before_state: dict | None  # state before change
       after_state: dict | None  # state after change
       metadata: dict  # additional context
   ```
2. Build `AuditLogger` middleware that wraps all memory operations
3. Implement audit queries:
   - `get_history(memory_id)` — full lifecycle of one memory
   - `get_operations_by_actor(actor_id, time_range)` — what did this agent do?
   - `get_state_at_time(memory_id, timestamp)` — point-in-time reconstruction
   - `detect_anomalies(time_range)` — unusual patterns (bulk writes, rapid changes)
4. Demo: reconstruct the full journey of a memory from creation to current state
5. Show forensic use: detect that an agent made 50 memory writes in 1 second (anomaly)

### Code Pattern

```python
class AuditLogger:
    """Middleware that logs all memory operations to append-only store."""

    async def log(self, event: AuditEvent):
        """Write audit event — never modifiable after creation."""
        await self.audit_container.create_item(event.dict())

    async def explain_memory(self, memory_id: str) -> list[AuditEvent]:
        """Answer: Why does this memory exist and what happened to it?"""
        return await self.query(f"SELECT * FROM c WHERE c.memory_id = '{memory_id}' ORDER BY c.timestamp")

    async def point_in_time(self, memory_id: str, at: datetime) -> dict:
        """Reconstruct memory state at a specific timestamp."""
        events = await self.explain_memory(memory_id)
        state = {}
        for event in events:
            if event.timestamp > at:
                break
            state = event.after_state or state
        return state
```

### Storage Backend

- Azure Cosmos DB — separate container `memory-audit-log` (append-only, TTL configurable for compliance)
- Partition key: `/memory_id` for efficient per-memory queries

### 📄 Reference Paper

**"Towards Security-Auditable LLM Agents: A Unified Graph Representation"** (arXiv:2605.06812)

Authors: Li, Zhang, Zhai, Feng, Yang, Wang, Dou, Ji, Hu, Wu, Liu, Zou (May 2026)

> Proposes a unified graph representation for auditing LLM agent behaviour, capturing the complete execution trace including memory operations. Demonstrates that flat-log auditing misses causal relationships between agent actions. **Relevant here**: the audit trail should capture not just WHAT happened but the causal chain (which conversation turn → which extraction → which memory write → which later retrieval influenced which decision).

---

## Notebook: `03_confidence_scoring.ipynb`

### Objective

Implement multi-signal confidence scoring that evaluates both stored memory confidence and retrieval-time confidence. Move beyond simple 0-1 scores to a principled confidence framework.

### Key Concepts

- Storage-time confidence: how confident are we when writing the memory?
- Retrieval-time confidence: how confident should we be when using this memory now?
- Confidence inputs: source authority, confirmation count, recency, consistency with other memories
- Confidence decay: unconfirmed memories lose confidence over time
- Confidence calibration: is a 0.8 confidence memory actually correct 80% of the time?

### Implementation Steps

1. Define multi-signal confidence model:
   ```python
   class ConfidenceScore:
       base_score: float  # from source authority at creation time
       confirmation_bonus: float  # +0.1 per independent confirmation
       recency_factor: float  # decays over time without confirmation
       consistency_score: float  # agreement with related memories
       composite: float  # weighted combination
   ```
2. Build `ConfidenceCalculator`:
   - At write time: initial score from source type + extraction confidence
   - At retrieval time: adjust for age decay, confirmation history, contradiction signals
   - Expose uncertainty: "I believe X with 0.7 confidence" vs silent assertion
3. Implement confidence-aware retrieval:
   - High-confidence memories returned as facts
   - Medium-confidence memories returned with hedging language
   - Low-confidence memories either excluded or flagged for user validation
4. Demo:
   - Store "Sarah prefers aisle seats" from explicit user statement (confidence=0.95)
   - Store "Sarah prefers morning flights" from single booking observation (confidence=0.55)
   - Show: agent confidently states aisle preference but asks "Would you prefer a morning flight?" for the uncertain one
5. Calibration analysis: measure whether confidence scores are well-calibrated

### Code Pattern

```python
class ConfidenceCalculator:
    def compute_retrieval_confidence(self, memory: MemoryItem) -> ConfidenceScore:
        base = memory.provenance.source_authority
        confirmations = memory.confirmation_count * 0.1
        recency = self.time_decay(memory.last_confirmed_at)
        consistency = self.check_consistency(memory, related_memories)

        composite = (
            self.weights.base * base +
            self.weights.confirmation * min(confirmations, 0.3) +
            self.weights.recency * recency +
            self.weights.consistency * consistency
        )
        return ConfidenceScore(base, confirmations, recency, consistency, composite)

    def should_surface(self, score: ConfidenceScore) -> str:
        if score.composite >= 0.8:
            return "assert"  # State as fact
        elif score.composite >= 0.5:
            return "hedge"   # "I believe..." / "Based on past interactions..."
        else:
            return "ask"     # "Would you like..." / Seek confirmation
```

### 📄 Reference Paper

**"Uncertainty Decomposition for Clarification Seeking in LLM Agents"** (arXiv:2606.19559)

Authors: Matsnev (Jun 2026)

> Argues that classical aleatoric/epistemic uncertainty is insufficient for interactive LLM agents. Proposes a decomposition that separates "what the agent doesn't know" from "what the agent knows is uncertain" — enabling targeted clarification questions. **Relevant here**: confidence scoring should distinguish between "never observed" (epistemic — ask the user) vs "observed conflicting signals" (aleatoric — present options) rather than collapsing both to a low number.

### 📄 Reference Paper

**"MEMPROBE: Probing Long-Term Agent Memory via Hidden User-State Recovery"** (arXiv:2606.24595)

Authors: Ma, Zhou, Huang, Yang, Ma, Wang, Li, Miao, Yu, Wang (Jun 2026)

> Evaluates memory as an auditable post-interaction artifact: after ordinary assistance, what structured user state can be reconstructed from the memory? Tests 5 representative memory systems and finds that task completion nearly saturates while memory recovery stays at ~0.6. **Relevant here**: confidence scoring should be validated by measuring whether high-confidence memories are actually recoverable/accurate when probed, using MEMPROBE-style evaluation.

---

## Prerequisites

- Module 02 completed (memory writes to modify with provenance)
- Module 03 concepts understood (staged promotion uses confidence to gate promotion)
- Cosmos DB provisioned (audit log container)

## Outputs for Later Modules

- `ProvenanceRecord` schema → used by 06_governance for access control decisions
- `AuditLogger` middleware → used by 07_security for forensic detection
- `ConfidenceScore` → used by 05_retrieval for confidence-weighted ranking
- Calibration methodology → used by 08_evaluation for quality measurement

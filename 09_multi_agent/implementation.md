# 09 Multi-Agent — Implementation Plan

## Module Narrative

> "Multiple agents sharing memory: isolation, handoff, and multi-principal governance."

When multiple agents serve the same user (or multiple users share the same agent), memory becomes a coordination challenge. This module covers memory handoff between agents, shared memory pools with isolation guarantees, and governance in multi-principal environments.

This module maps to discussion requirements: FR-015 (Least Privilege), FR-016 (Cross-User Isolation).

---

## Status: 🔨 TO IMPLEMENT

---

## Notebook: `01_memory_handoff.ipynb`

### Objective

Demonstrate how memory context is passed between agents during task handoff — ensuring continuity without over-sharing.

### Key Concepts

- Handoff = one agent passes control to another (e.g., booking agent → expense agent)
- Memory transfer scoping: what memories are relevant to the receiving agent?
- Need-to-know principle: transfer only what's needed, not the full memory store
- Handoff metadata: why the handoff happened, what the receiving agent should know
- Bidirectional update: receiving agent's discoveries should flow back to shared memory

### Implementation Steps

1. **Define handoff protocol**:
   ```python
   class MemoryHandoff:
       source_agent: str
       target_agent: str
       user_id: str
       transferred_memories: list[MemoryItem]  # scoped subset
       handoff_context: str  # why the handoff is happening
       permissions_granted: list[str]  # what target can do with transferred memories
   ```
2. **Build memory scoping for handoff**:
   - Given target agent's role, filter memories to only relevant categories
   - Travel agent → Expense agent: transfer trip details, NOT personal preferences
   - Travel agent → Restaurant agent: transfer dietary preferences, NOT budget level
3. **Demo multi-agent scenario**:
   - Agent A (travel): books flight, stores booking details and preferences
   - Handoff to Agent B (expense): receives trip details + policy context
   - Agent B processes expense → stores new memories (approval status, receipt)
   - Show: Agent B does NOT have access to Agent A's full memory scope
4. **Handle memory conflict on return**:
   - Agent B discovers user's level changed → updates shared memory
   - Agent A on next invocation: sees the update through shared store
5. **Measure handoff quality**:
   - Information completeness: did receiving agent have what it needed?
   - Information minimality: was anything unnecessary transferred?
   - Continuity: did the user experience feel seamless?

### Code Pattern

```python
class MemoryHandoffManager:
    async def prepare_handoff(
        self, source_agent: str, target_agent: str, user_id: str, reason: str
    ) -> MemoryHandoff:
        """Prepare scoped memory transfer for handoff."""
        all_memories = await self.memory_store.list(user_id=user_id)
        target_scope = self.get_agent_scope(target_agent)

        # Filter to only memories the target agent needs and is allowed to see
        transferable = [
            m for m in all_memories
            if m.category in target_scope.allowed_categories
            and m.classification <= target_scope.max_classification
        ]

        return MemoryHandoff(
            source_agent=source_agent,
            target_agent=target_agent,
            transferred_memories=transferable,
            handoff_context=reason,
            permissions_granted=target_scope.permissions
        )
```

---

## Notebook: `02_shared_memory.ipynb`

### Objective

Implement a shared memory pool where multiple agents can read/write memories for the same user — with proper isolation, conflict resolution, and consistency guarantees.

### Key Concepts

- Shared memory = multiple agents contribute to a single user's memory
- Consistency: what happens when two agents write conflicting information simultaneously?
- Isolation levels: read-committed, snapshot, serializable (trade-off with performance)
- Agent attribution: every memory tagged with which agent wrote it
- Merge strategies: last-write-wins, confidence-based, manual resolution

### Implementation Steps

1. **Build shared memory store (Redis-backed)**:
   - Shared namespace per user
   - Agent-scoped views (each agent sees a filtered subset)
   - Write-through to durable store (Cosmos DB) with Redis as fast cache
2. **Implement consistency model**:
   - Optimistic concurrency: agents read version, write with version check
   - Conflict detection: if two agents modify same memory, flag for resolution
   - Resolution: higher-confidence wins, or queue for user decision
3. **Demo concurrent agents**:
   - Agent A (travel) writes: "User prefers United Airlines"
   - Agent B (expense) writes: "User's company policy requires lowest fare"
   - Show conflict detection and resolution (both are valid in different scopes)
4. **Cross-user isolation testing**:
   - Agent serves User X and User Y
   - Verify: information from User X's session NEVER appears in User Y's responses
   - Verify: even with shared agent state, user memories are fully partitioned
5. **Performance testing**:
   - Measure read/write latency with 1, 10, 100 concurrent agents
   - Show Redis cache hit rates and consistency trade-offs

### Code Pattern

```python
class SharedMemoryStore:
    def __init__(self, redis_client, cosmos_client):
        self.cache = redis_client
        self.durable = cosmos_client

    async def write(self, memory: MemoryItem, agent_id: str) -> WriteResult:
        """Write with optimistic concurrency and agent attribution."""
        memory.written_by_agent = agent_id
        memory.version = await self.get_next_version(memory.user_id)

        # Check for conflicts
        existing = await self.cache.get(memory.key)
        if existing and existing.version != memory.expected_version:
            return WriteResult(conflict=True, existing=existing, proposed=memory)

        # Write-through
        await self.cache.set(memory.key, memory)
        await self.durable.upsert(memory)
        return WriteResult(success=True)

    async def read_scoped(self, user_id: str, agent_id: str) -> list[MemoryItem]:
        """Read only memories this agent is allowed to see."""
        all_memories = await self.cache.get_all(user_id)
        agent_scope = await self.get_agent_scope(agent_id)
        return [m for m in all_memories if agent_scope.allows(m)]
```

---

## Notebook: `03_multi_principal_governance.ipynb`

### Objective

Implement and test governance in environments where multiple principals (users, agents, admins) share a memory pool — the most challenging governance scenario.

### Key Concepts

- Multi-principal = hospitals, workplaces, households where multiple people interact with shared agents
- Principals have different roles, scopes, and trust levels
- Access control must be contextual: doctor can see patient records, receptionist cannot
- Active forgetting: when a principal requests deletion, it must be honored even in shared context
- Information flow: prevent unauthorized lateral information flow between principals

### Implementation Steps

1. **Define multi-principal scenario (workplace)**:
   - Principals: Employee (Sarah), Manager (James), HR Agent, Travel Agent, Admin
   - Shared memory pool: team travel preferences, booking history, policy compliance
   - Different views: Sarah sees her own data + team public; Manager sees team aggregate; HR sees compliance data
2. **Implement contextual access control**:
   - Role-based base permissions (RBAC)
   - Attribute-based overrides (ABAC): time-scoped, purpose-scoped, relationship-scoped
   - Example: Manager can see Sarah's travel budget usage but NOT her dietary preferences
3. **Test active forgetting**:
   - Sarah requests: "Delete my hotel preference history"
   - Verify: deleted from all views (including manager's aggregate reports)
   - Verify: audit trail records the deletion but doesn't leak the deleted content
4. **Test lateral flow prevention**:
   - Agent learns fact about Sarah from HR context
   - Verify: that fact does NOT appear when agent serves Sarah's colleague
   - Even if colleague asks directly: "What's Sarah's salary level?"
5. **Measure governance effectiveness** (using GateMem methodology):
   - Utility score: can agents still help effectively with governance enabled?
   - Access control score: % of unauthorized reads that are blocked
   - Forgetting score: % of deleted memories that are truly gone from all views
   - Leakage score: % of cross-principal information that flows where it shouldn't

### Code Pattern

```python
class MultiPrincipalGovernance:
    async def authorize_access(
        self, requestor: Principal, memory: MemoryItem, operation: str, context: RequestContext
    ) -> bool:
        """Contextual authorization for multi-principal access."""
        # Base RBAC check
        if not self.rbac_allows(requestor.role, memory.classification, operation):
            return False

        # ABAC overrides
        if memory.owner != requestor.id:
            # Cross-principal access — stricter rules
            if not self.relationship_allows(requestor, memory.owner, memory.category):
                return False
            if not self.purpose_allows(context.purpose, memory.category):
                return False

        return True

    async def handle_deletion_request(self, requestor: Principal, memory_id: str):
        """Active forgetting across all views and caches."""
        memory = await self.store.get(memory_id)
        if memory.owner != requestor.id and requestor.role != "admin":
            raise UnauthorizedError("Can only delete own memories")

        # Delete from all stores and caches
        await self.store.hard_delete(memory_id)
        await self.cache.invalidate(memory_id)
        await self.search_index.remove(memory_id)
        # Audit: record deletion occurred (but NOT the deleted content)
        await self.audit.log_deletion(memory_id, requestor.id, reason="user_request")
```

### 📄 Reference Paper

**"GateMem: Benchmarking Memory Governance in Multi-Principal Shared-Memory Agents"** (arXiv:2606.18829)

Authors: Ren, Yang, Chen, Zhao, Fu, Shu, Zhang, Xu, Guo, Yan (Jun 2026)

> The primary benchmark paper for this notebook. Evaluates utility, access control, and active forgetting jointly in multi-principal settings. Spans medical, office, education, and household domains with long-form multi-party episodes. Key finding: **no current method simultaneously achieves strong utility, robust access control, and reliable forgetting**. Retrieval-based methods reduce cost but still leak unauthorized or deleted information. Long-context prompting has best governance but at 10-100x token cost. **Our implementation must use enforcement-based (policy engine) rather than prompt-based (instruction following) governance.**

### 📄 Reference Paper

**"No Attacker Needed: Unintentional Cross-User Contamination in Shared-State LLM Agents"** (arXiv:2604.01350)

Authors: Yang, Li, Nian, Dong, Xu, Rossi, Ding, Zhao (Apr 2026)

> Demonstrates that cross-user contamination can happen WITHOUT malicious intent — just through normal operation of shared-state agents. When agents serve multiple users, residual information from one user's session can leak into another's responses through shared memory, cached states, or model activations. **Relevant here**: our isolation testing must cover not just intentional attacks but also unintentional leakage through legitimate operations.

### 📄 Reference Paper

**"AgentSafe: Safeguarding Large Language Model-based Multi-agent Systems via Hierarchical Data Management"** (arXiv:2503.04392)

Authors: Mao, Meng, Duan, Yu, Jia, Fang, Liang, Wang, Wen (Mar 2025)

> Proposes hierarchical data management for multi-agent memory safety. Implements access control at multiple granularity levels (system → team → agent → task) with information flow tracking between levels. **Relevant here**: provides the architectural pattern for hierarchical access control in multi-agent shared memory environments.

---

## Prerequisites

- Module 06 (access control and governance policies)
- Module 07 (security patterns for cross-user isolation)
- Redis provisioned (for shared memory cache layer)

## Outputs for Later Modules

- Shared memory patterns → used by 10_frontier for unified memory architecture
- Multi-principal governance → foundational for enterprise deployment
- Handoff protocol → reusable pattern for any multi-agent system

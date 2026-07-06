# 06 Governance — Implementation Plan

## Module Narrative

> "Who can see and change memories? How do users stay in control?"

Memory without governance is a liability. This module implements access control (who can read/write), contradiction management (conflicting facts), user control (inspect/approve/reject), and sensitive data handling (PII, classification). Governance is the policy layer that sits between memory operations and their execution.

This module maps to discussion requirements: FR-010 (Contradiction Management), FR-011 (Governance Layer), FR-012 (User Control), FR-015 (Least Privilege), FR-018 (Sensitive Data), FR-019 (Persistence Policies).

---

## Status: 🔨 TO IMPLEMENT

---

## Notebook: `01_access_control.ipynb`

### Objective

Implement role-based and attribute-based access control for memory operations. Different agents, users, and system components have different permissions over different memory classes.

### Key Concepts

- Principals: user, agent, admin, system — each with different trust levels
- Operations: create, read, update, promote, delete — each governed independently
- Memory classification: public, internal, confidential, restricted — affects who can access
- Partition isolation: user A cannot read user B's memories (even if same agent)
- Agent-level restrictions: a booking agent shouldn't read health-related memories

### Implementation Steps

1. Define access control model:
   ```python
   class AccessPolicy:
       principal_type: str  # "user" | "agent" | "admin" | "system"
       principal_id: str
       allowed_operations: list[str]  # ["read", "create"]
       memory_classifications: list[str]  # ["public", "internal"]
       memory_categories: list[str]  # ["travel", "preferences"] — category restrictions
   ```
2. Build `PolicyEngine` middleware:
   - Intercepts all memory operations
   - Evaluates caller's identity against policy rules
   - Denies unauthorized operations with audit log entry
   - Supports both deny-by-default and explicit allow rules
3. Implement user isolation:
   - Cosmos DB partition key enforced per `user_id`
   - Query-time filter: agent cannot cross partition boundaries
   - Demo: show that Agent A serving User X cannot retrieve User Y's memories
4. Implement agent-level restrictions:
   - Travel agent: can read/write travel preferences, NOT health data
   - HR agent: can read employment data, NOT personal preferences
   - Demo: booking agent tries to access dietary restrictions → denied
5. Admin operations:
   - Bulk audit queries (read-only across users for compliance)
   - Memory deletion by request (GDPR right-to-erasure)
   - Policy updates require admin principal

### Code Pattern

```python
class PolicyEngine:
    async def authorize(self, operation: MemoryOperation) -> AuthorizationResult:
        """Check if the operation is allowed by current policies."""
        policies = await self.get_policies(operation.principal)

        for policy in policies:
            if not policy.allows_operation(operation.type):
                return AuthorizationResult(denied=True, reason="Operation not permitted")
            if not policy.allows_classification(operation.memory.classification):
                return AuthorizationResult(denied=True, reason="Classification mismatch")
            if not policy.allows_category(operation.memory.category):
                return AuthorizationResult(denied=True, reason="Category restricted")

        # Log the authorization decision
        await self.audit_logger.log(AuthorizationEvent(operation, result))
        return AuthorizationResult(allowed=True)
```

### 📄 Reference Paper

**"GateMem: Benchmarking Memory Governance in Multi-Principal Shared-Memory Agents"** (arXiv:2606.18829)

Authors: Ren, Yang, Chen, Zhao, Fu, Shu, Zhang, Xu, Guo, Yan (Jun 2026)

> Introduces a benchmark for multi-principal shared-memory governance. Jointly evaluates utility (can the agent still help?), access control (does it prevent unauthorized reads?), and active forgetting (does it honor deletion requests?). Spans medical, office, education, and household domains. Key finding: **no method simultaneously achieves strong utility, robust access control, and reliable forgetting**. Long-context prompting yields best governance but at high token cost; retrieval-based methods reduce cost but still leak unauthorized or deleted information. **Relevant here**: our access control must be enforcement-based (policy engine denying operations) not prompt-based (asking the LLM to respect boundaries).

---

## Notebook: `02_contradiction_management.ipynb`

### Objective

Detect and resolve logical contradictions between memories — conflicting preferences, changed beliefs, and incompatible facts.

### Key Concepts

- Contradiction types: direct negation, value change, temporal inconsistency, scope conflict
- Detection: proactive (at write time) vs reactive (at retrieval time)
- Resolution strategies: ask user, use confidence, use recency, use source authority
- Contradiction graph: store contradictions as explicit relationships, not silent overwrites

### Implementation Steps

1. Build `ContradictionDetector`:
   - At write time: compare new memory against existing memories for same (subject, relation)
   - Use LLM to classify: contradiction, update, refinement, or unrelated
   - Score severity: hard contradiction (A and NOT A) vs soft (preference shift)
2. Implement resolution strategies:
   - **Ask user**: present both options, let user decide (highest authority)
   - **Confidence-based**: higher confidence wins, lower gets deprecated
   - **Recency-based**: newer supersedes older (with audit trail)
   - **Source authority**: user assertion > enterprise KB > inference
3. Demo scenarios:
   - Hard contradiction: "I'm vegetarian" then "I had steak last night"
     → Agent asks: "I have a note that you're vegetarian, but you mentioned steak. Has your diet changed?"
   - Soft update: "I prefer aisle seats" then "Actually, window seats are better for long flights"
     → Refine: "Aisle for short flights, window for long flights"
   - Scope conflict: "I love spicy food" + "No spicy food when traveling for client dinners"
     → Store both with context scope
4. Show contradiction graph: visualize conflicting memories as edges in Neo4j

### Code Pattern

```python
class ContradictionDetector:
    async def check_on_write(self, new_memory: MemoryItem) -> ContradictionResult:
        """Check if new memory contradicts existing memories."""
        related = await self.find_related(new_memory.subject, new_memory.relation)

        for existing in related:
            classification = await self.classify_relationship(new_memory, existing)
            if classification == "contradiction":
                return ContradictionResult(
                    type="hard_contradiction",
                    existing_memory=existing,
                    new_memory=new_memory,
                    resolution_options=self.get_resolution_options(existing, new_memory)
                )
            elif classification == "update":
                return ContradictionResult(
                    type="belief_update",
                    supersedes=existing,
                    resolution="apply_supersession"
                )

    def get_resolution_options(self, existing, new) -> list[Resolution]:
        return [
            Resolution("ask_user", "Ask the user to clarify"),
            Resolution("prefer_newer", f"Accept new: {new.content}"),
            Resolution("prefer_confident", f"Keep higher confidence: {existing.content}"),
            Resolution("store_both_scoped", "Both true in different contexts"),
        ]
```

### 📄 Reference Paper

**"MemSyco-Bench: Benchmarking Sycophancy in Agent Memory"** (arXiv:2607.01071)

Authors: Xiang, Chen, Tang, Wei, Ning, Lin, Zhang, Su (Jul 2026)

> Evaluates memory-induced sycophancy — where retrieved memories cause agents to over-align with the user at the cost of factual accuracy. Covers 5 tasks: reject memory as factual evidence, respect applicable scope, resolve conflicts between memory and objective evidence, track memory updates, and use valid memory for personalization. **Relevant here**: contradiction management must handle not just memory-vs-memory conflicts but also memory-vs-objective-reality conflicts (e.g., user believes something factually wrong — should the agent memorize it or push back?).

---

## Notebook: `03_user_control.ipynb`

### Objective

Give users the ability to inspect, approve, correct, and delete their memories. Implement the "user validation loop" where the agent proactively seeks confirmation for uncertain memories.

### Key Concepts

- Transparency: users can see everything the system remembers about them
- Correction: users can fix wrong memories (highest authority source)
- Deletion: users can remove any memory (right to erasure)
- Approval workflow: agent presents candidate memories for user sign-off
- Proactive validation: agent asks about uncertain or contradictory memories

### Implementation Steps

1. Build `MemoryInspector` tools for the agent:
   - `show_my_memories(category?)` — display all stored memories with confidence scores
   - `correct_memory(memory_id, new_value)` — user overwrites with high authority
   - `delete_memory(memory_id)` — permanent removal with audit trail
   - `approve_memory(memory_id)` — promote from candidate to trusted
   - `reject_memory(memory_id)` — mark as incorrect, prevent re-creation
2. Implement proactive validation loop:
   - Agent detects uncertainty or contradiction during conversation
   - Agent asks: "I have a note that [X]. Is that still correct?"
   - User response creates high-confidence update or confirmation
3. Build batch review mode:
   - Show user all `candidate` memories pending approval
   - "Here are 5 things I've learned about you recently. Can you confirm?"
4. Demo: end-of-session review where agent summarises what it learned and asks for corrections
5. Handle deletion cascading:
   - Deleting a memory also removes dependent inferences
   - Audit trail records deletion reason and requestor

### Code Pattern

```python
# Agent tools for user control
@tool
async def show_my_memories(category: str = None) -> str:
    """Show the user all memories stored about them."""
    memories = await memory_store.list(user_id=current_user, category=category)
    return format_memory_list(memories, include_confidence=True, include_source=True)

@tool
async def correct_memory(memory_id: str, corrected_value: str) -> str:
    """User corrects a memory — highest authority update."""
    await memory_store.update(
        memory_id,
        new_value=corrected_value,
        provenance=ProvenanceRecord(source_type="user_assertion", authority=1.0),
        state=MemoryState.TRUSTED  # user corrections auto-promote
    )
    return f"Updated. I'll remember: {corrected_value}"

@tool
async def delete_memory(memory_id: str, reason: str = "user_request") -> str:
    """User requests deletion of a memory."""
    await memory_store.delete(memory_id, reason=reason, requestor=current_user)
    await audit_logger.log(DeletionEvent(memory_id, reason, requestor=current_user))
    return "Deleted. I won't use this information anymore."
```

---

## Notebook: `04_sensitive_data.ipynb`

### Objective

Classify memories by sensitivity level and apply appropriate persistence policies, access restrictions, and handling rules.

### Key Concepts

- Data classification: `public`, `personal`, `sensitive_personal`, `protected`
- Auto-detection: identify PII patterns (emails, phone numbers, health info, financial data)
- Persistence policies: session_only (auto-delete), temporary (TTL), long_term, permanent
- Handling rules: sensitive memories get extra encryption, restricted access, audit requirements
- Compliance alignment: GDPR personal data categories, data minimisation principle

### Implementation Steps

1. Build `SensitivityClassifier`:
   - Pattern-based PII detection (regex for emails, phones, SSNs, etc.)
   - Category-based rules: health data → `sensitive_personal`, name → `personal`
   - LLM-based classification for complex cases (opinions about colleagues, salary info)
2. Implement persistence policies:
   ```python
   class PersistencePolicy:
       level: str  # "session_only" | "temporary" | "long_term" | "permanent"
       ttl_hours: int | None  # for temporary: auto-delete after N hours
       requires_consent: bool  # must user approve storage?
       requires_encryption: bool  # at-rest encryption beyond baseline
       audit_level: str  # "standard" | "enhanced" (log every read)
   ```
3. Apply policies at write time:
   - Classify incoming memory
   - Check if user has consented to this classification level
   - Apply TTL if temporary
   - Route to appropriate storage tier
4. Demo:
   - User mentions allergies (health data) → classified as `sensitive_personal`
   - Agent asks: "I'd like to remember your dietary restrictions for future bookings. Is that okay?"
   - If approved: stored with enhanced audit, restricted agent access
   - If denied: used in session only, not persisted
5. Implement data minimisation:
   - Store the minimum needed: "vegetarian" not "mentioned being vegetarian because of a medical condition diagnosed in 2020"
   - Strip unnecessary context from memory writes

### Code Pattern

```python
class SensitivityClassifier:
    PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\+?[\d\-\(\)\s]{10,}",
        "health": ["allergy", "medication", "diagnosis", "condition", "disability"],
        "financial": ["salary", "bank account", "credit card", "compensation"],
    }

    async def classify(self, memory_content: str) -> SensitivityLevel:
        # Pattern-based detection
        for category, pattern in self.PATTERNS.items():
            if self.matches(memory_content, pattern):
                return self.category_to_level(category)

        # LLM-based for complex cases
        return await self.llm_classify(memory_content)

    def get_policy(self, level: SensitivityLevel) -> PersistencePolicy:
        return {
            "public": PersistencePolicy(level="long_term", requires_consent=False),
            "personal": PersistencePolicy(level="long_term", requires_consent=True),
            "sensitive_personal": PersistencePolicy(level="temporary", ttl_hours=720,
                                                     requires_consent=True,
                                                     requires_encryption=True),
            "protected": PersistencePolicy(level="session_only", requires_consent=True),
        }[level]
```

---

## Prerequisites

- Module 03 (memory states and promotion for governance decisions)
- Module 04 (provenance and audit infrastructure)
- Module 05 (retrieval patterns that governance wraps around)

## Outputs for Later Modules

- `PolicyEngine` → used by 07_security as enforcement layer
- `ContradictionDetector` → used by 08_evaluation for contradiction handling metrics
- User control tools → used by 09_multi_agent for per-user governance in shared environments
- `SensitivityClassifier` → used by 09_multi_agent to prevent cross-user leakage of sensitive data

# 06 Governance & User Control — Implementation Plan

## Module Narrative

> "Users must be able to see, correct, and delete what the agent remembers."

Memory without user control is a liability. This module gives users tools to
inspect their memory profile, correct mistakes, and delete entries — plus
role-based scoping so different agents see different memory subsets.

Contradiction management (originally planned here) is already handled by
Module 3.4's supersession pattern — same-category updates automatically
retire the old value. This module focuses on **user agency** and **access control**.

Maps to: FR-010 (Contradiction — done in 3.4), FR-011 (Governance), FR-012 (User Control),
FR-015 (Least Privilege), FR-018 (Sensitive Data), FR-019 (Persistence Policies).

---

## Status: 🔨 TO IMPLEMENT

---

## Already Built (Module 3)

| Capability | Where | What It Does |
|---|---|---|
| Contradiction resolution | `GraphBeliefStore.store()` | Auto-supersedes conflicting beliefs |
| Memory inspection | `GraphBeliefStore.snapshot()` | Lists all beliefs with metadata |
| Provenance | `explain_belief` (Module 4) | Full origin story for any belief |
| Trust gating | `GraphPromotionStore.gated_recall()` | Only surfaces trusted/provisional |

**What's new**: user-facing correction/deletion tools, periodic review pattern,
role-based memory scoping via MAF middleware.

---

## Notebook 01: `01_user_control.ipynb`

### Objective

Give the user inspection, correction, and deletion tools — implemented as agent
`@tool` functions wrapping `GraphBeliefStore` / `GraphPromotionStore` methods.

### Builds On

- `GraphBeliefStore` (Module 3.4) — `snapshot()`, `history()`, `store()`
- `explain_belief` tool (Module 4) — provenance explanation
- `recall_with_confidence` (Module 4) — confidence-annotated recall

### New in `lifecycle_utils.py`

```python
# Add to GraphBeliefStore:
async def correct(self, category: str, new_preference: str) -> dict:
    # User correction: supersedes current value, stores new as trusted (authority=1.0).
    # Calls store() with source_type="user_correction", then force-promotes to trusted

async def delete(self, category: str) -> dict:
    # User deletion: retires current belief with valid_to=now, reason='user_deletion'.
    # Sets valid_to, does NOT hard-delete — audit trail preserved
    # Returns what was deleted for confirmation
```

### Agent Tools

| Tool | Purpose |
|------|---------|
| `show_my_memories` | Formatted snapshot: category, preference, confidence, source, state |
| `correct_memory` | User overrides a belief → auto-promoted to trusted |
| `delete_memory` | User removes a belief → retired with audit trail |
| `explain_belief` | From Module 4 — "why do you believe X?" |
| `recall_beliefs` | From Module 4 — confidence-aware recall |

### Demo Flow (6 turns)

1. **Setup** — Pre-populate agent with 8 beliefs (mix of user_assertion and llm_inference)
2. **Inspect** — "Show me everything you remember about me"
   → Agent calls `show_my_memories` → formatted table with confidence + source
3. **Correct** — "That's wrong — I don't prefer United, I prefer Delta"
   → Agent calls `correct_memory("airline", "Delta")` → supersedes United, stores Delta as trusted
4. **Delete** — "Forget my dietary preferences entirely"
   → Agent calls `delete_memory("diet")` → retired, audit trail preserved
5. **Verify** — "Show me my memories again"
   → United gone (superseded by Delta), diet gone (user-deleted)
6. **Periodic review** — Agent proactively: "I have some preferences I'm not sure about.
   You seem to prefer morning flights (inferred, confidence 0.55). Is that right?"
   → User confirms → promoted to trusted; or denies → deleted

### Key Insight: Correction ≠ Overwrite

Correction uses the same SCD Type 2 pattern as belief revision. The old value
is retired with `valid_to = now`, not deleted. The audit trail shows:
```
airline: United (2026-01-15 → 2026-07-15, superseded by user_correction)
airline: Delta  (2026-07-15 → present, source: user_correction, trusted)
```

### 📄 Reference Paper

**"GateMem: Benchmarking Memory Governance in Multi-Principal Shared-Memory Agents"** (arXiv:2606.18829)
> No current method simultaneously achieves strong utility, robust access control,
> and reliable forgetting. Our approach: enforcement-based deletion (Cypher `SET valid_to`)
> rather than prompt-based ("please forget X").

---

## Notebook 02: `02_access_control.ipynb`

### Objective

Implement role-based memory scoping: different agents see different memory subsets.
Plus PII detection as a pre-write hook that asks user consent before storing
sensitive data.

### Builds On

- `ToolApprovalMiddleware` (Module 3.2) — MAF middleware pattern
- `create_baseline_agent()` — factory with `middleware` parameter
- `GraphBeliefStore` — category-based storage

### New in `lifecycle_utils.py`

```python
class MemoryScopeMiddleware:
    # MAF middleware that filters memory tool results by agent role.
    def __init__(self, allowed_categories: list[str]):
        self.allowed = set(allowed_categories)
    # Intercepts recall/snapshot tool calls and filters results
    # to only include categories this agent is allowed to see.

class SensitivityDetector:
    # Pre-write hook that detects PII patterns and flags for consent.
    PATTERNS = {"email": r"...", "phone": r"...", "health": [...]}
    async def check(self, content: str) -> dict:
        # Returns: {is_sensitive: bool, category: str, requires_consent: bool}
```

### Agent Tools

Same memory tools as Module 04/06.1, but wrapped in `MemoryScopeMiddleware`
so each agent only sees its allowed categories.

### Demo Flow (5 turns)

1. **Setup** — Create two agents:
   - Travel agent: can access `home_city, airline, hotel, airport, seat, diet`
   - Expense agent: can access `home_city, budget_tier, expense_policy, airline`
   - Travel agent CANNOT see `budget_tier`; Expense agent CANNOT see `diet, seat, hotel`
2. **Populate** — Travel agent stores several preferences including diet
3. **Scope test** — Expense agent recalls preferences
   → Diet and seat preferences filtered out by `MemoryScopeMiddleware`
4. **PII detection** — User tells travel agent: "My passport number is X123456"
   → `SensitivityDetector` fires → agent asks: "That contains sensitive ID data.
   Should I remember this, or just use it for this session?"
5. **Cross-agent isolation** — Verify: expense agent cannot see travel-only memories
   even through direct tool calls

### Key Insight: Middleware, Not Policy Engine

Access control is implemented as MAF `middleware` — not a separate PolicyEngine
class with complex RBAC rules. The middleware intercepts tool results and filters
by category whitelist. Simple, composable, no reinvention.

### 📄 Reference Papers

**"GateMem"** (arXiv:2606.18829)
> Enforcement-based governance (middleware blocking operations) outperforms
> prompt-based (asking the LLM to respect boundaries).

**"AgentSafe: Safeguarding LLM-based Multi-agent Systems via Hierarchical Data Management"** (arXiv:2503.04392)
> Hierarchical access control at multiple granularity levels — our
> category-based scoping is the simplest correct implementation of this pattern.

---

## Prerequisites

- Module 3.4 (GraphBeliefStore — SCD Type 2 for correction/deletion audit trail)
- Module 4 (explain_belief, confidence-aware recall)
- Module 3.2 (ToolApprovalMiddleware pattern)

## Outputs for Later Modules

- User control tools → reused in Module 08 (evaluation — test user correction flow)
- `MemoryScopeMiddleware` → reused in Module 09 (multi-agent scoped handoff)
- `SensitivityDetector` → reused in Module 07 (defense — PII in tool output detection)

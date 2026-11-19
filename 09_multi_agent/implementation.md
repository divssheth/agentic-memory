# 09 Multi-Agent Memory — Implementation Plan

## Module Narrative

> "Share the minimum authorized memory, preserve user isolation, and propagate erasure."

Multiple agents may serve one user from shared Cosmos containers, but they do
not receive identical views. This module separates the user partition boundary
from the role/category boundary and tests both during handoff and erasure.

Maps to: FR-015 (Least Privilege), FR-016 (Cross-User Isolation),
FR-024 (Verified Forgetting).

---

## Status: 🔨 TO IMPLEMENT

## Already Built

| Capability | Source |
|------------|--------|
| User-bound Cosmos stores | `SemanticMemoryStore(user_id=...)` |
| Category-scoped tools/middleware | Module 6 |
| Multi-store routing | Module 5 |
| Secured retirement and erasure | Modules 6–7 |
| Canary evaluation | Module 8 |

---

## Notebook 01: `01_memory_handoff.ipynb`

### Objective

Handoff work between travel and expense agents without copying a user's entire
profile into prompts or a new uncontrolled store.

### Boundaries

| Boundary | Enforcement |
|----------|-------------|
| User isolation | Cosmos `/user_id` partition key bound during store construction |
| Agent role | Only allowed category tools are exposed to each agent |
| Handoff payload | Opaque references plus minimum task data |
| Durable projection | Registered with `ErasureCoordinator` if it can later serve personal data |

| Agent | Allowed Memory |
|-------|----------------|
| TravelAgent | home city, airport, airline, hotel, seat, diet, loyalty |
| ExpenseAgent | trip identifier, route, cost, expense status, applicable policy |

### Demo Flow

1. TravelAgent stores preferences and completes a booking.
2. It creates a scoped handoff containing a trip reference and minimum expense data.
3. ExpenseAgent resolves only fields permitted by its tools and user partition.
4. Attempts to retrieve diet, seat, or unrelated hotel preferences are denied
   before a Cosmos query is issued.
5. ExpenseAgent records expense status through its allowed category tool.
6. Verify bidirectional visibility only for explicitly shared categories.
7. Erase one handed-off personal field, start fresh sessions for both agents,
   and verify neither agent nor the durable handoff projection can retrieve it.

### Key Insight: Shared Storage Does Not Mean Shared Authority

Both agents may use the same containers, but each receives a user-bound store
and a role-specific tool surface. Middleware is defense in depth; it is not a
substitute for partition and pre-query scope enforcement.

---

## Notebook 02: `02_shared_memory.ipynb`

### Objective

Prove structural isolation for two users in shared Cosmos containers, including
ordinary retrieval, handoff, retirement, and erasure.

### Setup

| User | Example Profile | Partition |
|------|-----------------|-----------|
| Sarah | Denver, United, Marriott | `user_id=sarah` |
| James | Boston, JetBlue, Hilton | `user_id=james` |

The model never receives a tool parameter that selects another user's partition.

### Demo Flow

1. Populate both users with overlapping categories and distinct canaries.
2. Verify each user retrieves only their own records.
3. Ask one agent about the other user and verify an empty/denied result without
   existence disclosure.
4. Attempt to retire and erase the other user's record.
5. Erase Sarah's canary legitimately and recreate all agent sessions.
6. Verify Sarah's canary is absent from every registered projection while
   James's record remains retrievable.
7. Query Cosmos directly with each partition key for programmatic assertions.

### Validation Criteria

| Check | Expected Result |
|-------|-----------------|
| Cross-user recall | 0 records |
| Cross-user mutation | 0 records changed |
| Role/category leakage | 0 records enter context |
| Authorized handoff | Only minimum permitted data |
| Erasure propagation | All registered recipient projections verified absent |
| Neighbor integrity | Other user and categories unchanged |

---

## Prerequisites

- Module 5 routing
- Module 6 scoped governance and erasure adapters
- Module 7 authorization defenses
- Module 8 canary evaluation

## Outputs for Later Modules

- Scoped handoff composition → Module 10 unified agent
- Multi-user erasure and isolation assertions → capstone integration test

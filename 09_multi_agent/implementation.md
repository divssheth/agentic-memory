# 09 Multi-Agent Memory — Implementation Plan

## Module Narrative

> "Multiple agents, one user's memory — scoped sharing, not full exposure."

When a travel agent hands off to an expense agent, the expense agent needs trip
details but NOT dietary preferences. When two agents serve two users on the same
Neo4j graph, User A's data must never leak to User B. This module demonstrates
scoped memory handoff between MAF agents and cross-user isolation on shared storage.

Maps to: FR-015 (Least Privilege), FR-016 (Cross-User Isolation).

---

## Status: 🔨 TO IMPLEMENT

---

## Already Built (Modules 3–6)

| Capability | Where | Enables |
|---|---|---|
| Category-based storage | `GraphBeliefStore.store(category, ...)` | Scoped transfer by category |
| Memory scoping middleware | `MemoryScopeMiddleware` (Module 6) | Per-agent category whitelists |
| User-partitioned queries | Neo4j `MemoryClient` via `user_id` | Cross-user isolation |
| Agent factory | `create_baseline_agent()` | Constructing multiple agents with different configs |

---

## Notebook 01: `01_memory_handoff.ipynb`

### Objective

Demonstrate scoped memory transfer when one MAF agent hands control to another.
The receiving agent gets only the memories relevant to its role.

### Builds On

- `create_baseline_agent()` — creates agents with different tools and middleware
- `MemoryScopeMiddleware` (Module 6) — filters recall by category whitelist
- `GraphBeliefStore` — shared Neo4j graph

### Two Agents

| Agent | Role | Allowed Categories |
|-------|------|-------------------|
| TravelAgent | Book flights, hotels | home_city, airline, hotel, airport, seat, diet, loyalty |
| ExpenseAgent | Process expense reports | home_city, airline, airport, budget_tier, expense_policy |

Both agents read/write to the **same** Neo4j graph. The `MemoryScopeMiddleware`
ensures each agent only sees its allowed categories.

### Demo Flow (8 turns across 2 agents)

**Phase 1: Travel Agent (4 turns)**
1. User: "I live in Denver, I always fly United, Marriott for hotels"
   → TravelAgent stores: home_city, airline, hotel
2. User: "Book me a flight to NYC next week"
   → TravelAgent uses preferences for booking
3. User: "I'm vegetarian and prefer aisle seats"
   → TravelAgent stores: diet, seat
4. User: "Booking confirmed: United DEN→JFK, Marriott Times Square, $1,200 total"
   → TravelAgent stores trip details

**Phase 2: Handoff (1 cell)**
- Print what ExpenseAgent CAN see (home_city, airline, airport)
- Print what ExpenseAgent CANNOT see (diet, seat, hotel, loyalty)

**Phase 3: Expense Agent (3 turns)**
5. User: "Process the expense for my NYC trip"
   → ExpenseAgent recalls trip details via scoped memory — sees airline and city, not hotel or diet
6. ExpenseAgent: "I see you flew United DEN→JFK. What was the total cost?"
   → (cannot see hotel details — would need to ask)
7. User confirms cost → ExpenseAgent stores `expense_status: approved`
   → This write is visible to TravelAgent on next invocation

**Phase 4: Verify bidirectional flow (1 cell)**
8. TravelAgent recalls preferences → sees `expense_status: approved` from ExpenseAgent

### Key Insight: Shared Graph, Scoped Views

There is no "handoff protocol" class. Both agents point at the same Neo4j graph.
Scoping is enforced by `MemoryScopeMiddleware` — the middleware filters tool
results, not the graph itself. Simple and correct.

### 📄 Reference Paper

**"No Attacker Needed: Unintentional Cross-User Contamination"** (arXiv:2604.01350)
> Cross-user contamination can happen without malicious intent through shared state.
> Our middleware-based scoping prevents this structurally.

---

## Notebook 02: `02_shared_memory.ipynb`

### Objective

Verify cross-user isolation: two agents serve two different users on the same
Neo4j graph. User A's preferences must NEVER appear in User B's responses.

### Builds On

- Neo4j `MemoryClient` — user_id partitioning
- `GraphBeliefStore` — same class, different user context
- `create_baseline_agent()` — agent factory

### Two Users, One Graph

| Setup | Details |
|-------|---------|
| User A (Sarah) | home_city: Denver, airline: United, hotel: Marriott |
| User B (James) | home_city: Boston, airline: JetBlue, hotel: Hilton |
| Storage | Same Neo4j instance, same database |
| Isolation | `user_id` parameter on all MemoryClient operations |

### Demo Flow (6 turns)

1. **Populate Sarah** — Store 3 preferences for user_id="sarah"
2. **Populate James** — Store 3 preferences for user_id="james"
3. **Isolation test A** — Sarah's agent recalls preferences → sees only Sarah's data
4. **Isolation test B** — James's agent recalls preferences → sees only James's data
5. **Cross-query** — Sarah's agent asked "What does James prefer?" → no results
   (even if the agent tries, the graph query is partitioned by user_id)
6. **Neo4j verification** — Direct Cypher query showing both users' data exists
   but is partitioned by user_id on the Preference nodes

### Key Insight: Partition at the Data Layer

Isolation is enforced by `MemoryClient`'s `user_id` parameter on every query,
not by prompt instructions. The LLM cannot bypass this even if instructed to —
the Cypher query physically filters by user_id.

### 📄 Reference Papers

**"GateMem"** (arXiv:2606.18829)
> Joint evaluation of utility, access control, and active forgetting in multi-principal
> settings. Our partition-at-data-layer approach ensures structural isolation.

**"AgentSafe"** (arXiv:2503.04392)
> Hierarchical data management for multi-agent safety. Our user_id partitioning
> is the data-layer foundation that makes higher-level scoping possible.

---

## Prerequisites

- Module 6 (MemoryScopeMiddleware, access control patterns)
- Module 3 (GraphBeliefStore, GraphPromotionStore — shared graph backend)

## Outputs for Later Modules

- Scoped handoff pattern → used in Module 10 (unified agent with role-based views)
- Cross-user isolation → validated assumption for production deployment

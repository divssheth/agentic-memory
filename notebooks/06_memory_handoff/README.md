# Module 6: Memory Handoff

**Central thesis: Memory access defines responsibility.** Giving an agent a memory type is a statement about what that agent is responsible for — not a default.

## Learning Objectives

By the end of this module, you will:

1. Split a single agent into **specialist agents** with scoped memory
2. Apply the **4-question framework** for memory assignment decisions
3. Implement **HandoffContext** for structured data transfer between agents
4. Build **conditional dispatch** to route requests to the right agent path

## Prerequisites

- Completed Modules 1–5
- Azure AI Foundry Project with model deployment (configured via `FOUNDRY_MODEL`)

## Time

~60 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `06_memory_handoff.ipynb` | Hands-on notebook with concepts |
| `prompts/router_shared.md` | Router agent instructions (shared approach) |
| `prompts/router_scoped.md` | Router agent instructions (scoped approach) |
| `prompts/router_conditional.md` | Router with conditional dispatch |
| `prompts/policy_shared.md` | Policy agent instructions (shared) |
| `prompts/policy_scoped.md` | Policy agent instructions (scoped) |
| `prompts/booking_shared.md` | Booking agent instructions (shared) |
| `prompts/booking_scoped.md` | Booking agent instructions (scoped) |
| `procedures/domestic_booking.md` | Domestic booking procedure |
| `procedures/international_booking.md` | International booking procedure |

## Overview

Module 5 combined all three memory types into a single agent. This module separates responsibilities across specialist agents and teaches how memory findings transfer between them.

```
User → Router → Policy → Booking → Response
         │         │         │
         │         │         └── Reads HandoffContext only (no memory tools)
         │         └── Procedural memory → writes policy_findings
         └── Episodic + Semantic memory → writes user_preferences, relevant_history
```

## Structure

| Part | Topic |
|------|-------|
| **Part 1** | Why split agents, why scope memory, 4-question decision framework, the handoff problem |
| **Part 2** | Shared tools — brute-force approach where every agent gets everything |
| **Part 3** | Scoped handoff — each agent owns its memory, findings travel via HandoffContext + conditional dispatch |
| **Summary** | Central insight, comparison table, six-module recap |

## Agent Memory Assignment

| Agent | Memory Tools | Handoff Tools | Total |
|-------|-------------|---------------|-------|
| **Router** | recall_events, query_user_knowledge, learn_about_user | get / update / record | 6 |
| **Policy** | load_procedure | get / update / record | 4 |
| **Booking** | remember_event *(record only)* | get / update / record | 4 |

## Key Concepts

- **4-question framework**: Job → Information needed → Memory type → Direct access or handoff?
- **HandoffContext**: Typed dataclass carrying findings between agents (user_preferences ← semantic, relevant_history ← episodic, policy_findings ← procedural)
- **WorkflowBuilder**: Agent Framework's declarative orchestration (sequential, conditional switch, conditional edge, fan-out, fan-in)
- **Conditional dispatch**: Route requests to different agent paths based on classification

## Quick Start

```bash
# No external services needed — runs entirely in-memory
jupyter notebook 06_memory_handoff.ipynb
```

## Navigation

- ← Previous: [Module 5: Combined Memory](../05_combined_memory/)
- → Next: [Module 7: Shared Memory](../07_shared_memory/)

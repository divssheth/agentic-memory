# Module 6: Memory Handoff

**Central thesis: Memory access defines responsibility.** Giving an agent a memory type is a statement about what that agent is responsible for — not a default.

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

| Part | Topic | Cells |
|------|-------|-------|
| **Part 1** | Why split agents, why scope memory, 4-question decision framework, the handoff problem | Cells 5–8 (concepts) |
| **Part 2** | Shared tools — brute-force approach where every agent gets everything | Cells 9–13 |
| **Part 3** | Scoped handoff — each agent owns its memory, findings travel via HandoffContext + conditional dispatch | Cells 14–22 |
| **Summary** | Central insight, comparison table, six-module recap | Cells 23–24 |

## Files

- `build_notebook.py` — Generates the notebook (24 cells)
- `06_memory_handoff.ipynb` — Tutorial notebook

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

## Handoff Tools

| Tool | Purpose |
|------|---------|
| `handoff_to_agent` | Transfer to another agent |
| `update_context` | Add information to context |
| `complete_handoff` | Mark workflow complete |

## Prerequisites

- Completed Modules 1-5
- Understanding of combined memory

## Related

- [Module 5: Combined Memory](../05_combined_memory/)
- [Module 7: Shared Memory](../07_shared_memory/)

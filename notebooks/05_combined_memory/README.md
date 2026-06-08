# Module 5: Combined Memory — When Memories Disagree

This module brings together all three memory types into a single agent and tackles the emergent problem: **what happens when memories conflict?**

## Learning Objectives

By the end of this module, you will:

1. Combine episodic, semantic, and procedural memory in one agent
2. Identify **cross-memory conflicts** (preference vs. policy, history vs. stated change)
3. Design **priority hierarchies** for conflict resolution
4. Implement a two-tier persistence architecture (automatic vs. explicit)

## Prerequisites

- Completed Modules 1–4
- Azure AI Foundry Project with model deployment (configured via `FOUNDRY_MODEL`)
- (Optional) Azure Cosmos DB + Neo4j for persistence

## Time

~60 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `05_combined_memory.ipynb` | Hands-on notebook with concepts |
| `prompts/combined.md` | Combined instructions with conflict resolution rules |
| `prompts/combined_no_conflicts.md` | Baseline without conflict handling |
| `skills/domestic-booking/SKILL.md` | Domestic booking procedure |
| `skills/international-booking/SKILL.md` | International booking procedure |
| `steps/01_setup_cosmos.md` | Cosmos DB setup guide |

## Key Concepts

### Memory Routing

The agent routes queries based on patterns:

| Query Pattern | Memory Type |
|--------------|-------------|
| "last time", "before" | Episodic |
| "I prefer", "my usual" | Semantic |
| "policy", "how do I" | Procedural |
| Complex requests | Multiple |

### Conflict Resolution

When memories disagree, the priority hierarchy decides:

```
Policy (procedural) > Preference (semantic) > History (episodic)
```

Example: User prefers business class, but policy says economy for domestic flights → policy wins.

## Quick Start

```bash
# Without backends (in-memory)
jupyter notebook 05_combined_memory.ipynb

# With backends (persistent)
# Ensure COSMOS_ENDPOINT and NEO4J_URI are in .env
```

## Navigation

- ← Previous: [Module 4: Procedural Memory](../04_procedural_memory/)
- → Next: [Module 6: Memory Handoff](../06_memory_handoff/)

# Module 5: Combined Memory Agent

This module brings together all three memory types into a single powerful agent.

## Overview

| Memory Type | Purpose | When to Use |
|-------------|---------|-------------|
| **Episodic** | "What happened?" | History, past events |
| **Semantic** | "What do I know?" | Preferences, facts |
| **Procedural** | "How do I do X?" | Policies, rules |

## Files

- `combined_memory.py` - Combined memory implementation
- `05_combined_memory.ipynb` - Tutorial notebook with concepts

## Quick Start

```python
from combined_memory import (
    create_combined_memory_tools,
    COMBINED_MEMORY_INSTRUCTIONS
)

# Create all memory tools
all_tools, memory_agent = create_combined_memory_tools()

# Create agent with all memory types
agent = client.as_agent(
    name="TravelAssistant",
    instructions=COMBINED_MEMORY_INSTRUCTIONS,
    tools=all_tools
)
```

## Memory Routing

The agent routes queries based on patterns:

| Query Pattern | Memory Type |
|--------------|-------------|
| "last time", "before" | Episodic |
| "I prefer", "my usual" | Semantic |
| "policy", "how do I" | Procedural |
| Complex requests | Multiple |

## Tools Included

From Episodic Memory:
- `remember_event_local` - Store events
- `recall_events_local` - Retrieve events

From Semantic Memory:
- `learn_about_user_local` - Store facts
- `query_user_knowledge_local` - Query facts

From Procedural Memory:
- `find_procedure_local` - Search policies
- `get_policy_details_local` - Get specific policy

## Prerequisites

- Completed Modules 1-4
- Understanding of all memory types

## Related

- [Module 4: Procedural Memory](../04_procedural_memory/)
- [Module 6: Memory Handoff](../06_memory_handoff/)

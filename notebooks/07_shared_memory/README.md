# Module 7: Shared Memory Store

This module implements centralized memory using Redis for distributed agent scenarios.

## Overview

When agents are distributed across multiple instances or regions, they need a shared memory store:

```
Agent Node 1 (East) ──┐
                      ├──▶ Redis Memory Store
Agent Node 2 (West) ──┘
```

## Files

- `shared_memory.py` - Redis memory store implementation
- `07_shared_memory.ipynb` - Tutorial notebook with concepts
- `steps/01_setup_redis.md` - Redis setup guide

## Quick Start

```python
from shared_memory import create_shared_memory_tools, InMemorySharedStore

# Create tools (uses in-memory fallback if no Redis)
tools, store = create_shared_memory_tools()

# Store shared memory
await store.store(
    user_id="user123",
    entry_type="semantic",
    key="preference_airline",
    value="Delta"
)

# Retrieve from any agent
entry = await store.retrieve("user123", "semantic", "preference_airline")
print(entry.value)  # "Delta"
```

## Features

| Feature | Description |
|---------|-------------|
| **Key-Value** | Fast memory access |
| **TTL** | Auto-expire working memory |
| **Sorted Sets** | Temporal queries |
| **Pub/Sub** | Real-time synchronization |

## Memory Types

| Type | TTL | Purpose |
|------|-----|---------|
| `episodic` | Long/None | Past events |
| `semantic` | Long/None | Facts and preferences |
| `procedural` | Long/None | Cached policies |
| `working` | Short | Current context |

## Tools

| Tool | Purpose |
|------|---------|
| `store_shared_local` | Store memory entry |
| `retrieve_shared_local` | Get memory by key or recent |

## Prerequisites

- Completed Modules 1-6
- Redis (optional - in-memory fallback available)

## Related

- [Module 6: Memory Handoff](../06_memory_handoff/)
- [Module 8: Production](../08_production/)

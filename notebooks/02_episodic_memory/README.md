# Module 2: Episodic Memory with Cosmos DB

## Learning Objectives

By the end of this module, you will:

1. Understand **episodic memory** and when to use it
2. Create memory **tools** using the `@tool` decorator
3. Build an agent that stores and recalls past events
4. Implement persistent storage with Azure Cosmos DB

## Prerequisites

- Completed Module 1 (Agent Basics)
- Azure AI Foundry Project with gpt-5 deployment
- (Optional) Azure Cosmos DB account for persistence

## Time

~45 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `episodic_memory.py` | Cosmos DB implementation + tools |
| `02_episodic_memory.ipynb` | Hands-on notebook with concepts |
| `steps/01_setup_cosmos.md` | Cosmos DB setup guide |

## Key Concepts

### What is Episodic Memory?

Episodic memory stores **specific events** — what happened, when, and where.

```
"Last month I stayed at the Marriott in NYC"
    → Event stored with timestamp

"What hotels have I stayed at?"
    → Query returns relevant events
```

### Memory as Tools

Instead of injecting memory into prompts, we expose memory operations as **tools** that the agent calls:

```python
@tool
async def remember_event(user_id: str, event_type: str, description: str) -> str:
    """Store a past event."""
    # Implementation stores to Cosmos DB
    
@tool  
async def recall_events(user_id: str, query: str = None) -> str:
    """Recall past events."""
    # Implementation queries Cosmos DB
```

The LLM decides **when** to call these tools based on the conversation.

### Why Cosmos DB?

| Feature | Benefit |
|---------|---------|
| Document storage | Events are naturally JSON documents |
| Partition by user | Efficient user-scoped queries |
| Time-based ordering | Events have timestamps |
| Global distribution | Low latency worldwide |

## Quick Start

1. **Without Cosmos DB** (in-memory):
   ```bash
   # Just run the notebook - uses in-memory storage
   jupyter notebook 02_episodic_memory.ipynb
   ```

2. **With Cosmos DB** (persistent):
   ```bash
   # Follow steps/01_setup_cosmos.md first
   # Then add to .env:
   COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
   ```

## What You'll Build

An agent that:
- Stores events when user shares past experiences
- Recalls events when planning or recommending
- Uses Cosmos DB for persistent storage (optional)

```
User: "I stayed at the Marriott last month and loved it"
Agent: [calls remember_event] "I've noted your positive experience!"

User: "What hotel should I book in NYC?"
Agent: [calls recall_events] "Based on your great stay at the Marriott..."
```

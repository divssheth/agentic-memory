# Module 1: Agent Basics + Session Memory

## Learning Objectives

By the end of this module, you will:

1. Create an agent using the **Microsoft Agent Framework**
2. Understand how `AzureAIClient.as_agent()` works
3. Implement multi-turn conversations with session memory
4. Use streaming for better user experience
5. Recognize the difference between transient and persistent memory

## Prerequisites

- Python 3.11+
- Azure AI Foundry Project with model deployment (configured via `FOUNDRY_MODEL`)
- `az login` or managed identity configured

## Time

~30 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `01_what_is_memory.ipynb` | Hands-on notebook with concepts and runnable examples |

## Key Concepts

### The Stateless Problem

LLMs don't remember anything between API calls. Each request is independent:

```
Call 1: "My name is Sarah"     → "Nice to meet you, Sarah!"
Call 2: "What's my name?"      → "I don't know your name."
```

This is frustrating for users who expect continuity.

### The Solution: Session Memory

The Microsoft Agent Framework provides built-in session handling:

```python
async with AzureAIClient(...).as_agent(...) as agent:
    # Multiple calls within the same session share context
    response = await agent.run("My name is Sarah")
    response = await agent.run("What's my name?")  # ✅ Remembers!
```

### Transient vs Persistent

| Type | Lifespan | Example |
|------|----------|---------|
| **Transient** | Single session | Conversation history in a list |
| **Persistent** | Across sessions | User preferences in a database |

This module focuses on **transient memory** — we'll add persistence in Module 3.

## What You'll Build

A simple travel assistant that:
- ❌ First: Forgets everything (demonstrates the problem)
- ✅ Then: Remembers the conversation (demonstrates the solution)

## Navigation

- → Next: [Module 2: Episodic Memory](../02_episodic_memory/)

# Module 7: Shared Memory

The capstone module. Every module so far served one user — Sarah Chen. Real systems serve many users through the same agent. This module introduces **shared memory** — a layered architecture where some knowledge is global, some is per-user, and some is temporary.

## Learning Objectives

By the end of this module, you will:

1. Implement **multi-user isolation** — one agent, multiple users, private memory per user
2. Build a **global knowledge layer** — company policies accessible to all, modifiable by none
3. Create **working memory with TTL** — ephemeral context that expires after the session
4. Implement **memory promotion** — moving temporary context to permanent storage

## Prerequisites

- Completed Modules 1–6
- Azure AI Foundry Project with model deployment (configured via `FOUNDRY_MODEL`)

## Time

~45 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `07_shared_memory.ipynb` | Hands-on notebook with concepts |
| `steps/01_setup_redis.md` | Redis setup guide (optional, for production persistence) |

## Architecture

```
┌──────────────────────────────────────────────┐
│           Global Knowledge Layer              │
│  (travel policies, org chart, vendors)        │
│  READ-ONLY for agents                         │
├──────────┬──────────┬──────────┬─────────────┤
│ E001     │ E002     │ E003     │ ...         │
│ Memory   │ Memory   │ Memory   │             │
│ (private)│ (private)│ (private)│             │
│ r/w      │ r/w      │ r/w      │             │
└──────────┴──────────┴──────────┴─────────────┘
```

## Tools

| Tool | Layer | Purpose |
|------|-------|---------|
| `get_current_user` | Identity | Simulate auth — identify the current user |
| `remember_event` | User (episodic) | Store events scoped to current user |
| `recall_events` | User (episodic) | Search current user's event history |
| `learn_preference` | User (semantic) | Store facts/preferences for current user |
| `query_preferences` | User (semantic) | Query current user's stored preferences |
| `query_company_knowledge` | Global | Read-only company policies and org info |
| `set_working_memory` | Working | Temporary session context with TTL |
| `get_working_memory` | Working | Retrieve session context |
| `promote_working_memory` | Working → Permanent | Move temp context to episodic or semantic |

## Key Insight

Isolation is enforced at the **tool layer**, not the prompt. Every memory tool automatically scopes to `_current_user_id`. The agent cannot access another user's data because the tools don't accept a user ID parameter — it's injected from the simulated auth layer.

## Quick Start

```bash
# Runs entirely in-memory — no external services needed
jupyter notebook 07_shared_memory.ipynb

# For production persistence, follow steps/01_setup_redis.md
# and set REDIS_URL in .env
```

## Navigation

- ← Previous: [Module 6: Memory Handoff](../06_memory_handoff/)

# 01 Foundations — Implementation Plan

## Module Narrative

> "Agents forget between sessions — that's the problem."

This module introduces what agentic memory is, why it matters, and demonstrates the amnesia problem that motivates the entire framework. Users build a simple travel agent and observe that it loses all context between sessions.

---

## Status: ✅ IMPLEMENTED

---

## Notebook: `agentic_memory_basics.ipynb`

### Objective

Show that LLM agents without persistent memory cannot maintain continuity. Establish the travel agent domain that runs through all subsequent modules.

### What's Implemented

1. **Environment setup** — Azure OpenAI client, model configuration, mode selector (local/cloud)
2. **Tool definitions** — `search_flights`, `search_hotels`, `get_travel_policy` using `data/` JSON files
3. **Basic agent** — Stateless travel assistant using Agents SDK
4. **Amnesia demonstration** — Multi-turn conversation works within a session; fails across sessions
5. **Problem statement** — Motivates the four memory layers introduced in Module 02

### Key Takeaways for Users

- An agent without memory is stateless — it cannot learn, adapt, or personalise
- Session-scoped chat history is the baseline but insufficient for enterprise use
- Memory is not just "storing messages" — it's curated, typed, and governed knowledge

### Dependencies

- `shared/travel_agent.py` — reusable client factory and tool definitions
- `data/*.json` — employees, flights, hotels, travel policies, past trips

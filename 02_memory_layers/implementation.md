# 02 Memory Layers — Implementation Plan

## Module Narrative

> "Here are four memory types that solve the amnesia problem — each with different persistence, structure, and purpose."

This module implements the core memory taxonomy: chat history (short-term), episodic (event-based), semantic (knowledge graph), and procedural (workflow/skill). Together they form the foundation that all later modules govern, evaluate, and secure.

---

## Status: ✅ IMPLEMENTED

---

## Notebook: `01_chat_history.ipynb`

### Objective

Persist conversation history across sessions using Cosmos DB with automatic compaction.

### What's Implemented

1. Cosmos DB `CosmosHistoryProvider` — messages persisted by `session_id`
2. `CompactionProvider` + `SummarizationStrategy` — LLM-based summarisation when history exceeds target token window
3. Cross-session continuity demo — agent remembers prior conversation after restart
4. Token budget management — show unbounded growth problem and compaction solution

### Storage Backend

- Azure Cosmos DB (container: partitioned by `/session_id`)

---

## Notebook: `02_episodic_memory.ipynb`

### Objective

Store structured events (trips, preferences, feedback) that the agent curates from conversations.

### What's Implemented

1. Event schema: `{ id, user_id, event_type, description, details, timestamp }`
2. `remember_event(user_id, event_type, description, details)` — agent decides what's worth storing
3. `recall_events(user_id, event_type, limit)` — filtered retrieval
4. Demo: agent remembers past trip feedback and uses it for future recommendations
5. Distinction: raw transcript vs curated memory (agent as curator)

### Storage Backend

- Azure Cosmos DB (container: `episodic-events`, partition key: `/user_id`)

---

## Notebook: `03_semantic_memory.ipynb`

### Objective

Build a knowledge graph of durable facts, relationships, and preferences with entity deduplication.

### What's Implemented

1. **LLMEntityExtractor** — auto-extracts entities (Person, Organization, Location, Event, Object) and relationships from conversation
2. **Deduplication** — fuzzy matching + embedding-based merge (threshold 0.92)
3. **Three storage buckets**:
   - Entities (typed nodes)
   - Relationships (edges: `PREFERS`, `LOCATED_IN`, `WORKS_AT`)
   - Preferences (natural language + vector embeddings for semantic retrieval)
4. **Multi-hop reasoning** — traverse graph to combine facts from different conversations
5. **Confidence scoring** — `memory.add_preference(category, preference, confidence=0.9)`

### Storage Backend

- Neo4j AuraDB (free tier: 50K nodes)
- Vector embeddings for preference similarity search

### Key Design Decision

Preferences stored as natural language with embeddings (not rigid schema). Solves the "infinite schema" problem — any preference can be stored and semantically retrieved.

---

## Notebook: `04_procedural_memory.ipynb`

### Objective

Demonstrate three levels of procedural memory maturity: static skills, RAG-discovered procedures, and reflection-based learning.

### What's Implemented

#### Approach 1: SkillsProvider (Static)
- SKILL.md files in `skills/` folder with YAML frontmatter
- `load_skill("international-booking")` — loads checklist + bundled resources
- `read_skill_resource("budget-limits.json")` — supporting data

#### Approach 2: RAG-Based (Dynamic)
- Procedures indexed in Azure AI Search
- `search_procedures("international flight booking")` — semantic discovery
- Policy teams update docs → agent auto-discovers new procedures

#### Approach 3: Reflection-Based (Learned)
- Agent stores lessons in `procedural-reflections` container (Cosmos DB)
- `store_reflection(task_type, lesson)` / `recall_reflections(task_type)`
- Demo: Dubai transit visa lesson learned → proactively mentioned next time

### Storage Backends

- File system (skills/)
- Azure AI Search (RAG procedures)
- Cosmos DB (reflections container)

---

## Supporting Resources

| Resource | Purpose |
|----------|---------|
| `skills/domestic-booking/SKILL.md` | 6-step domestic booking checklist |
| `skills/international-booking/SKILL.md` | 9-step international booking checklist |
| `skills/international-booking/visa-checklist.md` | Visa reference document |
| `skills/*/budget-limits.json` | Budget constraints by employee level |
| `steps/01_setup_cosmos.md` | Cosmos DB provisioning guide |
| `steps/02_setup_neo4j.md` | Neo4j AuraDB setup guide |

# Module 3: Semantic Memory with Neo4j

## Learning Objectives

By the end of this module, you will:

1. Understand **semantic memory** and knowledge graphs
2. Use LLM for **dynamic knowledge extraction**
3. Implement **canonicalization** for synonym handling
4. Handle **contradictions** (newer wins strategy)
5. Build an agent that learns and recalls user knowledge

## Prerequisites

- Completed Module 2 (Episodic Memory)
- Azure AI Foundry Project with gpt-5 deployment
- (Optional) Neo4j database for persistence

## Time

~60 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `semantic_memory.py` | Neo4j implementation + tools |
| `03_semantic_memory.ipynb` | Hands-on notebook with concepts |
| `steps/01_setup_neo4j.md` | Neo4j setup guide |

## Key Concepts

### What is Semantic Memory?

Semantic memory stores **facts and relationships** — not events.

```
    ┌─────────┐     PREFERS     ┌─────────┐
    │  Sarah  │───────────────▶ │  Delta  │
    └────┬────┘                 └─────────┘
         │ REQUIRES
         ▼
    ┌─────────────┐
    │ Wheelchair  │
    └─────────────┘
```

### Dynamic Schema Extraction

Instead of hardcoded relationship types, we use LLM to extract knowledge:

```python
# User says: "I prefer Delta and need wheelchair help"
triplets = await extract_knowledge_triplets(statement)
# → [
#     {relationship: "prefers", object: "Delta", type: "airline"},
#     {relationship: "needs", object: "wheelchair help", type: "accessibility"}
# ]
```

### Canonicalization

Map synonyms to canonical forms:
- "needs", "requires", "must have" → **REQUIRES**
- "prefers", "likes", "favors" → **PREFERS**

### Why Neo4j?

| Feature | Benefit |
|---------|---------|
| Graph structure | Natural for relationships |
| Cypher queries | Powerful relationship traversal |
| MERGE operations | Idempotent updates |
| Labels | Dynamic entity typing |

## Quick Start

1. **Without Neo4j** (in-memory):
   ```bash
   jupyter notebook 03_semantic_memory.ipynb
   ```

2. **With Neo4j** (persistent):
   ```bash
   # Follow steps/01_setup_neo4j.md first
   # Add to .env:
   NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your-password
   ```

## What You'll Build

An agent that:
- Extracts knowledge from natural language
- Stores it in a graph (canonicalized)
- Handles contradictions gracefully
- Queries for personalization

```
User: "I prefer Delta and need wheelchair assistance"
Agent: [extracts & stores]
       - Sarah PREFERS Delta (AIRLINE)
       - Sarah REQUIRES wheelchair assistance (ACCESSIBILITY)

User: "What airlines do I like?"
Agent: [queries graph] "You prefer Delta."
```

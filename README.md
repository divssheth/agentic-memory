# Agentic Memory Tutorial Series

A progressive tutorial teaching memory patterns in AI agents — from transient to persistent to multi-agent shared memory — using a **Corporate Travel Assistant** as the consistent scenario.

## Learning Journey

| Module | Concept | What You'll Build |
|--------|---------|-------------------|
| **1. Agent Basics + Session Memory** | Stateless vs stateful agents | A travel assistant that forgets vs remembers within a session |
| **2. Episodic Memory** | Persisting events to Cosmos DB | Selective memory — the agent decides what's worth remembering |
| **3. Semantic Memory** | Facts & preferences in Neo4j | A knowledge graph of user preferences and relationships |
| **4. Procedural Memory** | Skills, procedures, budget rules | Domain-specific behaviors loaded from SKILL.md files |
| **5. Combined Memory** | All memory types + conflict resolution | Priority hierarchies when memories disagree |
| **6. Memory Handoff** | Passing context between agents | Router → specialist agent memory transfer |
| **7. Shared Memory** | Multi-user isolation | Concurrent users with isolated memory stores (Redis optional) |

## Scenario: Corporate Travel Assistant

Throughout this series, we build a travel booking system that:
- **Remembers** past trips and experiences (episodic memory — Cosmos DB)
- **Knows** preferences and relationships (semantic memory — Neo4j)
- **Follows** company policies and procedures (procedural memory — skills)
- **Resolves** conflicts when memories disagree (combined memory)
- **Hands off** context between specialized agents (memory handoff)
- **Shares** memory across users with isolation (shared memory — Redis)

## Prerequisites

- Python 3.11+
- Azure subscription with:
  - Azure AI Foundry project (endpoint in `.env`)
  - Model deployment (configured via `FOUNDRY_MODEL` in `.env`)
- Module-specific backends (set up as you progress):
  - **Module 2+**: Azure Cosmos DB (episodic memory + chat history)
  - **Module 3+**: Neo4j (semantic memory)
  - **Module 7**: Redis (optional — runs in-memory by default)

## Quick Start

```bash
# Clone and setup
cd agentic-memory
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure credentials

# Start with Module 1
jupyter notebook notebooks/01_what_is_memory/01_what_is_memory.ipynb
```

## Project Structure

```
agentic-memory/
├── data/                          # Shared data (employees, flights, hotels, policies)
├── notebooks/
│   ├── 01_what_is_memory/         # Session memory basics
│   ├── 02_episodic_memory/        # Events → Cosmos DB
│   ├── 03_semantic_memory/        # Facts → Neo4j
│   ├── 04_procedural_memory/      # Skills + budget rules
│   ├── 05_combined_memory/        # Conflict resolution
│   ├── 06_memory_handoff/         # Agent-to-agent context transfer
│   └── 07_shared_memory/          # Multi-user isolation (Redis)
├── src/                           # Reusable modules
├── requirements.txt               # Python dependencies
└── azure.yaml                     # Azure Developer CLI config
```

Each module folder contains:
- `XX_module_name.ipynb` — the tutorial notebook
- `README.md` — module-specific setup instructions
- `steps/` — backend setup guides (where applicable)
- `prompts/` or `skills/` — procedural memory assets (where applicable)

## Environment Variables

```env
FOUNDRY_PROJECT_ENDPOINT=https://...
FOUNDRY_MODEL=gpt-4o
AZURE_TENANT_ID=your-tenant-id
COSMOS_ENDPOINT=https://...documents.azure.com:443/
NEO4J_URI=neo4j+s://...
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
REDIS_URL=redis://...          # Module 7 only
```

## License

MIT

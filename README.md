# Agentic Memory Tutorial Series

A progressive tutorial teaching memory patterns in AI agents—from transient to persistent to multi-agent shared memory—using a **Corporate Travel Assistant** as the consistent scenario.

## Learning Journey

| Module | Concept | Duration |
|--------|---------|----------|
| **1. What is Agent Memory?** | Stateless vs stateful agents | 30 min |
| **2. Memory Types Explained** | Episodic, Semantic, Procedural | 30 min |
| **3. Persisting Memory** | Memory that survives restarts | 30 min |
| **4. Vector Memory & Semantic Search** | Embedding-based retrieval | 30 min |
| **5. Single Agent, Full Memory Stack** | All memory types combined | 30 min |
| **6. Memory Handoff Between Agents** | Passing context between agents | 30 min |
| **7. Shared Memory Store** | Multiple agents, one memory | 30 min |
| **8. Production Deployment** | Deployable multi-agent system | 45 min |

## Scenario: Corporate Travel Assistant

Throughout this series, we build a travel booking system that:
- **Remembers** your past trips (episodic memory)
- **Knows** your preferences (semantic memory)
- **Follows** company policies (procedural memory)
- **Coordinates** between multiple agents (shared memory)

## Prerequisites

- Python 3.11+
- Azure subscription with:
  - Azure AI Foundry Project (new, not classic)
  - Azure OpenAI deployment (GPT-4o recommended)
  - Azure AI Search (for Modules 4+)
  - Cosmos DB (for Modules 5+)
  - Redis Cache (for Module 7+)

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
jupyter notebook notebooks/01_what_is_memory.ipynb
```

## Project Structure

```
agentic-memory/
├── data/                    # Mock data (employees, flights, hotels, policies)
├── notebooks/               # All tutorial modules
│   ├── 01_what_is_memory/
│   ├── 02_memory_types/
│   ├── 03_persistent_memory/
│   ├── 04_vector_memory/
│   ├── 05_single_agent/
│   ├── 06_memory_handoff/
│   ├── 07_shared_memory/
│   └── 08_production/
├── src/                     # Reusable code
│   ├── memory/              # Memory implementations
│   ├── agents/              # Agent implementations
│   └── tools/               # Agent tools
└── azure.yaml               # Azure Developer CLI config
```

## Azure Infrastructure

| Resource | Purpose | Created In |
|----------|---------|------------|
| Azure AI Foundry Project | Agent hosting, model access | Pre-requisite |
| Azure OpenAI | LLM for agents | Pre-requisite |
| Azure AI Search | Vector memory, semantic retrieval | Module 4 |
| Cosmos DB | Persistent episodic/semantic memory | Module 5 |
| Redis Cache | Shared session state | Module 7 |

## License

MIT

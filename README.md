# Agentic Memory Tutorial Series

A progressive tutorial teaching memory patterns in AI agents — from foundations through lifecycle management to multi-agent architecttic — using a **Corporate Travel Assistant** as the consistent scenario.

Every notebook follows a **problem-first** structure: demonstrate a failure → name it → introduce the fix → show the payoff.

## Learning Journey

| Module | Folder | What You'll Build |
|--------|--------|-------------------|
| **01 Foundations** | `01_foundations/` | Stateless vs stateful agents; session memory basics |
| **02 Memory Layers** | `02_memory_layers/` | Chat history (Cosmos), episodic (Cosmos), semantic (Neo4j), procedural (Skills) |
| **03 Memory Lifecycle** | `03_memory_lifecycle/` | Identification, promotion, belief revision, retention, episodic/procedural lifecycle |
| **04 Provenance & Audit** | `04_provenance_and_audit/` | Who created a memory, why it was trusted, how it influenced decisions |
| **05 Retrieval** | `05_retrieval/` | Hybrid search, re-ranking, context window management |
| **06 Governance** | `06_governance/` | Policy enforcement, access control, compliance |
| **07 Security** | `07_security/` | Memory poisoning defense, prompt injection, isolation |
| **08 Evaluation** | `08_evaluation/` | Measuring memory quality, precision, staleness |
| **09 Multi-Agent** | `09_multi_agent/` | Shared memory, handoff, multi-user isolation |
| **10 Frontier** | `10_frontier/` | Emerging patterns and research directions |

## Scenario: Corporate Travel Assistant

Throughout this series, we build a travel booking system that:
- **Remembers** past trips and experiences (episodic memory — Cosmos DB)
- **Knows** preferences and relationships (semantic memory — Neo4j)
- **Follows** company policies and procedures (procedural memory — SKILL.md files)
- **Grounds** answers in authoritative policy (RAG via AI Search)
- **Manages** memory lifecycle: identification → promotion → revision → retention

## Prerequisites

- Python 3.11+ (tested on 3.14)
- Azure subscription with:
  - Azure AI Foundry project (endpoint + model deployment)
  - Azure Cosmos DB (episodic + chat history)
  - Azure AI Search (RAG ground truth — Module 03+)
  - Neo4j Aura (semantic memory — Module 02+)
- Authentication: Azure CLI (`az login`)

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
jupyter notebook 01_foundations/agentic_memory_basics.ipynb
```

## Project Structure

```
agentic-memory/
├── 01_foundations/                 # Agent basics, session memory
│   └── agentic_memory_basics.ipynb
├── 02_memory_layers/              # Four memory types
│   ├── 01_chat_history.ipynb      # Cosmos DB chat persistence
│   ├── 02_episodic_memory.ipynb   # Event storage + recall
│   ├── 03_semantic_memory.ipynb   # Neo4j knowledge graph
│   ├── 04_procedural_memory.ipynb # Skills + budget rules
│   ├── skills/                    # SKILL.md procedure files
│   └── steps/                     # Backend setup guides
├── 03_memory_lifecycle/           # Complete lifecycle management
│   ├── 00_setup_ai_search.ipynb   # RAG index provisioning
│   ├── 01_memory_vs_rag.ipynb     # Context vs RAG vs Memory
│   ├── 02_memory_identification.ipynb  # What to store
│   ├── 03_staged_promotion.ipynb  # Trust state machine
│   ├── 04_belief_revision.ipynb   # Bi-temporal fact tracking
│   ├── 05_retention_and_decay.ipynb # Bounded memory + eviction
│   ├── 06_episodic_lifecycle.ipynb # TTL + cross-session graduation
│   ├── 07_procedural_lifecycle.ipynb # RAG validation of procedures
│   └── lifecycle_utils.py         # Shared dataclasses + engines
├── 04_provenance_and_audit/       # (planned)
├── 05_retrieval/                  # (planned)
├── 06_governance/                 # (planned)
├── 07_security/                   # (planned)
├── 08_evaluation/                 # (planned)
├── 09_multi_agent/                # (planned)
├── 10_frontier/                   # (planned)
├── data/                          # Employees, flights, hotels, policies
│   └── policies/                  # Corporate policy documents (RAG source)
├── shared/                        # Reusable utilities
│   └── travel_agent.py            # Client factory, tools, system prompt
├── notebooks/                     # Legacy notebook layout (being migrated)
├── requirements.txt
└── azure.yaml
```

## Environment Variables

```env
FOUNDRY_PROJECT_ENDPOINT=https://your-foundry.services.ai.azure.com/api/projects/proj-default
FOUNDRY_MODEL=gpt-5-mini
AZURE_TENANT_ID=your-tenant-id
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-admin-key
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
```

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| `sniffio` context var instead of `nest_asyncio` | Python 3.14 compatibility |
| Top-level `await` instead of `asyncio.run()` | Jupyter kernel already runs event loop |
| Account-level Foundry endpoint for embeddings | Project-level returns 404 for `/embeddings` |
| `AzureKeyCredential` for AI Search data-plane | `AzureCliCredential` gets 403 on search ops |
| Mermaid diagrams over ASCII art | Renders natively in VS Code + GitHub |

## License

MIT

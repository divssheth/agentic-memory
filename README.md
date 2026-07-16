# Agentic Memory Tutorial Series

A progressive tutorial teaching memory patterns in AI agents — from foundations through lifecycle management to a unified production agent — using a **Corporate Travel Assistant** as the consistent scenario.

Every notebook follows a **problem-first** structure: demonstrate a failure → name it → introduce the fix → show the payoff. Each module builds on the previous one — the same agent accumulates capabilities until Module 10, where everything converges into one agent that does memory well.

## Learning Journey

| Module | Folder | Notebooks | What You'll Build |
|--------|--------|-----------|-------------------|
| **01 Foundations** | `01_foundations/` | 1 | Stateless vs stateful agents; session memory basics |
| **02 Memory Layers** | `02_memory_layers/` | 4 | Chat history (Cosmos), episodic (Cosmos), semantic (Neo4j), procedural (SkillsProvider) |
| **03 Memory Lifecycle** | `03_memory_lifecycle/` | 7 | Identification, staged promotion (Neo4j), belief revision (SCD Type 2), retention, episodic/procedural lifecycle |
| **04 Provenance & Confidence** | `04_provenance_and_audit/` | 1 | `explain_belief` tool + confidence-aware recall (assert / hedge / ask) |
| **05 Retention & Routing** | `05_retrieval/` | 2 | Bounded memory with eviction scoring; multi-store agent (LLM-as-router) |
| **06 Governance & User Control** | `06_governance/` | 2 | User inspect/correct/delete tools; role-based memory scoping via middleware |
| **07 Security** | `07_security/` | 2 | Memory poisoning attacks (3 channels); defense-in-depth (origin ceiling + Sybil resistance) |
| **08 Evaluation** | `08_evaluation/` | 2 | MEMPROBE-style quality probing; sycophancy + adversarial robustness testing |
| **09 Multi-Agent** | `09_multi_agent/` | 2 | Scoped memory handoff between agents; cross-user isolation on shared Neo4j |
| **10 Unified Agent** | `10_unified_agent/` | 1 | Capstone: one MAF agent with ALL memory capabilities in a 12-turn demo |

**Total: 24 notebooks** — each using Microsoft Agent Framework (MAF) agents with `@tool`, never standalone Python demo code.

## Scenario: Corporate Travel Assistant

Throughout this series, we build **one** travel booking agent that progressively gains:
- **Memory layers** — past trips (episodic / Cosmos DB), preferences (semantic / Neo4j), policies (procedural / SkillsProvider), chat history (AgentSession)
- **Lifecycle management** — what to store, when to trust it, how to revise it, when to evict it
- **Provenance & confidence** — explain any belief, hedge uncertain ones, assert confirmed ones
- **Governance** — users inspect/correct/delete their profile; agents see only their allowed scope
- **Security** — staged promotion + origin ceiling + Sybil-resistant corroboration = 0% attack success
- **Evaluation** — memory quality probing, sycophancy detection, adversarial robustness
- **Multi-agent** — scoped handoff, cross-user isolation on shared storage

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
├── 03_memory_lifecycle/           # Lifecycle management (Neo4j-backed)
│   ├── 00_setup_ai_search.ipynb   # RAG index provisioning
│   ├── 01_memory_vs_rag.ipynb     # Context vs RAG vs Memory
│   ├── 02_memory_identification.ipynb  # SkillsProvider + ToolApprovalMiddleware
│   ├── 03_staged_promotion_neo4j.ipynb # GraphPromotionStore trust state machine
│   ├── 04_belief_revision.ipynb   # GraphBeliefStore + SCD Type 2
│   ├── 05_retention_and_decay.ipynb # Bounded memory + eviction
│   ├── 06_episodic_lifecycle.ipynb # TTL + cross-session graduation
│   ├── 07_procedural_lifecycle.ipynb # RAG validation of procedures
│   ├── lifecycle_utils.py         # Shared stores + engines (grows each module)
│   └── skills/                    # Memory identification skills
├── 04_provenance_and_audit/       # Provenance + confidence-aware recall
│   └── 01_provenance_and_confidence.ipynb
├── 05_retrieval/                  # Retention + multi-store routing
│   ├── 01_retention_and_decay.ipynb
│   └── 02_memory_routing.ipynb
├── 06_governance/                 # User control + access scoping
│   ├── 01_user_control.ipynb
│   └── 02_access_control.ipynb
├── 07_security/                   # Attack surface + defense layers
│   ├── 01_attack_surface.ipynb
│   └── 02_defense_in_depth.ipynb
├── 08_evaluation/                 # Quality probing + sycophancy testing
│   ├── 01_memory_quality.ipynb
│   └── 02_sycophancy_and_adversarial.ipynb
├── 09_multi_agent/                # Handoff + cross-user isolation
│   ├── 01_memory_handoff.ipynb
│   └── 02_shared_memory.ipynb
├── 10_unified_agent/              # Capstone: one agent, all capabilities
│   └── 01_unified_memory_agent.ipynb
├── data/                          # Employees, flights, hotels, policies
├── shared/                        # Reusable utilities
│   └── travel_agent.py            # Client factory, tools, system prompt
├── notebooks/                     # Legacy notebook layout (being migrated)
├── requirements.txt
└── azure.yaml
```

## Shared Infrastructure: `lifecycle_utils.py`

All lifecycle capabilities accumulate in one shared module:

| Class | Module | Purpose |
|-------|--------|---------|
| `GraphPromotionStore` | 3.3 | Trust state machine: candidate → provisional → trusted |
| `GraphBeliefStore` | 3.4 | SCD Type 2 belief revision with time-travel queries |
| `RetentionScorer` | 3.5 / 5.1 | Multi-signal scoring for bounded memory eviction |
| `MemoryScopeMiddleware` | 6.2 | Role-based memory filtering via MAF middleware |
| `create_baseline_agent()` | 3.x | Factory with `context_providers` + `middleware` params |

Each later module adds methods to these classes rather than creating new ones.

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

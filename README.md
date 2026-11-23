# Agentic Memory Tutorial Series

A progressive tutorial teaching memory patterns in AI agents — from foundations through lifecycle management to a unified production agent — using a **Corporate Travel Assistant** as the consistent scenario.

Every notebook follows a **problem-first** structure: demonstrate a failure → name it → introduce the fix → show the payoff. Each module builds on the previous one — the same agent accumulates capabilities until Module 10, where everything converges into one agent that does memory well.

## Learning Journey

| Module | Folder | Notebooks | Status | What You'll Build |
|--------|--------|-----------|--------|-------------------|
| **01 Foundations** | `01_foundations/` | 1 | ✅ Complete | Stateless vs stateful agents; session memory basics |
| **02 Memory Layers** | `02_memory_layers/` | 4 | ✅ Complete | Chat history (Cosmos), episodic (Cosmos), semantic (Cosmos vector search), procedural (SkillsProvider) |
| **03 Memory Lifecycle** | `03_memory_lifecycle/` | 7 | ✅ Complete | Memory vs RAG, identification, staged promotion, belief revision (SCD Type 2), retention, episodic + procedural lifecycle |
| **04 Provenance & Confidence** | `04_provenance_and_audit/` | 1 | 🧪 Ready to test | `explain_belief` tool + confidence-aware recall (assert / hedge / ask) |
| **05 Retrieval & Routing** | `05_retrieval/` | 2 | 📋 Planned | Lifecycle-aware bounded retrieval; multi-store agent (LLM-as-router) |
| **06 Governance & User Control** | `06_governance/` | 2 | 📋 Planned | Inspect/correct/retire/erase tools with verified erasure; role-based memory scoping |
| **07 Security** | `07_security/` | 2 | 📋 Planned | Memory poisoning and unauthorized erasure attacks; defense-in-depth (origin ceiling + independent corroboration) |
| **08 Evaluation** | `08_evaluation/` | 2 | 📋 Planned | MEMPROBE-style quality probing; canary erasure test; sycophancy + adversarial robustness testing |
| **09 Multi-Agent** | `09_multi_agent/` | 2 | 📋 Planned | Scoped memory handoff between agents; cross-user isolation on shared Cosmos containers |
| **10 Unified Agent** | `10_unified_agent/` | 1 | 📋 Planned | Capstone: one MAF agent with ALL memory capabilities in a six-act demo |

**Total: 24 notebooks** — each using Microsoft Agent Framework (MAF) agents with `@tool`, never standalone Python demo code.

## Scenario: Corporate Travel Assistant

Throughout this series, we build **one** travel booking agent that progressively gains:
- **Memory layers** — past trips (episodic / Cosmos DB), preferences (semantic / Cosmos DB vector search), policies (procedural / SkillsProvider), chat history (AgentSession)
- **Lifecycle management** — what to store, when to trust it, how to revise it, when to evict it
- **Provenance & confidence** — explain any belief, hedge uncertain ones, assert confirmed ones
- **Governance** — users inspect/correct/retire/erase their profile; agents see only their allowed scope
- **Security** — staged promotion + origin ceiling + independent corroboration = 0% attack success
- **Evaluation** — memory quality probing, sycophancy detection, adversarial robustness
- **Multi-agent** — scoped handoff, cross-user isolation on shared storage

## Prerequisites

- Python 3.11+ (tested on 3.14)
- Azure subscription with:
  - Azure AI Foundry project (endpoint + model deployment)
  - Azure Cosmos DB for NoSQL with vector search (chat history, episodic and semantic memory)
  - Azure AI Search (RAG ground truth — Module 3+)
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
│   ├── 03_semantic_memory.ipynb   # Cosmos DB vector-backed preferences
│   ├── 04_procedural_memory.ipynb # Skills + budget rules
│   ├── skills/                    # SKILL.md procedure files
│   └── steps/                     # Backend setup guides
├── 03_memory_lifecycle/           # Lifecycle management (Cosmos-backed)
│   ├── 00_setup_ai_search.ipynb   # RAG index provisioning
│   ├── 01_memory_vs_rag.ipynb     # Context vs RAG vs Memory
│   ├── 02_memory_identification.ipynb  # SkillsProvider + ToolApprovalMiddleware
│   ├── 03_staged_promotion.ipynb  # CosmosPromotionStore trust state machine
│   ├── 04_belief_revision.ipynb   # CosmosBeliefStore + SCD Type 2
│   ├── 05_retention_and_decay.ipynb # Bounded memory + eviction scoring
│   ├── 06_episodic_and_procedural_lifecycle.ipynb # TTL-based episodic + 3-tier procedural
│   ├── lifecycle_utils.py         # Shared stores + engines (grows each module)
│   └── skills/                    # Memory identification skills
├── 04_provenance_and_audit/       # Provenance + confidence-aware recall
│   ├── 01_provenance_and_confidence.ipynb
│   └── lifecycle_utils.py         # CosmosProvenanceStore
├── 05_retrieval/                  # Lifecycle-aware retrieval + multi-store routing
│   ├── 01_retrieval_and_ranking.ipynb
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
│   ├── memory_tools.py            # Per-user memory tools + assert/hedge/ask rule
│   ├── semantic_store.py          # SemanticMemoryStore (Cosmos DB + vector search)
│   └── travel_agent.py            # Client factory, tools, system prompt
├── requirements.txt
└── azure.yaml
```

## Shared Infrastructure

All lifecycle stores operate on the same Cosmos DB preference documents managed by
`SemanticMemoryStore` ([shared/semantic_store.py](shared/semantic_store.py)). Module 3's
classes live in [03_memory_lifecycle/lifecycle_utils.py](03_memory_lifecycle/lifecycle_utils.py);
Module 4 adds `CosmosProvenanceStore` in its own
[04_provenance_and_audit/lifecycle_utils.py](04_provenance_and_audit/lifecycle_utils.py).

Agent memory tools are built per user with `make_preference_tools(store)`
([shared/memory_tools.py](shared/memory_tools.py)): the store is bound to one `user_id`,
so the model never chooses whose memories it reads or writes.

| Class | Module | Purpose |
|-------|--------|---------|
| `SemanticMemoryStore` | 2.3 | Cosmos DB preference documents with vector search and SCD Type 2 supersession |
| `MemoryCandidate` | 3.2 | Memorability scores and decision for one conversation turn |
| `PromotionConfig` | 3.3 | Confirmation thresholds and staleness window |
| `CosmosPromotionStore` | 3.3 | Trust state machine: candidate → provisional → trusted |
| `CosmosBeliefStore` | 3.4 | SCD Type 2 belief revision with time-travel queries |
| `RetentionScorer` | 3.5 | Multi-signal scoring for bounded memory eviction |
| `CosmosRetentionStore` | 3.5 | Cosmos-backed capacity-bounded memory store |
| `CosmosProvenanceStore` | 4.1 | Evidence metadata, `explain()` and confidence-aware recall |

## Environment Variables

```env
FOUNDRY_PROJECT_ENDPOINT=https://your-foundry.services.ai.azure.com/api/projects/proj-default
FOUNDRY_MODEL=gpt-5-mini
AZURE_OPENAI_ENDPOINT=https://your-service.openai.azure.com
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
COSMOS_DATABASE=travel-memory
COSMOS_SEMANTIC_CONTAINER=semantic-memory
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-admin-key
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

# Agentic Memory Implementation Roadmap (2026)

This branch implements the new roadmap without modifying legacy notebooks.

## Branch Policy

- Branch: `feature/agentic-memory-roadmap-2026`
- `main` remains unchanged.

## Structure

- `01_foundations`
- `02_memory_layers`
- `03_integration`
- `04_lifecycle`
- `05_retrieval`
- `06_advanced`
- `07_multi_agent`
- `08_evaluation`
- `09_governance`
- `10_frontier`
- `architecture_diagrams`

## Runtime Policy

- One shared repo virtual environment: `.venv`
- All notebooks are self-sufficient.
- Local/cloud behavior is env-driven.
- Foundry is default runtime endpoint.

## Environment Switches

- `AGENTIC_RUN_MODE=local|cloud`
- `FOUNDRY_PROJECT_ENDPOINT` (required for cloud LLM runtime)
- `FOUNDRY_MODEL` (default `gpt-4o`)
- `AZURE_SEARCH_ENDPOINT` (cloud RAG)
- `AZURE_SEARCH_ADMIN_KEY` (cloud RAG)
- `AZURE_SEARCH_INDEX` (cloud RAG index name)

## Cloud Seeding Rule

When `AGENTIC_RUN_MODE=cloud`, notebooks that need services should create and seed required resources (for example, Azure AI Search index + seed docs) instead of assuming preloaded state.

## Copilot SDK Companion (Option B)

Each notebook includes a runnable companion snippet section to map the same scenario flow to GitHub Copilot SDK usage.

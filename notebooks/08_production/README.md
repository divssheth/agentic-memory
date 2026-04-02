# Module 8: Production Deployment

Deploy your agentic memory system to production with observability, scaling, and reliability.

## Overview

This module covers:

- **Production Architecture** - Multi-instance deployment with shared storage
- **Graceful Degradation** - Fallback to in-memory when services unavailable
- **Observability** - Metrics, logging, and health checks
- **Deployment Patterns** - Container Apps, AKS, and other options

## Files

| File | Description |
|------|-------------|
| `production_memory.py` | Production-ready memory system |
| `08_production.ipynb` | Tutorial notebook |
| `api/` | FastAPI server implementation |
| `deploy/` | Deployment configurations |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (all optional for local dev)
export FOUNDRY_PROJECT_ENDPOINT="https://..."
export FOUNDRY_MODEL_DEPLOYMENT_NAME="gpt-4o"

# Run notebook
jupyter notebook 08_production.ipynb
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer                            │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Agent Pod 1   │     │   Agent Pod 2   │     │   Agent Pod 3   │
│  MemorySystem   │     │  MemorySystem   │     │  MemorySystem   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
    ┌───────────┬────────────────┼────────────────┬───────────┐
    │           │                │                │           │
    ▼           ▼                ▼                ▼           ▼
┌───────┐  ┌────────┐     ┌──────────┐     ┌──────────┐  ┌───────┐
│Cosmos │  │ Neo4j  │     │   Redis  │     │AI Search │  │Foundry│
│  DB   │  │        │     │  Cache   │     │          │  │       │
└───────┘  └────────┘     └──────────┘     └──────────┘  └───────┘
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `FOUNDRY_PROJECT_ENDPOINT` | Azure AI Foundry endpoint | Yes |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | Model deployment name | Yes |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint | No |
| `COSMOS_DATABASE` | Database name | No |
| `NEO4J_URI` | Neo4j connection URI | No |
| `NEO4J_USERNAME` | Neo4j username | No |
| `NEO4J_PASSWORD` | Neo4j password | No |
| `AZURE_SEARCH_ENDPOINT` | AI Search endpoint | No |
| `AZURE_SEARCH_INDEX` | Index name | No |
| `REDIS_URL` | Redis connection URL | No |

## Graceful Degradation

When external services are unavailable, the system automatically falls back:

| Service | Fallback | Impact |
|---------|----------|--------|
| Cosmos DB | In-memory store | No cross-session history |
| Neo4j | In-memory graph | No persistent preferences |
| AI Search | Sample policies | Limited policy set |
| Redis | Local store | No cross-instance sync |

## Production Checklist

### Security
- [ ] Use managed identities
- [ ] Configure network isolation
- [ ] Enable audit logging
- [ ] Review RBAC permissions

### Reliability
- [ ] Configure health probes
- [ ] Set up auto-scaling
- [ ] Implement retry logic
- [ ] Test failure scenarios

### Observability
- [ ] Enable Application Insights
- [ ] Configure log aggregation
- [ ] Set up alerts
- [ ] Track custom metrics

## Deployment

### Azure Container Apps

```bash
az containerapp create \
  --name travel-agent \
  --resource-group rg-travel \
  --image myregistry.azurecr.io/travel-agent:latest \
  --target-port 8000 \
  --ingress external
```

### Docker

```bash
docker build -t travel-agent .
docker run -p 8000:8000 \
  -e FOUNDRY_PROJECT_ENDPOINT="..." \
  travel-agent
```

## Related Modules

- [Module 1: Agent Basics](../01_agent_basics/)
- [Module 7: Shared Memory](../07_shared_memory/)

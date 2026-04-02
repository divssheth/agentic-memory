# Module 4: Procedural Memory

Procedural memory stores rules, policies, and procedures that guide agent behavior. It answers: *"How do I do this?"* and *"What are the rules?"*

## Overview

In this module, you'll learn:

- **Procedural memory** concepts and when to use them
- **Azure AI Search** integration for policy retrieval
- **RAG pattern** for grounding responses in authoritative sources
- **Tool design** for policy-aware agents

## Storage Choice: Azure AI Search

| Feature | Why AI Search |
|---------|---------------|
| **Hybrid Search** | Combines keyword and vector search |
| **Filtering** | OData filters for policy types, dates |
| **Relevance** | Semantic ranking for better results |
| **Scale** | Handles large policy libraries |

## Files

- `procedural_memory.py` - Azure AI Search implementation + in-memory fallback
- `04_procedural_memory.ipynb` - Tutorial notebook with concepts
- `steps/01_setup_search.md` - Azure AI Search setup guide
- `steps/02_index_policies.md` - Policy indexing guide

## Quick Start

### With In-Memory Store (No Azure Required)

```python
from procedural_memory import create_in_memory_tools

tools, store = create_in_memory_tools()

# Use with agent
agent = client.as_agent(
    name="PolicyAdvisor",
    instructions="Always look up policies before answering.",
    tools=tools
)
```

### With Azure AI Search (Production)

```python
from procedural_memory import find_procedure, get_policy_details

# Requires AZURE_SEARCH_ENDPOINT in environment

agent = client.as_agent(
    name="PolicyAdvisor",
    instructions="Always look up policies before answering.",
    tools=[find_procedure, get_policy_details]
)
```

## Tools

| Tool | Purpose | When to Call |
|------|---------|--------------|
| `find_procedure` | Search for relevant policies | "How do I...?", "What's the rule for...?" |
| `get_policy_details` | Get specific policy content | "Show me the travel policy" |

## Sample Policies Included

- Corporate Travel Policy (Booking, Approvals, Accessibility)
- Expense Policy (Meal Allowances, Receipts)

## Prerequisites

- Completed Modules 1-3
- Azure AI Search service (optional)

## Related

- [Module 3: Semantic Memory](../03_semantic_memory/)
- [Module 5: Combined Memory](../05_combined_memory/)

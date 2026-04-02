# Agentic Memory - Source Code

This folder contains reusable implementations used across modules.

## Structure

```
src/
├── memory/          # Memory implementations
│   ├── base.py      # Abstract base classes
│   ├── episodic.py  # Event/interaction memory
│   ├── semantic.py  # Facts/preferences memory
│   └── procedural.py # Rules/procedures memory
├── agents/          # Agent implementations
│   ├── travel_planner.py
│   ├── policy_checker.py
│   └── approval_agent.py
├── tools/           # Agent tools
│   └── travel_tools.py
└── storage/         # Storage backends
    ├── json_store.py
    ├── sqlite_store.py
    └── cosmos_store.py
```

## Usage

Import from notebooks/scripts:

```python
from src.memory import EpisodicMemory, SemanticMemory
from src.agents import TravelPlannerAgent
```

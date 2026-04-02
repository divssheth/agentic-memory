"""Build Module 7: Shared Memory notebook."""
import json


def md(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source.strip().split("\n")][:-1] + [source.strip().split("\n")[-1]]
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "source": [line + "\n" for line in source.strip().split("\n")][:-1] + [source.strip().split("\n")[-1]],
        "outputs": [],
        "execution_count": None
    }


cells = []

# ============================================================
# Cell 1: Install
# ============================================================
cells.append(code("""\
# Install required packages (run once)
%pip install -q -r ../../requirements.txt"""))

# ============================================================
# Cell 2: Title + What You'll Learn
# ============================================================
cells.append(md("""\
# Module 7: Shared Memory

Module 6 showed how multiple agents hand off memory within a single request. But every demo so far served **one user** — Sarah Chen. Real systems serve hundreds of users through the same agent, and that creates a new class of problems:

- When Agent processes Sarah's request, it must **never** leak Michael's preferences
- Travel policies are **the same** for everyone at a given level — duplicating them per user is wasteful
- Some context (current trip planning) should **expire** after the session, not persist forever

This module introduces **shared memory** — a layered approach where some knowledge is global, some is per-user, and some is temporary.

## What You'll Learn
1. **Multi-user isolation** — one agent, multiple users, private memory per user
2. **Global knowledge layer** — company policies accessible to all, editable by none
3. **Working memory with TTL** — ephemeral context that expires when the session ends
4. **Memory promotion** — when temporary working memory is worth keeping permanently

## The Journey
```
Session memory (Module 1)
    → Episodic memory for events (Module 2)
        → Semantic memory for facts (Module 3)
            → Procedural memory for behaviors (Module 4)
                → Combined memory with routing + conflicts (Module 5)
                    → Memory handoff between agents (Module 6)
                        → Shared memory across users (this module)
```"""))

# ============================================================
# Cell 3: Setup heading
# ============================================================
cells.append(md("""\
---
## Setup

> **Prerequisites**:
> - Modules 1–6 completed
> - Azure AI Foundry project endpoint in your `.env` file
>
> Everything in this module uses **in-memory stores** — no Redis, Cosmos DB, or other infrastructure needed.
> The focus is on multi-user isolation and shared knowledge patterns.
> In the summary, we'll discuss how Redis/Azure Cache for Redis handles this in production."""))

# ============================================================
# Cell 4: Imports + env vars + data loading
# ============================================================
cells.append(code("""\
import os
import json
import asyncio
import nest_asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv("../../.env", override=True)

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
TENANT_ID = os.environ.get("AZURE_TENANT_ID", "16b3c013-d300-468d-ac64-7eda0820b6d3")

# Load company data — this is the global knowledge base
EMPLOYEES = json.loads(Path("../../data/employees.json").read_text(encoding="utf-8"))
TRAVEL_POLICIES = json.loads(Path("../../data/travel_policies.json").read_text(encoding="utf-8"))

EMPLOYEES_BY_ID = {e["employee_id"]: e for e in EMPLOYEES}

print(f"Project: {PROJECT_ENDPOINT}")
print(f"Model:   {MODEL_DEPLOYMENT}")
print(f"\\nLoaded {len(EMPLOYEES)} employees:")
for e in EMPLOYEES:
    print(f"  {e['employee_id']}: {e['name']} ({e['level']}, {e['department']})")
print(f"\\nTravel policy levels: {list(TRAVEL_POLICIES['by_level'].keys())}")"""))

# ============================================================
# Cell 5: Part 1 heading — Multi-User Memory Isolation
# ============================================================
cells.append(md("""\
---
## Part 1: Multi-User Memory Isolation

In Modules 2–6, every demo used the same user: Sarah Chen (E001). The agent's memory was effectively single-tenant — one set of events, one set of preferences, one knowledge graph.

Real systems serve many users through the same agent. The agent must:
1. **Isolate** each user's memories — Sarah's preferences must never appear when serving Michael
2. **Identify** the current user — not from hardcoded instructions, but from the authentication layer
3. **Scope** every memory operation — reads and writes are always filtered by user ID

```
                    ┌─── E001 Memory (Sarah) ───┐
                    │  episodic: 3 trips         │
Agent ──────────────│  semantic: airline, hotel   │
(user-agnostic      │  (private, read-write)     │
 instructions)      └───────────────────────────┘
                    ┌─── E002 Memory (Michael) ──┐
                    │  episodic: 2 trips         │
                    │  semantic: airline, hotel   │
                    │  (private, read-write)     │
                    └───────────────────────────┘
```

The key insight: the agent's **instructions** don't mention any specific user. User identity comes from a tool that simulates the authentication layer."""))

# ============================================================
# Cell 6: SharedMemoryStore + tools + preloaded data
# ============================================================
cells.append(code("""\
from azure.identity.aio import AzureCliCredential
from agent_framework.azure import AzureAIClient
from agent_framework import tool

credential = AzureCliCredential(tenant_id=TENANT_ID)

# ─── Per-user memory stores ───

class SharedMemoryStore:
    \"\"\"Multi-user memory store with per-user isolation.

    Each user gets their own episodic events and semantic facts.
    All operations are scoped by user_id — no cross-user access.
    \"\"\"
    def __init__(self):
        self._episodic = {}   # {user_id: [events]}
        self._semantic = {}   # {user_id: [triplets]}

    def add_event(self, user_id, event):
        self._episodic.setdefault(user_id, []).append(event)

    def get_events(self, user_id, event_type=None, query=None, limit=5):
        events = self._episodic.get(user_id, [])
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        if query:
            events = [e for e in events if query.lower() in e["description"].lower()]
        return sorted(events, key=lambda e: e["timestamp"], reverse=True)[:limit]

    def add_fact(self, user_id, triplet):
        self._semantic.setdefault(user_id, [])
        # Upsert: replace existing fact of same type
        if triplet.get("object_type"):
            self._semantic[user_id] = [
                t for t in self._semantic[user_id]
                if not (t["relationship"] == triplet["relationship"]
                        and t["object_type"] == triplet["object_type"])
            ]
        self._semantic[user_id].append(triplet)

    def get_facts(self, user_id, relationship=None, object_type=None):
        facts = self._semantic.get(user_id, [])
        if relationship:
            facts = [f for f in facts if f["relationship"] == relationship]
        if object_type:
            facts = [f for f in facts if f["object_type"] == object_type]
        return facts

    def all_facts(self, user_id):
        return self._semantic.get(user_id, [])

    def user_count(self):
        all_ids = set(self._episodic.keys()) | set(self._semantic.keys())
        return len(all_ids)


# Global store instance — shared across all tool calls
_store = SharedMemoryStore()


# ─── Current user simulation ───
# In production, this comes from the auth layer (e.g., Azure Entra ID token).
# Here we simulate it with a module variable we can flip between demos.
_current_user_id = "E001"


@tool
async def get_current_user() -> str:
    \"\"\"Get the authenticated user's profile.

    Call this FIRST in every conversation to identify who you're talking to.
    Returns the user's employee ID, name, level, department, and preferences.
    This simulates looking up the user from an authentication token.
    \"\"\"
    user = EMPLOYEES_BY_ID.get(_current_user_id)
    if not user:
        return f"Unknown user: {_current_user_id}"
    return json.dumps(user, indent=2)


# ─── Memory tools (automatically scoped to current user) ───

@tool
async def remember_event(
    event_type: str,
    description: str,
    details: str = "",
) -> str:
    \"\"\"Store a significant event in the current user's episodic memory.

    Call this when:
    - A trip is completed or booked
    - The user shares feedback about a past experience
    - Something notable happens worth remembering for the future

    Args:
        event_type: Category — "trip", "booking", "feedback", "preference"
        description: Brief summary of what happened
        details: Optional JSON string with structured data
    \"\"\"
    event = {
        "id": f"{_current_user_id}-{uuid4().hex[:8]}",
        "user_id": _current_user_id,
        "event_type": event_type,
        "description": description,
        "details": json.loads(details) if details else {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _store.add_event(_current_user_id, event)
    return f"Remembered event: {description}"


@tool
async def recall_events(
    query: str = "",
    event_type: str = "",
    limit: int = 5,
) -> str:
    \"\"\"Search the current user's episodic memory for past events.

    Call this when:
    - Planning a trip and want to check past experiences
    - The user asks about their travel history
    - Need context from previous trips for recommendations

    Args:
        query: Optional keyword to search in descriptions
        event_type: Optional filter — "trip", "booking", "feedback"
        limit: Maximum number of events to return
    \"\"\"
    results = _store.get_events(_current_user_id, event_type=event_type or None,
                                query=query or None, limit=limit)
    return json.dumps(results, indent=2) if results else "No matching events found."


@tool
async def learn_preference(
    relationship: str,
    value: str,
    category: str,
) -> str:
    \"\"\"Store a fact or preference about the current user in semantic memory.

    Call this when the user expresses a persistent preference or requirement.
    Examples: "I prefer Delta" → relationship="prefers", value="Delta", category="airline"

    Args:
        relationship: How the user relates — "prefers", "requires", "dislikes"
        value: The entity (e.g. "Delta", "aisle", "vegetarian")
        category: Type — "airline", "hotel", "seat_type", "dietary", "flight_class"
    \"\"\"
    triplet = {
        "subject": _current_user_id,
        "relationship": relationship.upper(),
        "object": value,
        "object_type": category.upper(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _store.add_fact(_current_user_id, triplet)
    return f"Learned: {_current_user_id} {relationship} {value} ({category})"


@tool
async def query_preferences(
    relationship: str = "",
    category: str = "",
) -> str:
    \"\"\"Query the current user's stored preferences and facts.

    Call this to retrieve what you know about the user's preferences.

    Args:
        relationship: Optional filter — "PREFERS", "REQUIRES", "DISLIKES"
        category: Optional filter — "AIRLINE", "HOTEL", "SEAT_TYPE", "DIETARY"
    \"\"\"
    facts = _store.get_facts(
        _current_user_id,
        relationship=relationship.upper() if relationship else None,
        object_type=category.upper() if category else None,
    )
    if not facts:
        return "No matching preferences found."
    lines = [f"({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})" for f in facts]
    return "\\n".join(lines)


# ─── Preload data for two users ───

def preload_user_data():
    \"\"\"Preload realistic data for Sarah (E001) and Michael (E002).\"\"\"

    # Sarah Chen (E001) — Senior Engineer
    sarah = EMPLOYEES_BY_ID["E001"]
    for key, category in [("airline", "AIRLINE"), ("seat", "SEAT_TYPE"),
                          ("hotel_chain", "HOTEL")]:
        if sarah["preferences"].get(key):
            _store.add_fact("E001", {
                "subject": "E001", "relationship": "PREFERS",
                "object": sarah["preferences"][key], "object_type": category,
                "timestamp": "2025-01-01T00:00:00",
            })
    if sarah["preferences"].get("dietary"):
        _store.add_fact("E001", {
            "subject": "E001", "relationship": "REQUIRES",
            "object": sarah["preferences"]["dietary"], "object_type": "DIETARY",
            "timestamp": "2025-01-01T00:00:00",
        })

    _store.add_event("E001", {
        "id": "E001-trip1", "user_id": "E001", "event_type": "trip",
        "description": "New York trip for tech conference (Oct 15-18, 2025). Marriott Times Square, rated 5/5.",
        "details": {"destination": "New York", "hotel": "Marriott Times Square", "rating": 5, "total_cost": 1760},
        "timestamp": "2025-10-15T00:00:00",
    })
    _store.add_event("E001", {
        "id": "E001-trip2", "user_id": "E001", "event_type": "trip",
        "description": "London trip for client meeting (Nov 20-25, 2025). Marriott Park Lane, rated 4/5.",
        "details": {"destination": "London", "hotel": "Marriott Park Lane", "rating": 4, "total_cost": 3900},
        "timestamp": "2025-11-20T00:00:00",
    })
    _store.add_event("E001", {
        "id": "E001-trip3", "user_id": "E001", "event_type": "trip",
        "description": "Chicago trip for team offsite (Jan 10-12, 2026). Hampton Inn, rated 3/5. Hotel was noisy.",
        "details": {"destination": "Chicago", "hotel": "Hampton Inn", "rating": 3, "total_cost": 980},
        "timestamp": "2026-01-10T00:00:00",
    })

    # Michael Torres (E002) — Director, Engineering
    michael = EMPLOYEES_BY_ID["E002"]
    for key, category in [("airline", "AIRLINE"), ("seat", "SEAT_TYPE"),
                          ("hotel_chain", "HOTEL")]:
        if michael["preferences"].get(key):
            _store.add_fact("E002", {
                "subject": "E002", "relationship": "PREFERS",
                "object": michael["preferences"][key], "object_type": category,
                "timestamp": "2025-01-01T00:00:00",
            })

    _store.add_event("E002", {
        "id": "E002-trip1", "user_id": "E002", "event_type": "trip",
        "description": "San Francisco trip for engineering summit (Sep 5-8, 2025). Hilton Union Square, rated 4/5.",
        "details": {"destination": "San Francisco", "hotel": "Hilton Union Square", "rating": 4, "total_cost": 2200},
        "timestamp": "2025-09-05T00:00:00",
    })
    _store.add_event("E002", {
        "id": "E002-trip2", "user_id": "E002", "event_type": "trip",
        "description": "Tokyo trip for partner meeting (Dec 1-7, 2025). Hilton Tokyo, rated 5/5. Excellent service.",
        "details": {"destination": "Tokyo", "hotel": "Hilton Tokyo", "rating": 5, "total_cost": 5800},
        "timestamp": "2025-12-01T00:00:00",
    })


preload_user_data()

print("SharedMemoryStore initialized")
print(f"  Users with data: {_store.user_count()}")
print(f"  E001 (Sarah):  {len(_store.get_events('E001'))} events, {len(_store.all_facts('E001'))} facts")
print(f"  E002 (Michael): {len(_store.get_events('E002'))} events, {len(_store.all_facts('E002'))} facts")
print(f"\\nCurrent user: {_current_user_id} ({EMPLOYEES_BY_ID[_current_user_id]['name']})")
print(f"\\nTools defined: get_current_user, remember_event, recall_events, learn_preference, query_preferences")"""))

# ============================================================
# Cell 7: Agent instructions + first demo (Sarah)
# ============================================================
cells.append(code("""\
AGENT_INSTRUCTIONS = \"\"\"You are a Travel Assistant for Contoso Corp.

## Identity
You do NOT know who the user is until you call get_current_user.
ALWAYS call get_current_user as your FIRST action in every conversation.

## Your Capabilities
- **Recall past trips**: Use recall_events to find the user's travel history
- **Know preferences**: Use query_preferences to retrieve their airline, hotel, seat, dietary preferences
- **Learn new preferences**: Use learn_preference when the user shares a new preference
- **Remember events**: Use remember_event to record significant events

## Rules
- Never assume the user's identity — always verify with get_current_user
- All memory tools automatically scope to the authenticated user
- You cannot access another user's memories
- Be concise and personalized based on what you learn from memory
\"\"\"

# Demo 1: Sarah's session
_current_user_id = "E001"

async def demo_sarah():
    async with AzureAIClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL_DEPLOYMENT,
        credential=credential,
    ).as_agent(
        name="TravelAssistant",
        instructions=AGENT_INSTRUCTIONS,
        tools=[get_current_user, remember_event, recall_events, learn_preference, query_preferences],
    ) as agent:
        response = await agent.run("What do you know about me and my travel history?")
        print("User (Sarah): What do you know about me and my travel history?")
        print(f"\\nAgent:\\n{response.text}")

print("=== Demo: Sarah's Session (E001) ===\\n")
asyncio.run(demo_sarah())"""))

# ============================================================
# Cell 8: Same agent, different user (Michael)
# ============================================================
cells.append(code("""\
# Switch to Michael — same agent, same instructions, different user
_current_user_id = "E002"

async def demo_michael():
    async with AzureAIClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL_DEPLOYMENT,
        credential=credential,
    ).as_agent(
        name="TravelAssistant",
        instructions=AGENT_INSTRUCTIONS,
        tools=[get_current_user, remember_event, recall_events, learn_preference, query_preferences],
    ) as agent:
        response = await agent.run("What do you know about me and my travel history?")
        print("User (Michael): What do you know about me and my travel history?")
        print(f"\\nAgent:\\n{response.text}")

print("=== Demo: Michael's Session (E002) ===\\n")
asyncio.run(demo_michael())"""))

# ============================================================
# Cell 9: Analysis — isolation
# ============================================================
cells.append(md("""\
### How Isolation Works

Same agent, same instructions, same question — completely different answers. The key mechanisms:

1. **`get_current_user` tool** — simulates the auth layer. The agent doesn't know who it's talking to until it calls this tool. In production, this reads from the authentication token (Azure Entra ID, OAuth, etc.).

2. **`_current_user_id` module variable** — scopes all memory tools. Every `recall_events`, `query_preferences`, `learn_preference`, and `remember_event` call filters by this ID. The agent never passes a user ID explicitly — isolation happens at the tool layer.

3. **User-agnostic instructions** — the agent's system prompt doesn't mention Sarah or Michael. It says "call `get_current_user` first." This means the same instructions work for any number of users.

```python
# The privacy boundary is here — in the tool, not the prompt
@tool
async def recall_events(query="", event_type="", limit=5):
    results = _store.get_events(_current_user_id, ...)  # ← scoped
    return json.dumps(results)
```

**What's missing**: Company policies are the same for everyone at a given level, but right now the agent has no way to access them. Sarah (Senior) and Michael (Director) have different budget limits — the agent needs a **global knowledge layer** to answer policy questions."""))

# ============================================================
# Cell 10: Part 2 heading — Global Knowledge Layer
# ============================================================
cells.append(md("""\
---
## Part 2: Global Knowledge Layer

Not all knowledge is user-specific. Travel policies, org structure, and approved vendors are **company-wide** — the same for everyone. Storing them per-user would be:
- **Wasteful** — N copies of the same data
- **Error-prone** — update one copy, others are stale
- **Insecure** — users could modify shared policies via `learn_preference`

The solution: a **two-layer memory architecture**.

```
┌──────────────────────────────────────────────┐
│           Global Knowledge Layer              │
│  (travel policies, org chart, vendors)        │
│  READ-ONLY for agents                         │
├──────────┬──────────┬──────────┬─────────────┤
│ E001     │ E002     │ E003     │ ...         │
│ Memory   │ Memory   │ Memory   │             │
│ (private)│ (private)│ (private)│             │
│ r/w      │ r/w      │ r/w      │             │
└──────────┴──────────┴──────────┴─────────────┘
```

The agent queries the global layer for policy rules and combines them with user-specific context. Global knowledge is read-only — no tool can modify it."""))

# ============================================================
# Cell 11: Global knowledge tool + updated agent
# ============================================================
cells.append(code("""\
@tool
async def query_company_knowledge(
    topic: str,
    employee_id: str = "",
) -> str:
    \"\"\"Query company-wide knowledge: policies, org structure, employee info.

    This is READ-ONLY global data shared across all users. Use it to:
    - Look up travel policies for a specific employee level
    - Check international booking requirements
    - Find an employee's manager or department
    - Get general travel rules

    Args:
        topic: What to look up — "travel_policy", "international_rules",
               "employee_info", "org_structure", "general_rules"
        employee_id: Optional — specific employee to look up. If not provided,
                     uses the current authenticated user.
    \"\"\"
    eid = employee_id or _current_user_id
    emp = EMPLOYEES_BY_ID.get(eid)

    if topic == "travel_policy" and emp:
        level = emp["level"]
        policy = TRAVEL_POLICIES["by_level"].get(level, {})
        return json.dumps({
            "employee": emp["name"],
            "level": level,
            "policy": policy,
            "general_rules": TRAVEL_POLICIES["general"],
        }, indent=2)

    elif topic == "international_rules":
        return json.dumps({
            "international": TRAVEL_POLICIES["international"],
            "note": "These rules apply to ALL international trips regardless of level.",
        }, indent=2)

    elif topic == "employee_info" and emp:
        # Return non-preference info (preferences are in user's private memory)
        return json.dumps({
            "employee_id": emp["employee_id"],
            "name": emp["name"],
            "level": emp["level"],
            "department": emp["department"],
            "manager_id": emp["manager_id"],
        }, indent=2)

    elif topic == "org_structure":
        org = []
        for e in EMPLOYEES:
            manager_name = EMPLOYEES_BY_ID[e["manager_id"]]["name"] if e["manager_id"] else "None"
            org.append(f"  {e['employee_id']}: {e['name']} ({e['level']}) → reports to {manager_name}")
        return "Org structure:\\n" + "\\n".join(org)

    elif topic == "general_rules":
        return json.dumps(TRAVEL_POLICIES["general"], indent=2)

    return f"Unknown topic: {topic}. Try: travel_policy, international_rules, employee_info, org_structure, general_rules"


# Updated instructions that include global knowledge
AGENT_INSTRUCTIONS_V2 = \"\"\"You are a Travel Assistant for Contoso Corp.

## Identity
You do NOT know who the user is until you call get_current_user.
ALWAYS call get_current_user as your FIRST action in every conversation.

## Your Capabilities
- **User identity**: get_current_user — always call first
- **Recall past trips**: recall_events — search the user's travel history
- **Know preferences**: query_preferences — retrieve airline, hotel, seat, dietary preferences
- **Learn new preferences**: learn_preference — store when the user shares a preference
- **Remember events**: remember_event — record significant events
- **Company knowledge**: query_company_knowledge — look up travel policies, rules, and org info

## When Asked About Booking or Policies
1. Call get_current_user to identify the user
2. Call query_company_knowledge("travel_policy") to get their level's limits
3. Call query_preferences to get their personal preferences
4. Combine policy limits with personal preferences in your recommendation

## Rules
- Never assume the user's identity — always verify with get_current_user
- All memory tools automatically scope to the authenticated user
- You cannot access another user's memories
- Travel policies come from query_company_knowledge, not from memory
- When preferences conflict with policy, policy wins — explain the conflict
\"\"\"

ALL_TOOLS = [
    get_current_user,
    remember_event, recall_events,
    learn_preference, query_preferences,
    query_company_knowledge,
]

print("Global knowledge tool defined: query_company_knowledge")
print(f"  Topics: travel_policy, international_rules, employee_info, org_structure, general_rules")
print(f"\\nUpdated agent instructions (v2) with global knowledge awareness")
print(f"Total tools: {len(ALL_TOOLS)}")"""))

# ============================================================
# Cell 12: Demo — Sarah asks about business class
# ============================================================
cells.append(code("""\
_current_user_id = "E001"

async def demo_sarah_policy():
    async with AzureAIClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL_DEPLOYMENT,
        credential=credential,
    ).as_agent(
        name="TravelAssistant",
        instructions=AGENT_INSTRUCTIONS_V2,
        tools=ALL_TOOLS,
    ) as agent:
        response = await agent.run("Can I fly business class to London?")
        print("User (Sarah, Senior): Can I fly business class to London?")
        print(f"\\nAgent:\\n{response.text}")

print("=== Sarah (Senior) Asks About Business Class ===\\n")
asyncio.run(demo_sarah_policy())"""))

# ============================================================
# Cell 13: Demo — Michael asks the same question
# ============================================================
cells.append(code("""\
_current_user_id = "E002"

async def demo_michael_policy():
    async with AzureAIClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL_DEPLOYMENT,
        credential=credential,
    ).as_agent(
        name="TravelAssistant",
        instructions=AGENT_INSTRUCTIONS_V2,
        tools=ALL_TOOLS,
    ) as agent:
        response = await agent.run("Can I fly business class to London?")
        print("User (Michael, Director): Can I fly business class to London?")
        print(f"\\nAgent:\\n{response.text}")

print("=== Michael (Director) Asks About Business Class ===\\n")
asyncio.run(demo_michael_policy())"""))

# ============================================================
# Cell 14: Analysis — layered memory
# ============================================================
cells.append(md("""\
### Same Question, Different Answers

Both users asked "Can I fly business class to London?" The agent:
1. Called `get_current_user` → learned their level
2. Called `query_company_knowledge("travel_policy")` → got level-specific limits
3. Combined global policy with personal preferences

**Sarah (Senior)**: economy/economy-plus only, $800 max → business class denied
**Michael (Director)**: economy/economy-plus/business allowed, $1500 max → business class approved

The key architecture:

| Layer | Scope | Access | Examples |
|---|---|---|---|
| **Global** | All users | Read-only | Policies, org chart, vendors |
| **User** | One user | Read-write | Preferences, trip history, dietary |

The global layer is **not memory** in the traditional sense — it's reference data loaded from files. In production, this could be a database, API, or Azure AI Search index. The important thing is that it's **shared and read-only** — no agent can modify company policy through a tool call.

**Privacy note**: `query_company_knowledge("employee_info")` returns only public fields (name, level, department). Preferences stay in the user's private memory store."""))

# ============================================================
# Cell 15: Part 3 heading — Working Memory
# ============================================================
cells.append(md("""\
---
## Part 3: Working Memory

So far we have two memory durations:
- **Permanent** — episodic events and semantic facts, stored until explicitly deleted
- **Session** — the conversation itself, lost when the kernel restarts

But there's a gap between them. Consider a multi-turn trip planning conversation:

> **Turn 1**: "I need to fly to Tokyo next month"
> **Turn 2**: "What about hotels near Shibuya?"
> **Turn 3**: "Actually, make it Shinjuku instead"
> **Turn 4**: "Book it"

The destination and neighborhood choice are important **during** this conversation but don't belong in permanent memory. If the user comes back tomorrow and says "Book me a trip," they shouldn't get auto-routed to Tokyo/Shinjuku.

**Working memory** fills this gap — it's structured, queryable context that persists within a session but expires after a configurable TTL.

```
Duration:     Session < Working Memory < Permanent Memory
              (minutes)  (hours/days)    (forever)
Survives:     This turn   This session    All sessions
Stored in:    Conversation  Dict + TTL     Episodic/Semantic stores
```"""))

# ============================================================
# Cell 16: Working memory implementation
# ============================================================
cells.append(code("""\
# ─── Working memory with simulated TTL ───

_working_memory = {}  # {user_id: {key: {"value": ..., "expires": datetime}}}
WORKING_MEMORY_TTL_HOURS = 4  # Default: expire after 4 hours


@tool
async def set_working_memory(key: str, value: str) -> str:
    \"\"\"Store temporary context in working memory for the current session.

    Use this for information that's important NOW but shouldn't persist
    permanently — like a trip being planned, a destination under discussion,
    or a draft itinerary.

    Working memory expires after the session (simulated TTL). It is NOT
    the same as learn_preference (permanent) or remember_event (permanent).

    Args:
        key: Short identifier — "current_destination", "trip_dates", "draft_itinerary"
        value: The value to store
    \"\"\"
    if _current_user_id not in _working_memory:
        _working_memory[_current_user_id] = {}
    _working_memory[_current_user_id][key] = {
        "value": value,
        "expires": (datetime.now(timezone.utc) + timedelta(hours=WORKING_MEMORY_TTL_HOURS)).isoformat(),
        "created": datetime.now(timezone.utc).isoformat(),
    }
    return f"Working memory set: {key} = {value} (expires in {WORKING_MEMORY_TTL_HOURS}h)"


@tool
async def get_working_memory(key: str = "") -> str:
    \"\"\"Retrieve working memory for the current session.

    Returns temporary context stored during this session. If a key is
    specified, returns that specific value. Otherwise returns all working memory.

    Working memory expires after the session — use query_preferences for
    permanent facts and recall_events for permanent history.

    Args:
        key: Optional — specific key to retrieve. If empty, returns all.
    \"\"\"
    user_mem = _working_memory.get(_current_user_id, {})
    now = datetime.now(timezone.utc)

    # Filter expired entries
    active = {}
    for k, v in user_mem.items():
        if datetime.fromisoformat(v["expires"]) > now:
            active[k] = v["value"]

    if key:
        val = active.get(key)
        return val if val else f"No working memory found for key: {key}"

    if not active:
        return "No active working memory."
    return json.dumps(active, indent=2)


# ─── Promotion tool: working → permanent ───

@tool
async def promote_working_memory(
    key: str,
    memory_type: str,
    event_type: str = "preference",
    relationship: str = "prefers",
    category: str = "",
) -> str:
    \"\"\"Promote a working memory entry to permanent storage.

    Call this when a temporary piece of context turns out to be worth
    remembering permanently. For example, if the user planned a trip to
    Tokyo and says "I really liked that hotel — remember it for next time",
    promote it from working memory to episodic or semantic memory.

    Args:
        key: The working memory key to promote
        memory_type: Target — "episodic" (event) or "semantic" (fact/preference)
        event_type: For episodic — "trip", "booking", "feedback", "preference"
        relationship: For semantic — "prefers", "requires", "dislikes"
        category: For semantic — "airline", "hotel", "seat_type", "dietary"
    \"\"\"
    user_mem = _working_memory.get(_current_user_id, {})
    entry = user_mem.get(key)
    if not entry:
        return f"No working memory found for key: {key}"

    value = entry["value"]

    if memory_type == "episodic":
        event = {
            "id": f"{_current_user_id}-{uuid4().hex[:8]}",
            "user_id": _current_user_id,
            "event_type": event_type,
            "description": value,
            "details": {"promoted_from": "working_memory", "original_key": key},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _store.add_event(_current_user_id, event)
        # Remove from working memory after promotion
        del user_mem[key]
        return f"Promoted to episodic memory: {value}"

    elif memory_type == "semantic":
        triplet = {
            "subject": _current_user_id,
            "relationship": relationship.upper(),
            "object": value,
            "object_type": category.upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _store.add_fact(_current_user_id, triplet)
        del user_mem[key]
        return f"Promoted to semantic memory: {_current_user_id} {relationship} {value} ({category})"

    return f"Unknown memory_type: {memory_type}. Use 'episodic' or 'semantic'."


WORKING_TOOLS = ALL_TOOLS + [set_working_memory, get_working_memory, promote_working_memory]

print("Working memory tools defined:")
print("  set_working_memory      — store temporary session context")
print("  get_working_memory      — retrieve session context")
print("  promote_working_memory  — move working → permanent memory")
print(f"\\nTotal tools: {len(WORKING_TOOLS)}")
print(f"TTL: {WORKING_MEMORY_TTL_HOURS} hours")"""))

# ============================================================
# Cell 17: Working memory demo
# ============================================================
cells.append(code("""\
_current_user_id = "E001"
_working_memory.clear()

AGENT_INSTRUCTIONS_V3 = \"\"\"You are a Travel Assistant for Contoso Corp.

## Identity
You do NOT know who the user is until you call get_current_user.
ALWAYS call get_current_user as your FIRST action in every conversation.

## Your Capabilities
- **User identity**: get_current_user — always call first
- **Recall past trips**: recall_events — search the user's travel history
- **Know preferences**: query_preferences — retrieve permanent preferences
- **Learn new preferences**: learn_preference — store permanent preference
- **Remember events**: remember_event — record permanent event
- **Company knowledge**: query_company_knowledge — travel policies and org info
- **Working memory**: set_working_memory / get_working_memory — temporary session context
- **Promote memory**: promote_working_memory — move temp context to permanent storage

## Memory Duration Guide
- **Working memory** (set_working_memory): Current session only. Use for trip-in-progress details,
  draft plans, temporary choices. Expires after the session.
- **Permanent memory** (learn_preference, remember_event): Kept forever. Use for confirmed
  preferences, completed trips, definitive feedback.
- **Promotion** (promote_working_memory): When something temporary turns out to be worth keeping —
  e.g., the user says "remember that hotel for next time."

## Rules
- Never assume the user's identity — always verify with get_current_user
- Use working memory for trip planning details DURING the conversation
- Only promote to permanent memory when the user explicitly confirms
- When preferences conflict with policy, policy wins — explain the conflict
\"\"\"

async def demo_working_memory():
    \"\"\"Multi-turn trip planning that uses working memory.\"\"\"
    async with AzureAIClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL_DEPLOYMENT,
        credential=credential,
    ).as_agent(
        name="TravelAssistant",
        instructions=AGENT_INSTRUCTIONS_V3,
        tools=WORKING_TOOLS,
    ) as agent:
        # Turn 1: Start planning
        msg1 = "I need to plan a trip to Tokyo for a partner meeting next month."
        print(f"User: {msg1}")
        r1 = await agent.run(msg1)
        print(f"Agent: {r1.text}\\n")

        # Turn 2: Ask to remember a detail
        msg2 = "I stayed at the Park Hyatt last time and loved it. Remember that for next time."
        print(f"User: {msg2}")
        r2 = await agent.run(msg2)
        print(f"Agent: {r2.text}\\n")

    # Show what's in working vs permanent memory
    print("=" * 60)
    print("MEMORY STATE AFTER CONVERSATION")
    print("=" * 60)

    wm = _working_memory.get("E001", {})
    print(f"\\nWorking memory ({len(wm)} entries):")
    for k, v in wm.items():
        print(f"  {k}: {v['value']} (expires: {v['expires'][:16]})")

    facts = _store.all_facts("E001")
    print(f"\\nSemantic memory ({len(facts)} facts):")
    for f in facts:
        print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")

    events = _store.get_events("E001", limit=2)
    print(f"\\nLatest episodic events:")
    for e in events:
        promoted = " [promoted from working memory]" if e.get("details", {}).get("promoted_from") else ""
        print(f"  {e['description'][:80]}...{promoted}")

print("=== Working Memory: Multi-Turn Trip Planning ===\\n")
asyncio.run(demo_working_memory())"""))

# ============================================================
# Cell 18: Working memory + promotion analysis
# ============================================================
cells.append(md("""\
### Working Memory vs. Permanent Memory

| Aspect | Working Memory | Permanent Memory |
|---|---|---|
| **Duration** | Session (hours) | Forever |
| **Tools** | `set_working_memory`, `get_working_memory` | `learn_preference`, `remember_event` |
| **Use case** | Trip in progress, draft choices, temp context | Confirmed preferences, completed trips |
| **Promotion** | → `promote_working_memory` → episodic or semantic | Already permanent |
| **Production backend** | Redis with TTL | Cosmos DB, Neo4j, etc. |

### When to Promote

The agent should promote working memory to permanent storage when:

| Signal | Promote To | Example |
|---|---|---|
| User says "remember this" | Semantic (preference) | "I loved the Park Hyatt — remember that" |
| Trip is confirmed/booked | Episodic (event) | Booking confirmation received |
| Pattern emerges over multiple sessions | Semantic (preference) | User always chooses the same neighborhood |
| User gives explicit feedback | Episodic (feedback) | "That hotel was terrible, never again" |

The decision to promote is **the agent's judgment call** based on the user's language. "I'm thinking about the Park Hyatt" → working memory. "The Park Hyatt is my go-to in Tokyo" → permanent.

### TTL Strategy

```
Working Memory (4h TTL)
    ↕ promote_working_memory()
Episodic Memory (permanent)
Semantic Memory (permanent)
```

In production, Redis provides **native TTL** — `SET key value EX 14400` automatically expires after 4 hours. No cleanup needed. For the in-memory implementation here, we check timestamps on read."""))

# ============================================================
# Cell 19: Summary
# ============================================================
cells.append(md("""\
---
## Summary

### Seven Modules of Memory

| | Session (M1) | Episodic (M2) | Semantic (M3) | Procedural (M4) | Combined (M5) | Handoff (M6) | Shared (M7) |
|---|---|---|---|---|---|---|---|
| **Stores** | Conversation | Past events | Facts | Procedures | All of above | All + context | All + global + working |
| **Answers** | "What did we discuss?" | "What happened?" | "What is true?" | "How to act?" | "What to do?" | "Who handles this?" | "Whose memory is this?" |
| **Users** | 1 | 1 | 1 | 1 | 1 | 1 | Many |
| **New** | — | — | — | — | Routing, conflicts | Multi-agent, WorkflowBuilder | Isolation, global layer, TTL |

### Key Insights

1. **User identity belongs in the tool layer, not the prompt.** The agent's instructions are user-agnostic. `get_current_user` provides identity at runtime. This means one set of instructions serves all users — no per-user prompt variants.

2. **Memory has layers.** Global knowledge (policies, org chart) is shared and read-only. User knowledge (preferences, history) is private and read-write. Working memory (session context) is private and temporary. Each layer has different access patterns and lifetimes.

3. **Working memory fills the gap between conversation and permanent storage.** Not everything worth tracking should be permanent. Trip planning details, draft itineraries, and temporary preferences belong in working memory with a TTL. Promote to permanent storage only when confirmed.

4. **Isolation is enforced by tools, not by instructions.** Telling the agent "don't access other users' data" is insufficient — a prompt injection could override it. Instead, every memory tool is scoped by `_current_user_id`, which comes from the auth layer. The agent physically cannot access another user's data because the tools don't allow it.

### Production Considerations

In production, replace in-memory stores with:

| Layer | Production Backend | Why |
|---|---|---|
| **Global** | Azure AI Search, Cosmos DB | Indexed, versioned, searchable |
| **User (episodic)** | Cosmos DB (NoSQL) | Partitioned by user_id, TTL support |
| **User (semantic)** | Cosmos DB (Gremlin) or Neo4j | Graph queries for relationships |
| **Working** | Azure Cache for Redis | Native TTL, sub-ms latency, pub/sub |

Redis gives you:
- **Native TTL**: `SET key value EX 14400` — auto-expires, no cleanup code
- **Pub/Sub**: Real-time sync across multiple agent instances
- **Sorted sets**: Temporal queries ("what happened in the last hour?")
- **Atomic operations**: Thread-safe read-modify-write for concurrent users"""))

# ============================================================
# Cell 20: What's Next
# ============================================================
cells.append(md("""\
---
## What's Next

We've built all seven memory patterns — from simple session context to multi-user shared memory with TTL and promotion. But everything so far runs in a notebook with in-memory stores.

In **Module 8: Production Memory**, we'll take these patterns to production:
- Persistent backends (Cosmos DB, Redis, Azure AI Search)
- Monitoring and observability for memory operations
- API deployment with Docker and Azure Container Apps
- Evaluation framework to validate memory behavior"""))

# ============================================================
# Cell 21: Cleanup
# ============================================================
cells.append(code("""\
# Module 7 complete.
print("Module 7: Shared Memory — complete")
print(f"\\nFinal state:")
print(f"  SharedMemoryStore: {_store.user_count()} users")
print(f"  Working memory: {sum(len(v) for v in _working_memory.values())} entries across {len(_working_memory)} users")
print(f"  Current user: {_current_user_id} ({EMPLOYEES_BY_ID[_current_user_id]['name']})")"""))

# ============================================================
# Build the notebook
# ============================================================
notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.13.0"
        }
    },
    "cells": cells
}

with open("07_shared_memory.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print(f"Built 07_shared_memory.ipynb: {len(cells)} cells")
for i, c in enumerate(cells, 1):
    t = c["cell_type"]
    src = "".join(c["source"])
    preview = src[:60].replace("\n", " ")
    print(f"  {i:2d}. [{t:4s}] {preview}...")

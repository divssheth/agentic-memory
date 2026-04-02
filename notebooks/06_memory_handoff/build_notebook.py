"""Build Module 6: Memory Handoff notebook."""
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
# Module 6: Memory Handoff

Module 5 combined all three memory types into a **single agent** — and spent an entire module learning to resolve conflicts between them. The agent had every tool, every memory, and every responsibility. It worked, but it was doing two jobs at once: domain work AND arbitration.

This module asks a different question: **what if we separate responsibilities so conflicts don't arise in the first place?**

Instead of one agent doing everything, we'll split the work across specialist agents — a Router that understands the user, a Policy checker that knows the rules, and a Booking agent that acts on their combined findings. The central insight:

> **Memory access defines responsibility.** Giving an agent a memory type is a statement about what that agent is responsible for.

## What You'll Learn
1. **Why not every agent needs every memory** — and the problems that arise when they do
2. **A decision framework** for assigning memory types to agents
3. **Shared tools** — the brute-force approach where every agent gets everything
4. **Structured handoff** — scoped memory access with a `HandoffContext` that carries findings between agents
5. **Conditional dispatch** — routing requests to different agents based on classification

## The Journey
```
Session memory (Module 1)
    → Episodic memory for events (Module 2)
        → Semantic memory for facts (Module 3)
            → Procedural memory for behaviors (Module 4)
                → Conflict resolution across memories (Module 5)
                    → Memory handoff between agents (this module)
```"""))

# ============================================================
# Cell 3: Setup heading
# ============================================================
cells.append(md("""\
---
## Setup

> **Prerequisites**:
> - Modules 1–5 completed
> - Azure AI Foundry project endpoint in your `.env` file
>
> Everything in this module uses **in-memory stores** — no Cosmos DB, Neo4j, or Redis.
> The focus is on handoff mechanics, not persistence. Redis comes in Module 7, full production persistence in Module 8."""))

# ============================================================
# Cell 4: Imports + config
# ============================================================
cells.append(code("""\
import os
import json
import asyncio
import nest_asyncio
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv("../../.env", override=True)

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
TENANT_ID = os.environ.get("AZURE_TENANT_ID")

def load_instructions(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

print(f"Project: {PROJECT_ENDPOINT}")
print(f"Model:   {MODEL_DEPLOYMENT}")"""))

# ============================================================
# PART 1: From One Agent to Many (Concepts)
# ============================================================

# ============================================================
# Cell 5: The single-agent ceiling
# ============================================================
cells.append(md("""\
---
## Part 1: From One Agent to Many — Why Split and How to Assign Memory

### The Single-Agent Ceiling

Module 5's agent had all three memory types, all the tools, all the routing logic, and all the conflict-resolution rules. It worked — but look at what it was doing:

| Responsibility | What It Required |
|---|---|
| Remember past trips | Episodic memory + recall tools |
| Know user preferences | Semantic memory + knowledge graph tools |
| Follow booking procedures | Procedural memory + procedure loading |
| Resolve conflicts between the above | Complex system prompt with priority rules |
| Route between domestic/international | Request classification logic |

That's five distinct jobs in one agent. And the conflict resolution was the hardest part — not because the conflicts were complex, but because **one agent had to hold competing perspectives simultaneously**. It's the arbiter AND the advocate.

**What if we separate the work so conflicts don't arise structurally?**

Three reasons to split into specialist agents:
- **Specialization** — a policy agent doesn't need booking tools. A router doesn't need procedures for booking compliance.
- **Prompt focus** — shorter, targeted instructions per agent produce more reliable behavior than one massive prompt with 9+ tools.
- **Independent iteration** — change the policy-checking logic without touching the booking flow. Version and test agents independently."""))

# ============================================================
# Cell 6: Not every agent needs every memory
# ============================================================
cells.append(md("""\
### Not Every Agent Needs Every Memory

This is the central point of the module. When you split into specialist agents, the natural instinct is to give every agent access to every memory type — "just in case." But that recreates Module 5's problem at scale.

**Four reasons to scope memory access:**

1. **Responsibility diffusion** — If both the Router and the Policy agent can `load_procedure`, who is THE authoritative policy checker? If the Router loosely summarizes a budget limit and the Policy agent loads the precise rules, you now have two interpretations. Which does the Booking agent trust?

2. **Conflicting objectives solved structurally** — Module 5 showed that an agent with both preference memory AND policy memory has to resolve conflicts between what the user *wants* and what the rules *allow*. But if the Router advocates for the user's preferences and the Policy agent advocates for the rules, conflict resolution happens at the handoff boundary — not inside a single agent's reasoning. Each agent does its job without internal contradictions.

3. **Prompt complexity** — Each memory type adds 2–3 tools plus instructions for when and how to use them. One agent with 9+ tools = a long, complex prompt. Three agents with 2–3 tools each = shorter, focused prompts that the model follows more reliably.

4. **Least privilege** — A booking agent that processes reservations shouldn't be able to overwrite the user's preference memory. By giving it only handoff tools, you structurally prevent it from modifying data it shouldn't touch. This isn't about trust — it's about removing the possibility of accidental side effects.

> **Callout — each agent can have its OWN procedural memory.** When we say "the Router doesn't need procedural memory," we mean it doesn't need booking *procedures*. But the Router could absolutely have procedural memory about *routing* — e.g., "requests mentioning 'visa' or 'passport' → international path", "workation requests need both HR and travel policy review." Similarly, the Booking agent might develop procedural memory about recommendation strategies. Procedural memory is per-domain, not one-size-fits-all. We won't demo this, but it's a key production pattern."""))

# ============================================================
# Cell 7: The 4-question decision framework
# ============================================================
cells.append(md("""\
### How to Decide: The 4-Question Framework

For each agent in your system, walk through these questions:

1. **What is this agent's primary job?** (understand, check, or act)
2. **What information does it need** to do that job?
3. **Which memory type holds** that information?
4. **Does it need the raw memory**, or can it receive summarized findings from another agent?

Question 4 is the critical one. If summarized findings are sufficient, use handoff — don't give direct memory access.

Applied to our travel system:

| Agent | Primary Job | Information Needed | Memory Type | Access Level |
|---|---|---|---|---|
| **Router** | Understand the user | Who is Sarah? What does she prefer? Past trips? | Episodic + Semantic | **Direct** — first in the pipeline, no prior findings to read |
| **Policy** | Check rules | What does policy say about this trip type + employee level? | Procedural | **Direct** — the sole authority on rules |
| **Booking** | Recommend + act | User preferences + policy constraints combined | All of the above | **Handoff only** — reads what others found, never re-queries |

**Booking is the key case.** It needs information from ALL memory types but direct access to NONE. Everything it needs has already been gathered by specialists upstream. Giving it memory tools would mean re-querying data someone else already queried — risking different interpretations (context drift) and wasting tokens."""))

# ============================================================
# Cell 8: The handoff problem
# ============================================================
cells.append(md("""\
### The Handoff Problem

Once you've decided that the Booking agent doesn't get memory tools, you have a new problem: **how do the Router's semantic findings and Policy's procedural findings reach it?**

Think of it like a hospital. A GP examines you, writes notes on a chart, then sends you to a specialist. If the specialist has to re-examine you from scratch — ignoring the chart — you get redundant tests, possibly different findings, and no one can trace what the GP already ruled out. The chart IS the handoff.

Without explicit handoff, three things go wrong:

1. **Context loss** — The Booking agent doesn't know what the Router found about the user's preferences and history. It has to infer everything from the conversation, which is lossy.
2. **Context drift** — If the Booking agent re-queries semantic memory, it might get a different interpretation of the same data than the Router did. Now there are two versions of "what the user prefers."
3. **No audit trail** — After the workflow completes, you can't answer: "Which agent checked which memory type and what did it find?" You'd have to parse free-text conversation to reconstruct what happened.

We'll solve this in two steps:
1. **Part 2: The brute-force approach** — give every agent every tool, wire them sequentially. See what works and what doesn't.
2. **Part 3: The scoped approach** — each agent owns its memory type, findings travel via a typed `HandoffContext`."""))

# ============================================================
# PART 2: Shared Tools — The Brute-Force Approach
# ============================================================

# ============================================================
# Cell 9: Memory tools + reset
# ============================================================
cells.append(code("""\
# ─── Part 2: Shared Tools — The Brute-Force Approach ───
# In this approach, every agent gets every tool. We'll see why that's problematic.

from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework import tool
from agent_framework.orchestrations import SequentialBuilder

credential = AzureCliCredential()

# ─── Episodic memory (in-memory) ───

_episodic_store = []

@tool
async def remember_event(
    user_id: str,
    event_type: str,
    description: str,
    details: str = "",
) -> str:
    \"\"\"Store a significant event in the user's episodic memory.

    Call this when a trip is booked, feedback is shared, or something notable happens.

    Args:
        user_id: Employee ID (e.g. "E001")
        event_type: Category — "trip", "booking", "feedback", "preference"
        description: Brief summary of what happened
        details: Optional JSON string with structured data
    \"\"\"
    event = {
        "id": f"{user_id}-{uuid4().hex[:8]}",
        "user_id": user_id,
        "event_type": event_type,
        "description": description,
        "details": json.loads(details) if details else {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _episodic_store.append(event)
    return f"Remembered event: {description}"


@tool
async def recall_events(
    user_id: str,
    query: str = "",
    event_type: str = "",
    limit: int = 5,
) -> str:
    \"\"\"Search the user's episodic memory for past events.

    Call this when planning a trip, checking travel history, or needing context from past experiences.

    Args:
        user_id: Employee ID (e.g. "E001")
        query: Optional keyword to search in descriptions
        event_type: Optional filter — "trip", "booking", "feedback"
        limit: Maximum number of events to return
    \"\"\"
    results = [e for e in _episodic_store if e["user_id"] == user_id]
    if event_type:
        results = [e for e in results if e["event_type"] == event_type]
    if query:
        results = [e for e in results if query.lower() in e["description"].lower()]
    results = sorted(results, key=lambda e: e["timestamp"], reverse=True)[:limit]
    return json.dumps(results, indent=2) if results else "No matching events found."


# ─── Semantic memory (in-memory knowledge graph) ───

class OntologyManager:
    RELATIONSHIP_MAP = {
        "prefers": "PREFERS", "likes": "PREFERS", "prefer": "PREFERS",
        "loves": "PREFERS", "always": "PREFERS", "favorite": "PREFERS",
        "dislikes": "DISLIKES", "hates": "DISLIKES", "avoids": "DISLIKES",
        "never": "DISLIKES", "dont_like": "DISLIKES",
        "requires": "REQUIRES", "needs": "REQUIRES", "must_have": "REQUIRES",
        "works_at": "WORKS_AT", "employed_at": "WORKS_AT",
        "member_of": "MEMBER_OF", "belongs_to": "MEMBER_OF",
        "wants": "PREFERS",
    }
    ENTITY_TYPE_MAP = {
        "airline": "AIRLINE", "carrier": "AIRLINE",
        "hotel": "HOTEL", "hotel_chain": "HOTEL",
        "seat": "SEAT_TYPE", "seat_type": "SEAT_TYPE",
        "dietary": "DIETARY", "diet": "DIETARY", "food": "DIETARY",
        "department": "DEPARTMENT", "team": "DEPARTMENT",
        "accessibility": "ACCESSIBILITY",
        "flight_class": "FLIGHT_CLASS", "cabin": "FLIGHT_CLASS",
        "class": "FLIGHT_CLASS", "cabin_class": "FLIGHT_CLASS",
    }
    def canonicalize_relationship(self, raw):
        return self.RELATIONSHIP_MAP.get(raw.lower().strip().replace(" ", "_"), raw.upper())
    def canonicalize_entity_type(self, raw):
        return self.ENTITY_TYPE_MAP.get(raw.lower().strip().replace(" ", "_"), raw.upper())


class SmartKnowledgeGraph:
    def __init__(self):
        self.graph = {}
        self.ontology = OntologyManager()

    def store_triplet(self, user_id, subject, relationship, obj, object_type=""):
        rel = self.ontology.canonicalize_relationship(relationship)
        otype = self.ontology.canonicalize_entity_type(object_type) if object_type else ""
        if user_id not in self.graph:
            self.graph[user_id] = []
        if otype:
            self.graph[user_id] = [
                t for t in self.graph[user_id]
                if not (t["relationship"] == rel and t["object_type"] == otype)
            ]
        triplet = {
            "subject": subject, "relationship": rel, "object": obj,
            "object_type": otype, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.graph[user_id].append(triplet)
        return triplet

    def query(self, user_id, relationship=None, object_type=None):
        results = self.graph.get(user_id, [])
        if relationship:
            results = [t for t in results if t["relationship"] == relationship]
        if object_type:
            results = [t for t in results if t["object_type"] == object_type]
        return results

    def all_facts(self, user_id):
        return self.graph.get(user_id, [])


_knowledge_graph = SmartKnowledgeGraph()


EXTRACTION_PROMPT = \"\"\"Extract knowledge triplets from the user's statement.
Return a JSON array of objects with these fields:
- "relationship": how the subject relates to the object (e.g. "prefers", "requires", "dislikes", "wants")
- "object": the entity (e.g. "Delta", "aisle", "vegetarian", "business class")
- "object_type": category (e.g. "airline", "hotel", "seat_type", "dietary", "flight_class")

Rules:
- Only extract PERSISTENT facts (preferences, requirements) — not one-time plans
- "I need to fly Tuesday" is NOT a preference — skip it
- "I always fly United" IS a preference — extract it
- Return ONLY the JSON array, no other text

Examples:
Input: "I prefer Delta and I'm vegetarian"
Output: [{"relationship": "prefers", "object": "Delta", "object_type": "airline"}, {"relationship": "requires", "object": "vegetarian", "object_type": "dietary"}]

Input: "Book me a flight to NYC next week"
Output: []
\"\"\"


async def extract_knowledge_triplets(statement):
    extractor = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="Extractor",
        instructions=EXTRACTION_PROMPT,
    )
    response = await extractor.run(statement)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\\n", 1)[1] if "\\n" in text else text[3:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


@tool
async def learn_about_user(user_id: str, statement: str) -> str:
    \"\"\"Extract and store facts/preferences from a user's statement in semantic memory.

    Args:
        user_id: Employee ID (e.g. "E001")
        statement: Natural language containing facts to remember
    \"\"\"
    triplets = await extract_knowledge_triplets(statement)
    if not triplets:
        return "No persistent facts found in that statement."

    ontology = OntologyManager()
    stored = []
    for t in triplets:
        _knowledge_graph.store_triplet(
            user_id, user_id, t["relationship"], t["object"], t.get("object_type", ""),
        )
        rel = ontology.canonicalize_relationship(t["relationship"])
        otype = ontology.canonicalize_entity_type(t.get("object_type", ""))
        stored.append(f"({user_id}, {rel}, {t['object']}/{otype})")
    return f"Learned {len(stored)} facts: " + "; ".join(stored)


@tool
async def query_user_knowledge(
    user_id: str,
    relationship: str = "",
    entity_type: str = "",
) -> str:
    \"\"\"Query the user's semantic memory for stored facts and preferences.

    Args:
        user_id: Employee ID (e.g. "E001")
        relationship: Optional filter — "PREFERS", "REQUIRES", "DISLIKES"
        entity_type: Optional filter — "AIRLINE", "HOTEL", "SEAT_TYPE", "DIETARY", "FLIGHT_CLASS"
    \"\"\"
    ontology = OntologyManager()
    rel = ontology.canonicalize_relationship(relationship) if relationship else None
    etype = ontology.canonicalize_entity_type(entity_type) if entity_type else None
    facts = _knowledge_graph.query(user_id, relationship=rel, object_type=etype)
    if not facts:
        return "No matching facts found."
    lines = [f"({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})" for f in facts]
    return "\\n".join(lines)


# ─── Procedural memory (filesystem) ───

@tool
async def load_procedure(task_type: str) -> str:
    \"\"\"Load a task-specific procedure from the procedures directory.

    Args:
        task_type: The type of task — "domestic_booking" or "international_booking"
    \"\"\"
    path = Path(f"procedures/{task_type}.md")
    if not path.exists():
        return f"No procedure found for '{task_type}'. Available: domestic_booking, international_booking"
    return path.read_text(encoding="utf-8")


# ─── Shared tool list (ALL tools — given to every agent in Part 2) ───

ALL_MEMORY_TOOLS = [
    remember_event, recall_events,
    learn_about_user, query_user_knowledge,
    load_procedure,
]


# ─── Reset function for reproducible demos ───

def reset_memory():
    global _episodic_store, _knowledge_graph
    _episodic_store.clear()
    _knowledge_graph = SmartKnowledgeGraph()

    _episodic_store.extend([
        {"id": "E001-trip1", "user_id": "E001", "event_type": "trip",
         "description": "New York trip for tech conference (Oct 15-18, 2025). Marriott Times Square, rated 5/5.",
         "details": {"destination": "New York", "hotel": "Marriott Times Square", "rating": 5, "total_cost": 1760},
         "timestamp": "2025-10-15T00:00:00"},
        {"id": "E001-trip2", "user_id": "E001", "event_type": "trip",
         "description": "London trip for client meeting (Nov 20-25, 2025). Marriott Park Lane, rated 4/5.",
         "details": {"destination": "London", "hotel": "Marriott Park Lane", "rating": 4, "total_cost": 3900},
         "timestamp": "2025-11-20T00:00:00"},
        {"id": "E001-trip3", "user_id": "E001", "event_type": "trip",
         "description": "Chicago trip for team offsite (Jan 10-12, 2026). Hampton Inn, rated 3/5. Hotel was noisy.",
         "details": {"destination": "Chicago", "hotel": "Hampton Inn", "rating": 3, "total_cost": 980},
         "timestamp": "2026-01-10T00:00:00"},
    ])

    _knowledge_graph.store_triplet("E001", "E001", "prefers", "Delta", "airline")
    _knowledge_graph.store_triplet("E001", "E001", "prefers", "aisle", "seat_type")
    _knowledge_graph.store_triplet("E001", "E001", "prefers", "Marriott", "hotel")
    _knowledge_graph.store_triplet("E001", "E001", "requires", "vegetarian", "dietary")

reset_memory()

print("Memory tools defined:")
print("  Episodic:   remember_event, recall_events")
print("  Semantic:   learn_about_user, query_user_knowledge")
print("  Procedural: load_procedure")
print()
print("Preloaded data:")
print(f"  {len(_episodic_store)} episodic events (NYC 5/5, London 4/5, Chicago 3/5)")
print(f"  {len(_knowledge_graph.all_facts('E001'))} semantic facts (Delta, aisle, Marriott, vegetarian)")
print()
print("reset_memory() available — call to restore baseline state")"""))

# ============================================================
# Cell 10: Load agent instructions + procedure files (shared approach)
# ============================================================
cells.append(code("""\
# In this approach, ALL agents get ALL memory tools.
# Notice: every agent has access to episodic, semantic, AND procedural tools.
# Prompt files are in prompts/ and procedures/ — let's verify they exist and preview them.

prompt_files = ["prompts/router_shared.md", "prompts/policy_shared.md", "prompts/booking_shared.md"]
procedure_files = ["procedures/domestic_booking.md", "procedures/international_booking.md"]

print("Agent instructions (shared approach — every agent gets all tools):")
for pf in prompt_files:
    content = load_instructions(pf)
    print(f"  {pf} ({len(content.splitlines())} lines)")
    # Show first 3 lines as preview
    for line in content.splitlines()[:3]:
        print(f"    {line}")
    print()

print("Procedure files:")
for pf in procedure_files:
    content = load_instructions(pf)
    print(f"  {pf} ({len(content.splitlines())} lines)")
    print(f"    {content.splitlines()[0]}")
    print()"""))

# ============================================================
# Cell 11: Sequential orchestration intro
# ============================================================
cells.append(md("""\
### Orchestrating a Sequential Pipeline

We have three agents; now we need to run them in order: Router → Policy → Booking. The Agent Framework provides `SequentialBuilder` for exactly this — wire a list of agents into a pipeline that chains their conversation automatically.

The pattern is simple:
1. Create each agent with `Agent(client=..., name=..., ...)`
2. Pass them to `SequentialBuilder(participants=[...]).build()` to create a workflow
3. Run the workflow — each agent sees the full conversation from previous agents

```python
router = Agent(client=client, name="Router", instructions=..., tools=[...])
policy = Agent(client=client, name="Policy", instructions=..., tools=[...])
booking = Agent(client=client, name="Booking", instructions=..., tools=[...])

workflow = SequentialBuilder(participants=[router, policy, booking]).build()
result = await workflow.run(user_msg)
```

`SequentialBuilder` handles lifecycle, conversation chaining, and cleanup. Let's see this in action with our shared-tools agents."""))

# ============================================================
# Cell 12: Sequential pipeline demo (shared tools)
# ============================================================
cells.append(code("""\
reset_memory()

async def demo_shared_tools():
    \"\"\"Three agents chained sequentially — all share the same memory tools.\"\"\"
    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT,
        credential=credential,
    )

    user_msg = "Book me a trip to London next month for a client meeting."
    print(f"User: {user_msg}\\n")

    # ─── Create specialist agents — all share the same memory tools ───
    router = Agent(
        client=client,
        name="Router",
        instructions=load_instructions("prompts/router_shared.md"),
        tools=ALL_MEMORY_TOOLS,
    )
    policy = Agent(
        client=client,
        name="PolicyAgent",
        instructions=load_instructions("prompts/policy_shared.md"),
        tools=ALL_MEMORY_TOOLS,
    )
    booking = Agent(
        client=client,
        name="BookingAgent",
        instructions=load_instructions("prompts/booking_shared.md"),
        tools=ALL_MEMORY_TOOLS,
    )

    # ─── Wire into a sequential pipeline via SequentialBuilder ───
    workflow = SequentialBuilder(
        participants=[router, policy, booking],
        intermediate_outputs=True,
    ).build()

    result = await workflow.run(user_msg)

    agent_names = ["Router", "PolicyAgent", "BookingAgent"]
    for i, output in enumerate(result.get_outputs()):
        name = agent_names[i] if i < len(agent_names) else f"Agent {i}"
        # Each output value is the conversation (list[Message]) at that point
        messages = output.value if isinstance(output.value, list) else [output.value]
        # Show the last assistant message from each agent
        assistant_msgs = [m for m in messages if m.role == "assistant" and m.author_name == name]
        if assistant_msgs:
            print(f"--- [{name}] ---")
            print(assistant_msgs[-1].text)
            print()
        elif messages:
            # Fallback: show last assistant message
            last_asst = [m for m in messages if m.role == "assistant"]
            if last_asst:
                print(f"--- [{name}] ---")
                print(last_asst[-1].text)
                print()

print("=== Part 2: Shared Tools — Every Agent Gets Everything ===\\n")
asyncio.run(demo_shared_tools())"""))

# ============================================================
# Cell 13: What happened + what's wrong
# ============================================================
cells.append(md("""\
### What Happened — And What's Wrong

The pipeline ran: Router gathered context, Policy checked rules, Booking made a recommendation. It works. But look at the tool assignment:

| Agent | Tools Available | Tools Needed |
|---|---|---|
| Router | remember_event, recall_events, learn_about_user, query_user_knowledge, load_procedure | recall_events, query_user_knowledge |
| Policy | remember_event, recall_events, learn_about_user, query_user_knowledge, load_procedure | load_procedure |
| Booking | remember_event, recall_events, learn_about_user, query_user_knowledge, load_procedure | remember_event (to log the booking) |

Every agent had 5 tools. Each agent needed 1–2. That means:

- **Did the Booking agent re-query preferences** that the Router already found? Maybe. It had the tools. The conversation from the Router contained the findings, but the model might call `query_user_knowledge` anyway — and get a different interpretation.
- **Did the Policy agent look at episode history** it doesn't need? It could have. Nothing prevented it.
- **Which agents queried which memory types?** You'd have to parse the conversation to find out. There's no structured record.
- **Every request ran all three agents** — even a simple policy question that doesn't need booking.

This is the brute-force approach: it works, but it violates the principle that **memory access defines responsibility**. Let's fix it."""))

# ============================================================
# PART 3: Scoped Memory + Structured Handoff
# ============================================================

# ============================================================
# Cell 14: HandoffContext explanation
# ============================================================
cells.append(md("""\
---
## Part 3: Scoped Memory + Structured Handoff

### What Is a HandoffContext?

Think of it as a **shared clipboard**. Before each agent starts, it reads the clipboard to see what previous agents found. After it's done, it writes its findings back. At the end of the pipeline, you have a complete record of the entire workflow.

**What it solves** — mapped to the three failure modes from Part 1:

| Failure Mode | Without HandoffContext | With HandoffContext |
|---|---|---|
| **Context loss** | Booking infers preferences from conversation | Booking reads `user_preferences` — a typed dict set by Router |
| **Context drift** | Booking re-queries semantic memory, gets different interpretation | Booking reads Router's findings — single source of truth |
| **No audit trail** | Parse free-text conversation to reconstruct what happened | `agents_visited` tracks exactly who ran, what they did, when |

**How fields map to memory types:**

| HandoffContext Field | Memory Type | Set By | Read By |
|---|---|---|---|
| `user_preferences` | Semantic memory | Router | Booking |
| `relevant_history` | Episodic memory | Router | Booking |
| `policy_findings` | Procedural memory | Policy | Booking |

The Booking agent gets **ZERO memory tools** — just handoff tools. It reads what others found. This is the principle made concrete."""))

# ============================================================
# Cell 15: HandoffContext dataclass
# ============================================================
cells.append(code("""\
from dataclasses import dataclass, field, asdict


@dataclass
class HandoffContext:
    \"\"\"Structured context passed between agents via tools.

    Fields are organized by who sets them:
    - User identification: set at init
    - Request classification: set by Router
    - Memory findings: set by the agent that owns each memory type
    - Handoff tracking: set by each agent
    - Final state: set by last agent
    \"\"\"

    # ─── User identification ───
    user_id: str = "E001"

    # ─── Request classification (set by Router) ───
    request_summary: str = ""
    request_type: str = ""         # "booking", "policy_question", "general"
    destination: str = ""
    is_international: bool = False

    # ─── Memory findings ───
    # user_preferences ← semantic memory (set by Router)
    user_preferences: dict = field(default_factory=dict)
    # relevant_history ← episodic memory (set by Router)
    relevant_history: list = field(default_factory=list)
    # policy_findings ← procedural memory (set by Policy)
    policy_findings: list = field(default_factory=list)
    approval_required: bool = False

    # ─── Handoff tracking (set by each agent) ───
    agents_visited: list = field(default_factory=list)

    # ─── Final state (set by last agent) ───
    status: str = "in_progress"    # "in_progress", "complete", "needs_approval"
    final_response: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "HandoffContext":
        data = json.loads(json_str)
        return cls(**data)

    def add_agent_visit(self, agent_name: str, action: str):
        self.agents_visited.append({
            "agent": agent_name,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Module-level shared context — agents read/write via tools
_handoff_context = HandoffContext()

print("HandoffContext defined")
print(f"Fields: {list(HandoffContext.__dataclass_fields__.keys())}")"""))

# ============================================================
# Cell 16: The three handoff tools explained
# ============================================================
cells.append(md("""\
### The Three Handoff Tools

Each agent gets these tools to interact with the HandoffContext:

- **`get_handoff_context`** — Read what previous agents found. Call this at the START of your turn.
- **`update_handoff_context`** — Write your findings for the next agent. Call this BEFORE responding.
- **`record_agent_visit`** — Sign the clipboard so we know you were here and what you did.

The key design choice is what ELSE each agent gets:

| Agent | Memory Tools | Handoff Tools | Total Tools |
|---|---|---|---|
| **Router** | recall_events, query_user_knowledge, learn_about_user | get / update / record | **6** |
| **Policy** | load_procedure | get / update / record | **4** |
| **Booking** | *(none)* | get / update / record | **3** |

Compare to Part 2 where every agent had 5 memory tools. Now:
- The **Router** owns episodic + semantic memory — it's the only agent that can query preferences and history
- The **Policy** agent owns procedural memory — it's the sole authority on rules
- The **Booking** agent owns NO memory — it reads the HandoffContext and acts on combined findings"""))

# ============================================================
# Cell 17: Handoff tools + scoped agent instructions
# ============================================================
cells.append(code("""\
# ─── Handoff tools (used by all agents) ───

@tool
async def get_handoff_context() -> str:
    \"\"\"Read the current handoff context.

    Call this at the START of your turn to see what previous agents found.
    The context contains request details, preferences, history, policy findings,
    and which agents have already visited.
    \"\"\"
    return _handoff_context.to_json()


@tool
async def update_handoff_context(updates_json: str) -> str:
    \"\"\"Update the handoff context with your findings.

    Call this BEFORE responding to record what you found or decided.
    The next agent will see your updates.

    Args:
        updates_json: JSON object with fields to update.
            Example: {"request_type": "booking", "destination": "London", "is_international": true}
    \"\"\"
    updates = json.loads(updates_json)
    for key, value in updates.items():
        if hasattr(_handoff_context, key):
            current = getattr(_handoff_context, key)
            if isinstance(current, list) and isinstance(value, list):
                current.extend(value)
            elif isinstance(current, dict) and isinstance(value, dict):
                current.update(value)
            else:
                setattr(_handoff_context, key, value)
    return f"Context updated: {list(updates.keys())}"


@tool
async def record_agent_visit(agent_name: str, action_summary: str) -> str:
    \"\"\"Record that this agent has processed the request.

    Call this to log your visit in the handoff context for traceability.

    Args:
        agent_name: Your agent name (e.g. "Router", "PolicyAgent", "BookingAgent")
        action_summary: Brief description of what you did
    \"\"\"
    _handoff_context.add_agent_visit(agent_name, action_summary)
    return f"Recorded visit: {agent_name} — {action_summary}"


HANDOFF_TOOLS = [get_handoff_context, update_handoff_context, record_agent_visit]

# ─── Scoped tool lists — THIS IS THE KEY DIFFERENCE ───
# Each agent gets ONLY the memory tools for the memory types it owns

ROUTER_TOOLS = [recall_events, query_user_knowledge, learn_about_user] + HANDOFF_TOOLS   # episodic + semantic + handoff
POLICY_TOOLS = [load_procedure] + HANDOFF_TOOLS                                           # procedural + handoff
BOOKING_TOOLS = [remember_event] + HANDOFF_TOOLS                                          # record booking + handoff (NO querying)

# ─── Load scoped agent instructions from files ───

print("Scoped tool assignment:")
print(f"  Router:  {len(ROUTER_TOOLS)} tools — episodic + semantic + handoff")
print(f"  Policy:  {len(POLICY_TOOLS)} tools — procedural + handoff")
print(f"  Booking: {len(BOOKING_TOOLS)} tools — record + handoff (NO querying)")
print()

scoped_prompts = ["prompts/router_scoped.md", "prompts/policy_scoped.md", "prompts/booking_scoped.md"]
print("Scoped agent instructions:")
for pf in scoped_prompts:
    content = load_instructions(pf)
    print(f"  {pf} ({len(content.splitlines())} lines)")
    print(f"    {content.splitlines()[0]}")
print()
print("Compare to Part 2: every agent had 5 memory tools")
print("Now: Router=3 memory + 3 handoff, Policy=1 memory + 3 handoff, Booking=1 record + 3 handoff")"""))

# ============================================================
# Cell 18: Structured handoff demo
# ============================================================
cells.append(code("""\
reset_memory()
_handoff_context.__init__()  # Reset context to defaults

async def demo_scoped_handoff():
    \"\"\"Same request as Part 2, but each agent has scoped memory access.\"\"\"
    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT,
        credential=credential,
    )

    user_msg = "Book me a trip to London next month for a client meeting."
    print(f"User: {user_msg}\\n")

    # ─── Agent 1: Router — episodic + semantic + handoff ───
    router = Agent(
        client=client,
        name="Router",
        instructions=load_instructions("prompts/router_scoped.md"),
        tools=ROUTER_TOOLS,
    )
    router_result = await router.run(user_msg)
    print("--- [Router] ---")
    print(router_result.text)
    print()

    # ─── Agent 2: Policy — procedural + handoff ───
    policy = Agent(
        client=client,
        name="PolicyAgent",
        instructions=load_instructions("prompts/policy_scoped.md"),
        tools=POLICY_TOOLS,
    )
    policy_result = await policy.run(
        f"Previous agent (Router) findings:\\n{router_result.text}\\n\\nOriginal request: {user_msg}"
    )
    print("--- [PolicyAgent] ---")
    print(policy_result.text)
    print()

    # ─── Agent 3: Booking — record + handoff ONLY ───
    booking = Agent(
        client=client,
        name="BookingAgent",
        instructions=load_instructions("prompts/booking_scoped.md"),
        tools=BOOKING_TOOLS,
    )
    booking_result = await booking.run(
        f"Router findings:\\n{router_result.text}\\n\\nPolicy findings:\\n{policy_result.text}\\n\\nOriginal request: {user_msg}"
    )
    print("--- [BookingAgent] ---")
    print(booking_result.text)
    print()

    # Show the structured record
    print("=" * 60)
    print("HANDOFF CONTEXT — Structured Record of the Workflow")
    print("=" * 60)
    ctx = _handoff_context
    print(f"\\n  Request:       {ctx.request_summary}")
    print(f"  Type:          {ctx.request_type}")
    print(f"  Destination:   {ctx.destination}")
    print(f"  International: {ctx.is_international}")
    print(f"  Approval:      {ctx.approval_required}")
    print(f"  Status:        {ctx.status}")
    print(f"\\n  Agents visited ({len(ctx.agents_visited)}):")
    for visit in ctx.agents_visited:
        print(f"    {visit['agent']}: {visit['action']}")
    print(f"\\n  User preferences (← semantic memory, set by Router):")
    for k, v in ctx.user_preferences.items():
        print(f"    {k}: {v}")
    print(f"\\n  Relevant history (← episodic memory, set by Router): {len(ctx.relevant_history)} items")
    for item in ctx.relevant_history:
        if isinstance(item, dict):
            print(f"    - {item.get('description', item)}")
        else:
            print(f"    - {item}")
    print(f"\\n  Policy findings (← procedural memory, set by Policy): {len(ctx.policy_findings)} items")
    for finding in ctx.policy_findings:
        print(f"    - {finding}")

print("=== Part 3: Scoped Memory + Structured Handoff ===\\n")
asyncio.run(demo_scoped_handoff())"""))

# ============================================================
# Cell 19: Walk through HandoffContext output
# ============================================================
cells.append(md("""\
### What the HandoffContext Shows

Look at the structured record above. Same request as Part 2 — "Book me a trip to London" — but now we have:

**Agents visited** — an exact timeline of who ran, what they did, and when. No need to parse free-text conversation.

**user_preferences** — set by the Router from semantic memory. The Booking agent read this field; it never called `query_user_knowledge` itself. Single source of truth, no context drift.

**relevant_history** — set by the Router from episodic memory. Past trips to London and other destinations, gathered once.

**policy_findings** — set by the Policy agent from procedural memory. The rules that apply to this trip, checked once by the agent that owns that knowledge.

**Compare to Part 2:**
- Same request, same data, same recommendation
- But now we know **exactly which agent gathered what** from which memory type
- The Booking agent never called a memory query tool — it read structured findings
- If something goes wrong, you can inspect each field to find where the pipeline broke"""))

# ============================================================
# Cell 20: Conditional dispatch intro
# ============================================================
cells.append(md("""\
### Conditional Dispatch

Parts 2 and 3 always ran all three agents in sequence. But not every request needs a full pipeline:

| Request | Agents Needed |
|---|---|
| "What's the international booking process?" | Router → Policy (stops) |
| "Book me a trip to Chicago" | Router → Policy → Booking |
| "What airline do I prefer?" | Router only |

Running all three agents for a simple policy question wastes time and tokens. With manual orchestration, we can add a **classification step** — the Router classifies the request, and Python routes to the right specialist.

```
                    ┌─→ PolicyAgent (policy questions — stops here)
User → Router ──────┤
                    └─→ PolicyAgent → BookingAgent (booking requests)
```"""))

# ============================================================
# Cell 21: Conditional dispatch demo
# ============================================================
cells.append(code("""\
# ─── Classification tool — Router calls this to set the route ───

_request_classification = ""

@tool
async def classify_request(request_type: str) -> str:
    \"\"\"Classify the user's request to determine routing.

    MUST be called before responding. The classification determines
    which specialist agent handles the request next.

    Args:
        request_type: One of:
            - "booking" — user wants to book travel (needs policy + booking agents)
            - "policy_question" — user asks about rules/procedures (needs policy agent only)
            - "general" — simple memory query, no specialist needed
    \"\"\"
    global _request_classification
    _request_classification = request_type
    return f"Request classified as: {request_type}"


async def demo_conditional_dispatch():
    \"\"\"Three different requests, three different routing paths.\"\"\"
    global _request_classification, _handoff_context

    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT,
        credential=credential,
    )

    router_tools = [recall_events, query_user_knowledge, learn_about_user, classify_request] + HANDOFF_TOOLS

    requests = [
        ("What's the process for booking international travel?", "policy_question"),
        ("Book me a trip to Chicago next week.", "booking"),
        ("What airline do I prefer?", "general"),
    ]

    for user_msg, expected_type in requests:
        reset_memory()
        _request_classification = ""
        _handoff_context = HandoffContext()

        # ─── Router classifies and gathers context ───
        router = Agent(
            client=client,
            name="RouterConditional",
            instructions=load_instructions("prompts/router_conditional.md"),
            tools=router_tools,
        )
        router_result = await router.run(user_msg)

        print(f"User: {user_msg}")
        print(f"Expected: {expected_type}")
        print(f"Classification: {_request_classification}")

        agents_that_ran = ["RouterConditional"]

        # ─── Conditional routing based on classification ───
        if _request_classification == "general":
            # Router answered — no specialist needed
            print(f"Agents that ran: {' → '.join(agents_that_ran)}")
            print(f"Response: {router_result.text[:200]}...")

        elif _request_classification == "policy_question":
            # Route to Policy only — no booking needed
            policy = Agent(
                client=client,
                name="PolicyConditional",
                instructions=load_instructions("prompts/policy_scoped.md"),
                tools=POLICY_TOOLS,
            )
            policy_result = await policy.run(
                f"Router findings:\\n{router_result.text}\\n\\nOriginal request: {user_msg}"
            )
            agents_that_ran.append("PolicyConditional")
            print(f"Agents that ran: {' → '.join(agents_that_ran)}")
            print(f"Response: {policy_result.text[:200]}...")

        else:   # "booking" or fallback
            # Full pipeline: Policy → Booking
            policy = Agent(
                client=client,
                name="PolicyConditional",
                instructions=load_instructions("prompts/policy_scoped.md"),
                tools=POLICY_TOOLS,
            )
            policy_result = await policy.run(
                f"Router findings:\\n{router_result.text}\\n\\nOriginal request: {user_msg}"
            )
            agents_that_ran.append("PolicyConditional")

            booking = Agent(
                client=client,
                name="BookingConditional",
                instructions=load_instructions("prompts/booking_scoped.md"),
                tools=BOOKING_TOOLS,
            )
            booking_result = await booking.run(
                f"Router findings:\\n{router_result.text}\\n\\nPolicy findings:\\n{policy_result.text}\\n\\nOriginal request: {user_msg}"
            )
            agents_that_ran.append("BookingConditional")
            print(f"Agents that ran: {' → '.join(agents_that_ran)}")
            print(f"Response: {booking_result.text[:200]}...")

        print()
        print("-" * 60)
        print()

print("=== Conditional Dispatch: Different Paths for Different Requests ===\\n")
asyncio.run(demo_conditional_dispatch())"""))

# ============================================================
# Cell 22: Orchestration patterns
# ============================================================
cells.append(md("""\
### Orchestration Pattern Reference

| Pattern | Implementation | When to Use |
|---|---|---|
| **Sequential** | `SequentialBuilder(participants=[...]).build()` | Fixed pipeline — every request follows the same path |
| **Conditional** | Router sets classification, Python `if/else` routes | Route to different agents based on request type |
| **Short-circuit** | Skip agents when classification says they're not needed | Simple queries that don't need the full pipeline |

This module used **sequential** (Parts 2–3), **conditional routing** (Part 3: router classifies, Python routes), and **short-circuit** (general queries stop at the Router).

**The patterns:**
```python
# Sequential — SequentialBuilder handles conversation chaining
router = Agent(client=client, name="Router", instructions=..., tools=[...])
policy = Agent(client=client, name="Policy", instructions=..., tools=[...])
booking = Agent(client=client, name="Booking", instructions=..., tools=[...])

workflow = SequentialBuilder(participants=[router, policy, booking]).build()
result = await workflow.run(msg)

# Conditional — manual orchestration with Python routing
router_result = await router.run(msg)
if classification == "general":
    pass   # Router already answered
elif classification == "policy_question":
    result = await policy.run(f"Context:\\n{router_result.text}\\n\\nRequest: {msg}")
else:   # booking
    policy_result = await policy.run(...)
    result = await booking.run(...)
```

`SequentialBuilder` manages conversation chaining automatically. For conditional routing, manual orchestration gives you full control over which agents run."""))

# ============================================================
# Cell 23: Summary
# ============================================================
cells.append(md("""\
---
## Summary

### The Central Insight

**Memory access defines responsibility.** Giving an agent a memory type is a statement about what that agent is responsible for — not a default. Assign memory types based on the agent's job, using the 4-question framework:

1. What is this agent's primary job?
2. What information does it need?
3. Which memory type holds that information?
4. Does it need direct access, or can it receive findings from another agent?

### What We Built

| Approach | How Tools Are Assigned | Memory Isolation | Traceability |
|---|---|---|---|
| **Shared tools** (Part 2) | Every agent gets everything | None — any agent can query any memory | None — parse conversation |
| **Scoped handoff** (Part 3) | Each agent gets only its memory types | Full — router owns episodic+semantic, policy owns procedural, booking owns nothing | Full — HandoffContext records who did what |

### Key Takeaways

1. **Shared tools are the simplest approach** — all agents call the same tools that read the same memory. Good for prototypes, but violates scoping principles and gives no audit trail.

2. **HandoffContext adds structure** — a typed object that carries findings between agents. Router writes `user_preferences` from semantic memory, Policy writes `policy_findings` from procedural memory, Booking reads both and never queries memory directly.

3. **Scoping prevents conflicts structurally** — Module 5 resolved conflicts via system-prompt rules ("policy > preference > history"). This module prevents them by separating memory ownership: the Router advocates for the user, the Policy agent advocates for the rules. No single agent holds competing perspectives.

4. **Conditional dispatch avoids waste** — not every request needs every agent. The Router classifies the request, and Python routing sends it to the right specialist.

### Six Modules of Memory

| | Session (M1) | Episodic (M2) | Semantic (M3) | Procedural (M4) | Combined (M5) | Handoff (M6) |
|---|---|---|---|---|---|---|
| **Stores** | Current conversation | Past events | Facts & preferences | Behaviors & procedures | All of the above | All + handoff context |
| **Answers** | "What did we just discuss?" | "What happened?" | "What is true?" | "How should I act?" | "What should I do?" | "Who should handle this?" |
| **Agents** | 1 | 1 | 1 | 1 | 1 | 3 (Router, Policy, Booking) |
| **Orchestration** | — | — | — | — | Instructions | Sequential + conditional routing |
| **Key addition** | — | — | — | — | Conflict resolution | Scoped memory ownership |"""))

# ============================================================
# Cell 24: What's Next
# ============================================================
cells.append(md("""\
---
## What's Next

We've covered how memory transfers between agents within a single system. Each agent owns its memory types, and findings travel via a structured HandoffContext.

But what happens when **multiple users share the same agent system** — and need to share some memories while keeping others private?

In **Module 7: Shared Memory with Redis**, we'll explore how agents access a common knowledge base while maintaining per-user privacy."""))


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

with open("06_memory_handoff.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print(f"Built 06_memory_handoff.ipynb: {len(cells)} cells")
for i, c in enumerate(cells, 1):
    t = c["cell_type"]
    src = "".join(c["source"])
    preview = src[:80].replace("\n", " ")
    print(f"  {i:2d}. [{t:4s}] {preview}...")

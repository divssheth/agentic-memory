"""Build Module 4: Procedural Memory notebook."""
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
# Module 4: Procedural Memory

Modules 2 and 3 taught the agent **what to remember**:
- **Episodic memory** — past events: "Sarah's NYC trip was great"
- **Semantic memory** — current facts: "Sarah prefers Delta"

But neither answers **how** the agent should approach a task. Right now, that knowledge lives in a Python string deep inside our code — unversioned, unreviewable, impossible to diff.

In this module, we'll treat instructions as **procedural memory** — the agent's learned behaviors, refined over time and stored as version-controlled files.

## What You'll Learn
1. Why instructions are a **third kind of memory**, not just configuration
2. How to move instructions from **hardcoded strings to files** on the filesystem
3. The **feedback loop**: Run → Observe weakness → Refine → Verify improvement
4. How to create **task-specific procedures** — conditional playbooks loaded by context
5. **When to stop refining** — convergence signals, over-fitting risks, and stopping rules
6. How **git history** becomes the version-control system for procedural memory

## The Journey
```
Session memory (Module 1)
    → Episodic memory for events (Module 2)
        → Semantic memory for facts (Module 3)
            → Procedural memory for behaviors (this module)
```"""))

# ============================================================
# Cell 3: Setup heading
# ============================================================
cells.append(md("""\
---
## Setup

> **Prerequisites**:
> - Modules 1–3 completed
> - Azure AI Foundry project endpoint in your `.env` file
> - Git installed (for version tracking — optional but recommended)
>
> This module runs entirely with Azure AI Foundry — no additional infrastructure needed.
> Memory tools use in-memory stores so you can focus on the procedural memory concept."""))

# ============================================================
# Cell 4: Imports + env vars + helpers
# ============================================================
cells.append(code("""\
import os
import json
import asyncio
import difflib
import nest_asyncio
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv("../../.env", override=True)

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
TENANT_ID = os.environ.get("AZURE_TENANT_ID", "16b3c013-d300-468d-ac64-7eda0820b6d3")

print(f"Project:  {PROJECT_ENDPOINT}")
print(f"Model:    {MODEL_DEPLOYMENT}")


def load_instructions(path: str) -> str:
    \"\"\"Load agent instructions from a markdown file.\"\"\"
    return Path(path).read_text(encoding="utf-8")


def show_diff(old_path: str, new_path: str) -> None:
    \"\"\"Show a unified diff between two instruction files.\"\"\"
    old_lines = Path(old_path).read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = Path(new_path).read_text(encoding="utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=old_path, tofile=new_path)
    output = "".join(diff)
    if output:
        print(output)
    else:
        print("(no differences)")

print("\\nHelpers defined: load_instructions(), show_diff()")"""))

# ============================================================
# Cell 5: Part 1 heading — Instructions Are Memory Too
# ============================================================
cells.append(md("""\
---
## Part 1: Instructions Are Memory Too

### Three Kinds of Knowledge

By now, our travel assistant has two memory systems:

| Memory Type | What It Stores | Example |
|---|---|---|
| **Episodic** | Events, experiences | "Sarah's NYC trip cost $1,760" |
| **Semantic** | Facts, preferences | "Sarah prefers Delta" |
| **???** | How to approach tasks | ???

The missing piece is **procedural memory** — the knowledge of *how to do things*.

In cognitive psychology, this is the distinction between:
- **Declarative knowledge**: knowing *what* (episodic + semantic)
- **Procedural knowledge**: knowing *how* (riding a bike, booking a trip)

For an agent, procedural memory is its **instructions** — the playbook that governs behavior."""))

# ============================================================
# Cell 6: The Problem with Hardcoded Instructions
# ============================================================
cells.append(md("""\
### The Problem Today

In Modules 2 and 3, our agent instructions lived in Python strings:

```python
INSTRUCTIONS_V3 = \"\"\"You are a corporate travel assistant...

## Episodic Memory — Past Events
...
## Semantic Memory — Facts & Preferences
...
\"\"\"
```

This works, but it has serious problems:

- **No version history**: You can't see what changed between V2 and V3
- **No diffs**: Two 50-line instruction strings look identical in a code review
- **No rollback**: If V3 is worse than V2, you have to manually revert
- **No audit trail**: Who changed what, when, and why?
- **Mixed concerns**: Prompt engineering changes are buried in Python code changes

The shift: **treat instructions as first-class artifacts** — files on the filesystem, tracked by git, reviewed in PRs, diffed and rolled back like any other code."""))

# ============================================================
# Cell 7: What Makes Good Procedural Memory
# ============================================================
cells.append(md("""\
### What Belongs in Procedural Memory?

Not everything is procedural. Here's the boundary:

| **Procedural memory** (how to act) | **NOT procedural** (use other memory) |
|---|---|
| Booking workflow steps | "Sarah prefers Delta" (semantic) |
| Escalation procedures | "NYC trip cost $1,760" (episodic) |
| When-to-use-which-memory rules | "Book me a flight Tuesday" (request) |
| Task checklists | "I'm vegetarian" (semantic fact) |
| Budget verification steps | Travel cost data (grounding/RAG) |

Think of it this way:
- **Semantic memory** tells the agent what's true about the world
- **Episodic memory** tells the agent what happened in the past
- **Procedural memory** tells the agent how to use that knowledge to act"""))

# ============================================================
# Cell 8: Part 2 heading — From Strings to Files
# ============================================================
cells.append(md("""\
---
## Part 2: From Strings to Files

If procedural memory improves through iteration — run, observe, refine, verify — then the instructions need to live in a format that *supports* iteration.

A Python string buried in source code can't be diffed, reviewed in a PR, or rolled back independently. But a Markdown file can. Moving instructions to the filesystem is the foundation: **you can't improve what you can't track**.

Let's make the shift concrete."""))

# ============================================================
# Cell 9: Create prompts/v1.md
# ============================================================
cells.append(code("""\
# Create the prompts directory
os.makedirs("prompts", exist_ok=True)

V1_INSTRUCTIONS = \"\"\"You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.

## Episodic Memory — Past Events
You have access to the employee's episodic memory — their past trips and experiences.
When planning new trips:
1. Use recall_events to check if they've been to this destination before
2. Reference past experiences to make better recommendations
3. Use remember_event to store significant outcomes after bookings

## Semantic Memory — Facts & Preferences
You also have access to semantic memory — the user's facts, preferences, and relationships.

WHEN TO LEARN (call learn_about_user):
- User states a preference: "I prefer...", "I like...", "I always..."
- User shares a persistent fact: "I'm vegetarian", "I need wheelchair access"
- User corrects a previous preference: "Actually, I've switched to..."

WHEN TO QUERY (call query_user_knowledge):
- Before recommending flights or hotels → check known preferences first
- User asks about their own profile: "What do you know about me?"
- Making any personalized decision

WHEN TO SKIP:
- One-time situational info: "Book me a flight for Tuesday" (date, not a preference)
- Events that happened (use episodic memory for those, not semantic)
- Small talk, greetings, confirmations

WHEN FACTS CONFLICT:
- If the user explicitly corrects a preference, update immediately via learn_about_user
- If you detect a contradiction with stored knowledge, ASK the user before overwriting
- Newer explicit statements from the user override older ones

The current user is Sarah Chen (employee ID: E001, based in Seattle, USA).
Be concise and helpful.
\"\"\"

Path("prompts/v1.md").write_text(V1_INSTRUCTIONS, encoding="utf-8")
print("Created: prompts/v1.md")
print(f"Size: {len(V1_INSTRUCTIONS)} characters, {len(V1_INSTRUCTIONS.splitlines())} lines")"""))

# ============================================================
# Cell 10: Define tools + run agent with V1
# ============================================================
cells.append(code("""\
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework import tool

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

    Call this when:
    - A trip is completed or booked
    - The user shares feedback about a past experience
    - Something notable happens worth remembering for the future

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

    Call this when:
    - Planning a trip and want to check past experiences
    - The user asks about their travel history
    - Need context from previous trips for recommendations

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


# ─── Semantic memory (in-memory) ───

class OntologyManager:
    RELATIONSHIP_MAP = {
        "prefers": "PREFERS", "likes": "PREFERS", "prefer": "PREFERS",
        "loves": "PREFERS", "always": "PREFERS", "favorite": "PREFERS",
        "dislikes": "DISLIKES", "hates": "DISLIKES", "avoids": "DISLIKES",
        "never": "DISLIKES", "dont_like": "DISLIKES",
        "requires": "REQUIRES", "needs": "REQUIRES", "must_have": "REQUIRES",
        "works_at": "WORKS_AT", "employed_at": "WORKS_AT",
        "member_of": "MEMBER_OF", "belongs_to": "MEMBER_OF",
    }
    ENTITY_TYPE_MAP = {
        "airline": "AIRLINE", "carrier": "AIRLINE",
        "hotel": "HOTEL", "hotel_chain": "HOTEL",
        "seat": "SEAT_TYPE", "seat_type": "SEAT_TYPE",
        "dietary": "DIETARY", "diet": "DIETARY", "food": "DIETARY",
        "department": "DEPARTMENT", "team": "DEPARTMENT",
        "accessibility": "ACCESSIBILITY",
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
- "relationship": how the subject relates to the object (e.g. "prefers", "requires", "dislikes")
- "object": the entity (e.g. "Delta", "aisle", "vegetarian")
- "object_type": category (e.g. "airline", "hotel", "seat_type", "dietary", "accessibility")

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
        entity_type: Optional filter — "AIRLINE", "HOTEL", "SEAT_TYPE", "DIETARY"
    \"\"\"
    ontology = OntologyManager()
    rel = ontology.canonicalize_relationship(relationship) if relationship else None
    etype = ontology.canonicalize_entity_type(entity_type) if entity_type else None
    facts = _knowledge_graph.query(user_id, relationship=rel, object_type=etype)
    if not facts:
        return "No matching facts found."
    lines = [f"({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})" for f in facts]
    return "\\n".join(lines)


# ─── Preload data ───

_episodic_store.extend([
    {"id": "E001-trip1", "user_id": "E001", "event_type": "trip",
     "description": "New York trip for tech conference (Oct 15-18, 2025). Marriott Times Square, rated 5/5.",
     "details": {"destination": "New York", "hotel": "Marriott Times Square", "rating": 5, "total_cost": 1760},
     "timestamp": "2025-10-15T00:00:00"},
    {"id": "E001-trip2", "user_id": "E001", "event_type": "trip",
     "description": "London trip for client meeting (Nov 20-25, 2025). Marriott Park Lane, rated 4/5.",
     "details": {"destination": "London", "hotel": "Marriott Park Lane", "rating": 4, "total_cost": 3900},
     "timestamp": "2025-11-20T00:00:00"},
])

_knowledge_graph.store_triplet("E001", "E001", "prefers", "Delta", "airline")
_knowledge_graph.store_triplet("E001", "E001", "prefers", "aisle", "seat_type")
_knowledge_graph.store_triplet("E001", "E001", "prefers", "Marriott", "hotel")
_knowledge_graph.store_triplet("E001", "E001", "requires", "vegetarian", "dietary")

print("Tools defined:")
print("  Episodic:  remember_event, recall_events")
print("  Semantic:  learn_about_user, query_user_knowledge")
print()
print("Preloaded data:")
print(f"  {len(_episodic_store)} episodic events")
print(f"  {len(_knowledge_graph.all_facts('E001'))} semantic facts")"""))

# ============================================================
# Cell 11: Run agent with V1 (file-loaded)
# ============================================================
cells.append(code("""\
async def demo_v1():
    instructions = load_instructions("prompts/v1.md")
    print(f"Loaded instructions from: prompts/v1.md ({len(instructions)} chars)\\n")

    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=instructions,
        tools=[remember_event, recall_events, learn_about_user, query_user_knowledge],
    )
    turns = [
        "Hi, I'm Sarah Chen (E001). Can you help me plan a trip to Chicago?",
        "Book me a $3,000 business class flight to Chicago.",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")

print("=== V1: Module 3 instructions loaded from file ===\\n")
asyncio.run(demo_v1())"""))

# ============================================================
# Cell 12: V1 observation
# ============================================================
cells.append(md("""\
### What Just Happened?

File-loaded instructions, same behavior as Module 3. The agent has memory tools and trigger rules.

But look at that **$3,000 business class** request. Sarah is a **Senior Engineer** — her flight limit is $800, and she's only eligible for economy and economy plus. The agent may have checked preferences and past trips, but it didn't question the budget. It has no **procedure** for validating a booking request.

The instructions tell the agent *when to use memory*, but not *how to use it in a booking workflow*. That's the missing piece — and it's exactly what procedural memory adds."""))

# ============================================================
# Cell 13: Show the file
# ============================================================
cells.append(code("""\
print("=== prompts/v1.md ===\\n")
print(load_instructions("prompts/v1.md"))
print("\\n(This is now a reviewable, diffable, committable artifact)")"""))

# ============================================================
# Cell 14: Why files matter
# ============================================================
cells.append(md("""\
### Why This Matters

The instructions are now:
- **Reviewable**: `cat prompts/v1.md` — anyone can read them
- **Diffable**: changes are visible with `diff` or `git diff`
- **Committable**: `git add prompts/v1.md && git commit -m "v1: base instructions"`
- **Rollbackable**: `git checkout prompts/v1.md` if something breaks

Right now `prompts/v1.md` is identical to the Module 3 instructions. It tells the agent *when to use memory* but says nothing about *how to approach a booking*. Let's fix that."""))

# ============================================================
# Cell 15: Part 3 heading — The Feedback Loop
# ============================================================
cells.append(md("""\
---
## Part 3: The Feedback Loop — How Procedural Memory Forms

Think about how a new hire learns the booking process. Day one, they take a $3,000 business class request at face value and submit it. Their manager catches it: "Senior employees have an $800 limit — you need to check the policy first." Next time, they check. They've learned a *procedure* through doing it wrong, getting corrected, and doing it better.

Our agent learns the same way:

```
Run agent → Observe weakness → Refine instructions → Re-run → Verify improvement
```

This loop isn't just a software engineering pattern — it's **how procedural memory forms**. Each iteration teaches the agent a better way to approach a task. The instructions file is the artifact that captures what the agent has learned so far.

### What V1 Gets Wrong — and Why

V1 knows *what* Sarah prefers (semantic memory: Delta, aisle seats, Marriott). It knows *what happened* on past trips (episodic memory: NYC conference, London client meeting). But it has **zero procedure** for handling a booking request — no budget check, no workflow steps, no structured approach.

When Sarah asks for a $3,000 business class flight, the agent has no learned behavior to catch that violation. The fix isn't more memory tools — it's teaching the agent a *procedure*: a step-by-step booking workflow that tells it how to use those memory tools together.

That's the V1 → V2 transition: adding procedural knowledge."""))

# ============================================================
# Cell 16: Create V2 with booking procedure
# ============================================================
cells.append(code("""\
V2_INSTRUCTIONS = \"\"\"You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.

## Episodic Memory — Past Events
You have access to the employee's episodic memory — their past trips and experiences.
When planning new trips:
1. Use recall_events to check if they've been to this destination before
2. Reference past experiences to make better recommendations
3. Use remember_event to store significant outcomes after bookings

## Semantic Memory — Facts & Preferences
You also have access to semantic memory — the user's facts, preferences, and relationships.

WHEN TO LEARN (call learn_about_user):
- User states a preference: "I prefer...", "I like...", "I always..."
- User shares a persistent fact: "I'm vegetarian", "I need wheelchair access"
- User corrects a previous preference: "Actually, I've switched to..."

WHEN TO QUERY (call query_user_knowledge):
- Before recommending flights or hotels → check known preferences first
- User asks about their own profile: "What do you know about me?"
- Making any personalized decision

WHEN TO SKIP:
- One-time situational info: "Book me a flight for Tuesday" (date, not a preference)
- Events that happened (use episodic memory for those, not semantic)
- Small talk, greetings, confirmations

WHEN FACTS CONFLICT:
- If the user explicitly corrects a preference, update immediately via learn_about_user
- If you detect a contradiction with stored knowledge, ASK the user before overwriting
- Newer explicit statements from the user override older ones

## Booking Procedure
When the user requests a booking, follow these steps IN ORDER:

1. **Check preferences** (semantic memory): query_user_knowledge for airline, hotel, seat preferences
2. **Check history** (episodic memory): recall_events for past trips to the same destination
3. **Verify budget**: Senior employees have a $800 flight limit, economy/economy-plus only.
   - If the request exceeds the limit, explain the policy and suggest alternatives
   - Do NOT silently book over-budget options
4. **Explain your reasoning**: Tell the user WHY you're recommending what you recommend
   - "Based on your preference for Delta and your past positive experience at Marriott..."
   - "I notice this exceeds the $800 Senior-level flight budget, so here are alternatives..."
5. **Confirm before booking**: Always summarize the plan and ask for confirmation

The current user is Sarah Chen (employee ID: E001, level: Senior, based in Seattle, USA).
Be concise and helpful.
\"\"\"

Path("prompts/v2.md").write_text(V2_INSTRUCTIONS, encoding="utf-8")
print("Created: prompts/v2.md")
print(f"Size: {len(V2_INSTRUCTIONS)} characters, {len(V2_INSTRUCTIONS.splitlines())} lines")"""))

# ============================================================
# Cell 17: Diff V1 → V2
# ============================================================
cells.append(code("""\
print("=== What changed: V1 → V2 ===\\n")
show_diff("prompts/v1.md", "prompts/v2.md")"""))

# ============================================================
# Cell 18: V2 analysis
# ============================================================
cells.append(md("""\
### What We Added

The diff shows exactly one section was added: **Booking Procedure**. Five steps that define *how* to handle a booking request:

1. Check preferences (semantic)
2. Check history (episodic)
3. Verify budget against employee level
4. Explain reasoning
5. Confirm before booking

This is procedural memory — a step-by-step process the agent follows. It also tells the agent about Sarah's level (Senior, $800 limit), which wasn't in V1.

Let's re-run the same conversation and see the difference."""))

# ============================================================
# Cell 19: Re-run with V2
# ============================================================
cells.append(code("""\
async def demo_v2():
    instructions = load_instructions("prompts/v2.md")
    print(f"Loaded instructions from: prompts/v2.md ({len(instructions)} chars)\\n")

    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=instructions,
        tools=[remember_event, recall_events, learn_about_user, query_user_knowledge],
    )
    # Same conversation as V1 — same user, same requests
    turns = [
        "Hi, I'm Sarah Chen (E001). Can you help me plan a trip to Chicago?",
        "Book me a $3,000 business class flight to Chicago.",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")

print("=== V2: + Booking Procedure ===\\n")
asyncio.run(demo_v2())"""))

# ============================================================
# Cell 20: V2 observation
# ============================================================
cells.append(md("""\
### Same Tools, Different Behavior

Compare V1 and V2:

| | V1 | V2 |
|---|---|---|
| **$3,000 request** | May book without questioning | Flags the $800 Senior limit |
| **Preferences** | Uses them if it remembers | Checks systematically (step 1) |
| **Past trips** | May or may not check | Checks before recommending (step 2) |
| **Reasoning** | Often silent | Explains why (step 4) |
| **Confirmation** | May skip | Always asks (step 5) |

The four memory tools didn't change. What changed was the **procedure** — the step-by-step playbook that tells the agent how to use those tools in a booking workflow.

This is the core insight: **instructions are procedural memory**. They encode learned behaviors that improve over time."""))

# ============================================================
# Cell 21: Part 4 heading — Context-Dependent Procedures
# ============================================================
cells.append(md("""\
---
## Part 4: Context-Dependent Procedures

V2 gave the agent one procedure — a general booking workflow — and the agent adapted. But procedural memory in the real world is context-dependent. A doctor doesn't follow the same checklist for a routine checkup and emergency surgery. A travel agent doesn't follow the same steps for a domestic day-trip and an international relocation.

The agent's procedural memory needs to grow — it needs *task-specific* procedures that activate based on context:

| Domestic Booking | International Booking |
|---|---|
| Check preferences | Check preferences |
| Check past trips to same city | Check past trips + **visa history** |
| Verify budget ($800 Senior limit) | Verify budget ($800 Senior limit) |
| | **Check travel insurance requirement** |
| | **Verify 14-day advance booking** |
| Explain reasoning | Explain reasoning |
| Confirm | Confirm |

Same agent, same memory tools — but the *procedure* changes depending on context. This is exactly what procedural memory should do: adapt the approach based on the situation."""))

# ============================================================
# Cell 22: Procedures Orchestrate Memory
# ============================================================
cells.append(md("""\
### Procedures Orchestrate Memory

The V2 booking procedure is more than steps in a list — it orchestrates the agent's other memory systems:

- **"Check preferences"** → queries semantic memory
- **"Check history"** → recalls episodic memory
- **"Verify budget"** → applies policy data

The procedure acts as a conductor: it decides *which* memories to consult, in *what* order, and *what* to do with the results. With multiple task types, you need multiple conductors — each one coordinating memory differently. International trips need visa checks (episodic: has the traveler been to that country before?), domestic trips don't.

```
Procedural memory (the conductor)
    ├── "Check preferences" → semantic memory
    ├── "Check history"     → episodic memory
    ├── "Verify budget"     → policy knowledge
    └── "Check visa"        → episodic + ask user
```

This is why procedures matter: they're the glue that connects memory systems into coherent behavior."""))

# ============================================================
# Cell 23: Design Requirements
# ============================================================
cells.append(md("""\
### From One Procedure to Many — Design Requirements

Before reaching for any framework or pattern, ask: what properties should a procedural memory system have?

1. **Versionable** — Procedures improve over time. We need to see what changed (V1 → V2 → V3), why, and roll back if needed. Git gives us this for free — if procedures live in files.
2. **Human-in-the-loop** — Unlike episodic and semantic memory (which the agent updates via tools), procedural changes are high-stakes. A bad booking procedure affects every customer. Procedures should be reviewed by humans — in PRs, with diffs.
3. **Task-specific and on-demand** — Cramming every procedure into the system prompt wastes tokens and context. Most procedures won't apply to any given request. The agent should load only what it needs.
4. **Extensible without redeployment** — Adding a new procedure (say, `group-booking`) shouldn't require changing the agent's code or redeploying. Drop a folder, done.
5. **Bundles supporting data** — A booking procedure references budget limits by seniority level, visa checklists, insurance requirements. Procedures and their reference data should live together.

These requirements point toward a specific pattern: procedures as versioned files, discoverable by the agent, loaded on demand, with bundled resources. In the Agent Framework, this pattern is called **Skills** — and it's exactly what we'll use.

But remember: skills are the *delivery mechanism*. Procedural memory is the *concept* — the agent's learned ability to approach tasks correctly."""))

# ============================================================
# Cell 24: How Skills Deliver Procedural Memory
# ============================================================
cells.append(md("""\
### How Skills Deliver Procedural Memory

Here's how the pattern works mechanically:

- Each procedure lives in a **`SKILL.md` file** with YAML frontmatter (name, description, tags)
- Supporting data (budget JSON, visa checklists) lives alongside as **resources**
- **`SkillsProvider`** discovers these files, advertises one-line summaries to the agent, and exposes `load_skill()` / `read_skill_resource()` tools
- **Progressive disclosure**: advertise (~50 tokens per skill) → load (full procedure) → resources (supporting data)

In production, this means:

- A domain expert writes or edits a `SKILL.md` in a pull request → reviewed by the team → merged → agent picks it up on next run
- Git history = procedure evolution history = audit trail
- New procedure = new folder with `SKILL.md` → no code change, no redeployment
- The same pattern works for any domain: HR onboarding, IT support, compliance reviews

Now let's implement it."""))

# ============================================================
# Cell 25: Create skill files
# ============================================================
cells.append(code("""\
import shutil

# Create the skills directory structure
os.makedirs("skills/domestic-booking", exist_ok=True)
os.makedirs("skills/international-booking", exist_ok=True)

# ─── Domestic booking skill ───

DOMESTIC_SKILL = \"\"\"---
name: domestic-booking
description: "Step-by-step procedure for booking domestic (same-country) business travel. Use when employee requests a flight, hotel, or trip within their home country."
---

# Domestic Booking Procedure

Follow these steps when booking travel within the same country:

1. **Check preferences**: Query semantic memory for airline, hotel, and seat preferences
2. **Check history**: Recall past trips to the same city. If the user has been there before, reference their experience (hotel rating, what worked/didn't)
3. **Verify budget**: Use `read_skill_resource("domestic-booking", "budget-limits")` to get budget limits by employee level. Check the booking amount against the limit.
4. **Recommend options**: Use preferences and history to suggest specific flights/hotels
5. **Explain reasoning**: Tell the user WHY you're recommending each option
6. **Confirm**: Summarize the complete plan and get user approval before booking
\"\"\"

# ─── International booking skill ───

INTERNATIONAL_SKILL = \"\"\"---
name: international-booking
description: "Step-by-step procedure for booking international business travel. Use when employee requests travel to a different country. Includes visa, insurance, and advance booking requirements."
---

# International Booking Procedure

Follow these steps when booking travel to a different country:

1. **Check preferences**: Query semantic memory for airline, hotel, and seat preferences
2. **Check history**: Recall past international trips. Check for visa-related events or issues
3. **Verify budget**: Use `read_skill_resource("international-booking", "budget-limits")` to get budget limits. International trips often exceed domestic limits — flag and escalate if needed
4. **Travel insurance**: International trips REQUIRE travel insurance per company policy. Remind the user and include in the plan
5. **Advance booking**: International trips require 14-day advance booking per company policy. Check the requested dates and warn if too close
6. **Visa check**: Ask if the user has a valid visa for the destination country. Use `read_skill_resource("international-booking", "visa-checklist")` for requirements. Check episodic memory for past visits (which implies prior visa)
7. **Recommend options**: Prefer direct flights for international routes when within budget
8. **Explain reasoning**: Include policy requirements in your explanation
9. **Confirm**: Summarize the complete plan including insurance and visa status
\"\"\"

# ─── Shared resources ───

BUDGET_LIMITS = json.dumps({
    "by_level": {
        "Junior":   {"max_flight_cost": 500,   "max_hotel_per_night": 200,  "allowed_flight_class": ["economy"]},
        "Senior":   {"max_flight_cost": 800,   "max_hotel_per_night": 300,  "allowed_flight_class": ["economy", "economy_plus"]},
        "Director": {"max_flight_cost": 1500,  "max_hotel_per_night": 400,  "allowed_flight_class": ["economy", "economy_plus", "business"]},
        "VP":       {"max_flight_cost": 3000,  "max_hotel_per_night": 500,  "allowed_flight_class": ["economy", "economy_plus", "business"]},
        "C-Suite":  {"max_flight_cost": 10000, "max_hotel_per_night": 1000, "allowed_flight_class": ["economy", "economy_plus", "business", "first"]},
    },
    "general": {
        "max_trip_duration_days": 14,
        "requires_business_justification": True,
    },
}, indent=2)

VISA_CHECKLIST = \"\"\"# Visa Requirements Checklist

Before confirming any international booking:

1. **Ask the traveler** if they have a valid visa for the destination country
2. **Check episodic memory** — past trips to the same country imply prior visa (but check expiry)
3. **Visa processing time** — if a new visa is needed, factor in processing time before the trip
4. **Passport validity** — many countries require 6+ months remaining on passport
5. **Transit visas** — check if connecting flights transit through countries requiring a visa

If visa status is unclear, flag it as a blocker and do NOT confirm the booking.
\"\"\"

# Write skill files
Path("skills/domestic-booking/SKILL.md").write_text(DOMESTIC_SKILL, encoding="utf-8")
Path("skills/domestic-booking/budget-limits.json").write_text(BUDGET_LIMITS, encoding="utf-8")

Path("skills/international-booking/SKILL.md").write_text(INTERNATIONAL_SKILL, encoding="utf-8")
Path("skills/international-booking/budget-limits.json").write_text(BUDGET_LIMITS, encoding="utf-8")
Path("skills/international-booking/visa-checklist.md").write_text(VISA_CHECKLIST, encoding="utf-8")

print("Created skill files:")
for p in sorted(Path("skills").rglob("*")):
    if p.is_file():
        print(f"  {p}  ({len(p.read_text(encoding='utf-8').splitlines())} lines)")"""))

# ============================================================
# Cell 23: SkillsProvider + V3 instructions
# ============================================================
cells.append(code("""\
from agent_framework import SkillsProvider

# Create a SkillsProvider that discovers SKILL.md files automatically.
# This replaces our manual load_procedure() tool with the framework-native pattern.
procedures = SkillsProvider(skill_paths=["skills"])

# Show what was discovered
print("SkillsProvider discovered:\\n")
for skill in procedures._skills.values():
    desc = skill.description[:80] + "..." if len(skill.description) > 80 else skill.description
    print(f"  📋 {skill.name}: {desc}")
    if skill.resources:
        for rname in skill.resources:
            print(f"     └── resource: {rname}")
    print()

print("Tools exposed:")
for t in procedures._tools:
    print(f"  🔧 {t.name}")


# ─── V3: Instructions referencing SkillsProvider ───

V3_INSTRUCTIONS = \"\"\"You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.

## Episodic Memory — Past Events
You have access to the employee's episodic memory — their past trips and experiences.
When planning new trips:
1. Use recall_events to check if they've been to this destination before
2. Reference past experiences to make better recommendations
3. Use remember_event to store significant outcomes after bookings

## Semantic Memory — Facts & Preferences
You also have access to semantic memory — the user's facts, preferences, and relationships.

WHEN TO LEARN (call learn_about_user):
- User states a preference: "I prefer...", "I like...", "I always..."
- User shares a persistent fact: "I'm vegetarian", "I need wheelchair access"
- User corrects a previous preference: "Actually, I've switched to..."

WHEN TO QUERY (call query_user_knowledge):
- Before recommending flights or hotels → check known preferences first
- User asks about their own profile: "What do you know about me?"
- Making any personalized decision

WHEN TO SKIP:
- One-time situational info: "Book me a flight for Tuesday" (date, not a preference)
- Events that happened (use episodic memory for those, not semantic)
- Small talk, greetings, confirmations

WHEN FACTS CONFLICT:
- If the user explicitly corrects a preference, update immediately via learn_about_user
- If you detect a contradiction with stored knowledge, ASK the user before overwriting
- Newer explicit statements from the user override older ones

## Procedural Memory — Task Procedures
You have access to task-specific procedures via skills.

WHEN TO LOAD A PROCEDURE:
- User requests a booking → determine if domestic or international
- Call load_skill("domestic-booking") or load_skill("international-booking")
- Follow the loaded procedure step by step

FOR DETAILED DATA:
- Call read_skill_resource("domestic-booking", "budget-limits") for budget limits by level
- Call read_skill_resource("international-booking", "visa-checklist") for visa requirements

HOW TO CHOOSE:
- Same country (e.g. US to US) → domestic-booking
- Different country → international-booking
- If unsure, ask the user

ALWAYS follow the loaded procedure's checklist. Do not skip steps.

The current user is Sarah Chen (employee ID: E001, level: Senior, based in Seattle, USA).
Be concise and helpful.
\"\"\"

os.makedirs("prompts", exist_ok=True)
Path("prompts/v3.md").write_text(V3_INSTRUCTIONS, encoding="utf-8")
print(f"\\nCreated: prompts/v3.md")
print(f"Size: {len(V3_INSTRUCTIONS)} characters, {len(V3_INSTRUCTIONS.splitlines())} lines")"""))


# ============================================================
# Cell 24: Diff V2 → V3
# ============================================================
cells.append(code("""\
print("=== What changed: V2 → V3 ===\\n")
show_diff("prompts/v2.md", "prompts/v3.md")"""))

# ============================================================
# Cell 25: Demo V3 — international trip
# ============================================================
cells.append(code("""\
async def demo_v3():
    instructions = load_instructions("prompts/v3.md")
    print(f"Loaded instructions from: prompts/v3.md ({len(instructions)} chars)\\n")

    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=instructions,
        tools=[
            remember_event, recall_events,
            learn_about_user, query_user_knowledge,
        ],
        context_providers=[procedures],
    )
    turns = [
        "Hi, I'm Sarah Chen (E001). I need to book a trip to London next month for a client meeting.",
        "I've been to London before — you should have that in your records.",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")

print("=== V3: + Task-Specific Procedures via SkillsProvider ===\\n")
asyncio.run(demo_v3())"""))

# ============================================================
# Cell 29: V3 observation — merged reflection
# ============================================================
cells.append(md("""\
### Procedures Compose with Memory

Look at what the agent did with the `international-booking` skill:

1. **Loaded** the `international-booking` procedure via `load_skill` (procedural memory)
2. **Queried** Sarah's preferences (semantic memory)
3. **Recalled** her past London trip (episodic memory)
4. **Applied** policy rules: travel insurance, 14-day advance booking, visa check

The procedure told the agent *how* to use the other memory systems. That's the relationship:

```
Procedural memory (skills)
    ├── "Check preferences" → uses semantic memory
    ├── "Check history"     → uses episodic memory
    ├── "Verify insurance"  → applies policy knowledge (read_skill_resource)
    └── "Check visa"        → uses episodic + asks user
```

**Procedural memory orchestrates the other memory types.** It's the playbook that ties them together.

### Skills ≠ Procedural Memory

This is the distinction worth internalizing:

- **Procedural memory** is a *type of knowledge* — knowing how to do things. It's the agent's learned behavior for approaching tasks.
- **Skills** are a *delivery pattern* — a way to package and lazy-load domain knowledge on demand.

We chose skills because they satisfy the design requirements we identified: versionable (Git), human-in-the-loop (PRs), task-specific and on-demand (progressive disclosure), extensible (drop a folder), and bundle supporting data (resources). But skills can carry *any* knowledge type — reference data, API docs, policy rules. They aren't inherently procedural.

Procedural memory can be delivered many other ways too — we'll explore this more in the summary."""))

# ============================================================
# Cell 28: Part 5 heading — When to Stop Refining
# ============================================================
cells.append(md("""\
---
## Part 5: When to Stop Refining

The feedback loop is powerful:

```
V1 → "Agent doesn't check budget"      → add booking procedure     → V2
V2 → "Agent doesn't handle int'l rules" → add task procedures       → V3
V3 → "Agent doesn't ..."               → ???                       → V4
```

But without a stopping condition, this loop produces problems:"""))

# ============================================================
# Cell 29: Anti-patterns
# ============================================================
cells.append(md("""\
### The Four Anti-Patterns

**1. Over-fitting**

V7 instructions are so specific to Sarah's edge cases that they break for other employees:
```
"If the user is named Sarah and going to London and it's November,
 remind them about the fog..."
```

**2. Oscillation**

V5 fixes what V4 broke. V6 re-breaks what V5 fixed. Git log shows reverts:
```
git log --oneline prompts/
a1b2c3d v6: revert budget check — was too aggressive
d4e5f6g v5: add strict budget check
7h8i9j0 v4: relax budget check — too many false positives
```

**3. Diminishing returns**

Getting from 80% → 95% took two iterations. Getting from 95% → 97% took five. Each refinement handles rarer edge cases with diminishing impact.

**4. Instruction bloat**

V10 is three pages long. The model struggles with very long instructions — it starts ignoring sections or inconsistently following them. More instructions can actually mean *worse* behavior."""))

# ============================================================
# Cell 30: Stopping signals
# ============================================================
cells.append(md("""\
### Five Stopping Signals

| Signal | What to look for | When to stop |
|---|---|---|
| **1. Eval scores plateau** | Run the same test conversations, score results | Delta < meaningful threshold across iterations |
| **2. Git shows reverts** | `git log --oneline prompts/` | You're undoing previous changes |
| **3. Instruction length** | Count tokens | Prompt exceeds ~1500 tokens |
| **4. Edge case ratio** | Track what % of conversations each change addresses | >50% of changes address <5% of conversations |
| **5. The "3 iteration" rule** | V1 (baseline) → V2 (observed fixes) → V3 (polish) | Beyond V3, question if the problem is instructions vs tools |

### A Practical Default

Three iterations is a good default:
- **V1**: Baseline instructions — get something working
- **V2**: Fix observed weaknesses — the biggest behavioral gaps
- **V3**: Polish — edge cases and refinements

Beyond V3, the question changes from "What should the instructions say?" to "Do I need better tools, more context, or a different approach entirely?"

This doesn't mean V4 is always wrong — but it means V4 should require a strong justification, not just "let's try one more tweak.\""""))

# ============================================================
# Cell 31: Demo — git history
# ============================================================
cells.append(code("""\
# Show the evolution trail
print("=== Instruction Version History ===\\n")

versions = sorted(Path("prompts").glob("v*.md"))
for v in versions:
    content = v.read_text(encoding="utf-8")
    lines = content.splitlines()
    sections = [l.strip("# ").strip() for l in lines if l.startswith("## ")]
    print(f"  {v.name:8s}  {len(lines):3d} lines  {len(content):5d} chars  Sections: {', '.join(sections)}")

print()
print("Skills directory:")
for p in sorted(Path("skills").rglob("*")):
    if p.is_file():
        print(f"  {p}")

print()
print("If you've initialized git in this directory, you can run:")
print('  git add prompts/ skills/')
print('  git commit -m "procedural memory: v1 → v2 → v3 with SkillsProvider"')
print('  git log --oneline prompts/')
print()
print("The git history IS the procedural memory — it records how the agent learned.")"""))

# ============================================================
# Cell 32: Part 6 heading — Putting It All Together
# ============================================================
cells.append(md("""\
---
## Part 6: Putting It All Together

Our agent now has three memory systems plus task-specific procedures. Let's run a comprehensive demo that shows everything working together."""))

# ============================================================
# Cell 33: Full conversation demo
# ============================================================
cells.append(code("""\
async def demo_full():
    instructions = load_instructions("prompts/v3.md")

    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=instructions,
        tools=[
            remember_event, recall_events,
            learn_about_user, query_user_knowledge,
        ],
        context_providers=[procedures],
    )
    turns = [
        # Semantic: update a preference
        "I've switched from Delta to United — their international routes are better.",
        # Procedural + episodic + semantic: full booking
        "Plan a trip to London next month for a client meeting.",
        # Domestic trip for comparison
        "Also, I need a quick trip to NYC next week for a conference.",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")
        print("-" * 60 + "\\n")

print("=== Full Demo: All Memory Types + SkillsProvider ===\\n")
asyncio.run(demo_full())

# Show state
print("\\n--- Memory State After Demo ---")
print(f"\\nEpisodic events: {len(_episodic_store)}")
for e in _episodic_store[-3:]:
    print(f"  [{e['timestamp'][:10]}] {e['description'][:80]}")

print(f"\\nSemantic facts: {len(_knowledge_graph.all_facts('E001'))}")
for f in _knowledge_graph.all_facts("E001"):
    print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")

print(f"\\nSkills: {list(procedures._skills.keys())}")"""))

# ============================================================
# Cell 34: What just happened
# ============================================================
cells.append(md("""\
### What Just Happened

The agent used **all four memory systems** in one conversation:

| Action | Memory Type | Tool/File |
|---|---|---|
| "Switched to United" | **Semantic** — updated preference | `learn_about_user` |
| "Plan London trip" | **Procedural** — loaded int'l procedure | `load_skill` |
| Checked past London trip | **Episodic** — recalled history | `recall_events` |
| Applied travel insurance rule | **Procedural** — followed checklist | Skill resource |
| Checked budget limits | **Procedural** — queried budget data | `read_skill_resource` |
| Checked preferences before booking | **Semantic** — queried knowledge | `query_user_knowledge` |
| "Quick trip to NYC" | **Procedural** — loaded domestic procedure | `load_skill` |
| Referenced past NYC experience | **Episodic** — recalled conference trip | `recall_events` |

**Procedural memory orchestrates everything.** The skill files tell the agent which other memory systems to consult, in what order, and what to do with the results."""))

# ============================================================
# Cell 35: Summary
# ============================================================
cells.append(md("""\
---
## Summary

### Four Memory Types

| | Session (Module 1) | Episodic (Module 2) | Semantic (Module 3) | Procedural (Module 4) |
|---|---|---|---|---|
| **Stores** | Current conversation | Past events | Facts & preferences | Behaviors & procedures |
| **Answers** | "What did we just discuss?" | "What happened?" | "What is true?" | "How should I act?" |
| **Structure** | Message list | Event records | Knowledge graph | SKILL.md files |
| **Update pattern** | Automatic | `@tool` | `@tool` | Human refinement |
| **Version control** | N/A | Cosmos DB | Neo4j | SKILL.md files + git |
| **Key API** | `AgentSession` | `remember_event` | `learn_about_user` | `SkillsProvider` (`load_skill`, `read_skill_resource`) |

### Key Insights

1. **Instructions are memory.** The agent's behavior comes from its instructions — not from code. Treating them as versioned files makes them reviewable, diffable, and auditable.

2. **Procedures orchestrate other memories.** The booking procedure says "check preferences (semantic), check history (episodic), verify budget." It's the playbook that ties everything together.

3. **The feedback loop has a stopping condition.** Observe → refine → verify is powerful, but watch for over-fitting, oscillation, bloat, and diminishing returns. Three iterations is a good default.

4. **Task-specific procedures reduce complexity.** Instead of one giant instruction set, load the right playbook for the right task. International trips get visa checks; domestic trips don't.

5. **SkillsProvider is the delivery mechanism, not the memory.** Procedural memory is the concept (knowing *how* to do things). `SkillsProvider` is how the agent framework delivers it — lazy-loaded SKILL.md files with bundled resources. The same pattern can deliver any knowledge type.

### More Than One Way

`SkillsProvider` + git is one approach to delivering procedural memory — framework-native, with progressive disclosure and bundled resources. But procedural memory itself can be implemented many ways:

- **Skill libraries** (Voyager) — agent builds reusable executable procedures from successful tasks
- **Self-editing prompts** (MemGPT/Letta) — agent modifies its own instructions at runtime
- **Reflection-based learning** (Reflexion) — agent writes post-task observations that feed back into future context
- **Prompt optimization pipelines** — automated eval → optimizer → human review cycles

The same is true for episodic and semantic memory — each has multiple valid implementation strategies with different tradeoffs. We'll compare these approaches across all three memory types in a later module."""))

# ============================================================
# Cell 36: What's Next
# ============================================================
cells.append(md("""\
---
## What's Next

We've built four memory systems, but each module taught them **in isolation**. The agent in this module had all four memory types — but we set up each one from scratch.

In **Module 5: Combined Memory**, we'll bring all four memory systems together with shared infrastructure — a single agent configuration that leverages episodic, semantic, and procedural memory with persistent backends. No more rebuilding tools in each notebook."""))

# ============================================================
# Cell 37: Cleanup
# ============================================================
cells.append(code("""\
# Optional: Clean up files created by this module
# Uncomment and run to remove generated prompt and skill files

# import shutil
# if Path("prompts").exists():
#     shutil.rmtree("prompts")
#     print("Removed prompts/")
# if Path("skills").exists():
#     shutil.rmtree("skills")
#     print("Removed skills/")"""))

# ============================================================
# Build notebook JSON
# ============================================================
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.12.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

output_path = "04_procedural_memory.ipynb"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print(f"Built {output_path}: {len(cells)} cells")

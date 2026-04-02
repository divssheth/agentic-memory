"""Build Module 3: Semantic Memory notebook."""
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
%pip install -q neo4j -r ../../requirements.txt"""))

# ============================================================
# Cell 2: Title + What You'll Learn
# ============================================================
cells.append(md("""\
# Module 3: Semantic Memory

Module 2 gave us **episodic memory** — the ability to store and recall past events like trips, bookings, and feedback. That's powerful for answering *"What happened?"*

But not all knowledge is about events. **"Sarah prefers aisle seats"** isn't something that happened — it's a fact that's always true (until it changes). **"Sarah's manager is Michael Torres"** is a relationship, not an episode.

In this module we'll build a **semantic memory** system — a knowledge graph of facts, preferences, and relationships — and layer it on top of the episodic memory from Module 2.

## What You'll Learn
1. Why facts and preferences need a **different structure** than episodic events
2. How **knowledge graphs** represent facts as triplets: (Subject) → [Relationship] → (Object)
3. How to handle real-world messiness: **synonyms** and **contradictions**
4. How the LLM can **extract structured knowledge** from natural conversation
5. **When to trigger** semantic memory — the critical difference between an agent that *has* memory and one that *uses* it well
6. How to persist knowledge graphs with **Neo4j**

## The Journey
```
Session memory (Module 1)
    → Episodic memory for events (Module 2)
        → Semantic memory for facts (this module)
            → Both working together with clear trigger rules
```"""))

# ============================================================
# Cell 3: Setup heading
# ============================================================
cells.append(md("""\
---
## Setup

> **Prerequisites**:
> - Modules 1 and 2 completed
> - Azure AI Foundry project endpoint in your `.env` file
>
> **For Part 8 (persistence)**, you'll need:
> - **Neo4j**: Follow [`steps/01_setup_neo4j.md`](steps/01_setup_neo4j.md) — Docker or AuraDB (free tier)
>
> Parts 1–7 run entirely in-memory with just Azure AI Foundry — no graph database needed."""))

# ============================================================
# Cell 4: Imports + env vars
# ============================================================
cells.append(code("""\
import os
import json
import asyncio
import nest_asyncio
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv("../../.env", override=True)

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")

# Optional — only needed for Part 8
NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")
print(f"Project:  {PROJECT_ENDPOINT}")
print(f"Model:    {MODEL_DEPLOYMENT}")
print(f"Neo4j:    {'configured' if NEO4J_URI else 'not configured (optional)'}")"""))

# ============================================================
# Cell 5: Part 1 heading — Facts Are a Different Pattern
# ============================================================
cells.append(md("""\
---
## Part 1: Facts Are a Different Pattern

Module 2's episodic memory is excellent at capturing **events** — things that happened:
- "Sarah's NYC trip in October was rated 5 stars"
- "The London hotel was good but the flight was long"
- "Chicago conference — Palmer House Hilton, $1,850"

But what about knowledge like this?
- **"Sarah prefers aisle seats"** — a preference, not an event
- **"Sarah is vegetarian"** — a persistent fact
- **"Sarah's manager is Michael Torres"** — a relationship
- **"Sarah needs wheelchair access"** — a requirement

These aren't things that *happened*. They're things that *are true*. Episodic memory can store the event where Sarah mentioned her preference, but it can't answer "What seat does Sarah prefer?" without scanning through events looking for clues.

Let's see the problem concretely."""))

# ============================================================
# Cell 6: Demo — preferences as episodic events
# ============================================================
cells.append(code("""\
# Simulate: what if we stored preferences as episodic events?
preference_events = [
    {"event_type": "feedback", "description": "Sarah mentioned she likes United Airlines", "timestamp": "2025-01-15"},
    {"event_type": "trip", "description": "Booked Delta flight for Sarah to NYC", "timestamp": "2025-03-20"},
    {"event_type": "feedback", "description": "Sarah said she prefers aisle seats", "timestamp": "2025-04-02"},
    {"event_type": "feedback", "description": "Sarah mentioned she likes United for domestic", "timestamp": "2025-06-10"},
    {"event_type": "trip", "description": "Booked United flight for Sarah to London", "timestamp": "2025-07-15"},
    {"event_type": "feedback", "description": "Sarah switched to Delta — better loyalty program", "timestamp": "2025-09-01"},
]

# Now try to answer: "What airline does Sarah prefer?"
print("Question: What airline does Sarah prefer?\\n")
print("Searching episodic events for 'airline' or 'united' or 'delta'...\\n")

hits = []
for e in preference_events:
    desc = e["description"].lower()
    if any(kw in desc for kw in ["airline", "united", "delta", "prefer"]):
        hits.append(e)
        print(f"  [{e['timestamp']}] {e['description']}")

print(f"\\nFound {len(hits)} matching events.")
print("\\nWhich is current? 'likes United'? 'switched to Delta'?")
print("No structure, no timestamps on the FACT, just raw event descriptions.")
print("We'd have to read them all and reason about which is newest.")"""))

# ============================================================
# Cell 7: Transition — enter the knowledge graph
# ============================================================
cells.append(md("""\
### A Different Tool for a Different Job

Episodic memory stores **what happened** — and it does that well. But for **what is true right now**, we need a structure that:

1. **Captures the current state** — "Sarah prefers Delta" replaces "Sarah prefers United"
2. **Is directly queryable** — "What airline does Sarah prefer?" → one answer, immediately
3. **Has typed relationships** — preferences, requirements, and relationships are different kinds of facts

This is **semantic memory** — a knowledge graph of facts, preferences, and relationships. Not competing with episodic memory — complementing it."""))

# ============================================================
# Cell 8: Part 2 heading — Knowledge as a Graph
# ============================================================
cells.append(md("""\
---
## Part 2: Knowledge as a Graph

In cognitive psychology, **Endel Tulving (1972)** drew the distinction:
- **Episodic memory** = "What happened to me" (events, experiences)
- **Semantic memory** = "What I know to be true" (facts, concepts, relationships)

We represent semantic memory as a **knowledge graph** — a network of facts stored as **triplets**:

```
(Subject) ──[Relationship]──> (Object)
```

For example, Sarah's preferences form a graph:

```
                    ┌─────────┐
              ┌────>│  Delta  │
  ┌───────┐   │     └─────────┘
  │ Sarah │───┤ PREFERS
  │ (E001)│   │     ┌─────────┐
  └───┬───┘   └────>│ Marriott│
      │              └─────────┘
      │ PREFERS
      │         ┌─────────┐
      ├────────>│  aisle  │
      │         └─────────┘
      │ REQUIRES
      │         ┌────────────┐
      └────────>│ vegetarian │
                └────────────┘
```

Each arrow is a **triplet**: `(Sarah, PREFERS, Delta)`, `(Sarah, REQUIRES, vegetarian)`, etc."""))

# ============================================================
# Cell 9: InMemoryKnowledgeGraph
# ============================================================
cells.append(code("""\
class InMemoryKnowledgeGraph:
    \"\"\"A simple in-memory knowledge graph using triplets.\"\"\"

    def __init__(self):
        # {user_id: [{"subject": ..., "relationship": ..., "object": ..., "object_type": ...}, ...]}
        self.graph = {}

    def store_triplet(self, user_id, subject, relationship, obj, object_type=""):
        \"\"\"Store a fact as a triplet.\"\"\"
        if user_id not in self.graph:
            self.graph[user_id] = []

        triplet = {
            "subject": subject,
            "relationship": relationship,
            "object": obj,
            "object_type": object_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.graph[user_id].append(triplet)
        return triplet

    def query(self, user_id, relationship=None, object_type=None):
        \"\"\"Query facts by relationship type or object type.\"\"\"
        if user_id not in self.graph:
            return []
        results = self.graph[user_id]
        if relationship:
            results = [t for t in results if t["relationship"] == relationship]
        if object_type:
            results = [t for t in results if t["object_type"] == object_type]
        return results

    def all_facts(self, user_id):
        \"\"\"Get all facts for a user.\"\"\"
        return self.graph.get(user_id, [])

print("InMemoryKnowledgeGraph defined ✓")"""))

# ============================================================
# Cell 10: Demo — store and query triplets
# ============================================================
cells.append(code("""\
graph = InMemoryKnowledgeGraph()

# Store Sarah's preferences as structured triplets
graph.store_triplet("E001", "Sarah Chen", "PREFERS", "Delta", "AIRLINE")
graph.store_triplet("E001", "Sarah Chen", "PREFERS", "aisle", "SEAT_TYPE")
graph.store_triplet("E001", "Sarah Chen", "PREFERS", "Marriott", "HOTEL")
graph.store_triplet("E001", "Sarah Chen", "REQUIRES", "vegetarian", "DIETARY")
graph.store_triplet("E001", "Sarah Chen", "WORKS_AT", "Engineering", "DEPARTMENT")

# Query: What airline does Sarah prefer?
print("Query: PREFERS + AIRLINE")
for t in graph.query("E001", relationship="PREFERS", object_type="AIRLINE"):
    print(f"  ({t['subject']}) --[{t['relationship']}]--> {t['object']}")

# Query: What does Sarah require?
print("\\nQuery: REQUIRES")
for t in graph.query("E001", relationship="REQUIRES"):
    print(f"  ({t['subject']}) --[{t['relationship']}]--> {t['object']} ({t['object_type']})")

# Query: All facts
print(f"\\nTotal facts for Sarah: {len(graph.all_facts('E001'))}")"""))

# ============================================================
# Cell 11: Graph works, but problems
# ============================================================
cells.append(md("""\
### Structured and Queryable

Unlike searching through episodic events, the knowledge graph gives us:
- **Direct answers**: "What airline?" → one query, one result
- **Typed relationships**: PREFERS vs REQUIRES vs WORKS_AT
- **Typed objects**: AIRLINE vs SEAT_TYPE vs DIETARY

But two problems remain:

1. **Synonyms**: If one conversation says "likes United" and another says "prefers United" — are those the same relationship? We'd get duplicates.
2. **Facts change**: Sarah "prefers United" in January, then "switched to Delta" in September. The graph now has *both* — which is current?"""))

# ============================================================
# Cell 12: Part 3 heading — Canonicalization + Contradictions
# ============================================================
cells.append(md("""\
---
## Part 3: Taming the Real World

Two challenges with real-world knowledge:

### Challenge 1: Synonyms
Natural language has many ways to say the same thing:
- "I **like** United" / "I **prefer** United" / "I **always fly** United" → all mean PREFERS
- "I **hate** window seats" / "I **don't want** window seats" / "**never** window" → all mean DISLIKES

Without normalization, each phrasing creates a separate relationship. The solution: an **ontology** that maps synonyms to canonical forms.

### Challenge 2: Facts Change
- January: "I prefer United" → `(Sarah, PREFERS, United/AIRLINE)`
- September: "I switched to Delta" → `(Sarah, PREFERS, Delta/AIRLINE)`

Both can't be true simultaneously. The solution: **conflict detection** — when a new fact contradicts an existing one for the same relationship + object type, replace the old one. We call this **"newer wins"**."""))

# ============================================================
# Cell 13: OntologyManager + conflict handling
# ============================================================
cells.append(code("""\
class OntologyManager:
    \"\"\"Maps natural language to canonical relationship and entity types.\"\"\"

    RELATIONSHIP_MAP = {
        # → PREFERS
        "prefers": "PREFERS", "likes": "PREFERS", "prefer": "PREFERS",
        "loves": "PREFERS", "always": "PREFERS", "favorite": "PREFERS",
        # → DISLIKES
        "dislikes": "DISLIKES", "hates": "DISLIKES", "avoids": "DISLIKES",
        "never": "DISLIKES", "dont_like": "DISLIKES",
        # → REQUIRES
        "requires": "REQUIRES", "needs": "REQUIRES", "must_have": "REQUIRES",
        # → WORKS_AT
        "works_at": "WORKS_AT", "employed_at": "WORKS_AT",
        # → MEMBER_OF
        "member_of": "MEMBER_OF", "belongs_to": "MEMBER_OF",
    }

    ENTITY_TYPE_MAP = {
        "airline": "AIRLINE", "carrier": "AIRLINE", "flight_carrier": "AIRLINE",
        "hotel": "HOTEL", "hotel_chain": "HOTEL", "accommodation": "HOTEL",
        "seat": "SEAT_TYPE", "seat_type": "SEAT_TYPE", "seating": "SEAT_TYPE",
        "dietary": "DIETARY", "diet": "DIETARY", "food": "DIETARY",
        "department": "DEPARTMENT", "team": "DEPARTMENT",
        "accessibility": "ACCESSIBILITY", "accommodation_need": "ACCESSIBILITY",
    }

    def canonicalize_relationship(self, raw):
        \"\"\"Map a raw relationship string to its canonical form.\"\"\"
        key = raw.lower().strip().replace(" ", "_")
        return self.RELATIONSHIP_MAP.get(key, raw.upper())

    def canonicalize_entity_type(self, raw):
        \"\"\"Map a raw entity type string to its canonical form.\"\"\"
        key = raw.lower().strip().replace(" ", "_")
        return self.ENTITY_TYPE_MAP.get(key, raw.upper())


class SmartKnowledgeGraph(InMemoryKnowledgeGraph):
    \"\"\"Knowledge graph with canonicalization and conflict handling.\"\"\"

    def __init__(self):
        super().__init__()
        self.ontology = OntologyManager()

    def store_triplet(self, user_id, subject, relationship, obj, object_type=""):
        \"\"\"Store with canonicalization and conflict detection.\"\"\"
        rel = self.ontology.canonicalize_relationship(relationship)
        otype = self.ontology.canonicalize_entity_type(object_type) if object_type else ""

        # Conflict detection: same relationship + object_type → replace
        if user_id in self.graph and otype:
            self.graph[user_id] = [
                t for t in self.graph[user_id]
                if not (t["relationship"] == rel and t["object_type"] == otype)
            ]

        return super().store_triplet(user_id, subject, rel, obj, otype)

print("OntologyManager + SmartKnowledgeGraph defined ✓")"""))

# ============================================================
# Cell 14: Demo — canonicalization + contradiction
# ============================================================
cells.append(code("""\
smart_graph = SmartKnowledgeGraph()

# Synonyms → same canonical form
print("=== Canonicalization ===")
smart_graph.store_triplet("E001", "Sarah", "likes", "United", "airline")
print(f"  'likes' + 'airline' → ", end="")
t = smart_graph.query("E001", relationship="PREFERS", object_type="AIRLINE")[0]
print(f"({t['subject']}, {t['relationship']}, {t['object']}/{t['object_type']})")

smart_graph.store_triplet("E001", "Sarah", "prefers", "aisle", "seat")
print(f"  'prefers' + 'seat' → ", end="")
t = smart_graph.query("E001", relationship="PREFERS", object_type="SEAT_TYPE")[0]
print(f"({t['subject']}, {t['relationship']}, {t['object']}/{t['object_type']})")

smart_graph.store_triplet("E001", "Sarah", "needs", "vegetarian", "dietary")
print(f"  'needs' + 'dietary' → ", end="")
t = smart_graph.query("E001", relationship="REQUIRES", object_type="DIETARY")[0]
print(f"({t['subject']}, {t['relationship']}, {t['object']}/{t['object_type']})")

# Contradiction → newer wins
print("\\n=== Contradiction Handling ===")
airline_before = smart_graph.query("E001", relationship="PREFERS", object_type="AIRLINE")
print(f"  Before: Sarah PREFERS {airline_before[0]['object']}")

smart_graph.store_triplet("E001", "Sarah", "prefers", "Delta", "airline")
airline_after = smart_graph.query("E001", relationship="PREFERS", object_type="AIRLINE")
print(f"  After:  Sarah PREFERS {airline_after[0]['object']}")
print(f"  Total PREFERS/AIRLINE facts: {len(airline_after)} (old one replaced)")

print(f"\\nAll facts for Sarah: {len(smart_graph.all_facts('E001'))}")"""))

# ============================================================
# Cell 15: Transition to LLM extraction
# ============================================================
cells.append(md("""\
### The Graph Handles Real-World Messiness

- **"likes"** and **"prefers"** both map to `PREFERS`
- **"needs"** maps to `REQUIRES`
- When Sarah "switched to Delta", the old `PREFERS/AIRLINE` was replaced — no duplicates

But so far we've been creating triplets manually. In a real conversation, the user says *"I'm vegetarian and I always fly United"* — who turns that into structured triplets?

The answer: the LLM itself."""))

# ============================================================
# Cell 16: Part 4 heading — LLM-Driven Extraction
# ============================================================
cells.append(md("""\
---
## Part 4: LLM-Driven Extraction

Instead of writing parsing rules for every possible phrase, we give the LLM a natural language statement and ask it to extract structured triplets.

```
Input:  "I prefer Delta and need wheelchair assistance"

Output: [
    {"relationship": "prefers", "object": "Delta", "object_type": "airline"},
    {"relationship": "requires", "object": "wheelchair assistance", "object_type": "accessibility"}
]
```

The LLM understands semantics — it knows "need wheelchair assistance" is a requirement, not a preference. Our `OntologyManager` then canonicalizes the output."""))

# ============================================================
# Cell 17: extract_knowledge_triplets
# ============================================================
cells.append(code("""\
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

TENANT_ID = os.environ.get("AZURE_TENANT_ID", "16b3c013-d300-468d-ac64-7eda0820b6d3")
credential = AzureCliCredential()

EXTRACTION_PROMPT = \"\"\"Extract knowledge triplets from the user's statement.
Return a JSON array of objects with these fields:
- "relationship": how the subject relates to the object (e.g. "prefers", "requires", "dislikes", "works_at")
- "object": the entity (e.g. "Delta", "aisle", "vegetarian")
- "object_type": category (e.g. "airline", "hotel", "seat_type", "dietary", "accessibility", "department")

Rules:
- Only extract PERSISTENT facts (preferences, requirements, relationships) — not one-time plans
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
    \"\"\"Use the LLM to extract structured triplets from natural language.\"\"\"
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

    # Handle markdown code blocks
    if text.startswith("```"):
        text = text.split("\\n", 1)[1] if "\\n" in text else text[3:]
        text = text.rsplit("```", 1)[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"Warning: Could not parse LLM response: {text[:100]}")
        return []

print("extract_knowledge_triplets() defined ✓")"""))

# ============================================================
# Cell 18: Demo — LLM extraction
# ============================================================
cells.append(code("""\
async def demo_extraction():
    statements = [
        "I prefer Delta and I always want an aisle seat.",
        "I'm vegetarian and need wheelchair assistance when traveling.",
        "Book me a flight to NYC for next Tuesday.",  # Should extract nothing
        "I've switched from Marriott to Hilton — better loyalty rewards.",
    ]

    for statement in statements:
        print(f"Input:  \\"{statement}\\"")
        triplets = await extract_knowledge_triplets(statement)
        if triplets:
            for t in triplets:
                print(f"  → ({t['relationship']}, {t['object']}, {t['object_type']})")
        else:
            print("  → (no persistent facts detected)")
        print()

asyncio.run(demo_extraction())"""))

# ============================================================
# Cell 19: Part 5 heading — Agent with Instructions V1
# ============================================================
cells.append(md("""\
---
## Part 5: Wiring It Up — The Agent Gets Semantic Memory

We're using the same `@tool` pattern from Module 2. Two new tools:
- **`learn_about_user`** — extract triplets from a statement and store them in the graph
- **`query_user_knowledge`** — query the graph for personalization

But the agent **keeps its episodic tools** from Module 2 — `remember_event` and `recall_events`. It now has **four tools total**: two for events, two for facts.

Here's the question: in Module 2 we gave the agent clear instructions about *when* to use episodic memory. What happens if we add semantic tools **without** similar guidance? Let's find out."""))

# ============================================================
# Cell 20: Define all four tools (episodic + semantic)
# ============================================================
cells.append(code("""\
from agent_framework import tool

# ─── Episodic memory (in-memory for this module) ─── 

_episodic_store = []  # Simple list of events

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


# ─── Semantic memory ───

_knowledge_graph = SmartKnowledgeGraph()

@tool
async def learn_about_user(user_id: str, statement: str) -> str:
    \"\"\"Extract and store facts/preferences from a user's statement in semantic memory.

    Call this to store persistent knowledge about the user — preferences,
    requirements, relationships. The statement will be analyzed by the LLM
    to extract structured triplets.

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
        result = _knowledge_graph.store_triplet(
            user_id,
            user_id,  # subject
            t["relationship"],
            t["object"],
            t.get("object_type", ""),
        )
        if asyncio.iscoroutine(result):
            await result
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

    Call this to retrieve what you know about a user — their preferences,
    requirements, and relationships.

    Args:
        user_id: Employee ID (e.g. "E001")
        relationship: Optional filter — "PREFERS", "REQUIRES", "DISLIKES"
        entity_type: Optional filter — "AIRLINE", "HOTEL", "SEAT_TYPE", "DIETARY"
    \"\"\"
    ontology = OntologyManager()
    rel = ontology.canonicalize_relationship(relationship) if relationship else None
    etype = ontology.canonicalize_entity_type(entity_type) if entity_type else None

    facts = _knowledge_graph.query(user_id, relationship=rel, object_type=etype)
    if asyncio.iscoroutine(facts):
        facts = await facts

    if not facts:
        return "No matching facts found."

    lines = []
    for f in facts:
        lines.append(f"({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")
    return "\\n".join(lines)

print("All four tools defined:")
print("  Episodic:  remember_event, recall_events")
print("  Semantic:  learn_about_user, query_user_knowledge")"""))

# ============================================================
# Cell 21: Instructions V1 + demo
# ============================================================
cells.append(code("""\
# Preload some episodic events so the agent has trip history
_episodic_store.clear()
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

# V1: Episodic instructions (from Module 2) + bare semantic mention
INSTRUCTIONS_V1 = \"\"\"You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.

## Episodic Memory — Past Events
You have access to the employee's episodic memory — their past trips and experiences.
When planning new trips:
1. Use recall_events to check if they've been to this destination before
2. Reference past experiences to make better recommendations
3. Use remember_event to store significant outcomes after bookings

## Semantic Memory
You also have semantic memory tools for storing and querying user facts and preferences.

The current user is Sarah Chen (employee ID: E001, based in Seattle, USA).
Be concise and helpful.\"\"\"

async def demo_v1():
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=INSTRUCTIONS_V1,
        tools=[remember_event, recall_events, learn_about_user, query_user_knowledge],
    )
    turns = [
        "Hi! I always fly Delta and prefer aisle seats.",
        "I'm also vegetarian, just so you know.",
        "Can you help me plan a trip to New York next month?",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")

print("=== Instructions V1: Episodic guidance + bare semantic mention ===\\n")
asyncio.run(demo_v1())

# Check what got stored
print("\\n--- What the agent stored ---")
print(f"Episodic events: {len(_episodic_store)}")
print(f"Semantic facts:  {len(_knowledge_graph.all_facts('E001'))}")
for f in _knowledge_graph.all_facts("E001"):
    print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")"""))

# ============================================================
# Cell 22: V1 observation
# ============================================================
cells.append(md("""\
### What Happened with V1?

The agent had both tool sets, but notice the contrast:

- **Episodic memory** has clear trigger guidance from Module 2: *"check if they've been to this destination before"*, *"store significant outcomes"*. The agent uses it reliably.
- **Semantic memory** got only *"you have tools for storing and querying facts"*. No guidance on **when**. The agent may or may not have stored Sarah's preferences. It may or may not have queried preferences before recommending flights.

The tools are only as good as the instructions that govern them. Giving an agent a tool without trigger conditions is like giving someone a hammer and saying "you have this" — without saying when to use it.

**The fix: explicit trigger conditions.**"""))

# ============================================================
# Cell 23: Part 6 heading — Instructions V2
# ============================================================
cells.append(md("""\
---
## Part 6: When to Trigger — The Missing Piece

Each memory type needs its own **trigger conditions** — rules that tell the agent:
- **When to LEARN** — store a new fact
- **When to QUERY** — check what it already knows
- **When to SKIP** — this isn't semantic memory territory

| Action | When | Example |
|--------|------|---------|
| **LEARN** | User states a preference, fact, or correction | "I prefer Delta", "I'm vegetarian", "I switched to Hilton" |
| **QUERY** | Before recommending anything, or user asks about their profile | "Plan my NYC trip", "What do you know about me?" |
| **SKIP** | One-time info, events, small talk | "Book Tuesday flight", "My NYC trip was great", "Thanks!" |

Notice how this parallels Module 2's episodic triggers — same principle, different knowledge type. Events go to episodic memory. Facts go to semantic memory. One-time requests go to neither."""))

# ============================================================
# Cell 24: Instructions V2 + same demo
# ============================================================
cells.append(code("""\
# Reset semantic memory so we can compare fairly
_knowledge_graph.graph.clear()

# Reset episodic to just the preloaded trips
_episodic_store.clear()
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

INSTRUCTIONS_V2 = \"\"\"You are a corporate travel assistant for Contoso Corp.
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

The current user is Sarah Chen (employee ID: E001, based in Seattle, USA).
Be concise and helpful.\"\"\"

async def demo_v2():
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=INSTRUCTIONS_V2,
        tools=[remember_event, recall_events, learn_about_user, query_user_knowledge],
    )
    # Same conversation as V1
    turns = [
        "Hi! I always fly Delta and prefer aisle seats.",
        "I'm also vegetarian, just so you know.",
        "Can you help me plan a trip to New York next month?",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")

print("=== Instructions V2: Episodic + semantic trigger conditions ===\\n")
asyncio.run(demo_v2())

# Check what got stored
print("\\n--- What the agent stored ---")
print(f"Episodic events: {len(_episodic_store)}")
print(f"Semantic facts:  {len(_knowledge_graph.all_facts('E001'))}")
for f in _knowledge_graph.all_facts("E001"):
    print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")"""))

# ============================================================
# Cell 25: V2 observation
# ============================================================
cells.append(md("""\
### Same Tools, Better Instructions

Compare V1 and V2 — the agent now:

1. **LEARNs** when Sarah says "I always fly Delta" and "I'm vegetarian" — because the instructions say *"User states a preference → call learn_about_user"*
2. **QUERYs** before recommending a NYC trip — because the instructions say *"Before recommending → check known preferences first"*
3. **SKIPs** storing "help me plan a trip" — because the instructions say *"One-time info → skip"*

The pattern: **each memory type needs its own trigger conditions**. The agent needs to know not just *how* to remember, but *what* to remember *where*:
- "I prefer Delta" → semantic memory (a fact)
- "My NYC trip was amazing" → episodic memory (an event)
- "Book me a Tuesday flight" → neither (a request)"""))

# ============================================================
# Cell 26: Part 7 — Instructions V3 + contradiction demo
# ============================================================
cells.append(code("""\
INSTRUCTIONS_V3 = \"\"\"You are a corporate travel assistant for Contoso Corp.
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
Be concise and helpful.\"\"\"

async def demo_v3_contradiction():
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        ),
        name="TravelAssistant",
        instructions=INSTRUCTIONS_V3,
        tools=[remember_event, recall_events, learn_about_user, query_user_knowledge],
    )
    turns = [
        "What airline do you have on file for me?",
        "Actually, I've switched from Delta to United — better international routes.",
        "What are my current preferences?",
    ]
    for user_msg in turns:
        print(f"User: {user_msg}")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}\\n")

print("=== Instructions V3: + contradiction handling ===\\n")
asyncio.run(demo_v3_contradiction())

# Show the graph state
print("--- Semantic memory state ---")
for f in _knowledge_graph.all_facts("E001"):
    print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")"""))

# ============================================================
# Cell 27: V3 recap + progression visual
# ============================================================
cells.append(md("""\
---
## Part 7: The Instructions Progression

Three versions of instructions, same tools, increasingly better behavior:

```
V1: Tools only                V2: + Trigger conditions       V3: + Contradiction rules
─────────────────             ────────────────────────        ──────────────────────────
"You have semantic            WHEN TO LEARN:                  WHEN FACTS CONFLICT:
 memory tools."               - preferences stated            - explicit correction → update
                               - persistent facts              - detected conflict → ask
                               - corrections                   - newer wins
Agent behavior:
                              WHEN TO QUERY:
 ❌ Inconsistent               - before recommending           ✅ Handles preference changes
 ❌ Misses cues                - profile questions              ✅ Asks when unsure
 ❌ Stores noise               - personalized decisions         ✅ Keeps graph clean
                              
                              WHEN TO SKIP:
                               - one-time info
                               - events (→ episodic)
                               - small talk

                               ✅ Consistent behavior
                               ✅ Right memory, right time
```

### Key Insight

**Memory tools are half the solution. Instructions are the other half.**

The tools give the agent *capability*. The instructions give it *judgment*. As you add more memory types, the instructions grow — each section governs when and how to use that particular memory system.

By the end of this curriculum, the agent's instructions will be a complete playbook covering every memory type."""))

# ============================================================
# Cell 28: Part 8 heading — Going Persistent
# ============================================================
cells.append(md("""\
---
## Part 8: Going Persistent

So far, our knowledge graph lives in Python dictionaries — transient, just like the session memory problem from Module 1. For production, we need a **persistent graph database**.

**Neo4j** is a purpose-built graph database that stores nodes and edges natively — perfect for knowledge graphs:

| Feature | Details |
|---|---|
| **Query language** | Cypher |
| **Hosting** | AuraDB (cloud) or Docker (local) |
| **Free tier** | AuraDB Free (50K nodes) |
| **Strengths** | Purpose-built for graphs, rich multi-hop traversals |

> **Note**: This section requires Neo4j configured in your `.env`. If not configured, the demo falls back to the in-memory graph."""))

# ============================================================
# Cell 29: Neo4jKnowledgeGraph
# ============================================================
cells.append(code("""\
class Neo4jKnowledgeGraph:
    \"\"\"Knowledge graph backed by Neo4j. Same interface as InMemoryKnowledgeGraph.\"\"\"

    def __init__(self, driver):
        self.driver = driver
        self.ontology = OntologyManager()

    async def store_triplet(self, user_id, subject, relationship, obj, object_type=""):
        rel = self.ontology.canonicalize_relationship(relationship)
        otype = self.ontology.canonicalize_entity_type(object_type) if object_type else ""

        async with self.driver.session() as session:
            # Remove conflicting facts (same relationship + object_type)
            if otype:
                await session.run(
                    f\"\"\"MATCH (u:User {{id: $uid}})-[r:{rel}]->(e)
                    WHERE e.entity_type = $otype
                    DELETE r\"\"\",
                    uid=user_id, otype=otype,
                )

            # Create or merge the new fact
            await session.run(
                f\"\"\"MERGE (u:User {{id: $uid}})
                MERGE (e:Entity {{canonical: $obj_lower, entity_type: $otype}})
                SET e.raw = $obj
                MERGE (u)-[r:{rel}]->(e)
                SET r.timestamp = datetime()\"\"\",
                uid=user_id, obj=obj, obj_lower=obj.lower(), otype=otype,
            )

        return {"subject": user_id, "relationship": rel, "object": obj, "object_type": otype}

    async def query(self, user_id, relationship=None, object_type=None):
        query_parts = ["MATCH (u:User {id: $uid})-[r]->(e)"]
        params = {"uid": user_id}

        if relationship:
            rel = self.ontology.canonicalize_relationship(relationship)
            query_parts = [f"MATCH (u:User {{id: $uid}})-[r:{rel}]->(e)"]
        if object_type:
            otype = self.ontology.canonicalize_entity_type(object_type)
            query_parts.append("WHERE e.entity_type = $otype")
            params["otype"] = otype

        query_parts.append("RETURN type(r) AS relationship, e.raw AS object, e.entity_type AS object_type")

        async with self.driver.session() as session:
            result = await session.run("\\n".join(query_parts), **params)
            records = [record.data() async for record in result]

        return [
            {"subject": user_id, "relationship": r["relationship"],
             "object": r["object"], "object_type": r["object_type"]}
            for r in records
        ]

    async def all_facts(self, user_id):
        return await self.query(user_id)

print("Neo4jKnowledgeGraph defined ✓")"""))

# ============================================================
# Cell 30: Persistent demo — auto-detect backend
# ============================================================
cells.append(code("""\
async def demo_persistent():
    \"\"\"Run the agent with a persistent graph backend (if configured).\"\"\"
    graph = None
    backend = "in-memory"

    if NEO4J_URI and NEO4J_PASSWORD:
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        graph = Neo4jKnowledgeGraph(driver)
        backend = "Neo4j"
    else:
        graph = SmartKnowledgeGraph()
        print("No graph DB configured — using in-memory fallback.\\n")

    print(f"Backend: {backend}\\n")

    # Swap the global graph used by tools
    global _knowledge_graph
    old_graph = _knowledge_graph
    _knowledge_graph = graph

    try:
        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=INSTRUCTIONS_V3,
            tools=[remember_event, recall_events, learn_about_user, query_user_knowledge],
        )
        turns = [
            "Hi, I'm Sarah Chen (E001). I prefer United and always want aisle seats.",
            "I'm vegetarian. Can you check what you know about me?",
        ]
        for user_msg in turns:
            print(f"User: {user_msg}")
            response = await agent.run(user_msg)
            print(f"Agent: {response.text}\\n")

        # Show stored facts
        if hasattr(graph, "all_facts"):
            if asyncio.iscoroutinefunction(getattr(graph, "all_facts", None)):
                facts = await graph.all_facts("E001")
            else:
                facts = graph.all_facts("E001")
            print(f"\\n--- Facts in {backend} ---")
            for f in facts:
                print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")

    finally:
        _knowledge_graph = old_graph
        if backend == "Neo4j":
            await driver.close()

asyncio.run(demo_persistent())"""))

# ============================================================
# Cell 32: Comparison table
# ============================================================
cells.append(md("""\
### Choosing a Persistent Backend

| Feature | **Neo4j** | **In-Memory** |
|---------|-----------|---------------|
| **Query language** | Cypher | Python dicts |
| **Graph traversals** | Excellent — multi-hop native | Manual |
| **Hosting** | AuraDB (cloud) / Docker (local) | N/A |
| **Free tier** | AuraDB Free (50K nodes) | Always free |
| **Best for** | Complex graph queries, production | Prototyping |
| **Data persistence** | ✅ | ❌ |

Neo4j and the in-memory graph use the same **interface** — `store_triplet()`, `query()`, `all_facts()`. The agent doesn't know or care which backend is behind it. That's the power of a clean abstraction."""))

# ============================================================
# Cell 33: Summary
# ============================================================
cells.append(md("""\
---
## Summary

### Three Memory Types (So Far)

| | Session (Module 1) | Episodic (Module 2) | Semantic (Module 3) |
|---|---|---|---|
| **Stores** | Current conversation | Past events & experiences | Facts, preferences, relationships |
| **Answers** | "What did we just discuss?" | "What happened last time?" | "What does the user prefer?" |
| **Structure** | Message list | Event records | Knowledge graph (triplets) |
| **Update pattern** | Automatic each turn | `@tool` — agent decides | `@tool` — agent decides |
| **Persistence** | In-memory by default | Cosmos DB | Neo4j |
| **Key API** | `AgentSession` | `remember_event` / `recall_events` | `learn_about_user` / `query_user_knowledge` |

### Key Insights

1. **Facts ≠ events.** Episodic memory stores what *happened*. Semantic memory stores what *is true*. They complement each other.

2. **Canonicalization tames the real world.** "likes", "prefers", "always flies" all map to `PREFERS`. Without normalization, you get duplicates.

3. **Trigger conditions are as important as the tools.** V1 → V2 was the same four tools with better instructions. The behavior difference was dramatic.

4. **Instructions evolve as capabilities grow.** Each memory type adds a section to the agent's playbook. By the end of this curriculum, the instructions are a comprehensive guide governing all memory systems."""))

# ============================================================
# Cell 34: What's Next
# ============================================================
cells.append(md("""\
---
## What's Next

Semantic memory stores facts about the **user** — their preferences, requirements, and relationships.

But what about facts about the **organization**?

- "Senior Engineers can spend up to $800 on flights" — a policy, not a preference
- "International trips require travel insurance" — a rule, not a relationship
- "Trips over $2,000 need manager approval" — a procedure, not a fact

In **Module 4: Procedural Memory**, we'll add a memory system for learned behaviors — rules and procedures that the agent improves through practice and feedback, much like muscle memory in humans."""))

# ============================================================
# Cell 35: Cleanup
# ============================================================
cells.append(code("""\
# Optional: Clean up data created in this module
# Uncomment the relevant section and run

# --- Clear in-memory state ---
# _episodic_store.clear()
# _knowledge_graph.graph.clear()
# print("In-memory state cleared")

# --- Clear Neo4j ---
# from neo4j import AsyncGraphDatabase
# async def cleanup_neo4j():
#     driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
#     async with driver.session() as session:
#         await session.run("MATCH (n) DETACH DELETE n")
#     await driver.close()
#     print("Neo4j cleared")
# asyncio.run(cleanup_neo4j())

"""))

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

output_path = "03_semantic_memory.ipynb"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print(f"Built {output_path}: {len(cells)} cells")

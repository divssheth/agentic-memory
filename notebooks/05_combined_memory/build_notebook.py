"""Build Module 5: Combined Memory notebook."""
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
# Cell 1: Install required packages
# ============================================================
cells.append(code("""\
# Install required packages (run once)
%pip install -q -r ../../requirements.txt"""))

# ============================================================
# Cell 2: Module intro
# ============================================================
cells.append(md("""\
# Module 5: When Memories Disagree

Modules 2–4 built three memory systems and Module 4 brought them together in a single agent. The routing worked — the agent knew *which* memory to consult for each query. But we carefully avoided a harder question:

**What happens when the memories give contradictory answers?**

- Semantic memory says the user prefers business class. The booking procedure says economy only. **Which wins?**
- Trip history shows the user loved Marriott (5/5). The user says "try Hilton this time." **Which takes priority?**
- These contradictions don't exist when memories operate in isolation. They're an **emergent property** of combining memory types.

This module focuses on **conflict resolution** — the design decisions that determine how an agent arbitrates between disagreeing memories.

## What You'll Learn
1. **Why conflicts are emergent** — contradictions only appear when memory types interact, never in isolation
2. **Priority hierarchies** — why "policy > preference > history" is a domain decision, not a universal truth
3. **Detection vs. resolution** — the agent must first *recognize* a conflict before it can resolve one
4. **Persistence architecture** — two-tier persistence (automatic via context_providers, explicit via batch save) combining the backends from Modules 2–4

## The Journey
```
Session memory (Module 1)
    → Episodic memory for events (Module 2)
        → Semantic memory for facts (Module 3)
            → Procedural memory for behaviors (Module 4)
                → Conflict resolution across memories (this module)
```"""))

# ============================================================
# Cell 3: Setup prerequisites
# ============================================================
cells.append(md("""\
---
## Setup

> **Prerequisites** (all required — no in-memory fallbacks):
> - Modules 1–4 completed
> - Azure AI Foundry project endpoint in your `.env` file
> - **Azure Cosmos DB** with database `travel-memory` and containers `episodic-memory` + `chat-history` (Module 2 setup)
> - **Neo4j** instance with credentials (Module 3 setup)
>
> By Module 5, we've introduced the concepts and the technology. Every demo here runs against real backends — Cosmos DB for episodic events and chat history, Neo4j for semantic facts, and the filesystem for skills. If either backend is missing, the notebook will fail immediately rather than silently falling back to in-memory stores."""))

# ============================================================
# Cell 4: Configuration + Cosmos client
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

# ─── Hard requirements — no fallbacks ───
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
TENANT_ID = os.environ.get("AZURE_TENANT_ID", "16b3c013-d300-468d-ac64-7eda0820b6d3")
COSMOS_ENDPOINT = os.environ["COSMOS_ENDPOINT"]
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")

# ─── Shared Cosmos client (episodic + chat history) ───
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.cosmos import CosmosClient
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient

cosmos_credential = DefaultAzureCredential()
cosmos_client = CosmosClient(COSMOS_ENDPOINT, credential=cosmos_credential)
cosmos_db = cosmos_client.get_database_client("travel-memory")
chat_container_sync = cosmos_db.get_container_client("chat-history")
episodic_container_sync = cosmos_db.get_container_client("episodic-memory")

# For async operations (needed by CosmosDBHistoryProvider)
async def get_async_chat_container():
    async_credential = AsyncDefaultAzureCredential()
    async_client = AsyncCosmosClient(COSMOS_ENDPOINT, credential=async_credential)
    async_db = async_client.get_database_client("travel-memory")
    async_container = async_db.get_container_client("chat-history")
    return async_container, async_client, async_credential

print(f"Project:        {PROJECT_ENDPOINT}")
print(f"Model:          {MODEL_DEPLOYMENT}")
print(f"Cosmos NoSQL:   {COSMOS_ENDPOINT}")
print(f"Neo4j:          {NEO4J_URI}")
print(f"Cosmos DB:      travel-memory (containers: episodic-memory, chat-history)")

def load_instructions(path):
    return Path(path).read_text(encoding="utf-8")"""))

# ============================================================
# Cell 5: Part 1 intro
# ============================================================
cells.append(md("""\
---
## Part 1: The Problem That Only Appears When You Combine

Module 4's Part 6 already showed three memories working together — routing queries to the right memory, orchestrating multi-memory responses. That works when the memories **agree**.

But what happens when they don't? Consider this scenario:
- Semantic memory says the user **prefers business class**
- The booking procedure says Senior-level employees fly **economy only**
- The user's trip history shows they **loved Marriott**, but they just said "try Hilton"

Without explicit rules for handling these contradictions, the agent **improvises** — it may reach a reasonable answer, but the resolution is ad-hoc. It won't consistently name which memory sources disagree, explain what it's trading off, or guarantee the same reasoning across runs. The result might be correct today and different tomorrow.

Let's see this in action. The instructions below have routing and memory triggers, but **no conflict resolution rules**."""))

# ============================================================
# Cell 6A: Chat History Provider (Cosmos DB)
# ============================================================
cells.append(code('''\
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework import tool, BaseHistoryProvider, Message, AgentSession

credential = AzureCliCredential()

# ─── Chat History Provider ───
# Persists every chat message to Cosmos DB via the framework's BaseHistoryProvider.
# before_run() loads prior messages for session continuity.
# after_run() saves new messages (user input + agent response).
# Tool call/result content is stripped — only human-readable messages are stored.

_TOOL_CONTENT_TYPES = {"function_call", "function_result"}

def _strip_tool_content(msg):
    """Return a clean Message with tool content removed, or None if nothing remains."""
    clean = [c for c in msg.contents if c.type not in _TOOL_CONTENT_TYPES]
    if not clean:
        return None
    if len(clean) == len(msg.contents):
        return msg
    return Message(msg.role, clean)


class CosmosDBHistoryProvider(BaseHistoryProvider):
    """Persists every chat message to Cosmos DB (async container)."""
    def __init__(self, async_container_getter):
        super().__init__(source_id="cosmos_history")
        self.async_container_getter = async_container_getter

    async def get_messages(self, session_id, **kwargs):
        if not session_id:
            return []
        container, client, credential = await self.async_container_getter()
        query = "SELECT * FROM c WHERE c.conversation_id = @sid ORDER BY c._ts ASC"
        params = [{"name": "@sid", "value": session_id}]
        messages = []
        async for item in container.query_items(query=query, parameters=params, partition_key=session_id):
            msg = _strip_tool_content(Message.from_dict(item["message"]))
            if msg:
                messages.append(msg)
        await credential.close()
        await client.close()
        return messages

    async def save_messages(self, session_id, messages, **kwargs):
        if not session_id or not messages:
            return
        container, client, credential = await self.async_container_getter()
        for msg in messages:
            clean = _strip_tool_content(msg)
            if not clean:
                continue
            doc = {
                "id": f"{session_id}-{uuid4().hex[:8]}",
                "conversation_id": session_id,
                "role": clean.role,
                "message": clean.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await container.upsert_item(doc)
        await credential.close()
        await client.close()

history = CosmosDBHistoryProvider(get_async_chat_container)
print("Chat history provider: CosmosDBHistoryProvider (auto-persists every turn)")'''))

# ============================================================
# Cell 6B: Episodic Memory Tools
# ============================================================
cells.append(code('''\
# ─── Episodic Memory Tools ───
# Events accumulate in _episodic_store (runtime cache) during a conversation.
# remember_event() stores trip completions, booking confirmations, and user feedback.
# recall_events() searches by keyword/type, returning most recent matches first.
# The cache is batch-saved to Cosmos DB after the conversation (see Part 3).

_episodic_store = []

@tool
async def remember_event(
    user_id: str,
    event_type: str,
    description: str,
    details: str = "",
) -> str:
    """Store a significant event in the user's episodic memory.

    Call this when:
    - A trip is completed or booked
    - The user shares feedback about a past experience
    - Something notable happens worth remembering for the future

    Args:
        user_id: Employee ID (e.g. "E001")
        event_type: Category — "trip", "booking", "feedback", "preference"
        description: Brief summary of what happened
        details: Optional JSON string with structured data
    """
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
    """Search the user's episodic memory for past events.

    Call this when:
    - Planning a trip and want to check past experiences
    - The user asks about their travel history
    - Need context from previous trips for recommendations

    Args:
        user_id: Employee ID (e.g. "E001")
        query: Optional keyword to search in descriptions
        event_type: Optional filter — "trip", "booking", "feedback"
        limit: Maximum number of events to return
    """
    results = [e for e in _episodic_store if e["user_id"] == user_id]
    if event_type:
        results = [e for e in results if e["event_type"] == event_type]
    if query:
        results = [e for e in results if query.lower() in e["description"].lower()]
    results = sorted(results, key=lambda e: e["timestamp"], reverse=True)[:limit]
    return json.dumps(results, indent=2) if results else "No matching events found."

print("Episodic tools: remember_event, recall_events")'''))

# ============================================================
# Cell 6C: Semantic Memory Tools
# ============================================================
cells.append(code('''\
# ─── Semantic Memory Tools ───
# OntologyManager normalizes free-text relationships and entity types to canonical forms.
# "likes", "loves", "wants" → PREFERS; "airline", "carrier" → AIRLINE.
# SmartKnowledgeGraph stores (subject, relationship, object) triplets per user.
# Enforces uniqueness by (relationship, object_type) — a new airline preference replaces the old.
# learn_about_user() extracts persistent facts from natural language via LLM.
# query_user_knowledge() retrieves stored facts by relationship/entity type.
# The graph is batch-saved to Neo4j after the conversation (see Part 3).

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


EXTRACTION_PROMPT = """Extract knowledge triplets from the user's statement.
Return a JSON array of objects with these fields:
- "relationship": how the subject relates to the object (e.g. "prefers", "requires", "dislikes", "wants")
- "object": the entity (e.g. "Delta", "aisle", "vegetarian", "business class")
- "object_type": category (e.g. "airline", "hotel", "seat_type", "dietary", "flight_class")

Rules:
- Only extract PERSISTENT facts (preferences, requirements) — not one-time plans
- "I need to fly Tuesday" is NOT a preference — skip it
- "I always fly United" IS a preference — extract it
- "I want business class" IS a preference — extract it with object_type "flight_class"
- Return ONLY the JSON array, no other text

Examples:
Input: "I prefer Delta and I'm vegetarian"
Output: [{"relationship": "prefers", "object": "Delta", "object_type": "airline"}, {"relationship": "requires", "object": "vegetarian", "object_type": "dietary"}]

Input: "I want business class for my flights"
Output: [{"relationship": "prefers", "object": "business class", "object_type": "flight_class"}]

Input: "Book me a flight to NYC next week"
Output: []
"""


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
    """Extract and store facts/preferences from a user's statement in semantic memory.

    Args:
        user_id: Employee ID (e.g. "E001")
        statement: Natural language containing facts to remember
    """
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
        stored.append(f"({user_id}, {rel}, {t[\'object\']}/{otype})")
    return f"Learned {len(stored)} facts: " + "; ".join(stored)


@tool
async def query_user_knowledge(
    user_id: str,
    relationship: str = "",
    entity_type: str = "",
) -> str:
    """Query the user's semantic memory for stored facts and preferences.

    Args:
        user_id: Employee ID (e.g. "E001")
        relationship: Optional filter — "PREFERS", "REQUIRES", "DISLIKES"
        entity_type: Optional filter — "AIRLINE", "HOTEL", "SEAT_TYPE", "DIETARY", "FLIGHT_CLASS"
    """
    ontology = OntologyManager()
    rel = ontology.canonicalize_relationship(relationship) if relationship else None
    etype = ontology.canonicalize_entity_type(entity_type) if entity_type else None
    facts = _knowledge_graph.query(user_id, relationship=rel, object_type=etype)
    if not facts:
        return "No matching facts found."
    lines = [f"({f[\'subject\']}, {f[\'relationship\']}, {f[\'object\']}/{f[\'object_type\']})" for f in facts]
    return "\\n".join(lines)

print("Semantic tools: learn_about_user, query_user_knowledge")'''))

# ============================================================
# Cell 6D: Booking Tools (NEW)
# ============================================================
cells.append(code('''\
# ─── Booking Tools ───
# Stubs that search real flight/hotel data from the shared data files.
# search_flights() applies a class multiplier to base economy prices
#   (e.g., business = 2.8× economy) and returns matching flights.
#   When user_id is provided, includes budget_policy with violations.
# search_hotels() filters by city and optional hotel chain.
#   When user_id is provided, includes budget_policy with violations.
# book_trip() hard-rejects any booking that violates budget policy.
# Budget limits are read dynamically from skills/*/budget-limits.json.

_FLIGHTS = json.loads(Path("../../data/flights.json").read_text())
_HOTELS = json.loads(Path("../../data/hotels.json").read_text())
_EMPLOYEES = json.loads(Path("../../data/employees.json").read_text())

# Load budget limits from both skill resource files (same files read_skill_resource serves)
_BUDGET_LIMITS = {
    "domestic": json.loads(Path("skills/domestic-booking/budget-limits.json").read_text()),
    "international": json.loads(Path("skills/international-booking/budget-limits.json").read_text()),
}

_CITY_TO_CODE = {
    "seattle": "SEA", "san francisco": "SFO", "new york": "JFK",
    "london": "LHR", "tokyo": "NRT", "chicago": "ORD",
    "los angeles": "LAX", "denver": "DEN", "atlanta": "ATL", "dallas": "DFW",
}
_CLASS_MULTIPLIER = {
    "economy": 1.0, "economy_plus": 1.3, "business": 2.8, "first": 4.0,
}
_DOMESTIC_CODES = {"SEA", "SFO", "JFK", "ORD", "LAX", "DEN", "ATL", "DFW"}


def _get_budget_limits(user_id: str, origin_code: str, dest_code: str):
    """Look up budget limits for a user based on employee level and trip type."""
    employee = next((e for e in _EMPLOYEES if e["employee_id"] == user_id), None)
    if not employee:
        return None, None
    level = employee["level"]
    trip_type = "domestic" if origin_code in _DOMESTIC_CODES and dest_code in _DOMESTIC_CODES else "international"
    limits = _BUDGET_LIMITS[trip_type]["by_level"].get(level)
    return limits, level


@tool
async def search_flights(
    origin: str,
    destination: str,
    flight_class: str = "economy",
    user_id: str = "",
) -> str:
    """Search available flights between two cities.

    Args:
        origin: Origin city name or airport code (e.g. "Seattle" or "SEA")
        destination: Destination city name or airport code (e.g. "London" or "LHR")
        flight_class: Cabin class — "economy", "economy_plus", "business", or "first"
        user_id: Optional employee ID (e.g. "E001") — when provided, includes budget policy and violations
    """
    orig = _CITY_TO_CODE.get(origin.lower(), origin.upper())
    dest = _CITY_TO_CODE.get(destination.lower(), destination.upper())
    multiplier = _CLASS_MULTIPLIER.get(flight_class.lower(), 1.0)

    matches = []
    for f in _FLIGHTS:
        if f["origin"] == orig and f["destination"] == dest:
            adjusted = dict(f)
            adjusted["price"] = round(f["price"] * multiplier)
            adjusted["class"] = flight_class.lower()
            matches.append(adjusted)

    if not matches:
        return f"No flights found from {orig} to {dest}."

    if not user_id:
        return json.dumps(matches, indent=2)

    # Include budget policy when user_id is provided
    limits, level = _get_budget_limits(user_id, orig, dest)
    if not limits:
        return json.dumps(matches, indent=2)

    violations = []
    if flight_class.lower() not in limits["allowed_flight_class"]:
        violations.append(f"Class \\'{flight_class}\\' not allowed — permitted: {limits[\'allowed_flight_class\']}")
    over_budget = [f for f in matches if f["price"] > limits["max_flight_cost"]]
    if over_budget:
        violations.append(f"All {len(over_budget)} flights exceed ${limits[\'max_flight_cost\']} limit")

    return json.dumps({
        "flights": matches,
        "budget_policy": {
            "employee_level": level,
            "max_flight_cost": limits["max_flight_cost"],
            "allowed_flight_class": limits["allowed_flight_class"],
            "violations": violations,
        },
    }, indent=2)


@tool
async def search_hotels(
    city: str,
    hotel_chain: str = "",
    user_id: str = "",
) -> str:
    """Search available hotels in a city.

    Args:
        city: City name (e.g. "London", "New York")
        hotel_chain: Optional chain filter (e.g. "Hilton", "Marriott")
        user_id: Optional employee ID (e.g. "E001") — when provided, includes budget policy and violations
    """
    results = [h for h in _HOTELS if h["city"].lower() == city.lower()]
    if hotel_chain:
        results = [h for h in results if hotel_chain.lower() in h["chain"].lower()]
    if not results:
        return f"No hotels found in {city}." + (f" (chain filter: {hotel_chain})" if hotel_chain else "")

    if not user_id:
        return json.dumps(results, indent=2)

    # Determine trip type from city code
    city_code = results[0].get("city_code", "")
    trip_type = "domestic" if city_code in _DOMESTIC_CODES else "international"
    employee = next((e for e in _EMPLOYEES if e["employee_id"] == user_id), None)
    if not employee:
        return json.dumps(results, indent=2)

    level = employee["level"]
    limits = _BUDGET_LIMITS[trip_type]["by_level"].get(level)
    if not limits:
        return json.dumps(results, indent=2)

    violations = []
    over_budget = [h for h in results if h["price_per_night"] > limits["max_hotel_per_night"]]
    if over_budget:
        violations.append(f"{len(over_budget)} hotel(s) exceed ${limits[\'max_hotel_per_night\']}/night limit")

    return json.dumps({
        "hotels": results,
        "budget_policy": {
            "employee_level": level,
            "max_hotel_per_night": limits["max_hotel_per_night"],
            "violations": violations,
        },
    }, indent=2)


@tool
async def book_trip(
    user_id: str,
    flight_id: str,
    hotel_id: str,
    check_in: str,
    check_out: str,
    flight_class: str = "economy",
) -> str:
    """Book a trip with a specific flight and hotel.

    Args:
        user_id: Employee ID (e.g. "E001")
        flight_id: Flight ID from search_flights results (e.g. "DL550")
        hotel_id: Hotel ID from search_hotels results (e.g. "H007")
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        flight_class: Cabin class — "economy", "economy_plus", "business", or "first"
    """
    flight = next((f for f in _FLIGHTS if f["flight_id"] == flight_id), None)
    hotel = next((h for h in _HOTELS if h["hotel_id"] == hotel_id), None)

    if not flight:
        return f"Flight {flight_id} not found."
    if not hotel:
        return f"Hotel {hotel_id} not found."

    from datetime import date
    nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
    if nights <= 0:
        return "Check-out must be after check-in."

    # Budget enforcement — hard reject on violations
    multiplier = _CLASS_MULTIPLIER.get(flight_class.lower(), 1.0)
    adjusted_price = round(flight["price"] * multiplier)
    limits, level = _get_budget_limits(user_id, flight["origin"], flight["destination"])

    if limits:
        violations = []
        if flight_class.lower() not in limits["allowed_flight_class"]:
            violations.append(f"Class \\'{flight_class}\\' not allowed for {level} — permitted: {limits[\'allowed_flight_class\']}")
        if adjusted_price > limits["max_flight_cost"]:
            violations.append(f"Flight cost ${adjusted_price} exceeds ${limits[\'max_flight_cost\']} limit for {level}")
        if hotel["price_per_night"] > limits["max_hotel_per_night"]:
            violations.append(f"Hotel ${hotel[\'price_per_night\']}/night exceeds ${limits[\'max_hotel_per_night\']} limit for {level}")
        if violations:
            return json.dumps({
                "status": "REJECTED",
                "reason": "Budget policy violation",
                "violations": violations,
                "policy_limits": {
                    "employee_level": level,
                    "max_flight_cost": limits["max_flight_cost"],
                    "max_hotel_per_night": limits["max_hotel_per_night"],
                    "allowed_flight_class": limits["allowed_flight_class"],
                },
            }, indent=2)

    hotel_total = hotel["price_per_night"] * nights
    booking = {
        "booking_ref": f"BK-{uuid4().hex[:6].upper()}",
        "status": "confirmed",
        "user_id": user_id,
        "flight": {"id": flight_id, "airline": flight["airline"],
                   "route": f"{flight[\'origin\']}→{flight[\'destination\']}",
                   "class": flight_class.lower(),
                   "price": adjusted_price},
        "hotel": {"id": hotel_id, "name": hotel["name"],
                  "nights": nights, "per_night": hotel["price_per_night"],
                  "total": hotel_total},
        "total_cost": adjusted_price + hotel_total,
    }
    return json.dumps(booking, indent=2)

print(f"Booking tools:  search_flights, search_hotels, book_trip")
print(f"  Loaded {len(_FLIGHTS)} flights, {len(_HOTELS)} hotels from data files")
print(f"  Loaded {len(_EMPLOYEES)} employees, budget limits for {list(_BUDGET_LIMITS.keys())}")
print(f"  Budget enforcement: search tools include policy when user_id provided; book_trip hard-rejects violations")'''))

# ============================================================
# Cell 6E: Reset + Baseline Data
# ============================================================
cells.append(code('''\
# ─── Reset + Baseline Data ───
# Resets all runtime caches to a known baseline for reproducible demos.
# Preloads 3 episodic events (NYC 5/5, London 4/5, Chicago 3/5) and
# 4 semantic facts (Delta, aisle, Marriott, vegetarian).
# Call before each demo to ensure identical starting conditions.

def reset_memory():
    """Reset in-memory stores to a known baseline for reproducible demos."""
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

print(f"\\nAll tools ready:")
print(f"  Episodic:  remember_event, recall_events")
print(f"  Semantic:  learn_about_user, query_user_knowledge")
print(f"  Booking:   search_flights, search_hotels, book_trip")
print(f"  History:   CosmosDBHistoryProvider (automatic)")
print(f"\\nBaseline: {len(_episodic_store)} episodic events, {len(_knowledge_graph.all_facts('E001'))} semantic facts")
print(f"reset_memory() available — call to restore baseline state")'''))

# ============================================================
# Cell 7: SkillsProvider
# ============================================================
cells.append(code('''\
# ─── SkillsProvider (Module 4 pattern — auto-discovers SKILL.md files) ───
# Skills are pre-existing files in skills/ — same ones we created in Module 4.
# SkillsProvider scans for SKILL.md files and generates load_skill() + read_skill_resource() tools.

from agent_framework import SkillsProvider

procedures = SkillsProvider(skill_paths=["skills"])

print("Skills discovered by SkillsProvider:")
for skill in procedures._skills.values():
    desc = skill.description[:80] + "..." if len(skill.description) > 80 else skill.description
    print(f"  {skill.name}: {desc}")
    if skill.resources:
        for rname in skill.resources:
            print(f"    └── resource: {rname.name}")
print()
print("Prompt files (loaded at runtime):")
print(f"  prompts/combined_no_conflicts.md — NO conflict rules")
print(f"  prompts/combined.md              — WITH conflict rules")'''))

# ============================================================
# Cell 8: demo_silent_failures (3 turns + booking tools)
# ============================================================
cells.append(code("""\
async def demo_silent_failures():
    # Load instructions WITHOUT conflict resolution rules
    instructions = load_instructions("prompts/combined_no_conflicts.md")
    print(f"Loaded: prompts/combined_no_conflicts.md ({len(instructions)} chars)")
    print("Note: These instructions have memory routing but NO conflict resolution rules. Watch how the agent improvises.\\n")

    session = AgentSession()

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
            search_flights, search_hotels, book_trip,
        ],
        context_providers=[history, procedures],
    )
    turns = [
        # Turn 1: Store a preference that will conflict with policy
        "I want to fly business class from now on.",

        # Turn 2: Book a trip — triggers policy vs. preference + budget conflict
        "Book me a flight from Seattle to London, departing May 10-15. I have a valid visa.",

        # Turn 3: State a hotel preference that contradicts history
        "For the hotel, I want to try Hilton this time.",
    ]
    for i, user_msg in enumerate(turns, 1):
        print(f"--- Turn {i} ---")
        print(f"User: {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"Agent: {response.text}\\n")

    # Show memory state after the conversation
    print("\\n--- Memory State After Ad-hoc Demo ---")
    print(f"\\nSemantic facts ({len(_knowledge_graph.all_facts('E001'))}):")
    for f in _knowledge_graph.all_facts("E001"):
        print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")

print("=== Ad-hoc Resolution Demo: No Conflict Rules ===\\n")
reset_memory()
asyncio.run(demo_silent_failures())"""))

# ============================================================
# Cell 9: What Went Wrong
# ============================================================
cells.append(md("""\
### What to Look For

Review the agent's responses above with these questions in mind:

- **Memory attribution** — Did the agent name *which memory types* disagreed? For example, did it say "your preference *(semantic memory)* conflicts with policy *(procedural memory)*"? Or did it just relay the result without citing sources?
- **Budget transparency** — The `search_flights` tool returned a `budget_policy` block showing a $800 limit and violations. Did the agent explain that this limit comes from the Senior-level booking procedure, or did it just pass along the rejection?
- **History acknowledgment** — Trip history shows the user rated Marriott 4/5 in London. When switching to Hilton, did the agent mention this history? Or did it just accept the switch without comment?
- **Consistency guarantee** — If you reran this cell, would the response be the same? Without explicit rules, the agent's reasoning path may vary between runs.

The agent may handle all of this well — modern models are capable of improvising through conflicts. But improvisation is not a design decision. The resolution is **ad-hoc**: correct today, potentially different tomorrow, never traceable to a documented priority hierarchy."""))

# ============================================================
# Cell 10: Part 2 intro
# ============================================================
cells.append(md("""\
---
## Part 2: Designing Conflict Resolution

Part 1 showed the agent handling conflicts ad-hoc — sometimes well, sometimes not, never with consistent attribution. Now let's make it systematic.

Conflict resolution isn't something you bolt on — it's a **design decision** that reflects your domain. A healthcare compliance agent resolves conflicts differently than a consumer shopping assistant. Before writing rules, we need to understand the *types* of conflicts and the *hierarchy* that governs them."""))

# ============================================================
# Cell 11: Three Kinds of Conflict
# ============================================================
cells.append(md("""\
### Three Kinds of Conflict

| Conflict | Example | Why It's Hard |
|---|---|---|
| **Preference vs. Policy** | User prefers business class, but policy says economy only | Both are "correct" — the user genuinely prefers it, and the policy genuinely forbids it |
| **History vs. Stated Preference** | Past trips show Marriott (rated 5/5), but user says "try Hilton" | History suggests one answer, the user's explicit words say another |
| **Old Fact vs. New Fact** | Semantic memory says "prefers Delta", user says "I've switched to United" | Same memory type, but outdated vs. current |

The third type (old vs. new) is handled automatically by the `SmartKnowledgeGraph` — storing a new fact with the same relationship and type replaces the old one. Module 3 covered this.

The first two types are **cross-memory conflicts** — they only emerge when different memory systems interact. They need explicit rules.

### Priority Hierarchies Are Domain Decisions

Our travel domain uses this hierarchy:

```
Policy (procedural) > Stated preference (semantic) > History (episodic)
```

But this isn't universal. The right hierarchy depends on your domain:

| Domain | Hierarchy | Rationale |
|---|---|---|
| **Corporate travel** | Policy > preference > history | Compliance is non-negotiable |
| **Healthcare** | Regulation > clinical judgment > patient preference | Safety first, always |
| **Consumer e-commerce** | User preference > history > defaults | The customer is in control |
| **Personal assistant** | Stated preference > history > defaults | No policy layer exists |

The key insight: **your priority hierarchy should be a documented design decision, not an emergent accident.** If you don't define it explicitly, the agent will invent one — and it might invent a different one every time."""))

# ============================================================
# Cell 12: Detection vs. Resolution
# ============================================================
cells.append(md("""\
### Detection vs. Resolution

Conflict resolution actually has two distinct steps, and conflating them is a common mistake:

**Detection** — recognizing that a conflict exists. This requires cross-memory comparison:
1. The agent stores "prefers business class" in semantic memory
2. The agent loads a procedure that says "economy only for Senior"
3. The agent must *recognize* that these two facts contradict each other

**Resolution** — deciding what to do about it. This requires a priority hierarchy:
1. Apply the hierarchy: policy > preference → follow policy
2. Be transparent: explain *why* the preference can't be honored
3. Offer alternatives: "economy-plus is available within policy"

Detection is the harder problem. The agent needs to hold information from *two different memory types* simultaneously and compare them. This is procedural knowledge about *how to arbitrate* — which is why the conflict resolution rules belong in the agent's instructions (procedural memory), not in the tools or the data.

The `Cross-Memory Conflicts` section we'll add to the instructions handles both: it tells the agent *when* to recognize a conflict (detection) and *what to do* about it (resolution)."""))

# ============================================================
# Cell 13: demo_conflicts (3 turns + booking tools)
# ============================================================
cells.append(code("""\
reset_memory()  # Clean baseline: Delta, aisle, Marriott, vegetarian + 3 trips

async def demo_conflicts():
    # Now load instructions WITH conflict resolution rules
    instructions = load_instructions("prompts/combined.md")
    print(f"Loaded: prompts/combined.md ({len(instructions)} chars)")
    print("Note: These instructions INCLUDE mandatory budget checking AND conflict resolution rules.\\n")

    session = AgentSession()

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
            search_flights, search_hotels, book_trip,
        ],
        context_providers=[history, procedures],
    )
    # Same conversation as Part 1 — same conflicts, different outcome
    turns = [
        # Turn 1: Store a preference that will conflict with policy
        "I want to fly business class from now on.",

        # Turn 2: Book a trip — triggers policy vs. preference + budget conflict
        "Book me a flight from Seattle to London, departing May 10-15. I have a valid visa.",

        # Turn 3: State a hotel preference that contradicts history
        "For the hotel, I want to try Hilton this time.",
    ]
    for i, user_msg in enumerate(turns, 1):
        print(f"--- Turn {i} ---")
        print(f"User: {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"Agent: {response.text}\\n")

    # Show memory state after the conversation
    print("\\n--- Memory State After Conflict Demo ---")
    print(f"\\nSemantic facts ({len(_knowledge_graph.all_facts('E001'))}):")
    for f in _knowledge_graph.all_facts("E001"):
        print(f"  ({f['subject']}, {f['relationship']}, {f['object']}/{f['object_type']})")

print("=== Conflict Demo: With Explicit Resolution Rules ===\\n")
asyncio.run(demo_conflicts())"""))

# ============================================================
# Cell 14: Turn-by-Turn Analysis (3 rows)
# ============================================================
cells.append(md("""\
### Turn-by-Turn Analysis

| Turn | User Said | Memory Involved | Conflict? | Resolution |
|---|---|---|---|---|
| 1 | "I want business class" | **Semantic** — stores preference | No | Preference stored as (E001, PREFERS, business class/FLIGHT_CLASS) |
| 2 | "Book me Seattle→London" | **Procedural** (int'l procedure + budget-limits) + **Semantic** (preferences) + **Booking tools** (`search_flights` returns $1,050–$1,250 economy) | **Yes**: preference says business class ($2,940–$3,500), procedure says economy only for Senior, *and* even economy exceeds the $800 limit | **Policy wins** — agent explains the class restriction, flags the budget overage, and presents the options transparently |
| 3 | "Try Hilton this time" | **Semantic** (stated preference) + **Episodic** (Marriott rated 4/5 in London) | **Yes**: history shows Marriott was great, but user wants Hilton | **Stated preference wins** — agent acknowledges Marriott history, honors Hilton request |

The key moments are **Turns 2 and 3** — two different conflict types, two different resolutions, both driven by the `Cross-Memory Conflicts` section in the instructions."""))

# ============================================================
# Cell 15: Before vs. After
# ============================================================
cells.append(md("""\
### Ad-hoc vs. Systematic

The same conversation, the same memory state, the same budget data in tool responses — but a different approach to resolution:

| Turn | Ad-hoc (Part 1 — no conflict rules) | Systematic (Part 2 — with conflict rules) |
|---|---|---|
| "I want business class" / "Book Seattle→London" | Agent navigates the constraint but may not name *semantic memory* vs *procedural memory*. Resolution varies across runs. | Agent cites each memory source by name, applies the documented hierarchy (policy > preference), produces the same structured response every time. |
| "Try Hilton" | Agent likely switches to Hilton but may not mention the 4/5 Marriott rating from episodic memory. | Agent acknowledges Marriott history *(episodic)*, honors stated preference *(semantic)*, offers to update the default. |

The tools enforce budget policy identically in both demos. The difference is a single `Cross-Memory Conflicts` section in the instruction file that turns ad-hoc improvisation into documented, repeatable behavior."""))

# ============================================================
# Cell 16: How Conflict Resolution Fits Into the Flow
# ============================================================
cells.append(md("""\
### How Conflict Resolution Fits Into the Flow

When multiple memories are involved, the agent follows a sequence: route the query to the right memories, gather answers, then check for conflicts. Here's the full pattern for a booking request:

```
User: "I want business class" → stored in semantic memory
User: "Book me Seattle→London, May 10-15"
    → load_skill("international-booking") (procedural)
    → Procedure step 1: check preferences → semantic says business class
    → search_flights("Seattle", "London", "business", user_id="E001")
        → Returns flights at $2,940–$3,500 + budget_policy:
          {"allowed_flight_class": ["economy","economy_plus"], "max_flight_cost": 800, "violations": [...]}
    → CONFLICT DETECTED: preference vs. policy (class restriction + budget limit)
    → RESOLUTION: policy wins — explain limits, present options with prices, let user decide
    → book_trip() would REJECT any attempt to book above limits
    → Continue with remaining procedure steps (insurance, visa, hotel)
```

The conflict resolution step sits *between* gathering information and acting on it. The budget data comes directly from the search tool response (which reads from the same `budget-limits.json` that `read_skill_resource` serves). The agent doesn't skip the preference — it acknowledges it, explains the constraint, and proceeds transparently. This is what makes conflict resolution a form of **procedural memory**: it's knowledge about *how to arbitrate*, encoded in the instructions."""))

# ============================================================
# Cell 17: Part 3 intro
# ============================================================
cells.append(md("""\
---
## Part 3: Memory Architecture — Runtime Caches and Persistence

Parts 1 and 2 used in-memory runtime caches for episodic and semantic data — fast, simple, and sufficient for demonstrating conflict resolution. But those caches vanish on restart. For production, every memory type needs a persistent backend.

**Why two tiers?** Not all persistence works the same way. Some memory types are persisted **automatically** by the framework, while others require **explicit** batch operations. This is a deliberate architectural choice:

| Memory Type | Runtime | Backend | Persistence | Why |
|---|---|---|---|---|
| **Session (chat history)** | `CosmosDBHistoryProvider` | Cosmos DB (`chat-history`) | **Automatic** — framework calls `save_messages()` after every turn | Every interaction must be logged — no developer action needed |
| **Procedural (skills)** | `SkillsProvider` | Filesystem (`skills/`) | **Automatic** — read from disk on every `load_skill()` call | Skills are code artifacts, already persistent by nature |
| **Episodic (events)** | `_episodic_store` list | Cosmos DB (`episodic-memory`) | **Explicit** — batch save after conversation | Events accumulate during a session, then persist in bulk |
| **Semantic (facts)** | `SmartKnowledgeGraph` | Neo4j | **Explicit** — batch save after conversation | Knowledge graph updates are expensive; batch is more efficient |

The automatic tier (chat history, skills) is handled by `context_providers` — the framework knows when to load and save. The explicit tier (episodic, semantic) uses runtime caches that we flush to backends at the end of a session. This keeps tool calls fast (in-memory reads) while ensuring nothing is lost."""))

# ============================================================
# Cell 18: Storage Mapping
# ============================================================
cells.append(md("""\
### Storage Mapping

Each memory type maps to the backend that matches its data model — the same pattern from the individual modules:

- **Session → Cosmos DB NoSQL** (`chat-history` container): One document per message, partitioned by `conversation_id`. The `CosmosDBHistoryProvider` handles this automatically via the framework's `before_run`/`after_run` hooks — same pattern as Module 2.
- **Episodic → Cosmos DB NoSQL** (`episodic-memory` container): Flat JSON documents, partitioned by `user_id`. Same as Module 2.
- **Semantic → Neo4j**: Nodes and relationships — `(User)-[:PREFERS]->(Entity)`. Same Cypher patterns as Module 3.
- **Procedural → Filesystem** (`skills/`): SKILL.md files with YAML frontmatter + resource files. `SkillsProvider` auto-discovers them — same as Module 4."""))

# ============================================================
# Cell 19A: Persist Episodic → Cosmos
# ============================================================
cells.append(code('''\
# ─── Persist Episodic → Cosmos NoSQL ───
# Batch-saves episodic events from the runtime cache (_episodic_store) to Cosmos.
# Each event is upserted by its id — safe to run multiple times.

async def persist_episodic():
    from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
    from azure.identity.aio import DefaultAzureCredential as AsyncCredential

    async_credential = AsyncCredential()
    client = AsyncCosmosClient(COSMOS_ENDPOINT, credential=async_credential)
    database = client.get_database_client("travel-memory")
    container = database.get_container_client("episodic-memory")

    for event in _episodic_store:
        doc = {
            "id": event["id"],
            "user_id": event["user_id"],
            "event_type": event["event_type"],
            "description": event["description"],
            "details": event.get("details", {}),
            "timestamp": event["timestamp"],
        }
        await container.upsert_item(doc)

    print(f"Episodic: saved {len(_episodic_store)} events to Cosmos NoSQL")

    query = "SELECT c.id, c.description FROM c WHERE c.user_id = 'E001'"
    items = [item async for item in container.query_items(query=query, partition_key="E001")]
    for item in items:
        print(f"  [episodic] {item['id']}: {item.get('description', '')[:60]}")

    await async_credential.close()
    await client.close()

print("=== Persisting Episodic Memory ===\\n")
asyncio.run(persist_episodic())'''))

# ============================================================
# Cell 19B: Persist Semantic → Neo4j
# ============================================================
cells.append(code('''\
# ─── Persist Semantic → Neo4j ───
# Batch-saves semantic facts from the knowledge graph to Neo4j.
# For each fact, deletes any existing relationship of the same type
# (e.g., old airline preference) then creates the new one.
# This mirrors SmartKnowledgeGraph's replace-on-type logic.

async def persist_semantic():
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    async with driver.session(database=NEO4J_DATABASE) as neo4j_session:
        facts = _knowledge_graph.all_facts("E001")
        for fact in facts:
            obj_lower = fact["object"].lower().replace(" ", "-")
            otype = fact.get("object_type", "")
            rel = fact["relationship"]

            if otype:
                await neo4j_session.run(
                    "MATCH (u:User {id: $uid})-[r:" + rel + "]->(e) "
                    "WHERE e.entity_type = $otype DELETE r",
                    uid="E001", otype=otype,
                )

            await neo4j_session.run(
                "MERGE (u:User {id: $uid}) "
                "MERGE (e:Entity {canonical: $obj_lower, entity_type: $otype}) "
                "SET e.raw = $obj "
                "MERGE (u)-[r:" + rel + "]->(e) "
                "SET r.timestamp = datetime()",
                uid="E001", obj_lower=obj_lower, otype=otype, obj=fact["object"],
            )

        result = await neo4j_session.run(
            "MATCH (u:User {id: $uid})-[r]->(e) "
            "RETURN type(r) AS relationship, e.raw AS object, e.entity_type AS object_type",
            uid="E001",
        )
        records = [record async for record in result]
        print(f"Semantic: saved {len(facts)} facts to Neo4j")
        for r in records:
            print(f"  [semantic] {r['object']}/{r['object_type']}")

    await driver.close()

    print("\\nChat history: already persisted by CosmosDBHistoryProvider (automatic tier)")
    print("Skills: already on disk in skills/ (automatic tier)")

print("=== Persisting Semantic Memory ===\\n")
asyncio.run(persist_semantic())'''))

# ============================================================
# Cell 20A: Clear + Reload from Backends
# ============================================================
cells.append(code('''\
# ─── Clear + Reload from Backends ───
# Clears all runtime caches, then reloads episodic events from Cosmos NoSQL and
# semantic facts from Neo4j. Chat history is loaded automatically by CosmosDBHistoryProvider.
# This simulates an agent restart — proving that persisted data survives.

async def reload_memory():
    global _episodic_store, _knowledge_graph

    # Step 1: Clear in-memory state
    _episodic_store.clear()
    _knowledge_graph = SmartKnowledgeGraph()
    print("Step 1: Cleared in-memory state")
    print(f"  Episodic events: {len(_episodic_store)}")
    print(f"  Semantic facts:  {len(_knowledge_graph.all_facts('E001'))}")

    # Step 2a: Reload episodic from Cosmos NoSQL
    from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
    from azure.identity.aio import DefaultAzureCredential as AsyncCredential

    async_credential = AsyncCredential()
    client = AsyncCosmosClient(COSMOS_ENDPOINT, credential=async_credential)
    database = client.get_database_client("travel-memory")
    container = database.get_container_client("episodic-memory")

    query = "SELECT * FROM c WHERE c.user_id = 'E001'"
    items = [item async for item in container.query_items(query=query, partition_key="E001")]

    for item in items:
        _episodic_store.append({
            "id": item["id"],
            "user_id": item["user_id"],
            "event_type": item["event_type"],
            "description": item["description"],
            "details": item.get("details", {}),
            "timestamp": item["timestamp"],
        })

    await async_credential.close()
    await client.close()
    print(f"\\nStep 2a: Reloaded {len(_episodic_store)} episodic events from Cosmos NoSQL")

    # Step 2b: Reload semantic from Neo4j
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    async with driver.session(database=NEO4J_DATABASE) as neo4j_session:
        result = await neo4j_session.run(
            "MATCH (u:User {id: $uid})-[r]->(e) "
            "RETURN type(r) AS relationship, e.raw AS object, e.entity_type AS object_type",
            uid="E001",
        )
        records = [record async for record in result]

        for rec in records:
            raw = rec["object"]
            otype = rec["object_type"]
            rel = rec["relationship"]
            if raw:
                _knowledge_graph.store_triplet("E001", "E001", rel, raw, otype)

    await driver.close()
    print(f"Step 2b: Reloaded {len(_knowledge_graph.all_facts('E001'))} semantic facts from Neo4j")
    print("Step 2c: Chat history will be loaded automatically by CosmosDBHistoryProvider")

print("=== Reload: Clear → Restore from Backends ===\\n")
asyncio.run(reload_memory())'''))

# ============================================================
# Cell 20B: Verify with Agent
# ============================================================
cells.append(code('''\
# ─── Verify with Agent ───
# Runs the agent against reloaded memory to verify persistence.
# "What do you know about me?" should return the same facts and history
# that were available before the clear/reload cycle.

async def verify_reload():
    instructions = load_instructions("prompts/combined.md")
    session = AgentSession()

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
            search_flights, search_hotels, book_trip,
        ],
        context_providers=[history, procedures],
    )
    response = await agent.run(
        "What do you know about me? Summarize my travel history and preferences.",
        session=session,
    )
    print(f"User: What do you know about me?")
    print(f"Agent: {response.text}")

print("=== Verify: Agent Against Reloaded Memory ===\\n")
asyncio.run(verify_reload())'''))

# ============================================================
# Cell 21: Two-Tier Persistence Pattern
# ============================================================
cells.append(md("""\
### The Two-Tier Persistence Pattern

```
AUTOMATIC TIER (framework-managed)          EXPLICIT TIER (developer-managed)
────────────────────────────────            ─────────────────────────────────
CosmosDBHistoryProvider                     _episodic_store
  → save_messages() after every turn          → upsert_item() to Cosmos NoSQL
  → Cosmos DB (chat-history)                  → batch save after conversation

SkillsProvider                              _knowledge_graph
  → reads from skills/ on load_skill()        → MERGE to Neo4j
  → already on disk                           → batch save after conversation
                                            ↓
                                          Run agent (tools unchanged)
```

The tools don't change — `remember_event`, `recall_events`, `learn_about_user`, and `query_user_knowledge` work the same whether data comes from preloaded defaults or persistent backends. The only difference is where the data starts (in-memory baseline vs. reloaded from storage) and where it ends up (discarded vs. persisted).

Chat history and skills are handled by `context_providers` — the agent framework manages their lifecycle automatically. Episodic and semantic data require explicit save/load because they're runtime caches — fast during the conversation, persisted in bulk afterward."""))

# ============================================================
# Cell 22: Summary
# ============================================================
cells.append(md("""\
---
## Summary

### What This Module Proved

Combined memory introduces a problem that doesn't exist in isolation: **memories disagree**. The agent needs explicit rules to handle it — without them, the agent improvises — it may get the right answer, but the resolution is ad-hoc, unattributed, and inconsistent across runs.

### Key Insights

1. **Conflicts are emergent.** Each memory type is internally consistent. Contradictions only appear at the intersection — when policy meets preference, or history meets a stated change.

2. **Priority hierarchies are design decisions.** "Policy > preference > history" works for corporate travel. Other domains have different hierarchies. Document yours explicitly — don't let the agent invent one.

3. **Detection precedes resolution.** The agent must first *recognize* that two memories contradict before it can apply a rule. Both detection and resolution are procedural knowledge, encoded in the instructions.

4. **Transparency is non-negotiable.** The worst outcome isn't picking the wrong answer — it's picking silently. Conflict rules must require the agent to name the conflict and explain its decision.

5. **Persistence is a two-tier architecture.** Chat history and skills are persisted automatically via `context_providers` (the framework manages their lifecycle). Episodic and semantic data use runtime caches that are flushed to backends explicitly. This separation keeps tool calls fast while ensuring nothing is lost.

### More Than One Way

Conflict resolution via instruction rules (as in this module) is one approach. Alternatives include:

- **Tiered tool design** — separate "check policy" and "check preference" tools that return structured results, with a merge step that detects conflicts programmatically
- **Confidence scoring** — each memory returns a confidence value; the agent picks the highest-confidence answer and flags low-confidence conflicts for human review
- **Escalation protocols** — unresolvable conflicts (e.g., two policies that contradict) get escalated to a human approver rather than resolved by the agent"""))

# ============================================================
# Cell 23: What's Next
# ============================================================
cells.append(md("""\
---
## What's Next

We've combined all memory types into one agent with explicit routing and conflict resolution. But what happens when the user moves to a **different agent**?

In **Module 6: Memory Handoff**, we'll explore how memory transfers between agents — the protocols, formats, and tradeoffs when one agent needs to share what it knows with another."""))

# ============================================================
# Cell 24: Cleanup
# ============================================================
cells.append(code("""\
# Optional: Clean up files created by this module
# Uncomment and run to remove generated files

# import shutil
# if Path("prompts").exists():
#     shutil.rmtree("prompts")
#     print("Removed prompts/")
# if Path("skills").exists():
#     shutil.rmtree("skills")
#     print("Removed skills/")

# To clean up Cosmos NoSQL data (uncomment if needed):
# async def cleanup_cosmos():
#     from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
#     from azure.identity.aio import DefaultAzureCredential as AsyncCredential
#     async_credential = AsyncCredential()
#     client = AsyncCosmosClient(COSMOS_ENDPOINT, credential=async_credential)
#     database = client.get_database_client("travel-memory")
#
#     # Episodic
#     episodic = database.get_container_client("episodic-memory")
#     items = [item async for item in episodic.query_items(
#         query="SELECT c.id FROM c WHERE c.user_id = 'E001'",
#         partition_key="E001"
#     )]
#     for item in items:
#         await episodic.delete_item(item=item["id"], partition_key="E001")
#     print(f"Deleted {len(items)} episodic docs from Cosmos NoSQL")
#
#     # Chat history
#     chat = database.get_container_client("chat-history")
#     chat_items = [item async for item in chat.query_items(
#         query="SELECT c.id, c.conversation_id FROM c",
#         enable_cross_partition_query=True
#     )]
#     for item in chat_items:
#         await chat.delete_item(item=item["id"], partition_key=item["conversation_id"])
#     print(f"Deleted {len(chat_items)} chat history docs from Cosmos NoSQL")
#
#     await async_credential.close()
#     await client.close()
# asyncio.run(cleanup_cosmos())

# To clean up Neo4j semantic data (uncomment if needed):
# async def cleanup_neo4j():
#     from neo4j import AsyncGraphDatabase
#     driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
#     async with driver.session(database=NEO4J_DATABASE) as neo4j_session:
#         await neo4j_session.run(
#             "MATCH (u:User {id: $uid})-[r]->() DELETE r",
#             uid="E001",
#         )
#         await neo4j_session.run(
#             "MATCH (u:User {id: $uid}) DELETE u",
#             uid="E001",
#         )
#     await driver.close()
#     print("Deleted E001 data from Neo4j")
# asyncio.run(cleanup_neo4j())"""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11.0"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

with open("05_combined_memory.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")

print(f"Generated 05_combined_memory.ipynb with {len(cells)} cells")

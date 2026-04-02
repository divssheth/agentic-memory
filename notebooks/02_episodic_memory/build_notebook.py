"""Build Module 2: Episodic Memory notebook."""
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
%pip install -q azure-cosmos -r ../../requirements.txt"""))

# ============================================================
# Cell 2: Title + What You'll Learn
# ============================================================
cells.append(md("""\
# Module 2: Episodic Memory

Module 1 showed us that session memory is **transient** — lost when the session ends. The obvious fix? Save everything to a database.

In this module we'll try that, discover why it falls apart at scale, and arrive at a better approach: **episodic memory**.

## What You'll Learn
1. How to **persist chat history** to a database using the framework's `BaseHistoryProvider`
2. Why saving every message creates bloat, noise, and unqueryable data
3. How **episodic memory** stores only what matters — structured events the agent can recall
4. The design pattern: `@tool` for selective memory (agent decides what to remember)
5. How persistent chat history and episodic memory **work together** in practice

## The Journey
```
Transient memory (Module 1)
    → Persist every message (naive fix)
        → Discover the scaling problem
            → Episodic memory (selective, structured)
                → Both together (audit + intelligence)
```"""))

# ============================================================
# Cell 3: Setup heading
# ============================================================
cells.append(md("""\
---
## Setup

> **Prerequisite**: You need an Azure Cosmos DB account. Follow the steps in
> [`steps/01_setup_cosmos.md`](steps/01_setup_cosmos.md) if you haven't created one yet.
> Then add `COSMOS_ENDPOINT` to your `.env` file."""))

# ============================================================
# Cell 4: Imports + env vars
# ============================================================
cells.append(code("""\
import os
import json
import asyncio
import nest_asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv("../../.env", override=True)

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
COSMOS_ENDPOINT = os.environ["COSMOS_ENDPOINT"]

print(f"Project:  {PROJECT_ENDPOINT}")
print(f"Model:    {MODEL_DEPLOYMENT}")
print(f"Cosmos:   {COSMOS_ENDPOINT}")"""))

# ============================================================
# Cell 5: Auth + Cosmos containers
# ============================================================
cells.append(code("""\
from azure.identity import AzureCliCredential
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

TENANT_ID = os.environ.get("AZURE_TENANT_ID", "16b3c013-d300-468d-ac64-7eda0820b6d3")
credential = AzureCliCredential()

# ─── Create Cosmos DB database and containers ───
async def setup_cosmos():
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        database = await cosmos.create_database_if_not_exists("travel-memory")
        chat_container = await database.create_container_if_not_exists(
            "chat-history",
            partition_key=PartitionKey(path="/conversation_id"),
        )
        episodic_container = await database.create_container_if_not_exists(
            "episodic-memory",
            partition_key=PartitionKey(path="/user_id"),
        )
        print(f"Database:  travel-memory")
        print(f"Container: chat-history       (partition: /conversation_id)")
        print(f"Container: episodic-memory    (partition: /user_id)")

asyncio.run(setup_cosmos())"""))

# ============================================================
# Cell 6: Part 1 heading
# ============================================================
cells.append(md("""\
---
## Part 1: The Naive Fix — Persist Every Message

Module 1's problem: session memory vanishes when the session ends.

The natural first idea: **save every chat message to a database**. The Agent Framework makes this easy — subclass `BaseHistoryProvider` and the framework automatically stores and reloads conversation history.

```
┌──────────────────────────────────────────┐
│           BaseHistoryProvider             │
│                                          │
│  before_run()  → loads saved messages    │
│  after_run()   → saves new messages      │
│                                          │
│  You implement:                          │
│    get_messages(session_id) → [Message]  │
│    save_messages(session_id, [Message])  │
└──────────────────────────────────────────┘
```

Every turn, `after_run` persists the user's input and the agent's response. On the next turn (or a new session with the same ID), `before_run` reloads the full history."""))

# ============================================================
# Cell 7: CosmosDBHistoryProvider
# ============================================================
cells.append(code("""\
from agent_framework import BaseHistoryProvider, Message, AgentSession

class CosmosDBHistoryProvider(BaseHistoryProvider):
    \"\"\"Persists every chat message to Cosmos DB.\"\"\"

    def __init__(self, container):
        super().__init__(source_id="cosmos_history")
        self.container = container

    async def get_messages(self, session_id, **kwargs):
        \"\"\"Load all messages for this conversation from Cosmos DB.\"\"\"
        if not session_id:
            return []
        query = "SELECT * FROM c WHERE c.conversation_id = @sid ORDER BY c._ts ASC"
        params = [{"name": "@sid", "value": session_id}]
        messages = []
        async for item in self.container.query_items(
            query=query, parameters=params, partition_key=session_id
        ):
            messages.append(Message.from_dict(item["message"]))
        return messages

    async def save_messages(self, session_id, messages, **kwargs):
        \"\"\"Save new messages to Cosmos DB — one document per message.\"\"\"
        if not session_id or not messages:
            return
        for msg in messages:
            doc = {
                "id": f"{session_id}-{uuid4().hex[:8]}",
                "conversation_id": session_id,
                "role": msg.role,
                "message": msg.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.container.upsert_item(doc)

print("CosmosDBHistoryProvider defined ✓")"""))

# ============================================================
# Cell 8: Demo — conversation with persistence
# ============================================================
cells.append(code("""\
SYSTEM_INSTRUCTIONS = \"\"\"You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.
Be concise and helpful.\"\"\"

SESSION_ID = "demo-session-1"

async def conversation_with_persistence():
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        database = cosmos.get_database_client("travel-memory")
        container = database.get_container_client("chat-history")

        history = CosmosDBHistoryProvider(container)
        session = AgentSession(session_id=SESSION_ID)

        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=SYSTEM_INSTRUCTIONS,
            context_providers=[history],
        )
        turns = [
            "Hi, I'm Sarah Chen from Engineering.",
            "I need to travel to New York next month for a conference.",
            "I prefer the Marriott and aisle seats on United.",
        ]
        for user_msg in turns:
            print(f"User: {user_msg}")
            response = await agent.run(user_msg, session=session)
            print(f"Agent: {response.text}\\n")

    print("\\n--- Every message saved to Cosmos DB ---")

asyncio.run(conversation_with_persistence())"""))

# ============================================================
# Cell 9: It works — now prove it survives restart
# ============================================================
cells.append(md("""\
### Does It Survive a Restart?

The messages are in Cosmos DB. Let's simulate a restart — create a **completely new agent** with the same session ID and see if it remembers."""))

# ============================================================
# Cell 10: Restart demo
# ============================================================
cells.append(code("""\
async def restart_demo():
    \"\"\"Brand new agent instance, same session ID — does it remember?\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        database = cosmos.get_database_client("travel-memory")
        container = database.get_container_client("chat-history")

        history = CosmosDBHistoryProvider(container)
        session = AgentSession(session_id=SESSION_ID)  # Same session ID

        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=SYSTEM_INSTRUCTIONS,
            context_providers=[history],
        )
        # Ask about info from the PREVIOUS session
        print("--- New agent instance, same session ID ---\\n")
        user_msg = "What's my name, where am I going, and what are my preferences?"
        print(f"User: {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"Agent: {response.text}")

asyncio.run(restart_demo())"""))

# ============================================================
# Cell 11: Celebration + transition
# ============================================================
cells.append(md("""\
### Persisted Chat History Works!

The agent remembered Sarah's name, destination, and preferences — all loaded from Cosmos DB. The `CosmosDBHistoryProvider` automatically:

1. **`before_run`** → loaded all saved messages for `demo-session-1`
2. **`after_run`** → saved the new user input and agent response

Problem solved? Not quite. Let's see what happens at scale."""))

# ============================================================
# Cell 12: Part 2 heading
# ============================================================
cells.append(md("""\
---
## Part 2: The Problem with Saving Everything

Our `CosmosDBHistoryProvider` works perfectly for a few turns. But Sarah is a frequent traveler — she's had dozens of conversations with the assistant over months. Let's simulate that."""))

# ============================================================
# Cell 13: Simulate months of chat history
# ============================================================
cells.append(code("""\
# Simulate 6 months of chat history: 20 conversations, ~10 messages each
SYNTHETIC_CONVERSATIONS = [
    ("conv-jan-nyc", "January NYC trip planning", [
        ("user", "I need to book a trip to New York for January 15-18."),
        ("assistant", "I'd be happy to help you plan your NYC trip for January 15-18. Let me look into flights and hotels for you."),
        ("user", "What are the flight options from Seattle?"),
        ("assistant", "I found several flights from Seattle to JFK. United has a direct flight UA101 departing at 8am for $460, and Delta has DL305 at 10am for $420."),
        ("user", "Go with United. What about hotels?"),
        ("assistant", "For hotels, the Marriott Times Square has rooms at $280/night, and the Hilton Midtown is $260/night."),
        ("user", "Marriott please. And can you check if the conference venue is nearby?"),
        ("assistant", "The Marriott Times Square is about a 10-minute walk from the Javits Center. I'll book the Marriott for 3 nights at $280/night."),
        ("user", "Perfect, book it all."),
        ("assistant", "All booked! United UA101 on Jan 15, returning UA103 on Jan 18. Marriott Times Square for 3 nights. Total: $1,300."),
    ]),
    ("conv-feb-budget", "February budget discussion", [
        ("user", "What's my travel budget looking like?"),
        ("assistant", "Looking at your recent trips, you've spent about $3,200 in Q4 last year."),
        ("user", "Is that within policy?"),
        ("assistant", "Yes, Senior Engineers have an annual travel budget of $15,000. You're well within that."),
        ("user", "OK great, thanks for checking."),
        ("assistant", "You're welcome! Let me know if you need anything else."),
    ]),
    ("conv-mar-london", "March London trip planning", [
        ("user", "I need to go to London for a client meeting March 20-25."),
        ("assistant", "I'll look into London flights and hotels for March 20-25."),
        ("user", "Last time the flight was really long. Any better options?"),
        ("assistant", "United has a direct flight from SFO at 6pm, arriving at Heathrow at 11am. About 10.5 hours. British Airways also has a similar route."),
        ("user", "Let's go with United again for the miles."),
        ("assistant", "Good call on the miles. For hotels, there's the Marriott Park Lane at £220/night or the Hilton London at £195/night."),
        ("user", "Marriott. Same chain loyalty points."),
        ("assistant", "Smart thinking. Booking: United direct to LHR March 20, returning March 25. Marriott Park Lane for 5 nights. Total: approximately $3,800."),
        ("user", "Also, do I need a visa?"),
        ("assistant", "US citizens don't need a visa for UK business trips under 6 months. You'll just need your passport."),
        ("user", "Thanks!"),
        ("assistant", "You're welcome! Have a great trip to London."),
    ]),
    ("conv-apr-expense", "April expense report help", [
        ("user", "I need help with my expense report for the London trip."),
        ("assistant", "Of course! I can see your London trip was March 20-25. What do you need help with?"),
        ("user", "What were the exact costs?"),
        ("assistant", "Flight: $2,450 (United round trip). Hotel: $1,450 (Marriott Park Lane, 5 nights). Total: $3,900."),
        ("user", "Were there any meal expenses I should add?"),
        ("assistant", "You had a per diem allowance of $75/day for London, which gives you $375 for 5 days."),
        ("user", "Great, that covers it."),
        ("assistant", "I'll note that down. Your total London trip expense report should be $4,275."),
    ]),
    ("conv-may-cancel", "May trip cancellation", [
        ("user", "I need to cancel my Chicago trip next week."),
        ("assistant", "I see you have a Chicago trip booked for next week. I'll start the cancellation process. What's the reason?"),
        ("user", "The meeting got moved to a video call instead."),
        ("assistant", "Understood. I'll cancel the United flight and Hilton reservation. The flight has a cancellation fee of $150."),
        ("user", "That's fine, go ahead."),
        ("assistant", "Done. Flight and hotel cancelled. $150 cancellation fee applied. You'll get a credit for the hotel."),
    ]),
    ("conv-jun-team", "June team offsite discussion", [
        ("user", "We're planning a team offsite in Austin. 8 people, June 15-17."),
        ("assistant", "A team offsite in Austin sounds great! For 8 people over June 15-17, I'll look into group rates."),
        ("user", "We need a hotel with a meeting room."),
        ("assistant", "The Hilton Austin has group rates at $189/person/night and includes a meeting room for groups of 8+."),
        ("user", "What about flights for everyone from Seattle?"),
        ("assistant", "Southwest has the best group rates from Seattle to Austin. About $320 round trip per person."),
        ("user", "Can you send me a summary I can share with the team?"),
        ("assistant", "Here's the summary: Austin offsite, June 15-17. Hilton Austin at $189/night/person. Southwest flights at ~$320/person. Total estimate: ~$5,600 for 8 people."),
        ("user", "Looks good. I'll get budget approval and come back."),
        ("assistant", "Sounds like a plan! Let me know once you have approval and I'll make the bookings."),
    ]),
]

async def simulate_months_of_history():
    \"\"\"Write synthetic conversations to Cosmos DB to simulate scale.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        container = cosmos.get_database_client("travel-memory").get_container_client("chat-history")

        total_messages = 0
        for conv_id, description, messages in SYNTHETIC_CONVERSATIONS:
            for i, (role, content) in enumerate(messages):
                doc = {
                    "id": f"{conv_id}-{i:03d}",
                    "conversation_id": conv_id,
                    "role": role,
                    "message": Message("user" if role == "user" else "assistant", [content]).to_dict(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await container.upsert_item(doc)
                total_messages += 1
        print(f"Loaded {len(SYNTHETIC_CONVERSATIONS)} conversations, {total_messages} messages")

asyncio.run(simulate_months_of_history())"""))

# ============================================================
# Cell 14: Show the bloat
# ============================================================
cells.append(code("""\
async def show_the_bloat():
    \"\"\"Count ALL messages across ALL conversations in chat-history.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        container = cosmos.get_database_client("travel-memory").get_container_client("chat-history")

        # Count everything
        total = 0
        conversations = set()
        total_chars = 0
        async for item in container.read_all_items():
            total += 1
            conversations.add(item["conversation_id"])
            if "message" in item:
                msg = Message.from_dict(item["message"])
                total_chars += len(msg.text)

        estimated_tokens = total_chars // 4  # rough estimate

        print(f"Total messages in chat-history:  {total}")
        print(f"Across conversations:            {len(conversations)}")
        print(f"Total characters:                {total_chars:,}")
        print(f"Estimated tokens:                ~{estimated_tokens:,}")
        print()

        # Now try to answer a simple question from this data
        print("--- Try to find: 'What hotel did Sarah like in NYC?' ---")
        print()
        nyc_hits = 0
        async for item in container.query_items(
            query="SELECT c.conversation_id, c.role, c.message FROM c WHERE CONTAINS(LOWER(c.message.contents[0].text), 'marriott')",
        ):
            nyc_hits += 1
            msg = Message.from_dict(item["message"])
            print(f"  [{item['conversation_id']}] {item['role']}: {msg.text[:80]}...")
        print(f"\\n  Found {nyc_hits} messages mentioning 'marriott' — scattered across conversations.")
        print("  No structure, no ratings, no way to rank which trip mattered most.")

asyncio.run(show_the_bloat())"""))

# ============================================================
# Cell 15: Three problems explained
# ============================================================
cells.append(md("""\
### Three Problems with Persisted Chat History

| Problem | Description |
|---------|-------------|
| **Bloat** | Hundreds of messages for information that could fit in a few structured records |
| **Noise** | Small talk, corrections, tangents — all stored with equal weight |
| **Unqueryable** | "What hotel did she like in NYC?" requires searching raw text across conversations |

Persisted chat history is great for **audit trails** — you can always replay what was said. But it's a terrible way to build **intelligence**. The agent can't efficiently extract meaning from a wall of raw messages.

### "But What About Vector Search?"

You might think: *"Just add embeddings and do vector search over the messages."* Cosmos DB even supports this natively. But vector search only addresses one of the three problems:

| Problem | Does vector search help? |
|---------|---------------------------|
| **Bloat** | ❌ No — you still store and embed every message. The data keeps growing. |
| **Noise** | ❌ No — "sure, book it" and "thanks!" get embedded alongside useful content |
| **Unqueryable** | ✅ Partly — semantic matching helps, but returns raw text, not structured fields. You can't filter by rating > 4 or sort by cost. |

Vector search is a retrieval technique, not a memory architecture. It helps you *find* messages, but doesn't help you *understand* them. You still end up injecting raw conversation fragments into the agent's context.

### Context Is a Scarce Resource

Every LLM has a finite context window. Every token you spend on noise is a token you can't spend on useful context — the user's current request, relevant policies, structured data.

> **Rule of thumb**: Be deliberate about what you load into an agent's context. Context window tokens are a scarce resource — fill them with signal, not noise.

### If This Sounds Familiar…

This is the same trade-off as **virtual memory paging** in an operating system:

| OS Paging | Agent Memory |
|-----------|-------------|
| **RAM** (fast, limited) | Last N messages in the context window |
| **Disk** (slow, large) | Episodic memory in the database |
| **Page fault** → load from disk | Agent calls `recall_events` when it needs older context |
| **LRU eviction** | Oldest messages drop out of the sliding window |

Keep the most recent conversation in the "fast" context window. When the agent needs something older — "what hotel did I like in London?" — it "page faults" by calling a tool, which pulls structured data from the database on demand. Same principle, different layer of the stack."""))

# ============================================================
# Cell 16: The insight
# ============================================================
cells.append(md("""\
### What If We Could Be Selective?

Instead of saving every message, what if the agent could **decide what's worth remembering** and store it in a structured way?

```
Chat History (saves everything):          Episodic Memory (saves what matters):
─────────────────────────────             ─────────────────────────────────────
"Hi, I'm Sarah"                           Event: NYC trip, Oct 2025
"Hello Sarah!"                              Hotel: Marriott Times Square
"I need to go to NYC"                       Rating: ★★★★★
"Sure, when?"                               Note: "Great location, close to venue"
"October 15-18"
"Let me check flights..."                 Event: London trip, Nov 2025
"United has UA101 at 8am"                   Hotel: Marriott Park Lane
"Book it"                                   Rating: ★★★★
"What about hotels?"                        Note: "Long flight but productive"
"Marriott is $280/night"
"Book it"
"All set!"
...12 messages                            ...2 records
```

This is **episodic memory** — storing curated events instead of raw conversation."""))

# ============================================================
# Cell 17: Part 3 heading
# ============================================================
cells.append(md("""\
---
## Part 3: Episodic Memory — Remembering What Matters

**Episodic memory** stores specific events and experiences as structured records. It answers questions like:
- "What happened last time I went to NYC?"
- "Which hotels have I stayed at?"
- "How was my London trip?"

The key difference from chat history: the **agent decides** what's worth remembering and stores it as a searchable event — not as raw conversation text.

### The Pattern: `@tool`

We give the agent two tools:
- **`remember_event`** — store a structured event (agent calls this when something significant happens)
- **`recall_events`** — search past events (agent calls this when it needs historical context)

The agent uses judgment about **when** to call these tools. This selectivity is the whole point."""))

# ============================================================
# Cell 18: Episodic memory tools
# ============================================================
cells.append(code("""\
from agent_framework import tool

# We'll use a module-level container reference for the tools
_episodic_container = None

def set_episodic_container(container):
    global _episodic_container
    _episodic_container = container

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
        details: Optional JSON string with structured data (dates, costs, ratings)
    \"\"\"
    event = {
        "id": f"{user_id}-{uuid4().hex[:8]}",
        "user_id": user_id,
        "event_type": event_type,
        "description": description,
        "details": json.loads(details) if details else {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await _episodic_container.upsert_item(event)
    return f"Remembered: {description}"


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
    sql = "SELECT * FROM c WHERE c.user_id = @uid"
    params = [{"name": "@uid", "value": user_id}]

    if event_type:
        sql += " AND c.event_type = @etype"
        params.append({"name": "@etype", "value": event_type})
    if query:
        sql += " AND CONTAINS(LOWER(c.description), @q)"
        params.append({"name": "@q", "value": query.lower()})

    sql += " ORDER BY c.timestamp DESC"

    events = []
    async for item in _episodic_container.query_items(
        query=sql, parameters=params, partition_key=user_id
    ):
        events.append({
            "event_type": item["event_type"],
            "description": item["description"],
            "details": item.get("details", {}),
            "timestamp": item["timestamp"],
        })
        if len(events) >= limit:
            break

    return json.dumps(events, indent=2) if events else "No matching events found."

print("Episodic memory tools defined: remember_event, recall_events ✓")"""))

# ============================================================
# Cell 19: Pre-load past trips as episodic events
# ============================================================
cells.append(code("""\
async def preload_episodic_events():
    \"\"\"Load past trips from data file as episodic memory events.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        container = cosmos.get_database_client("travel-memory").get_container_client("episodic-memory")

        with open("../../data/past_trips.json") as f:
            trips = json.load(f)

        for trip in trips:
            event = {
                "id": f"trip-{trip['trip_id']}",
                "user_id": trip["employee_id"],
                "event_type": "trip",
                "description": (
                    f"{trip['destination']} trip for {trip['purpose']} "
                    f"({trip['departure_date']} to {trip['return_date']})"
                ),
                "details": {
                    "destination": trip["destination"],
                    "purpose": trip["purpose"],
                    "dates": f"{trip['departure_date']} to {trip['return_date']}",
                    "hotel_id": trip["hotel"]["hotel_id"],
                    "total_cost": trip["total_cost"],
                    "rating": trip["rating"],
                    "notes": trip["notes"],
                },
                "timestamp": trip["departure_date"] + "T00:00:00",
            }
            await container.upsert_item(event)
            print(f"  Loaded: {event['description']}")

    print(f"\\nLoaded {len(trips)} trips as episodic events")

asyncio.run(preload_episodic_events())"""))

# ============================================================
# Cell 20: Create agent with episodic tools
# ============================================================
cells.append(code("""\
EPISODIC_INSTRUCTIONS = \"\"\"You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.

You have access to the employee's episodic memory — their past trips and experiences.
When planning new trips:
1. Use recall_events to check if they've been to this destination before
2. Reference past experiences to make better recommendations
3. Use remember_event to store significant outcomes after bookings

The current user is Sarah Chen (employee ID: E001, based in Seattle, USA).
Be concise and helpful.\"\"\"

async def demo_episodic_recall():
    \"\"\"Show the agent using episodic memory to recall past trips.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        container = cosmos.get_database_client("travel-memory").get_container_client("episodic-memory")
        set_episodic_container(container)

        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=EPISODIC_INSTRUCTIONS,
            tools=[remember_event, recall_events],
        )
        user_msg = "I'm planning another trip to New York. What do you know about my past NYC trips?"
        print(f"User: {user_msg}\\n")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}")

asyncio.run(demo_episodic_recall())"""))

# ============================================================
# Cell 21: What happened
# ============================================================
cells.append(md("""\
### What Just Happened

The agent:
1. Received the user's question about NYC
2. **Decided** to call `recall_events(user_id="E001", query="new york")` — its own judgment
3. Retrieved structured records: destinations, ratings, costs, notes
4. Used that context to give a personalized, informed response

Compare this to searching through hundreds of raw chat messages. The episodic events are:
- **Structured** — fields like `rating`, `hotel_id`, `total_cost`
- **Queryable** — filter by destination, event type, date range
- **Compact** — one record per trip instead of dozens of messages"""))

# ============================================================
# Cell 22: Demo — agent remembers a new event
# ============================================================
cells.append(code("""\
async def demo_episodic_store():
    \"\"\"Show the agent storing a new episodic event.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        container = cosmos.get_database_client("travel-memory").get_container_client("episodic-memory")
        set_episodic_container(container)

        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=EPISODIC_INSTRUCTIONS,
            tools=[remember_event, recall_events],
        )
        user_msg = (
            "I just got back from a conference in Chicago. The Palmer House Hilton was amazing — "
            "5 stars. Great location, walking distance to the venue. Total cost was $1,850."
        )
        print(f"User: {user_msg}\\n")
        response = await agent.run(user_msg)
        print(f"Agent: {response.text}")

asyncio.run(demo_episodic_store())"""))

# ============================================================
# Cell 23: Verify the stored event
# ============================================================
cells.append(code("""\
async def verify_stored_event():
    \"\"\"Check what the agent stored in episodic memory.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        container = cosmos.get_database_client("travel-memory").get_container_client("episodic-memory")

        print("--- Sarah's episodic memory (most recent first) ---\\n")
        events = []
        async for item in container.query_items(
            query="SELECT * FROM c WHERE c.user_id = 'E001' ORDER BY c.timestamp DESC",
            partition_key="E001",
        ):
            events.append(item)

        for e in events:
            details = e.get("details", {})
            rating = details.get("rating", "—")
            cost = details.get("total_cost", "—")
            print(f"  [{e['event_type']}] {e['description']}")
            print(f"           Rating: {rating}  Cost: ${cost}")
            print()

        print(f"Total episodic events for Sarah: {len(events)}")

asyncio.run(verify_stored_event())"""))

# ============================================================
# Cell 24: Side-by-side comparison
# ============================================================
cells.append(code("""\
async def compare_approaches():
    \"\"\"Compare chat history vs episodic memory for answering the same question.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        db = cosmos.get_database_client("travel-memory")
        chat_container = db.get_container_client("chat-history")
        episodic_container = db.get_container_client("episodic-memory")

        # Chat history approach: search raw messages
        print("═" * 60)
        print("APPROACH 1: Search Chat History for 'NYC hotel'")
        print("═" * 60)
        chat_hits = 0
        chat_chars = 0
        async for item in chat_container.query_items(
            query=("SELECT * FROM c WHERE "
                   "CONTAINS(LOWER(c.message.contents[0].text), 'marriott') OR "
                   "CONTAINS(LOWER(c.message.contents[0].text), 'new york') OR "
                   "CONTAINS(LOWER(c.message.contents[0].text), 'nyc')"),
        ):
            chat_hits += 1
            msg = Message.from_dict(item["message"])
            chat_chars += len(msg.text)

        print(f"  Messages found:  {chat_hits}")
        print(f"  Characters:      {chat_chars:,}")
        print(f"  Tokens (est):    ~{chat_chars // 4:,}")
        print(f"  Structured?      No — raw conversation text")
        print(f"  Has ratings?     No — buried in natural language")

        # Episodic approach: query structured events
        print()
        print("═" * 60)
        print("APPROACH 2: Query Episodic Memory for NYC trips")
        print("═" * 60)
        ep_hits = 0
        ep_chars = 0
        async for item in episodic_container.query_items(
            query="SELECT * FROM c WHERE c.user_id = 'E001' AND CONTAINS(LOWER(c.description), 'new york')",
            partition_key="E001",
        ):
            ep_hits += 1
            ep_chars += len(json.dumps(item.get("details", {})))
            details = item.get("details", {})
            print(f"  → {item['description']}")
            print(f"    Rating: {details.get('rating', '—')}  Cost: ${details.get('total_cost', '—')}")

        print(f"\\n  Events found:    {ep_hits}")
        print(f"  Characters:      {ep_chars:,}")
        print(f"  Tokens (est):    ~{ep_chars // 4:,}")
        print(f"  Structured?      Yes — typed fields, queryable")
        print(f"  Has ratings?     Yes — directly accessible")

asyncio.run(compare_approaches())"""))

# ============================================================
# Cell 25: Part 4 heading — Better Together
# ============================================================
cells.append(md("""\
---
## Part 4: Better Together

We've seen two approaches in isolation. In production, you'll typically use **both**:

- **`BaseHistoryProvider`** → automatic conversation persistence (audit trail, continuity)
- **`@tool` episodic memory** → selective, structured knowledge (intelligence)

They serve different roles and complement each other. Let's see them working side by side."""))

# ============================================================
# Cell 26: Combined demo
# ============================================================
cells.append(code("""\
COMBINED_SESSION_ID = "demo-combined-1"

async def demo_combined_memory():
    \"\"\"Agent with BOTH persistent history AND episodic memory tools.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        db = cosmos.get_database_client("travel-memory")
        chat_container = db.get_container_client("chat-history")
        episodic_container = db.get_container_client("episodic-memory")

        history = CosmosDBHistoryProvider(chat_container)
        set_episodic_container(episodic_container)
        session = AgentSession(session_id=COMBINED_SESSION_ID)

        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=EPISODIC_INSTRUCTIONS,
            tools=[remember_event, recall_events],
            context_providers=[history],
        )
        turns = [
            "Hi, I'm Sarah Chen (E001). I need to plan a trip to Tokyo next month.",
            "Can you check my past trips for any Asia travel experience?",
            "Book the ANA flight and the Tokyo Marriott please.",
        ]
        for user_msg in turns:
            print(f"User: {user_msg}")
            response = await agent.run(user_msg, session=session)
            print(f"Agent: {response.text}\\n")

    print("--- Conversation persisted to chat-history, episodic memory available throughout ---")

asyncio.run(demo_combined_memory())"""))

# ============================================================
# Cell 27: Combined resume demo
# ============================================================
cells.append(code("""\
async def demo_combined_resume():
    \"\"\"New agent, same session — needs BOTH memory systems to answer.\"\"\"
    async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
        db = cosmos.get_database_client("travel-memory")
        chat_container = db.get_container_client("chat-history")
        episodic_container = db.get_container_client("episodic-memory")

        history = CosmosDBHistoryProvider(chat_container)
        set_episodic_container(episodic_container)
        session = AgentSession(session_id=COMBINED_SESSION_ID)

        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            ),
            name="TravelAssistant",
            instructions=EPISODIC_INSTRUCTIONS,
            tools=[remember_event, recall_events],
            context_providers=[history],
        )
        print("--- New agent, same session ID ---\\n")
        user_msg = (
            "Remind me what hotel we just booked for Tokyo, "
            "and how was my last NYC trip?"
        )
        print(f"User: {user_msg}\\n")
        response = await agent.run(user_msg, session=session)
        print(f"Agent: {response.text}")

asyncio.run(demo_combined_resume())"""))

# ============================================================
# Cell 28: Explanation
# ============================================================
cells.append(md("""\
### Two Memory Systems, One Agent

The agent answered using **both** systems:

| Question | Source | How |
|----------|--------|-----|
| "What hotel did we book for Tokyo?" | **Chat history** | `BaseHistoryProvider` reloaded the previous conversation |
| "How was my last NYC trip?" | **Episodic memory** | Agent called `recall_events(user_id="E001", query="new york")` |

```
┌──────────────────────────────────────────────────────────┐
│                    Travel Assistant                       │
│                                                          │
│  context_providers=[history]    tools=[remember, recall] │
│          │                              │                │
│          ▼                              ▼                │
│  ┌──────────────┐              ┌─────────────────┐       │
│  │ Chat History  │              │ Episodic Memory │       │
│  │ (automatic)   │              │ (selective)     │       │
│  │  every turn   │              │  curated events │       │
│  │  raw messages │              │  structured     │       │
│  └──────────────┘              └─────────────────┘       │
│         │                              │                 │
│         ▼                              ▼                 │
│     Cosmos DB                     Cosmos DB              │
│   chat-history                  episodic-memory          │
└──────────────────────────────────────────────────────────┘
```

The `BaseHistoryProvider` gives **continuity** — the agent can resume conversations. The `@tool` episodic memory gives **intelligence** — the agent can learn from the past."""))

# ============================================================
# Cell 29: Summary
# ============================================================
cells.append(md("""\
---
## Summary

### Two Approaches to Persistence

| | Chat History | Episodic Memory |
|---|---|---|
| **What's stored** | Every message, every turn | Curated events and outcomes |
| **Who decides** | Automatic (framework) | Agent judgment (`@tool`) |
| **Structure** | Raw text | Typed fields (rating, cost, dates) |
| **Queryable** | Text search only | Filter by type, destination, date |
| **Scales** | Grows with every conversation | Grows with significant events |
| **Best for** | Audit trails, compliance | Intelligence, recommendations |

### Key Insights

1. **Chat history is for audit, episodic memory is for intelligence.** Persisted conversations tell you what was *said*. Episodic events tell you what *happened* and what it *means*.

2. **Context is a scarce resource.** Every LLM has a finite context window. Be deliberate about what you load — fill it with signal, not noise.

3. **Use both.** A `BaseHistoryProvider` for continuity and compliance. `@tool` episodic memory for the agent's working knowledge. They complement each other."""))

# ============================================================
# Cell 30: What's next + cleanup
# ============================================================
cells.append(md("""\
---
## What's Next

Episodic memory captures **events** — things that happened. But what about **facts**?

- "Sarah prefers aisle seats" isn't an event — it's a persistent fact.
- "Sarah's manager is Michael Torres" is a relationship, not an episode.

In **Module 3: Semantic Memory**, we'll add a memory system for facts, preferences, and relationships — the kind of knowledge that's always true (until it changes)."""))

# ============================================================
# Cell 31: Cleanup helper
# ============================================================
cells.append(code("""\
# Optional: Clean up Cosmos DB containers
# Uncomment and run to delete all data created in this module

# async def cleanup():
#     async with CosmosClient(COSMOS_ENDPOINT, credential=credential) as cosmos:
#         db = cosmos.get_database_client("travel-memory")
#         # Delete containers
#         await db.delete_container("chat-history")
#         await db.delete_container("episodic-memory")
#         print("Cleaned up: chat-history and episodic-memory containers deleted")
#
# asyncio.run(cleanup())"""))

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

output_path = "02_episodic_memory.ipynb"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print(f"Built {output_path}: {len(cells)} cells")

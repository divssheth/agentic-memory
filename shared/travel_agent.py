"""Shared travel agent — reusable across all modules."""

import json
import os
from pathlib import Path

from azure.identity import AzureCliCredential
from dotenv import load_dotenv

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient

# ---------------------------------------------------------------------------
# Data (loaded once at import time)
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data"
flights = json.loads((_DATA_DIR / "flights.json").read_text(encoding="utf-8"))
hotels = json.loads((_DATA_DIR / "hotels.json").read_text(encoding="utf-8"))
policies = json.loads((_DATA_DIR / "travel_policies.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


CITY_TO_CODES = {
    "new york": "JFK", "nyc": "JFK", "jfk": "JFK",
    "london": "LHR", "heathrow": "LHR", "lhr": "LHR",
    "tokyo": "NRT", "narita": "NRT", "nrt": "NRT",
    "seattle": "SEA", "sea": "SEA",
    "san francisco": "SFO", "sf": "SFO", "sfo": "SFO",
}


@tool
async def search_flights(destination: str) -> str:
    """Search available flights to a destination city or airport code."""
    key = destination.lower().strip()
    code = CITY_TO_CODES.get(key, key.upper())
    results = [f for f in flights if f["destination"].upper() == code
               or destination.lower() in f.get("destination", "").lower()]
    if not results:
        return f"No flights found to {destination}"
    return json.dumps(results[:3], indent=2)


@tool
async def search_hotels(city: str) -> str:
    """Search available hotels in a city."""
    results = [h for h in hotels if city.lower() in h["city"].lower()]
    if not results:
        return f"No hotels found in {city}"
    return json.dumps(results[:3], indent=2)


@tool
async def get_travel_policy(employee_level: str) -> str:
    """Get travel policy rules for an employee level (e.g. Junior, Senior, Director)."""
    level_policies = policies.get("by_level", {}).get(employee_level, {})
    if not level_policies:
        return f"No policy found for level: {employee_level}"
    return json.dumps(level_policies, indent=2)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a corporate travel assistant for Contoso Corp.
Help employees book business travel including flights and hotels.
Use the available tools to search for real options.
Be concise and helpful."""


def create_client(env_path: str = "../.env"):
    """Load env vars, return (FoundryChatClient, AzureCliCredential)."""
    load_dotenv(env_path, override=True)
    credential = AzureCliCredential()
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("FOUNDRY_MODEL", "gpt-4o"),
        credential=credential,
    )
    return client, credential


def create_travel_agent(client: FoundryChatClient) -> Agent:
    """Create the standard travel agent with all tools."""
    return Agent(
        client=client,
        name="TravelAssistant",
        instructions=SYSTEM_PROMPT,
        tools=[search_flights, search_hotels, get_travel_policy],
    )

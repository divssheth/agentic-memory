"""Module 3 — Memory Lifecycle utilities.

Grouped by the notebook that introduces each piece:

    3.2 Identification    MemoryDecision, MemoryCandidate
    3.3 Staged promotion  PromotionConfig, CosmosPromotionStore
    3.4 Belief revision   CosmosBeliefStore
    3.5 Retention         MemoryState, MemoryItem, RetentionScorer, CosmosRetentionStore
    Notebook setup        setup_backends, create_baseline_agent

Every Cosmos-backed store wraps a ``SemanticMemoryStore`` (shared/semantic_store.py)
that is bound to a single user, so all reads and writes stay in that user's partition.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
import uuid

TRUST_STATES = ["trusted", "provisional"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(days: float) -> str:
    return (_now() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# 3.2 Identification
# ---------------------------------------------------------------------------

class MemoryDecision(Enum):
    MEMORISE = "memorise"
    DISCARD = "discard"
    ASK_USER = "ask_user"


@dataclass
class MemoryCandidate:
    """Result of scoring one conversation turn for memorability (each score 0-1)."""
    content: str
    category: str  # preference | fact | event | procedure
    durability: float = 0.0
    reusability: float = 0.0
    user_specificity: float = 0.0
    actionability: float = 0.0
    decision: MemoryDecision = MemoryDecision.DISCARD
    reasoning: str = ""

    @property
    def composite_score(self) -> float:
        return (self.durability + self.reusability +
                self.user_specificity + self.actionability) / 4.0


# ---------------------------------------------------------------------------
# 3.3 Staged promotion
# ---------------------------------------------------------------------------

@dataclass
class PromotionConfig:
    confirmation_threshold: int = 2   # confirmations to reach trusted
    provisional_threshold: int = 1    # confirmations to reach provisional
    staleness_days: int = 180         # trusted but unconfirmed this long -> provisional


class CosmosPromotionStore:
    """Trust states (candidate -> provisional -> trusted) on preference documents.

    Recall filters on ``state``, so an untrusted write never reaches the model.
    """

    def __init__(self, store, config: PromotionConfig = None):
        self._s = store
        self.config = config or PromotionConfig()

    async def reset(self) -> int:
        """Delete this scope's preferences so demo re-runs start clean."""
        return await self._s.reset()

    async def record(self, category, preference, source_type, confidence=0.7) -> str:
        """Store a preference: user assertions start provisional, everything else candidate."""
        state = "provisional" if source_type == "user_assertion" else "candidate"
        await self._s.add_preference(category, preference, confidence, source_type, state)
        return state

    async def record_trusted(self, category, preference, confidence=0.9) -> None:
        """The anti-pattern: trust on first write."""
        await self._s.add_preference(category, preference, confidence,
                                     "tool_output", "trusted")

    async def confirm(self, preference) -> dict:
        """Record one confirmation (matched by semantic search) and promote."""
        result = await self._s.confirm(
            preference,
            provisional_threshold=self.config.provisional_threshold,
            trusted_threshold=self.config.confirmation_threshold,
        )
        return result or {"state": None, "confirmations": 0}

    async def snapshot(self) -> list[dict]:
        docs = await self._s.snapshot()
        return [{"preference": d["preference"], "state": d["state"],
                 "confirmations": d.get("confirmation_count", 0),
                 "source_type": d.get("source_type", "")} for d in docs]

    async def staleness_sweep(self) -> int:
        """Demote trusted memories not confirmed within the staleness window."""
        ids = await self._s.stale_trusted_ids(_ago(self.config.staleness_days))
        for doc_id in ids:
            await self._s.set_state(doc_id, "provisional")
        return len(ids)

    async def gated_recall(self, query) -> str:
        """Recall only trusted (as fact) and provisional (as likely) preferences."""
        results = await self._s.search(query, states=TRUST_STATES)
        if not results:
            return "No trusted preferences to share yet."
        tags = {"trusted": "[KNOWN FACT]",
                "provisional": "[LIKELY - confirm before assuming]"}
        return "\n".join(f"{tags[r['state']]} {r['preference']}" for r in results)

    async def recall_all(self, query) -> str:
        """Ungated recall: every current preference is presented as fact."""
        results = await self._s.search(query)
        if not results:
            return "No preferences found."
        return "\n".join(f"[FACT] {r['preference']}" for r in results)

    async def backdate(self, preference_text, days) -> None:
        """Test helper: pretend the closest match was last confirmed `days` ago."""
        results = await self._s.search(preference_text, top_k=1)
        if results:
            await self._s.update_fields(results[0]["id"], {"last_confirmed": _ago(days)})


# ---------------------------------------------------------------------------
# 3.4 Belief revision
# ---------------------------------------------------------------------------

class CosmosBeliefStore:
    """SCD Type 2 belief revision: superseded values are retired, never deleted.

    Supersession itself happens in ``SemanticMemoryStore.add_preference``; this
    class adds current-value, point-in-time and history views on top.
    """

    def __init__(self, store):
        self._s = store

    async def reset(self) -> int:
        """Delete this scope's preferences so demo re-runs start clean."""
        return await self._s.reset()

    async def store(self, category: str, preference: str,
                    source_type: str = "user_assertion") -> dict:
        """Store a belief, superseding a conflicting current value in the category."""
        existing = await self._s.get_current(category)
        doc = await self._s.add_preference(category, preference, 0.8, source_type)
        superseded = None
        if existing and existing["preference"].lower() != preference.lower():
            superseded = existing["preference"]
        return {"preference": preference, "state": doc["state"], "superseded": superseded}

    async def recall_current(self, query: str) -> str:
        results = await self._s.search(query, states=TRUST_STATES)
        if not results:
            return "No current beliefs found."
        tags = {"trusted": "[KNOWN]", "provisional": "[LIKELY]"}
        return "\n".join(f"{tags[r['state']]} {r['preference']}" for r in results)

    async def recall_at_time(self, query: str, iso_date: str) -> str:
        """Time travel: beliefs that were valid on ``iso_date``."""
        results = await self._s.search(query, current_only=False, top_k=20)
        valid = [r for r in results
                 if r.get("valid_from", "") <= iso_date
                 and (r.get("valid_to") is None or r["valid_to"] > iso_date)]
        if not valid:
            return f"No beliefs found valid at {iso_date}."
        return "\n".join(
            f"{r['preference']} (valid {r['valid_from'][:10]} → "
            f"{r['valid_to'][:10] if r['valid_to'] else 'present'})"
            for r in valid
        )

    async def history(self, category: str) -> list[dict]:
        return await self._s.history(category)

    async def snapshot(self) -> list[dict]:
        return await self._s.snapshot(include_deprecated=False)


# ---------------------------------------------------------------------------
# 3.5 Retention
# ---------------------------------------------------------------------------

class MemoryState(Enum):
    CANDIDATE = "candidate"       # stored, not used in decisions
    PROVISIONAL = "provisional"   # used with hedging
    TRUSTED = "trusted"           # used as fact
    DEPRECATED = "deprecated"     # kept for history only


@dataclass
class MemoryItem:
    """In-memory view of a preference with the signals the retention scorer needs."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    content: str = ""
    category: str = ""
    state: MemoryState = MemoryState.CANDIDATE
    confidence: float = 0.5
    confirmation_count: int = 0
    first_seen: datetime = field(default_factory=_now)
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    success_correlation: float = 0.0


class RetentionScorer:
    """Scores memories for retention; the lowest scores are evicted first."""

    DEFAULT_WEIGHTS = {
        "recency": 0.20,
        "access_frequency": 0.15,
        "success": 0.25,
        "redundancy_penalty": 0.15,  # not computed yet, so it contributes 0
        "specificity": 0.10,
        "utility": 0.15,
    }
    STATE_UTILITY = {MemoryState.TRUSTED: 0.8, MemoryState.PROVISIONAL: 0.5,
                     MemoryState.CANDIDATE: 0.2}

    def __init__(self, weights: dict = None, capacity: int = 500,
                 half_life_days: float = 30.0):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.capacity = capacity
        self.half_life_days = half_life_days

    def _decay(self, since: datetime) -> float:
        age_days = (_now() - since).total_seconds() / 86400.0
        return math.exp(-0.693 * age_days / self.half_life_days)

    def score(self, memory: MemoryItem) -> float:
        """Higher means keep longer."""
        recency = self._decay(memory.first_seen)
        access = min(memory.access_count / 10.0, 1.0)
        if memory.last_accessed:
            access *= self._decay(memory.last_accessed)
        specificity = min(len(memory.content) / 200.0, 1.0)
        utility = (self.STATE_UTILITY.get(memory.state, 0.0)
                   + min(memory.confirmation_count * 0.1, 0.2))
        w = self.weights
        return (w["recency"] * recency
                + w["access_frequency"] * access
                + w["success"] * memory.success_correlation
                + w["specificity"] * specificity
                + w["utility"] * utility)


def _parse_dt(value) -> datetime:
    # Documents written before retention tracking existed are treated as 90 days old.
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _now() - timedelta(days=90)


class CosmosRetentionStore:
    """Scores preference documents, writes scores back and deprecates the lowest."""

    def __init__(self, store, scorer: RetentionScorer = None, capacity: int = 50):
        self._s = store
        self.scorer = scorer or RetentionScorer(capacity=capacity)
        self.capacity = capacity

    async def reset(self) -> int:
        """Delete this scope's demo preferences so re-runs start clean."""
        return await self._s.reset()

    cleanup_scope = reset

    async def add_preference(self, category: str, preference: str,
                             state: str = "candidate", access_count: int = 0,
                             success_correlation: float = 0.0,
                             age_days: int = 0) -> str:
        """Demo helper: add a preference with simulated age and usage."""
        doc = await self._s.add_preference(category, preference, 0.7,
                                           "llm_inference", state)
        fields = {"first_seen": _ago(age_days), "access_count": access_count,
                  "success_correlation": success_correlation}
        if access_count > 0:
            fields["last_accessed"] = _ago(int(age_days * 0.3))
        await self._s.update_fields(doc["id"], fields)
        return doc["id"]

    async def score_all(self) -> list[dict]:
        """Score every active preference, ascending (evict first)."""
        scored = []
        for d in await self._s.snapshot(include_deprecated=False):
            if d.get("valid_to") is not None:
                continue
            item = MemoryItem(
                id=d["id"], content=d.get("preference", ""),
                state=MemoryState(d.get("state") or "candidate"),
                access_count=d.get("access_count") or 0,
                success_correlation=d.get("success_correlation") or 0.0,
                first_seen=_parse_dt(d.get("first_seen")),
                last_accessed=_parse_dt(d.get("last_accessed")),
                confirmation_count=d.get("confirmation_count") or 0,
            )
            score = self.scorer.score(item)
            scored.append({"id": d["id"], "preference": d["preference"],
                           "state": d["state"], "score": score})
            await self._s.update_fields(d["id"], {"retention_score": score,
                                                  "last_scored": _now().isoformat()})
        return sorted(scored, key=lambda x: x["score"])

    async def evict(self, count: int) -> list[dict]:
        """Deprecate the ``count`` lowest-scored preferences."""
        to_evict = (await self.score_all())[:count]
        for item in to_evict:
            await self._s.set_state(item["id"], "deprecated")
            item["state"] = "deprecated"
        return to_evict

    async def snapshot(self) -> list[dict]:
        return [{"preference": d["preference"], "state": d["state"],
                 "score": d.get("retention_score") or 0,
                 "access_count": d.get("access_count") or 0,
                 "success_correlation": d.get("success_correlation") or 0}
                for d in await self._s.snapshot(include_deprecated=True)]

    async def active_count(self) -> int:
        return await self._s.count(current_only=True)


# ---------------------------------------------------------------------------
# Notebook setup
# ---------------------------------------------------------------------------

def create_baseline_agent(
    client,
    *,
    semantic_store=None,
    search_client=None,
    openai_client=None,
    embedding_model: str = "text-embedding-ada-002",
    extra_tools: list = None,
    instructions_suffix: str = "",
    context_providers: list = None,
    middleware: list = None,
    name: str = "TravelAssistant",
):
    """Travel agent with semantic memory and policy RAG but no lifecycle management.

    Memory tools come from ``make_preference_tools(semantic_store)``, so they are
    bound to the store's user. Policy search uses hybrid (keyword + vector) search.
    """
    from agent_framework import Agent, tool
    from shared.memory_tools import make_preference_tools
    from shared.travel_agent import (
        SYSTEM_PROMPT, get_travel_policy, search_flights, search_hotels,
    )

    tools = [search_flights, search_hotels, get_travel_policy]
    if semantic_store is not None:
        tools += make_preference_tools(semantic_store)

    if search_client is not None and openai_client is not None:
        from azure.search.documents.models import VectorizedQuery

        @tool
        async def search_travel_policies(query: str, category: str = "", top_k: int = 3) -> str:
            """Search corporate travel policies, procedures, and compliance documents.
            Use this to find current policy information about budgets, vendors,
            safety requirements, expense rules, and booking procedures."""
            embedding = openai_client.embeddings.create(
                input=query[:8000], model=embedding_model).data[0].embedding
            results = search_client.search(
                search_text=query,
                vector_queries=[VectorizedQuery(vector=embedding, k_nearest_neighbors=top_k,
                                                fields="content_vector")],
                filter=f"category eq '{category}'" if category else None,
                top=top_k,
                select=["id", "title", "content", "category", "version"],
            )
            docs = [{"title": r["title"], "content": r["content"][:1000],
                     "version": r["version"]} for r in results]
            return json.dumps(docs, indent=2) if docs else "No matching policies found."

        tools.append(search_travel_policies)

    tools += extra_tools or []

    instructions = SYSTEM_PROMPT + (
        "\n\nYou have access to the user's semantic memory (preferences) and corporate "
        "travel policies. Before making recommendations, recall the user's stored "
        "preferences. The current user is Sarah Chen (employee E001)."
    )
    if instructions_suffix:
        instructions += "\n\n" + instructions_suffix

    kwargs = {}
    if context_providers:
        kwargs["context_providers"] = context_providers
    if middleware:
        kwargs["middleware"] = middleware
    return Agent(client=client, name=name, instructions=instructions, tools=tools, **kwargs)


def setup_backends(credential, env_path: str = "../.env"):
    """Connect to Cosmos DB and AI Search.

    Returns ``(cosmos_client, embed_fn, search_client, openai_client)``:
    the async Cosmos client, an async embedding function for semantic memory,
    the policy-index SearchClient, and a sync OpenAI client for policy-query embeddings.
    """
    import os
    from azure.core.credentials import AzureKeyCredential
    from azure.cosmos.aio import CosmosClient
    from azure.identity.aio import AzureCliCredential as AsyncCliCredential
    from azure.identity.aio import get_bearer_token_provider
    from azure.search.documents import SearchClient
    from dotenv import load_dotenv
    from openai import AsyncAzureOpenAI, OpenAI

    load_dotenv(env_path, override=True)
    scope = "https://cognitiveservices.azure.com/.default"

    cosmos = CosmosClient(os.environ["COSMOS_ENDPOINT"], credential=AsyncCliCredential())

    embed_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    embed_client = AsyncAzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=get_bearer_token_provider(AsyncCliCredential(), scope),
        api_version="2024-02-01",
    )

    async def embed_fn(text: str) -> list[float]:
        r = await embed_client.embeddings.create(input=[text], model=embed_deployment)
        return r.data[0].embedding

    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name="travel-policies",
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
    )

    # The Foundry project endpoint 404s on /embeddings; the account-level one works.
    account_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].split("/api/projects")[0]
    openai_client = OpenAI(
        base_url=f"{account_endpoint}/openai/v1",
        api_key="placeholder",
        default_headers={"Authorization": f"Bearer {credential.get_token(scope).token}"},
    )

    return cosmos, embed_fn, search_client, openai_client

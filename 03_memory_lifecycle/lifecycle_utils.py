"""
Shared utilities for Module 03 — Memory Lifecycle.

Provides core data models and engines used across all lifecycle notebooks:
- MemoryState enum and transitions
- MemoryItem with lifecycle metadata
- PromotionEngine for staged trust gating
- RetentionScorer for bounded memory management
- BiTemporalRecord for belief revision
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
import uuid
import json


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MemoryState(Enum):
    CANDIDATE = "candidate"       # Stored, NOT used in agent decisions
    PROVISIONAL = "provisional"   # Stored, used with hedging language
    TRUSTED = "trusted"           # Stored, used as fact
    DEPRECATED = "deprecated"     # Superseded, kept for history only
    DELETED = "deleted"           # Logically removed


class MemoryDecision(Enum):
    MEMORISE = "memorise"
    DISCARD = "discard"
    ASK_USER = "ask_user"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

@dataclass
class MemoryCandidate:
    """Result of the memory identification step."""
    content: str
    category: str  # preference | fact | event | procedure
    durability: float = 0.0       # 0-1: how likely to remain true
    reusability: float = 0.0      # 0-1: how likely to be useful later
    user_specificity: float = 0.0 # 0-1: how personal
    actionability: float = 0.0    # 0-1: can agent use this to improve service
    decision: MemoryDecision = MemoryDecision.DISCARD
    reasoning: str = ""

    @property
    def composite_score(self) -> float:
        return (self.durability + self.reusability +
                self.user_specificity + self.actionability) / 4.0


@dataclass
class MemoryItem:
    """A memory object with full lifecycle metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    content: str = ""
    category: str = ""  # preference | fact | event | procedure
    state: MemoryState = MemoryState.CANDIDATE
    confidence: float = 0.5
    confirmation_count: int = 0
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_confirmed: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    source_type: str = "llm_inference"  # user_assertion | enterprise_kb | llm_inference | tool_output
    state_history: list = field(default_factory=list)
    success_correlation: float = 0.0

    def transition(self, new_state: MemoryState, reason: str = ""):
        """Record a state transition."""
        self.state_history.append({
            "from": self.state.value,
            "to": new_state.value,
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        })
        self.state = new_state

    def confirm(self):
        """Record a confirmation signal."""
        self.confirmation_count += 1
        self.last_confirmed = datetime.now(timezone.utc)

    def record_access(self):
        """Record that this memory was retrieved."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)

    def to_cosmos(self) -> dict:
        d = {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "category": self.category,
            "state": self.state.value,
            "confidence": self.confidence,
            "confirmation_count": self.confirmation_count,
            "first_seen": self.first_seen.isoformat(),
            "last_confirmed": self.last_confirmed.isoformat() if self.last_confirmed else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "source_type": self.source_type,
            "state_history": self.state_history,
            "success_correlation": self.success_correlation,
        }
        return d

    @classmethod
    def from_cosmos(cls, doc: dict) -> "MemoryItem":
        return cls(
            id=doc["id"],
            user_id=doc["user_id"],
            content=doc["content"],
            category=doc["category"],
            state=MemoryState(doc["state"]),
            confidence=doc["confidence"],
            confirmation_count=doc["confirmation_count"],
            first_seen=datetime.fromisoformat(doc["first_seen"]),
            last_confirmed=datetime.fromisoformat(doc["last_confirmed"]) if doc.get("last_confirmed") else None,
            last_accessed=datetime.fromisoformat(doc["last_accessed"]) if doc.get("last_accessed") else None,
            access_count=doc["access_count"],
            source_type=doc["source_type"],
            state_history=doc.get("state_history", []),
            success_correlation=doc.get("success_correlation", 0.0),
        )


# ---------------------------------------------------------------------------
# Staged Promotion
# ---------------------------------------------------------------------------

@dataclass
class PromotionConfig:
    confirmation_threshold: int = 2          # confirms needed for candidate → trusted
    provisional_threshold: int = 1           # confirms needed for candidate → provisional
    user_assertion_auto_promote: bool = True  # explicit user statements skip candidate
    confidence_floor: float = 0.2            # below this → deprecated
    staleness_days: int = 180                # unconfirmed this long → review


class PromotionEngine:
    """Evaluates memory state transitions based on configurable rules."""

    def __init__(self, config: PromotionConfig = None):
        self.config = config or PromotionConfig()

    def evaluate(self, memory: MemoryItem) -> MemoryState:
        """Determine the appropriate state for a memory based on current signals."""
        # User assertions auto-promote to trusted
        if (memory.source_type == "user_assertion"
                and self.config.user_assertion_auto_promote):
            return MemoryState.TRUSTED

        # Confidence floor → deprecate
        if memory.confidence < self.config.confidence_floor:
            return MemoryState.DEPRECATED

        # Promotion from candidate
        if memory.state == MemoryState.CANDIDATE:
            if memory.confirmation_count >= self.config.confirmation_threshold:
                return MemoryState.TRUSTED
            elif memory.confirmation_count >= self.config.provisional_threshold:
                return MemoryState.PROVISIONAL

        # Promotion from provisional
        if memory.state == MemoryState.PROVISIONAL:
            if memory.confirmation_count >= self.config.confirmation_threshold:
                return MemoryState.TRUSTED

        # Staleness check for trusted memories
        if memory.state == MemoryState.TRUSTED and memory.last_confirmed:
            days_since = (datetime.now(timezone.utc) - memory.last_confirmed).days
            if days_since > self.config.staleness_days:
                return MemoryState.PROVISIONAL  # Demote stale memories

        return memory.state  # No transition

    def apply(self, memory: MemoryItem) -> bool:
        """Evaluate and apply transition if needed. Returns True if state changed."""
        new_state = self.evaluate(memory)
        if new_state != memory.state:
            memory.transition(new_state, reason=f"promotion_engine: {self._reason(memory, new_state)}")
            return True
        return False

    def _reason(self, memory: MemoryItem, new_state: MemoryState) -> str:
        if new_state == MemoryState.TRUSTED:
            if memory.source_type == "user_assertion":
                return "user_assertion_auto_promote"
            return f"confirmation_count={memory.confirmation_count} >= threshold"
        if new_state == MemoryState.PROVISIONAL:
            if memory.state == MemoryState.TRUSTED:
                return "staleness_demotion"
            return f"confirmation_count={memory.confirmation_count} >= provisional_threshold"
        if new_state == MemoryState.DEPRECATED:
            return f"confidence={memory.confidence} < floor={self.config.confidence_floor}"
        return "unknown"


# ---------------------------------------------------------------------------
# Cosmos-Backed Staged Promotion
# ---------------------------------------------------------------------------

class CosmosPromotionStore:
    """Staged-promotion trust state stored on Cosmos DB preference documents.

    Every transition is a partial update (patch_item) so the same operations
    work from a notebook, a request handler, or a scheduled maintenance job.
    Preferences carry a ``state`` property (candidate -> provisional -> trusted
    -> deprecated); the agent's recall path filters on it, so an untrusted
    write can never reach the model.

    **User isolation**: every query filters on ``user_id`` (partition key).
    """

    def __init__(self, store, config: "PromotionConfig" = None):
        self._s = store  # SemanticMemoryStore
        self.config = config or PromotionConfig()

    async def reset(self) -> int:
        """Delete this scope's preferences so demo re-runs start clean."""
        return await self._s.reset()

    async def record(self, category, preference, source_type, confidence=0.7) -> str:
        """Persist a preference with its initial trust state.
        user_assertion enters 'provisional' (anti-spoofing); else 'candidate'."""
        state = "provisional" if source_type == "user_assertion" else "candidate"
        doc = await self._s.add_preference(category, preference, confidence,
                                           source_type, state)
        return state
        return state

    async def record_trusted(self, category, preference, confidence=0.9) -> None:
        """Trust-on-first-write (the anti-pattern) - write straight to trusted."""
        await self._s.add_preference(category, preference, confidence,
                                     "tool_output", "trusted")

    async def confirm(self, preference) -> dict:
        """One confirmation + promotion. Matches by semantic search."""
        result = await self._s.confirm(preference)
        if not result:
            return {"state": None, "confirmations": 0}
        return result

    async def snapshot(self) -> list:
        """Read this user's lifecycle-managed preferences and their live states."""
        docs = await self._s.snapshot()
        return [{"preference": d["preference"], "state": d["state"],
                 "confirmations": d.get("confirmation_count", 0),
                 "source_type": d.get("source_type", "")} for d in docs]

    async def staleness_sweep(self) -> int:
        """Demote trusted memories unconfirmed past the staleness window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(
            days=self.config.staleness_days)).isoformat()
        sql = (
            "SELECT c.id FROM c WHERE c.user_id = @uid "
            "AND c.state = 'trusted' AND c.last_confirmed < @cutoff"
        )
        params = [{"name": "@uid", "value": self._s._user_id},
                  {"name": "@cutoff", "value": cutoff}]
        if self._s.scope_tag:
            sql += " AND c.scope_tag = @scope"
            params.append({"name": "@scope", "value": self._s.scope_tag})
        ids = [item["id"] async for item in self._s._c.query_items(
            sql, parameters=params, partition_key=self._s._user_id)]
        for doc_id in ids:
            await self._s.set_state(doc_id, "provisional")
        return len(ids)

    async def gated_recall(self, query) -> str:
        """Semantic recall filtered by trust state."""
        results = await self._s.search(query, states=["trusted", "provisional"])
        if not results:
            return "No trusted preferences to share yet."
        out = []
        for r in results:
            if r["state"] == "trusted":
                out.append(f"[KNOWN FACT] {r['preference']}")
            elif r["state"] == "provisional":
                out.append(f"[LIKELY - confirm before assuming] {r['preference']}")
        return "\n".join(out) if out else "No trusted preferences to share yet."

    async def recall_all(self, query) -> str:
        """Ungated recall — returns every stored preference as fact."""
        results = await self._s.search(query, current_only=True)
        if not results:
            return "No preferences found."
        return "\n".join(f"[FACT] {r['preference']}" for r in results)

    async def backdate(self, preference_text, days) -> None:
        """Test helper: simulate age by moving last_confirmed into the past."""
        results = await self._s.search(preference_text, top_k=1)
        if results:
            old_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            await self._s._c.patch_item(
                item=results[0]["id"],
                partition_key=self._s._user_id,
                patch_operations=[
                    {"op": "set", "path": "/last_confirmed", "value": old_date},
                ],
            )


# ---------------------------------------------------------------------------
# Bi-Temporal Belief Revision
# ---------------------------------------------------------------------------

@dataclass
class Triple:
    """A (subject, relation, object) fact with optional context."""
    subject: str
    relation: str
    object: str
    context: str = ""  # e.g., "for work travel", "temporarily"


@dataclass
class BiTemporalRecord:
    """A belief with both valid-time and transaction-time tracking."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    triple: Triple = field(default_factory=lambda: Triple("", "", ""))
    valid_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_to: Optional[datetime] = None  # None = currently valid
    transaction_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    superseded_by: Optional[str] = None
    state: MemoryState = MemoryState.TRUSTED
    confidence: float = 0.8
    source: str = "user_assertion"

    @property
    def is_current(self) -> bool:
        return self.valid_to is None

    def supersede(self, new_record_id: str, valid_to: datetime):
        """Mark this record as superseded."""
        self.valid_to = valid_to
        self.superseded_by = new_record_id
        self.state = MemoryState.DEPRECATED

    def to_cosmos(self) -> dict:
        return {
            "id": self.id,
            "subject": self.triple.subject,
            "relation": self.triple.relation,
            "object": self.triple.object,
            "context": self.triple.context,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "transaction_time": self.transaction_time.isoformat(),
            "superseded_by": self.superseded_by,
            "state": self.state.value,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_cosmos(cls, doc: dict) -> "BiTemporalRecord":
        return cls(
            id=doc["id"],
            triple=Triple(
                subject=doc["subject"],
                relation=doc["relation"],
                object=doc["object"],
                context=doc.get("context", ""),
            ),
            valid_from=datetime.fromisoformat(doc["valid_from"]),
            valid_to=datetime.fromisoformat(doc["valid_to"]) if doc.get("valid_to") else None,
            transaction_time=datetime.fromisoformat(doc["transaction_time"]),
            superseded_by=doc.get("superseded_by"),
            state=MemoryState(doc["state"]),
            confidence=doc.get("confidence", 0.8),
            source=doc.get("source", "unknown"),
        )


class CosmosBeliefStore:
    """Bi-temporal belief revision on Cosmos DB preference documents (SCD Type 2).

    Every preference carries ``valid_from`` / ``valid_to`` timestamps. When a
    new value supersedes an old one the old document is *retired* (``valid_to``
    set, ``superseded_by`` linked) — never deleted. This gives full audit
    history plus time-travel queries, all via SQL API.

    Composes with ``CosmosPromotionStore``: a revised belief still has a trust
    ``state`` (candidate / provisional / trusted).
    """

    def __init__(self, store):
        self._s = store  # SemanticMemoryStore

    async def reset(self) -> int:
        """Delete this scope's preferences so demo re-runs start clean."""
        return await self._s.reset()

    async def store(self, category: str, preference: str,
                    source_type: str = "user_assertion") -> dict:
        """Store a new belief. Auto-supersedes conflicting current value (SCD Type 2)."""
        existing = await self._s.get_current(category)
        doc = await self._s.add_preference(category, preference, 0.8, source_type)
        return {"preference": preference, "state": doc["state"],
                "superseded": existing["preference"] if existing and existing["preference"].lower() != preference.lower() else None}

    async def recall_current(self, query: str) -> str:
        """Recall currently-valid beliefs (state trusted/provisional)."""
        results = await self._s.search(query, states=["trusted", "provisional"])
        if not results:
            return "No current beliefs found."
        return "\n".join(
            f"{'[KNOWN]' if r['state'] == 'trusted' else '[LIKELY]'} {r['preference']}"
            for r in results
        )

    async def recall_at_time(self, query: str, iso_date: str) -> str:
        """Time-travel: recall beliefs valid on a specific date."""
        results = await self._s.search(query, current_only=False, top_k=20)
        valid = []
        for r in results:
            vf = r.get("valid_from", "")
            vt = r.get("valid_to")
            if vf <= iso_date and (vt is None or vt > iso_date):
                valid.append(r)
        if not valid:
            return f"No beliefs found valid at {iso_date}."
        return "\n".join(
            f"{r['preference']} (valid {r['valid_from'][:10]} → {r['valid_to'][:10] if r['valid_to'] else 'present'})"
            for r in valid
        )

    async def history(self, category: str) -> list[dict]:
        """Full SCD Type 2 audit trail for a category."""
        return await self._s.history(category)

    async def snapshot(self) -> list[dict]:
        """Read this user's belief-managed preferences."""
        return await self._s.snapshot(include_deprecated=False)


# ---------------------------------------------------------------------------
# Retention Scoring
# ---------------------------------------------------------------------------

class RetentionScorer:
    """Scores memories for retention priority. Lower scores get evicted first."""

    DEFAULT_WEIGHTS = {
        "recency": 0.20,
        "access_frequency": 0.15,
        "success": 0.25,
        "redundancy_penalty": 0.15,
        "specificity": 0.10,
        "utility": 0.15,
    }

    def __init__(self, weights: dict = None, capacity: int = 500,
                 half_life_days: float = 30.0):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.capacity = capacity
        self.half_life_days = half_life_days

    def score(self, memory: MemoryItem, all_memories: list["MemoryItem"] = None) -> float:
        """Compute retention score for a memory (higher = keep longer)."""
        import math

        now = datetime.now(timezone.utc)
        age_days = (now - memory.first_seen).total_seconds() / 86400.0

        # Recency: exponential decay
        recency = math.exp(-0.693 * age_days / self.half_life_days)

        # Access frequency (capped at 1.0)
        access = min(memory.access_count / 10.0, 1.0)
        if memory.last_accessed:
            access_age = (now - memory.last_accessed).total_seconds() / 86400.0
            access *= math.exp(-0.693 * access_age / self.half_life_days)

        # Success correlation
        success = memory.success_correlation

        # Redundancy penalty (requires all_memories for pairwise comparison)
        redundancy = 0.0  # Default: no penalty if we don't check

        # Specificity heuristic: longer, more detailed content = more specific
        specificity = min(len(memory.content) / 200.0, 1.0)

        # Utility: combination of confirmation count and state
        utility = 0.0
        if memory.state == MemoryState.TRUSTED:
            utility = 0.8
        elif memory.state == MemoryState.PROVISIONAL:
            utility = 0.5
        elif memory.state == MemoryState.CANDIDATE:
            utility = 0.2
        utility += min(memory.confirmation_count * 0.1, 0.2)

        return (
            self.weights["recency"] * recency +
            self.weights["access_frequency"] * access +
            self.weights["success"] * success -
            self.weights["redundancy_penalty"] * redundancy +
            self.weights["specificity"] * specificity +
            self.weights["utility"] * utility
        )

    def rank(self, memories: list["MemoryItem"]) -> list[tuple["MemoryItem", float]]:
        """Rank memories by retention score (ascending = evict first)."""
        scored = [(m, self.score(m, memories)) for m in memories]
        scored.sort(key=lambda x: x[1])
        return scored

    def select_for_eviction(self, memories: list["MemoryItem"],
                            evict_count: int = None) -> list["MemoryItem"]:
        """Select lowest-scored memories for eviction."""
        if evict_count is None:
            evict_count = max(1, self.capacity // 10)
        ranked = self.rank(memories)
        return [m for m, _ in ranked[:evict_count]]


# ---------------------------------------------------------------------------
# Cosmos-Backed Retention
# ---------------------------------------------------------------------------

class CosmosRetentionStore:
    """Bounded retention scoring on Cosmos DB preference documents.

    Reads all lifecycle-managed preferences, scores them using
    ``RetentionScorer``, writes scores back via partial updates, and evicts
    the lowest-scored by setting their state to DEPRECATED.
    """

    def __init__(self, store, scorer: RetentionScorer = None,
                 capacity: int = 50):
        self._s = store  # SemanticMemoryStore
        self.scorer = scorer or RetentionScorer(capacity=capacity)
        self.capacity = capacity

    async def reset(self) -> int:
        """Delete scoped demo preferences so re-runs start clean."""
        return await self._s.reset()

    async def cleanup_scope(self) -> int:
        """Delete only this scope's demo preferences."""
        return await self._s.reset()

    async def add_preference(self, category: str, preference: str,
                             state: str = "candidate", access_count: int = 0,
                             success_correlation: float = 0.0,
                             age_days: int = 0) -> str:
        """Helper: add a preference with retention-relevant metadata for demos."""
        doc = await self._s.add_preference(category, preference, 0.7,
                                           "llm_inference", state)
        # Backdate and set retention-specific fields
        first_seen = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
        last_accessed = (datetime.now(timezone.utc) - timedelta(
            days=int(age_days * 0.3))).isoformat() if access_count > 0 else None
        ops = [
            {"op": "set", "path": "/first_seen", "value": first_seen},
            {"op": "set", "path": "/access_count", "value": access_count},
            {"op": "set", "path": "/success_correlation", "value": success_correlation},
        ]
        if last_accessed:
            ops.append({"op": "set", "path": "/last_accessed", "value": last_accessed})
        await self._s._c.patch_item(
            item=doc["id"], partition_key=self._s._user_id,
            patch_operations=ops,
        )
        return doc["id"]

    async def score_all(self) -> list[dict]:
        """Score all active preferences. Returns list sorted ascending (evict-first)."""
        docs = await self._s.snapshot(include_deprecated=False)
        scored = []
        for d in docs:
            if d.get("state") == "deprecated" or d.get("valid_to") is not None:
                continue
            m = MemoryItem(
                id=d["id"], content=d.get("preference", ""),
                state=MemoryState(d["state"]) if d.get("state") else MemoryState.CANDIDATE,
                access_count=d.get("access_count", 0) or 0,
                success_correlation=d.get("success_correlation", 0.0) or 0.0,
                first_seen=self._parse_dt(d.get("first_seen")),
                last_accessed=self._parse_dt(d.get("last_accessed")),
                confirmation_count=d.get("confirmation_count", 0) or 0,
            )
            score = self.scorer.score(m)
            scored.append({"id": d["id"], "preference": d["preference"],
                           "state": d["state"], "score": score})
            # Write score back
            await self._s._c.patch_item(
                item=d["id"], partition_key=self._s._user_id,
                patch_operations=[
                    {"op": "set", "path": "/retention_score", "value": score},
                    {"op": "set", "path": "/last_scored",
                     "value": datetime.now(timezone.utc).isoformat()},
                ],
            )
        scored.sort(key=lambda x: x["score"])
        return scored

    async def evict(self, count: int) -> list[dict]:
        """Deprecate the N lowest-scored preferences."""
        scored = await self.score_all()
        to_evict = scored[:count]
        for item in to_evict:
            await self._s.set_state(item["id"], "deprecated")
            item["state"] = "deprecated"
        return to_evict

    async def snapshot(self) -> list[dict]:
        """All preferences with their retention scores."""
        docs = await self._s.snapshot(include_deprecated=True)
        return [{"preference": d["preference"], "state": d["state"],
                 "score": d.get("retention_score") or 0,
                 "access_count": d.get("access_count") or 0,
                 "success_correlation": d.get("success_correlation") or 0}
                for d in docs]

    async def active_count(self) -> int:
        """Count of non-deprecated, non-deleted, current preferences."""
        return await self._s.count(current_only=True)

    @staticmethod
    def _parse_dt(val) -> datetime:
        if val is None:
            return datetime.now(timezone.utc) - timedelta(days=90)
        if isinstance(val, str):
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Episodic Memory Lifecycle
# ---------------------------------------------------------------------------

@dataclass
class EpisodicTTLConfig:
    """TTL configuration for episodic memory events (Cosmos DB native TTL)."""
    default_ttl_days: int = 180
    ttl_by_event_type: dict = field(default_factory=lambda: {
        "trip": 365,        # Historical reference value
        "feedback": 180,    # Preferences evolve
        "preference": 90,   # Short-lived unless graduated to semantic
    })
    graduation_threshold: int = 3      # Pattern must appear N+ times
    graduation_session_min: int = 3    # ...across N+ distinct sessions

    def compute_ttl_seconds(self, event_type: str) -> int:
        """Compute TTL in seconds for Cosmos DB `ttl` field."""
        days = self.ttl_by_event_type.get(event_type, self.default_ttl_days)
        return days * 86400


@dataclass
class EpisodicPattern:
    """A detected pattern across episodic events that may graduate to semantic."""
    pattern_type: str       # e.g., "hotel_preference", "airline_preference"
    value: str              # e.g., "Marriott", "United"
    event_count: int = 0
    session_ids: list = field(default_factory=list)
    event_ids: list = field(default_factory=list)
    composite_content: str = ""  # Generated semantic memory content

    @property
    def session_count(self) -> int:
        return len(set(self.session_ids))

    def qualifies(self, config: EpisodicTTLConfig) -> bool:
        """Check if this pattern qualifies for graduation."""
        return (self.event_count >= config.graduation_threshold and
                self.session_count >= config.graduation_session_min)


# ---------------------------------------------------------------------------
# Procedural Memory Lifecycle
# ---------------------------------------------------------------------------

@dataclass
class ProceduralReflection:
    """A learned procedure/lesson with lifecycle metadata for validation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    task_type: str = ""              # e.g., "international-booking"
    content: str = ""                # The lesson/procedure text
    state: MemoryState = MemoryState.TRUSTED
    confidence: float = 0.8
    # Policy anchoring
    policy_reference: str = ""       # AI Search doc ID that justified this
    policy_version: str = ""         # Version of policy at time of creation
    # Execution tracking (cooperative — agent reports back)
    execution_count: int = 0
    success_count: int = 0
    last_executed: Optional[datetime] = None
    # Validation
    last_validated: Optional[datetime] = None
    validation_result: str = ""      # "valid" | "stale" | "contradicted"
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count

    def record_execution(self, success: bool):
        """Record that this reflection was used and whether it succeeded."""
        self.execution_count += 1
        if success:
            self.success_count += 1
        self.last_executed = datetime.now(timezone.utc)

    def to_cosmos(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "task_type": self.task_type,
            "content": self.content,
            "state": self.state.value,
            "confidence": self.confidence,
            "policy_reference": self.policy_reference,
            "policy_version": self.policy_version,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
            "validation_result": self.validation_result,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }

    @classmethod
    def from_cosmos(cls, doc: dict) -> "ProceduralReflection":
        return cls(
            id=doc["id"],
            user_id=doc.get("user_id", ""),
            task_type=doc["task_type"],
            content=doc["content"],
            state=MemoryState(doc["state"]),
            confidence=doc.get("confidence", 0.8),
            policy_reference=doc.get("policy_reference", ""),
            policy_version=doc.get("policy_version", ""),
            execution_count=doc.get("execution_count", 0),
            success_count=doc.get("success_count", 0),
            last_executed=datetime.fromisoformat(doc["last_executed"]) if doc.get("last_executed") else None,
            last_validated=datetime.fromisoformat(doc["last_validated"]) if doc.get("last_validated") else None,
            validation_result=doc.get("validation_result", ""),
            created_at=datetime.fromisoformat(doc["created_at"]) if doc.get("created_at") else datetime.now(timezone.utc),
            last_accessed=datetime.fromisoformat(doc["last_accessed"]) if doc.get("last_accessed") else None,
        )


@dataclass
class ValidationResult:
    """Result of validating a procedural reflection against current policy."""
    is_valid: bool
    confidence: float          # 0-1 how confident the validation is
    reason: str                # Explanation
    action: str                # "keep" | "flag" | "deprecate"
    current_policy_snippet: str = ""  # The relevant policy text found
    policy_version: str = ""   # Current policy version in AI Search


# ---------------------------------------------------------------------------
# Baseline Agent Factory
# ---------------------------------------------------------------------------

def create_baseline_agent(
    client,
    credential,
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
    """
    Create a baseline travel agent with semantic memory (Cosmos) and RAG (AI Search).

    This agent represents the "complete but lifecycle-unmanaged" state:
    - Can recall preferences from the semantic-memory container
    - Can store new preferences to the semantic-memory container
    - Can search corporate policies via AI Search (hybrid search)
    - Can search flights/hotels from local data
    - Has NO lifecycle management (no identification, promotion, revision, etc.)

    Args:
        client: FoundryChatClient instance
        credential: AzureCliCredential for Search auth
        semantic_store: SemanticMemoryStore instance for preferences
        search_client: Azure SearchClient for policy RAG
        openai_client: OpenAI client for embeddings (account-level)
        embedding_model: Embedding model deployment name
        extra_tools: Additional tools to add to the agent
        instructions_suffix: Extra text appended to system prompt
        context_providers: Context providers (e.g. SkillsProvider) for the agent
        middleware: Middleware list (e.g. ToolApprovalMiddleware) for the agent
        name: Agent name

    Returns:
        Agent instance with all tools configured
    """
    from agent_framework import Agent, tool
    from shared.travel_agent import (
        SYSTEM_PROMPT, search_flights, search_hotels, get_travel_policy,
    )

    tools = [search_flights, search_hotels, get_travel_policy]

    # --- Semantic memory tools (Cosmos DB) ---
    if semantic_store is not None:
        @tool
        async def recall_preferences(
            user_id: str, query: str = "travel preferences", limit: int = 5
        ) -> str:
            """Recall stored preferences for a user from semantic memory."""
            results = await semantic_store.search(query, top_k=limit)
            if not results:
                return f"No preferences found for {user_id}"
            lines = [f"[{r['category']}] {r['preference']} (confidence: {r.get('confidence', 0):.2f})"
                     for r in results]
            return "\n".join(lines)

        @tool
        async def store_preference(
            user_id: str, category: str, preference: str,
            source_type: str = "user_assertion", confidence: float = 0.8
        ) -> str:
            """Store a personal preference. category: airline, hotel_chain,
            seating, dietary, home_city, budget, etc."""
            doc = await semantic_store.add_preference(
                category, preference, confidence, source_type)
            return f"Stored [{category}]: {preference}"

        tools.extend([recall_preferences, store_preference])

    # --- RAG tools (AI Search) ---
    if search_client is not None and openai_client is not None:
        from azure.search.documents.models import VectorizedQuery

        def _get_embedding(text: str) -> list[float]:
            response = openai_client.embeddings.create(
                input=text[:8000], model=embedding_model
            )
            return response.data[0].embedding

        @tool
        async def search_travel_policies(
            query: str, category: str = "", top_k: int = 3
        ) -> str:
            """Search corporate travel policies, procedures, and compliance documents.
            Use this to find current policy information about budgets, vendors,
            safety requirements, expense rules, and booking procedures."""
            vector_query = VectorizedQuery(
                vector=_get_embedding(query),
                k_nearest_neighbors=top_k,
                fields="content_vector",
            )
            filter_expr = f"category eq '{category}'" if category else None
            results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                filter=filter_expr,
                top=top_k,
                select=["id", "title", "content", "category", "version"],
            )
            docs = [
                {"title": r["title"], "content": r["content"][:1000],
                 "version": r["version"]}
                for r in results
            ]
            if not docs:
                return "No matching policies found."
            return json.dumps(docs, indent=2)

        tools.append(search_travel_policies)

    # --- Add extra tools ---
    if extra_tools:
        tools.extend(extra_tools)

    # --- Build agent ---
    instructions = SYSTEM_PROMPT + (
        "\n\nYou have access to the user's semantic memory (preferences) and corporate travel policies. "
        "Before making recommendations, recall the user's stored preferences. "
        "The current user is Sarah Chen (employee E001)."
    )
    if instructions_suffix:
        instructions += "\n\n" + instructions_suffix

    agent_kwargs = dict(
        client=client,
        name=name,
        instructions=instructions,
        tools=tools,
    )
    if context_providers:
        agent_kwargs["context_providers"] = context_providers
    if middleware:
        agent_kwargs["middleware"] = middleware

    return Agent(**agent_kwargs)


def setup_backends(credential, env_path: str = "../.env"):
    """
    Connect to Cosmos DB (semantic memory) and AI Search. Returns (semantic_store, search_client, openai_client).

    Requires env vars: COSMOS_ENDPOINT, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY,
    FOUNDRY_PROJECT_ENDPOINT, and optionally AZURE_OPENAI_EMBEDDING_DEPLOYMENT.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)

    # Cosmos DB — semantic memory container
    from azure.cosmos.aio import CosmosClient
    from azure.identity.aio import (
        AzureCliCredential as AsyncCliCredential,
        get_bearer_token_provider as async_get_bearer_token_provider,
    )
    from openai import AsyncAzureOpenAI
    from shared.semantic_store import SemanticMemoryStore, create_container

    cosmos = CosmosClient(os.environ["COSMOS_ENDPOINT"], credential=AsyncCliCredential())

    embed_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    embed_client = AsyncAzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=async_get_bearer_token_provider(
            AsyncCliCredential(), "https://cognitiveservices.azure.com/.default",
        ),
        api_version="2024-02-01",
    )

    async def _embed(text: str) -> list[float]:
        r = await embed_client.embeddings.create(input=[text], model=embed_deployment)
        return r.data[0].embedding

    # AI Search
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name="travel-policies",
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
    )

    # OpenAI embeddings (sync, for RAG)
    from openai import OpenAI
    foundry_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    account_endpoint = foundry_endpoint.split("/api/projects")[0]
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    openai_client = OpenAI(
        base_url=f"{account_endpoint}/openai/v1",
        api_key="placeholder",
        default_headers={"Authorization": f"Bearer {token}"},
    )

    return cosmos, _embed, search_client, openai_client

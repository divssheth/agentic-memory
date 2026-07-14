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
# Graph-Backed Staged Promotion (Neo4j)
# ---------------------------------------------------------------------------

class GraphPromotionStore:
    """Staged-promotion trust state stored ON Neo4j preference nodes.

    Every transition is a Cypher statement executed inside the database, so the
    same operations run unchanged from a notebook, a request handler, or a
    scheduled maintenance job. Preferences carry a ``state`` property
    (candidate -> provisional -> trusted -> deprecated); the agent's recall path
    filters on it, so an untrusted write can never reach the model.

    Scope: every method only touches preferences that have a ``state`` property,
    i.e. the ones this lifecycle manages. Preferences written by other modules
    (which lack ``state``) are left untouched.
    """

    def __init__(self, memory, config: "PromotionConfig" = None):
        self._m = memory
        self.config = config or PromotionConfig()

    async def reset(self) -> None:
        """Delete lifecycle-managed preferences so demo re-runs start clean."""
        await self._m._client.execute_write(
            "MATCH (p:Preference) WHERE p.state IS NOT NULL DETACH DELETE p"
        )

    async def record(self, category, preference, source_type, confidence=0.7) -> str:
        """OP1 - persist a preference with its initial trust state.
        user_assertion enters 'provisional' (anti-spoofing); else 'candidate'."""
        pref = await self._m.long_term.add_preference(
            category=category, preference=preference, confidence=confidence
        )
        state = "provisional" if source_type == "user_assertion" else "candidate"
        await self._m._client.execute_write(
            """MATCH (p:Preference {id:$id})
               SET p.state=$state, p.source_type=$src, p.confirmation_count=0,
                   p.first_seen=datetime(),
                   p.last_confirmed=CASE WHEN $state='provisional'
                                         THEN datetime() ELSE null END""",
            {"id": str(pref.id), "state": state, "src": source_type},
        )
        return state

    async def record_trusted(self, category, preference, confidence=0.9) -> None:
        """Trust-on-first-write (the anti-pattern) - write straight to trusted."""
        await self.record(category, preference, "tool_output", confidence)
        await self._m._client.execute_write(
            "MATCH (p:Preference {preference:$t}) "
            "SET p.state='trusted', p.last_confirmed=datetime()",
            {"t": preference},
        )

    async def confirm(self, preference) -> dict:
        """OP2 - one confirmation + promotion, atomically (race-free).
        Matches the closest stored preference by semantic search, so the agent
        can reaffirm in its own words. Ignores preferences stored <5s ago
        (prevents same-turn remember+confirm from skipping provisional)."""
        hits = await self._m.long_term.search_preferences(
            query=preference, threshold=0.0, limit=1
        )
        if not hits:
            return {"state": None, "confirmations": 0}
        rows = await self._m._client.execute_write(
            """MATCH (p:Preference {id:$id})
               WHERE p.first_seen < datetime() - duration({seconds:5})
               SET p.confirmation_count=coalesce(p.confirmation_count,0)+1,
                   p.last_confirmed=datetime()
               WITH p
               SET p.state=CASE
                 WHEN p.source_type='user_assertion' AND p.confirmation_count>=1
                     THEN 'trusted'
                 WHEN p.confirmation_count>=$tt THEN 'trusted'
                 WHEN p.confirmation_count>=$pt THEN 'provisional'
                 ELSE p.state END
               RETURN p.state AS state, p.confirmation_count AS confirmations""",
            {"id": str(hits[0].id),
             "tt": self.config.confirmation_threshold,
             "pt": self.config.provisional_threshold},
        )
        if not rows:
            # Preference was too recently stored — return current state without promoting
            snap = await self._m.query.cypher(
                "MATCH (p:Preference {id:$id}) RETURN p.state AS state, "
                "p.confirmation_count AS confirmations",
                params={"id": str(hits[0].id)},
            )
            return snap[0] if snap else {"state": "candidate", "confirmations": 0}
        return rows[0]

    async def snapshot(self) -> list:
        """Read all lifecycle-managed preferences and their live states from Neo4j."""
        return await self._m.query.cypher(
            "MATCH (p:Preference) WHERE p.state IS NOT NULL "
            "RETURN p.preference AS preference, p.state AS state, "
            "p.confirmation_count AS confirmations, p.source_type AS source_type "
            "ORDER BY p.first_seen"
        )

    async def staleness_sweep(self) -> int:
        """OP4 - demote trusted memories unconfirmed past the window.
        Stateless and idempotent: this is the body of a scheduled job."""
        rows = await self._m._client.execute_write(
            """MATCH (p:Preference)
               WHERE p.state='trusted'
                 AND p.last_confirmed < datetime() - duration({days:$d})
               SET p.state='provisional' RETURN count(p) AS demoted""",
            {"d": self.config.staleness_days},
        )
        return rows[0]["demoted"]

    async def deprecation_sweep(self) -> int:
        """OP5 - retire memories whose confidence fell below the floor."""
        rows = await self._m._client.execute_write(
            """MATCH (p:Preference)
               WHERE p.confidence < $f AND coalesce(p.state,'')<>'deprecated'
               SET p.state='deprecated' RETURN count(p) AS deprecated""",
            {"f": self.config.confidence_floor},
        )
        return rows[0]["deprecated"]

    async def gated_recall(self, query) -> str:
        """The agent's read path - semantic recall FILTERED BY TRUST STATE.
        trusted -> stated as fact; provisional -> hedged; candidate/deprecated withheld."""
        prefs = await self._m.long_term.search_preferences(query=query, threshold=0.0)
        if not prefs:
            return "No preferences found."
        rows = await self._m.query.cypher(
            "MATCH (p:Preference) WHERE p.id IN $ids "
            "RETURN p.preference AS preference, p.state AS state",
            params={"ids": [str(p.id) for p in prefs]},
        )
        out = []
        for r in rows:
            if r["state"] == "trusted":
                out.append(f"[KNOWN FACT] {r['preference']}")
            elif r["state"] == "provisional":
                out.append(f"[LIKELY - confirm before assuming] {r['preference']}")
        return "\n".join(out) if out else "No trusted preferences to share yet."

    async def recall_all(self, query) -> str:
        """Ungated recall - returns every stored preference as fact (no filtering)."""
        prefs = await self._m.long_term.search_preferences(query=query, threshold=0.0)
        if not prefs:
            return "No preferences found."
        return "\n".join(f"[FACT] {p.preference}" for p in prefs)

    async def backdate(self, preference, days) -> None:
        """Test helper: simulate age by moving last_confirmed into the past."""
        hits = await self._m.long_term.search_preferences(
            query=preference, threshold=0.0, limit=1
        )
        if hits:
            await self._m._client.execute_write(
                "MATCH (p:Preference {id:$id}) "
                "SET p.last_confirmed = datetime() - duration({days:$d})",
                {"id": str(hits[0].id), "d": days},
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


class GraphBeliefStore:
    """Bi-temporal belief revision on Neo4j Preference nodes (SCD Type 2).

    Every preference carries ``valid_from`` / ``valid_to`` timestamps.  When a
    new value supersedes an old one the old node is *retired* (``valid_to`` set,
    ``superseded_by`` linked) — never deleted.  This gives full audit history
    plus time-travel queries, all in Cypher.

    Composes with ``GraphPromotionStore``: a revised belief still has a trust
    ``state`` (candidate / provisional / trusted).
    """

    def __init__(self, memory):
        self._m = memory

    async def reset(self) -> None:
        """Delete belief-managed preferences so demo re-runs start clean."""
        await self._m._client.execute_write(
            "MATCH (p:Preference) WHERE p.valid_from IS NOT NULL DETACH DELETE p"
        )

    async def store(self, category: str, preference: str,
                    source_type: str = "user_assertion") -> dict:
        """Store a new belief.  If an existing current belief in the same
        category contradicts it, supersede the old one (SCD Type 2)."""
        # Check for existing current belief in this category
        existing = await self._m.query.cypher(
            "MATCH (p:Preference) "
            "WHERE p.category = $cat AND p.valid_to IS NULL "
            "  AND p.valid_from IS NOT NULL "
            "RETURN p.id AS id, p.preference AS preference",
            params={"cat": category},
        )
        # Supersede if there's a conflicting current value
        if existing and existing[0]["preference"].lower() != preference.lower():
            await self._m._client.execute_write(
                "MATCH (p:Preference {id:$id}) "
                "SET p.valid_to = datetime(), p.superseded_by = $new_pref",
                {"id": existing[0]["id"], "new_pref": preference},
            )

        # Write new preference with temporal properties
        pref = await self._m.long_term.add_preference(
            category=category, preference=preference, confidence=0.8
        )
        state = "provisional" if source_type == "user_assertion" else "candidate"
        await self._m._client.execute_write(
            """MATCH (p:Preference {id:$id})
               SET p.valid_from = datetime(), p.valid_to = null,
                   p.source_type = $src, p.state = $state,
                   p.category = $cat, p.confirmation_count = 0,
                   p.first_seen = datetime(), p.last_confirmed = datetime()""",
            {"id": str(pref.id), "src": source_type, "state": state, "cat": category},
        )
        return {"preference": preference, "state": state,
                "superseded": existing[0]["preference"] if existing else None}

    async def recall_current(self, query: str) -> str:
        """Recall only currently-valid beliefs (valid_to IS NULL, state trusted/provisional)."""
        prefs = await self._m.long_term.search_preferences(
            query=query, threshold=0.0)
        if not prefs:
            return "No preferences found."
        rows = await self._m.query.cypher(
            "MATCH (p:Preference) WHERE p.id IN $ids "
            "AND p.valid_to IS NULL AND p.state IN ['trusted','provisional'] "
            "RETURN p.preference AS preference, p.state AS state, p.category AS category",
            params={"ids": [str(p.id) for p in prefs]},
        )
        if not rows:
            return "No current beliefs found."
        out = []
        for r in rows:
            tag = "[KNOWN]" if r["state"] == "trusted" else "[LIKELY]"
            out.append(f"{tag} {r['preference']}")
        return "\n".join(out)

    async def recall_at_time(self, query: str, iso_date: str) -> str:
        """Recall beliefs that were valid at a specific date (time-travel query)."""
        prefs = await self._m.long_term.search_preferences(
            query=query, threshold=0.0)
        if not prefs:
            return "No preferences found."
        rows = await self._m.query.cypher(
            "MATCH (p:Preference) WHERE p.id IN $ids "
            "AND p.valid_from <= datetime($dt) "
            "AND (p.valid_to IS NULL OR p.valid_to > datetime($dt)) "
            "RETURN p.preference AS preference, p.category AS cat, "
            "       toString(p.valid_from) AS vf, toString(p.valid_to) AS vt",
            params={"ids": [str(p.id) for p in prefs], "dt": iso_date},
        )
        if not rows:
            return f"No beliefs found valid at {iso_date}."
        return "\n".join(
            f"{r['preference']} (valid {r['vf'][:10]} → {r['vt'][:10] if r['vt'] else 'present'})"
            for r in rows
        )

    async def history(self, category: str) -> list[dict]:
        """Full evolution of a belief category (SCD Type 2 audit trail)."""
        return await self._m.query.cypher(
            "MATCH (p:Preference) WHERE p.category = $cat "
            "AND p.valid_from IS NOT NULL "
            "RETURN p.preference AS preference, p.state AS state, "
            "       toString(p.valid_from) AS valid_from, "
            "       toString(p.valid_to) AS valid_to, "
            "       p.superseded_by AS superseded_by "
            "ORDER BY p.valid_from",
            params={"cat": category},
        )

    async def snapshot(self) -> list[dict]:
        """Read all belief-managed preferences from Neo4j."""
        return await self._m.query.cypher(
            "MATCH (p:Preference) WHERE p.valid_from IS NOT NULL "
            "RETURN p.preference AS preference, p.state AS state, "
            "       p.category AS category, "
            "       toString(p.valid_from) AS valid_from, "
            "       toString(p.valid_to) AS valid_to "
            "ORDER BY p.valid_from"
        )


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
    cosmos_container=None,
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
    Create a baseline travel agent with episodic memory (Cosmos) and RAG (AI Search).

    This agent represents the "complete but lifecycle-unmanaged" state:
    - Can recall past events from Cosmos DB
    - Can store new events to Cosmos DB
    - Can search corporate policies via AI Search (hybrid search)
    - Can search flights/hotels from local data
    - Has NO lifecycle management (no identification, promotion, revision, etc.)

    Each lifecycle notebook imports this, demonstrates what goes wrong,
    then layers on the specific lifecycle mechanism.

    Args:
        client: FoundryChatClient instance
        credential: AzureCliCredential for Cosmos/Search auth
        cosmos_container: Async Cosmos container client for episodic events
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

    # --- Episodic memory tools (Cosmos DB) ---
    if cosmos_container is not None:
        @tool
        async def recall_events(
            user_id: str, event_type: str = "", limit: int = 5
        ) -> str:
            """Recall past events for a user from episodic memory.
            Optionally filter by event_type: trip, preference, or feedback."""
            query = "SELECT * FROM c WHERE c.user_id = @uid"
            params = [{"name": "@uid", "value": user_id}]
            if event_type:
                query += " AND c.event_type = @etype"
                params.append({"name": "@etype", "value": event_type})
            query += " ORDER BY c.timestamp DESC OFFSET 0 LIMIT @lim"
            params.append({"name": "@lim", "value": limit})

            items = [item async for item in cosmos_container.query_items(
                query, parameters=params, partition_key=user_id
            )]
            if not items:
                return f"No events found for {user_id}"
            return json.dumps(items, indent=2, default=str)

        @tool
        async def store_event(
            user_id: str, event_type: str, description: str, details: str = "{}"
        ) -> str:
            """Store a new episodic event for a user.
            event_type should be: trip, preference, or feedback.
            details is a JSON string with additional structured data."""
            import uuid as _uuid
            doc = {
                "id": f"{user_id}-{_uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "event_type": event_type,
                "description": description,
                "details": json.loads(details) if isinstance(details, str) else details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await cosmos_container.upsert_item(doc)
            return f"Stored event: {description}"

        tools.extend([recall_events, store_event])

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
        "\n\nYou have access to the user's episodic memory and corporate travel policies. "
        "Before making recommendations, recall the user's past events and preferences. "
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
    Connect to Cosmos DB and AI Search. Returns (cosmos_container, search_client, openai_client).

    Requires env vars: COSMOS_ENDPOINT, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY,
    FOUNDRY_PROJECT_ENDPOINT, and optionally AZURE_OPENAI_EMBEDDING_DEPLOYMENT.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)

    # Cosmos DB (async client)
    from azure.cosmos.aio import CosmosClient
    cosmos = CosmosClient(os.environ["COSMOS_ENDPOINT"], credential=credential)
    db = cosmos.get_database_client("travel-memory")
    cosmos_container = db.get_container_client("episodic-events")

    # AI Search
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name="travel-policies",
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
    )

    # OpenAI embeddings (account-level endpoint)
    from openai import OpenAI
    foundry_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    account_endpoint = foundry_endpoint.split("/api/projects")[0]
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    openai_client = OpenAI(
        base_url=f"{account_endpoint}/openai/v1",
        api_key="placeholder",
        default_headers={"Authorization": f"Bearer {token}"},
    )

    return cosmos_container, search_client, openai_client

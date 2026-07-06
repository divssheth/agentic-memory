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

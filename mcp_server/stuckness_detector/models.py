"""Stuckness Detector data models — pure dataclasses, zero I/O."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


RESCUE_TYPES = [
    "contrast_needed",
    "section_missing",
    "hook_underdeveloped",
    "transition_not_earned",
    "overpolished_loop",
    "identity_unclear",
    "too_dense_to_progress",
    "too_safe_to_progress",
]


@dataclass
class StucknessSignal:
    """A single signal contributing to stuckness detection."""

    signal_type: str = ""  # "repeated_undo", "local_tweaking", "long_loop", etc.
    strength: float = 0.0  # 0-1
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StucknessReport:
    """Full stuckness analysis for a session."""

    confidence: float = 0.0  # 0-1 how stuck the session is
    level: str = "flowing"  # "flowing", "slowing", "stuck", "deeply_stuck"
    signals: list[StucknessSignal] = field(default_factory=list)
    diagnosis: str = ""
    primary_rescue_type: str = ""
    secondary_rescue_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "confidence": round(self.confidence, 3),
            "level": self.level,
            "signals": [s.to_dict() for s in self.signals],
            "diagnosis": self.diagnosis,
            "primary_rescue_type": self.primary_rescue_type,
            "secondary_rescue_types": self.secondary_rescue_types,
        }


@dataclass
class RescueSuggestion:
    """A momentum rescue suggestion."""

    rescue_type: str = ""
    title: str = ""
    description: str = ""
    urgency: str = "medium"  # "low", "medium", "high"
    strategies: list[str] = field(default_factory=list)
    identity_effect: str = "preserves"

    def to_dict(self) -> dict:
        return asdict(self)

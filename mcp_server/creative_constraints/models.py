"""Creative Constraints data models — pure dataclasses, zero I/O."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


CONSTRAINT_MODES = [
    "use_loaded_devices_only",
    "no_new_tracks",
    "subtraction_only",
    "arrangement_only",
    "mood_shift_without_new_fx",
    "make_it_stranger_but_keep_the_hook",
    "club_translation_safe",
    "performance_safe_creative",
]


@dataclass
class ConstraintSet:
    """A set of creative constraints for planning."""

    constraints: list[str] = field(default_factory=list)
    description: str = ""
    reason: str = ""  # why these constraints help

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReferencePrinciple:
    """A distilled principle from a reference track."""

    domain: str = ""  # "arrangement", "texture", "density", "width", "payoff", "emotional"
    principle: str = ""  # human-readable principle
    value: float = 0.0  # quantified where possible
    applicability: float = 0.5  # 0-1 how applicable to current song
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReferenceDistillation:
    """Distilled principles from a reference, ready to apply."""

    reference_id: str = ""
    reference_description: str = ""
    principles: list[ReferencePrinciple] = field(default_factory=list)
    emotional_posture: str = ""
    density_motion: str = ""
    arrangement_patience: str = ""
    texture_treatment: str = ""
    foreground_background: str = ""
    width_strategy: str = ""
    payoff_architecture: str = ""

    def to_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "reference_description": self.reference_description,
            "principles": [p.to_dict() for p in self.principles],
            "emotional_posture": self.emotional_posture,
            "density_motion": self.density_motion,
            "arrangement_patience": self.arrangement_patience,
            "texture_treatment": self.texture_treatment,
            "foreground_background": self.foreground_background,
            "width_strategy": self.width_strategy,
            "payoff_architecture": self.payoff_architecture,
            "principle_count": len(self.principles),
        }

"""SongBrain data models — pure dataclasses, zero I/O.

SongBrain is the runtime object that captures the musical identity of the
current piece.  It is distinct from project topology and from cross-session
user taste.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class SacredElement:
    """A musical element that should not be casually damaged."""

    element_type: str = ""  # "motif", "texture", "groove", "progression", "timbre"
    description: str = ""
    location: str = ""  # track/clip reference
    salience: float = 0.0  # 0-1 how central to identity
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SectionPurpose:
    """What a section is trying to do emotionally."""

    section_id: str = ""
    label: str = ""  # "intro", "verse", "chorus", "bridge", "breakdown", "outro"
    emotional_intent: str = ""  # "build tension", "release", "establish mood", etc.
    energy_level: float = 0.5  # 0-1
    is_payoff: bool = False  # whether this section should feel like an arrival
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OpenQuestion:
    """An unresolved creative question about the song."""

    question: str = ""
    domain: str = ""  # "arrangement", "mix", "harmony", "sound_design", "identity"
    priority: float = 0.5  # 0-1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SongBrain:
    """The musical identity of the current piece.

    Built from project brain, composition analysis, motif data, phrase
    similarity, role graph, and recent accepted moves.
    """

    brain_id: str = ""

    # Core identity
    identity_core: str = ""  # the strongest defining idea in the session
    identity_confidence: float = 0.5  # 0-1

    # Sacred elements
    sacred_elements: list[SacredElement] = field(default_factory=list)

    # Section purposes
    section_purposes: list[SectionPurpose] = field(default_factory=list)

    # Energy arc across sections (ordered floats 0-1)
    energy_arc: list[float] = field(default_factory=list)

    # Identity drift risk (0=stable, 1=drifting away from itself)
    identity_drift_risk: float = 0.0

    # Payoff targets — sections that should feel like arrival points
    payoff_targets: list[str] = field(default_factory=list)

    # Open questions the song has not resolved
    open_questions: list[OpenQuestion] = field(default_factory=list)

    # Evidence breakdown — what data informed each inference
    evidence_breakdown: dict = field(default_factory=dict)

    # Metadata
    built_from: dict = field(default_factory=dict)  # what data sources contributed

    def to_dict(self) -> dict:
        return {
            "brain_id": self.brain_id,
            "identity_core": self.identity_core,
            "identity_confidence": self.identity_confidence,
            "sacred_elements": [e.to_dict() for e in self.sacred_elements],
            "section_purposes": [s.to_dict() for s in self.section_purposes],
            "energy_arc": self.energy_arc,
            "identity_drift_risk": self.identity_drift_risk,
            "payoff_targets": self.payoff_targets,
            "open_questions": [q.to_dict() for q in self.open_questions],
            "evidence_breakdown": self.evidence_breakdown,
            "built_from": self.built_from,
        }

    @property
    def summary(self) -> str:
        """Human-readable one-line summary."""
        parts = []
        if self.identity_core:
            parts.append(f"Identity: {self.identity_core}")
        sacred_count = len(self.sacred_elements)
        if sacred_count:
            parts.append(f"{sacred_count} sacred element(s)")
        section_count = len(self.section_purposes)
        if section_count:
            parts.append(f"{section_count} section(s)")
        if self.identity_drift_risk > 0.3:
            parts.append(f"drift risk {self.identity_drift_risk:.0%}")
        return " | ".join(parts) if parts else "No identity established yet"


@dataclass
class IdentityDrift:
    """Result of comparing two SongBrain snapshots."""

    drift_score: float = 0.0  # 0=identical, 1=completely different
    changed_elements: list[str] = field(default_factory=list)
    sacred_damage: list[str] = field(default_factory=list)  # sacred elements affected
    energy_arc_shift: float = 0.0
    recommendation: str = ""  # "safe", "caution", "rollback_suggested"

    def to_dict(self) -> dict:
        return asdict(self)

"""Transition Engine state models — all dataclasses with to_dict().

Pure data structures for boundary analysis, transition planning,
archetype selection, and scoring.

Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


# ── Boundary ──────────────────────────────────────────────────────────


@dataclass
class TransitionBoundary:
    """The junction between two adjacent sections."""

    from_section_id: str = ""
    to_section_id: str = ""
    boundary_bar: int = 0
    from_type: str = "unknown"
    to_type: str = "unknown"
    energy_delta: float = 0.0   # positive = energy rises
    density_delta: float = 0.0  # positive = density rises

    def to_dict(self) -> dict:
        return asdict(self)


# ── Archetype ─────────────────────────────────────────────────────────


@dataclass
class TransitionArchetype:
    """A curated transition pattern with risk profile and verification cues."""

    name: str = ""
    description: str = ""
    use_cases: list[str] = field(default_factory=list)
    risk_profile: str = "low"  # "low", "medium", "high"
    devices: list[str] = field(default_factory=list)
    gestures: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Plan ──────────────────────────────────────────────────────────────


@dataclass
class TransitionPlan:
    """A concrete plan for executing a transition at a boundary."""

    boundary: TransitionBoundary = field(default_factory=TransitionBoundary)
    archetype: TransitionArchetype = field(default_factory=TransitionArchetype)
    lead_in_gestures: list[dict] = field(default_factory=list)
    arrival_gestures: list[dict] = field(default_factory=list)
    payoff_estimate: float = 0.0  # 0.0-1.0

    def to_dict(self) -> dict:
        return {
            "boundary": self.boundary.to_dict(),
            "archetype": self.archetype.to_dict(),
            "lead_in_gestures": list(self.lead_in_gestures),
            "arrival_gestures": list(self.arrival_gestures),
            "payoff_estimate": self.payoff_estimate,
        }


# ── Score ─────────────────────────────────────────────────────────────


@dataclass
class TransitionScore:
    """Multi-dimensional quality score for a transition."""

    boundary_clarity: float = 0.0      # 0.0-1.0
    payoff_strength: float = 0.0       # 0.0-1.0
    energy_redirection: float = 0.0    # 0.0-1.0
    identity_preservation: float = 0.0  # 0.0-1.0
    cliche_risk: float = 0.0           # 0.0-1.0 (lower is better)
    overall: float = 0.0              # 0.0-1.0

    def to_dict(self) -> dict:
        return asdict(self)

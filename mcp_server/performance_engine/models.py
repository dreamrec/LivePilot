"""Performance Engine state models — all dataclasses with to_dict().

Pure data structures for live performance mode:
SceneRole, EnergyWindow, LiveSafeMove, HandoffPlan, PerformanceState.

Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


# ── Valid values ──────────────────────────────────────────────────────

VALID_ROLES = frozenset({
    "intro", "verse", "chorus", "build", "drop",
    "breakdown", "outro", "transition",
})

VALID_RISK_LEVELS = frozenset({"safe", "caution", "blocked"})

VALID_DIRECTIONS = frozenset({"up", "down", "hold"})


# ── SceneRole ─────────────────────────────────────────────────────────


@dataclass
class SceneRole:
    """A scene's structural role and energy level."""

    scene_index: int = 0
    name: str = ""
    energy_level: float = 0.5
    role: str = "verse"

    def __post_init__(self) -> None:
        if not 0.0 <= self.energy_level <= 1.0:
            raise ValueError(
                f"energy_level must be 0.0-1.0, got {self.energy_level}"
            )
        if self.role not in VALID_ROLES:
            raise ValueError(
                f"role must be one of {sorted(VALID_ROLES)}, got {self.role!r}"
            )

    def to_dict(self) -> dict:
        return asdict(self)


# ── EnergyWindow ──────────────────────────────────────────────────────


@dataclass
class EnergyWindow:
    """Current energy state and steering intent."""

    current_energy: float = 0.5
    target_energy: float = 0.5
    direction: str = "hold"
    urgency: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.current_energy <= 1.0:
            raise ValueError(
                f"current_energy must be 0.0-1.0, got {self.current_energy}"
            )
        if not 0.0 <= self.target_energy <= 1.0:
            raise ValueError(
                f"target_energy must be 0.0-1.0, got {self.target_energy}"
            )
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {sorted(VALID_DIRECTIONS)}, "
                f"got {self.direction!r}"
            )
        if not 0.0 <= self.urgency <= 1.0:
            raise ValueError(
                f"urgency must be 0.0-1.0, got {self.urgency}"
            )

    def to_dict(self) -> dict:
        return asdict(self)


# ── LiveSafeMove ──────────────────────────────────────────────────────


@dataclass
class LiveSafeMove:
    """A single performance-safe move suggestion."""

    move_type: str = ""
    target: str = ""
    description: str = ""
    risk_level: str = "safe"
    parameters: dict = field(default_factory=dict)
    reversible: bool = True

    def __post_init__(self) -> None:
        if self.risk_level not in VALID_RISK_LEVELS:
            raise ValueError(
                f"risk_level must be one of {sorted(VALID_RISK_LEVELS)}, "
                f"got {self.risk_level!r}"
            )

    def to_dict(self) -> dict:
        return asdict(self)


# ── HandoffPlan ───────────────────────────────────────────────────────


@dataclass
class HandoffPlan:
    """Transition plan from one scene to another."""

    from_scene: int = 0
    to_scene: int = 0
    gestures: list[dict] = field(default_factory=list)
    energy_path: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── PerformanceState ──────────────────────────────────────────────────


@dataclass
class PerformanceState:
    """Top-level container for live performance state."""

    scenes: list[SceneRole] = field(default_factory=list)
    current_scene: int = 0
    energy_window: EnergyWindow = field(default_factory=EnergyWindow)
    safe_moves: list[LiveSafeMove] = field(default_factory=list)
    blocked_moves: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scenes": [s.to_dict() for s in self.scenes],
            "current_scene": self.current_scene,
            "energy_window": self.energy_window.to_dict(),
            "safe_moves": [m.to_dict() for m in self.safe_moves],
            "blocked_moves": list(self.blocked_moves),
        }

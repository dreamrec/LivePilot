"""Mix Engine state models — all dataclasses with to_dict().

Pure data structures representing the five mix subgraphs
(BalanceState, MaskingMap, DynamicsState, StereoState, DepthState)
plus the composite MixState container.

Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Track-level state ───────────────────────────────────────────────


@dataclass
class TrackMixState:
    """Mix-relevant state for a single track."""

    track_index: int = 0
    name: str = ""
    role: str = "unknown"
    volume: float = 0.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    send_levels: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Balance ─────────────────────────────────────────────────────────


@dataclass
class BalanceState:
    """Track-level and role-weighted loudness balance."""

    track_states: list[TrackMixState] = field(default_factory=list)
    anchor_tracks: list[int] = field(default_factory=list)
    loudest_track: int = -1
    quietest_track: int = -1

    def to_dict(self) -> dict:
        return {
            "track_states": [t.to_dict() for t in self.track_states],
            "anchor_tracks": list(self.anchor_tracks),
            "loudest_track": self.loudest_track,
            "quietest_track": self.quietest_track,
        }


# ── Masking ─────────────────────────────────────────────────────────


@dataclass
class MaskingEntry:
    """A single frequency masking collision between two tracks."""

    track_a: int = 0
    track_b: int = 0
    overlap_band: str = ""
    severity: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MaskingMap:
    """All detected frequency masking collisions."""

    entries: list[MaskingEntry] = field(default_factory=list)
    worst_pair: Optional[tuple[int, int]] = None

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "worst_pair": list(self.worst_pair) if self.worst_pair else None,
        }


# ── Dynamics ────────────────────────────────────────────────────────


@dataclass
class DynamicsState:
    """Master dynamics condition."""

    crest_factor_db: float = 0.0
    over_compressed: bool = False
    headroom: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Stereo ──────────────────────────────────────────────────────────


@dataclass
class StereoState:
    """Stereo field condition."""

    center_strength: float = 0.0
    side_activity: float = 0.0
    mono_risk: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── Depth ───────────────────────────────────────────────────────────


@dataclass
class DepthState:
    """Front-to-back depth separation."""

    wet_dry_ratio: float = 0.0
    depth_separation: float = 0.0
    wash_risk: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── Composite container ────────────────────────────────────────────


@dataclass
class MixState:
    """Top-level container for all mix sub-states."""

    balance: BalanceState = field(default_factory=BalanceState)
    masking: MaskingMap = field(default_factory=MaskingMap)
    dynamics: DynamicsState = field(default_factory=DynamicsState)
    stereo: StereoState = field(default_factory=StereoState)
    depth: DepthState = field(default_factory=DepthState)

    def to_dict(self) -> dict:
        return {
            "balance": self.balance.to_dict(),
            "masking": self.masking.to_dict(),
            "dynamics": self.dynamics.to_dict(),
            "stereo": self.stereo.to_dict(),
            "depth": self.depth.to_dict(),
        }

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
    """A single frequency masking collision between two tracks.

    Fields
    ------
    track_a, track_b : int
        Track indices of the colliding pair.
    overlap_band : str
        Frequency band where the collision is strongest (e.g. "sub", "low").
    severity : float
        0–1 collision severity.  When ``measured`` is True this reflects
        actual per-track band energy overlap; when False it is a role-pair
        heuristic constant from the collision-rule table.
    measured : bool
        True  → severity was scaled by real per-track spectral data.
        False → severity is a role-prior heuristic (no per-track spectrum).
    severity_basis : str
        Human-readable label for the severity origin.
        Either "spectral_overlap" (measured) or "role_heuristic" (heuristic).
    """

    track_a: int = 0
    track_b: int = 0
    overlap_band: str = ""
    severity: float = 0.0
    measured: bool = False
    severity_basis: str = "role_heuristic"

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

    def evidence_summary(self) -> dict:
        """Describe what each sub-state actually measures.

        Fader positions, pan, and sends are useful setup evidence, but they are
        not interchangeable with hearing each track. This label travels with
        every public Mix Engine response so callers can calibrate claims.
        """
        measured_masking = sum(1 for entry in self.masking.entries if entry.measured)
        heuristic_masking = len(self.masking.entries) - measured_masking
        if measured_masking and not heuristic_masking:
            masking_basis = "per_track_audio"
        elif measured_masking:
            masking_basis = "mixed_per_track_audio_and_role_heuristic"
        elif heuristic_masking:
            masking_basis = "role_heuristic"
        else:
            masking_basis = "unavailable_or_no_candidate_pairs"

        if measured_masking:
            scope = "per_track_audio_and_mix_setup"
        elif self.dynamics.headroom is not None:
            scope = "master_audio_and_mix_setup"
        else:
            scope = "mix_setup_audit"

        return {
            "analysis_scope": scope,
            "balance": "fader_and_role_setup",
            "masking": masking_basis,
            "dynamics": (
                "master_audio" if self.dynamics.headroom is not None else "unavailable"
            ),
            "stereo": "pan_position_proxy",
            "depth": "send_level_proxy",
            "measured_masking_entries": measured_masking,
            "heuristic_masking_entries": heuristic_masking,
        }

    def to_dict(self) -> dict:
        evidence = self.evidence_summary()
        return {
            "balance": self.balance.to_dict(),
            "masking": self.masking.to_dict(),
            "dynamics": self.dynamics.to_dict(),
            "stereo": self.stereo.to_dict(),
            "depth": self.depth.to_dict(),
            "analysis_scope": evidence["analysis_scope"],
            "evidence": evidence,
        }

"""Reference Engine state models — all dataclasses with to_dict().

Pure data structures for reference profiles, gap reports, and tactic plans.
Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Reference Profile ──────────────────────────────────────────────


@dataclass
class ReferenceProfile:
    """Multi-dimensional snapshot of a reference target.

    Built from audio analysis, style tactic data, user descriptions,
    or project-internal section comparisons.
    """

    source_type: str = "audio"  # "audio", "style", "user_described", "internal_section"
    loudness_posture: float = 0.0  # integrated LUFS
    spectral_contour: dict = field(default_factory=dict)  # band_balance + centroid
    width_depth: dict = field(default_factory=dict)  # stereo width, depth hints
    density_arc: list[float] = field(default_factory=list)  # per-section density 0-1
    section_pacing: list[dict] = field(default_factory=list)  # [{label, bars, energy}]
    harmonic_character: str = ""  # e.g. "minor_modal", "chromatic", "diatonic_major"
    transition_tendencies: list[str] = field(default_factory=list)  # gesture names

    def to_dict(self) -> dict:
        return asdict(self)


# ── Gap Entry / Report ─────────────────────────────────────────────


@dataclass
class GapEntry:
    """A single measured difference between project and reference."""

    domain: str = ""  # "spectral", "loudness", "density", "width", "pacing", "harmonic"
    delta: float = 0.0  # signed difference (project - reference)
    relevant: bool = True  # whether the user's goal cares about this
    identity_warning: bool = False  # closing this gap risks flattening identity
    suggested_tactic: str = ""  # short tactic label

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GapReport:
    """All gaps between a project snapshot and a reference profile."""

    reference_id: str = ""
    gaps: list[GapEntry] = field(default_factory=list)
    overall_distance: float = 0.0  # aggregate distance metric

    @property
    def relevant_gaps(self) -> list[GapEntry]:
        """Return only gaps marked as relevant to the user's goal."""
        return [g for g in self.gaps if g.relevant]

    @property
    def identity_warnings(self) -> list[str]:
        """Return warning messages for gaps that threaten project identity."""
        warnings: list[str] = []
        for g in self.gaps:
            if g.identity_warning:
                warnings.append(
                    f"Closing the {g.domain} gap (delta={g.delta:+.2f}) "
                    f"may flatten your project's identity"
                )
        return warnings

    def to_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "gaps": [g.to_dict() for g in self.gaps],
            "relevant_gaps": [g.to_dict() for g in self.relevant_gaps],
            "identity_warnings": self.identity_warnings,
            "overall_distance": self.overall_distance,
        }


# ── Reference Plan ─────────────────────────────────────────────────


@dataclass
class ReferencePlan:
    """Actionable plan derived from a gap report."""

    gap_report: GapReport = field(default_factory=GapReport)
    ranked_tactics: list[dict] = field(default_factory=list)
    target_engines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "gap_report": self.gap_report.to_dict(),
            "ranked_tactics": list(self.ranked_tactics),
            "target_engines": list(self.target_engines),
        }

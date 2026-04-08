"""Project Brain data models — all dataclasses with to_dict().

Zero I/O.  Pure data structures representing the five subgraphs
(SessionGraph, ArrangementGraph, RoleGraph, AutomationGraph,
CapabilityGraph) plus freshness/confidence metadata.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Freshness ────────────────────────────────────────────────────────


@dataclass
class FreshnessInfo:
    """Tracks when a subgraph was built and whether it is stale."""

    built_at_ms: float = 0.0
    source_revision: int = 0
    stale: bool = True
    stale_reason: Optional[str] = "never built"

    def mark_fresh(self, revision: int) -> None:
        self.built_at_ms = time.time() * 1000
        self.source_revision = revision
        self.stale = False
        self.stale_reason = None

    def mark_stale(self, reason: str) -> None:
        self.stale = True
        self.stale_reason = reason

    def to_dict(self) -> dict:
        return {
            "built_at_ms": self.built_at_ms,
            "source_revision": self.source_revision,
            "stale": self.stale,
            "stale_reason": self.stale_reason,
        }


# ── Confidence ───────────────────────────────────────────────────────


@dataclass
class ConfidenceInfo:
    """Confidence summary for inference-bearing graphs."""

    overall: float = 0.0
    low_confidence_nodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "low_confidence_nodes": list(self.low_confidence_nodes),
        }


# ── SessionGraph ─────────────────────────────────────────────────────


@dataclass
class TrackNode:
    """A single track in the session."""

    index: int = 0
    name: str = ""
    has_midi: bool = False
    has_audio: bool = False
    mute: bool = False
    solo: bool = False
    arm: bool = False
    group_index: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "has_midi": self.has_midi,
            "has_audio": self.has_audio,
            "mute": self.mute,
            "solo": self.solo,
            "arm": self.arm,
            "group_index": self.group_index,
        }


@dataclass
class SessionGraph:
    """Physical/session topology — tracks, returns, scenes, tempo."""

    tracks: list[TrackNode] = field(default_factory=list)
    return_tracks: list[dict] = field(default_factory=list)
    scenes: list[dict] = field(default_factory=list)
    tempo: float = 120.0
    time_signature: str = "4/4"
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def add_track(self, track: TrackNode) -> None:
        self.tracks.append(track)

    def to_dict(self) -> dict:
        return {
            "tracks": [t.to_dict() for t in self.tracks],
            "return_tracks": list(self.return_tracks),
            "scenes": list(self.scenes),
            "tempo": self.tempo,
            "time_signature": self.time_signature,
            "freshness": self.freshness.to_dict(),
        }


# ── ArrangementGraph ─────────────────────────────────────────────────


@dataclass
class SectionNode:
    """A section in the arrangement timeline."""

    section_id: str = ""
    start_bar: int = 0
    end_bar: int = 0
    section_type: str = "unknown"
    energy: float = 0.0
    density: float = 0.0

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "start_bar": self.start_bar,
            "end_bar": self.end_bar,
            "section_type": self.section_type,
            "energy": self.energy,
            "density": self.density,
        }


@dataclass
class ArrangementGraph:
    """Time-structure layer — sections, boundaries, cue points."""

    sections: list[SectionNode] = field(default_factory=list)
    boundaries: list[dict] = field(default_factory=list)
    cue_points: list[dict] = field(default_factory=list)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def to_dict(self) -> dict:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "boundaries": list(self.boundaries),
            "cue_points": list(self.cue_points),
            "freshness": self.freshness.to_dict(),
        }


# ── RoleGraph ────────────────────────────────────────────────────────


@dataclass
class RoleNode:
    """Maps a musical function to a track within a section."""

    track_index: int = 0
    section_id: str = ""
    role: str = "unknown"
    confidence: float = 0.0
    foreground: bool = False

    def to_dict(self) -> dict:
        return {
            "track_index": self.track_index,
            "section_id": self.section_id,
            "role": self.role,
            "confidence": self.confidence,
            "foreground": self.foreground,
        }


@dataclass
class RoleGraph:
    """Musical function assignments across tracks and sections."""

    roles: list[RoleNode] = field(default_factory=list)
    confidence: ConfidenceInfo = field(default_factory=ConfidenceInfo)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def add_role(self, role: RoleNode) -> None:
        self.roles.append(role)

    def to_dict(self) -> dict:
        return {
            "roles": [r.to_dict() for r in self.roles],
            "confidence": self.confidence.to_dict(),
            "freshness": self.freshness.to_dict(),
        }


# ── AutomationGraph ──────────────────────────────────────────────────


@dataclass
class AutomationGraph:
    """Automation presence and gesture density."""

    automated_params: list[dict] = field(default_factory=list)
    density_by_section: dict[str, float] = field(default_factory=dict)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def to_dict(self) -> dict:
        return {
            "automated_params": list(self.automated_params),
            "density_by_section": dict(self.density_by_section),
            "freshness": self.freshness.to_dict(),
        }


# ── CapabilityGraph ──────────────────────────────────────────────────


@dataclass
class CapabilityGraph:
    """Runtime capability awareness — what tools/features are available."""

    analyzer_available: bool = False
    flucoma_available: bool = False
    plugin_health: dict[str, Any] = field(default_factory=dict)
    research_providers: list[str] = field(default_factory=list)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def to_dict(self) -> dict:
        return {
            "analyzer_available": self.analyzer_available,
            "flucoma_available": self.flucoma_available,
            "plugin_health": dict(self.plugin_health),
            "research_providers": list(self.research_providers),
            "freshness": self.freshness.to_dict(),
        }


# ── ProjectState ─────────────────────────────────────────────────────


@dataclass
class ProjectState:
    """Top-level container — one canonical project snapshot."""

    project_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    revision: int = 0
    session_graph: SessionGraph = field(default_factory=SessionGraph)
    arrangement_graph: ArrangementGraph = field(default_factory=ArrangementGraph)
    role_graph: RoleGraph = field(default_factory=RoleGraph)
    automation_graph: AutomationGraph = field(default_factory=AutomationGraph)
    capability_graph: CapabilityGraph = field(default_factory=CapabilityGraph)
    active_issues: list[dict] = field(default_factory=list)

    def is_stale(self) -> bool:
        """True if any subgraph is stale."""
        return any([
            self.session_graph.freshness.stale,
            self.arrangement_graph.freshness.stale,
            self.role_graph.freshness.stale,
            self.automation_graph.freshness.stale,
            self.capability_graph.freshness.stale,
        ])

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "revision": self.revision,
            "session_graph": self.session_graph.to_dict(),
            "arrangement_graph": self.arrangement_graph.to_dict(),
            "role_graph": self.role_graph.to_dict(),
            "automation_graph": self.automation_graph.to_dict(),
            "capability_graph": self.capability_graph.to_dict(),
            "active_issues": list(self.active_issues),
            "is_stale": self.is_stale(),
        }

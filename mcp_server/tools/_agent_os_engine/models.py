"""Part of the _agent_os_engine package — extracted from the single-file engine.

Pure-computation core. Callers should import from the package facade
(`from mcp_server.tools._agent_os_engine import X`), which re-exports from
these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# ── Shared utility ────────────────────────────────────────────────────
def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi] range. Shared across evaluation + taste."""
    return max(lo, min(hi, value))


# ── Quality Dimensions ────────────────────────────────────────────────
QUALITY_DIMENSIONS = frozenset({
    "energy", "punch", "weight", "density", "brightness", "warmth",
    "width", "depth", "motion", "contrast", "clarity", "cohesion",
    "groove", "tension", "novelty", "polish", "emotion",
})

MEASURABLE_PROXIES: dict[str, str] = {
    "brightness": "high + presence bands (averaged)",
    "warmth": "low_mid band energy",
    "weight": "sub + low bands (averaged)",
    "clarity": "inverse of low_mid congestion",
    "density": "spectral flatness (geometric/arithmetic mean ratio)",
    "energy": "RMS level",
    "punch": "crest factor in dB (20*log10(peak/rms))",
}

VALID_MODES = frozenset({"observe", "improve", "explore", "finish", "diagnose"})

VALID_RESEARCH_MODES = frozenset({"none", "targeted", "deep"})


# ── GoalVector ────────────────────────────────────────────────────────
@dataclass
class GoalVector:
    """Compiled user intent as a machine-usable goal.

    targets: dimension → weight (0-1). Weights should approximately sum to 1.0.
    protect: dimension → minimum acceptable value (0-1). If a dimension drops
             below this value after a move, the move is undone.
    """
    request_text: str
    targets: dict[str, float] = field(default_factory=dict)
    protect: dict[str, float] = field(default_factory=dict)
    mode: str = "improve"
    aggression: float = 0.5
    research_mode: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)

_ROLE_PATTERNS: list[tuple[str, str]] = [
    (r"kick|bd|bass\s*drum", "kick"),
    (r"snare|sd|snr", "snare"),
    (r"clap|cp|hand\s*clap", "clap"),
    (r"h(?:i)?[\s\-]?hat|hh|hat", "hihat"),
    (r"perc|percussion|conga|bongo|shaker|tamb", "percussion"),
    (r"sub\s*bass|sub", "sub_bass"),
    (r"bass|low", "bass"),
    (r"pad|atmosphere|atmo|ambient|drone", "pad"),
    (r"lead|melody|mel|synth\s*lead", "lead"),
    (r"chord|keys|piano|organ|rhodes", "chords"),
    (r"vocal|vox|voice", "vocal"),
    (r"fx|sfx|riser|sweep|noise|texture|tape", "texture"),
    (r"string", "strings"),
    (r"brass", "brass"),
    (r"resamp|bounce|bus|group|master", "utility"),
]

@dataclass
class WorldModel:
    """Session state snapshot for critic analysis."""
    topology: dict = field(default_factory=dict)
    sonic: Optional[dict] = None
    technical: dict = field(default_factory=dict)
    track_roles: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Critics ───────────────────────────────────────────────────────────
@dataclass
class Issue:
    """A diagnosed problem or opportunity."""
    type: str
    critic: str  # "sonic" or "technical"
    severity: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    affected_dimensions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Technique Cards (Round 2) ─────────────────────────────────────────
@dataclass
class TechniqueCard:
    """A structured, reusable production recipe — not just text."""
    problem: str
    context: list[str] = field(default_factory=list)  # genre/style tags
    devices: list[str] = field(default_factory=list)  # what to load
    method: str = ""  # step-by-step instructions
    verification: list[str] = field(default_factory=list)  # what to check after
    evidence: dict = field(default_factory=dict)  # {sources, in_session_tested}

    def to_dict(self) -> dict:
        return asdict(self)

    def to_memory_payload(self) -> dict:
        """Convert to a payload suitable for memory_learn(type='technique_card')."""
        return {
            "problem": self.problem,
            "context": self.context,
            "devices": self.devices,
            "method": self.method,
            "verification": self.verification,
            "evidence": self.evidence,
        }


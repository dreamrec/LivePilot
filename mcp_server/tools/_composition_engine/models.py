"""Part of the _composition_engine package — extracted from the single-file engine.

Pure-computation core, no external deps. Callers should import from the package
facade (e.g. `from mcp_server.tools._composition_engine import X`), which
re-exports everything from these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Enums ─────────────────────────────────────────────────────────────
class SectionType(str, Enum):
    LOOP = "loop"
    INTRO = "intro"
    VERSE = "verse"
    PRE_CHORUS = "pre_chorus"
    CHORUS = "chorus"
    BUILD = "build"
    DROP = "drop"
    BRIDGE = "bridge"
    BREAKDOWN = "breakdown"
    OUTRO = "outro"
    UNKNOWN = "unknown"

class RoleType(str, Enum):
    KICK_ANCHOR = "kick_anchor"
    BASS_ANCHOR = "bass_anchor"
    HOOK = "hook"
    LEAD = "lead"
    HARMONY_BED = "harmony_bed"
    RHYTHMIC_TEXTURE = "rhythmic_texture"
    TEXTURE_WASH = "texture_wash"
    TRANSITION_FX = "transition_fx"
    UTILITY = "utility"
    UNKNOWN = "unknown"

class GestureIntent(str, Enum):
    REVEAL = "reveal"
    CONCEAL = "conceal"
    HANDOFF = "handoff"
    INHALE = "inhale"
    RELEASE = "release"
    LIFT = "lift"
    SINK = "sink"
    PUNCTUATE = "punctuate"
    DRIFT = "drift"

@dataclass
class SectionNode:
    """A section of the arrangement with inferred type and energy."""
    section_id: str
    start_bar: int
    end_bar: int
    section_type: SectionType
    confidence: float  # 0.0-1.0
    energy: float  # 0.0-1.0 (relative within the track)
    density: float  # 0.0-1.0 (how many tracks are active)
    tracks_active: list[int] = field(default_factory=list)
    name: str = ""

    def length_bars(self) -> int:
        return self.end_bar - self.start_bar

    def to_dict(self) -> dict:
        d = asdict(self)
        d["section_type"] = self.section_type.value
        d["length_bars"] = self.length_bars()
        return d


# ── Phrase Grid ───────────────────────────────────────────────────────
@dataclass
class PhraseUnit:
    """A musical phrase within a section."""
    phrase_id: str
    section_id: str
    start_bar: int
    end_bar: int
    cadence_strength: float  # 0.0-1.0 (how strongly it resolves)
    note_density: float  # notes per bar
    has_variation: bool  # differs from adjacent phrases

    def length_bars(self) -> int:
        return self.end_bar - self.start_bar

    def to_dict(self) -> dict:
        d = asdict(self)
        d["length_bars"] = self.length_bars()
        return d


# ── Role Inference ────────────────────────────────────────────────────
@dataclass
class RoleNode:
    """A track's musical role within a specific section."""
    track_index: int
    track_name: str
    section_id: str
    role: RoleType
    confidence: float  # 0.0-1.0
    foreground: bool  # is this a focal element?

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        return d


# ── Composition Critics ───────────────────────────────────────────────
@dataclass
class CompositionIssue:
    """A structural or musical problem detected by a critic."""
    issue_type: str
    critic: str  # "form", "section_identity", "phrase"
    severity: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    scope: dict = field(default_factory=dict)  # e.g., {"section_id": "sec_01"}
    recommended_moves: list[str] = field(default_factory=list)
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class GesturePlan:
    """A concrete automation plan derived from a musical gesture intent."""
    gesture_id: str
    intent: GestureIntent
    description: str
    target_tracks: list[int]
    parameter_hints: list[str]
    curve_family: str
    direction: str
    start_bar: int
    end_bar: int
    foreground: bool  # is this a musical focus or background motion?

    def to_dict(self) -> dict:
        d = asdict(self)
        d["intent"] = self.intent.value
        d["duration_bars"] = self.end_bar - self.start_bar
        return d


# ── Full Analysis Pipeline ────────────────────────────────────────────
@dataclass
class CompositionAnalysis:
    """Complete composition analysis result."""
    sections: list[SectionNode]
    phrases: list[PhraseUnit]
    roles: list[RoleNode]
    issues: list[CompositionIssue]

    def to_dict(self) -> dict:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "section_count": len(self.sections),
            "phrases": [p.to_dict() for p in self.phrases],
            "phrase_count": len(self.phrases),
            "roles": [r.to_dict() for r in self.roles],
            "role_count": len(self.roles),
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": len(self.issues),
            "issue_summary": {
                "form": len([i for i in self.issues if i.critic == "form"]),
                "section_identity": len([i for i in self.issues if i.critic == "section_identity"]),
                "phrase": len([i for i in self.issues if i.critic == "phrase"]),
                "transition": len([i for i in self.issues if i.critic == "transition"]),
            },
        }


# ── Harmony Field (Round 1) ──────────────────────────────────────────
@dataclass
class HarmonyField:
    """Harmonic analysis of a section — key, chords, voice-leading, tension."""
    section_id: str
    key: str = ""
    mode: str = ""
    confidence: float = 0.0
    chord_progression: list[str] = field(default_factory=list)
    voice_leading_quality: float = 0.5  # 0=rough, 1=smooth
    instability: float = 0.0  # 0=stable/tonic, 1=highly unstable
    resolution_potential: float = 0.5  # tendency toward resolution

    def to_dict(self) -> dict:
        return asdict(self)


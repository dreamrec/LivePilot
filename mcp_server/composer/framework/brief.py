"""Brief dataclasses — uniform shape across the 3 compose modes (fast/full/develop).

The framework provides VOCABULARY (descriptive). The LLM provides FORM (creative).
Briefs MUST NOT carry predetermined section sequences, bar counts, or variant taxonomies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from typing import Optional, Type, TypeVar


T = TypeVar("T", bound="Brief")


@dataclass(frozen=True)
class Brief:
    """Base — every compose mode returns a Brief subclass.

    Common fields shared across all modes. Subclasses extend with mode-
    specific fields (instruments_by_role, design_targets, seed_state, etc.).
    """
    mode: str
    tempo: float
    key: Optional[str]
    intent: dict
    knowledge: dict

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict including subclass fields."""
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], data: dict) -> T:
        """Deserialize from a dict.

        Filters out unknown keys (forward-compatibility) and uses dataclass
        defaults for missing optional fields.
        """
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass(frozen=True)
class FastBrief(Brief):
    """Loop-sketch brief — agent designs MIDI inline.

    instruments_by_role: dict mapping role name → list of atlas device candidates
    scale_pitches: list of MIDI pitches in the inferred key/scale
    """
    instruments_by_role: dict = field(default_factory=dict)
    scale_pitches: list = field(default_factory=list)


@dataclass(frozen=True)
class FullBrief(Brief):
    """Full-track brief — agent designs FORM and notes per call.

    NB: must NOT include section_sequence, bar_counts, or form_template
    fields per the vocabulary-not-form principle.

    research_hooks: list of niche-style terms the agent should research
                    before designing (WebSearch directives)
    design_targets: open-ended description of what the agent should produce
    """
    research_hooks: list = field(default_factory=list)
    design_targets: str = ""


@dataclass(frozen=True)
class DevelopBrief(Brief):
    """Loop-extension brief — agent designs variants per call.

    seed_state: introspected SeedState dict (key, tempo, role classification, motif)
    identity_preservation_directive: explicit guidance that seed must survive
    """
    seed_state: dict = field(default_factory=dict)
    identity_preservation_directive: str = ""

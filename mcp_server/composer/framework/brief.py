"""Brief dataclasses — uniform shape across the 3 compose modes."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Brief:
    """Base — every compose mode returns a Brief subclass.

    The framework provides VOCABULARY (descriptive). The LLM provides FORM (creative).
    Briefs MUST NOT carry predetermined section sequences, bar counts, or variant taxonomies.
    """
    mode: str
    tempo: float
    key: Optional[str]
    intent: dict
    knowledge: dict


@dataclass(frozen=True)
class FastBrief(Brief):
    """Loop-sketch brief — agent designs MIDI inline. Phase 1 stub."""
    instruments_by_role: dict = field(default_factory=dict)
    scale_pitches: list = field(default_factory=list)


@dataclass(frozen=True)
class FullBrief(Brief):
    """Full-track brief — agent designs FORM and notes per call. Phase 1 stub.

    NB: must NOT include section_sequence, bar_counts, or form_template fields
    per the vocabulary-not-form principle.
    """
    research_hooks: list = field(default_factory=list)
    design_targets: str = ""


@dataclass(frozen=True)
class DevelopBrief(Brief):
    """Loop-extension brief — agent designs variants per call. Phase 1 stub."""
    seed_state: dict = field(default_factory=dict)
    identity_preservation_directive: str = ""

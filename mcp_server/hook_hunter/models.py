"""Hook Hunter data models — pure dataclasses, zero I/O."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class HookCandidate:
    """A potential hook element in the track."""

    hook_id: str = ""
    hook_type: str = ""  # "melodic", "rhythmic", "timbral", "harmonic", "textural"
    description: str = ""
    location: str = ""  # track/clip reference
    memorability: float = 0.0  # 0-1 how catchy/memorable
    recurrence: float = 0.0  # 0-1 how often it appears
    contrast_potential: float = 0.0  # 0-1 how well it stands out
    development_potential: float = 0.0  # 0-1 how much room to develop
    salience: float = 0.0  # composite score

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PhraseImpact:
    """Phrase-level emotional impact scoring."""

    phrase_id: str = ""
    target: str = ""  # "hook", "drop", "chorus", "transition", "loop"
    arrival_strength: float = 0.0  # 0-1 does it feel like an arrival?
    anticipation_strength: float = 0.0  # 0-1 does the setup work?
    contrast_quality: float = 0.0  # 0-1 is there enough change?
    repetition_fatigue: float = 0.0  # 0-1 is it overused?
    section_clarity: float = 0.0  # 0-1 is the section role clear?
    groove_continuity: float = 0.0  # 0-1 does the groove carry through?
    payoff_balance: float = 0.0  # 0-1 setup vs payoff balance
    composite_impact: float = 0.0  # weighted aggregate

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PayoffFailure:
    """A detected payoff failure — where the song should deliver but doesn't."""

    section_id: str = ""
    expected_target: str = ""  # "drop", "chorus", "hook"
    failure_type: str = ""  # "flat_arrival", "weak_contrast", "no_setup", "hook_absent"
    severity: float = 0.0  # 0-1
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

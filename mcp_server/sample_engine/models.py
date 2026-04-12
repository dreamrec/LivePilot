"""Sample Engine data models — all dataclasses with to_dict().

Pure data structures for sample profiles, intents, critic results,
fit reports, candidates, and techniques. Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


VALID_MATERIAL_TYPES = frozenset({
    "vocal", "drum_loop", "instrument_loop", "one_shot",
    "texture", "foley", "fx", "full_mix", "unknown",
})

VALID_INTENTS = frozenset({
    "rhythm", "texture", "layer", "melody", "vocal",
    "atmosphere", "transform", "challenge",
})

VALID_SIMPLER_MODES = frozenset({"classic", "one_shot", "slice"})

VALID_SLICE_METHODS = frozenset({"transient", "beat", "region", "manual"})

VALID_WARP_MODES = frozenset({
    "beats", "tones", "texture", "complex", "complex_pro",
})


@dataclass
class SampleProfile:
    """Complete fingerprint of a sample."""

    source: str
    file_path: str
    name: str
    uri: Optional[str] = None
    freesound_id: Optional[int] = None
    license: Optional[str] = None

    key: Optional[str] = None
    key_confidence: float = 0.0
    bpm: Optional[float] = None
    bpm_confidence: float = 0.0
    time_signature: str = "4/4"

    material_type: str = "unknown"
    material_confidence: float = 0.0

    frequency_center: float = 0.0
    frequency_spread: float = 0.0
    brightness: float = 0.0
    transient_density: float = 0.0

    duration_seconds: float = 0.0
    duration_beats: Optional[float] = None
    bar_count: Optional[float] = None
    has_clear_downbeat: bool = False

    suggested_mode: str = "classic"
    suggested_slice_by: str = "transient"
    suggested_warp_mode: str = "complex"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SampleIntent:
    """What the user wants to do with a sample."""

    intent_type: str
    description: str
    philosophy: str = "auto"
    target_track: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CriticResult:
    """Result from a single sample critic."""

    critic_name: str
    score: float
    recommendation: str
    adjustments: list = field(default_factory=list)

    @property
    def rating(self) -> str:
        if self.score >= 0.8:
            return "excellent"
        if self.score >= 0.6:
            return "good"
        if self.score >= 0.4:
            return "fair"
        return "poor"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rating"] = self.rating
        return d


@dataclass
class SampleFitReport:
    """Output of the 6-critic battery."""

    sample: SampleProfile
    critics: dict  # str -> CriticResult
    recommended_intent: str = ""
    recommended_technique: str = ""
    processing_chain: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    surgeon_plan: list = field(default_factory=list)
    alchemist_plan: list = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        if not self.critics:
            return 0.0
        scores = [c.score if isinstance(c, CriticResult) else c.get("score", 0)
                  for c in self.critics.values()]
        return sum(scores) / len(scores) if scores else 0.0

    def to_dict(self) -> dict:
        return {
            "sample": self.sample.to_dict(),
            "overall_score": round(self.overall_score, 3),
            "critics": {k: (v.to_dict() if isinstance(v, CriticResult) else v)
                        for k, v in self.critics.items()},
            "recommended_intent": self.recommended_intent,
            "recommended_technique": self.recommended_technique,
            "processing_chain": self.processing_chain,
            "warnings": self.warnings,
            "surgeon_plan": self.surgeon_plan,
            "alchemist_plan": self.alchemist_plan,
        }


@dataclass
class SampleCandidate:
    """A sample discovered by a source, pre-load."""

    source: str
    name: str
    metadata: dict = field(default_factory=dict)
    file_path: Optional[str] = None
    uri: Optional[str] = None
    freesound_id: Optional[int] = None
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TechniqueStep:
    """A single step in a sample technique recipe."""

    tool: str
    params: dict = field(default_factory=dict)
    description: str = ""
    condition: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SampleTechnique:
    """A sample manipulation recipe from the technique library."""

    technique_id: str
    name: str
    philosophy: str
    material_types: list = field(default_factory=list)
    intents: list = field(default_factory=list)
    difficulty: str = "basic"
    description: str = ""
    inspiration: str = ""
    steps: list = field(default_factory=list)  # list[TechniqueStep]
    success_signals: list = field(default_factory=list)
    failure_signals: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [s.to_dict() if isinstance(s, TechniqueStep) else s
                      for s in self.steps]
        return d

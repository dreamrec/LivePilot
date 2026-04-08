"""Translation Engine models — all dataclasses with to_dict().

Pure data structures for playback robustness analysis.
Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List


@dataclass
class TranslationReport:
    """Full playback robustness report."""

    mono_safe: bool = True
    small_speaker_safe: bool = True
    harshness_risk: float = 0.0  # 0-1
    low_end_stable: bool = True
    front_element_present: bool = True
    overall_robustness: str = "robust"  # "robust", "fragile", "critical"
    issues: List[dict] = field(default_factory=list)
    suggested_moves: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

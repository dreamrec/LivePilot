"""TasteMemory — extended taste tracking beyond quality dimensions.

Pure Python, zero I/O.  Infers user taste from kept/undone outcomes
across 8 production dimensions so that planners can bias toward preferences.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


EXTENDED_TASTE_DIMENSIONS = [
    "transition_boldness",
    "automation_density",
    "dryness_preference",
    "harmonic_boldness",
    "width_preference",
    "native_vs_plugin",
    "density_tolerance",
    "fx_intensity",
]

# Maps outcome signals to taste dimension adjustments.
# Each key is a dimension name; values map (outcome_signal -> adjustment).
_OUTCOME_SIGNALS: dict[str, dict[str, float]] = {
    "transition_boldness": {
        "bold_transition_kept": 0.15,
        "bold_transition_undone": -0.15,
        "subtle_transition_kept": -0.10,
        "subtle_transition_undone": 0.10,
    },
    "automation_density": {
        "dense_automation_kept": 0.12,
        "dense_automation_undone": -0.12,
        "sparse_automation_kept": -0.08,
    },
    "dryness_preference": {
        "dry_mix_kept": 0.15,
        "dry_mix_undone": -0.15,
        "wet_mix_kept": -0.12,
        "wet_mix_undone": 0.12,
    },
    "harmonic_boldness": {
        "bold_harmony_kept": 0.15,
        "bold_harmony_undone": -0.15,
        "safe_harmony_kept": -0.10,
    },
    "width_preference": {
        "wide_mix_kept": 0.12,
        "wide_mix_undone": -0.12,
        "narrow_mix_kept": -0.10,
    },
    "native_vs_plugin": {
        "native_device_kept": 0.10,
        "plugin_kept": -0.10,
    },
    "density_tolerance": {
        "dense_arrangement_kept": 0.12,
        "dense_arrangement_undone": -0.12,
        "sparse_arrangement_kept": -0.08,
    },
    "fx_intensity": {
        "heavy_fx_kept": 0.15,
        "heavy_fx_undone": -0.15,
        "light_fx_kept": -0.10,
        "light_fx_undone": 0.10,
    },
}


@dataclass
class TasteDimension:
    """Extended taste tracking beyond quality dimensions."""

    name: str  # e.g. "transition_boldness", "automation_density"
    value: float  # -1 to 1 (negative=prefers less, positive=prefers more)
    evidence_count: int
    last_updated_ms: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": round(self.value, 3),
            "evidence_count": self.evidence_count,
            "last_updated_ms": self.last_updated_ms,
        }


class TasteMemoryStore:
    """In-memory store for taste dimensions inferred from outcomes."""

    def __init__(self) -> None:
        self._dims: dict[str, TasteDimension] = {}
        # Initialize all known dimensions at neutral
        for name in EXTENDED_TASTE_DIMENSIONS:
            self._dims[name] = TasteDimension(
                name=name, value=0.0, evidence_count=0, last_updated_ms=0
            )

    def update_from_outcome(self, outcome: dict) -> None:
        """Infer taste dimensions from a kept/undone outcome dict.

        The outcome dict should contain:
          - kept: bool
          - signals: list[str]  — e.g. ["bold_transition_kept", "wide_mix_kept"]
        """
        signals = outcome.get("signals", [])
        if not signals:
            return

        now_ms = int(time.time() * 1000)

        for signal in signals:
            for dim_name, signal_map in _OUTCOME_SIGNALS.items():
                adj = signal_map.get(signal)
                if adj is not None:
                    dim = self._dims.get(dim_name)
                    if dim is None:
                        dim = TasteDimension(
                            name=dim_name, value=0.0,
                            evidence_count=0, last_updated_ms=0,
                        )
                        self._dims[dim_name] = dim
                    dim.value = max(-1.0, min(1.0, dim.value + adj))
                    dim.evidence_count += 1
                    dim.last_updated_ms = now_ms

    def get_taste_dimensions(self) -> list[TasteDimension]:
        """Return all taste dimensions."""
        return list(self._dims.values())

    def get_dimension(self, name: str) -> Optional[TasteDimension]:
        """Return a specific taste dimension, or None."""
        return self._dims.get(name)

    def should_prefer(self, dimension: str, direction: str) -> bool:
        """True if evidence suggests the user prefers this direction.

        direction: "more" or "less"
        Returns True only if evidence_count >= 2 and value agrees.
        """
        dim = self._dims.get(dimension)
        if dim is None or dim.evidence_count < 2:
            return False
        if direction == "more":
            return dim.value > 0.1
        elif direction == "less":
            return dim.value < -0.1
        return False

    def to_dict(self) -> dict:
        """Serialize the full store."""
        return {
            "dimensions": [d.to_dict() for d in self._dims.values()],
            "count": len(self._dims),
        }

"""AntiMemory — tracks user dislikes and anti-preferences.

Pure Python, zero I/O.  Records dimensions the user repeatedly rejects
so that planners and critics can caution against repeating them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AntiPreference:
    """A single anti-preference: something the user dislikes."""

    dimension: str  # e.g. "brightness", "width", "density"
    direction: str  # "increase" or "decrease"
    strength: float = 0.0  # 0-1, how strongly disliked
    evidence_count: int = 0  # how many times undone/rejected
    last_seen_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "direction": self.direction,
            "strength": self.strength,
            "evidence_count": self.evidence_count,
            "last_seen_ms": self.last_seen_ms,
        }


class AntiMemoryStore:
    """In-memory store for anti-preferences."""

    def __init__(self) -> None:
        self._prefs: dict[tuple[str, str], AntiPreference] = {}

    def record_dislike(self, dimension: str, direction: str) -> AntiPreference:
        """Record or increment an anti-preference.

        Strength grows with evidence but caps at 1.0.
        """
        key = (dimension, direction)
        pref = self._prefs.get(key)
        if pref is None:
            pref = AntiPreference(dimension=dimension, direction=direction)
            self._prefs[key] = pref

        pref.evidence_count += 1
        # Strength: asymptotic growth toward 1.0
        pref.strength = min(1.0, pref.evidence_count * 0.2)
        pref.last_seen_ms = int(time.time() * 1000)
        return pref

    def get_anti_preferences(self) -> list[AntiPreference]:
        """Return all active anti-preferences."""
        return list(self._prefs.values())

    def get_anti_preference(
        self, dimension: str, direction: str
    ) -> AntiPreference | None:
        """Return a specific anti-preference, or None."""
        return self._prefs.get((dimension, direction))

    def should_caution(self, dimension: str, direction: str) -> bool:
        """True if evidence_count >= 2 for the given dimension+direction."""
        pref = self._prefs.get((dimension, direction))
        if pref is None:
            return False
        return pref.evidence_count >= 2

    def to_dict(self) -> dict:
        """Serialize the full store."""
        return {
            "anti_preferences": [p.to_dict() for p in self._prefs.values()],
            "count": len(self._prefs),
        }

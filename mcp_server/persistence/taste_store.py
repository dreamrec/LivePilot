"""Persistent taste state — survives server restart.

Stores move outcomes, novelty preference, device affinity,
anti-preferences, and dimension weights. Located at
~/.livepilot/taste.json.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore


_DEFAULT_PATH = Path.home() / ".livepilot" / "taste.json"


class PersistentTasteStore:
    """Persistent backing for TasteGraph data."""

    def __init__(self, path: Optional[Path] = None):
        self._store = PersistentJsonStore(path or _DEFAULT_PATH)

    def get_all(self) -> dict:
        """Get all persisted taste data."""
        data = self._store.read()
        return data if data.get("version") == 1 else self._default()

    def record_move_outcome(
        self, move_id: str, family: str, kept: bool, score: float = 0.0,
    ) -> None:
        """Persist a move outcome."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            outcomes = data.setdefault("move_outcomes", {})
            entry = outcomes.setdefault(move_id, {
                "family": family, "kept_count": 0, "undone_count": 0,
            })
            entry["family"] = family
            if kept:
                entry["kept_count"] = entry.get("kept_count", 0) + 1
            else:
                entry["undone_count"] = entry.get("undone_count", 0) + 1
            data["evidence_count"] = data.get("evidence_count", 0) + 1
            data["last_updated_ms"] = int(time.time() * 1000)
            return data
        self._store.update(_update)

    def update_novelty(self, chose_bold: bool) -> None:
        """Update novelty band from experiment choice."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            band = data.get("novelty_band", 0.5)
            if chose_bold:
                data["novelty_band"] = min(1.0, band + 0.05)
            else:
                data["novelty_band"] = max(0.0, band - 0.05)
            data["evidence_count"] = data.get("evidence_count", 0) + 1
            return data
        self._store.update(_update)

    def record_device_use(self, device_name: str, positive: bool = True) -> None:
        """Persist device affinity."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            affinities = data.setdefault("device_affinities", {})
            entry = affinities.setdefault(device_name, {
                "affinity": 0.0, "use_count": 0,
            })
            entry["use_count"] = entry.get("use_count", 0) + 1
            aff = entry.get("affinity", 0.0)
            if positive:
                entry["affinity"] = min(1.0, aff + 0.05)
            else:
                entry["affinity"] = max(-1.0, aff - 0.08)
            data["evidence_count"] = data.get("evidence_count", 0) + 1
            return data
        self._store.update(_update)

    def record_anti_preference(self, dimension: str, direction: str) -> None:
        """Persist an anti-preference."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            antis = data.setdefault("anti_preferences", [])
            existing = next(
                (a for a in antis if a["dimension"] == dimension and a["direction"] == direction),
                None,
            )
            if existing:
                existing["count"] = existing.get("count", 0) + 1
                existing["strength"] = min(1.0, existing["count"] * 0.2)
            else:
                antis.append({
                    "dimension": dimension, "direction": direction,
                    "count": 1, "strength": 0.2,
                })
            data["evidence_count"] = data.get("evidence_count", 0) + 1
            return data
        self._store.update(_update)

    def record_dimension_weight(self, dimension: str, value: float) -> None:
        """Persist a dimension weight update."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            data.setdefault("dimension_weights", {})[dimension] = round(value, 3)
            return data
        self._store.update(_update)

    @staticmethod
    def _default() -> dict:
        return {
            "version": 1,
            "move_outcomes": {},
            "novelty_band": 0.5,
            "device_affinities": {},
            "anti_preferences": [],
            "dimension_weights": {},
            "evidence_count": 0,
            "last_updated_ms": 0,
        }

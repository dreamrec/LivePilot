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

    def update_novelty(self, chose_bold: bool, goal_mode: str = "improve") -> None:
        """Update novelty band from experiment choice for a given goal mode.

        PR8: goal_mode defaults to "improve" so legacy callers land on the
        same band they updated before. The per-mode dict ``novelty_bands``
        is maintained alongside the flat ``novelty_band`` field; the flat
        field mirrors the "improve" band.
        """
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            # Ensure the per-mode dict exists (migrating from legacy shape).
            bands = data.get("novelty_bands")
            if not isinstance(bands, dict) or not bands:
                flat = data.get("novelty_band", 0.5)
                bands = {"improve": flat, "explore": flat}
            current = bands.get(goal_mode, 0.5)
            if chose_bold:
                bands[goal_mode] = min(1.0, current + 0.05)
            else:
                bands[goal_mode] = max(0.0, current - 0.05)
            data["novelty_bands"] = bands
            # Mirror the improve band onto the flat field for back-compat.
            data["novelty_band"] = bands.get("improve", 0.5)
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
            # PR8 — per-goal-mode novelty bands; novelty_band mirrors "improve"
            "novelty_bands": {"improve": 0.5, "explore": 0.5},
            "device_affinities": {},
            "anti_preferences": [],
            "dimension_weights": {},
            "evidence_count": 0,
            "last_updated_ms": 0,
        }

"""Persistent taste state — survives server restart.

Stores move outcomes, novelty preference, device affinity,
anti-preferences, and dimension weights. Located at
~/.livepilot/taste.json.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from .base_store import PersistentJsonStore

logger = logging.getLogger(__name__)


_DEFAULT_PATH = Path.home() / ".livepilot" / "taste.json"

# Schema version of the on-disk shape this build writes/expects.
CURRENT_VERSION = 1

# Migration table: source version -> callable that upgrades data from that
# version to the next. Empty today — CURRENT_VERSION has been 1 since this
# store existed, so there has never been a real migration to run. This is
# scaffolding: when a future schema bump lands, add `{OLD: _migrate_fn}` here
# and bump CURRENT_VERSION. Without this table, ANY version mismatch (a
# future bump, a downgrade, a hand-edited file) silently discarded the
# user's entire taste/anti-preference history back to defaults with no
# warning and no backup — that's the bug this scaffolding closes.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


class PersistentTasteStore:
    """Persistent backing for TasteGraph data."""

    def __init__(self, path: Optional[Path] = None):
        self._store = PersistentJsonStore(path or _DEFAULT_PATH)

    def _coerce(self, data: dict) -> dict:
        """Return schema-current data — migrating forward or resetting.

        - version == CURRENT_VERSION: pass through unchanged (hot path).
        - version has a registered migration chain to CURRENT_VERSION: run it.
        - anything else (missing/non-int version, or a version this build
          doesn't know how to migrate — e.g. it's newer than this build):
          back up the raw file to ``<path>.pre-migration``, log a WARNING,
          and fall back to defaults. Never silently discard.
        """
        version = data.get("version")
        if version == CURRENT_VERSION:
            return data
        migrated = self._migrate(data, version)
        if migrated is not None:
            return migrated
        if data:
            self._backup_unmigrated(version)
        return self._default()

    @staticmethod
    def _migrate(data: dict, version) -> Optional[dict]:
        """Run the migration chain from ``version`` to CURRENT_VERSION.

        Returns None if there's no registered path (unknown/future version),
        signalling the caller to fall back to defaults.
        """
        if not isinstance(version, int):
            return None
        migrated = dict(data)
        seen: set[int] = set()
        while migrated.get("version") != CURRENT_VERSION:
            v = migrated.get("version")
            if not isinstance(v, int) or v in seen or v not in _MIGRATIONS:
                return None
            seen.add(v)
            migrated = _MIGRATIONS[v](migrated)
        return migrated

    def _backup_unmigrated(self, version) -> None:
        """Preserve the raw on-disk file before falling back to defaults."""
        path = self._store.path
        backup = path.with_suffix(path.suffix + ".pre-migration")
        try:
            if path.exists():
                path.replace(backup)
                logger.warning(
                    "PersistentTasteStore: unrecognized schema version %r in "
                    "%s (expected %r) — backed up to %s and falling back to "
                    "defaults; the original data was NOT discarded",
                    version, path, CURRENT_VERSION, backup,
                )
            else:
                logger.warning(
                    "PersistentTasteStore: unrecognized schema version %r "
                    "(expected %r, no on-disk file to back up) — falling "
                    "back to defaults",
                    version, CURRENT_VERSION,
                )
        except OSError as exc:
            logger.warning(
                "PersistentTasteStore: failed to back up unrecognized-"
                "version file %s (%s) — falling back to defaults without "
                "a backup",
                path, exc,
            )

    def get_all(self) -> dict:
        """Get all persisted taste data."""
        data = self._store.read()
        return self._coerce(data)

    def record_move_outcome(
        self, move_id: str, family: str, kept: bool, score: float = 0.0,
    ) -> None:
        """Persist a move outcome."""
        def _update(data: dict) -> dict:
            data = self._coerce(data)
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
            data = self._coerce(data)
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
            data = self._coerce(data)
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
            data = self._coerce(data)
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
            data = self._coerce(data)
            data.setdefault("dimension_weights", {})[dimension] = round(value, 3)
            data["evidence_count"] = data.get("evidence_count", 0) + 1
            data["last_updated_ms"] = int(time.time() * 1000)
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

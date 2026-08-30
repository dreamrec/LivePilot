"""Per-project persistent state — threads, turns, Wonder outcomes.

Stores session continuity data scoped to a project identity.
Located at ~/.livepilot/projects/<hash>/state.json.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from .base_store import PersistentJsonStore

logger = logging.getLogger(__name__)


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
_MAX_TURNS = 50
_MAX_WONDER_OUTCOMES = 10
# Creative threads accumulate one entry per open_thread() call, and
# session_continuity mints a fresh thread_id (ms-timestamp-seeded hash) every
# time — unlike turns/wonder_outcomes there was previously NO cap here, so
# the list grew monotonically forever and every save_thread() became a
# full read-modify-write over an ever-larger threads array.
_MAX_THREADS = 100

# Schema version of the on-disk shape this build writes/expects.
CURRENT_VERSION = 1

# Migration table: source version -> callable that upgrades data from that
# version to the next. Empty today — CURRENT_VERSION has been 1 since this
# store existed. Scaffolding for the day a schema bump actually needs a real
# migration; until then any version mismatch backs up the raw file and warns
# instead of silently discarding the project's threads/turns/wonder history.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def project_hash(session_info: dict) -> str:
    """Compute a project fingerprint from session info.

    Identity preference order:
      1. Saved Live Set path — stable across edits and restarts.
      2. Remote-Script session instance — stable for an unsaved set across
         MCP restarts, distinct when the user opens/creates another set.
      3. Legacy structural fingerprint — compatibility with older scripts.

    v1.10.3 Truth Release: this used to use `tempo + len(tracks) + sorted
    track names`, which had obvious collisions — any two songs at the same
    tempo with the same track names collided even if the tracks were in
    different order, the scenes were different, or the arrangement length
    differed. The author's own comment acknowledged the weakness.

    The legacy fallback uses a lot more entropy from the session:
      * tempo (1 decimal)
      * time signature (num/denom)
      * song_length (arrangement length in beats) — very distinguishing
      * ORDERED track list: (index, name, color_index, has_midi_input)
      * ORDERED scene list: (index, name, color_index)
      * return track count + names

    It is used only when neither modern identity field is available.
      * template-based starts diverge once the user renames a track, adds
        a scene, or adjusts the arrangement length
      * track reordering produces a new hash (correctly — it's a real edit)
      * two songs at 128 BPM with tracks named Drums/Bass no longer collide
        unless they also share identical scene lists AND song length
    """
    file_path = str(session_info.get("file_path") or "").strip()
    if file_path:
        try:
            normalized_path = str(Path(file_path).expanduser().resolve(strict=False))
        except (OSError, RuntimeError, ValueError):
            normalized_path = file_path
        return hashlib.sha256(
            f"live-set-path:{normalized_path.casefold()}".encode()
        ).hexdigest()[:12]

    session_instance_id = str(session_info.get("session_instance_id") or "").strip()
    if session_instance_id:
        return hashlib.sha256(
            f"live-set-instance:{session_instance_id}".encode()
        ).hexdigest()[:12]

    tempo = session_info.get("tempo", 120.0)
    sig_num = session_info.get("signature_numerator", 4)
    sig_denom = session_info.get("signature_denominator", 4)
    song_length = session_info.get("song_length", 0.0)

    tracks = session_info.get("tracks", []) or []
    # Ordered track signature — (index, name, color, has_midi_input)
    track_sig = "|".join(
        f"{t.get('index', i)}:{t.get('name', '')}:{t.get('color_index', 0)}:{int(t.get('has_midi_input', False))}"
        for i, t in enumerate(tracks)
        if isinstance(t, dict)
    )

    return_tracks = session_info.get("return_tracks", []) or []
    return_sig = "|".join(
        f"{r.get('index', i)}:{r.get('name', '')}"
        for i, r in enumerate(return_tracks)
        if isinstance(r, dict)
    )

    scenes = session_info.get("scenes", []) or []
    scene_sig = "|".join(
        f"{s.get('index', i)}:{s.get('name', '')}:{s.get('color_index', 0)}"
        for i, s in enumerate(scenes)
        if isinstance(s, dict)
    )

    seed = "||".join([
        f"t={tempo:.1f}",
        f"sig={sig_num}/{sig_denom}",
        f"len={song_length:.2f}",
        f"n_tracks={len(tracks)}",
        f"tracks=[{track_sig}]",
        f"n_returns={len(return_tracks)}",
        f"returns=[{return_sig}]",
        f"n_scenes={len(scenes)}",
        f"scenes=[{scene_sig}]",
    ])
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


def _prune_threads(threads: list[dict], max_threads: int) -> list[dict]:
    """Cap the thread list, preferring to drop resolved threads first.

    Mirrors the capping pattern already used by save_turn (_MAX_TURNS) and
    save_wonder_outcome (_MAX_WONDER_OUTCOMES) — but threads never had one,
    and open_thread() mints a fresh thread_id every call, so the list grew
    monotonically forever.

    Eviction order:
      1. Resolved threads, oldest-touched first — a long resolved history
         shouldn't crowd out genuinely open creative threads.
      2. If resolved threads alone aren't enough to reach the cap, fall back
         to dropping the oldest-touched threads overall (any status), so the
         most-recently-touched threads always survive.
    """
    if len(threads) <= max_threads:
        return threads

    overflow = len(threads) - max_threads

    resolved_idx = sorted(
        (i for i, t in enumerate(threads) if t.get("status") == "resolved"),
        key=lambda i: threads[i].get("last_touched_ms", 0),
    )
    drop: set[int] = set(resolved_idx[:overflow])

    if len(drop) < overflow:
        remaining_idx = [i for i in range(len(threads)) if i not in drop]
        remaining_idx.sort(key=lambda i: threads[i].get("last_touched_ms", 0))
        need_more = overflow - len(drop)
        drop.update(remaining_idx[:need_more])

    return [t for i, t in enumerate(threads) if i not in drop]


class ProjectStore:
    """Persistent per-project state."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _PROJECTS_DIR
        self._store = PersistentJsonStore(base / project_id / "state.json")
        self._project_id = project_id

    @property
    def project_id(self) -> str:
        return self._project_id

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
                    "ProjectStore(%s): unrecognized schema version %r in %s "
                    "(expected %r) — backed up to %s and falling back to "
                    "defaults; the original data was NOT discarded",
                    self._project_id, version, path, CURRENT_VERSION, backup,
                )
            else:
                logger.warning(
                    "ProjectStore(%s): unrecognized schema version %r "
                    "(expected %r, no on-disk file to back up) — falling "
                    "back to defaults",
                    self._project_id, version, CURRENT_VERSION,
                )
        except OSError as exc:
            logger.warning(
                "ProjectStore(%s): failed to back up unrecognized-version "
                "file %s (%s) — falling back to defaults without a backup",
                self._project_id, path, exc,
            )

    def get_all(self) -> dict:
        data = self._store.read()
        return self._coerce(data)

    def save_thread(self, thread: dict) -> None:
        """Save or update a creative thread (capped at _MAX_THREADS)."""
        def _update(data: dict) -> dict:
            data = self._coerce(data)
            threads = data.setdefault("threads", [])
            # Update existing or append
            for i, t in enumerate(threads):
                if t.get("thread_id") == thread.get("thread_id"):
                    threads[i] = thread
                    break
            else:
                threads.append(thread)
            if len(threads) > _MAX_THREADS:
                threads = _prune_threads(threads, _MAX_THREADS)
            data["threads"] = threads
            return data
        self._store.update(_update)

    def save_turn(self, turn: dict) -> None:
        """Save a turn resolution (capped at MAX_TURNS)."""
        def _update(data: dict) -> dict:
            data = self._coerce(data)
            turns = data.setdefault("turns", [])
            turns.append(turn)
            # Cap at max
            if len(turns) > _MAX_TURNS:
                data["turns"] = turns[-_MAX_TURNS:]
            data["last_updated_ms"] = int(time.time() * 1000)
            return data
        self._store.update(_update)

    def save_wonder_outcome(self, outcome: dict) -> None:
        """Save a Wonder session outcome (capped at MAX_WONDER_OUTCOMES)."""
        def _update(data: dict) -> dict:
            data = self._coerce(data)
            outcomes = data.setdefault("wonder_outcomes", [])
            outcomes.append(outcome)
            if len(outcomes) > _MAX_WONDER_OUTCOMES:
                data["wonder_outcomes"] = outcomes[-_MAX_WONDER_OUTCOMES:]
            return data
        self._store.update(_update)

    def get_threads(self) -> list[dict]:
        return self.get_all().get("threads", [])

    def get_turns(self) -> list[dict]:
        return self.get_all().get("turns", [])

    def get_wonder_outcomes(self) -> list[dict]:
        return self.get_all().get("wonder_outcomes", [])

    @staticmethod
    def _default() -> dict:
        return {
            "version": 1,
            "threads": [],
            "turns": [],
            "wonder_outcomes": [],
            "last_updated_ms": 0,
        }

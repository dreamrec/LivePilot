"""Per-project persistent state — threads, turns, Wonder outcomes.

Stores session continuity data scoped to a project identity.
Located at ~/.livepilot/projects/<hash>/state.json.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
_MAX_TURNS = 50
_MAX_WONDER_OUTCOMES = 10


def project_hash(session_info: dict) -> str:
    """Compute a stable project fingerprint from session info.

    Uses tempo + track count + sorted track names. This is imperfect
    but stable enough for per-song state within a production session.
    """
    tempo = session_info.get("tempo", 120.0)
    tracks = session_info.get("tracks", [])
    track_names = sorted(t.get("name", "") for t in tracks if isinstance(t, dict))
    seed = f"{tempo:.1f}|{len(tracks)}|{'|'.join(track_names)}"
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


class ProjectStore:
    """Persistent per-project state."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _PROJECTS_DIR
        self._store = PersistentJsonStore(base / project_id / "state.json")
        self._project_id = project_id

    @property
    def project_id(self) -> str:
        return self._project_id

    def get_all(self) -> dict:
        data = self._store.read()
        return data if data.get("version") == 1 else self._default()

    def save_thread(self, thread: dict) -> None:
        """Save or update a creative thread."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
            threads = data.setdefault("threads", [])
            # Update existing or append
            for i, t in enumerate(threads):
                if t.get("thread_id") == thread.get("thread_id"):
                    threads[i] = thread
                    return data
            threads.append(thread)
            return data
        self._store.update(_update)

    def save_turn(self, turn: dict) -> None:
        """Save a turn resolution (capped at MAX_TURNS)."""
        def _update(data: dict) -> dict:
            data = data if data.get("version") == 1 else self._default()
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
            data = data if data.get("version") == 1 else self._default()
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

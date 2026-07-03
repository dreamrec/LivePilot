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
from .paths import livepilot_projects_dir


_PROJECTS_DIR: Optional[Path] = None
_MAX_TURNS = 50
_MAX_WONDER_OUTCOMES = 10


def project_hash(session_info: dict) -> str:
    """Compute a project fingerprint from session info.

    v1.10.3 Truth Release: this used to use `tempo + len(tracks) + sorted
    track names`, which had obvious collisions — any two songs at the same
    tempo with the same track names collided even if the tracks were in
    different order, the scenes were different, or the arrangement length
    differed. The author's own comment acknowledged the weakness.

    The new hash uses a lot more entropy from the session:
      * tempo (1 decimal)
      * time signature (num/denom)
      * song_length (arrangement length in beats) — very distinguishing
      * ORDERED track list: (index, name, color_index, has_midi_input)
      * ORDERED scene list: (index, name, color_index)
      * return track count + names

    Prefer the Live set file path/name when the Remote Script exposes it.
    The structural fallback is still only a fingerprint, but it is
    collision-resistant across the common failure modes:
      * template-based starts diverge once the user renames a track, adds
        a scene, or adjusts the arrangement length
      * track reordering produces a new hash (correctly — it's a real edit)
      * two songs at 128 BPM with tracks named Drums/Bass no longer collide
        unless they also share identical scene lists AND song length
    """
    project_identity = _stable_saved_project_identity(session_info)
    if project_identity:
        return hashlib.sha256(f"project-v2||{project_identity}".encode()).hexdigest()[:12]

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


def _stable_saved_project_identity(session_info: dict) -> str:
    identity = session_info.get("project_identity")
    if not isinstance(identity, dict):
        identity = {}
    for key in (
        "file_path",
        "path",
        "project_path",
        "set_path",
        "live_set_path",
    ):
        value = str(identity.get(key) or session_info.get(key) or "").strip()
        if value:
            return f"saved_path={value}"
    for key in ("name", "project_name", "set_name", "live_set_name"):
        value = str(identity.get(key) or session_info.get(key) or "").strip()
        if value and value.lower() != "untitled":
            return f"saved_name={value}"
    return ""


class ProjectStore:
    """Persistent per-project state."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _projects_dir()
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


def _projects_dir() -> Path:
    return Path(_PROJECTS_DIR) if _PROJECTS_DIR is not None else livepilot_projects_dir()

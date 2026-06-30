"""Last-known Ableton session snapshot for browser-only cockpit workflows."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .track_annotations import annotation_project_hash


_LIVEPILOT_DIR = Path.home() / ".livepilot"
_STORE_VERSION = 1


class SessionSnapshotStore:
    """Atomic JSON store for the most recent get_session_info result."""

    def __init__(self, path: Optional[Path] = None):
        self._store = PersistentJsonStore(path or _LIVEPILOT_DIR / "current_session.json")

    @property
    def path(self) -> Path:
        return self._store.path

    def save(self, session_info: dict, source: str = "mcp") -> dict:
        if not _looks_like_session_info(session_info):
            raise ValueError("session_info does not look like a LivePilot session snapshot")
        project_id = annotation_project_hash(session_info)
        now = int(time.time() * 1000)
        record = {
            "version": _STORE_VERSION,
            "project_id": project_id,
            "updated_at_ms": now,
            "source": str(source or "mcp"),
            "session_info": dict(session_info),
        }
        self._store.write(record)
        return record

    def load(self) -> Optional[dict]:
        record = self._store.read()
        if record.get("version") != _STORE_VERSION:
            return None
        session_info = record.get("session_info")
        if not _looks_like_session_info(session_info):
            return None
        return dict(record)


def save_session_snapshot(session_info: dict, source: str = "mcp") -> Optional[dict]:
    """Best-effort save helper; never lets snapshot I/O break LivePilot tools."""
    try:
        return SessionSnapshotStore().save(session_info, source=source)
    except Exception:
        return None


def load_session_snapshot() -> Optional[dict]:
    return SessionSnapshotStore().load()


def _looks_like_session_info(value) -> bool:
    if not isinstance(value, dict):
        return False
    return isinstance(value.get("tracks"), list) and "tempo" in value

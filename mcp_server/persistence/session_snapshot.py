"""Last-known Ableton session snapshot for browser-only cockpit workflows."""

from __future__ import annotations

from collections import Counter
import time
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .track_annotations import annotation_project_id_for_session


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
        previous = self.load()
        incoming = _preserve_rich_arrangement_metadata(
            dict(session_info),
            (previous or {}).get("session_info") or {},
        )
        project_id = annotation_project_id_for_session(incoming)
        now = int(time.time() * 1000)
        record = {
            "version": _STORE_VERSION,
            "project_id": project_id,
            "updated_at_ms": now,
            "source": str(source or "mcp"),
            "session_info": incoming,
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


def _preserve_rich_arrangement_metadata(
    current: dict,
    previous: dict,
) -> dict:
    if not _same_snapshot_project(current, previous):
        return current
    enriched = dict(current)
    if not enriched.get("cue_points") and previous.get("cue_points"):
        enriched["cue_points"] = list(previous.get("cue_points") or [])
    enriched["tracks"] = _merge_section_track_clips(
        enriched.get("tracks") or [],
        previous.get("tracks") or [],
    )
    return enriched


def _same_snapshot_project(current: dict, previous: dict) -> bool:
    if not _looks_like_session_info(current) or not _looks_like_session_info(previous):
        return False
    current_identity = _saved_project_identity(current)
    previous_identity = _saved_project_identity(previous)
    if current_identity or previous_identity:
        return current_identity == previous_identity
    current_names = _track_name_signature(current)
    previous_names = _track_name_signature(previous)
    return _track_name_overlap(current_names, previous_names) >= 0.8


def _saved_project_identity(session_info: dict) -> str:
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


def _track_name_signature(session_info: dict) -> tuple[str, ...]:
    return tuple(
        str(track.get("name") or "")
        for track in (session_info.get("tracks") or [])
        if isinstance(track, dict)
    )


def _track_name_overlap(current_names: tuple[str, ...], previous_names: tuple[str, ...]) -> float:
    if not current_names or not previous_names:
        return 0.0
    current_counts = Counter(name for name in current_names if name)
    previous_counts = Counter(name for name in previous_names if name)
    if not current_counts or not previous_counts:
        return 0.0
    shared = sum((current_counts & previous_counts).values())
    return shared / max(sum(current_counts.values()), sum(previous_counts.values()))


def _merge_section_track_clips(
    current_tracks: list,
    previous_tracks: list,
) -> list:
    previous_by_key = {
        _track_key(track): track
        for track in previous_tracks
        if isinstance(track, dict)
    }
    merged: list = []
    for track in current_tracks:
        if not isinstance(track, dict):
            merged.append(track)
            continue
        if not _is_section_map_track(track):
            merged.append(track)
            continue
        previous = previous_by_key.get(_track_key(track)) or {}
        if not isinstance(previous, dict):
            merged.append(track)
            continue
        entry = dict(track)
        if not entry.get("arrangement_clips") and previous.get("arrangement_clips"):
            entry["arrangement_clips"] = list(previous.get("arrangement_clips") or [])
        if not entry.get("clips") and previous.get("clips"):
            entry["clips"] = list(previous.get("clips") or [])
        merged.append(entry)
    return merged


def _track_key(track: dict) -> tuple:
    return (track.get("index"), str(track.get("name") or ""))


def _is_section_map_track(track: dict) -> bool:
    name = str(track.get("name") or "").lower()
    return "section map" in name or "arrangement map" in name

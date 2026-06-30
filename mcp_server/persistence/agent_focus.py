"""Project-scoped agent focus state for human pointing workflows.

The focus panel lets a user point at tracks in a local browser UI while agents
read that pointing state through MCP tools. The store is intentionally tiny and
uses the same order-stable project hash as track annotations so focus survives
ordinary track reordering.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .track_annotations import annotation_project_hash


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
_STORE_VERSION = 1
_HISTORY_LIMIT = 25


class AgentFocusService:
    """Read/write the current user-pointed track focus."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _PROJECTS_DIR

    def get_focus(self, session_info: dict) -> dict:
        store = self._store_for_session(session_info)
        raw_focus = store.get_focus()
        resolved = _resolve_focus(session_info, raw_focus)
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "focus": resolved,
        }

    def set_focus(
        self,
        session_info: dict,
        track_indices: list[int],
        label: Optional[str] = None,
        source: str = "mcp",
    ) -> dict:
        normalized = _normalize_track_indices(track_indices)
        tracks = _regular_tracks(session_info)
        by_index = {int(track["index"]): track for track in tracks}
        missing = [idx for idx in normalized if idx not in by_index]
        if missing:
            raise ValueError(f"Track index not found in current session: {missing}")

        focus = {
            "focus_id": f"focus_{uuid.uuid4().hex[:12]}",
            "track_indices": normalized,
            "label": (label or "").strip(),
            "source": (source or "mcp").strip() or "mcp",
            "updated_at_ms": int(time.time() * 1000),
            "track_refs": [
                _make_focus_track_ref(by_index[idx])
                for idx in normalized
            ],
        }
        store = self._store_for_session(session_info)
        store.set_focus(focus)
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "focus": _resolve_focus(session_info, focus),
        }

    def clear_focus(self, session_info: dict) -> dict:
        store = self._store_for_session(session_info)
        previous = store.get_focus()
        store.clear_focus()
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "previous_focus": _resolve_focus(session_info, previous),
            "focus": _empty_focus(),
        }

    def history(self, session_info: dict) -> list[dict]:
        store = self._store_for_session(session_info)
        return [
            _resolve_focus(session_info, item)
            for item in store.get_history()
            if item
        ]

    def _store_for_session(self, session_info: dict) -> "AgentFocusStore":
        return AgentFocusStore(annotation_project_hash(session_info), self._base_dir)


class AgentFocusStore:
    """Atomic JSON store for one project's agent focus state."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _PROJECTS_DIR
        self._store = PersistentJsonStore(base / project_id / "agent_focus.json")
        self._project_id = project_id

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def path(self) -> Path:
        return self._store.path

    def get_all(self) -> dict:
        data = self._store.read()
        return data if data.get("version") == _STORE_VERSION else self._default()

    def get_focus(self) -> Optional[dict]:
        focus = self.get_all().get("focus")
        return dict(focus) if isinstance(focus, dict) else None

    def get_history(self) -> list[dict]:
        history = self.get_all().get("history")
        return list(history) if isinstance(history, list) else []

    def set_focus(self, focus: dict) -> dict:
        focus = dict(focus)
        now = int(time.time() * 1000)
        focus.setdefault("updated_at_ms", now)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            previous = data.get("focus")
            history = data.setdefault("history", [])
            if isinstance(previous, dict):
                history.insert(0, previous)
                del history[_HISTORY_LIMIT:]
            data["focus"] = focus
            data["last_updated_ms"] = focus["updated_at_ms"]
            return data

        return self._store.update(_update)

    def clear_focus(self) -> dict:
        now = int(time.time() * 1000)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            previous = data.get("focus")
            history = data.setdefault("history", [])
            if isinstance(previous, dict):
                history.insert(0, previous)
                del history[_HISTORY_LIMIT:]
            data["focus"] = None
            data["last_updated_ms"] = now
            return data

        return self._store.update(_update)

    @staticmethod
    def _default() -> dict:
        return {
            "version": _STORE_VERSION,
            "focus": None,
            "history": [],
            "last_updated_ms": 0,
        }


def resolve_focus(session_info: dict, raw_focus: Optional[dict]) -> dict:
    """Public helper used by tests and the focus panel."""
    return _resolve_focus(session_info, raw_focus)


def _resolve_focus(session_info: dict, raw_focus: Optional[dict]) -> dict:
    if not isinstance(raw_focus, dict):
        return _empty_focus()

    tracks = _regular_tracks(session_info)
    resolved_tracks = []
    unresolved_refs = []
    for ref in raw_focus.get("track_refs") or []:
        match = _resolve_track_ref(tracks, ref)
        if match.get("status") == "resolved":
            resolved_tracks.append({
                "index": match["track_index"],
                "name": match["track_name"],
                "confidence": match["confidence"],
                "reason": match["reason"],
                "color_index": match.get("color_index"),
                "has_midi_input": match.get("has_midi_input"),
                "has_audio_input": match.get("has_audio_input"),
            })
        else:
            unresolved_refs.append({
                "stored_index": ref.get("index"),
                "stored_name": ref.get("name"),
                "reason": match.get("reason"),
                "candidates": match.get("candidates", []),
            })

    seen = set()
    deduped_tracks = []
    for track in resolved_tracks:
        idx = track["index"]
        if idx in seen:
            continue
        seen.add(idx)
        deduped_tracks.append(track)

    if not deduped_tracks:
        resolution_status = "empty" if not raw_focus.get("track_refs") else "unresolved"
    elif unresolved_refs:
        resolution_status = "partial"
    else:
        resolution_status = "resolved"

    return {
        "focus_id": raw_focus.get("focus_id"),
        "label": raw_focus.get("label", ""),
        "source": raw_focus.get("source", ""),
        "updated_at_ms": raw_focus.get("updated_at_ms"),
        "original_track_indices": list(raw_focus.get("track_indices") or []),
        "track_indices": [track["index"] for track in deduped_tracks],
        "tracks": deduped_tracks,
        "resolution_status": resolution_status,
        "unresolved_refs": unresolved_refs,
        "is_empty": len(deduped_tracks) == 0,
    }


def _empty_focus() -> dict:
    return {
        "focus_id": None,
        "label": "",
        "source": "",
        "updated_at_ms": None,
        "original_track_indices": [],
        "track_indices": [],
        "tracks": [],
        "resolution_status": "empty",
        "unresolved_refs": [],
        "is_empty": True,
    }


def _regular_tracks(session_info: dict) -> list[dict]:
    return [
        track for track in (session_info.get("tracks") or [])
        if isinstance(track, dict) and isinstance(track.get("index"), int)
    ]


def _normalize_track_indices(track_indices: list[int]) -> list[int]:
    if not isinstance(track_indices, list):
        raise ValueError("track_indices must be a list of regular track indices")
    normalized = []
    for value in track_indices:
        try:
            idx = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid track index: {value!r}") from exc
        if idx < 0:
            raise ValueError("Agent focus currently supports regular tracks only")
        if idx not in normalized:
            normalized.append(idx)
    if not normalized:
        raise ValueError("track_indices must include at least one track")
    return normalized


def _make_focus_track_ref(track: dict) -> dict:
    return {
        "index": int(track.get("index")),
        "name": str(track.get("name") or ""),
        "color_index": track.get("color_index"),
        "has_midi_input": track.get("has_midi_input"),
        "has_audio_input": track.get("has_audio_input"),
    }


def _resolve_track_ref(tracks: list[dict], ref: dict) -> dict:
    scored = [_score_track_ref(track, ref) for track in tracks]
    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        return {"status": "unresolved", "reason": "no_tracks", "candidates": []}

    best = scored[0]
    second = scored[1]["score"] if len(scored) > 1 else 0.0
    margin = best["score"] - second
    resolved = best["score"] >= 0.65 and (margin >= 0.1 or best["score"] >= 0.9)
    if not resolved:
        return {
            "status": "unresolved",
            "reason": "low_confidence_or_ambiguous",
            "candidates": [_compact_candidate(item) for item in scored[:5]],
        }
    return {
        "status": "resolved",
        "track_index": best["track_index"],
        "track_name": best["track_name"],
        "color_index": best.get("color_index"),
        "has_midi_input": best.get("has_midi_input"),
        "has_audio_input": best.get("has_audio_input"),
        "confidence": round(best["score"], 3),
        "reason": best["reason"],
        "candidates": [_compact_candidate(item) for item in scored[:5]],
    }


def _score_track_ref(track: dict, ref: dict) -> dict:
    score = 0.0
    reasons = []
    stored_index = ref.get("index")
    stored_name = str(ref.get("name") or "")
    current_name = str(track.get("name") or "")

    if stored_index == track.get("index"):
        score += 0.3
        reasons.append("index")
    if stored_name and stored_name == current_name:
        score += 0.45
        reasons.append("name")
    elif stored_name and stored_name.lower() == current_name.lower():
        score += 0.35
        reasons.append("name_case_insensitive")
    if ref.get("color_index") is not None and ref.get("color_index") == track.get("color_index"):
        score += 0.12
        reasons.append("color")
    for key in ("has_midi_input", "has_audio_input"):
        if ref.get(key) is not None and bool(ref.get(key)) == bool(track.get(key)):
            score += 0.08
            reasons.append(key)

    return {
        "track_index": track.get("index"),
        "track_name": current_name,
        "color_index": track.get("color_index"),
        "has_midi_input": track.get("has_midi_input"),
        "has_audio_input": track.get("has_audio_input"),
        "score": min(score, 1.0),
        "reason": "+".join(reasons) if reasons else "no_match",
    }


def _compact_candidate(item: dict) -> dict:
    return {
        "track_index": item.get("track_index"),
        "track_name": item.get("track_name"),
        "score": round(float(item.get("score") or 0.0), 3),
        "reason": item.get("reason"),
    }

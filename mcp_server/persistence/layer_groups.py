"""Project-scoped musical layer groups for cockpit targeting."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .paths import livepilot_projects_dir
from .track_annotations import (
    annotation_project_id_for_session,
    make_track_signature,
)


_PROJECTS_DIR: Optional[Path] = None
_STORE_VERSION = 1
_VALID_STATUSES = {"layered", "singleton", "potential"}


class LayerGroupService:
    """Read/write project-scoped musical layer groups."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _projects_dir()

    def store_for_session(self, session_info: dict) -> "LayerGroupStore":
        return LayerGroupStore(
            annotation_project_id_for_session(session_info, self._base_dir),
            self._base_dir,
        )

    def list_groups(self, session_info: dict) -> dict:
        store = self.store_for_session(session_info)
        groups = [
            _resolve_layer_group(session_info, item)
            for item in store.list_layers()
        ]
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "layer_groups": groups,
        }

    def save_group(
        self,
        session_info: dict,
        *,
        label: str,
        track_indices: list[int],
        layer_id: str = "",
        status: str = "layered",
        linked_layers: Optional[list[str]] = None,
        notes: str = "",
    ) -> dict:
        store = self.store_for_session(session_info)
        tracks = _regular_tracks(session_info)
        by_index = {int(track["index"]): track for track in tracks}
        member_refs = []
        for raw_index in track_indices:
            index = int(raw_index)
            track = by_index.get(index)
            if not track:
                raise ValueError(f"Track index {index} not found in current session")
            member_refs.append({
                "signature": make_track_signature(track),
                "last_seen_index": index,
            })
        layer = store.upsert_layer({
            "layer_id": _normalize_key(layer_id or label),
            "label": str(label or layer_id or "Layer").strip() or "Layer",
            "status": _normalize_status(status),
            "member_refs": member_refs,
            "linked_layers": _normalize_string_list(linked_layers),
            "notes": str(notes or "").strip(),
        })
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "layer": _resolve_layer_group(session_info, layer),
        }

    def delete_group(self, session_info: dict, layer_id: str) -> dict:
        store = self.store_for_session(session_info)
        deleted = store.delete_layer(_normalize_key(layer_id))
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "deleted": deleted,
            "layer_id": _normalize_key(layer_id),
            "layer_groups": [
                _resolve_layer_group(session_info, item)
                for item in store.list_layers()
            ],
        }


class LayerGroupStore:
    """Atomic JSON store for one project's musical layer groups."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _projects_dir()
        self._store = PersistentJsonStore(base / project_id / "layer_groups.json")
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

    def list_layers(self) -> list[dict]:
        return list(self.get_all().get("layers") or [])

    def upsert_layer(self, layer: dict) -> dict:
        now = _now_ms()
        normalized = _normalize_layer(layer, now=now)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            layers = data.setdefault("layers", [])
            for index, existing in enumerate(layers):
                if existing.get("layer_id") == normalized["layer_id"]:
                    merged = dict(existing)
                    merged.update(normalized)
                    merged["created_at_ms"] = existing.get("created_at_ms", now)
                    merged["updated_at_ms"] = now
                    layers[index] = merged
                    data["last_updated_ms"] = now
                    return data
            layers.append(normalized)
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return next(
            item for item in data.get("layers", [])
            if item.get("layer_id") == normalized["layer_id"]
        )

    def delete_layer(self, layer_id: str) -> bool:
        layer_id = _normalize_key(layer_id)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            before = len(data.get("layers") or [])
            data["layers"] = [
                item for item in (data.get("layers") or [])
                if item.get("layer_id") != layer_id
            ]
            if len(data["layers"]) != before:
                data["last_updated_ms"] = _now_ms()
            return data

        before = len(self.list_layers())
        self._store.update(_update)
        return len(self.list_layers()) != before

    @staticmethod
    def _default() -> dict:
        return {
            "version": _STORE_VERSION,
            "layers": [],
            "last_updated_ms": 0,
        }


def _resolve_layer_group(session_info: dict, layer: dict) -> dict:
    tracks = _regular_tracks(session_info)
    resolved_members = []
    unresolved_members = []
    for ref in layer.get("member_refs") or []:
        resolution = _resolve_member_ref(tracks, ref)
        item = {"ref": ref, "resolution": resolution}
        if resolution["status"] == "resolved":
            resolved_members.append(item)
        else:
            unresolved_members.append(item)
    track_indices = [
        item["resolution"]["resolved_track_index"]
        for item in resolved_members
    ]
    track_names = [
        item["resolution"]["resolved_track_name"]
        for item in resolved_members
    ]
    status = str(layer.get("status") or "layered")
    return {
        "key": layer.get("layer_id"),
        "layer_id": layer.get("layer_id"),
        "label": layer.get("label") or _humanize_key(layer.get("layer_id")),
        "status": status,
        "source": "store",
        "count": len(track_indices),
        "track_indices": track_indices,
        "track_names": track_names,
        "member_refs": list(layer.get("member_refs") or []),
        "resolved_members": resolved_members,
        "unresolved_members": unresolved_members,
        "unresolved_count": len(unresolved_members),
        "linked_layers": list(layer.get("linked_layers") or []),
        "notes": layer.get("notes") or "",
        "created_at_ms": layer.get("created_at_ms"),
        "updated_at_ms": layer.get("updated_at_ms"),
        "is_expandable": status in {"singleton", "potential"},
    }


def _resolve_member_ref(tracks: list[dict], ref: dict) -> dict:
    scored = [_score_member_ref(track, ref) for track in tracks]
    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        return {
            "status": "unresolved",
            "resolved_track_index": None,
            "resolved_track_name": None,
            "confidence": 0.0,
            "reason": "no_tracks",
            "candidates": [],
        }
    best = scored[0]
    second = scored[1]["score"] if len(scored) > 1 else 0.0
    margin = best["score"] - second
    resolved = best["score"] >= 0.62 and (
        margin >= 0.08 or best["score"] >= 0.85
    )
    return {
        "status": "resolved" if resolved else "unresolved",
        "resolved_track_index": best["track_index"] if resolved else None,
        "resolved_track_name": best["track_name"] if resolved else None,
        "confidence": round(best["score"], 3),
        "reason": best["reason"] if resolved else "low_confidence_or_ambiguous",
        "candidates": scored[:5],
    }


def _score_member_ref(track: dict, ref: dict) -> dict:
    signature = ref.get("signature") or {}
    score = 0.0
    reasons = []
    stored_name = str(signature.get("name") or ref.get("name") or "")
    current_name = str(track.get("name") or "")
    if stored_name and stored_name == current_name:
        score += 0.45
        reasons.append("name")
    elif stored_name and stored_name.lower() == current_name.lower():
        score += 0.35
        reasons.append("name_case_insensitive")
    elif stored_name and current_name:
        stored_norm = stored_name.lower()
        current_norm = current_name.lower()
        if stored_norm in current_norm or current_norm in stored_norm:
            score += 0.25
            reasons.append("name_substring")
    for key, weight in (
        ("has_midi_input", 0.13),
        ("has_audio_input", 0.13),
        ("is_foldable", 0.05),
    ):
        if key in signature and bool(signature.get(key)) == bool(track.get(key, False)):
            score += weight
            reasons.append(key)
    if (
        signature.get("color_index") is not None
        and signature.get("color_index") == track.get("color_index")
    ):
        score += 0.10
        reasons.append("color")
    if ref.get("last_seen_index") == track.get("index"):
        score += 0.08
        reasons.append("last_seen_index")
    return {
        "track_index": track.get("index"),
        "track_name": current_name,
        "score": round(min(score, 1.0), 3),
        "reason": "+".join(reasons) if reasons else "no_match",
    }


def _regular_tracks(session_info: dict) -> list[dict]:
    return [
        track for track in (session_info.get("tracks") or [])
        if isinstance(track, dict) and isinstance(track.get("index"), int)
    ]


def _normalize_layer(layer: dict, *, now: int) -> dict:
    layer_id = _normalize_key(layer.get("layer_id") or layer.get("label"))
    if not layer_id:
        raise ValueError("layer_id or label is required")
    return {
        "layer_id": layer_id,
        "label": str(layer.get("label") or _humanize_key(layer_id)).strip(),
        "status": _normalize_status(layer.get("status") or "layered"),
        "member_refs": [
            ref for ref in (layer.get("member_refs") or [])
            if isinstance(ref, dict)
        ],
        "linked_layers": _normalize_string_list(layer.get("linked_layers")),
        "notes": str(layer.get("notes") or "").strip(),
        "created_at_ms": int(layer.get("created_at_ms") or now),
        "updated_at_ms": now,
    }


def _normalize_status(value) -> str:
    status = _normalize_key(value or "layered")
    return status if status in _VALID_STATUSES else "layered"


def _normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _normalize_key(item)
        if text and text not in out:
            out.append(text)
    return out


def _normalize_key(value) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _projects_dir() -> Path:
    return Path(_PROJECTS_DIR) if _PROJECTS_DIR is not None else livepilot_projects_dir()


def _humanize_key(value) -> str:
    return str(value or "").replace("_", " ").strip().title()


def _now_ms() -> int:
    return int(time.time() * 1000)

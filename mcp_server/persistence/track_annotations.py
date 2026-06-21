"""Persistent track annotations that can survive track reordering.

Ableton's public surfaces expose track indexes, but indexes are positional.
These helpers store human intent against a track signature, then resolve it
back to the current session on read.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
_STORE_VERSION = 1


def annotation_project_hash(session_info: dict) -> str:
    """Compute a track-order-stable project fingerprint for annotations.

    The main ProjectStore hash intentionally changes when tracks are reordered.
    Track annotations need the opposite behavior: if the user drags "vox1" from
    index 4 to index 2, the notes should still be found. This fingerprint keeps
    broad project identity fields but sorts track/scene/return signatures.
    """
    tempo = session_info.get("tempo", 120.0)
    sig_num = session_info.get("signature_numerator", 4)
    sig_denom = session_info.get("signature_denominator", 4)
    song_length = session_info.get("song_length", 0.0)

    tracks = session_info.get("tracks", []) or []
    track_sig = "|".join(sorted(
        _track_hash_fragment(t) for t in tracks if isinstance(t, dict)
    ))

    return_tracks = session_info.get("return_tracks", []) or []
    return_sig = "|".join(sorted(
        str(r.get("name", "")) for r in return_tracks if isinstance(r, dict)
    ))

    scenes = session_info.get("scenes", []) or []
    scene_sig = "|".join(sorted(
        f"{s.get('name', '')}:{s.get('color_index', 0)}"
        for s in scenes
        if isinstance(s, dict)
    ))

    seed = "||".join([
        f"annotation-v1",
        f"t={float(tempo):.1f}",
        f"sig={sig_num}/{sig_denom}",
        f"len={float(song_length):.2f}",
        f"n_tracks={len(tracks)}",
        f"tracks=[{track_sig}]",
        f"n_returns={len(return_tracks)}",
        f"returns=[{return_sig}]",
        f"n_scenes={len(scenes)}",
        f"scenes=[{scene_sig}]",
    ])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def make_track_signature(track: dict, detail: Optional[dict] = None) -> dict:
    """Build a resolver signature from session-info track data."""
    devices = []
    clips = []
    if isinstance(detail, dict):
        devices = [
            str(d.get("name") or d.get("class_name") or "")
            for d in (detail.get("devices") or [])
            if isinstance(d, dict)
        ][:16]
        clips = [
            str(c.get("name") or "")
            for c in (detail.get("clips") or [])
            if isinstance(c, dict) and c.get("name")
        ][:16]
    return {
        "name": str(track.get("name", "")),
        "color_index": track.get("color_index"),
        "has_midi_input": bool(track.get("has_midi_input", False)),
        "has_audio_input": bool(track.get("has_audio_input", False)),
        "is_foldable": bool(track.get("is_foldable", False)),
        "devices": devices,
        "clips": clips,
    }


def resolve_annotations(session_info: dict, annotations: list[dict]) -> list[dict]:
    """Attach current-track resolution metadata to annotations."""
    tracks = [
        t for t in (session_info.get("tracks") or [])
        if isinstance(t, dict) and isinstance(t.get("index"), int)
    ]
    resolved = []
    for annotation in annotations:
        match = resolve_annotation(session_info, annotation, tracks=tracks)
        item = dict(annotation)
        item["resolution"] = match
        resolved.append(item)
    return resolved


def resolve_annotation(
    session_info: dict,
    annotation: dict,
    tracks: Optional[list[dict]] = None,
) -> dict:
    """Resolve one annotation against the current session track list."""
    del session_info  # Reserved for future resolver inputs.
    candidates = tracks or []
    scored = [
        _score_track(annotation, track)
        for track in candidates
    ]
    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        return {
            "status": "unresolved",
            "resolved_track_index": None,
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
    status = (
        "resolved"
        if resolved
        else "ambiguous"
        if best["score"] >= 0.45
        else "unresolved"
    )
    return {
        "status": status,
        "resolved_track_index": best["track_index"] if resolved else None,
        "resolved_track_name": best["track_name"] if resolved else None,
        "confidence": round(best["score"], 3),
        "reason": "matched_signature" if resolved else "low_confidence_or_ambiguous",
        "candidates": scored[:5],
    }


def find_annotation_for_track(
    session_info: dict,
    annotations: list[dict],
    track_index: int,
) -> Optional[dict]:
    """Return the best annotation currently resolved to track_index."""
    resolved = resolve_annotations(session_info, annotations)
    matches = [
        item for item in resolved
        if item.get("resolution", {}).get("resolved_track_index") == track_index
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda item: item.get("resolution", {}).get("confidence", 0.0),
        reverse=True,
    )
    return matches[0]


class TrackAnnotationStore:
    """Project-scoped JSON sidecar for track annotations."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _PROJECTS_DIR
        self._store = PersistentJsonStore(base / project_id / "track_annotations.json")
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

    def list_annotations(self) -> list[dict]:
        return list(self.get_all().get("annotations", []))

    def upsert(self, annotation: dict) -> dict:
        now = int(time.time() * 1000)
        annotation = dict(annotation)
        annotation.setdefault("annotation_id", _new_annotation_id())
        annotation.setdefault("created_at_ms", now)
        annotation["updated_at_ms"] = now

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            annotations = data.setdefault("annotations", [])
            for index, existing in enumerate(annotations):
                if existing.get("annotation_id") == annotation["annotation_id"]:
                    merged = dict(existing)
                    merged.update(annotation)
                    merged.setdefault("created_at_ms", existing.get("created_at_ms", now))
                    merged["updated_at_ms"] = now
                    annotations[index] = merged
                    data["last_updated_ms"] = now
                    return data
            annotations.append(annotation)
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return next(
            item for item in data.get("annotations", [])
            if item.get("annotation_id") == annotation["annotation_id"]
        )

    def delete(self, annotation_id: str) -> bool:
        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            before = len(data.get("annotations", []))
            data["annotations"] = [
                a for a in data.get("annotations", [])
                if a.get("annotation_id") != annotation_id
            ]
            if len(data["annotations"]) != before:
                data["last_updated_ms"] = int(time.time() * 1000)
            return data

        before = self.list_annotations()
        self._store.update(_update)
        return len(before) != len(self.list_annotations())

    @staticmethod
    def _default() -> dict:
        return {
            "version": _STORE_VERSION,
            "annotations": [],
            "last_updated_ms": 0,
        }


def _track_hash_fragment(track: dict) -> str:
    return ":".join([
        str(track.get("name", "")),
        str(track.get("color_index", 0)),
        str(int(bool(track.get("has_midi_input", False)))),
        str(int(bool(track.get("has_audio_input", False)))),
    ])


def _new_annotation_id() -> str:
    return f"trkann_{uuid.uuid4().hex[:12]}"


def _score_track(annotation: dict, track: dict) -> dict:
    track_ref = annotation.get("track_ref") or {}
    signature = track_ref.get("signature") or {}
    score = 0.0
    reasons: list[str] = []

    stored_name = str(signature.get("name") or track_ref.get("name") or "")
    current_name = str(track.get("name") or "")
    if stored_name and stored_name == current_name:
        score += 0.45
        reasons.append("name")
    elif stored_name and stored_name.lower() == current_name.lower():
        score += 0.35
        reasons.append("name_case_insensitive")

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

    last_seen = track_ref.get("last_seen_index")
    if isinstance(last_seen, int) and last_seen == track.get("index"):
        score += 0.08
        reasons.append("last_seen_index")

    return {
        "track_index": track.get("index"),
        "track_name": current_name,
        "score": round(min(score, 1.0), 3),
        "reasons": reasons,
    }

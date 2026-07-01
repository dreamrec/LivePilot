"""Persistent track annotations that can survive track reordering.

Ableton's public surfaces expose track indexes, but indexes are positional.
These helpers store human intent against a track signature, then resolve it
back to the current session on read.
"""

from __future__ import annotations

import ast
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
_STORE_VERSION = 1
_VALID_SCOPES = {"track", "relationship", "section", "project"}
_ACTIVE_DECISION_STATES = {"committed", "open", "hypothesis"}
_COMMITTED_STATES = {"committed"}
_OPEN_STATES = {"open"}
_REJECTED_STATES = {"rejected"}


def annotation_project_hash(session_info: dict) -> str:
    """Compute a track-order-stable project fingerprint for annotations.

    The main ProjectStore hash intentionally changes when tracks are reordered.
    Track annotations need the opposite behavior: if the user drags "vox1" from
    index 4 to index 2, the notes should still be found. This fingerprint keeps
    stable project identity fields but sorts track/scene/return signatures.
    """
    project_identity = _stable_saved_project_identity(session_info)
    if project_identity:
        seed = "||".join(["annotation-v2", project_identity])
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

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
        f"annotation-v2",
        "unsaved-or-path-unavailable",
        f"n_tracks={len(tracks)}",
        f"tracks=[{track_sig}]",
        f"n_returns={len(return_tracks)}",
        f"returns=[{return_sig}]",
        f"n_scenes={len(scenes)}",
        f"scenes=[{scene_sig}]",
    ])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


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


def annotation_project_id_for_session(
    session_info: dict,
    base_dir: Optional[Path] = None,
) -> str:
    """Return the best project id for sparse, user-authored annotations.

    The direct fingerprint includes broad song identity fields such as tempo.
    That is useful for avoiding collisions, but tempo automation/live-refresh
    snapshots can drift enough to strand annotations in an older project
    folder. If the direct folder has no annotations, recover the existing
    annotation store whose track references resolve best against this session.
    """
    direct_id = annotation_project_hash(session_info)
    base = base_dir or _PROJECTS_DIR
    direct_annotations = _read_annotation_file(
        base / direct_id / "track_annotations.json"
    )
    if direct_annotations:
        return direct_id

    best_id = ""
    best_score: tuple[int, int, int, int, float] = (0, 0, 0, 0, 0.0)
    for path in base.glob("*/track_annotations.json"):
        project_id = path.parent.name
        if project_id == direct_id:
            continue
        annotations = _read_annotation_file(path)
        if not annotations:
            continue
        score = _score_annotation_project(session_info, annotations, path)
        if score > best_score:
            best_id = project_id
            best_score = score

    resolved_tracks, resolved_annotations, layer_tags, _active, _mtime = best_score
    if resolved_tracks >= 2 or (
        resolved_tracks >= 1 and resolved_annotations >= 1 and layer_tags >= 1
    ):
        return best_id
    return direct_id


def normalize_annotation(annotation: dict) -> dict:
    """Normalize optional intent fields while preserving sparse annotations."""
    normalized = dict(annotation)
    scope = str(normalized.get("scope") or "track").strip().lower()
    normalized["scope"] = scope if scope in _VALID_SCOPES else "track"

    for key in (
        "role",
        "priority",
        "notes",
        "tags",
        "mix_intent",
        "composition_intent",
        "sound_design_intent",
        "source",
        "decision_policy",
    ):
        if normalized.get(key) is not None:
            normalized[key] = str(normalized[key]).strip()

    normalized["tags"] = _normalize_string_list(normalized.get("tags"))
    normalized["role_candidates"] = _normalize_string_list(
        normalized.get("role_candidates")
    )
    normalized["constraints"] = _normalize_string_list(normalized.get("constraints"))
    normalized["options"] = _normalize_dict_list(normalized.get("options"))
    normalized["references"] = _normalize_dict_list(normalized.get("references"))
    normalized["relationships"] = _normalize_dict_list(normalized.get("relationships"))

    if normalized.get("relationship") and not normalized["relationships"]:
        normalized["relationships"] = [{
            "type": "related",
            "notes": str(normalized["relationship"]).strip(),
        }]

    if normalized.get("confidence") is not None:
        try:
            normalized["confidence"] = max(0.0, min(1.0, float(normalized["confidence"])))
        except (TypeError, ValueError):
            normalized.pop("confidence", None)

    if not normalized.get("source"):
        normalized["source"] = "user_explicit"
    if normalized.get("confidence") is None and normalized["source"] == "user_explicit":
        normalized["confidence"] = 1.0

    decision_state = str(normalized.get("decision_state") or "").strip().lower()
    if not decision_state:
        decision_state = "open" if normalized["options"] else "committed"
    normalized["decision_state"] = decision_state
    return normalized


def build_track_intent_map(session_info: dict, annotations: list[dict]) -> dict:
    """Build a compact decision-time intent map for the current session."""
    from ..semantic_moves.resolvers import infer_role

    resolved = [
        normalize_annotation(annotation)
        for annotation in resolve_annotations(session_info, annotations)
    ]
    tracks = [
        t for t in (session_info.get("tracks") or [])
        if isinstance(t, dict) and isinstance(t.get("index"), int)
    ]
    by_track: dict[int, list[dict]] = {int(t.get("index")): [] for t in tracks}
    warnings: list[dict] = []
    relationship_intents: list[dict] = []
    section_intents: list[dict] = []
    project_intents: list[dict] = []

    for annotation in resolved:
        resolution = annotation.get("resolution") or {}
        scope = annotation.get("scope") or "track"
        if scope == "project":
            project_intents.append(_compact_annotation(annotation))
        elif scope == "section":
            section_intents.append(_compact_annotation(annotation))
        elif scope == "relationship":
            relationship_intents.append(_compact_annotation(annotation))

        status = resolution.get("status")
        if status in {"ambiguous", "unresolved"}:
            warnings.append({
                "annotation_id": annotation.get("annotation_id"),
                "status": status,
                "reason": resolution.get("reason"),
                "candidates": resolution.get("candidates", []),
            })

        idx = resolution.get("resolved_track_index")
        if isinstance(idx, int) and idx in by_track:
            by_track[idx].append(annotation)

    intent_tracks = []
    annotated_count = 0
    for track in tracks:
        idx = int(track.get("index"))
        active_annotations = [
            a for a in by_track.get(idx, [])
            if a.get("decision_state") not in _REJECTED_STATES
        ]
        rejected_annotations = [
            a for a in by_track.get(idx, [])
            if a.get("decision_state") in _REJECTED_STATES
        ]
        decision_annotations = active_annotations or rejected_annotations
        if decision_annotations:
            annotated_count += 1
        inferred_role = infer_role(str(track.get("name", "")))
        primary = _select_primary_annotation(decision_annotations)
        track_entry = _build_track_intent_entry(
            track=track,
            inferred_role=inferred_role,
            annotations=decision_annotations,
            primary=primary,
        )
        intent_tracks.append(track_entry)

    return {
        "tracks": intent_tracks,
        "relationship_intents": relationship_intents,
        "section_intents": section_intents,
        "project_intents": project_intents,
        "warnings": warnings,
        "coverage": {
            "annotated_tracks": annotated_count,
            "total_tracks": len(tracks),
        },
    }


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
        annotation = normalize_annotation(annotation)
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


def _read_annotation_file(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict) or data.get("version") != _STORE_VERSION:
        return []
    annotations = data.get("annotations")
    return list(annotations) if isinstance(annotations, list) else []


def _score_annotation_project(
    session_info: dict,
    annotations: list[dict],
    path: Path,
) -> tuple[int, int, int, int, float]:
    resolved = resolve_annotations(session_info, annotations)
    resolved_track_indices = {
        item.get("resolution", {}).get("resolved_track_index")
        for item in resolved
        if item.get("resolution", {}).get("status") == "resolved"
        and isinstance(item.get("resolution", {}).get("resolved_track_index"), int)
    }
    resolved_annotations = [
        item for item in resolved
        if item.get("resolution", {}).get("status") == "resolved"
    ]
    layer_tags = sum(
        1
        for item in resolved_annotations
        for tag in (item.get("tags") or [])
        if str(tag).strip().lower().startswith("layer:")
    )
    active_annotations = [
        item for item in resolved_annotations
        if item.get("decision_state") not in _REJECTED_STATES
    ]
    try:
        mtime = float(path.stat().st_mtime)
    except OSError:
        mtime = 0.0
    return (
        len(resolved_track_indices),
        len(resolved_annotations),
        layer_tags,
        len(active_annotations),
        mtime,
    )


def _new_annotation_id() -> str:
    return f"trkann_{uuid.uuid4().hex[:12]}"


def _normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                parsed = None
            value = parsed if isinstance(parsed, list) else [text]
        elif "," in text:
            value = [part.strip() for part in text.split(",")]
        else:
            value = [text]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip().startswith("["):
            for text in _normalize_string_list(item):
                if text not in out:
                    out.append(text)
            continue
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def _normalize_dict_list(value) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _select_primary_annotation(annotations: list[dict]) -> Optional[dict]:
    if not annotations:
        return None
    priority = {
        "committed": 0,
        "open": 1,
        "hypothesis": 2,
    }
    return sorted(
        annotations,
        key=lambda a: (
            priority.get(str(a.get("decision_state") or "committed"), 5),
            -float(a.get("confidence") or 0.0),
            str(a.get("updated_at_ms") or ""),
        ),
    )[0]


def _build_track_intent_entry(
    track: dict,
    inferred_role: str,
    annotations: list[dict],
    primary: Optional[dict],
) -> dict:
    effective_role = None
    role_source = "inferred_name"
    requires_audition = False
    decision_state = "inferred"
    priority = None

    if primary:
        decision_state = primary.get("decision_state") or "committed"
        priority = primary.get("priority") or None

    candidate_inferred_role = (
        "" if decision_state in _REJECTED_STATES else inferred_role
    )
    role_candidates = _collect_role_candidates(annotations, candidate_inferred_role)

    if primary:
        selected = _selected_option(primary)
        if selected and selected.get("role"):
            effective_role = str(selected["role"]).strip()
            role_source = "selected_option"
        elif decision_state in _COMMITTED_STATES and primary.get("role"):
            effective_role = primary.get("role")
            role_source = primary.get("source") or "annotation"
        elif decision_state in _OPEN_STATES:
            role_source = "open_options"
            requires_audition = True
        elif decision_state == "hypothesis" and primary.get("role"):
            effective_role = primary.get("role")
            role_source = primary.get("source") or "hypothesis"
        elif decision_state in _REJECTED_STATES:
            effective_role = primary.get("role") or "rejected"
            role_source = primary.get("source") or "rejected_annotation"

        if primary.get("decision_policy") == "audition_before_commit":
            requires_audition = True

    if not effective_role and role_source != "open_options":
        effective_role = inferred_role

    return {
        "index": track.get("index"),
        "name": track.get("name", ""),
        "inferred_role": inferred_role,
        "effective_role": effective_role,
        "role_candidates": role_candidates,
        "role_source": role_source,
        "decision_state": decision_state,
        "priority": priority or "undecided",
        "intent": _merge_intent_fields(annotations),
        "constraints": _merge_string_fields(annotations, "constraints"),
        "options": _merge_list_fields(annotations, "options"),
        "references": _merge_list_fields(annotations, "references"),
        "relationships": _merge_relationships(annotations),
        "requires_audition": requires_audition,
        "annotations": [_compact_annotation(a) for a in annotations],
    }


def _collect_role_candidates(annotations: list[dict], inferred_role: str) -> list[str]:
    candidates: list[str] = []
    for annotation in annotations:
        for role in annotation.get("role_candidates") or []:
            if role and role not in candidates:
                candidates.append(role)
        role = annotation.get("role")
        if role and role not in candidates:
            candidates.append(role)
        for option in annotation.get("options") or []:
            role = option.get("role") or option.get("effective_role")
            if role and role not in candidates:
                candidates.append(str(role))
    if inferred_role and inferred_role != "unknown" and inferred_role not in candidates:
        candidates.append(inferred_role)
    return candidates


def _selected_option(annotation: dict) -> Optional[dict]:
    selected_id = annotation.get("selected_option_id")
    if not selected_id:
        return None
    for option in annotation.get("options") or []:
        if option.get("option_id") == selected_id:
            return option
    return None


def _merge_intent_fields(annotations: list[dict]) -> dict:
    merged: dict = {}
    for key in ("notes", "mix_intent", "composition_intent", "sound_design_intent"):
        values = [
            str(a.get(key)).strip()
            for a in annotations
            if a.get(key) is not None and str(a.get(key)).strip()
        ]
        if values:
            merged[key] = values[-1]
    return merged


def _merge_string_fields(annotations: list[dict], key: str) -> list[str]:
    merged: list[str] = []
    for annotation in annotations:
        for value in annotation.get(key) or []:
            if value not in merged:
                merged.append(value)
    return merged


def _merge_list_fields(annotations: list[dict], key: str) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for annotation in annotations:
        for value in annotation.get(key) or []:
            token = repr(sorted(value.items()))
            if token not in seen:
                merged.append(value)
                seen.add(token)
    return merged


def _merge_relationships(annotations: list[dict]) -> list[dict]:
    relationships = _merge_list_fields(annotations, "relationships")
    for annotation in annotations:
        if annotation.get("relationship"):
            relationships.append({
                "type": "related",
                "notes": annotation.get("relationship"),
            })
    return relationships


def _compact_annotation(annotation: dict) -> dict:
    keep = (
        "annotation_id",
        "scope",
        "decision_state",
        "source",
        "confidence",
        "role",
        "role_candidates",
        "priority",
        "notes",
        "tags",
        "mix_intent",
        "composition_intent",
        "sound_design_intent",
        "constraints",
        "options",
        "references",
        "relationships",
        "relationship",
        "decision_policy",
        "selected_option_id",
        "resolution",
    )
    return {
        key: annotation[key]
        for key in keep
        if key in annotation and annotation[key] not in (None, [], {})
    }


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

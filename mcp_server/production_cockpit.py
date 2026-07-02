"""Browser-first cockpit for LivePilot production workflows."""

from __future__ import annotations

import json
from typing import Optional

from fastmcp import Context
from fastmcp.tools.base import ToolResult

from . import __version__
from .persistence.agent_focus import AgentFocusService
from .persistence.briefs import BriefService
from .persistence.layer_groups import LayerGroupService
from .persistence.orchestration_queue import OrchestrationService
from .persistence.production_context import ProductionContextService
from .persistence.track_annotations import (
    TrackAnnotationStore,
    annotation_project_id_for_session,
    build_track_intent_map as build_track_intent_map_data,
    make_track_signature,
)
from .server import mcp
from .tools._conductor import classify_request

_BACKEND_TOOL_NAMES = {
    "get_state": "get_cockpit_state",
    "set_focus": "set_cockpit_focus",
    "clear_focus": "clear_cockpit_focus",
    "save_context": "save_production_context",
    "send_brief": "send_cockpit_brief",
    "save_track_intent": "save_cockpit_track_intent",
    "save_layer": "save_cockpit_layer_group",
    "delete_layer": "delete_cockpit_layer_group",
    "audition_action": "submit_cockpit_audition_action",
    "get_live_selection": "get_cockpit_live_selection",
    "select_live_track": "select_live_track",
    "loop_live_section": "loop_live_section",
    "write_live_locator": "write_live_locator",
}

_TRACK_GROUPS = [
    {
        "key": "maps",
        "label": "Maps",
        "terms": ("tempo", "section map", "chord map", "marker", "locator"),
    },
    {
        "key": "drums",
        "label": "Drums",
        "terms": ("drum", "ezdrummer", "kick", "snare", "trigger"),
    },
    {
        "key": "bass",
        "label": "Bass",
        "terms": ("bass", "ezbass", "low", "sub"),
    },
    {
        "key": "keys_piano",
        "label": "Keys / Piano",
        "terms": ("key", "piano", "ezkeys", "upright", "organ", "chord"),
    },
    {
        "key": "vocals",
        "label": "Vocals",
        "terms": ("vox", "vocal", "voice", "harm", "merged"),
    },
    {
        "key": "guitars",
        "label": "Guitars",
        "terms": ("guit", "gtr", "guitar", "elec", "distorted", "born-run"),
    },
    {
        "key": "strings_textures",
        "label": "Strings / Textures",
        "terms": (
            "string", "violin", "viola", "cello", "pad", "glock",
            "woman", "ahh", "ensemb", "texture",
        ),
    },
    {
        "key": "sketches_archive",
        "label": "Sketches / Archive",
        "terms": ("odds", "ends", "sketch", "test", "moises", "import"),
    },
]

_GROUP_LABELS = {item["key"]: item["label"] for item in _TRACK_GROUPS}
_LAYER_TAG_PREFIX = "layer:"
_LAYER_STATUS_TAG_PREFIX = "layer_status:"


def _cockpit_url(ctx: Context) -> Optional[str]:
    base = _focus_panel_url(ctx)
    if not base:
        return None
    return base.rstrip("/") + "/cockpit"


def _backend_tool_map() -> dict[str, str]:
    return dict(_BACKEND_TOOL_NAMES)


def _lifespan(ctx: Context) -> dict:
    return getattr(ctx, "lifespan_context", {}) or {}


def _cockpit_capabilities(ctx: Context) -> dict:
    mode = str(_lifespan(ctx).get("cockpit_mode") or "").strip().lower()
    if mode:
        live_mode = mode == "live"
    else:
        live_mode = _lifespan(ctx).get("ableton") is not None
    return {
        "live_pointing": live_mode,
        "transport_ops": live_mode,
        "locator_write": live_mode,
    }


def _get_ableton(ctx: Context):
    return _lifespan(ctx)["ableton"]


def _require_session_info(ctx: Context) -> dict:
    info = _get_ableton(ctx).send_command("get_session_info")
    if not isinstance(info, dict) or info.get("error"):
        raise RuntimeError(f"Could not read session info: {info!r}")
    return info


def _focus_service(ctx: Context) -> AgentFocusService:
    service = _lifespan(ctx).get("agent_focus")
    if isinstance(service, AgentFocusService):
        return service
    return AgentFocusService()


def _production_context_service(ctx: Context) -> ProductionContextService:
    service = _lifespan(ctx).get("production_context")
    if isinstance(service, ProductionContextService):
        return service
    return ProductionContextService()


def _layer_group_service(ctx: Context) -> LayerGroupService:
    service = _lifespan(ctx).get("layer_groups")
    if isinstance(service, LayerGroupService):
        return service
    return LayerGroupService()


def _brief_service(ctx: Context) -> BriefService:
    service = _lifespan(ctx).get("briefs")
    if isinstance(service, BriefService):
        return service
    return BriefService()


def _orchestration_service(ctx: Context) -> OrchestrationService:
    service = _lifespan(ctx).get("orchestration_queue")
    if isinstance(service, OrchestrationService):
        return service
    return OrchestrationService()


def _annotation_store_for_session(session_info: dict) -> TrackAnnotationStore:
    return TrackAnnotationStore(annotation_project_id_for_session(session_info))


def _focus_panel_url(ctx: Context) -> Optional[str]:
    value = _lifespan(ctx).get("focus_panel_url")
    return str(value) if value else None


def _regular_tracks(session_info: dict) -> list[dict]:
    tracks = []
    for track in session_info.get("tracks") or []:
        if not isinstance(track, dict) or not isinstance(track.get("index"), int):
            continue
        group = _classify_track_group(track)
        tracks.append({
            "index": track.get("index"),
            "name": track.get("name", ""),
            "group": group["key"],
            "group_label": group["label"],
            "color_index": track.get("color_index"),
            "mute": track.get("mute"),
            "solo": track.get("solo"),
            "arm": track.get("arm"),
            "has_midi_input": track.get("has_midi_input"),
            "has_audio_input": track.get("has_audio_input"),
            "is_foldable": track.get("is_foldable"),
        })
    return tracks


def _normalize_cockpit_focus_indices(track_indices) -> list[int]:
    if isinstance(track_indices, str):
        text = track_indices.strip()
        if text.startswith("["):
            track_indices = json.loads(text)
        elif text:
            track_indices = [part.strip() for part in text.split(",")]
        else:
            track_indices = []
    if not isinstance(track_indices, list):
        raise ValueError(
            "track_indices must be a list, JSON array, or comma-separated string"
        )
    out: list[int] = []
    for value in track_indices:
        idx = int(value)
        if idx < 0:
            raise ValueError("Cockpit focus currently supports regular tracks only")
        if idx not in out:
            out.append(idx)
    return out


def _classify_track_group(track: dict) -> dict:
    name = str(track.get("name") or "").lower()
    for group in _TRACK_GROUPS:
        if any(term in name for term in group["terms"]):
            return {"key": group["key"], "label": group["label"]}
    return {"key": "other", "label": "Other"}


def _build_track_groups(tracks: list[dict]) -> list[dict]:
    by_key = {
        group["key"]: {
            "key": group["key"],
            "label": group["label"],
            "count": 0,
            "track_indices": [],
            "track_names": [],
        }
        for group in _TRACK_GROUPS
    }
    by_key["other"] = {
        "key": "other",
        "label": "Other",
        "count": 0,
        "track_indices": [],
        "track_names": [],
    }
    for track in tracks:
        if not _is_musical_target_track(track):
            continue
        key = str(track.get("group") or "other")
        entry = by_key.setdefault(key, {
            "key": key,
            "label": _GROUP_LABELS.get(key, key.replace("_", " ").title()),
            "count": 0,
            "track_indices": [],
            "track_names": [],
        })
        entry["count"] += 1
        entry["track_indices"].append(track.get("index"))
        entry["track_names"].append(track.get("name", ""))
    return [group for group in by_key.values() if group["count"] > 0]


def _is_musical_target_track(track: dict) -> bool:
    """Return False for maps and organizational folder tracks."""
    constraints = {
        str(item or "").strip().lower()
        for item in (track.get("constraints") or [])
    }
    if constraints & {
        "folder_only",
        "metadata_only",
        "do_not_target_for_mix_decisions",
    }:
        return False
    role = str(track.get("effective_role") or track.get("inferred_role") or "").strip().lower()
    if role in {"organizational_folder", "utility_map"}:
        return False
    if str(track.get("priority") or "").strip().lower() == "utility":
        return False
    return True


def _normalize_target_token(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _build_layer_groups(
    tracks: list[dict],
    stored_layers: Optional[list[dict]] = None,
) -> list[dict]:
    by_key: dict[str, dict] = {}
    for group in stored_layers or []:
        key = _normalize_target_token(
            str(group.get("key") or group.get("layer_id") or "")
        )
        if not key:
            continue
        entry = dict(group)
        entry["key"] = key
        entry["layer_id"] = key
        entry.setdefault("label", _humanize_key(key))
        entry.setdefault("track_indices", [])
        entry.setdefault("track_names", [])
        entry.setdefault("linked_layers", [])
        entry.setdefault("status", "layered")
        entry.setdefault("source", "store")
        sources = list(entry.get("sources") or [])
        if "store" not in sources:
            sources.insert(0, "store")
        entry["sources"] = sources
        entry["track_indices"] = list(entry.get("track_indices") or [])
        entry["track_names"] = list(entry.get("track_names") or [])
        entry["count"] = len(entry["track_indices"])
        entry["is_expandable"] = entry.get("status") in {"singleton", "potential"}
        by_key[key] = entry

    for group in _annotation_layer_groups(tracks):
        key = str(group.get("key") or "")
        if key in by_key:
            entry = by_key[key]
            entry.setdefault("sources", ["store"])
            if "annotation_tag" not in entry["sources"]:
                entry["sources"].append("annotation_tag")
            for index, name in zip(
                group.get("track_indices") or [],
                group.get("track_names") or [],
            ):
                if index not in entry["track_indices"]:
                    entry["track_indices"].append(index)
                    entry["track_names"].append(name)
            for linked in group.get("linked_layers") or []:
                if linked not in entry["linked_layers"]:
                    entry["linked_layers"].append(linked)
            entry["count"] = len(entry["track_indices"])
            if entry.get("status") == "layered" and group.get("status") == "potential":
                entry["status"] = "potential"
            entry["is_expandable"] = entry.get("status") in {"singleton", "potential"}
        else:
            item = dict(group)
            item["source"] = "annotation_tag"
            item["sources"] = ["annotation_tag"]
            by_key[key] = item
    return sorted(
        by_key.values(),
        key=lambda item: str(item.get("label") or "").lower(),
    )


def _annotation_layer_groups(tracks: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for track in tracks:
        if not _is_musical_target_track(track):
            continue
        track_index = track.get("index")
        for annotation in track.get("annotations") or []:
            if annotation.get("decision_state") == "rejected":
                continue
            layer_keys = _layer_keys_from_annotation(annotation)
            for key in layer_keys:
                entry = by_key.setdefault(key, {
                    "key": key,
                    "label": _humanize_key(key),
                    "count": 0,
                    "track_indices": [],
                    "track_names": [],
                    "linked_layers": [],
                    "status": "singleton",
                    "status_tags": [],
                    "is_expandable": True,
                })
                if track_index not in entry["track_indices"]:
                    entry["track_indices"].append(track_index)
                    entry["track_names"].append(track.get("name", ""))
                    entry["count"] = len(entry["track_indices"])
                for status in _layer_statuses_from_annotation(annotation, key):
                    if status not in entry["status_tags"]:
                        entry["status_tags"].append(status)
                for linked_key in _linked_layer_keys(annotation):
                    if linked_key != key and linked_key not in entry["linked_layers"]:
                        entry["linked_layers"].append(linked_key)
    for entry in by_key.values():
        entry["status"] = _layer_group_status(entry)
        entry["is_expandable"] = entry["status"] in {"singleton", "potential"}
    return sorted(by_key.values(), key=lambda item: item["label"].lower())


def _layer_keys_from_annotation(annotation: dict) -> list[str]:
    keys: list[str] = []
    for tag in annotation.get("tags") or []:
        text = str(tag or "").strip()
        if not text.lower().startswith(_LAYER_TAG_PREFIX):
            continue
        key = _normalize_target_token(text[len(_LAYER_TAG_PREFIX):])
        if key and key not in keys:
            keys.append(key)
    return keys


def _linked_layer_keys(annotation: dict) -> list[str]:
    keys: list[str] = []
    for relationship in annotation.get("relationships") or []:
        if not isinstance(relationship, dict):
            continue
        rel_type = _normalize_target_token(str(relationship.get("type") or ""))
        if rel_type not in {"linked_layer", "linked_layers", "linked"}:
            continue
        raw_values = [
            relationship.get("layer_id"),
            relationship.get("target_layer"),
            relationship.get("layer"),
        ]
        for value in raw_values:
            key = _normalize_target_token(str(value or ""))
            if key and key not in keys:
                keys.append(key)
    return keys


def _layer_statuses_from_annotation(annotation: dict, layer_key: str) -> list[str]:
    statuses: list[str] = []
    for tag in annotation.get("tags") or []:
        text = str(tag or "").strip()
        lower = text.lower()
        if not lower.startswith(_LAYER_STATUS_TAG_PREFIX):
            continue
        raw = text[len(_LAYER_STATUS_TAG_PREFIX):]
        parts = raw.split(":")
        if len(parts) >= 2:
            target_layer = _normalize_target_token(parts[0])
            if target_layer != layer_key:
                continue
            status = _normalize_target_token(":".join(parts[1:]))
        else:
            status = _normalize_target_token(raw)
        if status and status not in statuses:
            statuses.append(status)
    return statuses


def _layer_group_status(entry: dict) -> str:
    statuses = set(entry.get("status_tags") or [])
    if statuses & {"potential", "planned", "future", "expandable"}:
        return "potential"
    try:
        count = int(entry.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    return "layered" if count > 1 else "singleton"


def _humanize_key(value: str) -> str:
    return str(value or "").replace("_", " ").strip().title()


def _target_context(
    state: dict,
    tracks: list[dict],
    layer_groups: Optional[list[dict]] = None,
    *,
    beats_per_bar: float = 4.0,
) -> dict:
    raw_query = str(state.get("target_query") or state.get("target_group") or "").strip()
    target_mode = _normalize_target_mode(state.get("target_mode"))
    target_layer = _normalize_target_token(str(state.get("target_layer") or ""))
    normalized = _normalize_target_token(raw_query)
    layer_lookup = {
        group["key"]: group
        for group in (layer_groups or [])
        if isinstance(group, dict) and group.get("key")
    }
    for group in (layer_groups or []):
        if not isinstance(group, dict):
            continue
        layer_lookup[_normalize_target_token(group.get("label", ""))] = group

    matched_layer = None
    if target_mode == "layer":
        matched_layer = layer_lookup.get(target_layer) or layer_lookup.get(normalized)
        if matched_layer:
            matched_indices = set(matched_layer.get("track_indices") or [])
            matches = [
                track for track in tracks
                if track.get("index") in matched_indices
            ]
            section = _section_context(state)
            return {
                "query": raw_query,
                "target_mode": target_mode,
                "target_layer": matched_layer.get("key", ""),
                "matched_layer": matched_layer.get("key", ""),
                "matched_layer_label": matched_layer.get("label", ""),
                "matched_group": "",
                "matched_group_label": "",
                "track_indices": [track.get("index") for track in matches],
                "track_names": [track.get("name", "") for track in matches],
                "track_count": len(matches),
                "section": section,
            }
        section = _section_context(state)
        return {
            "query": raw_query,
            "target_mode": target_mode,
            "target_layer": target_layer,
            "matched_layer": "",
            "matched_layer_label": "",
            "matched_group": "",
            "matched_group_label": "",
            "track_indices": [],
            "track_names": [],
            "track_count": 0,
            "section": section,
        }

    group_lookup = {
        group["key"]: group
        for group in _TRACK_GROUPS
    }
    for group in _TRACK_GROUPS:
        group_lookup[_normalize_target_token(group["label"])] = group
        for term in group["terms"]:
            group_lookup[_normalize_target_token(term)] = group

    matched_group = group_lookup.get(normalized)
    if matched_group:
        matches = [
            track for track in tracks
            if (
                track.get("group") == matched_group["key"]
                and _is_musical_target_track(track)
            )
        ]
    elif raw_query:
        terms = [
            term for term in raw_query.lower().replace(",", " ").split()
            if term
        ]
        matches = [
            track for track in tracks
            if _track_matches_terms(track, terms)
        ]
    else:
        matches = []

    section = _section_context(state, beats_per_bar=beats_per_bar)
    return {
        "query": raw_query,
        "target_mode": target_mode,
        "target_layer": target_layer,
        "matched_layer": "",
        "matched_layer_label": "",
        "matched_group": matched_group["key"] if matched_group else "",
        "matched_group_label": matched_group["label"] if matched_group else "",
        "track_indices": [track.get("index") for track in matches],
        "track_names": [track.get("name", "") for track in matches],
        "track_count": len(matches),
        "section": section,
    }


def _normalize_target_mode(value) -> str:
    mode = _normalize_target_token(str(value or "instrument"))
    if mode in {"instrument", "layer", "query"}:
        return mode
    return "instrument"


def _track_matches_terms(track: dict, terms: list[str]) -> bool:
    if not terms:
        return False
    haystack = " ".join([
        str(track.get("name") or ""),
        str(track.get("group") or ""),
        str(track.get("group_label") or ""),
        str(track.get("effective_role") or ""),
        str(track.get("inferred_role") or ""),
    ]).lower()
    return all(term in haystack for term in terms)


def _section_context(state: dict, *, beats_per_bar: float = 4.0) -> dict:
    section = state.get("section") if isinstance(state.get("section"), dict) else None
    if not section:
        return {
            "section_id": "",
            "scope": "whole_song",
            "label": "Whole song",
            "source": "whole_song",
            "start_beat": None,
            "end_beat": None,
            "start_bar": None,
            "end_bar": None,
        }
    start_beat = _float_or_none(section.get("start_beat"))
    end_beat = _float_or_none(section.get("end_beat"))
    return {
        "section_id": str(section.get("section_id") or section.get("id") or ""),
        "scope": str(section.get("section_id") or section.get("id") or "custom"),
        "label": str(section.get("label") or "Section"),
        "source": str(section.get("source") or "manual"),
        "start_beat": start_beat,
        "end_beat": end_beat,
        "start_bar": _bar_from_beat(start_beat, beats_per_bar),
        "end_bar": _bar_from_beat(end_beat, beats_per_bar),
    }


def _float_or_none(value) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _beats_per_bar(session_info: dict) -> float:
    numerator = _float_or_none(
        session_info.get("signature_numerator")
        or session_info.get("time_signature_numerator")
    )
    if numerator is None or numerator <= 0:
        return 4.0
    return numerator


def _song_length_beats(session_info: dict) -> Optional[float]:
    value = _float_or_none(session_info.get("song_length"))
    if value is None or value <= 0:
        return None
    return value


def _current_song_time_beats(session_info: dict) -> Optional[float]:
    for key in ("current_song_time", "current_time", "song_time"):
        value = _float_or_none(session_info.get(key))
        if value is not None:
            return value
    return None


def _bar_from_beat(beat: Optional[float], beats_per_bar: float) -> Optional[float]:
    if beat is None:
        return None
    return (float(beat) / beats_per_bar) + 1.0


def _section_bar_label(value: Optional[float]) -> str:
    if value is None:
        return ""
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}".rstrip("0").rstrip(".")


def _section_id(source: str, label: str, start_beat: Optional[float]) -> str:
    start = 0 if start_beat is None else int(round(float(start_beat) * 1000))
    key = _normalize_target_token(label) or "section"
    return f"{_normalize_target_token(source)}_{start}_{key}"


def _section_entry(
    *,
    source: str,
    label: str,
    start_beat: Optional[float],
    end_beat: Optional[float],
    beats_per_bar: float,
    current_beat: Optional[float],
) -> dict:
    if start_beat is not None and end_beat is not None and end_beat <= start_beat:
        end_beat = None
    duration_beats = (
        max(0.0, float(end_beat) - float(start_beat))
        if start_beat is not None and end_beat is not None else None
    )
    start_bar = _bar_from_beat(start_beat, beats_per_bar)
    end_bar = _bar_from_beat(end_beat, beats_per_bar)
    is_current = False
    if current_beat is not None and start_beat is not None:
        if end_beat is None:
            is_current = current_beat >= start_beat
        else:
            is_current = start_beat <= current_beat < end_beat
    return {
        "id": _section_id(source, label, start_beat),
        "label": str(label or "Section").strip() or "Section",
        "source": source,
        "start_beat": start_beat,
        "end_beat": end_beat,
        "duration_beats": duration_beats,
        "start_bar": start_bar,
        "end_bar": end_bar,
        "bar_label": _section_range_label(start_bar, end_bar),
        "is_current": is_current,
    }


def _section_range_label(
    start_bar: Optional[float],
    end_bar: Optional[float],
) -> str:
    if start_bar is None and end_bar is None:
        return ""
    if end_bar is None:
        return f"Bar {_section_bar_label(start_bar)}"
    return f"Bars {_section_bar_label(start_bar)}-{_section_bar_label(end_bar)}"


def _cue_points_from_session(session_info: dict) -> list[dict]:
    candidates = []
    for key in ("cue_points", "locators", "arrangement_markers"):
        raw = session_info.get(key)
        if isinstance(raw, dict):
            raw = raw.get("cue_points") or raw.get("locators") or raw.get("markers")
        if isinstance(raw, list):
            candidates.extend(item for item in raw if isinstance(item, dict))
    seen: set[tuple[float, str]] = set()
    normalized: list[dict] = []
    for index, cue in enumerate(candidates):
        time_value = _float_or_none(
            cue.get("time")
            if "time" in cue
            else cue.get("beat")
            if "beat" in cue
            else cue.get("start_beat")
        )
        if time_value is None or time_value < 0:
            continue
        label = str(cue.get("name") or cue.get("label") or f"Marker {index + 1}").strip()
        key = (round(time_value, 6), label)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"time": time_value, "label": label})
    return sorted(normalized, key=lambda item: item["time"])


def _section_map_from_cue_points(session_info: dict) -> list[dict]:
    cues = _cue_points_from_session(session_info)
    if not cues:
        return []
    beats = _beats_per_bar(session_info)
    current = _current_song_time_beats(session_info)
    song_length = _song_length_beats(session_info)
    sections: list[dict] = []
    for index, cue in enumerate(cues):
        next_time = cues[index + 1]["time"] if index + 1 < len(cues) else song_length
        sections.append(_section_entry(
            source="cue_points",
            label=cue["label"],
            start_beat=cue["time"],
            end_beat=next_time,
            beats_per_bar=beats,
            current_beat=current,
        ))
    return sections


def _section_map_from_section_track(session_info: dict) -> list[dict]:
    beats = _beats_per_bar(session_info)
    current = _current_song_time_beats(session_info)
    sections: list[dict] = []
    for track in session_info.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        name = str(track.get("name") or "").lower()
        if "section map" not in name and "arrangement map" not in name:
            continue
        clips = (
            track.get("clips")
            or track.get("arrangement_clips")
            or track.get("clip_slots")
            or []
        )
        for index, clip in enumerate(clips):
            if not isinstance(clip, dict):
                continue
            start = _float_or_none(
                clip.get("start_beat")
                if "start_beat" in clip
                else clip.get("start_time")
                if "start_time" in clip
                else clip.get("start")
            )
            end = _float_or_none(
                clip.get("end_beat")
                if "end_beat" in clip
                else clip.get("end_time")
                if "end_time" in clip
                else clip.get("end")
            )
            length = _float_or_none(clip.get("length"))
            if end is None and start is not None and length is not None:
                end = start + length
            if start is None:
                continue
            label = str(clip.get("name") or clip.get("label") or f"Section {index + 1}")
            sections.append(_section_entry(
                source="section_track",
                label=label,
                start_beat=start,
                end_beat=end,
                beats_per_bar=beats,
                current_beat=current,
            ))
    return sorted(sections, key=lambda item: item.get("start_beat") or 0.0)


def _section_map_from_saved_context(session_info: dict, state: dict) -> list[dict]:
    section = state.get("section") if isinstance(state.get("section"), dict) else None
    if not section:
        return []
    beats = _beats_per_bar(session_info)
    current = _current_song_time_beats(session_info)
    return [_section_entry(
        source=str(section.get("source") or "manual"),
        label=str(section.get("label") or "Section"),
        start_beat=_float_or_none(section.get("start_beat")),
        end_beat=_float_or_none(section.get("end_beat")),
        beats_per_bar=beats,
        current_beat=current,
    )]


def _fallback_section_map(session_info: dict) -> list[dict]:
    beats = _beats_per_bar(session_info)
    current = _current_song_time_beats(session_info)
    return [_section_entry(
        source="manual",
        label="Whole song",
        start_beat=0.0,
        end_beat=_song_length_beats(session_info),
        beats_per_bar=beats,
        current_beat=current,
    )]


def _build_section_map(session_info: dict, state: dict) -> dict:
    sources = [
        ("cue_points", "Arrangement markers", _section_map_from_cue_points),
        ("section_track", "SECTION MAP track", _section_map_from_section_track),
        ("saved_context", "Saved section", lambda info: _section_map_from_saved_context(info, state)),
        ("manual", "Manual scope", _fallback_section_map),
    ]
    source = "manual"
    source_label = "Manual scope"
    sections: list[dict] = []
    for key, label, builder in sources:
        sections = builder(session_info)
        if sections:
            source = key
            source_label = label
            break
    current_section_id = ""
    for section in sections:
        if section.get("is_current"):
            current_section_id = str(section.get("id") or "")
            break
    return {
        "source": source,
        "source_label": source_label,
        "beats_per_bar": _beats_per_bar(session_info),
        "current_song_time": _current_song_time_beats(session_info),
        "song_length": _song_length_beats(session_info),
        "current_section_id": current_section_id,
        "sections": sections,
    }


def _read_cue_points(ctx: Context) -> list[dict]:
    try:
        result = _get_ableton(ctx).send_command("get_cue_points", {}) or {}
    except Exception:
        return []
    if not isinstance(result, dict) or result.get("error"):
        return []
    cues = result.get("cue_points")
    return cues if isinstance(cues, list) else []


def _section_map_track(track: dict) -> bool:
    name = str(track.get("name") or "").lower()
    return "section map" in name or "arrangement map" in name


def _read_arrangement_clips(ctx: Context, track_index: int) -> list[dict]:
    try:
        result = _get_ableton(ctx).send_command(
            "get_arrangement_clips",
            {"track_index": int(track_index)},
        ) or {}
    except Exception:
        return []
    if not isinstance(result, dict) or result.get("error"):
        return []
    clips = result.get("clips")
    return clips if isinstance(clips, list) else []


def _attach_section_track_clips(ctx: Context, session_info: dict) -> dict:
    tracks = session_info.get("tracks") or []
    updated_tracks: list[dict] = []
    changed = False
    for track in tracks:
        if not isinstance(track, dict):
            updated_tracks.append(track)
            continue
        if not _section_map_track(track):
            updated_tracks.append(track)
            continue
        if track.get("clips") or track.get("arrangement_clips"):
            updated_tracks.append(track)
            continue
        index = track.get("index")
        if not isinstance(index, int):
            updated_tracks.append(track)
            continue
        clips = _read_arrangement_clips(ctx, index)
        if not clips:
            updated_tracks.append(track)
            continue
        entry = dict(track)
        entry["arrangement_clips"] = clips
        updated_tracks.append(entry)
        changed = True
    if not changed:
        return session_info
    enriched = dict(session_info)
    enriched["tracks"] = updated_tracks
    return enriched


def _compact_orchestration_job(job: dict) -> dict:
    scope = job.get("scope") if isinstance(job.get("scope"), dict) else {}
    return {
        "job_id": job.get("job_id", ""),
        "title": job.get("title") or job.get("job_type", "Ableton job"),
        "job_type": job.get("job_type", ""),
        "status": job.get("status", ""),
        "priority": job.get("priority"),
        "snapshot_id": job.get("snapshot_id", ""),
        "requires_transport": bool(job.get("requires_transport", False)),
        "requires_write": bool(job.get("requires_write", False)),
        "write_set": job.get("write_set") or [],
        "scope": scope,
        "sequence": job.get("sequence"),
        "updated_at_ms": job.get("updated_at_ms"),
    }


def _compact_orchestration_proposal(proposal: dict) -> dict:
    return {
        "proposal_id": proposal.get("proposal_id", ""),
        "task_id": proposal.get("task_id", ""),
        "snapshot_id": proposal.get("snapshot_id", ""),
        "agent_role": proposal.get("agent_role", ""),
        "summary": proposal.get("summary", ""),
        "confidence": proposal.get("confidence"),
        "risk": proposal.get("risk", ""),
        "status": proposal.get("status", ""),
        "requires_user_decision": bool(
            proposal.get("requires_user_decision", False)
        ),
        "transport_required": bool(proposal.get("transport_required", False)),
        "write_set": proposal.get("write_set") or [],
        "updated_at_ms": proposal.get("updated_at_ms"),
    }


def _compact_orchestration_lease(lease: dict) -> dict:
    return {
        "lease_id": lease.get("lease_id", ""),
        "resource": lease.get("resource", ""),
        "job_id": lease.get("job_id", ""),
        "owner": lease.get("owner", ""),
        "expires_at_ms": lease.get("expires_at_ms"),
    }


def _orchestration_summary(ctx: Context, session_info: dict) -> dict:
    """Return queue/proposal state for cockpit display.

    This is read-only and intentionally compact: the cockpit needs enough state
    to show what is waiting for Codex, not the full durable queue payload.
    """
    try:
        store = _orchestration_service(ctx).store_for_session(session_info)
        data = store.get_all()
        tasks = store.list_tasks()
        proposals = store.list_proposals()
        jobs = store.list_jobs(ordered=True)
        active_leases = store.list_leases(include_expired=False)
        queued_jobs = [
            job for job in jobs
            if job.get("status") == "queued"
        ]
        active_jobs = [
            job for job in jobs
            if job.get("status") in {"queued", "running", "awaiting_decision"}
        ]
        recent_jobs = sorted(
            [
                job for job in jobs
                if job.get("status") in {"done", "failed", "canceled"}
            ],
            key=lambda item: int(item.get("updated_at_ms") or 0),
            reverse=True,
        )
        pending_proposals = [
            proposal for proposal in proposals
            if proposal.get("status") in {
                "proposed",
                "approved",
                "stale_needs_revalidation",
            }
        ]
        stale_proposals = [
            proposal for proposal in proposals
            if proposal.get("status") == "stale_needs_revalidation"
        ]
        next_job = queued_jobs[0] if queued_jobs else None
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "project_revision": store.get_revision(),
            "last_updated_ms": data.get("last_updated_ms", 0),
            "has_activity": bool(tasks or proposals or jobs or active_leases),
            "counts": {
                "tasks": len(tasks),
                "queued_tasks": sum(
                    1 for task in tasks if task.get("status") == "queued"
                ),
                "proposals": len(proposals),
                "pending_proposals": len(pending_proposals),
                "stale_proposals": len(stale_proposals),
                "jobs": len(jobs),
                "queued_jobs": len(queued_jobs),
                "running_jobs": sum(
                    1 for job in jobs if job.get("status") == "running"
                ),
                "awaiting_decision_jobs": sum(
                    1 for job in jobs
                    if job.get("status") == "awaiting_decision"
                ),
                "active_leases": len(active_leases),
            },
            "next_queued_job": (
                _compact_orchestration_job(next_job) if next_job else None
            ),
            "active_jobs": [
                _compact_orchestration_job(job)
                for job in active_jobs[:8]
            ],
            "recent_jobs": [
                _compact_orchestration_job(job)
                for job in recent_jobs[:5]
            ],
            "pending_proposals": [
                _compact_orchestration_proposal(proposal)
                for proposal in pending_proposals[:8]
            ],
            "active_leases": [
                _compact_orchestration_lease(lease)
                for lease in active_leases[:8]
            ],
            "warnings": (
                ["stale_proposals_need_revalidation"]
                if stale_proposals else []
            ),
        }
    except Exception as exc:  # noqa: BLE001 - cockpit must degrade.
        return {
            "status": "unavailable",
            "warning": f"orchestration_unavailable: {exc}",
            "has_activity": False,
            "counts": {
                "tasks": 0,
                "queued_tasks": 0,
                "proposals": 0,
                "pending_proposals": 0,
                "stale_proposals": 0,
                "jobs": 0,
                "queued_jobs": 0,
                "running_jobs": 0,
                "awaiting_decision_jobs": 0,
                "active_leases": 0,
            },
            "active_jobs": [],
            "recent_jobs": [],
            "pending_proposals": [],
            "active_leases": [],
            "warnings": [],
        }


def _orchestration_state_for_briefs(ctx: Context, session_info: dict) -> dict:
    try:
        store = _orchestration_service(ctx).store_for_session(session_info)
        return {
            "tasks": store.list_tasks(),
            "jobs": store.list_jobs(ordered=True),
        }
    except Exception:
        return {"tasks": [], "jobs": []}


def _build_context(
    ctx: Context,
    request_text: str = "",
    include_history: bool = False,
) -> dict:
    session_info = _require_session_info(ctx)
    cue_points = _read_cue_points(ctx)
    if cue_points:
        session_info = dict(session_info)
        session_info["cue_points"] = cue_points
    session_info = _attach_section_track_clips(ctx, session_info)
    focus = _focus_service(ctx).get_focus(session_info)
    if include_history:
        focus["history"] = _focus_service(ctx).history(session_info)

    production_context = _production_context_service(ctx).get_state(session_info)
    annotation_store = _annotation_store_for_session(session_info)
    intent_map = build_track_intent_map_data(
        session_info,
        annotation_store.list_annotations(),
    )
    intent_map["project_id"] = annotation_store.project_id
    intent_map["store_path"] = str(annotation_store.path)

    focused_indices = set(focus.get("focus", {}).get("track_indices") or [])
    intent_by_index = {
        item.get("index"): item
        for item in intent_map.get("tracks") or []
        if isinstance(item, dict)
    }
    tracks = []
    for track in _regular_tracks(session_info):
        intent = intent_by_index.get(track["index"]) or {}
        entry = dict(track)
        entry["focused"] = track["index"] in focused_indices
        entry["effective_role"] = intent.get("effective_role")
        entry["inferred_role"] = intent.get("inferred_role")
        entry["priority"] = intent.get("priority")
        entry["decision_state"] = intent.get("decision_state")
        entry["requires_audition"] = intent.get("requires_audition")
        entry["intent"] = intent.get("intent") or {}
        entry["constraints"] = intent.get("constraints") or []
        entry["references"] = intent.get("references") or []
        entry["annotations"] = intent.get("annotations") or []
        tracks.append(entry)

    focused_tracks = [track for track in tracks if track.get("focused")]
    production_state = production_context.get("state") or {}
    track_groups = _build_track_groups(tracks)
    layer_result = _layer_group_service(ctx).list_groups(session_info)
    layer_groups = _build_layer_groups(
        tracks,
        layer_result.get("layer_groups") or [],
    )
    target = _target_context(
        production_state,
        tracks,
        layer_groups,
        beats_per_bar=_beats_per_bar(session_info),
    )
    section_map = _build_section_map(session_info, production_state)
    orchestration = _orchestration_summary(ctx, session_info)
    brief_state = _brief_service(ctx).list_briefs(
        session_info,
        orchestration_state=_orchestration_state_for_briefs(ctx, session_info),
    )
    payload = {
        "status": "ok",
        "version": __version__,
        "project_id": production_context.get("project_id")
        or annotation_store.project_id,
        "backend_tools": _backend_tool_map(),
        "session": {
            "tempo": session_info.get("tempo"),
            "signature_numerator": session_info.get("signature_numerator"),
            "signature_denominator": session_info.get("signature_denominator"),
            "project_identity": session_info.get("project_identity"),
            "song_length": session_info.get("song_length"),
            "track_count": session_info.get("track_count", len(tracks)),
            "is_playing": session_info.get("is_playing"),
            "current_time": session_info.get("current_time"),
            "current_song_time": session_info.get("current_song_time"),
            "arrangement_override": session_info.get("arrangement_override"),
        },
        "focus": focus,
        "focus_panel_url": _focus_panel_url(ctx),
        "cockpit_url": _cockpit_url(ctx),
        "production_context": production_context,
        "track_intent_map": intent_map,
        "track_groups": track_groups,
        "layer_groups": layer_groups,
        "section_map": section_map,
        "capabilities": _cockpit_capabilities(ctx),
        "briefs": brief_state.get("briefs", []),
        "brief_count": brief_state.get("brief_count", 0),
        "codex_last_read_ms": brief_state.get("codex_last_read_ms", 0),
        "orchestration": orchestration,
        "target": target,
        "tracks": tracks,
        "focused_tracks": focused_tracks,
        "target_tracks": [
            track for track in tracks
            if track.get("index") in set(target.get("track_indices") or [])
        ],
        "summary": _summarize_context(
            production_state,
            focused_tracks,
            target,
        ),
    }
    if request_text:
        payload["route"] = classify_request(str(request_text)).to_dict()
    return payload


def _summarize_context(
    state: dict,
    focused_tracks: list[dict],
    target: dict,
) -> dict:
    track_names = [str(track.get("name") or "") for track in focused_tracks]
    return {
        "lane": state.get("lane", "holistic"),
        "workflow_mode": state.get("workflow_mode", "guided"),
        "audition_required": bool(state.get("audition_required", True)),
        "audition_count": int(state.get("audition_count") or 3),
        "audition_scope": state.get("audition_scope", "layer"),
        "target_query": target.get("query", ""),
        "target_mode": target.get("target_mode", "instrument"),
        "target_layer": target.get("target_layer", ""),
        "target_layer_label": target.get("matched_layer_label", ""),
        "target_track_names": target.get("track_names", []),
        "target_track_count": target.get("track_count", 0),
        "section": target.get("section", {}),
        "focused_track_names": track_names,
        "focused_track_count": len(track_names),
        "reference": state.get("reference", ""),
        "protect": state.get("protect", []),
    }


def _task_scope_from_context(context: dict) -> dict:
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    section = target.get("section") if isinstance(target.get("section"), dict) else {}
    scope = {
        "track_indices": target.get("track_indices") or [],
        "target_mode": target.get("target_mode", "instrument"),
        "section": section,
    }
    layer_id = target.get("matched_layer") or target.get("target_layer")
    if layer_id:
        scope["layer_id"] = layer_id
    if section.get("section_id"):
        scope["section_id"] = section.get("section_id")
    elif section.get("scope") and section.get("scope") != "whole_song":
        scope["section_id"] = section.get("scope")
    if section.get("label"):
        scope["section_label"] = section.get("label")
    if section.get("source"):
        scope["section_source"] = section.get("source")
    if section.get("start_beat") is not None:
        scope["section_start_beat"] = section.get("start_beat")
    if section.get("end_beat") is not None:
        scope["section_end_beat"] = section.get("end_beat")
    if section.get("start_bar") is not None:
        scope["section_start_bar"] = section.get("start_bar")
    if section.get("end_bar") is not None:
        scope["section_end_bar"] = section.get("end_bar")
    return scope


def _brief_text_from_payload(payload: dict, context: dict) -> str:
    for key in ("request_text", "brief", "text", "notes"):
        text = str(payload.get(key) or "").strip()
        if text:
            return text
    state = context.get("production_context", {}).get("state", {})
    return str(state.get("notes") or "").strip()


def _brief_context_digest(context: dict) -> dict:
    state = context.get("production_context", {}).get("state", {})
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    target_tracks = [
        track for track in (context.get("target_tracks") or [])
        if isinstance(track, dict)
    ]
    track_refs = [
        {
            "signature": make_track_signature(track),
            "last_seen_index": track.get("index"),
        }
        for track in target_tracks
    ]
    return {
        "target_mode": target.get("target_mode", state.get("target_mode", "")),
        "target_label": (
            target.get("matched_layer_label")
            or target.get("matched_group_label")
            or target.get("query", "")
        ),
        "layer_id": target.get("matched_layer") or target.get("target_layer") or "",
        "track_indices": target.get("track_indices") or [],
        "track_refs": track_refs,
        "section": target.get("section") or state.get("section"),
        "lane": state.get("lane", "holistic"),
        "workflow_mode": state.get("workflow_mode", "guided"),
        "audition_count": int(state.get("audition_count") or 3),
        "audition_scope": state.get("audition_scope", "layer"),
        "protect": state.get("protect", []),
        "reference": state.get("reference", ""),
    }


def _submit_cockpit_brief_packet(
    ctx: Context,
    context: dict,
    request_text: str,
) -> dict:
    """Create orchestration snapshot/task and optional audition job."""
    session_info = _require_session_info(ctx)
    service = _orchestration_service(ctx)
    brief_result = _brief_service(ctx).create_brief(
        session_info,
        request_text=request_text,
        context_digest=_brief_context_digest(context),
        source="cockpit",
    )
    brief = brief_result["brief"]
    brief_id = brief["brief_id"]
    snapshot_result = service.create_snapshot(
        session_info,
        brief=dict(context.get("summary") or {}) | (
            {"text": request_text} if request_text else {}
        ) | {"brief_id": brief_id, "seq": brief.get("seq")},
        session_kernel=_build_session_kernel_for_cockpit(
            ctx,
            request_text=request_text,
            mode=str(
                context.get("production_context", {})
                .get("state", {})
                .get("workflow_mode", "observe")
            ),
        ),
        cockpit_context=context,
        section_map=(context.get("section_map") or {}).get("sections", []),
        layer_groups=context.get("layer_groups") or [],
        track_intent_map=context.get("track_intent_map") or {},
    )
    snapshot = snapshot_result["snapshot"]
    state = context.get("production_context", {}).get("state", {})
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    scope = _task_scope_from_context(context)
    scope["brief_id"] = brief_id
    store = service.store_for_session(session_info)
    task = store.save_task({
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "audition_planner"
        if state.get("workflow_mode") == "audition"
        else "production_conductor",
        "instruction": request_text or "Review the saved cockpit brief.",
        "scope": scope,
        "constraints": {
            "workflow_mode": state.get("workflow_mode", "guided"),
            "lane": state.get("lane", "holistic"),
            "protect": state.get("protect", []),
            "audition_required": bool(state.get("audition_required", True)),
            "audition_count": int(state.get("audition_count") or 3),
            "audition_scope": state.get("audition_scope", "layer"),
            "brief_id": brief_id,
        },
        "status": "queued",
    })

    job = None
    if (
        state.get("workflow_mode") == "audition"
        and (target.get("track_indices") or [])
    ):
        from .orchestration_queue_tools import submit_ableton_job

        job_scope = dict(scope)
        layer_id = target.get("matched_layer") or target.get("target_layer")
        if layer_id:
            job_scope["layer_id"] = layer_id
        job_scope.update({
            "track_indices": target.get("track_indices") or [],
            "audition_count": int(state.get("audition_count") or 3),
            "brief": request_text,
            "brief_id": brief_id,
        })
        job = submit_ableton_job(
            ctx,
            job_type="audition",
            snapshot_id=snapshot["snapshot_id"],
            title="",
            priority=80,
            scope=job_scope,
            submitted_by="cockpit",
        )["job"]

    attached = _brief_service(ctx).attach_artifacts(
        session_info,
        brief_id,
        snapshot_id=snapshot["snapshot_id"],
        task_id=task["task_id"],
        job_ids=[job["job_id"]] if job else [],
    )["brief"]

    return {
        "status": "ok",
        "brief": attached,
        "snapshot": snapshot,
        "task": task,
        "job": job,
    }


def _build_session_kernel_for_cockpit(
    ctx: Context,
    request_text: str,
    mode: str,
) -> dict:
    try:
        from .runtime.tools import get_session_kernel
        lifespan = _lifespan(ctx)
        previous = lifespan.get("_suppress_brief_reader_stamp")
        lifespan["_suppress_brief_reader_stamp"] = True
        try:
            return get_session_kernel(
                ctx,
                request_text=request_text,
                mode=mode or "observe",
            )
        finally:
            if previous is None:
                lifespan.pop("_suppress_brief_reader_stamp", None)
            else:
                lifespan["_suppress_brief_reader_stamp"] = previous

    except Exception as exc:  # noqa: BLE001 - brief packet should degrade.
        return {
            "status": "degraded",
            "warning": f"session_kernel_unavailable: {exc}",
        }


def _send_cockpit_brief(
    ctx: Context,
    payload: dict,
) -> dict:
    """Save a cockpit brief and submit it into the orchestration queue."""
    save_production_context(
        ctx,
        lane=payload.get("lane"),
        workflow_mode=payload.get("workflow_mode"),
        audition_required=payload.get("audition_required"),
        audition_count=payload.get("audition_count"),
        audition_scope=payload.get("audition_scope"),
        protect=payload.get("protect"),
        reference=payload.get("reference"),
        notes=payload.get("notes"),
        target_query=payload.get("target_query"),
        target_group=payload.get("target_group"),
        target_mode=payload.get("target_mode"),
        target_layer=payload.get("target_layer"),
        section=payload.get("section"),
        section_scope=payload.get("section_scope"),
        section_label=payload.get("section_label"),
        section_start_bar=payload.get("section_start_bar"),
        section_end_bar=payload.get("section_end_bar"),
    )
    context = _build_context(ctx, include_history=False)
    request_text = _brief_text_from_payload(payload, context)
    submission = _submit_cockpit_brief_packet(ctx, context, request_text)
    context = _build_context(ctx, include_history=False)
    context["orchestration_submission"] = submission
    return context


def _tool_result(text: str, structured: dict, meta: Optional[dict] = None) -> ToolResult:
    return ToolResult(
        content=text,
        structured_content=structured,
        meta=meta,
    )


def _stamp_reader(ctx: Context, reader: str) -> None:
    try:
        if _lifespan(ctx).get("_suppress_brief_reader_stamp"):
            return
        session_info = _require_session_info(ctx)
        _brief_service(ctx).stamp_reader(session_info, reader)
    except Exception:
        pass


def get_production_context(
    ctx: Context,
    request_text: str = "",
    include_history: bool = False,
) -> dict:
    """Return focused tracks plus current lane, preserve flags, and track intent.

    Use this before acting on phrases like "this track", "the focused tracks",
    "composition lane", "sound design lane", or "mix lane" from the embedded
    LivePilot Production Cockpit.
    """
    _stamp_reader(ctx, "get_production_context")
    return _build_context(
        ctx,
        request_text=request_text,
        include_history=include_history,
    )


def list_cockpit_briefs(
    ctx: Context,
    limit: int = 20,
    status: str = "",
) -> dict:
    """List durable cockpit briefs with derived queue status."""
    _stamp_reader(ctx, "list_cockpit_briefs")
    session_info = _require_session_info(ctx)
    return _brief_service(ctx).list_briefs(
        session_info,
        limit=limit,
        status=status,
        orchestration_state=_orchestration_state_for_briefs(ctx, session_info),
    )


def open_livepilot_production_cockpit(
    ctx: Context,
    request_text: str = "",
) -> ToolResult:
    """Return cockpit context and the outside-browser cockpit URL."""
    data = _build_context(ctx, request_text=request_text, include_history=False)
    url = data.get("cockpit_url") or data.get("focus_panel_url")
    text = (
        f"LivePilot Production Cockpit is available at {url}."
        if url else
        "LivePilot Production Cockpit browser server is not running."
    )
    return _tool_result(text, data)


mcp.tool(
    name="open_livepilot_production_cockpit",
    title="Open LivePilot Production Cockpit",
    description=(
        "Return the outside-browser LivePilot cockpit URL for selecting "
        "focused tracks, workflow lane, preserve flags, and per-track "
        "production intent."
    ),
)(open_livepilot_production_cockpit)

mcp.tool()(get_production_context)
mcp.tool()(list_cockpit_briefs)


def get_cockpit_state(ctx: Context) -> dict:
    """State read used by the browser cockpit UI."""
    return _build_context(ctx, include_history=False)


def set_cockpit_focus(
    ctx: Context,
    track_indices: list[int],
    label: str = "",
) -> dict:
    """Focus write used by the browser cockpit UI."""
    session_info = _require_session_info(ctx)
    indices = _normalize_cockpit_focus_indices(track_indices)
    _focus_service(ctx).set_focus(
        session_info,
        indices,
        label=label,
        source="production_cockpit",
    )
    return _build_context(ctx, include_history=False)


def clear_cockpit_focus(ctx: Context) -> dict:
    """Focus clear used by the browser cockpit UI."""
    session_info = _require_session_info(ctx)
    _focus_service(ctx).clear_focus(session_info)
    return _build_context(ctx, include_history=False)


def save_production_context(
    ctx: Context,
    lane: Optional[str] = None,
    workflow_mode: Optional[str] = None,
    audition_required: Optional[bool] = None,
    audition_count: Optional[int] = None,
    audition_scope: Optional[str] = None,
    protect: Optional[list[str]] = None,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
    target_query: Optional[str] = None,
    target_group: Optional[str] = None,
    target_mode: Optional[str] = None,
    target_layer: Optional[str] = None,
    section: Optional[dict] = None,
    section_scope: Optional[str] = None,
    section_label: Optional[str] = None,
    section_start_bar: Optional[float] = None,
    section_end_bar: Optional[float] = None,
) -> dict:
    """Production context write used by the browser cockpit UI."""
    session_info = _require_session_info(ctx)
    _production_context_service(ctx).save_state(
        session_info,
        lane=lane,
        workflow_mode=workflow_mode,
        audition_required=audition_required,
        audition_count=audition_count,
        audition_scope=audition_scope,
        protect=protect,
        reference=reference,
        notes=notes,
        target_query=target_query,
        target_group=target_group,
        target_mode=target_mode,
        target_layer=target_layer,
        section=section,
        section_scope=section_scope,
        section_label=section_label,
        section_start_bar=section_start_bar,
        section_end_bar=section_end_bar,
    )
    return _build_context(ctx, include_history=False)


def send_cockpit_brief(
    ctx: Context,
    lane: Optional[str] = None,
    workflow_mode: Optional[str] = None,
    audition_required: Optional[bool] = None,
    audition_count: Optional[int] = None,
    audition_scope: Optional[str] = None,
    protect: Optional[list[str]] = None,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
    request_text: Optional[str] = None,
    target_query: Optional[str] = None,
    target_group: Optional[str] = None,
    target_mode: Optional[str] = None,
    target_layer: Optional[str] = None,
    section: Optional[dict] = None,
    section_scope: Optional[str] = None,
    section_label: Optional[str] = None,
    section_start_bar: Optional[float] = None,
    section_end_bar: Optional[float] = None,
) -> dict:
    """Brief submission that creates orchestration work."""
    return _send_cockpit_brief(
        ctx,
        {
            "lane": lane,
            "workflow_mode": workflow_mode,
            "audition_required": audition_required,
            "audition_count": audition_count,
            "audition_scope": audition_scope,
            "protect": protect,
            "reference": reference,
            "notes": notes,
            "request_text": request_text,
            "target_query": target_query,
            "target_group": target_group,
            "target_mode": target_mode,
            "target_layer": target_layer,
            "section": section,
            "section_scope": section_scope,
            "section_label": section_label,
            "section_start_bar": section_start_bar,
            "section_end_bar": section_end_bar,
        },
    )


def save_cockpit_layer_group(
    ctx: Context,
    label: str,
    track_indices: list[int],
    layer_id: str = "",
    status: str = "layered",
    linked_layers: Optional[list[str]] = None,
    notes: str = "",
) -> dict:
    """Create or update a project-scoped musical layer group."""
    session_info = _require_session_info(ctx)
    result = _layer_group_service(ctx).save_group(
        session_info,
        label=label,
        layer_id=layer_id,
        track_indices=track_indices,
        status=status,
        linked_layers=linked_layers,
        notes=notes,
    )
    _orchestration_service(ctx).store_for_session(session_info).increment_revision(
        reason="layer_map_save",
        source_id=str(result.get("layer", {}).get("layer_id") or ""),
        metadata={"label": result.get("layer", {}).get("label")},
    )
    context = _build_context(ctx, include_history=False)
    context["layer_save"] = result
    return context


def delete_cockpit_layer_group(ctx: Context, layer_id: str) -> dict:
    """Delete a project-scoped musical layer group."""
    session_info = _require_session_info(ctx)
    result = _layer_group_service(ctx).delete_group(session_info, layer_id)
    if result.get("deleted"):
        _orchestration_service(ctx).store_for_session(session_info).increment_revision(
            reason="layer_map_delete",
            source_id=str(layer_id or ""),
        )
    context = _build_context(ctx, include_history=False)
    context["layer_delete"] = result
    return context


def submit_cockpit_audition_action(
    ctx: Context,
    source_job_id: str,
    action: str,
    variant_letter: str = "",
) -> dict:
    """Queue a play/promote/discard job for a visible audition variant."""
    from .orchestration_queue_tools import submit_audition_action_job

    result = submit_audition_action_job(
        ctx,
        source_job_id=source_job_id,
        action=action,
        variant_letter=variant_letter,
    )
    context = _build_context(ctx, include_history=False)
    context["audition_action_submission"] = result
    return context


def save_cockpit_track_intent(
    ctx: Context,
    track_index: int,
    role: Optional[str] = None,
    priority: Optional[str] = None,
    notes: Optional[str] = None,
    composition_intent: Optional[str] = None,
    sound_design_intent: Optional[str] = None,
    mix_intent: Optional[str] = None,
    constraints: Optional[list[str]] = None,
    decision_state: Optional[str] = None,
) -> dict:
    """Per-track intent write used by the browser cockpit UI."""
    from .tools.tracks import set_track_annotation as _set_track_annotation_tool

    _set_track_annotation_tool(
        ctx,
        track_index=track_index,
        role=role,
        priority=priority,
        notes=notes,
        composition_intent=composition_intent,
        sound_design_intent=sound_design_intent,
        mix_intent=mix_intent,
        constraints=constraints,
        decision_state=decision_state or "committed",
        source="production_cockpit",
        confidence=1.0,
    )
    return _build_context(ctx, include_history=False)


def _render_cockpit_html(transport: str = "mcp") -> str:
    tools = json.dumps(_backend_tool_map(), sort_keys=True)
    call_tool_js = _cockpit_call_tool_js(transport)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LivePilot Production Cockpit</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #151515;
      --panel: #202124;
      --panel-2: #292b2f;
      --line: #3c4046;
      --text: #f0f1f2;
      --muted: #aeb4ba;
      --accent: #f0a33a;
      --blue: #5da8ff;
      --green: #72bd7a;
      --red: #e06161;
      --input: #111214;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 13px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    button, input, textarea, select {{
      font: inherit;
      color: var(--text);
    }}
    button {{
      border: 1px solid var(--line);
      background: var(--panel-2);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
    }}
    button:hover {{ border-color: var(--accent); }}
    button.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #1a1206;
      font-weight: 650;
    }}
    button.ghost {{
      background: transparent;
    }}
    input, textarea, select {{
      width: 100%;
      background: var(--input);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 8px;
      outline: none;
    }}
    textarea {{ min-height: 72px; resize: vertical; }}
    label {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    header {{
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: center;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #111214;
      position: sticky;
      top: 0;
      z-index: 4;
    }}
    h1 {{
      margin: 0;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .status {{
      color: var(--muted);
      font-size: 12px;
      min-width: 110px;
      text-align: right;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(220px, 30%) minmax(320px, 1fr);
      min-height: calc(100vh - 55px);
    }}
    .tracks {{
      border-right: 1px solid var(--line);
      overflow: auto;
      background: #18191b;
      display: grid;
      grid-template-rows: auto 1fr;
    }}
    .track-filter {{
      display: grid;
      gap: 8px;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: #151619;
    }}
    .group-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }}
    .target-mode-row {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }}
    .target-mode-row button.active {{
      background: #32465f;
      border-color: var(--blue);
    }}
    .group-button {{
      text-align: left;
      min-height: 34px;
      padding: 6px 8px;
    }}
    .group-button.active {{
      border-color: var(--accent);
      background: #302414;
    }}
    .group-button .count {{
      color: var(--muted);
      font-size: 11px;
      float: right;
    }}
    .group-button .layer-status {{
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .track-scroll {{
      overflow: auto;
    }}
    .track {{
      display: grid;
      grid-template-columns: 4px 1fr auto;
      gap: 9px;
      align-items: center;
      min-height: 44px;
      padding: 8px 10px;
      border-bottom: 1px solid #24262a;
      cursor: pointer;
    }}
    .track:hover {{ background: #202227; }}
    .track.selected {{ background: #2b2419; }}
    .track.focused {{ outline: 1px solid var(--accent); outline-offset: -1px; }}
    .swatch {{
      width: 4px;
      height: 28px;
      border-radius: 2px;
      background: var(--blue);
    }}
    .track-name {{
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .track-meta {{
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .badges {{
      display: flex;
      gap: 4px;
      justify-content: flex-end;
      align-items: center;
    }}
    .badge {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 1px 6px;
      color: var(--muted);
      font-size: 10px;
      min-width: 18px;
      text-align: center;
    }}
    .badge.hot {{ color: #17110a; background: var(--accent); border-color: var(--accent); }}
    main {{
      overflow: auto;
      padding: 14px;
      display: grid;
      align-content: start;
      gap: 14px;
    }}
    .band {{
      display: grid;
      gap: 12px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--line);
    }}
    .top-grid {{
      display: grid;
      grid-template-columns: 1fr 150px 130px;
      gap: 10px;
      align-items: end;
    }}
    .lane-row {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
    }}
    .lane-row button {{
      min-height: 34px;
      padding-left: 6px;
      padding-right: 6px;
    }}
    .lane-row button.active {{
      background: #32465f;
      border-color: var(--blue);
    }}
    .checks {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .check {{
      display: flex;
      gap: 7px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 8px;
      color: var(--text);
      text-transform: none;
      font-size: 12px;
    }}
    .check input {{ width: auto; }}
    .brief-grid {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: center;
    }}
    .quick-grid {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }}
    .quick-grid textarea {{
      min-height: 48px;
    }}
    .preset-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .preset-row button {{
      padding: 5px 8px;
      font-size: 12px;
    }}
    .lane-help {{
      color: var(--muted);
      background: #1b1d20;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      min-height: 34px;
    }}
    .scope-grid {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }}
    .section-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .section-row button {{
      padding: 6px 8px;
    }}
    .section-row button.active {{
      background: #32465f;
      border-color: var(--blue);
    }}
    .custom-bars {{
      display: grid;
      grid-template-columns: 88px 88px;
      gap: 6px;
      align-items: end;
    }}
    .audition-board {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .audition-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      display: grid;
      gap: 8px;
      min-height: 150px;
    }}
    .audition-card h3 {{
      margin: 0;
      font-size: 13px;
      letter-spacing: 0;
    }}
    .audition-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }}
    .audition-card button {{
      justify-self: start;
      padding: 5px 8px;
    }}
    .subhead {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    details.advanced {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #1b1d20;
      padding: 8px;
    }}
    details.advanced > summary {{
      cursor: pointer;
      color: var(--muted);
      list-style-position: inside;
    }}
    .advanced-body {{
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }}
    .primary-field {{
      border: 1px solid #4b5e73;
      background: #1c2430;
      border-radius: 6px;
      padding: 10px;
    }}
    .editor-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .wide {{ grid-column: 1 / -1; }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      background: var(--panel);
    }}
    .pill.good {{ color: var(--green); }}
    .pill.warn {{ color: var(--accent); }}
    .actions {{
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }}
    .empty {{
      color: var(--muted);
      padding: 18px 0;
    }}
    @media (max-width: 760px) {{
      header {{ grid-template-columns: 1fr auto; }}
      .status {{ grid-column: 1 / -1; text-align: left; }}
      .layout {{ grid-template-columns: 1fr; }}
      .tracks {{ max-height: 38vh; border-right: 0; border-bottom: 1px solid var(--line); }}
      .top-grid, .editor-grid, .brief-grid, .quick-grid, .scope-grid, .audition-board {{ grid-template-columns: 1fr; }}
      .checks {{ grid-template-columns: 1fr 1fr; }}
      .group-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>LivePilot Production Cockpit</h1>
    <div class="status" id="status">Loading</div>
    <button class="ghost" id="refresh">Refresh</button>
  </header>
  <div class="layout">
    <aside class="tracks">
      <div class="track-filter">
        <label>
          Work target
          <input id="targetQuery" placeholder="guitars, lead vox, rhythm section, intro strings">
        </label>
        <div class="target-mode-row" id="targetModeRow">
          <button data-target-mode="instrument">Instruments</button>
          <button data-target-mode="layer">Layers</button>
        </div>
        <div class="actions" style="justify-content: stretch">
          <button id="applyTarget">Apply Target</button>
          <button id="showAllTracks">Show All</button>
        </div>
        <div class="group-grid" id="groupGrid"></div>
      </div>
      <div class="track-scroll" id="trackList"></div>
    </aside>
    <main>
      <section class="band">
        <div class="brief-grid">
          <div class="summary" id="summary"></div>
          <div class="actions">
            <button id="setFocus">Set Focus</button>
            <button id="clearFocus">Clear Focus</button>
          </div>
        </div>
      </section>

      <section class="band">
        <label>
          Quick brief
          <textarea id="quickBrief" placeholder="e.g. Mix the focused vox. Rawer, less glossy, preserve timing and vocal character."></textarea>
        </label>
        <div class="actions">
          <button id="sendBrief" class="primary">Send Brief to Codex</button>
        </div>
        <div class="preset-row" id="presetRow">
          <button data-preset="mix">Mix selected</button>
          <button data-preset="sound">Sound design selected</button>
          <button data-preset="composition">Composition idea</button>
          <button data-preset="audition">Audition variants</button>
          <button data-preset="preserve_notes">Do not change notes</button>
          <button data-preset="preserve_vocal">Preserve vocal</button>
        </div>
      </section>

      <section class="band">
        <div class="scope-grid">
          <label>
            Section scope
            <div class="section-row" id="sectionRow">
              <button data-section="whole_song" data-label="Whole song">Whole song</button>
              <button data-section="intro" data-label="Intro">Intro</button>
              <button data-section="verse_1" data-label="Verse 1">Verse 1</button>
              <button data-section="verse_2" data-label="Verse 2">Verse 2</button>
              <button data-section="chorus" data-label="Chorus">Chorus</button>
              <button data-section="custom" data-label="Custom">Custom</button>
            </div>
          </label>
          <div class="custom-bars">
            <label>
              Start bar
              <input id="sectionStart" type="number" step="0.25" min="0">
            </label>
            <label>
              End bar
              <input id="sectionEnd" type="number" step="0.25" min="0">
            </label>
          </div>
        </div>
      </section>

      <section class="band">
        <label>
          Lane
          <div class="lane-row" id="laneRow">
            <button data-lane="holistic">Holistic</button>
            <button data-lane="composition">Composition</button>
            <button data-lane="sound_design">Sound</button>
            <button data-lane="mix">Mix</button>
          </div>
        </label>
        <div class="lane-help" id="laneHelp"></div>
        <div class="subhead">Relevant guardrails</div>
        <div class="checks" id="protectFlags"></div>
        <details class="advanced" style="margin-top: 12px">
          <summary>Advanced session context</summary>
          <div class="advanced-body">
            <div class="top-grid">
              <label>
                Mode
                <select id="workflowMode">
                  <option value="observe">Observe</option>
                  <option value="guided">Guided</option>
                  <option value="audition">Audition</option>
                  <option value="commit">Commit</option>
                </select>
              </label>
              <label>
                Audition
                <select id="auditionRequired">
                  <option value="true">Required</option>
                  <option value="false">Optional</option>
                </select>
              </label>
            </div>
            <label>
              Reference
              <input id="reference" placeholder="e.g. The Suburbs: raw ensemble glue">
            </label>
            <label>
              Session notes
              <textarea id="contextNotes"></textarea>
            </label>
            <div class="actions">
              <button id="saveContext">Save Context</button>
            </div>
          </div>
        </details>
      </section>

      <section class="band">
        <div class="subhead">Audition board</div>
        <div class="audition-board" id="auditionBoard"></div>
      </section>

      <section class="band">
        <div id="intentEditor"></div>
      </section>
    </main>
  </div>
  <script>
    const BACKEND_TOOLS = {tools};
    const PROTECT_FLAGS = [
      ["preserve_arrangement", "Arrangement"],
      ["preserve_notes", "Notes"],
      ["preserve_timing", "Timing"],
      ["preserve_sound", "Sound"],
      ["preserve_level", "Level"],
      ["preserve_vocal", "Vocal"],
      ["preserve_groove", "Groove"]
    ];
    const LANE_CONFIG = {{
      holistic: {{
        label: "Holistic",
        help: "Overall song direction, tradeoffs, references, and what should be protected before acting.",
        primaryField: "notes",
        primaryLabel: "Current decision / question",
        protect: ["preserve_arrangement", "preserve_vocal", "preserve_groove"]
      }},
      composition: {{
        label: "Composition",
        help: "Notes, rhythms, harmony, structure, section energy, and arrangement shape.",
        primaryField: "composition_intent",
        primaryLabel: "Composition intent",
        protect: ["preserve_sound", "preserve_level", "preserve_vocal"]
      }},
      sound_design: {{
        label: "Sound",
        help: "Tone, devices, layering, texture, modulation, and emotional character.",
        primaryField: "sound_design_intent",
        primaryLabel: "Sound design intent",
        protect: ["preserve_notes", "preserve_timing", "preserve_vocal"]
      }},
      mix: {{
        label: "Mix",
        help: "Balance, EQ, compression, space, depth, glue, headroom, and foreground/background decisions.",
        primaryField: "mix_intent",
        primaryLabel: "Mix intent",
        protect: ["preserve_timing", "preserve_vocal", "preserve_groove", "preserve_notes"]
      }}
    }};
    const PRESETS = {{
      mix: {{
        lane: "mix",
        workflow_mode: "guided",
        protect: ["preserve_timing", "preserve_vocal"],
        notes: "Mix focused tracks."
      }},
      sound: {{
        lane: "sound_design",
        workflow_mode: "guided",
        protect: ["preserve_notes", "preserve_timing"],
        notes: "Shape the sound of focused tracks."
      }},
      composition: {{
        lane: "composition",
        workflow_mode: "guided",
        protect: ["preserve_sound", "preserve_level"],
        notes: "Work on the musical idea for focused tracks."
      }},
      audition: {{
        workflow_mode: "audition",
        audition_required: true,
        notes: "Audition options before committing."
      }},
      preserve_notes: {{
        protect: ["preserve_notes", "preserve_timing"],
        notes: "Do not change notes or timing."
      }},
      preserve_vocal: {{
        protect: ["preserve_vocal", "preserve_timing"],
        notes: "Preserve the vocal character and timing."
      }}
    }};
    const AUDITION_TEMPLATES = {{
      mix: [
        ["A", "Balance first", "Level and pan the target so it sits with the track before tone changes."],
        ["B", "Add edge", "Try subtle saturation, presence, or transient shape for more character."],
        ["C", "Tuck and glue", "Make it support the song with less foreground pressure and more shared space."]
      ],
      sound_design: [
        ["A", "Rawer character", "Push texture, grit, modulation, or device color while preserving notes."],
        ["B", "Layer for role", "Add or reshape a supporting layer to clarify the target's job."],
        ["C", "Darker space", "Use tone, width, or ambience to change mood without crowding the mix."]
      ],
      composition: [
        ["A", "Simplify", "Remove or thin activity so the part supports the section more clearly."],
        ["B", "Counter-move", "Try a small answering phrase, rhythm shift, or harmonic support idea."],
        ["C", "Section lift", "Change density or register only where the section needs movement."]
      ],
      holistic: [
        ["A", "Clarify role", "Decide whether the target is foreground, support, texture, or archive."],
        ["B", "Reference pass", "Move the target toward the saved reference without overfitting."],
        ["C", "Risky branch", "Try one bolder idea as an audition, with easy rejection."]
      ]
    }};
    let state = null;
    let selected = new Set();
    let activeTrack = null;
    let showAllTracks = false;

    function setStatus(text) {{
      document.getElementById("status").textContent = text;
    }}

    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }}[ch]));
    }}

{call_tool_js}

    async function refresh() {{
      try {{
        setStatus("Refreshing");
        state = await callTool(BACKEND_TOOLS.get_state);
        const focused = (((state || {{}}).focus || {{}}).focus || {{}}).track_indices || [];
        if (selected.size === 0) selected = new Set(focused);
        render();
        setStatus("Ready");
      }} catch (error) {{
        setStatus(error.message || String(error));
      }}
    }}

    function render() {{
      if (!state) return;
      renderContext();
      renderTarget();
      renderSection();
      renderTracks();
      renderSummary();
      renderAuditionBoard();
      renderEditor();
    }}

    function renderContext() {{
      const ctx = (((state || {{}}).production_context || {{}}).state) || {{}};
      const lane = ctx.lane || "holistic";
      document.querySelectorAll("#laneRow button").forEach(button => {{
        button.classList.toggle("active", button.dataset.lane === lane);
      }});
      document.getElementById("workflowMode").value = ctx.workflow_mode || "guided";
      document.getElementById("auditionRequired").value = String(ctx.audition_required !== false);
      document.getElementById("reference").value = ctx.reference || "";
      document.getElementById("contextNotes").value = ctx.notes || "";
      const protect = new Set(ctx.protect || []);
      const laneProtect = new Set((LANE_CONFIG[lane] || LANE_CONFIG.holistic).protect);
      const primary = PROTECT_FLAGS.filter(([value]) => laneProtect.has(value));
      const secondary = PROTECT_FLAGS.filter(([value]) => !laneProtect.has(value));
      document.getElementById("laneHelp").textContent = (LANE_CONFIG[lane] || LANE_CONFIG.holistic).help;
      document.getElementById("protectFlags").innerHTML = [
        ...primary.map(([value, label]) => renderProtectCheck(value, label, protect)),
        `<details class="advanced wide">
          <summary>More guardrails</summary>
          <div class="advanced-body checks">
            ${{secondary.map(([value, label]) => renderProtectCheck(value, label, protect)).join("")}}
          </div>
        </details>`
      ].join("");
    }}

    function renderProtectCheck(value, label, protect) {{
      return `
        <label class="check">
          <input type="checkbox" value="${{value}}" ${{protect.has(value) ? "checked" : ""}}>
          <span>${{label}}</span>
        </label>
      `;
    }}

    function trackColor(track) {{
      const colors = ["#9aa0a6", "#f06d5e", "#f0a33a", "#f4cf58", "#72bd7a", "#54c7c3", "#5da8ff", "#b08cff", "#e07ab6"];
      const raw = Number(track.color_index || 0);
      return colors[Math.abs(raw) % colors.length];
    }}

    function renderTarget() {{
      const ctx = (((state || {{}}).production_context || {{}}).state) || {{}};
      const mode = ctx.target_mode || ((state.target || {{}}).target_mode) || "instrument";
      document.getElementById("targetQuery").value = ctx.target_query || "";
      document.getElementById("targetQuery").placeholder = mode === "layer"
        ? "intro handoff, verse color, low support"
        : "guitars, lead vox, rhythm section, intro strings";
      document.querySelectorAll("#targetModeRow button").forEach(button => {{
        button.classList.toggle("active", button.dataset.targetMode === mode);
      }});
      document.getElementById("showAllTracks").textContent = showAllTracks ? "Use Target" : "Show All";
      const activeGroup = mode === "layer"
        ? ((state.target || {{}}).matched_layer || ctx.target_layer || "")
        : ((state.target || {{}}).matched_group || ctx.target_group || "");
      const groups = mode === "layer" ? (state.layer_groups || []) : (state.track_groups || []);
      document.getElementById("groupGrid").innerHTML = groups.map(group => `
        <button class="group-button ${{group.key === activeGroup ? "active" : ""}}" data-group="${{escapeHtml(group.key)}}" data-label="${{escapeHtml(group.label)}}">
          <span>${{escapeHtml(group.label)}}</span>
          <span class="count">${{group.count}}</span>
          ${{mode === "layer" ? `<span class="layer-status">${{escapeHtml(group.status || "singleton")}}</span>` : ""}}
        </button>
      `).join("");
      document.querySelectorAll("#groupGrid button").forEach(button => {{
        button.addEventListener("click", () => applyTarget(
          button.dataset.label || button.dataset.group || "",
          button.dataset.group || ""
        ));
      }});
    }}

    function renderSection() {{
      const ctx = (((state || {{}}).production_context || {{}}).state) || {{}};
      const scope = ctx.section_scope || "whole_song";
      document.querySelectorAll("#sectionRow button").forEach(button => {{
        button.classList.toggle("active", button.dataset.section === scope);
      }});
      document.getElementById("sectionStart").value = ctx.section_start_bar ?? "";
      document.getElementById("sectionEnd").value = ctx.section_end_bar ?? "";
    }}

    function filteredTracks() {{
      const tracks = state.tracks || [];
      if (showAllTracks) return tracks;
      const targetIndices = new Set(((state.target || {{}}).track_indices) || []);
      if (targetIndices.size > 0) {{
        return tracks.filter(track => targetIndices.has(Number(track.index)));
      }}
      const focused = tracks.filter(track => selected.has(Number(track.index)));
      if (focused.length) return focused;
      return [];
    }}

    function renderTracks() {{
      const allTracks = state.tracks || [];
      const tracks = filteredTracks();
      const list = document.getElementById("trackList");
      if (!allTracks.length) {{
        list.innerHTML = '<div class="empty">No tracks reported by Live.</div>';
        return;
      }}
      if (!tracks.length) {{
        list.innerHTML = '<div class="empty">Pick a target like guitars, vocals, drums, bass, keys, or strings.</div>';
        return;
      }}
      list.innerHTML = tracks.map(track => {{
        const idx = Number(track.index);
        const isSelected = selected.has(idx);
        const isActive = activeTrack === idx;
        const role = track.effective_role || track.inferred_role || "unknown";
        const input = track.has_midi_input ? "MIDI" : track.has_audio_input ? "Audio" : "Track";
        return `
          <div class="track ${{isSelected ? "focused" : ""}} ${{isActive ? "selected" : ""}}" data-index="${{idx}}">
            <div class="swatch" style="background:${{trackColor(track)}}"></div>
            <div>
              <div class="track-name">${{idx + 1}} - ${{escapeHtml(track.name)}}</div>
              <div class="track-meta">${{escapeHtml(track.group_label || "Other")}} - ${{escapeHtml(role)}} - ${{input}}</div>
            </div>
            <div class="badges">
              ${{track.mute ? '<span class="badge">M</span>' : ''}}
              ${{track.solo ? '<span class="badge hot">S</span>' : ''}}
              ${{track.requires_audition ? '<span class="badge hot">A</span>' : ''}}
            </div>
          </div>
        `;
      }}).join("");
      list.querySelectorAll(".track").forEach(row => {{
        row.addEventListener("click", async event => {{
          const idx = Number(row.dataset.index);
          if (event.metaKey || event.ctrlKey || event.shiftKey) {{
            if (selected.has(idx)) selected.delete(idx);
            else selected.add(idx);
          }} else {{
            selected = new Set([idx]);
          }}
          activeTrack = idx;
          render();
          await saveFocus();
        }});
      }});
      if ((activeTrack == null || !tracks.some(track => Number(track.index) === Number(activeTrack))) && tracks.length) {{
        activeTrack = Number(tracks[0].index);
      }}
    }}

    function renderSummary() {{
      const tracks = state.tracks || [];
      const names = tracks.filter(t => selected.has(Number(t.index))).map(t => t.name);
      const ctx = (((state || {{}}).production_context || {{}}).state) || {{}};
      const protect = ctx.protect || [];
      const reference = ctx.reference ? [`<span class="pill">${{escapeHtml(ctx.reference)}}</span>`] : [];
      const target = state.target || {{}};
      const targetPill = target.query ? [`<span class="pill good">target: ${{escapeHtml(target.query)}} (${{target.track_count || 0}})</span>`] : [];
      const modeLabel = target.target_mode === "layer"
        ? `layer: ${{target.matched_layer_label || target.target_layer || "none"}}`
        : `mode: ${{target.target_mode || "instrument"}}`;
      const section = target.section || {{}};
      document.getElementById("summary").innerHTML = [
        `<span class="pill good">${{names.length}} focused</span>`,
        `<span class="pill">${{escapeHtml(modeLabel)}}</span>`,
        ...targetPill,
        `<span class="pill">${{escapeHtml(section.label || "Whole song")}}</span>`,
        `<span class="pill">${{escapeHtml((ctx.lane || "holistic").replace("_", " "))}}</span>`,
        `<span class="pill">${{escapeHtml(ctx.workflow_mode || "guided")}}</span>`,
        `<span class="pill warn">${{ctx.audition_required === false ? "audition optional" : "audition required"}}</span>`,
        ...reference,
        ...protect.map(flag => `<span class="pill">${{escapeHtml(flag.replace("preserve_", ""))}}</span>`),
        ...names.map(name => `<span class="pill">${{escapeHtml(name)}}</span>`)
      ].join("");
    }}

    function renderAuditionBoard() {{
      const lane = selectedLane();
      const templates = AUDITION_TEMPLATES[lane] || AUDITION_TEMPLATES.holistic;
      const target = state.target || {{}};
      const section = (target.section || {{}}).label || "Whole song";
      const targetName = target.query || "selected target";
      document.getElementById("auditionBoard").innerHTML = templates.map(([id, title, body]) => `
        <div class="audition-card">
          <h3>${{id}}: ${{escapeHtml(title)}}</h3>
          <p>${{escapeHtml(body)}}</p>
          <p>${{escapeHtml(targetName)}} / ${{escapeHtml(section)}}</p>
          <button data-audition="${{id}}" data-title="${{escapeHtml(title)}}" data-body="${{escapeHtml(body)}}">Use as brief</button>
        </div>
      `).join("");
      document.querySelectorAll("#auditionBoard button").forEach(button => {{
        button.addEventListener("click", () => useAuditionBrief(
          button.dataset.audition || "",
          button.dataset.title || "",
          button.dataset.body || ""
        ));
      }});
    }}

    function activeTrackData() {{
      const tracks = state.tracks || [];
      if (activeTrack == null && tracks.length) activeTrack = Number(tracks[0].index);
      return tracks.find(track => Number(track.index) === Number(activeTrack));
    }}

    function renderEditor() {{
      const track = activeTrackData();
      const editor = document.getElementById("intentEditor");
      if (!track) {{
        editor.innerHTML = '<div class="empty">Select a track.</div>';
        return;
      }}
      const lane = selectedLane();
      const config = LANE_CONFIG[lane] || LANE_CONFIG.holistic;
      const intent = track.intent || {{}};
      const primaryValue = intent[config.primaryField] || (config.primaryField === "notes" ? intent.notes || "" : "");
      editor.innerHTML = `
        <details class="advanced">
          <summary>Selected track intent</summary>
          <div class="advanced-body editor-grid">
            <label>
              Track
              <input value="${{escapeHtml((Number(track.index) + 1) + " - " + track.name)}}" disabled>
            </label>
            <label>
              Role
              <input id="intentRole" value="${{escapeHtml(track.effective_role || "")}}">
            </label>
            <label>
              Priority
              <select id="intentPriority">
                ${{["undecided", "foreground", "co_foreground", "support", "background", "mute_candidate"].map(value => `
                  <option value="${{value}}" ${{value === (track.priority || "undecided") ? "selected" : ""}}>${{value}}</option>
                `).join("")}}
              </select>
            </label>
            <label class="wide primary-field">
              ${{escapeHtml(config.primaryLabel)}}
              <textarea id="intentPrimary">${{escapeHtml(primaryValue)}}</textarea>
            </label>
            <label class="wide">
              Constraints
              <input id="intentConstraints" value="${{escapeHtml((track.constraints || []).join(", "))}}">
            </label>
            <label class="wide">
              General notes
              <textarea id="intentNotes">${{escapeHtml(intent.notes || "")}}</textarea>
            </label>
            <label>
              Composition
              <textarea id="intentComposition">${{escapeHtml(intent.composition_intent || "")}}</textarea>
            </label>
            <label>
              Sound Design
              <textarea id="intentSound">${{escapeHtml(intent.sound_design_intent || "")}}</textarea>
            </label>
            <label>
              Mix
              <textarea id="intentMix">${{escapeHtml(intent.mix_intent || "")}}</textarea>
            </label>
            <div class="actions wide" style="margin-top: 12px">
              <button id="saveIntent">Save Track Intent</button>
            </div>
          </div>
        </details>
      `;
      document.getElementById("saveIntent").addEventListener("click", saveIntent);
      syncPrimaryIntentField();
    }}

    function selectedLane() {{
      const active = document.querySelector("#laneRow button.active");
      return active ? active.dataset.lane : "holistic";
    }}

    function selectedTargetMode() {{
      const active = document.querySelector("#targetModeRow button.active");
      const mode = active ? active.dataset.targetMode : ((((state || {{}}).production_context || {{}}).state || {{}}).target_mode || "instrument");
      return mode === "layer" || mode === "query" ? mode : "instrument";
    }}

    function selectedSectionButton() {{
      return document.querySelector("#sectionRow button.active");
    }}

    function selectedSectionScope() {{
      const active = selectedSectionButton();
      return active ? active.dataset.section : "whole_song";
    }}

    function selectedSectionLabel() {{
      const active = selectedSectionButton();
      if (active && active.dataset.section !== "custom") return active.dataset.label || "Whole song";
      if (selectedSectionScope() === "custom") {{
        const start = document.getElementById("sectionStart").value;
        const end = document.getElementById("sectionEnd").value;
        if (start || end) return `Bars ${{start || "?"}}-${{end || "?"}}`;
      }}
      return active ? (active.dataset.label || "Whole song") : "Whole song";
    }}

    function selectedTargetGroup() {{
      if (selectedTargetMode() !== "instrument") return "";
      const ctx = (((state || {{}}).production_context || {{}}).state) || {{}};
      return ((state || {{}}).target || {{}}).matched_group || ctx.target_group || "";
    }}

    function selectedTargetLayer() {{
      if (selectedTargetMode() !== "layer") return "";
      const ctx = (((state || {{}}).production_context || {{}}).state) || {{}};
      return ((state || {{}}).target || {{}}).matched_layer || ctx.target_layer || "";
    }}

    function normalizeTargetToken(value) {{
      return String(value || "")
        .trim()
        .toLowerCase()
        .replace(/[-/\\s]+/g, "_")
        .replace(/_+/g, "_");
    }}

    function findTrackGroup(query, groupKey = "", mode = selectedTargetMode()) {{
      const groups = mode === "layer" ? (state.layer_groups || []) : (state.track_groups || []);
      if (groupKey) {{
        const exact = groups.find(group => group.key === groupKey);
        if (exact) return exact;
      }}
      const normalized = normalizeTargetToken(query);
      return groups.find(group =>
        normalizeTargetToken(group.key) === normalized ||
        normalizeTargetToken(group.label) === normalized
      );
    }}

    function selectTargetTracks() {{
      const indices = (((state || {{}}).target || {{}}).track_indices || [])
        .map(value => Number(value))
        .filter(value => Number.isFinite(value));
      selected = new Set(indices);
      activeTrack = indices.length ? indices[0] : null;
      return indices.length;
    }}

    function currentContextState() {{
      state.production_context = state.production_context || {{ state: {{}} }};
      state.production_context.state = state.production_context.state || {{}};
      return state.production_context.state;
    }}

    function updateDraftContext(patch) {{
      const ctx = currentContextState();
      Object.assign(ctx, patch);
      renderContext();
      renderSummary();
      renderEditor();
    }}

    function inferLane(text) {{
      const lower = text.toLowerCase();
      if (/\\b(mix|level|balance|eq|compress|compression|reverb|delay|glue|headroom|pan|stereo)\\b/.test(lower)) return "mix";
      if (/\\b(sound|tone|texture|layer|device|synth|patch|distort|raw|glossy|shimmer|dark|bright)\\b/.test(lower)) return "sound_design";
      if (/\\b(composition|notes|melody|harmony|chord|rhythm|structure|arrange|section|verse|chorus)\\b/.test(lower)) return "composition";
      if (/\\b(holistic|overall|song|vibe|direction|reference)\\b/.test(lower)) return "holistic";
      return selectedLane();
    }}

    function inferProtectFlags(text) {{
      const lower = text.toLowerCase();
      const flags = [];
      if (/preserve|keep|do not|don't|without changing|avoid changing/.test(lower)) {{
        if (/note|melody|harmony|chord/.test(lower)) flags.push("preserve_notes");
        if (/timing|rhythm|groove|feel/.test(lower)) flags.push("preserve_timing");
        if (/vocal|vox|voice/.test(lower)) flags.push("preserve_vocal");
        if (/sound|tone|texture|character/.test(lower)) flags.push("preserve_sound");
        if (/level|volume|balance/.test(lower)) flags.push("preserve_level");
        if (/arrangement|structure|section/.test(lower)) flags.push("preserve_arrangement");
        if (/groove|pocket/.test(lower)) flags.push("preserve_groove");
      }}
      return flags;
    }}

    function appendNote(existing, next) {{
      const first = String(existing || "").trim();
      const second = String(next || "").trim();
      if (!second) return first;
      if (!first) return second;
      if (first.includes(second)) return first;
      return first + "\\n" + second;
    }}

    function mergeProtect(existing, incoming) {{
      const merged = new Set(existing || []);
      (incoming || []).forEach(flag => merged.add(flag));
      return [...merged];
    }}

    async function applyPreset(name) {{
      const preset = PRESETS[name];
      if (!preset) return;
      const ctx = currentContextState();
      updateDraftContext({{
        lane: preset.lane || ctx.lane || selectedLane(),
        workflow_mode: preset.workflow_mode || ctx.workflow_mode || "guided",
        audition_required: preset.audition_required ?? ctx.audition_required ?? true,
        protect: mergeProtect(ctx.protect, preset.protect || []),
        notes: appendNote(ctx.notes, preset.notes || "")
      }});
      await saveContext();
    }}

    async function applyTarget(query, groupKey = "") {{
      const value = String(query || document.getElementById("targetQuery").value || "").trim();
      const mode = selectedTargetMode();
      const group = findTrackGroup(value, groupKey, mode);
      const targetGroup = mode === "instrument" && group ? group.key : "";
      const targetLayer = mode === "layer" && group ? group.key : "";
      document.getElementById("targetQuery").value = value;
      showAllTracks = false;
      selected.clear();
      activeTrack = null;
      const ctx = currentContextState();
      updateDraftContext({{
        target_mode: mode,
        target_query: value,
        target_group: targetGroup,
        target_layer: targetLayer,
        notes: ctx.notes || ""
      }});
      await saveContext({{
        target_mode: mode,
        target_query: value,
        target_group: targetGroup,
        target_layer: targetLayer
      }});
      const count = selectTargetTracks();
      render();
      if (count) {{
        await saveFocus();
      }} else {{
        setStatus("Target saved; no tracks matched");
      }}
    }}

    async function chooseSection(scope, label) {{
      updateDraftContext({{
        section_scope: scope,
        section_label: label || "Whole song"
      }});
      await saveContext();
    }}

    async function useAuditionBrief(id, title, body) {{
      const ctx = currentContextState();
      const target = ((state || {{}}).target || {{}}).query || ctx.target_query || "current target";
      const section = (((state || {{}}).target || {{}}).section || {{}}).label || ctx.section_label || "Whole song";
      const brief = `Audition ${{id}}: ${{title}} on ${{target}} / ${{section}}. ${{body}}`;
      updateDraftContext({{
        workflow_mode: "audition",
        audition_required: true,
        notes: appendNote(ctx.notes, brief)
      }});
      await saveContext();
    }}

    async function applyQuickBrief() {{
      return sendBrief();
    }}

    async function sendBrief() {{
      const text = document.getElementById("quickBrief").value.trim();
      const checkedProtect = [...document.querySelectorAll("#protectFlags input:checked")]
        .map(input => input.value);
      const ctx = currentContextState();
      const lane = text ? inferLane(text) : selectedLane();
      const mode = selectedTargetMode();
      const targetQuery = (
        document.getElementById("targetQuery").value.trim() ||
        ctx.target_query ||
        inferTargetText(text)
      );
      const group = findTrackGroup(
        targetQuery,
        mode === "layer" ? selectedTargetLayer() : selectedTargetGroup(),
        mode
      );
      const targetGroup = mode === "instrument" && group ? group.key : selectedTargetGroup();
      const targetLayer = mode === "layer" && group ? group.key : selectedTargetLayer();
      const protect = mergeProtect(
        mergeProtect(ctx.protect, checkedProtect),
        text ? inferProtectFlags(text) : []
      );
      const notes = appendNote(document.getElementById("contextNotes").value || ctx.notes, text);
      document.getElementById("targetQuery").value = targetQuery;
      updateDraftContext({{
        lane,
        target_mode: mode,
        target_query: targetQuery,
        target_group: targetGroup,
        target_layer: targetLayer,
        protect,
        notes
      }});
      await saveContext({{
        lane,
        target_mode: mode,
        target_query: targetQuery,
        target_group: targetGroup,
        target_layer: targetLayer,
        protect,
        notes
      }});
      if (selected.size === 0) {{
        selectTargetTracks();
        render();
      }}
      if (selected.size > 0) {{
        await saveFocus();
      }}
      document.getElementById("quickBrief").value = "";
      setStatus("Brief sent");
    }}

    function inferTargetText(text) {{
      const lower = text.toLowerCase();
      const candidates = [
        ["guitars", /\\b(guitar|guit|gtr)\\b/],
        ["vocals", /\\b(vocal|vox|voice|harm)\\b/],
        ["drums", /\\b(drum|kick|snare|beat)\\b/],
        ["bass", /\\b(bass|low end|sub)\\b/],
        ["keys", /\\b(keys|piano|organ|chord)\\b/],
        ["strings", /\\b(string|violin|viola|cello|pad)\\b/]
      ];
      for (const [label, pattern] of candidates) {{
        if (pattern.test(lower)) return label;
      }}
      return "";
    }}

    function primaryIntentKey() {{
      const config = LANE_CONFIG[selectedLane()] || LANE_CONFIG.holistic;
      return config.primaryField || "notes";
    }}

    function primaryIntentTargetId() {{
      return {{
        notes: "intentNotes",
        composition_intent: "intentComposition",
        sound_design_intent: "intentSound",
        mix_intent: "intentMix"
      }}[primaryIntentKey()] || "intentNotes";
    }}

    function syncPrimaryIntentField() {{
      const primary = document.getElementById("intentPrimary");
      if (!primary) return;
      primary.addEventListener("input", () => {{
        const target = document.getElementById(primaryIntentTargetId());
        if (target) target.value = primary.value;
      }});
    }}

    function applyPrimaryIntentValue() {{
      const primary = document.getElementById("intentPrimary");
      if (!primary) return;
      const target = document.getElementById(primaryIntentTargetId());
      if (target) target.value = primary.value;
    }}

    async function saveContext(overrides = {{}}) {{
      try {{
        setStatus("Saving");
        const protect = [...document.querySelectorAll("#protectFlags input:checked")].map(input => input.value);
        state = await callTool(BACKEND_TOOLS.save_context, Object.assign({{
          lane: selectedLane(),
          workflow_mode: document.getElementById("workflowMode").value,
          audition_required: document.getElementById("auditionRequired").value === "true",
          protect,
          reference: document.getElementById("reference").value,
          notes: document.getElementById("contextNotes").value,
          target_query: document.getElementById("targetQuery").value,
          target_group: selectedTargetGroup(),
          target_mode: selectedTargetMode(),
          target_layer: selectedTargetLayer(),
          section_scope: selectedSectionScope(),
          section_label: selectedSectionLabel(),
          section_start_bar: document.getElementById("sectionStart").value || null,
          section_end_bar: document.getElementById("sectionEnd").value || null
        }}, overrides));
        render();
        setStatus("Saved");
        return state;
      }} catch (error) {{
        setStatus(error.message || String(error));
        throw error;
      }}
    }}

    async function saveFocus() {{
      try {{
        setStatus("Saving focus");
        state = await callTool(BACKEND_TOOLS.set_focus, {{
          track_indices: [...selected],
          label: [...selected].map(index => Number(index) + 1).join(",")
        }});
        render();
        setStatus("Focus saved");
      }} catch (error) {{
        setStatus(error.message || String(error));
      }}
    }}

    async function clearFocus() {{
      try {{
        setStatus("Clearing");
        selected.clear();
        state = await callTool(BACKEND_TOOLS.clear_focus, {{}});
        render();
        setStatus("Focus cleared");
      }} catch (error) {{
        setStatus(error.message || String(error));
      }}
    }}

    async function saveIntent() {{
      const track = activeTrackData();
      if (!track) return;
      try {{
        setStatus("Saving intent");
        applyPrimaryIntentValue();
        const constraints = document.getElementById("intentConstraints").value
          .split(",")
          .map(value => value.trim())
          .filter(Boolean);
        state = await callTool(BACKEND_TOOLS.save_track_intent, {{
          track_index: Number(track.index),
          role: document.getElementById("intentRole").value,
          priority: document.getElementById("intentPriority").value,
          notes: document.getElementById("intentNotes").value,
          composition_intent: document.getElementById("intentComposition").value,
          sound_design_intent: document.getElementById("intentSound").value,
          mix_intent: document.getElementById("intentMix").value,
          constraints,
          decision_state: "committed"
        }});
        render();
        setStatus("Intent saved");
      }} catch (error) {{
        setStatus(error.message || String(error));
      }}
    }}

    document.getElementById("refresh").addEventListener("click", refresh);
    document.getElementById("saveContext").addEventListener("click", saveContext);
    document.getElementById("setFocus").addEventListener("click", saveFocus);
    document.getElementById("clearFocus").addEventListener("click", clearFocus);
    document.getElementById("sendBrief").addEventListener("click", sendBrief);
    document.getElementById("applyTarget").addEventListener("click", () => applyTarget());
    document.getElementById("targetQuery").addEventListener("keydown", event => {{
      if (event.key === "Enter") applyTarget();
    }});
    document.getElementById("targetModeRow").addEventListener("click", event => {{
      const button = event.target.closest("button[data-target-mode]");
      if (!button) return;
      document.querySelectorAll("#targetModeRow button").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      const mode = selectedTargetMode();
      updateDraftContext({{
        target_mode: mode,
        target_group: mode === "instrument" ? selectedTargetGroup() : "",
        target_layer: mode === "layer" ? selectedTargetLayer() : ""
      }});
      saveContext({{
        target_mode: mode,
        target_group: mode === "instrument" ? selectedTargetGroup() : "",
        target_layer: mode === "layer" ? selectedTargetLayer() : ""
      }});
    }});
    document.getElementById("showAllTracks").addEventListener("click", () => {{
      showAllTracks = !showAllTracks;
      document.getElementById("showAllTracks").textContent = showAllTracks ? "Use Target" : "Show All";
      renderTracks();
    }});
    document.getElementById("presetRow").addEventListener("click", event => {{
      const button = event.target.closest("button[data-preset]");
      if (!button) return;
      applyPreset(button.dataset.preset);
    }});
    document.getElementById("sectionRow").addEventListener("click", event => {{
      const button = event.target.closest("button[data-section]");
      if (!button) return;
      document.querySelectorAll("#sectionRow button").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      chooseSection(button.dataset.section || "whole_song", button.dataset.label || "Whole song");
    }});
    document.getElementById("sectionStart").addEventListener("change", saveContext);
    document.getElementById("sectionEnd").addEventListener("change", saveContext);
    document.getElementById("workflowMode").addEventListener("change", saveContext);
    document.getElementById("auditionRequired").addEventListener("change", saveContext);
    document.getElementById("laneRow").addEventListener("click", event => {{
      const button = event.target.closest("button[data-lane]");
      if (!button) return;
      document.querySelectorAll("#laneRow button").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      saveContext();
    }});

    refresh();
  </script>
</body>
</html>"""


def _render_intent_first_cockpit_html(transport: str = "mcp") -> str:
    tools = json.dumps(_backend_tool_map(), sort_keys=True)
    call_tool_js = _cockpit_call_tool_js(transport)
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LivePilot Intent Cockpit</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f1115;
      --panel: #191c22;
      --panel-2: #20242c;
      --rail: #151820;
      --raise: #252a33;
      --line: #2d3440;
      --line-2: #424b5a;
      --text: #edeff3;
      --muted: #a3aab4;
      --muted-2: #707782;
      --accent: #f0a33a;
      --blue: #67a7e3;
      --green: #68c38f;
      --red: #e06666;
      --input: #11141a;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 18px;
    }
    button, input, textarea, select { font: inherit; color: var(--text); }
    button {
      border: 1px solid var(--line);
      background: var(--raise);
      border-radius: 8px;
      padding: 8px 11px;
      cursor: pointer;
    }
    button:hover { border-color: var(--accent); }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #1a1206;
      font-weight: 700;
    }
    button.soft { background: transparent; }
    input, textarea, select {
      width: 100%;
      background: var(--input);
      border: 1px solid var(--line-2);
      border-radius: 8px;
      padding: 9px 10px;
      outline: none;
    }
    textarea { resize: vertical; }
    input:focus, textarea:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(240, 163, 58, 0.12);
    }
    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .app {
      max-width: 1280px;
      margin: 0 auto;
      display: grid;
      gap: 14px;
    }
    .top {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }
    .mark {
      width: 28px;
      height: 28px;
      border-radius: 8px;
      background: var(--accent);
      color: #1a1206;
      display: grid;
      place-items: center;
      font-weight: 800;
    }
    .brand b { display: block; font-size: 15px; }
    .brand span { color: var(--muted); font-size: 12px; }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      padding: 6px 10px;
      font-size: 12px;
      white-space: nowrap;
    }
    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--green);
    }
    .song-map {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      display: grid;
      gap: 10px;
    }
    .song-map-head {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }
    .song-map-title {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .song-map-title b {
      font-size: 13px;
    }
    .song-map-title span {
      color: var(--muted);
      font-size: 12px;
    }
    .whole-song {
      border-radius: 999px;
      white-space: nowrap;
    }
    .whole-song.active {
      border-color: var(--accent);
      background: #2a2113;
      color: #f5d9aa;
    }
    .live-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    .song-strip {
      display: flex;
      gap: 5px;
      min-height: 54px;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    .section-seg {
      min-width: 86px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--raise);
      padding: 8px;
      text-align: left;
      display: grid;
      align-content: start;
      gap: 2px;
    }
    .section-seg.active {
      border-color: var(--accent);
      background: #2a2113;
      color: #f5d9aa;
    }
    .section-seg.current {
      box-shadow: inset 0 -2px 0 var(--green);
    }
    .section-seg b {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
    }
    .section-seg span {
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
    }
    .grid {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr) 340px;
      gap: 14px;
      align-items: start;
    }
    .card, .rail, .brief {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .card, .brief { padding: 16px; }
    .rail {
      padding: 14px;
      position: sticky;
      top: 18px;
      background: var(--rail);
    }
    .brief {
      position: sticky;
      top: 18px;
    }
    .label {
      color: var(--muted-2);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0;
      margin: 0 0 8px;
    }
    .section { margin-top: 16px; }
    .focus-card {
      border: 1px solid #4a3819;
      background: #211a10;
      border-radius: 8px;
      padding: 12px;
      display: grid;
      gap: 3px;
    }
    .focus-card b { font-size: 14px; }
    .focus-card span { color: var(--muted); font-size: 12px; }
    .track-list {
      display: grid;
      gap: 5px;
      max-height: 48vh;
      overflow: auto;
    }
    .track {
      display: grid;
      grid-template-columns: 4px minmax(0, 1fr) auto;
      gap: 9px;
      align-items: center;
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 8px;
      cursor: pointer;
    }
    .track:hover { background: var(--panel-2); }
    .track.disabled {
      opacity: 0.58;
      cursor: default;
    }
    .track.disabled:hover { background: transparent; }
    .track.selected {
      background: #261f13;
      border-color: #594019;
    }
    .swatch { width: 4px; height: 30px; border-radius: 3px; background: var(--blue); }
    .track-name {
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .track-meta {
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .track-layers {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 4px;
    }
    .badge {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 1px 6px;
      color: var(--muted);
      font-size: 10px;
    }
    .badge.layer {
      border-color: rgba(91, 184, 184, 0.38);
      color: #bfe8e8;
      background: rgba(91, 184, 184, 0.09);
    }
    .target-picker {
      margin-top: 10px;
      display: grid;
      gap: 8px;
    }
    .seg-row, .chip-row, .moves, .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .seg-row button.active,
    .chip.active,
    .opt.on {
      border-color: var(--accent);
      background: #2a2113;
      color: #f5d9aa;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--raise);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      color: #dbe0e7;
      font-size: 12px;
      cursor: pointer;
    }
    .chip small { color: var(--muted); }
    .target-chip-name {
      display: inline-block;
      max-width: 176px;
      overflow: hidden;
      text-overflow: ellipsis;
      vertical-align: bottom;
      white-space: nowrap;
    }
    .sentence {
      min-height: 92px;
      font-size: 17px;
      line-height: 1.48;
    }
    .prompt-line {
      color: var(--muted);
      margin: 0 0 12px;
      font-size: 13px;
    }
    .moves { margin-top: 12px; }
    .move {
      border-radius: 999px;
      font-size: 12px;
      padding: 7px 11px;
    }
    .actions { margin-top: 14px; align-items: center; }
    .count-control {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .audition-count {
      width: auto;
      min-width: 74px;
      padding: 7px 8px;
    }
    .helper { color: var(--muted); font-size: 12px; margin-top: 10px; }
    .drawer {
      margin-top: 14px;
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .drawer-head {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px;
      cursor: pointer;
    }
    .drawer-head span { color: var(--muted); font-size: 12px; }
    .drawer-head b { font-size: 13px; }
    .drawer-head .chev { margin-left: auto; color: var(--muted); }
    .drawer-body {
      display: none;
      padding: 0 12px 14px;
      gap: 14px;
    }
    .drawer.open .drawer-body { display: grid; }
    .drawer.open .chev { transform: rotate(90deg); }
    .opt {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 7px 10px;
      background: var(--raise);
      cursor: pointer;
      color: #dbe0e7;
      font-size: 12px;
    }
    .tog.on { border-color: var(--green); color: #d7f0df; }
    .brief-head {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .brief-head b { font-size: 14px; }
    .brief-head span { margin-left: auto; color: var(--muted); font-size: 11px; }
    .brief-row {
      display: grid;
      grid-template-columns: 18px 1fr;
      gap: 10px;
      align-items: start;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
    }
    .brief-row:last-child { border-bottom: 0; }
    .ic {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: rgba(104, 195, 143, 0.16);
      color: var(--green);
      display: grid;
      place-items: center;
      font-size: 11px;
      font-weight: 800;
    }
    .brief-row.warn .ic {
      background: rgba(240, 163, 58, 0.18);
      color: var(--accent);
    }
    .k {
      color: var(--muted-2);
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0;
    }
    .v { font-weight: 650; margin-top: 1px; }
    .sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
    .plan {
      margin-top: 12px;
      border-top: 1px dashed var(--line-2);
      padding-top: 12px;
      display: grid;
      gap: 8px;
    }
    .plan ul { margin: 0; padding-left: 18px; color: #d8dde5; font-size: 12px; }
    .queue-card {
      border-top: 1px solid var(--border);
      padding-top: 12px;
      display: grid;
      gap: 8px;
    }
    .queue-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      color: #f3f5f8;
      font-size: 13px;
    }
    .queue-badge {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 8px;
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
    }
    .queue-list {
      display: grid;
      gap: 6px;
    }
    .queue-item {
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 8px;
      padding: 8px;
      background: rgba(255, 255, 255, 0.03);
      display: grid;
      gap: 3px;
    }
    .queue-item b {
      color: #e8edf3;
      font-size: 12px;
      line-height: 1.25;
    }
    .queue-item span {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
    }
    .queue-item.stale {
      border-color: rgba(240, 163, 58, 0.5);
      background: rgba(240, 163, 58, 0.08);
    }
    .status {
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }
    .toast {
      position: fixed;
      left: 50%;
      bottom: 22px;
      transform: translateX(-50%) translateY(18px);
      opacity: 0;
      transition: 0.2s;
      pointer-events: none;
      background: #13241c;
      border: 1px solid #2c5a42;
      color: #d7f0df;
      border-radius: 8px;
      padding: 10px 14px;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
      font-size: 13px;
      font-weight: 650;
    }
    .toast.show {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
    @media (max-width: 1020px) {
      body { padding: 12px; }
      .top { grid-template-columns: 1fr; }
      .song-map-head { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .rail, .brief { position: static; }
      .track-list { max-height: none; }
    }
  </style>
</head>
<body>
  <div class="app">
    <div class="top">
      <div class="brand">
        <div class="mark">LP</div>
        <div><b>LivePilot</b><span>Intent Cockpit</span></div>
      </div>
      <div class="pill"><span class="dot"></span><span id="sessionPill">Loading session</span></div>
      <div class="status" id="status">Loading</div>
    </div>

    <div class="song-map" id="songMap">
      <div class="song-map-head">
        <div>
          <div class="label">Song Sections</div>
          <div class="song-map-title"><b id="songMapTitle">Loading sections</b><span id="songMapMeta"></span></div>
        </div>
        <div class="live-actions">
          <button class="whole-song" id="grabLiveSelection">Grab selection from Live</button>
          <button class="whole-song" id="loopSectionLive">Loop section in Live</button>
          <button class="whole-song" id="writeSectionLocator">Write section to Live locator</button>
          <button class="whole-song" id="wholeSongButton">Whole song</button>
        </div>
      </div>
      <div class="song-strip" id="songStrip"></div>
    </div>

    <div class="grid">
      <aside class="rail">
        <div class="label">Target</div>
        <div class="focus-card">
          <b id="focusTitle">No target</b>
          <span id="focusSub">Choose a target or type a brief.</span>
        </div>
        <div class="actions">
          <button class="soft" id="clearTarget">Clear target</button>
          <button class="soft" id="refresh">Refresh</button>
          <button class="soft" id="refreshLive">Refresh from Ableton</button>
        </div>
        <div class="target-picker" id="targetPicker">
          <div class="seg-row" id="targetModeRow">
            <button data-mode="instrument">Auto Groups</button>
            <button data-mode="layer">Song Layers</button>
            <button data-mode="track">Tracks</button>
          </div>
          <input id="targetQuery" placeholder="Search groups, layers, or tracks">
          <div class="chip-row" id="groupChips"></div>
          <div class="actions" id="layerActions">
            <button class="soft" id="saveLayer">Save selection as layer</button>
            <button class="soft" id="deleteLayer">Delete layer</button>
          </div>
        </div>

        <div class="section">
          <div class="label">Tracks</div>
          <div class="track-list" id="trackList"></div>
        </div>

        <div class="section">
          <div class="label">Context</div>
          <div class="sub" id="contextLine">No session context loaded.</div>
        </div>
      </aside>

      <main>
        <div class="card">
          <p class="prompt-line" id="promptLine">Say what should happen to the focused target.</p>
          <textarea id="sentence" class="sentence" spellcheck="false" placeholder="Make the focused part rawer and darker, but keep the notes and timing."></textarea>
          <div class="moves" id="quickMoves"></div>
          <div class="actions">
            <div class="seg-row" id="outputModeRow">
              <button class="opt" data-output="ask">Ask first</button>
              <button class="opt" data-output="auditions">Auditions</button>
              <button class="opt" data-output="apply">Apply</button>
            </div>
            <div class="count-control" id="auditionControl">
              <span>Auditions</span>
              <select id="auditionCount" class="audition-count" aria-label="Audition count">
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3" selected>3</option>
                <option value="4">4</option>
                <option value="5">5</option>
              </select>
            </div>
          </div>
          <div class="helper" id="helperLine">Briefs save to LivePilot context; Codex reads the saved state before acting.</div>
        </div>

        <div class="drawer" id="fineTune">
          <div class="drawer-head" id="fineTuneHead">
            <b>Fine-tune this brief</b><span>scope, lane, guardrails</span><span class="chev">&gt;</span>
          </div>
          <div class="drawer-body">
            <div>
              <div class="label">Focus area</div>
              <div class="seg-row" id="laneRow">
                <button class="opt" data-lane="sound_design">Sound</button>
                <button class="opt" data-lane="mix">Mix</button>
                <button class="opt" data-lane="composition">Composition</button>
                <button class="opt" data-lane="holistic">Holistic</button>
              </div>
            </div>
            <div>
              <div class="label">Keep safe</div>
              <div class="seg-row" id="protectRow">
                <button class="opt tog" data-protect="preserve_notes">Notes</button>
                <button class="opt tog" data-protect="preserve_timing">Timing</button>
                <button class="opt tog" data-protect="preserve_vocal">Vocal</button>
                <button class="opt tog" data-protect="preserve_arrangement">Arrangement</button>
                <button class="opt tog" data-protect="preserve_level">Level</button>
              </div>
            </div>
          </div>
        </div>
      </main>

      <aside class="brief">
        <div class="brief-head"><b>Codex understood</b><span id="briefAge">live</span></div>
        <div class="brief-row"><div class="ic">Y</div><div><div class="k">Target</div><div class="v" id="briefTarget">None</div><div class="sub" id="briefTracks"></div></div></div>
        <div class="brief-row"><div class="ic">Y</div><div><div class="k">Focus</div><div class="v" id="briefLane">Holistic</div></div></div>
        <div class="brief-row"><div class="ic">Y</div><div><div class="k">Direction</div><div class="v" id="briefDirection">Waiting for brief</div></div></div>
        <div class="brief-row"><div class="ic">Y</div><div><div class="k">Scope</div><div class="v" id="briefScope">Whole song</div></div></div>
        <div class="brief-row"><div class="ic">Y</div><div><div class="k">Keep safe</div><div class="v" id="briefProtect">None</div></div></div>
        <div class="brief-row warn" id="outputRow"><div class="ic">!</div><div><div class="k">Output</div><div class="v" id="briefOutput">3 layer auditions</div><div class="sub" id="briefOutputSub">Requires a Song Layer target.</div></div></div>
        <div class="queue-card" id="queueCard">
          <div class="queue-head"><b>Agent Queue</b><span class="queue-badge" id="queueBadge">Idle</span></div>
          <div class="sub" id="queueSummary">No orchestration work queued.</div>
          <div class="queue-list" id="queueItems"></div>
        </div>
        <div class="queue-card" id="briefFeedCard">
          <div class="queue-head"><b>Briefs</b><span class="queue-badge" id="briefBadge">None</span></div>
          <div class="queue-list" id="briefFeed"></div>
        </div>
        <div class="plan" id="plan">
          <div class="k">Codex will</div>
          <ul id="willList"></ul>
          <div class="k">Codex will not</div>
          <ul id="wontList"></ul>
        </div>
        <div class="actions">
          <button class="primary" id="runBrief">Save brief for Codex</button>
        </div>
      </aside>
    </div>
  </div>
  <div id="toast" class="toast">Saved</div>
  <script>
    const BACKEND_TOOLS = __BACKEND_TOOLS__;
    const HTTP_REFRESH_AVAILABLE = __HTTP_REFRESH_AVAILABLE__;
__CALL_TOOL_JS__
    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    const QUICK_MOVES = [
      {label: "Make it rawer", text: "Make the focused part rawer and grittier, but keep the notes and timing.", lane: "sound_design", protect: ["preserve_notes", "preserve_timing"]},
      {label: "Sit behind vocal", text: "Tuck the focused part behind the vocal so it supports instead of fights.", lane: "mix", protect: ["preserve_vocal", "preserve_timing"]},
      {label: "Make it bigger", text: "Make the focused part bigger and wider without crowding the mix.", lane: "mix", protect: ["preserve_notes", "preserve_timing"]},
      {label: "Less glossy", text: "Take the polish off the focused part; make it less glossy and more honest.", lane: "sound_design", protect: ["preserve_notes", "preserve_timing"]},
      {label: "Fix what feels off", text: "Listen in context and fix whatever feels off, keeping the important musical idea intact.", lane: "holistic", protect: []}
    ];
    const OUTPUTS = {
      ask: {label: "Ask before acting", workflow: "guided", audition: true},
      auditions: {label: "Layer auditions", workflow: "audition", audition: true},
      apply: {label: "Apply carefully", workflow: "commit", audition: false}
    };
    const PROTECT_LABELS = {
      preserve_arrangement: "Arrangement",
      preserve_notes: "Notes",
      preserve_timing: "Timing",
      preserve_sound: "Sound",
      preserve_level: "Level",
      preserve_vocal: "Vocal",
      preserve_groove: "Groove"
    };
    let state = null;
    let selected = new Set();
    let outputMode = "auditions";
    let targetModeDraft = "instrument";

    function setStatus(text) {
      $("#status").textContent = text;
    }
    function toast(text) {
      const node = $("#toast");
      node.textContent = text;
      node.classList.add("show");
      clearTimeout(window.__lpToast);
      window.__lpToast = setTimeout(() => node.classList.remove("show"), 2200);
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function ctxState() {
      return (((state || {}).production_context || {}).state) || {};
    }
    function capabilities() {
      return (state || {}).capabilities || {};
    }
    function targetState() {
      return (state || {}).target || {};
    }
    function currentLane() {
      return selectedLane() || ctxState().lane || "holistic";
    }
    function selectedLane() {
      const active = $("#laneRow .on");
      return active ? active.dataset.lane : "";
    }
    function savedSection() {
      const section = ctxState().section;
      return section && typeof section === "object" ? section : null;
    }
    function selectedSectionLabel() {
      const section = savedSection();
      return section ? (section.label || "Section") : "Whole song";
    }
    function liveSection() {
      const section = savedSection();
      if (!section || section.scope === "whole_song" || section.source === "whole_song") return null;
      return section;
    }
    function hasLiveSectionBounds(section = liveSection()) {
      if (!section) return false;
      const start = Number(section.start_beat);
      const end = Number(section.end_beat);
      return Number.isFinite(start) && Number.isFinite(end) && end > start;
    }
    function sectionMapState() {
      return (state || {}).section_map || {};
    }
    function selectedSectionMatches(section) {
      const saved = savedSection();
      if (!saved || !section) return false;
      const savedId = String(saved.section_id || saved.id || "");
      if (savedId && savedId === String(section.id || section.section_id || "")) return true;
      const labelMatches = normalizeToken(saved.label) === normalizeToken(section.label);
      const savedStart = Number(saved.start_beat);
      const sectionStart = Number(section.start_beat);
      const startMatches = Number.isFinite(savedStart) && Number.isFinite(sectionStart) && Math.abs(savedStart - sectionStart) < 0.2;
      return Boolean(labelMatches && startMatches);
    }
    function sectionFlex(section) {
      const duration = Number(section.duration_beats);
      if (!Number.isFinite(duration) || duration <= 0) return 6;
      return Math.max(6, Math.min(duration, 96));
    }
    function sectionBarText(section) {
      return section.bar_label || "";
    }
    function projectId() {
      return (state || {}).project_id || "unknown_project";
    }
    function draftKey() {
      return `livepilot.intent.draft.${projectId()}`;
    }
    function loadDraft() {
      try {
        return window.localStorage.getItem(draftKey()) || "";
      } catch (_error) {
        return "";
      }
    }
    function saveDraft() {
      try {
        window.localStorage.setItem(draftKey(), $("#sentence").value || "");
      } catch (_error) {
        // Ignore localStorage failures; server state remains authoritative.
      }
    }
    function clearDraft() {
      try {
        window.localStorage.removeItem(draftKey());
      } catch (_error) {
        // Ignore localStorage failures.
      }
    }
    function currentProtect() {
      return $$("#protectRow .tog.on").map(node => node.dataset.protect).filter(Boolean);
    }
    function auditionCount() {
      const node = $("#auditionCount");
      const raw = Number((node && node.value) || ctxState().audition_count || 3);
      if (!Number.isFinite(raw)) return 3;
      return Math.max(1, Math.min(8, Math.round(raw)));
    }
    function auditionLabel() {
      const count = auditionCount();
      return `${count} audition${count === 1 ? "" : "s"}`;
    }
    function outputLabel() {
      return outputMode === "auditions" ? auditionLabel() : OUTPUTS[outputMode].label;
    }
    function auditionLayerReady() {
      return targetTracks().length > 0;
    }
    function selectionFromState(payload = state) {
      const targetIndices = (((payload || {}).target || {}).track_indices || []).map(Number);
      if (targetIndices.length) return new Set(targetIndices);
      const focusIndices = ((((payload || {}).focus || {}).focus || {}).track_indices || []).map(Number);
      return new Set(focusIndices);
    }
    function trackByIndex(index) {
      return ((state || {}).tracks || []).find(track => Number(track.index) === Number(index));
    }
    function isMusicalTargetTrack(track) {
      if (!track) return false;
      const constraints = new Set((track.constraints || []).map(item => String(item || "").toLowerCase()));
      const role = String(track.effective_role || track.inferred_role || "").toLowerCase();
      const priority = String(track.priority || "").toLowerCase();
      if (constraints.has("folder_only") || constraints.has("metadata_only") || constraints.has("do_not_target_for_mix_decisions")) return false;
      if (role === "organizational_folder" || role === "utility_map") return false;
      if (priority === "utility") return false;
      return true;
    }
    function targetTracks() {
      const tracks = (state || {}).target_tracks || [];
      if (tracks.length) return tracks;
      const focused = (state || {}).focused_tracks || [];
      if (focused.length) return focused;
      const all = (state || {}).tracks || [];
      return all.filter(track => selected.has(Number(track.index)));
    }
    function hasTarget() {
      const target = targetState();
      const ctx = ctxState();
      return Boolean(
        targetTracks().length ||
        target.query ||
        target.matched_group ||
        target.matched_layer ||
        ctx.target_query ||
        ctx.target_group ||
        ctx.target_layer
      );
    }
    function targetLabel() {
      const target = targetState();
      return target.matched_layer_label || target.matched_group_label || target.query || ctxState().target_query || "No target";
    }
    function pickerMode() {
      if (targetModeDraft === "layer") return "layer";
      if (targetModeDraft === "track") return "track";
      return "instrument";
    }
    function targetMode() {
      return ctxState().target_mode || targetState().target_mode || "instrument";
    }
    function inferLane(text) {
      const lower = String(text || "").toLowerCase();
      if (/\b(mix|level|balance|eq|compress|reverb|delay|glue|headroom|pan|stereo|tuck)\b/.test(lower)) return "mix";
      if (/\b(sound|tone|texture|layer|device|synth|patch|distort|raw|glossy|shimmer|dark|bright|grit)\b/.test(lower)) return "sound_design";
      if (/\b(composition|notes|melody|harmony|chord|rhythm|structure|arrange|section|verse|chorus)\b/.test(lower)) return "composition";
      return currentLane();
    }
    function inferDirection(text) {
      const lower = String(text || "").toLowerCase();
      const found = [];
      if (/raw|grit|dirty|crunch|edge/.test(lower)) found.push("Rawer");
      if (/dark|dreary|sad|lower/.test(lower)) found.push("Darker");
      if (/gloss|polish|smooth|sheen/.test(lower)) found.push("Less glossy");
      if (/big|wide|huge|bigger|wider/.test(lower)) found.push("Bigger");
      if (/vocal|behind|support|tuck/.test(lower)) found.push("Behind vocal");
      if (/pop|forward|front|lead/.test(lower)) found.push("More forward");
      return found.length ? found.join(" - ") : (text ? "Custom brief" : "Waiting for brief");
    }
    function inferProtect(text) {
      const lower = String(text || "").toLowerCase();
      const flags = [];
      if (/note|melody|harmony|chord/.test(lower)) flags.push("preserve_notes");
      if (/timing|rhythm|groove|feel/.test(lower)) flags.push("preserve_timing");
      if (/vocal|vox|voice/.test(lower)) flags.push("preserve_vocal");
      if (/level|volume|balance/.test(lower)) flags.push("preserve_level");
      return flags;
    }
    function appendNote(existing, next) {
      const first = String(existing || "").trim();
      const second = String(next || "").trim();
      if (!second) return first;
      if (!first) return second;
      if (first.includes(second)) return first;
      return first + "\\n" + second;
    }
    function mergeUnique(...lists) {
      const out = new Set();
      lists.flat().filter(Boolean).forEach(item => out.add(item));
      return [...out];
    }
    function normalizeToken(value) {
      return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/_+/g, "_");
    }
    function trackColor(track) {
      const colors = ["#9aa0a6", "#f06d5e", "#f0a33a", "#f4cf58", "#72bd7a", "#54c7c3", "#5da8ff", "#b08cff", "#e07ab6"];
      const raw = Number(track.color_index || 0);
      return colors[Math.abs(raw) % colors.length];
    }
    function trackLayers(track) {
      const idx = Number((track || {}).index);
      return ((state || {}).layer_groups || []).filter(group => {
        const indices = (group.track_indices || []).map(Number);
        return indices.includes(idx);
      });
    }
    function trackLayerChips(track) {
      const layers = trackLayers(track);
      if (!layers.length) return "";
      return `
        <div class="track-layers">
          ${layers.slice(0, 4).map(layer => `<span class="badge layer">${escapeHtml(layer.label || layer.key || "Layer")}</span>`).join("")}
          ${layers.length > 4 ? `<span class="badge">+${layers.length - 4}</span>` : ""}
        </div>
      `;
    }

    async function refresh() {
      try {
        setStatus("Refreshing");
        state = await callTool(BACKEND_TOOLS.get_state);
        selected = selectionFromState();
        targetModeDraft = targetMode() === "layer" ? "layer" : targetMode() === "query" ? "track" : "instrument";
        syncControlsFromState();
        render();
        setStatus("Ready");
      } catch (error) {
        setStatus(error.message || String(error));
      }
    }
    async function refreshLive() {
      if (!HTTP_REFRESH_AVAILABLE) {
        setStatus("Live refresh is only available in the browser cockpit.");
        return;
      }
      try {
        setStatus("Refreshing from Ableton");
        const response = await fetch("/api/cockpit/refresh-live", { method: "POST" });
        const body = await response.json();
        if (!response.ok || body.status === "error") {
          throw new Error(body.hint || body.error || `Request failed: ${response.status}`);
        }
        state = body;
        selected = selectionFromState(body);
        syncControlsFromState();
        render();
        setStatus("Ready");
        toast("Live snapshot refreshed");
      } catch (error) {
        setStatus(error.message || String(error));
        toast("Snapshot not refreshed");
      }
    }

    function syncControlsFromState() {
      const ctx = ctxState();
      const sentence = $("#sentence");
      if (!sentence.value) sentence.value = loadDraft();
      outputMode = ctx.workflow_mode === "commit" ? "apply" : ctx.workflow_mode === "guided" ? "ask" : "auditions";
      const savedMode = ctx.target_mode || targetMode();
      targetModeDraft = savedMode === "layer" ? "layer" : savedMode === "query" ? "track" : "instrument";
      $("#auditionCount").value = String(Math.max(1, Math.min(5, Number(ctx.audition_count || 3))));
      $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === (ctx.lane || "holistic")));
      $$("#outputModeRow .opt").forEach(node => node.classList.toggle("on", node.dataset.output === outputMode));
      const protect = new Set(ctx.protect || []);
      $$("#protectRow .tog").forEach(node => node.classList.toggle("on", protect.has(node.dataset.protect)));
      $("#targetQuery").value = ctx.target_query || targetState().query || "";
    }

    function render() {
      renderTop();
      renderSectionMap();
      renderFocus();
      renderPicker();
      renderTracks();
      renderQuickMoves();
      renderBrief();
      renderOrchestration();
      renderBriefFeed();
    }
    function renderTop() {
      const session = (state || {}).session || {};
      const tempo = session.tempo ? Math.round(Number(session.tempo)) + " BPM" : "tempo unknown";
      const count = session.track_count || ((state || {}).tracks || []).length || 0;
      const source = sessionSourceLabel();
      const project = compactId(projectId());
      const codex = Number((state || {}).codex_last_read_ms || 0);
      const codexText = codex ? `Codex ${formatAge(Date.now() - codex)}` : "Codex never";
      $("#sessionPill").textContent = `${tempo} - ${count} tracks - ${project}${source ? " - " + source : ""} - ${codexText}`;
      $("#refreshLive").style.display = HTTP_REFRESH_AVAILABLE ? "" : "none";
    }
    function sessionSourceLabel() {
      const source = (state || {}).session_source || "";
      const snapshotSource = (state || {}).session_snapshot_source || "";
      const updated = Number((state || {}).session_updated_at_ms || 0);
      const age = updated ? Math.max(0, Date.now() - updated) : 0;
      const ageText = updated ? formatAge(age) : "";
      if (source === "live" || source === "live_probe") return "live";
      if (source === "snapshot") {
        return `snapshot${snapshotSource ? ":" + snapshotSource : ""}${ageText ? " " + ageText : ""}`;
      }
      return "";
    }
    function formatAge(ms) {
      const seconds = Math.round(ms / 1000);
      if (seconds < 60) return `${seconds}s old`;
      const minutes = Math.round(seconds / 60);
      if (minutes < 60) return `${minutes}m old`;
      const hours = Math.round(minutes / 60);
      return `${hours}h old`;
    }
    function renderSectionMap() {
      const map = sectionMapState();
      const sections = Array.isArray(map.sections) ? map.sections : [];
      const source = map.source_label || "Manual scope";
      const caps = capabilities();
      const section = liveSection();
      $("#songMapTitle").textContent = source;
      $("#songMapMeta").textContent = sections.length
        ? `${sections.length} section${sections.length === 1 ? "" : "s"}`
        : "";
      $("#wholeSongButton").classList.toggle("active", !savedSection());
      $("#grabLiveSelection").disabled = !caps.live_pointing;
      $("#loopSectionLive").disabled = !caps.transport_ops || !hasLiveSectionBounds(section);
      $("#writeSectionLocator").disabled = !caps.locator_write || !section || !Number.isFinite(Number(section.start_beat));
      $("#grabLiveSelection").title = caps.live_pointing ? "Use the selected track from Ableton" : "Unavailable in snapshot mode";
      $("#loopSectionLive").title = caps.transport_ops ? "Set Live loop brace and play this section" : "Unavailable in snapshot mode";
      $("#writeSectionLocator").title = caps.locator_write ? "Create or rename a Live locator at this section start" : "Unavailable in snapshot mode";
      if (!sections.length) {
        $("#songStrip").innerHTML = '<button class="section-seg active" data-whole-song="1"><b>Whole song</b><span></span></button>';
      } else {
        $("#songStrip").innerHTML = sections.map(section => {
          const selectedSection = selectedSectionMatches(section);
          const currentSection = section.is_current || section.id === map.current_section_id;
          return `
            <button class="section-seg ${selectedSection ? "active" : ""} ${currentSection ? "current" : ""}" data-section-id="${escapeHtml(section.id || "")}" style="flex: ${sectionFlex(section)} 1 90px">
              <b title="${escapeHtml(section.label || "Section")}">${escapeHtml(section.label || "Section")}</b>
              <span>${escapeHtml(sectionBarText(section))}</span>
            </button>
          `;
        }).join("");
      }
      $$("#songStrip .section-seg").forEach(node => node.addEventListener("click", () => {
        if (node.dataset.wholeSong) chooseWholeSong();
        else chooseSection(node.dataset.sectionId || "");
      }));
    }
    function renderFocus() {
      const tracks = targetTracks();
      const target = targetState();
      const label = targetLabel();
      $("#focusTitle").textContent = tracks.length ? `${label} - ${tracks.length} track${tracks.length === 1 ? "" : "s"}` : label;
      $("#focusSub").textContent = ((target.section || {}).label || selectedSectionLabel());
      $("#clearTarget").disabled = !hasTarget();
      $("#contextLine").textContent = [
        `Target: ${hasTarget() ? (targetMode() === "layer" ? "song layer" : targetMode() === "query" ? "track/search" : "auto group") : "none"}`,
        `Lane: ${currentLane().replace("_", " ")}`,
        `Output: ${outputLabel()}`
      ].join(" / ");
    }
    function renderPicker() {
      $$("#targetModeRow button").forEach(node => node.classList.toggle("active", node.dataset.mode === pickerMode()));
      const mode = pickerMode();
      if (mode === "track") {
        const activeTracks = targetTracks();
        const activeTrackKey = activeTracks.length === 1 && targetMode() === "query"
          ? String(activeTracks[0].index)
          : "";
        const tracks = ((state || {}).tracks || []).filter(isMusicalTargetTrack);
        if (!tracks.length) {
          $("#groupChips").innerHTML = '<span class="sub">No musical tracks found.</span>';
          renderLayerActions();
          return;
        }
        $("#groupChips").innerHTML = tracks.map(track => {
          const idx = Number(track.index);
          const label = `${idx + 1} ${track.name || "Track"}`;
          return `
            <button class="chip ${String(idx) === activeTrackKey ? "active" : ""}" data-track-index="${idx}" title="${escapeHtml(label)}">
              <span class="target-chip-name">${escapeHtml(label)}</span>
            </button>
          `;
        }).join("");
        $$("#groupChips .chip").forEach(node => node.addEventListener("click", () => {
          if (node.classList.contains("active")) clearTarget();
          else selectTrackTarget(Number(node.dataset.trackIndex));
        }));
        renderLayerActions();
        return;
      }
      const groups = mode === "layer" ? ((state || {}).layer_groups || []) : ((state || {}).track_groups || []);
      const activeKey = mode === "layer" ? targetState().matched_layer : targetState().matched_group;
      if (!groups.length) {
        $("#groupChips").innerHTML = mode === "layer"
          ? '<span class="sub">No layers yet - choose Tracks or Auto Groups, then save the target as a layer.</span>'
          : '<span class="sub">No auto groups found.</span>';
        renderLayerActions();
        return;
      }
      $("#groupChips").innerHTML = groups.map(group => `
        <button class="chip ${group.key === activeKey ? "active" : ""}" data-key="${escapeHtml(group.key)}" data-label="${escapeHtml(group.label)}">
          ${escapeHtml(group.label)}
          ${mode === "layer" ? `<small>${escapeHtml(group.status || "layered")}</small>` : ""}
          <small>${group.count}</small>
        </button>
      `).join("");
      $$("#groupChips .chip").forEach(node => node.addEventListener("click", () => {
        if (node.classList.contains("active")) clearTarget();
        else chooseTarget(node.dataset.label, node.dataset.key);
      }));
      renderLayerActions();
    }
    function renderLayerActions() {
      const actions = $("#layerActions");
      if (!actions) return;
      const mode = pickerMode();
      const target = targetState();
      const ctx = ctxState();
      const hasTracks = targetTracks().length > 0 || selected.size > 0;
      const layerId = target.matched_layer || ctx.target_layer || "";
      const canDelete = mode === "layer" && Boolean(layerId);
      actions.style.display = mode === "layer" || hasTracks ? "flex" : "none";
      $("#saveLayer").disabled = !hasTracks;
      $("#deleteLayer").disabled = !canDelete;
    }
    function renderTracks() {
      const targeted = targetTracks();
      const showingAll = !targeted.length;
      const tracks = showingAll ? ((state || {}).tracks || []) : targeted;
      if (!tracks.length) {
        $("#trackList").innerHTML = '<div class="sub">No tracks loaded yet.</div>';
        return;
      }
      const intro = showingAll
        ? '<div class="sub">Showing all tracks until a target is chosen.</div>'
        : "";
      $("#trackList").innerHTML = intro + tracks.map(track => {
        const idx = Number(track.index);
        const role = track.effective_role || track.inferred_role || track.group_label || "track";
        const kind = track.has_midi_input ? "MIDI" : track.has_audio_input ? "Audio" : "Track";
        const musical = isMusicalTargetTrack(track);
        return `
          <div class="track ${selected.has(idx) || track.focused ? "selected" : ""} ${musical ? "" : "disabled"}" data-index="${idx}" data-musical="${musical ? "1" : "0"}">
            <div class="swatch" style="background:${trackColor(track)}"></div>
            <div>
              <div class="track-name">${idx + 1} - ${escapeHtml(track.name)}</div>
              <div class="track-meta">${escapeHtml(role)} - ${kind}</div>
              ${trackLayerChips(track)}
            </div>
            <div>${track.mute ? '<span class="badge">M</span>' : ''}${track.solo ? '<span class="badge">S</span>' : ''}</div>
          </div>
        `;
      }).join("");
      $$("#trackList .track").forEach(node => node.addEventListener("click", () => selectTrackTarget(Number(node.dataset.index))));
    }
    function renderQuickMoves() {
      $("#quickMoves").innerHTML = QUICK_MOVES.map(move => `<button class="move" data-label="${escapeHtml(move.label)}">${escapeHtml(move.label)}</button>`).join("");
      $$("#quickMoves .move").forEach((node, index) => node.addEventListener("click", () => applyQuickMove(QUICK_MOVES[index])));
    }
    function renderBrief() {
      const text = $("#sentence").value.trim();
      const target = targetState();
      const tracks = targetTracks();
      const protect = currentProtect();
      const lane = text ? inferLane(text) : currentLane();
      $("#briefTarget").textContent = targetLabel();
      $("#briefTracks").textContent = tracks.map(track => `${Number(track.index) + 1} ${track.name}`).slice(0, 5).join(" / ");
      $("#briefLane").textContent = lane.replace("_", " ");
      $("#briefDirection").textContent = inferDirection(text);
      $("#briefScope").textContent = ((target.section || {}).label || selectedSectionLabel());
      $("#briefProtect").textContent = protect.length ? protect.map(flag => PROTECT_LABELS[flag] || flag).join(" / ") : "None";
      $("#briefOutput").textContent = outputLabel();
      $("#briefOutputSub").textContent = outputMode === "auditions"
        ? (auditionLayerReady() ? "Codex will create visible muted audition lanes." : "Choose a layer or track target before saving auditions.")
        : "Output mode selected in the brief controls.";
      $$("#outputModeRow .opt").forEach(node => node.classList.toggle("on", node.dataset.output === outputMode));
      $("#outputRow").classList.toggle("warn", outputMode !== "apply");
      $("#runBrief").textContent = outputMode === "apply"
        ? "Save apply brief for Codex"
        : outputMode === "auditions"
          ? `Save ${auditionLabel()} for Codex`
          : "Save brief for Codex";
      $("#runBrief").disabled = outputMode === "auditions" && !auditionLayerReady();
      $("#auditionCount").disabled = outputMode !== "auditions";
      $("#auditionControl").style.display = outputMode === "auditions" ? "inline-flex" : "none";
      $("#helperLine").textContent = outputMode === "auditions" && !auditionLayerReady()
        ? "Choose a Song Layer or Track target before saving audition variants."
        : "Briefs save to LivePilot context; Codex reads the saved state before acting.";
      $("#willList").innerHTML = planWill(text, tracks).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      $("#wontList").innerHTML = planWont(protect).map(item => `<li>${escapeHtml(item)}</li>`).join("");
    }
    function orchestrationState() {
      return (state || {}).orchestration || {};
    }
    function compactId(value) {
      const text = String(value || "");
      return text.length > 10 ? text.slice(0, 10) : text;
    }
    function renderOrchestration() {
      const orchestration = orchestrationState();
      const counts = orchestration.counts || {};
      const badge = $("#queueBadge");
      const summary = $("#queueSummary");
      const items = $("#queueItems");
      if (!badge || !summary || !items) return;
      if (orchestration.status && orchestration.status !== "ok") {
        badge.textContent = "Unavailable";
        summary.textContent = orchestration.warning || "Orchestration state is not available.";
        items.innerHTML = "";
        return;
      }
      const queued = Number(counts.queued_jobs || 0);
      const running = Number(counts.running_jobs || 0);
      const decisions = Number(counts.awaiting_decision_jobs || 0);
      const proposals = Number(counts.pending_proposals || 0);
      const stale = Number(counts.stale_proposals || 0);
      const leases = Number(counts.active_leases || 0);
      badge.textContent = queued || running || decisions
        ? `${queued} queued / ${running + decisions} active`
        : "Idle";
      if (!orchestration.has_activity) {
        summary.textContent = "No queued jobs or pending proposals for this project.";
        items.innerHTML = "";
        return;
      }
      summary.textContent = [
        `${queued} queued job${queued === 1 ? "" : "s"}`,
        `${proposals} pending proposal${proposals === 1 ? "" : "s"}`,
        stale ? `${stale} stale` : "",
        leases ? `${leases} lease${leases === 1 ? "" : "s"}` : ""
      ].filter(Boolean).join(" - ");
      const rows = [];
      (orchestration.active_jobs || []).slice(0, 4).forEach(job => {
        const title = job.title || job.job_type || "Ableton job";
        rows.push(`
          <div class="queue-item">
            <b>${escapeHtml(title)}</b>
            <span>${escapeHtml(job.status || "queued")} - ${escapeHtml(job.job_type || "job")} ${compactId(job.job_id) ? "#" + escapeHtml(compactId(job.job_id)) : ""}</span>
          </div>
        `);
      });
      (orchestration.pending_proposals || []).slice(0, 3).forEach(proposal => {
        const staleClass = proposal.status === "stale_needs_revalidation" ? " stale" : "";
        rows.push(`
          <div class="queue-item${staleClass}">
            <b>${escapeHtml(proposal.summary || proposal.agent_role || "Agent proposal")}</b>
            <span>${escapeHtml(proposal.status || "proposed")} - ${escapeHtml(proposal.agent_role || "agent")} ${compactId(proposal.proposal_id) ? "#" + escapeHtml(compactId(proposal.proposal_id)) : ""}</span>
          </div>
        `);
      });
      if (!rows.length) {
        rows.push('<div class="queue-item"><b>No active queue items</b><span>Recent completed jobs are stored in the project queue.</span></div>');
      }
      items.innerHTML = rows.join("");
    }
    function renderBriefFeed() {
      const briefs = Array.isArray((state || {}).briefs) ? state.briefs : [];
      const badge = $("#briefBadge");
      const feed = $("#briefFeed");
      if (!badge || !feed) return;
      badge.textContent = briefs.length ? `${briefs.length} saved` : "None";
      if (!briefs.length) {
        feed.innerHTML = '<div class="queue-item"><b>No briefs yet</b><span>Save a brief and tell Codex to pick it up.</span></div>';
        return;
      }
      feed.innerHTML = briefs.slice(0, 6).map(brief => {
        const trail = (brief.status_trail || [brief.status || "saved"]).join(" -> ");
        const text = brief.request_text || "Untitled brief";
        const jobs = brief.related_jobs || [];
        const plan = jobs.flatMap(job => job.plan || []).slice(0, 3);
        const variants = jobs.flatMap(job => {
          const manifest = job.audition_manifest || {};
          return (manifest.variants || []).map(variant => ({
            source_job_id: job.job_id,
            letter: variant.letter || "",
            label: variant.label || "",
          }));
        }).slice(0, 8);
        const planText = plan.length
          ? plan.map(step => step.summary || step.tool || "step").join(" / ")
          : `${brief.related_task_count || 0} task${brief.related_task_count === 1 ? "" : "s"} / ${brief.related_job_count || 0} job${brief.related_job_count === 1 ? "" : "s"}`;
        return `
          <div class="queue-item">
            <b>${escapeHtml(text)}</b>
            <span>${escapeHtml(trail)} - #${escapeHtml(String(brief.seq || ""))}</span>
            <span>${escapeHtml(planText)}</span>
            ${variants.length ? `<span>${variants.map(variant => `
              ${escapeHtml(variant.letter)} ${escapeHtml(variant.label)}
              <button class="soft audition-action" data-action="play" data-job-id="${escapeHtml(variant.source_job_id)}" data-variant="${escapeHtml(variant.letter)}">Play</button>
              <button class="soft audition-action" data-action="promote" data-job-id="${escapeHtml(variant.source_job_id)}" data-variant="${escapeHtml(variant.letter)}">Promote</button>
              <button class="soft audition-action" data-action="discard" data-job-id="${escapeHtml(variant.source_job_id)}" data-variant="${escapeHtml(variant.letter)}">Discard</button>
            `).join(" ")}</span>` : ""}
          </div>
        `;
      }).join("");
    }
    function planWill(text, tracks) {
      const direction = inferDirection(text).toLowerCase();
      const count = tracks.length || targetState().track_count || 0;
      const items = [`Use ${count || "the focused"} target track${count === 1 ? "" : "s"} as context`];
      if (outputMode === "auditions") items.push(`Create ${auditionLabel()} as visible muted Arrangement lanes`);
      if (outputMode === "apply") items.push("Apply one careful pass to the selected target");
      if (direction && direction !== "waiting for brief") items.push(`Aim for: ${direction}`);
      return items.slice(0, 3);
    }
    function planWont(protect) {
      const items = [];
      if (protect.includes("preserve_notes")) items.push("Change notes or harmony");
      if (protect.includes("preserve_timing")) items.push("Change timing or groove");
      if (protect.includes("preserve_vocal")) items.push("Touch the vocal unless it is targeted");
      if (protect.includes("preserve_arrangement")) items.push("Change arrangement structure");
      if (!items.length) items.push("Overwrite originals without an explicit commit decision");
      return items.slice(0, 4);
    }

    async function chooseTarget(label, key) {
      const mode = pickerMode();
      const payload = {
        target_mode: mode,
        target_query: label || key || "",
        target_group: mode === "instrument" ? key || "" : "",
        target_layer: mode === "layer" ? key || "" : ""
      };
      state = await callTool(BACKEND_TOOLS.save_context, payload);
      selected = selectionFromState();
      render();
      await saveFocus(label || key || "target");
      toast("Target saved");
    }
    async function chooseWholeSong() {
      state = await callTool(BACKEND_TOOLS.save_context, {
        section_scope: "whole_song"
      });
      syncControlsFromState();
      render();
      toast("Whole song scoped");
    }
    async function chooseSection(sectionId) {
      const section = (sectionMapState().sections || []).find(item => String(item.id || "") === String(sectionId || ""));
      if (!section) return;
      const payload = {
        section: {
          section_id: section.id || section.section_id || "",
          label: section.label || "Section",
          start_beat: Number.isFinite(Number(section.start_beat)) ? Number(section.start_beat) : null,
          end_beat: Number.isFinite(Number(section.end_beat)) ? Number(section.end_beat) : null,
          source: section.source || "manual"
        }
      };
      state = await callTool(BACKEND_TOOLS.save_context, payload);
      syncControlsFromState();
      render();
      toast("Section scoped");
    }
    async function chooseFreeQuery(query) {
      const label = query || "target";
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "query",
        target_query: label,
        target_group: "",
        target_layer: ""
      });
      selected = selectionFromState();
      await saveFocus(label);
      toast("Target saved");
    }
    async function saveCurrentLayer() {
      const tracks = targetTracks();
      const indices = tracks.length
        ? tracks.map(track => Number(track.index))
        : [...selected].map(Number);
      if (!indices.length) {
        toast("Choose tracks first");
        return;
      }
      const currentLayer = targetState().matched_layer || ctxState().target_layer || "";
      const defaultLabel = targetLabel() && targetLabel() !== "No target"
        ? targetLabel()
        : "New Layer";
      const label = window.prompt("Layer name", defaultLabel);
      if (!label) return;
      state = await callTool(BACKEND_TOOLS.save_layer, {
        label,
        layer_id: pickerMode() === "layer" ? currentLayer : "",
        track_indices: indices,
        status: indices.length > 1 ? "layered" : "singleton"
      });
      const savedLayer = (((state || {}).layer_save || {}).layer || {});
      const layerId = savedLayer.layer_id || savedLayer.key || normalizeToken(label);
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "layer",
        target_query: savedLayer.label || label,
        target_group: "",
        target_layer: layerId
      });
      targetModeDraft = "layer";
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Layer saved");
    }
    async function deleteCurrentLayer() {
      const layerId = targetState().matched_layer || ctxState().target_layer || "";
      if (!layerId) return;
      if (!window.confirm(`Delete layer "${targetLabel()}"?`)) return;
      state = await callTool(BACKEND_TOOLS.delete_layer, {layer_id: layerId});
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "instrument",
        target_query: "",
        target_group: "",
        target_layer: ""
      });
      targetModeDraft = "layer";
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Layer deleted");
    }
    async function submitAuditionAction(action, sourceJobId, variantLetter) {
      if (!sourceJobId || !action) return;
      state = await callTool(BACKEND_TOOLS.audition_action, {
        source_job_id: sourceJobId,
        action,
        variant_letter: variantLetter || ""
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast(`Queued audition ${action}`);
    }
    async function grabLiveSelection() {
      if (!capabilities().live_pointing) {
        toast("Live pointing unavailable in snapshot mode");
        return;
      }
      const result = await callTool(BACKEND_TOOLS.get_live_selection);
      const selection = result.selection || result || {};
      const index = Number(selection.track_index);
      if (!Number.isInteger(index) || index < 0) {
        setStatus("Select a regular track in Ableton first.");
        toast("No regular Live track selected");
        return;
      }
      await selectTrackTarget(index);
      toast("Grabbed Live selection");
    }
    async function loopSelectedSectionLive() {
      const section = liveSection();
      if (!capabilities().transport_ops) {
        toast("Live transport unavailable in snapshot mode");
        return;
      }
      if (!hasLiveSectionBounds(section)) {
        toast("Choose a bounded section first");
        return;
      }
      state = await callTool(BACKEND_TOOLS.loop_live_section, {
        section,
        play: true
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Looped section in Live");
    }
    async function writeSelectedSectionLocator() {
      const section = liveSection();
      if (!capabilities().locator_write) {
        toast("Locator write unavailable in snapshot mode");
        return;
      }
      if (!section || !Number.isFinite(Number(section.start_beat))) {
        toast("Choose a section first");
        return;
      }
      const label = section.label || "Section";
      if (!window.confirm(`Write "${label}" to Live locators?`)) return;
      state = await callTool(BACKEND_TOOLS.write_live_locator, {
        section,
        name: label,
        confirm: true
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Locator written");
    }
    async function clearTarget() {
      const keepPickerMode = pickerMode();
      setStatus("Clearing target");
      selected.clear();
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "instrument",
        target_query: "",
        target_group: "",
        target_layer: ""
      });
      state = await callTool(BACKEND_TOOLS.clear_focus, {});
      targetModeDraft = keepPickerMode;
      syncControlsFromState();
      targetModeDraft = keepPickerMode;
      selected = selectionFromState();
      render();
      setStatus("Ready");
      toast("Target cleared");
    }
    async function selectTrackTarget(index) {
      const track = trackByIndex(index);
      if (!isMusicalTargetTrack(track)) {
        setStatus("That row is a folder or map, not a musical target.");
        toast("Choose a musical track");
        return;
      }
      const currentTracks = targetTracks();
      if (
        currentTracks.length === 1 &&
        Number(currentTracks[0].index) === Number(index) &&
        targetMode() === "query"
      ) {
        await clearTarget();
        return;
      }
      const label = track.name || String(index + 1);
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "query",
        target_query: label,
        target_group: "",
        target_layer: ""
      });
      selected = new Set([index]);
      state = await callTool(BACKEND_TOOLS.set_focus, {
        track_indices: [index],
        label: `${index + 1} ${label}`
      });
      if (capabilities().live_pointing) {
        try {
          state = await callTool(BACKEND_TOOLS.select_live_track, {
            track_index: index
          });
        } catch (error) {
          setStatus(error.message || String(error));
          toast("Cockpit target saved; Live selection not changed");
        }
      }
      syncControlsFromState();
      render();
      toast("Track target saved");
    }
    async function saveFocus(label = "") {
      if (!selected.size) return;
      state = await callTool(BACKEND_TOOLS.set_focus, {
        track_indices: [...selected],
        label: label || targetLabel() || [...selected].map(index => Number(index) + 1).join(",")
      });
      syncControlsFromState();
      render();
    }
    function applyQuickMove(move) {
      $("#sentence").value = move.text;
      $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === move.lane));
      const merged = mergeUnique(currentProtect(), move.protect || []);
      $$("#protectRow .tog").forEach(node => node.classList.toggle("on", merged.includes(node.dataset.protect)));
      renderBrief();
    }
    async function saveBrief(mode = outputMode) {
      outputMode = mode;
      if (outputMode === "auditions" && !auditionLayerReady()) {
        setStatus("Choose a layer or track target before saving auditions.");
        toast("Choose a target first");
        renderBrief();
        return;
      }
      const text = $("#sentence").value.trim();
      const ctx = ctxState();
      const lane = text ? inferLane(text) : currentLane();
      $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === lane));
      const protect = mergeUnique(currentProtect(), inferProtect(text));
      $$("#protectRow .tog").forEach(node => node.classList.toggle("on", protect.includes(node.dataset.protect)));
      const payload = {
        lane,
        workflow_mode: OUTPUTS[outputMode].workflow,
        audition_required: OUTPUTS[outputMode].audition,
        audition_count: auditionCount(),
        audition_scope: targetMode() === "layer" ? "layer" : "track",
        protect,
        request_text: text,
        target_query: $("#targetQuery").value || targetState().query || ctx.target_query || "",
        target_mode: targetMode(),
        target_group: targetMode() === "instrument" ? (targetState().matched_group || ctx.target_group || "") : "",
        target_layer: targetMode() === "layer" ? (targetState().matched_layer || ctx.target_layer || "") : "",
        section: savedSection()
      };
      if (selected.size) {
        state = await callTool(BACKEND_TOOLS.set_focus, {
          track_indices: [...selected],
          label: targetLabel() || [...selected].map(index => Number(index) + 1).join(",")
        });
      }
      state = await callTool(BACKEND_TOOLS.send_brief, payload);
      selected = selectionFromState();
      $("#sentence").value = "";
      clearDraft();
      render();
      const queued = (((state || {}).orchestration_submission || {}).job || {}).title;
      toast(queued ? `Queued: ${queued}` : "Brief sent to Codex");
    }

    $("#refresh").addEventListener("click", refresh);
    $("#refreshLive").addEventListener("click", refreshLive);
    $("#grabLiveSelection").addEventListener("click", grabLiveSelection);
    $("#loopSectionLive").addEventListener("click", loopSelectedSectionLive);
    $("#writeSectionLocator").addEventListener("click", writeSelectedSectionLocator);
    $("#clearTarget").addEventListener("click", clearTarget);
    $("#saveLayer").addEventListener("click", saveCurrentLayer);
    $("#deleteLayer").addEventListener("click", deleteCurrentLayer);
    $("#wholeSongButton").addEventListener("click", chooseWholeSong);
    $("#targetModeRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-mode]");
      if (!button) return;
      targetModeDraft = button.dataset.mode || "instrument";
      renderPicker();
    });
    $("#targetQuery").addEventListener("keydown", event => {
      if (event.key !== "Enter") return;
      const query = $("#targetQuery").value.trim();
      const normalized = normalizeToken(query);
      if (pickerMode() === "track") {
        const tracks = ((state || {}).tracks || []).filter(isMusicalTargetTrack);
        const match = tracks.find(track => {
          const idx = Number(track.index);
          return normalizeToken(track.name) === normalized ||
            normalizeToken(`${idx + 1} ${track.name}`) === normalized ||
            String(idx + 1) === query ||
            String(idx) === query;
        });
        if (match) selectTrackTarget(Number(match.index));
        else chooseFreeQuery(query);
        return;
      }
      const groups = pickerMode() === "layer" ? ((state || {}).layer_groups || []) : ((state || {}).track_groups || []);
      const match = groups.find(group => normalizeToken(group.key) === normalized || normalizeToken(group.label) === normalized);
      if (match) chooseTarget(match.label || query, match.key);
      else chooseFreeQuery(query);
    });
    $("#sentence").addEventListener("input", () => {
      saveDraft();
      renderBrief();
    });
    $("#auditionCount").addEventListener("change", renderBrief);
    $("#outputModeRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-output]");
      if (!button) return;
      outputMode = button.dataset.output || "ask";
      renderBrief();
    });
    $("#briefFeed").addEventListener("click", event => {
      const button = event.target.closest("button.audition-action");
      if (!button) return;
      submitAuditionAction(
        button.dataset.action || "",
        button.dataset.jobId || "",
        button.dataset.variant || ""
      );
    });
    $("#fineTuneHead").addEventListener("click", () => $("#fineTune").classList.toggle("open"));
    $("#laneRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-lane]");
      if (!button) return;
      $$("#laneRow .opt").forEach(node => node.classList.remove("on"));
      button.classList.add("on");
      renderBrief();
    });
    $("#protectRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-protect]");
      if (!button) return;
      button.classList.toggle("on");
      renderBrief();
    });
    $("#runBrief").addEventListener("click", () => saveBrief(outputMode));

    refresh();
    setInterval(() => {
      if (!document.hidden) refresh();
    }, 4000);
  </script>
</body>
</html>"""
    return (
        html
        .replace("__BACKEND_TOOLS__", tools)
        .replace("__HTTP_REFRESH_AVAILABLE__", "true" if transport == "http" else "false")
        .replace("__CALL_TOOL_JS__", call_tool_js.rstrip())
    )


def _cockpit_call_tool_js(transport: str) -> str:
    del transport
    return """    async function callTool(name, args = {}) {
      const routes = {
        [BACKEND_TOOLS.get_state]: ["GET", "/api/cockpit/state"],
        [BACKEND_TOOLS.set_focus]: ["POST", "/api/cockpit/focus"],
        [BACKEND_TOOLS.clear_focus]: ["POST", "/api/cockpit/focus/clear"],
        [BACKEND_TOOLS.save_context]: ["POST", "/api/cockpit/context"],
        [BACKEND_TOOLS.send_brief]: ["POST", "/api/cockpit/brief"],
        [BACKEND_TOOLS.save_track_intent]: ["POST", "/api/cockpit/track-intent"],
        [BACKEND_TOOLS.save_layer]: ["POST", "/api/cockpit/layers/save"],
        [BACKEND_TOOLS.delete_layer]: ["POST", "/api/cockpit/layers/delete"],
        [BACKEND_TOOLS.audition_action]: ["POST", "/api/cockpit/auditions/action"],
        [BACKEND_TOOLS.get_live_selection]: ["GET", "/api/cockpit/live/selection"],
        [BACKEND_TOOLS.select_live_track]: ["POST", "/api/cockpit/live/select-track"],
        [BACKEND_TOOLS.loop_live_section]: ["POST", "/api/cockpit/live/loop-section"],
        [BACKEND_TOOLS.write_live_locator]: ["POST", "/api/cockpit/live/write-locator"]
      };
      const route = routes[name];
      if (!route) throw new Error(`Unknown cockpit tool: ${name}`);
      const [method, path] = route;
      const response = await fetch(path, {
        method,
        headers: { "content-type": "application/json" },
        body: method === "GET" ? undefined : JSON.stringify(args || {})
      });
      const body = await response.json();
      if (!response.ok || body.status === "error") {
        throw new Error(body.error || `Request failed: ${response.status}`);
      }
      return body;
    }
"""

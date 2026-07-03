"""Browser-first cockpit for LivePilot production workflows."""

from __future__ import annotations

from importlib import resources
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
    "delete_brief": "delete_cockpit_brief",
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
    return base.rstrip("/") + "/cockpit/intent"


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
        "track_indices": _working_track_indices(context),
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
    target_tracks = _working_tracks(context)
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
        "track_indices": _working_track_indices(context),
        "track_refs": track_refs,
        "section": target.get("section") or state.get("section"),
        "lane": state.get("lane", "holistic"),
        "workflow_mode": state.get("workflow_mode", "guided"),
        "audition_count": int(state.get("audition_count") or 3),
        "audition_scope": state.get("audition_scope", "layer"),
        "protect": state.get("protect", []),
        "reference": state.get("reference", ""),
    }


def _working_track_indices(context: dict) -> list[int]:
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    focus = (context.get("focus") or {}).get("focus")
    if not isinstance(focus, dict):
        focus = {}
    target_indices = [
        int(index)
        for index in (target.get("track_indices") or [])
        if isinstance(index, int)
    ]
    focus_indices = [
        int(index)
        for index in (focus.get("track_indices") or [])
        if isinstance(index, int)
    ]
    if focus_indices and target_indices:
        target_set = set(target_indices)
        if set(focus_indices).issubset(target_set):
            return focus_indices
    if target_indices:
        return target_indices
    return focus_indices


def _working_tracks(context: dict) -> list[dict]:
    working = set(_working_track_indices(context))
    return [
        track for track in (context.get("tracks") or [])
        if isinstance(track, dict) and track.get("index") in working
    ]


def _compact_session_kernel_for_snapshot(kernel: dict) -> dict:
    """Keep a durable reference/summary, not the full Live session dump."""
    if not isinstance(kernel, dict):
        return {}
    compact = {
        "kernel_id": kernel.get("kernel_id", ""),
        "request_text": kernel.get("request_text", ""),
        "mode": kernel.get("mode", ""),
        "aggression": kernel.get("aggression"),
        "tempo": kernel.get("tempo"),
        "track_count": kernel.get("track_count"),
        "capability_state": kernel.get("capability_state") or {},
        "ledger_summary": _compact_ledger_summary(kernel.get("ledger_summary") or {}),
        "recommended_engines": kernel.get("recommended_engines") or [],
        "recommended_workflow": kernel.get("recommended_workflow") or "",
        "warnings": kernel.get("warnings") or [],
        "session_ref": {
            "embedded": False,
            "reason": "full_session_info_omitted_from_orchestration_snapshot",
            "track_count": kernel.get("track_count"),
            "tempo": kernel.get("tempo"),
        },
    }
    if kernel.get("track_intent_map"):
        compact["track_intent_summary"] = _track_intent_summary(
            kernel.get("track_intent_map") or {}
        )
    return compact


def _compact_ledger_summary(ledger: dict) -> dict:
    return {
        "total_moves": ledger.get("total_moves", 0),
        "memory_candidate_count": ledger.get("memory_candidate_count", 0),
        "last_move": ledger.get("last_move"),
    }


def _compact_cockpit_context_for_snapshot(context: dict) -> dict:
    state = (context.get("production_context") or {}).get("state") or {}
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    focus = (context.get("focus") or {}).get("focus") or {}
    return {
        "project_id": context.get("project_id", ""),
        "version": context.get("version", ""),
        "session": dict(context.get("session") or {}),
        "summary": dict(context.get("summary") or {}),
        "production_state": dict(state),
        "target": _compact_target_for_snapshot(target),
        "focus": {
            "track_indices": focus.get("track_indices") or [],
            "label": focus.get("label", ""),
            "source": focus.get("source", ""),
        },
        "route": dict(context.get("route") or {}),
        "capabilities": dict(context.get("capabilities") or {}),
    }


def _compact_target_for_snapshot(target: dict) -> dict:
    return {
        "target_mode": target.get("target_mode", ""),
        "query": target.get("query", ""),
        "matched_group": target.get("matched_group", ""),
        "matched_group_label": target.get("matched_group_label", ""),
        "matched_layer": target.get("matched_layer", ""),
        "matched_layer_label": target.get("matched_layer_label", ""),
        "target_layer": target.get("target_layer", ""),
        "track_indices": target.get("track_indices") or [],
        "track_names": target.get("track_names") or [],
        "track_count": target.get("track_count", 0),
        "section": target.get("section") or {},
    }


def _compact_layer_groups_for_snapshot(groups: list[dict]) -> list[dict]:
    compact = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        compact.append({
            "key": group.get("key") or group.get("layer_id") or "",
            "layer_id": group.get("layer_id") or group.get("key") or "",
            "label": group.get("label", ""),
            "status": group.get("status", ""),
            "count": group.get("count", 0),
            "track_indices": group.get("track_indices") or [],
            "track_names": group.get("track_names") or [],
            "unresolved_count": group.get("unresolved_count", 0),
            "linked_layers": group.get("linked_layers") or [],
        })
    return compact


def _compact_track_intent_map_for_snapshot(intent_map: dict, context: dict) -> dict:
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    focus = (context.get("focus") or {}).get("focus") or {}
    relevant_indices = {
        int(index)
        for index in (target.get("track_indices") or []) + (focus.get("track_indices") or [])
        if isinstance(index, int)
    }
    tracks = []
    for track in intent_map.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        index = track.get("index")
        has_intent = bool(
            track.get("annotations")
            or track.get("intent")
            or track.get("decision_state")
            or track.get("effective_role")
        )
        if relevant_indices and index not in relevant_indices and not has_intent:
            continue
        tracks.append({
            "index": index,
            "name": track.get("name", ""),
            "effective_role": track.get("effective_role", ""),
            "inferred_role": track.get("inferred_role", ""),
            "priority": track.get("priority", ""),
            "decision_state": track.get("decision_state", ""),
            "constraints": track.get("constraints") or [],
            "tags": _track_intent_tags(track),
        })
        if len(tracks) >= 24:
            break
    return {
        "project_id": intent_map.get("project_id", ""),
        "coverage": dict(intent_map.get("coverage") or {}),
        "warnings": list(intent_map.get("warnings") or [])[:8],
        "tracks": tracks,
        "omitted_full_intent_map": True,
    }


def _track_intent_tags(track: dict) -> list[str]:
    tags: list[str] = []
    for annotation in track.get("annotations") or []:
        if not isinstance(annotation, dict):
            continue
        for tag in annotation.get("tags") or []:
            text = str(tag or "").strip()
            if text and text not in tags:
                tags.append(text)
    return tags[:12]


def _track_intent_summary(intent_map: dict) -> dict:
    return {
        "project_id": intent_map.get("project_id", ""),
        "coverage": dict(intent_map.get("coverage") or {}),
        "warning_count": len(intent_map.get("warnings") or []),
        "track_count": len(intent_map.get("tracks") or []),
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
    session_kernel = _build_session_kernel_for_cockpit(
        ctx,
        request_text=request_text,
        mode=str(
            context.get("production_context", {})
            .get("state", {})
            .get("workflow_mode", "observe")
        ),
    )
    snapshot_result = service.create_snapshot(
        session_info,
        brief=dict(context.get("summary") or {}) | (
            {"text": request_text} if request_text else {}
        ) | {"brief_id": brief_id, "seq": brief.get("seq")},
        session_kernel=_compact_session_kernel_for_snapshot(session_kernel),
        cockpit_context=_compact_cockpit_context_for_snapshot(context),
        section_map=(context.get("section_map") or {}).get("sections", []),
        layer_groups=_compact_layer_groups_for_snapshot(
            context.get("layer_groups") or []
        ),
        track_intent_map=_compact_track_intent_map_for_snapshot(
            context.get("track_intent_map") or {},
            context,
        ),
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
            "track_indices": _working_track_indices(context),
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


def delete_cockpit_brief(ctx: Context, brief_id: str) -> dict:
    """Delete a saved cockpit brief from the project brief feed."""
    session_info = _require_session_info(ctx)
    result = _brief_service(ctx).delete_brief(session_info, brief_id)
    context = _build_context(ctx, include_history=False)
    context["brief_delete"] = result
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


def _cockpit_ui_text(name: str) -> str:
    return resources.files("mcp_server.cockpit_ui").joinpath(name).read_text(
        encoding="utf-8",
    )


def _render_intent_first_cockpit_html(transport: str = "mcp") -> str:
    tools = json.dumps(_backend_tool_map(), sort_keys=True)
    call_tool_js = _cockpit_call_tool_js(transport).rstrip()
    return (
        _cockpit_ui_text("intent.html")
        .replace("__INTENT_CSS__", _cockpit_ui_text("intent.css").rstrip())
        .replace("__INTENT_JS__", _cockpit_ui_text("intent.js").rstrip())
        .replace("__BACKEND_TOOLS__", tools)
        .replace("__HTTP_REFRESH_AVAILABLE__", "true" if transport == "http" else "false")
        .replace("__CALL_TOOL_JS__", call_tool_js)
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
        [BACKEND_TOOLS.delete_brief]: ["POST", "/api/cockpit/briefs/delete"],
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

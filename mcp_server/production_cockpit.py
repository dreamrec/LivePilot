"""Browser-first cockpit for LivePilot production workflows."""

from __future__ import annotations

from importlib import resources
import json
import os
from pathlib import Path
import re
import time
from typing import Optional
from urllib.parse import quote

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
    adopt_annotation_memory_for_session,
    annotation_project_id_for_session,
    annotation_memory_suggestion_for_session,
    build_track_intent_map as build_track_intent_map_data,
    find_annotation_for_track,
    make_track_signature,
    resolve_annotation,
)
from .server import mcp
from .tools._conductor import classify_request

_BACKEND_TOOL_NAMES = {
    "get_state": "get_cockpit_state",
    "set_focus": "set_cockpit_focus",
    "clear_focus": "clear_cockpit_focus",
    "save_context": "save_production_context",
    "send_brief": "send_cockpit_brief",
    "archive_brief": "archive_cockpit_brief",
    "rerun_brief": "rerun_cockpit_brief",
    "save_track_intent": "save_cockpit_track_intent",
    "save_layer": "save_cockpit_layer_group",
    "delete_layer": "delete_cockpit_layer_group",
    "delete_brief": "delete_cockpit_brief",
    "adopt_memory": "adopt_cockpit_memory",
    "record_dispatch": "record_cockpit_brief_dispatch",
    "set_working_thread": "set_cockpit_working_thread",
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
_CODEX_DISPATCH_PROMPT_TEMPLATE = (
    "Pick up LivePilot cockpit brief #{seq} (id {brief_id}) - read it with "
    "get_production_context / list_cockpit_briefs, then run the queue."
)
_CODEX_DISPATCH_SWEEP_PROMPT_TEMPLATE = (
    "Pick up the unseen LivePilot cockpit briefs - read them with "
    "list_cockpit_briefs / get_production_context, run the queue, then "
    "complete each with complete_cockpit_brief."
)
_BRIEF_COMPLETION_CONTRACT = (
    "When a brief's work is finished, call complete_cockpit_brief with "
    "learnings: update each touched track's intent fields and decision_state, "
    "and record rejected alternatives with reasons. A brief without recorded "
    "learnings is not done."
)
_CODEX_DEEPLINK_NEW_THREAD_TEMPLATE = (
    "codex://threads/new?prompt={prompt}&path={path}"
)
_CODEX_DEEPLINK_OPEN_THREAD_TEMPLATE = "codex://threads/{thread_id}"
# Safe fallback until a visual Codex Desktop composer check confirms existing
# thread prompt prefill. Disk checks only prove no auto-submit.
_CODEX_EXISTING_THREAD_PREFILL = False
_CODEX_EXISTING_THREAD_PREFILL_STATUS = "unverified_safe_fallback"
_CODEX_SESSIONS_DIR: Optional[Path] = None
_CODEX_CAPTURE_WINDOW_MS = 120_000
_CODEX_CAPTURE_MTIME_FUZZ_MS = 2_000
_CODEX_THREAD_ID_RE = re.compile(
    r"(?P<thread_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    r"\.jsonl$"
)


def _cockpit_url(ctx: Context) -> Optional[str]:
    base = _focus_panel_url(ctx)
    if not base:
        return None
    return base.rstrip("/") + "/cockpit/intent"


def _codex_dispatch_base() -> dict:
    return {
        "deeplink_open_thread": _CODEX_DEEPLINK_OPEN_THREAD_TEMPLATE,
        "deeplink_open_thread_template": _CODEX_DEEPLINK_OPEN_THREAD_TEMPLATE,
        "deeplink_new_thread": _CODEX_DEEPLINK_NEW_THREAD_TEMPLATE,
        "prompt_template": _CODEX_DISPATCH_PROMPT_TEMPLATE,
        "sweep_prompt_template": _CODEX_DISPATCH_SWEEP_PROMPT_TEMPLATE,
        "existing_thread_prefill": _CODEX_EXISTING_THREAD_PREFILL,
        "existing_thread_prefill_status": _CODEX_EXISTING_THREAD_PREFILL_STATUS,
        "workspace_path": _codex_dispatch_workspace_path(),
    }


def _codex_dispatch_workspace_path() -> str:
    return str(Path(__file__).resolve().parents[1])


def _brief_dispatch_action(
    brief: dict,
    working_thread: Optional[dict] = None,
    working_thread_status: str = "unset",
) -> dict:
    prompt = _codex_dispatch_prompt(brief)
    workspace_path = _codex_dispatch_workspace_path()
    working_thread = working_thread if isinstance(working_thread, dict) else None
    action = {
        "prompt": prompt,
        "prompt_template": _CODEX_DISPATCH_PROMPT_TEMPLATE,
        "sweep_prompt": _CODEX_DISPATCH_SWEEP_PROMPT_TEMPLATE,
        "sweep_prompt_template": _CODEX_DISPATCH_SWEEP_PROMPT_TEMPLATE,
        "deeplink_new_thread": _CODEX_DEEPLINK_NEW_THREAD_TEMPLATE.format(
            prompt=quote(prompt, safe=""),
            path=quote(workspace_path, safe=""),
        ),
        "deeplink_open_thread": "",
        "deeplink_working_thread": "",
        "existing_thread_prefill": _CODEX_EXISTING_THREAD_PREFILL,
        "existing_thread_prefill_status": _CODEX_EXISTING_THREAD_PREFILL_STATUS,
        "working_thread_status": working_thread_status,
    }
    if working_thread and working_thread_status == "live":
        action["working_thread_id"] = str(working_thread.get("thread_id") or "")
        action["deeplink_working_thread"] = _CODEX_DEEPLINK_OPEN_THREAD_TEMPLATE.format(
            thread_id=quote(str(working_thread.get("thread_id") or ""), safe=""),
        )
    thread_id = str(brief.get("thread_id") or "").strip()
    if _looks_like_codex_thread_id(thread_id):
        action["deeplink_open_thread"] = _CODEX_DEEPLINK_OPEN_THREAD_TEMPLATE.format(
            thread_id=quote(thread_id, safe=""),
        )
    return action


def _codex_dispatch_prompt(brief: dict) -> str:
    return _CODEX_DISPATCH_PROMPT_TEMPLATE.format(
        seq=brief.get("seq") or "?",
        brief_id=brief.get("brief_id") or "",
    )


def _looks_like_codex_thread_id(value: str) -> bool:
    parts = str(value or "").split("-")
    return (
        len(parts) == 5
        and [len(part) for part in parts] == [8, 4, 4, 4, 12]
        and all(part and all(ch in "0123456789abcdefABCDEF" for ch in part) for part in parts)
    )


def _codex_sessions_dir() -> Path:
    if _CODEX_SESSIONS_DIR is not None:
        return Path(_CODEX_SESSIONS_DIR)
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return base / "sessions"


def _working_thread_status(working_thread) -> str:
    if not isinstance(working_thread, dict):
        return "unset"
    thread_id = str(working_thread.get("thread_id") or "").strip()
    if not thread_id:
        return "unset"
    sessions_dir = _codex_sessions_dir()
    if not sessions_dir.exists():
        return "missing"
    try:
        for _path in sessions_dir.rglob(f"*-{thread_id}.jsonl"):
            return "live"
    except OSError:
        return "missing"
    return "missing"


def _capture_pending_dispatch_thread(
    ctx: Context,
    session_info: dict,
    brief_state: dict,
) -> Optional[dict]:
    pending = _pending_thread_capture_briefs(brief_state.get("briefs") or [])
    if not pending:
        return None
    brief = pending[0]
    dispatch = brief.get("dispatch") or {}
    candidates = _recent_rollout_thread_candidates(
        int(dispatch.get("at_ms") or 0)
    )
    if len(candidates) != 1:
        return None
    thread_id = candidates[0]
    result = _brief_service(ctx).capture_dispatch_thread_id(
        session_info,
        brief.get("brief_id", ""),
        codex_thread_id=thread_id,
    )
    return {
        "brief_id": result.get("brief", {}).get("brief_id", brief.get("brief_id", "")),
        "thread_id": thread_id,
    }


def _pending_thread_capture_briefs(briefs: list[dict]) -> list[dict]:
    now = int(time.time() * 1000)
    pending: list[dict] = []
    for brief in briefs:
        if not isinstance(brief, dict):
            continue
        dispatch = brief.get("dispatch")
        if not isinstance(dispatch, dict):
            continue
        if dispatch.get("method") != "deeplink":
            continue
        if dispatch.get("codex_thread_id"):
            continue
        try:
            at_ms = int(dispatch.get("at_ms") or 0)
        except (TypeError, ValueError):
            continue
        if at_ms <= 0 or now - at_ms > _CODEX_CAPTURE_WINDOW_MS:
            continue
        pending.append(brief)
    return sorted(
        pending,
        key=lambda item: int((item.get("dispatch") or {}).get("at_ms") or 0),
        reverse=True,
    )


def _recent_rollout_thread_candidates(dispatch_at_ms: int) -> list[str]:
    sessions_dir = _codex_sessions_dir()
    if not sessions_dir.exists():
        return []
    threshold = (dispatch_at_ms - _CODEX_CAPTURE_MTIME_FUZZ_MS) / 1000.0
    seen: list[str] = []
    try:
        for path in sessions_dir.rglob("*.jsonl"):
            candidate_time = _rollout_candidate_time_seconds(path)
            if candidate_time is None or candidate_time < threshold:
                continue
            match = _CODEX_THREAD_ID_RE.search(path.name)
            if not match:
                continue
            thread_id = match.group("thread_id").lower()
            if thread_id not in seen:
                seen.append(thread_id)
    except OSError:
        return []
    return seen


def _rollout_candidate_time_seconds(path: Path) -> Optional[float]:
    try:
        stat_result = path.stat()
    except OSError:
        return None
    birthtime = getattr(stat_result, "st_birthtime", None)
    if isinstance(birthtime, (int, float)) and birthtime > 0:
        return float(birthtime)
    return float(stat_result.st_mtime)


def _briefs_with_dispatch_actions(
    briefs: list[dict],
    session_info: Optional[dict] = None,
    production_state: Optional[dict] = None,
    working_thread_status: str = "unset",
) -> list[dict]:
    production_state = production_state if isinstance(production_state, dict) else {}
    working_thread = production_state.get("working_thread")
    out = []
    for brief in briefs:
        item = dict(brief)
        if isinstance(session_info, dict):
            item["aim_status"] = _brief_aim_status(item, session_info)
        item["dispatch_action"] = _brief_dispatch_action(
            item,
            working_thread=working_thread,
            working_thread_status=working_thread_status,
        )
        out.append(item)
    return out


def _partition_briefs_for_session(
    briefs: list[dict],
    session_info: dict,
) -> dict:
    current: list[dict] = []
    stale: list[dict] = []
    unresolved = 0
    foreign = 0
    degraded = 0
    for brief in briefs:
        if not isinstance(brief, dict):
            continue
        aim = _brief_aim_status(brief, session_info)
        item = dict(brief)
        item["aim_status"] = aim
        status = str(aim.get("status") or "")
        if status == "foreign_set":
            foreign += 1
            stale.append(item)
            continue
        if status == "unresolved":
            unresolved += 1
            stale.append(item)
            continue
        if status == "degraded":
            degraded += 1
        current.append(item)
    return {
        "current": current,
        "stale": stale,
        "foreign_count": foreign,
        "unresolved_count": unresolved,
        "degraded_count": degraded,
    }


def _brief_aim_status(brief: dict, session_info: dict) -> dict:
    digest = brief.get("context_digest") if isinstance(brief.get("context_digest"), dict) else {}
    refs = [ref for ref in (digest.get("track_refs") or []) if isinstance(ref, dict)]
    section = digest.get("section") if isinstance(digest.get("section"), dict) else {}
    digest_identity = digest.get("set_identity") if isinstance(digest.get("set_identity"), dict) else {}
    current_identity = _set_identity_for_session(session_info)
    old_path = str(digest_identity.get("file_path") or "").strip()
    current_path = str(current_identity.get("file_path") or "").strip()
    if old_path and current_path and old_path != current_path:
        return {
            "status": "foreign_set",
            "label": str(digest_identity.get("name") or old_path),
            "set_identity": digest_identity,
            "current_set_identity": current_identity,
            "resolved": 0,
            "unresolved": len(refs),
            "total": len(refs),
            "resolved_track_indices": [],
            "resolved_track_names": [],
            "unresolved_refs": refs,
        }
    if not refs:
        if _section_is_whole_song(section):
            return {
                "status": "no_aim",
                "resolved": 0,
                "unresolved": 0,
                "total": 0,
                "resolved_track_indices": [],
                "resolved_track_names": [],
                "unresolved_refs": [],
            }
        return {
            "status": "current",
            "resolved": 0,
            "unresolved": 0,
            "total": 0,
            "resolved_track_indices": [],
            "resolved_track_names": [],
            "unresolved_refs": [],
        }

    resolved = []
    unresolved = []
    tracks = _regular_tracks(session_info)
    for ref in refs:
        resolution = resolve_annotation(
            session_info,
            {"track_ref": ref},
            tracks=tracks,
        )
        item = {"ref": ref, "resolution": resolution}
        if resolution.get("status") == "resolved":
            resolved.append(item)
        else:
            unresolved.append(item)
    resolved_indices = [
        item["resolution"]["resolved_track_index"]
        for item in resolved
        if isinstance(item.get("resolution", {}).get("resolved_track_index"), int)
    ]
    resolved_names = [
        str(item["resolution"].get("resolved_track_name") or "")
        for item in resolved
    ]
    status = (
        "current"
        if len(resolved) == len(refs)
        else "degraded"
        if resolved
        else "unresolved"
    )
    return {
        "status": status,
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "total": len(refs),
        "resolved_track_indices": resolved_indices,
        "resolved_track_names": resolved_names,
        "unresolved_refs": [
            _compact_aim_ref(item.get("ref") or {}, item.get("resolution") or {})
            for item in unresolved
        ],
        "set_identity": digest_identity,
        "current_set_identity": current_identity,
    }


def _compact_aim_ref(ref: dict, resolution: dict) -> dict:
    signature = ref.get("signature") if isinstance(ref.get("signature"), dict) else {}
    return {
        "name": str(signature.get("name") or ref.get("name") or ""),
        "last_seen_index": ref.get("last_seen_index"),
        "resolution": resolution,
    }


def _section_is_whole_song(section: dict) -> bool:
    if not section:
        return True
    source = str(section.get("source") or "").strip().lower()
    scope = str(section.get("scope") or section.get("section_id") or "").strip().lower()
    label = str(section.get("label") or "").strip().lower()
    return (
        source == "whole_song"
        or scope == "whole_song"
        or label == "whole song"
    )


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


def _partition_layer_groups(groups: list[dict]) -> dict:
    current: list[dict] = []
    stale: list[dict] = []
    unresolved_members = 0
    for group in groups:
        if not isinstance(group, dict):
            continue
        unresolved = int(group.get("unresolved_count") or 0)
        count = int(group.get("count") or 0)
        unresolved_members += unresolved
        if count <= 0 and unresolved > 0:
            stale.append(group)
            continue
        current.append(group)
    return {
        "current": current,
        "stale": stale,
        "unresolved_member_count": unresolved_members,
    }


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
    all_layer_groups = _build_layer_groups(
        tracks,
        layer_result.get("layer_groups") or [],
    )
    layer_partition = _partition_layer_groups(all_layer_groups)
    layer_groups = layer_partition["current"]
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
    captured_thread = _capture_pending_dispatch_thread(ctx, session_info, brief_state)
    if captured_thread:
        brief_state = _brief_service(ctx).list_briefs(
            session_info,
            orchestration_state=_orchestration_state_for_briefs(ctx, session_info),
        )
    working_thread_status = _working_thread_status(
        production_state.get("working_thread")
    )
    brief_partition = _partition_briefs_for_session(
        brief_state.get("briefs", []),
        session_info,
    )
    current_briefs = _briefs_with_dispatch_actions(
        brief_partition["current"],
        session_info=session_info,
        production_state=production_state,
        working_thread_status=working_thread_status,
    )
    stale_briefs = _briefs_with_dispatch_actions(
        brief_partition["stale"],
        session_info=session_info,
        production_state=production_state,
        working_thread_status=working_thread_status,
    )
    memory_health = {
        "briefs_count": len(current_briefs),
        "foreign_or_unresolved_briefs": (
            int(brief_partition["foreign_count"])
            + int(brief_partition["unresolved_count"])
        ),
        "degraded_briefs": int(brief_partition["degraded_count"]),
        "annotation_warnings": len(intent_map.get("warnings") or []),
        "layer_groups_count": len(layer_groups),
        "stale_layer_groups": len(layer_partition["stale"]),
        "unresolved_layer_members": int(layer_partition["unresolved_member_count"]),
    }
    production_context = dict(production_context)
    production_context["working_thread_status"] = working_thread_status
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
        "memory_health": memory_health,
        "stale_memory": {
            "briefs": stale_briefs,
            "layer_groups": layer_partition["stale"],
        },
        "capabilities": _cockpit_capabilities(ctx),
        "memory_suggestion": annotation_memory_suggestion_for_session(session_info),
        "dispatch": _codex_dispatch_base(),
        "completion_contract": _BRIEF_COMPLETION_CONTRACT,
        "briefs": current_briefs,
        "brief_count": len(current_briefs),
        "all_brief_count": brief_state.get("brief_count", 0),
        "captured_thread": captured_thread,
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
        "evidence_budget": state.get("evidence_budget", "standard"),
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


def _brief_context_digest(context: dict, session_info: Optional[dict] = None) -> dict:
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
    session_info = (
        session_info
        if isinstance(session_info, dict)
        else {"project_identity": (context.get("session") or {}).get("project_identity"), **(context.get("session") or {})}
    )
    return {
        "set_identity": _set_identity_for_session(session_info),
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
        "evidence_budget": state.get("evidence_budget", "standard"),
        "protect": state.get("protect", []),
        "reference": state.get("reference", ""),
    }


def _set_identity_for_session(session_info: dict) -> dict:
    identity = session_info.get("project_identity")
    if not isinstance(identity, dict):
        identity = {}
    file_path = ""
    for key in ("file_path", "path", "project_path", "set_path", "live_set_path"):
        file_path = str(identity.get(key) or session_info.get(key) or "").strip()
        if file_path:
            break
    name = ""
    for key in ("name", "project_name", "set_name", "live_set_name"):
        name = str(identity.get(key) or session_info.get(key) or "").strip()
        if name:
            break
    return {
        "name": name,
        "file_path": file_path,
        "track_count": int(session_info.get("track_count") or len(session_info.get("tracks") or [])),
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
    parent_brief_id: str = "",
    thread_id: str = "",
) -> dict:
    """Create orchestration snapshot/task and optional audition job."""
    session_info = _require_session_info(ctx)
    service = _orchestration_service(ctx)
    context_digest = _brief_context_digest(context, session_info)
    brief_result = _brief_service(ctx).create_brief(
        session_info,
        request_text=request_text,
        context_digest=context_digest,
        source="cockpit",
        parent_brief_id=parent_brief_id or None,
        thread_id=thread_id or None,
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
        context_digest=context_digest,
        production_context_state=dict(
            (context.get("production_context") or {}).get("state") or {}
        ),
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
            "evidence_budget": state.get("evidence_budget", "standard"),
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
        "dispatch": _brief_dispatch_action(
            attached,
            working_thread=state.get("working_thread"),
            working_thread_status=(
                (context.get("production_context") or {})
                .get("working_thread_status", "unset")
            ),
        ),
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
        evidence_budget=payload.get("evidence_budget"),
        section=payload.get("section"),
        section_scope=payload.get("section_scope"),
        section_label=payload.get("section_label"),
        section_start_bar=payload.get("section_start_bar"),
        section_end_bar=payload.get("section_end_bar"),
    )
    context = _build_context(ctx, include_history=False)
    request_text = _brief_text_from_payload(payload, context)
    submission = _submit_cockpit_brief_packet(
        ctx,
        context,
        request_text,
        parent_brief_id=str(payload.get("parent_brief_id") or "").strip(),
        thread_id=str(payload.get("thread_id") or "").strip(),
    )
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
    result = _brief_service(ctx).list_briefs(
        session_info,
        limit=limit,
        status=status,
        orchestration_state=_orchestration_state_for_briefs(ctx, session_info),
    )
    production_context = _production_context_service(ctx).get_state(session_info)
    production_state = production_context.get("state") or {}
    working_thread_status = _working_thread_status(
        production_state.get("working_thread")
    )
    result["dispatch"] = _codex_dispatch_base()
    result["completion_contract"] = _BRIEF_COMPLETION_CONTRACT
    result["working_thread_status"] = working_thread_status
    partition = _partition_briefs_for_session(result.get("briefs", []), session_info)
    result["briefs"] = _briefs_with_dispatch_actions(
        partition["current"],
        session_info=session_info,
        production_state=production_state,
        working_thread_status=working_thread_status,
    )
    result["stale_briefs"] = _briefs_with_dispatch_actions(
        partition["stale"],
        session_info=session_info,
        production_state=production_state,
        working_thread_status=working_thread_status,
    )
    result["brief_count"] = len(result["briefs"])
    result["all_brief_count"] = (
        len(result["briefs"]) + len(result["stale_briefs"])
    )
    result["memory_health"] = {
        "briefs_count": len(result["briefs"]),
        "foreign_or_unresolved_briefs": (
            int(partition["foreign_count"]) + int(partition["unresolved_count"])
        ),
        "degraded_briefs": int(partition["degraded_count"]),
    }
    return result


def complete_cockpit_brief(
    ctx: Context,
    brief_id: str,
    status: str,
    summary: str = "",
    learnings: Optional[list[dict]] = None,
) -> dict:
    """Complete a cockpit brief and write its learnings into song memory.

    Work is finished when the song's memory reflects it. Each learning updates
    the touched track's annotation fields, and rejected options are stored with
    reasons. Invalid learning rows are reported without rolling back valid rows.
    """
    session_info = _require_session_info(ctx)
    learning_results = []
    successful_annotations = []
    for index, learning in enumerate(learnings or []):
        try:
            result = _apply_brief_learning(ctx, session_info, learning)
        except Exception as exc:  # noqa: BLE001 - per-item degradation contract.
            learning_results.append({
                "index": index,
                "ok": False,
                "error": str(exc),
            })
            continue
        annotation = result.get("annotation") or {}
        annotation_id = str(annotation.get("annotation_id") or "")
        successful_annotations.append(annotation_id)
        learning_results.append({
            "index": index,
            "ok": True,
            "track_index": result.get("track_index"),
            "annotation_id": annotation_id,
        })

    successful_count = len([item for item in learning_results if item.get("ok")])
    outcome = _brief_service(ctx).complete_brief(
        session_info,
        brief_id,
        status=status,
        summary=summary,
        learnings_count=successful_count,
    )
    _brief_service(ctx).stamp_reader(session_info, "complete_cockpit_brief")
    revision = _orchestration_service(ctx).store_for_session(
        session_info
    ).increment_revision(
        reason="brief_completed",
        source_id=str(brief_id or ""),
        metadata={
            "outcome": outcome.get("brief", {}).get("outcome") or {},
            "successful_learning_count": successful_count,
            "failed_learning_count": len(learning_results) - successful_count,
        },
    )
    context = _build_context(ctx, include_history=False)
    return {
        "status": "ok",
        "brief": outcome.get("brief"),
        "learning_results": learning_results,
        "annotation_ids": [
            annotation_id for annotation_id in successful_annotations
            if annotation_id
        ],
        "orchestration_revision": revision.get("project_revision"),
        "context": context,
    }


def _apply_brief_learning(ctx: Context, session_info: dict, learning: dict) -> dict:
    if not isinstance(learning, dict):
        raise ValueError("learning must be an object")
    track_index = int(learning.get("track_index"))
    rejected_option = learning.get("rejected_option")
    notes = str(learning.get("notes") or "").strip()
    options = None
    if rejected_option is not None:
        if not isinstance(rejected_option, dict):
            raise ValueError("rejected_option must be an object")
        option_label = str(rejected_option.get("label") or "").strip()
        reason = str(rejected_option.get("reason") or "").strip()
        if not option_label:
            raise ValueError("rejected_option.label is required")
        if not reason:
            raise ValueError("rejected_option.reason is required")
        existing = find_annotation_for_track(
            session_info,
            _annotation_store_for_session(session_info).list_annotations(),
            track_index,
        )
        options = list((existing or {}).get("options") or [])
        options.append({
            "label": option_label,
            "decision_state": "rejected",
            "notes": reason,
        })
        rejected_note = f"Rejected {option_label}: {reason}"
        notes = f"{notes}\n{rejected_note}".strip() if notes else rejected_note

    meaningful = any(
        _optional_text(learning.get(key))
        for key in (
            "role",
            "priority",
            "mix_intent",
            "sound_design_intent",
            "composition_intent",
            "decision_state",
        )
    ) or bool(notes) or options is not None
    if not meaningful:
        raise ValueError(
            "learning must update intent fields, notes, decision_state, or rejected_option"
        )

    from .tools.tracks import set_track_annotation as _set_track_annotation_tool

    set_kwargs = {
        "track_index": track_index,
        "role": _optional_text(learning.get("role")),
        "priority": _optional_text(learning.get("priority")),
        "mix_intent": _optional_text(learning.get("mix_intent")),
        "sound_design_intent": _optional_text(learning.get("sound_design_intent")),
        "composition_intent": _optional_text(learning.get("composition_intent")),
        "notes": notes if notes else None,
        "decision_state": _optional_text(learning.get("decision_state")),
        "options": options,
        "source": "brief_completion",
        "confidence": 1.0,
    }
    return dict(
        _set_track_annotation_tool(
            ctx,
            **{key: value for key, value in set_kwargs.items() if value is not None},
        ),
        track_index=track_index,
    )


def _optional_text(value) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


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
mcp.tool()(complete_cockpit_brief)


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
    working_thread: Optional[dict] = None,
    evidence_budget: Optional[str] = None,
    section: Optional[dict] = None,
    section_scope: Optional[str] = None,
    section_label: Optional[str] = None,
    section_start_bar: Optional[float] = None,
    section_end_bar: Optional[float] = None,
    parent_brief_id: Optional[str] = None,
    thread_id: Optional[str] = None,
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
        working_thread=working_thread,
        evidence_budget=evidence_budget,
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
    evidence_budget: Optional[str] = None,
    section: Optional[dict] = None,
    section_scope: Optional[str] = None,
    section_label: Optional[str] = None,
    section_start_bar: Optional[float] = None,
    section_end_bar: Optional[float] = None,
    parent_brief_id: Optional[str] = None,
    thread_id: Optional[str] = None,
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
            "evidence_budget": evidence_budget,
            "section": section,
            "section_scope": section_scope,
            "section_label": section_label,
            "section_start_bar": section_start_bar,
            "section_end_bar": section_end_bar,
            "parent_brief_id": parent_brief_id,
            "thread_id": thread_id,
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


def archive_cockpit_brief(ctx: Context, brief_id: str) -> dict:
    """Archive a saved cockpit brief without incrementing orchestration revision.

    This browser action is a producer inbox cleanup: it marks the brief as
    abandoned, but it does not mean the song changed. Codex-side
    complete_cockpit_brief still increments revision because it records finished
    work and song-memory learnings.
    """
    session_info = _require_session_info(ctx)
    result = _brief_service(ctx).complete_brief(
        session_info,
        brief_id,
        status="abandoned",
        summary="archived from cockpit",
        learnings_count=0,
    )
    context = _build_context(ctx, include_history=False)
    context["brief_archive"] = result
    return context


def rerun_cockpit_brief(ctx: Context, brief_id: str) -> dict:
    """Return a composer prefill package for a saved brief re-run."""
    session_info = _require_session_info(ctx)
    context = _build_context(ctx, include_history=False)
    brief = _find_context_brief(context, brief_id)
    digest = brief.get("context_digest") if isinstance(brief.get("context_digest"), dict) else {}
    aim = _brief_aim_status(brief, session_info)
    section = _rerun_section_from_digest(digest, context.get("section_map") or {})
    package = {
        "status": "ok",
        "brief_id": brief.get("brief_id", ""),
        "seq": brief.get("seq"),
        "parent_brief_id": brief.get("brief_id", ""),
        "thread_id": brief.get("thread_id", ""),
        "request_text": brief.get("request_text", ""),
        "lane": digest.get("lane", "holistic"),
        "protect": digest.get("protect", []),
        "workflow_mode": digest.get("workflow_mode", "guided"),
        "audition_count": int(digest.get("audition_count") or 3),
        "audition_scope": digest.get("audition_scope", "layer"),
        "evidence_budget": digest.get("evidence_budget", "standard"),
        "aim_status": aim,
        "resolved_track_indices": aim.get("resolved_track_indices") or [],
        "resolved_track_names": aim.get("resolved_track_names") or [],
        "unresolved_refs": aim.get("unresolved_refs") or [],
        "target_mode": _rerun_target_mode(digest, context, aim),
        "target_query": _rerun_target_query(digest, aim),
        "target_group": _rerun_target_group(digest, context, aim),
        "target_layer": _rerun_target_layer(digest, context, aim),
        "section": section,
        "banner": _rerun_banner(brief, aim),
    }
    return package


def adopt_cockpit_memory(ctx: Context, project_id: str) -> dict:
    """Explicitly import a similar project memory into the current set identity."""
    session_info = _require_session_info(ctx)
    result = adopt_annotation_memory_for_session(session_info, project_id)
    context = _build_context(ctx, include_history=False)
    context["memory_adoption"] = result
    return context


def delete_cockpit_brief(ctx: Context, brief_id: str) -> dict:
    """Backward-compatible browser action; archives because briefs are durable."""
    return archive_cockpit_brief(ctx, brief_id)


def _find_context_brief(context: dict, brief_id: str) -> dict:
    brief_id = str(brief_id or "").strip()
    for brief in context.get("briefs") or []:
        if brief.get("brief_id") == brief_id:
            return brief
    raise KeyError(f"brief_id not found: {brief_id}")


def _rerun_section_from_digest(digest: dict, section_map: dict) -> Optional[dict]:
    section = digest.get("section") if isinstance(digest.get("section"), dict) else {}
    if not section or _section_is_whole_song(section):
        return None
    sections = section_map.get("sections") if isinstance(section_map, dict) else []
    section_id = str(section.get("section_id") or section.get("id") or "")
    label = _normalize_target_token(str(section.get("label") or ""))
    for candidate in sections or []:
        if section_id and section_id == str(candidate.get("id") or candidate.get("section_id") or ""):
            return _section_prefill(candidate)
    for candidate in sections or []:
        if label and label == _normalize_target_token(str(candidate.get("label") or "")):
            return _section_prefill(candidate)
    return {
        "section_id": section_id,
        "label": str(section.get("label") or "Section"),
        "start_beat": _float_or_none(section.get("start_beat")),
        "end_beat": _float_or_none(section.get("end_beat")),
        "source": str(section.get("source") or "manual"),
    }


def _section_prefill(section: dict) -> dict:
    return {
        "section_id": str(section.get("id") or section.get("section_id") or ""),
        "label": str(section.get("label") or "Section"),
        "start_beat": _float_or_none(section.get("start_beat")),
        "end_beat": _float_or_none(section.get("end_beat")),
        "source": str(section.get("source") or "manual"),
    }


def _rerun_target_mode(digest: dict, context: dict, aim: dict) -> str:
    if aim.get("status") == "foreign_set":
        return "query"
    layer_id = str(digest.get("layer_id") or "").strip()
    if layer_id and _context_has_layer(context, layer_id):
        return "layer"
    if aim.get("resolved_track_indices"):
        return "query"
    mode = _normalize_target_mode(digest.get("target_mode"))
    return mode if mode != "layer" else "query"


def _rerun_target_query(digest: dict, aim: dict) -> str:
    names = aim.get("resolved_track_names") or []
    if names:
        return ", ".join(str(name) for name in names if name)
    return str(digest.get("target_label") or "")


def _rerun_target_group(digest: dict, context: dict, aim: dict) -> str:
    if _rerun_target_mode(digest, context, aim) == "instrument":
        return str(digest.get("target_label") or "")
    return ""


def _rerun_target_layer(digest: dict, context: dict, aim: dict) -> str:
    layer_id = _normalize_target_token(str(digest.get("layer_id") or ""))
    if _rerun_target_mode(digest, context, aim) == "layer" and layer_id:
        return layer_id
    return ""


def _context_has_layer(context: dict, layer_id: str) -> bool:
    normalized = _normalize_target_token(layer_id)
    return any(
        normalized == _normalize_target_token(str(group.get("key") or group.get("layer_id") or ""))
        for group in context.get("layer_groups") or []
        if isinstance(group, dict)
    )


def _rerun_banner(brief: dict, aim: dict) -> str:
    seq = brief.get("seq") or "?"
    status = aim.get("status")
    if status == "foreign_set":
        return f"Re-running brief #{seq} - aimed at another set; point at a new target."
    if status == "degraded":
        return (
            f"Re-running brief #{seq} - aim re-resolved "
            f"({aim.get('resolved', 0)} of {aim.get('total', 0)} tracks matched)."
        )
    if status == "unresolved":
        return f"Re-running brief #{seq} - aim could not be re-resolved; point at a new target."
    if status == "current":
        total = aim.get("total", 0)
        return f"Re-running brief #{seq} - aim re-resolved ({total} of {total} tracks matched)."
    return f"Re-running brief #{seq}."


def record_cockpit_brief_dispatch(
    ctx: Context,
    brief_id: str,
    method: str,
    codex_thread_id: str = "",
) -> dict:
    """Record that a cockpit brief was dispatched to Codex."""
    session_info = _require_session_info(ctx)
    result = _brief_service(ctx).record_dispatch(
        session_info,
        brief_id,
        method=method,
        codex_thread_id=codex_thread_id,
    )
    context = _build_context(ctx, include_history=False)
    context["brief_dispatch"] = result
    return context


def set_cockpit_working_thread(
    ctx: Context,
    thread_id: str = "",
    label: str = "",
    clear: bool = False,
) -> dict:
    """Pin or clear the Codex working thread for this project."""
    session_info = _require_session_info(ctx)
    working_thread: dict = {}
    if not clear:
        thread_id = str(thread_id or "").strip()
        if not thread_id:
            raise ValueError("thread_id is required unless clear is true")
        working_thread = {
            "thread_id": thread_id,
            "label": str(label or "").strip(),
            "last_used_ms": int(time.time() * 1000),
        }
    _production_context_service(ctx).save_state(
        session_info,
        working_thread=working_thread,
    )
    context = _build_context(ctx, include_history=False)
    context["working_thread_update"] = {
        "status": "cleared" if clear else "pinned",
        "thread_id": "" if clear else thread_id,
    }
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
        [BACKEND_TOOLS.archive_brief]: ["POST", "/api/cockpit/brief-archive"],
        [BACKEND_TOOLS.rerun_brief]: ["POST", "/api/cockpit/brief-rerun"],
        [BACKEND_TOOLS.save_track_intent]: ["POST", "/api/cockpit/track-intent"],
        [BACKEND_TOOLS.save_layer]: ["POST", "/api/cockpit/layers/save"],
        [BACKEND_TOOLS.delete_layer]: ["POST", "/api/cockpit/layers/delete"],
        [BACKEND_TOOLS.delete_brief]: ["POST", "/api/cockpit/briefs/delete"],
        [BACKEND_TOOLS.adopt_memory]: ["POST", "/api/cockpit/adopt-memory"],
        [BACKEND_TOOLS.record_dispatch]: ["POST", "/api/cockpit/brief-dispatch"],
        [BACKEND_TOOLS.set_working_thread]: ["POST", "/api/cockpit/working-thread"],
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

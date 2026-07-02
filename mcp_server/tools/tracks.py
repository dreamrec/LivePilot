"""Track MCP tools — create, delete, rename, mute, solo, arm, group fold, monitor, freeze, flatten.

20 tools matching the Remote Script tracks domain.
"""

from __future__ import annotations

import ast
import json
from typing import Optional

from fastmcp import Context

from ..persistence.agent_focus import AgentFocusService
from ..persistence.layer_groups import LayerGroupService
from ..persistence.orchestration_queue import OrchestrationService
from ..persistence.track_annotations import (
    TrackAnnotationStore,
    annotation_project_id_for_session,
    build_track_intent_map as build_track_intent_map_data,
    find_annotation_for_track,
    make_track_signature,
    resolve_annotation,
    resolve_annotations,
)
from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


MASTER_TRACK_INDEX = -1000  # mirrors remote_script/LivePilot/utils.py


def _validate_track_index(track_index: int, allow_return: bool = True, allow_master: bool = True):
    """Validate track index.

    Regular tracks: >= 0. Return tracks: -1 (A), -2 (B), etc. Master: -1000.
    Set allow_return=False for operations that only work on regular tracks
    (e.g., create_scene, set_group_fold).
    Set allow_master=False for operations that don't make sense on master
    (e.g., delete_track, set_track_arm).
    """
    if track_index == MASTER_TRACK_INDEX:
        if not allow_master:
            raise ValueError("track_index=-1000 (master) is not supported for this operation")
        return
    if track_index < 0:
        if not allow_return:
            raise ValueError("track_index must be >= 0 (return tracks not supported for this operation)")
        if track_index < -99:
            raise ValueError(
                "track_index must be >= 0 for regular tracks, "
                "-1..-99 for return tracks (-1=A, -2=B), "
                "or -1000 for master"
            )


def _validate_color_index(color_index: int):
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


def _require_session_info(ctx: Context) -> dict:
    info = _get_ableton(ctx).send_command("get_session_info")
    if not isinstance(info, dict) or info.get("error"):
        raise RuntimeError(f"Could not read session info: {info!r}")
    return info


def _annotation_store_for_session(session_info: dict) -> TrackAnnotationStore:
    return TrackAnnotationStore(annotation_project_id_for_session(session_info))


def _layer_group_service_for_ctx(ctx: Context) -> LayerGroupService:
    service = getattr(ctx, "lifespan_context", {}).get("layer_groups")
    if isinstance(service, LayerGroupService):
        return service
    return LayerGroupService()


def _orchestration_service_for_ctx(ctx: Context) -> OrchestrationService:
    service = getattr(ctx, "lifespan_context", {}).get("orchestration_queue")
    if isinstance(service, OrchestrationService):
        return service
    return OrchestrationService()


def _find_regular_track(session_info: dict, track_index: int) -> dict:
    for track in session_info.get("tracks") or []:
        if isinstance(track, dict) and track.get("index") == track_index:
            return track
    raise ValueError(f"Track index {track_index} not found in current session")


def _normalize_tags(tags: Optional[list[str]]) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        text = tags.strip()
        if text.startswith("["):
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                parsed = None
            if isinstance(parsed, list):
                tags = parsed
            else:
                tags = [text]
        elif "," in text:
            tags = [part.strip() for part in text.split(",")]
        else:
            tags = [text]
    normalized: list[str] = []
    for tag in tags:
        if isinstance(tag, str) and tag.strip().startswith("["):
            for value in _normalize_tags(tag):
                if value not in normalized:
                    normalized.append(value)
            continue
        value = str(tag).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _load_track_detail_safely(ctx: Context, track_index: int) -> dict:
    try:
        info = _get_ableton(ctx).send_command("get_track_info", {"track_index": track_index})
    except Exception:
        return {}
    return info if isinstance(info, dict) else {}


def _annotation_for_track(ctx: Context, track_index: int) -> Optional[dict]:
    try:
        session_info = _require_session_info(ctx)
        store = _annotation_store_for_session(session_info)
        return find_annotation_for_track(
            session_info,
            store.list_annotations(),
            track_index,
        )
    except Exception:
        return None


def _focus_service(ctx: Context) -> AgentFocusService:
    service = ctx.lifespan_context.get("agent_focus")
    if isinstance(service, AgentFocusService):
        return service
    return AgentFocusService()


def _focus_panel_url(ctx: Context) -> Optional[str]:
    value = ctx.lifespan_context.get("focus_panel_url")
    return str(value) if value else None


def _normalize_focus_indices(track_indices) -> list[int]:
    if isinstance(track_indices, str):
        text = track_indices.strip()
        if text.startswith("["):
            track_indices = json.loads(text)
        elif text:
            track_indices = [part.strip() for part in text.split(",")]
        else:
            track_indices = []
    if not isinstance(track_indices, list):
        raise ValueError("track_indices must be a list, JSON array, or comma-separated string")
    out: list[int] = []
    for value in track_indices:
        idx = int(value)
        if idx < 0:
            raise ValueError("Agent focus currently supports regular tracks only")
        if idx not in out:
            out.append(idx)
    return out


def _track_matches_token(track: dict, token: str) -> bool:
    name = str(track.get("name") or "")
    return name == token or name.lower() == token.lower()


def _track_contains_token(track: dict, token: str) -> bool:
    return token.lower() in str(track.get("name") or "").lower()


@mcp.tool()
def get_track_info(
    ctx: Context,
    track_index: int,
    include_device_parameters: bool = False,
    max_device_parameters: int = 128,
    include_device_parameter_count: bool = False,
) -> dict:
    """Get track clips, device-chain summaries, and mixer state; device parameters are opt-in and capped.

    BUG-2026-04-22#11 FIX: track_index=-1000 (the master-track convention
    used by set_track_volume, find_and_load_device, etc.) now dispatches
    to the get_master_track endpoint instead of rejecting. This makes
    -1000 work consistently across every track-addressing tool.

    Device parameters are omitted by default because many plugins expose
    thousands of parameters. Use get_device_parameters for intentional
    single-device parameter reads, or opt in here for a capped diagnostic
    sample.
    """
    _validate_track_index(track_index)
    if track_index == MASTER_TRACK_INDEX:
        return _get_ableton(ctx).send_command("get_master_track")
    params = {
        "track_index": track_index,
        "include_device_parameters": include_device_parameters,
        "max_device_parameters": max_device_parameters,
        "include_device_parameter_count": include_device_parameter_count,
    }
    result = _get_ableton(ctx).send_command("get_track_info", params)
    if isinstance(result, dict) and track_index >= 0:
        result["track_annotation"] = _annotation_for_track(ctx, track_index)
    return result


@mcp.tool()
def get_agent_focus(ctx: Context, include_history: bool = False) -> dict:
    """Return the tracks the user has pointed LivePilot at in the focus panel.

    Use this when the user says "this track", "these tracks", "focused",
    "the selected ones", or otherwise refers to the browser focus panel.
    """
    session_info = _require_session_info(ctx)
    service = _focus_service(ctx)
    result = service.get_focus(session_info)
    result["focus_panel_url"] = _focus_panel_url(ctx)
    if include_history:
        result["history"] = service.history(session_info)
    return result


@mcp.tool()
def set_agent_focus(
    ctx: Context,
    track_indices: list[int],
    label: Optional[str] = None,
    source: str = "mcp",
) -> dict:
    """Set LivePilot's current agent focus to one or more regular tracks.

    This is the MCP equivalent of clicking tracks in the local focus panel.
    """
    session_info = _require_session_info(ctx)
    indices = _normalize_focus_indices(track_indices)
    result = _focus_service(ctx).set_focus(
        session_info,
        track_indices=indices,
        label=label,
        source=source or "mcp",
    )
    result["focus_panel_url"] = _focus_panel_url(ctx)
    return result


@mcp.tool()
def clear_agent_focus(ctx: Context) -> dict:
    """Clear LivePilot's current agent focus."""
    session_info = _require_session_info(ctx)
    result = _focus_service(ctx).clear_focus(session_info)
    result["focus_panel_url"] = _focus_panel_url(ctx)
    return result


@mcp.tool()
def resolve_track_ref(ctx: Context, track_ref: str) -> dict:
    """Resolve a conversational track reference to current track indices.

    Handles "focused" / "this" via agent focus, "master", exact names,
    unique case-insensitive names, unique substrings, and numeric indices.
    """
    token = str(track_ref or "").strip()
    if not token:
        raise ValueError("track_ref cannot be empty")

    lower = token.lower()
    if lower in {"focused", "focus", "this", "these", "selected", "selection"}:
        focus = get_agent_focus(ctx)
        resolved = focus.get("focus") or {}
        if resolved.get("is_empty"):
            return {
                "status": "unresolved",
                "resolution_type": "agent_focus",
                "reason": "agent_focus_empty",
                "track_indices": [],
                "tracks": [],
                "focus_panel_url": focus.get("focus_panel_url"),
            }
        return {
            "status": resolved.get("resolution_status", "resolved"),
            "resolution_type": "agent_focus",
            "track_indices": resolved.get("track_indices", []),
            "tracks": resolved.get("tracks", []),
            "focus_panel_url": focus.get("focus_panel_url"),
        }

    if lower == "master":
        return {
            "status": "resolved",
            "resolution_type": "master",
            "track_indices": [-1000],
            "tracks": [{"index": -1000, "name": "Master"}],
        }

    session_info = _require_session_info(ctx)
    tracks = [
        track for track in (session_info.get("tracks") or [])
        if isinstance(track, dict) and isinstance(track.get("index"), int)
    ]

    try:
        numeric = int(token)
    except ValueError:
        numeric = None
    if numeric is not None:
        if numeric == -1000:
            return {
                "status": "resolved",
                "resolution_type": "master",
                "track_indices": [-1000],
                "tracks": [{"index": -1000, "name": "Master"}],
            }
        matches = [track for track in tracks if track.get("index") == numeric]
        if matches:
            return {
                "status": "resolved",
                "resolution_type": "index",
                "track_indices": [numeric],
                "tracks": matches,
            }
        return {
            "status": "unresolved",
            "resolution_type": "index",
            "reason": "track_index_not_found",
            "track_indices": [],
            "tracks": [],
        }

    exact = [track for track in tracks if _track_matches_token(track, token)]
    if len(exact) == 1:
        return {
            "status": "resolved",
            "resolution_type": "name",
            "track_indices": [exact[0]["index"]],
            "tracks": exact,
        }
    if len(exact) > 1:
        return {
            "status": "ambiguous",
            "resolution_type": "name",
            "reason": "multiple_exact_name_matches",
            "track_indices": [track["index"] for track in exact],
            "tracks": exact,
        }

    contains = [track for track in tracks if _track_contains_token(track, token)]
    if len(contains) == 1:
        return {
            "status": "resolved",
            "resolution_type": "substring",
            "track_indices": [contains[0]["index"]],
            "tracks": contains,
        }
    if len(contains) > 1:
        return {
            "status": "ambiguous",
            "resolution_type": "substring",
            "reason": "multiple_substring_matches",
            "track_indices": [track["index"] for track in contains],
            "tracks": contains,
        }

    return {
        "status": "unresolved",
        "resolution_type": "name",
        "reason": "no_match",
        "track_indices": [],
        "tracks": [],
    }


@mcp.tool()
def set_track_annotation(
    ctx: Context,
    track_index: Optional[int] = None,
    scope: str = "track",
    decision_state: Optional[str] = None,
    role: Optional[str] = None,
    role_candidates: Optional[list[str]] = None,
    priority: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    relationship: Optional[str] = None,
    relationships: Optional[list[dict]] = None,
    references: Optional[list[dict]] = None,
    options: Optional[list[dict]] = None,
    constraints: Optional[list[str]] = None,
    mix_intent: Optional[str] = None,
    composition_intent: Optional[str] = None,
    sound_design_intent: Optional[str] = None,
    decision_policy: Optional[str] = None,
    selected_option_id: Optional[str] = None,
    source: Optional[str] = None,
    confidence: Optional[float] = None,
    annotation_id: Optional[str] = None,
) -> dict:
    """Attach persistent sparse intent metadata to a track or project scope.

    The annotation is stored in a project-scoped sidecar and resolved later
    from track name/color/type signatures, so it survives ordinary track
    reordering instead of trusting the old positional track_index forever.
    """
    scope = (scope or "track").strip().lower()
    if scope == "track" and track_index is None:
        raise ValueError("track_index is required when scope='track'")
    if track_index is not None:
        _validate_track_index(track_index, allow_return=False, allow_master=False)

    settable_values = (
        decision_state,
        role,
        role_candidates,
        priority,
        notes,
        tags,
        relationship,
        relationships,
        references,
        options,
        constraints,
        mix_intent,
        composition_intent,
        sound_design_intent,
        decision_policy,
        selected_option_id,
        source,
        confidence,
    )
    if all(value is None for value in settable_values):
        raise ValueError("Provide at least one of role, notes, tags, or relationship")

    session_info = _require_session_info(ctx)
    track = _find_regular_track(session_info, track_index) if track_index is not None else None
    detail = _load_track_detail_safely(ctx, track_index) if track_index is not None else {}
    store = _annotation_store_for_session(session_info)
    annotations = store.list_annotations()

    existing = None
    if annotation_id:
        existing = next(
            (item for item in annotations if item.get("annotation_id") == annotation_id),
            None,
        )
        if existing is None:
            raise ValueError(f"annotation_id not found: {annotation_id}")
    else:
        existing = (
            find_annotation_for_track(session_info, annotations, track_index)
            if track_index is not None
            else None
        )

    annotation = dict(existing or {})
    annotation["scope"] = scope
    if decision_state is not None:
        annotation["decision_state"] = decision_state.strip()
    if role is not None:
        annotation["role"] = role.strip()
    if role_candidates is not None:
        annotation["role_candidates"] = role_candidates
    if priority is not None:
        annotation["priority"] = priority.strip()
    if notes is not None:
        annotation["notes"] = notes.strip()
    if tags is not None:
        annotation["tags"] = _normalize_tags(tags)
    elif "tags" not in annotation:
        annotation["tags"] = []
    if relationship is not None:
        annotation["relationship"] = relationship.strip()
    if relationships is not None:
        annotation["relationships"] = relationships
    if references is not None:
        annotation["references"] = references
    if options is not None:
        annotation["options"] = options
    if constraints is not None:
        annotation["constraints"] = constraints
    if mix_intent is not None:
        annotation["mix_intent"] = mix_intent.strip()
    if composition_intent is not None:
        annotation["composition_intent"] = composition_intent.strip()
    if sound_design_intent is not None:
        annotation["sound_design_intent"] = sound_design_intent.strip()
    if decision_policy is not None:
        annotation["decision_policy"] = decision_policy.strip()
    if selected_option_id is not None:
        annotation["selected_option_id"] = selected_option_id.strip()
    if source is not None:
        annotation["source"] = source.strip()
    if confidence is not None:
        annotation["confidence"] = confidence

    if track is not None:
        signature = make_track_signature(track, detail=detail)
        annotation["track_ref"] = {
            "name": track.get("name", ""),
            "last_seen_index": track_index,
            "signature": signature,
        }
    if annotation_id:
        annotation["annotation_id"] = annotation_id

    saved = store.upsert(annotation)
    saved = dict(saved)
    saved["resolution"] = resolve_annotation(session_info, saved)
    return {
        "status": "ok",
        "project_id": store.project_id,
        "store_path": str(store.path),
        "annotation": saved,
    }


@mcp.tool()
def build_track_intent_map(ctx: Context) -> dict:
    """Build the decision-time map of track roles, options, references, and intent.

    Combines current session tracks with persistent annotations. User-explicit
    committed intent outranks name inference; open options remain unresolved so
    creative workflows can audition branches instead of silently choosing.
    """
    session_info = _require_session_info(ctx)
    store = _annotation_store_for_session(session_info)
    result = build_track_intent_map_data(session_info, store.list_annotations())
    result["project_id"] = store.project_id
    result["store_path"] = str(store.path)
    return result


@mcp.tool()
def list_layer_groups(ctx: Context) -> dict:
    """List project-scoped musical layer groups resolved to current tracks."""
    session_info = _require_session_info(ctx)
    return _layer_group_service_for_ctx(ctx).list_groups(session_info)


@mcp.tool()
def save_layer_group(
    ctx: Context,
    label: str,
    track_indices: list[int],
    layer_id: str = "",
    status: str = "layered",
    linked_layers: Optional[list[str]] = None,
    notes: str = "",
) -> dict:
    """Create or update a project-scoped musical layer group.

    The saved member references are signature-based, so future reads can
    resolve the layer after ordinary track reordering or renaming.
    """
    session_info = _require_session_info(ctx)
    result = _layer_group_service_for_ctx(ctx).save_group(
        session_info,
        label=label,
        layer_id=layer_id,
        track_indices=track_indices,
        status=status,
        linked_layers=linked_layers,
        notes=notes,
    )
    revision = _orchestration_service_for_ctx(ctx).store_for_session(
        session_info
    ).increment_revision(
        reason="layer_map_save",
        source_id=str(result.get("layer", {}).get("layer_id") or ""),
        metadata={"label": result.get("layer", {}).get("label")},
    )
    result["orchestration_revision"] = revision.get("project_revision")
    return result


@mcp.tool()
def delete_layer_group(ctx: Context, layer_id: str) -> dict:
    """Delete a project-scoped musical layer group."""
    session_info = _require_session_info(ctx)
    result = _layer_group_service_for_ctx(ctx).delete_group(session_info, layer_id)
    if result.get("deleted"):
        revision = _orchestration_service_for_ctx(ctx).store_for_session(
            session_info
        ).increment_revision(
            reason="layer_map_delete",
            source_id=str(layer_id or ""),
        )
        result["orchestration_revision"] = revision.get("project_revision")
    return result


@mcp.tool()
def get_track_annotations(
    ctx: Context,
    track_index: Optional[int] = None,
    include_unresolved: bool = True,
) -> dict:
    """List persistent track annotations resolved against the current session.

    Pass track_index to return only annotations currently resolved to that
    regular track. Each annotation includes resolution confidence and candidate
    matches so callers can detect renamed or duplicate tracks.
    """
    if track_index is not None:
        _validate_track_index(track_index, allow_return=False, allow_master=False)
    session_info = _require_session_info(ctx)
    store = _annotation_store_for_session(session_info)
    annotations = resolve_annotations(session_info, store.list_annotations())
    if track_index is not None:
        annotations = [
            item for item in annotations
            if item.get("resolution", {}).get("resolved_track_index") == track_index
        ]
    if not include_unresolved:
        annotations = [
            item for item in annotations
            if item.get("resolution", {}).get("status") == "resolved"
        ]
    return {
        "project_id": store.project_id,
        "store_path": str(store.path),
        "count": len(annotations),
        "annotations": annotations,
    }


@mcp.tool()
def clear_track_annotation(
    ctx: Context,
    track_index: Optional[int] = None,
    annotation_id: Optional[str] = None,
) -> dict:
    """Clear a persistent track annotation by current track or annotation_id.

    Use annotation_id for ambiguous duplicate-name cases. Use track_index when
    the annotation resolves cleanly to the current regular track.
    """
    if (track_index is None) == (annotation_id is None):
        raise ValueError("Pass exactly one of track_index or annotation_id")
    if track_index is not None:
        _validate_track_index(track_index, allow_return=False, allow_master=False)

    session_info = _require_session_info(ctx)
    store = _annotation_store_for_session(session_info)
    annotations = resolve_annotations(session_info, store.list_annotations())
    if annotation_id is not None:
        targets = [
            item for item in annotations
            if item.get("annotation_id") == annotation_id
        ]
    else:
        targets = [
            item for item in annotations
            if item.get("resolution", {}).get("resolved_track_index") == track_index
        ]

    cleared = []
    for item in targets:
        item_id = item.get("annotation_id")
        if isinstance(item_id, str) and store.delete(item_id):
            cleared.append(item)

    return {
        "status": "ok",
        "project_id": store.project_id,
        "cleared_count": len(cleared),
        "cleared_annotations": cleared,
    }


@mcp.tool()
def verify_device_alive(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Check whether a loaded device is alive (BUG-2026-04-22 #19).

    Static health check based on get_device_info — no test note required.
    A device is considered DEAD when:
      - class_name contains "PluginDevice" (AU/VST) AND parameter_count <= 1
        (the shell loaded but the DSP engine crashed / wasn't activated)
      - health_flags contains "opaque_or_failed_plugin"

    Returns: {alive: bool, reason: str, parameter_count: int, class_name: str,
              health_flags: list, recommendation: str | None}

    The `recommendation` is a one-liner like "delete and load native
    alternative" when the device is dead. None when alive.
    """
    _validate_track_index(track_index)
    info = _get_ableton(ctx).send_command(
        "get_device_info", {"track_index": track_index, "device_index": device_index},
    )
    if not isinstance(info, dict):
        return {"alive": False, "reason": f"get_device_info returned non-dict: {info!r}"}

    class_name = str(info.get("class_name", ""))
    parameter_count = int(info.get("parameter_count", 0))
    health_flags = list(info.get("health_flags", []))

    if "PluginDevice" in class_name and parameter_count <= 1:
        return {
            "alive": False,
            "reason": (
                f"plugin_shell_no_dsp — class_name={class_name!r}, "
                f"parameter_count={parameter_count}. The plugin host loaded "
                f"the shell but the DSP engine did not activate (common "
                f"after a crash or unauthorized AU/VST)."
            ),
            "parameter_count": parameter_count,
            "class_name": class_name,
            "health_flags": health_flags,
            "recommendation": (
                "Delete this device and load a native Ableton alternative "
                "(Wavetable / Operator / Drift for synth, Reverb / Delay / "
                "Compressor for FX)."
            ),
        }

    if "opaque_or_failed_plugin" in health_flags:
        return {
            "alive": False,
            "reason": "health_flags reports opaque_or_failed_plugin",
            "parameter_count": parameter_count,
            "class_name": class_name,
            "health_flags": health_flags,
            "recommendation": "Delete and replace with a native alternative.",
        }

    return {
        "alive": True,
        "reason": "passes static health checks",
        "parameter_count": parameter_count,
        "class_name": class_name,
        "health_flags": health_flags,
        "recommendation": None,
    }


def _find_name_collisions(ctx: Context, name: str) -> list[int]:
    """Return track indices whose name exactly matches `name` (case-sensitive).

    BUG #5 fix (v1.20.2): downstream role-based resolvers like
    find_tracks_by_role match on track names. If create_midi_track
    creates a second "Pad" while another "Pad" already exists, mix
    moves like widen_stereo match BOTH — applying the change twice.
    This helper enables create_*_track to warn the caller so they can
    pick a unique name or explicitly accept the collision.

    Best-effort: returns [] when session_info can't be fetched —
    collision detection must never block creation.
    """
    try:
        info = _get_ableton(ctx).send_command("get_session_info")
    except Exception:
        return []
    if not isinstance(info, dict):
        return []
    tracks = info.get("tracks") or []
    matches: list[int] = []
    for t in tracks:
        if isinstance(t, dict) and t.get("name") == name:
            idx = t.get("index")
            if isinstance(idx, int):
                matches.append(idx)
    return matches


def _resolve_color_alias(
    color: Optional[int],
    color_index: Optional[int],
) -> Optional[int]:
    """BUG-2026-04-26#3: accept both `color` and `color_index` keywords.

    The track-creation tools used `color` while `set_track_color` used
    `color_index`. Callers writing parallel tool batches (create + paint
    in one shot) consistently picked the wrong name and lost a whole
    parallel batch to the validation error. This helper accepts either,
    rejects the conflict case, and returns the resolved value.
    """
    if color is not None and color_index is not None:
        if color != color_index:
            raise ValueError(
                "Pass either 'color' or 'color_index', not both with "
                f"different values (got color={color}, color_index={color_index})"
            )
        return color
    if color is not None:
        return color
    return color_index


@mcp.tool()
def create_midi_track(
    ctx: Context,
    index: int = -1,
    name: Optional[str] = None,
    color: Optional[int] = None,
    color_index: Optional[int] = None,
) -> dict:
    """Create a new MIDI track. index=-1 appends at end.

    `color` and `color_index` are accepted interchangeably (BUG-2026-04-26#3).
    Both reference Ableton's 0-69 color palette. Pass either; passing
    both with different values is rejected.

    Response (v1.20.2+): when `name` is provided, the response carries
    a ``name_collision`` bool and ``existing_tracks_with_same_name``
    list[int]. Downstream role-based resolvers (find_tracks_by_role)
    match duplicate names and apply mix changes twice — check the
    warning before proceeding with mix moves on the new track's role.
    """
    color = _resolve_color_alias(color, color_index)

    collisions: list[int] = []
    if name is not None and name.strip():
        collisions = _find_name_collisions(ctx, name)

    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color_index"] = color
    result = _get_ableton(ctx).send_command("create_midi_track", params)
    if isinstance(result, dict):
        # Always stamp both fields so callers can check unconditionally
        # (False + [] when no name provided or no collision).
        result["name_collision"] = bool(collisions)
        result["existing_tracks_with_same_name"] = collisions
    return result


@mcp.tool()
def create_audio_track(
    ctx: Context,
    index: int = -1,
    name: Optional[str] = None,
    color: Optional[int] = None,
    color_index: Optional[int] = None,
) -> dict:
    """Create a new audio track. index=-1 appends at end.

    `color` and `color_index` are accepted interchangeably (BUG-2026-04-26#3).
    See create_midi_track for full semantics.

    Response (v1.20.2+): ``name_collision`` + ``existing_tracks_with_same_name``
    same as create_midi_track — see BUG #5 rationale there.
    """
    color = _resolve_color_alias(color, color_index)

    collisions: list[int] = []
    if name is not None and name.strip():
        collisions = _find_name_collisions(ctx, name)

    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color_index"] = color
    result = _get_ableton(ctx).send_command("create_audio_track", params)
    if isinstance(result, dict):
        result["name_collision"] = bool(collisions)
        result["existing_tracks_with_same_name"] = collisions
    return result


@mcp.tool()
def create_return_track(ctx: Context) -> dict:
    """Create a new return track."""
    return _get_ableton(ctx).send_command("create_return_track")


@mcp.tool()
def delete_track(ctx: Context, track_index: int) -> dict:
    """Delete a track by index. Use undo to revert if needed.

    Ableton requires at least one track in the session. Attempting to
    delete the last remaining track raises ValueError with actionable
    guidance rather than surfacing Ableton's misleading default
    STATE_ERROR text (BUG-F3).
    """
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    session_info = ableton.send_command("get_session_info")
    track_count = session_info.get("track_count") if session_info else None
    if track_count is not None and track_count <= 1:
        raise ValueError(
            "Cannot delete track: Ableton requires at least one track "
            "in the session. Add another track first, or rename the "
            "current track if you want a clean slate."
        )
    return ableton.send_command("delete_track", {"track_index": track_index})


@mcp.tool()
def duplicate_track(ctx: Context, track_index: int) -> dict:
    """Duplicate a track (copies all clips, devices, and settings)."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("duplicate_track", {"track_index": track_index})


@mcp.tool()
def set_track_name(ctx: Context, track_index: int, name: str) -> dict:
    """Rename a track. The new name appears in both the Session and Arrangement views and survives session save."""
    _validate_track_index(track_index)
    if not name.strip():
        raise ValueError("Track name cannot be empty")
    return _get_ableton(ctx).send_command("set_track_name", {
        "track_index": track_index,
        "name": name,
    })


@mcp.tool()
def set_track_color(ctx: Context, track_index: int, color_index: int) -> dict:
    """Set track color (0-69, Ableton's color palette)."""
    _validate_track_index(track_index)
    _validate_color_index(color_index)
    return _get_ableton(ctx).send_command("set_track_color", {
        "track_index": track_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_track_mute(ctx: Context, track_index: int, muted: bool) -> dict:
    """Mute or unmute a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_mute", {
        "track_index": track_index,
        "mute": muted,
    })


@mcp.tool()
def set_track_solo(ctx: Context, track_index: int, solo: bool) -> dict:
    """Solo or unsolo a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_solo", {
        "track_index": track_index,
        "solo": solo,
    })


@mcp.tool()
def set_track_arm(ctx: Context, track_index: int, arm: bool) -> dict:
    """Arm or disarm a track for recording."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_arm", {
        "track_index": track_index,
        "arm": arm,
    })


@mcp.tool()
def stop_track_clips(ctx: Context, track_index: int) -> dict:
    """Stop all playing clips on a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("stop_track_clips", {"track_index": track_index})


@mcp.tool()
def set_group_fold(ctx: Context, track_index: int, folded: bool) -> dict:
    """Fold or unfold a group track to show/hide its children."""
    _validate_track_index(track_index, allow_return=False)
    return _get_ableton(ctx).send_command("set_group_fold", {
        "track_index": track_index,
        "folded": folded,
    })


@mcp.tool()
def set_track_input_monitoring(ctx: Context, track_index: int, state: int) -> dict:
    """Set input monitoring (0=In, 1=Auto, 2=Off). Only for regular tracks, not return tracks."""
    _validate_track_index(track_index, allow_return=False)
    if state not in (0, 1, 2):
        raise ValueError("Monitoring state must be 0=In, 1=Auto, or 2=Off")
    return _get_ableton(ctx).send_command("set_track_input_monitoring", {
        "track_index": track_index,
        "state": state,
    })


# ── Freeze / Flatten ────────────────────────────────────────────────────


@mcp.tool()
def freeze_track(ctx: Context, track_index: int) -> dict:
    """Freeze a track — render all devices to audio for CPU savings.

    Freeze is async in Ableton: this initiates the render and returns
    immediately. Poll get_freeze_status to check when it's done.
    Freezing a track that's already frozen is a no-op.

    Note: freeze() is not available via ControlSurface API in all Live
    versions. If this fails, use Ableton's Freeze Track menu command
    (Cmd+F on Mac) manually instead.
    """
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("freeze_track", {
        "track_index": track_index,
    })


@mcp.tool()
def flatten_track(ctx: Context, track_index: int) -> dict:
    """Flatten a frozen track — commit rendered audio permanently.

    Destructive: replaces all devices with the rendered audio file.
    The track must already be frozen. Use undo to revert.
    """
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("flatten_track", {
        "track_index": track_index,
    })


@mcp.tool()
def get_freeze_status(ctx: Context, track_index: int) -> dict:
    """Check if a track is frozen.

    Use after freeze_track to poll for completion, or before
    flatten_track to verify the track is ready to flatten.
    """
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_freeze_status", {
        "track_index": track_index,
    })


# ── Track long-tail primitives ──────────────────────────────────────────


@mcp.tool()
def jump_in_session_clip(ctx: Context, track_index: int, beats: float) -> dict:
    """Jump playhead within a running session clip, in beats from start."""
    _validate_track_index(track_index, allow_return=False)
    return _get_ableton(ctx).send_command("jump_in_session_clip", {
        "track_index": track_index,
        "beats": beats,
    })


@mcp.tool()
def get_track_performance_impact(ctx: Context, track_index: int) -> dict:
    """Read a track's CPU performance impact metric."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_track_performance_impact", {
        "track_index": track_index,
    })


@mcp.tool()
def get_appointed_device(ctx: Context) -> dict:
    """Return the Blue Hand (appointed/focused) device location as (track_index, device_index, track_name, device_name)."""
    return _get_ableton(ctx).send_command("get_appointed_device", {})

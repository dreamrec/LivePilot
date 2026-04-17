"""Project Brain build pipeline — orchestrates full state construction.

Pure computation, zero I/O.  MCP tool wrappers call this with
pre-fetched data from Ableton.
"""

from __future__ import annotations

from typing import Any, Optional

from .arrangement_graph import build_arrangement_graph
from .automation_graph import build_automation_graph
from .capability_graph import build_capability_graph
from .models import ProjectState
from .role_graph import build_role_graph
from .session_graph import build_session_graph


def build_project_state_from_data(
    session_info: dict,
    scenes: Optional[list[dict]] = None,
    clip_matrix: Optional[list[list[dict]]] = None,
    track_infos: Optional[list[dict]] = None,
    notes_map: Optional[dict[str, dict[int, list[dict]]]] = None,
    arrangement_clips: Optional[dict] = None,
    clip_automation: Optional[list[dict]] = None,
    analyzer_ok: bool = False,
    flucoma_ok: bool = False,
    plugin_health: Optional[dict[str, Any]] = None,
    session_ok: bool = True,
    memory_ok: bool = False,
    web_ok: bool = False,
    analyzer_fresh: bool = False,
    previous_revision: int = 0,
) -> ProjectState:
    """Build a full ProjectState from pre-fetched data.

    Args:
        session_info: raw get_session_info output.
        scenes: list of scene dicts for arrangement graph.
        clip_matrix: [scene_index][track_index] clip slot dicts.
        track_infos: list of per-track info dicts (devices, params).
        notes_map: {section_id: {track_index: [notes]}} for role inference.
        arrangement_clips: legacy dict of track_index -> clip list.
        analyzer_ok: whether M4L analyzer bridge is responding.
        flucoma_ok: whether FluCoMa is available.
        plugin_health: dict of plugin_name -> health info.
        session_ok: whether Ableton session is reachable.
        memory_ok: whether technique memory is available.
        web_ok: whether web research is available.
        analyzer_fresh: whether analyzer data is fresh.
        previous_revision: last known revision number.

    Returns:
        ProjectState with incremented revision and all subgraphs populated.
    """
    state = ProjectState()
    state.revision = previous_revision + 1

    # 1. Session graph (always built)
    state.session_graph = build_session_graph(session_info)
    state.session_graph.freshness.mark_fresh(state.revision)

    # 2. Arrangement graph
    track_count = len(session_info.get("tracks", []))

    if scenes and clip_matrix:
        # New path: real scene-based section inference
        state.arrangement_graph = build_arrangement_graph(
            scenes, clip_matrix, track_count,
        )
    elif arrangement_clips:
        # Legacy path: arrangement clips from per-track fetch
        from .models import ArrangementGraph, SectionNode
        arr = ArrangementGraph()
        sections = []
        for track_idx, clips in arrangement_clips.items():
            for clip in clips:
                sections.append(SectionNode(
                    section_id=f"t{track_idx}_c{clip.get('index', 0)}",
                    start_bar=int(clip.get("start_time", 0)),
                    end_bar=int(clip.get("end_time", 0)),
                    section_type=clip.get("name", "unknown"),
                ))
        arr.sections = sections
        state.arrangement_graph = arr
    # else: leave as default empty ArrangementGraph

    state.arrangement_graph.freshness.mark_fresh(state.revision)

    # 3. Role graph
    if state.arrangement_graph.sections and track_infos:
        section_dicts = [s.to_dict() for s in state.arrangement_graph.sections]
        state.role_graph = build_role_graph(
            sections=section_dicts,
            track_data=track_infos,
            notes_map=notes_map or {},
        )
    state.role_graph.freshness.mark_fresh(state.revision)

    # 4. Automation graph
    section_dicts_for_auto = (
        [s.to_dict() for s in state.arrangement_graph.sections]
        if state.arrangement_graph.sections else None
    )
    state.automation_graph = build_automation_graph(
        track_infos=track_infos or [],
        sections=section_dicts_for_auto,
        clip_automation=clip_automation or [],
    )
    state.automation_graph.freshness.mark_fresh(state.revision)

    # 5. Capability graph
    state.capability_graph = build_capability_graph(
        analyzer_ok=analyzer_ok,
        flucoma_ok=flucoma_ok,
        plugin_health=plugin_health,
        session_ok=session_ok,
        memory_ok=memory_ok,
        web_ok=web_ok,
        analyzer_fresh=analyzer_fresh,
    )
    state.capability_graph.freshness.mark_fresh(state.revision)

    return state

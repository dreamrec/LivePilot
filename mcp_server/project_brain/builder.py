"""Project Brain build pipeline — orchestrates full state construction.

Pure computation, zero I/O.  MCP tool wrappers call this with
pre-fetched data from Ableton.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    ArrangementGraph,
    AutomationGraph,
    CapabilityGraph,
    ProjectState,
    RoleGraph,
    SectionNode,
)
from .session_graph import build_session_graph


def build_project_state_from_data(
    session_info: dict,
    arrangement_clips: Optional[dict] = None,
    track_infos: Optional[list[dict]] = None,
    previous_revision: int = 0,
) -> ProjectState:
    """Build a full ProjectState from pre-fetched data.

    Args:
        session_info: raw get_session_info output.
        arrangement_clips: optional dict of track_index -> clip list.
        track_infos: optional list of per-track info dicts.
        previous_revision: last known revision number.

    Returns:
        ProjectState with incremented revision and all subgraphs populated.
    """
    state = ProjectState()
    state.revision = previous_revision + 1

    # 1. Session graph (always built)
    state.session_graph = build_session_graph(session_info)
    state.session_graph.freshness.mark_fresh(state.revision)

    # 2. Capability graph (placeholder — always built)
    state.capability_graph = CapabilityGraph()
    state.capability_graph.freshness.mark_fresh(state.revision)

    # 3. Arrangement graph (from clips if available)
    arr = ArrangementGraph()
    if arrangement_clips:
        sections: list[SectionNode] = []
        for track_idx, clips in arrangement_clips.items():
            for clip in clips:
                sections.append(SectionNode(
                    section_id=f"t{track_idx}_c{clip.get('index', 0)}",
                    start_bar=int(clip.get("start_time", 0)),
                    end_bar=int(clip.get("end_time", 0)),
                    section_type=clip.get("name", "unknown"),
                ))
        arr.sections = sections
    arr.freshness.mark_fresh(state.revision)
    state.arrangement_graph = arr

    # 4. Role graph (placeholder — needs deeper inference)
    role_graph = RoleGraph()
    role_graph.freshness.mark_fresh(state.revision)
    state.role_graph = role_graph

    # 5. Automation graph (placeholder — needs deeper inference)
    auto_graph = AutomationGraph()
    auto_graph.freshness.mark_fresh(state.revision)
    state.automation_graph = auto_graph

    return state

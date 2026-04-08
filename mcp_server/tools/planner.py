"""Planner MCP tools — loop-to-song arrangement planning.

2 tools that connect the planner engine (_planner_engine.py) to the
live Ableton session.

  plan_arrangement — transform a loop into a full arrangement blueprint
  get_emotional_arc — (in research.py, shares composition data)
"""

from __future__ import annotations

import json
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import _composition_engine as comp_engine
from . import _planner_engine as planner_engine


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def plan_arrangement(
    ctx: Context,
    target_bars: int = 128,
    style: str = "electronic",
) -> dict:
    """Transform the current loop/session into a full arrangement blueprint.

    Analyzes the existing tracks and their roles, then proposes:
    - Section sequence (intro → verse → build → drop → etc.)
    - Element reveal order (what enters/exits when)
    - Gesture automation suggestions for transitions
    - Orchestration plan (which tracks play in which sections)

    target_bars: desired total arrangement length (default: 128 bars)
    style: electronic | hiphop | pop | ambient | techno

    Returns: full ArrangementPlan with actionable section-by-section instructions.
    """
    if style not in planner_engine.VALID_STYLES:
        return {"error": f"Unknown style '{style}'. Valid: {sorted(planner_engine.VALID_STYLES)}"}

    ableton = _get_ableton(ctx)

    # 1. Get session info
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    tracks = session.get("tracks", [])
    track_count = session.get("track_count", 0)

    # 2. Build section graph (to analyze current state)
    from .composition import _build_clip_matrix
    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = comp_engine.build_section_graph_from_scenes(scenes, clip_matrix, track_count)

    # 3. Get track info for role inference
    track_data = []
    notes_map: dict[str, dict[int, list]] = {}

    for track in tracks:
        t_idx = track["index"]
        try:
            ti = ableton.send_command("get_track_info", {"track_index": t_idx})
            track_data.append(ti)
        except Exception:
            track_data.append({"index": t_idx, "name": track.get("name", ""), "devices": []})

    for section in sections:
        notes_map[section.section_id] = {}
        for t_idx in section.tracks_active:
            notes_map[section.section_id][t_idx] = []

    # 4. Build role graph
    roles = comp_engine.build_role_graph(sections, track_data, notes_map)

    # 5. Analyze loop identity
    loop_identity = planner_engine.analyze_loop_identity(roles, sections)

    # 6. Plan arrangement
    plan = planner_engine.plan_arrangement_from_loop(
        loop_identity,
        target_duration_bars=target_bars,
        style=style,
    )

    result = plan.to_dict()
    result["loop_identity"] = loop_identity.to_dict()
    result["available_styles"] = sorted(planner_engine.VALID_STYLES)
    return result

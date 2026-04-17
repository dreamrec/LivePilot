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
import logging

logger = logging.getLogger(__name__)


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
        except Exception as exc:
            logger.debug("plan_arrangement failed: %s", exc)
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

    # Add section-level sample role hints
    planner_engine.add_sample_hints(plan)

    result = plan.to_dict()
    result["loop_identity"] = loop_identity.to_dict()
    result["available_styles"] = sorted(planner_engine.VALID_STYLES)
    return result

# ── transform_section (Round 4) ─────────────────────────────────────


@mcp.tool()
def transform_section(
    ctx: Context,
    transformation: str,
    section_index: int = -1,
    bars: int = 8,
) -> dict:
    """Apply a structural transformation to the arrangement.

    Proposes radical structural moves — reorder sections, expand loops,
    compress verbose arrangements, insert bridges. Returns the proposed
    new section graph without modifying the actual session.

    transformation: insert_bridge_before_final_chorus | swap_verse_positions |
                    extend_section | compress_section | insert_breakdown |
                    duplicate_section | remove_section | reverse_section_order |
                    split_section
    section_index: which section to transform (required for targeted operations, -1 = auto)
    bars: how many bars for extend/compress/insert operations

    Returns: before/after section graphs with description and bar delta.
    """
    from . import _form_engine as form_engine

    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    track_count = session.get("track_count", 0)

    from .composition import _build_clip_matrix

    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = comp_engine.build_section_graph_from_scenes(scenes, clip_matrix, track_count)

    if not sections:
        return {"error": "No sections detected in the arrangement"}

    target = section_index if section_index >= 0 else None

    try:
        result = form_engine.transform_section_order(
            sections, transformation, target_index=target, bars=bars,
        )
        return result.to_dict()
    except ValueError as e:
        return {"error": str(e)}

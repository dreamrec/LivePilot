"""Musical intelligence MCP tools — song-level analysis and critique.

4 tools that look beyond parameters into musical meaning:
  detect_repetition_fatigue — is the arrangement getting stale?
  detect_role_conflicts — are tracks fighting for the same space?
  infer_section_purposes — what is each section trying to do?
  score_emotional_arc — does the song have a satisfying arc?
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import detectors


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def detect_repetition_fatigue(ctx: Context) -> dict:
    """Detect repetition fatigue — are patterns overused?

    Analyzes clip reuse across scenes, motif overuse, and section staleness.
    Returns fatigue level (0=fresh, 1=stale), specific issues, and recommendations.

    Use this when the track "feels repetitive" or when arrangement
    has been looping without variation.
    """
    ableton = _get_ableton(ctx)

    # Get scene matrix for clip reuse analysis
    try:
        matrix = ableton.send_command("get_scene_matrix")
    except Exception:
        matrix = {}

    scenes = []
    for i, scene_data in enumerate(matrix.get("scenes", [])):
        row = matrix.get("matrix", [[]])[i] if i < len(matrix.get("matrix", [])) else []
        scenes.append({
            "name": scene_data.get("name", f"Scene {i}"),
            "clips": row,
        })

    # Try to get motif graph for deeper analysis
    motif_graph = None
    try:
        motif_graph = ableton.send_command("get_motif_graph")
    except Exception:
        pass

    report = detectors.detect_repetition_fatigue(scenes, motif_graph)
    return report.to_dict()


@mcp.tool()
def detect_role_conflicts(ctx: Context) -> dict:
    """Detect role conflicts — are tracks fighting for the same musical space?

    Checks for: multiple bass tracks, competing leads, overlapping drum layers.
    Also flags missing essential roles (no bass, no drums).

    Returns conflict list with severity and recommendations.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    tracks = session.get("tracks", [])

    conflicts = detectors.detect_role_conflicts(tracks)
    return {
        "conflicts": [c.to_dict() for c in conflicts],
        "conflict_count": len(conflicts),
        "track_count": len(tracks),
    }


@mcp.tool()
def infer_section_purposes(ctx: Context) -> dict:
    """Infer what each section/scene is trying to do musically.

    Labels each scene as: setup, tension, payoff, contrast, release,
    development, or outro — based on density, position, and energy changes.

    Use this to understand the song's structure before making arrangement decisions.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    total_tracks = session.get("track_count", 6)

    # Get scene matrix for density analysis
    try:
        matrix = ableton.send_command("get_scene_matrix")
    except Exception:
        matrix = {}

    scenes = []
    for i, scene_data in enumerate(matrix.get("scenes", [])):
        row = matrix.get("matrix", [[]])[i] if i < len(matrix.get("matrix", [])) else []
        scenes.append({
            "name": scene_data.get("name", f"Scene {i}"),
            "clips": row,
        })

    purposes = detectors.infer_section_purposes(scenes, total_tracks)
    return {
        "sections": [p.to_dict() for p in purposes],
        "section_count": len(purposes),
        "purpose_summary": {p.purpose: sum(1 for s in purposes if s.purpose == p.purpose)
                           for p in purposes},
    }


@mcp.tool()
def score_emotional_arc(ctx: Context) -> dict:
    """Score the emotional arc of the arrangement.

    Measures: arc clarity (build→climax→resolve), contrast between sections,
    payoff strength (does the climax feel earned?), and resolution (does it end well?).

    Returns an overall score (0-1) and specific issues with recommendations.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    total_tracks = session.get("track_count", 6)

    try:
        matrix = ableton.send_command("get_scene_matrix")
    except Exception:
        matrix = {}

    scenes = []
    for i, scene_data in enumerate(matrix.get("scenes", [])):
        row = matrix.get("matrix", [[]])[i] if i < len(matrix.get("matrix", [])) else []
        scenes.append({
            "name": scene_data.get("name", f"Scene {i}"),
            "clips": row,
        })

    purposes = detectors.infer_section_purposes(scenes, total_tracks)
    arc = detectors.score_emotional_arc(purposes)
    return arc.to_dict()

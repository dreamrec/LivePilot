"""Project Brain MCP tools — build and query the shared state substrate.

2 tools:
  build_project_brain — full build from live Ableton session
  get_project_brain_summary — lightweight summary without full rebuild
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from .builder import build_project_state_from_data


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def build_project_brain(ctx: Context) -> dict:
    """Build a full Project Brain snapshot from the current Ableton session.

    Gathers session info, builds all five subgraphs (session, arrangement,
    role, automation, capability), and returns the canonical project state.

    This is the primary entry point for engines that need a coherent view
    of the project. Call once at session start, then use scoped refreshes.
    """
    ableton = _get_ableton(ctx)

    # 1. Get session info
    session_info = ableton.send_command("get_session_info")

    # 2. Gather arrangement clips per track
    arrangement_clips = {}
    tracks = session_info.get("tracks", [])
    for track in tracks:
        try:
            arr = ableton.send_command("get_arrangement_clips", {
                "track_index": track["index"],
            })
            clips = arr.get("clips", [])
            if clips:
                arrangement_clips[track["index"]] = clips
        except Exception:
            pass

    # 3. Build state
    state = build_project_state_from_data(
        session_info=session_info,
        arrangement_clips=arrangement_clips,
        previous_revision=0,
    )

    return state.to_dict()


@mcp.tool()
def get_project_brain_summary(ctx: Context) -> dict:
    """Get a lightweight Project Brain summary — track count, section count, stale status.

    Faster than build_project_brain when you just need an overview.
    Builds session graph only, skips deep inference.
    """
    ableton = _get_ableton(ctx)
    session_info = ableton.send_command("get_session_info")

    state = build_project_state_from_data(
        session_info=session_info,
        previous_revision=0,
    )

    return {
        "project_id": state.project_id,
        "revision": state.revision,
        "track_count": len(state.session_graph.tracks),
        "return_track_count": len(state.session_graph.return_tracks),
        "scene_count": len(state.session_graph.scenes),
        "section_count": len(state.arrangement_graph.sections),
        "tempo": state.session_graph.tempo,
        "time_signature": state.session_graph.time_signature,
        "is_stale": state.is_stale(),
    }

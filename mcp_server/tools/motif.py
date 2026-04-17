"""Motif MCP tools — pattern detection and transformation.

2 tools: get_motif_graph (detect patterns) and transform_motif (apply transformations).
"""

from __future__ import annotations

import json

from fastmcp import Context

from ..server import mcp
from . import _motif_engine as motif_engine
import logging

logger = logging.getLogger(__name__)



def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def get_motif_graph(ctx: Context) -> dict:
    """Detect recurring melodic and rhythmic patterns across all tracks.

    Scans note data from all session clips to find repeated interval
    patterns. Returns motifs sorted by salience (most memorable first),
    with occurrence locations, fatigue risk, and suggested transformations.

    Use this to understand what musical ideas are present and which
    ones need development or variation.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    tracks = session.get("tracks", [])

    # Collect notes from all tracks and clips
    notes_by_track: dict[int, list[dict]] = {}
    for track in tracks:
        t_idx = track["index"]
        if not track.get("has_midi_input", False):
            continue
        track_notes = []
        for clip_idx in range(session.get("scene_count", 8)):
            try:
                result = ableton.send_command("get_notes", {
                    "track_index": t_idx,
                    "clip_index": clip_idx,
                })
                track_notes.extend(result.get("notes", []))
            except Exception as exc:
                logger.debug("get_motif_graph failed: %s", exc)

        if track_notes:
            notes_by_track[t_idx] = track_notes

    motifs = motif_engine.detect_motifs(notes_by_track)

    return {
        "motifs": [m.to_dict() for m in motifs],
        "motif_count": len(motifs),
        "tracks_analyzed": len(notes_by_track),
    }


@mcp.tool()
def transform_motif(
    ctx: Context,
    motif_intervals: list | str,
    transformation: str,
    reference_pitch: int = 60,
) -> dict:
    """Transform a musical motif using classical composition techniques.

    motif_intervals: interval pattern (list of semitone distances, e.g., [2, -1, 3])
                     Get this from get_motif_graph → motif.intervals
    transformation: inversion | retrograde | augmentation | diminution |
                    fragmentation | register_shift_up | register_shift_down
    reference_pitch: starting MIDI pitch for output (default: C4=60)

    Returns: list of notes ready for add_notes.

    Example: transform_motif([2, 2, -1, 2], "inversion", 60)
    → notes descending instead of ascending
    """
    if isinstance(motif_intervals, str):
        try:
            motif_intervals = json.loads(motif_intervals)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in motif_intervals: {exc}") from exc

    # Build a temporary MotifUnit for the transformation
    motif = motif_engine.MotifUnit(
        motif_id="transform_input",
        kind="melodic",
        intervals=motif_intervals,
        rhythm=[],
        representative_pitches=[reference_pitch],
    )

    notes = motif_engine.transform_motif(motif, transformation, reference_pitch)
    return {
        "notes": notes,
        "note_count": len(notes),
        "transformation": transformation,
        "original_intervals": motif_intervals,
    }

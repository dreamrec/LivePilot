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
def get_motif_graph(
    ctx: Context,
    limit: int = 50,
    offset: int = 0,
    summary_only: bool = False,
) -> dict:
    """Detect recurring melodic and rhythmic patterns across all tracks.

    Scans note data from all session clips to find repeated interval
    patterns. Returns motifs sorted by salience (most memorable first),
    with occurrence locations, fatigue risk, and suggested transformations.

    Use this to understand what musical ideas are present and which
    ones need development or variation.

    BUG-B7 fix: sessions with many clips produced 90 KB+ payloads that
    exceeded inline-tool-response limits. Callers now page the list and
    can opt into a compact summary view that drops per-motif occurrence
    arrays and suggested_developments.

    Args:
        limit: maximum motifs returned per call (default 50, max 500).
        offset: skip this many of the highest-salience motifs (for paging).
        summary_only: return only motif_id + kind + salience + fatigue_risk
                      + occurrence_count per motif, dropping occurrences
                      and other lists. Use when you need a bird's-eye view.
    """
    # Cheap input validation — these bounds match the tool contract the
    # rest of the server relies on for inline responses.
    if limit < 0:
        raise ValueError("limit must be >= 0")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    limit = min(limit, 500)

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
    total = len(motifs)
    page = motifs[offset:offset + limit] if limit > 0 else []

    if summary_only:
        # Compact per-motif record: keep identity + scoring signals, drop
        # occurrences / developments / pitch/rhythm payloads that balloon
        # the response on complex sessions.
        motif_dicts = [{
            "motif_id": m.motif_id,
            "kind": m.kind,
            "salience": m.salience,
            "fatigue_risk": m.fatigue_risk,
            "occurrence_count": len(m.occurrences),
        } for m in page]
    else:
        motif_dicts = [m.to_dict() for m in page]

    return {
        "motifs": motif_dicts,
        "motif_count": len(motif_dicts),
        "total_motifs": total,
        "offset": offset,
        "limit": limit,
        "summary_only": summary_only,
        "has_more": offset + len(motif_dicts) < total,
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

"""Shared motif service — one entry point for all motif consumers.

SongBrain, HookHunter, and musical_intelligence all import from here
instead of making ad-hoc calls to the motif engine or TCP.

Pure computation — no I/O. Callers provide pre-fetched data.
"""

from __future__ import annotations

from typing import Optional
import logging

logger = logging.getLogger(__name__)


def get_motif_data(
    notes_by_track: dict[int, list[dict]],
) -> dict:
    """Extract motif data from pre-fetched notes.

    Args:
        notes_by_track: {track_index: [note_dicts]} from get_notes calls

    Returns:
        Motif analysis dict with motifs, motif_count, tracks_analyzed.
        Returns empty result if no notes or engine unavailable.
    """
    if not notes_by_track:
        return {"motifs": [], "motif_count": 0, "tracks_analyzed": 0}

    try:
        from ..tools import _motif_engine as motif_engine

        motifs = motif_engine.detect_motifs(notes_by_track)
        return {
            "motifs": [m.to_dict() for m in motifs],
            "motif_count": len(motifs),
            "tracks_analyzed": len(notes_by_track),
        }
    except Exception as exc:
        logger.debug("get_motif_data failed: %s", exc)
        return {"motifs": [], "motif_count": 0, "tracks_analyzed": 0}


def fetch_notes_from_ableton(ableton, tracks: list[dict], max_clips: int = 8) -> dict[int, list[dict]]:
    """Fetch notes from Ableton for motif analysis.

    This is the I/O helper — calls get_notes through valid TCP commands.
    Callers pass the ableton connection; this function does the fetching.
    """
    notes_by_track: dict[int, list[dict]] = {}
    for track in tracks:
        t_idx = track.get("index", 0)
        if not track.get("has_midi_input", False) and not any(
            kw in track.get("name", "").lower()
            for kw in ("midi", "synth", "bass", "lead", "pad", "keys", "piano", "chord")
        ):
            continue
        track_notes = []
        for clip_idx in range(max_clips):
            try:
                result = ableton.send_command("get_notes", {
                    "track_index": t_idx,
                    "clip_index": clip_idx,
                })
                track_notes.extend(result.get("notes", []))
            except Exception as exc:
                logger.debug("fetch_notes_from_ableton failed: %s", exc)

        if track_notes:
            notes_by_track[t_idx] = track_notes
    return notes_by_track

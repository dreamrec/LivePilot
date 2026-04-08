"""Session graph builder — transforms raw get_session_info into SessionGraph.

Pure computation, zero I/O.
"""

from __future__ import annotations

from .models import FreshnessInfo, SessionGraph, TrackNode


def build_session_graph(session_info: dict) -> SessionGraph:
    """Build a SessionGraph from raw get_session_info output.

    Args:
        session_info: dict from Ableton's get_session_info command.

    Returns:
        Populated SessionGraph with freshness marked fresh (revision 0).
    """
    graph = SessionGraph()

    # Tracks
    for raw in session_info.get("tracks", []):
        track = TrackNode(
            index=raw.get("index", 0),
            name=raw.get("name", ""),
            has_midi=raw.get("has_midi_input", False) or raw.get("has_midi", False),
            has_audio=raw.get("has_audio_input", False) or raw.get("has_audio", False),
            mute=raw.get("mute", False),
            solo=raw.get("solo", False),
            arm=raw.get("arm", False),
            group_index=raw.get("group_track_index", None),
        )
        graph.add_track(track)

    # Return tracks
    graph.return_tracks = session_info.get("return_tracks", [])

    # Scenes
    graph.scenes = session_info.get("scenes", [])

    # Tempo & time signature
    graph.tempo = session_info.get("tempo", 120.0)
    ts_num = session_info.get("time_signature_numerator", 4)
    ts_den = session_info.get("time_signature_denominator", 4)
    graph.time_signature = f"{ts_num}/{ts_den}"

    # Mark fresh
    graph.freshness.mark_fresh(revision=0)

    return graph

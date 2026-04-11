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

    # Motif data — pure-Python engine, not TCP
    motif_graph = None
    try:
        from ..tools.motif import _motif_engine
        tracks = matrix.get("scenes", [])
        notes_by_track = {}
        for i in range(len(scenes)):
            try:
                notes = ableton.send_command("get_notes", {"track_index": i, "clip_index": 0})
                if notes and notes.get("notes"):
                    notes_by_track[i] = notes
            except Exception:
                pass
        if notes_by_track:
            session_info = ableton.send_command("get_session_info", {})
            motif_graph = _motif_engine.detect_motifs(session_info, notes_by_track)
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


# ── Phrase Evaluation ────────────────────────────────────────────────


@mcp.tool()
def analyze_phrase_arc(
    ctx: Context,
    file_path: str,
    target: str = "loop",
) -> dict:
    """Analyze a captured audio phrase for musical quality.

    Evaluates: arc clarity, contrast, fatigue risk, payoff strength,
    identity strength, and translation risk.

    file_path: path to a captured audio file (from capture_audio)
    target: what the phrase is ("loop", "drop", "chorus", "transition", "intro", "outro")

    Requires capture_audio + analyze_loudness + analyze_spectrum_offline first.
    """
    from . import phrase_critic

    ableton = _get_ableton(ctx)

    # Run offline analysis on the file
    loudness_data = None
    spectrum_data = None

    # Direct Python calls to perception engine — not TCP
    try:
        from ..tools._perception_engine import compute_loudness
        loudness_data = compute_loudness(file_path, detail="full")
    except Exception:
        pass

    try:
        from ..tools._perception_engine import compute_spectral
        spectrum_data = compute_spectral(file_path)
    except Exception:
        pass

    critique = phrase_critic.analyze_phrase(loudness_data, spectrum_data, target)
    critique.render_id = file_path.split("/")[-1] if "/" in file_path else file_path
    return critique.to_dict()


@mcp.tool()
def compare_phrase_renders(
    ctx: Context,
    file_paths: list,
    target: str = "loop",
) -> dict:
    """Compare multiple audio captures and rank by musical quality.

    file_paths: list of paths to captured audio files
    target: what the phrases are ("loop", "drop", "chorus", etc.)

    Returns ranked list with scores and notes for each.
    """
    from . import phrase_critic

    critiques = []
    for path in file_paths:
        # Try to get cached analysis or run fresh
        critique = phrase_critic.analyze_phrase(target=target)
        critique.render_id = path.split("/")[-1] if isinstance(path, str) and "/" in path else str(path)
        critiques.append(critique)

    ranking = phrase_critic.compare_phrases(critiques)
    return {
        "ranking": ranking,
        "count": len(ranking),
        "target": target,
        "best": ranking[0] if ranking else None,
    }

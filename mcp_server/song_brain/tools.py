"""SongBrain MCP tools — 3 tools for song identity modeling.

  build_song_brain — construct the musical identity of the current piece
  explain_song_identity — human-readable summary of what the song is about
  detect_identity_drift — compare before/after to detect identity damage
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import builder
from .models import SongBrain


# Module-level cache for the most recent SongBrain
_current_brain: SongBrain | None = None


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _fetch_session_data(ctx: Context) -> dict:
    """Fetch all available session data for brain building.

    Populates real data from Ableton and pure-computation modules:
    - motif_data: from get_motif_graph (motif engine)
    - composition_analysis: from musical intelligence section inference
    - role_graph: from semantic move resolvers (track role inference)
    - recent_moves: from session-scoped action ledger
    """
    ableton = _get_ableton(ctx)
    data: dict = {
        "session_info": {},
        "scenes": [],
        "tracks": [],
        "motif_data": {},
        "composition_analysis": {},
        "role_graph": {},
        "recent_moves": [],
    }

    try:
        data["session_info"] = ableton.send_command("get_session_info", {})
    except Exception:
        data["session_info"] = {"tempo": 120.0, "track_count": 0}

    try:
        matrix = ableton.send_command("get_scene_matrix")
        data["scenes"] = [
            {"name": s.get("name", f"Scene {i}"), "clips": row}
            for i, (s, row) in enumerate(
                zip(matrix.get("scenes", []), matrix.get("matrix", []))
            )
        ]
    except Exception:
        pass

    try:
        info = data["session_info"]
        tracks_list = info.get("tracks", [])
        data["tracks"] = tracks_list if isinstance(tracks_list, list) else []
    except Exception:
        pass

    # Motif data — from the motif engine if notes exist
    try:
        data["motif_data"] = ableton.send_command("get_motif_graph")
    except Exception:
        pass  # Motif graph requires notes in clips; empty is valid

    # Composition analysis — from musical intelligence detectors (pure computation)
    try:
        from ..musical_intelligence import detectors
        total_tracks = data["session_info"].get("track_count", 6)
        purposes = detectors.infer_section_purposes(data["scenes"], total_tracks)
        arc = detectors.score_emotional_arc(purposes)
        data["composition_analysis"] = {
            "sections": [p.to_dict() for p in purposes],
            "emotional_arc": arc.to_dict(),
        }
    except Exception:
        pass

    # Role graph — from semantic move resolvers (pure computation, no I/O)
    try:
        from ..semantic_moves.resolvers import infer_role
        roles = {}
        for track in data["tracks"]:
            name = track.get("name", "")
            role = infer_role(name)
            roles[name] = {"index": track.get("index", 0), "role": role}
        data["role_graph"] = roles
    except Exception:
        pass

    # Recent moves — from session-scoped action ledger
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger = ctx.lifespan_context.get("action_ledger")
        if isinstance(ledger, SessionLedger):
            recent = ledger.get_recent_moves(limit=10)
            data["recent_moves"] = [e.to_dict() for e in recent]
    except Exception:
        pass

    return data


@mcp.tool()
def build_song_brain(ctx: Context) -> dict:
    """Build the musical identity model for the current song.

    Analyzes the session to identify:
    - identity_core: the strongest defining idea
    - sacred_elements: motifs/textures/grooves that must be preserved
    - section_purposes: what each section is trying to do emotionally
    - energy_arc: rise/fall shape across sections
    - open_questions: what the song has not resolved yet

    Call this at the start of complex creative workflows.
    Returns the full SongBrain as a dict.
    """
    global _current_brain

    data = _fetch_session_data(ctx)
    brain = builder.build_song_brain(
        session_info=data["session_info"],
        scenes=data["scenes"],
        tracks=data["tracks"],
        motif_data=data["motif_data"],
        composition_analysis=data["composition_analysis"],
        role_graph=data["role_graph"],
        recent_moves=data["recent_moves"],
    )
    _current_brain = brain

    return {
        **brain.to_dict(),
        "summary": brain.summary,
    }


@mcp.tool()
def explain_song_identity(ctx: Context) -> dict:
    """Explain the current song's identity in human musical language.

    If no SongBrain exists yet, builds one first. Returns a structured
    explanation suitable for the agent to talk about the song naturally.
    """
    global _current_brain

    if _current_brain is None:
        data = _fetch_session_data(ctx)
        _current_brain = builder.build_song_brain(
            session_info=data["session_info"],
            scenes=data["scenes"],
            tracks=data["tracks"],
            motif_data=data["motif_data"],
            composition_analysis=data["composition_analysis"],
            role_graph=data["role_graph"],
            recent_moves=data["recent_moves"],
        )

    brain = _current_brain
    explanation: dict = {
        "identity": brain.identity_core,
        "confidence": brain.identity_confidence,
    }

    # Sacred elements in natural language
    if brain.sacred_elements:
        explanation["protect"] = [
            f"{e.element_type}: {e.description}" for e in brain.sacred_elements
        ]
    else:
        explanation["protect"] = ["No clearly sacred elements detected yet"]

    # What each section does
    if brain.section_purposes:
        explanation["sections"] = [
            f"{s.label} — {s.emotional_intent} (energy {s.energy_level:.0%})"
            for s in brain.section_purposes
        ]

    # Energy shape
    if brain.energy_arc:
        arc = brain.energy_arc
        if len(arc) >= 3:
            peak_idx = arc.index(max(arc))
            peak_pct = peak_idx / max(len(arc) - 1, 1)
            if peak_pct < 0.3:
                explanation["energy_shape"] = "front-loaded — peaks early"
            elif peak_pct > 0.7:
                explanation["energy_shape"] = "slow burn — builds to late peak"
            else:
                explanation["energy_shape"] = "centered arc — peaks in the middle"
        else:
            explanation["energy_shape"] = "short form — limited arc data"

    # Open questions
    if brain.open_questions:
        explanation["open_questions"] = [q.question for q in brain.open_questions]

    # Drift warning
    if brain.identity_drift_risk > 0.3:
        explanation["warning"] = (
            f"Identity drift risk is {brain.identity_drift_risk:.0%} — "
            "recent edits may be moving the song away from itself"
        )

    explanation["summary"] = brain.summary
    return explanation


@mcp.tool()
def detect_identity_drift(
    ctx: Context,
    before_brain_id: str = "",
) -> dict:
    """Detect whether recent changes have damaged the song's identity.

    Compares the current state against the cached SongBrain.
    If no previous brain exists, builds both and reports baseline.

    before_brain_id: optional — if empty, uses the last cached brain.

    Returns drift score, changed elements, sacred damage, and recommendation.
    """
    global _current_brain

    before = _current_brain

    # Build fresh brain from current state
    data = _fetch_session_data(ctx)
    after = builder.build_song_brain(
        session_info=data["session_info"],
        scenes=data["scenes"],
        tracks=data["tracks"],
        motif_data=data["motif_data"],
        composition_analysis=data["composition_analysis"],
        role_graph=data["role_graph"],
        recent_moves=data["recent_moves"],
    )

    if before is None:
        _current_brain = after
        return {
            "drift_score": 0.0,
            "note": "No previous brain to compare — this is the baseline",
            "brain_id": after.brain_id,
            "recommendation": "safe",
        }

    drift = builder.detect_identity_drift(before, after)
    _current_brain = after

    return {
        **drift.to_dict(),
        "before_brain_id": before.brain_id,
        "after_brain_id": after.brain_id,
    }

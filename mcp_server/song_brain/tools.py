"""SongBrain MCP tools — 3 tools for song identity modeling.

  build_song_brain — construct the musical identity of the current piece
  explain_song_identity — human-readable summary of what the song is about
  detect_identity_drift — compare before/after to detect identity damage
"""

from __future__ import annotations

from fastmcp import Context

from ..runtime.degradation import DegradationInfo
from ..server import mcp
from . import builder
from .models import SongBrain
import logging

logger = logging.getLogger(__name__)

# Module-level fallback for consumers without ctx.
# Prefer ctx.lifespan_context["current_brain"] when ctx is available.
_current_brain: SongBrain | None = None

# Snapshot store: brain_id -> SongBrain, max 10 snapshots
_brain_snapshots: dict[str, SongBrain] = {}
_MAX_SNAPSHOTS = 10


def _set_brain(ctx: Context, brain: SongBrain) -> None:
    """Store brain in lifespan_context, module fallback, and snapshot store."""
    global _current_brain
    _current_brain = brain
    ctx.lifespan_context["current_brain"] = brain
    # Save snapshot for later drift comparison
    _brain_snapshots[brain.brain_id] = brain
    # Evict oldest if over limit
    while len(_brain_snapshots) > _MAX_SNAPSHOTS:
        oldest_key = next(iter(_brain_snapshots))
        del _brain_snapshots[oldest_key]


def _get_snapshot(brain_id: str) -> SongBrain | None:
    """Retrieve a past brain snapshot by ID."""
    return _brain_snapshots.get(brain_id)


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _fetch_session_data(ctx: Context) -> dict:
    """Fetch all available session data for brain building.

    Populates real data from Ableton and pure-computation modules:
    - motif_data: from get_motif_graph (motif engine)
    - composition_analysis: from musical intelligence section inference
    - role_graph: from semantic move resolvers (track role inference)
    - recent_moves: from session-scoped action ledger

    On session-fetch failure the fallback session_info shape is injected
    (``tempo=120.0, track_count=0``) and a ``DegradationInfo`` is attached
    under the ``_degradation`` key so callers can tell synthesized data
    from real data. ``_fetch_session_data`` never raises — it always
    returns a dict with the expected keys.
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
    degradation = DegradationInfo()

    try:
        data["session_info"] = ableton.send_command("get_session_info", {})
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)
        data["session_info"] = {"tempo": 120.0, "track_count": 0}
        degradation.is_degraded = True
        if "session_fetch_failed" not in degradation.reasons:
            degradation.reasons.append("session_fetch_failed")
        for fld in ("tempo", "track_count"):
            if fld not in degradation.substituted_fields:
                degradation.substituted_fields.append(fld)

    try:
        matrix = ableton.send_command("get_scene_matrix")
        data["scenes"] = [
            {"name": s.get("name", f"Scene {i}"), "clips": row}
            for i, (s, row) in enumerate(
                zip(matrix.get("scenes", []), matrix.get("matrix", []))
            )
        ]
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)

    try:
        info = data["session_info"]
        tracks_list = info.get("tracks", [])
        data["tracks"] = tracks_list if isinstance(tracks_list, list) else []
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)

    # Motif data — via shared motif service (pure-Python, not TCP)
    try:
        from ..services.motif_service import get_motif_data, fetch_notes_from_ableton
        notes_by_track = fetch_notes_from_ableton(ableton, data.get("tracks", []))
        data["motif_data"] = get_motif_data(notes_by_track)
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)
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
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)

    # Role graph — from semantic move resolvers (pure computation, no I/O)
    try:
        from ..semantic_moves.resolvers import infer_role
        roles = {}
        for track in data["tracks"]:
            name = track.get("name", "")
            role = infer_role(name)
            roles[name] = {"index": track.get("index", 0), "role": role}
        data["role_graph"] = roles
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)

    # store_purpose: anti_repetition
    # song_brain's _fetch_session_data surfaces recent moves into the
    # brain's context so section analysis can detect repeated work
    # patterns. Recency signal — NOT the persistent technique library.
    # Correct store: SessionLedger.get_recent_moves (v1.20 director SKILL
    # previously pointed at memory_list for this, which was wrong).
    # Recent moves — from session-scoped action ledger
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger = ctx.lifespan_context.get("action_ledger")
        if isinstance(ledger, SessionLedger):
            recent = ledger.get_recent_moves(limit=10)
            data["recent_moves"] = [e.to_dict() for e in recent]
    except Exception as exc:
        logger.debug("_fetch_session_data failed: %s", exc)

    # Attach the degradation signal so build_song_brain can surface it.
    # Under a reserved key (leading underscore) so it never collides with
    # a real session data field.
    data["_degradation"] = degradation
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
    data = _fetch_session_data(ctx)

    # Capability reporting — what data was actually available
    from ..runtime.capability import build_capability

    cap = build_capability(
        required=["session_info", "scenes", "tracks", "motif_data", "composition_analysis", "role_graph"],
        available={
            "session_info": bool(data.get("session_info", {}).get("tempo")),
            "scenes": bool(data.get("scenes")),
            "tracks": bool(data.get("tracks")),
            "motif_data": bool(data.get("motif_data")),
            "composition_analysis": bool(data.get("composition_analysis")),
            "role_graph": bool(data.get("role_graph")),
        },
    )

    brain = builder.build_song_brain(
        session_info=data["session_info"],
        scenes=data["scenes"],
        tracks=data["tracks"],
        motif_data=data["motif_data"],
        composition_analysis=data["composition_analysis"],
        role_graph=data["role_graph"],
        recent_moves=data["recent_moves"],
    )
    _set_brain(ctx, brain)

    # Surface the degradation payload so callers can distinguish a
    # tempo=120 / track_count=0 synthesized response from a real one.
    degradation = data.get("_degradation") or DegradationInfo()

    return {
        **brain.to_dict(),
        "summary": brain.summary,
        "capability": cap.to_dict(),
        "degradation": degradation.to_dict(),
    }


def classify_energy_shape(arc: list[float]) -> dict:
    """Classify the shape of an energy arc for user-facing explanation.

    BUG-B13 fix: the old single-max-position classifier labeled
    [0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4] (peaks at 1-2 AND 5) as
    "front-loaded" because max()'s first occurrence is at index 1.
    We now find ALL peaks above a dynamic threshold and classify by
    count + distribution.

    Returns {"shape": str, "peak_positions": list[int] | None}.
    """
    arc = [x for x in (arc or []) if x is not None]
    if len(arc) < 3:
        return {"shape": "short form — limited arc data", "peak_positions": None}

    max_energy = max(arc)
    arc_min = min(arc)
    dynamic_mid = (arc_min + max_energy) / 2.0
    peak_threshold = max(max_energy * 0.9, dynamic_mid)
    peak_indices = [i for i, v in enumerate(arc) if v >= peak_threshold]

    # Collapse runs of adjacent peak indices into their starting index —
    # [1, 2, 5] has peaks at "position ~1" and "position 5", NOT three
    # distinct peaks. Without this, front-loaded arcs where bars 0 and 1
    # are both above threshold would misfire the dual-peak branch.
    distinct_peaks: list[int] = []
    for idx in peak_indices:
        if not distinct_peaks or idx - distinct_peaks[-1] > 1:
            distinct_peaks.append(idx)

    n = len(arc)
    first_third = {i for i in range(0, n // 3 + 1)}
    last_third = {i for i in range(2 * n // 3, n)}
    in_first = any(i in first_third for i in peak_indices)
    in_last = any(i in last_third for i in peak_indices)
    in_middle = any(
        i not in first_third and i not in last_third
        for i in peak_indices
    )

    # Plateau FIRST — when the dynamic range is narrow (<0.3) and most
    # of the arc sits at/near the max, it's a plateau, not a multi-peak
    # shape. Has to win over dual-peak so [0.7, 0.8, 0.8, 0.75, 0.8, …]
    # doesn't get labeled "dual-peak at 2 and 6" when it's clearly flat.
    if len(peak_indices) >= max(n - 2, 2) and (
        max_energy - arc_min < 0.3
    ):
        shape = "plateau — sustained energy with limited dynamic range"
    # Multi-peak: at least 2 DISTINCT peaks (after collapsing adjacent runs),
    # separated by >= n/3 positions. Adjacent peaks are a single plateau, not two.
    elif len(distinct_peaks) >= 2 and (
        max(distinct_peaks) - min(distinct_peaks) >= max(n // 3, 2)
    ):
        shape = (
            f"dual-peak — energy peaks at positions "
            f"{distinct_peaks[0]+1} and {distinct_peaks[-1]+1}"
        )
    elif in_first and not in_middle and not in_last:
        shape = "front-loaded — peaks early"
    elif in_last and not in_first and not in_middle:
        shape = "slow burn — builds to late peak"
    elif in_middle and not in_first and not in_last:
        shape = "centered arc — peaks in the middle"
    else:
        shape = (
            f"mixed — peaks at positions "
            f"{', '.join(str(i+1) for i in peak_indices)}"
        )
    return {"shape": shape, "peak_positions": peak_indices}


@mcp.tool()
def explain_song_identity(ctx: Context) -> dict:
    """Explain the current song's identity in human musical language.

    If no SongBrain exists yet, builds one first. Returns a structured
    explanation suitable for the agent to talk about the song naturally.
    """
    if _current_brain is None:
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
        _set_brain(ctx, brain)

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

    # Energy shape — BUG-B13 fix: dual-peak detection. See
    # classify_energy_shape() for logic.
    if brain.energy_arc:
        shape_info = classify_energy_shape(brain.energy_arc)
        explanation["energy_shape"] = shape_info["shape"]
        if shape_info["peak_positions"] is not None:
            explanation["peak_positions"] = shape_info["peak_positions"]

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

    Compares the current state against a previous SongBrain snapshot.
    If before_brain_id is provided, looks up that specific snapshot.
    If empty, uses the last cached brain.
    If no previous brain exists, builds baseline and reports no drift.

    before_brain_id: optional brain_id from a previous build_song_brain call.

    Returns drift score, changed elements, sacred damage, and recommendation.
    """
    # Look up the "before" brain — by ID if provided, else use last cached
    if before_brain_id:
        before = _get_snapshot(before_brain_id)
        if before is None:
            available = list(_brain_snapshots.keys())
            return {
                "error": f"No snapshot found for brain_id '{before_brain_id}'",
                "available_snapshots": available,
            }
    else:
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
        _set_brain(ctx, after)
        return {
            "drift_score": 0.0,
            "note": "No previous brain to compare — this is the baseline",
            "brain_id": after.brain_id,
            "recommendation": "safe",
        }

    drift = builder.detect_identity_drift(before, after)
    _set_brain(ctx, after)

    return {
        **drift.to_dict(),
        "before_brain_id": before.brain_id,
        "after_brain_id": after.brain_id,
    }

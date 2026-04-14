"""Wonder Mode MCP tools — 3 tools for stuck-rescue workflow.

  enter_wonder_mode — diagnose + generate distinct variants + open thread
  rank_wonder_variants — standalone re-ranker for any variant list
  discard_wonder_session — reject all variants, keep thread open
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import engine


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception:
        pass
    return {}


def _get_taste_graph(ctx: Context):
    """Return the TasteGraph object (not dict) for engine use."""
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore
        from ..persistence.taste_store import PersistentTasteStore
        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        persistent = ctx.lifespan_context.setdefault("persistent_taste", PersistentTasteStore())
        return build_taste_graph(
            taste_store=taste_store, anti_store=anti_store,
            persistent_store=persistent,
        )
    except Exception:
        pass
    return None


def _get_active_constraints():
    """Read active constraints from creative_constraints module if set."""
    try:
        from ..creative_constraints.tools import _active_constraints
        return _active_constraints
    except Exception:
        return None


def _get_ledger_entries(ctx: Context) -> list[dict]:
    """Get recent action ledger entries as dicts."""
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger: SessionLedger = ctx.lifespan_context.setdefault(
            "action_ledger", SessionLedger()
        )
        entries = ledger.get_recent_moves(limit=20)
        return [e.to_dict() for e in entries]
    except Exception:
        return []


def _get_stuckness_report(ctx: Context, song_brain: dict) -> dict | None:
    """Run stuckness detection on recent actions if available."""
    try:
        from ..stuckness_detector.detector import detect_stuckness
        action_ledger = _get_ledger_entries(ctx)
        if not action_ledger:
            return None
        # Pass session_info if available for better accuracy
        session_info = {}
        try:
            ableton = ctx.lifespan_context.get("ableton")
            if ableton:
                session_info = ableton.send_command("get_session_info", {})
        except Exception:
            pass
        report = detect_stuckness(
            action_history=action_ledger,
            session_info=session_info,
            song_brain=song_brain,
        )
        return report.to_dict()
    except Exception:
        return None


@mcp.tool()
def enter_wonder_mode(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
) -> dict:
    """Activate Wonder Mode — stuck-rescue workflow with real diagnosis.

    Diagnoses why the session needs creative rescue, generates 1-3
    genuinely distinct executable variants (plus honest analytical
    fallbacks), and opens a creative thread for tracking.

    Returns wonder_session_id for use with create_preview_set,
    commit_preview_variant, and discard_wonder_session.

    request_text: the creative request or description of being stuck
    kernel_id: optional session kernel reference
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    from .diagnosis import build_diagnosis
    from .session import WonderSession, store_wonder_session

    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph(ctx)
    active_constraints = _get_active_constraints()
    action_ledger = _get_ledger_entries(ctx)
    stuckness_report = _get_stuckness_report(ctx, song_brain)

    # 1. Build diagnosis
    diagnosis = build_diagnosis(
        stuckness_report=stuckness_report,
        song_brain=song_brain,
        action_ledger=action_ledger,
    )

    # 1b. If diagnosis includes sample domains, search for candidates
    sample_context = {}
    diag_dict = diagnosis.to_dict()
    candidate_domains = diag_dict.get("candidate_domains") or []
    if "sample" in candidate_domains:
        try:
            from ..sample_engine.tools import get_sample_opportunities, search_samples
            opportunities = get_sample_opportunities(ctx)
            if opportunities.get("opportunities"):
                opp = opportunities["opportunities"][0]
                query = opp.get("search_query", opp.get("description", "sample"))
                results = search_samples(ctx, query=query, max_results=3)
                candidates = results.get("results", [])
                if candidates:
                    best = candidates[0]
                    sample_context["sample_file_path"] = best.get("file_path", "")
                    sample_context["sample_name"] = best.get("name", "")
                    sample_context["material_type"] = best.get("material_type", "")
        except Exception:
            pass  # Graceful degradation — analytical variants still work

    # 1c. Get session info for kernel
    session_info = {}
    try:
        ableton = ctx.lifespan_context.get("ableton")
        if ableton:
            session_info = ableton.send_command("get_session_info", {})
    except Exception:
        pass

    # 2. Generate variants
    result = engine.generate_wonder_variants(
        request_text=request_text,
        diagnosis=diag_dict,
        kernel_id=kernel_id,
        song_brain=song_brain,
        taste_graph=taste_graph,
        active_constraints=active_constraints,
        session_info=session_info,
        sample_context=sample_context,
    )

    # 3. Create WonderSession (unique per invocation, not deterministic)
    import hashlib, time
    _seed = f"{request_text}:{kernel_id}:{time.time()}"
    session_id = "ws_" + hashlib.sha256(_seed.encode()).hexdigest()[:12]
    ws = WonderSession(
        session_id=session_id,
        request_text=request_text,
        kernel_id=kernel_id,
        diagnosis=diagnosis,
        variants=result["variants"],
        recommended=result.get("recommended", ""),
        variant_count_actual=result.get("variant_count_actual", 0),
        degraded_reason=result.get("degraded_reason", ""),
        status="diagnosing",  # will transition below
    )
    ws.transition_to("variants_ready")

    # 4. Open creative thread (exploration, NOT turn resolution)
    try:
        from ..session_continuity.tracker import open_thread
        thread_domain = diagnosis.candidate_domains[0] if diagnosis.candidate_domains else "exploration"
        thread = open_thread(
            description=f"Wonder: {request_text}",
            domain=thread_domain,
        )
        ws.creative_thread_id = thread.thread_id
    except Exception:
        pass

    # 5. Store session
    store_wonder_session(ws)

    # 6. Return full response (NO turn resolution recorded here)
    return {
        "wonder_session_id": ws.session_id,
        "creative_thread_id": ws.creative_thread_id,
        "diagnosis": diagnosis.to_dict(),
        "variants": result["variants"],
        "recommended": result.get("recommended", ""),
        "variant_count_actual": result.get("variant_count_actual", 0),
        "degraded_reason": ws.degraded_reason,
        "mode": "wonder",
    }


@mcp.tool()
def rank_wonder_variants(
    ctx: Context,
    variants: list[dict] | None = None,
) -> dict:
    """Rank wonder-mode variants by taste + identity + novelty + coherence.

    Standalone re-ranker for any list of variant dicts. Preserves ALL
    input fields (what_changed, compiled_plan, move_id, targets_snapshot).

    Uses the current SongBrain and session taste graph for scoring.
    When input dicts lack targets_snapshot, sacred element penalty
    is skipped gracefully.

    variants: list of variant dicts with at least variant_id,
              novelty_level, identity_effect, taste_fit fields

    Returns ranked list with composite scores, breakdowns, and recommendation.
    """
    if not variants:
        return {"error": "No variants provided", "rankings": []}

    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph(ctx)

    novelty_band = 0.5
    taste_evidence = 0
    if taste_graph is not None:
        novelty_band = taste_graph.novelty_band
        taste_evidence = taste_graph.evidence_count

    ranked = engine.rank_variants(
        variant_dicts=[dict(v) for v in variants],  # copy to avoid mutating input
        song_brain=song_brain,
        novelty_band=novelty_band,
        taste_evidence=taste_evidence,
    )

    return {
        "rankings": ranked,
        "recommended": ranked[0]["variant_id"] if ranked else "",
    }


@mcp.tool()
def discard_wonder_session(
    ctx: Context,
    wonder_session_id: str,
) -> dict:
    """Reject all Wonder variants and close the session.

    The creative thread stays open — the problem isn't solved.
    Records a rejected turn resolution and updates taste.

    wonder_session_id: the session to discard
    """
    from .session import get_wonder_session

    ws = get_wonder_session(wonder_session_id)
    if not ws:
        return {"error": "Wonder session not found", "wonder_session_id": wonder_session_id}

    if not ws.transition_to("resolved"):
        return {"error": f"Cannot discard session in '{ws.status}' state", "wonder_session_id": wonder_session_id}

    ws.outcome = "rejected_all"

    # Record rejected turn
    try:
        from ..session_continuity.tracker import record_turn_resolution
        record_turn_resolution(
            request_text=ws.request_text,
            outcome="rejected",
            move_applied="",
            identity_effect="",
            user_sentiment="disliked",
        )
    except Exception:
        pass

    # Update taste graph — rejection is a negative signal for all executable variants
    try:
        taste_graph = _get_taste_graph(ctx)
        if taste_graph:
            for v in ws.variants:
                if not v.get("analytical_only") and v.get("move_id") and v.get("family"):
                    taste_graph.record_move_outcome(
                        move_id=v["move_id"],
                        family=v["family"],
                        kept=False,
                    )
    except Exception:
        pass

    # Discard linked preview set
    if ws.preview_set_id:
        try:
            from ..preview_studio.engine import discard_set
            discard_set(ws.preview_set_id)
        except Exception:
            pass

    return {
        "discarded": True,
        "wonder_session_id": wonder_session_id,
        "thread_still_open": bool(ws.creative_thread_id),
    }

"""Wonder Mode MCP tools — 3 tools for stuck-rescue workflow.

  enter_wonder_mode — diagnose + generate distinct variants + open thread
  rank_wonder_variants — standalone re-ranker for any variant list
  discard_wonder_session — reject all variants, keep thread open
"""

from __future__ import annotations

import logging

from fastmcp import Context

from ..server import mcp
from . import engine

logger = logging.getLogger(__name__)


def _build_synth_profiles_for_wonder(ctx, request_text: str, diagnosis: dict) -> list:
    """Build SynthProfile objects for every track holding a native synth.

    Wires the synthesis_brain producer into enter_wonder_mode's runtime
    flow — without this helper, ``propose_synth_branches`` is registered
    but unreachable from the MCP surface.

    Returns a list of SynthProfile objects (possibly empty). All errors
    are swallowed and logged — missing devices, disconnected Ableton,
    unsupported devices all land as "no synth branches" rather than
    failing the whole wonder session.
    """
    try:
        from ..synthesis_brain import analyze_synth_patch, supported_devices
    except ImportError as exc:
        logger.debug("synthesis_brain not importable: %s", exc)
        return []

    ableton = ctx.lifespan_context.get("ableton")
    if ableton is None:
        return []

    try:
        session = ableton.send_command("get_session_info", {})
    except Exception as exc:
        logger.debug("session fetch for synth profiles failed: %s", exc)
        return []
    if not isinstance(session, dict) or "error" in session:
        return []

    native_names = set(supported_devices())
    profiles: list = []

    tracks = session.get("tracks") or []
    for track in tracks:
        track_index = track.get("index")
        devices = track.get("devices") or []
        if track_index is None or not devices:
            continue
        for dev in devices:
            dev_name = dev.get("name") or dev.get("class_name") or ""
            if dev_name not in native_names:
                continue
            dev_index = dev.get("index")
            if dev_index is None:
                continue
            try:
                params_result = ableton.send_command(
                    "get_device_parameters",
                    {"track_index": track_index, "device_index": dev_index},
                )
            except Exception as exc:
                logger.debug(
                    "get_device_parameters failed for track=%s device=%s: %s",
                    track_index, dev_index, exc,
                )
                continue
            if not isinstance(params_result, dict) or "error" in params_result:
                continue

            parameter_state = {}
            display_values = {}
            for p in params_result.get("parameters", []) or []:
                name = p.get("name")
                if name is None:
                    continue
                parameter_state[name] = p.get("value")
                if "value_string" in p:
                    display_values[name] = p["value_string"]

            try:
                profile = analyze_synth_patch(
                    device_name=dev_name,
                    track_index=track_index,
                    device_index=dev_index,
                    parameter_state=parameter_state,
                    display_values=display_values,
                    role_hint=track.get("name", ""),
                )
                profiles.append(profile)
            except Exception as exc:
                logger.warning(
                    "analyze_synth_patch failed for %s on track %s: %s",
                    dev_name, track_index, exc,
                )
                continue

    return profiles


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception as exc:
        logger.warning("song_brain lookup failed: %s", exc)
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
    except Exception as exc:
        logger.warning("taste_graph build failed: %s", exc)
    return None


def _get_active_constraints():
    """Read active constraints from creative_constraints module if set."""
    try:
        from ..creative_constraints.tools import _active_constraints
        return _active_constraints
    except Exception as exc:
        logger.debug("creative_constraints not importable: %s", exc)
        return None


def _get_ledger_entries(ctx: Context) -> list[dict]:
    """Get recent action ledger entries as dicts."""
    # store_purpose: anti_repetition
    # Wonder Mode's rescue trigger reads recent_moves to feed the
    # stuckness detector — classic recency signal, NOT the persistent
    # technique library. Correct store: SessionLedger.get_recent_moves.
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger: SessionLedger = ctx.lifespan_context.setdefault(
            "action_ledger", SessionLedger()
        )
        entries = ledger.get_recent_moves(limit=20)
        return [e.to_dict() for e in entries]
    except Exception as exc:
        logger.warning("action_ledger recent_moves failed: %s", exc)
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
        except Exception as exc:
            logger.warning("session_info fetch for stuckness failed: %s", exc)
        report = detect_stuckness(
            action_history=action_ledger,
            session_info=session_info,
            song_brain=song_brain,
        )
        return report.to_dict()
    except Exception as exc:
        logger.warning("stuckness detection failed: %s", exc)
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
        except Exception as exc:
            # Graceful degradation — analytical variants still work
            logger.warning("sample opportunity search failed: %s", exc)

    # 1c. Get session info for kernel
    session_info = {}
    try:
        ableton = ctx.lifespan_context.get("ableton")
        if ableton:
            session_info = ableton.send_command("get_session_info", {})
    except Exception as exc:
        logger.warning("session_info fetch for kernel failed: %s", exc)

    # 2. Generate variants (legacy path)
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

    # 2b. PR6 — also emit BranchSeeds for the branch-native experiment flow.
    # Pull session_memory from the conversation lifespan when available so
    # technique seeds can be sourced. Kernel state here is a lightweight
    # dict — enter_wonder_mode doesn't always have a full SessionKernel.
    branch_kernel: dict = {}
    try:
        from ..memory.session_memory import SessionMemoryStore
        mem_store = ctx.lifespan_context.setdefault("session_memory", SessionMemoryStore())
        branch_kernel["session_memory"] = [
            entry.to_dict() for entry in mem_store.get_recent(limit=10)
        ]
    except Exception as exc:
        logger.debug("session_memory fetch for seeds failed: %s", exc)
    # Freshness defaults to 0.5 — enter_wonder_mode is inherently exploratory,
    # so lean slightly toward surprise.
    branch_kernel["freshness"] = 0.65

    # Build SynthProfiles for tracks mentioned in the request or for every
    # track that holds a native synth. Lets propose_synth_branches reach
    # the runtime — without this the producer is dark despite being
    # registered in the conductor.
    synth_profiles = _build_synth_profiles_for_wonder(ctx, request_text, diag_dict)

    # Composer branches fire when the base conductor routes to
    # composition — otherwise we'd be emitting composition scaffolding
    # for every mix/transition request, which is noise.
    composer_request: str = ""
    try:
        from ..tools._conductor import classify_request
        base_plan = classify_request(request_text)
        if base_plan.routes and base_plan.routes[0].engine == "composition":
            composer_request = request_text
    except Exception as exc:
        logger.debug("composer routing check failed: %s", exc)

    try:
        branch_seeds, compiled_plans_by_seed = engine.generate_branch_seeds_and_plans(
            request_text=request_text,
            kernel=branch_kernel,
            song_brain=song_brain,
            active_constraints=active_constraints,
            taste_graph=taste_graph,
            synth_profiles=synth_profiles,
            composer_request=composer_request or None,
        )
        branch_seeds_dicts = [s.to_dict() for s in branch_seeds]
    except Exception as exc:
        # Seed assembly is additive — never let it break wonder mode.
        logger.warning("generate_branch_seeds_and_plans failed: %s", exc)
        branch_seeds_dicts = []
        compiled_plans_by_seed = {}

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
    except Exception as exc:
        logger.warning("open creative thread failed: %s", exc)

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
        # Branch-native seeds from six producers (semantic_move, technique,
        # synthesis, sacred-inversion, composer, corpus). Feed directly to
        # create_experiment(seeds=[...], compiled_plans=[...]) — align the
        # compiled_plans list with branch_seeds by matching seed_ids.
        "branch_seeds": branch_seeds_dicts,
        # seed_id → pre-compiled plan dict. Only synthesis and composer
        # seeds currently populate this — other sources either defer
        # compilation to run_experiment (semantic_move) or stay analytical
        # (technique reuse, sacred-inversion, corpus hints).
        "compiled_plans_by_seed_id": compiled_plans_by_seed,
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
    except Exception as exc:
        logger.warning("record_turn_resolution(rejected) failed: %s", exc)

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
    except Exception as exc:
        logger.warning("taste_graph negative-signal update failed: %s", exc)

    # Discard linked preview set
    if ws.preview_set_id:
        try:
            from ..preview_studio.engine import discard_set
            discard_set(ws.preview_set_id)
        except Exception as exc:
            logger.warning("discard_set(%s) failed: %s", ws.preview_set_id, exc)

    return {
        "discarded": True,
        "wonder_session_id": wonder_session_id,
        "thread_still_open": bool(ws.creative_thread_id),
    }

"""Semantic move MCP tools — propose, preview, and apply musical intents.

3 tools:
  list_semantic_moves — discover available moves by domain
  preview_semantic_move — see what a move will do before applying
  propose_next_best_move — AI-ranked suggestions based on current session state
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import registry
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
def list_semantic_moves(
    ctx: Context,
    domain: str = "",
    style: str = "",
) -> dict:
    """List available semantic moves — high-level musical intents.

    Semantic moves express WHAT to achieve musically, not HOW parametrically.
    Each move compiles into a sequence of existing deterministic tools.

    domain: filter by family (e.g. mix, arrangement, transition, sound_design, sample, performance)
    style: filter by genre/style (reserved for future use)

    Returns: list of moves with move_id, family, intent, targets, risk_level.
    """
    moves = registry.list_moves(domain=domain, style=style)
    all_moves = registry.list_moves()
    domains = sorted({m.get("family", "") for m in all_moves if m.get("family")})
    return {"moves": moves, "count": len(moves), "available_domains": domains}


@mcp.tool()
def preview_semantic_move(
    ctx: Context,
    move_id: str,
    args: Optional[dict] = None,
) -> dict:
    """Preview what a semantic move will do before applying it.

    Returns the static plan_template + verification_plans, PLUS an additive
    compiled_plan field built by compiling the move against a lightweight
    kernel of the current session. Use compiled_plan to inspect the concrete
    tool calls the move would emit right now; use plan_template to understand
    the move's shape independent of session state.

    args (v1.20+): user-supplied seed parameters threaded into the kernel as
    ``kernel["seed_args"]``. Routing / content / metadata moves require these
    (e.g., ``{"return_track_index": 0, "device_chain": ["Echo", ...]}``).
    Pre-v1.20 moves read only from ``session_info`` and ignore seed_args.

    Existing callers reading plan_template are unaffected by the addition.
    """
    move = registry.get_move(move_id)
    if not move:
        available = [m["move_id"] for m in registry.list_moves()]
        return {
            "error": f"Unknown move_id: {move_id}",
            "available_moves": available,
        }

    result = move.to_full_dict()

    # Additive: compile against a lightweight kernel so callers get an
    # executable representation alongside the static plan_template.
    try:
        from ..runtime.session_kernel import build_session_kernel
        from ..runtime.capability_state import build_capability_state
        from . import compiler as move_compiler

        ableton = None
        if hasattr(ctx, "lifespan_context"):
            ableton = ctx.lifespan_context.get("ableton")

        session_info: dict = {}
        if ableton is not None:
            try:
                info = ableton.send_command("get_session_info")
                if isinstance(info, dict):
                    session_info = info
            except Exception as exc:
                logger.debug("preview_semantic_move failed: %s", exc)
                session_info = {}

        state = build_capability_state(
            session_ok=bool(session_info),
            analyzer_ok=False,
            memory_ok=True,
        )
        kernel = build_session_kernel(
            session_info=session_info,
            capability_state=state.to_dict(),
        )
        kernel_dict = kernel.to_dict()
        # v1.20: thread user seed_args through to the compiler.
        kernel_dict["seed_args"] = dict(args) if args else {}
        plan = move_compiler.compile(move, kernel_dict)
        result["compiled_plan"] = plan.to_dict()
        result["compiled_plan_executable"] = bool(plan.executable)
    except Exception as e:
        result["compiled_plan"] = None
        result["compiled_plan_executable"] = False
        result["compiled_plan_error"] = str(e)

    return result


def _build_taste_context(ctx: Context) -> dict:
    """Pull the active taste graph for ranking, with defensive fallbacks.

    Returns a dict with ``dimension_weights``, ``dimension_avoidances``,
    ``move_family_scores`` (family → score), and ``evidence_count``.
    Empty dicts when no taste has been recorded yet — the ranker then
    collapses to pure keyword matching, which is the correct behavior for
    a cold-start user with no history.
    """
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore

        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store)

        move_family_scores: dict[str, float] = {}
        for family, entry in getattr(graph, "move_family_scores", {}).items():
            score = getattr(entry, "score", None)
            if isinstance(score, (int, float)):
                move_family_scores[family] = float(score)

        return {
            "dimension_weights": dict(getattr(graph, "dimension_weights", {}) or {}),
            "dimension_avoidances": dict(getattr(graph, "dimension_avoidances", {}) or {}),
            "move_family_scores": move_family_scores,
            "evidence_count": int(getattr(graph, "evidence_count", 0) or 0),
        }
    except Exception as exc:
        logger.debug("_build_taste_context failed: %s", exc)
        return {
            "dimension_weights": {},
            "dimension_avoidances": {},
            "move_family_scores": {},
            "evidence_count": 0,
        }


def _score_move_for_request(move, request_lower: str, request_words: set, taste: dict) -> tuple[float, dict]:
    """Compute the composite score for a single move.

    Composition:
        0.55 × keyword overlap (intent + move_id + targets)
        0.30 × taste alignment (from taste_graph.dimension_weights on move.targets)
        0.15 × (1 - anti avoidance penalty) (from dimension_avoidances)

        ± up to 0.10 family bonus/penalty from move_family_scores[family].

    When the user has no recorded taste (evidence_count == 0), the taste
    and anti-penalty components collapse to neutral 0.5 so cold-start
    behavior stays identical to the old keyword-only ranker.
    """
    # ── Keyword overlap component (0..1) ──────────────────────────────
    intent_lower = move.intent.lower()
    move_words = set(move.move_id.replace("_", " ").split())
    intent_words = set(intent_lower.split())

    overlap = request_words & (move_words | intent_words)
    keyword_score = min(1.0, len(overlap) * 0.3)

    for dim in move.targets:
        if dim.lower() in request_lower:
            keyword_score = min(1.0, keyword_score + 0.2)

    if move.move_id.replace("_", " ") in request_lower:
        keyword_score = 1.0

    # ── Taste alignment component (0..1) ──────────────────────────────
    evidence_count = taste["evidence_count"]
    dim_weights = taste["dimension_weights"]
    dim_avoid = taste["dimension_avoidances"]

    if evidence_count > 0 and move.targets:
        # Average dimension_weights for this move's targets; weights are
        # -1..1 with 0 meaning unknown. Remap to 0..1 so "neutral" is 0.5.
        raw_taste = [
            dim_weights.get(dim, 0.0) for dim in move.targets
        ]
        taste_alignment = sum((w + 1.0) / 2.0 for w in raw_taste) / len(raw_taste)
        avoidance = sum(
            dim_avoid.get(dim, 0.0) for dim in move.targets
        ) / len(move.targets)
        avoidance = max(0.0, min(1.0, avoidance))
    else:
        taste_alignment = 0.5
        avoidance = 0.0

    composite = (
        0.55 * keyword_score
        + 0.30 * taste_alignment
        + 0.15 * (1.0 - avoidance)
    )

    # ── Family bonus/penalty (±0.1) ────────────────────────────────────
    family_bonus = 0.0
    family_score = taste["move_family_scores"].get(move.family)
    if family_score is not None:
        # family score is 0..1 with 0.5 neutral; remap to -0.1..+0.1
        family_bonus = (family_score - 0.5) * 0.2
        composite += family_bonus

    composite = max(0.0, min(1.0, composite))

    breakdown = {
        "keyword_score": round(keyword_score, 3),
        "taste_alignment": round(taste_alignment, 3),
        "avoidance_penalty": round(avoidance, 3),
        "family_bonus": round(family_bonus, 3),
        "evidence_count": evidence_count,
    }
    return composite, breakdown


@mcp.tool()
def propose_next_best_move(
    ctx: Context,
    request_text: str,
    limit: int = 3,
) -> dict:
    """Propose the best semantic moves for a natural language request, ranked
    by keyword fit AND the active taste graph.

    Shipped in v1.10.9: ranking is no longer pure keyword overlap — it now
    blends keyword match with taste alignment (``dimension_weights`` on each
    move's targets), an anti-preference penalty (``dimension_avoidances``),
    and a small family bonus from ``move_family_scores``. Cold-start users
    with zero recorded evidence get the same ranking as before; users with
    history see recommendations pulled toward dimensions they've kept and
    away from ones they've undone.

    request_text: what the user wants (e.g., "make this punchier",
                  "tighten the low end", "reduce repetition")
    limit: max suggestions to return (default 3)
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    request_lower = request_text.lower()
    request_words = set(request_lower.split())
    taste = _build_taste_context(ctx)
    all_moves = list(registry._REGISTRY.values())

    scored: list[tuple[object, float, dict]] = []
    for move in all_moves:
        score, breakdown = _score_move_for_request(
            move, request_lower, request_words, taste,
        )
        # Keep only moves that had any keyword signal or strong taste pull —
        # a move with zero keyword overlap AND neutral taste would be noise.
        if breakdown["keyword_score"] > 0 or taste["evidence_count"] >= 5:
            scored.append((move, score, breakdown))

    scored.sort(key=lambda x: -x[1])
    top = scored[:limit]

    suggestions = []
    for move, score, breakdown in top:
        d = move.to_dict()
        d["match_score"] = round(score, 3)
        d["score_breakdown"] = breakdown
        suggestions.append(d)

    return {
        "request": request_text,
        "suggestions": suggestions,
        "count": len(suggestions),
        "taste_active": taste["evidence_count"] > 0,
        "taste_evidence_count": taste["evidence_count"],
    }


@mcp.tool()
async def apply_semantic_move(
    ctx: Context,
    move_id: str,
    mode: str = "improve",
    args: Optional[dict] = None,
) -> dict:
    """Compile and optionally execute a semantic move against the current session.

    Resolves the move's intent into concrete, parameterized tool calls based
    on the current session topology (track names, roles, devices).

    mode controls behavior:
    - "improve" / "finish": compile and RETURN the plan for user approval.
      The agent should present the steps and ask "Shall I do it?"
    - "explore": compile and EXECUTE immediately, capturing before/after.
    - "observe" / "diagnose": compile only, never execute. Return the plan.

    args (v1.20+): user-supplied seed parameters threaded into the kernel as
    ``kernel["seed_args"]``. Required by routing / content / metadata moves —
    e.g., ``apply_semantic_move("build_send_chain", mode="explore",
    args={"return_track_index": 0, "device_chain": ["Echo", "Auto Filter"]})``.
    Pre-v1.20 moves read only from ``session_info`` and ignore seed_args.

    Returns: CompiledPlan with concrete steps, summary, and execution status.
    """
    from . import compiler

    move = registry.get_move(move_id)
    if not move:
        return {"error": f"Unknown move_id: {move_id}"}

    # Build a lightweight kernel from session info
    ableton = ctx.lifespan_context["ableton"]
    session_info = ableton.send_command("get_session_info")
    kernel = {
        "session_info": session_info,
        "mode": mode,
        "capability_state": {},
        "seed_args": dict(args) if args else {},
    }

    # Compile the move
    plan = compiler.compile(move, kernel)

    if not plan.executable:
        result = plan.to_dict()
        result["executed"] = False
        return result

    if mode in ("observe", "diagnose"):
        result = plan.to_dict()
        result["executed"] = False
        result["note"] = f"Mode '{mode}' — plan compiled but not executed"
        return result

    if mode in ("improve", "finish"):
        result = plan.to_dict()
        result["executed"] = False
        result["note"] = "Awaiting approval — present the plan to the user, then execute steps individually"
        return result

    # explore mode — execute through the async router
    from ..runtime.execution_router import execute_plan_steps_async

    # Propagate the optional backend annotation through to the router so a
    # compiler that's certain about a step's backend (e.g. bridge_command for
    # capture_audio) can short-circuit classify_step(). Steps without backend
    # fall back to the classifier as before.
    def _step_to_dict(step):
        d = {
            "tool": step.tool,
            "params": step.params,
            "description": step.description,
        }
        if getattr(step, "backend", None):
            d["backend"] = step.backend
        # v1.20.2 (BUG #3 fix): propagate optional flag so the router
        # can skip-and-continue on soft failures (e.g., analyzer pre-reads).
        if getattr(step, "optional", False):
            d["optional"] = True
        return d

    step_dicts = [_step_to_dict(step) for step in plan.steps]
    bridge = ctx.lifespan_context.get("m4l")
    mcp_registry = ctx.lifespan_context.get("mcp_dispatch", {})
    exec_results = await execute_plan_steps_async(
        step_dicts,
        ableton=ableton,
        bridge=bridge,
        mcp_registry=mcp_registry,
        ctx=ctx,
    )

    executed_steps = []
    for i, er in enumerate(exec_results):
        executed_steps.append({
            "tool": er.tool,
            "backend": er.backend,
            "description": step_dicts[i].get("description", ""),
            "result": er.result if er.ok else None,
            "error": er.error if not er.ok else None,
            "ok": er.ok,
        })

    success_count = sum(1 for s in executed_steps if s["ok"])
    failure_count = sum(1 for s in executed_steps if not s["ok"])

    # store_purpose: writer
    # v1.20: apply_semantic_move is the canonical semantic-moves writer
    # to the SessionLedger. Downstream anti-repetition / stuckness /
    # song-brain readers (annotated store_purpose: anti_repetition) consume
    # entries this block writes. commit_experiment (v1.21) mirrors this
    # pattern with a "composer|experiment" engine tag instead of
    # "semantic_moves". Best-effort — a ledger write failure must not
    # fail the overall move.
    ledger_entry_id: Optional[str] = None
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger = ctx.lifespan_context.setdefault("action_ledger", SessionLedger())
        ledger_entry_id = ledger.start_move(
            engine="semantic_moves",
            move_class=move.family,
            intent=f"{move.move_id}: {move.intent}",
            undo_scope="micro",
        )
        for es in executed_steps:
            if es["ok"]:
                ledger.append_action(
                    ledger_entry_id,
                    tool_name=es["tool"],
                    summary=es.get("description", "") or es["tool"],
                )
        # Provisional keep — evaluate_move / user undo flip this later.
        ledger.finalize_move(
            ledger_entry_id,
            kept=(failure_count == 0),
            score=(float(success_count) / len(executed_steps)) if executed_steps else 0.0,
            memory_candidate=False,
        )
    except Exception as exc:  # pragma: no cover — ledger is best-effort
        logger.warning("apply_semantic_move ledger write failed: %s", exc)

    result = plan.to_dict()
    result["executed"] = True
    result["execution_results"] = executed_steps
    result["success_count"] = success_count
    result["failure_count"] = failure_count
    if ledger_entry_id is not None:
        result["ledger_entry_id"] = ledger_entry_id
    return result

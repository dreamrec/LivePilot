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
) -> dict:
    """Preview what a semantic move will do before applying it.

    Returns the static plan_template + verification_plans, PLUS an additive
    compiled_plan field built by compiling the move against a lightweight
    kernel of the current session. Use compiled_plan to inspect the concrete
    tool calls the move would emit right now; use plan_template to understand
    the move's shape independent of session state.

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
        plan = move_compiler.compile(move, kernel.to_dict())
        result["compiled_plan"] = plan.to_dict()
        result["compiled_plan_executable"] = bool(plan.executable)
    except Exception as e:
        result["compiled_plan"] = None
        result["compiled_plan_executable"] = False
        result["compiled_plan_error"] = str(e)

    return result


@mcp.tool()
def propose_next_best_move(
    ctx: Context,
    request_text: str,
    limit: int = 3,
) -> dict:
    """Propose the best semantic moves for a natural language request.

    Analyzes the request text and ranks available semantic moves by
    relevance. Returns up to `limit` suggestions with confidence scores.

    request_text: what the user wants (e.g., "make this punchier",
                  "tighten the low end", "reduce repetition")
    limit: max suggestions to return (default 3)
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    # Simple keyword matching for now — will be replaced by conductor
    # routing + taste ranking in V2 Step 7
    request_lower = request_text.lower()
    all_moves = list(registry._REGISTRY.values())

    scored = []
    for move in all_moves:
        score = 0.0
        # Match keywords from intent and move_id
        intent_lower = move.intent.lower()
        move_words = set(move.move_id.replace("_", " ").split())
        intent_words = set(intent_lower.split())
        request_words = set(request_lower.split())

        # Word overlap scoring
        overlap = request_words & (move_words | intent_words)
        score += len(overlap) * 0.3

        # Dimension matching
        for dim in move.targets:
            if dim in request_lower:
                score += 0.2

        # Boost exact intent matches
        if move.move_id.replace("_", " ") in request_lower:
            score += 1.0

        if score > 0:
            scored.append((move, min(score, 1.0)))

    # Sort by score descending
    scored.sort(key=lambda x: -x[1])
    top = scored[:limit]

    suggestions = []
    for move, score in top:
        d = move.to_dict()
        d["match_score"] = round(score, 3)
        suggestions.append(d)

    return {
        "request": request_text,
        "suggestions": suggestions,
        "count": len(suggestions),
    }


@mcp.tool()
async def apply_semantic_move(
    ctx: Context,
    move_id: str,
    mode: str = "improve",
) -> dict:
    """Compile and optionally execute a semantic move against the current session.

    Resolves the move's intent into concrete, parameterized tool calls based
    on the current session topology (track names, roles, devices).

    mode controls behavior:
    - "improve" / "finish": compile and RETURN the plan for user approval.
      The agent should present the steps and ask "Shall I do it?"
    - "explore": compile and EXECUTE immediately, capturing before/after.
    - "observe" / "diagnose": compile only, never execute. Return the plan.

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

    result = plan.to_dict()
    result["executed"] = True
    result["execution_results"] = executed_steps
    result["success_count"] = sum(1 for s in executed_steps if s["ok"])
    result["failure_count"] = sum(1 for s in executed_steps if not s["ok"])
    return result

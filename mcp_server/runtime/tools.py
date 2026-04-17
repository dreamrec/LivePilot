"""MCP tool wrappers for runtime capability state and session kernel.

Tools:
  get_capability_state — probe session + analyzer + memory, return snapshot
  get_session_kernel — build the unified V2 turn snapshot for orchestration
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from ..memory.technique_store import TechniqueStore
from .capability_state import build_capability_state
import logging

logger = logging.getLogger(__name__)

_memory_store = TechniqueStore()


@mcp.tool()
def get_capability_state(ctx: Context) -> dict:
    """Probe the runtime and return a capability state snapshot.

    Checks session connectivity, analyzer freshness, memory availability,
    and reports what modes the system can operate in right now.
    """
    ableton = ctx.lifespan_context["ableton"]
    spectral = ctx.lifespan_context.get("spectral")

    # ── Probe session ───────────────────────────────────────────────
    session_ok = False
    try:
        result = ableton.send_command("get_session_info")
        session_ok = isinstance(result, dict) and "error" not in result
    except Exception as exc:
        logger.debug("get_capability_state failed: %s", exc)
        session_ok = False

    # ── Probe analyzer (M4L bridge) ─────────────────────────────────
    analyzer_ok = False
    analyzer_fresh = False
    if spectral is not None:
        analyzer_ok = spectral.is_connected
        if analyzer_ok:
            # Check if we have recent spectrum data
            snap = spectral.get("spectrum")
            analyzer_fresh = snap is not None

    # ── Probe memory (direct TechniqueStore, not TCP) ────────────────
    memory_ok = False
    try:
        _memory_store.list_techniques(limit=1)
        memory_ok = True
    except Exception as exc:
        logger.debug("get_capability_state failed: %s", exc)
        memory_ok = False

    # ── Web / FluCoMa — not probed live, default to False ───────────
    web_ok = False
    flucoma_ok = False

    state = build_capability_state(
        session_ok=session_ok,
        analyzer_ok=analyzer_ok,
        analyzer_fresh=analyzer_fresh,
        memory_ok=memory_ok,
        web_ok=web_ok,
        flucoma_ok=flucoma_ok,
    )

    return state.to_dict()


@mcp.tool()
def get_session_kernel(
    ctx: Context,
    request_text: str = "",
    mode: str = "improve",
    aggression: float = 0.5,
) -> dict:
    """Build the unified turn snapshot for V2 orchestration.

    This is the preferred entrypoint for any complex agentic workflow.
    Assembles: session info, capability state, action ledger, taste profile,
    anti-preferences, and session memory into one canonical snapshot.

    mode: observe | improve | explore | finish | diagnose
    aggression: 0.0 (subtle) to 1.0 (bold)

    Returns: SessionKernel dict with kernel_id, session topology, capabilities,
    memory context, and routing hints.
    """
    from .session_kernel import build_session_kernel

    ableton = ctx.lifespan_context["ableton"]
    spectral = ctx.lifespan_context.get("spectral")

    # Core: session info + capability state
    session_info = ableton.send_command("get_session_info")
    session_ok = isinstance(session_info, dict) and "error" not in session_info

    analyzer_ok = False
    analyzer_fresh = False
    if spectral is not None:
        analyzer_ok = spectral.is_connected
        if analyzer_ok:
            analyzer_fresh = spectral.get("spectrum") is not None

    state = build_capability_state(
        session_ok=session_ok,
        analyzer_ok=analyzer_ok,
        analyzer_fresh=analyzer_fresh,
        memory_ok=True,
    )

    # Optional subcomponents — degrade gracefully, but reach into the SAME
    # session-scoped stores the public memory tools read/write via
    # ctx.lifespan_context.setdefault(...). Creating fresh stores here meant
    # users who recorded anti-preferences, session memory, or taste signals
    # through the MCP tools always saw an empty kernel.
    ledger_summary: dict = {}
    taste_graph: dict = {}
    anti_prefs: list = []
    session_mem: list = []
    kernel_warnings: list[str] = []

    try:
        from .action_ledger import SessionLedger
        ledger = ctx.lifespan_context.get("action_ledger")
        if ledger is None:
            ledger = SessionLedger()
            ctx.lifespan_context["action_ledger"] = ledger
        recent = ledger.get_recent_moves(limit=10)
        ledger_summary = {
            "total_moves": len(ledger._entries),
            "memory_candidate_count": len(ledger.get_memory_candidates()),
            "last_move": ledger.get_last_move().to_dict() if ledger.get_last_move() else None,
            "recent_moves": [entry.to_dict() for entry in recent],
        }
    except Exception as e:
        kernel_warnings.append(f"ledger_unavailable: {e}")

    # Taste graph + anti-prefs — share stores via lifespan_context, use the
    # canonical build_taste_graph() so consumers see dimension_weights shape.
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore
        from ..persistence.taste_store import PersistentTasteStore
        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        persistent = ctx.lifespan_context.setdefault("persistent_taste", PersistentTasteStore())
        graph = build_taste_graph(
            taste_store=taste_store,
            anti_store=anti_store,
            persistent_store=persistent,
        )
        taste_graph = graph.to_dict()
        anti_prefs = [p.to_dict() for p in anti_store.get_anti_preferences()]
    except Exception as e:
        kernel_warnings.append(f"taste_graph_unavailable: {e}")

    try:
        from ..memory.session_memory import SessionMemoryStore
        mem_store = ctx.lifespan_context.setdefault("session_memory", SessionMemoryStore())
        session_mem = [entry.to_dict() for entry in mem_store.get_recent(limit=10)]
    except Exception as e:
        kernel_warnings.append(f"session_memory_unavailable: {e}")

    kernel = build_session_kernel(
        session_info=session_info,
        capability_state=state.to_dict(),
        request_text=request_text,
        mode=mode,
        aggression=aggression,
        ledger_summary=ledger_summary,
        session_memory=session_mem,
        taste_graph=taste_graph,
        anti_preferences=anti_prefs,
    )

    # Populate routing hints from conductor when request context is available
    if request_text.strip():
        try:
            from ..tools._conductor import classify_request

            plan = classify_request(request_text)
            kernel.recommended_engines = [r.engine for r in plan.routes[:3]]
            kernel.recommended_workflow = plan.workflow_mode
        except Exception as e:
            kernel_warnings.append(f"conductor_routing_unavailable: {e}")

    result_dict = kernel.to_dict()
    if kernel_warnings:
        # Additive — callers can ignore; debug-mode introspection benefits.
        result_dict["warnings"] = kernel_warnings
    return result_dict

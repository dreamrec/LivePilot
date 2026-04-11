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
    except Exception:
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
    except Exception:
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

    # Optional subcomponents — degrade gracefully
    ledger_summary = {}
    taste_graph = {}
    anti_prefs = []
    session_mem = []

    try:
        from .action_ledger import SessionLedger
        ledger = ctx.lifespan_context.get("action_ledger")
        if ledger is None:
            ledger = SessionLedger()
            ctx.lifespan_context["action_ledger"] = ledger
        if ledger:
            recent = ledger.get_recent_moves(limit=10)
            ledger_summary = {
                "total_moves": len(ledger._entries),
                "memory_candidate_count": len(ledger.get_memory_candidates()),
                "last_move": ledger.get_last_move().to_dict() if ledger.get_last_move() else None,
                "recent_moves": [entry.to_dict() for entry in recent],
            }
    except Exception:
        pass

    try:
        from ..memory.taste_memory import TasteMemoryStore
        taste_store = TasteMemoryStore()
        taste_graph = {d.name: d.to_dict() for d in taste_store._dims.values()
                       if d.evidence_count > 0}
    except Exception:
        pass

    try:
        from ..memory.anti_memory import AntiMemoryStore
        anti_store = AntiMemoryStore()
        anti_prefs = anti_store.list_all()
    except Exception:
        pass

    try:
        from ..memory.session_memory import SessionMemoryStore
        mem_store = SessionMemoryStore()
        session_mem = mem_store.recent(limit=10)
    except Exception:
        pass

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

    return kernel.to_dict()

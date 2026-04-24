"""MCP tool wrappers for runtime capability state and session kernel.

Tools:
  get_capability_state — probe session + analyzer + memory, return snapshot
  get_session_kernel — build the unified V2 turn snapshot for orchestration
"""

from __future__ import annotations

import importlib.util
import logging
import urllib.request
from typing import Optional

from fastmcp import Context

from ..server import mcp
from ..memory.technique_store import TechniqueStore
from .capability_state import build_capability_state

logger = logging.getLogger(__name__)

_memory_store = TechniqueStore()


# ── Capability probes ──────────────────────────────────────────────────
#
# These helpers are module-level so tests can monkeypatch them directly.


def _probe_web(timeout: float = 0.5) -> bool:
    """Server-side outbound HTTP probe.

    True when the MCP host can reach an arbitrary public URL. Does NOT
    imply curated research corpora are installed — see the ``research``
    domain for that.

    Implementation: a ``timeout``-second HEAD request to
    ``https://api.github.com`` using stdlib ``urllib.request``. Any
    exception (DNS failure, TLS error, socket timeout, proxy block,
    non-2xx response) collapses to False so the probe is safe to call
    from any code path.
    """
    req = urllib.request.Request("https://api.github.com", method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None)
            return status is not None and 200 <= status < 400
    except Exception as exc:  # noqa: BLE001 — swallow everything to False
        logger.debug("_probe_web failed: %s", exc)
        return False


def _probe_flucoma() -> bool:
    """Check whether the ``flucoma`` Python package is importable.

    Uses ``importlib.util.find_spec`` so no import side-effects fire
    (matching the pattern already used for optional capability probes
    elsewhere in the codebase). Returns False if the package is missing
    or if the spec lookup itself raises.
    """
    try:
        return importlib.util.find_spec("flucoma") is not None
    except Exception as exc:  # noqa: BLE001
        logger.debug("_probe_flucoma failed: %s", exc)
        return False


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

    # ── Web — actually probe outbound HTTP egress ───────────────────
    # Scoped to server-side outbound HTTP reachability; does NOT imply
    # a curated research corpus is installed (see ``research`` domain).
    web_ok = _probe_web()

    # ── FluCoMa — optional import via find_spec (no side effects) ───
    flucoma_ok = _probe_flucoma()

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
    freshness: float = 0.5,
    creativity_profile: str = "",
    sacred_elements: Optional[list] = None,
    synth_hints: Optional[dict] = None,
) -> dict:
    """Build the unified turn snapshot for V2 orchestration.

    This is the preferred entrypoint for any complex agentic workflow.
    Assembles: session info, capability state, action ledger, taste profile,
    anti-preferences, and session memory into one canonical snapshot.

    Core params:
      mode: observe | improve | explore | finish | diagnose
      aggression: 0.0 (subtle) to 1.0 (bold) — execution boldness.

    Creative controls (PR2 — branch-native migration, optional):
      freshness: 0.0 (don't surprise me) to 1.0 (surprise me). Read by
        producers (Wonder, synthesis_brain, composer) to bias branch
        generation. Distinct from aggression, which is about applying
        a single move boldly; freshness is about how far to roam.
      creativity_profile: shorthand producer philosophy tag. Known values
        include "surgeon" (targeted), "alchemist" (transformative),
        "sculptor" (synthesis-focused). Empty ⇒ producer picks a default.
      sacred_elements: caller-asserted list of sacred elements that
        override or augment what song_brain infers. Shape matches
        song_brain entries: {element_type, description, salience}.
      synth_hints: focus hints for synthesis_brain; shape is open in PR2
        and firms up in PR9. Typical keys: track_indices, device_paths,
        target_timbre, preferred_devices.

    Returns: SessionKernel dict with kernel_id, session topology, capabilities,
    memory context, routing hints, and (if provided) creative controls.
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

    # P2#3 (v1.17.3): probe web + flucoma the same way get_capability_state
    # does, and propagate through. Without this the kernel's capability view
    # lies to orchestration planners.
    web_ok = _probe_web()
    flucoma_ok = _probe_flucoma()

    # v1.17.4: probe memory the same way too. Previously memory_ok=True was
    # hardcoded — if the store raised, the kernel still reported memory
    # available. Same truth-gap class as the v1.17.3 web/flucoma fix.
    memory_ok = False
    try:
        _memory_store.list_techniques(limit=1)
        memory_ok = True
    except Exception as exc:
        logger.debug("get_session_kernel memory probe failed: %s", exc)

    state = build_capability_state(
        session_ok=session_ok,
        analyzer_ok=analyzer_ok,
        analyzer_fresh=analyzer_fresh,
        memory_ok=memory_ok,
        web_ok=web_ok,
        flucoma_ok=flucoma_ok,
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

    # store_purpose: audit_readonly
    # The world-model kernel builder surfaces ledger state (total moves,
    # memory candidates, last_move, recent_moves) as diagnostic data for
    # downstream consumers. Not an anti-repetition reader — it's a
    # kernel-assembly surface; consumers that want recency should either
    # call SessionLedger.get_recent_moves directly (annotated as
    # anti_repetition) or use get_action_ledger_summary.
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

    # v1.17.4: state.to_dict() wraps its output as {"capability_state": {...}}
    # because that shape is what the standalone get_capability_state tool
    # returns. When building the session kernel, that wrapper becomes the
    # ugly double-nested kernel["capability_state"]["capability_state"]["domains"]
    # path. Unwrap once here so kernel consumers get
    # kernel["capability_state"]["domains"] directly.
    _cap_dict = state.to_dict()
    _cap_flat = _cap_dict.get("capability_state", _cap_dict)

    kernel = build_session_kernel(
        session_info=session_info,
        capability_state=_cap_flat,
        request_text=request_text,
        mode=mode,
        aggression=aggression,
        ledger_summary=ledger_summary,
        session_memory=session_mem,
        taste_graph=taste_graph,
        anti_preferences=anti_prefs,
        freshness=freshness,
        creativity_profile=creativity_profile,
        sacred_elements=sacred_elements,
        synth_hints=synth_hints,
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

"""Registry of in-process MCP tools callable from the async execution router.

These tools live as Python async functions in the MCP server — not TCP Remote
Script handlers and not M4L bridge commands. Plans that want to invoke them
go through this registry so the async router can dispatch them in-process.

Each entry is a thin wrapper around the real MCP tool import, keeping the
module cheap to import (no heavy server wiring until a caller actually
dispatches an MCP step).

To add a new in-process tool to plans:
  1. Add the tool name to MCP_TOOLS in execution_router.py so classify_step
     returns "mcp_tool" for it.
  2. Add an _adapter function here that imports the real implementation and
     adapts its kwargs from a plan-style params dict.
  3. Register the adapter in build_mcp_dispatch_registry.

Every entry in MCP_TOOLS must have a matching adapter here — the contract
test tests/test_mcp_dispatch_contract.py enforces this.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable


async def _call(fn, ctx, params: dict) -> Any:
    """Call an MCP tool with ctx + kwargs from a plan params dict.

    Filters params to the tool's declared parameters, awaits if coroutine.
    Unknown params are dropped silently — plans may carry extra metadata.
    """
    sig = inspect.signature(fn)
    accepted = set(sig.parameters.keys())
    kwargs = {k: v for k, v in params.items() if k in accepted}
    result = fn(ctx, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


async def _load_sample_to_simpler(params: dict, ctx: Any = None) -> dict:
    from ..tools.analyzer import load_sample_to_simpler
    return await load_sample_to_simpler(
        ctx,
        track_index=int(params["track_index"]),
        file_path=str(params["file_path"]),
        device_index=int(params.get("device_index", 0)),
    )


async def _apply_automation_shape(params: dict, ctx: Any = None) -> dict:
    from ..tools.automation import apply_automation_shape
    return await _call(apply_automation_shape, ctx, params)


async def _apply_gesture_template(params: dict, ctx: Any = None) -> dict:
    from ..tools.composition import apply_gesture_template
    return await _call(apply_gesture_template, ctx, params)


async def _analyze_mix(params: dict, ctx: Any = None) -> dict:
    from ..mix_engine.tools import analyze_mix
    return await _call(analyze_mix, ctx, params)


async def _get_master_spectrum(params: dict, ctx: Any = None) -> dict:
    from ..tools.analyzer import get_master_spectrum
    return await _call(get_master_spectrum, ctx, params)


async def _get_emotional_arc(params: dict, ctx: Any = None) -> dict:
    from ..tools.research import get_emotional_arc
    return await _call(get_emotional_arc, ctx, params)


async def _get_motif_graph(params: dict, ctx: Any = None) -> dict:
    from ..tools.motif import get_motif_graph
    return await _call(get_motif_graph, ctx, params)


async def _generate_m4l_effect(params: dict, ctx: Any = None) -> dict:
    from ..device_forge.tools import generate_m4l_effect
    return await _call(generate_m4l_effect, ctx, params)


async def _install_m4l_device(params: dict, ctx: Any = None) -> dict:
    from ..device_forge.tools import install_m4l_device
    return await _call(install_m4l_device, ctx, params)


async def _list_genexpr_templates(params: dict, ctx: Any = None) -> dict:
    from ..device_forge.tools import list_genexpr_templates
    return await _call(list_genexpr_templates, ctx, params)


# ── MIDI Tool bridge (v1.12.0+) ───────────────────────────────────────────
#
# These four run entirely in-process: install_miditool_device copies .amxd
# files, set_miditool_target writes to MidiToolCache + OSC-sends config,
# get_miditool_context reads the cache, list_miditool_generators reads the
# GENERATOR_METADATA dict. None of them need TCP or bridge round-trips.

async def _install_miditool_device(params: dict, ctx: Any = None) -> dict:
    from ..tools.miditool import install_miditool_device
    return await _call(install_miditool_device, ctx, params)


async def _set_miditool_target(params: dict, ctx: Any = None) -> dict:
    from ..tools.miditool import set_miditool_target
    return await _call(set_miditool_target, ctx, params)


async def _get_miditool_context(params: dict, ctx: Any = None) -> dict:
    from ..tools.miditool import get_miditool_context
    return await _call(get_miditool_context, ctx, params)


async def _list_miditool_generators(params: dict, ctx: Any = None) -> dict:
    from ..tools.miditool import list_miditool_generators
    return await _call(list_miditool_generators, ctx, params)


# ── Session memory writes (v1.20) ─────────────────────────────────────────
#
# remove_device emits an add_session_memory step to log its audit reason.
# Director Phase 6's escape hatch also writes tech_debt entries through
# this path. In-process — no TCP, no bridge.

async def _add_session_memory(params: dict, ctx: Any = None) -> dict:
    from ..memory.tools import add_session_memory
    return await _call(add_session_memory, ctx, params)


def build_mcp_dispatch_registry() -> dict[str, Callable]:
    """Return the canonical registry of MCP-only tools for plan execution.

    Callers (typically the server lifespan init) should call this once and
    pass the registry to execute_plan_steps_async via the mcp_registry kwarg.

    INVARIANT: the set of keys here must equal MCP_TOOLS in execution_router.
    Enforced by tests/test_mcp_dispatch_contract.py.
    """
    return {
        "load_sample_to_simpler": _load_sample_to_simpler,
        "apply_automation_shape": _apply_automation_shape,
        "apply_gesture_template": _apply_gesture_template,
        "analyze_mix": _analyze_mix,
        "get_master_spectrum": _get_master_spectrum,
        "get_emotional_arc": _get_emotional_arc,
        "get_motif_graph": _get_motif_graph,
        "generate_m4l_effect": _generate_m4l_effect,
        "install_m4l_device": _install_m4l_device,
        "list_genexpr_templates": _list_genexpr_templates,
        # v1.12.0 MIDI Tool bridge
        "install_miditool_device": _install_miditool_device,
        "set_miditool_target": _set_miditool_target,
        "get_miditool_context": _get_miditool_context,
        "list_miditool_generators": _list_miditool_generators,
        # v1.20 — session memory writes for remove_device audit + director
        # escape-hatch tech_debt logging.
        "add_session_memory": _add_session_memory,
    }

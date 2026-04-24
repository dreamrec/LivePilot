"""Unified async execution router for compiled plan steps.

Classifies each step by backend (remote_command, mcp_tool, bridge_command)
and dispatches through the correct transport. Async-only — there is no
sync path. Callers that need to execute plans live inside an async tool
and await execute_plan_steps_async.

Step backends:
  remote_command — valid Remote Script handler, goes through the sync TCP
                    client (ableton.send_command)
  bridge_command — M4L bridge handler, goes through the async UDP M4L bridge
                    client (bridge.send_command), NOT through ableton
  mcp_tool       — in-process Python function, dispatched via an mcp_registry
                    dict supplied by the server lifespan
  unknown        — not a valid target anywhere; returns a clear error

Step-result binding:
  Any step may carry an optional step_id. Later steps may reference an
  earlier result by setting a param to {"$from_step": "<id>", "path": "a.b"}.
  Resolved recursively BEFORE dispatch.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .remote_commands import BRIDGE_COMMANDS, REMOTE_COMMANDS


# MCP-only tools that exist as Python functions but NOT as TCP handlers.
# These must be called through direct import, not ableton.send_command().
# NOTE: capture_audio is a BRIDGE command (livepilot_bridge.js:146), not MCP.
# It used to be duplicated here; removed to keep classification unambiguous.
MCP_TOOLS: frozenset[str] = frozenset({
    "apply_automation_shape",
    "apply_gesture_template",
    "analyze_mix",
    "get_master_spectrum",
    "get_emotional_arc",
    "get_motif_graph",
    # Sample-engine workflow tools — async Python that orchestrates multiple
    # sub-commands (search_browser + load_browser_item + bridge.replace_simpler_sample).
    "load_sample_to_simpler",
    # Device Forge tools (MCP-only, no TCP handler)
    "generate_m4l_effect",
    "install_m4l_device",
    "list_genexpr_templates",
    # MIDI Tool bridge (v1.12.0+) — these run entirely in the MCP server:
    # config dispatch via OSC to m4l_bridge, cache state reads, filesystem
    # copy. No TCP remote command, no bridge TCP round-trip.
    "install_miditool_device",
    "set_miditool_target",
    "get_miditool_context",
    "list_miditool_generators",
    # Session memory writes (v1.20) — MCP-side store in mcp_server/memory/tools.py.
    # No TCP round-trip. Used by remove_device to audit destructive ops + by
    # the director's escape-hatch tech_debt logging.
    "add_session_memory",
    # Drum-rack pad construction (v1.20) — async orchestrator in
    # mcp_server/tools/analyzer.py:775 that composes insert_rack_chain +
    # set_drum_chain_note + insert_device + replace_sample_native. Used by
    # the create_drum_rack_pad semantic move.
    "add_drum_rack_pad",
})


# Tools that observe session state without mutating it. Executors use this set
# to separate "apply pass" steps (writes) from "verification reads". Counting
# reads toward applied_count and then calling undo that many times walks back
# earlier user edits — see preview_studio/tools.py and experiment/engine.py.
READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "get_track_meters",
    "get_master_spectrum",
    "get_master_meters",
    "get_master_rms",
    "get_mix_snapshot",
    "get_session_info",
    "get_track_info",
    "get_track_routing",
    "get_return_tracks",
    "get_device_info",
    "get_device_parameters",
    "get_clip_info",
    "get_notes",
    "get_arrangement_notes",
    "get_arrangement_clips",
    "get_scenes_info",
    "get_scene_matrix",
    "get_playing_clips",
    "get_cue_points",
    "get_rack_chains",
    "get_clip_automation",
    "analyze_mix",
    "get_emotional_arc",
    "get_motif_graph",
    "get_session_diagnostics",
    "ping",
})


def filter_apply_steps(steps: list) -> list:
    """Return only the steps that mutate session state.

    Read-only steps (meters, spectrum, info) do not create undo points in
    Ableton. Including them in an applied_count and then undoing that many
    times walks back earlier user edits. Always filter writes from reads
    before the apply pass and before the undo loop.
    """
    out = []
    for s in steps:
        tool = (s.get("tool") if isinstance(s, dict) else getattr(s, "tool", "")) or ""
        if tool and tool not in READ_ONLY_TOOLS:
            out.append(s)
    return out


@dataclass
class ExecutionResult:
    """Result of executing a single plan step."""

    ok: bool = False
    backend: str = ""
    tool: str = ""
    result: Any = None
    error: str = ""

    def to_dict(self) -> dict:
        d = {"ok": self.ok, "backend": self.backend, "tool": self.tool}
        if self.ok:
            d["result"] = self.result
        else:
            d["error"] = self.error
        return d


def classify_step(tool: str) -> str:
    """Classify a step's execution backend."""
    if tool in REMOTE_COMMANDS:
        return "remote_command"
    if tool in BRIDGE_COMMANDS:
        return "bridge_command"
    if tool in MCP_TOOLS:
        return "mcp_tool"
    return "unknown"


# ── Step-result binding ─────────────────────────────────────────────────

def _resolve_binding(binding: dict, step_results: dict) -> Any:
    """Resolve a {"$from_step": step_id, "path": "a.b.c"} binding.

    Raises ValueError with a clear message on missing step_id or missing key.
    """
    step_id = binding["$from_step"]
    path = binding.get("path", "")

    if step_id not in step_results:
        available = sorted(step_results.keys())
        raise ValueError(
            f"Step binding failed: step_id '{step_id}' not found. "
            f"Available: {available or '(no earlier results)'}"
        )

    current = step_results[step_id]
    if not isinstance(current, dict):
        raise ValueError(
            f"Step binding failed: result of '{step_id}' is "
            f"{type(current).__name__}, not a dict"
        )

    if not path:
        return current

    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            keys = list(current.keys()) if isinstance(current, dict) else type(current).__name__
            raise ValueError(
                f"Step binding failed: path '{path}' not found in result of "
                f"'{step_id}'. Available at this level: {keys}"
            )
        current = current[segment]

    return current


def _resolve_params(params: Any, step_results: dict) -> Any:
    """Recursively walk params and resolve any $from_step bindings."""
    if isinstance(params, dict):
        if "$from_step" in params:
            return _resolve_binding(params, step_results)
        return {k: _resolve_params(v, step_results) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_params(v, step_results) for v in params]
    return params


# ── Async execution path ────────────────────────────────────────────────

async def _execute_step_async(
    tool: str,
    params: dict,
    ableton: Any,
    bridge: Any,
    mcp_registry: dict[str, Callable],
    ctx: Any,
    declared_backend: Optional[str] = None,
) -> ExecutionResult:
    """Dispatch a single step through the correct transport, async-aware."""
    backend = (
        declared_backend
        if declared_backend in ("remote_command", "bridge_command", "mcp_tool")
        else classify_step(tool)
    )

    if backend == "remote_command":
        if ableton is None:
            return ExecutionResult(
                ok=False, backend=backend, tool=tool,
                error="Ableton connection unavailable",
            )
        try:
            result = ableton.send_command(tool, params)
            if isinstance(result, dict) and "error" in result:
                return ExecutionResult(ok=False, backend=backend, tool=tool, error=result["error"])
            return ExecutionResult(ok=True, backend=backend, tool=tool, result=result)
        except Exception as e:
            return ExecutionResult(ok=False, backend=backend, tool=tool, error=str(e))

    if backend == "bridge_command":
        if bridge is None:
            return ExecutionResult(
                ok=False, backend=backend, tool=tool,
                error="M4L bridge unavailable — cannot dispatch bridge command",
            )
        try:
            # M4LBridge.send_command accepts (command, *args) and OSC-encodes
            # each arg positionally. Plan authors construct params dicts in
            # the order the bridge command expects; we unpack by insertion
            # order (Python 3.7+ guarantees this). This keeps plans readable
            # while matching the real bridge's positional wire format.
            positional = list(params.values()) if params else []
            call = bridge.send_command(tool, *positional)
            result = await call if inspect.isawaitable(call) else call
            if isinstance(result, dict) and "error" in result:
                return ExecutionResult(ok=False, backend=backend, tool=tool, error=result["error"])
            return ExecutionResult(ok=True, backend=backend, tool=tool, result=result)
        except Exception as e:
            return ExecutionResult(ok=False, backend=backend, tool=tool, error=str(e))

    if backend == "mcp_tool":
        fn = mcp_registry.get(tool) if mcp_registry else None
        if fn is None:
            return ExecutionResult(
                ok=False, backend=backend, tool=tool,
                error=(
                    f"MCP tool '{tool}' not registered in async router dispatch map. "
                    f"Add it to mcp_server.runtime.mcp_dispatch.build_mcp_dispatch_registry()."
                ),
            )
        try:
            sig = inspect.signature(fn)
            kwargs = {"ctx": ctx} if "ctx" in sig.parameters else {}
            call = fn(params, **kwargs)
            result = await call if inspect.isawaitable(call) else call
            if isinstance(result, dict) and "error" in result:
                return ExecutionResult(ok=False, backend=backend, tool=tool, error=result["error"])
            return ExecutionResult(ok=True, backend=backend, tool=tool, result=result)
        except Exception as e:
            return ExecutionResult(ok=False, backend=backend, tool=tool, error=str(e))

    return ExecutionResult(
        ok=False, backend="unknown", tool=tool,
        error=(
            f"Unknown tool '{tool}' — not a Remote Script command, "
            f"bridge command, or registered MCP tool"
        ),
    )


async def execute_plan_steps_async(
    steps: list[dict],
    ableton: Any = None,
    bridge: Any = None,
    mcp_registry: Optional[dict[str, Callable]] = None,
    ctx: Any = None,
    stop_on_failure: bool = True,
) -> list[ExecutionResult]:
    """Async plan executor with step-result binding and correct bridge transport.

    Supports three backends:
      - remote_command via ableton.send_command (sync TCP client)
      - bridge_command via bridge.send_command  (async UDP M4L bridge client)
      - mcp_tool       via mcp_registry[tool](params, ctx=ctx)

    Step-result binding:
      Any step may carry an optional "step_id". Later steps may reference an
      earlier result by setting a param to {"$from_step": "<id>", "path": "a.b"}.
      The router walks params recursively and resolves bindings before dispatch.
      Missing ids or missing paths fail that step with a clear error.

    stop_on_failure: Stop the plan on the first failing step (default). Set to
      False for best-effort execution (each result still recorded).
    """
    results: list[ExecutionResult] = []
    step_results: dict[str, Any] = {}
    mcp_registry = mcp_registry or {}

    for step in steps:
        tool = step.get("tool") or step.get("command", "")
        raw_params = step.get("params") or step.get("args", {}) or {}
        step_id = step.get("step_id")
        declared_backend = step.get("backend")
        # v1.20.2 (BUG #3 fix): optional steps whose failure should NOT
        # halt the plan. Used for soft pre-reads like get_master_spectrum
        # that depend on the analyzer being loaded.
        is_optional = bool(step.get("optional", False))

        if not tool:
            results.append(ExecutionResult(
                ok=False, backend="unknown", tool="",
                error="Step has no tool/command field",
            ))
            if stop_on_failure:
                break
            continue

        # Resolve any $from_step bindings in params BEFORE dispatch.
        try:
            params = _resolve_params(raw_params, step_results)
        except ValueError as e:
            results.append(ExecutionResult(
                ok=False, backend="binding", tool=tool, error=str(e),
            ))
            if stop_on_failure:
                break
            continue

        result = await _execute_step_async(
            tool, params,
            ableton=ableton, bridge=bridge,
            mcp_registry=mcp_registry, ctx=ctx,
            declared_backend=declared_backend,
        )
        results.append(result)

        # Record successful step result for future bindings
        if result.ok and step_id:
            if isinstance(result.result, dict):
                step_results[step_id] = result.result
            else:
                # Log but DO NOT silently drop the binding without telling
                # anyone — the previous version let non-dict results slip
                # past, which meant any downstream {"$from_step": step_id}
                # reference blew up with a confusing "step_id not found"
                # instead of the real "result wasn't a dict" cause.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "step_results: dropping non-dict result for "
                    "step_id=%s tool=%s type=%s. Any $from_step refs to "
                    "this step_id will fail with 'step_id not found'.",
                    step_id, tool, type(result.result).__name__,
                )

        if not result.ok and stop_on_failure:
            if is_optional:
                # Optional step failed — log a warning but CONTINUE to
                # subsequent steps. Per BUG #3 fix (v1.20.2): analyzer pre-
                # reads and other soft dependencies shouldn't halt the
                # plan's actual mutation work.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "execute_plan_steps_async: optional step %r failed "
                    "(%s); continuing to next step.",
                    tool, result.error,
                )
                continue
            break

    return results

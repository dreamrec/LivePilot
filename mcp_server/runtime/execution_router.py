"""Unified execution router for compiled plan steps.

Classifies each step by backend (remote_command, mcp_tool, bridge_command)
and dispatches to the correct execution path. Replaces the pattern of
sending everything through ableton.send_command() blindly.

Step backends:
  remote_command — valid Remote Script handler, goes through TCP
  bridge_command — M4L bridge handler, goes through the UDP M4L bridge client
                    (NOT through ableton.send_command — different transport)
  mcp_tool       — in-process Python function, dispatched via mcp_registry
  unknown        — not a valid target anywhere

Two executors exist:
  execute_plan_steps       — sync legacy path. Bridge commands still go through
                             ableton.send_command, which is wrong for bridge
                             transport but preserved for back-compat with old
                             callers that don't pass an async bridge client.
  execute_plan_steps_async — canonical async path. Handles all three backends
                             through their correct transports AND supports
                             step-result binding via {"$from_step": ..., "path": ...}.

Prefer the async path for new call sites. Migrate old sites in later PRs.
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
})


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


def execute_step(
    tool: str,
    params: dict,
    ableton: Any = None,
    ctx: Any = None,
    declared_backend: str | None = None,
) -> ExecutionResult:
    """Execute a single plan step through the correct backend."""
    backend = declared_backend if declared_backend in ("remote_command", "bridge_command", "mcp_tool") else classify_step(tool)

    if backend in ("remote_command", "bridge_command"):
        if ableton is None:
            return ExecutionResult(
                ok=False, backend=backend, tool=tool,
                error="Ableton connection unavailable",
            )
        try:
            result = ableton.send_command(tool, params)
            return ExecutionResult(ok=True, backend=backend, tool=tool, result=result)
        except Exception as e:
            return ExecutionResult(ok=False, backend=backend, tool=tool, error=str(e))

    elif backend == "mcp_tool":
        # MCP tools require direct Python dispatch.
        # For now, return a clear error — full MCP dispatch is wired per-tool
        # in the callers (apply_semantic_move, render_preview_variant).
        return ExecutionResult(
            ok=False, backend=backend, tool=tool,
            error=f"MCP tool '{tool}' requires direct Python dispatch — "
                  f"not executable through TCP. Use the MCP layer directly.",
        )

    else:
        return ExecutionResult(
            ok=False, backend="unknown", tool=tool,
            error=f"Unknown tool '{tool}' — not a Remote Script command, "
                  f"bridge command, or registered MCP tool",
        )


def execute_plan_steps(
    steps: list[dict],
    ableton: Any = None,
    ctx: Any = None,
    stop_on_failure: bool = True,
) -> list[ExecutionResult]:
    """Execute a list of plan steps, returning results for each.

    Stops on first failure by default. Set stop_on_failure=False
    to continue past errors (useful for best-effort execution).

    NOTE: This is the legacy sync path. Bridge commands still route through
    ableton.send_command, which is the wrong transport. New callers should use
    execute_plan_steps_async which dispatches bridge commands through the
    async M4L bridge client.
    """
    results: list[ExecutionResult] = []

    for step in steps:
        tool = step.get("tool") or step.get("command", "")
        params = step.get("params") or step.get("args", {})
        # Honor declared backend from step annotations (PR5) if present
        declared_backend = step.get("backend")

        if not tool:
            results.append(ExecutionResult(
                ok=False, backend="unknown", tool="",
                error="Step has no tool/command field",
            ))
            if stop_on_failure:
                break
            continue

        result = execute_step(tool, params, ableton=ableton, ctx=ctx, declared_backend=declared_backend)
        results.append(result)

        if not result.ok and stop_on_failure:
            break

    return results


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
            # Real bridge client accepts positional args; fakes may too.
            # Pass params as a single dict arg for forward-compat.
            call = bridge.send_command(tool, params) if params else bridge.send_command(tool)
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
        if result.ok and step_id and isinstance(result.result, dict):
            step_results[step_id] = result.result

        if not result.ok and stop_on_failure:
            break

    return results

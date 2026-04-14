"""Unified execution router for compiled plan steps.

Classifies each step by backend (remote_command, mcp_tool, bridge_command)
and dispatches to the correct execution path. Replaces the pattern of
sending everything through ableton.send_command() blindly.

Step backends:
  remote_command — valid Remote Script handler, goes through TCP
  bridge_command — M4L bridge handler, goes through TCP (requires bridge)
  mcp_tool — MCP-layer Python function, called directly
  unknown — not a valid target anywhere
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

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

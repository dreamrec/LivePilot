"""MCP tool wrapper for the Safety Kernel.

Tools:
  check_safety — validate a proposed action before executing
"""

from __future__ import annotations

import json

from fastmcp import Context

from ..server import mcp
from .safety_kernel import check_action_safety


@mcp.tool()
def check_safety(ctx: Context, action: str, scope: str = "{}") -> dict:
    """Validate a proposed action against safety policies before executing.

    Parameters
    ----------
    action : str
        The tool / command name to check (e.g. "delete_track").
    scope : str
        JSON string describing what the action will affect.
        Recognised keys: ``track_count`` (int).
        Defaults to ``"{}"``.

    Returns
    -------
    dict
        SafetyCheck with keys: action, allowed, risk_level, reason,
        requires_confirmation.
    """
    try:
        scope_dict = json.loads(scope) if isinstance(scope, str) else scope
    except (json.JSONDecodeError, TypeError):
        scope_dict = {}

    result = check_action_safety(action, scope=scope_dict)
    return result.to_dict()

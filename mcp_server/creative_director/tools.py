"""Creative Director MCP tools — v1.18.3+ brief compliance.

Exposes `check_brief_compliance` as an MCP tool so the
`livepilot-creative-director` skill can call it before each risky
Phase 6 tool execution. Caller passes the compiled brief dict + the
intended tool call; the tool returns a violations report.

Stateless by design: no session storage of the active brief. The
director passes the brief each time. Full session-state active-brief
storage is v1.19 scope.
"""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context

from ..server import mcp
from .compliance import check_brief_compliance as _check_brief_compliance


@mcp.tool()
def check_brief_compliance(
    ctx: Context,
    brief: dict,
    tool_name: str,
    tool_args: Optional[dict] = None,
) -> dict:
    """Check whether an intended tool call complies with the active creative brief.

    v1.18.3 #7 + #8 runtime enforcement for the director's anti_patterns
    and locked_dimensions brief fields. Call this BEFORE executing any
    risky tool from director's Phase 6 — especially when the brief has
    non-empty anti_patterns or locked_dimensions.

    brief: the compiled Creative Brief dict. May contain anti_patterns
           (list of prose phrases), locked_dimensions (list of:
           structural/rhythmic/timbral/spatial), reference_anchors, etc.
    tool_name: the MCP tool name you're about to call.
    tool_args: dict of arguments you'll pass to that tool.

    Returns:
        {
          "ok": bool,
          "violations": [
            {
              "rule": "anti_pattern" | "locked_dimension",
              "detail": <the anti_pattern phrase OR the locked dimension>,
              "reason": "Why this call appears to violate the brief",
              "suggestion": "What to do about it",
            },
            ...
          ],
        }

    Violations are NEVER automatic blocks — they're reports. The
    director decides whether to proceed, surface to user, or abandon.
    Empty brief (no anti_patterns, no locked_dimensions) always
    returns ok=True.

    Best-effort keyword heuristic, NOT semantic understanding. Will
    miss subtle violations (e.g., 'too muddy' → 300 Hz cut needs
    judgment this checker doesn't have). Will catch obvious ones
    (e.g., 'bright top-end' → Hi Gain positive boost).
    """
    result = _check_brief_compliance(
        brief=brief,
        tool_name=tool_name,
        tool_args=tool_args or {},
    )
    return result

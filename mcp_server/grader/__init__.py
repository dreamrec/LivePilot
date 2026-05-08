"""Rubric grader — mechanical checks on session state.

Phase 1 ships one rubric: §7.3 layer accumulation. Pure-Python checks,
zero LLM calls. Wire-up to MCP tools lands in Phase 2.

Usage:
    from mcp_server.grader import evaluate, format_revision_brief

    verdict = evaluate("layer_accumulation", state)
    if not verdict["passed"]:
        brief = format_revision_brief(verdict)
"""

from mcp_server.grader.client import evaluate
from mcp_server.grader.iterator import format_revision_brief

__all__ = ["evaluate", "format_revision_brief"]

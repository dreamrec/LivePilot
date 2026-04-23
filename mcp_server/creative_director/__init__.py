"""Creative Director — v1.18.3+ runtime compliance check for brief constraints.

The livepilot-creative-director skill compiles a Creative Brief inline in
each creative turn. The brief's `anti_patterns` and `locked_dimensions`
fields were previously advisory — no runtime machinery verified that
intended tool calls respected them.

This module ships the minimum-effective enforcement layer: a pure
check function `check_brief_compliance(brief, tool_name, tool_args)`
that returns {"ok": bool, "violations": [...]}. Director's Phase 6
calls it before each risky tool execution. Violations don't block
execution automatically — the director reports them to the user, who
can override or abandon.

Full session-state active-brief storage + automatic interception is a
v1.19 scope item.
"""

from .compliance import check_brief_compliance

__all__ = ["check_brief_compliance"]

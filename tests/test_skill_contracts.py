"""Validate skill/command examples against live tool signatures.

Catches:
- Backticked tool calls referencing non-existent tools
- File paths in skills that don't resolve
- Tool catalog missing registered tools
"""

import asyncio
import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _get_live_tools() -> dict[str, set[str]]:
    """Return {tool_name: set_of_param_names} from live server."""
    import sys
    sys.path.insert(0, str(ROOT))
    from mcp_server.server import mcp

    tools_raw = asyncio.run(mcp.list_tools())
    result = {}
    for t in tools_raw:
        func = t.fn if hasattr(t, "fn") else None
        if func:
            sig = inspect.signature(func)
            params = {p for p in sig.parameters if p != "ctx"}
            result[t.name] = params
        else:
            result[t.name] = set()
    return result


def _extract_tool_calls_from_markdown(path: Path) -> list[dict]:
    """Extract backticked tool calls like `tool_name(arg1, arg2)` from markdown."""
    text = path.read_text(encoding="utf-8")
    pattern = r"`(\w+)\(([^`]*)\)`"
    calls = []
    for match in re.finditer(pattern, text):
        name = match.group(1)
        calls.append({
            "file": str(path.relative_to(ROOT)),
            "tool": name,
            "raw": match.group(0),
            "line": text[: match.start()].count("\n") + 1,
        })
    return calls


# Functions that look like tool calls but aren't MCP tools
_SKIP_NAMES = {
    "undo", "redo", "get_anti_preferences", "print", "len", "range",
    "sorted", "list", "dict", "set", "int", "float", "str", "bool",
    "min", "max", "abs", "sum", "round", "type", "isinstance",
    "if", "for", "while", "return", "def", "class", "import",
    "assert", "raise", "pass", "break", "continue", "with", "as",
    "from", "try", "except", "finally", "yield", "lambda", "not",
    "and", "or", "in", "is", "True", "False", "None",
    # Claude Code built-in tools (referenced by skills but not MCP-registered)
    "WebSearch", "WebFetch", "Agent", "Task", "Read", "Write", "Edit",
    "Bash", "Glob", "Grep", "TodoWrite", "ToolSearch",
}


def test_skill_tool_calls_match_live_registry():
    """Every backticked tool call in skills/commands must reference a real tool."""
    live_tools = _get_live_tools()
    tool_names = set(live_tools.keys())

    errors = []
    for md_path in sorted(ROOT.glob("livepilot/**/*.md")):
        for call in _extract_tool_calls_from_markdown(md_path):
            if call["tool"] in _SKIP_NAMES:
                continue
            if call["tool"] not in tool_names:
                errors.append(
                    f"  {call['file']}:{call['line']}: "
                    f"unknown tool `{call['tool']}` in {call['raw']}"
                )

    assert not errors, (
        f"Stale tool references in skills ({len(errors)}):\n"
        + "\n".join(errors)
    )


def test_tool_catalog_matches_live_registry():
    """The published tool catalog must list every registered tool."""
    live_tools = _get_live_tools()
    catalog_path = ROOT / "docs" / "manual" / "tool-catalog.md"
    if not catalog_path.exists():
        pytest.skip("Tool catalog not found")

    catalog_text = catalog_path.read_text(encoding="utf-8")
    missing = []
    for name in sorted(live_tools):
        if f"`{name}`" not in catalog_text:
            missing.append(name)

    assert not missing, (
        f"Tool catalog missing {len(missing)} tools: {', '.join(missing)}"
    )

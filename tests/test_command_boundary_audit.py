"""Static boundary audit: every ableton.send_command() target must exist
in the Remote Script.

CI fails if any MCP code calls a non-existent Remote Script command
through the raw TCP connection.
"""

import ast
from pathlib import Path

from mcp_server.runtime.remote_commands import ALL_VALID_COMMANDS, REMOTE_COMMANDS


MCP_SERVER = Path(__file__).resolve().parents[1] / "mcp_server"
REMOTE_SCRIPT = Path(__file__).resolve().parents[1] / "remote_script" / "LivePilot"
_REMOTE_COMMAND_EXCEPTIONS = {"ping", "reload_handlers"}


def _find_send_command_targets() -> list[tuple[str, int, str]]:
    """Find all direct send_command("...") calls under mcp_server/.

    AST scanning catches multiline calls and nested packages; the previous
    regex only checked one-line calls in hand-picked top-level directories.
    """
    results = []
    for py_file in MCP_SERVER.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "send_command":
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                results.append((
                    str(py_file.relative_to(MCP_SERVER.parent)),
                    node.lineno,
                    first.value,
                ))
    return results


def _registered_remote_handlers() -> set[str]:
    """Return command names declared by @register("...") in Remote Script."""
    registered: set[str] = set()
    for py_file in REMOTE_SCRIPT.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not decorator.args:
                    continue
                func = decorator.func
                is_register = (
                    isinstance(func, ast.Name) and func.id == "register"
                ) or (
                    isinstance(func, ast.Attribute) and func.attr == "register"
                )
                first = decorator.args[0]
                if (
                    is_register
                    and isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                ):
                    registered.add(first.value)
    return registered


def test_all_send_command_targets_are_valid_remote_commands():
    """Every ableton.send_command target must be a registered Remote Script command."""
    violations = []
    for filepath, line, cmd in _find_send_command_targets():
        if cmd not in ALL_VALID_COMMANDS:
            violations.append(
                f"  {filepath}:{line} — send_command(\"{cmd}\") is NOT a Remote Script command"
            )

    assert not violations, (
        f"Found {len(violations)} send_command calls targeting non-existent "
        f"Remote Script commands:\n" + "\n".join(violations)
    )


def test_remote_commands_set_is_not_empty():
    """Sanity check: the command set should have the expected size."""
    assert len(REMOTE_COMMANDS) >= 80, (
        f"Expected at least 80 Remote Script commands, got {len(REMOTE_COMMANDS)}"
    )


def test_remote_commands_matches_registered_handlers():
    """REMOTE_COMMANDS must track every @register handler exactly.

    The async execution router depends on REMOTE_COMMANDS to decide whether
    a compiled step can travel over TCP. If this set drifts, valid handlers
    become "unknown" or nonexistent handlers get routed to Live.
    """
    registered = _registered_remote_handlers()
    missing = registered - REMOTE_COMMANDS
    extra = REMOTE_COMMANDS - registered - _REMOTE_COMMAND_EXCEPTIONS

    assert not missing, (
        "These @register handlers are missing from REMOTE_COMMANDS: "
        f"{sorted(missing)}"
    )
    assert not extra, (
        "These REMOTE_COMMANDS entries have no @register handler: "
        f"{sorted(extra)}"
    )

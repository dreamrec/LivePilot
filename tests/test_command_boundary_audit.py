"""Static boundary audit: every ableton.send_command() target must exist
in the Remote Script.

CI fails if any MCP code calls a non-existent Remote Script command
through the raw TCP connection.
"""

import re
from pathlib import Path

from mcp_server.runtime.remote_commands import ALL_VALID_COMMANDS, REMOTE_COMMANDS


MCP_SERVER = Path(__file__).resolve().parents[1] / "mcp_server"

# Directories to scan for send_command calls
_SCAN_DIRS = [
    MCP_SERVER / "song_brain",
    MCP_SERVER / "hook_hunter",
    MCP_SERVER / "musical_intelligence",
    MCP_SERVER / "preview_studio",
    MCP_SERVER / "semantic_moves",
    MCP_SERVER / "tools",
    MCP_SERVER / "mix_engine",
    MCP_SERVER / "evaluation",
    MCP_SERVER / "wonder_mode",
    MCP_SERVER / "session_continuity",
    MCP_SERVER / "creative_constraints",
    MCP_SERVER / "sound_design",
    MCP_SERVER / "transition_engine",
    MCP_SERVER / "reference_engine",
    MCP_SERVER / "translation_engine",
    MCP_SERVER / "performance_engine",
    MCP_SERVER / "project_brain",
    MCP_SERVER / "runtime",
    MCP_SERVER / "experiment",
]

# Pattern: send_command("command_name" or send_command('command_name'
_SEND_CMD_RE = re.compile(r'send_command\(\s*["\']([^"\']+)["\']')


def _find_send_command_targets() -> list[tuple[str, int, str]]:
    """Find all send_command("...") calls and extract the command string."""
    results = []
    for scan_dir in _SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(source.splitlines(), 1):
                match = _SEND_CMD_RE.search(line)
                if match:
                    results.append((
                        str(py_file.relative_to(MCP_SERVER.parent)),
                        i,
                        match.group(1),
                    ))
    return results


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

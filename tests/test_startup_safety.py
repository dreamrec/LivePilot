"""Tests for startup safety — port conflict handling (audit fix).

Verifies that the MCP server does NOT kill foreign processes when
UDP port 9880 is busy, and gracefully degrades analyzer functionality.

Run with: .venv/bin/python -m pytest tests/test_startup_safety.py -v
"""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestStartupSafety:
    """Verify that _kill_port_holder is removed and _identify_port_holder is safe."""

    def test_kill_port_holder_removed(self):
        """The dangerous _kill_port_holder function must not exist."""
        from mcp_server import server
        assert not hasattr(server, "_kill_port_holder"), (
            "_kill_port_holder still exists — it must be removed for startup safety"
        )

    def test_identify_port_holder_exists(self):
        """The safe _identify_port_holder function must exist."""
        from mcp_server import server
        assert hasattr(server, "_identify_port_holder"), (
            "_identify_port_holder missing — needed for safe port conflict logging"
        )

    def test_identify_does_not_kill(self):
        """_identify_port_holder must not contain os.kill calls."""
        import inspect
        from mcp_server.server import _identify_port_holder
        source = inspect.getsource(_identify_port_holder)
        assert "os.kill" not in source, (
            "_identify_port_holder contains os.kill — must be read-only"
        )
        assert "signal.SIGTERM" not in source, (
            "_identify_port_holder contains SIGTERM — must be read-only"
        )
        assert "signal.SIGKILL" not in source, (
            "_identify_port_holder contains SIGKILL — must be read-only"
        )

    def test_identify_returns_none_for_free_port(self):
        """When no process holds the port, should return None.

        BUG-audit-M4: earlier versions of this test hardcoded port 59999
        as "almost certainly free" — which failed intermittently when
        another process (e.g., the hosting Claude Desktop app) happened
        to be listening there. Instead, bind-and-release a kernel-
        assigned port to get a guaranteed-free port number.
        """
        import socket

        from mcp_server.server import _identify_port_holder

        # Bind to an OS-assigned ephemeral port, read the number, then
        # release. The kernel won't immediately reassign it, so it's
        # genuinely free when _identify_port_holder queries lsof.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        # Socket closed → port free
        result = _identify_port_holder(free_port)
        assert result is None, (
            f"Port {free_port} was just freed but lsof reports: {result}"
        )

    def test_identify_returns_none_on_lsof_timeout(self, monkeypatch):
        """BUG from Batch-6 debug session: _identify_port_holder used to let
        subprocess.TimeoutExpired propagate when lsof took >3s on a busy
        system — stalling startup with an ugly stack trace. Caller should
        see None just like any other identification failure."""
        import subprocess
        from mcp_server import server

        def _boom(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0] if args else "lsof",
                                             timeout=3)
        monkeypatch.setattr(server.subprocess, "check_output", _boom)

        result = server._identify_port_holder(9999)
        assert result is None, (
            "Timeout during lsof must degrade to None, not raise"
        )

    def test_no_signal_import(self):
        """The signal module should not be imported in server.py."""
        import inspect
        from mcp_server import server
        source = inspect.getsource(server)
        # Check that 'import signal' is not present
        assert "import signal" not in source, (
            "server.py still imports signal — should be removed"
        )


class TestCodexPlugin:
    """Verify Codex plugin packaging exists alongside Claude plugin."""

    def test_codex_plugin_json_exists(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        codex_path = os.path.join(base, "livepilot", ".Codex-plugin", "plugin.json")
        assert os.path.exists(codex_path), (
            f"Codex plugin.json not found at {codex_path}"
        )

    def test_codex_matches_claude(self):
        import json
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        claude_path = os.path.join(base, "livepilot", ".claude-plugin", "plugin.json")
        codex_path = os.path.join(base, "livepilot", ".Codex-plugin", "plugin.json")
        with open(claude_path) as f:
            claude = json.load(f)
        with open(codex_path) as f:
            codex = json.load(f)
        assert claude["version"] == codex["version"], (
            f"Version mismatch: Claude={claude['version']}, Codex={codex['version']}"
        )
        assert claude["name"] == codex["name"], (
            f"Name mismatch: Claude={claude['name']}, Codex={codex['name']}"
        )

"""Socket-level tests for the Remote Script single-client guard."""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import time
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"


def _load_server_module():
    for name in [
        "remote_script.LivePilot.server",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
    ]:
        sys.modules.pop(name, None)

    remote_pkg = types.ModuleType("remote_script")
    remote_pkg.__path__ = [str(ROOT / "remote_script")]
    sys.modules["remote_script"] = remote_pkg

    live_pkg = types.ModuleType("remote_script.LivePilot")
    live_pkg.__path__ = [str(REMOTE_ROOT)]
    sys.modules["remote_script.LivePilot"] = live_pkg

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    _load("remote_script.LivePilot.utils", REMOTE_ROOT / "utils.py")
    _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    return _load("remote_script.LivePilot.server", REMOTE_ROOT / "server.py")


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class _FakeControlSurface:
    def __init__(self):
        self.logs = []

    def log_message(self, message):
        self.logs.append(message)

    def schedule_message(self, _delay, func):
        func()

    def song(self):
        return object()


def test_second_client_gets_explicit_state_error():
    server_mod = _load_server_module()
    cs = _FakeControlSurface()
    server = server_mod.LivePilotServer(cs, port=0)

    first = None
    second = None
    try:
        server.start()
        assert _wait_until(lambda: server._server_socket is not None)
        # Use the actual bound address (may be IPv4 or IPv6 depending on OS)
        host, port = server._server_socket.getsockname()[:2]
        if host == "" or host == "0.0.0.0" or host == "::":
            host = "127.0.0.1"

        first = socket.create_connection((host, port), timeout=2.0)
        assert _wait_until(lambda: server._client_connected)

        second = socket.create_connection((host, port), timeout=2.0)
        second.settimeout(2.0)
        payload = second.recv(4096).decode("utf-8").strip()
        response = json.loads(payload)

        assert response["ok"] is False
        assert response["error"]["code"] == "STATE_ERROR"
        assert "already connected" in response["error"]["message"]
    finally:
        if first is not None:
            first.close()
        if second is not None:
            second.close()
        server.stop()


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


def test_second_client_replaces_stale_connection():
    """A new connection kicks the stale one and becomes active.

    LivePilot is single-client by design, but rejecting concurrent
    connections (the previous behavior) had a footgun: when the MCP
    server restarted uncleanly, the Remote Script's recv() loop didn't
    notice the disconnect for up to a second. During that window, the
    legitimate reconnect attempt got rejected with STATE_ERROR — often
    requiring an Ableton restart to recover.

    The kick-stale-and-accept policy treats a new connection as proof
    that the old one is dead, which is the right call given the
    single-client architecture.
    """
    server_mod = _load_server_module()
    cs = _FakeControlSurface()
    server = server_mod.LivePilotServer(cs, port=0)

    first = None
    second = None
    try:
        server.start()
        assert _wait_until(
            lambda: server._server_socket is not None
            and server._server_socket.getsockname()[1] != 0
        )
        host, port = server._server_socket.getsockname()[:2]
        if host == "" or host == "0.0.0.0" or host == "::":
            host = "127.0.0.1"

        first = socket.create_connection((host, port), timeout=2.0)
        assert _wait_until(lambda: server._client_connected)
        first_socket_at_connect = server._current_client

        # Open a second connection — this should kick the first.
        second = socket.create_connection((host, port), timeout=2.0)

        # The first socket should now be the kicked one — confirm by
        # observing that the server's _current_client reference flipped
        # to the new socket (different object identity).
        assert _wait_until(
            lambda: server._current_client is not None
            and server._current_client is not first_socket_at_connect
        ), "expected _current_client to be replaced by the new connection"

        # The first socket's recv() should now return EOF (b'') because
        # the server closed it from the accept loop.
        first.settimeout(2.0)
        try:
            data = first.recv(4096)
        except OSError:
            data = b""
        assert data == b"", "first client should observe EOF after being replaced"

        # And the new connection should NOT receive a STATE_ERROR (no
        # rejection JSON appears on the wire).
        second.settimeout(0.5)
        try:
            leftover = second.recv(4096)
        except (socket.timeout, OSError):
            leftover = b""
        assert leftover == b"", (
            "second client should not receive a STATE_ERROR rejection — "
            f"got {leftover!r}"
        )
    finally:
        if first is not None:
            try: first.close()
            except OSError: pass
        if second is not None:
            try: second.close()
            except OSError: pass
        server.stop()


def test_schedule_message_disconnect_sends_state_error():
    server_mod = _load_server_module()

    class _DisconnectingControlSurface:
        def schedule_message(self, _delay, _func):
            raise AssertionError("disconnecting")

        def log_message(self, _message):
            return None

    class _FakeClient:
        def __init__(self):
            self.payloads = []

        def sendall(self, payload):
            self.payloads.append(payload.decode("utf-8"))

    server = server_mod.LivePilotServer(_DisconnectingControlSurface(), port=0)
    client = _FakeClient()

    server._process_line(client, json.dumps({"id": "abc", "type": "ping"}))

    assert client.payloads, "disconnect path should send a response to the client"
    response = json.loads(client.payloads[0].strip())
    assert response["ok"] is False
    assert response["error"]["code"] == "STATE_ERROR"

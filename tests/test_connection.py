"""Mock socket tests for AbletonConnection."""

import json
import socket
import threading
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.connection import AbletonConnection, AbletonConnectionError
import mcp_server.connection as connection_mod


class MockAbletonServer:
    """A minimal TCP server that mimics the LivePilot Remote Script protocol.

    Protocol: JSON-over-newline on TCP.
    Request:  {"id": "abc", "type": "set_tempo", "params": {"tempo": 140}}
    Success:  {"id": "abc", "ok": true, "result": {"tempo": 140.0}}
    Error:    {"id": "abc", "ok": false, "error": {"code": "INVALID_PARAM", "message": "..."}}
    Ping:     {"id": "abc", "type": "ping"} -> {"id": "abc", "ok": true, "result": {"pong": true}}
    """

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._running = True
        self._custom_responses = {}
        self._error_responses = {}
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def set_response(self, command_type, result):
        """Register a custom result for a given command_type."""
        self._custom_responses[command_type] = result

    def set_error(self, command_type, code, message):
        """Register an error response for a given command_type."""
        self._error_responses[command_type] = {"code": code, "message": message}

    def _accept_loop(self):
        self._sock.settimeout(1.0)
        while self._running:
            try:
                client, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client):
        buf = b""
        client.settimeout(5.0)
        try:
            while self._running:
                chunk = client.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        request = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    response = self._build_response(request)
                    client.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except (socket.timeout, OSError):
            pass
        finally:
            client.close()

    def _build_response(self, request):
        req_type = request.get("type", "")
        request_id = request.get("id", "unknown")

        if req_type == "ping":
            return {
                "id": request_id,
                "ok": True,
                "result": {"pong": True},
            }

        if req_type in self._error_responses:
            return {
                "id": request_id,
                "ok": False,
                "error": self._error_responses[req_type],
            }

        if req_type in self._custom_responses:
            return {
                "id": request_id,
                "ok": True,
                "result": self._custom_responses[req_type],
            }

        return {
            "id": request_id,
            "ok": True,
            "result": {},
        }

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=3)


@pytest.fixture
def mock_server():
    server = MockAbletonServer()
    yield server
    server.stop()


def test_connect_and_ping(mock_server):
    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()
    try:
        assert conn.ping() is True
    finally:
        conn.disconnect()


def test_send_command(mock_server):
    mock_server.set_response("get_session_info", {
        "tempo": 120.0,
        "is_playing": False,
        "track_count": 4,
    })
    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()
    try:
        result = conn.send_command("get_session_info")
        assert result["tempo"] == 120.0
        assert result["is_playing"] is False
        assert result["track_count"] == 4
    finally:
        conn.disconnect()


def test_error_response(mock_server):
    mock_server.set_error("bad_command", "INVALID_PARAM", "Tempo must be between 20 and 999")
    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()
    try:
        with pytest.raises(Exception, match="INVALID_PARAM.*Tempo must be between 20 and 999"):
            conn.send_command("bad_command")
    finally:
        conn.disconnect()


def test_connection_refused():
    conn = AbletonConnection(host="127.0.0.1", port=19999)
    with pytest.raises(AbletonConnectionError):
        conn.connect()


def test_disconnect_clears_recv_buf():
    """Verify disconnect() discards partial receive buffer so retries
    don't corrupt the next response with leftover bytes."""
    conn = AbletonConnection(host="127.0.0.1", port=19999)
    # Simulate partial data left in buffer
    conn._recv_buf = b'{"partial": tru'
    conn.disconnect()
    assert conn._recv_buf == b"", "disconnect must clear _recv_buf"


def test_retry_after_timeout_gets_clean_response(mock_server):
    """After a timeout + reconnect, the next command should not see
    leftover bytes from the failed attempt."""
    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()
    try:
        # Inject garbage into the recv buffer to simulate partial read
        conn._recv_buf = b'{"broken": '
        # disconnect should clear it
        conn.disconnect()
        assert conn._recv_buf == b""
        # Reconnect and verify clean response
        conn.connect()
        result = conn.send_command("ping")
        assert result.get("pong") is True
    finally:
        conn.disconnect()


def test_timeout_mentions_other_connected_client(monkeypatch, mock_server):
    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()

    class _TimeoutSocket:
        def sendall(self, _payload):
            return None

        def recv(self, _size):
            raise socket.timeout()

        def close(self):
            return None

        def settimeout(self, _timeout):
            return None

    monkeypatch.setattr(connection_mod, "_identify_other_tcp_client", lambda host, port: "PID 999 (node)")
    conn._socket = _TimeoutSocket()

    with pytest.raises(AbletonConnectionError, match="Another LivePilot client appears to be connected"):
        conn._send_raw({"type": "ping"})

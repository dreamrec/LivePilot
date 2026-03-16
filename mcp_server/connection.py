"""TCP client for communicating with Ableton Live's Remote Script."""

import json
import os
import socket
import uuid

CONNECT_TIMEOUT = 5
RECV_TIMEOUT = 20


class AbletonConnectionError(Exception):
    """Raised when communication with Ableton Live fails."""
    pass


class AbletonConnection:
    """TCP client that sends JSON commands to the LivePilot Remote Script."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or os.environ.get("LIVE_MCP_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("LIVE_MCP_PORT", "9878"))
        self._socket: socket.socket | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open a TCP connection to the Remote Script."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect((self.host, self.port))
            sock.settimeout(RECV_TIMEOUT)
            self._socket = sock
        except OSError as exc:
            self._socket = None
            raise AbletonConnectionError(
                f"Could not connect to Ableton Live at {self.host}:{self.port} — {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def is_connected(self) -> bool:
        """Return True if a socket is currently held."""
        return self._socket is not None

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Send a ping and return True if a pong is received."""
        try:
            resp = self._send_raw({"type": "ping"})
            return resp.get("result", {}).get("pong") is True
        except Exception:
            return False

    def send_command(self, command_type: str, params: dict | None = None) -> dict:
        """Send a command to Ableton and return the result dict.

        Handles stale-socket detection via ping and retries once on
        socket errors with a fresh connection.
        """
        # Ensure we have a connection
        if not self.is_connected():
            self.connect()

        # Stale detection — if ping fails, reconnect
        if not self.ping():
            self.disconnect()
            self.connect()

        command: dict = {"type": command_type}
        if params:
            command["params"] = params

        try:
            response = self._send_raw(command)
        except (OSError, AbletonConnectionError):
            # Retry once with a fresh connection
            self.disconnect()
            self.connect()
            response = self._send_raw(command)

        # Handle error responses — Remote Script uses {"ok": false, "error": {"code": ..., "message": ...}}
        if response.get("ok") is False:
            err = response.get("error", {})
            code = err.get("code", "INTERNAL") if isinstance(err, dict) else "INTERNAL"
            message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise Exception(f"[{code}] {message}")

        return response.get("result", {})

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------

    def _send_raw(self, command: dict) -> dict:
        """Send a JSON command (with request_id) and read the response."""
        if self._socket is None:
            raise AbletonConnectionError("Not connected to Ableton Live")

        command["id"] = str(uuid.uuid4())[:8]
        payload = json.dumps(command) + "\n"

        try:
            self._socket.sendall(payload.encode("utf-8"))
        except OSError as exc:
            self.disconnect()
            raise AbletonConnectionError(f"Failed to send command: {exc}") from exc

        # Read until newline
        buf = b""
        try:
            while True:
                chunk = self._socket.recv(4096)
                if not chunk:
                    self.disconnect()
                    raise AbletonConnectionError("Connection closed by Ableton")
                buf += chunk
                if b"\n" in buf:
                    break
        except socket.timeout as exc:
            self.disconnect()
            raise AbletonConnectionError(
                f"Timeout waiting for response from Ableton ({RECV_TIMEOUT}s)"
            ) from exc
        except OSError as exc:
            self.disconnect()
            raise AbletonConnectionError(
                f"Socket error reading response: {exc}"
            ) from exc

        line = buf.split(b"\n", 1)[0]
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise AbletonConnectionError(
                f"Invalid JSON from Ableton: {line[:200]}"
            ) from exc

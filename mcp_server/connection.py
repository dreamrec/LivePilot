"""TCP client for communicating with Ableton Live's Remote Script."""

import json
import os
import socket
import time
import uuid
from collections import deque

CONNECT_TIMEOUT = 5
RECV_TIMEOUT = 20


class AbletonConnectionError(Exception):
    """Raised when communication with Ableton Live fails."""
    pass


# Error messages with user-friendly context
_ERROR_HINTS = {
    "INDEX_ERROR": "Check that the track, clip, device, or scene index exists. "
                   "Use get_session_info to see current indices.",
    "NOT_FOUND": "The requested item could not be found in the Live session. "
                 "Verify names and indices with get_session_info or get_track_info.",
    "INVALID_PARAM": "A parameter value was out of range or the wrong type. "
                     "Use get_device_parameters to check valid ranges.",
    "STATE_ERROR": "The operation isn't valid in the current state. "
                   "For example, you can't add notes to a clip that doesn't exist yet.",
    "TIMEOUT": "Ableton took too long to respond. This can happen with heavy sessions. "
               "Try again, or check if Ableton is unresponsive.",
}


def _friendly_error(code: str, message: str, command_type: str) -> str:
    """Format an error from the Remote Script into a user-friendly message."""
    hint = _ERROR_HINTS.get(code, "")
    parts = [f"[{code}] {message}"]
    if hint:
        parts.append(hint)
    return " ".join(parts)


class AbletonConnection:
    """TCP client that sends JSON commands to the LivePilot Remote Script."""

    MAX_LOG_ENTRIES = 50

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or os.environ.get("LIVE_MCP_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("LIVE_MCP_PORT", "9878"))
        self._socket: socket.socket | None = None
        self._command_log: deque[dict] = deque(maxlen=self.MAX_LOG_ENTRIES)

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
        except ConnectionRefusedError:
            self._socket = None
            raise AbletonConnectionError(
                f"Cannot reach Ableton Live on {self.host}:{self.port}. "
                "Make sure Ableton Live is running and the LivePilot Remote Script "
                "is enabled in Preferences > Link, Tempo & MIDI > Control Surface. "
                "Run 'npx livepilot --doctor' for a full diagnostic."
            )
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

        Retries once on socket errors with a fresh connection.
        """
        # Ensure we have a connection
        if not self.is_connected():
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

        # Log the command and response
        log_entry = {
            "command": command_type,
            "params": params,
            "timestamp": time.time(),
            "ok": response.get("ok", True),
        }

        # Handle error responses — Remote Script uses {"ok": false, "error": {"code": ..., "message": ...}}
        if response.get("ok") is False:
            err = response.get("error", {})
            code = err.get("code", "INTERNAL") if isinstance(err, dict) else "INTERNAL"
            message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            log_entry["error"] = code
            self._command_log.append(log_entry)
            friendly = _friendly_error(code, message, command_type)
            raise AbletonConnectionError(friendly)

        self._command_log.append(log_entry)
        return response.get("result", {})

    # ------------------------------------------------------------------
    # Command log
    # ------------------------------------------------------------------

    def get_recent_commands(self, limit: int = 20) -> list[dict]:
        """Return the most recent commands sent to Ableton (newest first)."""
        entries = list(self._command_log)
        entries.reverse()
        return entries[:limit]

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------

    def _send_raw(self, command: dict) -> dict:
        """Send a JSON command (with request_id) and read the response."""
        if self._socket is None:
            raise AbletonConnectionError("Not connected to Ableton Live")

        # Don't mutate the caller's dict
        envelope = {**command, "id": str(uuid.uuid4())[:8]}
        payload = json.dumps(envelope) + "\n"

        try:
            self._socket.sendall(payload.encode("utf-8"))
        except OSError as exc:
            self.disconnect()
            raise AbletonConnectionError(f"Failed to send command: {exc}") from exc

        # Read until newline, preserving any trailing bytes in _recv_buf
        buf = getattr(self, "_recv_buf", b"")
        try:
            while b"\n" not in buf:
                chunk = self._socket.recv(4096)
                if not chunk:
                    self._recv_buf = b""
                    self.disconnect()
                    raise AbletonConnectionError("Connection closed by Ableton")
                buf += chunk
        except socket.timeout as exc:
            self._recv_buf = buf
            self.disconnect()
            raise AbletonConnectionError(
                f"Timeout waiting for response from Ableton ({RECV_TIMEOUT}s)"
            ) from exc
        except OSError as exc:
            self._recv_buf = b""
            self.disconnect()
            raise AbletonConnectionError(
                f"Socket error reading response: {exc}"
            ) from exc

        line, remainder = buf.split(b"\n", 1)
        self._recv_buf = remainder
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise AbletonConnectionError(
                f"Invalid JSON from Ableton: {line[:200]}"
            ) from exc

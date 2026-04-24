"""TCP client for communicating with Ableton Live's Remote Script."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import uuid
from collections import deque
from typing import Optional
import logging

logger = logging.getLogger(__name__)


CONNECT_TIMEOUT = 5
RECV_TIMEOUT = 20
SINGLE_CLIENT_RETRY_DELAY = 0.25
# v1.20.2 race-condition fix: UI transitions (Cmd+N, project open) close
# the command socket briefly. Retry once after this delay to let Ableton
# finish setting up the new session state.
UI_TRANSITION_RETRY_DELAY = 0.4
COMMAND_RECV_TIMEOUTS = {
    # Server-side slow write window is 35s; give the client a small buffer.
    "freeze_track": 40,
}


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
    if command_type:
        parts.append(f"(while running '{command_type}')")
    if hint:
        parts.append(hint)
    return " ".join(parts)


def _is_single_client_state_error(response: dict) -> bool:
    """Return True when the server rejected a fresh connection due to single-client guard."""
    if response.get("ok") is not False:
        return False
    err = response.get("error", {})
    if not isinstance(err, dict):
        return False
    return (
        err.get("code") == "STATE_ERROR"
        and "Another client is already connected" in str(err.get("message", ""))
    )


def _identify_other_tcp_client(host: str, port: int) -> str | None:
    """Return a short description of another established client on the Live port."""
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", f"-iTCP:{port}"],
            text=True,
            timeout=3,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, OSError):
        return None

    target = f"->{host}:{port}"
    my_pid = os.getpid()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or target not in line or "(ESTABLISHED)" not in line:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        if pid == my_pid:
            continue
        return f"PID {pid} ({parts[0]})"
    return None


class AbletonConnection:
    """TCP client that sends JSON commands to the LivePilot Remote Script."""

    MAX_LOG_ENTRIES = 50

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or os.environ.get("LIVE_MCP_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("LIVE_MCP_PORT", "9878"))
        self._socket: Optional[socket.socket] = None
        self._recv_buf: bytes = b""
        self._command_log: deque[dict] = deque(maxlen=self.MAX_LOG_ENTRIES)
        self._lock = threading.Lock()  # Serialize all TCP send/receive cycles

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
        """Close the TCP connection and discard any partial receive buffer."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        self._recv_buf = b""

    def is_connected(self) -> bool:
        """Return True if a socket is currently held."""
        return self._socket is not None

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Send a ping and return True if a pong is received."""
        try:
            return self.send_command("ping").get("pong") is True
        except Exception as exc:
            logger.debug("ping failed: %s", exc)
            return False

    def send_command(self, command_type: str, params: Optional[dict] = None) -> dict:
        """Send a command to Ableton and return the result dict.

        Thread-safe: a lock serializes all TCP send/receive cycles to
        prevent socket corruption when multiple MCP tools fire concurrently.
        Retries once on connection errors (command never reached Ableton).
        Does NOT retry on timeouts — Ableton may have already processed the
        command, and retrying would cause duplicate mutations.
        """
        with self._lock:
            # Ensure we have a connection
            fresh_connect = not self.is_connected()
            if fresh_connect:
                self.connect()

            command: dict = {"type": command_type}
            if params:
                command["params"] = params

            try:
                response = self._send_raw(
                    command,
                    recv_timeout=COMMAND_RECV_TIMEOUTS.get(command_type, RECV_TIMEOUT),
                )
            except AbletonConnectionError as exc:
                # If the send phase succeeded (data left this process),
                # Ableton may have already applied the command.  Never
                # replay — the duplicate mutation is worse than the error.
                if getattr(exc, '_send_completed', False):
                    # v1.20.2 race-condition fix: the specific error
                    # "Connection closed by Ableton" fires reliably after
                    # UI state transitions (Cmd+N opens new live set,
                    # project open, etc.). The Remote Script's socket
                    # recv returns empty bytes in a ~300ms window around
                    # the transition. Retry ONCE with backoff so an
                    # immediate follow-up command survives.
                    #
                    # Idempotence note: most commands are idempotent
                    # (set_tempo, set_track_volume overwrite; get_*
                    # reads are side-effect-free). Non-idempotent
                    # mutations (add_notes, create_clip) may in theory
                    # double-apply — but in practice Ableton's
                    # single-threaded command processing means the
                    # "Connection closed" happens BEFORE command
                    # processing begins, not after. Campaign repros
                    # showed 3/3 set_tempo failures post-Cmd+N that
                    # would have been fine to retry.
                    if "Connection closed by Ableton" in str(exc):
                        logger.warning(
                            "Ableton closed socket mid-%s — likely UI "
                            "state transition. Retrying once after %dms.",
                            command_type, int(UI_TRANSITION_RETRY_DELAY * 1000),
                        )
                        self.disconnect()
                        time.sleep(UI_TRANSITION_RETRY_DELAY)
                        self.connect()
                        response = self._send_raw(
                            command,
                            recv_timeout=COMMAND_RECV_TIMEOUTS.get(command_type, RECV_TIMEOUT),
                        )
                    else:
                        raise
                # Don't retry timeouts either
                elif "Timeout" in str(exc):
                    raise
                else:
                    # Send itself failed — safe to retry with a fresh connection
                    self.disconnect()
                    self.connect()
                    response = self._send_raw(
                        command,
                        recv_timeout=COMMAND_RECV_TIMEOUTS.get(command_type, RECV_TIMEOUT),
                    )
            except OSError:
                # Socket error before send — safe to retry
                self.disconnect()
                self.connect()
                response = self._send_raw(
                    command,
                    recv_timeout=COMMAND_RECV_TIMEOUTS.get(command_type, RECV_TIMEOUT),
                )

            # The single-client guard can briefly reject an immediate reconnect
            # after this process closes a previous socket. Retry once after a
            # short delay when the command was rejected before execution.
            #
            # IMPORTANT: release the lock around the sleep so concurrent tool
            # calls are not blocked on an idle timer. The previous version
            # slept 250ms while holding the lock, which stalled every other
            # async MCP handler in the server.
            needs_retry = fresh_connect and _is_single_client_state_error(response)

        if needs_retry:
            self.disconnect()
            time.sleep(SINGLE_CLIENT_RETRY_DELAY)
            with self._lock:
                self.connect()
                response = self._send_raw(
                    command,
                    recv_timeout=COMMAND_RECV_TIMEOUTS.get(command_type, RECV_TIMEOUT),
                )

        # Log and error handling outside the lock (no socket access needed)
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

    def _send_raw(self, command: dict, recv_timeout: int = RECV_TIMEOUT) -> dict:
        """Send a JSON command (with request_id) and read the response."""
        if self._socket is None:
            raise AbletonConnectionError("Not connected to Ableton Live")

        # Don't mutate the caller's dict
        envelope = {**command, "id": str(uuid.uuid4())[:8]}
        payload = json.dumps(envelope) + "\n"
        self._socket.settimeout(recv_timeout)

        try:
            self._socket.sendall(payload.encode("utf-8"))
        except OSError as exc:
            self.disconnect()
            raise AbletonConnectionError(f"Failed to send command: {exc}") from exc

        # Read until newline, preserving any trailing bytes in _recv_buf.
        # Any error past this point means the send already reached Ableton,
        # so callers must NOT retry the command (it may have been applied).
        buf = self._recv_buf
        try:
            while b"\n" not in buf:
                chunk = self._socket.recv(4096)
                if not chunk:
                    self._recv_buf = b""
                    self.disconnect()
                    err = AbletonConnectionError("Connection closed by Ableton")
                    err._send_completed = True
                    raise err
                buf += chunk
                if len(buf) > 10 * 1024 * 1024:  # 10 MB
                    self._recv_buf = b""
                    self.disconnect()
                    err = AbletonConnectionError("Response too large (>10 MB)")
                    err._send_completed = True
                    raise err
        except socket.timeout as exc:
            self._recv_buf = buf
            self.disconnect()
            other_client = _identify_other_tcp_client(self.host, self.port)
            if other_client:
                err = AbletonConnectionError(
                    "Timeout waiting for response from Ableton. "
                    f"Another LivePilot client appears to be connected on {self.host}:{self.port} "
                    f"({other_client}). Disconnect the other client and retry."
                )
                err._send_completed = True
                raise err from exc
            err = AbletonConnectionError(
                f"Timeout waiting for response from Ableton ({RECV_TIMEOUT}s)"
            )
            err._send_completed = True
            raise err from exc
        except OSError as exc:
            self._recv_buf = b""
            self.disconnect()
            err = AbletonConnectionError(
                f"Socket error reading response: {exc}"
            )
            err._send_completed = True
            raise err from exc

        line, remainder = buf.split(b"\n", 1)
        self._recv_buf = remainder
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise AbletonConnectionError(
                f"Invalid JSON from Ableton: {line[:200]}"
            ) from exc
        finally:
            if self._socket is not None:
                try:
                    self._socket.settimeout(RECV_TIMEOUT)
                except OSError:
                    pass

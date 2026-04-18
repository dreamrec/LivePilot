"""
LivePilot - TCP server with thread-safe command queue.

Runs a background daemon thread that accepts JSON-over-TCP connections.
Commands are forwarded to Ableton's main thread via schedule_message,
and responses are returned through per-command Queue objects.
"""

import socket
import threading
import json

import queue

from . import router

# ── Commands that modify Live state (need settle delay) ──────────────────────

WRITE_COMMANDS = frozenset([
    # transport
    "set_tempo", "set_time_signature", "start_playback", "stop_playback",
    "continue_playback", "toggle_metronome", "set_session_loop", "undo", "redo",
    # tracks
    "create_midi_track", "create_audio_track", "create_return_track",
    "delete_track", "duplicate_track", "set_track_name", "set_track_color",
    "set_track_mute", "set_track_solo", "set_track_arm", "stop_track_clips",
    "set_group_fold", "set_track_input_monitoring",
    # clips
    "create_clip", "delete_clip", "duplicate_clip", "fire_clip", "stop_clip",
    "set_clip_name", "set_clip_color", "set_clip_loop", "set_clip_launch",
    "set_clip_warp_mode",
    # notes
    "add_notes", "remove_notes", "remove_notes_by_id", "modify_notes",
    "duplicate_notes", "transpose_notes", "quantize_clip",
    # devices
    "set_device_parameter", "batch_set_parameters", "toggle_device",
    "delete_device", "load_device_by_uri", "find_and_load_device",
    "set_chain_volume", "set_simpler_playback_mode",
    # scenes
    "create_scene", "delete_scene", "duplicate_scene", "fire_scene",
    "set_scene_name", "set_scene_color", "set_scene_tempo",
    "fire_scene_clips", "stop_all_clips",
    # tracks (freeze/flatten)
    "freeze_track", "flatten_track",
    # mixing
    "set_track_volume", "set_track_pan", "set_track_send",
    "set_master_volume", "set_track_routing",
    # browser
    "load_browser_item",
    # arrangement
    "jump_to_time", "jump_to_cue", "capture_midi", "start_recording",
    "stop_recording", "toggle_cue_point", "back_to_arranger",
    "create_arrangement_clip", "add_arrangement_notes",
    "remove_arrangement_notes", "remove_arrangement_notes_by_id",
    "modify_arrangement_notes", "duplicate_arrangement_notes",
    "transpose_arrangement_notes", "set_arrangement_automation",
    "set_arrangement_clip_name",
    # clip automation
    "set_clip_automation",
    "clear_clip_automation",
])

# Commands that need longer timeouts (e.g., freeze renders audio)
SLOW_WRITE_COMMANDS = frozenset([
    "freeze_track",
])


class LivePilotServer(object):
    """TCP server that bridges JSON commands to Ableton's main thread.

    Single-client by design: only one client can be connected at a time.
    All commands must execute on Ableton's main thread (Live Object Model
    is not thread-safe), so serialized client access prevents race conditions.
    Additional connection attempts are rejected with a clear error message.
    """

    def __init__(self, control_surface, host="127.0.0.1", port=9878):
        self._cs = control_surface
        self._host = host
        self._port = port
        self._running = False
        self._server_socket = None
        self._thread = None
        self._client_thread = None
        self._command_queue = queue.Queue()
        self._client_lock = threading.Lock()
        self._client_connected = False

    # ── Public API ───────────────────────────────────────────────────────

    def start(self):
        """Start the background listener thread."""
        self._running = True
        self._thread = threading.Thread(target=self._server_loop)
        self._thread.daemon = True
        self._thread.start()
        # Note: "Listening on ..." is logged from _server_loop after bind
        # succeeds. Don't log "Server started" here — bind may still fail.

    def stop(self):
        """Shutdown the server gracefully."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._client_thread and self._client_thread.is_alive():
            self._client_thread.join(timeout=3)
        self._log("Server stopped")

    # ── Logging ──────────────────────────────────────────────────────────

    def _log(self, message):
        try:
            self._cs.log_message("[LivePilot] " + str(message))
        except Exception:
            pass

    # ── Background thread ────────────────────────────────────────────────

    def _server_loop(self):
        """Runs in a daemon thread.  Accepts one client at a time."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self._host, self._port))
            self._server_socket.listen(2)
            self._server_socket.settimeout(1.0)
            self._log("Listening on %s:%d" % (self._host, self._port))
        except OSError as exc:
            self._log("Failed to bind: %s" % exc)
            return

        while self._running:
            try:
                client, addr = self._server_socket.accept()
                with self._client_lock:
                    if self._client_connected:
                        # Reject concurrent clients with an explicit message
                        self._log("Rejected client from %s:%d (another client is connected)" % addr)
                        try:
                            reject = json.dumps({
                                "id": "system",
                                "ok": False,
                                "error": {
                                    "code": "STATE_ERROR",
                                    "message": "Another client is already connected. "
                                               "LivePilot accepts one client at a time. "
                                               "Disconnect the current client first."
                                }
                            }) + "\n"
                            client.sendall(reject.encode("utf-8"))
                        except OSError:
                            pass
                        try:
                            client.close()
                        except OSError:
                            pass
                        continue
                    self._client_connected = True
                    self._client_thread = threading.Thread(
                        target=self._run_client_session,
                        args=(client, addr),
                    )
                    self._client_thread.daemon = True
                    self._client_thread.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    self._log("Accept error")
                break

        try:
            self._server_socket.close()
        except OSError:
            pass

    def _run_client_session(self, client, addr):
        """Handle one active client without blocking new connection rejects."""
        self._log("Client connected from %s:%d" % addr)
        try:
            self._handle_client(client)
        except OSError as exc:
            self._log("Client error: %s" % exc)
        finally:
            try:
                client.close()
            except OSError:
                pass
            with self._client_lock:
                self._client_connected = False
            self._log("Client disconnected")

    def _handle_client(self, client):
        """Read newline-delimited JSON from a connected client.

        Accumulate raw bytes and only attempt UTF-8 decode on newline-framed
        lines — the previous implementation decoded each recv chunk eagerly
        with ``errors="replace"``, which silently corrupted JSON when a
        multi-byte UTF-8 sequence (non-ASCII filename or rack name) straddled
        the 4096-byte recv boundary. Trailing bytes of the split codepoint
        were converted to U+FFFD, breaking JSON parsing.
        """
        client.settimeout(1.0)
        buf = bytearray()
        MAX_BUF = 4 * 1024 * 1024  # 4 MB
        while self._running:
            try:
                data = client.recv(4096)
                if not data:
                    break
                buf.extend(data)
                if len(buf) > MAX_BUF:
                    self._log("Client buffer overflow — disconnecting")
                    break
                while True:
                    nl = buf.find(b"\n")
                    if nl < 0:
                        break
                    raw_line = bytes(buf[:nl])
                    del buf[: nl + 1]
                    try:
                        line = raw_line.decode("utf-8").strip()
                    except UnicodeDecodeError as exc:
                        self._send(client, {
                            "id": "unknown",
                            "ok": False,
                            "error": {
                                "code": "INVALID_PARAM",
                                "message": "Invalid UTF-8 in request: %s" % exc,
                            },
                        })
                        continue
                    if line:
                        self._process_line(client, line)
            except socket.timeout:
                continue
            except OSError as exc:
                self._log("Recv error: %s" % exc)
                break

    def _process_line(self, client, line):
        """Parse one JSON command, queue it for main thread, wait for result."""
        try:
            command = json.loads(line)
        except (ValueError, TypeError) as exc:
            resp = {
                "id": "unknown",
                "ok": False,
                "error": {"code": "INVALID_PARAM", "message": "Bad JSON: %s" % exc},
            }
            self._send(client, resp)
            return

        request_id = command.get("id", "unknown")
        cmd_type = command.get("type", "")

        # Determine timeout based on read vs write vs slow write
        is_write = cmd_type in WRITE_COMMANDS
        if cmd_type in SLOW_WRITE_COMMANDS:
            timeout = 35
        elif is_write:
            timeout = 15
        else:
            timeout = 10

        # Per-command response queue
        response_queue = queue.Queue()
        self._command_queue.put((command, response_queue))

        # Schedule processing on Ableton's main thread
        try:
            self._cs.schedule_message(0, self._process_next_command)
        except AssertionError:
            # ControlSurface is disconnecting — return an error instead of
            # running LOM calls on the TCP thread (which would be unsafe).
            #
            # The previous version called get_nowait() unconditionally, which
            # would happily drain a different item if one had been enqueued
            # concurrently (e.g. if _drain_queue had just put another). Under
            # the current single-client model the race is theoretical, but the
            # filtered-rebuild below is correct regardless and defends against
            # any future multi-path enqueue.
            remaining = []
            while True:
                try:
                    item = self._command_queue.get_nowait()
                except queue.Empty:
                    break
                # Drop only OUR own pending item; preserve anything else
                if item[1] is not response_queue:
                    remaining.append(item)
            for item in remaining:
                self._command_queue.put(item)
            self._send(client, {
                "id": request_id,
                "ok": False,
                "error": {"code": "STATE_ERROR", "message": "Script is disconnecting"},
            })
            return

        # Wait for response from main thread
        try:
            resp = response_queue.get(timeout=timeout)
        except queue.Empty:
            resp = {
                "id": request_id,
                "ok": False,
                "error": {"code": "TIMEOUT", "message": "Command timed out after %ds" % timeout},
            }

        self._send(client, resp)

    # ── Main thread execution ────────────────────────────────────────────

    def _process_next_command(self):
        """Called on Ableton's main thread via schedule_message.
        Processes one command from the queue."""
        try:
            command, response_queue = self._command_queue.get_nowait()
        except queue.Empty:
            return

        cmd_type = command.get("type", "")
        is_write = cmd_type in WRITE_COMMANDS

        try:
            song = self._cs.song()
            result = router.dispatch(song, command)
        except Exception as exc:
            result = {
                "id": command.get("id", "unknown"),
                "ok": False,
                "error": {"code": "INTERNAL", "message": str(exc)},
            }

        if is_write:
            # Schedule response after 100ms settle delay for write operations
            def send_response():
                response_queue.put(result)
                # Drain any remaining queued commands
                self._drain_queue()
            try:
                self._cs.schedule_message(1, send_response)  # ~100ms
            except AssertionError:
                # ControlSurface disconnecting — send result immediately
                response_queue.put(result)
        else:
            response_queue.put(result)
            # Drain any remaining queued commands
            self._drain_queue()

    def _drain_queue(self):
        """Process any remaining commands in the queue."""
        if not self._command_queue.empty():
            try:
                self._cs.schedule_message(0, self._process_next_command)
            except AssertionError:
                # ControlSurface disconnecting — drop remaining commands
                # rather than running LOM calls on the wrong thread
                pass

    # ── Socket I/O ───────────────────────────────────────────────────────

    def _send(self, client, response):
        """Send a JSON response to the client."""
        from .utils import serialize_json
        try:
            client.sendall(serialize_json(response).encode("utf-8"))
        except OSError as exc:
            self._log("Send error: %s" % exc)

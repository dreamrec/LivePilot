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

# P2-48 backstop: "undo"/"redo" are bare verbs — no read/write prefix applies
# to them, so they only ever classified as writes via the literals inside
# WRITE_COMMANDS above. If a future WRITE_COMMANDS trim ever dropped them
# (e.g. a well-intentioned dedupe pass), is_write_command() would silently
# reclassify genuinely-mutating commands as reads, reintroducing the
# read-after-write race the settle delay exists to prevent. This frozenset is
# checked independently of WRITE_COMMANDS so that can't happen silently.
WRITE_BARE_VERBS = frozenset([
    "undo",
    "redo",
])

# Future-safe write detection. WRITE_COMMANDS remains the explicit allow-list
# for older handlers and readability; the prefix classifier catches newer
# mutating handlers so they still receive the write timeout and settle delay.
READ_COMMAND_PREFIXES = ("get_", "list_", "scan_")
READ_ONLY_COMMANDS = frozenset([
    "ping",
    "reload_handlers",
])
WRITE_COMMAND_PREFIXES = (
    "add_",
    "apply_",
    "arrangement_automation_",
    "assign_",
    "back_to_",
    "batch_",
    "capture_",
    "cleanup_",
    "clear_",
    "continue_",
    "copy_",
    "create_",
    "delete_",
    "duplicate_",
    "find_and_load_",
    "fire_",
    "flatten_",
    "force_",
    "freeze_",
    "import_",
    "insert_",
    "jump_",
    "load_",
    "modify_",
    "move_",
    "nudge_",
    "quantize_",
    "randomize_",
    "recall_",
    "remove_",
    "replace_",
    "reset_",
    "set_",
    "start_",
    "stop_",
    "store_",
    "tap_",
    "toggle_",
    "transpose_",
)


def is_write_command(command_type):
    """Return True if a command is expected to mutate Live state."""
    # Checked first and independent of WRITE_COMMANDS — see WRITE_BARE_VERBS.
    if command_type in WRITE_BARE_VERBS:
        return True
    if command_type in WRITE_COMMANDS:
        return True
    if command_type in READ_ONLY_COMMANDS:
        return False
    if command_type.startswith(READ_COMMAND_PREFIXES):
        return False
    return command_type.startswith(WRITE_COMMAND_PREFIXES)


# Commands that need longer timeouts (freeze renders audio; flatten runs
# track.flatten() synchronously in-call)
SLOW_WRITE_COMMANDS = frozenset([
    "freeze_track",
    "flatten_track",
])


class _CmdState(object):
    """Shared cancel/commit state for one queued command.

    The TCP thread (which waits for the response and may time out) and the
    main thread (which dispatches the command) both touch this object. The
    lock makes "cancel" and "commit" mutually exclusive so they cannot race:
    a write is either cancelled BEFORE the main thread commits to dispatching
    it (so it never runs — no phantom mutation after a reported TIMEOUT), or
    the main thread commits first (so a late timeout cannot cancel a write
    that is already going to run). The two flags can never both be True.
    """

    __slots__ = ("lock", "cancelled", "committed")

    def __init__(self):
        self.lock = threading.Lock()
        self.cancelled = False
        self.committed = False


class LivePilotServer(object):
    """TCP server that bridges JSON commands to Ableton's main thread.

    Single-client by design: only one client can be connected at a time.
    All commands must execute on Ableton's main thread (Live Object Model
    is not thread-safe), so serialized client access prevents race conditions.
    Additional connection attempts are rejected with a clear error message.
    """

    supports_deferred_results = True

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
        # Track the active client socket so we can close it from the accept
        # loop when a new connection arrives. See _server_loop's kick-stale
        # flow — without this, an unclean MCP-server restart leaves the
        # Remote Script in a state where new connections get rejected until
        # the old socket times out (often requiring an Ableton restart).
        self._current_client = None

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
                # Single-client design: a new connection means the previous one
                # is dead. Close the stale socket and join its thread (outside
                # the lock so the thread's finally block can acquire it), then
                # accept the new connection. Without this, the server could
                # reject reconnections for up to 1s after an unclean MCP-server
                # restart — the old recv() loop hadn't yet observed EOF.
                stale_thread = None
                stale_client = None
                with self._client_lock:
                    if self._client_connected and self._current_client is not None:
                        stale_client = self._current_client
                        stale_thread = self._client_thread
                        self._log(
                            "Replacing stale client with new connection from %s:%d" % addr
                        )
                if stale_client is not None:
                    try:
                        stale_client.close()
                    except OSError:
                        pass
                if stale_thread is not None and stale_thread.is_alive():
                    # 2s is generous — the old recv() unblocks the moment we
                    # close the socket above, then the thread's finally block
                    # acquires the lock, resets _client_connected, and exits.
                    stale_thread.join(timeout=2)

                with self._client_lock:
                    self._client_connected = True
                    self._current_client = client
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
                # Only clear _current_client if it still points at us — the
                # accept loop may have already replaced us with a new client
                # (in which case _current_client is the new socket).
                if self._current_client is client:
                    self._current_client = None
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
                if len(buf) > MAX_BUF and buf.find(b"\n") < 0:
                    # A single request line exceeded MAX_BUF with no framing
                    # newline. Emit a structured error (mirroring the
                    # UnicodeDecodeError branch below) and resynchronize the
                    # stream by dropping the oversized buffer, rather than a
                    # bare disconnect the client can't distinguish from a
                    # crash or stolen socket.
                    self._log("Request line exceeded %d bytes — dropping" % MAX_BUF)
                    del buf[:]
                    self._send(client, {
                        "id": "unknown",
                        "ok": False,
                        "error": {
                            "code": "INVALID_PARAM",
                            "message": "Request line exceeded %d bytes "
                                       "without a newline" % MAX_BUF,
                        },
                    })
                    continue
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
        is_write = is_write_command(cmd_type)
        if cmd_type in SLOW_WRITE_COMMANDS:
            timeout = 35
        elif is_write:
            timeout = 15
        else:
            timeout = 10

        # Per-command response queue + cancellation flag. The flag is shared
        # between this TCP thread and the main thread that dequeues the item:
        # if we time out below, we set it so _process_next_command skips the
        # (now-abandoned) dispatch instead of mutating Live after the client
        # has already been told the command timed out (phantom write).
        response_queue = queue.Queue()
        state = _CmdState()
        self._command_queue.put((command, response_queue, state))

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
            # Abandon the queued command — but ATOMICALLY. We only mark it
            # cancelled if the main thread has not already committed to
            # dispatching it. Holding state.lock across the check+set makes
            # this mutually exclusive with _process_next_command's commit, so
            # there is no window where a write dispatches even though the TCP
            # thread intended to cancel it. If the main thread already
            # committed (committed is True), the write is legitimately in
            # flight and we simply report the timeout without cancelling.
            with state.lock:
                if not state.committed:
                    state.cancelled = True
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
            command, response_queue, state = self._command_queue.get_nowait()
        except queue.Empty:
            return

        # Atomically decide whether to run this command. If the TCP thread
        # already gave up (timed out) and cancelled it, skip the dispatch —
        # running the write now would be a phantom mutation after the client
        # was told TIMEOUT. Otherwise mark it committed UNDER THE SAME LOCK so
        # a concurrent timeout cannot cancel a write that is about to run.
        # Once committed is True, state.cancelled can never become True, so
        # the settle-hop send_response below always targets a live decision.
        with state.lock:
            if state.cancelled:
                self._drain_queue()
                return
            state.committed = True

        cmd_type = command.get("type", "")
        is_write = is_write_command(cmd_type)

        try:
            song = self._cs.song()
            result = router.dispatch(song, command)
        except BaseException as exc:
            # P3-41: catch BaseException, not just Exception. If a handler
            # raised a non-Exception BaseException (SystemExit / KeyboardInterrupt
            # / GeneratorExit), `result` would never be assigned, the response/
            # drain block below would never run, and the TCP thread would hang
            # on response_queue.get() to its full timeout WHILE the command queue
            # stalls. Converting any dispatch failure into a structured INTERNAL
            # result guarantees the caller is unblocked and the queue advances.
            # (Ableton's embedded main-thread processor has no legitimate
            # SystemExit/KeyboardInterrupt to propagate.)
            result = {
                "id": command.get("id", "unknown"),
                "ok": False,
                "error": {"code": "INTERNAL", "message": str(exc)},
            }

        def resolve_deferred(value):
            if isinstance(value, router.DeferredResult):
                def resume():
                    try:
                        next_value = value.resume()
                    except BaseException as exc:
                        next_value = {
                            "id": command.get("id", "unknown"),
                            "ok": False,
                            "error": {"code": "INTERNAL", "message": str(exc)},
                        }
                    resolve_deferred(next_value)
                try:
                    self._cs.schedule_message(1, resume)
                except AssertionError:
                    response_queue.put({
                        "id": command.get("id", "unknown"),
                        "ok": False,
                        "error": {"code": "STATE_ERROR", "message": "Control surface disconnected"},
                    })
                return
            response_queue.put(value)
            self._drain_queue()

        if isinstance(result, router.DeferredResult):
            resolve_deferred(result)
        elif is_write:
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

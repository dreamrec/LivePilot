# LivePilot Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the end-to-end working pipeline — Remote Script inside Ableton → MCP Server → CLI — with Transport (10 tools) and Tracks (12 tools) as the proving domains.

**Architecture:** Bottom-up: Remote Script runs inside Ableton's Python (ControlSurface), accepts JSON over TCP on port 9878 via a background socket thread, dispatches commands to the main thread via a command queue, and returns results via a response queue. The MCP Server (FastMCP) connects to this TCP socket, validates inputs, and exposes tools via MCP protocol. The CLI (`npx livepilot`) spawns the MCP server in stdio mode.

**Tech Stack:** Python 3.10+ (Ableton's embedded Python for Remote Script, system Python for MCP Server), FastMCP v3+ (`from fastmcp import FastMCP`), Node.js (CLI wrapper + installer)

**Research fixes applied (2026-03-17):**
- FastMCP import: `from fastmcp import FastMCP` (not `mcp.server.fastmcp`)
- ControlSurface: `from _Framework.ControlSurface import ControlSurface` (v2, not v3 — v3 is for MIDI controller mapping)
- Lifespan context: `ctx.lifespan_context["ableton"]` (dict, not dataclass attribute)
- Dependency: `fastmcp>=3.0.0` (not `mcp[cli]`)

**Spec:** `docs/specs/2026-03-17-livepilot-design.md`

---

## Chunk 1: Remote Script Foundation

### Task 1: Remote Script — utils.py (error formatting + validation)

**Files:**
- Create: `remote_script/LivePilot/utils.py`

This is the base utility module used by all other Remote Script modules. It provides structured error responses and common validation helpers. Runs inside Ableton's Python — no external dependencies allowed.

- [ ] **Step 1: Create utils.py with error formatting and validation**

```python
# remote_script/LivePilot/utils.py
"""Utility functions for LivePilot Remote Script."""

import json


# Error codes matching the design spec
INDEX_ERROR = "INDEX_ERROR"
NOT_FOUND = "NOT_FOUND"
INVALID_PARAM = "INVALID_PARAM"
STATE_ERROR = "STATE_ERROR"
TIMEOUT = "TIMEOUT"
INTERNAL = "INTERNAL"


def success_response(request_id, result):
    """Build a success response dict."""
    return {"id": request_id, "status": "success", "result": result}


def error_response(request_id, message, code=INTERNAL):
    """Build an error response dict."""
    return {"id": request_id, "status": "error", "error": message, "code": code}


def get_track(song, track_index):
    """Get a track by index, raising IndexError with clear message.

    Searches visible tracks (session tracks). Index 0 = first track.
    """
    tracks = song.visible_tracks
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(
            f"Track index {track_index} out of range (0-{len(tracks) - 1})"
        )
    return tracks[track_index]


def get_clip_slot(song, track_index, clip_index):
    """Get a clip slot by track and clip index."""
    track = get_track(song, track_index)
    clip_slots = track.clip_slots
    if clip_index < 0 or clip_index >= len(clip_slots):
        raise IndexError(
            f"Clip index {clip_index} out of range (0-{len(clip_slots) - 1})"
        )
    return clip_slots[clip_index]


def get_clip(song, track_index, clip_index):
    """Get a clip by track and clip index. Raises if slot is empty."""
    clip_slot = get_clip_slot(song, track_index, clip_index)
    clip = clip_slot.clip
    if clip is None:
        raise ValueError(
            f"No clip in track {track_index}, slot {clip_index}"
        )
    return clip


def get_device(track, device_index):
    """Get a device by index on a track."""
    devices = track.devices
    if device_index < 0 or device_index >= len(devices):
        raise IndexError(
            f"Device index {device_index} out of range (0-{len(devices) - 1})"
        )
    return devices[device_index]


def get_scene(song, scene_index):
    """Get a scene by index."""
    scenes = song.scenes
    if scene_index < 0 or scene_index >= len(scenes):
        raise IndexError(
            f"Scene index {scene_index} out of range (0-{len(scenes) - 1})"
        )
    return scenes[scene_index]


def serialize_json(data):
    """Serialize data to a JSON string with newline delimiter."""
    return json.dumps(data) + "\n"
```

- [ ] **Step 2: Commit**

```bash
git add remote_script/LivePilot/utils.py
git commit -m "feat(remote-script): add utils.py with error formatting and index helpers"
```

---

### Task 2: Remote Script — router.py (command dispatch)

**Files:**
- Create: `remote_script/LivePilot/router.py`

The router maps command type strings (e.g., `"get_session_info"`, `"set_tempo"`) to handler functions. Domain modules register their handlers at import time. The server calls `router.dispatch(song, command)` from the main thread.

- [ ] **Step 1: Create router.py with dispatch registry**

```python
# remote_script/LivePilot/router.py
"""Command router for LivePilot Remote Script.

Domain modules register handlers via @register decorator.
The server dispatches commands through router.dispatch().
"""

from . import utils

# Command type -> handler function
_handlers = {}


def register(command_type):
    """Decorator to register a handler for a command type.

    Usage:
        @register("set_tempo")
        def handle_set_tempo(song, params):
            song.tempo = params["tempo"]
            return {"tempo": song.tempo}
    """
    def decorator(func):
        _handlers[command_type] = func
        return func
    return decorator


def dispatch(song, command):
    """Dispatch a command dict to the appropriate handler.

    Args:
        song: Live.Song object (main thread only)
        command: dict with "id", "type", and optional "params"

    Returns:
        Response dict (success or error)
    """
    request_id = command.get("id", "unknown")
    command_type = command.get("type")
    params = command.get("params", {})

    if command_type == "ping":
        return utils.success_response(request_id, {"pong": True})

    handler = _handlers.get(command_type)
    if handler is None:
        return utils.error_response(
            request_id,
            f"Unknown command type: {command_type}",
            utils.NOT_FOUND
        )

    try:
        result = handler(song, params)
        return utils.success_response(request_id, result)
    except IndexError as e:
        return utils.error_response(request_id, str(e), utils.INDEX_ERROR)
    except ValueError as e:
        return utils.error_response(request_id, str(e), utils.INVALID_PARAM)
    except Exception as e:
        return utils.error_response(
            request_id,
            f"{type(e).__name__}: {e}",
            utils.INTERNAL
        )
```

- [ ] **Step 2: Commit**

```bash
git add remote_script/LivePilot/router.py
git commit -m "feat(remote-script): add router.py with command dispatch registry"
```

---

### Task 3: Remote Script — server.py (TCP server + thread safety)

**Files:**
- Create: `remote_script/LivePilot/server.py`

This is the most critical file — it implements the thread-safe TCP server that bridges socket I/O (background thread) with Live's main thread (where all LOM calls must happen). Uses `schedule_message` to ensure main-thread execution.

- [ ] **Step 1: Create server.py with TCP server and command queue pattern**

```python
# remote_script/LivePilot/server.py
"""TCP server for LivePilot Remote Script.

Runs a background socket thread that accepts one client at a time.
Commands are dispatched to Ableton's main thread via schedule_message
and the command_queue / response_queue pattern.

ALL Live Object Model calls MUST execute on the main thread.
"""

import json
import socket
import threading
try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

from . import router
from . import utils


# Timeouts (seconds)
READ_TIMEOUT = 10
WRITE_TIMEOUT = 15
SETTLE_DELAY_MS = 100  # milliseconds, for schedule_message

# Write commands get longer timeout + settle delay
WRITE_COMMANDS = {
    "set_tempo", "set_time_signature", "start_playback", "stop_playback",
    "continue_playback", "toggle_metronome", "set_session_loop", "undo", "redo",
    "create_midi_track", "create_audio_track", "create_return_track",
    "delete_track", "duplicate_track", "set_track_name", "set_track_color",
    "set_track_mute", "set_track_solo", "set_track_arm", "stop_track_clips",
    "create_clip", "delete_clip", "duplicate_clip", "fire_clip", "stop_clip",
    "set_clip_name", "set_clip_color", "set_clip_loop", "set_clip_launch",
    "add_notes", "remove_notes", "remove_notes_by_id", "modify_notes",
    "duplicate_notes", "transpose_notes", "quantize_clip",
    "set_device_parameter", "batch_set_parameters", "toggle_device",
    "delete_device", "load_device_by_uri", "find_and_load_device",
    "set_chain_volume",
    "create_scene", "delete_scene", "duplicate_scene", "fire_scene",
    "set_scene_name",
    "set_track_volume", "set_track_pan", "set_track_send", "set_master_volume",
    "set_track_routing",
    "load_browser_item",
    "jump_to_time", "capture_midi", "start_recording", "stop_recording",
    "jump_to_cue", "toggle_cue_point",
}


class LivePilotServer:
    """TCP server that bridges socket I/O with Ableton's main thread."""

    def __init__(self, control_surface, host="127.0.0.1", port=9878):
        self._control_surface = control_surface
        self._host = host
        self._port = port
        self._command_queue = Queue()
        self._server_socket = None
        self._client_socket = None
        self._running = False
        self._thread = None

    def start(self):
        """Start the TCP server on a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._server_loop, daemon=True)
        self._thread.start()
        self._log("LivePilot server started on {}:{}".format(self._host, self._port))

    def stop(self):
        """Stop the server and clean up."""
        self._running = False
        if self._client_socket:
            try:
                self._client_socket.close()
            except Exception:
                pass
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        self._log("LivePilot server stopped")

    def _log(self, message):
        """Log via control surface (shows in Ableton's Log.txt)."""
        self._control_surface.log_message("[LivePilot] " + str(message))

    def _server_loop(self):
        """Background thread: accept connections and handle commands."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self._host, self._port))
            self._server_socket.listen(1)
            self._server_socket.settimeout(1.0)
        except Exception as e:
            self._log("Failed to start server: {}".format(e))
            return

        while self._running:
            try:
                self._client_socket, addr = self._server_socket.accept()
                self._log("Client connected from {}".format(addr))
                self._handle_client()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self._log("Accept error: {}".format(e))

    def _handle_client(self):
        """Handle a single client connection. Returns when client disconnects."""
        client = self._client_socket
        buffer = ""

        try:
            client.settimeout(1.0)
            while self._running:
                try:
                    data = client.recv(65536)
                    if not data:
                        break
                    buffer += data.decode("utf-8")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        self._process_line(client, line)

                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        self._log("Recv error: {}".format(e))
                    break
        finally:
            try:
                client.close()
            except Exception:
                pass
            self._client_socket = None
            self._log("Client disconnected")

    def _process_line(self, client, line):
        """Parse a JSON line and queue it for main-thread execution."""
        try:
            command = json.loads(line)
        except json.JSONDecodeError as e:
            error = utils.error_response(
                "unknown",
                "Invalid JSON: {}".format(e),
                utils.INVALID_PARAM
            )
            self._send(client, error)
            return

        request_id = command.get("id", "unknown")
        command_type = command.get("type", "")
        is_write = command_type in WRITE_COMMANDS
        timeout = WRITE_TIMEOUT if is_write else READ_TIMEOUT

        response_queue = Queue()
        self._command_queue.put((command, response_queue))

        # schedule_message(delay_ms, callback) runs callback on main thread
        self._control_surface.schedule_message(1, self._process_next_command)

        try:
            response = response_queue.get(timeout=timeout)
            self._send(client, response)
        except Empty:
            error = utils.error_response(
                request_id,
                "Command timed out after {}s".format(timeout),
                utils.TIMEOUT
            )
            self._send(client, error)

    def _process_next_command(self):
        """Called on Ableton's main thread via schedule_message.

        Pops one command from the queue, executes it, puts result
        in the command's response queue.
        """
        try:
            command, response_queue = self._command_queue.get_nowait()
        except Empty:
            return

        song = self._control_surface.song()
        response = router.dispatch(song, command)

        command_type = command.get("type", "")
        if command_type in WRITE_COMMANDS:
            def send_response():
                response_queue.put(response)
            self._control_surface.schedule_message(SETTLE_DELAY_MS, send_response)
        else:
            response_queue.put(response)

        if not self._command_queue.empty():
            self._control_surface.schedule_message(1, self._process_next_command)

    def _send(self, client, response):
        """Send a JSON response to the client."""
        try:
            data = utils.serialize_json(response)
            client.sendall(data.encode("utf-8"))
        except Exception as e:
            self._log("Send error: {}".format(e))
```

- [ ] **Step 2: Commit**

```bash
git add remote_script/LivePilot/server.py
git commit -m "feat(remote-script): add server.py with thread-safe TCP server and command queue"
```

---

### Task 4: Remote Script — transport.py (first domain, 10 handlers)

**Files:**
- Create: `remote_script/LivePilot/transport.py`

First domain module. Registers 10 command handlers for transport control. Each handler receives `(song, params)` and returns a result dict.

- [ ] **Step 1: Create transport.py with all 10 handlers**

```python
# remote_script/LivePilot/transport.py
"""Transport domain handlers for LivePilot Remote Script.

10 tools: get_session_info, set_tempo, set_time_signature,
start/stop/continue_playback, toggle_metronome, set_session_loop,
undo, redo.
"""

from .router import register


@register("get_session_info")
def handle_get_session_info(song, params):
    """Return comprehensive session state."""
    tracks_info = []
    for i, track in enumerate(song.visible_tracks):
        track_data = {
            "index": i,
            "name": track.name,
            "color_index": track.color_index,
            "is_midi_track": track.has_midi_input,
            "is_audio_track": track.has_audio_input,
            "mute": track.mute,
            "solo": track.solo,
            "arm": track.arm,
        }
        tracks_info.append(track_data)

    return_tracks = []
    for i, track in enumerate(song.return_tracks):
        return_tracks.append({
            "index": i,
            "name": track.name,
            "color_index": track.color_index,
        })

    scenes_info = []
    for i, scene in enumerate(song.scenes):
        scenes_info.append({
            "index": i,
            "name": scene.name,
            "tempo": scene.tempo if scene.tempo > 0 else None,
        })

    return {
        "tempo": song.tempo,
        "signature_numerator": song.signature_numerator,
        "signature_denominator": song.signature_denominator,
        "is_playing": song.is_playing,
        "song_length": song.song_length,
        "current_song_time": song.current_song_time,
        "loop": song.loop,
        "loop_start": song.loop_start,
        "loop_length": song.loop_length,
        "metronome": song.metronome,
        "record_mode": song.record_mode,
        "session_record": song.session_record,
        "track_count": len(list(song.visible_tracks)),
        "return_track_count": len(list(song.return_tracks)),
        "scene_count": len(list(song.scenes)),
        "tracks": tracks_info,
        "return_tracks": return_tracks,
        "scenes": scenes_info,
    }


@register("set_tempo")
def handle_set_tempo(song, params):
    """Set the song tempo (BPM)."""
    tempo = params["tempo"]
    song.tempo = float(tempo)
    return {"tempo": song.tempo}


@register("set_time_signature")
def handle_set_time_signature(song, params):
    """Set time signature numerator and denominator."""
    numerator = params["numerator"]
    denominator = params["denominator"]
    song.signature_numerator = int(numerator)
    song.signature_denominator = int(denominator)
    return {
        "signature_numerator": song.signature_numerator,
        "signature_denominator": song.signature_denominator,
    }


@register("start_playback")
def handle_start_playback(song, params):
    """Start playback from the beginning."""
    song.start_playing()
    return {"is_playing": song.is_playing}


@register("stop_playback")
def handle_stop_playback(song, params):
    """Stop playback."""
    song.stop_playing()
    return {"is_playing": song.is_playing}


@register("continue_playback")
def handle_continue_playback(song, params):
    """Continue playback from current position."""
    song.continue_playing()
    return {"is_playing": song.is_playing}


@register("toggle_metronome")
def handle_toggle_metronome(song, params):
    """Enable or disable the metronome."""
    enabled = params["enabled"]
    song.metronome = bool(enabled)
    return {"metronome": song.metronome}


@register("set_session_loop")
def handle_set_session_loop(song, params):
    """Set loop enabled state and optional loop region."""
    enabled = params["enabled"]
    song.loop = bool(enabled)

    if "start" in params:
        song.loop_start = float(params["start"])
    if "length" in params:
        song.loop_length = float(params["length"])

    return {
        "loop": song.loop,
        "loop_start": song.loop_start,
        "loop_length": song.loop_length,
    }


@register("undo")
def handle_undo(song, params):
    """Undo the last action."""
    song.undo()
    return {"undone": True}


@register("redo")
def handle_redo(song, params):
    """Redo the last undone action."""
    song.redo()
    return {"redone": True}
```

- [ ] **Step 2: Commit**

```bash
git add remote_script/LivePilot/transport.py
git commit -m "feat(remote-script): add transport.py with 10 transport handlers"
```

---

### Task 5: Remote Script — tracks.py (second domain, 12 handlers)

**Files:**
- Create: `remote_script/LivePilot/tracks.py`

- [ ] **Step 1: Create tracks.py with all 12 handlers**

```python
# remote_script/LivePilot/tracks.py
"""Track domain handlers for LivePilot Remote Script.

12 tools: get_track_info, create_midi_track, create_audio_track,
create_return_track, delete_track, duplicate_track, set_track_name,
set_track_color, set_track_mute, set_track_solo, set_track_arm,
stop_track_clips.
"""

from .router import register
from . import utils


@register("get_track_info")
def handle_get_track_info(song, params):
    """Return detailed info about a single track."""
    track = utils.get_track(song, params["track_index"])

    clip_slots = []
    for i, slot in enumerate(track.clip_slots):
        clip = slot.clip
        clip_data = {"index": i, "has_clip": clip is not None}
        if clip is not None:
            clip_data.update({
                "name": clip.name,
                "color_index": clip.color_index,
                "length": clip.length,
                "is_playing": clip.is_playing,
                "is_recording": clip.is_recording,
                "looping": clip.looping,
            })
        clip_slots.append(clip_data)

    devices = []
    for i, device in enumerate(track.devices):
        devices.append({
            "index": i,
            "name": device.name,
            "class_name": device.class_name,
            "is_active": device.parameters[0].value if len(device.parameters) > 0 else True,
        })

    mixer = track.mixer_device
    sends = []
    for i, send in enumerate(mixer.sends):
        sends.append({"index": i, "value": send.value, "name": send.name})

    return {
        "index": params["track_index"],
        "name": track.name,
        "color_index": track.color_index,
        "is_midi_track": track.has_midi_input,
        "is_audio_track": track.has_audio_input,
        "mute": track.mute,
        "solo": track.solo,
        "arm": track.arm,
        "volume": mixer.volume.value,
        "panning": mixer.panning.value,
        "sends": sends,
        "clip_slots": clip_slots,
        "devices": devices,
        "clip_slot_count": len(clip_slots),
        "device_count": len(devices),
    }


@register("create_midi_track")
def handle_create_midi_track(song, params):
    """Create a new MIDI track."""
    index = params.get("index", -1)
    song.create_midi_track(index)

    if index == -1:
        new_index = len(list(song.visible_tracks)) - 1
    else:
        new_index = index

    track = utils.get_track(song, new_index)

    if "name" in params:
        track.name = params["name"]
    if "color" in params:
        track.color_index = int(params["color"])

    return {
        "index": new_index,
        "name": track.name,
        "color_index": track.color_index,
    }


@register("create_audio_track")
def handle_create_audio_track(song, params):
    """Create a new audio track."""
    index = params.get("index", -1)
    song.create_audio_track(index)

    if index == -1:
        new_index = len(list(song.visible_tracks)) - 1
    else:
        new_index = index

    track = utils.get_track(song, new_index)

    if "name" in params:
        track.name = params["name"]
    if "color" in params:
        track.color_index = int(params["color"])

    return {
        "index": new_index,
        "name": track.name,
        "color_index": track.color_index,
    }


@register("create_return_track")
def handle_create_return_track(song, params):
    """Create a new return track."""
    song.create_return_track()
    returns = list(song.return_tracks)
    new_track = returns[-1]
    return {
        "index": len(returns) - 1,
        "name": new_track.name,
    }


@register("delete_track")
def handle_delete_track(song, params):
    """Delete a track by index."""
    track_index = params["track_index"]
    utils.get_track(song, track_index)
    song.delete_track(track_index)
    return {"deleted": track_index}


@register("duplicate_track")
def handle_duplicate_track(song, params):
    """Duplicate a track by index."""
    track_index = params["track_index"]
    utils.get_track(song, track_index)
    song.duplicate_track(track_index)
    new_index = track_index + 1
    new_track = utils.get_track(song, new_index)
    return {
        "source_index": track_index,
        "new_index": new_index,
        "name": new_track.name,
    }


@register("set_track_name")
def handle_set_track_name(song, params):
    """Rename a track."""
    track = utils.get_track(song, params["track_index"])
    track.name = params["name"]
    return {"index": params["track_index"], "name": track.name}


@register("set_track_color")
def handle_set_track_color(song, params):
    """Set track color index (0-69)."""
    track = utils.get_track(song, params["track_index"])
    track.color_index = int(params["color_index"])
    return {"index": params["track_index"], "color_index": track.color_index}


@register("set_track_mute")
def handle_set_track_mute(song, params):
    """Mute or unmute a track."""
    track = utils.get_track(song, params["track_index"])
    track.mute = bool(params["muted"])
    return {"index": params["track_index"], "mute": track.mute}


@register("set_track_solo")
def handle_set_track_solo(song, params):
    """Solo or unsolo a track."""
    track = utils.get_track(song, params["track_index"])
    track.solo = bool(params["soloed"])
    return {"index": params["track_index"], "solo": track.solo}


@register("set_track_arm")
def handle_set_track_arm(song, params):
    """Arm or disarm a track for recording."""
    track = utils.get_track(song, params["track_index"])
    track.arm = bool(params["armed"])
    return {"index": params["track_index"], "arm": track.arm}


@register("stop_track_clips")
def handle_stop_track_clips(song, params):
    """Stop all clips on a track."""
    track = utils.get_track(song, params["track_index"])
    track.stop_all_clips()
    return {"index": params["track_index"], "stopped": True}
```

- [ ] **Step 2: Commit**

```bash
git add remote_script/LivePilot/tracks.py
git commit -m "feat(remote-script): add tracks.py with 12 track handlers"
```

---

### Task 6: Remote Script — __init__.py (ControlSurface entry point)

**Files:**
- Create: `remote_script/LivePilot/__init__.py`

This is the entry point Ableton calls. It must export `create_instance()` and subclass `ControlSurface`. Importing domain modules triggers handler registration via the `@register` decorator.

- [ ] **Step 1: Create __init__.py with ControlSurface and create_instance**

```python
# remote_script/LivePilot/__init__.py
"""LivePilot — Ableton Live 12 AI Copilot Remote Script.

This module is loaded by Ableton as a Control Surface.
It starts a TCP server that accepts commands from the MCP server.
"""

from ableton.v3.control_surface import ControlSurface

from .server import LivePilotServer

# Import domain modules to register their handlers with the router.
# Each module uses @register decorator at import time.
from . import transport  # noqa: F401
from . import tracks     # noqa: F401


def create_instance(c_instance):
    """Entry point called by Ableton to create the Control Surface."""
    return LivePilot(c_instance=c_instance)


class LivePilot(ControlSurface):
    """LivePilot Control Surface — bridges AI commands to Live's API."""

    def __init__(self, c_instance):
        super().__init__(c_instance=c_instance)
        self._server = LivePilotServer(self)
        self._server.start()
        self.log_message("LivePilot v1.0.0 initialized")

    def disconnect(self):
        """Called when Ableton unloads the Control Surface."""
        if self._server:
            self._server.stop()
        self.log_message("LivePilot disconnected")
        super().disconnect()
```

- [ ] **Step 2: Commit**

```bash
git add remote_script/LivePilot/__init__.py
git commit -m "feat(remote-script): add __init__.py with ControlSurface entry point"
```

---

## Chunk 2: MCP Server

### Task 7: MCP Server — connection.py (TCP client to Ableton)

**Files:**
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/connection.py`

The MCP server's TCP client connects to the Remote Script on port 9878. It handles: connecting, sending commands with request IDs, receiving responses, auto-reconnecting on failure, and ping-based stale detection.

- [ ] **Step 1: Create mcp_server/__init__.py**

```python
# mcp_server/__init__.py
"""LivePilot MCP Server — bridges MCP protocol to Ableton Live."""

__version__ = "1.0.0"
```

- [ ] **Step 2: Create connection.py with AbletonConnection class**

```python
# mcp_server/connection.py
"""TCP connection to Ableton's LivePilot Remote Script.

Handles connecting, sending JSON commands, receiving responses,
auto-reconnecting, and stale connection detection via ping.
"""

import json
import socket
import uuid
import os


LIVE_HOST = os.environ.get("LIVE_MCP_HOST", "127.0.0.1")
LIVE_PORT = int(os.environ.get("LIVE_MCP_PORT", "9878"))
CONNECT_TIMEOUT = 5
RECV_TIMEOUT = 20  # Generous to cover write settle delays


class AbletonConnectionError(Exception):
    """Raised when connection to Ableton fails."""
    pass


class AbletonConnection:
    """Manages TCP connection to the LivePilot Remote Script in Ableton."""

    def __init__(self, host=None, port=None):
        self._host = host or LIVE_HOST
        self._port = port or LIVE_PORT
        self._socket = None

    def connect(self):
        """Establish TCP connection to the Remote Script."""
        if self._socket is not None:
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect((self._host, self._port))
            sock.settimeout(RECV_TIMEOUT)
            self._socket = sock
        except (socket.error, OSError) as e:
            self._socket = None
            raise AbletonConnectionError(
                f"Cannot connect to Ableton on {self._host}:{self._port}. "
                f"Is Ableton running with LivePilot Remote Script loaded? ({e})"
            )

    def disconnect(self):
        """Close the TCP connection."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def is_connected(self):
        """Check if socket is open (does not verify liveness)."""
        return self._socket is not None

    def ping(self):
        """Send a lightweight ping to verify the connection is alive."""
        try:
            response = self._send_raw({"type": "ping"})
            return response.get("result", {}).get("pong") is True
        except Exception:
            return False

    def send_command(self, command_type, params=None):
        """Send a command to Ableton and return the result.

        Performs stale detection via ping before the actual command.
        Auto-reconnects once on failure.

        Args:
            command_type: The command type string (e.g., "set_tempo")
            params: Optional dict of parameters

        Returns:
            Result dict from Ableton

        Raises:
            AbletonConnectionError: If connection fails after retry
            Exception: If command returns an error status
        """
        if not self.is_connected():
            self.connect()

        if not self.ping():
            self.disconnect()
            self.connect()
            if not self.ping():
                raise AbletonConnectionError(
                    "Connection to Ableton is stale and reconnect failed"
                )

        command = {
            "type": command_type,
            "params": params or {},
        }

        try:
            response = self._send_raw(command)
        except (socket.error, OSError):
            self.disconnect()
            self.connect()
            response = self._send_raw(command)

        if response.get("status") == "error":
            error_msg = response.get("error", "Unknown error")
            error_code = response.get("code", "INTERNAL")
            raise Exception(f"[{error_code}] {error_msg}")

        return response.get("result", {})

    def _send_raw(self, command):
        """Send a raw command dict and receive the response."""
        if self._socket is None:
            raise AbletonConnectionError("Not connected to Ableton")

        request_id = str(uuid.uuid4())[:8]
        command["id"] = request_id

        data = json.dumps(command) + "\n"
        self._socket.sendall(data.encode("utf-8"))

        buffer = ""
        while True:
            try:
                chunk = self._socket.recv(65536)
                if not chunk:
                    raise AbletonConnectionError("Connection closed by Ableton")
                buffer += chunk.decode("utf-8")
                if "\n" in buffer:
                    line = buffer.split("\n", 1)[0].strip()
                    if line:
                        return json.loads(line)
            except socket.timeout:
                raise AbletonConnectionError(
                    "Timed out waiting for response from Ableton"
                )
```

- [ ] **Step 3: Commit**

```bash
git add mcp_server/__init__.py mcp_server/connection.py
git commit -m "feat(mcp-server): add connection.py with AbletonConnection TCP client"
```

---

### Task 8: MCP Server — server.py (FastMCP entry + lifespan)

**Files:**
- Create: `mcp_server/server.py`

FastMCP server entry point. Lifespan hook creates the AbletonConnection. All tools access it via the MCP context.

- [ ] **Step 1: Create server.py with FastMCP and lifespan**

```python
# mcp_server/server.py
"""LivePilot MCP Server — FastMCP entry point.

Exposes MCP tools that communicate with Ableton Live
through the LivePilot Remote Script.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from .connection import AbletonConnection


@dataclass
class LivePilotServices:
    """Service container shared across all MCP tools."""
    ableton: AbletonConnection


@asynccontextmanager
async def lifespan(server):
    """Initialize services at startup, clean up at shutdown."""
    ableton = AbletonConnection()
    services = LivePilotServices(ableton=ableton)
    try:
        yield services
    finally:
        ableton.disconnect()


mcp = FastMCP(
    "LivePilot",
    lifespan=lifespan,
)

# Import tool modules to register them with the MCP server.
from .tools import transport  # noqa: F401, E402
from .tools import tracks     # noqa: F401, E402


def main():
    """CLI entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat(mcp-server): add server.py with FastMCP entry and lifespan"
```

---

### Task 9: MCP Server — tools/__init__.py

**Files:**
- Create: `mcp_server/tools/__init__.py`

- [ ] **Step 1: Create tools __init__.py**

```python
# mcp_server/tools/__init__.py
"""MCP tool modules for LivePilot.

Each module registers tools with the FastMCP server via @mcp.tool().
"""
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/tools/__init__.py
git commit -m "feat(mcp-server): add tools package init"
```

---

### Task 10: MCP Server — tools/transport.py (10 MCP tools with validation)

**Files:**
- Create: `mcp_server/tools/transport.py`

- [ ] **Step 1: Create tools/transport.py with all 10 transport MCP tools**

```python
# mcp_server/tools/transport.py
"""Transport MCP tools for LivePilot.

10 tools: get_session_info, set_tempo, set_time_signature,
start/stop/continue_playback, toggle_metronome, set_session_loop,
undo, redo.
"""

from mcp.server.fastmcp import Context

from ..server import mcp, LivePilotServices


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from MCP context."""
    services: LivePilotServices = ctx.request_context.lifespan_context
    return services.ableton


@mcp.tool()
def get_session_info(ctx: Context) -> dict:
    """Get comprehensive Ableton session state: tempo, tracks, scenes, transport."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("get_session_info")


@mcp.tool()
def set_tempo(ctx: Context, tempo: float) -> dict:
    """Set the song tempo in BPM (20-999)."""
    if not 20 <= tempo <= 999:
        raise ValueError("Tempo must be between 20 and 999 BPM")
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_tempo", {"tempo": tempo})


@mcp.tool()
def set_time_signature(ctx: Context, numerator: int, denominator: int) -> dict:
    """Set the time signature (e.g., 4/4, 3/4, 6/8)."""
    if numerator < 1 or numerator > 99:
        raise ValueError("Numerator must be between 1 and 99")
    if denominator not in (1, 2, 4, 8, 16):
        raise ValueError("Denominator must be 1, 2, 4, 8, or 16")
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_time_signature", {
        "numerator": numerator,
        "denominator": denominator,
    })


@mcp.tool()
def start_playback(ctx: Context) -> dict:
    """Start playback from the beginning of the arrangement/session."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("start_playback")


@mcp.tool()
def stop_playback(ctx: Context) -> dict:
    """Stop playback."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("stop_playback")


@mcp.tool()
def continue_playback(ctx: Context) -> dict:
    """Continue playback from the current position."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("continue_playback")


@mcp.tool()
def toggle_metronome(ctx: Context, enabled: bool) -> dict:
    """Enable or disable the metronome click."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("toggle_metronome", {"enabled": enabled})


@mcp.tool()
def set_session_loop(
    ctx: Context,
    enabled: bool,
    start: float | None = None,
    length: float | None = None,
) -> dict:
    """Set loop on/off and optional loop region (start beat, length in beats)."""
    params = {"enabled": enabled}
    if start is not None:
        if start < 0:
            raise ValueError("Loop start must be >= 0")
        params["start"] = start
    if length is not None:
        if length <= 0:
            raise ValueError("Loop length must be > 0")
        params["length"] = length
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_session_loop", params)


@mcp.tool()
def undo(ctx: Context) -> dict:
    """Undo the last action in Ableton."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("undo")


@mcp.tool()
def redo(ctx: Context) -> dict:
    """Redo the last undone action in Ableton."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("redo")
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/tools/transport.py
git commit -m "feat(mcp-server): add transport tools with 10 MCP tools and validation"
```

---

### Task 11: MCP Server — tools/tracks.py (12 MCP tools with validation)

**Files:**
- Create: `mcp_server/tools/tracks.py`

- [ ] **Step 1: Create tools/tracks.py with all 12 tracks MCP tools**

```python
# mcp_server/tools/tracks.py
"""Track MCP tools for LivePilot.

12 tools: get_track_info, create_midi_track, create_audio_track,
create_return_track, delete_track, duplicate_track, set_track_name,
set_track_color, set_track_mute, set_track_solo, set_track_arm,
stop_track_clips.
"""

from mcp.server.fastmcp import Context

from ..server import mcp, LivePilotServices


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from MCP context."""
    services: LivePilotServices = ctx.request_context.lifespan_context
    return services.ableton


def _validate_track_index(track_index: int):
    """Validate track index is non-negative."""
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


def _validate_color_index(color_index: int):
    """Validate color index is in Ableton's range."""
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


@mcp.tool()
def get_track_info(ctx: Context, track_index: int) -> dict:
    """Get detailed info about a track: clips, devices, mixer state."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("get_track_info", {"track_index": track_index})


@mcp.tool()
def create_midi_track(
    ctx: Context,
    index: int = -1,
    name: str | None = None,
    color: int | None = None,
) -> dict:
    """Create a new MIDI track. index=-1 appends at end."""
    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color"] = color
    ableton = _get_ableton(ctx)
    return ableton.send_command("create_midi_track", params)


@mcp.tool()
def create_audio_track(
    ctx: Context,
    index: int = -1,
    name: str | None = None,
    color: int | None = None,
) -> dict:
    """Create a new audio track. index=-1 appends at end."""
    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color"] = color
    ableton = _get_ableton(ctx)
    return ableton.send_command("create_audio_track", params)


@mcp.tool()
def create_return_track(ctx: Context) -> dict:
    """Create a new return track."""
    ableton = _get_ableton(ctx)
    return ableton.send_command("create_return_track")


@mcp.tool()
def delete_track(ctx: Context, track_index: int) -> dict:
    """Delete a track by index. This is destructive — use undo to revert."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("delete_track", {"track_index": track_index})


@mcp.tool()
def duplicate_track(ctx: Context, track_index: int) -> dict:
    """Duplicate a track (copies all clips, devices, and settings)."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("duplicate_track", {"track_index": track_index})


@mcp.tool()
def set_track_name(ctx: Context, track_index: int, name: str) -> dict:
    """Rename a track."""
    _validate_track_index(track_index)
    if not name.strip():
        raise ValueError("Track name cannot be empty")
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_track_name", {
        "track_index": track_index,
        "name": name,
    })


@mcp.tool()
def set_track_color(ctx: Context, track_index: int, color_index: int) -> dict:
    """Set track color (0-69, Ableton's color palette)."""
    _validate_track_index(track_index)
    _validate_color_index(color_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_track_color", {
        "track_index": track_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_track_mute(ctx: Context, track_index: int, muted: bool) -> dict:
    """Mute or unmute a track."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_track_mute", {
        "track_index": track_index,
        "muted": muted,
    })


@mcp.tool()
def set_track_solo(ctx: Context, track_index: int, soloed: bool) -> dict:
    """Solo or unsolo a track."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_track_solo", {
        "track_index": track_index,
        "soloed": soloed,
    })


@mcp.tool()
def set_track_arm(ctx: Context, track_index: int, armed: bool) -> dict:
    """Arm or disarm a track for recording."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("set_track_arm", {
        "track_index": track_index,
        "armed": armed,
    })


@mcp.tool()
def stop_track_clips(ctx: Context, track_index: int) -> dict:
    """Stop all playing clips on a track."""
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    return ableton.send_command("stop_track_clips", {"track_index": track_index})
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/tools/tracks.py
git commit -m "feat(mcp-server): add tracks tools with 12 MCP tools and validation"
```

---

## Chunk 3: CLI, Installer & Tests

### Task 12: CLI — bin/livepilot.js

**Files:**
- Create: `bin/livepilot.js`

Node.js CLI entry point. `npx livepilot` starts the MCP server. `--install` copies the Remote Script. `--status` checks connection. `--version` prints version.

- [ ] **Step 1: Create bin/livepilot.js**

```javascript
#!/usr/bin/env node
// bin/livepilot.js — CLI entry for LivePilot
//
// Usage:
//   npx livepilot              Start MCP server (stdio mode)
//   npx livepilot --install    Install Remote Script to Ableton
//   npx livepilot --uninstall  Remove Remote Script
//   npx livepilot --status     Check Ableton connection
//   npx livepilot --version    Print version

const { execFileSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "..");
const VERSION = require(path.join(ROOT, "package.json")).version;

const args = process.argv.slice(2);

if (args.includes("--version") || args.includes("-v")) {
  console.log(`LivePilot v${VERSION}`);
  process.exit(0);
}

if (args.includes("--install")) {
  const { install } = require(path.join(ROOT, "installer", "install.js"));
  install();
  process.exit(0);
}

if (args.includes("--uninstall")) {
  const { uninstall } = require(path.join(ROOT, "installer", "install.js"));
  uninstall();
  process.exit(0);
}

if (args.includes("--status")) {
  checkStatus();
  // checkStatus handles its own exit
} else {
  // Default: start MCP server in stdio mode
  startServer();
}

function startServer() {
  const python = findPython();
  if (!python) {
    console.error("Error: Python 3.10+ not found. Install Python and try again.");
    process.exit(1);
  }

  // Spawn Python MCP server, inherit stdio for MCP protocol
  const child = spawn(python, ["-m", "mcp_server"], {
    cwd: ROOT,
    stdio: "inherit",
    env: { ...process.env },
  });

  child.on("error", (err) => {
    console.error(`Failed to start MCP server: ${err.message}`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code || 0);
  });
}

function checkStatus() {
  const net = require("net");
  const host = process.env.LIVE_MCP_HOST || "127.0.0.1";
  const port = parseInt(process.env.LIVE_MCP_PORT || "9878", 10);

  console.log(`Checking Ableton connection on ${host}:${port}...`);

  const client = new net.Socket();
  client.setTimeout(3000);

  client.connect(port, host, () => {
    // Send ping
    client.write(JSON.stringify({ id: "status", type: "ping" }) + "\n");
  });

  let buffer = "";
  client.on("data", (data) => {
    buffer += data.toString();
    if (buffer.includes("\n")) {
      try {
        const response = JSON.parse(buffer.split("\n")[0]);
        if (response.result && response.result.pong) {
          console.log("Connected to Ableton Live (LivePilot Remote Script active)");
        } else {
          console.log("Connected but unexpected response");
        }
      } catch {
        console.log("Connected but invalid response");
      }
      client.destroy();
    }
  });

  client.on("timeout", () => {
    console.log("Connection timed out — Ableton not responding");
    client.destroy();
    process.exit(1);
  });

  client.on("error", (err) => {
    if (err.code === "ECONNREFUSED") {
      console.log("Connection refused — Ableton not running or Remote Script not loaded");
    } else {
      console.log(`Connection error: ${err.message}`);
    }
    process.exit(1);
  });
}

function findPython() {
  const candidates = ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const version = execFileSync(cmd, ["--version"], { encoding: "utf-8" });
      const match = version.match(/Python (\d+)\.(\d+)/);
      if (match && (parseInt(match[1]) > 3 || (parseInt(match[1]) === 3 && parseInt(match[2]) >= 10))) {
        return cmd;
      }
    } catch {
      // Not found, try next
    }
  }
  return null;
}
```

- [ ] **Step 2: Commit**

```bash
git add bin/livepilot.js
git commit -m "feat(cli): add livepilot.js CLI with start, install, status, version"
```

---

### Task 13: Installer — paths.js + install.js

**Files:**
- Create: `installer/paths.js`
- Create: `installer/install.js`

Auto-detects Ableton's Remote Scripts directory on macOS and Windows. Copies the `remote_script/LivePilot/` folder there.

- [ ] **Step 1: Create installer/paths.js**

```javascript
// installer/paths.js — Ableton Remote Script path detection

const fs = require("fs");
const path = require("path");
const os = require("os");

/**
 * Find all valid Ableton Remote Script directories.
 * Returns array of { path, description } objects.
 */
function findAbletonPaths() {
  const platform = os.platform();
  const home = os.homedir();
  const candidates = [];

  if (platform === "darwin") {
    // macOS: Live 12 default
    candidates.push({
      path: path.join(home, "Music", "Ableton", "User Library", "Remote Scripts"),
      description: "Ableton User Library (default)",
    });

    // macOS: version-specific
    const prefsDir = path.join(home, "Library", "Preferences", "Ableton");
    if (fs.existsSync(prefsDir)) {
      try {
        const entries = fs.readdirSync(prefsDir);
        for (const entry of entries) {
          if (entry.startsWith("Live 12")) {
            const candidate = path.join(prefsDir, entry, "User Remote Scripts");
            candidates.push({
              path: candidate,
              description: `Ableton ${entry}`,
            });
          }
        }
      } catch {
        // Permission error, skip
      }
    }
  } else if (platform === "win32") {
    const userProfile = process.env.USERPROFILE || home;
    const appData = process.env.APPDATA || path.join(userProfile, "AppData", "Roaming");

    // Windows: Live 12 default
    candidates.push({
      path: path.join(userProfile, "Documents", "Ableton", "User Library", "Remote Scripts"),
      description: "Ableton User Library (default)",
    });

    // Windows: version-specific
    const abletonAppData = path.join(appData, "Ableton");
    if (fs.existsSync(abletonAppData)) {
      try {
        const entries = fs.readdirSync(abletonAppData);
        for (const entry of entries) {
          if (entry.startsWith("Live 12")) {
            const candidate = path.join(abletonAppData, entry, "Preferences", "User Remote Scripts");
            candidates.push({
              path: candidate,
              description: `Ableton ${entry}`,
            });
          }
        }
      } catch {
        // Permission error, skip
      }
    }
  }

  // Filter to paths that exist (or whose parent exists)
  return candidates.filter((c) => {
    return fs.existsSync(c.path) || fs.existsSync(path.dirname(c.path));
  });
}

module.exports = { findAbletonPaths };
```

- [ ] **Step 2: Create installer/install.js**

```javascript
// installer/install.js — Install/uninstall LivePilot Remote Script

const fs = require("fs");
const path = require("path");
const { findAbletonPaths } = require("./paths");

const ROOT = path.resolve(__dirname, "..");
const SOURCE = path.join(ROOT, "remote_script", "LivePilot");

function install() {
  console.log("LivePilot Remote Script Installer\n");

  const paths = findAbletonPaths();

  if (paths.length === 0) {
    console.log("No Ableton installation found.");
    console.log("Please manually copy the remote_script/LivePilot/ folder to:");
    console.log("  macOS: ~/Music/Ableton/User Library/Remote Scripts/LivePilot/");
    console.log("  Windows: Documents\\Ableton\\User Library\\Remote Scripts\\LivePilot\\");
    process.exit(1);
  }

  let targetBase;

  if (paths.length === 1) {
    targetBase = paths[0].path;
    console.log(`Found: ${paths[0].description}`);
    console.log(`  ${targetBase}\n`);
  } else {
    console.log("Multiple Ableton installations found:\n");
    paths.forEach((p, i) => {
      console.log(`  [${i + 1}] ${p.description}`);
      console.log(`      ${p.path}`);
    });
    console.log("\nUsing first found. Pass a custom path with --path <dir> if needed.\n");
    targetBase = paths[0].path;
  }

  const target = path.join(targetBase, "LivePilot");

  // Create target directory if needed
  if (!fs.existsSync(targetBase)) {
    fs.mkdirSync(targetBase, { recursive: true });
  }

  // Copy files
  copyDirSync(SOURCE, target);

  console.log(`LivePilot Remote Script installed to:`);
  console.log(`  ${target}\n`);
  console.log("Next steps:");
  console.log("  1. Restart Ableton Live (or open Preferences > Link, Tempo & MIDI)");
  console.log('  2. Set Control Surface to "LivePilot"');
  console.log("  3. Run: npx livepilot --status");
}

function uninstall() {
  console.log("LivePilot Remote Script Uninstaller\n");

  const paths = findAbletonPaths();

  for (const p of paths) {
    const target = path.join(p.path, "LivePilot");
    if (fs.existsSync(target)) {
      fs.rmSync(target, { recursive: true, force: true });
      console.log(`Removed: ${target}`);
    }
  }

  console.log("\nDone. Restart Ableton Live to complete uninstall.");
}

function copyDirSync(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.name === "__pycache__" || entry.name === ".DS_Store") {
      continue;
    }

    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

module.exports = { install, uninstall };
```

- [ ] **Step 3: Commit**

```bash
git add installer/paths.js installer/install.js
git commit -m "feat(installer): add path detection and install/uninstall for macOS and Windows"
```

---

### Task 14: MCP Server — __main__.py

**Files:**
- Create: `mcp_server/__main__.py`

This allows `python -m mcp_server` to start the server.

- [ ] **Step 1: Create mcp_server/__main__.py**

```python
# mcp_server/__main__.py
"""Allow running as: python -m mcp_server"""

from .server import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/__main__.py
git commit -m "feat: add __main__.py for python -m mcp_server"
```

---

### Task 15: Tests — tool contract + connection mock

**Files:**
- Create: `tests/test_tools_contract.py`
- Create: `tests/test_connection.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create requirements.txt**

```
# requirements.txt — LivePilot MCP Server dependencies
mcp[cli]>=1.0.0
```

- [ ] **Step 2: Create tests/test_tools_contract.py**

```python
# tests/test_tools_contract.py
"""Verify all expected MCP tools are registered with correct names."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_transport_tools_registered():
    """All 10 transport tools must be registered."""
    from mcp_server.server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    expected_transport = {
        "get_session_info", "set_tempo", "set_time_signature",
        "start_playback", "stop_playback", "continue_playback",
        "toggle_metronome", "set_session_loop", "undo", "redo",
    }

    missing = expected_transport - names
    assert not missing, f"Missing transport tools: {missing}"


def test_tracks_tools_registered():
    """All 12 tracks tools must be registered."""
    from mcp_server.server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    expected_tracks = {
        "get_track_info", "create_midi_track", "create_audio_track",
        "create_return_track", "delete_track", "duplicate_track",
        "set_track_name", "set_track_color", "set_track_mute",
        "set_track_solo", "set_track_arm", "stop_track_clips",
    }

    missing = expected_tracks - names
    assert not missing, f"Missing tracks tools: {missing}"


def test_total_tool_count():
    """Verify total registered tool count matches expected.

    Currently 22 (Transport: 10 + Tracks: 12).
    Update this as domains are added toward the full 76.
    """
    from mcp_server.server import mcp

    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 22, f"Expected 22 tools, got {len(tools)}: {[t.name for t in tools]}"
```

- [ ] **Step 3: Create tests/test_connection.py**

```python
# tests/test_connection.py
"""Mock socket tests for AbletonConnection."""

import json
import socket
import threading
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.connection import AbletonConnection, AbletonConnectionError
import pytest


class MockAbletonServer:
    """Minimal TCP server that mimics the Remote Script."""

    def __init__(self, port=0):
        self.port = port
        self.server = None
        self.responses = {}

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", self.port))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]

        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self):
        if self.server:
            self.server.close()

    def _serve(self):
        try:
            client, _ = self.server.accept()
            buffer = ""
            while True:
                data = client.recv(65536)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    command = json.loads(line)
                    response = self._handle(command)
                    client.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except Exception:
            pass

    def _handle(self, command):
        request_id = command.get("id", "unknown")
        command_type = command.get("type")

        if command_type == "ping":
            return {"id": request_id, "status": "success", "result": {"pong": True}}

        result = self.responses.get(command_type, {"ok": True})
        return {"id": request_id, "status": "success", "result": result}


@pytest.fixture
def mock_server():
    server = MockAbletonServer()
    server.start()
    yield server
    server.stop()


def test_connect_and_ping(mock_server):
    """Should connect and ping successfully."""
    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()
    assert conn.ping() is True
    conn.disconnect()


def test_send_command(mock_server):
    """Should send a command and get the result."""
    mock_server.responses["get_session_info"] = {"tempo": 120.0}

    conn = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    conn.connect()
    result = conn.send_command("get_session_info")
    assert result["tempo"] == 120.0
    conn.disconnect()


def test_connection_refused():
    """Should raise AbletonConnectionError when nothing is listening."""
    conn = AbletonConnection(host="127.0.0.1", port=19999)
    with pytest.raises(AbletonConnectionError):
        conn.connect()
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/test_tools_contract.py tests/test_connection.py
git commit -m "test: add tool contract tests and connection mock tests"
```

---

### Task 16: Run tests and verify

- [ ] **Step 1: Install dependencies**

```bash
cd /Users/visansilviugeorge/Desktop/LivePilot
pip install -r requirements.txt pytest
```

- [ ] **Step 2: Run tool contract tests**

```bash
pytest tests/test_tools_contract.py -v
```

Expected: 3 tests pass (transport registered, tracks registered, total count = 22)

- [ ] **Step 3: Run connection tests**

```bash
pytest tests/test_connection.py -v
```

Expected: 3 tests pass (connect+ping, send_command, connection_refused)

- [ ] **Step 4: Fix any failures and re-run until green**

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "fix: resolve test failures"
```

---

## Summary

| Phase | Tasks | Files | Tools |
|-------|-------|-------|-------|
| Remote Script | 1-6 | 6 Python files | 22 handlers (10 transport + 12 tracks) |
| MCP Server | 7-11 | 6 Python files | 22 MCP tools (10 transport + 12 tracks) |
| CLI + Installer | 12-13 | 3 JS files | CLI commands: start, install, uninstall, status, version |
| Tests + Wiring | 14-16 | 4 files | 6 test cases |
| **Total** | **16 tasks** | **19 files** | **22 of 76 tools** |

After this plan completes, the full loop works: `npx livepilot --install` copies Remote Script → Ableton loads it → `npx livepilot` starts MCP server → Claude Code sends tool calls → MCP validates → TCP to Ableton → main thread executes → result flows back.

Remaining 54 tools (clips, notes, devices, scenes, mixing, browser, arrangement) and the plugin (skills, commands, agent) are expansion work on a proven foundation.

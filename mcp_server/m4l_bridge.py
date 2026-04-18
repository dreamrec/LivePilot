"""
LivePilot M4L Bridge — UDP communication with the LivePilot Analyzer device.

Receives spectral data (spectrum bands, RMS, peak, pitch) via UDP/OSC from
the M4L device on the master track. Sends commands back for deep LOM access.

Architecture:
    M4L → UDP:9880 → SpectralReceiver → SpectralCache → MCP tools
    MCP tools → M4LBridge → UDP:9881 → M4L device

OSC address convention:
    - OUTGOING (this side → M4L): address string is sent WITHOUT a leading
      slash because Max's `udpreceive` treats a literal '/' as part of the
      selector. The JS side (livepilot_bridge.js) routes on bare selectors
      like "cmd" / "ping".
    - INCOMING (M4L → this side): the M4L side uses Max's `udpsend`, whose
      outlet messages include the leading slash (e.g. "/response"). The
      `_parse_osc` helper normalizes with `rest = "/" + rest.lstrip("/\\")`
      so both forms are tolerated — keep that normalization; both sides
      bend toward leniency but the outgoing convention here is slash-less.
"""

from __future__ import annotations

import asyncio
import base64
import json
import random
import socket
import struct
import threading
import time
from typing import Any, Callable, Optional


def _encode_string_arg(value: str) -> str:
    """Encode a Python string arg into an ASCII-safe OSC payload.

    The Max JS side decodes values with the ``b64:`` prefix back to UTF-8.
    Keeping the wire payload ASCII-only avoids OSC/client issues with
    non-ASCII file paths and device names.
    """
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
    return "b64:" + encoded.rstrip("=")


def _normalize_macos_path(path: str) -> str:
    """Convert Max-style HFS-ish paths into POSIX paths when possible."""
    if len(path) >= 3 and path[1] == ":" and path[2] in ("/", "\\"):
        return path

    colon = path.find(":")
    slash = path.find("/")
    if colon <= 0 or (slash != -1 and colon > slash):
        return path

    rest = path[colon + 1:]
    if ":" in rest:
        rest = rest.replace(":", "/")
    if not rest.startswith("/"):
        rest = "/" + rest.lstrip("/\\")
    return rest


def _normalize_bridge_payload(value: Any) -> Any:
    """Normalize filesystem paths inside bridge payloads."""
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if key == "file_path" and isinstance(item, str):
                normalized[key] = _normalize_macos_path(item)
            else:
                normalized[key] = _normalize_bridge_payload(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_bridge_payload(item) for item in value]
    return value


class SpectralCache:
    """Thread-safe cache for incoming spectral data from M4L.

    Data goes stale after max_age seconds (default 5).
    When the M4L device is removed, data stops arriving and
    get() returns None — graceful degradation.
    """

    def __init__(self, max_age: float = 5.0):
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._max_age = max_age
        self._connected = False
        self._last_seen = 0.0

    def update(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = {
                "value": value,
                "time": time.monotonic(),
            }
            self._last_seen = time.monotonic()
            self._connected = True

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            age = time.monotonic() - entry["time"]
            if age > self._max_age:
                return None
            return {
                "value": entry["value"],
                "age_ms": int(age * 1000),
            }

    @property
    def is_connected(self) -> bool:
        with self._lock:
            if not self._connected:
                return False
            return (time.monotonic() - self._last_seen) < self._max_age

    def get_all(self) -> dict:
        """Get all cached data that hasn't gone stale."""
        with self._lock:
            now = time.monotonic()
            result = {}
            for key, entry in self._data.items():
                age = now - entry["time"]
                if age <= self._max_age:
                    result[key] = {
                        "value": entry["value"],
                        "age_ms": int(age * 1000),
                    }
            return result


# ─── MIDI Tool bridge (Live 12.0+ MIDI Generators / Transformations) ─────────


class MidiToolCache:
    """Thread-safe cache for MIDI Tool requests from live.miditool.in.

    Mirrors SpectralCache semantics: entries age out after max_age seconds
    (default 5). Distinct cache so MIDI-Tool state doesn't get mixed in with
    analyzer spectrum/RMS/pitch data that tools read by key.

    The last-received request payload carries ``{context, notes}`` where
    ``context`` is ``{grid, selection, scale, seed, tuning}`` emitted by
    Live's ``live.miditool.in`` right outlet, and ``notes`` is the note
    list from the left outlet.
    """

    def __init__(self, max_age: float = 5.0):
        self._lock = threading.Lock()
        self._max_age = max_age
        self._context: Optional[dict] = None
        self._notes: Optional[list] = None
        self._last_seen = 0.0
        self._connected = False
        self._target_tool: Optional[str] = None
        self._target_params: dict = {}

    def set_request(self, context: dict, notes: list) -> None:
        with self._lock:
            self._context = context
            self._notes = notes
            self._last_seen = time.monotonic()
            self._connected = True

    def mark_ready(self) -> None:
        """Called when the bridge announces itself (``/miditool/ready``)."""
        with self._lock:
            self._last_seen = time.monotonic()
            self._connected = True

    def get_last_context(self) -> Optional[dict]:
        with self._lock:
            if self._context is None:
                return None
            age = time.monotonic() - self._last_seen
            if age > self._max_age:
                return None
            return dict(self._context)

    def get_last_notes(self) -> Optional[list]:
        with self._lock:
            if self._notes is None:
                return None
            age = time.monotonic() - self._last_seen
            if age > self._max_age:
                return None
            return list(self._notes)

    @property
    def is_connected(self) -> bool:
        with self._lock:
            if not self._connected:
                return False
            return (time.monotonic() - self._last_seen) < self._max_age

    def set_target(self, tool_name: Optional[str], params: Optional[dict]) -> None:
        with self._lock:
            self._target_tool = tool_name
            self._target_params = dict(params or {})

    def get_target(self) -> tuple[Optional[str], dict]:
        with self._lock:
            return self._target_tool, dict(self._target_params)


# ─── Built-in generator implementations ──────────────────────────────────────
#
# These run in-process when a MIDI Tool request arrives. Each takes
# ``(notes, context, params)`` and returns a new notes list. Notes are dicts
# matching Live's live.miditool.in format:
#   {pitch, start_time, duration, velocity, mute, probability,
#    velocity_deviation, release_velocity, note_id}
#
# Generators should preserve unknown fields so Live's richer note data round-
# trips unchanged through the bridge.


def _bjorklund(pulses: int, steps: int) -> list[int]:
    """Classic Bjorklund equidistribution. Returns [0, 1] pattern of length steps."""
    if steps <= 0:
        return []
    if pulses <= 0:
        return [0] * steps
    if pulses >= steps:
        return [1] * steps

    counts: list[int] = []
    remainders: list[int] = [pulses]
    divisor = steps - pulses
    level = 0
    while True:
        counts.append(divisor // remainders[level])
        remainders.append(divisor % remainders[level])
        divisor = remainders[level]
        level += 1
        if remainders[level] <= 1:
            break
    counts.append(divisor)

    def build(lv: int) -> list[int]:
        if lv == -1:
            return [0]
        if lv == -2:
            return [1]
        out: list[int] = []
        for _ in range(counts[lv]):
            out += build(lv - 1)
        if remainders[lv] != 0:
            out += build(lv - 2)
        return out

    pattern = build(level)
    return pattern[:steps] if len(pattern) >= steps else pattern + [0] * (steps - len(pattern))


def _euclidean_rhythm(notes: list, context: dict, params: dict) -> list:
    """Replace the selection with a Bjorklund-distributed rhythm.

    params:
      steps (int, required)         — subdivisions of the selection
      pulses (int, required)        — hits to distribute
      rotation (int, optional)      — pattern rotation, default 0
      note (int, optional)          — MIDI pitch, default 36 (C1)
      velocity (float, optional)    — 0.0..1.0, default 0.8

    Selection span comes from context["selection"] if present, otherwise
    falls back to min/max of input note start_times.
    """
    steps = int(params.get("steps", 16))
    pulses = int(params.get("pulses", 4))
    rotation = int(params.get("rotation", 0))
    pitch = int(params.get("note", 36))
    velocity = float(params.get("velocity", 0.8))

    if steps <= 0:
        return list(notes)
    pulses = max(0, min(pulses, steps))

    pattern = _bjorklund(pulses, steps)
    if rotation:
        rotation = rotation % steps
        pattern = pattern[rotation:] + pattern[:rotation]

    selection = context.get("selection") or {}
    try:
        start = float(selection.get("start", 0.0))
        end = float(selection.get("end", start + float(steps)))
    except (TypeError, ValueError):
        start = 0.0
        end = float(steps)
    if end <= start:
        # Fall back to input note span, else a bar at current tempo.
        if notes:
            start = min(float(n.get("start_time", 0.0)) for n in notes)
            end = max(
                float(n.get("start_time", 0.0)) + float(n.get("duration", 0.25))
                for n in notes
            )
        if end <= start:
            end = start + 4.0

    step_dur = (end - start) / float(steps)
    velocity = max(0.0, min(1.0, velocity))

    out: list[dict] = []
    for i, hit in enumerate(pattern):
        if not hit:
            continue
        out.append({
            "pitch": max(0, min(127, pitch)),
            "start_time": round(start + i * step_dur, 6),
            "duration": round(step_dur, 6),
            "velocity": velocity,
            "mute": False,
            "probability": 1.0,
            "velocity_deviation": 0.0,
            "release_velocity": 0.5,
            "note_id": -1,
        })
    return out


def _tintinnabuli(notes: list, context: dict, params: dict) -> list:
    """Add an Arvo Pärt-style companion voice on the tonic triad.

    For each input note, emit the input plus a companion note locked to
    the nearest member of the supplied triad (above / below / alternating).

    params:
      t_voice_triad (list[int], optional) — semitone offsets from scale root.
                                             default [0, 4, 7] (major triad)
      direction (str, optional)            — "above" | "below" | "alternate".
                                             default "above"
    """
    triad = params.get("t_voice_triad")
    if not triad:
        triad = [0, 4, 7]
    triad = [int(t) % 12 for t in triad]
    direction = str(params.get("direction", "above")).lower()

    scale = context.get("scale") or {}
    try:
        scale_root = int(scale.get("root", 0)) % 12
    except (TypeError, ValueError):
        scale_root = 0

    out: list[dict] = []
    for i, n in enumerate(notes):
        out.append(dict(n))  # preserve the melody
        try:
            pitch = int(n.get("pitch", 60))
        except (TypeError, ValueError):
            continue

        # Build absolute candidate triad pitches within ±1 octave of the note.
        candidates = []
        for octave in range(-2, 3):
            for t in triad:
                cand = ((pitch // 12) + octave) * 12 + ((scale_root + t) % 12)
                if 0 <= cand <= 127 and cand != pitch:
                    candidates.append(cand)
        if not candidates:
            continue

        if direction == "below":
            below = [c for c in candidates if c < pitch]
            companion = max(below) if below else min(candidates)
        elif direction == "alternate":
            if i % 2 == 0:
                above = [c for c in candidates if c > pitch]
                companion = min(above) if above else max(candidates)
            else:
                below = [c for c in candidates if c < pitch]
                companion = max(below) if below else min(candidates)
        else:  # "above" (default)
            above = [c for c in candidates if c > pitch]
            companion = min(above) if above else max(candidates)

        comp = dict(n)
        comp["pitch"] = max(0, min(127, companion))
        comp["note_id"] = -1  # new note
        out.append(comp)
    return out


def _humanize(notes: list, context: dict, params: dict) -> list:
    """Humanize timing + velocity of existing notes.

    params:
      timing_spread (float, optional)   — beats, default 0.05
      velocity_spread (float, optional) — 0.0..1.0, default 0.1

    Uses context["seed"] for deterministic jitter when present, otherwise
    system randomness.
    """
    timing = float(params.get("timing_spread", 0.05))
    vel_spread = float(params.get("velocity_spread", 0.1))

    seed = context.get("seed")
    rng = random.Random()
    if seed is not None:
        try:
            rng.seed(int(seed))
        except (TypeError, ValueError):
            rng.seed(str(seed))

    out: list[dict] = []
    for n in notes:
        m = dict(n)
        try:
            start = float(m.get("start_time", 0.0))
        except (TypeError, ValueError):
            start = 0.0
        try:
            vel = float(m.get("velocity", 0.8))
        except (TypeError, ValueError):
            vel = 0.8
        m["start_time"] = round(max(0.0, start + rng.uniform(-timing, timing)), 6)
        m["velocity"] = round(max(0.0, min(1.0, vel + rng.uniform(-vel_spread, vel_spread))), 4)
        out.append(m)
    return out


# Registry: name -> callable(notes, context, params) -> list[note_dict]
_GENERATORS: dict[str, Callable[[list, dict, dict], list]] = {
    "euclidean_rhythm": _euclidean_rhythm,
    "tintinnabuli": _tintinnabuli,
    "humanize": _humanize,
}


# Metadata for list_miditool_generators.
GENERATOR_METADATA: dict[str, dict] = {
    "euclidean_rhythm": {
        "description": "Bjorklund-distributed rhythm over the selection",
        "required_params": ["steps", "pulses"],
        "optional_params": ["rotation", "note", "velocity"],
    },
    "tintinnabuli": {
        "description": "Pärt-style voice with tintinnabuli companion",
        "required_params": ["t_voice_triad"],
        "optional_params": ["direction"],
    },
    "humanize": {
        "description": "Humanize timing + velocity of existing notes",
        "required_params": [],
        "optional_params": ["timing_spread", "velocity_spread"],
    },
}


def available_generators() -> list[str]:
    """List registered generator names."""
    return sorted(_GENERATORS.keys())


def run_generator(tool_name: str, notes: list, context: dict, params: dict) -> list:
    """Invoke a registered generator by name. Raises KeyError if unknown."""
    fn = _GENERATORS[tool_name]
    return fn(list(notes or []), dict(context or {}), dict(params or {}))


class SpectralReceiver(asyncio.DatagramProtocol):
    """Receives OSC-formatted UDP packets from the M4L device.

    OSC messages:
        /spectrum f f f f f f f f  — 8-band spectrum
        /peak f                    — peak level
        /rms f                     — RMS level
        /pitch f f                 — MIDI note, amplitude
        /response s                — base64-encoded JSON (single packet)
        /response_chunk i i s      — chunked response (index, total, data)
    """

    BAND_NAMES = ["sub", "low", "low_mid", "mid", "high_mid", "high", "presence", "air"]

    def __init__(self, cache: SpectralCache, miditool_cache: Optional["MidiToolCache"] = None):
        self.cache = cache
        self.miditool_cache = miditool_cache
        self._chunks: dict[str, dict] = {}  # Reassembly buffer for chunked responses
        self._chunk_times: dict[str, float] = {}  # Monotonic timestamp per chunk sequence
        self._chunk_id = 0
        self._response_callback: Optional[asyncio.Future] = None
        self._capture_future: Optional[asyncio.Future] = None
        self._miditool_handler: Optional[Callable[[str, dict, list], None]] = None

    def set_miditool_handler(self, handler: Optional[Callable[[str, dict, list], None]]) -> None:
        """Register a callback invoked on each /miditool/request packet.

        Signature: ``handler(request_id, context, notes) -> None``.
        The handler is expected to run the configured generator and push
        a ``/miditool/response`` OSC back via M4LBridge.send_miditool_response.
        """
        self._miditool_handler = handler

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            self._parse_osc(data)
        except Exception as exc:
            import sys
            print(f"LivePilot: malformed OSC packet from {addr}: {exc}", file=sys.stderr)

    def _parse_osc(self, data: bytes) -> None:
        """Parse a minimal OSC message (address + typed args)."""
        # OSC address is a null-terminated string, padded to 4-byte boundary
        null_pos = data.index(b'\x00')
        address = data[:null_pos].decode('ascii')

        # Skip to type tag string (after address padding)
        offset = null_pos + 1
        while offset % 4 != 0:
            offset += 1

        # Type tag string starts with ','
        if offset < len(data) and data[offset] == ord(','):
            tag_null = data.index(b'\x00', offset)
            type_tags = data[offset + 1:tag_null].decode('ascii')
            offset = tag_null + 1
            while offset % 4 != 0:
                offset += 1
        else:
            type_tags = ""

        # Parse arguments based on type tags
        args = []
        for tag in type_tags:
            if tag == 'f':
                val = struct.unpack('>f', data[offset:offset + 4])[0]
                args.append(val)
                offset += 4
            elif tag == 'i':
                val = struct.unpack('>i', data[offset:offset + 4])[0]
                args.append(val)
                offset += 4
            elif tag == 's':
                s_null = data.index(b'\x00', offset)
                val = data[offset:s_null].decode('ascii')
                args.append(val)
                offset = s_null + 1
                while offset % 4 != 0:
                    offset += 1

        self._handle_message(address, args)

    def _handle_message(self, address: str, args: list) -> None:
        if address == "/spectrum" and len(args) >= 8:
            bands = {}
            for i, name in enumerate(self.BAND_NAMES):
                if i < len(args):
                    bands[name] = round(float(args[i]), 4)
            self.cache.update("spectrum", bands)

        elif address == "/peak" and len(args) >= 1:
            self.cache.update("peak", round(float(args[0]), 4))

        elif address == "/rms" and len(args) >= 1:
            self.cache.update("rms", round(float(args[0]), 4))

        elif address == "/pitch" and len(args) >= 2:
            self.cache.update("pitch", {
                "midi_note": round(float(args[0]), 2),
                "amplitude": round(float(args[1]), 4),
            })

        elif address == "/key" and len(args) >= 2:
            self.cache.update("key", {
                "key": str(args[0]),
                "scale": str(args[1]),
            })

        elif address == "/spectral_shape" and len(args) >= 7:
            names = ["centroid", "spread", "skewness", "kurtosis", "rolloff", "flatness", "crest"]
            self.cache.update("spectral_shape", {
                n: round(float(args[i]), 4) for i, n in enumerate(names)
            })

        elif address == "/mel_bands" and len(args) >= 1:
            self.cache.update("mel_bands", [round(float(a), 6) for a in args])

        elif address == "/chroma" and len(args) >= 12:
            self.cache.update("chroma", [round(float(a), 4) for a in args[:12]])

        elif address == "/onset" and len(args) >= 1:
            strength = round(float(args[0]), 4)
            self.cache.update("onset", {
                "detected": strength > 0.5,
                "strength": strength,
            })

        elif address == "/novelty" and len(args) >= 1:
            score = round(float(args[0]), 4)
            self.cache.update("novelty", {
                "score": score,
                "boundary": score > 0.5,
            })

        elif address == "/loudness" and len(args) >= 2:
            self.cache.update("loudness", {
                "momentary_lufs": round(float(args[0]), 1),
                "true_peak_dbtp": round(float(args[1]), 1),
            })

        elif address == "/capture_complete" and len(args) >= 1:
            self._handle_capture_complete(str(args[0]))

        elif address == "/response" and len(args) >= 1:
            self._handle_response(str(args[0]))

        elif address == "/response_chunk" and len(args) >= 3:
            self._handle_chunk(int(args[0]), int(args[1]), str(args[2]))

        elif address == "/miditool/request" and len(args) >= 1:
            self._handle_miditool_request(str(args[0]))

        elif address == "/miditool/ready":
            if self.miditool_cache is not None:
                self.miditool_cache.mark_ready()

    def _handle_response(self, encoded: str) -> None:
        """Decode a single-packet base64 response.

        Resolves _response_callback exactly once, then clears it. Without the
        clear, a second late packet could overwrite a future belonging to a
        different in-flight command. The protocol has no request id yet
        (livepilot_bridge.js:666 emits bare /response), so correlation relies
        on the single-command-in-flight invariant enforced by M4LBridge._cmd_lock
        plus this one-shot clear.
        """
        try:
            # URL-safe base64 decode (- and _ instead of + and /)
            padded = encoded + "=" * (-len(encoded) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
            result = _normalize_bridge_payload(json.loads(decoded))
            cb = self._response_callback
            if cb and not cb.done():
                cb.set_result(result)
            # Clear regardless — either we consumed it, or it was already
            # done/abandoned. Future packets with no owner get dropped.
            self._response_callback = None
        except Exception as exc:
            import sys
            print(f"LivePilot: failed to decode bridge response: {exc}", file=sys.stderr)

    def _handle_miditool_request(self, encoded: str) -> None:
        """Decode a /miditool/request packet and dispatch to the configured handler.

        Payload: base64(JSON({request_id, context, notes})).
        Packet arrives on the UDP receive thread; the registered handler is
        expected to schedule work on an event loop rather than block here.
        """
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as exc:
            import sys
            print(f"LivePilot: failed to decode miditool request: {exc}", file=sys.stderr)
            return

        request_id = str(payload.get("request_id", ""))
        context = payload.get("context") or {}
        notes = payload.get("notes") or []

        if self.miditool_cache is not None:
            self.miditool_cache.set_request(context, notes)

        handler = self._miditool_handler
        if handler is not None:
            try:
                handler(request_id, context, notes)
            except Exception as exc:
                import sys
                print(f"LivePilot: miditool handler error: {exc}", file=sys.stderr)

    def _handle_chunk(self, index: int, total: int, encoded: str) -> None:
        """Reassemble chunked responses.

        The previous implementation incremented ``_chunk_id`` only when
        ``index == 0`` and assumed the first chunk always arrived first.
        Under UDP reordering (rare on loopback but possible under system
        load), a chunk with ``index > 0`` arriving before ``index 0`` would
        be dropped into the PREVIOUS sequence's bucket — silently corrupting
        that earlier response's payload.

        Until the wire protocol adds an explicit sequence id, the safer
        behavior is: if we see an out-of-order first-chunk (``index > 0``
        with no open bucket), start a fresh bucket but log a warning. That
        way we never poison a prior sequence, and the problem surfaces in
        logs if it happens.
        """
        if index == 0:
            self._chunk_id += 1
            key = str(self._chunk_id)
            self._chunks[key] = {"parts": {}, "total": total}
            self._chunk_times[key] = time.monotonic()
        else:
            key = str(self._chunk_id)
            if key not in self._chunks:
                # Out-of-order arrival. Start a new bucket rather than append
                # to the previous sequence's parts — that's the corruption
                # path. Log once so it's diagnosable.
                import sys
                print(
                    f"LivePilot: chunk index={index}/{total} arrived before "
                    f"index=0 — starting fresh bucket. UDP reordering on "
                    f"loopback suggests system load.",
                    file=sys.stderr,
                )
                self._chunk_id += 1
                key = str(self._chunk_id)
                self._chunks[key] = {"parts": {}, "total": total}
                self._chunk_times[key] = time.monotonic()

        self._chunks[key]["parts"][index] = encoded

        if len(self._chunks[key]["parts"]) == total:
            # All chunks received — reassemble
            full = ""
            for i in range(total):
                full += self._chunks[key]["parts"][i]
            del self._chunks[key]
            self._chunk_times.pop(key, None)
            self._handle_response(full)

        # Evict incomplete chunk sequences older than 30 seconds
        now = time.monotonic()
        stale = [k for k, t in self._chunk_times.items() if now - t > 30.0]
        for k in stale:
            self._chunks.pop(k, None)
            self._chunk_times.pop(k, None)

    def _handle_capture_complete(self, encoded: str) -> None:
        """Decode a /capture_complete OSC message and resolve _capture_future."""
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
            result = _normalize_bridge_payload(json.loads(decoded))
            if self._capture_future and not self._capture_future.done():
                self._capture_future.set_result(result)
        except Exception as exc:
            import sys
            print(f"LivePilot: failed to decode capture response: {exc}", file=sys.stderr)

    def set_response_future(self, future: asyncio.Future) -> None:
        """Set a future to be resolved with the next response."""
        self._response_callback = future

    def set_capture_future(self, future: asyncio.Future) -> None:
        """Set a future to be resolved when a capture_complete OSC arrives."""
        self._capture_future = future


class M4LBridge:
    """Sends commands to the M4L device and waits for responses.

    Commands are sent via UDP to port 9881. Responses come back on port 9880
    and are handled by the SpectralReceiver.
    """

    def __init__(
        self,
        cache: SpectralCache,
        receiver: Optional[SpectralReceiver] = None,
        miditool_cache: Optional[MidiToolCache] = None,
    ):
        self.cache = cache
        self.receiver = receiver
        self.miditool_cache = miditool_cache
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._m4l_addr = ("127.0.0.1", 9881)
        self._cmd_lock: Optional[asyncio.Lock] = None

        # Wire the miditool dispatch: receiver calls us on /miditool/request,
        # we look up the configured generator and push the response back.
        if self.receiver is not None:
            self.receiver.set_miditool_handler(self._dispatch_miditool_request)
            if self.receiver.miditool_cache is None and miditool_cache is not None:
                self.receiver.miditool_cache = miditool_cache

    def _dispatch_miditool_request(
        self, request_id: str, context: dict, notes: list,
    ) -> None:
        """Handle a decoded /miditool/request: run the configured generator,
        send /miditool/response back with {request_id, notes}.

        Invoked from SpectralReceiver on the UDP receive thread. We do not
        await anything here — generators are synchronous, pure Python.
        If no target is configured, pass notes through unchanged (identity).
        """
        if self.miditool_cache is None:
            return
        tool_name, params = self.miditool_cache.get_target()

        try:
            if tool_name and tool_name in _GENERATORS:
                out_notes = run_generator(tool_name, notes, context, params)
            else:
                out_notes = list(notes)
        except Exception as exc:
            import sys
            print(
                f"LivePilot: miditool generator '{tool_name}' failed: {exc} — "
                f"passing input unchanged.",
                file=sys.stderr,
            )
            out_notes = list(notes)

        try:
            self.send_miditool_response(request_id, out_notes)
        except Exception as exc:
            import sys
            print(f"LivePilot: failed to send miditool response: {exc}", file=sys.stderr)

    def send_miditool_config(self, tool_name: Optional[str], params: Optional[dict]) -> None:
        """Push the currently-selected generator config to the JS bridge.

        Sends ``miditool/config`` OSC with a JSON blob. The underlying
        ``_build_osc`` applies the standard ``b64:`` prefix encoding to the
        string arg, so we just pass the raw JSON — single-encoded on the wire.
        The JS side decodes via ``_decode_b64_arg`` like every other command.
        """
        payload = {"tool_name": tool_name or "", "params": params or {}}
        osc = self._build_osc("miditool/config", (json.dumps(payload),))
        self._sock.sendto(osc, self._m4l_addr)

    def send_miditool_response(self, request_id: str, notes: list) -> None:
        """Send transformed notes back to the JS bridge.

        Packet: ``miditool/response`` <b64-encoded JSON({request_id, notes})>.
        The JS side matches request_id and emits notes out live.miditool.out.
        """
        payload = {"request_id": str(request_id or ""), "notes": list(notes or [])}
        osc = self._build_osc("miditool/response", (json.dumps(payload),))
        self._sock.sendto(osc, self._m4l_addr)

    async def send_command(self, command: str, *args: Any, timeout: float = 5.0) -> dict:
        """Send an OSC command to the M4L device and wait for the response."""
        if not self.cache.is_connected:
            return {"error": "LivePilot Analyzer not connected. Drop it on the master track."}

        # Fail fast if there is no receiver to correlate the response. The
        # previous version sent the OSC packet anyway, dropped the reply
        # inside _handle_response (no future registered), and waited out
        # the full 5s timeout before returning a misleading "device may be
        # busy or removed" error. The real cause was "no receiver wired",
        # which the caller should see immediately.
        if self.receiver is None:
            return {
                "error": "M4L bridge has no active receiver — the UDP 9880 "
                         "listener did not start. Check server startup logs "
                         "for a bind failure on port 9880."
            }

        if self._cmd_lock is None:
            self._cmd_lock = asyncio.Lock()
        async with self._cmd_lock:
            # Create a future for the response
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self.receiver.set_response_future(future)

            # Build and send OSC message (no leading / — Max udpreceive
            # passes messagename with / intact to JS, breaking dispatch)
            osc_data = self._build_osc(command, args)
            self._sock.sendto(osc_data, self._m4l_addr)

            # Wait for response with timeout
            try:
                result = await asyncio.wait_for(future, timeout=timeout)
                return result
            except asyncio.TimeoutError:
                return {"error": "M4L bridge timeout — device may be busy or removed"}
            finally:
                # Always clear the future — on success the receiver has already
                # cleared it inside _handle_response, but calling again is a
                # no-op. On timeout this is what prevents a delayed packet from
                # resolving a future belonging to the next command.
                self.receiver.set_response_future(None)

    async def send_capture(self, command: str, *args: Any, timeout: float = 35.0) -> dict:
        """Send a capture command to the M4L device and wait for /capture_complete."""
        if not self.cache.is_connected:
            return {"error": "LivePilot Analyzer not connected. Drop it on the master track."}

        # Fail fast if there is no receiver to correlate the reply. Prior
        # versions sent the OSC packet anyway, never registered a future,
        # and then waited out the full 35s timeout with a misleading
        # "device may be busy or removed" diagnosis — the real cause was
        # "no receiver wired" (UDP 9880 failed to bind at startup).
        if self.receiver is None:
            return {
                "error": "M4L bridge has no active receiver — the UDP 9880 "
                         "listener did not start. Check server startup logs "
                         "for a bind failure on port 9880."
            }

        if self._cmd_lock is None:
            self._cmd_lock = asyncio.Lock()
        async with self._cmd_lock:
            # Cancel any stale capture future before creating a new one
            if self.receiver._capture_future and not self.receiver._capture_future.done():
                self.receiver._capture_future.cancel()

            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self.receiver.set_capture_future(future)

            osc_data = self._build_osc(command, args)
            self._sock.sendto(osc_data, self._m4l_addr)

            try:
                result = await asyncio.wait_for(future, timeout=timeout)
                return result
            except asyncio.TimeoutError:
                # Clean up the dangling future
                self.receiver._capture_future = None
                return {"error": "M4L capture timeout — device may be busy or removed"}

    async def cancel_capture_future(self) -> None:
        """Resolve any in-progress capture future with a stopped result.

        Does NOT acquire _cmd_lock — send_capture holds it during recording.
        Resolving (not cancelling) the future lets send_capture return a
        clean partial-result dict instead of raising CancelledError.
        """
        if self.receiver and self.receiver._capture_future \
                and not self.receiver._capture_future.done():
            self.receiver._capture_future.set_result({
                "ok": True,
                "stopped_early": True,
            })
            self.receiver._capture_future = None

    def _build_osc(self, address: str, args: tuple) -> bytes:
        """Build a minimal OSC message.

        OSC addresses are ASCII-only command names.
        String arguments are encoded into an ASCII-safe ``b64:...`` payload
        and decoded back to UTF-8 in the Max bridge.
        """
        # Address string — always ASCII (command names like "get_params")
        addr_bytes = address.encode('ascii') + b'\x00'
        while len(addr_bytes) % 4 != 0:
            addr_bytes += b'\x00'

        # Type tag string
        type_tags = ","
        arg_data = b""
        for arg in args:
            if isinstance(arg, int):
                type_tags += "i"
                arg_data += struct.pack('>i', arg)
            elif isinstance(arg, float):
                type_tags += "f"
                arg_data += struct.pack('>f', arg)
            elif isinstance(arg, str):
                type_tags += "s"
                encoded = _encode_string_arg(arg)
                s_bytes = encoded.encode('ascii') + b'\x00'
                while len(s_bytes) % 4 != 0:
                    s_bytes += b'\x00'
                arg_data += s_bytes

        tag_bytes = type_tags.encode('ascii') + b'\x00'
        while len(tag_bytes) % 4 != 0:
            tag_bytes += b'\x00'

        return addr_bytes + tag_bytes + arg_data

    def close(self) -> None:
        self._sock.close()

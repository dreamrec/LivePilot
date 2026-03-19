"""
LivePilot M4L Bridge — UDP communication with the LivePilot Analyzer device.

Receives spectral data (spectrum bands, RMS, peak, pitch) via UDP/OSC from
the M4L device on the master track. Sends commands back for deep LOM access.

Architecture:
    M4L → UDP:9880 → SpectralReceiver → SpectralCache → MCP tools
    MCP tools → M4LBridge → UDP:9881 → M4L device
"""

from __future__ import annotations

import asyncio
import base64
import json
import socket
import struct
import threading
import time
from typing import Any, Optional


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

    def __init__(self, cache: SpectralCache):
        self.cache = cache
        self._chunks: dict[str, dict] = {}  # Reassembly buffer for chunked responses
        self._response_callback: Optional[asyncio.Future] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            self._parse_osc(data)
        except Exception:
            pass  # Malformed packet, ignore

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

        elif address == "/response" and len(args) >= 1:
            self._handle_response(str(args[0]))

        elif address == "/response_chunk" and len(args) >= 3:
            self._handle_chunk(int(args[0]), int(args[1]), str(args[2]))

    def _handle_response(self, encoded: str) -> None:
        """Decode a single-packet base64 response."""
        try:
            # URL-safe base64 decode (- and _ instead of + and /)
            padded = encoded + "=" * (-len(encoded) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
            result = json.loads(decoded)
            if self._response_callback and not self._response_callback.done():
                self._response_callback.set_result(result)
        except Exception:
            pass

    def _handle_chunk(self, index: int, total: int, encoded: str) -> None:
        """Reassemble chunked responses."""
        key = str(total)  # Simple key — assumes one response at a time
        if key not in self._chunks:
            self._chunks[key] = {"parts": {}, "total": total}

        self._chunks[key]["parts"][index] = encoded

        if len(self._chunks[key]["parts"]) == total:
            # All chunks received — reassemble
            full = ""
            for i in range(total):
                full += self._chunks[key]["parts"][i]
            del self._chunks[key]
            self._handle_response(full)

    def set_response_future(self, future: asyncio.Future) -> None:
        """Set a future to be resolved with the next response."""
        self._response_callback = future


class M4LBridge:
    """Sends commands to the M4L device and waits for responses.

    Commands are sent via UDP to port 9881. Responses come back on port 9880
    and are handled by the SpectralReceiver.
    """

    def __init__(self, cache: SpectralCache, receiver: Optional[SpectralReceiver] = None):
        self.cache = cache
        self.receiver = receiver
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._m4l_addr = ("127.0.0.1", 9881)

    async def send_command(self, command: str, *args: Any, timeout: float = 5.0) -> dict:
        """Send an OSC command to the M4L device and wait for the response."""
        if not self.cache.is_connected:
            return {"error": "LivePilot Analyzer not connected. Drop it on the master track."}

        # Create a future for the response
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        if self.receiver:
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

    def _build_osc(self, address: str, args: tuple) -> bytes:
        """Build a minimal OSC message."""
        # Address string (null-terminated, padded to 4 bytes)
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
                s_bytes = arg.encode('ascii') + b'\x00'
                while len(s_bytes) % 4 != 0:
                    s_bytes += b'\x00'
                arg_data += s_bytes

        tag_bytes = type_tags.encode('ascii') + b'\x00'
        while len(tag_bytes) % 4 != 0:
            tag_bytes += b'\x00'

        return addr_bytes + tag_bytes + arg_data

    def close(self) -> None:
        self._sock.close()

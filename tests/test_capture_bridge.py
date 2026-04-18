"""Tests for the capture bridge — Task 1 & 2 of v1.8 Perception Layer.

Covers:
  - /capture_complete OSC resolves _capture_future (not _response_callback)
  - /response still resolves _response_callback
  - send_capture uses _capture_future
"""

import asyncio
import base64
import json
import struct
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.m4l_bridge import SpectralCache, SpectralReceiver, M4LBridge


# ── OSC packet builder ──────────────────────────────────────────────────────

def _build_osc(address: str, *args) -> bytes:
    """Build a minimal OSC packet for testing."""
    # Address string (null-terminated, padded to 4 bytes)
    addr_bytes = address.encode("ascii") + b"\x00"
    while len(addr_bytes) % 4 != 0:
        addr_bytes += b"\x00"

    # Determine type tags and encode args
    type_tags = ","
    arg_data = b""
    for arg in args:
        if isinstance(arg, int):
            type_tags += "i"
            arg_data += struct.pack(">i", arg)
        elif isinstance(arg, float):
            type_tags += "f"
            arg_data += struct.pack(">f", arg)
        elif isinstance(arg, str):
            type_tags += "s"
            s_bytes = arg.encode("ascii") + b"\x00"
            while len(s_bytes) % 4 != 0:
                s_bytes += b"\x00"
            arg_data += s_bytes

    tag_bytes = type_tags.encode("ascii") + b"\x00"
    while len(tag_bytes) % 4 != 0:
        tag_bytes += b"\x00"

    return addr_bytes + tag_bytes + arg_data


def _encode_payload(payload: dict) -> str:
    """Encode a dict as base64url for use in OSC string args."""
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _parse_string_args(packet: bytes) -> list[str]:
    """Extract OSC string args from a packet."""
    null_pos = packet.index(b"\x00")
    offset = null_pos + 1
    while offset % 4 != 0:
        offset += 1

    tag_null = packet.index(b"\x00", offset)
    type_tags = packet[offset + 1:tag_null].decode("ascii")
    offset = tag_null + 1
    while offset % 4 != 0:
        offset += 1

    strings = []
    for tag in type_tags:
        if tag == "i" or tag == "f":
            offset += 4
        elif tag == "s":
            s_null = packet.index(b"\x00", offset)
            strings.append(packet[offset:s_null].decode("ascii"))
            offset = s_null + 1
            while offset % 4 != 0:
                offset += 1
    return strings


# ── Task 1 Tests ────────────────────────────────────────────────────────────

def test_capture_complete_resolves_capture_future():
    """OSC /capture_complete resolves _capture_future, NOT _response_callback."""
    loop = asyncio.new_event_loop()
    try:
        cache = SpectralCache()
        receiver = SpectralReceiver(cache)

        capture_fut = loop.create_future()
        response_fut = loop.create_future()

        receiver.set_capture_future(capture_fut)
        receiver.set_response_future(response_fut)

        payload = {"ok": True, "file": "capture_001.wav"}
        encoded = _encode_payload(payload)
        packet = _build_osc("/capture_complete", encoded)

        receiver._parse_osc(packet)

        # capture_future must be resolved
        assert capture_fut.done(), "_capture_future was not resolved by /capture_complete"
        assert capture_fut.result() == payload

        # response_callback must NOT be touched
        assert not response_fut.done(), "_response_callback was wrongly resolved"
    finally:
        loop.close()


def test_regular_response_not_affected_by_capture():
    """OSC /response resolves _response_callback, NOT _capture_future."""
    loop = asyncio.new_event_loop()
    try:
        cache = SpectralCache()
        receiver = SpectralReceiver(cache)

        capture_fut = loop.create_future()
        response_fut = loop.create_future()

        receiver.set_capture_future(capture_fut)
        receiver.set_response_future(response_fut)

        payload = {"params": [1, 2, 3]}
        encoded = _encode_payload(payload)
        packet = _build_osc("/response", encoded)

        receiver._parse_osc(packet)

        # response_callback must be resolved
        assert response_fut.done(), "_response_callback was not resolved by /response"
        assert response_fut.result() == payload

        # capture_future must NOT be touched
        assert not capture_fut.done(), "_capture_future was wrongly resolved by /response"
    finally:
        loop.close()


def test_capture_future_none_safe():
    """Receiving /capture_complete with no future set does not raise."""
    loop = asyncio.new_event_loop()
    try:
        cache = SpectralCache()
        receiver = SpectralReceiver(cache)
        # No set_capture_future call — _capture_future is None

        payload = {"ok": True}
        encoded = _encode_payload(payload)
        packet = _build_osc("/capture_complete", encoded)

        # Should not raise
        receiver._parse_osc(packet)
    finally:
        loop.close()


# ── Task 2 Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bridge_send_capture_uses_capture_future():
    """send_capture sets _capture_future, not _response_callback."""
    cache = SpectralCache()
    # Mark cache as connected so send_capture doesn't bail out early
    cache.update("rms", 0.1)

    receiver = SpectralReceiver(cache)
    bridge = M4LBridge(cache, receiver)

    # We'll simulate the M4L response by resolving the future directly
    # after a tiny delay, instead of sending real UDP.
    async def _simulate_capture_complete():
        await asyncio.sleep(0.05)
        if receiver._capture_future and not receiver._capture_future.done():
            receiver._capture_future.set_result({"ok": True, "file": "test.wav"})

    # Replace _sock with a MagicMock so sendto is a no-op
    import unittest.mock as mock
    bridge._sock = mock.MagicMock()

    task = asyncio.create_task(_simulate_capture_complete())
    result = await bridge.send_capture("capture_audio", 10000, "test.wav", timeout=2.0)
    await task

    assert result.get("ok") is True
    assert result.get("file") == "test.wav"

    # Verify _response_callback was NOT set (still None)
    assert receiver._response_callback is None


# ── BUG-audit-C2: _parse_osc must not crash on malformed packets ───────────


def test_parse_osc_handles_packet_with_no_null_byte():
    """BUG-audit-C2: a packet with no null byte in the address would
    raise `ValueError: substring not found` from data.index(). The
    outer datagram_received catches Exception, but error storms in
    the log are noisy. The parser should detect missing null early
    and skip the packet cleanly."""
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)

    # No null byte anywhere — this should not raise
    bad_packet = b"this is not a valid OSC packet and has no null at all"
    # Parser returns normally (no handler dispatched); no exception
    receiver._parse_osc(bad_packet)

    # Cache untouched
    assert cache.get("spectrum") is None


def test_parse_osc_handles_truncated_string_arg():
    """Packet with a type-tag 's' but no null terminator in the string
    argument should not raise — the packet is malformed and should be
    silently dropped (with the caller's Exception catch acting as the
    ultimate guard)."""
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)

    # Build a packet with address "/foo" + type-tag ",s" but no string null.
    # addr: /foo\x00\x00\x00\x00 (padded to 8)
    # tag: ,s\x00\x00 (padded to 4)
    # string arg: bytes without a null terminator
    packet = b"/foo\x00\x00\x00\x00,s\x00\x00stringwithoutnull"

    # Must not raise out of _parse_osc
    try:
        receiver._parse_osc(packet)
    except ValueError:
        raise AssertionError(
            "Malformed OSC packet with unterminated string arg raised "
            "ValueError — parser should detect and drop cleanly."
        )


def test_parse_osc_handles_truncated_tag_string():
    """Type-tag string without a null terminator."""
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)

    # addr + comma but no tag-string terminator
    packet = b"/foo\x00\x00\x00\x00,ffff_no_terminator_at_all"
    try:
        receiver._parse_osc(packet)
    except ValueError:
        raise AssertionError(
            "Malformed OSC packet with unterminated tag string raised "
            "ValueError — parser should detect and drop cleanly."
        )


def test_parse_osc_valid_packet_still_works():
    """Regression: valid OSC packets must still parse correctly after the fix."""
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    # Valid /peak packet with one float
    packet = _build_osc("/peak", 0.42)
    receiver._parse_osc(packet)
    assert cache.get("peak") is not None
    assert abs(cache.get("peak")["value"] - 0.42) < 0.001


# ── BUG-audit-C1: send_capture must NOT block concurrent send_command ──────


@pytest.mark.asyncio
async def test_send_capture_does_not_block_send_command():
    """BUG-audit-C1: send_capture previously held _cmd_lock for the entire
    recording duration (up to 35s), so any concurrent send_command would
    block. send_capture uses _capture_future and send_command uses
    _response_callback — they are independent and must run concurrently.
    """
    import unittest.mock as mock

    cache = SpectralCache()
    cache.update("rms", 0.1)  # mark connected
    receiver = SpectralReceiver(cache)
    bridge = M4LBridge(cache, receiver)
    bridge._sock = mock.MagicMock()

    # Kick off a send_capture that we will NEVER resolve — it must sit
    # on its future until timeout. If it holds _cmd_lock, the concurrent
    # send_command below will block for the same duration.
    capture_task = asyncio.create_task(
        bridge.send_capture("capture_audio", 10000, "test.wav", timeout=3.0)
    )
    # Let the capture coroutine reach its await point
    await asyncio.sleep(0.05)

    # Now fire a send_command — it must NOT block on the capture's lock.
    # We resolve its _response_callback (which IS the future itself —
    # see m4l_bridge.py _handle_response) immediately so it returns fast.
    async def _resolve_response_soon():
        await asyncio.sleep(0.05)
        cb = receiver._response_callback
        if cb is not None and not cb.done():
            cb.set_result({"ok": True, "from": "cmd"})

    resolver = asyncio.create_task(_resolve_response_soon())
    # If capture holds the lock, this will time out ~30s from now.
    # With the fix, it should return in ~0.05s.
    cmd_result = await asyncio.wait_for(
        bridge.send_command("get_params", timeout=2.0),
        timeout=1.0,  # strict upper bound — fails if blocked on capture
    )
    await resolver

    assert cmd_result.get("from") == "cmd"
    assert cmd_result.get("ok") is True

    # Clean up: resolve the capture so the task doesn't leak
    receiver._capture_future.set_result({"ok": True, "stopped_early": True})
    capture_result = await capture_task
    assert capture_result.get("ok") is True


# ── Task 10 Tests — FluCoMa OSC handlers ──────────────────────────────────


def test_spectral_shape_osc():
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    packet = _build_osc("/spectral_shape", 2840.0, 1200.0, 0.34, 2.1, 6200.0, 0.012, 8.4)
    receiver.datagram_received(packet, ("127.0.0.1", 9880))
    data = cache.get("spectral_shape")
    assert data is not None
    assert abs(data["value"]["centroid"] - 2840.0) < 1


def test_mel_bands_osc():
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    bands = [0.01 * i for i in range(40)]
    packet = _build_osc("/mel_bands", *bands)
    receiver.datagram_received(packet, ("127.0.0.1", 9880))
    data = cache.get("mel_bands")
    assert data is not None
    assert len(data["value"]) == 40


def test_chroma_osc():
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    chroma = [0.85, 0.12, 0.45, 0.08, 0.72, 0.15, 0.05, 0.68, 0.10, 0.52, 0.06, 0.38]
    packet = _build_osc("/chroma", *chroma)
    receiver.datagram_received(packet, ("127.0.0.1", 9880))
    data = cache.get("chroma")
    assert data is not None
    assert len(data["value"]) == 12


def test_loudness_osc():
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    packet = _build_osc("/loudness", -14.2, -1.5)
    receiver.datagram_received(packet, ("127.0.0.1", 9880))
    data = cache.get("loudness")
    assert data is not None
    assert abs(data["value"]["momentary_lufs"] - (-14.2)) < 0.2


def test_build_osc_base64_encodes_unicode_string_args():
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    bridge = M4LBridge(cache, receiver)

    original = "Beyonce_테스트_東京.wav"
    packet = bridge._build_osc("replace_simpler_sample", (0, 1, original))
    strings = _parse_string_args(packet)

    assert len(strings) == 1
    encoded = strings[0]
    assert encoded.startswith("b64:")
    assert encoded.isascii()

    payload = encoded[4:] + "=" * (-len(encoded[4:]) % 4)
    decoded = base64.urlsafe_b64decode(payload).decode("utf-8")
    assert decoded == original


def test_capture_complete_normalizes_max_style_file_path():
    loop = asyncio.new_event_loop()
    try:
        cache = SpectralCache()
        receiver = SpectralReceiver(cache)

        capture_fut = loop.create_future()
        receiver.set_capture_future(capture_fut)

        payload = {
            "ok": True,
            "file": "capture.wav",
            "file_path": "Macintosh HD:/Users/tester/Desktop/capture.wav",
        }
        encoded = _encode_payload(payload)
        packet = _build_osc("/capture_complete", encoded)

        receiver._parse_osc(packet)

        assert capture_fut.done()
        result = capture_fut.result()
        assert result["file_path"] == "/Users/tester/Desktop/capture.wav"
    finally:
        loop.close()


def test_bridge_js_has_b64_decode_support():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bridge_js = os.path.join(root, "m4l_device", "livepilot_bridge.js")
    with open(bridge_js, "r", encoding="utf-8") as f:
        source = f.read()

    assert "_decode_arg_strings" in source
    assert "_decode_b64_arg" in source
    assert 'b64:' in source
    assert "String(arg)" in source

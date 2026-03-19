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

pytestmark = pytest.mark.asyncio(loop_scope="function")

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

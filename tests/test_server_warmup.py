"""Analyzer bridge startup warm-up tests."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.m4l_bridge import SpectralCache
from mcp_server.server import _warm_analyzer_bridge


class _FakeAbleton:
    def __init__(self, master_track):
        self._master_track = master_track

    def send_command(self, command, params=None):
        if command != "get_master_track":
            raise AssertionError(f"Unexpected command: {command}")
        return self._master_track


@pytest.mark.asyncio
async def test_warm_analyzer_bridge_waits_for_first_frame():
    ableton = _FakeAbleton({
        "devices": [
            {
                "index": 0,
                "name": "LivePilot_Analyzer",
                "class_name": "MxDeviceAudioEffect",
                "is_active": True,
            }
        ]
    })
    spectral = SpectralCache()

    async def _emit_frame():
        await asyncio.sleep(0.05)
        spectral.update("rms", 0.1)

    task = asyncio.create_task(_emit_frame())
    await _warm_analyzer_bridge(ableton, spectral, timeout=0.5)
    await task

    assert spectral.is_connected is True


@pytest.mark.asyncio
async def test_warm_analyzer_bridge_skips_when_device_missing():
    ableton = _FakeAbleton({"devices": []})
    spectral = SpectralCache()

    start = asyncio.get_running_loop().time()
    await _warm_analyzer_bridge(ableton, spectral, timeout=0.5)
    elapsed = asyncio.get_running_loop().time() - start

    assert elapsed < 0.1
    assert spectral.is_connected is False

"""Capture-pipeline hardening regression tests (review 2026-07-30).

Covers the four verified defects:
1. capture_stop must merge the device's file/file_path into the in-flight
   capture_audio future (previously silently dropped).
2. _relocate_capture_file must tolerate late disk flushes (bounded retry,
   size-stability) and surface a warning when it gives up.
3. CAPTURE_DIR must be evicted beyond MAX_CAPTURE_FILES.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.m4l_bridge import M4LBridge, SpectralCache, SpectralReceiver
from mcp_server.tools import analyzer


# ── 1. cancel_capture_future merges the device response ────────────────


def _bridge_with_receiver() -> M4LBridge:
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    return M4LBridge(cache, receiver=receiver)


def test_cancel_capture_future_merges_device_file_path():
    bridge = _bridge_with_receiver()

    async def scenario():
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        bridge.receiver.set_capture_future(future)
        await bridge.cancel_capture_future({
            "ok": True,
            "stopped": True,
            "file": "partial_take",
            "file_path": "/tmp/partial_take.aiff",
        })
        return await future

    result = asyncio.run(scenario())
    assert result["ok"] is True
    assert result["stopped_early"] is True
    assert result["file"] == "partial_take"
    assert result["file_path"] == "/tmp/partial_take.aiff"


def test_cancel_capture_future_without_device_result_keeps_old_shape():
    bridge = _bridge_with_receiver()

    async def scenario():
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        bridge.receiver.set_capture_future(future)
        await bridge.cancel_capture_future()
        return await future

    result = asyncio.run(scenario())
    assert result == {"ok": True, "stopped_early": True}


def test_cancel_capture_future_ignores_error_device_result():
    bridge = _bridge_with_receiver()

    async def scenario():
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        bridge.receiver.set_capture_future(future)
        await bridge.cancel_capture_future({"error": "M4L capture timeout"})
        return await future

    result = asyncio.run(scenario())
    assert result == {"ok": True, "stopped_early": True}
    assert "file_path" not in result


def test_cancel_capture_future_noop_when_future_already_done():
    bridge = _bridge_with_receiver()

    async def scenario():
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result({"ok": True, "file_path": "/tmp/full.aiff"})
        bridge.receiver.set_capture_future(future)
        await bridge.cancel_capture_future({"ok": True, "file_path": "/tmp/other.aiff"})
        return await future

    result = asyncio.run(scenario())
    assert result["file_path"] == "/tmp/full.aiff"  # natural completion wins


# ── 2. _relocate_capture_file retry + stability + warning ──────────────


def test_relocate_waits_for_late_file(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "CAPTURE_DIR", str(tmp_path / "captures"))
    os.makedirs(str(tmp_path / "captures"), exist_ok=True)
    src = tmp_path / "late.aiff"

    def write_late():
        time.sleep(0.15)  # within the ~480 ms retry budget
        src.write_bytes(b"x" * 2048)

    writer = threading.Thread(target=write_late)
    writer.start()
    try:
        new_path, warning = analyzer._relocate_capture_file(str(src))
    finally:
        writer.join()

    assert new_path == os.path.join(str(tmp_path / "captures"), "late.aiff")
    assert os.path.isfile(new_path)


def test_relocate_gives_up_with_warning_when_file_never_appears(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "CAPTURE_DIR", str(tmp_path))
    new_path, warning = analyzer._relocate_capture_file(str(tmp_path / "ghost.aiff"))
    assert new_path is None
    assert warning is not None and "did not appear" in warning


def test_relocate_same_path_is_idempotent(tmp_path, monkeypatch):
    """capture_stop relocates first; capture_audio's later relocate of the
    already-final path must be a harmless same-path rename."""
    monkeypatch.setattr(analyzer, "CAPTURE_DIR", str(tmp_path))
    final = tmp_path / "take.aiff"
    final.write_bytes(b"x" * 1024)
    new_path, warning = analyzer._relocate_capture_file(str(final))
    assert new_path == str(final)
    assert os.path.isfile(str(final))


# ── 3. CAPTURE_DIR eviction ─────────────────────────────────────────────


def test_prune_capture_dir_evicts_oldest_beyond_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "CAPTURE_DIR", str(tmp_path))
    monkeypatch.setattr(analyzer, "MAX_CAPTURE_FILES", 5)

    for i in range(8):
        p = tmp_path / f"cap_{i}.wav"
        p.write_bytes(b"x")
        os.utime(p, (1000 + i, 1000 + i))  # cap_0 oldest … cap_7 newest
    (tmp_path / "notes.txt").write_text("not audio — must survive")

    removed = analyzer._prune_capture_dir()

    assert removed == 3
    survivors = sorted(f for f in os.listdir(tmp_path) if f.endswith(".wav"))
    assert survivors == [f"cap_{i}.wav" for i in range(3, 8)]
    assert (tmp_path / "notes.txt").exists()


def test_prune_capture_dir_noop_under_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "CAPTURE_DIR", str(tmp_path))
    monkeypatch.setattr(analyzer, "MAX_CAPTURE_FILES", 5)
    for i in range(3):
        (tmp_path / f"cap_{i}.wav").write_bytes(b"x")
    assert analyzer._prune_capture_dir() == 0
    assert len(list(tmp_path.iterdir())) == 3


def test_prune_capture_dir_missing_dir_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "CAPTURE_DIR", str(tmp_path / "nonexistent"))
    assert analyzer._prune_capture_dir() == 0

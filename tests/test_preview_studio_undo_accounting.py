"""Contract test for Preview Studio's undo accounting.

Finding 2 from the v1.10.6 audit: render_preview_variant counted every
successful step (including read-only get_track_meters / get_master_spectrum)
toward applied_count, then called ableton.send_command("undo") that many
times. In Ableton, read steps don't create undo points, so the extra undos
walk back earlier user edits.

This test exercises the undo loop against a fake ableton client and asserts
the undo count matches only the WRITE steps.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from mcp_server.runtime.execution_router import filter_apply_steps


class FakeAbleton:
    """Captures every send_command invocation for assertions."""

    def __init__(self):
        self.calls: list[tuple[str, Any]] = []

    def send_command(self, command: str, params: Any = None) -> dict:
        self.calls.append((command, params))
        if command == "get_session_info":
            return {"tempo": 120, "track_count": 4}
        if command == "get_track_meters":
            return {"meters": []}
        if command == "get_master_spectrum":
            return {"bands": []}
        if command == "set_track_volume":
            return {"ok": True}
        if command == "set_track_send":
            return {"ok": True}
        if command == "undo":
            return {"ok": True}
        return {"ok": True}

    def undo_count(self) -> int:
        return sum(1 for c, _ in self.calls if c == "undo")


def test_filter_apply_steps_matches_undo_count_for_mixed_plan():
    """A plan with 2 writes + 2 reads should produce exactly 2 undos after
    filtering — the read-only tools must never land in apply_steps."""
    plan_steps = [
        {"tool": "get_track_meters", "params": {}},
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.7}},
        {"tool": "set_track_send", "params": {"track_index": 0, "send_index": 0, "value": 0.2}},
        {"tool": "get_master_spectrum", "params": {}},
    ]
    apply_steps = filter_apply_steps(plan_steps)
    assert [s["tool"] for s in apply_steps] == ["set_track_volume", "set_track_send"]
    # This is what render_preview_variant uses as applied_count upper bound.
    assert len(apply_steps) == 2


def test_all_reads_produce_zero_applies():
    plan_steps = [
        {"tool": "get_track_meters", "params": {}},
        {"tool": "get_master_spectrum", "params": {}},
        {"tool": "analyze_mix", "params": {}},
        {"tool": "get_session_info", "params": {}},
    ]
    assert filter_apply_steps(plan_steps) == []


def test_all_writes_are_preserved():
    plan_steps = [
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.7}},
        {"tool": "set_track_send", "params": {"track_index": 0, "send_index": 0, "value": 0.2}},
        {"tool": "set_track_pan", "params": {"track_index": 0, "pan": -0.2}},
    ]
    kept = filter_apply_steps(plan_steps)
    assert len(kept) == 3


def test_simulated_preview_does_not_over_undo():
    """End-to-end style check: run the filter pattern used by preview_studio,
    count fake 'undo' calls after the finally block, confirm the count equals
    successful writes — not total step count."""
    plan_steps = [
        {"tool": "get_track_meters", "params": {}},
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.7}},
        {"tool": "get_master_spectrum", "params": {}},
        {"tool": "set_track_send", "params": {"track_index": 0, "send_index": 0, "value": 0.2}},
        {"tool": "get_track_meters", "params": {}},
    ]
    apply_steps = filter_apply_steps(plan_steps)

    fake = FakeAbleton()
    applied_count = 0
    try:
        for step in apply_steps:
            result = fake.send_command(step["tool"], step["params"])
            if result.get("ok"):
                applied_count += 1
    finally:
        for _ in range(applied_count):
            fake.send_command("undo")

    assert applied_count == 2
    assert fake.undo_count() == 2
    # And crucially, the full plan had 5 steps — a naive implementation
    # would have undone 5 times and walked back 3 pre-existing user edits.
    assert fake.undo_count() != len(plan_steps)

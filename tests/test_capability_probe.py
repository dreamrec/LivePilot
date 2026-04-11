"""Tests for runtime capability probe."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.capability_probe import probe_capabilities, format_doctor_report


class _Ctx:
    def __init__(self, lifespan_context):
        self.lifespan_context = lifespan_context


class _ConnectedSpectral:
    is_connected = True


def test_probe_without_ableton():
    report = probe_capabilities(ableton=None, ctx=None)
    assert report["ableton"]["status"] == "unavailable"
    assert report["m4l_bridge"]["status"] == "unavailable"
    assert report["remote_script"]["command_count"] >= 80
    # Without Ableton, active tier is creative_intelligence (heuristic-only)
    assert report["tier"]["active"] == "creative_intelligence"
    assert report["tier"]["levels"]["core_control"] is False
    assert report["tier"]["levels"]["creative_intelligence"] is True


def test_probe_persistence():
    report = probe_capabilities()
    # ~/.livepilot/ should exist from earlier taste persistence work
    assert report["persistence"]["status"] in ("ok", "unavailable")


def test_format_doctor_report():
    report = probe_capabilities()
    text = format_doctor_report(report)
    assert "LivePilot Capability Report" in text
    assert "ableton" in text
    assert "persistence" in text


def test_probe_has_all_areas():
    report = probe_capabilities()
    expected = {"ableton", "remote_script", "m4l_bridge", "offline_perception", "persistence", "tier"}
    assert expected.issubset(set(report.keys()))


def test_probe_detects_m4l_bridge_from_lifespan_context():
    report = probe_capabilities(ableton=None, ctx=_Ctx({"m4l": object(), "spectral": _ConnectedSpectral()}))
    assert report["m4l_bridge"]["status"] == "ok"

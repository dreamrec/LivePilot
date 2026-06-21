"""Tests for the real-time Arrangement automation recorder."""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _load_tool():
    from mcp_server.tools.automation import record_parameter_automation_realtime

    tool = record_parameter_automation_realtime
    return getattr(tool, "fn", tool)


def _load_m4l_tool():
    from mcp_server.tools.automation import record_parameter_automation_m4l_curve

    tool = record_parameter_automation_m4l_curve
    return getattr(tool, "fn", tool)


class _FakeAbleton:
    def __init__(
        self,
        *,
        record_engages: bool = True,
        record_resets_to_start: bool = False,
    ):
        self.calls: list[tuple[str, dict]] = []
        self.tracks = [
            {"index": 0, "name": "Target", "arm": False},
            {"index": 1, "name": "Previously Armed", "arm": True},
        ]
        self.position = 32.0
        self.is_playing = False
        self.record_mode = False
        self.record_engages = record_engages
        self.record_resets_to_start = record_resets_to_start
        self.deleted_tracks: list[int] = []
        self.parameter_values: list[float] = []

    def _session(self) -> dict:
        return {
            "tempo": 120.0,
            "current_song_time": self.position,
            "is_playing": self.is_playing,
            "record_mode": self.record_mode,
            "session_record": False,
            "tracks": [dict(track) for track in self.tracks],
            "arrangement_override": False,
        }

    def send_command(self, command: str, params: dict | None = None) -> dict:
        params = params or {}
        self.calls.append((command, dict(params)))

        if command == "get_session_info":
            return self._session()
        if command == "get_recording_state":
            return {
                "record_mode": self.record_mode,
                "session_record": False,
                "is_playing": self.is_playing,
                "current_song_time": self.position,
                "automation_record": {"supported": True, "value": True},
            }
        if command == "get_device_parameters":
            return {
                "parameters": [
                    {
                        "index": 9,
                        "name": "Output",
                        "value": 0.0,
                        "min": -1.0,
                        "max": 1.0,
                    },
                ],
            }
        if command == "create_midi_track":
            index = len(self.tracks)
            self.tracks.append({
                "index": index,
                "name": params.get("name", "MIDI"),
                "arm": False,
            })
            return {"index": index, "name": params.get("name", "MIDI")}
        if command == "set_track_input_monitoring":
            return {"index": params["track_index"], "monitoring_state": params["state"]}
        if command == "set_track_arm":
            self.tracks[int(params["track_index"])]["arm"] = bool(params["arm"])
            return {"index": params["track_index"], "arm": bool(params["arm"])}
        if command == "stop_playback":
            self.is_playing = False
            return {"is_playing": False}
        if command == "stop_all_clips":
            return {"stopped": True}
        if command == "back_to_arranger":
            return {"back_to_arranger": False}
        if command == "jump_to_time":
            self.position = float(params["beat_time"])
            return {"current_song_time": self.position}
        if command == "continue_playback":
            self.is_playing = True
            return {"is_playing": True}
        if command == "start_recording":
            self.is_playing = True
            self.record_mode = bool(self.record_engages)
            if self.record_resets_to_start:
                self.position = 0.0
            return {"record_mode": self.record_mode, "session_record": False}
        if command == "set_device_parameter":
            self.parameter_values.append(float(params["value"]))
            return {
                "name": "Output",
                "value": float(params["value"]),
                "value_string": "0.00 dB",
            }
        if command == "stop_recording":
            self.record_mode = False
            return {"record_mode": False, "session_record": False}
        if command == "delete_track":
            index = int(params["track_index"])
            self.deleted_tracks.append(index)
            if index == len(self.tracks) - 1:
                self.tracks.pop()
            return {"deleted": True, "index": index}
        if command == "start_playback":
            self.is_playing = True
            return {"is_playing": True}

        raise AssertionError(f"Unexpected command: {command}")


class _FakeCtx:
    def __init__(self, fake: _FakeAbleton):
        self.ableton = fake
        self.lifespan_context = {"ableton": fake}


class _FakeM4LBridge:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.armed_payload = None
        self.cancelled = False

    async def send_command(self, command: str, *args, **kwargs):
        self.calls.append((command, args, kwargs))
        if command == "automation_curve_arm":
            self.armed_payload = json.loads(args[0])
            return {
                "ok": True,
                "status": "armed",
                "id": self.armed_payload["id"],
                "point_count": len(self.armed_payload["points"]),
                "first_beat": self.armed_payload["points"][0]["beat"],
                "end_beat": self.armed_payload["end_beat"],
                "mode": self.armed_payload["mode"],
                "tick_ms": self.armed_payload["tick_ms"],
            }
        if command == "automation_curve_status":
            return {
                "ok": True,
                "status": "completed",
                "set_count": 8,
                "point_count": len((self.armed_payload or {}).get("points", [])),
            }
        if command == "automation_curve_cancel":
            self.cancelled = True
            return {"ok": True, "status": "cancelled"}
        raise AssertionError(f"Unexpected bridge command: {command}")


class _FakePingBridge:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    async def send_command(self, command: str, *args, **kwargs):
        self.calls.append((command, args, kwargs))
        if command == "ping":
            return {"ok": True, "version": "test"}
        if command == "get_auto_state":
            return {"automated_params": [{"index": 9, "name": "Output"}]}
        raise AssertionError(f"Unexpected bridge command: {command}")


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    from mcp_server.tools import automation

    async def _noop(_seconds):
        return None

    monkeypatch.setattr(automation.asyncio, "sleep", _noop)


def _run(coro):
    return asyncio.run(coro)


def test_realtime_recorder_uses_temp_trigger_track_not_session_clip(monkeypatch):
    from mcp_server.tools import automation

    states = [
        ({"automated_params": []}, []),
        ({"automated_params": [{"index": 9, "name": "Output", "automation_state": 1}]}, []),
    ]

    async def fake_read_state(*_args, **_kwargs):
        return states.pop(0)

    monkeypatch.setattr(automation, "_read_automation_state", fake_read_state)
    fake = _FakeAbleton()

    result = _run(_load_tool()(
        _FakeCtx(fake),
        track_index=0,
        device_index=0,
        parameter_index=9,
        points=[{"time": 0.0, "value": -0.25}, {"time": 1.0, "value": 0.1}],
        start_beat=16.0,
        duration_beats=2.0,
    ))

    commands = [command for command, _params in fake.calls]
    assert result["ok"] is True
    assert "arrangement_automation_via_session_record_start" not in commands
    assert "arrangement_automation_via_session_record_complete" not in commands
    assert "create_clip" not in commands
    assert "fire_clip" not in commands
    assert "create_midi_track" in commands
    assert "delete_track" in commands
    assert fake.parameter_values == [0.0, -0.25, 0.1]
    assert result["record_start_beat"] == 15.75
    assert result["transport_start_beat"] == 7.75
    assert result["record_duration_beats"] == 2.25
    assert result["guard_point"] == {"time": 0.0, "value": 0.0, "guard": True}
    assert result["points_recorded"][0]["guard"] is True
    assert result["points_recorded"][1]["requested_time"] == 0.0
    assert result["verified"] is True
    assert result["temporary_trigger_track"] is True
    start_calls = [
        params for command, params in fake.calls if command == "start_recording"
    ]
    assert start_calls == [{"arrangement": True}]


def test_realtime_recorder_fails_safe_if_record_starts_outside_preroll(monkeypatch):
    from mcp_server.tools import automation

    async def fake_read_state(*_args, **_kwargs):
        return {"automated_params": []}, []

    monkeypatch.setattr(automation, "_read_automation_state", fake_read_state)
    fake = _FakeAbleton(record_resets_to_start=True)

    result = _run(_load_tool()(
        _FakeCtx(fake),
        track_index=0,
        device_index=0,
        parameter_index=9,
        points=[{"time": 0.0, "value": -0.25}],
        start_beat=16.0,
        duration_beats=1.0,
        require_verification=False,
    ))

    jump_calls = [
        params["beat_time"]
        for command, params in fake.calls
        if command == "jump_to_time"
    ]
    assert result["ok"] is False
    assert result["phase"] == "transport"
    assert "outside the pre-roll window" in result["error"]
    assert jump_calls[:2] == [7.75, 7.75]
    assert fake.parameter_values == []


def test_m4l_curve_recorder_arms_scheduler_not_tcp_point_writes(monkeypatch):
    from mcp_server.tools import automation

    async def fake_read_state(*_args, **_kwargs):
        return {"automated_params": []}, []

    fake_bridge = _FakeM4LBridge()

    async def fake_ready_bridge(*_args, **_kwargs):
        return fake_bridge, []

    monkeypatch.setattr(automation, "_read_automation_state", fake_read_state)
    monkeypatch.setattr(automation, "_get_ready_m4l_bridge", fake_ready_bridge)
    fake = _FakeAbleton()

    result = _run(_load_m4l_tool()(
        _FakeCtx(fake),
        track_index=0,
        device_index=0,
        parameter_index=9,
        points=[{"time": 0.0, "value": -0.25}, {"time": 1.0, "value": 0.1}],
        start_beat=16.0,
        duration_beats=2.0,
        require_verification=False,
        mode="linear",
        tick_ms=10,
    ))

    commands = [command for command, _params in fake.calls]
    bridge_commands = [command for command, _args, _kwargs in fake_bridge.calls]
    assert result["ok"] is True
    assert "set_device_parameter" not in commands
    assert "continue_playback" in commands
    assert "start_recording" in commands
    assert "delete_track" in commands
    assert bridge_commands == ["automation_curve_arm", "automation_curve_status"]
    assert fake_bridge.armed_payload["mode"] == "linear"
    assert fake_bridge.armed_payload["time_base"] == "wall_clock"
    assert fake_bridge.armed_payload["origin_beat"] == 7.75
    assert fake_bridge.armed_payload["seconds_per_beat"] == 0.5
    assert fake_bridge.armed_payload["tick_ms"] == 10
    assert fake_bridge.armed_payload["points"] == [
        {"beat": 15.75, "value": 0.0, "guard": True, "requested_time": None},
        {"beat": 16.0, "value": -0.25, "guard": False, "requested_time": 0.0},
        {"beat": 17.0, "value": 0.1, "guard": False, "requested_time": 1.0},
    ]
    assert result["scheduler_status"]["status"] == "completed"


def test_m4l_ready_uses_command_ping_when_spectral_cache_is_stale(monkeypatch):
    from mcp_server.m4l_bridge import SpectralCache
    from mcp_server.tools import analyzer, automation

    fake_bridge = _FakePingBridge()
    ctx = _FakeCtx(_FakeAbleton())
    ctx.lifespan_context["spectral"] = SpectralCache()
    ctx.lifespan_context["m4l"] = fake_bridge

    async def fake_ensure(*_args, **_kwargs):
        return {"status": "already_loaded"}

    async def fake_reconnect(*_args, **_kwargs):
        return {"ok": True}

    monkeypatch.setattr(analyzer, "ensure_analyzer_on_master", fake_ensure)
    monkeypatch.setattr(analyzer, "reconnect_bridge", fake_reconnect)

    bridge, warnings = _run(automation._get_ready_m4l_bridge(ctx))

    assert bridge is fake_bridge
    assert fake_bridge.calls == [("ping", (), {"timeout": 1.5})]
    assert any("command bridge responded" in warning for warning in warnings)


def test_read_automation_state_falls_back_to_direct_bridge_on_stale_gate(monkeypatch):
    from mcp_server.m4l_bridge import SpectralCache
    from mcp_server.tools import analyzer, automation

    fake_bridge = _FakePingBridge()
    ctx = _FakeCtx(_FakeAbleton())
    ctx.lifespan_context["spectral"] = SpectralCache()
    ctx.lifespan_context["m4l"] = fake_bridge

    async def fake_ensure(*_args, **_kwargs):
        return {"status": "already_loaded"}

    async def fake_reconnect(*_args, **_kwargs):
        return {"ok": True}

    async def stale_gate(*_args, **_kwargs):
        raise ValueError("LivePilot Analyzer is loaded, but the UDP bridge is not connected")

    monkeypatch.setattr(analyzer, "ensure_analyzer_on_master", fake_ensure)
    monkeypatch.setattr(analyzer, "reconnect_bridge", fake_reconnect)
    monkeypatch.setattr(analyzer, "get_automation_state", stale_gate)

    state, warnings = _run(automation._read_automation_state(ctx, 0, 0))

    assert state == {"automated_params": [{"index": 9, "name": "Output"}]}
    assert fake_bridge.calls == [("get_auto_state", (0, 0), {"timeout": 10.0})]
    assert any("direct M4L command bridge" in warning for warning in warnings)


def test_realtime_recorder_refuses_existing_automation_by_default(monkeypatch):
    from mcp_server.tools import automation

    async def fake_read_state(*_args, **_kwargs):
        return {
            "automated_params": [{"index": 9, "name": "Output", "automation_state": 1}],
        }, []

    monkeypatch.setattr(automation, "_read_automation_state", fake_read_state)
    fake = _FakeAbleton()

    result = _run(_load_tool()(
        _FakeCtx(fake),
        track_index=0,
        device_index=0,
        parameter_name="Output",
        points=[{"time": 0.0, "value": 0.2}],
        start_beat=8.0,
    ))

    commands = [command for command, _params in fake.calls]
    assert result["ok"] is False
    assert result["phase"] == "preflight"
    assert "already has automation" in result["error"]
    assert "create_midi_track" not in commands


def test_realtime_recorder_cleans_up_when_record_never_engages(monkeypatch):
    from mcp_server.tools import automation

    async def fake_read_state(*_args, **_kwargs):
        return {"automated_params": []}, []

    monkeypatch.setattr(automation, "_read_automation_state", fake_read_state)
    fake = _FakeAbleton(record_engages=False)

    result = _run(_load_tool()(
        _FakeCtx(fake),
        track_index=0,
        device_index=0,
        parameter_index=9,
        points=[{"time": 0.0, "value": 0.2}],
        start_beat=8.0,
        require_verification=False,
    ))

    commands = [command for command, _params in fake.calls]
    assert result["ok"] is False
    assert result["phase"] == "transport"
    assert "Arrangement record did not engage" in result["error"]
    assert "stop_recording" in commands
    assert "delete_track" in commands
    assert fake.deleted_tracks == [2]
    assert fake.tracks[1]["arm"] is True

"""Regression tests for verified arrangement playback positioning."""

from __future__ import annotations

from types import SimpleNamespace

from mcp_server.tools import arrangement as arrangement_tools


class _FakeAbleton:
    def __init__(
        self,
        session_reads: list[dict] | None = None,
        playing_clip_reads: list[list[dict]] | None = None,
    ):
        self.calls: list[tuple[str, dict]] = []
        self.position = 99.0
        self.is_playing = True
        self.loop = False
        self.session_reads = list(session_reads or [])
        self.playing_clip_reads = list(playing_clip_reads or [])

    def send_command(self, command: str, params: dict | None = None) -> dict:
        params = params or {}
        self.calls.append((command, dict(params)))

        if command == "stop_playback":
            self.is_playing = False
            return {"is_playing": False}
        if command == "stop_all_clips":
            return {"stopped": True}
        if command == "get_playing_clips":
            if self.playing_clip_reads:
                return {"clips": self.playing_clip_reads.pop(0)}
            return {"clips": []}
        if command == "back_to_arranger":
            return {"back_to_arranger": False}
        if command == "set_session_loop":
            self.loop = bool(params.get("enabled"))
            return {
                "loop": self.loop,
                "loop_start": params.get("loop_start"),
                "loop_length": params.get("loop_length"),
            }
        if command == "jump_to_time":
            self.position = float(params["beat_time"])
            return {"current_song_time": self.position}
        if command == "start_playback":
            self.is_playing = True
            return {"is_playing": True}
        if command == "continue_playback":
            self.is_playing = True
            return {"is_playing": True}
        if command == "get_session_info":
            if self.session_reads:
                override = self.session_reads.pop(0)
                return {
                    "current_song_time": override.get("current_song_time", self.position),
                    "is_playing": override.get("is_playing", self.is_playing),
                    "loop": override.get("loop", self.loop),
                    "arrangement_override": override.get("arrangement_override", False),
                }
            return {
                "current_song_time": self.position,
                "is_playing": self.is_playing,
                "loop": self.loop,
                "arrangement_override": False,
            }
        raise AssertionError(f"Unexpected command: {command}")


def _ctx(fake: _FakeAbleton):
    return SimpleNamespace(lifespan_context={"ableton": fake})


def test_force_arrangement_sequences_seek_then_start(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton()

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=0, play=True)

    commands = [command for command, _params in fake.calls]
    assert commands[:6] == [
        "stop_playback",
        "stop_all_clips",
        "get_playing_clips",
        "back_to_arranger",
        "jump_to_time",
        "get_session_info",
    ]
    assert "continue_playback" not in commands
    assert "start_playback" in commands
    assert result["verified_position"] is True
    assert result["verified_playback"] is True
    assert result["session_clear"] is True
    assert result["position"] == 0.0


def test_force_arrangement_retries_when_session_info_reports_stale_position(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton(session_reads=[
        {"current_song_time": 64.0, "is_playing": False},
        {"current_song_time": 0.0, "is_playing": False},
        {"current_song_time": 0.0, "is_playing": True},
    ])

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=0, play=True)

    jump_calls = [params for command, params in fake.calls if command == "jump_to_time"]
    assert jump_calls == [{"beat_time": 0.0}, {"beat_time": 0.0}]
    assert result["seek_attempts"] == 2
    assert result["verified_position"] is True
    assert result["verified_playback"] is True
    assert result["warnings"] == []


def test_force_arrangement_retries_start_until_playing_verifies(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton(session_reads=[
        {"current_song_time": 4.0, "is_playing": False},
        {"current_song_time": 4.0, "is_playing": False},
        {"current_song_time": 4.0, "is_playing": True},
    ])

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=4, play=True)

    commands = [command for command, _params in fake.calls]
    assert commands.count("start_playback") == 2
    assert result["play_attempts"] == 2
    assert result["verified_playback"] is True


def test_force_arrangement_accepts_normal_playhead_advance_after_start(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton(session_reads=[
        {"current_song_time": 0.0, "is_playing": False},
        {"current_song_time": 2.9, "is_playing": True},
    ])

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=0, play=True)

    commands = [command for command, _params in fake.calls]
    assert commands.count("start_playback") == 1
    assert result["play_attempts"] == 1
    assert result["verified_playback"] is True
    assert result["warnings"] == []


def test_force_arrangement_reseeks_after_start_when_live_resumes_old_position(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton(session_reads=[
        {"current_song_time": 4.0, "is_playing": False},
        {"current_song_time": 128.0, "is_playing": True},
        {"current_song_time": 4.0, "is_playing": True},
    ])

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=4, play=True)

    jump_calls = [params for command, params in fake.calls if command == "jump_to_time"]
    assert jump_calls == [{"beat_time": 4.0}, {"beat_time": 4.0}]
    assert result["verified_playback"] is True
    assert result["position"] == 4.0


def test_force_arrangement_play_false_only_verifies_seek(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton()

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=8, play=False)

    commands = [command for command, _params in fake.calls]
    assert "continue_playback" not in commands
    assert result["position"] == 8.0
    assert result["is_playing"] is False
    assert result["verified_position"] is True
    assert result["verified_playback"] is True


def test_force_arrangement_waits_for_session_clips_to_clear(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton(playing_clip_reads=[
        [{
            "track_index": 0,
            "track_name": "Session Loop",
            "clip_index": 0,
            "clip_name": "Loop",
            "is_playing": True,
            "is_triggered": False,
        }],
        [],
        [],
    ])

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=0, play=True)

    commands = [command for command, _params in fake.calls]
    assert commands.count("stop_all_clips") == 2
    assert result["session_clear"] is True
    assert result["session_clear_attempts"] == 2
    assert result["playing_clips"] == []
    assert result["verified_playback"] is True


def test_force_arrangement_retries_when_arrangement_override_stays_lit(monkeypatch):
    monkeypatch.setattr(arrangement_tools, "_TRANSPORT_SETTLE_SECONDS", 0)
    fake = _FakeAbleton(session_reads=[
        {"current_song_time": 0.0, "is_playing": False},
        {"current_song_time": 0.0, "is_playing": True, "arrangement_override": True},
        {"current_song_time": 0.0, "is_playing": True, "arrangement_override": False},
    ])

    result = arrangement_tools.force_arrangement(_ctx(fake), beat_time=0, play=True)

    commands = [command for command, _params in fake.calls]
    assert commands.count("start_playback") == 2
    assert commands.count("back_to_arranger") >= 3
    assert result["arrangement_active"] is True
    assert result["arrangement_override"] is False
    assert result["verified_playback"] is True

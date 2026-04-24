"""Tests for experiment baseline transport snapshot / restore (v1.19 Item A).

Between branches of an experiment, state drift (playing clips, changed
mute/solo/arm, transport position) makes each branch's ``before_snapshot``
incomparable. The baseline module captures a reference transport state
once before the first branch runs and restores it between branches.

v1.18.0 Test 8 live-verified the drift: 3-branch experiment produced
track_meters[0].level values of 0.764, 0.000, 0.873 across branches'
before_snapshots — clip stopped mid-experiment.
"""

from __future__ import annotations

import time

import pytest


# ── MockAbleton reused across baseline tests ─────────────────────────────────


class MockAbleton:
    """Records every send_command call in order; returns queued responses."""

    def __init__(self, get_session_info_response: dict | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._gsi = get_session_info_response or {
            "is_playing": False,
            "current_song_time": 0.0,
            "tracks": [],
        }

    def send_command(self, tool: str, params: dict | None = None):
        self.calls.append((tool, dict(params or {})))
        if tool == "get_session_info":
            return self._gsi
        return {"ok": True}


# ── capture_baseline ─────────────────────────────────────────────────────────


class TestCaptureBaseline:

    def test_records_is_playing(self):
        from mcp_server.experiment.baseline import capture_baseline

        ableton = MockAbleton({
            "is_playing": True, "current_song_time": 4.5, "tracks": [],
        })
        baseline = capture_baseline(ableton)
        assert baseline.is_playing is True

    def test_records_song_time(self):
        from mcp_server.experiment.baseline import capture_baseline

        ableton = MockAbleton({
            "is_playing": False, "current_song_time": 12.25, "tracks": [],
        })
        baseline = capture_baseline(ableton)
        assert baseline.song_time == pytest.approx(12.25)

    def test_records_per_track_mute_solo_arm(self):
        from mcp_server.experiment.baseline import capture_baseline

        ableton = MockAbleton({
            "is_playing": False, "current_song_time": 0.0,
            "tracks": [
                {"index": 0, "mute": False, "solo": False, "arm": True},
                {"index": 1, "mute": True,  "solo": False, "arm": False},
                {"index": 2, "mute": False, "solo": True,  "arm": False},
            ],
        })
        baseline = capture_baseline(ableton)
        assert len(baseline.track_states) == 3
        assert baseline.track_states[0] == {
            "index": 0, "mute": False, "solo": False, "arm": True,
        }
        assert baseline.track_states[1]["mute"] is True
        assert baseline.track_states[2]["solo"] is True

    def test_empty_tracks_list(self):
        from mcp_server.experiment.baseline import capture_baseline

        ableton = MockAbleton()  # default: zero tracks
        baseline = capture_baseline(ableton)
        assert baseline.track_states == []

    def test_captured_at_ms_is_epoch_millis(self):
        from mcp_server.experiment.baseline import capture_baseline

        ableton = MockAbleton()
        before = int(time.time() * 1000)
        baseline = capture_baseline(ableton)
        after = int(time.time() * 1000)
        assert before <= baseline.captured_at_ms <= after

    def test_missing_track_field_defaults_false(self):
        """Remote Script may omit mute/solo/arm for some track types."""
        from mcp_server.experiment.baseline import capture_baseline

        ableton = MockAbleton({
            "is_playing": False, "current_song_time": 0.0,
            "tracks": [{"index": 0}],  # no mute/solo/arm keys
        })
        baseline = capture_baseline(ableton)
        assert baseline.track_states[0] == {
            "index": 0, "mute": False, "solo": False, "arm": False,
        }


# ── restore_baseline ─────────────────────────────────────────────────────────


def _make_baseline(track_states=None, is_playing=True, song_time=2.0):
    from mcp_server.experiment.baseline import BaselineTransportState

    return BaselineTransportState(
        is_playing=is_playing,
        song_time=song_time,
        track_states=track_states if track_states is not None else [],
        captured_at_ms=1000,
    )


class TestRestoreBaseline:

    def test_stop_playback_is_first_command(self):
        from mcp_server.experiment.baseline import restore_baseline

        ableton = MockAbleton()
        baseline = _make_baseline()
        restore_baseline(ableton, baseline, stabilize_ms=0)
        assert ableton.calls[0][0] == "stop_playback"

    def test_restores_mute_for_each_track(self):
        from mcp_server.experiment.baseline import restore_baseline

        ableton = MockAbleton()
        baseline = _make_baseline([
            {"index": 0, "mute": True,  "solo": False, "arm": False},
            {"index": 1, "mute": False, "solo": False, "arm": False},
        ])
        restore_baseline(ableton, baseline, stabilize_ms=0)

        mute_calls = [c for c in ableton.calls if c[0] == "set_track_mute"]
        assert len(mute_calls) == 2
        assert mute_calls[0][1] == {"track_index": 0, "mute": True}
        assert mute_calls[1][1] == {"track_index": 1, "mute": False}

    def test_restores_solo_for_each_track(self):
        from mcp_server.experiment.baseline import restore_baseline

        ableton = MockAbleton()
        baseline = _make_baseline([
            {"index": 0, "mute": False, "solo": True,  "arm": False},
            {"index": 1, "mute": False, "solo": False, "arm": False},
        ])
        restore_baseline(ableton, baseline, stabilize_ms=0)

        solo_calls = [c for c in ableton.calls if c[0] == "set_track_solo"]
        assert len(solo_calls) == 2
        assert solo_calls[0][1] == {"track_index": 0, "solo": True}

    def test_restores_arm_for_each_track(self):
        from mcp_server.experiment.baseline import restore_baseline

        ableton = MockAbleton()
        baseline = _make_baseline([
            {"index": 0, "mute": False, "solo": False, "arm": True},
            {"index": 1, "mute": False, "solo": False, "arm": False},
        ])
        restore_baseline(ableton, baseline, stabilize_ms=0)

        arm_calls = [c for c in ableton.calls if c[0] == "set_track_arm"]
        assert len(arm_calls) == 2
        assert arm_calls[0][1] == {"track_index": 0, "arm": True}
        assert arm_calls[1][1] == {"track_index": 1, "arm": False}

    def test_stabilize_ms_zero_skips_sleep(self, monkeypatch):
        from mcp_server.experiment import baseline as baseline_mod

        slept: list[float] = []
        monkeypatch.setattr(baseline_mod.time, "sleep", lambda s: slept.append(s))

        ableton = MockAbleton()
        baseline_mod.restore_baseline(ableton, _make_baseline(), stabilize_ms=0)
        assert slept == []

    def test_stabilize_ms_positive_sleeps(self, monkeypatch):
        from mcp_server.experiment import baseline as baseline_mod

        slept: list[float] = []
        monkeypatch.setattr(baseline_mod.time, "sleep", lambda s: slept.append(s))

        ableton = MockAbleton()
        baseline_mod.restore_baseline(ableton, _make_baseline(), stabilize_ms=300)
        assert slept == [pytest.approx(0.3)]

    def test_send_command_error_on_one_track_does_not_abort_restore(self):
        """A single flaky track shouldn't prevent restoring the rest."""
        from mcp_server.experiment.baseline import restore_baseline

        class FlakyAbleton(MockAbleton):
            def send_command(self, tool, params=None):
                if tool == "set_track_mute" and (params or {}).get("track_index") == 0:
                    raise RuntimeError("flaky")
                return super().send_command(tool, params)

        ableton = FlakyAbleton()
        baseline = _make_baseline([
            {"index": 0, "mute": True,  "solo": False, "arm": False},
            {"index": 1, "mute": False, "solo": False, "arm": False},
        ])
        # Must not raise
        restore_baseline(ableton, baseline, stabilize_ms=0)

        # Track 1 mute should still have been attempted.
        mute_attempts = [c for c in ableton.calls if c[0] == "set_track_mute"]
        track_1_mute = [c for c in mute_attempts if c[1].get("track_index") == 1]
        assert len(track_1_mute) == 1

    def test_return_track_arm_skipped(self):
        """Return tracks (negative index convention or flagged) can't be armed.

        The remote command ``set_track_arm`` raises on negative indices. The
        restore path should not call set_track_arm for such tracks — we skip
        arm on any track recorded with ``arm=None`` or index < 0.
        """
        from mcp_server.experiment.baseline import restore_baseline

        ableton = MockAbleton()
        baseline = _make_baseline([
            {"index": -1, "mute": False, "solo": False, "arm": False},  # return
            {"index": 0,  "mute": False, "solo": False, "arm": True},
        ])
        restore_baseline(ableton, baseline, stabilize_ms=0)

        arm_calls = [c for c in ableton.calls if c[0] == "set_track_arm"]
        # Only the non-return track was armed
        assert len(arm_calls) == 1
        assert arm_calls[0][1]["track_index"] == 0


# ── ExperimentSet.baseline_transport field ──────────────────────────────────


class TestExperimentSetBaselineField:

    def test_new_experiment_set_has_none_baseline(self):
        from mcp_server.experiment.models import ExperimentSet

        exp = ExperimentSet(experiment_id="e1", request_text="t")
        assert exp.baseline_transport is None

    def test_baseline_survives_to_dict(self):
        from mcp_server.experiment.baseline import BaselineTransportState
        from mcp_server.experiment.models import ExperimentSet

        exp = ExperimentSet(experiment_id="e1", request_text="t")
        exp.baseline_transport = BaselineTransportState(
            is_playing=True, song_time=1.0,
            track_states=[{"index": 0, "mute": False, "solo": False, "arm": False}],
            captured_at_ms=123,
        )
        d = exp.to_dict()
        assert "baseline_transport" in d
        assert d["baseline_transport"]["is_playing"] is True
        assert d["baseline_transport"]["song_time"] == 1.0

    def test_no_baseline_not_in_to_dict(self):
        """When baseline_transport is None, it shouldn't bloat the dict."""
        from mcp_server.experiment.models import ExperimentSet

        exp = ExperimentSet(experiment_id="e1", request_text="t")
        d = exp.to_dict()
        assert "baseline_transport" not in d


# ── prepare_for_next_branch helper ──────────────────────────────────────────


class TestPrepareForNextBranch:
    """Engine-level helper called between branches in the experiment loop.

    Thin wrapper around restore_baseline that the MCP tool invokes. Kept as
    a separate engine function so the MCP tool body stays small and the
    wiring is testable without a FastMCP Context mock.
    """

    def test_no_op_when_baseline_is_none(self):
        from mcp_server.experiment.engine import prepare_for_next_branch

        ableton = MockAbleton()
        # Should not crash, and should not send any commands.
        prepare_for_next_branch(ableton, baseline=None, stabilize_ms=0)
        assert ableton.calls == []

    def test_delegates_to_restore_baseline(self):
        from mcp_server.experiment.engine import prepare_for_next_branch

        ableton = MockAbleton()
        baseline = _make_baseline([
            {"index": 0, "mute": True, "solo": False, "arm": False},
        ])
        prepare_for_next_branch(ableton, baseline=baseline, stabilize_ms=0)

        # Stop + 3 per-track restore commands (mute + solo + arm) = 4 total
        assert ableton.calls[0][0] == "stop_playback"
        tools = [c[0] for c in ableton.calls]
        assert "set_track_mute" in tools
        assert "set_track_solo" in tools
        assert "set_track_arm" in tools


# ── Tool-level wiring (integration) ─────────────────────────────────────────


class TestRunExperimentWiresBaseline:
    """Verify the MCP tool actually captures baseline on first run.

    The between-branches restore is covered by TestPrepareForNextBranch; we
    only need to verify the tool *calls* capture_baseline exactly once by
    checking the resulting experiment.baseline_transport state.
    """

    def test_run_experiment_captures_baseline_when_none(self):
        import asyncio
        from types import SimpleNamespace
        from mcp_server.experiment.tools import run_experiment
        from mcp_server.experiment import engine

        # Create experiment but force all branches to non-pending so the
        # per-branch run loop short-circuits — the baseline-capture lines
        # execute unconditionally once before the loop starts.
        exp = engine.create_experiment(
            request_text="baseline wiring test",
            move_ids=["make_punchier"],
        )
        for b in exp.branches:
            b.status = "evaluated"
        assert exp.baseline_transport is None  # pre-condition

        gsi_response = {
            "is_playing": True,
            "current_song_time": 1.5,
            "tracks": [
                {"index": 0, "mute": False, "solo": False, "arm": True},
                {"index": 1, "mute": True,  "solo": False, "arm": False},
            ],
        }
        ableton = MockAbleton(gsi_response)
        ctx = SimpleNamespace(lifespan_context={
            "ableton": ableton, "m4l": None, "mcp_dispatch": {},
        })

        asyncio.run(run_experiment(ctx, exp.experiment_id))

        # Baseline must be populated on the stored experiment
        assert exp.baseline_transport is not None
        assert exp.baseline_transport.is_playing is True
        assert exp.baseline_transport.song_time == pytest.approx(1.5)
        assert len(exp.baseline_transport.track_states) == 2
        assert exp.baseline_transport.track_states[1]["mute"] is True

    def test_compare_experiments_surfaces_baseline_transport(self):
        """v1.19.1 #1 — compare_experiments must expose baseline_transport so
        operators can verify the drift-fix is actually firing per experiment.

        Pre-v1.19.1 the field was populated internally on ExperimentSet but
        compare_experiments' return dict omitted it — no MCP-surface path to
        verify the baseline was captured.
        """
        import asyncio
        from types import SimpleNamespace
        from mcp_server.experiment.tools import compare_experiments
        from mcp_server.experiment import engine
        from mcp_server.experiment.baseline import BaselineTransportState

        exp = engine.create_experiment(
            request_text="baseline observability test",
            move_ids=["make_punchier"],
        )
        # Seed a distinctive baseline so we can assert it comes through
        exp.baseline_transport = BaselineTransportState(
            is_playing=True,
            song_time=42.0,
            track_states=[
                {"index": 0, "mute": False, "solo": False, "arm": True},
            ],
            captured_at_ms=1234567890,
        )

        ctx = SimpleNamespace(lifespan_context={"ableton": MockAbleton()})
        result = compare_experiments(ctx, exp.experiment_id)

        assert "baseline_transport" in result
        assert result["baseline_transport"] is not None
        assert result["baseline_transport"]["is_playing"] is True
        assert result["baseline_transport"]["song_time"] == pytest.approx(42.0)
        assert result["baseline_transport"]["track_states"][0]["arm"] is True
        assert result["baseline_transport"]["captured_at_ms"] == 1234567890

    def test_compare_experiments_baseline_none_when_not_captured(self):
        """When no baseline captured (e.g., experiment never run), field is None
        — not absent, not a crash."""
        import asyncio
        from types import SimpleNamespace
        from mcp_server.experiment.tools import compare_experiments
        from mcp_server.experiment import engine

        exp = engine.create_experiment(
            request_text="no-baseline test",
            move_ids=["make_punchier"],
        )
        # baseline_transport is None by default

        ctx = SimpleNamespace(lifespan_context={"ableton": MockAbleton()})
        result = compare_experiments(ctx, exp.experiment_id)

        # Must be present in the response with value None, so clients can
        # reliably check `result["baseline_transport"] is None` instead of
        # needing to check for key presence first.
        assert "baseline_transport" in result
        assert result["baseline_transport"] is None

    def test_run_experiment_preserves_existing_baseline(self):
        """Second run_experiment call shouldn't re-capture (baseline is idempotent)."""
        import asyncio
        from types import SimpleNamespace
        from mcp_server.experiment.tools import run_experiment
        from mcp_server.experiment import engine
        from mcp_server.experiment.baseline import BaselineTransportState

        exp = engine.create_experiment(
            request_text="idempotent baseline",
            move_ids=["make_punchier"],
        )
        for b in exp.branches:
            b.status = "evaluated"

        # Seed a pre-existing baseline with a distinctive song_time
        exp.baseline_transport = BaselineTransportState(
            is_playing=False, song_time=99.99, track_states=[], captured_at_ms=1,
        )

        ableton = MockAbleton({
            "is_playing": True, "current_song_time": 0.0, "tracks": [],
        })
        ctx = SimpleNamespace(lifespan_context={
            "ableton": ableton, "m4l": None, "mcp_dispatch": {},
        })

        asyncio.run(run_experiment(ctx, exp.experiment_id))

        # Seeded baseline preserved, not overwritten
        assert exp.baseline_transport.song_time == pytest.approx(99.99)

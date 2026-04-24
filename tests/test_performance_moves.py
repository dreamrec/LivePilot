"""Tests for the configure_record_readiness move (v1.21 commit 3).

One new performance-family move that closes the tech_debt entry from
v1.20 live test 6 (raw set_track_arm without a semantic-move wrapper).

**Plan corrections applied here** (see plan §3.1 vs Remote Script
handler reality):
    1. ``set_track_arm`` handler reads ``params["arm"]``, not ``params["armed"]``.
       MCP tool (mcp_server/tools/tracks.py:312) accepts Python kwarg ``armed``
       but renames to wire-format ``arm`` before send_command. Plan §3.1's
       compiler step was `{"track_index": ..., "armed": ...}` — that would
       drift past the parity gate (remote_command backend bypasses the rename
       layer). Corrected to emit `{"track_index": ..., "arm": ...}`.
    2. ``set_exclusive_arm`` handler is a GLOBAL MODE TOGGLE accepting
       ``{"enabled": bool}``, NOT a per-track arm tool. Plan §3.1 assumed
       `set_exclusive_arm(track_index=...)` — that handler signature does
       not exist. Corrected compiler emits a 2-step plan for exclusive
       arming: ``set_exclusive_arm(enabled=True)`` + ``set_track_arm(
       track_index, arm=True)`` — Ableton's exclusive_arm mode auto-disarms
       other regular tracks when one gets armed.
    3. ``set_track_arm`` handler rejects negative track indices
       (`ValueError: "Cannot arm a return track"` at tracks.py:261). Plan
       §3.1's test ``test_compiler_accepts_negative_track_index_for_returns``
       would compile a plan that fails at runtime. Corrected to pin the
       compile-time rejection instead.

Plan references:
  - docs/plans/v1.21-structural-plan.md §3.1, §4.4 (wire-format discipline)
  - docs/plans/v1.21-implementation-plan.md Task 3.1 + 3.2
  - docs/plans/v1.21-impl-status.md (plan-vs-reality correction log)
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401 — triggers registrations
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


class TestConfigureRecordReadinessMove:
    def test_move_registered_in_performance_family(self):
        move = get_move("configure_record_readiness")
        assert move is not None, "configure_record_readiness not registered"
        assert move.family == "performance"

    def test_protects_signal_integrity_dimension(self):
        move = get_move("configure_record_readiness")
        assert "signal_integrity" in move.protect, (
            f"expected signal_integrity in protect, got {sorted(move.protect.keys())}"
        )
        assert move.protect["signal_integrity"] >= 0.5

    def test_risk_level_is_low(self):
        move = get_move("configure_record_readiness")
        assert move.risk_level == "low", (
            f"arming/disarming is reversible via undo — risk should be low, "
            f"got {move.risk_level!r}"
        )

    def test_required_capability_session_declared(self):
        """Performance moves require session-mode (post-v1.20 convention)."""
        move = get_move("configure_record_readiness")
        assert "session" in move.required_capabilities

    def test_compiler_emits_set_track_arm_in_non_exclusive_mode(self):
        """Non-exclusive: single set_track_arm step. Params MUST use the
        wire-format key `arm` (not `armed`) because the remote_command
        backend bypasses the MCP tool's rename layer (see tools/tracks.py:317)."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": 2, "armed": True, "exclusive": False},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable, f"plan should be executable; warnings={plan.warnings}"
        arm_steps = [s for s in plan.steps if s.tool == "set_track_arm"]
        assert len(arm_steps) == 1
        # Wire-format key is `arm`, not `armed`.
        assert arm_steps[0].params == {"track_index": 2, "arm": True}

    def test_compiler_emits_disarm_others_plus_arm_target_when_exclusive(self):
        """exclusive=True + armed=True → N+1 steps emulating Ableton's
        exclusive-arm mode manually:
            * set_track_arm(other_idx, arm=False) for every regular track
              ≠ target
            * set_track_arm(target, arm=True) for the target

        Live 12.4 live-test pre-flight (2026-04-24) surfaced that
        ``song.exclusive_arm`` has no Python setter in current LOM —
        ``set_exclusive_arm`` errors with "property of 'Song' object has
        no setter". The compiler emulates the mode manually rather than
        relying on the broken toggle. See
        remote_script/LivePilot/transport.py:180 for the (pre-existing,
        tracked) broken handler."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": 2, "armed": True, "exclusive": True},
            "session_info": {
                "tracks": [
                    {"index": 0, "name": "Kick", "type": "midi"},
                    {"index": 1, "name": "Bass", "type": "midi"},
                    {"index": 2, "name": "Lead", "type": "audio"},  # target
                    {"index": 3, "name": "Pad", "type": "midi"},
                ],
            },
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable, f"plan should be executable; warnings={plan.warnings}"
        # Every step is set_track_arm — no set_exclusive_arm (broken in 12.4).
        tools = [s.tool for s in plan.steps]
        assert all(t == "set_track_arm" for t in tools), (
            f"exclusive mode emulation should only emit set_track_arm steps; "
            f"got tools={tools}"
        )
        # 3 disarm steps (tracks 0, 1, 3) + 1 arm step (track 2) = 4 steps
        assert len(plan.steps) == 4
        # Exactly one arm=True step (the target)
        arm_true = [s for s in plan.steps if s.params.get("arm") is True]
        assert len(arm_true) == 1
        assert arm_true[0].params["track_index"] == 2
        # The rest disarm the other regular tracks
        arm_false = [s for s in plan.steps if s.params.get("arm") is False]
        assert len(arm_false) == 3
        disarmed_indices = sorted(s.params["track_index"] for s in arm_false)
        assert disarmed_indices == [0, 1, 3]

    def test_compiler_exclusive_skips_return_and_master_tracks(self):
        """Exclusive mode must not try to disarm return/master tracks —
        Ableton's set_track_arm rejects negative indices (tracks.py:261)."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": 1, "armed": True, "exclusive": True},
            "session_info": {
                "tracks": [
                    {"index": 0, "name": "Regular", "type": "midi"},
                    {"index": 1, "name": "Target", "type": "audio"},
                    {"index": -1, "name": "A-Reverb", "type": "return"},
                    {"index": -2, "name": "B-Delay", "type": "return"},
                ],
            },
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable
        # Should emit 2 steps: disarm track 0, arm track 1. Returns skipped.
        assert len(plan.steps) == 2
        indices_emitted = {s.params["track_index"] for s in plan.steps}
        assert indices_emitted == {0, 1}, (
            f"return/master tracks must be skipped; got {indices_emitted}"
        )

    def test_compiler_exclusive_without_session_info_rejects(self):
        """The manual-disarm strategy needs session_info.tracks. Without
        it, the compiler rejects with an actionable warning."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": 2, "armed": True, "exclusive": True},
            "session_info": {},  # no tracks
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable
        joined = " ".join(plan.warnings).lower()
        assert "session_info" in joined, (
            f"warning should point at the session_info requirement; "
            f"got: {plan.warnings}"
        )

    def test_compiler_rejects_exclusive_true_with_armed_false(self):
        """`exclusive=True + armed=False` is a contradiction — the point
        of exclusive is to become the SINGLE ARMED track, so disarming
        under exclusive makes no sense. Reject at compile time."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": 2, "armed": False, "exclusive": True},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable, (
            "exclusive=True + armed=False must be rejected — contradictory contract"
        )
        joined = " ".join(plan.warnings).lower()
        assert "exclusive" in joined, f"warning should mention exclusive; got: {plan.warnings}"

    def test_compiler_rejects_missing_armed_seed_arg(self):
        """seed_args.armed is required — reject with a clear warning."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": 2},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_negative_track_index(self):
        """Return tracks cannot be armed — the Remote Script handler
        (tracks.py:261) raises `ValueError: Cannot arm a return track`
        on negative indices. Reject at compile time for a clean warning
        path instead of a runtime error."""
        move = get_move("configure_record_readiness")
        kernel = {
            "seed_args": {"track_index": -1, "armed": True, "exclusive": False},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable, (
            "negative track_index (return track) must be rejected — "
            "Ableton's handler won't arm return tracks"
        )
        joined = " ".join(plan.warnings).lower()
        assert "return" in joined or "negative" in joined, (
            f"warning should explain return-track constraint; got: {plan.warnings}"
        )

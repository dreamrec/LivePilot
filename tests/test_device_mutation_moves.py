"""Device-mutation family semantic-moves tests (v1.20 commit 2).

Two new moves:
    configure_device   — sound_design family, sets N parameters via batch_set_parameters
    remove_device      — sound_design family, deletes a device + logs a reason

Both take user input via ``kernel["seed_args"]``. configure_device uses
explicit ``param_overrides: dict`` (not a preset library — the plan's
preset-YAML infrastructure is deferred to v1.21 so this commit can ship
at-budget; see docs/plans/v1.20-structural-plan.md §3.2 note).
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


# ── configure_device ──────────────────────────────────────────────────────────


class TestConfigureDeviceMove:
    def test_move_registered(self):
        move = get_move("configure_device")
        assert move is not None
        assert move.family == "sound_design"

    def test_risk_level_acknowledges_bounded_param_changes(self):
        """Parameter changes are bounded (batch_set_parameters validates),
        so risk is low — but lower than sound design moves that swap devices."""
        move = get_move("configure_device")
        assert move.risk_level in ("low", "medium")

    def test_compiler_emits_single_batch_set_parameters(self):
        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 1,
                "param_overrides": {"Decay Time": 4000.0, "Dry/Wet": 0.35},
            },
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        batch_steps = [s for s in plan.steps if s.tool == "batch_set_parameters"]
        assert len(batch_steps) == 1
        params = batch_steps[0].params
        assert params["track_index"] == 0
        assert params["device_index"] == 1

    def test_compiler_translates_param_overrides_to_batch_format(self):
        """batch_set_parameters expects a list of {parameter_name, value} dicts.
        The compiler must normalize the ergonomic ``param_overrides`` dict
        into that shape."""
        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "param_overrides": {"Freq": 440.0, "Q": 0.7},
            },
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        batch = [s for s in plan.steps if s.tool == "batch_set_parameters"][0]
        parameters = batch.params["parameters"]
        by_name = {p["parameter_name"]: p["value"] for p in parameters}
        assert by_name == {"Freq": 440.0, "Q": 0.7}

    def test_compiler_rejects_empty_param_overrides(self):
        move = get_move("configure_device")
        kernel = {
            "seed_args": {"track_index": 0, "device_index": 0, "param_overrides": {}},
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_missing_required_seed_args(self):
        move = get_move("configure_device")
        kernel = {
            "seed_args": {"track_index": 0},  # missing device_index + param_overrides
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_accepts_return_track_negative_index(self):
        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": -1,
                "device_index": 0,
                "param_overrides": {"Decay Time": 4000.0},
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        # -1 = Return A per mcp_server/tools/devices.py:367
        assert plan.executable
        batch = [s for s in plan.steps if s.tool == "batch_set_parameters"][0]
        assert batch.params["track_index"] == -1

    def test_compiler_rejects_non_dict_param_overrides(self):
        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "param_overrides": [("Freq", 440.0)],  # not a dict
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── remove_device ──────────────────────────────────────────────────────────────


class TestRemoveDeviceMove:
    def test_move_registered(self):
        move = get_move("remove_device")
        assert move is not None
        assert move.family == "sound_design"

    def test_protects_signal_integrity(self):
        """Removing a device on a live signal path breaks audio — must
        declare signal_integrity as protected."""
        move = get_move("remove_device")
        assert "signal_integrity" in move.protect
        assert move.protect["signal_integrity"] >= 0.8

    def test_risk_level_is_medium(self):
        """Destructive but undoable via Live's undo stack."""
        move = get_move("remove_device")
        assert move.risk_level in ("medium", "high")

    def test_compiler_emits_delete_device_step(self):
        move = get_move("remove_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 2,
                "reason": "clearing stale reverb before reconfig",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        delete_steps = [s for s in plan.steps if s.tool == "delete_device"]
        assert len(delete_steps) == 1
        assert delete_steps[0].params == {"track_index": 0, "device_index": 2}

    def test_compiler_logs_reason_to_session_memory(self):
        """Reason string must be captured via add_session_memory so the
        ledger has audit trail alongside the move_executed marker."""
        move = get_move("remove_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 2,
                "reason": "device added by mistake in prior turn",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        memory_steps = [s for s in plan.steps if s.tool == "add_session_memory"]
        assert len(memory_steps) == 1
        content = memory_steps[0].params.get("content", "")
        assert "device added by mistake in prior turn" in content

    def test_compiler_rejects_missing_reason(self):
        """remove_device requires a reason — destructive ops must be
        justified, not silent."""
        move = get_move("remove_device")
        kernel = {
            "seed_args": {"track_index": 0, "device_index": 2},  # no reason
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_empty_reason(self):
        move = get_move("remove_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 2,
                "reason": "   ",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── Cross-family checks ───────────────────────────────────────────────────────


def test_device_mutation_family_compilers_registered():
    """configure_device + remove_device must each have a compiler; no
    fallback warnings."""
    for move_id in ("configure_device", "remove_device"):
        move = get_move(move_id)
        kernel = {"seed_args": {}, "session_info": {}, "mode": "improve"}
        plan = move_compiler.compile(move, kernel)
        fallback = [w for w in plan.warnings if "No compiler" in w]
        assert not fallback, f"{move_id}: missing compiler"

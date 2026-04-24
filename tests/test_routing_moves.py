"""Routing family semantic-moves tests (v1.20 commit 1).

Three new moves:
    build_send_chain              — device_creation family
    configure_send_architecture   — mix family
    set_track_routing             — mix family

All three read user input from ``kernel["seed_args"]`` and emit concrete
tool-call steps the execution router can dispatch without further
resolution.
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401 — triggers all registrations
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


# ── build_send_chain ──────────────────────────────────────────────────────────


class TestBuildSendChainMove:
    def test_move_registered(self):
        move = get_move("build_send_chain")
        assert move is not None
        assert move.family == "device_creation"

    def test_targets_sum_within_unit(self):
        move = get_move("build_send_chain")
        assert sum(move.targets.values()) <= 1.0 + 1e-6

    def test_intent_mentions_send_chain(self):
        move = get_move("build_send_chain")
        intent = move.intent.lower()
        assert "return" in intent or "send" in intent or "chain" in intent

    def test_compiler_emits_one_step_per_device(self):
        move = get_move("build_send_chain")
        kernel = {
            "session_info": {"tracks": [], "return_tracks": [{"name": "A-Reverb"}]},
            "seed_args": {
                "return_track_index": 0,
                "device_chain": ["Echo", "Auto Filter", "Convolution Reverb"],
            },
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        load_steps = [s for s in plan.steps if s.tool == "find_and_load_device"]
        assert len(load_steps) == 3

    def test_compiler_targets_return_track_via_negative_index(self):
        move = get_move("build_send_chain")
        kernel = {
            "seed_args": {"return_track_index": 0, "device_chain": ["Echo"]},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        load_steps = [s for s in plan.steps if s.tool == "find_and_load_device"]
        # Return A → track_index = -(0+1) = -1 per mixing.py:227 convention
        assert load_steps[0].params["track_index"] == -1

    def test_compiler_return_b_maps_to_minus_two(self):
        move = get_move("build_send_chain")
        kernel = {
            "seed_args": {"return_track_index": 1, "device_chain": ["Delay"]},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        load_steps = [s for s in plan.steps if s.tool == "find_and_load_device"]
        assert load_steps[0].params["track_index"] == -2

    def test_compiler_allows_duplicate_devices(self):
        """Return chains may legitimately hold two of the same device (e.g.,
        Echo feedback-stacked). Compiler must request allow_duplicate=True."""
        move = get_move("build_send_chain")
        kernel = {
            "seed_args": {"return_track_index": 0, "device_chain": ["Echo", "Echo"]},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        load_steps = [s for s in plan.steps if s.tool == "find_and_load_device"]
        assert len(load_steps) == 2
        assert all(s.params.get("allow_duplicate") is True for s in load_steps)

    def test_compiler_warns_when_device_chain_empty(self):
        move = get_move("build_send_chain")
        kernel = {
            "seed_args": {"return_track_index": 0, "device_chain": []},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable or any("empty" in w.lower() or "no device" in w.lower() for w in plan.warnings)

    def test_compiler_warns_when_seed_args_missing(self):
        move = get_move("build_send_chain")
        kernel = {"seed_args": {}, "session_info": {}, "mode": "improve"}
        plan = move_compiler.compile(move, kernel)
        assert plan.warnings, "compiler must warn on missing seed_args"

    def test_compiler_rejects_negative_return_index(self):
        move = get_move("build_send_chain")
        kernel = {
            "seed_args": {"return_track_index": -1, "device_chain": ["Echo"]},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        # Negative return_track_index is user error; plan should not be executable
        assert not plan.executable


# ── configure_send_architecture ───────────────────────────────────────────────


class TestConfigureSendArchitectureMove:
    def test_move_registered(self):
        move = get_move("configure_send_architecture")
        assert move is not None
        assert move.family == "mix"

    def test_compiler_emits_one_set_track_send_per_track(self):
        move = get_move("configure_send_architecture")
        kernel = {
            "seed_args": {
                "source_track_indices": [0, 1, 2],
                "send_index": 0,
                "levels": [0.4, 0.25, 0.1],
            },
            "session_info": {"tracks": [{"index": 0}, {"index": 1}, {"index": 2}]},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        send_steps = [s for s in plan.steps if s.tool == "set_track_send"]
        assert len(send_steps) == 3

    def test_compiler_pairs_tracks_with_levels(self):
        move = get_move("configure_send_architecture")
        kernel = {
            "seed_args": {
                "source_track_indices": [0, 1],
                "send_index": 1,
                "levels": [0.3, 0.7],
            },
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        send_steps = [s for s in plan.steps if s.tool == "set_track_send"]
        # Step order must preserve the user's track/level pairing
        assert send_steps[0].params == {"track_index": 0, "send_index": 1, "value": 0.3}
        assert send_steps[1].params == {"track_index": 1, "send_index": 1, "value": 0.7}

    def test_compiler_rejects_mismatched_track_and_level_counts(self):
        move = get_move("configure_send_architecture")
        kernel = {
            "seed_args": {
                "source_track_indices": [0, 1, 2],
                "send_index": 0,
                "levels": [0.4],  # length mismatch
            },
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_clamps_levels_to_unit_range(self):
        """User may pass e.g. 1.5 by mistake — compiler must clamp, not explode
        (set_track_send validates 0..1 and would raise)."""
        move = get_move("configure_send_architecture")
        kernel = {
            "seed_args": {
                "source_track_indices": [0],
                "send_index": 0,
                "levels": [1.5],
            },
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        send_steps = [s for s in plan.steps if s.tool == "set_track_send"]
        # Either clamps silently, or emits a warning and refuses to execute
        if plan.executable:
            assert 0.0 <= send_steps[0].params["value"] <= 1.0
        else:
            assert plan.warnings


# ── set_track_routing ─────────────────────────────────────────────────────────


class TestSetTrackRoutingMove:
    def test_move_registered(self):
        move = get_move("set_track_routing")
        assert move is not None
        assert move.family == "mix"

    def test_compiler_emits_single_routing_step_in_wire_format(self):
        """BUG-2026-04-24 (same family as the batch_set_parameters bug):
        the MCP tool set_track_routing renames
        output_routing_type → output_type before ableton.send_command.
        Compiled steps must emit the wire-format keys directly because
        the remote_command backend bypasses the MCP tool layer.
        Authoritative names: remote_script/LivePilot/mixing.py:227."""
        move = get_move("set_track_routing")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "output_routing_type": "Sends Only",
                "output_routing_channel": "Post Mixer",
            },
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        routing_steps = [s for s in plan.steps if s.tool == "set_track_routing"]
        assert len(routing_steps) == 1
        params = routing_steps[0].params
        assert params["track_index"] == 0
        # Wire-format keys (what Ableton reads):
        assert params["output_type"] == "Sends Only"
        assert params["output_channel"] == "Post Mixer"
        # Ergonomic keys MUST NOT leak through:
        assert "output_routing_type" not in params, (
            "compiled step leaked ergonomic key output_routing_type — "
            "Ableton would silently ignore it"
        )
        assert "output_routing_channel" not in params

    def test_compiler_requires_output_fields(self):
        move = get_move("set_track_routing")
        kernel = {
            "seed_args": {"track_index": 0},  # no routing fields
            "session_info": {"tracks": []},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_routing_move_protects_clarity(self):
        """A bad routing change can silence a track; protect clarity."""
        move = get_move("set_track_routing")
        assert "clarity" in move.protect


# ── Cross-family checks ───────────────────────────────────────────────────────


def test_routing_family_move_ids_unique_across_registry():
    from mcp_server.semantic_moves.registry import _REGISTRY
    routing_ids = {"build_send_chain", "configure_send_architecture", "set_track_routing"}
    assert routing_ids.issubset(_REGISTRY.keys())


def test_routing_moves_all_have_compiler_registered():
    """Each routing move must have a compiler — otherwise compile() falls back
    to the non-executable warning path, which v1.20 live pressure tests refuse."""
    for move_id in ("build_send_chain", "configure_send_architecture", "set_track_routing"):
        move = get_move(move_id)
        kernel = {"seed_args": {}, "session_info": {}, "mode": "improve"}
        plan = move_compiler.compile(move, kernel)
        # Missing compiler signature is the literal "No compiler for <id> —
        # manual execution required" warning. Reject.
        warnings = [w for w in plan.warnings if "No compiler" in w]
        assert not warnings, f"{move_id}: {warnings}"

"""Metadata-family semantic-moves tests (v1.20 commit 4).

Three new moves:
    configure_groove       — arrangement, assign groove + tune timing
    set_scene_metadata     — arrangement, cosmetic scene fields
    set_track_metadata     — mix, cosmetic track fields (bundled rename + color)

The metadata family takes conditional seed_args: name/color/tempo are
each optional, and the compiler emits one step per provided field. This
is the ergonomic collapse of two raw-tool patterns (rename+color) into
a single named intent.
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


# ── configure_groove ──────────────────────────────────────────────────────────


class TestConfigureGrooveMove:
    def test_move_registered(self):
        move = get_move("configure_groove")
        assert move is not None
        assert move.family == "arrangement"

    def test_targets_favor_groove_dimension(self):
        move = get_move("configure_groove")
        assert "groove" in move.targets
        assert move.targets["groove"] >= 0.4

    def test_compiler_assigns_groove_to_each_clip(self):
        move = get_move("configure_groove")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_indices": [0, 1, 2],
                "groove_id": 4,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assign_steps = [s for s in plan.steps if s.tool == "assign_clip_groove"]
        assert len(assign_steps) == 3
        for i, step in enumerate(assign_steps):
            assert step.params["track_index"] == 0
            assert step.params["clip_index"] == i
            assert step.params["groove_id"] == 4

    def test_compiler_emits_set_groove_params_when_timing_amount_given(self):
        move = get_move("configure_groove")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_indices": [0],
                "groove_id": 4,
                "timing_amount": 0.7,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        param_steps = [s for s in plan.steps if s.tool == "set_groove_params"]
        assert len(param_steps) == 1
        assert param_steps[0].params["groove_id"] == 4
        assert param_steps[0].params["timing_amount"] == 0.7

    def test_compiler_skips_set_groove_params_when_no_timing_amount(self):
        move = get_move("configure_groove")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_indices": [0],
                "groove_id": 4,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert all(s.tool != "set_groove_params" for s in plan.steps)

    def test_compiler_clamps_timing_amount_to_unit_range(self):
        """timing_amount >1.0 would raise ValueError in set_groove_params;
        compiler clamps + warns rather than emit a guaranteed-to-fail step."""
        move = get_move("configure_groove")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_indices": [0],
                "groove_id": 4,
                "timing_amount": 1.5,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        param_steps = [s for s in plan.steps if s.tool == "set_groove_params"]
        if plan.executable:
            assert 0.0 <= param_steps[0].params["timing_amount"] <= 1.0
        else:
            assert plan.warnings

    def test_compiler_rejects_empty_clip_indices(self):
        move = get_move("configure_groove")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_indices": [],
                "groove_id": 4,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── set_scene_metadata ────────────────────────────────────────────────────────


class TestSetSceneMetadataMove:
    def test_move_registered(self):
        move = get_move("set_scene_metadata")
        assert move is not None
        assert move.family == "arrangement"

    def test_has_no_targets_since_metadata_only(self):
        """Pure metadata — no dimension claim."""
        move = get_move("set_scene_metadata")
        assert move.targets == {}

    def test_compiler_only_emits_step_for_provided_fields(self):
        move = get_move("set_scene_metadata")
        kernel = {
            "seed_args": {"scene_index": 0, "name": "Breakdown"},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        tools_used = [s.tool for s in plan.steps]
        assert tools_used == ["set_scene_name"]

    def test_compiler_emits_three_steps_when_all_fields_provided(self):
        move = get_move("set_scene_metadata")
        kernel = {
            "seed_args": {
                "scene_index": 2,
                "name": "Drop",
                "color_index": 5,
                "tempo": 128.0,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        tools_used = [s.tool for s in plan.steps]
        assert set(tools_used) == {"set_scene_name", "set_scene_color", "set_scene_tempo"}
        for step in plan.steps:
            assert step.params["scene_index"] == 2

    def test_compiler_rejects_no_fields_provided(self):
        """Empty metadata call is a no-op; reject so caller knows intent was dropped."""
        move = get_move("set_scene_metadata")
        kernel = {
            "seed_args": {"scene_index": 0},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_missing_scene_index(self):
        move = get_move("set_scene_metadata")
        kernel = {
            "seed_args": {"name": "Drop"},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── set_track_metadata (bundled rename + color) ───────────────────────────────


class TestSetTrackMetadataMove:
    def test_move_registered(self):
        move = get_move("set_track_metadata")
        assert move is not None
        assert move.family == "mix"

    def test_compiler_emits_name_only_when_only_name_given(self):
        move = get_move("set_track_metadata")
        kernel = {
            "seed_args": {"track_index": 0, "name": "Bass"},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        tools_used = [s.tool for s in plan.steps]
        assert tools_used == ["set_track_name"]
        assert plan.steps[0].params == {"track_index": 0, "name": "Bass"}

    def test_compiler_emits_both_when_both_provided(self):
        move = get_move("set_track_metadata")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "name": "Bass",
                "color_index": 7,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        tools_used = [s.tool for s in plan.steps]
        assert set(tools_used) == {"set_track_name", "set_track_color"}

    def test_compiler_supports_return_track_negative_index(self):
        move = get_move("set_track_metadata")
        kernel = {
            "seed_args": {"track_index": -1, "name": "A-Dub Reverb"},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable
        name_step = [s for s in plan.steps if s.tool == "set_track_name"][0]
        assert name_step.params["track_index"] == -1

    def test_compiler_rejects_no_fields(self):
        move = get_move("set_track_metadata")
        kernel = {
            "seed_args": {"track_index": 0},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── Cross-family ──────────────────────────────────────────────────────────────


def test_metadata_family_compilers_registered():
    for move_id in ("configure_groove", "set_scene_metadata", "set_track_metadata"):
        move = get_move(move_id)
        kernel = {"seed_args": {}, "session_info": {}, "mode": "improve"}
        plan = move_compiler.compile(move, kernel)
        fallback = [w for w in plan.warnings if "No compiler" in w]
        assert not fallback, f"{move_id}: {fallback}"


def test_total_move_count_hits_v1_20_target():
    """All v1.20 moves registered. The plan's §1 says 9, but its §3 + §2
    decision table enumerate 10 (3 routing + 2 device-mutation + 2 content +
    3 metadata). The enumerated contracts are authoritative."""
    from mcp_server.semantic_moves import registry
    assert registry.count() == 43, (
        f"expected 43 moves post-v1.20 (33 baseline + 10); got {registry.count()}"
    )


def test_v1_20_moves_all_registered_by_id():
    """Spot-check each expected move_id exists in the registry — catches
    silent rename drift between plan and implementation."""
    from mcp_server.semantic_moves.registry import _REGISTRY
    v1_20_move_ids = {
        # routing
        "build_send_chain", "configure_send_architecture", "set_track_routing",
        # device-mutation
        "configure_device", "remove_device",
        # content
        "load_chord_source", "create_drum_rack_pad",
        # metadata
        "configure_groove", "set_scene_metadata", "set_track_metadata",
    }
    missing = v1_20_move_ids - set(_REGISTRY.keys())
    assert not missing, f"missing v1.20 moves: {sorted(missing)}"

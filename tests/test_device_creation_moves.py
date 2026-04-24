"""Tests for device_creation semantic moves."""

from __future__ import annotations

import pytest

from mcp_server.semantic_moves.registry import list_moves, get_move


class TestDeviceCreationMovesRegistered:
    def test_at_least_6_device_creation_moves(self):
        moves = list_moves(domain="device_creation")
        assert len(moves) >= 6

    def test_chaos_modulator_exists(self):
        move = get_move("create_chaos_modulator")
        assert move is not None
        assert move.family == "device_creation"

    def test_feedback_resonator_exists(self):
        move = get_move("create_feedback_resonator")
        assert move is not None

    def test_wavefolder_exists(self):
        move = get_move("create_wavefolder_effect")
        assert move is not None

    def test_bitcrusher_exists(self):
        move = get_move("create_bitcrusher_effect")
        assert move is not None

    def test_karplus_string_exists(self):
        move = get_move("create_karplus_string")
        assert move is not None

    def test_stochastic_texture_exists(self):
        move = get_move("create_stochastic_texture")
        assert move is not None

    def test_fdn_reverb_exists(self):
        move = get_move("create_fdn_reverb")
        assert move is not None

    def test_all_have_plan_templates(self):
        moves = list_moves(domain="device_creation")
        for m in moves:
            full = get_move(m["move_id"])
            assert full.plan_template, f"{m['move_id']} has no plan_template"

    def test_m4l_forge_moves_also_load_the_generated_device(self):
        """Any move that calls generate_m4l_effect must also immediately
        load the result — otherwise the agent generates code that nothing
        picks up. This invariant is anchored on the TOOL, not the move_id
        prefix, so post-v1.20 device-loader moves (build_send_chain,
        create_drum_rack_pad) are naturally out-of-scope."""
        moves = list_moves(domain="device_creation")
        forge_moves = [
            get_move(m["move_id"]) for m in moves
            if any(s.get("tool") == "generate_m4l_effect" for s in get_move(m["move_id"]).plan_template)
        ]
        assert forge_moves, "expected at least one Device Forge move in the family"
        for full in forge_moves:
            tools_used = [s.get("tool") for s in full.plan_template]
            assert "find_and_load_device" in tools_used, (
                f"{full.move_id} uses generate_m4l_effect but never loads the "
                "generated device — orphaned M4L code."
            )

    def test_every_device_creation_move_loads_or_generates_a_device(self):
        """Family-level invariant: a device_creation move must do at least
        ONE of {generate_m4l_effect, find_and_load_device, add_drum_rack_pad,
        load_browser_item} — otherwise it doesn't create any device and is
        misfiled."""
        loader_tools = {
            "generate_m4l_effect",
            "find_and_load_device",
            "add_drum_rack_pad",
            "load_browser_item",
        }
        for m in list_moves(domain="device_creation"):
            full = get_move(m["move_id"])
            tools_used = {s.get("tool") for s in full.plan_template}
            assert tools_used & loader_tools, (
                f"{m['move_id']} has no device-creating tool in plan_template; "
                f"expected at least one of {sorted(loader_tools)}"
            )

    def test_all_have_verification_plans(self):
        moves = list_moves(domain="device_creation")
        for m in moves:
            full = get_move(m["move_id"])
            assert full.verification_plan, f"{m['move_id']} has no verification_plan"

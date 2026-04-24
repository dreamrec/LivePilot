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

    def test_device_forge_moves_use_generate_m4l_effect(self):
        """Device-Forge-generated M4L moves (the pre-v1.20 subset, all named
        ``create_*``) must invoke generate_m4l_effect. Post-v1.20 the
        device_creation family also holds device-*loading* moves (e.g.,
        build_send_chain), which load existing devices via find_and_load_device
        — those are intentionally exempt from this invariant."""
        moves = list_moves(domain="device_creation")
        forge_moves = [m for m in moves if m["move_id"].startswith("create_")]
        assert forge_moves, "expected at least one Device Forge move in the family"
        for m in forge_moves:
            full = get_move(m["move_id"])
            tools_used = [s.get("tool") for s in full.plan_template]
            assert "generate_m4l_effect" in tools_used, (
                f"{m['move_id']} is a create_* move but doesn't use generate_m4l_effect"
            )

    def test_all_have_verification_plans(self):
        moves = list_moves(domain="device_creation")
        for m in moves:
            full = get_move(m["move_id"])
            assert full.verification_plan, f"{m['move_id']} has no verification_plan"

"""Tests for sample-domain semantic moves."""

from __future__ import annotations

from mcp_server.semantic_moves.registry import list_moves, get_move


class TestSampleMoves:
    def test_sample_moves_registered(self):
        sample_moves = list_moves(domain="sample")
        assert len(sample_moves) >= 6

    def test_chop_rhythm_exists(self):
        m = get_move("sample_chop_rhythm")
        assert m is not None
        assert m.family == "sample"
        assert len(m.plan_template) > 0

    def test_texture_layer_exists(self):
        m = get_move("sample_texture_layer")
        assert m is not None

    def test_vocal_ghost_exists(self):
        m = get_move("sample_vocal_ghost")
        assert m is not None

    def test_break_layer_exists(self):
        m = get_move("sample_break_layer")
        assert m is not None

    def test_resample_destroy_exists(self):
        m = get_move("sample_resample_destroy")
        assert m is not None

    def test_one_shot_accent_exists(self):
        m = get_move("sample_one_shot_accent")
        assert m is not None

    def test_all_sample_moves_have_plan_templates(self):
        sample_moves = list_moves(domain="sample")
        for move_dict in sample_moves:
            full = get_move(move_dict["move_id"])
            assert full is not None
            assert full.plan_template, f"{move_dict['move_id']} has no plan_template"

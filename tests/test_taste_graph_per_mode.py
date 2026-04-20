"""Tests for per-goal-mode novelty bands and taste-bypass flag (PR8).

Covers the new novelty_bands dict, bypass_taste_in_generation flag,
and migration between the legacy flat novelty_band and the per-mode dict.
Existing taste_graph tests already cover the base ranking behavior.
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.memory.taste_graph import TasteGraph, build_taste_graph, MoveFamilyScore
from mcp_server.persistence.taste_store import PersistentTasteStore


# ── Default bands ───────────────────────────────────────────────────────


class TestDefaultBands:

    def test_both_keys_present(self):
        g = TasteGraph()
        assert "improve" in g.novelty_bands
        assert "explore" in g.novelty_bands

    def test_defaults_match_legacy_band(self):
        g = TasteGraph()
        assert g.novelty_bands["improve"] == 0.5
        assert g.novelty_bands["explore"] == 0.5
        assert g.novelty_band == 0.5

    def test_default_instances_are_independent(self):
        # Mutable-default regression guard.
        a = TasteGraph()
        b = TasteGraph()
        a.novelty_bands["improve"] = 0.9
        assert b.novelty_bands["improve"] == 0.5


# ── update_novelty_from_experiment ──────────────────────────────────────


class TestUpdateNovelty:

    def test_defaults_to_improve_mode(self):
        g = TasteGraph()
        g.update_novelty_from_experiment(chose_bold=True)
        assert g.novelty_bands["improve"] > 0.5
        # explore untouched
        assert g.novelty_bands["explore"] == 0.5

    def test_explicit_explore_mode(self):
        g = TasteGraph()
        g.update_novelty_from_experiment(chose_bold=True, goal_mode="explore")
        assert g.novelty_bands["explore"] > 0.5
        assert g.novelty_bands["improve"] == 0.5

    def test_improve_mirror_to_legacy_field(self):
        g = TasteGraph()
        g.update_novelty_from_experiment(chose_bold=True, goal_mode="improve")
        # Legacy novelty_band tracks the improve band.
        assert g.novelty_band == g.novelty_bands["improve"]

    def test_explore_does_not_touch_legacy_field(self):
        g = TasteGraph()
        original_legacy = g.novelty_band
        g.update_novelty_from_experiment(chose_bold=True, goal_mode="explore")
        # Legacy band is tied to improve only.
        assert g.novelty_band == original_legacy

    def test_decrement_on_conservative_choice(self):
        g = TasteGraph()
        g.novelty_bands["explore"] = 0.5
        g.update_novelty_from_experiment(chose_bold=False, goal_mode="explore")
        assert g.novelty_bands["explore"] < 0.5

    def test_clamped_at_one(self):
        g = TasteGraph()
        g.novelty_bands["explore"] = 0.98
        g.update_novelty_from_experiment(chose_bold=True, goal_mode="explore")
        assert g.novelty_bands["explore"] == 1.0

    def test_clamped_at_zero(self):
        g = TasteGraph()
        g.novelty_bands["explore"] = 0.02
        g.update_novelty_from_experiment(chose_bold=False, goal_mode="explore")
        assert g.novelty_bands["explore"] == 0.0


# ── rank_moves with goal_mode ───────────────────────────────────────────


class TestRankMovesPerMode:

    @staticmethod
    def _moves():
        # Two moves — one safe, one risky.
        return [
            {"move_id": "conservative", "family": "mix", "targets": {}, "risk_level": "low"},
            {"move_id": "bold", "family": "mix", "targets": {}, "risk_level": "high"},
        ]

    def test_improve_mode_prefers_safer_when_band_low(self):
        g = TasteGraph()
        g.novelty_bands["improve"] = 0.1  # very conservative
        ranked = g.rank_moves(self._moves(), goal_mode="improve")
        assert ranked[0]["move_id"] == "conservative"

    def test_explore_mode_independent_from_improve(self):
        g = TasteGraph()
        g.novelty_bands["improve"] = 0.1  # user is timid in improve
        g.novelty_bands["explore"] = 0.9  # but adventurous in explore
        ranked_improve = g.rank_moves(self._moves(), goal_mode="improve")
        ranked_explore = g.rank_moves(self._moves(), goal_mode="explore")
        assert ranked_improve[0]["move_id"] == "conservative"
        assert ranked_explore[0]["move_id"] == "bold"

    def test_unknown_goal_mode_falls_back_to_legacy_band(self):
        g = TasteGraph()
        g.novelty_band = 0.8
        # "weird_mode" isn't in novelty_bands — should fall back to novelty_band.
        ranked = g.rank_moves(self._moves(), goal_mode="weird_mode")
        assert ranked[0]["move_id"] == "bold"


# ── bypass_taste_in_generation ──────────────────────────────────────────


class TestBypassTasteInGeneration:

    def test_uniform_scores_when_bypassed(self):
        g = TasteGraph(bypass_taste_in_generation=True)
        g.dimension_weights["brightness"] = 0.9  # strong preference
        moves = [
            {"move_id": "aligned", "family": "mix", "targets": {"brightness": 1.0}, "risk_level": "low"},
            {"move_id": "opposed", "family": "mix", "targets": {"brightness": -1.0}, "risk_level": "high"},
        ]
        ranked = g.rank_moves(moves)
        # Both score 0.5 — taste doesn't prune either option.
        scores = {m["move_id"]: m["taste_score"] for m in ranked}
        assert scores["aligned"] == 0.5
        assert scores["opposed"] == 0.5

    def test_input_order_preserved_when_bypassed(self):
        g = TasteGraph(bypass_taste_in_generation=True)
        moves = [{"move_id": f"m{i}", "family": "mix"} for i in range(3)]
        ranked = g.rank_moves(moves)
        assert [m["move_id"] for m in ranked] == ["m0", "m1", "m2"]


# ── to_dict ──────────────────────────────────────────────────────────────


class TestToDictShape:

    def test_both_novelty_shapes_present(self):
        g = TasteGraph()
        d = g.to_dict()
        assert "novelty_band" in d  # legacy
        assert "novelty_bands" in d  # PR8
        assert d["novelty_bands"]["improve"] == 0.5
        assert d["novelty_bands"]["explore"] == 0.5

    def test_bypass_flag_exposed(self):
        g = TasteGraph(bypass_taste_in_generation=True)
        assert g.to_dict()["bypass_taste_in_generation"] is True


# ── Persistence migration ───────────────────────────────────────────────


class TestPersistenceMigration:

    def test_build_from_legacy_flat_band(self, tmp_path: Path):
        # Simulate a legacy persistence dict with only novelty_band.
        store = PersistentTasteStore(path=tmp_path / "taste.json")
        # Manually write a v1 doc without the bands dict.
        store._store.write({
            "version": 1,
            "novelty_band": 0.75,
            "move_outcomes": {},
            "device_affinities": {},
            "anti_preferences": [],
            "dimension_weights": {},
            "evidence_count": 5,
        })
        graph = build_taste_graph(persistent_store=store)
        assert graph.novelty_band == 0.75
        assert graph.novelty_bands["improve"] == 0.75
        assert graph.novelty_bands["explore"] == 0.75

    def test_build_from_new_bands_dict(self, tmp_path: Path):
        store = PersistentTasteStore(path=tmp_path / "taste.json")
        store._store.write({
            "version": 1,
            "novelty_band": 0.3,
            "novelty_bands": {"improve": 0.3, "explore": 0.9},
            "move_outcomes": {},
            "device_affinities": {},
            "anti_preferences": [],
            "dimension_weights": {},
            "evidence_count": 10,
        })
        graph = build_taste_graph(persistent_store=store)
        assert graph.novelty_bands["improve"] == 0.3
        assert graph.novelty_bands["explore"] == 0.9

    def test_update_novelty_writes_per_mode(self, tmp_path: Path):
        store = PersistentTasteStore(path=tmp_path / "taste.json")
        store.update_novelty(chose_bold=True, goal_mode="explore")
        store.update_novelty(chose_bold=True, goal_mode="explore")
        data = store.get_all()
        assert data["novelty_bands"]["explore"] > 0.5
        # improve untouched
        assert data["novelty_bands"]["improve"] == 0.5
        # legacy field mirrors improve
        assert data["novelty_band"] == 0.5

    def test_legacy_update_novelty_call_still_works(self, tmp_path: Path):
        """Callers that call update_novelty without goal_mode update improve."""
        store = PersistentTasteStore(path=tmp_path / "taste.json")
        store.update_novelty(chose_bold=True)
        data = store.get_all()
        assert data["novelty_bands"]["improve"] > 0.5
        assert data["novelty_band"] == data["novelty_bands"]["improve"]

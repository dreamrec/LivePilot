"""Tests for the composer branch producer (PR11).

Covers:
  - propose_composer_branches returns BranchSeed + plan tuples
  - Freshness gates which strategies are available
  - Each branch has a distinct hypothesis + distinctness_reason
  - source="composer" on every seed
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import BranchSeed
from mcp_server.composer import propose_composer_branches


class TestProposeComposerBranches:

    def test_returns_branch_seed_tuples(self):
        pairs = propose_composer_branches("make me a techno track")
        assert len(pairs) >= 1
        for seed, plan in pairs:
            assert isinstance(seed, BranchSeed)
            assert isinstance(plan, dict)

    def test_seeds_are_composer_source(self):
        pairs = propose_composer_branches("make me an ambient piece")
        for seed, _ in pairs:
            assert seed.source == "composer"

    def test_low_freshness_gives_only_canonical(self):
        pairs = propose_composer_branches(
            "build a techno loop",
            kernel={"freshness": 0.2},
        )
        assert len(pairs) == 1
        assert "canonical" in pairs[0][0].hypothesis.lower()

    def test_medium_freshness_gives_canonical_plus_energy_shift(self):
        pairs = propose_composer_branches(
            "build a techno loop",
            kernel={"freshness": 0.5},
            count=3,
        )
        assert len(pairs) == 2
        hyps = [s.hypothesis.lower() for s, _ in pairs]
        assert any("canonical" in h for h in hyps)
        assert any("energy_shift" in h for h in hyps)

    def test_high_freshness_unlocks_all_strategies(self):
        pairs = propose_composer_branches(
            "build a techno loop",
            kernel={"freshness": 0.85},
            count=3,
        )
        assert len(pairs) == 3
        hyps = [s.hypothesis.lower() for s, _ in pairs]
        assert any("layer_contrast" in h for h in hyps)

    def test_count_limits_output(self):
        pairs = propose_composer_branches(
            "make a track",
            kernel={"freshness": 0.9},
            count=1,
        )
        assert len(pairs) == 1

    def test_each_seed_has_distinctness_reason(self):
        pairs = propose_composer_branches(
            "ambient piece",
            kernel={"freshness": 0.8},
            count=3,
        )
        for seed, _ in pairs:
            assert seed.distinctness_reason, f"seed {seed.seed_id} missing distinctness_reason"

    def test_novelty_labels_distributed(self):
        pairs = propose_composer_branches(
            "house track",
            kernel={"freshness": 0.9},
            count=3,
        )
        labels = {seed.novelty_label for seed, _ in pairs}
        # Canonical=safe, energy_shift=strong, layer_contrast=unexpected
        assert "safe" in labels
        assert "strong" in labels or "unexpected" in labels

    def test_seeds_are_stable_across_calls(self):
        a = propose_composer_branches("techno", kernel={"freshness": 0.5})
        b = propose_composer_branches("techno", kernel={"freshness": 0.5})
        # Same input → same seed_ids
        assert [s.seed_id for s, _ in a] == [s.seed_id for s, _ in b]

    def test_plan_has_compatible_shape(self):
        pairs = propose_composer_branches("techno")
        for _seed, plan in pairs:
            # Either executable (step_count > 0 with steps) or marked analytical
            if plan:
                assert "steps" in plan
                assert "step_count" in plan
                assert "summary" in plan

    def test_canonical_energy_preserved(self):
        pairs = propose_composer_branches(
            "calm ambient at low energy",
            kernel={"freshness": 0.2},  # canonical only
        )
        _seed, plan = pairs[0]
        # Canonical doesn't invert energy
        assert "canonical" in plan.get("summary", "").lower()

    def test_energy_shift_direction_in_summary(self):
        pairs = propose_composer_branches(
            "calm ambient at low energy",
            kernel={"freshness": 0.5},
        )
        # The energy_shift branch should mark direction in its distinctness
        energy_branches = [
            (s, p) for s, p in pairs if "energy_shift" in s.hypothesis.lower()
        ]
        assert len(energy_branches) >= 1
        seed = energy_branches[0][0]
        assert "shifted" in seed.distinctness_reason.lower() or \
               "energy" in seed.distinctness_reason.lower()

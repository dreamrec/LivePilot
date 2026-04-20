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


class TestStepParamContracts:
    """Regression guards for the step-param contract bug found in review:
    set_tempo wants "tempo" not "bpm"; create_scene wants "index" not "name";
    section names land via set_scene_name(scene_index, name)."""

    def test_set_tempo_uses_tempo_key_not_bpm(self):
        # Use a prompt whose parser fills in a concrete tempo.
        pairs = propose_composer_branches(
            "techno at 128 bpm",
            kernel={"freshness": 0.2},  # canonical only
        )
        _seed, plan = pairs[0]
        tempo_steps = [s for s in plan["steps"] if s["tool"] == "set_tempo"]
        assert len(tempo_steps) >= 1, "set_tempo step missing"
        params = tempo_steps[0]["params"]
        assert "tempo" in params, f"set_tempo needs 'tempo', got {params.keys()}"
        assert "bpm" not in params, "remote handler rejects 'bpm'"

    def test_create_scene_uses_index_key_not_name(self):
        pairs = propose_composer_branches(
            "techno track",
            kernel={"freshness": 0.2},
        )
        _seed, plan = pairs[0]
        scene_steps = [s for s in plan["steps"] if s["tool"] == "create_scene"]
        assert len(scene_steps) >= 1, "create_scene step missing"
        for step in scene_steps:
            params = step["params"]
            assert "index" in params, f"create_scene needs 'index', got {params.keys()}"
            assert "name" not in params, (
                "create_scene remote handler does not accept 'name' — "
                "section labels must go through set_scene_name"
            )

    def test_set_scene_name_follows_create_scene_with_binding(self):
        pairs = propose_composer_branches(
            "techno track",
            kernel={"freshness": 0.2},
        )
        _seed, plan = pairs[0]
        steps = plan["steps"]
        # Each create_scene should be immediately followed by a set_scene_name
        # referencing its step_id.
        create_indices = [
            i for i, s in enumerate(steps) if s["tool"] == "create_scene"
        ]
        assert create_indices, "no create_scene steps to validate against"
        for i in create_indices:
            create = steps[i]
            assert "step_id" in create, "create_scene needs step_id for binding"
            rename = steps[i + 1]
            assert rename["tool"] == "set_scene_name"
            scene_idx_param = rename["params"].get("scene_index")
            assert isinstance(scene_idx_param, dict), (
                f"scene_index must be a $from_step binding dict, got {scene_idx_param!r}"
            )
            assert scene_idx_param.get("$from_step") == create["step_id"]
            assert scene_idx_param.get("path") == "index"

    def test_section_names_preserved_via_set_scene_name(self):
        pairs = propose_composer_branches(
            "techno track",
            kernel={"freshness": 0.2},
        )
        _seed, plan = pairs[0]
        rename_steps = [s for s in plan["steps"] if s["tool"] == "set_scene_name"]
        # Every rename must carry a non-empty name — the whole point of the
        # two-step create+rename pattern is that scene labels survive.
        for step in rename_steps:
            assert step["params"].get("name"), (
                "set_scene_name step missing name — section labels not preserved"
            )

    def test_no_top_level_name_in_create_scene_params(self):
        # Specific sanity check: historically the bug was a top-level
        # params={"name": "..."} on create_scene. Guard against regression
        # by asserting no create_scene has a "name" key.
        pairs = propose_composer_branches(
            "trap track",
            kernel={"freshness": 0.2},
        )
        for _seed, plan in pairs:
            for step in plan["steps"]:
                if step["tool"] == "create_scene":
                    assert "name" not in step["params"]

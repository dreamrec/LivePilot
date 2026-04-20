"""Tests for generate_branch_seeds_and_plans — the multi-producer entry
point that wires synthesis_brain and composer into Wonder.

Review flagged that propose_synth_branches and propose_composer_branches
were effectively unreachable from the MCP runtime despite being
registered in the conductor. This function fixes that gap.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import BranchSeed
from mcp_server.synthesis_brain import analyze_synth_patch
from mcp_server.wonder_mode.engine import (
    generate_branch_seeds,
    generate_branch_seeds_and_plans,
)


class TestReturnShape:

    def test_returns_tuple_of_seeds_and_plans_dict(self):
        seeds, plans = generate_branch_seeds_and_plans("make it punchier")
        assert isinstance(seeds, list)
        assert isinstance(plans, dict)

    def test_without_synth_or_composer_matches_base_function(self):
        # When neither synth_profiles nor composer_request is provided,
        # the new function should produce the same seed list as the
        # base generate_branch_seeds — producer union is empty.
        base = generate_branch_seeds("make it punchier")
        seeds, plans = generate_branch_seeds_and_plans("make it punchier")
        assert [s.seed_id for s in seeds] == [s.seed_id for s in base]
        # Base seeds don't carry pre-compiled plans.
        assert plans == {}


class TestSynthesisWiring:

    def _wavetable_profile(self):
        return analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Osc 1 Position": 0.3, "Voices": 2, "Voices Detune": 0.05},
        )

    def test_synth_profile_produces_synthesis_seeds(self):
        profile = self._wavetable_profile()
        seeds, plans = generate_branch_seeds_and_plans(
            "xyzzy unrelated request",  # keep semantic_move seeds out of the way
            synth_profiles=[profile],
            max_seeds=5,
        )
        synth_seeds = [s for s in seeds if s.source == "synthesis"]
        assert len(synth_seeds) >= 1
        # Every synth seed must have a pre-compiled plan in the plans dict.
        for s in synth_seeds:
            assert s.seed_id in plans
            plan = plans[s.seed_id]
            assert "steps" in plan
            assert plan["step_count"] >= 1

    def test_synth_plans_are_execution_router_compatible(self):
        profile = self._wavetable_profile()
        _seeds, plans = generate_branch_seeds_and_plans(
            "xyzzy",
            synth_profiles=[profile],
        )
        for plan in plans.values():
            for step in plan["steps"]:
                assert "tool" in step
                assert "params" in step
                # Wavetable proposer uses set_device_parameter
                if step["tool"] == "set_device_parameter":
                    assert "parameter_name" in step["params"]

    def test_max_seeds_caps_across_producers(self):
        profile = self._wavetable_profile()
        seeds, _plans = generate_branch_seeds_and_plans(
            "make it punchier",  # semantic moves match
            synth_profiles=[profile],
            max_seeds=2,
        )
        assert len(seeds) <= 2

    def test_no_profiles_skips_synthesis_path(self):
        seeds, plans = generate_branch_seeds_and_plans(
            "xyzzy",
            synth_profiles=[],
        )
        assert not any(s.source == "synthesis" for s in seeds)


class TestComposerWiring:

    def test_composer_request_produces_composer_seeds(self):
        seeds, plans = generate_branch_seeds_and_plans(
            "xyzzy",
            composer_request="build me a techno loop at 128",
            composer_count=2,
            max_seeds=5,
        )
        comp_seeds = [s for s in seeds if s.source == "composer"]
        assert len(comp_seeds) >= 1
        for s in comp_seeds:
            # Plans may be attached (scaffolding plans) or absent (analytical).
            if s.seed_id in plans:
                assert "steps" in plans[s.seed_id]

    def test_no_composer_request_skips_composer_path(self):
        seeds, _ = generate_branch_seeds_and_plans(
            "make it punchier",
            composer_request=None,
        )
        assert not any(s.source == "composer" for s in seeds)


class TestResilience:

    def test_synthesis_producer_failure_does_not_kill_assembly(self):
        # A bad profile shouldn't blow up the whole call — other sources
        # should still produce their seeds.
        class BadProfile:
            opacity = "native"
            device_name = "Wavetable"
            # Missing every other field — will raise on proposal.

        seeds, _plans = generate_branch_seeds_and_plans(
            "make it punchier",
            synth_profiles=[BadProfile()],
        )
        # Semantic move seeds should survive.
        assert any(s.source == "semantic_move" for s in seeds)

    def test_empty_request_returns_empty_or_minimal(self):
        seeds, plans = generate_branch_seeds_and_plans("")
        assert isinstance(seeds, list)
        assert isinstance(plans, dict)

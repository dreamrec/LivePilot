"""Tests for the Conductor — intelligent request routing."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._conductor import (
    classify_request,
    classify_request_creative,
    ConductorPlan,
    CreativeSearchPlan,
    EngineRoute,
)


class TestClassifyRequest:
    def test_mix_request(self):
        plan = classify_request("make this cleaner and less muddy")
        assert plan.request_type == "mix"
        assert plan.routes[0].engine == "mix_engine"
        assert plan.routes[0].entry_tool == "analyze_mix"

    def test_punch_routes_to_mix(self):
        plan = classify_request("make the drums hit harder with more punch")
        assert plan.routes[0].engine == "mix_engine"

    def test_width_routes_to_mix(self):
        plan = classify_request("make this wider in the chorus")
        assert any(r.engine == "mix_engine" for r in plan.routes)

    def test_composition_request(self):
        plan = classify_request("turn this loop into a full arrangement")
        assert plan.request_type == "composition"
        assert plan.routes[0].engine == "composition"

    def test_section_routes_to_composition(self):
        plan = classify_request("add a breakdown before the drop")
        assert plan.routes[0].engine == "composition"

    def test_sound_design_request(self):
        plan = classify_request("make this synth patch sound more haunted")
        assert plan.routes[0].engine == "sound_design"

    def test_modulation_routes_to_sound_design(self):
        plan = classify_request("add more movement and modulation to the pad")
        assert plan.routes[0].engine == "sound_design"

    def test_transition_request(self):
        plan = classify_request("make the transition feel earned and smooth the handoff")
        assert any(r.engine == "transition_engine" for r in plan.routes)

    def test_reference_request(self):
        plan = classify_request("make this sound like Burial")
        assert plan.routes[0].engine == "reference_engine"

    def test_translation_request(self):
        plan = classify_request("check translation and mono compatibility")
        assert any(r.engine == "translation_engine" for r in plan.routes)

    def test_mono_routes_to_translation(self):
        plan = classify_request("test mono compatibility for earbuds")
        assert any(r.engine == "translation_engine" for r in plan.routes)

    def test_performance_request(self):
        plan = classify_request("help me with my live set")
        assert plan.routes[0].engine == "performance_engine"

    def test_research_request(self):
        plan = classify_request("research how to sidechain properly")
        assert plan.routes[0].engine == "research"

    def test_unknown_defaults_to_agent_os(self):
        plan = classify_request("do something cool")
        assert plan.request_type == "general"
        assert plan.routes[0].engine == "agent_os"

    def test_empty_request(self):
        plan = classify_request("")
        assert plan.request_type == "unknown"

    def test_multi_engine_routing(self):
        plan = classify_request("make this wider and check mono compatibility")
        assert len(plan.routes) >= 2
        engines = {r.engine for r in plan.routes}
        assert "mix_engine" in engines or "translation_engine" in engines

    def test_multi_engine_gets_brain_note(self):
        plan = classify_request("clean up the mix and fix the transition into the drop")
        if len(plan.routes) > 1:
            assert any("session_kernel" in n.lower() or "shared state" in n.lower()
                       for n in plan.notes)

    def test_mix_requests_analyzer_capability(self):
        plan = classify_request("make the drums punchier")
        assert "analyzer" in plan.capability_requirements

    def test_priority_ordering(self):
        plan = classify_request("make this cleaner")
        if plan.routes:
            assert plan.routes[0].priority == 1


class TestConductorPlan:
    def test_to_dict(self):
        plan = classify_request("make this wider")
        d = plan.to_dict()
        assert "request" in d
        assert "routes" in d
        assert "primary_engine" in d
        assert d["engine_count"] >= 1

    def test_primary_engine_in_dict(self):
        plan = classify_request("add more punch")
        d = plan.to_dict()
        assert d["primary_engine"] is not None


# ── PR4 — creative_search routing fork ──────────────────────────────────


class TestClassifyRequestCreative:
    """The creative_search path is additive — classify_request() must be
    unchanged. These tests verify the new function's producer-selection
    behavior without touching the base classifier."""

    def test_returns_creative_search_plan(self):
        plan = classify_request_creative("explore some options for the drop")
        assert isinstance(plan, CreativeSearchPlan)
        assert isinstance(plan.base_plan, ConductorPlan)

    def test_base_plan_matches_classify_request(self):
        request = "make this wider"
        creative = classify_request_creative(request)
        base = classify_request(request)
        # Base routing is delegated exactly — engines match identically.
        assert [r.engine for r in creative.base_plan.routes] == [r.engine for r in base.routes]

    def test_semantic_move_always_first_source(self):
        plan = classify_request_creative("do something")
        assert plan.branch_sources[0] == "semantic_move"

    def test_freeform_always_last_source(self):
        plan = classify_request_creative("do something")
        assert plan.branch_sources[-1] == "freeform"

    def test_synthesis_producer_added_by_request_keyword(self):
        plan = classify_request_creative("redesign this wavetable patch")
        assert "synthesis" in plan.branch_sources
        assert plan.seed_hints.get("synthesis", {}).get("inferred_from_request") is True

    def test_synthesis_producer_added_by_kernel_hints(self):
        kernel = {"synth_hints": {"track_indices": [2], "preferred_devices": ["Wavetable"]}}
        # Request mentions nothing about synths — kernel alone adds the producer.
        plan = classify_request_creative("surprise me", kernel=kernel)
        assert "synthesis" in plan.branch_sources
        hint = plan.seed_hints["synthesis"]
        assert hint["track_indices"] == [2]
        assert "inferred_from_request" not in hint  # came from kernel, not text

    def test_composer_added_for_composition_primary_route(self):
        plan = classify_request_creative("turn this loop into a full arrangement")
        assert "composer" in plan.branch_sources
        assert plan.seed_hints["composer"]["request"].startswith("turn this loop")

    def test_composer_not_added_for_non_composition_request(self):
        plan = classify_request_creative("clean up the low end")
        assert "composer" not in plan.branch_sources

    def test_technique_added_when_kernel_has_taste_evidence(self):
        kernel = {
            "taste_graph": {
                "evidence_count": 5,
                "move_family_scores": {
                    "mix": {"score": 0.4, "kept_count": 3, "undone_count": 1},
                    "arrangement": {"score": -0.1, "kept_count": 1, "undone_count": 2},
                },
            }
        }
        plan = classify_request_creative("surprise me", kernel=kernel)
        assert "technique" in plan.branch_sources
        # Only families with score > 0.2 are preferred
        assert plan.seed_hints["technique"]["preferred_families"] == ["mix"]

    def test_technique_added_when_request_hints_prior_work(self):
        plan = classify_request_creative("do it like last time")
        assert "technique" in plan.branch_sources
        assert plan.seed_hints["technique"]["hinted_by_request"] is True

    def test_technique_not_added_without_evidence_or_hint(self):
        kernel = {"taste_graph": {"evidence_count": 1, "move_family_scores": {}}}
        plan = classify_request_creative("do something new", kernel=kernel)
        assert "technique" not in plan.branch_sources

    def test_freshness_and_creativity_profile_threaded_from_kernel(self):
        kernel = {"freshness": 0.9, "creativity_profile": "alchemist"}
        plan = classify_request_creative("surprise me", kernel=kernel)
        assert plan.freshness == 0.9
        assert plan.creativity_profile == "alchemist"

    def test_defaults_without_kernel(self):
        plan = classify_request_creative("make something")
        assert plan.freshness == 0.5
        assert plan.creativity_profile == ""

    def test_target_branch_count_default_three(self):
        plan = classify_request_creative("make something")
        assert plan.target_branch_count == 3


class TestCreativeSearchPlanSerialization:

    def test_to_dict_wraps_base_plan(self):
        plan = classify_request_creative("widen this")
        d = plan.to_dict()
        # Base fields from ConductorPlan are all present
        assert "request" in d
        assert "routes" in d
        assert "engine_count" in d
        # Creative fields live under a dedicated key
        assert "creative_search" in d
        cs = d["creative_search"]
        assert "branch_sources" in cs
        assert "seed_hints" in cs
        assert "target_branch_count" in cs
        assert "freshness" in cs

    def test_to_dict_always_recommends_experiment(self):
        # A creative_search plan implies experiment_recommended=True regardless
        # of what the base plan thought.
        plan = classify_request_creative("clean this up")  # non-exploratory language
        d = plan.to_dict()
        assert d["experiment_recommended"] is True


class TestClassifyRequestUnchanged:
    """Regression guard — PR4 adds no behavior to the base classifier."""

    def test_request_type_stable(self):
        # Exact-match test that the base classifier wasn't perturbed.
        plan = classify_request("make the transition feel earned and smooth the handoff")
        assert plan.request_type == "transition"

    def test_workflow_mode_still_inferred(self):
        plan = classify_request("explore some variants")
        assert plan.workflow_mode == "creative_search"


class TestEngineRoute:
    def test_to_dict(self):
        route = EngineRoute(engine="mix_engine", priority=1, reason="test",
                            entry_tool="analyze_mix", follow_up_tools=["plan_mix_move"])
        d = route.to_dict()
        assert d["engine"] == "mix_engine"
        assert d["priority"] == 1


class TestConductorV2:
    """Tests for V2 conductor extensions: semantic moves, workflow modes."""

    def test_punchier_finds_semantic_move(self):
        plan = classify_request("make this punchier")
        assert len(plan.semantic_moves) > 0
        assert any(m["move_id"] == "make_punchier" for m in plan.semantic_moves)

    def test_widen_finds_semantic_move(self):
        plan = classify_request("make the stereo image wider")
        assert len(plan.semantic_moves) > 0
        assert any(m["move_id"] == "widen_stereo" for m in plan.semantic_moves)

    def test_tighten_low_end_move(self):
        plan = classify_request("tighten the low end")
        assert len(plan.semantic_moves) > 0
        assert any(m["move_id"] == "tighten_low_end" for m in plan.semantic_moves)

    def test_plan_includes_semantic_moves_in_dict(self):
        plan = classify_request("make it punchier")
        d = plan.to_dict()
        assert "semantic_moves" in d
        assert "workflow_mode" in d
        assert "experiment_recommended" in d

    def test_experiment_recommended_for_creative_search(self):
        plan = classify_request("try some different ideas for the transition")
        assert plan.workflow_mode == "creative_search"
        assert plan.experiment_recommended is True

    def test_performance_safe_mode(self):
        plan = classify_request("help me in my live set")
        assert plan.workflow_mode == "performance_safe"

    def test_quick_fix_mode(self):
        plan = classify_request("just fix the low end quickly")
        assert plan.workflow_mode == "quick_fix"

    def test_guided_workflow_default(self):
        plan = classify_request("improve the mix balance")
        assert plan.workflow_mode == "guided_workflow"

    def test_use_session_kernel_always_true(self):
        plan = classify_request("anything")
        assert plan.use_session_kernel is True

    def test_semantic_move_note_added_when_moves_found(self):
        plan = classify_request("make this punchier")
        if plan.semantic_moves:
            assert any("semantic move" in n.lower() for n in plan.notes)

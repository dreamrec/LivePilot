"""Tests for the Conductor — intelligent request routing."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._conductor import classify_request, ConductorPlan, EngineRoute


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
            assert any("build_project_brain" in n for n in plan.notes)

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


class TestEngineRoute:
    def test_to_dict(self):
        route = EngineRoute(engine="mix_engine", priority=1, reason="test",
                            entry_tool="analyze_mix", follow_up_tools=["plan_mix_move"])
        d = route.to_dict()
        assert d["engine"] == "mix_engine"
        assert d["priority"] == 1

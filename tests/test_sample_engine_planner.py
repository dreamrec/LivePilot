from mcp_server.sample_engine.planner import (
    select_technique,
    compile_sample_plan,
)
from mcp_server.sample_engine.models import SampleProfile, SampleIntent, SampleFitReport
from mcp_server.sample_engine.critics import CriticResult


class TestSamplePlanner:
    def test_select_technique_drum_rhythm(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="drum_loop")
        intent = SampleIntent(intent_type="rhythm", description="chop it")
        technique = select_technique(profile, intent)
        assert technique is not None
        assert "rhythm" in technique.intents or "drum_loop" in technique.material_types

    def test_select_technique_vocal_texture(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="vocal")
        intent = SampleIntent(intent_type="texture", philosophy="alchemist",
                              description="stretch into pad")
        technique = select_technique(profile, intent)
        assert technique is not None
        assert technique.philosophy in ("alchemist", "both")

    def test_compile_plan_returns_tool_steps(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="drum_loop", bpm=128.0)
        intent = SampleIntent(intent_type="rhythm", description="")
        plan = compile_sample_plan(profile, intent, target_track=0)
        assert len(plan) > 0
        assert all("tool" in step for step in plan)

    def test_surgeon_vs_alchemist_plans_differ(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="vocal")
        surgeon = compile_sample_plan(
            profile,
            SampleIntent(intent_type="layer", philosophy="surgeon", description=""),
            target_track=0,
        )
        alchemist = compile_sample_plan(
            profile,
            SampleIntent(intent_type="layer", philosophy="alchemist", description=""),
            target_track=0,
        )
        # Plans should differ in approach
        surgeon_tools = [s["tool"] for s in surgeon]
        alchemist_tools = [s["tool"] for s in alchemist]
        assert surgeon_tools != alchemist_tools or len(surgeon) != len(alchemist)

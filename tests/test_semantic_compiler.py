"""Tests for the semantic move compiler — verifies moves compile to concrete tool calls."""

import pytest

from mcp_server.semantic_moves.models import SemanticMove
from mcp_server.semantic_moves.compiler import compile, CompiledPlan, CompiledStep
from mcp_server.semantic_moves.registry import get_move
from mcp_server.semantic_moves import resolvers


# ── Mock kernel ──────────────────────────────────────────────────────────────

MOCK_KERNEL = {
    "session_info": {
        "tempo": 82,
        "track_count": 6,
        "tracks": [
            {"index": 0, "name": "Drums", "mute": False, "solo": False},
            {"index": 1, "name": "Sub Bass", "mute": False, "solo": False},
            {"index": 2, "name": "Rhodes", "mute": False, "solo": False},
            {"index": 3, "name": "Texture Pad", "mute": False, "solo": False},
            {"index": 4, "name": "Glitch Lead", "mute": False, "solo": False},
            {"index": 5, "name": "Lo-fi Perc", "mute": False, "solo": False},
        ],
    },
    "mode": "improve",
    "capability_state": {},
}


# ── Resolver tests ───────────────────────────────────────────────────────────

def test_infer_role_drums():
    assert resolvers.infer_role("Drums") == "drums"
    assert resolvers.infer_role("808 Kit") == "drums"  # "kit" matches drums first
    assert resolvers.infer_role("Main Beat") == "drums"


def test_infer_role_bass():
    assert resolvers.infer_role("Sub Bass") == "bass"
    assert resolvers.infer_role("Deep Sub") == "bass"


def test_infer_role_chords():
    assert resolvers.infer_role("Rhodes") == "chords"
    assert resolvers.infer_role("Piano Chords") == "chords"


def test_infer_role_pad():
    assert resolvers.infer_role("Texture Pad") == "pad"
    assert resolvers.infer_role("Ambient Drone") == "pad"


def test_infer_role_lead():
    assert resolvers.infer_role("Glitch Lead") == "lead"
    assert resolvers.infer_role("Synth Melody") == "lead"


def test_infer_role_unknown():
    assert resolvers.infer_role("Track 7") == "unknown"


def test_find_tracks_by_role():
    bass = resolvers.find_tracks_by_role(MOCK_KERNEL, ["bass"])
    assert len(bass) == 1
    assert bass[0]["name"] == "Sub Bass"
    assert bass[0]["index"] == 1


def test_find_tracks_by_role_multiple():
    melodic = resolvers.find_tracks_by_role(MOCK_KERNEL, ["chords", "lead"])
    assert len(melodic) == 2
    names = {t["name"] for t in melodic}
    assert "Rhodes" in names
    assert "Glitch Lead" in names


def test_find_track_by_name():
    t = resolvers.find_track_by_name(MOCK_KERNEL, "Rhodes")
    assert t is not None
    assert t["index"] == 2


def test_find_track_by_name_not_found():
    assert resolvers.find_track_by_name(MOCK_KERNEL, "Violin") is None


def test_volume_math():
    assert resolvers.clamp_volume(1.5) == 1.0
    assert resolvers.clamp_volume(-0.5) == 0.0
    assert resolvers.adjust_volume(0.7, 5) == pytest.approx(0.75)
    assert resolvers.adjust_volume(0.95, 10) == 1.0  # Clamped


# ── Compiler tests ───────────────────────────────────────────────────────────

def test_compile_make_punchier():
    move = get_move("make_punchier")
    assert move is not None
    plan = compile(move, MOCK_KERNEL)
    assert isinstance(plan, CompiledPlan)
    assert plan.executable
    assert plan.move_id == "make_punchier"
    # Should have steps for drums + pads + verification
    assert plan.step_count >= 3
    # All steps must have a tool name
    for step in plan.steps:
        assert step.tool, f"Step missing tool: {step.description}"


def test_compile_tighten_low_end():
    move = get_move("tighten_low_end")
    plan = compile(move, MOCK_KERNEL)
    assert plan.executable
    # Should target Sub Bass track
    bass_steps = [s for s in plan.steps if "Sub Bass" in s.description]
    assert len(bass_steps) >= 1


def test_compile_widen_stereo():
    move = get_move("widen_stereo")
    plan = compile(move, MOCK_KERNEL)
    assert plan.executable
    pan_steps = [s for s in plan.steps if s.tool == "set_track_pan"]
    assert len(pan_steps) >= 2  # At least chords + lead


def test_compile_darken_mix():
    move = get_move("darken_without_losing_width")
    plan = compile(move, MOCK_KERNEL)
    assert plan.executable


def test_compile_reduce_repetition():
    move = get_move("reduce_repetition_fatigue")
    plan = compile(move, MOCK_KERNEL)
    assert plan.executable
    perlin_steps = [s for s in plan.steps if "perlin" in s.description.lower()]
    assert len(perlin_steps) >= 1


def test_compile_unknown_move_returns_non_executable():
    fake_move = SemanticMove(move_id="nonexistent", family="unknown", intent="???")
    plan = compile(fake_move, MOCK_KERNEL)
    assert not plan.executable
    assert len(plan.warnings) > 0


def test_compiled_plan_to_dict():
    move = get_move("make_punchier")
    plan = compile(move, MOCK_KERNEL)
    d = plan.to_dict()
    assert "steps" in d
    assert "summary" in d
    assert "executable" in d
    assert d["executable"] is True
    for step in d["steps"]:
        assert "tool" in step
        assert "params" in step
        assert "description" in step


def test_compiled_plan_requires_approval_in_improve_mode():
    move = get_move("make_punchier")
    plan = compile(move, MOCK_KERNEL)
    assert plan.requires_approval is True


def test_compiled_plan_auto_executes_in_explore_mode():
    move = get_move("make_punchier")
    kernel = {**MOCK_KERNEL, "mode": "explore"}
    plan = compile(move, kernel)
    assert plan.requires_approval is False


def test_empty_session_degrades_gracefully():
    """Compiler should handle sessions with no tracks."""
    empty_kernel = {
        "session_info": {"tempo": 120, "track_count": 0, "tracks": []},
        "mode": "improve",
    }
    move = get_move("make_punchier")
    plan = compile(move, empty_kernel)
    # Should still return a plan (maybe with warnings)
    assert isinstance(plan, CompiledPlan)
    assert len(plan.warnings) > 0 or plan.step_count <= 2  # Just reads + verify

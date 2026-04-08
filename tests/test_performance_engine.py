"""Tests for Performance Engine V1 — live-safe mode, scene steering, safety."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.performance_engine.models import (
    EnergyWindow,
    HandoffPlan,
    LiveSafeMove,
    PerformanceState,
    SceneRole,
    VALID_DIRECTIONS,
    VALID_RISK_LEVELS,
    VALID_ROLES,
)
from mcp_server.performance_engine.safety import (
    BLOCKED_MOVE_TYPES,
    CAUTION_MOVE_TYPES,
    SAFE_MOVE_TYPES,
    classify_move_safety,
    get_blocked_moves,
    get_safe_moves,
)
from mcp_server.performance_engine.planner import (
    build_performance_state,
    plan_scene_transition,
    suggest_energy_moves,
)


# ── SceneRole ─────────────────────────────────────────────────────────


class TestSceneRole:
    def test_valid_scene_role(self):
        s = SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro")
        assert s.scene_index == 0
        assert s.name == "Intro"
        assert s.energy_level == 0.2
        assert s.role == "intro"

    def test_to_dict(self):
        s = SceneRole(scene_index=1, name="Drop", energy_level=0.9, role="drop")
        d = s.to_dict()
        assert d["scene_index"] == 1
        assert d["name"] == "Drop"
        assert d["energy_level"] == 0.9
        assert d["role"] == "drop"
        assert isinstance(d, dict)

    def test_invalid_energy_level(self):
        with pytest.raises(ValueError, match="energy_level"):
            SceneRole(scene_index=0, name="Bad", energy_level=1.5, role="verse")

    def test_invalid_energy_level_negative(self):
        with pytest.raises(ValueError, match="energy_level"):
            SceneRole(scene_index=0, name="Bad", energy_level=-0.1, role="verse")

    def test_invalid_role(self):
        with pytest.raises(ValueError, match="role"):
            SceneRole(scene_index=0, name="Bad", energy_level=0.5, role="invalid")

    def test_all_valid_roles(self):
        for role in VALID_ROLES:
            s = SceneRole(scene_index=0, name="Test", energy_level=0.5, role=role)
            assert s.role == role


# ── EnergyWindow ──────────────────────────────────────────────────────


class TestEnergyWindow:
    def test_valid_energy_window(self):
        ew = EnergyWindow(current_energy=0.3, target_energy=0.7, direction="up", urgency=0.5)
        assert ew.direction == "up"
        assert ew.urgency == 0.5

    def test_to_dict(self):
        ew = EnergyWindow(current_energy=0.5, target_energy=0.5, direction="hold", urgency=0.0)
        d = ew.to_dict()
        assert d["direction"] == "hold"
        assert isinstance(d, dict)

    def test_invalid_direction(self):
        with pytest.raises(ValueError, match="direction"):
            EnergyWindow(direction="sideways")

    def test_invalid_urgency(self):
        with pytest.raises(ValueError, match="urgency"):
            EnergyWindow(urgency=1.5)


# ── LiveSafeMove ──────────────────────────────────────────────────────


class TestLiveSafeMove:
    def test_valid_move(self):
        m = LiveSafeMove(
            move_type="scene_launch",
            target="scene_0",
            description="Launch intro",
            risk_level="safe",
            parameters={"scene_index": 0},
            reversible=True,
        )
        assert m.move_type == "scene_launch"
        assert m.reversible is True

    def test_to_dict(self):
        m = LiveSafeMove(move_type="mute_toggle", target="track_1", description="Mute")
        d = m.to_dict()
        assert d["move_type"] == "mute_toggle"
        assert d["reversible"] is True
        assert isinstance(d, dict)

    def test_invalid_risk_level(self):
        with pytest.raises(ValueError, match="risk_level"):
            LiveSafeMove(risk_level="extreme")


# ── HandoffPlan ───────────────────────────────────────────────────────


class TestHandoffPlan:
    def test_to_dict(self):
        hp = HandoffPlan(
            from_scene=0,
            to_scene=2,
            gestures=[{"type": "prepare"}],
            energy_path=[0.2, 0.5, 0.8],
        )
        d = hp.to_dict()
        assert d["from_scene"] == 0
        assert d["to_scene"] == 2
        assert len(d["energy_path"]) == 3


# ── PerformanceState ──────────────────────────────────────────────────


class TestPerformanceState:
    def test_to_dict(self):
        ps = PerformanceState(
            scenes=[SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro")],
            current_scene=0,
            energy_window=EnergyWindow(),
            safe_moves=[],
            blocked_moves=["note_edit"],
        )
        d = ps.to_dict()
        assert len(d["scenes"]) == 1
        assert d["current_scene"] == 0
        assert "note_edit" in d["blocked_moves"]
        assert isinstance(d["energy_window"], dict)


# ── Safety classification ─────────────────────────────────────────────


class TestSafetyClassification:
    def test_safe_moves(self):
        for mt in SAFE_MOVE_TYPES:
            assert classify_move_safety(mt) == "safe"

    def test_blocked_moves(self):
        for mt in BLOCKED_MOVE_TYPES:
            assert classify_move_safety(mt) == "blocked"

    def test_unknown_is_caution(self):
        assert classify_move_safety("something_unknown") == "caution"

    def test_caution_moves(self):
        for mt in CAUTION_MOVE_TYPES:
            assert classify_move_safety(mt) == "caution"

    def test_no_overlap_safe_blocked(self):
        assert SAFE_MOVE_TYPES & BLOCKED_MOVE_TYPES == frozenset()

    def test_get_blocked_moves_sorted(self):
        blocked = get_blocked_moves()
        assert blocked == sorted(blocked)
        assert len(blocked) == len(BLOCKED_MOVE_TYPES)

    def test_safe_move_count(self):
        assert len(SAFE_MOVE_TYPES) == 6

    def test_blocked_move_count(self):
        assert len(BLOCKED_MOVE_TYPES) == 5


# ── Safe move suggestions ─────────────────────────────────────────────


class TestGetSafeMoves:
    def _make_scenes(self):
        return [
            SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro"),
            SceneRole(scene_index=1, name="Verse", energy_level=0.4, role="verse"),
            SceneRole(scene_index=2, name="Chorus", energy_level=0.7, role="chorus"),
            SceneRole(scene_index=3, name="Drop", energy_level=0.9, role="drop"),
        ]

    def test_energy_up_suggests_higher_scenes(self):
        scenes = self._make_scenes()
        ew = EnergyWindow(current_energy=0.3, target_energy=0.8, direction="up", urgency=0.5)
        moves = get_safe_moves(scenes, 0, ew)
        scene_launches = [m for m in moves if m.move_type == "scene_launch"]
        # Should suggest scenes with higher energy than current
        for m in scene_launches:
            idx = m.parameters["scene_index"]
            assert scenes[idx].energy_level > ew.current_energy

    def test_energy_down_suggests_lower_scenes(self):
        scenes = self._make_scenes()
        ew = EnergyWindow(current_energy=0.8, target_energy=0.3, direction="down", urgency=0.5)
        moves = get_safe_moves(scenes, 3, ew)
        scene_launches = [m for m in moves if m.move_type == "scene_launch"]
        for m in scene_launches:
            idx = m.parameters["scene_index"]
            assert scenes[idx].energy_level < ew.current_energy

    def test_always_includes_macro_nudge(self):
        scenes = self._make_scenes()
        ew = EnergyWindow()
        moves = get_safe_moves(scenes, 0, ew)
        macro_moves = [m for m in moves if m.move_type == "macro_nudge"]
        assert len(macro_moves) >= 1

    def test_all_moves_are_safe(self):
        scenes = self._make_scenes()
        ew = EnergyWindow(current_energy=0.3, target_energy=0.8, direction="up")
        moves = get_safe_moves(scenes, 0, ew)
        for m in moves:
            assert m.risk_level == "safe"


# ── Planner ───────────────────────────────────────────────────────────


class TestPlanSceneTransition:
    def test_basic_transition(self):
        from_s = SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro")
        to_s = SceneRole(scene_index=2, name="Chorus", energy_level=0.7, role="chorus")
        plan = plan_scene_transition(from_s, to_s)
        assert plan.from_scene == 0
        assert plan.to_scene == 2
        assert len(plan.energy_path) >= 3
        assert plan.energy_path[0] == pytest.approx(0.2, abs=0.01)
        assert plan.energy_path[-1] == pytest.approx(0.7, abs=0.01)

    def test_transition_has_gestures(self):
        from_s = SceneRole(scene_index=0, name="Verse", energy_level=0.4, role="verse")
        to_s = SceneRole(scene_index=1, name="Drop", energy_level=0.9, role="drop")
        plan = plan_scene_transition(from_s, to_s)
        assert len(plan.gestures) >= 3
        gesture_types = [g["type"] for g in plan.gestures]
        assert "prepare" in gesture_types
        assert "scene_launch" in gesture_types
        assert "settle" in gesture_types

    def test_small_delta_fewer_steps(self):
        from_s = SceneRole(scene_index=0, name="Verse", energy_level=0.4, role="verse")
        to_s = SceneRole(scene_index=1, name="Chorus", energy_level=0.5, role="chorus")
        plan = plan_scene_transition(from_s, to_s)
        # Small delta = 2 steps = 3 energy path points
        assert len(plan.energy_path) == 3

    def test_large_delta_more_steps(self):
        from_s = SceneRole(scene_index=0, name="Intro", energy_level=0.1, role="intro")
        to_s = SceneRole(scene_index=3, name="Drop", energy_level=0.9, role="drop")
        plan = plan_scene_transition(from_s, to_s)
        # Large delta = 6 steps = 7 energy path points
        assert len(plan.energy_path) == 7

    def test_to_dict(self):
        from_s = SceneRole(scene_index=0, name="A", energy_level=0.3, role="verse")
        to_s = SceneRole(scene_index=1, name="B", energy_level=0.6, role="chorus")
        plan = plan_scene_transition(from_s, to_s)
        d = plan.to_dict()
        assert isinstance(d, dict)
        assert "gestures" in d
        assert "energy_path" in d


# ── Suggest energy moves ──────────────────────────────────────────────


class TestSuggestEnergyMoves:
    def test_hold_near_target(self):
        ew = EnergyWindow(current_energy=0.5, target_energy=0.52, direction="hold")
        scene = SceneRole(scene_index=0, name="Verse", energy_level=0.5, role="verse")
        moves = suggest_energy_moves(ew, scene)
        assert len(moves) == 1
        assert moves[0].move_type == "macro_nudge"

    def test_energy_up_suggests_volume(self):
        ew = EnergyWindow(current_energy=0.3, target_energy=0.7, direction="up", urgency=0.5)
        scene = SceneRole(scene_index=1, name="Build", energy_level=0.6, role="build")
        moves = suggest_energy_moves(ew, scene)
        types = [m.move_type for m in moves]
        assert "volume_nudge" in types

    def test_energy_down_suggests_filter(self):
        ew = EnergyWindow(current_energy=0.8, target_energy=0.3, direction="down", urgency=0.5)
        scene = SceneRole(scene_index=2, name="Breakdown", energy_level=0.3, role="breakdown")
        moves = suggest_energy_moves(ew, scene)
        types = [m.move_type for m in moves]
        assert "filter_sweep" in types


# ── Build performance state ───────────────────────────────────────────


class TestBuildPerformanceState:
    def test_basic_build(self):
        scenes = [
            SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro"),
            SceneRole(scene_index=1, name="Verse", energy_level=0.4, role="verse"),
            SceneRole(scene_index=2, name="Drop", energy_level=0.9, role="drop"),
        ]
        state = build_performance_state(scenes, 0)
        assert isinstance(state, PerformanceState)
        assert state.current_scene == 0
        assert len(state.scenes) == 3
        assert len(state.blocked_moves) == len(BLOCKED_MOVE_TYPES)

    def test_energy_direction_inferred(self):
        scenes = [
            SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro"),
            SceneRole(scene_index=1, name="Drop", energy_level=0.9, role="drop"),
        ]
        state = build_performance_state(scenes, 0)
        assert state.energy_window.direction == "up"
        assert state.energy_window.target_energy == 0.9

    def test_last_scene_holds(self):
        scenes = [
            SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro"),
            SceneRole(scene_index=1, name="Outro", energy_level=0.2, role="outro"),
        ]
        state = build_performance_state(scenes, 1)
        assert state.energy_window.direction == "hold"

    def test_missing_scene_defaults(self):
        scenes = [
            SceneRole(scene_index=0, name="A", energy_level=0.5, role="verse"),
        ]
        state = build_performance_state(scenes, 99)
        assert state.energy_window.current_energy == 0.5
        assert state.energy_window.direction == "hold"

    def test_to_dict_round_trip(self):
        scenes = [
            SceneRole(scene_index=0, name="Intro", energy_level=0.2, role="intro"),
            SceneRole(scene_index=1, name="Verse", energy_level=0.4, role="verse"),
        ]
        state = build_performance_state(scenes, 0)
        d = state.to_dict()
        assert isinstance(d, dict)
        assert "scenes" in d
        assert "energy_window" in d
        assert "safe_moves" in d
        assert "blocked_moves" in d
        assert d["current_scene"] == 0

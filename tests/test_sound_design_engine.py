"""Tests for the Sound Design Engine — models, critics, planner.

Pure-computation tests, no I/O or Ableton connection required.
"""

from __future__ import annotations

import pytest

from mcp_server.sound_design.models import (
    LayerStrategy,
    PatchBlock,
    PatchModel,
    SoundDesignState,
    TimbralGoalVector,
    VALID_BLOCK_TYPES,
)
from mcp_server.sound_design.critics import (
    SoundDesignIssue,
    run_all_sound_design_critics,
    run_layer_overlap_critic,
    run_masking_role_critic,
    run_modulation_flatness_critic,
    run_static_timbre_critic,
    run_weak_identity_critic,
)
from mcp_server.sound_design.planner import (
    SoundDesignMove,
    plan_sound_design_moves,
)


# ═══════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════


class TestTimbralGoalVector:
    def test_defaults(self):
        g = TimbralGoalVector()
        assert g.brightness == 0.0
        assert g.protect == {}

    def test_to_dict(self):
        g = TimbralGoalVector(brightness=0.5, protect={"weight": 0.8})
        d = g.to_dict()
        assert d["brightness"] == 0.5
        assert d["protect"] == {"weight": 0.8}
        assert isinstance(d, dict)

    def test_custom_values(self):
        g = TimbralGoalVector(
            brightness=-0.3, warmth=0.7, movement=0.5, instability=0.2
        )
        assert g.brightness == -0.3
        assert g.warmth == 0.7


class TestPatchBlock:
    def test_valid_block_types(self):
        for bt in VALID_BLOCK_TYPES:
            b = PatchBlock(block_type=bt, device_name="Test")
            assert b.block_type == bt

    def test_invalid_block_type_raises(self):
        with pytest.raises(ValueError, match="Invalid block_type"):
            PatchBlock(block_type="invalid_type", device_name="Test")

    def test_to_dict(self):
        b = PatchBlock(block_type="filter", device_name="EQ Eight", controllable=True)
        d = b.to_dict()
        assert d["block_type"] == "filter"
        assert d["device_name"] == "EQ Eight"
        assert d["controllable"] is True


class TestPatchModel:
    def test_defaults(self):
        p = PatchModel()
        assert p.track_index == 0
        assert p.device_chain == []
        assert p.blocks == []

    def test_to_dict(self):
        p = PatchModel(
            track_index=3,
            device_chain=["Wavetable", "Saturator"],
            roles=["lead"],
            blocks=[
                PatchBlock(block_type="oscillator", device_name="Wavetable"),
                PatchBlock(block_type="saturation", device_name="Saturator"),
            ],
            opaque_blocks=[],
        )
        d = p.to_dict()
        assert d["track_index"] == 3
        assert len(d["blocks"]) == 2
        assert d["blocks"][0]["block_type"] == "oscillator"

    def test_to_dict_isolation(self):
        """to_dict returns a new dict, not a reference to internal state."""
        p = PatchModel(device_chain=["A"])
        d = p.to_dict()
        d["device_chain"].append("B")
        assert p.device_chain == ["A"]


class TestLayerStrategy:
    def test_defaults_are_none(self):
        ls = LayerStrategy()
        assert ls.sub_anchor is None
        assert ls.body_layer is None

    def test_to_dict(self):
        ls = LayerStrategy(sub_anchor=0, body_layer=1, width_layer=3)
        d = ls.to_dict()
        assert d["sub_anchor"] == 0
        assert d["transient_layer"] is None
        assert d["width_layer"] == 3


class TestSoundDesignState:
    def test_to_dict(self):
        state = SoundDesignState()
        d = state.to_dict()
        assert "goal" in d
        assert "patch" in d
        assert "layers" in d
        assert d["goal"]["brightness"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Critics
# ═══════════════════════════════════════════════════════════════════════


class TestSoundDesignIssue:
    def test_to_dict(self):
        issue = SoundDesignIssue(
            issue_type="test",
            critic="test_critic",
            severity=0.5,
            confidence=0.8,
        )
        d = issue.to_dict()
        assert d["issue_type"] == "test"
        assert d["severity"] == 0.5


class TestStaticTimbreCritic:
    def test_static_when_goal_wants_movement(self):
        patch = PatchModel(
            blocks=[
                PatchBlock(block_type="oscillator", device_name="Osc"),
                PatchBlock(block_type="filter", device_name="Filter"),
            ]
        )
        goal = TimbralGoalVector(movement=0.5)
        issues = run_static_timbre_critic(patch, goal)
        assert len(issues) >= 1
        assert issues[0].issue_type == "static_timbre"

    def test_no_issue_when_lfo_present(self):
        patch = PatchModel(
            blocks=[
                PatchBlock(block_type="oscillator", device_name="Osc"),
                PatchBlock(block_type="lfo", device_name="LFO"),
            ]
        )
        goal = TimbralGoalVector(movement=0.5)
        issues = run_static_timbre_critic(patch, goal)
        # Should not fire static_timbre
        static = [i for i in issues if i.issue_type == "static_timbre"]
        assert len(static) == 0

    def test_mild_issue_without_goal(self):
        patch = PatchModel(
            blocks=[
                PatchBlock(block_type="oscillator", device_name="Osc"),
            ]
        )
        goal = TimbralGoalVector()
        issues = run_static_timbre_critic(patch, goal)
        assert len(issues) >= 1
        assert issues[0].issue_type == "no_modulation_sources"
        assert issues[0].severity < 0.5

    def test_empty_patch_no_issue(self):
        patch = PatchModel(blocks=[])
        goal = TimbralGoalVector(movement=0.8)
        issues = run_static_timbre_critic(patch, goal)
        assert len(issues) == 0


class TestWeakIdentityCritic:
    def test_too_few_blocks(self):
        patch = PatchModel(
            device_chain=["Simpler"],
            blocks=[PatchBlock(block_type="oscillator", device_name="Simpler")],
        )
        issues = run_weak_identity_critic(patch)
        types = [i.issue_type for i in issues]
        assert "too_few_blocks" in types

    def test_generic_chain(self):
        patch = PatchModel(
            device_chain=["Osc", "Delay"],
            blocks=[
                PatchBlock(block_type="oscillator", device_name="Osc"),
                PatchBlock(block_type="spatial", device_name="Delay"),
            ],
        )
        issues = run_weak_identity_critic(patch)
        types = [i.issue_type for i in issues]
        assert "generic_chain" in types

    def test_no_issue_with_filter(self):
        patch = PatchModel(
            device_chain=["Osc", "Filter"],
            blocks=[
                PatchBlock(block_type="oscillator", device_name="Osc"),
                PatchBlock(block_type="filter", device_name="Filter"),
            ],
        )
        issues = run_weak_identity_critic(patch)
        types = [i.issue_type for i in issues]
        assert "generic_chain" not in types


class TestMaskingRoleCritic:
    def test_adjacent_roles_overlap(self):
        patch = PatchModel(track_index=0)
        layers = LayerStrategy(sub_anchor=0, body_layer=0)
        issues = run_masking_role_critic(patch, layers)
        assert len(issues) >= 1
        assert issues[0].issue_type == "frequency_role_overlap"

    def test_no_overlap_different_tracks(self):
        patch = PatchModel(track_index=0)
        layers = LayerStrategy(sub_anchor=0, body_layer=1)
        issues = run_masking_role_critic(patch, layers)
        assert len(issues) == 0


class TestModulationFlatnessCritic:
    def test_no_modulation_with_many_blocks(self):
        patch = PatchModel(
            blocks=[
                PatchBlock(block_type="oscillator", device_name="A"),
                PatchBlock(block_type="filter", device_name="B"),
                PatchBlock(block_type="saturation", device_name="C"),
            ]
        )
        issues = run_modulation_flatness_critic(patch)
        types = [i.issue_type for i in issues]
        assert "no_modulation" in types

    def test_no_lfo_but_has_envelope(self):
        patch = PatchModel(
            blocks=[
                PatchBlock(block_type="oscillator", device_name="A"),
                PatchBlock(block_type="filter", device_name="B"),
                PatchBlock(block_type="envelope", device_name="C"),
            ]
        )
        issues = run_modulation_flatness_critic(patch)
        types = [i.issue_type for i in issues]
        assert "no_lfo_movement" in types
        assert "no_modulation" not in types

    def test_no_issue_with_lfo(self):
        patch = PatchModel(
            blocks=[
                PatchBlock(block_type="oscillator", device_name="A"),
                PatchBlock(block_type="filter", device_name="B"),
                PatchBlock(block_type="lfo", device_name="C"),
            ]
        )
        issues = run_modulation_flatness_critic(patch)
        assert len(issues) == 0


class TestLayerOverlapCritic:
    def test_multi_role_track(self):
        layers = LayerStrategy(sub_anchor=0, body_layer=0, texture_layer=0)
        issues = run_layer_overlap_critic(layers)
        assert len(issues) >= 1
        assert issues[0].issue_type == "multi_role_track"

    def test_no_overlap(self):
        layers = LayerStrategy(sub_anchor=0, body_layer=1, texture_layer=2)
        issues = run_layer_overlap_critic(layers)
        assert len(issues) == 0

    def test_empty_layers(self):
        layers = LayerStrategy()
        issues = run_layer_overlap_critic(layers)
        assert len(issues) == 0


class TestRunAllCritics:
    def test_aggregates_issues(self):
        state = SoundDesignState(
            goal=TimbralGoalVector(movement=0.6),
            patch=PatchModel(
                track_index=0,
                device_chain=["Osc"],
                blocks=[PatchBlock(block_type="oscillator", device_name="Osc")],
            ),
            layers=LayerStrategy(sub_anchor=0, body_layer=0),
        )
        issues = run_all_sound_design_critics(state)
        critics = {i.critic for i in issues}
        # Should get issues from multiple critics
        assert len(issues) >= 2
        assert "static_timbre" in critics

    def test_clean_state_minimal_issues(self):
        state = SoundDesignState(
            goal=TimbralGoalVector(),
            patch=PatchModel(
                track_index=0,
                device_chain=["Wavetable", "Saturator", "Chorus"],
                blocks=[
                    PatchBlock(block_type="oscillator", device_name="Wavetable"),
                    PatchBlock(block_type="filter", device_name="Wavetable"),
                    PatchBlock(block_type="envelope", device_name="Wavetable"),
                    PatchBlock(block_type="lfo", device_name="Wavetable"),
                    PatchBlock(block_type="saturation", device_name="Saturator"),
                    PatchBlock(block_type="spatial", device_name="Chorus"),
                ],
            ),
            layers=LayerStrategy(body_layer=0),
        )
        issues = run_all_sound_design_critics(state)
        # Well-equipped patch should have minimal issues
        assert len(issues) <= 2


# ═══════════════════════════════════════════════════════════════════════
# Planner
# ═══════════════════════════════════════════════════════════════════════


class TestSoundDesignMove:
    def test_to_dict(self):
        m = SoundDesignMove(
            move_type="filter_contour",
            target_block="EQ Eight",
            description="test",
            estimated_impact=0.5,
            risk=0.1,
        )
        d = m.to_dict()
        assert d["move_type"] == "filter_contour"
        assert d["risk"] == 0.1


class TestPlanner:
    def test_empty_issues_returns_empty(self):
        state = SoundDesignState()
        moves = plan_sound_design_moves([], state)
        assert moves == []

    def test_moves_generated_from_issues(self):
        issues = [
            SoundDesignIssue(
                issue_type="static_timbre",
                critic="static_timbre",
                severity=0.7,
                confidence=0.8,
                affected_blocks=["Osc"],
                recommended_moves=["modulation_injection"],
            ),
        ]
        state = SoundDesignState()
        moves = plan_sound_design_moves(issues, state)
        assert len(moves) >= 1
        assert moves[0].move_type == "modulation_injection"
        assert moves[0].target_block == "Osc"

    def test_moves_ranked_by_impact(self):
        issues = [
            SoundDesignIssue(
                issue_type="low_priority",
                critic="test",
                severity=0.2,
                confidence=0.5,
                recommended_moves=["filter_contour"],
            ),
            SoundDesignIssue(
                issue_type="high_priority",
                critic="test",
                severity=0.9,
                confidence=0.9,
                recommended_moves=["source_balance"],
            ),
        ]
        state = SoundDesignState()
        moves = plan_sound_design_moves(issues, state)
        assert len(moves) == 2
        # Higher impact move should come first
        assert moves[0].estimated_impact > moves[1].estimated_impact

    def test_parameter_scope_preferred(self):
        """Parameter-level moves should be preferred over chain-level at equal impact."""
        issues = [
            SoundDesignIssue(
                issue_type="test_a",
                critic="test",
                severity=0.5,
                confidence=0.8,
                recommended_moves=["layer_split"],  # chain scope
            ),
            SoundDesignIssue(
                issue_type="test_b",
                critic="test",
                severity=0.5,
                confidence=0.8,
                recommended_moves=["filter_contour"],  # parameter scope
            ),
        ]
        state = SoundDesignState()
        moves = plan_sound_design_moves(issues, state)
        # filter_contour (parameter) should rank higher due to lower risk
        assert moves[0].move_type == "filter_contour"

    def test_all_move_types_recognized(self):
        """All six move types should produce valid moves."""
        move_types = [
            "source_balance", "filter_contour", "envelope_shape",
            "modulation_injection", "spatial_separation", "layer_split",
        ]
        for mt in move_types:
            issues = [
                SoundDesignIssue(
                    issue_type="test",
                    critic="test",
                    severity=0.5,
                    confidence=0.5,
                    recommended_moves=[mt],
                ),
            ]
            moves = plan_sound_design_moves(issues, SoundDesignState())
            assert len(moves) == 1
            assert moves[0].move_type == mt


# ─── BUG-B35 regressions — role-aware critic filtering ─────────────────────


class TestBugB35RoleAwareFiltering:
    """BUG-B35: analyze_sound_design used to flag 'too_few_blocks' and
    'no_modulation_sources' for simple kick/drum/bass patches — but a
    DS Kick + Saturator chain is textbook drum design, not weak identity.
    The fix filters role-sensitive critics based on track name keywords."""

    def test_simple_role_detection(self):
        """_is_simple_role_track should match percussion/kick/snare/bass
        names but not pads / leads / synths."""
        from mcp_server.sound_design.tools import _is_simple_role_track
        assert _is_simple_role_track("Kick")
        assert _is_simple_role_track("DS Kick")
        assert _is_simple_role_track("Snare Rim")
        assert _is_simple_role_track("Perc Hats")
        assert _is_simple_role_track("Sub Bass")
        assert not _is_simple_role_track("Pad Lush")
        assert not _is_simple_role_track("Lead Synth")
        assert not _is_simple_role_track("Wavetable 1")
        assert not _is_simple_role_track("Rhodes")

    def test_filter_drops_too_few_blocks_on_kick(self):
        """A kick track with too_few_blocks should have that issue
        filtered out, but other issues pass through."""
        from mcp_server.sound_design.tools import _filter_role_appropriate_issues
        issues = [
            SoundDesignIssue(issue_type="too_few_blocks", severity=0.5),
            SoundDesignIssue(issue_type="no_modulation_sources", severity=0.3),
            SoundDesignIssue(issue_type="masking_role", severity=0.6),
        ]
        filtered = _filter_role_appropriate_issues(issues, "Kick")
        filtered_types = {i.issue_type for i in filtered}
        assert "too_few_blocks" not in filtered_types
        assert "no_modulation_sources" not in filtered_types
        assert "masking_role" in filtered_types

    def test_filter_preserves_issues_on_pad_track(self):
        """Pad / Lead tracks SHOULD be flagged for simplicity — the
        filter only activates on drum-family names."""
        from mcp_server.sound_design.tools import _filter_role_appropriate_issues
        issues = [
            SoundDesignIssue(issue_type="too_few_blocks", severity=0.5),
            SoundDesignIssue(issue_type="no_modulation_sources", severity=0.3),
        ]
        filtered = _filter_role_appropriate_issues(issues, "Pad Lush")
        assert {i.issue_type for i in filtered} == {
            "too_few_blocks", "no_modulation_sources",
        }

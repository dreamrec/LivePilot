"""Tests for Agent OS V1 pure-computation engine."""

import pytest

from mcp_server.tools._agent_os_engine import (
    QUALITY_DIMENSIONS,
    GoalVector,
    Issue,
    WorldModel,
    build_world_model_from_data,
    compute_evaluation_score,
    infer_track_role,
    run_sonic_critic,
    run_technical_critic,
    validate_goal_vector,
)


# ── GoalVector validation ─────────────────────────────────────────────


class TestGoalVector:
    def test_valid_goal(self):
        gv = validate_goal_vector(
            request_text="make this hit harder",
            targets={"punch": 0.4, "weight": 0.3, "energy": 0.3},
            protect={"clarity": 0.8},
            mode="improve",
            aggression=0.5,
            research_mode="none",
        )
        assert gv.mode == "improve"
        assert abs(sum(gv.targets.values()) - 1.0) < 0.02

    def test_rejects_empty_request(self):
        with pytest.raises(ValueError, match="empty"):
            validate_goal_vector("", {"punch": 1.0}, {}, "improve", 0.5, "none")

    def test_rejects_unknown_dimension(self):
        with pytest.raises(ValueError, match="Unknown target"):
            validate_goal_vector("test", {"loudness": 1.0}, {}, "improve", 0.5, "none")

    def test_rejects_unknown_protect_dimension(self):
        with pytest.raises(ValueError, match="Unknown protect"):
            validate_goal_vector("test", {"punch": 1.0}, {"bass": 0.5}, "improve", 0.5, "none")

    def test_rejects_invalid_mode(self):
        with pytest.raises(ValueError, match="mode"):
            validate_goal_vector("test", {"punch": 1.0}, {}, "attack", 0.5, "none")

    def test_rejects_invalid_research_mode(self):
        with pytest.raises(ValueError, match="research_mode"):
            validate_goal_vector("test", {"punch": 1.0}, {}, "improve", 0.5, "wikipedia")

    def test_rejects_aggression_out_of_range(self):
        with pytest.raises(ValueError, match="aggression"):
            validate_goal_vector("test", {"punch": 1.0}, {}, "improve", 1.5, "none")

    def test_normalizes_weights(self):
        gv = validate_goal_vector("test", {"punch": 2.0, "weight": 3.0}, {}, "improve", 0.5, "none")
        assert abs(sum(gv.targets.values()) - 1.0) < 0.02

    def test_weight_range_validation(self):
        with pytest.raises(ValueError, match=">= 0.0"):
            validate_goal_vector("test", {"punch": -0.5}, {}, "improve", 0.5, "none")

    def test_to_dict(self):
        gv = validate_goal_vector("test", {"punch": 1.0}, {}, "improve", 0.5, "none")
        d = gv.to_dict()
        assert d["request_text"] == "test"
        assert "targets" in d

    def test_all_modes_accepted(self):
        for mode in ("observe", "improve", "explore", "finish", "diagnose"):
            gv = validate_goal_vector("test", {"punch": 1.0}, {}, mode, 0.5, "none")
            assert gv.mode == mode


# ── Track role inference ──────────────────────────────────────────────


class TestTrackRoleInference:
    def test_kick(self):
        assert infer_track_role("Kick") == "kick"
        assert infer_track_role("BD Deep") == "kick"
        assert infer_track_role("Bass Drum") == "kick"

    def test_bass(self):
        assert infer_track_role("Sub Bass") == "sub_bass"
        assert infer_track_role("Bass Synth") == "bass"

    def test_hihat(self):
        assert infer_track_role("Hats") == "hihat"
        assert infer_track_role("Hi-Hat") == "hihat"
        assert infer_track_role("HH Closed") == "hihat"

    def test_pad(self):
        assert infer_track_role("Pad") == "pad"
        assert infer_track_role("Atmosphere") == "pad"
        assert infer_track_role("Dark Atmo") == "pad"

    def test_lead(self):
        assert infer_track_role("Melody") == "lead"
        assert infer_track_role("Lead Synth") == "lead"

    def test_texture(self):
        assert infer_track_role("Tape") == "texture"
        assert infer_track_role("FX Riser") == "texture"
        assert infer_track_role("Noise Layer") == "texture"

    def test_unknown(self):
        assert infer_track_role("Track 42") == "unknown"
        assert infer_track_role("") == "unknown"


# ── WorldModel ────────────────────────────────────────────────────────


class TestWorldModel:
    def test_builds_from_session_info(self):
        session = {
            "tempo": 120,
            "signature_numerator": 4,
            "signature_denominator": 4,
            "track_count": 2,
            "return_track_count": 1,
            "scene_count": 4,
            "is_playing": False,
            "tracks": [
                {"index": 0, "name": "Kick", "has_midi_input": True,
                 "has_audio_input": False, "mute": False, "solo": False, "arm": False},
                {"index": 1, "name": "Bass", "has_midi_input": True,
                 "has_audio_input": False, "mute": False, "solo": False, "arm": False},
            ],
        }
        wm = build_world_model_from_data(session)
        assert wm.topology["tempo"] == 120
        assert wm.topology["track_count"] == 2
        assert wm.track_roles[0] == "kick"
        assert wm.track_roles[1] == "bass"
        assert wm.sonic is None  # No spectrum data

    def test_builds_with_sonic_data(self):
        session = {"tempo": 120, "tracks": [], "track_count": 0,
                    "return_track_count": 0, "scene_count": 0}
        spectrum = {"bands": {"sub": 0.5, "low": 0.4, "low_mid": 0.3,
                              "mid": 0.2, "high_mid": 0.1, "high": 0.1,
                              "presence": 0.05, "air": 0.02}}
        rms = {"rms": 0.6, "peak": 0.9}
        key = {"key": "C", "scale": "minor", "confidence": 80}

        wm = build_world_model_from_data(session, spectrum, rms, key)
        assert wm.sonic is not None
        assert wm.sonic["spectrum"]["sub"] == 0.5
        assert wm.sonic["rms"] == 0.6
        assert wm.sonic["key"] == "C"

    def test_degrades_without_analyzer(self):
        session = {"tempo": 120, "tracks": [], "track_count": 0,
                    "return_track_count": 0, "scene_count": 0}
        wm = build_world_model_from_data(session, spectrum=None)
        assert wm.sonic is None
        assert wm.technical["analyzer_available"] is False

    def test_detects_unhealthy_plugins(self):
        session = {"tempo": 120, "tracks": [], "track_count": 0,
                    "return_track_count": 0, "scene_count": 0}
        track_infos = [
            {"index": 0, "devices": [
                {"name": "DeadPlugin", "health_flags": ["opaque_or_failed_plugin"]},
            ]},
        ]
        wm = build_world_model_from_data(session, track_infos=track_infos)
        assert len(wm.technical["unhealthy_devices"]) == 1


# ── Sonic Critic ──────────────────────────────────────────────────────


class TestSonicCritic:
    def _make_goal(self, **targets):
        return GoalVector(
            request_text="test",
            targets=targets,
            mode="improve",
            aggression=0.5,
        )

    def test_returns_analyzer_unavailable_when_no_sonic(self):
        issues = run_sonic_critic(None, self._make_goal(punch=1.0), {})
        assert len(issues) == 1
        assert issues[0].type == "analyzer_unavailable"

    def test_detects_mud(self):
        sonic = {"spectrum": {"low_mid": 0.85}, "rms": 0.5, "peak": 0.7}
        issues = run_sonic_critic(sonic, self._make_goal(clarity=1.0), {})
        types = [i.type for i in issues]
        assert "low_mid_congestion" in types

    def test_no_mud_when_below_threshold(self):
        sonic = {"spectrum": {"low_mid": 0.5}, "rms": 0.5, "peak": 0.7}
        issues = run_sonic_critic(sonic, self._make_goal(clarity=1.0), {})
        types = [i.type for i in issues]
        assert "low_mid_congestion" not in types

    def test_detects_weak_sub(self):
        sonic = {"spectrum": {"sub": 0.05}, "rms": 0.5, "peak": 0.7}
        roles = {0: "kick", 1: "bass"}
        issues = run_sonic_critic(sonic, self._make_goal(weight=1.0), roles)
        types = [i.type for i in issues]
        assert "weak_foundation" in types

    def test_detects_harsh_highs(self):
        sonic = {"spectrum": {"high": 0.5, "presence": 0.4}, "rms": 0.5, "peak": 0.7}
        issues = run_sonic_critic(sonic, self._make_goal(brightness=1.0), {})
        types = [i.type for i in issues]
        assert "harsh_highs" in types

    def test_detects_headroom_risk(self):
        sonic = {"spectrum": {}, "rms": 0.95, "peak": 0.99}
        issues = run_sonic_critic(sonic, self._make_goal(energy=1.0), {})
        types = [i.type for i in issues]
        assert "headroom_risk" in types

    def test_only_fires_for_relevant_dimensions(self):
        sonic = {"spectrum": {"low_mid": 0.9}, "rms": 0.5, "peak": 0.7}
        # Goal targets "motion" which mud doesn't affect
        issues = run_sonic_critic(sonic, self._make_goal(motion=1.0), {})
        types = [i.type for i in issues]
        assert "low_mid_congestion" not in types


# ── Technical Critic ──────────────────────────────────────────────────


class TestTechnicalCritic:
    def test_detects_analyzer_offline(self):
        issues = run_technical_critic({"analyzer_available": False, "unhealthy_devices": []})
        types = [i.type for i in issues]
        assert "analyzer_offline" in types

    def test_clean_when_healthy(self):
        issues = run_technical_critic({"analyzer_available": True, "unhealthy_devices": []})
        assert len(issues) == 0

    def test_detects_unhealthy_plugin(self):
        issues = run_technical_critic({
            "analyzer_available": True,
            "unhealthy_devices": [{"track": 0, "device": "Dead", "flag": "opaque_or_failed_plugin"}],
        })
        types = [i.type for i in issues]
        assert "unhealthy_plugin" in types


# ── Evaluation Scorer ─────────────────────────────────────────────────


class TestEvaluationScorer:
    def _make_goal(self, **targets):
        return GoalVector(
            request_text="test", targets=targets, mode="improve", aggression=0.5,
        )

    def test_improvement_kept(self):
        goal = self._make_goal(weight=0.5, energy=0.5)
        before = {"spectrum": {"sub": 0.3, "low": 0.3}, "rms": 0.5, "peak": 0.7}
        after = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is True
        assert result["measurable_delta"] > 0

    def test_no_improvement_undone(self):
        goal = self._make_goal(weight=1.0)
        before = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        after = {"spectrum": {"sub": 0.4, "low": 0.4}, "rms": 0.5, "peak": 0.7}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is False
        assert "measurable delta <= 0" in str(result["notes"])

    def test_protected_dimension_violated_by_threshold(self):
        """C3 fix: protect threshold is now actually used."""
        goal = GoalVector(
            request_text="test",
            targets={"brightness": 1.0},
            protect={"weight": 0.4},  # weight must stay >= 0.4
            mode="improve",
            aggression=0.5,
        )
        before = {"spectrum": {"sub": 0.6, "low": 0.6, "high": 0.3, "presence": 0.3},
                  "rms": 0.5, "peak": 0.7}
        # Weight drops to 0.1 (below threshold 0.4)
        after = {"spectrum": {"sub": 0.1, "low": 0.1, "high": 0.6, "presence": 0.6},
                 "rms": 0.5, "peak": 0.7}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is False
        assert "PROTECTED" in str(result["notes"])
        assert "below threshold" in str(result["notes"])

    def test_protected_dimension_violated_by_large_drop(self):
        """Even if still above threshold, a large drop (>0.15) triggers undo."""
        goal = GoalVector(
            request_text="test",
            targets={"brightness": 1.0},
            protect={"weight": 0.1},  # lenient threshold
            mode="improve",
            aggression=0.5,
        )
        before = {"spectrum": {"sub": 0.6, "low": 0.6, "high": 0.3, "presence": 0.3},
                  "rms": 0.5, "peak": 0.7}
        # Weight drops by 0.2 (> 0.15) but stays above 0.1 threshold
        after = {"spectrum": {"sub": 0.4, "low": 0.4, "high": 0.5, "presence": 0.5},
                 "rms": 0.5, "peak": 0.7}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is False
        assert "drop" in str(result["notes"])

    def test_unmeasurable_defers_to_agent(self):
        goal = self._make_goal(groove=0.5, tension=0.5)
        before = {"spectrum": {}, "rms": 0.5, "peak": 0.7}
        after = {"spectrum": {}, "rms": 0.5, "peak": 0.7}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is True  # Defers to agent
        assert "not measurable" in str(result["notes"])

    def test_score_below_threshold(self):
        goal = self._make_goal(weight=1.0)
        before = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        # Tiny negative change
        after = {"spectrum": {"sub": 0.49, "low": 0.49}, "rms": 0.59, "peak": 0.79}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is False

    def test_width_not_in_measurable_proxies(self):
        """P4: width is NOT measurable in Phase 1 — it must not be in MEASURABLE_PROXIES."""
        from mcp_server.tools._agent_os_engine import MEASURABLE_PROXIES
        assert "width" not in MEASURABLE_PROXIES, \
            "width should not be in MEASURABLE_PROXIES until stereo analysis is in the snapshot"

    def test_consecutive_undo_hint(self):
        """I5: evaluate_move returns consecutive_undo_hint for agent tracking."""
        goal = self._make_goal(weight=1.0)
        before = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        after = {"spectrum": {"sub": 0.3, "low": 0.3}, "rms": 0.4, "peak": 0.6}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is False
        assert result["consecutive_undo_hint"] is True

    def test_consecutive_undo_hint_false_on_keep(self):
        goal = self._make_goal(weight=0.5, energy=0.5)
        before = {"spectrum": {"sub": 0.3, "low": 0.3}, "rms": 0.5, "peak": 0.7}
        after = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is True
        assert result["consecutive_undo_hint"] is False

    def test_protection_overrides_unmeasurable_defer(self):
        """Finding 1: protection violations must not be overridden by unmeasurable defer."""
        goal = GoalVector(
            request_text="test",
            targets={"groove": 1.0},  # unmeasurable
            protect={"weight": 0.4},  # measurable + protected
            mode="improve",
            aggression=0.5,
        )
        before = {"spectrum": {"sub": 0.6, "low": 0.6}, "rms": 0.5, "peak": 0.7}
        # Weight drops to 0.1, well below threshold 0.4
        after = {"spectrum": {"sub": 0.1, "low": 0.1}, "rms": 0.5, "peak": 0.7}
        result = compute_evaluation_score(goal, before, after)
        assert result["keep_change"] is False, \
            "Protection violation must force undo even when all targets are unmeasurable"
        assert "PROTECTED" in str(result["notes"])

    def test_snapshot_accepts_bands_key(self):
        """Finding 2: evaluator must accept 'bands' key (raw get_master_spectrum output)."""
        goal = GoalVector(
            request_text="test",
            targets={"energy": 1.0},
            mode="improve",
            aggression=0.5,
        )
        # Use "bands" key instead of "spectrum" — this is what get_master_spectrum returns
        before = {"bands": {"sub": 0.3, "low": 0.3}, "rms": 0.5, "peak": 0.7}
        after = {"bands": {"sub": 0.3, "low": 0.3}, "rms": 0.7, "peak": 0.9}
        result = compute_evaluation_score(goal, before, after)
        assert result["measurable_dimensions"] > 0, \
            "Evaluator should accept 'bands' key from raw get_master_spectrum output"
        assert result["keep_change"] is True

    def test_density_uses_geometric_mean(self):
        """P1: density should use spectral flatness, not simple mean."""
        from mcp_server.tools._agent_os_engine import _extract_dimension_value
        # Uniform distribution → flatness close to 1.0
        uniform = {"spectrum": {"sub": 0.5, "low": 0.5, "mid": 0.5, "high": 0.5}, "rms": 0.5}
        # Concentrated distribution → flatness close to 0.0
        peaked = {"spectrum": {"sub": 0.9, "low": 0.01, "mid": 0.01, "high": 0.01}, "rms": 0.5}
        uniform_density = _extract_dimension_value(uniform, "density")
        peaked_density = _extract_dimension_value(peaked, "density")
        assert uniform_density > peaked_density, \
            "Uniform spectrum should have higher density than peaked"

    def test_dimension_changes_tracked(self):
        goal = self._make_goal(energy=1.0)
        # energy maps to rms — spectrum must have at least one band for sonic to be "present"
        before = {"spectrum": {"sub": 0.5}, "rms": 0.5, "peak": 0.7}
        after = {"spectrum": {"sub": 0.5}, "rms": 0.7, "peak": 0.9}
        result = compute_evaluation_score(goal, before, after)
        assert "energy" in result["dimension_changes"]
        assert result["dimension_changes"]["energy"]["delta"] > 0

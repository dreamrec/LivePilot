"""Tests for the Safety Kernel — policy enforcement layer."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.safety_kernel import (
    SafetyCheck,
    check_action_safety,
    check_batch_safety,
    is_read_only_action,
    get_max_safe_scope,
    BLOCKED_ACTIONS,
    CONFIRM_REQUIRED_ACTIONS,
    SAFE_ACTIONS,
)


# ── TestBlockedActions ────────────────────────────────────────────


class TestBlockedActions:
    def test_delete_all_tracks_blocked(self):
        r = check_action_safety("delete_all_tracks")
        assert not r.allowed
        assert r.risk_level == "blocked"

    def test_delete_all_clips_blocked(self):
        r = check_action_safety("delete_all_clips")
        assert not r.allowed
        assert r.risk_level == "blocked"

    def test_delete_all_scenes_blocked(self):
        r = check_action_safety("delete_all_scenes")
        assert not r.allowed
        assert r.risk_level == "blocked"

    def test_clear_all_automation_blocked(self):
        r = check_action_safety("clear_all_automation")
        assert not r.allowed
        assert r.risk_level == "blocked"

    def test_reset_all_devices_blocked(self):
        r = check_action_safety("reset_all_devices")
        assert not r.allowed
        assert r.risk_level == "blocked"
        assert not r.requires_confirmation


# ── TestConfirmRequired ───────────────────────────────────────────


class TestConfirmRequired:
    def test_delete_track_needs_confirmation(self):
        r = check_action_safety("delete_track")
        assert r.allowed
        assert r.risk_level == "caution"
        assert r.requires_confirmation

    def test_delete_clip_needs_confirmation(self):
        r = check_action_safety("delete_clip")
        assert r.allowed
        assert r.requires_confirmation

    def test_flatten_needs_confirmation(self):
        r = check_action_safety("flatten_track")
        assert r.allowed
        assert r.requires_confirmation

    def test_replace_simpler_sample_needs_confirmation(self):
        r = check_action_safety("replace_simpler_sample")
        assert r.allowed
        assert r.requires_confirmation

    def test_delete_scene_needs_confirmation(self):
        r = check_action_safety("delete_scene")
        assert r.allowed
        assert r.requires_confirmation


# ── TestSafeActions ───────────────────────────────────────────────


class TestSafeActions:
    def test_get_session_info_safe(self):
        r = check_action_safety("get_session_info")
        assert r.allowed
        assert r.risk_level == "safe"
        assert not r.requires_confirmation

    def test_get_notes_safe(self):
        r = check_action_safety("get_notes")
        assert r.allowed
        assert r.risk_level == "safe"

    def test_analyze_harmony_safe(self):
        r = check_action_safety("analyze_harmony")
        assert r.allowed
        assert r.risk_level == "safe"

    def test_all_safe_actions_allowed(self):
        for action in SAFE_ACTIONS:
            r = check_action_safety(action)
            assert r.allowed, f"{action} should be allowed"
            assert r.risk_level == "safe", f"{action} should be safe"


# ── TestScopeCheck ────────────────────────────────────────────────


class TestScopeCheck:
    def test_wide_scope_triggers_caution(self):
        r = check_action_safety("set_track_volume", scope={"track_count": 10})
        assert r.allowed
        assert r.risk_level == "caution"
        assert r.requires_confirmation

    def test_narrow_scope_is_safe(self):
        r = check_action_safety("set_track_volume", scope={"track_count": 2})
        assert r.allowed
        assert r.risk_level == "safe"
        assert not r.requires_confirmation

    def test_threshold_boundary(self):
        # Exactly 5 should be safe, 6 should trigger caution
        r5 = check_action_safety("set_track_volume", scope={"track_count": 5})
        assert r5.risk_level == "safe"
        r6 = check_action_safety("set_track_volume", scope={"track_count": 6})
        assert r6.risk_level == "caution"


# ── TestCapabilityGating ──────────────────────────────────────────


class TestCapabilityGating:
    def test_read_only_blocks_mutations(self):
        r = check_action_safety(
            "set_tempo",
            capability_state={"mode": "read_only"},
        )
        assert not r.allowed
        assert r.risk_level == "blocked"

    def test_read_only_allows_reads(self):
        r = check_action_safety(
            "get_session_info",
            capability_state={"mode": "read_only"},
        )
        assert r.allowed
        assert r.risk_level == "safe"

    def test_normal_allows_mutations(self):
        r = check_action_safety(
            "set_tempo",
            capability_state={"mode": "normal"},
        )
        assert r.allowed

    def test_measured_degraded_limits_scope(self):
        r = check_action_safety(
            "set_track_volume",
            scope={"track_count": 5},
            capability_state={"mode": "measured_degraded"},
        )
        assert not r.allowed
        assert r.risk_level == "blocked"

    def test_judgment_only_limits_scope(self):
        r = check_action_safety(
            "set_track_volume",
            scope={"track_count": 2},
            capability_state={"mode": "judgment_only"},
        )
        assert not r.allowed
        assert r.risk_level == "blocked"


# ── TestBatchSafety ───────────────────────────────────────────────


class TestBatchSafety:
    def test_mixed_batch_returns_per_action_results(self):
        batch = [
            {"action": "get_session_info"},
            {"action": "delete_all_tracks"},
            {"action": "delete_track"},
        ]
        results = check_batch_safety(batch)
        assert len(results) == 3
        assert results[0].allowed and results[0].risk_level == "safe"
        assert not results[1].allowed and results[1].risk_level == "blocked"
        assert results[2].allowed and results[2].requires_confirmation

    def test_empty_batch(self):
        assert check_batch_safety([]) == []

    def test_batch_with_scope(self):
        batch = [
            {"action": "set_track_volume", "scope": {"track_count": 10}},
            {"action": "set_track_volume", "scope": {"track_count": 1}},
        ]
        results = check_batch_safety(batch)
        assert results[0].risk_level == "caution"
        assert results[1].risk_level == "safe"


# ── TestReadOnlyClassification ────────────────────────────────────


class TestReadOnlyClassification:
    def test_get_prefix_is_read_only(self):
        assert is_read_only_action("get_session_info")
        assert is_read_only_action("get_anything")

    def test_set_prefix_is_not_read_only(self):
        assert not is_read_only_action("set_tempo")
        assert not is_read_only_action("set_track_volume")

    def test_analyze_prefix_is_read_only(self):
        assert is_read_only_action("analyze_harmony")

    def test_delete_is_not_read_only(self):
        assert not is_read_only_action("delete_track")

    def test_create_is_not_read_only(self):
        assert not is_read_only_action("create_midi_track")


# ── TestMaxSafeScope ──────────────────────────────────────────────


class TestMaxSafeScope:
    def test_normal_unlimited(self):
        s = get_max_safe_scope("normal")
        assert s["max_tracks"] == 0

    def test_measured_degraded(self):
        s = get_max_safe_scope("measured_degraded")
        assert s["max_tracks"] == 3

    def test_judgment_only(self):
        s = get_max_safe_scope("judgment_only")
        assert s["max_tracks"] == 1

    def test_unknown_mode_defaults_to_normal(self):
        s = get_max_safe_scope("unknown_mode")
        assert s["max_tracks"] == 0


# ── TestSafetyCheckDataclass ──────────────────────────────────────


class TestSafetyCheckDataclass:
    def test_to_dict(self):
        sc = SafetyCheck(
            action="test",
            allowed=True,
            risk_level="safe",
            reason="ok",
            requires_confirmation=False,
        )
        d = sc.to_dict()
        assert d["action"] == "test"
        assert d["allowed"] is True
        assert d["risk_level"] == "safe"

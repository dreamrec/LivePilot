"""Comprehensive tests for Mix Engine V1."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.mix_engine.models import (
    BalanceState,
    DepthState,
    DynamicsState,
    MaskingEntry,
    MaskingMap,
    MixState,
    StereoState,
    TrackMixState,
)
from mcp_server.mix_engine.state_builder import (
    build_balance_state,
    build_dynamics_state,
    build_masking_map,
    build_mix_state,
)
from mcp_server.mix_engine.critics import (
    MixIssue,
    run_all_mix_critics,
    run_balance_critic,
    run_depth_critic,
    run_dynamics_critic,
    run_masking_critic,
    run_stereo_critic,
    run_translation_critic,
)
from mcp_server.mix_engine.planner import MixMove, plan_mix_moves


# ── TestMixModels ───────────────────────────────────────────────────


class TestMixModels:
    def test_track_mix_state_to_dict(self):
        t = TrackMixState(track_index=0, name="Kick", role="kick", volume=0.8)
        d = t.to_dict()
        assert d["track_index"] == 0
        assert d["name"] == "Kick"
        assert d["role"] == "kick"
        assert d["volume"] == 0.8

    def test_balance_state_to_dict(self):
        t = TrackMixState(track_index=0, name="Kick", role="kick")
        bs = BalanceState(track_states=[t], anchor_tracks=[0], loudest_track=0, quietest_track=0)
        d = bs.to_dict()
        assert len(d["track_states"]) == 1
        assert d["anchor_tracks"] == [0]

    def test_masking_entry_to_dict(self):
        e = MaskingEntry(track_a=0, track_b=1, overlap_band="sub", severity=0.7)
        d = e.to_dict()
        assert d["overlap_band"] == "sub"
        assert d["severity"] == 0.7

    def test_masking_map_to_dict(self):
        e = MaskingEntry(track_a=0, track_b=1, overlap_band="sub", severity=0.7)
        mm = MaskingMap(entries=[e], worst_pair=(0, 1))
        d = mm.to_dict()
        assert d["worst_pair"] == [0, 1]
        assert len(d["entries"]) == 1

    def test_masking_map_none_worst_pair(self):
        mm = MaskingMap(entries=[], worst_pair=None)
        d = mm.to_dict()
        assert d["worst_pair"] is None

    def test_dynamics_state_to_dict(self):
        ds = DynamicsState(crest_factor_db=12.0, over_compressed=False, headroom=6.0)
        d = ds.to_dict()
        assert d["crest_factor_db"] == 12.0
        assert d["headroom"] == 6.0

    def test_stereo_state_to_dict(self):
        ss = StereoState(center_strength=0.6, side_activity=0.3, mono_risk=False)
        d = ss.to_dict()
        assert d["center_strength"] == 0.6
        assert d["mono_risk"] is False

    def test_depth_state_to_dict(self):
        ds = DepthState(wet_dry_ratio=0.3, depth_separation=0.1, wash_risk=False)
        d = ds.to_dict()
        assert d["wet_dry_ratio"] == 0.3
        assert d["wash_risk"] is False

    def test_mix_state_to_dict(self):
        ms = MixState()
        d = ms.to_dict()
        assert "balance" in d
        assert "masking" in d
        assert "dynamics" in d
        assert "stereo" in d
        assert "depth" in d


# ── TestStateBuilder ────────────────────────────────────────────────


class TestStateBuilder:
    def test_build_balance_state_basic(self):
        tracks = [
            {"index": 0, "name": "Kick", "volume": 0.8, "pan": 0.0, "mute": False, "solo": False},
            {"index": 1, "name": "Bass", "volume": 0.7, "pan": 0.0, "mute": False, "solo": False},
            {"index": 2, "name": "Pad", "volume": 0.5, "pan": -0.3, "mute": False, "solo": False},
        ]
        roles = {0: "kick", 1: "bass", 2: "pad"}
        bs = build_balance_state(tracks, roles)
        assert len(bs.track_states) == 3
        assert 0 in bs.anchor_tracks
        assert 1 in bs.anchor_tracks
        assert 2 not in bs.anchor_tracks

    def test_build_balance_state_empty(self):
        bs = build_balance_state([], {})
        assert len(bs.track_states) == 0
        assert bs.loudest_track == -1

    def test_build_masking_map_with_roles(self):
        roles = {0: "kick", 1: "bass"}
        mm = build_masking_map({"bands": {}}, roles)
        assert len(mm.entries) > 0
        assert mm.worst_pair is not None

    def test_build_masking_map_empty(self):
        mm = build_masking_map(None, None)
        assert len(mm.entries) == 0
        assert mm.worst_pair is None

    def test_build_dynamics_state_normal(self):
        ds = build_dynamics_state(rms=0.1, peak=0.5)
        assert ds.crest_factor_db > 0
        assert ds.over_compressed is False

    def test_build_dynamics_state_compressed(self):
        ds = build_dynamics_state(rms=0.5, peak=0.55)
        assert ds.over_compressed is True
        assert ds.crest_factor_db < 6.0

    def test_build_dynamics_state_none(self):
        ds = build_dynamics_state(rms=None, peak=None)
        assert ds.crest_factor_db == 0.0

    def test_build_mix_state_full(self):
        tracks = [
            {"index": 0, "name": "Kick", "volume": 0.8, "pan": 0.0, "mute": False, "solo": False},
        ]
        ms = build_mix_state(
            session_info={"tempo": 120},
            track_infos=tracks,
            rms_data=0.1,
        )
        assert len(ms.balance.track_states) == 1

    def test_build_mix_state_missing_data(self):
        ms = build_mix_state()
        assert len(ms.balance.track_states) == 0
        assert ms.dynamics.crest_factor_db == 0.0


# ── TestBalanceCritic ───────────────────────────────────────────────


class TestBalanceCritic:
    def test_detects_anchor_too_weak(self):
        tracks = [
            TrackMixState(track_index=0, name="Kick", role="kick", volume=0.1, mute=False),
            TrackMixState(track_index=1, name="Bass", role="bass", volume=0.8, mute=False),
            TrackMixState(track_index=2, name="Pad", role="pad", volume=0.8, mute=False),
        ]
        bs = BalanceState(
            track_states=tracks,
            anchor_tracks=[0, 1],
            loudest_track=1,
            quietest_track=0,
        )
        issues = run_balance_critic(bs)
        types = [i.issue_type for i in issues]
        assert "anchor_too_weak" in types

    def test_no_issues_when_balanced(self):
        tracks = [
            TrackMixState(track_index=0, name="Kick", role="kick", volume=0.7, mute=False),
            TrackMixState(track_index=1, name="Bass", role="bass", volume=0.7, mute=False),
        ]
        bs = BalanceState(
            track_states=tracks,
            anchor_tracks=[0, 1],
            loudest_track=0,
            quietest_track=1,
        )
        issues = run_balance_critic(bs)
        assert len(issues) == 0


# ── TestMaskingCritic ───────────────────────────────────────────────


class TestMaskingCritic:
    def test_detects_collisions(self):
        entries = [
            MaskingEntry(track_a=0, track_b=1, overlap_band="sub", severity=0.7),
            MaskingEntry(track_a=0, track_b=1, overlap_band="low", severity=0.6),
        ]
        mm = MaskingMap(entries=entries, worst_pair=(0, 1))
        issues = run_masking_critic(mm)
        assert len(issues) == 2
        assert all(i.issue_type == "frequency_collision" for i in issues)

    def test_no_issues_when_clean(self):
        mm = MaskingMap(entries=[], worst_pair=None)
        issues = run_masking_critic(mm)
        assert len(issues) == 0

    def test_skips_low_severity(self):
        entries = [
            MaskingEntry(track_a=0, track_b=1, overlap_band="mid", severity=0.2),
        ]
        mm = MaskingMap(entries=entries, worst_pair=(0, 1))
        issues = run_masking_critic(mm)
        assert len(issues) == 0


# ── TestDynamicsCritic ──────────────────────────────────────────────


class TestDynamicsCritic:
    def test_over_compression(self):
        ds = DynamicsState(crest_factor_db=4.0, over_compressed=True, headroom=6.0)
        issues = run_dynamics_critic(ds)
        types = [i.issue_type for i in issues]
        assert "over_compressed" in types

    def test_flat_dynamics(self):
        """flat_dynamics fires when crest < 3.0 and not already over_compressed."""
        ds = DynamicsState(crest_factor_db=2.0, over_compressed=False, headroom=6.0)
        issues = run_dynamics_critic(ds)
        types = [i.issue_type for i in issues]
        assert "flat_dynamics" in types

    def test_over_compressed_does_not_double_count_flat(self):
        """over_compressed and flat_dynamics should not both fire (no double-counting)."""
        ds = DynamicsState(crest_factor_db=2.0, over_compressed=True, headroom=6.0)
        issues = run_dynamics_critic(ds)
        types = [i.issue_type for i in issues]
        assert "over_compressed" in types
        assert "flat_dynamics" not in types

    def test_headroom_risk(self):
        ds = DynamicsState(crest_factor_db=12.0, over_compressed=False, headroom=0.5)
        issues = run_dynamics_critic(ds)
        types = [i.issue_type for i in issues]
        assert "low_headroom" in types

    def test_healthy_dynamics(self):
        ds = DynamicsState(crest_factor_db=14.0, over_compressed=False, headroom=6.0)
        issues = run_dynamics_critic(ds)
        assert len(issues) == 0


# ── TestStereoCritic ────────────────────────────────────────────────


class TestStereoCritic:
    def test_center_collapse(self):
        ss = StereoState(center_strength=0.9, side_activity=0.02, mono_risk=True)
        issues = run_stereo_critic(ss)
        types = [i.issue_type for i in issues]
        assert "center_collapse" in types

    def test_overwide(self):
        ss = StereoState(center_strength=0.2, side_activity=0.8, mono_risk=False)
        issues = run_stereo_critic(ss)
        types = [i.issue_type for i in issues]
        assert "overwide" in types

    def test_healthy_stereo(self):
        ss = StereoState(center_strength=0.5, side_activity=0.3, mono_risk=False)
        issues = run_stereo_critic(ss)
        assert len(issues) == 0


# ── TestDepthCritic ─────────────────────────────────────────────────


class TestDepthCritic:
    def test_no_separation(self):
        ds = DepthState(wet_dry_ratio=0.3, depth_separation=0.02, wash_risk=False)
        issues = run_depth_critic(ds)
        types = [i.issue_type for i in issues]
        assert "no_depth_separation" in types

    def test_excessive_wash(self):
        ds = DepthState(wet_dry_ratio=0.8, depth_separation=0.2, wash_risk=True)
        issues = run_depth_critic(ds)
        types = [i.issue_type for i in issues]
        assert "excessive_wash" in types

    def test_healthy_depth(self):
        ds = DepthState(wet_dry_ratio=0.3, depth_separation=0.15, wash_risk=False)
        issues = run_depth_critic(ds)
        assert len(issues) == 0


# ── TestTranslationCritic ──────────────────────────────────────────


class TestTranslationCritic:
    def test_mono_risk(self):
        dyn = DynamicsState(crest_factor_db=12.0, over_compressed=False, headroom=6.0)
        stereo = StereoState(center_strength=0.2, side_activity=0.7, mono_risk=False)
        issues = run_translation_critic(dyn, stereo)
        types = [i.issue_type for i in issues]
        assert "mono_weakness" in types

    def test_harshness(self):
        dyn = DynamicsState(crest_factor_db=4.0, over_compressed=True, headroom=1.0)
        stereo = StereoState(center_strength=0.5, side_activity=0.3, mono_risk=False)
        issues = run_translation_critic(dyn, stereo)
        types = [i.issue_type for i in issues]
        assert "harshness_risk" in types

    def test_no_translation_issues(self):
        dyn = DynamicsState(crest_factor_db=14.0, over_compressed=False, headroom=6.0)
        stereo = StereoState(center_strength=0.5, side_activity=0.3, mono_risk=False)
        issues = run_translation_critic(dyn, stereo)
        assert len(issues) == 0


# ── TestRunAllCritics ──────────────────────────────────────────────


class TestRunAllCritics:
    def test_aggregates_all_critics(self):
        ms = MixState(
            balance=BalanceState(
                track_states=[
                    TrackMixState(track_index=0, name="Kick", role="kick", volume=0.1, mute=False),
                    TrackMixState(track_index=1, name="Pad", role="pad", volume=0.8, mute=False),
                ],
                anchor_tracks=[0],
                loudest_track=1,
                quietest_track=0,
            ),
            masking=MaskingMap(
                entries=[MaskingEntry(0, 1, "sub", 0.7)],
                worst_pair=(0, 1),
            ),
            dynamics=DynamicsState(crest_factor_db=4.0, over_compressed=True, headroom=0.5),
            stereo=StereoState(center_strength=0.9, side_activity=0.02, mono_risk=True),
            depth=DepthState(wet_dry_ratio=0.8, depth_separation=0.01, wash_risk=True),
        )
        issues = run_all_mix_critics(ms)
        critics_found = {i.critic for i in issues}
        # Should have issues from multiple critics
        assert len(critics_found) >= 3

    def test_empty_state_no_crash(self):
        ms = MixState()
        issues = run_all_mix_critics(ms)
        assert isinstance(issues, list)


# ── TestMixPlanner ──────────────────────────────────────────────────


class TestMixPlanner:
    def test_ranks_moves(self):
        issues = [
            MixIssue(
                issue_type="over_compressed",
                critic="dynamics",
                severity=0.8,
                confidence=0.7,
                affected_tracks=[],
                evidence="test",
                recommended_moves=["bus_compression", "transient_shaping"],
            ),
            MixIssue(
                issue_type="anchor_too_weak",
                critic="balance",
                severity=0.6,
                confidence=0.7,
                affected_tracks=[0],
                evidence="test",
                recommended_moves=["gain_staging"],
            ),
        ]
        ms = MixState()
        moves = plan_mix_moves(issues, ms)
        assert len(moves) == 3
        # First move should have highest impact * (1 - risk)
        scores = [m.estimated_impact * (1 - m.risk) for m in moves]
        assert scores == sorted(scores, reverse=True)

    def test_prefers_track_level(self):
        issues = [
            MixIssue(
                issue_type="test",
                critic="test",
                severity=0.5,
                confidence=0.8,
                affected_tracks=[0],
                evidence="test",
                recommended_moves=["gain_staging", "bus_compression"],
            ),
        ]
        ms = MixState()
        moves = plan_mix_moves(issues, ms)
        # gain_staging (track-level) should come before bus_compression
        assert moves[0].move_type == "gain_staging"

    def test_empty_for_no_issues(self):
        moves = plan_mix_moves([], MixState())
        assert moves == []


# ── TestMixMove ─────────────────────────────────────────────────────


class TestMixMove:
    def test_to_dict(self):
        m = MixMove(
            move_type="eq_correction",
            target_tracks=[0, 1],
            description="fix masking",
            estimated_impact=0.5,
            risk=0.1,
            parameters={"source_issue": "frequency_collision"},
        )
        d = m.to_dict()
        assert d["move_type"] == "eq_correction"
        assert d["target_tracks"] == [0, 1]
        assert d["estimated_impact"] == 0.5
        assert d["risk"] == 0.1
        assert "source_issue" in d["parameters"]


# ── TestMixIssue ────────────────────────────────────────────────────


class TestMixIssue:
    def test_to_dict(self):
        i = MixIssue(
            issue_type="anchor_too_weak",
            critic="balance",
            severity=0.7,
            confidence=0.6,
            affected_tracks=[0],
            evidence="Kick too quiet",
            recommended_moves=["gain_staging"],
        )
        d = i.to_dict()
        assert d["issue_type"] == "anchor_too_weak"
        assert d["severity"] == 0.7
        assert d["recommended_moves"] == ["gain_staging"]

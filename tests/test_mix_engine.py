"""Comprehensive tests for Mix Engine V1."""

import math
import sys
import os

import pytest

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
        assert d["analysis_scope"] == "mix_setup_audit"
        assert d["evidence"]["stereo"] == "pan_position_proxy"
        assert d["evidence"]["depth"] == "send_level_proxy"

    def test_mix_state_labels_measured_and_heuristic_masking(self):
        ms = MixState(masking=MaskingMap(entries=[
            MaskingEntry(track_a=0, track_b=1, measured=True),
            MaskingEntry(track_a=2, track_b=3, measured=False),
        ]))
        evidence = ms.evidence_summary()
        assert evidence["analysis_scope"] == "per_track_audio_and_mix_setup"
        assert evidence["masking"] == "mixed_per_track_audio_and_role_heuristic"
        assert evidence["measured_masking_entries"] == 1
        assert evidence["heuristic_masking_entries"] == 1


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

    # ── P2-25: spectral-overlap severity scaling ────────────────────

    def test_masking_heuristic_labels_master_only_spectrum(self):
        """Master-bus-only spectrum → severity_basis='role_heuristic', measured=False."""
        roles = {0: "kick", 1: "bass"}
        # No "tracks" key → master-only shape
        mm = build_masking_map({"bands": {"sub": 0.9, "low": 0.7}}, roles)
        assert len(mm.entries) > 0
        for entry in mm.entries:
            assert entry.measured is False
            assert entry.severity_basis == "role_heuristic"
        # Severity must equal the role-prior constant (e.g. kick/bass/sub = 0.7)
        sub_entries = [e for e in mm.entries if e.overlap_band == "sub"]
        assert sub_entries, "Expected kick/bass sub collision"
        assert sub_entries[0].severity == pytest.approx(0.7)

    def test_masking_spectral_scaling_with_per_track_data(self):
        """Per-track spectrum: severity is scaled by actual band overlap.

        Kick with high sub energy (0.9) + Bass with high sub energy (0.8):
        overlap = sqrt(0.9 * 0.8) ≈ 0.849 → severity = 0.7 * 0.849 ≈ 0.594.
        Must be measured=True and severity_basis='spectral_overlap'.
        """
        roles = {0: "kick", 1: "bass"}
        spectrum = {
            "tracks": {
                "0": {"sub": 0.9, "low": 0.8, "low_mid": 0.3},
                "1": {"sub": 0.8, "low": 0.7, "low_mid": 0.4},
            }
        }
        mm = build_masking_map(spectrum, roles)
        sub_entries = [e for e in mm.entries if e.overlap_band == "sub"]
        assert sub_entries, "Expected kick/bass sub collision"
        e = sub_entries[0]
        assert e.measured is True
        assert e.severity_basis == "spectral_overlap"
        expected = 0.7 * math.sqrt(0.9 * 0.8)
        assert e.severity == pytest.approx(expected, rel=1e-6)

    def test_masking_eq_separated_tracks_produce_near_zero_severity(self):
        """EQ-separated kick and bass: kick has sub energy, bass has NONE.

        overlap = sqrt(0.9 * 0.0) = 0 → severity = 0.7 * 0 = 0.0.
        The collision entry must still exist but severity is effectively zero
        so it won't trigger the masking critic (threshold 0.4).
        """
        roles = {0: "kick", 1: "bass"}
        spectrum = {
            "tracks": {
                "0": {"sub": 0.9, "low": 0.8},   # kick has sub energy
                "1": {"sub": 0.0, "low": 0.0, "low_mid": 0.7},  # bass EQ'd out of sub
            }
        }
        mm = build_masking_map(spectrum, roles)
        sub_entries = [e for e in mm.entries if e.overlap_band == "sub"]
        assert sub_entries, "Entry must still exist even when overlap is zero"
        assert sub_entries[0].severity == pytest.approx(0.0, abs=1e-9)
        assert sub_entries[0].measured is True
        # Critic must NOT fire for a zero-severity entry
        from mcp_server.mix_engine.critics import run_masking_critic
        issues = run_masking_critic(mm)
        sub_issues = [i for i in issues if "sub" in i.evidence]
        assert len(sub_issues) == 0

    def test_masking_per_track_missing_one_side_falls_back_to_heuristic(self):
        """If per-track data exists for track 0 but not track 1, fall back to heuristic."""
        roles = {0: "kick", 1: "bass"}
        spectrum = {
            "tracks": {
                "0": {"sub": 0.9},
                # track 1 absent → no data for bass
            }
        }
        mm = build_masking_map(spectrum, roles)
        for entry in mm.entries:
            assert entry.measured is False
            assert entry.severity_basis == "role_heuristic"

    def test_build_dynamics_state_normal(self):
        ds = build_dynamics_state(rms=0.1, peak=0.5)
        assert ds.crest_factor_db > 0
        assert ds.over_compressed is False

    def test_build_dynamics_state_compressed(self):
        # crest ~4 dB lands in the over-compressed band [3, 6); below 3 dB the
        # (now-reachable) flat_dynamics critic takes over instead of over_compressed.
        ds = build_dynamics_state(rms=0.5, peak=0.79)
        assert ds.over_compressed is True
        assert 3.0 <= ds.crest_factor_db < 6.0

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

    def test_build_mix_state_uses_inferred_roles_for_masking(self):
        tracks = [
            {"index": 0, "name": "Kick", "volume": 0.8, "pan": 0.0, "mute": False, "solo": False},
            {"index": 1, "name": "Sub Bass", "volume": 0.7, "pan": 0.0, "mute": False, "solo": False},
        ]
        ms = build_mix_state(track_infos=tracks, spectrum={"bands": {"sub": 0.8}})
        assert len(ms.masking.entries) > 0
        assert ms.masking.worst_pair == (0, 1)

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

def test_flat_dynamics_fires_through_production_pipeline():
    """Extremely flat audio (crest < 3 dB) must surface flat_dynamics, not over_compressed.

    Regression for the dead-code bug: build_dynamics_state set
    over_compressed = crest < 6.0, which made the critic's `elif crest < 3.0`
    (flat_dynamics) branch unreachable for any real signal. This drives the
    actual production path (build_dynamics_state -> run_dynamics_critic).
    """
    # rms=0.5, peak=0.63 -> crest ~= 2.0 dB (well under 3 dB)
    ds = build_dynamics_state(rms=0.5, peak=0.63)
    assert ds.crest_factor_db < 3.0
    assert ds.over_compressed is False  # below 3 dB must NOT be tagged over_compressed
    issues = run_dynamics_critic(ds)
    types = {i.issue_type for i in issues}
    assert "flat_dynamics" in types
    assert "over_compressed" not in types


def test_over_compressed_band_still_fires():
    """Mid-flat audio (3 dB <= crest < 6 dB) must still flag over_compressed.

    Guards against the fix over-correcting and silencing the over_compressed
    warning for genuinely over-compressed (but not extreme) material.
    """
    # rms=0.5, peak=0.84 -> crest ~= 4.5 dB (in the 3-6 dB over_compressed band)
    ds = build_dynamics_state(rms=0.5, peak=0.84)
    assert 3.0 <= ds.crest_factor_db < 6.0
    assert ds.over_compressed is True
    issues = run_dynamics_critic(ds)
    types = {i.issue_type for i in issues}
    assert "over_compressed" in types
    assert "flat_dynamics" not in types


# ── TestConfidenceDerivation ─────────────────────────────────────────
#
# Confidence values must be data-derived, not decorative flat literals.
# These tests pin the modulation direction (more/better data -> higher
# confidence) and the [0.3, 0.95] bounds, without over-specifying exact
# numbers so the formula can be tuned later.


class TestConfidenceDerivation:
    def test_balance_confidence_scales_with_active_track_count(self):
        """anchor_too_weak confidence should be higher when the average it's
        compared against is backed by more tracks."""
        few_tracks = [
            TrackMixState(track_index=0, name="Kick", role="kick", volume=0.1),
            TrackMixState(track_index=1, name="Bass", role="bass", volume=0.8),
        ]
        many_tracks = few_tracks + [
            TrackMixState(track_index=i, name=f"T{i}", role="pad", volume=0.8)
            for i in range(2, 8)
        ]
        few_issues = run_balance_critic(BalanceState(
            track_states=few_tracks, anchor_tracks=[0, 1],
            loudest_track=1, quietest_track=0,
        ))
        many_issues = run_balance_critic(BalanceState(
            track_states=many_tracks, anchor_tracks=[0, 1],
            loudest_track=1, quietest_track=0,
        ))
        few_conf = next(i.confidence for i in few_issues if i.issue_type == "anchor_too_weak")
        many_conf = next(i.confidence for i in many_issues if i.issue_type == "anchor_too_weak")
        assert many_conf > few_conf
        assert 0.3 <= few_conf <= 0.95
        assert 0.3 <= many_conf <= 0.95

    def test_masking_confidence_higher_when_measured(self):
        """Real per-track spectral overlap should earn a higher confidence
        than a role-pair heuristic prior with identical severity."""
        measured_entry = MaskingEntry(
            track_a=0, track_b=1, overlap_band="sub", severity=0.6, measured=True,
            severity_basis="spectral_overlap",
        )
        heuristic_entry = MaskingEntry(
            track_a=0, track_b=1, overlap_band="sub", severity=0.6, measured=False,
            severity_basis="role_heuristic",
        )
        measured_issue = run_masking_critic(MaskingMap(entries=[measured_entry]))[0]
        heuristic_issue = run_masking_critic(MaskingMap(entries=[heuristic_entry]))[0]
        assert measured_issue.confidence > heuristic_issue.confidence
        assert 0.3 <= heuristic_issue.confidence <= 0.95
        assert 0.3 <= measured_issue.confidence <= 0.95

    def test_dynamics_confidence_higher_at_band_center_than_edge(self):
        """over_compressed confidence should be highest at the center of the
        3-6dB band and discounted near either edge."""
        edge = build_dynamics_state(rms=0.5, peak=10 ** (3.01 / 20) * 0.5)  # crest ~3.01
        center = build_dynamics_state(rms=0.5, peak=10 ** (4.5 / 20) * 0.5)  # crest ~4.5
        edge_issue = next(i for i in run_dynamics_critic(edge) if i.issue_type == "over_compressed")
        center_issue = next(i for i in run_dynamics_critic(center) if i.issue_type == "over_compressed")
        assert center_issue.confidence > edge_issue.confidence
        assert 0.3 <= edge_issue.confidence <= 0.95

    def test_dynamics_low_headroom_confidence_scales_with_depth(self):
        shallow = DynamicsState(crest_factor_db=10.0, over_compressed=False, headroom=0.95)
        deep = DynamicsState(crest_factor_db=10.0, over_compressed=False, headroom=0.05)
        shallow_conf = next(i.confidence for i in run_dynamics_critic(shallow) if i.issue_type == "low_headroom")
        deep_conf = next(i.confidence for i in run_dynamics_critic(deep) if i.issue_type == "low_headroom")
        assert deep_conf > shallow_conf
        assert 0.3 <= shallow_conf <= 0.95

    def test_dynamics_context_loud_master_suppresses_over_compressed(self):
        """context={"target_style": "loud_master"} must suppress the
        over_compressed flag entirely — deliberately loud masters target
        this exact crest band by design."""
        ds = DynamicsState(crest_factor_db=4.5, over_compressed=True, headroom=6.0)
        default_issues = run_dynamics_critic(ds)
        loud_master_issues = run_dynamics_critic(ds, context={"target_style": "loud_master"})
        assert any(i.issue_type == "over_compressed" for i in default_issues)
        assert not any(i.issue_type == "over_compressed" for i in loud_master_issues)

    def test_dynamics_over_compressed_evidence_states_the_assumption(self):
        """Even without context, the evidence string must state the dynamic-
        mix-target assumption so a reader doesn't over-trust the flag for a
        style that intentionally sits in the 3-6dB crest band."""
        ds = DynamicsState(crest_factor_db=4.5, over_compressed=True, headroom=6.0)
        issue = next(i for i in run_dynamics_critic(ds) if i.issue_type == "over_compressed")
        assert "assumes" in issue.evidence.lower()

    def test_run_all_mix_critics_forwards_dynamics_context(self):
        """run_all_mix_critics must thread an optional dynamics_context
        through without requiring callers to pass it (default-preserving)."""
        ms = MixState(dynamics=DynamicsState(crest_factor_db=4.5, over_compressed=True, headroom=6.0))
        default_issues = run_all_mix_critics(ms)
        suppressed_issues = run_all_mix_critics(ms, dynamics_context={"target_style": "loud_master"})
        assert any(i.issue_type == "over_compressed" for i in default_issues)
        assert not any(i.issue_type == "over_compressed" for i in suppressed_issues)

    def test_stereo_and_depth_and_translation_confidence_scale_with_margin(self):
        """Deep-in-the-flagged-region measurements should out-confidence
        barely-past-threshold ones for stereo/depth/translation critics."""
        deep_mono = run_stereo_critic(StereoState(center_strength=0.99, side_activity=0.0, mono_risk=True))[0]
        edge_mono = run_stereo_critic(StereoState(center_strength=0.86, side_activity=0.049, mono_risk=True))[0]
        assert deep_mono.confidence > edge_mono.confidence

        deep_wash = run_depth_critic(DepthState(wet_dry_ratio=1.0, depth_separation=0.2, wash_risk=True))[0]
        edge_wash = run_depth_critic(DepthState(wet_dry_ratio=0.61, depth_separation=0.2, wash_risk=True))[0]
        assert deep_wash.confidence > edge_wash.confidence

        dyn = DynamicsState(crest_factor_db=14.0, over_compressed=False, headroom=6.0)
        deep_translation = run_translation_critic(
            dyn, StereoState(center_strength=0.0, side_activity=1.0, mono_risk=False),
        )[0]
        edge_translation = run_translation_critic(
            dyn, StereoState(center_strength=0.29, side_activity=0.51, mono_risk=False),
        )[0]
        assert deep_translation.confidence > edge_translation.confidence

    def test_confidence_never_leaves_bounds(self):
        """Spot-check bounds across a spread of critics/inputs."""
        all_issues = []
        all_issues += run_balance_critic(BalanceState(
            track_states=[
                TrackMixState(track_index=0, name="Kick", role="kick", volume=0.01),
                TrackMixState(track_index=1, name="Bass", role="bass", volume=1.0),
            ],
            anchor_tracks=[0, 1], loudest_track=1, quietest_track=0,
        ))
        all_issues += run_masking_critic(MaskingMap(entries=[
            MaskingEntry(track_a=0, track_b=1, overlap_band="sub", severity=1.0, measured=True),
        ]))
        all_issues += run_dynamics_critic(DynamicsState(
            crest_factor_db=0.01, over_compressed=False, headroom=0.0,
        ))
        for issue in all_issues:
            assert 0.3 <= issue.confidence <= 0.95, (issue.issue_type, issue.confidence)

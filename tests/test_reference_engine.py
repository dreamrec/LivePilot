"""Tests for Reference Engine V1 — profiles, gap analysis, tactic routing.

~20 tests covering models, profile builders, gap analyzer, tactic router.
All pure-function tests, no I/O.
"""

from __future__ import annotations

import math

import pytest

from mcp_server.reference_engine.models import (
    GapEntry,
    GapReport,
    ReferencePlan,
    ReferenceProfile,
)
from mcp_server.reference_engine.profile_builder import (
    build_audio_reference_profile,
    build_style_reference_profile,
)
from mcp_server.reference_engine.gap_analyzer import (
    analyze_gaps,
    classify_gap_relevance,
    detect_identity_warnings,
)
from mcp_server.reference_engine.tactic_router import (
    build_reference_plan,
    route_to_engines,
)


# ── Model tests ────────────────────────────────────────────────────


class TestReferenceProfile:
    def test_default_source_type(self):
        p = ReferenceProfile()
        assert p.source_type == "audio"

    def test_to_dict_roundtrip(self):
        p = ReferenceProfile(
            source_type="style",
            loudness_posture=-14.0,
            spectral_contour={"centroid": 2000},
            harmonic_character="warm_harmonic",
            transition_tendencies=["reveal", "drift"],
        )
        d = p.to_dict()
        assert d["source_type"] == "style"
        assert d["loudness_posture"] == -14.0
        assert d["harmonic_character"] == "warm_harmonic"
        assert len(d["transition_tendencies"]) == 2

    def test_to_dict_has_all_fields(self):
        d = ReferenceProfile().to_dict()
        expected_keys = {
            "source_type", "loudness_posture", "spectral_contour",
            "width_depth", "density_arc", "section_pacing",
            "harmonic_character", "transition_tendencies",
        }
        assert set(d.keys()) == expected_keys


class TestGapEntry:
    def test_to_dict(self):
        g = GapEntry(domain="spectral", delta=0.05, relevant=True)
        d = g.to_dict()
        assert d["domain"] == "spectral"
        assert d["delta"] == 0.05

    def test_defaults(self):
        g = GapEntry()
        assert g.relevant is True
        assert g.identity_warning is False


class TestGapReport:
    def test_relevant_gaps_property(self):
        report = GapReport(
            reference_id="test",
            gaps=[
                GapEntry(domain="loudness", delta=2.0, relevant=True),
                GapEntry(domain="width", delta=0.01, relevant=False),
                GapEntry(domain="spectral", delta=0.05, relevant=True),
            ],
        )
        assert len(report.relevant_gaps) == 2
        assert all(g.relevant for g in report.relevant_gaps)

    def test_identity_warnings_property(self):
        report = GapReport(
            reference_id="test",
            gaps=[
                GapEntry(domain="harmonic", delta=1.0, identity_warning=True),
                GapEntry(domain="loudness", delta=2.0, identity_warning=False),
            ],
        )
        warnings = report.identity_warnings
        assert len(warnings) == 1
        assert "harmonic" in warnings[0]

    def test_to_dict_includes_computed_properties(self):
        report = GapReport(
            reference_id="test_ref",
            gaps=[GapEntry(domain="loudness", delta=3.0, relevant=True)],
            overall_distance=3.0,
        )
        d = report.to_dict()
        assert "relevant_gaps" in d
        assert "identity_warnings" in d
        assert d["overall_distance"] == 3.0
        assert len(d["relevant_gaps"]) == 1


class TestReferencePlan:
    def test_to_dict(self):
        plan = ReferencePlan(
            gap_report=GapReport(reference_id="r1"),
            ranked_tactics=[{"rank": 1, "tactic": "EQ cut"}],
            target_engines=["mix_engine"],
        )
        d = plan.to_dict()
        assert d["target_engines"] == ["mix_engine"]
        assert len(d["ranked_tactics"]) == 1
        assert d["gap_report"]["reference_id"] == "r1"


# ── Profile builder tests ─────────────────────────────────────────


class TestBuildAudioProfile:
    def test_basic_audio_profile(self):
        comparison = {
            "reference_lufs": -14.0,
            "centroid_delta_hz": 200.0,
            "stereo_width_ref": 0.25,
            "band_deltas": {"sub_60hz": 0.01, "mid_2khz": -0.03},
        }
        p = build_audio_reference_profile(comparison)
        assert p.source_type == "audio"
        assert p.loudness_posture == -14.0
        assert p.width_depth["stereo_width"] == 0.25
        assert "band_balance" in p.spectral_contour

    def test_missing_fields_default_gracefully(self):
        p = build_audio_reference_profile({})
        assert p.source_type == "audio"
        assert p.loudness_posture == 0.0
        assert p.spectral_contour["band_balance"] == {}


class TestBuildStyleProfile:
    def test_empty_tactics(self):
        p = build_style_reference_profile([])
        assert p.source_type == "style"
        assert p.transition_tendencies == []

    def test_single_tactic(self):
        tactic = {
            "artist_or_genre": "techno",
            "tactic_name": "rolling_groove",
            "arrangement_patterns": ["long_intro_16bars", "minimal_variation"],
            "device_chain": [{"name": "Compressor"}, {"name": "Delay"}],
            "automation_gestures": ["drift", "release"],
        }
        p = build_style_reference_profile([tactic])
        assert p.source_type == "style"
        assert "drift" in p.transition_tendencies
        assert "release" in p.transition_tendencies
        assert len(p.section_pacing) == 2
        assert len(p.density_arc) == 1

    def test_harmonic_character_inference(self):
        tactic = {
            "artist_or_genre": "ambient",
            "tactic_name": "texture_bed",
            "arrangement_patterns": [],
            "device_chain": [
                {"name": "Reverb"},
                {"name": "Auto Filter"},
            ],
            "automation_gestures": [],
        }
        p = build_style_reference_profile([tactic])
        assert p.harmonic_character == "atmospheric_filtered"


# ── Gap analyzer tests ─────────────────────────────────────────────


class TestAnalyzeGaps:
    def test_loudness_gap(self):
        snapshot = {"loudness": -10.0}
        ref = ReferenceProfile(loudness_posture=-14.0)
        report = analyze_gaps(snapshot, ref)
        loudness_gaps = [g for g in report.gaps if g.domain == "loudness"]
        assert len(loudness_gaps) == 1
        assert loudness_gaps[0].delta == pytest.approx(4.0, abs=0.01)

    def test_spectral_gap(self):
        snapshot = {"spectral": {"band_balance": {"mid_2khz": 0.3}}}
        ref = ReferenceProfile(
            spectral_contour={"band_balance": {"mid_2khz": 0.2}},
        )
        report = analyze_gaps(snapshot, ref)
        spectral_gaps = [g for g in report.gaps if g.domain == "spectral"]
        assert len(spectral_gaps) == 1
        assert spectral_gaps[0].delta == pytest.approx(0.1, abs=0.001)

    def test_width_gap(self):
        snapshot = {"width": 0.4}
        ref = ReferenceProfile(width_depth={"stereo_width": 0.2})
        report = analyze_gaps(snapshot, ref)
        width_gaps = [g for g in report.gaps if g.domain == "width"]
        assert len(width_gaps) == 1
        assert width_gaps[0].delta == pytest.approx(0.2, abs=0.001)

    def test_harmonic_gap_identity_warning(self):
        snapshot = {"harmonic_character": "diatonic_major"}
        ref = ReferenceProfile(harmonic_character="minor_modal")
        report = analyze_gaps(snapshot, ref)
        harmonic_gaps = [g for g in report.gaps if g.domain == "harmonic"]
        assert len(harmonic_gaps) == 1
        assert harmonic_gaps[0].identity_warning is True

    def test_empty_snapshot_and_ref(self):
        report = analyze_gaps({}, ReferenceProfile())
        assert report.overall_distance == 0.0

    def test_overall_distance_positive(self):
        snapshot = {"loudness": -8.0, "width": 0.5}
        ref = ReferenceProfile(
            loudness_posture=-14.0,
            width_depth={"stereo_width": 0.1},
        )
        report = analyze_gaps(snapshot, ref)
        assert report.overall_distance > 0


class TestClassifyGapRelevance:
    def test_with_goal_dimensions(self):
        gap = GapEntry(domain="spectral", delta=0.05, relevant=True)
        assert classify_gap_relevance(gap, ["spectral", "width"]) is True
        assert classify_gap_relevance(gap, ["loudness"]) is False

    def test_empty_goal_keeps_original(self):
        gap = GapEntry(domain="spectral", delta=0.05, relevant=False)
        assert classify_gap_relevance(gap, []) is False


class TestDetectIdentityWarnings:
    def test_warns_on_identity_gaps(self):
        gaps = [
            GapEntry(domain="harmonic", delta=1.0, identity_warning=True),
            GapEntry(domain="loudness", delta=3.0, identity_warning=False),
        ]
        warnings = detect_identity_warnings(gaps)
        assert len(warnings) == 1
        assert "harmonic" in warnings[0]

    def test_no_warnings(self):
        gaps = [GapEntry(domain="loudness", delta=3.0, identity_warning=False)]
        assert detect_identity_warnings(gaps) == []


# ── Tactic router tests ───────────────────────────────────────────


class TestRouteToEngines:
    def test_spectral_routes_to_mix(self):
        report = GapReport(
            reference_id="test",
            gaps=[GapEntry(domain="spectral", delta=0.05, relevant=True)],
        )
        routes = route_to_engines(report)
        assert len(routes) == 1
        assert routes[0]["engine"] == "mix_engine"

    def test_pacing_routes_to_composition(self):
        report = GapReport(
            reference_id="test",
            gaps=[GapEntry(domain="pacing", delta=3.0, relevant=True)],
        )
        routes = route_to_engines(report)
        assert routes[0]["engine"] == "composition"

    def test_irrelevant_gaps_excluded(self):
        report = GapReport(
            reference_id="test",
            gaps=[
                GapEntry(domain="spectral", delta=0.05, relevant=False),
                GapEntry(domain="loudness", delta=3.0, relevant=True),
            ],
        )
        routes = route_to_engines(report)
        assert len(routes) == 1
        assert routes[0]["domain"] == "loudness"

    def test_sorted_by_priority(self):
        report = GapReport(
            reference_id="test",
            gaps=[
                GapEntry(domain="loudness", delta=1.5, relevant=True),
                GapEntry(domain="spectral", delta=0.1, relevant=True),
            ],
        )
        routes = route_to_engines(report)
        assert routes[0]["priority"] >= routes[1]["priority"]


class TestBuildReferencePlan:
    def test_plan_has_all_components(self):
        report = GapReport(
            reference_id="test",
            gaps=[
                GapEntry(domain="spectral", delta=0.05, relevant=True,
                         suggested_tactic="EQ cut"),
                GapEntry(domain="pacing", delta=2.0, relevant=True,
                         suggested_tactic="Add sections"),
            ],
        )
        plan = build_reference_plan(report)
        assert len(plan.ranked_tactics) == 2
        assert "mix_engine" in plan.target_engines
        assert "composition" in plan.target_engines

    def test_plan_to_dict(self):
        report = GapReport(reference_id="r1")
        plan = build_reference_plan(report)
        d = plan.to_dict()
        assert "gap_report" in d
        assert "ranked_tactics" in d
        assert "target_engines" in d

    def test_identity_warned_gaps_deprioritized(self):
        report = GapReport(
            reference_id="test",
            gaps=[
                GapEntry(domain="harmonic", delta=1.0, relevant=True,
                         identity_warning=True, suggested_tactic="Reharmonize"),
                GapEntry(domain="loudness", delta=8.0, relevant=True,
                         identity_warning=False, suggested_tactic="Gain up"),
            ],
        )
        plan = build_reference_plan(report)
        # Loudness should rank higher despite harmonic having delta=1.0
        assert plan.ranked_tactics[0]["domain"] == "loudness"

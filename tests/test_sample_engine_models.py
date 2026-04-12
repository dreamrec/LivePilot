"""Tests for Sample Engine data models — pure dataclass tests, no I/O."""

from __future__ import annotations

import pytest

from mcp_server.sample_engine.models import (
    SampleProfile,
    SampleIntent,
    CriticResult,
    SampleFitReport,
    SampleCandidate,
    SampleTechnique,
    TechniqueStep,
    VALID_MATERIAL_TYPES,
    VALID_INTENTS,
    VALID_SIMPLER_MODES,
    VALID_SLICE_METHODS,
    VALID_WARP_MODES,
)


class TestSampleProfile:
    def test_defaults(self):
        p = SampleProfile(source="browser", file_path="/tmp/test.wav", name="test")
        assert p.source == "browser"
        assert p.key is None
        assert p.key_confidence == 0.0
        assert p.material_type == "unknown"
        assert p.suggested_mode == "classic"

    def test_to_dict(self):
        p = SampleProfile(source="filesystem", file_path="/a/b.wav", name="b",
                          key="Cm", key_confidence=0.8, bpm=120.0)
        d = p.to_dict()
        assert isinstance(d, dict)
        assert d["key"] == "Cm"
        assert d["bpm"] == 120.0

    def test_material_types_valid(self):
        for mt in VALID_MATERIAL_TYPES:
            p = SampleProfile(source="test", file_path="/t.wav", name="t",
                              material_type=mt)
            assert p.material_type == mt


class TestSampleIntent:
    def test_defaults(self):
        i = SampleIntent(intent_type="rhythm", description="chop it")
        assert i.philosophy == "auto"
        assert i.target_track is None

    def test_to_dict(self):
        i = SampleIntent(intent_type="texture", philosophy="alchemist",
                         description="stretch into pad")
        d = i.to_dict()
        assert d["intent_type"] == "texture"
        assert d["philosophy"] == "alchemist"


class TestCriticResult:
    def test_rating_from_score(self):
        r = CriticResult(critic_name="key_fit", score=0.9,
                         recommendation="load directly")
        assert r.rating == "excellent"

    def test_rating_boundaries(self):
        assert CriticResult(critic_name="t", score=0.85, recommendation="").rating == "excellent"
        assert CriticResult(critic_name="t", score=0.7, recommendation="").rating == "good"
        assert CriticResult(critic_name="t", score=0.5, recommendation="").rating == "fair"
        assert CriticResult(critic_name="t", score=0.2, recommendation="").rating == "poor"


class TestSampleFitReport:
    def test_overall_score_computed(self):
        critics = {
            "key_fit": CriticResult(critic_name="key_fit", score=1.0, recommendation=""),
            "tempo_fit": CriticResult(critic_name="tempo_fit", score=0.8, recommendation=""),
        }
        report = SampleFitReport(
            sample=SampleProfile(source="test", file_path="/t.wav", name="t"),
            critics=critics,
            recommended_intent="rhythm",
            recommended_technique="slice_and_sequence",
        )
        assert report.overall_score > 0.0
        assert isinstance(report.warnings, list)


class TestSampleCandidate:
    def test_creation(self):
        c = SampleCandidate(source="freesound", name="vocal_Cm_120",
                            metadata={"key": "Cm", "bpm": 120})
        assert c.source == "freesound"

    def test_to_dict(self):
        c = SampleCandidate(source="browser", name="kick", metadata={})
        d = c.to_dict()
        assert d["source"] == "browser"


class TestSampleTechnique:
    def test_creation(self):
        t = SampleTechnique(
            technique_id="slice_and_sequence",
            name="Slice & Sequence",
            philosophy="surgeon",
            material_types=["drum_loop"],
            intents=["rhythm"],
            difficulty="basic",
            description="Classic MPC-style slice and sequence",
            inspiration="MPC workflow",
            steps=[TechniqueStep(tool="set_simpler_playback_mode",
                                 params={"playback_mode": 2},
                                 description="Set to Slice mode")],
        )
        assert t.technique_id == "slice_and_sequence"
        assert len(t.steps) == 1

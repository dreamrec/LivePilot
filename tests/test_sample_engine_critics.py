"""Tests for Sample Engine critics — pure computation, no I/O."""

from __future__ import annotations

import pytest

from types import SimpleNamespace

from mcp_server.sample_engine.critics import (
    run_key_fit_critic,
    run_tempo_fit_critic,
    run_frequency_fit_critic,
    run_role_fit_critic,
    run_vibe_fit_critic,
    run_intent_fit_critic,
    run_all_sample_critics,
)
from mcp_server.sample_engine.models import (
    SampleProfile,
    SampleIntent,
    CriticResult,
)


def _make_profile(**kwargs) -> SampleProfile:
    defaults = {"source": "test", "file_path": "/t.wav", "name": "test"}
    defaults.update(kwargs)
    return SampleProfile(**defaults)


class TestKeyFitCritic:
    def test_same_key_perfect_score(self):
        r = run_key_fit_critic(_make_profile(key="Cm"), song_key="Cm")
        assert r.score == 1.0

    def test_relative_major_minor(self):
        r = run_key_fit_critic(_make_profile(key="Eb"), song_key="Cm")
        assert r.score >= 0.8

    def test_fifth_relationship(self):
        r = run_key_fit_critic(_make_profile(key="Gm"), song_key="Cm")
        assert r.score >= 0.6

    def test_distant_key_low_score(self):
        r = run_key_fit_critic(_make_profile(key="F#"), song_key="C")
        assert r.score <= 0.5

    def test_unknown_key_zero(self):
        r = run_key_fit_critic(_make_profile(key=None), song_key="Cm")
        assert r.score == 0.0

    def test_no_song_key_neutral(self):
        r = run_key_fit_critic(_make_profile(key="Cm"), song_key=None)
        assert r.score == 0.5


class TestTempoFitCritic:
    def test_exact_match(self):
        r = run_tempo_fit_critic(_make_profile(bpm=128.0), session_tempo=128.0)
        assert r.score >= 0.95

    def test_half_time(self):
        r = run_tempo_fit_critic(_make_profile(bpm=64.0), session_tempo=128.0)
        assert r.score >= 0.85

    def test_double_time(self):
        r = run_tempo_fit_critic(_make_profile(bpm=256.0), session_tempo=128.0)
        assert r.score >= 0.85

    def test_close_bpm(self):
        r = run_tempo_fit_critic(_make_profile(bpm=132.0), session_tempo=128.0)
        assert r.score >= 0.6

    def test_far_bpm(self):
        r = run_tempo_fit_critic(_make_profile(bpm=80.0), session_tempo=140.0)
        assert r.score <= 0.4

    def test_unknown_bpm_zero(self):
        r = run_tempo_fit_critic(_make_profile(bpm=None), session_tempo=128.0)
        assert r.score == 0.0


class TestRoleFitCritic:
    def test_fills_missing_role(self):
        r = run_role_fit_critic(
            _make_profile(material_type="vocal"),
            existing_roles=["drums", "bass", "synth"],
        )
        assert r.score >= 0.8

    def test_redundant_role(self):
        r = run_role_fit_critic(
            _make_profile(material_type="drum_loop"),
            existing_roles=["drums", "percussion", "hihat"],
        )
        assert r.score <= 0.5


class TestVibeFitCritic:
    def test_no_taste_graph_neutral(self):
        r = run_vibe_fit_critic(_make_profile(), taste_graph=None)
        assert r.score == 0.5

    def test_zero_evidence_neutral(self):
        tg = SimpleNamespace(evidence_count=0, novelty_band=0.5)
        r = run_vibe_fit_critic(_make_profile(), taste_graph=tg)
        assert r.score == 0.5

    def test_high_energy_high_novelty_good_fit(self):
        tg = SimpleNamespace(evidence_count=10, novelty_band=0.9)
        profile = _make_profile(brightness=0.9, transient_density=0.8)
        r = run_vibe_fit_critic(profile, taste_graph=tg)
        assert r.score >= 0.7

    def test_low_energy_high_novelty_poor_fit(self):
        tg = SimpleNamespace(evidence_count=10, novelty_band=0.9)
        profile = _make_profile(brightness=0.1, transient_density=0.1)
        r = run_vibe_fit_critic(profile, taste_graph=tg)
        assert r.score <= 0.5

    def test_low_energy_low_novelty_good_fit(self):
        tg = SimpleNamespace(evidence_count=10, novelty_band=0.1)
        profile = _make_profile(brightness=0.1, transient_density=0.1)
        r = run_vibe_fit_critic(profile, taste_graph=tg)
        assert r.score >= 0.7

    def test_score_always_in_range(self):
        tg = SimpleNamespace(evidence_count=5, novelty_band=0.5)
        profile = _make_profile(brightness=0.5, transient_density=0.5)
        r = run_vibe_fit_critic(profile, taste_graph=tg)
        assert 0.0 <= r.score <= 1.0


class TestIntentFitCritic:
    def test_perfect_match(self):
        r = run_intent_fit_critic(
            _make_profile(material_type="drum_loop"),
            intent=SampleIntent(intent_type="rhythm", description=""),
        )
        assert r.score >= 0.8

    def test_creative_mismatch(self):
        r = run_intent_fit_critic(
            _make_profile(material_type="vocal"),
            intent=SampleIntent(intent_type="rhythm", description=""),
        )
        # Vocal for rhythm is unusual but possible (chop workflow)
        assert 0.4 <= r.score <= 0.8


class TestRunAllCritics:
    def test_returns_all_six(self):
        results = run_all_sample_critics(
            profile=_make_profile(key="Cm", bpm=128.0, material_type="vocal"),
            intent=SampleIntent(intent_type="vocal", description=""),
            song_key="Cm",
            session_tempo=128.0,
            existing_roles=["drums", "bass"],
        )
        assert "key_fit" in results
        assert "tempo_fit" in results
        assert "frequency_fit" in results
        assert "role_fit" in results
        assert "vibe_fit" in results
        assert "intent_fit" in results
        assert all(isinstance(v, CriticResult) for v in results.values())

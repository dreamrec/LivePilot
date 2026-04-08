"""Tests for Translation Engine V1 — playback robustness intelligence."""

import pytest

from mcp_server.translation_engine.models import TranslationReport
from mcp_server.translation_engine.critics import (
    TranslationIssue,
    build_translation_report,
    run_all_translation_critics,
    run_front_element_critic,
    run_harshness_critic,
    run_low_end_instability_critic,
    run_mono_collapse_critic,
    run_small_speaker_critic,
)


# ── TranslationReport Model ──────────────────────────────────────


class TestTranslationReport:
    def test_default_report_is_robust(self):
        report = TranslationReport()
        assert report.mono_safe is True
        assert report.small_speaker_safe is True
        assert report.harshness_risk == 0.0
        assert report.low_end_stable is True
        assert report.front_element_present is True
        assert report.overall_robustness == "robust"

    def test_to_dict(self):
        report = TranslationReport(
            mono_safe=False,
            overall_robustness="critical",
            issues=[{"type": "test"}],
            suggested_moves=["fix_it"],
        )
        d = report.to_dict()
        assert d["mono_safe"] is False
        assert d["overall_robustness"] == "critical"
        assert d["issues"] == [{"type": "test"}]
        assert d["suggested_moves"] == ["fix_it"]


# ── TranslationIssue Model ───────────────────────────────────────


class TestTranslationIssue:
    def test_to_dict(self):
        issue = TranslationIssue(
            issue_type="mono_collapse",
            critic="mono_collapse",
            severity=0.8,
            confidence=0.7,
            evidence="test evidence",
            recommended_moves=["narrow_stereo_width"],
        )
        d = issue.to_dict()
        assert d["issue_type"] == "mono_collapse"
        assert d["severity"] == 0.8
        assert d["recommended_moves"] == ["narrow_stereo_width"]


# ── Mono Collapse Critic ──────────────────────────────────────────


class TestMonoCollapseCritic:
    def test_no_issue_when_narrow(self):
        issues = run_mono_collapse_critic(stereo_width=0.3, center_strength=0.6)
        assert len(issues) == 0

    def test_no_issue_when_strong_center(self):
        issues = run_mono_collapse_critic(stereo_width=0.9, center_strength=0.5)
        assert len(issues) == 0

    def test_issue_when_wide_and_weak_center(self):
        issues = run_mono_collapse_critic(stereo_width=0.9, center_strength=0.2)
        assert len(issues) == 1
        assert issues[0].issue_type == "mono_collapse"
        assert issues[0].severity > 0


# ── Small Speaker Critic ──────────────────────────────────────────


class TestSmallSpeakerCritic:
    def test_no_issue_balanced_low_end(self):
        issues = run_small_speaker_critic(sub_energy=0.2, low_energy=0.5)
        assert len(issues) == 0

    def test_issue_when_sub_dominant(self):
        issues = run_small_speaker_critic(sub_energy=0.7, low_energy=0.2)
        assert len(issues) == 1
        assert issues[0].issue_type == "small_speaker_loss"

    def test_no_issue_when_zero_energy(self):
        issues = run_small_speaker_critic(sub_energy=0.0, low_energy=0.0)
        assert len(issues) == 0


# ── Harshness Critic ──────────────────────────────────────────────


class TestHarshnessCritic:
    def test_no_issue_when_mellow(self):
        issues = run_harshness_critic(high_energy=0.2, presence_energy=0.3)
        assert len(issues) == 0

    def test_issue_when_bright(self):
        issues = run_harshness_critic(high_energy=0.5, presence_energy=0.4)
        assert len(issues) == 1
        assert issues[0].issue_type == "harshness_risk"
        assert issues[0].severity > 0


# ── Low End Instability Critic ────────────────────────────────────


class TestLowEndInstabilityCritic:
    def test_no_issue_when_clean(self):
        issues = run_low_end_instability_critic(sub_energy=0.2, low_mid_energy=0.2)
        assert len(issues) == 0

    def test_issue_when_competing(self):
        issues = run_low_end_instability_critic(sub_energy=0.6, low_mid_energy=0.5)
        assert len(issues) == 1
        assert issues[0].issue_type == "low_end_instability"


# ── Front Element Critic ──────────────────────────────────────────


class TestFrontElementCritic:
    def test_no_issue_when_present(self):
        issues = run_front_element_critic(has_foreground=True, foreground_masked=False)
        assert len(issues) == 0

    def test_issue_when_missing(self):
        issues = run_front_element_critic(has_foreground=False, foreground_masked=False)
        assert len(issues) == 1
        assert issues[0].issue_type == "no_front_element"

    def test_issue_when_masked(self):
        issues = run_front_element_critic(has_foreground=True, foreground_masked=True)
        assert len(issues) == 1
        assert issues[0].issue_type == "front_element_masked"


# ── Run All Critics ───────────────────────────────────────────────


class TestRunAllCritics:
    def test_clean_mix_no_issues(self):
        snapshot = {
            "stereo_width": 0.4,
            "center_strength": 0.6,
            "sub_energy": 0.2,
            "low_energy": 0.4,
            "low_mid_energy": 0.2,
            "high_energy": 0.2,
            "presence_energy": 0.3,
            "has_foreground": True,
            "foreground_masked": False,
        }
        issues = run_all_translation_critics(snapshot)
        assert len(issues) == 0

    def test_problematic_mix_multiple_issues(self):
        snapshot = {
            "stereo_width": 0.9,
            "center_strength": 0.1,
            "sub_energy": 0.8,
            "low_energy": 0.1,
            "low_mid_energy": 0.5,
            "high_energy": 0.5,
            "presence_energy": 0.4,
            "has_foreground": False,
            "foreground_masked": False,
        }
        issues = run_all_translation_critics(snapshot)
        types = {i.issue_type for i in issues}
        assert "mono_collapse" in types
        assert "small_speaker_loss" in types
        assert "harshness_risk" in types
        assert "low_end_instability" in types
        assert "no_front_element" in types


# ── Build Translation Report ──────────────────────────────────────


class TestBuildTranslationReport:
    def test_robust_report(self):
        snapshot = {
            "stereo_width": 0.4,
            "center_strength": 0.6,
            "sub_energy": 0.2,
            "low_energy": 0.4,
            "low_mid_energy": 0.2,
            "high_energy": 0.2,
            "presence_energy": 0.3,
            "has_foreground": True,
            "foreground_masked": False,
        }
        report = build_translation_report(snapshot)
        assert report.overall_robustness == "robust"
        assert report.mono_safe is True
        assert report.small_speaker_safe is True
        assert len(report.issues) == 0

    def test_critical_report(self):
        snapshot = {
            "stereo_width": 0.95,
            "center_strength": 0.1,
            "sub_energy": 0.8,
            "low_energy": 0.1,
            "low_mid_energy": 0.5,
            "high_energy": 0.5,
            "presence_energy": 0.4,
            "has_foreground": False,
            "foreground_masked": False,
        }
        report = build_translation_report(snapshot)
        assert report.overall_robustness == "critical"
        assert report.mono_safe is False
        assert report.small_speaker_safe is False
        assert report.front_element_present is False
        assert len(report.issues) >= 3
        assert len(report.suggested_moves) > 0

    def test_report_to_dict_roundtrip(self):
        snapshot = {
            "stereo_width": 0.8,
            "center_strength": 0.2,
            "sub_energy": 0.3,
            "low_energy": 0.3,
            "low_mid_energy": 0.2,
            "high_energy": 0.3,
            "presence_energy": 0.3,
            "has_foreground": True,
            "foreground_masked": False,
        }
        report = build_translation_report(snapshot)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "mono_safe" in d
        assert "overall_robustness" in d
        assert "issues" in d
        assert "suggested_moves" in d

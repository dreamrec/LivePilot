"""Tests for the Transition Engine — models, archetypes, critics, scoring."""

from __future__ import annotations

import pytest

from mcp_server.transition_engine.models import (
    TransitionArchetype,
    TransitionBoundary,
    TransitionPlan,
    TransitionScore,
)
from mcp_server.transition_engine.archetypes import (
    TRANSITION_ARCHETYPES,
    select_archetype,
)
from mcp_server.transition_engine.critics import (
    TransitionIssue,
    run_all_transition_critics,
    run_boundary_clarity_critic,
    run_energy_redirection_critic,
    run_gesture_fit_critic,
    run_overtelegraphing_critic,
    run_payoff_critic,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def build_to_drop_boundary():
    return TransitionBoundary(
        from_section_id="sec_build",
        to_section_id="sec_drop",
        boundary_bar=32,
        from_type="build",
        to_type="drop",
        energy_delta=0.5,
        density_delta=0.3,
    )


@pytest.fixture
def flat_boundary():
    return TransitionBoundary(
        from_section_id="sec_a",
        to_section_id="sec_b",
        boundary_bar=16,
        from_type="verse",
        to_type="verse",
        energy_delta=0.02,
        density_delta=0.01,
    )


@pytest.fixture
def verse_to_chorus_boundary():
    return TransitionBoundary(
        from_section_id="sec_verse",
        to_section_id="sec_chorus",
        boundary_bar=24,
        from_type="verse",
        to_type="chorus",
        energy_delta=0.3,
        density_delta=0.2,
    )


# ── Model Tests ───────────────────────────────────────────────────────


class TestTransitionBoundary:
    def test_to_dict(self, build_to_drop_boundary):
        d = build_to_drop_boundary.to_dict()
        assert d["from_section_id"] == "sec_build"
        assert d["to_section_id"] == "sec_drop"
        assert d["boundary_bar"] == 32
        assert d["energy_delta"] == 0.5

    def test_defaults(self):
        b = TransitionBoundary()
        assert b.from_type == "unknown"
        assert b.energy_delta == 0.0


class TestTransitionArchetype:
    def test_to_dict(self):
        a = TransitionArchetype(
            name="test",
            description="test archetype",
            use_cases=["test"],
            risk_profile="low",
        )
        d = a.to_dict()
        assert d["name"] == "test"
        assert d["risk_profile"] == "low"
        assert isinstance(d["use_cases"], list)


class TestTransitionPlan:
    def test_to_dict(self, build_to_drop_boundary):
        plan = TransitionPlan(
            boundary=build_to_drop_boundary,
            archetype=TRANSITION_ARCHETYPES["subtractive_inhale"],
            lead_in_gestures=[{"intent": "inhale"}],
            arrival_gestures=[{"intent": "release"}],
            payoff_estimate=0.8,
        )
        d = plan.to_dict()
        assert d["boundary"]["from_type"] == "build"
        assert d["archetype"]["name"] == "subtractive_inhale"
        assert len(d["lead_in_gestures"]) == 1
        assert d["payoff_estimate"] == 0.8


class TestTransitionScore:
    def test_to_dict(self):
        s = TransitionScore(
            boundary_clarity=0.8,
            payoff_strength=0.7,
            energy_redirection=0.6,
            identity_preservation=0.5,
            cliche_risk=0.3,
            overall=0.65,
        )
        d = s.to_dict()
        assert d["overall"] == 0.65
        assert d["cliche_risk"] == 0.3

    def test_defaults_are_zero(self):
        s = TransitionScore()
        assert s.overall == 0.0
        assert s.boundary_clarity == 0.0


# ── Archetype Tests ───────────────────────────────────────────────────


class TestArchetypeLibrary:
    def test_has_seven_archetypes(self):
        assert len(TRANSITION_ARCHETYPES) == 7

    def test_all_archetypes_have_required_fields(self):
        for name, arch in TRANSITION_ARCHETYPES.items():
            assert arch.name == name
            assert arch.description
            assert len(arch.use_cases) > 0
            assert arch.risk_profile in ("low", "medium", "high")
            assert len(arch.devices) > 0
            assert len(arch.gestures) > 0
            assert len(arch.verification) > 0

    def test_archetype_names(self):
        expected = {
            "subtractive_inhale", "fill_and_reset", "tail_throw",
            "width_bloom", "harmonic_suspend", "impact_vacuum",
            "delayed_foreground_handoff",
        }
        assert set(TRANSITION_ARCHETYPES.keys()) == expected

    def test_risk_profiles_vary(self):
        profiles = {a.risk_profile for a in TRANSITION_ARCHETYPES.values()}
        assert "low" in profiles
        assert "medium" in profiles
        assert "high" in profiles


class TestSelectArchetype:
    def test_build_to_drop(self, build_to_drop_boundary):
        arch = select_archetype(build_to_drop_boundary)
        assert arch.name == "subtractive_inhale"

    def test_verse_to_chorus(self, verse_to_chorus_boundary):
        arch = select_archetype(verse_to_chorus_boundary)
        assert arch.name == "fill_and_reset"

    def test_large_energy_increase_fallback(self):
        b = TransitionBoundary(
            from_type="unknown", to_type="unknown", energy_delta=0.5,
        )
        arch = select_archetype(b)
        assert arch.name == "subtractive_inhale"

    def test_large_energy_decrease_fallback(self):
        b = TransitionBoundary(
            from_type="unknown", to_type="unknown", energy_delta=-0.5,
        )
        arch = select_archetype(b)
        assert arch.name == "tail_throw"

    def test_flat_energy_fallback(self):
        b = TransitionBoundary(
            from_type="unknown", to_type="unknown", energy_delta=0.0,
        )
        arch = select_archetype(b)
        assert arch.name == "width_bloom"


# ── Critic Tests ──────────────────────────────────────────────────────


class TestBoundaryClarity:
    def test_invisible_boundary(self, flat_boundary):
        issues = run_boundary_clarity_critic(flat_boundary)
        types = [i.issue_type for i in issues]
        assert "invisible_boundary" in types

    def test_clear_boundary_no_issues(self, build_to_drop_boundary):
        issues = run_boundary_clarity_critic(build_to_drop_boundary)
        assert len(issues) == 0

    def test_structural_only_boundary(self):
        b = TransitionBoundary(energy_delta=0.02, density_delta=0.2)
        issues = run_boundary_clarity_critic(b)
        types = [i.issue_type for i in issues]
        assert "structural_only_boundary" in types


class TestPayoffCritic:
    def test_weak_payoff(self):
        b = TransitionBoundary(energy_delta=0.4, from_type="verse", to_type="verse")
        s = TransitionScore(payoff_strength=0.2)
        issues = run_payoff_critic(b, s)
        types = [i.issue_type for i in issues]
        assert "weak_payoff" in types

    def test_anticlimactic_arrival(self):
        b = TransitionBoundary(
            from_type="build", to_type="drop", energy_delta=0.3,
        )
        s = TransitionScore(payoff_strength=0.3)
        issues = run_payoff_critic(b, s)
        types = [i.issue_type for i in issues]
        assert "anticlimactic_arrival" in types

    def test_good_payoff_no_issues(self):
        b = TransitionBoundary(energy_delta=0.1, from_type="verse", to_type="verse")
        s = TransitionScore(payoff_strength=0.8)
        issues = run_payoff_critic(b, s)
        assert len(issues) == 0


class TestOvertelegraphingCritic:
    def test_too_many_gestures(self):
        plan = TransitionPlan(
            lead_in_gestures=[{"a": 1}, {"b": 2}, {"c": 3}],
            arrival_gestures=[{"d": 4}, {"e": 5}, {"f": 6}],
        )
        issues = run_overtelegraphing_critic(plan)
        types = [i.issue_type for i in issues]
        assert "overtelegraphed_transition" in types

    def test_reasonable_gestures_no_issues(self):
        plan = TransitionPlan(
            lead_in_gestures=[{"a": 1}],
            arrival_gestures=[{"b": 2}],
        )
        issues = run_overtelegraphing_critic(plan)
        assert len(issues) == 0

    def test_high_risk_overloaded(self):
        plan = TransitionPlan(
            archetype=TransitionArchetype(risk_profile="high"),
            lead_in_gestures=[{"a": 1}, {"b": 2}],
            arrival_gestures=[{"c": 3}, {"d": 4}],
        )
        issues = run_overtelegraphing_critic(plan)
        types = [i.issue_type for i in issues]
        assert "high_risk_overloaded" in types


class TestEnergyRedirectionCritic:
    def test_flat_high_contrast(self):
        b = TransitionBoundary(
            from_type="build", to_type="drop", energy_delta=0.05,
        )
        issues = run_energy_redirection_critic(b)
        types = [i.issue_type for i in issues]
        assert "flat_high_contrast_transition" in types

    def test_unexpected_shift_in_same_type(self):
        b = TransitionBoundary(
            from_type="verse", to_type="verse", energy_delta=0.5,
        )
        issues = run_energy_redirection_critic(b)
        types = [i.issue_type for i in issues]
        assert "unexpected_energy_shift" in types

    def test_normal_transition_no_issues(self, verse_to_chorus_boundary):
        issues = run_energy_redirection_critic(verse_to_chorus_boundary)
        assert len(issues) == 0


class TestGestureFitCritic:
    def test_overkill_archetype(self):
        b = TransitionBoundary(
            from_type="verse", to_type="verse", energy_delta=0.05,
        )
        arch = TransitionArchetype(
            name="impact_vacuum", risk_profile="high",
            use_cases=["build_to_drop"],
        )
        plan = TransitionPlan(boundary=b, archetype=arch)
        issues = run_gesture_fit_critic(plan)
        types = [i.issue_type for i in issues]
        assert "overkill_archetype" in types

    def test_matching_archetype_no_fit_issue(self, build_to_drop_boundary):
        arch = TRANSITION_ARCHETYPES["subtractive_inhale"]
        plan = TransitionPlan(boundary=build_to_drop_boundary, archetype=arch)
        issues = run_gesture_fit_critic(plan)
        # subtractive_inhale use_cases include "build_to_drop" — should match
        mismatch = [i for i in issues if i.issue_type == "archetype_section_mismatch"]
        assert len(mismatch) == 0


class TestRunAllCritics:
    def test_returns_list(self, flat_boundary):
        plan = TransitionPlan(boundary=flat_boundary)
        score = TransitionScore()
        issues = run_all_transition_critics(flat_boundary, plan, score)
        assert isinstance(issues, list)
        assert all(isinstance(i, TransitionIssue) for i in issues)

    def test_all_issues_have_to_dict(self, flat_boundary):
        plan = TransitionPlan(boundary=flat_boundary)
        score = TransitionScore()
        issues = run_all_transition_critics(flat_boundary, plan, score)
        for issue in issues:
            d = issue.to_dict()
            assert "issue_type" in d
            assert "critic" in d
            assert "severity" in d

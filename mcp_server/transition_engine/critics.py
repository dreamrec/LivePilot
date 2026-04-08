"""Transition Engine critics — 5 boundary-specific critics.

Detect transition quality issues: boundary clarity, payoff strength,
overtelegraphing, energy redirection, and gesture fit.

All pure computation, zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .models import TransitionBoundary, TransitionPlan, TransitionScore


# ── TransitionIssue ───────────────────────────────────────────────────


@dataclass
class TransitionIssue:
    """A single detected transition issue."""

    issue_type: str = ""
    critic: str = ""
    severity: float = 0.0       # 0.0-1.0
    confidence: float = 0.0     # 0.0-1.0
    boundary: dict = field(default_factory=dict)
    evidence: str = ""
    recommended_moves: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Boundary Clarity Critic ───────────────────────────────────────────


def run_boundary_clarity_critic(
    boundary: TransitionBoundary,
) -> list[TransitionIssue]:
    """Detect unclear boundaries — no energy or density change."""
    issues: list[TransitionIssue] = []

    abs_energy = abs(boundary.energy_delta)
    abs_density = abs(boundary.density_delta)

    # Both energy and density flat — boundary is invisible
    if abs_energy < 0.05 and abs_density < 0.05:
        issues.append(TransitionIssue(
            issue_type="invisible_boundary",
            critic="boundary_clarity",
            severity=0.7,
            confidence=0.75,
            boundary=boundary.to_dict(),
            evidence=(
                f"Neither energy (delta={boundary.energy_delta:.2f}) nor density "
                f"(delta={boundary.density_delta:.2f}) changes at boundary bar "
                f"{boundary.boundary_bar}"
            ),
            recommended_moves=[
                "add_fill_at_boundary",
                "vary_density_before_arrival",
                "insert_breath_before_downbeat",
            ],
        ))

    # Only density changes but energy is flat — structural but not felt
    if abs_energy < 0.05 and abs_density >= 0.1:
        issues.append(TransitionIssue(
            issue_type="structural_only_boundary",
            critic="boundary_clarity",
            severity=0.4,
            confidence=0.60,
            boundary=boundary.to_dict(),
            evidence=(
                f"Density shifts (delta={boundary.density_delta:.2f}) but energy "
                f"is flat (delta={boundary.energy_delta:.2f}) — transition may feel "
                f"like track muting, not a musical boundary"
            ),
            recommended_moves=[
                "add_energy_gesture_at_boundary",
                "automate_filter_or_volume_sweep",
            ],
        ))

    return issues


# ── Payoff Critic ─────────────────────────────────────────────────────


def run_payoff_critic(
    boundary: TransitionBoundary,
    score: TransitionScore,
) -> list[TransitionIssue]:
    """Detect weak payoff — high energy arrival without reward."""
    issues: list[TransitionIssue] = []

    # High energy increase but low payoff score
    if boundary.energy_delta > 0.2 and score.payoff_strength < 0.4:
        issues.append(TransitionIssue(
            issue_type="weak_payoff",
            critic="payoff",
            severity=0.7,
            confidence=0.70,
            boundary=boundary.to_dict(),
            evidence=(
                f"Energy rises by {boundary.energy_delta:.2f} at bar "
                f"{boundary.boundary_bar} but payoff_strength is only "
                f"{score.payoff_strength:.2f} — arrival doesn't feel earned"
            ),
            recommended_moves=[
                "add_pre_arrival_subtraction",
                "increase_contrast_at_boundary",
                "add_impact_element_at_downbeat",
            ],
        ))

    # Build section into drop/chorus with low payoff
    build_types = {"build", "pre_chorus"}
    peak_types = {"drop", "chorus"}
    if (boundary.from_type in build_types
            and boundary.to_type in peak_types
            and score.payoff_strength < 0.5):
        issues.append(TransitionIssue(
            issue_type="anticlimactic_arrival",
            critic="payoff",
            severity=0.8,
            confidence=0.75,
            boundary=boundary.to_dict(),
            evidence=(
                f"{boundary.from_type} -> {boundary.to_type} transition at bar "
                f"{boundary.boundary_bar} has payoff {score.payoff_strength:.2f} "
                f"— peak section should feel like a reward"
            ),
            recommended_moves=[
                "deepen_subtraction_in_build",
                "add_impact_vacuum",
                "widen_stereo_at_arrival",
            ],
        ))

    return issues


# ── Overtelegraphing Critic ───────────────────────────────────────────


def run_overtelegraphing_critic(
    plan: TransitionPlan,
) -> list[TransitionIssue]:
    """Detect transitions that use too many gestures — trying too hard."""
    issues: list[TransitionIssue] = []

    total_gestures = len(plan.lead_in_gestures) + len(plan.arrival_gestures)

    # Too many gestures — overproduced transition
    if total_gestures > 5:
        issues.append(TransitionIssue(
            issue_type="overtelegraphed_transition",
            critic="overtelegraphing",
            severity=min(1.0, 0.3 + (total_gestures - 5) * 0.15),
            confidence=0.65,
            boundary=plan.boundary.to_dict(),
            evidence=(
                f"Transition uses {total_gestures} gestures "
                f"({len(plan.lead_in_gestures)} lead-in, "
                f"{len(plan.arrival_gestures)} arrival) — more FX != better transition"
            ),
            recommended_moves=[
                "remove_weakest_gesture",
                "simplify_to_one_lead_in_and_one_arrival",
                "trust_the_arrangement",
            ],
        ))

    # High-risk archetype with many gestures — doubly obvious
    if plan.archetype.risk_profile == "high" and total_gestures > 3:
        issues.append(TransitionIssue(
            issue_type="high_risk_overloaded",
            critic="overtelegraphing",
            severity=0.6,
            confidence=0.60,
            boundary=plan.boundary.to_dict(),
            evidence=(
                f"High-risk archetype '{plan.archetype.name}' combined with "
                f"{total_gestures} gestures — dramatic archetype needs fewer "
                f"gestures, not more"
            ),
            recommended_moves=[
                "reduce_to_core_gestures_only",
                "let_archetype_do_the_work",
            ],
        ))

    return issues


# ── Energy Redirection Critic ─────────────────────────────────────────


def run_energy_redirection_critic(
    boundary: TransitionBoundary,
) -> list[TransitionIssue]:
    """Detect boundaries where energy doesn't redirect enough."""
    issues: list[TransitionIssue] = []

    abs_energy = abs(boundary.energy_delta)

    # Section types that demand energy change
    high_contrast_pairs = {
        ("build", "drop"), ("breakdown", "drop"),
        ("breakdown", "chorus"), ("pre_chorus", "chorus"),
    }
    low_contrast_pairs = {
        ("verse", "verse"), ("chorus", "chorus"),
    }

    pair = (boundary.from_type, boundary.to_type)

    # High-contrast pair with low energy change — transition falls flat
    if pair in high_contrast_pairs and abs_energy < 0.15:
        issues.append(TransitionIssue(
            issue_type="flat_high_contrast_transition",
            critic="energy_redirection",
            severity=0.7,
            confidence=0.70,
            boundary=boundary.to_dict(),
            evidence=(
                f"{boundary.from_type} -> {boundary.to_type} expects significant "
                f"energy change but delta is only {boundary.energy_delta:.2f}"
            ),
            recommended_moves=[
                "increase_energy_contrast",
                "subtract_before_arrival",
                "add_elements_at_arrival",
            ],
        ))

    # Same section type repeating with large energy change — unintentional
    if pair in low_contrast_pairs and abs_energy > 0.3:
        issues.append(TransitionIssue(
            issue_type="unexpected_energy_shift",
            critic="energy_redirection",
            severity=0.4,
            confidence=0.55,
            boundary=boundary.to_dict(),
            evidence=(
                f"Repeating section type '{boundary.from_type}' has energy delta "
                f"of {boundary.energy_delta:.2f} — may feel inconsistent"
            ),
            recommended_moves=[
                "normalize_energy_across_repeats",
                "differentiate_section_types_if_intentional",
            ],
        ))

    return issues


# ── Gesture Fit Critic ────────────────────────────────────────────────


def run_gesture_fit_critic(
    plan: TransitionPlan,
) -> list[TransitionIssue]:
    """Detect mismatches between archetype and section types."""
    issues: list[TransitionIssue] = []

    boundary = plan.boundary
    archetype = plan.archetype

    # Check if the section pair matches any of the archetype's use cases
    pair_tags = {
        f"{boundary.from_type}_to_{boundary.to_type}",
        boundary.from_type,
        boundary.to_type,
    }
    use_case_match = any(
        tag in uc or uc in tag
        for tag in pair_tags
        for uc in archetype.use_cases
    )

    if not use_case_match:
        issues.append(TransitionIssue(
            issue_type="archetype_section_mismatch",
            critic="gesture_fit",
            severity=0.5,
            confidence=0.55,
            boundary=boundary.to_dict(),
            evidence=(
                f"Archetype '{archetype.name}' (use_cases={archetype.use_cases}) "
                f"doesn't match section pair {boundary.from_type} -> "
                f"{boundary.to_type}"
            ),
            recommended_moves=[
                "select_different_archetype",
                "customize_gestures_for_section_pair",
            ],
        ))

    # High-risk archetype for low-energy transitions — overkill
    if archetype.risk_profile == "high" and abs(boundary.energy_delta) < 0.15:
        issues.append(TransitionIssue(
            issue_type="overkill_archetype",
            critic="gesture_fit",
            severity=0.5,
            confidence=0.60,
            boundary=boundary.to_dict(),
            evidence=(
                f"High-risk archetype '{archetype.name}' used for low-contrast "
                f"transition (energy_delta={boundary.energy_delta:.2f}) — "
                f"dramatic technique for a subtle moment"
            ),
            recommended_moves=[
                "use_lower_risk_archetype",
                "increase_energy_contrast_if_dramatic_intent",
            ],
        ))

    return issues


# ── Run All ───────────────────────────────────────────────────────────


def run_all_transition_critics(
    boundary: TransitionBoundary,
    plan: TransitionPlan,
    score: TransitionScore,
) -> list[TransitionIssue]:
    """Run all 5 transition critics and return combined issues."""
    issues: list[TransitionIssue] = []
    issues.extend(run_boundary_clarity_critic(boundary))
    issues.extend(run_payoff_critic(boundary, score))
    issues.extend(run_overtelegraphing_critic(plan))
    issues.extend(run_energy_redirection_critic(boundary))
    issues.extend(run_gesture_fit_critic(plan))
    return issues

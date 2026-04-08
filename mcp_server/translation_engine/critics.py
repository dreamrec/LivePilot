"""Translation Engine critics — detect playback robustness issues.

Five critics: mono_collapse, small_speaker, harshness,
low_end_instability, front_element.
All pure computation, zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List

from .models import TranslationReport


# ── TranslationIssue ──────────────────────────────────────────────


@dataclass
class TranslationIssue:
    """A single detected translation/playback issue."""

    issue_type: str = ""
    critic: str = ""
    severity: float = 0.0  # 0-1
    confidence: float = 0.0  # 0-1
    evidence: str = ""
    recommended_moves: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Mono Collapse Critic ──────────────────────────────────────────


def run_mono_collapse_critic(
    stereo_width: float,
    center_strength: float,
) -> List[TranslationIssue]:
    """Warn if stereo width > 0.7 and center strength < 0.4.

    A wide mix with weak center will lose significant content
    when summed to mono.
    """
    issues: List[TranslationIssue] = []

    if stereo_width > 0.7 and center_strength < 0.4:
        severity = min(1.0, (stereo_width - 0.5) * (0.5 - center_strength) * 4.0)
        issues.append(TranslationIssue(
            issue_type="mono_collapse",
            critic="mono_collapse",
            severity=max(0.0, severity),
            confidence=0.7,
            evidence=(
                f"Stereo width {stereo_width:.2f} with center strength "
                f"{center_strength:.2f} — mono playback will lose "
                f"significant stereo content"
            ),
            recommended_moves=["narrow_stereo_width", "strengthen_center"],
        ))

    return issues


# ── Small Speaker Critic ──────────────────────────────────────────


def run_small_speaker_critic(
    sub_energy: float,
    low_energy: float,
) -> List[TranslationIssue]:
    """Warn if sub-bass dominates the low-end balance.

    If sub_energy > 0.5 of total low-end (sub + low), small speakers
    will lose the foundation because they cannot reproduce sub frequencies.
    """
    issues: List[TranslationIssue] = []
    total_low = sub_energy + low_energy

    if total_low > 0 and sub_energy / total_low > 0.5:
        sub_ratio = sub_energy / total_low
        severity = min(1.0, (sub_ratio - 0.5) * 4.0)
        issues.append(TranslationIssue(
            issue_type="small_speaker_loss",
            critic="small_speaker",
            severity=max(0.0, severity),
            confidence=0.65,
            evidence=(
                f"Sub energy {sub_energy:.2f} is {sub_ratio:.0%} of total "
                f"low-end ({total_low:.2f}) — small speakers will lose "
                f"the low-end foundation"
            ),
            recommended_moves=["add_harmonics_to_bass", "reduce_sub_energy"],
        ))

    return issues


# ── Harshness Critic ──────────────────────────────────────────────


def run_harshness_critic(
    high_energy: float,
    presence_energy: float,
) -> List[TranslationIssue]:
    """Warn if combined high + presence energy exceeds 0.75.

    Excessive brightness causes listening fatigue, especially on
    earbuds and small speakers with boosted treble response.
    """
    issues: List[TranslationIssue] = []
    combined = high_energy + presence_energy

    if combined > 0.75:
        severity = min(1.0, (combined - 0.75) * 4.0)
        issues.append(TranslationIssue(
            issue_type="harshness_risk",
            critic="harshness",
            severity=max(0.0, severity),
            confidence=0.6,
            evidence=(
                f"High energy {high_energy:.2f} + presence energy "
                f"{presence_energy:.2f} = {combined:.2f} — "
                f"likely harsh on earbuds and small speakers"
            ),
            recommended_moves=["reduce_high_shelf", "tame_presence_peak"],
        ))

    return issues


# ── Low End Instability Critic ────────────────────────────────────


def run_low_end_instability_critic(
    sub_energy: float,
    low_mid_energy: float,
) -> List[TranslationIssue]:
    """Warn if sub and low-mid energies are competing.

    When both are high, they create muddiness and masking in
    the low-frequency range.
    """
    issues: List[TranslationIssue] = []

    if sub_energy > 0.4 and low_mid_energy > 0.4:
        severity = min(1.0, (sub_energy + low_mid_energy - 0.8) * 2.5)
        issues.append(TranslationIssue(
            issue_type="low_end_instability",
            critic="low_end_instability",
            severity=max(0.0, severity),
            confidence=0.6,
            evidence=(
                f"Sub energy {sub_energy:.2f} and low-mid energy "
                f"{low_mid_energy:.2f} are both high — "
                f"competing low frequencies cause muddiness"
            ),
            recommended_moves=["high_pass_non_bass", "eq_low_mid_cut"],
        ))

    return issues


# ── Front Element Critic ──────────────────────────────────────────


def run_front_element_critic(
    has_foreground: bool,
    foreground_masked: bool,
) -> List[TranslationIssue]:
    """Warn if lead/vocal is absent or buried.

    The front element (vocal, lead synth, melody) must remain
    present and unmasked for the mix to translate.
    """
    issues: List[TranslationIssue] = []

    if not has_foreground:
        issues.append(TranslationIssue(
            issue_type="no_front_element",
            critic="front_element",
            severity=0.7,
            confidence=0.5,
            evidence="No foreground element detected — mix lacks a focal point",
            recommended_moves=["add_lead_element", "boost_vocal"],
        ))

    if has_foreground and foreground_masked:
        issues.append(TranslationIssue(
            issue_type="front_element_masked",
            critic="front_element",
            severity=0.6,
            confidence=0.6,
            evidence=(
                "Foreground element is present but masked — "
                "lead/vocal is buried in the mix"
            ),
            recommended_moves=["eq_pocket_for_vocal", "reduce_competing_mids"],
        ))

    return issues


# ── Run all translation critics ───────────────────────────────────


def run_all_translation_critics(mix_snapshot: dict) -> List[TranslationIssue]:
    """Run all 5 translation critics against a mix snapshot.

    Expected mix_snapshot keys:
        stereo_width: float (0-1)
        center_strength: float (0-1)
        sub_energy: float (0-1)
        low_energy: float (0-1)
        low_mid_energy: float (0-1)
        high_energy: float (0-1)
        presence_energy: float (0-1)
        has_foreground: bool
        foreground_masked: bool
    """
    issues: List[TranslationIssue] = []

    issues.extend(run_mono_collapse_critic(
        stereo_width=mix_snapshot.get("stereo_width", 0.0),
        center_strength=mix_snapshot.get("center_strength", 0.5),
    ))

    issues.extend(run_small_speaker_critic(
        sub_energy=mix_snapshot.get("sub_energy", 0.0),
        low_energy=mix_snapshot.get("low_energy", 0.0),
    ))

    issues.extend(run_harshness_critic(
        high_energy=mix_snapshot.get("high_energy", 0.0),
        presence_energy=mix_snapshot.get("presence_energy", 0.0),
    ))

    issues.extend(run_low_end_instability_critic(
        sub_energy=mix_snapshot.get("sub_energy", 0.0),
        low_mid_energy=mix_snapshot.get("low_mid_energy", 0.0),
    ))

    issues.extend(run_front_element_critic(
        has_foreground=mix_snapshot.get("has_foreground", True),
        foreground_masked=mix_snapshot.get("foreground_masked", False),
    ))

    return issues


# ── Build TranslationReport ───────────────────────────────────────


def build_translation_report(mix_snapshot: dict) -> TranslationReport:
    """Run all critics and compile a TranslationReport."""
    issues = run_all_translation_critics(mix_snapshot)

    # Classify booleans from issues
    mono_safe = not any(i.issue_type == "mono_collapse" for i in issues)
    small_speaker_safe = not any(i.issue_type == "small_speaker_loss" for i in issues)
    harshness = max(
        (i.severity for i in issues if i.issue_type == "harshness_risk"),
        default=0.0,
    )
    low_end_stable = not any(i.issue_type == "low_end_instability" for i in issues)
    front_element_present = not any(
        i.issue_type in ("no_front_element", "front_element_masked")
        for i in issues
    )

    # Collect all suggested moves
    all_moves: list[str] = []
    for issue in issues:
        for move in issue.recommended_moves:
            if move not in all_moves:
                all_moves.append(move)

    # Overall robustness classification
    max_severity = max((i.severity for i in issues), default=0.0)
    if max_severity >= 0.7 or len(issues) >= 3:
        overall = "critical"
    elif max_severity >= 0.4 or len(issues) >= 2:
        overall = "fragile"
    else:
        overall = "robust"

    return TranslationReport(
        mono_safe=mono_safe,
        small_speaker_safe=small_speaker_safe,
        harshness_risk=harshness,
        low_end_stable=low_end_stable,
        front_element_present=front_element_present,
        overall_robustness=overall,
        issues=[i.to_dict() for i in issues],
        suggested_moves=all_moves,
    )

"""Mix Engine critics — detect mix issues from state data.

Six critics: balance, masking, dynamics, stereo, depth, translation.
All pure computation, zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .models import (
    BalanceState,
    DepthState,
    DynamicsState,
    MaskingMap,
    MixState,
    StereoState,
)


# ── MixIssue ───────────────────────────────────────────────────────


@dataclass
class MixIssue:
    """A single detected mix issue."""

    issue_type: str = ""
    critic: str = ""
    severity: float = 0.0
    confidence: float = 0.0
    affected_tracks: list[int] = field(default_factory=list)
    evidence: str = ""
    recommended_moves: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Balance Critic ──────────────────────────────────────────────────


def run_balance_critic(balance: BalanceState) -> list[MixIssue]:
    """Detect balance problems: anchor too weak, support too loud."""
    issues: list[MixIssue] = []
    active = [t for t in balance.track_states if not t.mute]

    if not active:
        return issues

    # Compute average volume of active tracks
    avg_vol = sum(t.volume for t in active) / len(active)

    # Check if anchor tracks are too quiet
    for t in active:
        if t.track_index in balance.anchor_tracks:
            if t.volume < avg_vol * 0.6:
                issues.append(MixIssue(
                    issue_type="anchor_too_weak",
                    critic="balance",
                    severity=min(1.0, (avg_vol - t.volume) / max(avg_vol, 0.01)),
                    confidence=0.7,
                    affected_tracks=[t.track_index],
                    evidence=(
                        f"Anchor track '{t.name}' (role={t.role}) at volume "
                        f"{t.volume:.2f}, average is {avg_vol:.2f}"
                    ),
                    recommended_moves=["gain_staging"],
                ))

    # Check if non-anchor tracks are too loud
    for t in active:
        if t.track_index not in balance.anchor_tracks:
            if t.volume > avg_vol * 1.5 and t.role not in ("kick", "bass", "vocal", "lead"):
                issues.append(MixIssue(
                    issue_type="support_too_loud",
                    critic="balance",
                    severity=min(1.0, (t.volume - avg_vol) / max(avg_vol, 0.01)),
                    confidence=0.6,
                    affected_tracks=[t.track_index],
                    evidence=(
                        f"Support track '{t.name}' (role={t.role}) at volume "
                        f"{t.volume:.2f}, average is {avg_vol:.2f}"
                    ),
                    recommended_moves=["gain_staging"],
                ))

    return issues


# ── Masking Critic ──────────────────────────────────────────────────


def run_masking_critic(masking: MaskingMap) -> list[MixIssue]:
    """Detect frequency collision issues from masking map."""
    issues: list[MixIssue] = []

    for entry in masking.entries:
        if entry.severity >= 0.4:
            issues.append(MixIssue(
                issue_type="frequency_collision",
                critic="masking",
                severity=entry.severity,
                confidence=0.6,
                affected_tracks=[entry.track_a, entry.track_b],
                evidence=(
                    f"Tracks {entry.track_a} and {entry.track_b} collide "
                    f"in {entry.overlap_band} band (severity {entry.severity:.2f})"
                ),
                recommended_moves=["eq_correction"],
            ))

    return issues


# ── Dynamics Critic ─────────────────────────────────────────────────


def run_dynamics_critic(dynamics: DynamicsState) -> list[MixIssue]:
    """Detect dynamics problems: over-compression, flat dynamics, low headroom."""
    issues: list[MixIssue] = []

    if dynamics.over_compressed:
        issues.append(MixIssue(
            issue_type="over_compressed",
            critic="dynamics",
            severity=min(1.0, max(0.0, (6.0 - dynamics.crest_factor_db) / 6.0)),
            confidence=0.7,
            affected_tracks=[],
            evidence=(
                f"Crest factor {dynamics.crest_factor_db:.1f} dB — "
                f"dynamics are flat, likely over-compressed"
            ),
            recommended_moves=["bus_compression", "transient_shaping"],
        ))

    elif dynamics.crest_factor_db < 3.0 and dynamics.crest_factor_db > 0:
        issues.append(MixIssue(
            issue_type="flat_dynamics",
            critic="dynamics",
            severity=0.8,
            confidence=0.8,
            affected_tracks=[],
            evidence=(
                f"Crest factor {dynamics.crest_factor_db:.1f} dB — "
                f"extremely flat, transients are lost"
            ),
            recommended_moves=["transient_shaping", "gain_staging"],
        ))

    if dynamics.headroom < 1.0:
        issues.append(MixIssue(
            issue_type="low_headroom",
            critic="dynamics",
            severity=min(1.0, (1.0 - dynamics.headroom)),
            confidence=0.9,
            affected_tracks=[],
            evidence=f"Only {dynamics.headroom:.1f} dB headroom — clipping risk",
            recommended_moves=["gain_staging"],
        ))

    return issues


# ── Stereo Critic ───────────────────────────────────────────────────


def run_stereo_critic(stereo: StereoState) -> list[MixIssue]:
    """Detect stereo problems: center collapse, overwide."""
    issues: list[MixIssue] = []

    if stereo.mono_risk:
        issues.append(MixIssue(
            issue_type="center_collapse",
            critic="stereo",
            severity=0.6,
            confidence=0.7,
            affected_tracks=[],
            evidence=(
                f"Center strength {stereo.center_strength:.2f}, "
                f"side activity {stereo.side_activity:.2f} — "
                f"mix is essentially mono"
            ),
            recommended_moves=["width_adjustment"],
        ))

    if stereo.side_activity > 0.7:
        issues.append(MixIssue(
            issue_type="overwide",
            critic="stereo",
            severity=min(1.0, stereo.side_activity - 0.5),
            confidence=0.5,
            affected_tracks=[],
            evidence=(
                f"Side activity {stereo.side_activity:.2f} — "
                f"mix may be too wide, center elements could be weak"
            ),
            recommended_moves=["width_adjustment"],
        ))

    return issues


# ── Depth Critic ────────────────────────────────────────────────────


def run_depth_critic(depth: DepthState) -> list[MixIssue]:
    """Detect depth problems: no separation, excessive wash."""
    issues: list[MixIssue] = []

    if depth.depth_separation < 0.05 and depth.wet_dry_ratio > 0.0:
        issues.append(MixIssue(
            issue_type="no_depth_separation",
            critic="depth",
            severity=0.5,
            confidence=0.5,
            affected_tracks=[],
            evidence=(
                f"Depth separation {depth.depth_separation:.3f} — "
                f"all tracks at similar depth, no front/back contrast"
            ),
            recommended_moves=["send_rebalance"],
        ))

    if depth.wash_risk:
        issues.append(MixIssue(
            issue_type="excessive_wash",
            critic="depth",
            severity=min(1.0, depth.wet_dry_ratio),
            confidence=0.6,
            affected_tracks=[],
            evidence=(
                f"Wet/dry ratio {depth.wet_dry_ratio:.2f} — "
                f"excessive reverb/delay washing out the mix"
            ),
            recommended_moves=["send_rebalance"],
        ))

    return issues


# ── Translation Critic ──────────────────────────────────────────────


def run_translation_critic(
    dynamics: DynamicsState,
    stereo: StereoState,
) -> list[MixIssue]:
    """Detect translation risks: mono weakness, harshness risk."""
    issues: list[MixIssue] = []

    # Mono weakness: wide mix with weak center
    if stereo.side_activity > 0.5 and stereo.center_strength < 0.3:
        issues.append(MixIssue(
            issue_type="mono_weakness",
            critic="translation",
            severity=0.7,
            confidence=0.6,
            affected_tracks=[],
            evidence=(
                f"Side activity {stereo.side_activity:.2f} with center "
                f"strength {stereo.center_strength:.2f} — mono playback "
                f"will lose significant content"
            ),
            recommended_moves=["width_adjustment", "gain_staging"],
        ))

    # Harshness risk: over-compressed + low headroom
    if dynamics.over_compressed and dynamics.headroom < 3.0:
        issues.append(MixIssue(
            issue_type="harshness_risk",
            critic="translation",
            severity=0.6,
            confidence=0.5,
            affected_tracks=[],
            evidence=(
                f"Over-compressed (crest {dynamics.crest_factor_db:.1f} dB) "
                f"with only {dynamics.headroom:.1f} dB headroom — "
                f"will sound harsh on smaller speakers"
            ),
            recommended_moves=["gain_staging", "bus_compression"],
        ))

    return issues


# ── Run all critics ─────────────────────────────────────────────────


def run_all_mix_critics(mix_state: MixState) -> list[MixIssue]:
    """Run all six critics and aggregate issues."""
    issues: list[MixIssue] = []
    issues.extend(run_balance_critic(mix_state.balance))
    issues.extend(run_masking_critic(mix_state.masking))
    issues.extend(run_dynamics_critic(mix_state.dynamics))
    issues.extend(run_stereo_critic(mix_state.stereo))
    issues.extend(run_depth_critic(mix_state.depth))
    issues.extend(run_translation_critic(mix_state.dynamics, mix_state.stereo))
    return issues

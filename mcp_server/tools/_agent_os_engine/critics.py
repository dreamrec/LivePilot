"""Part of the _agent_os_engine package — extracted from the single-file engine.

Pure-computation core. Callers should import from the package facade
(`from mcp_server.tools._agent_os_engine import X`), which re-exports from
these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .models import Issue, GoalVector, WorldModel, MEASURABLE_PROXIES

def run_sonic_critic(
    sonic: Optional[dict],
    goal: GoalVector,
    track_roles: dict,
) -> list[Issue]:
    """Run sonic heuristics against spectrum data. Returns issues that overlap
    with the goal's target dimensions."""
    if sonic is None:
        return [Issue(
            type="analyzer_unavailable",
            critic="sonic",
            severity=0.3,
            confidence=1.0,
            affected_dimensions=list(MEASURABLE_PROXIES.keys()),
            evidence=["M4L Analyzer not connected or no audio playing"],
            recommended_actions=["Load LivePilot_Analyzer on master", "Start playback"],
        )]

    issues = []
    bands = sonic.get("spectrum", {})
    rms = sonic.get("rms")
    peak = sonic.get("peak")
    target_dims = set(goal.targets.keys())

    # 1. Mud detection: low_mid congestion
    low_mid = bands.get("low_mid", 0)
    if low_mid > 0.7 and {"clarity", "weight", "warmth"} & target_dims:
        issues.append(Issue(
            type="low_mid_congestion",
            critic="sonic",
            severity=min(1.0, (low_mid - 0.7) * 3.3),
            confidence=0.85,
            affected_dimensions=["clarity", "weight"],
            evidence=[f"low_mid band energy: {low_mid:.2f} (threshold: 0.7)"],
            recommended_actions=["EQ cut 200-500Hz on muddiest track", "HPF on non-bass elements"],
        ))

    # 2. Weak sub
    sub = bands.get("sub", 0)
    has_bass = any(r in ("kick", "bass", "sub_bass") for r in track_roles.values())
    if sub < 0.15 and has_bass and {"weight", "energy", "punch"} & target_dims:
        issues.append(Issue(
            type="weak_foundation",
            critic="sonic",
            severity=0.6,
            confidence=0.75,
            affected_dimensions=["weight", "energy"],
            evidence=[f"sub band energy: {sub:.2f} with bass tracks present"],
            recommended_actions=["Boost sub on kick/bass", "Check HPF not too aggressive"],
        ))

    # 3. Harsh top
    high = bands.get("high", 0)
    presence = bands.get("presence", 0)
    if (high + presence) > 0.8 and {"brightness", "clarity", "warmth"} & target_dims:
        issues.append(Issue(
            type="harsh_highs",
            critic="sonic",
            severity=min(1.0, ((high + presence) - 0.8) * 2.5),
            confidence=0.80,
            affected_dimensions=["brightness", "clarity"],
            evidence=[f"high+presence: {high + presence:.2f} (threshold: 0.8)"],
            recommended_actions=["Reduce high shelf on brightest element", "Add subtle LP filter"],
        ))

    # 4. Low headroom
    if rms is not None and rms > 0.9 and {"energy", "punch", "clarity"} & target_dims:
        issues.append(Issue(
            type="headroom_risk",
            critic="sonic",
            severity=min(1.0, (rms - 0.9) * 10),
            confidence=0.90,
            affected_dimensions=["energy", "clarity", "punch"],
            evidence=[f"RMS: {rms:.3f} (threshold: 0.9)"],
            recommended_actions=["Reduce master volume", "Lower loudest track", "Add limiter"],
        ))

    # 5. Flat dynamics (C1 fix: correct dB formula)
    if rms is not None and peak is not None and rms > 0 and peak > 0:
        crest_db = 20.0 * math.log10(peak / max(rms, 0.001))
        if crest_db < 3.0 and {"punch", "energy", "contrast"} & target_dims:
            issues.append(Issue(
                type="dynamics_flat",
                critic="sonic",
                severity=0.5,
                confidence=0.70,
                affected_dimensions=["punch", "contrast"],
                evidence=[f"crest factor: {crest_db:.1f} dB (threshold: 3 dB)"],
                recommended_actions=["Reduce compression", "Add transient shaper", "Reduce limiter"],
            ))

    return issues

def run_technical_critic(technical: dict) -> list[Issue]:
    """Check technical health of the session."""
    issues = []

    if not technical.get("analyzer_available", False):
        issues.append(Issue(
            type="analyzer_offline",
            critic="technical",
            severity=0.4,
            confidence=1.0,
            evidence=["LivePilot Analyzer not receiving data"],
            recommended_actions=["Load LivePilot_Analyzer.amxd on master track"],
        ))

    for dev in technical.get("unhealthy_devices", []):
        issues.append(Issue(
            type="unhealthy_plugin",
            critic="technical",
            severity=0.7,
            confidence=0.95,
            evidence=[f"Track {dev['track']}: {dev['device']} — {dev['flag']}"],
            recommended_actions=["Delete and replace with native Ableton device"],
        ))

    return issues


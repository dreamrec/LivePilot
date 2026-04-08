"""Agent OS V1 Engine — pure-computation core for goal compilation, world modeling,
critic analysis, and evaluation scoring.

Zero external dependencies beyond stdlib. All functions are pure — no I/O, no Ableton
connection, no network calls. The MCP tool wrappers in agent_os.py handle data fetching;
this module handles computation.

Design: spec at docs/AGENT_OS_V1.md, sections 6-12.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# ── Quality Dimensions ────────────────────────────────────────────────

QUALITY_DIMENSIONS = frozenset({
    "energy", "punch", "weight", "density", "brightness", "warmth",
    "width", "depth", "motion", "contrast", "clarity", "cohesion",
    "groove", "tension", "novelty", "polish", "emotion",
})

# Dimensions with measurable spectral proxies in Phase 1.
# Others (motion, contrast, groove, tension, novelty, polish, emotion, cohesion, depth)
# get confidence=0.0 — the LLM agent uses its own musical judgment for those.
#
# Note: "width" requires stereo width data (side/mid ratio) from compare_to_reference.
# Phase 1 does NOT have this in the sonic snapshot, so width is NOT measurable yet.
# It is intentionally excluded here until Phase 2 adds stereo analysis to the snapshot.
MEASURABLE_PROXIES: dict[str, str] = {
    "brightness": "high + presence bands (averaged)",
    "warmth": "low_mid band energy",
    "weight": "sub + low bands (averaged)",
    "clarity": "inverse of low_mid congestion",
    "density": "spectral flatness (geometric/arithmetic mean ratio)",
    "energy": "RMS level",
    "punch": "crest factor in dB (20*log10(peak/rms))",
}

VALID_MODES = frozenset({"observe", "improve", "explore", "finish", "diagnose"})
VALID_RESEARCH_MODES = frozenset({"none", "targeted", "deep"})


# ── GoalVector ────────────────────────────────────────────────────────

@dataclass
class GoalVector:
    """Compiled user intent as a machine-usable goal.

    targets: dimension → weight (0-1). Weights should approximately sum to 1.0.
    protect: dimension → minimum acceptable value (0-1). If a dimension drops
             below this value after a move, the move is undone.
    """
    request_text: str
    targets: dict[str, float] = field(default_factory=dict)
    protect: dict[str, float] = field(default_factory=dict)
    mode: str = "improve"
    aggression: float = 0.5
    research_mode: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)


def validate_goal_vector(
    request_text: str,
    targets: dict[str, float],
    protect: dict[str, float],
    mode: str,
    aggression: float,
    research_mode: str,
) -> GoalVector:
    """Validate and construct a GoalVector. Raises ValueError on invalid input."""
    if not request_text or not request_text.strip():
        raise ValueError("request_text cannot be empty")

    # Validate dimensions
    for dim in targets:
        if dim not in QUALITY_DIMENSIONS:
            raise ValueError(
                f"Unknown target dimension '{dim}'. "
                f"Valid: {sorted(QUALITY_DIMENSIONS)}"
            )
    for dim in protect:
        if dim not in QUALITY_DIMENSIONS:
            raise ValueError(
                f"Unknown protect dimension '{dim}'. "
                f"Valid: {sorted(QUALITY_DIMENSIONS)}"
            )

    # Validate weights are non-negative
    for dim, w in targets.items():
        if w < 0.0:
            raise ValueError(f"Target weight for '{dim}' must be >= 0.0, got {w}")
    for dim, w in protect.items():
        if not 0.0 <= w <= 1.0:
            raise ValueError(f"Protect threshold for '{dim}' must be 0.0-1.0, got {w}")

    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}, got '{mode}'")
    if research_mode not in VALID_RESEARCH_MODES:
        raise ValueError(
            f"research_mode must be one of {sorted(VALID_RESEARCH_MODES)}, "
            f"got '{research_mode}'"
        )
    if not 0.0 <= aggression <= 1.0:
        raise ValueError(f"aggression must be 0.0-1.0, got {aggression}")

    # Normalize target weights to sum to ~1.0 if they don't already
    total = sum(targets.values())
    if targets and total > 0:
        if abs(total - 1.0) > 0.01:
            targets = {k: v / total for k, v in targets.items()}

    return GoalVector(
        request_text=request_text.strip(),
        targets=targets,
        protect=protect,
        mode=mode,
        aggression=aggression,
        research_mode=research_mode,
    )


# ── WorldModel ────────────────────────────────────────────────────────

# Track role inference patterns — ordered by specificity
_ROLE_PATTERNS: list[tuple[str, str]] = [
    (r"kick|bd|bass\s*drum", "kick"),
    (r"snare|sd|snr", "snare"),
    (r"clap|cp|hand\s*clap", "clap"),
    (r"h(?:i)?[\s\-]?hat|hh|hat", "hihat"),
    (r"perc|percussion|conga|bongo|shaker|tamb", "percussion"),
    (r"sub\s*bass|sub", "sub_bass"),
    (r"bass|low", "bass"),
    (r"pad|atmosphere|atmo|ambient|drone", "pad"),
    (r"lead|melody|mel|synth\s*lead", "lead"),
    (r"chord|keys|piano|organ|rhodes", "chords"),
    (r"vocal|vox|voice", "vocal"),
    (r"fx|sfx|riser|sweep|noise|texture|tape", "texture"),
    (r"string", "strings"),
    (r"brass", "brass"),
    (r"resamp|bounce|bus|group|master", "utility"),
]


def infer_track_role(track_name: str) -> str:
    """Infer a track's musical role from its name. Returns 'unknown' if no match."""
    name_lower = track_name.lower().strip()
    for pattern, role in _ROLE_PATTERNS:
        if re.search(pattern, name_lower):
            return role
    return "unknown"


@dataclass
class WorldModel:
    """Session state snapshot for critic analysis."""
    topology: dict = field(default_factory=dict)
    sonic: Optional[dict] = None
    technical: dict = field(default_factory=dict)
    track_roles: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_world_model_from_data(
    session_info: dict,
    spectrum: Optional[dict] = None,
    rms: Optional[dict] = None,
    detected_key: Optional[dict] = None,
    flucoma_status: Optional[dict] = None,
    track_infos: Optional[list[dict]] = None,
) -> WorldModel:
    """Assemble a WorldModel from raw tool outputs.

    All parameters are optional — the model degrades gracefully when
    analyzer data is unavailable.
    """
    # Topology
    tracks = session_info.get("tracks", [])
    topology = {
        "tempo": session_info.get("tempo"),
        "time_signature": f"{session_info.get('signature_numerator', 4)}/{session_info.get('signature_denominator', 4)}",
        "track_count": session_info.get("track_count", 0),
        "return_count": session_info.get("return_track_count", 0),
        "scene_count": session_info.get("scene_count", 0),
        "is_playing": session_info.get("is_playing", False),
        "tracks": [
            {
                "index": t.get("index"),
                "name": t.get("name", ""),
                "has_midi": t.get("has_midi_input", False),
                "has_audio": t.get("has_audio_input", False),
                "mute": t.get("mute", False),
                "solo": t.get("solo", False),
                "arm": t.get("arm", False),
            }
            for t in tracks
        ],
    }

    # Track roles
    track_roles = {}
    for t in tracks:
        idx = t.get("index", 0)
        name = t.get("name", "")
        track_roles[idx] = infer_track_role(name)

    # Sonic state (None if analyzer unavailable)
    sonic = None
    if spectrum and spectrum.get("bands"):
        sonic = {
            "spectrum": spectrum.get("bands", {}),
            "rms": rms.get("rms") if rms else None,
            "peak": rms.get("peak") if rms else None,
            "key": detected_key.get("key") if detected_key else None,
            "scale": detected_key.get("scale") if detected_key else None,
            "key_confidence": detected_key.get("confidence") if detected_key else None,
        }

    # Technical state
    analyzer_available = spectrum is not None and bool(spectrum.get("bands"))
    flucoma_available = (
        flucoma_status is not None
        and flucoma_status.get("flucoma_available", False)
    )

    # Check plugin health from track_infos if provided
    unhealthy_devices = []
    if track_infos:
        for ti in track_infos:
            for dev in ti.get("devices", []):
                flags = dev.get("health_flags", [])
                if "opaque_or_failed_plugin" in flags:
                    unhealthy_devices.append({
                        "track": ti.get("index"),
                        "device": dev.get("name"),
                        "flag": "opaque_or_failed_plugin",
                    })

    technical = {
        "analyzer_available": analyzer_available,
        "flucoma_available": flucoma_available,
        "unhealthy_devices": unhealthy_devices,
    }

    return WorldModel(
        topology=topology,
        sonic=sonic,
        technical=technical,
        track_roles=track_roles,
    )


# ── Critics ───────────────────────────────────────────────────────────

@dataclass
class Issue:
    """A diagnosed problem or opportunity."""
    type: str
    critic: str  # "sonic" or "technical"
    severity: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    affected_dimensions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


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


# ── Evaluation Engine ─────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi] range."""
    return max(lo, min(hi, value))


def _extract_dimension_value(
    sonic: dict,
    dimension: str,
) -> Optional[float]:
    """Map a quality dimension to a measurable value from sonic data.

    Returns None for unmeasurable dimensions (confidence=0.0 in Phase 1).
    All returned values are clamped to 0.0-1.0 for consistent scoring.
    """
    if not sonic:
        return None
    # Accept both "spectrum" and "bands" keys — get_master_spectrum returns
    # {"bands": {...}} while the evaluator historically expected {"spectrum": {...}}.
    # Finding 2 fix: tolerate either shape so raw analyzer output works.
    bands = sonic.get("spectrum") or sonic.get("bands")
    if not bands:
        return None
    rms = sonic.get("rms")
    peak = sonic.get("peak")

    if dimension == "brightness":
        high = bands.get("high", 0)
        presence = bands.get("presence", 0)
        return _clamp((high + presence) / 2.0)
    elif dimension == "warmth":
        return _clamp(bands.get("low_mid", 0))
    elif dimension == "weight":
        sub = bands.get("sub", 0)
        low = bands.get("low", 0)
        return _clamp((sub + low) / 2.0)
    elif dimension == "clarity":
        low_mid = bands.get("low_mid", 0)
        return _clamp(1.0 - low_mid)
    elif dimension == "density":
        # Spectral flatness: geometric mean / arithmetic mean of band values.
        # Higher = more evenly distributed energy (noise-like).
        # Lower = more tonal (energy concentrated in few bands).
        vals = [max(v, 1e-10) for v in bands.values() if isinstance(v, (int, float))]
        if not vals:
            return None
        geo_mean = math.exp(sum(math.log(v) for v in vals) / len(vals))
        arith_mean = sum(vals) / len(vals)
        return _clamp(geo_mean / max(arith_mean, 1e-10))
    elif dimension == "energy":
        return _clamp(rms) if rms is not None else None
    elif dimension == "punch":
        if rms and peak and rms > 0:
            crest_db = 20.0 * math.log10(max(peak / rms, 1.0))
            # Normalize: 0 dB = 0.0, 20 dB = 1.0
            return _clamp(crest_db / 20.0)
        return None
    else:
        # Unmeasurable in Phase 1 (width, depth, motion, contrast,
        # groove, tension, novelty, polish, emotion, cohesion)
        return None


def compute_evaluation_score(
    goal: GoalVector,
    before_sonic: dict,
    after_sonic: dict,
) -> dict:
    """Compute whether a move improved the mix toward the goal.

    Returns:
        {
            "score": float (0-1),
            "keep_change": bool,
            "goal_progress": float (-1 to 1),
            "collateral_damage": float (0-1),
            "measurable_delta": float (-1 to 1),
            "notes": list[str],
            "dimension_changes": dict,
            "consecutive_undo_hint": bool,
        }
    """
    notes: list[str] = []
    dimension_changes: dict[str, dict] = {}

    # Compute per-dimension deltas
    total_goal_progress = 0.0
    measurable_count = 0

    for dim, weight in goal.targets.items():
        before_val = _extract_dimension_value(before_sonic, dim)
        after_val = _extract_dimension_value(after_sonic, dim)

        if before_val is not None and after_val is not None:
            delta = after_val - before_val
            dimension_changes[dim] = {
                "before": round(before_val, 4),
                "after": round(after_val, 4),
                "delta": round(delta, 4),
            }
            total_goal_progress += delta * weight
            measurable_count += 1
        else:
            notes.append(f"{dim}: not measurable in Phase 1 (confidence=0.0)")

    # Check protected dimensions (C3 fix: use the actual threshold)
    collateral_damage = 0.0
    protection_violated = False

    for dim, threshold in goal.protect.items():
        before_val = _extract_dimension_value(before_sonic, dim)
        after_val = _extract_dimension_value(after_sonic, dim)

        if before_val is not None and after_val is not None:
            drop = before_val - after_val
            if drop > 0:
                collateral_damage = max(collateral_damage, drop)
            # Violation: value dropped below the user's threshold
            if after_val < threshold:
                protection_violated = True
                notes.append(
                    f"PROTECTED dimension '{dim}' at {after_val:.3f}, "
                    f"below threshold {threshold:.3f}"
                )
            # Also flag large drops even if still above threshold
            elif drop > 0.15:
                protection_violated = True
                notes.append(
                    f"PROTECTED dimension '{dim}' dropped by {drop:.3f} "
                    f"(absolute drop > 0.15)"
                )

    # Measurable delta (average improvement across measured dimensions)
    measurable_delta = total_goal_progress / max(measurable_count, 1)

    # Compute composite score (spec section 12.2)
    # I4 fix: reduce constant floor — use 0.0 for placeholders instead of fake values
    goal_fit = _clamp(0.5 + total_goal_progress)
    measurable_component = _clamp(0.5 + measurable_delta)
    preservation = _clamp(1.0 - collateral_damage * 5)
    confidence = measurable_count / max(len(goal.targets), 1)

    score = (
        0.30 * goal_fit
        + 0.25 * measurable_component
        + 0.15 * preservation
        + 0.10 * 0.0   # taste_fit: Phase 2 (no free floor)
        + 0.10 * confidence
        + 0.10 * 1.0   # reversibility: 1.0 for undo-able moves
    )

    # Hard rules
    keep_change = True

    if measurable_count > 0 and measurable_delta <= 0:
        keep_change = False
        notes.append("HARD RULE: measurable delta <= 0 — no measurable improvement")

    if protection_violated:
        keep_change = False
        notes.append("HARD RULE: protected dimension violated")

    if score < 0.40:
        keep_change = False
        notes.append(f"HARD RULE: total score {score:.3f} < 0.40 threshold")

    if measurable_count == 0 and not protection_violated:
        # All TARGET dimensions unmeasurable AND no protection violations —
        # defer keep/undo to the agent's musical judgment.
        # IMPORTANT: protection violations still force undo even when
        # targets are unmeasurable (Finding 1 fix).
        keep_change = True
        notes.append(
            "No measurable target dimensions — deferring keep/undo to agent musical judgment"
        )

    return {
        "score": round(score, 4),
        "keep_change": keep_change,
        "goal_progress": round(total_goal_progress, 4),
        "collateral_damage": round(collateral_damage, 4),
        "measurable_delta": round(measurable_delta, 4),
        "measurable_dimensions": measurable_count,
        "total_dimensions": len(goal.targets),
        "dimension_changes": dimension_changes,
        "notes": notes,
        # I5: hint for the agent to track consecutive undos
        "consecutive_undo_hint": not keep_change,
    }


# ── Technique Cards (Round 2) ─────────────────────────────────────────

@dataclass
class TechniqueCard:
    """A structured, reusable production recipe — not just text."""
    problem: str
    context: list[str] = field(default_factory=list)  # genre/style tags
    devices: list[str] = field(default_factory=list)  # what to load
    method: str = ""  # step-by-step instructions
    verification: list[str] = field(default_factory=list)  # what to check after
    evidence: dict = field(default_factory=dict)  # {sources, in_session_tested}

    def to_dict(self) -> dict:
        return asdict(self)

    def to_memory_payload(self) -> dict:
        """Convert to a payload suitable for memory_learn(type='technique_card')."""
        return {
            "problem": self.problem,
            "context": self.context,
            "devices": self.devices,
            "method": self.method,
            "verification": self.verification,
            "evidence": self.evidence,
        }


def build_technique_card_from_outcome(outcome: dict) -> Optional[TechniqueCard]:
    """Extract a technique card from a successful outcome.

    Only produces a card if the outcome was kept and had meaningful improvement.
    """
    if not outcome.get("kept", False):
        return None
    if outcome.get("score", 0) < 0.6:
        return None

    gv = outcome.get("goal_vector", {})
    move = outcome.get("move", {})
    dim_changes = outcome.get("dimension_changes", {})

    # Build problem description from goal
    targets = gv.get("targets", {})
    if not targets:
        return None

    top_dim = max(targets.items(), key=lambda x: x[1])[0] if targets else "general"
    problem = f"Improve {top_dim} in production"

    # Build method from move
    method = move.get("name", "unknown technique")
    if isinstance(move.get("actions"), list):
        method = " → ".join(move["actions"])

    # Build verification from dimension changes
    verification = []
    for dim, change in dim_changes.items():
        if isinstance(change, dict) and change.get("delta", 0) > 0:
            verification.append(f"{dim} should improve (was +{change['delta']:.3f})")

    return TechniqueCard(
        problem=problem,
        context=list(gv.get("tags", [])) if isinstance(gv.get("tags"), list) else [],
        devices=move.get("devices", []) if isinstance(move.get("devices"), list) else [],
        method=method,
        verification=verification,
        evidence={"score": outcome.get("score", 0), "in_session_tested": True},
    )


# ── Outcome Memory Analysis (Round 1) ────────────────────────────────

def analyze_outcome_history(outcomes: list[dict]) -> dict:
    """Analyze accumulated outcome memories to identify user taste patterns.

    outcomes: list of outcome technique payloads from memory_list(type="outcome")
    Returns taste analysis: keep rate, dimension success, inferred preferences.
    """
    if not outcomes:
        return {
            "total_outcomes": 0,
            "keep_rate": 0.0,
            "dimension_success": {},
            "common_kept_moves": [],
            "common_undone_moves": [],
            "taste_vector": {},
            "notes": ["No outcome history — use the evaluation loop to build taste data"],
        }

    total = len(outcomes)
    kept = [o for o in outcomes if o.get("kept", False)]
    undone = [o for o in outcomes if not o.get("kept", False)]
    keep_rate = len(kept) / total

    # Dimension success: average improvement per dimension when kept
    dimension_success: dict[str, list[float]] = {}
    for o in kept:
        for dim, change in o.get("dimension_changes", {}).items():
            delta = change.get("delta", 0) if isinstance(change, dict) else 0
            dimension_success.setdefault(dim, []).append(delta)

    avg_dimension_success = {
        dim: round(sum(vals) / len(vals), 4)
        for dim, vals in dimension_success.items()
        if vals
    }

    # Common move types
    kept_moves = {}
    undone_moves = {}
    for o in kept:
        move_name = o.get("move", {}).get("name", "unknown") if isinstance(o.get("move"), dict) else "unknown"
        kept_moves[move_name] = kept_moves.get(move_name, 0) + 1
    for o in undone:
        move_name = o.get("move", {}).get("name", "unknown") if isinstance(o.get("move"), dict) else "unknown"
        undone_moves[move_name] = undone_moves.get(move_name, 0) + 1

    common_kept = sorted(kept_moves.items(), key=lambda x: -x[1])[:5]
    common_undone = sorted(undone_moves.items(), key=lambda x: -x[1])[:5]

    # Taste vector: which dimensions does this user care about?
    # Weight by how often each dimension appears in kept outcomes
    taste_vector: dict[str, float] = {}
    for o in kept:
        gv = o.get("goal_vector", {})
        targets = gv.get("targets", {}) if isinstance(gv, dict) else {}
        for dim, weight in targets.items():
            taste_vector[dim] = taste_vector.get(dim, 0) + weight

    # Normalize
    taste_total = sum(taste_vector.values())
    if taste_total > 0:
        taste_vector = {k: round(v / taste_total, 3) for k, v in taste_vector.items()}

    notes = []
    if keep_rate < 0.3:
        notes.append(f"Low keep rate ({keep_rate:.0%}) — agent may be too aggressive")
    if keep_rate > 0.8:
        notes.append(f"High keep rate ({keep_rate:.0%}) — agent is well-calibrated or too conservative")

    return {
        "total_outcomes": total,
        "kept": len(kept),
        "undone": len(undone),
        "keep_rate": round(keep_rate, 3),
        "dimension_success": avg_dimension_success,
        "common_kept_moves": [{"move": m, "count": c} for m, c in common_kept],
        "common_undone_moves": [{"move": m, "count": c} for m, c in common_undone],
        "taste_vector": taste_vector,
        "notes": notes,
    }

"""Hook Hunter analysis — pure computation, zero I/O.

Identifies hooks, ranks candidates, scores phrase impact, and
detects payoff failures.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Optional

from .models import HookCandidate, PayoffFailure, PhraseImpact


# ── Hook detection ────────────────────────────────────────────────


def find_hook_candidates(
    tracks: list[dict],
    motif_data: Optional[dict] = None,
    scene_data: Optional[list[dict]] = None,
    composition: Optional[dict] = None,
) -> list[HookCandidate]:
    """Detect and rank hook candidates from session data.

    Looks for: salient melodic motifs, distinctive rhythmic cells,
    signature timbral textures, recurring harmonic progressions.
    """
    motif_data = motif_data or {}
    scene_data = scene_data or []
    composition = composition or {}
    candidates: list[HookCandidate] = []

    # 1. Motif-based hooks
    for motif in motif_data.get("motifs", []):
        salience = motif.get("salience", 0)
        recurrence = motif.get("recurrence", 0)
        if salience > 0.2 or recurrence > 0.3:
            candidates.append(HookCandidate(
                hook_id=f"motif_{motif.get('name', 'unknown')}",
                hook_type="melodic",
                description=motif.get("description", motif.get("name", "motif")),
                location=motif.get("location", ""),
                memorability=min(1.0, salience * 1.2),
                recurrence=recurrence,
                contrast_potential=motif.get("contrast", 0.5),
                development_potential=_estimate_development_potential(motif),
            ))

    # 2. Track-name-based detection (lead, hook, melody, riff)
    hook_keywords = {"lead", "hook", "melody", "riff", "main", "top", "vocal", "synth"}
    for track in tracks:
        name = track.get("name", "").lower()
        if any(kw in name for kw in hook_keywords):
            candidates.append(HookCandidate(
                hook_id=f"track_{name.replace(' ', '_')}",
                hook_type="melodic" if "melody" in name or "vocal" in name else "timbral",
                description=f"Track: {track.get('name', name)}",
                location=track.get("name", ""),
                memorability=0.5,
                recurrence=0.6,  # present across scenes typically
                contrast_potential=0.5,
                development_potential=0.6,
            ))

    # 3. Rhythmic hooks from drum/percussion patterns
    rhythm_keywords = {"drum", "beat", "perc", "hat", "kick", "clap"}
    groove_tracks = [t for t in tracks if any(kw in t.get("name", "").lower() for kw in rhythm_keywords)]
    if groove_tracks:
        # Check for distinctive rhythmic patterns via clip reuse
        clip_reuse = _measure_clip_reuse(scene_data, groove_tracks)
        if clip_reuse > 0.5:
            candidates.append(HookCandidate(
                hook_id="groove_pattern",
                hook_type="rhythmic",
                description="Primary groove pattern",
                location=groove_tracks[0].get("name", "drums"),
                memorability=0.5,
                recurrence=clip_reuse,
                contrast_potential=0.4,
                development_potential=0.5,
            ))

    # Score all candidates
    for c in candidates:
        c.salience = _compute_salience(c)

    # Sort by salience
    candidates.sort(key=lambda c: c.salience, reverse=True)
    return candidates


def find_primary_hook(
    tracks: list[dict],
    motif_data: Optional[dict] = None,
    scene_data: Optional[list[dict]] = None,
    composition: Optional[dict] = None,
) -> Optional[HookCandidate]:
    """Find the single most salient hook in the session."""
    candidates = find_hook_candidates(tracks, motif_data, scene_data, composition)
    return candidates[0] if candidates else None


# ── Phrase impact scoring ─────────────────────────────────────────


def score_phrase_impact(
    section_data: dict,
    target: str = "hook",
    song_brain: Optional[dict] = None,
    prev_section: Optional[dict] = None,
) -> PhraseImpact:
    """Score the emotional impact of a musical phrase/section.

    Uses contrast, density shift, harmonic support, and energy
    to judge whether the phrase "lands" emotionally.
    """
    song_brain = song_brain or {}
    prev_section = prev_section or {}

    energy = section_data.get("energy", 0.5)
    prev_energy = prev_section.get("energy", 0.5)
    density = section_data.get("density", 0.5)
    prev_density = prev_section.get("density", 0.5)

    # Arrival: big energy jump = strong arrival
    energy_delta = energy - prev_energy
    arrival = min(1.0, max(0.0, energy_delta * 2 + 0.3))

    # Anticipation: was there a dip before?
    anticipation = min(1.0, max(0.0, (0.5 - prev_energy) * 2)) if prev_energy < 0.5 else 0.2

    # Contrast: density or energy change
    contrast = min(1.0, abs(density - prev_density) + abs(energy_delta))

    # Repetition fatigue: high density with no change = fatiguing
    fatigue = max(0.0, 1.0 - contrast) * 0.5

    # Section clarity: does it have a clear role?
    clarity = 0.7 if section_data.get("label") else 0.3

    # Groove continuity: rhythm present
    groove = 0.7 if section_data.get("has_drums", True) else 0.3

    # Payoff balance
    payoff = min(1.0, (arrival + anticipation) / 2)

    # Composite — target-specific weighting
    weights = _get_target_weights(target)
    composite = (
        arrival * weights.get("arrival", 0.2)
        + anticipation * weights.get("anticipation", 0.15)
        + contrast * weights.get("contrast", 0.2)
        + (1.0 - fatigue) * weights.get("freshness", 0.1)
        + clarity * weights.get("clarity", 0.1)
        + groove * weights.get("groove", 0.1)
        + payoff * weights.get("payoff", 0.15)
    )

    section_id = section_data.get("id", section_data.get("name", ""))

    return PhraseImpact(
        phrase_id=f"phrase_{hashlib.sha256(str(section_id).encode()).hexdigest()[:8]}",
        target=target,
        arrival_strength=round(arrival, 3),
        anticipation_strength=round(anticipation, 3),
        contrast_quality=round(contrast, 3),
        repetition_fatigue=round(fatigue, 3),
        section_clarity=round(clarity, 3),
        groove_continuity=round(groove, 3),
        payoff_balance=round(payoff, 3),
        composite_impact=round(composite, 3),
    )


def compare_phrase_impacts(
    impacts: list[PhraseImpact],
) -> list[dict]:
    """Rank multiple phrase impacts by composite score."""
    ranked = sorted(impacts, key=lambda i: i.composite_impact, reverse=True)
    return [
        {
            "rank": idx + 1,
            "phrase_id": imp.phrase_id,
            "target": imp.target,
            "composite_impact": imp.composite_impact,
            "arrival_strength": imp.arrival_strength,
            "contrast_quality": imp.contrast_quality,
        }
        for idx, imp in enumerate(ranked)
    ]


# ── Payoff failure detection ─────────────────────────────────────


def detect_payoff_failures(
    sections: list[dict],
    song_brain: Optional[dict] = None,
) -> list[PayoffFailure]:
    """Detect sections that should deliver a payoff but don't."""
    song_brain = song_brain or {}
    payoff_targets = song_brain.get("payoff_targets", [])
    failures: list[PayoffFailure] = []

    for i, section in enumerate(sections):
        section_id = section.get("id", section.get("name", f"section_{i}"))
        label = section.get("label", "").lower()
        energy = section.get("energy", 0.5)
        prev_energy = sections[i - 1].get("energy", 0.5) if i > 0 else 0.3

        is_payoff = (
            section_id in payoff_targets
            or label in ("chorus", "drop", "hook")
            or section.get("is_payoff", False)
        )

        if not is_payoff:
            continue

        # Check for flat arrival (no energy increase)
        if energy - prev_energy < 0.1:
            failures.append(PayoffFailure(
                section_id=section_id,
                expected_target=label or "payoff",
                failure_type="flat_arrival",
                severity=0.6,
                suggestion="Increase energy contrast — try subtracting before the payoff section",
            ))

        # Check for weak contrast (only if flat_arrival didn't already fire)
        elif i > 0 and abs(energy - prev_energy) < 0.05:
            failures.append(PayoffFailure(
                section_id=section_id,
                expected_target=label or "payoff",
                failure_type="weak_contrast",
                severity=0.5,
                suggestion="Add density or timbral contrast leading into this section",
            ))

    return failures


def suggest_payoff_repairs(
    failures: list[PayoffFailure],
) -> list[dict]:
    """Generate repair suggestions for payoff failures."""
    repairs = []
    for f in failures:
        repair = {
            "section_id": f.section_id,
            "failure_type": f.failure_type,
            "severity": f.severity,
            "suggestion": f.suggestion,
        }

        # Add specific repair strategies
        if f.failure_type == "flat_arrival":
            repair["strategies"] = [
                "Add a 2-4 bar breakdown before this section",
                "Use a filter sweep or riser to build anticipation",
                "Strip elements in the preceding section to create contrast",
            ]
        elif f.failure_type == "weak_contrast":
            repair["strategies"] = [
                "Increase track count or add a new element at the payoff",
                "Change the harmonic content (key change, chord substitution)",
                "Add rhythmic variation (double-time feel, new percussion)",
            ]
        elif f.failure_type == "no_setup":
            repair["strategies"] = [
                "Add a buildup section before the payoff",
                "Use automation to create a gradual energy ramp",
            ]
        else:
            repair["strategies"] = [f.suggestion]

        repairs.append(repair)

    return repairs


# ── Helpers ───────────────────────────────────────────────────────


def _compute_salience(c: HookCandidate) -> float:
    """Compute composite salience score for a hook candidate."""
    return round(
        c.memorability * 0.35
        + c.recurrence * 0.25
        + c.contrast_potential * 0.2
        + c.development_potential * 0.2,
        3,
    )


def _estimate_development_potential(motif: dict) -> float:
    """Estimate how much room a motif has for development."""
    # Simple heuristic: shorter motifs have more development room
    length = motif.get("length_beats", 4)
    if length <= 2:
        return 0.8
    elif length <= 4:
        return 0.6
    elif length <= 8:
        return 0.4
    return 0.3


def _measure_clip_reuse(scene_data: list[dict], target_tracks: list[dict]) -> float:
    """Measure how much clips are reused across scenes for target tracks."""
    if not scene_data:
        return 0.0

    target_names = {t.get("name", "").lower() for t in target_tracks}
    clip_names = Counter()

    for scene in scene_data:
        for clip in scene.get("clips", []):
            clip_name = clip.get("name", "") if isinstance(clip, dict) else str(clip)
            track_name = clip.get("track", "") if isinstance(clip, dict) else ""
            if track_name.lower() in target_names and clip_name:
                clip_names[clip_name] += 1

    if not clip_names:
        return 0.0

    max_reuse = max(clip_names.values())
    return min(1.0, max_reuse / max(len(scene_data), 1))


def _get_target_weights(target: str) -> dict:
    """Get scoring weights based on target type."""
    presets = {
        "hook": {"arrival": 0.15, "anticipation": 0.1, "contrast": 0.2, "freshness": 0.15, "clarity": 0.1, "groove": 0.1, "payoff": 0.2},
        "drop": {"arrival": 0.3, "anticipation": 0.2, "contrast": 0.2, "freshness": 0.05, "clarity": 0.05, "groove": 0.1, "payoff": 0.1},
        "chorus": {"arrival": 0.2, "anticipation": 0.15, "contrast": 0.15, "freshness": 0.1, "clarity": 0.15, "groove": 0.1, "payoff": 0.15},
        "transition": {"arrival": 0.1, "anticipation": 0.1, "contrast": 0.3, "freshness": 0.1, "clarity": 0.1, "groove": 0.15, "payoff": 0.15},
        "loop": {"arrival": 0.05, "anticipation": 0.05, "contrast": 0.1, "freshness": 0.25, "clarity": 0.1, "groove": 0.3, "payoff": 0.15},
    }
    return presets.get(target, presets["hook"])

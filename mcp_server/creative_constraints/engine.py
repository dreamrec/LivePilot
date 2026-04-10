"""Creative Constraints engine — pure computation, zero I/O.

Handles constraint application, reference distillation, and
constrained variant generation.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .models import (
    CONSTRAINT_MODES,
    ConstraintSet,
    ReferenceDistillation,
    ReferencePrinciple,
)


# ── Constraint application ────────────────────────────────────────


def build_constraint_set(
    constraints: list[str],
    session_info: Optional[dict] = None,
) -> ConstraintSet:
    """Validate and build a constraint set."""
    valid = [c for c in constraints if c in CONSTRAINT_MODES]
    invalid = [c for c in constraints if c not in CONSTRAINT_MODES]

    descriptions = {
        "use_loaded_devices_only": "Only use devices already loaded in the session",
        "no_new_tracks": "Work within existing tracks — no new tracks",
        "subtraction_only": "Only remove or reduce — no additions",
        "arrangement_only": "Only arrangement changes — no sound design or mixing",
        "mood_shift_without_new_fx": "Shift the mood using only existing tools",
        "make_it_stranger_but_keep_the_hook": "Push novelty while preserving the hook",
        "club_translation_safe": "Keep changes club/DJ-friendly",
        "performance_safe_creative": "Only changes safe for live performance",
    }

    desc_parts = [descriptions.get(c, c) for c in valid]

    reasons = {
        "use_loaded_devices_only": "Forces creative use of existing palette",
        "no_new_tracks": "Keeps complexity manageable",
        "subtraction_only": "Sometimes less is more — helps find the essence",
        "arrangement_only": "Separates arrangement thinking from production details",
        "mood_shift_without_new_fx": "Tests whether the composition carries the mood",
        "make_it_stranger_but_keep_the_hook": "Pushes boundaries safely",
        "club_translation_safe": "Ensures dancefloor viability",
        "performance_safe_creative": "Ensures live-safe changes",
    }

    reason_parts = [reasons.get(c, "") for c in valid if c in reasons]

    cs = ConstraintSet(
        constraints=valid,
        description="; ".join(desc_parts),
        reason="; ".join(reason_parts),
    )

    return cs


def validate_plan_against_constraints(
    plan: dict,
    constraint_set: ConstraintSet,
    session_info: Optional[dict] = None,
) -> dict:
    """Check whether a plan respects the active constraints."""
    session_info = session_info or {}
    violations: list[str] = []
    warnings: list[str] = []

    steps = plan.get("steps", [])

    for constraint in constraint_set.constraints:
        if constraint == "no_new_tracks":
            for step in steps:
                action = step.get("action", "")
                if action in ("create_midi_track", "create_audio_track", "create_return_track"):
                    violations.append(f"Step creates a new track ({action}) — violates no_new_tracks")

        elif constraint == "subtraction_only":
            add_actions = {"create_clip", "create_midi_track", "create_audio_track",
                          "duplicate_clip", "duplicate_track"}
            for step in steps:
                if step.get("action", "") in add_actions:
                    violations.append(f"Step adds content ({step['action']}) — violates subtraction_only")

        elif constraint == "arrangement_only":
            mix_actions = {"set_device_parameter", "set_track_volume", "set_track_pan",
                          "set_send_level"}
            for step in steps:
                if step.get("action", "") in mix_actions:
                    warnings.append(f"Step modifies mix ({step['action']}) — arrangement_only prefers structural changes")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "constraint_count": len(constraint_set.constraints),
    }


# ── Reference distillation ────────────────────────────────────────


def distill_reference_principles(
    reference_profile: dict,
    reference_description: str = "",
) -> ReferenceDistillation:
    """Distill musical principles from a reference profile.

    Extracts emotional posture, density motion, arrangement patience,
    texture treatment, and payoff architecture — never surface traits.
    """
    ref_id = hashlib.sha256(str(reference_profile).encode()).hexdigest()[:10]

    principles: list[ReferencePrinciple] = []

    # Emotional posture
    emotional = reference_profile.get("emotional_stance", "")
    if emotional:
        principles.append(ReferencePrinciple(
            domain="emotional",
            principle=f"Emotional posture: {emotional}",
            value=0.0,
            applicability=0.7,
            note="Apply the feeling, not the specific sounds",
        ))

    # Density motion
    density_arc = reference_profile.get("density_arc", [])
    if density_arc:
        motion = _describe_density_motion(density_arc)
        principles.append(ReferencePrinciple(
            domain="density",
            principle=f"Density motion: {motion}",
            value=sum(density_arc) / len(density_arc) if density_arc else 0.5,
            applicability=0.6,
        ))

    # Arrangement patience
    pacing = reference_profile.get("section_pacing", [])
    if pacing:
        avg_bars = sum(s.get("bars", 8) for s in pacing) / max(len(pacing), 1)
        patience = "patient" if avg_bars > 16 else "moderate" if avg_bars > 8 else "rapid"
        principles.append(ReferencePrinciple(
            domain="arrangement",
            principle=f"Arrangement patience: {patience} (avg {avg_bars:.0f} bars/section)",
            value=avg_bars,
            applicability=0.7,
        ))

    # Width/space strategy
    width = reference_profile.get("width_depth", {})
    if width:
        w_val = width.get("stereo_width", 0.5)
        strategy = "wide" if w_val > 0.7 else "focused" if w_val < 0.3 else "balanced"
        principles.append(ReferencePrinciple(
            domain="width",
            principle=f"Width strategy: {strategy} stereo field",
            value=w_val,
            applicability=0.5,
        ))

    # Spectral character
    spectral = reference_profile.get("spectral_contour", {})
    if spectral:
        balance = spectral.get("band_balance", {})
        if balance:
            dominant = max(balance.items(), key=lambda kv: kv[1], default=("mid", 0.5))
            principles.append(ReferencePrinciple(
                domain="spectral",
                principle=f"Spectral emphasis: {dominant[0]}-forward",
                value=dominant[1],
                applicability=0.5,
            ))

    # Groove posture
    groove = reference_profile.get("groove_posture", {})
    if groove:
        swing = groove.get("swing", 0)
        groove_desc = "swung" if swing > 20 else "straight" if swing < 5 else "lightly swung"
        principles.append(ReferencePrinciple(
            domain="groove",
            principle=f"Groove feel: {groove_desc}",
            value=swing,
            applicability=0.6,
        ))

    return ReferenceDistillation(
        reference_id=ref_id,
        reference_description=reference_description,
        principles=principles,
        emotional_posture=emotional,
        density_motion=_describe_density_motion(density_arc) if density_arc else "",
        arrangement_patience=f"{sum(s.get('bars', 8) for s in pacing) / max(len(pacing), 1):.0f} bars avg" if pacing else "",
        texture_treatment=reference_profile.get("harmonic_character", ""),
        foreground_background="",
        width_strategy=width.get("description", "") if isinstance(width, dict) else "",
        payoff_architecture="",
    )


def map_principles_to_song(
    song_brain: dict,
    distillation: ReferenceDistillation,
) -> list[dict]:
    """Map reference principles to the current song's context.

    Translates each principle through the song's identity, loaded tools,
    and hook identity. Never outputs a plan that simply copies surface traits.
    """
    identity = song_brain.get("identity_core", "")
    sacred = [e.get("description", "") for e in song_brain.get("sacred_elements", [])]

    mappings = []
    for p in distillation.principles:
        mapping = {
            "principle": p.principle,
            "domain": p.domain,
            "applicability": p.applicability,
            "in_your_song": _translate_principle(p, identity, sacred),
            "preserves": "Adapts the principle while maintaining your song's identity",
        }
        mappings.append(mapping)

    return mappings


# ── Helpers ───────────────────────────────────────────────────────


def _describe_density_motion(arc: list[float]) -> str:
    """Describe the density arc pattern."""
    if len(arc) < 2:
        return "static"

    # Check for patterns
    increasing = all(arc[i] <= arc[i + 1] for i in range(len(arc) - 1))
    decreasing = all(arc[i] >= arc[i + 1] for i in range(len(arc) - 1))

    if increasing:
        return "steadily building"
    if decreasing:
        return "gradually thinning"

    # Find peak position
    peak_idx = arc.index(max(arc))
    peak_pct = peak_idx / max(len(arc) - 1, 1)

    if peak_pct < 0.3:
        return "front-loaded density"
    elif peak_pct > 0.7:
        return "late-peak density"
    else:
        return "centered density arc"


def _translate_principle(
    principle: ReferencePrinciple,
    identity: str,
    sacred: list[str],
) -> str:
    """Translate a reference principle into current-song language."""
    translations = {
        "emotional": f"Channel the {principle.principle.split(': ')[-1]} feeling through your existing palette",
        "density": f"Apply {principle.principle.split(': ')[-1]} while keeping your identity ({identity})",
        "arrangement": f"Use {principle.principle.split(': ')[-1]} pacing to develop your song's structure",
        "width": f"Apply this stereo approach while preserving your groove",
        "spectral": f"Lean into this spectral emphasis using your existing sounds",
        "groove": f"Adapt this groove feel to your rhythm section",
    }
    return translations.get(principle.domain, f"Apply: {principle.principle}")

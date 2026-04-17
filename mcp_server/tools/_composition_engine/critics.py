"""Part of the _composition_engine package — extracted from the single-file engine.

Pure-computation core, no external deps. Callers should import from the package
facade (e.g. `from mcp_server.tools._composition_engine import X`), which
re-exports everything from these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from .models import SectionType, RoleType, SectionNode, PhraseUnit, RoleNode, CompositionIssue, HarmonyField

def run_form_critic(sections: list[SectionNode]) -> list[CompositionIssue]:
    """Critique the overall form/structure of the arrangement."""
    issues = []
    if not sections:
        issues.append(CompositionIssue(
            issue_type="no_sections",
            critic="form",
            severity=0.8,
            confidence=1.0,
            evidence="No sections detected in the arrangement",
            recommended_moves=["create_sections", "add_scene_structure"],
        ))
        return issues

    # 1. Too few sections for a full track
    if len(sections) < 3:
        issues.append(CompositionIssue(
            issue_type="too_few_sections",
            critic="form",
            severity=0.6,
            confidence=0.8,
            evidence=f"Only {len(sections)} section(s) detected",
            recommended_moves=["section_expansion", "add_contrast_section"],
        ))

    # 2. No energy arc (all sections similar energy)
    if len(sections) >= 2:
        energies = [s.energy for s in sections]
        energy_range = max(energies) - min(energies)
        if energy_range < 0.15:
            issues.append(CompositionIssue(
                issue_type="flat_energy_arc",
                critic="form",
                severity=0.7,
                confidence=0.75,
                evidence=f"Energy range: {energy_range:.2f} (all sections similar density)",
                recommended_moves=["vary_track_count", "add_build_section", "create_breakdown"],
            ))

    # 3. No contrast between adjacent sections
    for i in range(1, len(sections)):
        prev = sections[i - 1]
        curr = sections[i]
        energy_diff = abs(curr.energy - prev.energy)
        density_diff = abs(curr.density - prev.density)
        if energy_diff < 0.1 and density_diff < 0.1:
            issues.append(CompositionIssue(
                issue_type="no_adjacent_contrast",
                critic="form",
                severity=0.5,
                confidence=0.7,
                scope={"sections": [prev.section_id, curr.section_id]},
                evidence=f"Sections '{prev.name or prev.section_id}' and '{curr.name or curr.section_id}' have similar energy/density",
                recommended_moves=["thin_one_section", "add_element_to_one", "vary_automation"],
            ))

    # 4. First section too dense (reveals too much too early)
    if sections and sections[0].density > 0.7:
        issues.append(CompositionIssue(
            issue_type="intro_too_dense",
            critic="form",
            severity=0.5,
            confidence=0.65,
            scope={"section_id": sections[0].section_id},
            evidence=f"First section density: {sections[0].density:.2f} (reveals too much)",
            recommended_moves=["remove_elements_from_intro", "defer_reveal"],
        ))

    return issues

def run_section_identity_critic(
    sections: list[SectionNode],
    roles: list[RoleNode],
) -> list[CompositionIssue]:
    """Critique individual section identity and clarity."""
    issues = []

    for section in sections:
        section_roles = [r for r in roles if r.section_id == section.section_id]
        foreground_count = sum(1 for r in section_roles if r.foreground)

        # 1. No clear foreground element
        if foreground_count == 0 and len(section_roles) > 0:
            issues.append(CompositionIssue(
                issue_type="no_foreground",
                critic="section_identity",
                severity=0.6,
                confidence=0.70,
                scope={"section_id": section.section_id},
                evidence=f"Section '{section.name or section.section_id}' has {len(section_roles)} tracks but none inferred as foreground",
                recommended_moves=["assign_lead_role", "add_hook_element"],
            ))

        # 2. Too many foreground voices
        if foreground_count > 3:
            issues.append(CompositionIssue(
                issue_type="too_many_foregrounds",
                critic="section_identity",
                severity=0.5,
                confidence=0.65,
                scope={"section_id": section.section_id},
                evidence=f"Section has {foreground_count} foreground elements (max recommended: 3)",
                recommended_moves=["background_some_elements", "thin_section", "use_automation_to_rotate"],
            ))

        # 3. Section type mismatch — e.g., "chorus" less energetic than "verse"
        # (Compare against adjacent sections of different type)

    # Cross-section type check
    choruses = [s for s in sections if s.section_type == SectionType.CHORUS]
    verses = [s for s in sections if s.section_type == SectionType.VERSE]
    if choruses and verses:
        chorus_energy = max(s.energy for s in choruses)
        verse_energy = max(s.energy for s in verses)
        if chorus_energy <= verse_energy:
            issues.append(CompositionIssue(
                issue_type="chorus_not_stronger_than_verse",
                critic="section_identity",
                severity=0.6,
                confidence=0.60,
                evidence=f"Chorus energy ({chorus_energy:.2f}) <= verse energy ({verse_energy:.2f})",
                recommended_moves=["add_elements_to_chorus", "thin_verse", "add_chorus_hook"],
            ))

    return issues

def run_phrase_critic(phrases: list[PhraseUnit]) -> list[CompositionIssue]:
    """Critique phrase structure within sections."""
    issues = []

    if len(phrases) < 2:
        return issues

    # 1. All phrases identical length (no variation)
    lengths = [p.length_bars() for p in phrases]
    unique_lengths = set(lengths)
    if len(unique_lengths) == 1 and len(phrases) > 3:
        issues.append(CompositionIssue(
            issue_type="uniform_phrase_lengths",
            critic="phrase",
            severity=0.4,
            confidence=0.60,
            evidence=f"All {len(phrases)} phrases are {lengths[0]} bars — no structural variation",
            recommended_moves=["extend_one_phrase", "add_pickup", "truncate_for_surprise"],
        ))

    # 2. No cadence detected (all cadence_strength near 0)
    weak_cadences = [p for p in phrases if p.cadence_strength < 0.2]
    if len(weak_cadences) > len(phrases) * 0.7:
        issues.append(CompositionIssue(
            issue_type="weak_cadences",
            critic="phrase",
            severity=0.5,
            confidence=0.55,
            evidence=f"{len(weak_cadences)}/{len(phrases)} phrases have weak cadence (< 0.2)",
            recommended_moves=["add_resolution_notes", "create_turnaround", "vary_last_bar"],
        ))

    # 3. No variation between adjacent phrases
    no_variation = sum(1 for p in phrases if not p.has_variation)
    if no_variation >= len(phrases) - 1 and len(phrases) > 2:
        issues.append(CompositionIssue(
            issue_type="no_phrase_variation",
            critic="phrase",
            severity=0.5,
            confidence=0.60,
            evidence=f"{no_variation}/{len(phrases)} phrases identical to their neighbor",
            recommended_moves=["add_fill", "vary_notes", "create_response_phrase"],
        ))

    return issues


# ── Transition Critic (Round 1) ──────────────────────────────────────
def run_transition_critic(
    sections: list[SectionNode],
    roles: list[RoleNode],
    harmony_fields: Optional[list[HarmonyField]] = None,
) -> list[CompositionIssue]:
    """Analyze boundaries between adjacent sections for transition quality."""
    issues = []
    if len(sections) < 2:
        return issues

    harmony_map = {}
    if harmony_fields:
        harmony_map = {hf.section_id: hf for hf in harmony_fields}

    for i in range(1, len(sections)):
        prev = sections[i - 1]
        curr = sections[i]

        # 1. Hard cut — no energy or density change at boundary
        energy_delta = abs(curr.energy - prev.energy)
        density_delta = abs(curr.density - prev.density)

        if energy_delta < 0.05 and density_delta < 0.05:
            issues.append(CompositionIssue(
                issue_type="hard_cut_transition",
                critic="transition",
                severity=0.5,
                confidence=0.70,
                scope={"from": prev.section_id, "to": curr.section_id},
                evidence=f"No energy/density change between '{prev.name or prev.section_id}' and '{curr.name or curr.section_id}'",
                recommended_moves=["add_transition_fx", "create_fill", "vary_density_at_boundary"],
            ))

        # 2. No pre-arrival subtraction before high-energy section
        if curr.energy > 0.7 and prev.energy > 0.6:
            issues.append(CompositionIssue(
                issue_type="no_pre_arrival_subtraction",
                critic="transition",
                severity=0.6,
                confidence=0.65,
                scope={"from": prev.section_id, "to": curr.section_id},
                evidence=f"High-energy section '{curr.name or curr.section_id}' (E={curr.energy:.2f}) not preceded by subtraction (prev E={prev.energy:.2f})",
                recommended_moves=["thin_preceding_section", "add_breakdown_before_peak", "inhale_gesture"],
            ))

        # 3. Groove break — rhythmic elements drop out at boundary
        prev_rhythm = {r.track_index for r in roles
                       if r.section_id == prev.section_id
                       and r.role in (RoleType.KICK_ANCHOR, RoleType.RHYTHMIC_TEXTURE)}
        curr_rhythm = {r.track_index for r in roles
                       if r.section_id == curr.section_id
                       and r.role in (RoleType.KICK_ANCHOR, RoleType.RHYTHMIC_TEXTURE)}

        if prev_rhythm and not curr_rhythm:
            issues.append(CompositionIssue(
                issue_type="groove_break_at_transition",
                critic="transition",
                severity=0.5,
                confidence=0.60,
                scope={"from": prev.section_id, "to": curr.section_id},
                evidence=f"All rhythmic elements ({len(prev_rhythm)} tracks) drop out at '{curr.name or curr.section_id}'",
                recommended_moves=["carry_one_rhythm_element", "add_transition_percussion"],
            ))

        # 4. Harmonic non-sequitur — key change without voice-leading support
        prev_hf = harmony_map.get(prev.section_id)
        curr_hf = harmony_map.get(curr.section_id)

        if prev_hf and curr_hf and prev_hf.key and curr_hf.key:
            if prev_hf.key != curr_hf.key:
                # Key change: check if it's prepared
                if prev_hf.resolution_potential < 0.5 and curr_hf.instability > 0.5:
                    issues.append(CompositionIssue(
                        issue_type="harmonic_non_sequitur",
                        critic="transition",
                        severity=0.6,
                        confidence=0.55,
                        scope={"from": prev.section_id, "to": curr.section_id},
                        evidence=f"Key change {prev_hf.key} → {curr_hf.key} without harmonic preparation",
                        recommended_moves=["add_pivot_chord", "use_chromatic_mediant", "prepare_with_dominant"],
                    ))

        # 5. Weak build — energy rises but no role rotation
        if curr.energy > prev.energy + 0.2:
            prev_fg = {r.track_index for r in roles
                       if r.section_id == prev.section_id and r.foreground}
            curr_fg = {r.track_index for r in roles
                       if r.section_id == curr.section_id and r.foreground}

            if prev_fg == curr_fg and prev_fg:
                issues.append(CompositionIssue(
                    issue_type="weak_build",
                    critic="transition",
                    severity=0.4,
                    confidence=0.55,
                    scope={"from": prev.section_id, "to": curr.section_id},
                    evidence=f"Energy rises but same foreground voices ({len(prev_fg)} tracks) — no role rotation",
                    recommended_moves=["rotate_foreground_voice", "add_new_element", "handoff_gesture"],
                ))

    return issues


# ── Emotional Arc Critic (Round 3) ──────────────────────────────────
def run_emotional_arc_critic(
    sections: list[SectionNode],
    harmony_fields: Optional[list["HarmonyField"]] = None,
) -> list[CompositionIssue]:
    """Analyze whether the arrangement tells an emotional story.

    Builds a tension curve from energy, harmonic instability, and density,
    then checks for common arc problems: monotone, all-climax, build
    without payoff, no resolution.
    """
    issues = []
    if len(sections) < 3:
        return issues  # Need enough sections to judge an arc

    # Build tension curve: composite of energy, density, and harmonic instability
    harmony_map = {}
    if harmony_fields:
        harmony_map = {hf.section_id: hf for hf in harmony_fields}

    tension_curve: list[float] = []
    for section in sections:
        energy_component = section.energy
        density_component = section.density

        # Add harmonic instability if available
        hf = harmony_map.get(section.section_id)
        instability = hf.instability if hf else 0.3  # neutral default

        tension = (energy_component * 0.5 + density_component * 0.3 + instability * 0.2)
        tension_curve.append(round(tension, 3))

    # 1. Monotone arc — tension doesn't vary enough
    tension_range = max(tension_curve) - min(tension_curve)
    if tension_range < 0.15:
        issues.append(CompositionIssue(
            issue_type="monotone_arc",
            critic="emotional_arc",
            severity=0.7,
            confidence=0.70,
            evidence=f"Tension range: {tension_range:.2f} — arrangement feels static",
            recommended_moves=[
                "add_breakdown_section", "create_energy_contrast",
                "thin_one_section", "add_build_before_peak",
            ],
        ))

    # 2. All-climax — high tension everywhere, no rest
    high_tension_count = sum(1 for t in tension_curve if t > 0.7)
    if high_tension_count > len(tension_curve) * 0.6:
        issues.append(CompositionIssue(
            issue_type="all_climax",
            critic="emotional_arc",
            severity=0.6,
            confidence=0.65,
            evidence=f"{high_tension_count}/{len(tension_curve)} sections have tension > 0.7 — no rest",
            recommended_moves=[
                "add_low_energy_section", "create_breakdown",
                "reduce_density_in_verse", "strip_back_intro",
            ],
        ))

    # 3. Build without payoff — tension rises then doesn't reach peak
    peak_idx = tension_curve.index(max(tension_curve))
    if peak_idx < len(tension_curve) - 1:
        # Check if there's a build (rising tension) before the peak
        has_build = False
        for i in range(1, peak_idx + 1):
            if tension_curve[i] > tension_curve[i - 1] + 0.1:
                has_build = True
                break

        if not has_build and len(tension_curve) > 4:
            issues.append(CompositionIssue(
                issue_type="no_clear_build",
                critic="emotional_arc",
                severity=0.5,
                confidence=0.55,
                evidence="No gradual tension increase before peak — peak arrives without anticipation",
                recommended_moves=[
                    "add_build_section", "tension_ratchet_gesture",
                    "gradual_element_addition", "harmonic_tint_rise",
                ],
            ))

    # 4. No resolution — tension stays high at the end
    if len(tension_curve) >= 3:
        final_tension = tension_curve[-1]
        peak_tension = max(tension_curve)
        if final_tension > peak_tension * 0.8 and peak_tension > 0.5:
            issues.append(CompositionIssue(
                issue_type="no_resolution",
                critic="emotional_arc",
                severity=0.5,
                confidence=0.60,
                evidence=f"Final tension ({final_tension:.2f}) nearly as high as peak ({peak_tension:.2f}) — no release",
                recommended_moves=[
                    "add_outro", "create_energy_drop_at_end",
                    "outro_decay_dissolve_gesture", "strip_elements_gradually",
                ],
            ))

    # 5. Peak too early — climax in first third
    if peak_idx < len(tension_curve) / 3 and len(tension_curve) > 4:
        issues.append(CompositionIssue(
            issue_type="peak_too_early",
            critic="emotional_arc",
            severity=0.5,
            confidence=0.55,
            evidence=f"Peak tension at section {peak_idx + 1}/{len(tension_curve)} — climax in first third",
            recommended_moves=[
                "move_peak_elements_later", "add_second_bigger_climax",
                "reorder_sections", "save_hook_reveal_for_later",
            ],
        ))

    return issues


# ── Cross-Section Critic (Round 4) ──────────────────────────────────
def run_cross_section_critic(
    sections: list[SectionNode],
    roles: list[RoleNode],
    harmony_fields: Optional[list["HarmonyField"]] = None,
    motif_count: int = 0,
) -> list[CompositionIssue]:
    """Reason across the entire arrangement for cross-section coherence.

    Checks that the arrangement works as a whole, not just per-section:
    - Clear reveal order (elements shouldn't all appear at once)
    - Foreground voice rotation (same lead everywhere = fatigue)
    - Harmonic pacing (rapid key changes everywhere = chaos)
    - Element variety across sections
    """
    issues = []
    if len(sections) < 3:
        return issues

    # 1. All elements appear from the start — no reveal order
    if len(sections) >= 3:
        first_active = set(sections[0].tracks_active)
        second_active = set(sections[1].tracks_active)
        third_active = set(sections[2].tracks_active)
        if first_active == second_active == third_active and first_active:
            issues.append(CompositionIssue(
                issue_type="no_reveal_order",
                critic="cross_section",
                severity=0.6,
                confidence=0.65,
                evidence=f"First 3 sections all have same {len(first_active)} active tracks — no staggered reveal",
                recommended_moves=[
                    "defer_elements_to_later_sections", "strip_intro",
                    "create_reveal_sequence", "mute_tracks_in_early_sections",
                ],
            ))

    # 2. Same foreground voices in every section — no rotation
    fg_by_section: list[set[int]] = []
    for section in sections:
        fg = {r.track_index for r in roles
              if r.section_id == section.section_id and r.foreground}
        fg_by_section.append(fg)

    if len(fg_by_section) >= 3:
        all_same = all(fg == fg_by_section[0] for fg in fg_by_section[1:])
        if all_same and fg_by_section[0]:
            issues.append(CompositionIssue(
                issue_type="no_foreground_rotation",
                critic="cross_section",
                severity=0.5,
                confidence=0.60,
                evidence=f"Same foreground voices ({len(fg_by_section[0])} tracks) in all {len(sections)} sections",
                recommended_moves=[
                    "alternate_lead_voice", "handoff_gesture_between_sections",
                    "mute_lead_in_bridge", "introduce_new_hook_element",
                ],
            ))

    # 3. Harmonic monotony — same key across all sections
    if harmony_fields:
        keys = [hf.key for hf in harmony_fields if hf.key]
        if len(keys) >= 3 and len(set(keys)) == 1:
            issues.append(CompositionIssue(
                issue_type="harmonic_monotony",
                critic="cross_section",
                severity=0.4,
                confidence=0.50,
                evidence=f"All {len(keys)} sections in same key ({keys[0]}) — consider modulation",
                recommended_moves=[
                    "modulate_for_bridge", "use_chromatic_mediant",
                    "borrow_from_parallel_key", "transpose_final_chorus",
                ],
            ))

        # 4. Harmonic chaos — different key in every section
        unique_keys = set(keys)
        if len(unique_keys) > len(keys) * 0.7 and len(keys) >= 4:
            issues.append(CompositionIssue(
                issue_type="harmonic_chaos",
                critic="cross_section",
                severity=0.5,
                confidence=0.45,
                evidence=f"{len(unique_keys)} different keys across {len(keys)} sections — hard to follow",
                recommended_moves=[
                    "consolidate_to_two_keys", "use_pivot_chords",
                    "establish_home_key", "group_related_sections",
                ],
            ))

    # 5. No motif development (if motifs exist but aren't varied)
    if motif_count > 0:
        # Check if sections have varying density (proxy for development)
        densities = [s.density for s in sections]
        unique_densities = len(set(round(d, 1) for d in densities))
        if unique_densities <= 2 and len(sections) > 4:
            issues.append(CompositionIssue(
                issue_type="static_arrangement",
                critic="cross_section",
                severity=0.4,
                confidence=0.50,
                evidence=f"Only {unique_densities} distinct density levels across {len(sections)} sections with {motif_count} motifs",
                recommended_moves=[
                    "vary_motif_density_per_section", "fragment_motif_in_bridge",
                    "augment_motif_in_outro", "register_shift_for_variety",
                ],
            ))

    return issues


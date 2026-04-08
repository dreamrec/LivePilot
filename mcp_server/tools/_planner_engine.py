"""Planner Engine — loop-to-song arrangement planning and orchestration.

Transforms a single loop analysis into a full arrangement blueprint:
section sequence, element reveal order, gesture automation, and
orchestration plan.

Zero external dependencies beyond stdlib. The MCP tool wrappers in
planner.py handle data fetching; this module handles computation.

Design: spec at docs/specs/2026-04-08-phase2-4-roadmap.md, Round 3 (3.3).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from ._composition_engine import (
    GestureIntent,
    GesturePlan,
    RoleNode,
    RoleType,
    SectionNode,
    SectionType,
    plan_gesture,
)


# ── Section Templates ────────────────────────────────────────────────

# Prototypical section sequences by style. Each entry:
# (section_type, energy_target, density_target, typical_bars)
STYLE_TEMPLATES: dict[str, list[tuple[SectionType, float, float, int]]] = {
    "electronic": [
        (SectionType.INTRO, 0.2, 0.2, 16),
        (SectionType.VERSE, 0.5, 0.5, 16),
        (SectionType.BUILD, 0.6, 0.6, 8),
        (SectionType.DROP, 0.9, 0.9, 16),
        (SectionType.BREAKDOWN, 0.3, 0.3, 8),
        (SectionType.BUILD, 0.7, 0.7, 8),
        (SectionType.DROP, 1.0, 1.0, 16),
        (SectionType.OUTRO, 0.2, 0.2, 16),
    ],
    "hiphop": [
        (SectionType.INTRO, 0.3, 0.3, 8),
        (SectionType.VERSE, 0.6, 0.6, 16),
        (SectionType.CHORUS, 0.8, 0.8, 8),
        (SectionType.VERSE, 0.6, 0.6, 16),
        (SectionType.CHORUS, 0.8, 0.8, 8),
        (SectionType.BRIDGE, 0.5, 0.4, 8),
        (SectionType.CHORUS, 0.9, 0.9, 8),
        (SectionType.OUTRO, 0.3, 0.3, 8),
    ],
    "pop": [
        (SectionType.INTRO, 0.3, 0.3, 8),
        (SectionType.VERSE, 0.5, 0.5, 16),
        (SectionType.PRE_CHORUS, 0.6, 0.6, 8),
        (SectionType.CHORUS, 0.8, 0.8, 8),
        (SectionType.VERSE, 0.5, 0.5, 16),
        (SectionType.PRE_CHORUS, 0.6, 0.6, 8),
        (SectionType.CHORUS, 0.9, 0.9, 8),
        (SectionType.BRIDGE, 0.4, 0.4, 8),
        (SectionType.CHORUS, 1.0, 1.0, 8),
        (SectionType.OUTRO, 0.3, 0.3, 8),
    ],
    "ambient": [
        (SectionType.INTRO, 0.1, 0.1, 32),
        (SectionType.VERSE, 0.3, 0.3, 32),
        (SectionType.VERSE, 0.5, 0.5, 32),
        (SectionType.BREAKDOWN, 0.2, 0.2, 16),
        (SectionType.VERSE, 0.4, 0.4, 32),
        (SectionType.OUTRO, 0.1, 0.1, 32),
    ],
    "techno": [
        (SectionType.INTRO, 0.3, 0.3, 16),
        (SectionType.VERSE, 0.6, 0.6, 32),
        (SectionType.BUILD, 0.7, 0.7, 8),
        (SectionType.DROP, 1.0, 1.0, 32),
        (SectionType.BREAKDOWN, 0.3, 0.3, 16),
        (SectionType.BUILD, 0.8, 0.8, 8),
        (SectionType.DROP, 1.0, 1.0, 32),
        (SectionType.OUTRO, 0.3, 0.3, 16),
    ],
}

VALID_STYLES = frozenset(STYLE_TEMPLATES.keys())


# ── Loop Identity ────────────────────────────────────────────────────

@dataclass
class LoopIdentity:
    """What makes this loop recognizable — its core musical DNA."""
    track_count: int
    foreground_tracks: list[int]  # track indices of lead/hook elements
    rhythm_tracks: list[int]  # kick, hats, perc
    harmonic_tracks: list[int]  # pads, chords, bass
    texture_tracks: list[int]  # fx, atmosphere
    energy: float  # 0-1
    density: float  # 0-1
    estimated_bars: int

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_loop_identity(
    roles: list[RoleNode],
    sections: list[SectionNode],
) -> LoopIdentity:
    """Identify the musical DNA of a loop from its role and section analysis.

    Works with a single-section (loop) or multi-section input.
    """
    # Use first section as the loop
    section = sections[0] if sections else None
    track_count = len(section.tracks_active) if section else 0
    energy = section.energy if section else 0.5
    density = section.density if section else 0.5
    bars = section.length_bars() if section else 8

    # Classify tracks by role
    foreground = []
    rhythm = []
    harmonic = []
    texture = []

    section_id = section.section_id if section else ""
    for role in roles:
        if role.section_id != section_id:
            continue
        if role.role in (RoleType.LEAD, RoleType.HOOK):
            foreground.append(role.track_index)
        elif role.role in (RoleType.KICK_ANCHOR, RoleType.RHYTHMIC_TEXTURE):
            rhythm.append(role.track_index)
        elif role.role in (RoleType.BASS_ANCHOR, RoleType.HARMONY_BED):
            harmonic.append(role.track_index)
        elif role.role in (RoleType.TEXTURE_WASH, RoleType.TRANSITION_FX):
            texture.append(role.track_index)

    return LoopIdentity(
        track_count=track_count,
        foreground_tracks=foreground,
        rhythm_tracks=rhythm,
        harmonic_tracks=harmonic,
        texture_tracks=texture,
        energy=energy,
        density=density,
        estimated_bars=bars,
    )


# ── Arrangement Plan ─────────────────────────────────────────────────

@dataclass
class SectionPlan:
    """Planned section in the arrangement."""
    section_type: SectionType
    start_bar: int
    end_bar: int
    energy_target: float
    density_target: float
    tracks_active: list[int]  # which tracks should play
    tracks_entering: list[int]  # new elements introduced in this section
    tracks_exiting: list[int]  # elements removed in this section

    def length_bars(self) -> int:
        return self.end_bar - self.start_bar

    def to_dict(self) -> dict:
        d = asdict(self)
        d["section_type"] = self.section_type.value
        d["length_bars"] = self.length_bars()
        return d


@dataclass
class ArrangementPlan:
    """Full arrangement blueprint from a loop."""
    style: str
    total_bars: int
    sections: list[SectionPlan]
    gesture_plan: list[dict]  # gesture template suggestions per transition
    reveal_order: list[dict]  # [{track_index, enters_at_section, role}]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "style": self.style,
            "total_bars": self.total_bars,
            "sections": [s.to_dict() for s in self.sections],
            "section_count": len(self.sections),
            "gesture_plan": self.gesture_plan,
            "reveal_order": self.reveal_order,
            "notes": self.notes,
        }


# ── Core Planner ─────────────────────────────────────────────────────

def plan_arrangement_from_loop(
    loop_identity: LoopIdentity,
    target_duration_bars: int = 128,
    style: str = "electronic",
) -> ArrangementPlan:
    """Transform a loop identity into a full arrangement blueprint.

    1. Select section template based on style
    2. Scale section lengths to target duration
    3. Plan element reveal order (what enters/exits when)
    4. Suggest gesture automation for transitions
    """
    if style not in STYLE_TEMPLATES:
        raise ValueError(f"Unknown style '{style}'. Valid: {sorted(VALID_STYLES)}")

    template = STYLE_TEMPLATES[style]

    # 1. Scale sections to target duration
    template_bars = sum(s[3] for s in template)
    scale_factor = target_duration_bars / template_bars

    sections: list[SectionPlan] = []
    current_bar = 0

    for stype, energy_target, density_target, base_bars in template:
        # Scale but keep bar counts as multiples of 4
        scaled_bars = max(4, round(base_bars * scale_factor / 4) * 4)
        end_bar = current_bar + scaled_bars

        sections.append(SectionPlan(
            section_type=stype,
            start_bar=current_bar,
            end_bar=end_bar,
            energy_target=energy_target,
            density_target=density_target,
            tracks_active=[],  # Filled in by reveal planning
            tracks_entering=[],
            tracks_exiting=[],
        ))
        current_bar = end_bar

    # 2. Plan element reveal order
    all_tracks = (
        loop_identity.rhythm_tracks
        + loop_identity.harmonic_tracks
        + loop_identity.foreground_tracks
        + loop_identity.texture_tracks
    )

    reveal_order = _plan_reveal_order(
        sections, loop_identity, all_tracks,
    )

    # Apply reveal order to section active tracks
    active_set: set[int] = set()
    for i, section in enumerate(sections):
        # Add entering tracks
        for entry in reveal_order:
            if entry["enters_at_section"] == i:
                active_set.add(entry["track_index"])
                section.tracks_entering.append(entry["track_index"])

        # Remove exiting tracks (for breakdowns/bridges)
        if section.section_type in (SectionType.BREAKDOWN, SectionType.BRIDGE):
            # Keep only rhythm + harmony (strip foreground + texture)
            to_remove = [t for t in active_set
                         if t in loop_identity.foreground_tracks
                         or t in loop_identity.texture_tracks]
            for t in to_remove:
                active_set.discard(t)
                section.tracks_exiting.append(t)

        section.tracks_active = sorted(active_set)

    # 3. Suggest gesture templates for transitions
    gesture_plan = _plan_transition_gestures(sections)

    # 4. Notes
    total_bars = sections[-1].end_bar if sections else 0
    notes = []
    if total_bars != target_duration_bars:
        notes.append(f"Actual duration: {total_bars} bars (target was {target_duration_bars})")
    if not loop_identity.foreground_tracks:
        notes.append("No clear foreground element detected — consider adding a lead/hook")
    if not loop_identity.rhythm_tracks:
        notes.append("No rhythm tracks detected — arrangement may feel floaty without groove")

    return ArrangementPlan(
        style=style,
        total_bars=total_bars,
        sections=sections,
        gesture_plan=gesture_plan,
        reveal_order=reveal_order,
        notes=notes,
    )


def _plan_reveal_order(
    sections: list[SectionPlan],
    loop_identity: LoopIdentity,
    all_tracks: list[int],
) -> list[dict]:
    """Plan when each track enters the arrangement.

    Strategy: stagger element introductions for maximum impact.
    - Intro: minimal (rhythm only, or partial rhythm)
    - First verse/section: add bass + harmony
    - Build/pre-chorus: add texture
    - Drop/chorus: full reveal (foreground enters)
    """
    if not all_tracks or not sections:
        return []

    reveal: list[dict] = []
    assigned: set[int] = set()

    # Group tracks by priority
    groups = [
        ("rhythm_foundation", loop_identity.rhythm_tracks[:2]),  # Kick + one more
        ("harmonic_base", loop_identity.harmonic_tracks[:2]),  # Bass + pad
        ("texture_layer", loop_identity.texture_tracks),
        ("foreground_reveal", loop_identity.foreground_tracks),
        ("remaining_rhythm", loop_identity.rhythm_tracks[2:]),
        ("remaining_harmony", loop_identity.harmonic_tracks[2:]),
    ]

    # Map groups to section types (when they should enter)
    entry_map: dict[str, list[SectionType]] = {
        "rhythm_foundation": [SectionType.INTRO],
        "harmonic_base": [SectionType.VERSE],
        "texture_layer": [SectionType.BUILD, SectionType.PRE_CHORUS, SectionType.VERSE],
        "foreground_reveal": [SectionType.DROP, SectionType.CHORUS],
        "remaining_rhythm": [SectionType.VERSE, SectionType.BUILD],
        "remaining_harmony": [SectionType.BUILD, SectionType.PRE_CHORUS],
    }

    for group_name, tracks in groups:
        target_types = entry_map.get(group_name, [SectionType.VERSE])

        # Find first section matching target type
        target_section_idx = 0
        for i, section in enumerate(sections):
            if section.section_type in target_types:
                target_section_idx = i
                break

        for track in tracks:
            if track in assigned:
                continue
            reveal.append({
                "track_index": track,
                "enters_at_section": target_section_idx,
                "group": group_name,
            })
            assigned.add(track)

    # Any remaining unassigned tracks enter at section 1
    for track in all_tracks:
        if track not in assigned:
            reveal.append({
                "track_index": track,
                "enters_at_section": min(1, len(sections) - 1),
                "group": "unassigned",
            })

    return reveal


def _plan_transition_gestures(sections: list[SectionPlan]) -> list[dict]:
    """Suggest gesture templates for each section transition."""
    gestures = []

    for i in range(1, len(sections)):
        prev = sections[i - 1]
        curr = sections[i]

        suggestion = {
            "transition": f"{prev.section_type.value} → {curr.section_type.value}",
            "boundary_bar": curr.start_bar,
            "templates": [],
        }

        # Select templates based on transition type
        energy_increase = curr.energy_target > prev.energy_target + 0.15

        if curr.section_type in (SectionType.DROP, SectionType.CHORUS) and energy_increase:
            suggestion["templates"].append("pre_arrival_vacuum")
            if curr.tracks_entering:
                suggestion["templates"].append("re_entry_spotlight")

        elif curr.section_type == SectionType.BUILD:
            suggestion["templates"].append("tension_ratchet")

        elif curr.section_type in (SectionType.BREAKDOWN, SectionType.BRIDGE):
            suggestion["templates"].append("sectional_width_bloom")

        elif curr.section_type == SectionType.OUTRO:
            suggestion["templates"].append("outro_decay_dissolve")

        elif curr.section_type == SectionType.VERSE and prev.section_type == SectionType.CHORUS:
            suggestion["templates"].append("turnaround_accent")

        else:
            # Generic transition
            if energy_increase:
                suggestion["templates"].append("harmonic_tint_rise")
            else:
                suggestion["templates"].append("phrase_end_throw")

        gestures.append(suggestion)

    return gestures

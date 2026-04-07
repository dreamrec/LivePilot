"""Composition Engine V1 — structural and musical intelligence for arrangement.

Pure-computation core: section inference, phrase boundary detection,
section-aware role assignment, composition critics, gesture planning,
and composition-specific evaluation.

Zero external dependencies beyond stdlib. The MCP tool wrappers in
composition.py handle data fetching; this module handles computation.

Design: spec at docs/COMPOSITION_ENGINE_V1.md, sections 7-15.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Enums ─────────────────────────────────────────────────────────────

class SectionType(str, Enum):
    LOOP = "loop"
    INTRO = "intro"
    VERSE = "verse"
    PRE_CHORUS = "pre_chorus"
    CHORUS = "chorus"
    BUILD = "build"
    DROP = "drop"
    BRIDGE = "bridge"
    BREAKDOWN = "breakdown"
    OUTRO = "outro"
    UNKNOWN = "unknown"


class RoleType(str, Enum):
    KICK_ANCHOR = "kick_anchor"
    BASS_ANCHOR = "bass_anchor"
    HOOK = "hook"
    LEAD = "lead"
    HARMONY_BED = "harmony_bed"
    RHYTHMIC_TEXTURE = "rhythmic_texture"
    TEXTURE_WASH = "texture_wash"
    TRANSITION_FX = "transition_fx"
    UTILITY = "utility"
    UNKNOWN = "unknown"


class GestureIntent(str, Enum):
    REVEAL = "reveal"
    CONCEAL = "conceal"
    HANDOFF = "handoff"
    INHALE = "inhale"
    RELEASE = "release"
    LIFT = "lift"
    SINK = "sink"
    PUNCTUATE = "punctuate"
    DRIFT = "drift"


# ── Section Graph ─────────────────────────────────────────────────────

# Patterns for inferring section type from scene/clip names
_SECTION_NAME_PATTERNS: list[tuple[str, SectionType]] = [
    (r"intro", SectionType.INTRO),
    (r"verse|vrs", SectionType.VERSE),
    (r"pre[\s\-]?chorus", SectionType.PRE_CHORUS),
    (r"chorus|hook|chrs", SectionType.CHORUS),
    (r"build|riser|tension", SectionType.BUILD),
    (r"drop|main|peak", SectionType.DROP),
    (r"bridge|brg", SectionType.BRIDGE),
    (r"break(?:down)?|strip", SectionType.BREAKDOWN),
    (r"outro|end|fade", SectionType.OUTRO),
    (r"loop", SectionType.LOOP),
]


@dataclass
class SectionNode:
    """A section of the arrangement with inferred type and energy."""
    section_id: str
    start_bar: int
    end_bar: int
    section_type: SectionType
    confidence: float  # 0.0-1.0
    energy: float  # 0.0-1.0 (relative within the track)
    density: float  # 0.0-1.0 (how many tracks are active)
    tracks_active: list[int] = field(default_factory=list)
    name: str = ""

    def length_bars(self) -> int:
        return self.end_bar - self.start_bar

    def to_dict(self) -> dict:
        d = asdict(self)
        d["section_type"] = self.section_type.value
        d["length_bars"] = self.length_bars()
        return d


def _infer_section_type_from_name(name: str) -> tuple[SectionType, float]:
    """Infer section type from a scene or clip name. Returns (type, confidence)."""
    lower = name.lower().strip()
    for pattern, stype in _SECTION_NAME_PATTERNS:
        if re.search(pattern, lower):
            return stype, 0.85
    return SectionType.UNKNOWN, 0.0


def _infer_section_type_from_energy(
    energy: float, density: float, position_ratio: float, total_sections: int,
) -> tuple[SectionType, float]:
    """Infer section type from energy/density/position heuristics."""
    # Position-based heuristics
    if position_ratio < 0.1 and density < 0.4:
        return SectionType.INTRO, 0.6
    if position_ratio > 0.9 and density < 0.4:
        return SectionType.OUTRO, 0.6

    # Energy-based heuristics
    if energy > 0.8 and density > 0.7:
        return SectionType.DROP, 0.5
    if energy < 0.3 and density < 0.3:
        return SectionType.BREAKDOWN, 0.5
    if 0.4 <= energy <= 0.7:
        return SectionType.VERSE, 0.4

    return SectionType.UNKNOWN, 0.0


def build_section_graph_from_scenes(
    scenes: list[dict],
    clip_matrix: list[list[dict]],
    track_count: int,
    beats_per_bar: int = 4,
) -> list[SectionNode]:
    """Build section graph from session view scenes.

    scenes: list of {index, name, tempo, color_index}
    clip_matrix: [scene_index][track_index] = {state, name, ...} or None
    """
    sections = []
    # Estimate bar positions: each scene is a section, assume 8-bar default
    # unless clips provide length info
    current_bar = 0

    for i, scene in enumerate(scenes):
        scene_name = scene.get("name", "")
        if not scene_name.strip():
            continue  # Skip unnamed empty scenes

        # Count active tracks in this scene
        active_tracks = []
        if i < len(clip_matrix):
            for t_idx in range(min(track_count, len(clip_matrix[i]))):
                slot = clip_matrix[i][t_idx]
                if slot and slot.get("state") in ("playing", "stopped", "triggered"):
                    if slot.get("has_clip", True):
                        active_tracks.append(t_idx)

        density = len(active_tracks) / max(track_count, 1)

        # Estimate section length (default 32 beats = 8 bars)
        section_length_bars = 8
        start_bar = current_bar
        end_bar = start_bar + section_length_bars

        # Infer type from name first, then energy/position
        stype, confidence = _infer_section_type_from_name(scene_name)
        if stype == SectionType.UNKNOWN:
            total = len([s for s in scenes if s.get("name", "").strip()])
            position_ratio = i / max(total - 1, 1) if total > 1 else 0.5
            stype, confidence = _infer_section_type_from_energy(
                energy=density, density=density,
                position_ratio=position_ratio, total_sections=total,
            )

        sections.append(SectionNode(
            section_id=f"sec_{i:02d}",
            start_bar=start_bar,
            end_bar=end_bar,
            section_type=stype,
            confidence=confidence,
            energy=density,  # density as energy proxy
            density=density,
            tracks_active=active_tracks,
            name=scene_name,
        ))
        current_bar = end_bar

    return sections


def build_section_graph_from_arrangement(
    arrangement_clips: dict[int, list[dict]],
    track_count: int,
    beats_per_bar: int = 4,
) -> list[SectionNode]:
    """Build section graph from arrangement view clips.

    arrangement_clips: {track_index: [{start_time, end_time, length, name}, ...]}
    """
    if not arrangement_clips:
        return []

    # Collect all time boundaries
    boundaries: set[float] = set()
    for clips in arrangement_clips.values():
        for clip in clips:
            boundaries.add(clip.get("start_time", 0))
            boundaries.add(clip.get("end_time", clip.get("start_time", 0) + clip.get("length", 0)))

    sorted_bounds = sorted(boundaries)
    if len(sorted_bounds) < 2:
        return []

    sections = []
    for i in range(len(sorted_bounds) - 1):
        start_beat = sorted_bounds[i]
        end_beat = sorted_bounds[i + 1]
        if end_beat - start_beat < beats_per_bar:
            continue  # Skip very short segments

        start_bar = int(start_beat / beats_per_bar)
        end_bar = int(end_beat / beats_per_bar)
        if end_bar <= start_bar:
            continue

        # Count active tracks in this time range
        active_tracks = []
        for t_idx, clips in arrangement_clips.items():
            for clip in clips:
                clip_start = clip.get("start_time", 0)
                clip_end = clip.get("end_time", clip_start + clip.get("length", 0))
                if clip_start < end_beat and clip_end > start_beat:
                    active_tracks.append(t_idx)
                    break

        density = len(active_tracks) / max(track_count, 1)
        total_sections = len(sorted_bounds) - 1
        position_ratio = i / max(total_sections - 1, 1) if total_sections > 1 else 0.5

        stype, confidence = _infer_section_type_from_energy(
            energy=density, density=density,
            position_ratio=position_ratio, total_sections=total_sections,
        )

        sections.append(SectionNode(
            section_id=f"arr_{i:02d}",
            start_bar=start_bar,
            end_bar=end_bar,
            section_type=stype,
            confidence=confidence,
            energy=density,
            density=density,
            tracks_active=active_tracks,
        ))

    return sections


# ── Phrase Grid ───────────────────────────────────────────────────────

@dataclass
class PhraseUnit:
    """A musical phrase within a section."""
    phrase_id: str
    section_id: str
    start_bar: int
    end_bar: int
    cadence_strength: float  # 0.0-1.0 (how strongly it resolves)
    note_density: float  # notes per bar
    has_variation: bool  # differs from adjacent phrases

    def length_bars(self) -> int:
        return self.end_bar - self.start_bar

    def to_dict(self) -> dict:
        d = asdict(self)
        d["length_bars"] = self.length_bars()
        return d


def detect_phrases(
    section: SectionNode,
    notes_by_track: dict[int, list[dict]],
    default_phrase_length: int = 4,
    beats_per_bar: int = 4,
) -> list[PhraseUnit]:
    """Detect phrase boundaries within a section from note data.

    Uses note density changes and gap detection to find phrase boundaries.
    Falls back to regular grid (4 or 8 bar phrases).
    """
    section_length = section.length_bars()
    if section_length <= 0:
        return []

    # Aggregate all notes into a bar-level density map
    bar_densities: dict[int, int] = {}
    for bar in range(section.start_bar, section.end_bar):
        bar_densities[bar] = 0

    for track_notes in notes_by_track.values():
        for note in track_notes:
            start_beat = note.get("start_time", 0)
            note_bar = section.start_bar + int(start_beat / beats_per_bar)
            if section.start_bar <= note_bar < section.end_bar:
                bar_densities[note_bar] = bar_densities.get(note_bar, 0) + 1

    # Find phrase boundaries using density drops (gaps)
    boundaries = [section.start_bar]
    bars = sorted(bar_densities.keys())

    for i in range(1, len(bars)):
        prev_density = bar_densities.get(bars[i - 1], 0)
        curr_density = bar_densities.get(bars[i], 0)

        # A phrase boundary is where density drops significantly or a gap exists
        if prev_density > 0 and curr_density == 0:
            boundaries.append(bars[i])
        elif (bars[i] - section.start_bar) % default_phrase_length == 0:
            # Regular grid fallback
            if bars[i] not in boundaries:
                boundaries.append(bars[i])

    boundaries.append(section.end_bar)
    boundaries = sorted(set(boundaries))

    # Build phrases from boundaries
    phrases = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end <= start:
            continue

        # Calculate note density for this phrase
        total_notes = sum(bar_densities.get(b, 0) for b in range(start, end))
        phrase_bars = end - start
        density = total_notes / max(phrase_bars, 1)

        # Cadence strength: higher if the last bar has lower density (resolution)
        last_bar_density = bar_densities.get(end - 1, 0)
        avg_density = density
        cadence = max(0.0, min(1.0, 1.0 - (last_bar_density / max(avg_density, 0.1)))) if avg_density > 0 else 0.3

        phrases.append(PhraseUnit(
            phrase_id=f"{section.section_id}_phr_{i:02d}",
            section_id=section.section_id,
            start_bar=start,
            end_bar=end,
            cadence_strength=round(cadence, 3),
            note_density=round(density, 2),
            has_variation=False,  # Computed later by phrase critic
        ))

    # Mark variation: compare adjacent phrase densities
    for i in range(1, len(phrases)):
        density_diff = abs(phrases[i].note_density - phrases[i - 1].note_density)
        if density_diff > 1.0:
            phrases[i].has_variation = True

    return phrases


# ── Role Inference ────────────────────────────────────────────────────

@dataclass
class RoleNode:
    """A track's musical role within a specific section."""
    track_index: int
    track_name: str
    section_id: str
    role: RoleType
    confidence: float  # 0.0-1.0
    foreground: bool  # is this a focal element?

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        return d


# Name-based role hints (extends _agent_os_engine.infer_track_role)
_ROLE_NAME_HINTS: list[tuple[str, RoleType]] = [
    (r"kick|bd|bass\s*drum", RoleType.KICK_ANCHOR),
    (r"sub\s*bass|sub|bass", RoleType.BASS_ANCHOR),
    (r"lead|melody|mel|hook|synth\s*lead", RoleType.LEAD),
    (r"pad|atmosphere|atmo|ambient|drone|chord|keys", RoleType.HARMONY_BED),
    (r"h(?:i)?[\s\-]?hat|hh|hat|perc|percussion|clap|snare|rim", RoleType.RHYTHMIC_TEXTURE),
    (r"fx|sfx|riser|sweep|noise|texture|tape", RoleType.TEXTURE_WASH),
    (r"resamp|bounce|bus|group|master|return", RoleType.UTILITY),
]


def infer_role_for_track(
    track_name: str,
    notes: list[dict],
    device_class: str = "",
    beats_per_bar: int = 4,
) -> tuple[RoleType, float, bool]:
    """Infer a track's role from name, notes, and device class.

    Returns (role, confidence, is_foreground).
    """
    # 1. Name-based inference (highest confidence)
    lower_name = track_name.lower().strip()
    for pattern, role in _ROLE_NAME_HINTS:
        if re.search(pattern, lower_name):
            foreground = role in (RoleType.LEAD, RoleType.HOOK, RoleType.KICK_ANCHOR)
            return role, 0.80, foreground

    # 2. Device-class inference
    dc = device_class.lower()
    if "drumgroup" in dc or "drum" in dc:
        return RoleType.RHYTHMIC_TEXTURE, 0.70, False
    if "simpler" in dc and not notes:
        return RoleType.TEXTURE_WASH, 0.50, False

    # 3. Note-based inference
    if not notes:
        return RoleType.UNKNOWN, 0.0, False

    # Analyze pitch register and density
    pitches = [n.get("pitch", 60) for n in notes]
    durations = [n.get("duration", 0.5) for n in notes]
    avg_pitch = sum(pitches) / len(pitches)
    avg_duration = sum(durations) / len(durations)
    note_count = len(notes)

    # Sub-bass register (< MIDI 48 = C3)
    if avg_pitch < 48:
        return RoleType.BASS_ANCHOR, 0.65, False

    # Very long sustained notes → harmony bed
    if avg_duration > 4.0:
        return RoleType.HARMONY_BED, 0.60, False

    # Dense short notes → rhythmic or lead
    if avg_duration < 0.5 and note_count > 8:
        if avg_pitch > 60:
            return RoleType.LEAD, 0.55, True
        return RoleType.RHYTHMIC_TEXTURE, 0.55, False

    # Medium density, mid register → could be hook or lead
    if 55 <= avg_pitch <= 80 and 0.5 <= avg_duration <= 2.0:
        return RoleType.HOOK, 0.45, True

    return RoleType.UNKNOWN, 0.3, False


def build_role_graph(
    sections: list[SectionNode],
    track_data: list[dict],
    notes_by_section_track: dict[str, dict[int, list[dict]]],
) -> list[RoleNode]:
    """Build role graph: what each track does in each section.

    track_data: [{index, name, devices: [{class_name, ...}]}]
    notes_by_section_track: {section_id: {track_index: [notes]}}
    """
    roles = []
    for section in sections:
        for track in track_data:
            t_idx = track.get("index", 0)
            if t_idx not in section.tracks_active:
                continue

            t_name = track.get("name", "")
            devices = track.get("devices", [])
            device_class = devices[0].get("class_name", "") if devices else ""

            section_notes = notes_by_section_track.get(section.section_id, {}).get(t_idx, [])

            role, confidence, foreground = infer_role_for_track(
                t_name, section_notes, device_class,
            )

            roles.append(RoleNode(
                track_index=t_idx,
                track_name=t_name,
                section_id=section.section_id,
                role=role,
                confidence=confidence,
                foreground=foreground,
            ))

    return roles


# ── Composition Critics ───────────────────────────────────────────────

@dataclass
class CompositionIssue:
    """A structural or musical problem detected by a critic."""
    issue_type: str
    critic: str  # "form", "section_identity", "phrase"
    severity: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    scope: dict = field(default_factory=dict)  # e.g., {"section_id": "sec_01"}
    recommended_moves: list[str] = field(default_factory=list)
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


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


# ── Gesture Planner ───────────────────────────────────────────────────

# Maps gesture intents to automation parameters and curve families
_GESTURE_MAPPINGS: dict[GestureIntent, dict] = {
    GestureIntent.REVEAL: {
        "description": "Open filter, introduce width, grow send level, unmask harmonics",
        "parameter_hints": ["filter_cutoff", "send_level", "utility_width"],
        "curve_family": "exponential",
        "default_direction": "up",
        "typical_duration_bars": 4,
    },
    GestureIntent.CONCEAL: {
        "description": "Close filter, narrow image, reduce send, darken support",
        "parameter_hints": ["filter_cutoff", "volume", "utility_width"],
        "curve_family": "logarithmic",
        "default_direction": "down",
        "typical_duration_bars": 4,
    },
    GestureIntent.HANDOFF: {
        "description": "One voice dims while another emerges",
        "parameter_hints": ["volume", "send_level"],
        "curve_family": "s_curve",
        "default_direction": "crossfade",
        "typical_duration_bars": 2,
    },
    GestureIntent.INHALE: {
        "description": "Pull energy back before impact — pre-drop vacuum",
        "parameter_hints": ["volume", "filter_cutoff", "send_level"],
        "curve_family": "exponential",
        "default_direction": "down",
        "typical_duration_bars": 2,
    },
    GestureIntent.RELEASE: {
        "description": "Restore weight, width, or harmonic color after tension",
        "parameter_hints": ["filter_cutoff", "utility_width", "volume"],
        "curve_family": "spring",
        "default_direction": "up",
        "typical_duration_bars": 1,
    },
    GestureIntent.LIFT: {
        "description": "HP filter rise, reverb send increase — upward energy",
        "parameter_hints": ["hp_filter", "send_level", "reverb_mix"],
        "curve_family": "exponential",
        "default_direction": "up",
        "typical_duration_bars": 8,
    },
    GestureIntent.SINK: {
        "description": "LP filter close, remove highs, settle into sub",
        "parameter_hints": ["filter_cutoff", "eq_high"],
        "curve_family": "logarithmic",
        "default_direction": "down",
        "typical_duration_bars": 4,
    },
    GestureIntent.PUNCTUATE: {
        "description": "Dub throw spike, beat repeat burst — accent a moment",
        "parameter_hints": ["send_level", "beat_repeat"],
        "curve_family": "spike",
        "default_direction": "burst",
        "typical_duration_bars": 1,
    },
    GestureIntent.DRIFT: {
        "description": "Subtle organic movement — perlin noise on parameters",
        "parameter_hints": ["filter_cutoff", "pan", "send_level"],
        "curve_family": "perlin",
        "default_direction": "oscillate",
        "typical_duration_bars": 8,
    },
}


@dataclass
class GesturePlan:
    """A concrete automation plan derived from a musical gesture intent."""
    gesture_id: str
    intent: GestureIntent
    description: str
    target_tracks: list[int]
    parameter_hints: list[str]
    curve_family: str
    direction: str
    start_bar: int
    end_bar: int
    foreground: bool  # is this a musical focus or background motion?

    def to_dict(self) -> dict:
        d = asdict(self)
        d["intent"] = self.intent.value
        d["duration_bars"] = self.end_bar - self.start_bar
        return d


def plan_gesture(
    intent: GestureIntent,
    target_tracks: list[int],
    start_bar: int,
    duration_bars: Optional[int] = None,
    foreground: bool = False,
) -> GesturePlan:
    """Create a gesture plan from a musical intent.

    Maps the abstract intent to concrete automation parameters and curve type.
    The agent uses this plan with apply_automation_shape to execute.
    """
    mapping = _GESTURE_MAPPINGS.get(intent)
    if mapping is None:
        raise ValueError(f"Unknown gesture intent: {intent}")

    actual_duration = duration_bars or mapping["typical_duration_bars"]

    return GesturePlan(
        gesture_id=f"gest_{intent.value}_{start_bar}",
        intent=intent,
        description=mapping["description"],
        target_tracks=target_tracks,
        parameter_hints=mapping["parameter_hints"],
        curve_family=mapping["curve_family"],
        direction=mapping["default_direction"],
        start_bar=start_bar,
        end_bar=start_bar + actual_duration,
        foreground=foreground,
    )


# ── Composition Evaluation ────────────────────────────────────────────

COMPOSITION_DIMENSIONS = frozenset({
    "section_clarity", "phrase_completion", "narrative_pacing",
    "transition_strength", "orchestration_clarity", "tension_release",
})


def evaluate_composition_move(
    before_issues: list[CompositionIssue],
    after_issues: list[CompositionIssue],
    target_dimensions: dict[str, float],
    protect: dict[str, float],
) -> dict:
    """Evaluate whether a composition move improved the arrangement.

    Compares issue counts and severities before and after.
    Returns: {score, keep_change, issue_delta, notes}
    """
    notes: list[str] = []

    # Count issues by type before and after
    before_count = len(before_issues)
    after_count = len(after_issues)
    issue_delta = before_count - after_count

    # Severity-weighted improvement
    before_severity = sum(i.severity for i in before_issues)
    after_severity = sum(i.severity for i in after_issues)
    severity_improvement = before_severity - after_severity

    # Score: positive improvement = good
    if before_count > 0:
        improvement_ratio = severity_improvement / max(before_severity, 0.01)
    else:
        improvement_ratio = 0.0 if after_count == 0 else -0.5

    # Normalize to 0-1 score
    score = max(0.0, min(1.0, 0.5 + improvement_ratio * 0.5))

    # Keep/undo decision
    keep_change = True

    if severity_improvement < 0:
        keep_change = False
        notes.append(f"WORSE: total severity increased by {-severity_improvement:.2f}")

    if after_count > before_count + 1:
        keep_change = False
        notes.append(f"NEW ISSUES: {after_count - before_count} new issues introduced")

    if score < 0.40:
        keep_change = False
        notes.append(f"SCORE: {score:.3f} below 0.40 threshold")

    if keep_change and severity_improvement > 0:
        notes.append(f"IMPROVED: resolved {issue_delta} issue(s), severity reduced by {severity_improvement:.2f}")

    return {
        "score": round(score, 4),
        "keep_change": keep_change,
        "issue_delta": issue_delta,
        "before_issue_count": before_count,
        "after_issue_count": after_count,
        "severity_improvement": round(severity_improvement, 4),
        "notes": notes,
        "consecutive_undo_hint": not keep_change,
    }


# ── Full Analysis Pipeline ────────────────────────────────────────────

@dataclass
class CompositionAnalysis:
    """Complete composition analysis result."""
    sections: list[SectionNode]
    phrases: list[PhraseUnit]
    roles: list[RoleNode]
    issues: list[CompositionIssue]

    def to_dict(self) -> dict:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "section_count": len(self.sections),
            "phrases": [p.to_dict() for p in self.phrases],
            "phrase_count": len(self.phrases),
            "roles": [r.to_dict() for r in self.roles],
            "role_count": len(self.roles),
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": len(self.issues),
            "issue_summary": {
                "form": len([i for i in self.issues if i.critic == "form"]),
                "section_identity": len([i for i in self.issues if i.critic == "section_identity"]),
                "phrase": len([i for i in self.issues if i.critic == "phrase"]),
            },
        }

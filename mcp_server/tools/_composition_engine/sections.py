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

from .models import SectionType, RoleType, SectionNode, PhraseUnit, RoleNode

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


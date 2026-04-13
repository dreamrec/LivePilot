"""Slice workflow planner — generates MIDI patterns for sliced samples.

Given a slice count and musical intent, produces a complete workflow plan:
- Create a clip
- Program MIDI notes mapped to Simpler slices
- Suggest follow-up techniques

This is pure computation — does not execute against Ableton.
"""

from __future__ import annotations

import hashlib

# Simpler maps slices to MIDI notes starting at C3 (60)
SLICE_BASE_NOTE = 60


def plan_slice_steps(
    slice_count: int,
    intent: str = "rhythm",
    bars: int = 4,
    tempo: float = 120.0,
    track_index: int = 0,
    clip_slot_index: int = 0,
) -> dict:
    """Generate a slice workflow plan with real MIDI notes.

    Returns a dict with steps (tool calls), note_map, and suggestions.
    """
    note_map = _build_note_map(slice_count)
    beats = bars * 4  # 4/4 time
    notes = _generate_notes(note_map, intent, beats, slice_count)

    steps = []

    steps.append({
        "tool": "create_clip",
        "params": {
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "length": float(beats),
            "name": f"Slice {intent}",
        },
        "description": f"Create {bars}-bar clip for {intent} slice pattern",
    })

    steps.append({
        "tool": "add_notes",
        "params": {
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "notes": notes,
        },
        "description": f"Program {len(notes)} notes across {slice_count} slices",
    })

    return {
        "steps": steps,
        "note_map": note_map,
        "slice_count": slice_count,
        "intent": intent,
        "bars": bars,
        "note_count": len(notes),
        "suggested_techniques": _suggest_techniques(intent),
    }


def _build_note_map(slice_count: int) -> list[dict]:
    """Map slice indices to MIDI notes."""
    return [
        {"slice_index": i, "midi_note": SLICE_BASE_NOTE + i, "label": f"Slice {i + 1}"}
        for i in range(slice_count)
    ]


def _generate_notes(
    note_map: list[dict], intent: str, beats: int, slice_count: int,
) -> list[dict]:
    """Generate MIDI notes based on intent. Uses deterministic patterns."""
    generators = {
        "rhythm": _gen_rhythm,
        "hook": _gen_hook,
        "texture": _gen_texture,
        "percussion": _gen_percussion,
        "melodic": _gen_melodic,
    }
    gen = generators.get(intent, _gen_rhythm)
    return gen(note_map, beats, slice_count)


def _gen_rhythm(note_map: list, beats: int, sc: int) -> list[dict]:
    """Sparse groove — hits on downbeats and off-beats."""
    notes = []
    step = 0.5  # 8th notes
    for t in range(int(beats / step)):
        time = t * step
        if t % 4 == 0:
            idx = 0
        elif t % 4 == 2:
            idx = min(1, sc - 1)
        elif t % 8 in (3, 7) and sc > 2:
            idx = min(2 + (t % 3), sc - 1)
        else:
            continue
        vel = 100 - (t % 4) * 5  # Downbeats louder
        notes.append({
            "pitch": note_map[idx]["midi_note"],
            "start_time": time,
            "duration": step * 0.8,
            "velocity": max(60, min(127, vel)),
        })
    return notes


def _gen_hook(note_map: list, beats: int, sc: int) -> list[dict]:
    """Repeated motif contour — short phrase looped."""
    phrase_len = min(4.0, beats)
    motif_slices = list(range(min(4, sc)))
    notes = []
    reps = max(1, int(beats / phrase_len))
    for rep in range(reps):
        offset = rep * phrase_len
        for i, idx in enumerate(motif_slices):
            notes.append({
                "pitch": note_map[idx]["midi_note"],
                "start_time": offset + i * (phrase_len / len(motif_slices)),
                "duration": phrase_len / len(motif_slices) * 0.9,
                "velocity": 100 - i * 5,
            })
    return notes


def _gen_texture(note_map: list, beats: int, sc: int) -> list[dict]:
    """Sparse, long notes — sustained atmosphere."""
    notes = []
    used = min(3, sc)
    spacing = beats / max(used, 1)
    for i in range(used):
        notes.append({
            "pitch": note_map[i]["midi_note"],
            "start_time": i * spacing,
            "duration": spacing * 0.95,
            "velocity": 65,
        })
    return notes


def _gen_percussion(note_map: list, beats: int, sc: int) -> list[dict]:
    """Kick/snare/hat-like distribution."""
    notes = []
    step = 0.25  # 16th notes
    for t in range(int(beats / step)):
        time = t * step
        if t % 8 == 0 and sc > 0:
            notes.append({"pitch": note_map[0]["midi_note"], "start_time": time,
                         "duration": 0.2, "velocity": 110})
        if t % 8 == 4 and sc > 1:
            notes.append({"pitch": note_map[min(1, sc - 1)]["midi_note"], "start_time": time,
                         "duration": 0.2, "velocity": 100})
        if t % 2 == 0 and sc > 2:
            notes.append({"pitch": note_map[min(2, sc - 1)]["midi_note"], "start_time": time,
                         "duration": 0.15, "velocity": 70})
    return notes


def _gen_melodic(note_map: list, beats: int, sc: int) -> list[dict]:
    """Pitch contour phrase — ascending/descending motion."""
    notes = []
    phrase_notes = min(8, sc)
    step = beats / max(phrase_notes, 1)
    for i in range(phrase_notes):
        notes.append({
            "pitch": note_map[i % sc]["midi_note"],
            "start_time": i * step,
            "duration": step * 0.85,
            "velocity": 85,
        })
    return notes


def _suggest_techniques(intent: str) -> list[str]:
    """Suggest follow-up techniques based on intent."""
    suggestions = {
        "rhythm": ["quantize_clip", "add reverb send for depth", "layer with acoustic hits"],
        "hook": ["duplicate for variation", "add filter automation", "pitch shift for call-response"],
        "texture": ["heavy reverb send", "low-pass filter automation", "pan automation"],
        "percussion": ["parallel compression", "transient shaping", "short room reverb send"],
        "melodic": ["add delay send", "pitch correction if needed", "double with octave layer"],
    }
    return suggestions.get(intent, ["quantize_clip", "add effects"])

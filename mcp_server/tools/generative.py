"""Generative music tools — Euclidean rhythms, tintinnabuli, phase shift, additive process.

5 tools returning note arrays. Pure computation — no Ableton connection needed.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastmcp import Context

from ..server import mcp
from . import _generative_engine as gen
from . import _theory_engine as theory


def _ensure_list(value: Any) -> list:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in parameter: {exc}") from exc
    return value


# -- Tool 1: generate_euclidean_rhythm --------------------------------------

@mcp.tool()
def generate_euclidean_rhythm(
    ctx: Context,
    pulses: int,
    steps: int,
    rotation: int = 0,
    pitch: int = 36,
    velocity: int = 100,
    step_duration: float = 0.25,
) -> dict:
    """Generate a Euclidean rhythm using the Bjorklund algorithm.

    Distributes pulses as evenly as possible across steps. Identifies
    known rhythms (tresillo, cinquillo, bossa nova, etc.) when matched.
    Returns note array — use add_notes to place in a clip.
    """
    if not 0 <= pulses <= 64:
        return {"error": "pulses must be 0-64"}
    if not 1 <= steps <= 64:
        return {"error": "steps must be 1-64"}
    if pulses > steps:
        return {"error": "pulses must be <= steps"}

    pattern = gen.bjorklund(pulses, steps)
    if rotation:
        pattern = gen.rotate_pattern(pattern, rotation)

    notes = []
    for i, hit in enumerate(pattern):
        if hit:
            notes.append({
                "pitch": pitch,
                "start_time": round(i * step_duration, 4),
                "duration": step_duration,
                "velocity": velocity,
            })

    return {
        "notes": notes,
        "pattern": pattern,
        "name": gen.identify_rhythm(pulses, steps),
        "total_duration": round(steps * step_duration, 4),
    }


# -- Tool 2: layer_euclidean_rhythms ----------------------------------------

@mcp.tool()
def layer_euclidean_rhythms(
    ctx: Context,
    layers: Any,
) -> dict:
    """Stack multiple Euclidean rhythms for polyrhythmic textures.

    Each layer specifies pulses, steps, pitch, and optional velocity/rotation.
    Returns combined note array ready for add_notes.
    """
    layers = _ensure_list(layers)
    if not layers:
        return {"error": "At least one layer required"}

    all_notes: list[dict] = []
    layer_info: list[dict] = []
    max_duration = 0.0

    for layer in layers:
        p = int(layer["pulses"])
        s = int(layer["steps"])
        rot = int(layer.get("rotation", 0))
        pitch = int(layer["pitch"])
        vel = int(layer.get("velocity", 100))
        dur = float(layer.get("step_duration", 0.25))

        pattern = gen.bjorklund(p, s)
        if rot:
            pattern = gen.rotate_pattern(pattern, rot)

        layer_notes = []
        for i, hit in enumerate(pattern):
            if hit:
                layer_notes.append({
                    "pitch": pitch,
                    "start_time": round(i * dur, 4),
                    "duration": dur,
                    "velocity": vel,
                })

        all_notes.extend(layer_notes)
        total_dur = round(s * dur, 4)
        max_duration = max(max_duration, total_dur)
        layer_info.append({
            "pattern": pattern,
            "note_count": len(layer_notes),
            "name": gen.identify_rhythm(p, s),
        })

    return {
        "notes": sorted(all_notes, key=lambda n: n["start_time"]),
        "layers": layer_info,
        "total_duration": max_duration,
    }


# -- Tool 3: generate_tintinnabuli ------------------------------------------

@mcp.tool()
def generate_tintinnabuli(
    ctx: Context,
    melody_notes: Any,
    triad: str,
    position: str = "nearest",
    velocity: int = 80,
) -> dict:
    """Generate a tintinnabuli voice (Arvo Pärt technique).

    For each melody note, finds the nearest note of the specified triad.
    Returns the tintinnabuli voice as a separate note array — combine
    with the original melody via add_notes for the full Pärt effect.
    Only major and minor triads are supported.
    """
    melody_notes = _ensure_list(melody_notes)
    if not melody_notes:
        return {"error": "melody_notes cannot be empty"}
    if position not in ("above", "below", "nearest"):
        return {"error": "position must be 'above', 'below', or 'nearest'"}

    try:
        parsed = theory.parse_key(triad)
    except ValueError:
        return {"error": f"Cannot parse triad: {triad}"}
    if parsed["mode"] not in ("major", "minor"):
        return {"error": "Only major and minor triads are supported"}

    root = parsed["tonic"]
    if parsed["mode"] == "major":
        triad_pcs = [root, (root + 4) % 12, (root + 7) % 12]
    else:
        triad_pcs = [root, (root + 3) % 12, (root + 7) % 12]

    melody_pitches = [int(n["pitch"]) for n in melody_notes]
    t_pitches = gen.tintinnabuli_voice(melody_pitches, triad_pcs, position)

    notes = []
    for i, n in enumerate(melody_notes):
        notes.append({
            "pitch": t_pitches[i],
            "start_time": float(n["start_time"]),
            "duration": float(n["duration"]),
            "velocity": velocity,
        })

    triad_name = f"{theory.NOTE_NAMES[root]} {parsed['mode']}"
    return {
        "notes": notes,
        "technique": "tintinnabuli",
        "triad_used": triad_name,
        "description": f"T-voice moves to {position} {triad_name} triad tone for each melody note",
    }


# -- Tool 4: generate_phase_shift -------------------------------------------

@mcp.tool()
def generate_phase_shift(
    ctx: Context,
    pattern_notes: Any,
    voices: int = 2,
    shift_amount: float = 0.125,
    total_length: float = 16.0,
) -> dict:
    """Generate a phase-shifted canon (Steve Reich technique).

    Voice 0 loops the pattern normally. Each subsequent voice drifts
    by shift_amount beats per repetition, creating gradual phase displacement.
    Returns combined note array with velocity-encoded voices.
    """
    pattern_notes = _ensure_list(pattern_notes)
    if not pattern_notes:
        return {"error": "pattern_notes cannot be empty"}
    if not 1 <= voices <= 8:
        return {"error": "voices must be 1-8"}
    if shift_amount <= 0:
        return {"error": "shift_amount must be > 0"}

    result_notes = gen.phase_shift(pattern_notes, voices, shift_amount, total_length)

    pattern_length = max(n["start_time"] + n["duration"] for n in pattern_notes)

    alignment = None
    if voices == 2 and shift_amount > 0 and pattern_length > 0:
        alignment = round((pattern_length / shift_amount) * pattern_length, 4)
        if alignment > total_length:
            alignment = None

    return {
        "notes": result_notes,
        "voices": voices,
        "shift_per_repeat": shift_amount,
        "pattern_length": round(pattern_length, 4),
        "full_alignment_at": alignment,
    }


# -- Tool 5: generate_additive_process --------------------------------------

@mcp.tool()
def generate_additive_process(
    ctx: Context,
    melody_notes: Any,
    direction: str = "forward",
    repetitions_per_stage: int = 2,
) -> dict:
    """Generate an additive process (Philip Glass technique).

    Forward: builds melody note by note (1, then 1-2, then 1-2-3...).
    Backward: full melody, then removes from front.
    Both: forward then backward.
    Returns note array — use add_notes to place in a clip.
    """
    melody_notes = _ensure_list(melody_notes)
    if not melody_notes:
        return {"error": "melody_notes cannot be empty"}
    if direction not in ("forward", "backward", "both"):
        return {"error": "direction must be 'forward', 'backward', or 'both'"}
    if repetitions_per_stage < 1:
        return {"error": "repetitions_per_stage must be >= 1"}

    result_notes = gen.additive_process(melody_notes, direction,
                                         repetitions_per_stage)
    n = len(melody_notes)
    if direction == "forward":
        stages = n
    elif direction == "backward":
        stages = n
    else:
        stages = (2 * n) - 1

    total_duration = max(
        (no["start_time"] + no["duration"] for no in result_notes),
        default=0.0,
    )

    return {
        "notes": result_notes,
        "stages": stages,
        "total_duration": round(total_duration, 4),
        "direction": direction,
    }

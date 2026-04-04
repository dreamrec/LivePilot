"""MIDI file I/O tools — export, import, analyze, piano roll.

4 tools bridging LivePilot's session clips with .mid files.
Tools 1-2 require Ableton connection. Tools 3-4 are offline-capable.
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path
from typing import Any, Optional

from fastmcp import Context

from ..connection import AbletonConnectionError
from ..server import mcp
from . import _theory_engine as theory


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _require_midiutil():
    try:
        from midiutil import MIDIFile
        return MIDIFile
    except ImportError:
        raise ImportError(
            "midiutil is required for MIDI export. "
            "Install with: pip install midiutil"
        )


def _require_pretty_midi():
    try:
        import pretty_midi
        return pretty_midi
    except ImportError:
        raise ImportError(
            "pretty-midi is required for this tool. "
            "Install with: pip install pretty-midi"
        )


def _output_dir() -> Path:
    d = Path.home() / "Documents" / "LivePilot" / "outputs" / "midi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_output_path(directory: Path, filename: str) -> Path:
    """Join *filename* to *directory* with path-traversal containment.

    Strips directory components (``../../evil.mid`` → ``evil.mid``),
    resolves the result, and verifies it is still inside *directory*.
    Raises ``ValueError`` on any escape attempt.
    """
    safe_name = Path(filename).name          # strip directory components
    if not safe_name:
        raise ValueError(f"Invalid filename: {filename!r}")
    out = (directory / safe_name).resolve()
    if not str(out).startswith(str(directory.resolve())):
        raise ValueError(f"Filename escapes output directory: {filename!r}")
    return out


def _validate_midi_path(file_path: str) -> Path:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if p.suffix.lower() not in (".mid", ".midi"):
        raise ValueError(f"Not a MIDI file: {file_path}")
    return p


def _midi_notes_to_beats(pm) -> list[dict]:
    """Convert pretty_midi notes to beat-position dicts using the file's own tempo map.

    Uses time_to_tick/resolution to preserve the MIDI file's beat grid,
    regardless of the current Ableton session tempo.
    """
    notes_raw = []
    for inst in pm.instruments:
        for n in inst.notes:
            start_beat = round(pm.time_to_tick(n.start) / pm.resolution, 3)
            end_beat = round(pm.time_to_tick(n.end) / pm.resolution, 3)
            dur_beat = round(end_beat - start_beat, 3)
            notes_raw.append({
                "pitch": n.pitch,
                "start_time": start_beat,
                "duration": max(dur_beat, 0.001),
                "velocity": n.velocity,
            })
    return notes_raw


# -- Tool 1: export_clip_midi ------------------------------------------------

@mcp.tool()
def export_clip_midi(
    ctx: Context,
    track_index: int,
    clip_index: int,
    filename: Optional[str] = None,
) -> dict:
    """Export a session clip's notes to a .mid file.

    Fetches notes from the clip and writes them to a standard MIDI file.
    Auto-generates filename from track/clip if not provided.
    """
    MIDIFile = _require_midiutil()
    ableton = _get_ableton(ctx)

    notes_result = ableton.send_command("get_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    notes = notes_result.get("notes", [])

    session = ableton.send_command("get_session_info", {})
    tempo = float(session.get("tempo", 120.0))

    if not filename:
        filename = f"track{track_index}_clip{clip_index}.mid"
    if not filename.endswith((".mid", ".midi")):
        filename += ".mid"

    out_path = _safe_output_path(_output_dir(), filename)

    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo)

    duration_beats = 0.0
    for n in notes:
        start = float(n["start_time"])
        dur = float(n["duration"])
        pitch = int(n["pitch"])
        vel = int(n.get("velocity", 100))
        midi.addNote(0, 0, pitch, start, dur, vel)
        duration_beats = max(duration_beats, start + dur)

    with open(out_path, "wb") as f:
        midi.writeFile(f)

    return {
        "file_path": str(out_path),
        "note_count": len(notes),
        "duration_beats": round(duration_beats, 4),
        "tempo": tempo,
    }


# -- Tool 2: import_midi_to_clip ---------------------------------------------

@mcp.tool()
def import_midi_to_clip(
    ctx: Context,
    file_path: str,
    track_index: int,
    clip_index: int,
    create_clip: bool = True,
) -> dict:
    """Load a .mid file into a session clip.

    Reads MIDI, converts timing to beats using the file's own tempo map,
    and writes notes into the target clip slot. When create_clip=True
    (default), creates a new clip if the slot is empty; if a clip already
    exists, clears its notes before importing.
    """
    pretty_midi = _require_pretty_midi()
    ableton = _get_ableton(ctx)

    path = _validate_midi_path(file_path)
    pm = pretty_midi.PrettyMIDI(str(path))

    # Convert using the MIDI file's own tempo map (not session tempo)
    notes_raw = _midi_notes_to_beats(pm)

    seen = set()
    notes = []
    for n in notes_raw:
        key = (n["pitch"], round(n["start_time"], 3), round(n["duration"], 3))
        if key not in seen:
            seen.add(key)
            notes.append(n)

    notes = notes[:2000]

    duration_beats = max((n["start_time"] + n["duration"] for n in notes),
                         default=4.0)

    if create_clip:
        # Check if clip already exists — only create if the slot is empty
        slot_has_clip = False
        try:
            ableton.send_command("get_clip_info", {
                "track_index": track_index,
                "clip_index": clip_index,
            })
            slot_has_clip = True
        except AbletonConnectionError:
            # Slot is empty — send_command raises AbletonConnectionError
            # for all Remote Script errors including INDEX_ERROR/NOT_FOUND
            pass

        if slot_has_clip:
            # Clip exists — clear its notes before importing
            ableton.send_command("remove_notes", {
                "track_index": track_index,
                "clip_index": clip_index,
            })
        else:
            # Empty slot — create a new clip
            ableton.send_command("create_clip", {
                "track_index": track_index,
                "clip_index": clip_index,
                "length": round(duration_beats, 2),
            })

    if notes:
        ableton.send_command("add_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

    tempo_changes = pm.get_tempo_changes()
    midi_tempo = float(tempo_changes[1][0]) if len(tempo_changes[1]) > 0 else 120.0

    return {
        "note_count": len(notes),
        "duration_beats": round(duration_beats, 4),
        "midi_tempo": midi_tempo,
    }


# -- Tool 3: analyze_midi_file -----------------------------------------------

@mcp.tool()
def analyze_midi_file(
    ctx: Context,
    file_path: str,
) -> dict:
    """Analyze a .mid file — works offline, no Ableton needed.

    Returns note count, duration, tempo, pitch range, instruments,
    velocity stats, density curve, and estimated key.
    """
    pretty_midi = _require_pretty_midi()
    path = _validate_midi_path(file_path)
    pm = pretty_midi.PrettyMIDI(str(path))

    all_notes = []
    for inst in pm.instruments:
        for n in inst.notes:
            all_notes.append(n)

    if not all_notes:
        return {
            "note_count": 0,
            "duration_seconds": round(pm.get_end_time(), 2),
            "tempo_estimates": list(pm.get_tempo_changes()[1]),
            "pitch_range": [0, 0],
            "instruments": [i.name for i in pm.instruments],
            "velocity_stats": {},
            "density_curve": [],
            "key_estimate": "unknown",
        }

    pitches = [n.pitch for n in all_notes]
    velocities = [n.velocity for n in all_notes]
    duration = pm.get_end_time()

    density_curve = []
    window = 1.0
    t = 0.0
    while t < duration:
        count = sum(1 for n in all_notes if t <= n.start < t + window)
        density_curve.append({
            "time": round(t, 1),
            "density": count / window,
        })
        t += window

    notes_for_key = [
        {"pitch": n.pitch, "duration": n.end - n.start}
        for n in all_notes
    ]
    key_result = theory.detect_key(notes_for_key)
    key_str = f"{key_result['tonic_name']} {key_result['mode']}"

    vel_stats = {
        "mean": round(statistics.mean(velocities), 1),
        "min": min(velocities),
        "max": max(velocities),
        "std": round(statistics.stdev(velocities), 1) if len(velocities) > 1 else 0.0,
    }

    return {
        "note_count": len(all_notes),
        "duration_seconds": round(duration, 2),
        "tempo_estimates": [round(t, 1) for t in pm.get_tempo_changes()[1]],
        "pitch_range": [min(pitches), max(pitches)],
        "instruments": [i.name for i in pm.instruments],
        "velocity_stats": vel_stats,
        "density_curve": density_curve,
        "key_estimate": key_str,
    }


# -- Tool 4: extract_piano_roll ----------------------------------------------

@mcp.tool()
def extract_piano_roll(
    ctx: Context,
    file_path: str,
    resolution: float = 0.125,
) -> dict:
    """Extract a 2D piano roll matrix from a .mid file. Offline-capable.

    Returns a velocity matrix [pitch_index][time_step] trimmed to
    the actual pitch range. Resolution is in beats (0.125 = 32nd note).
    """
    pretty_midi = _require_pretty_midi()
    path = _validate_midi_path(file_path)
    pm = pretty_midi.PrettyMIDI(str(path))

    tempo_changes = pm.get_tempo_changes()
    tempo = float(tempo_changes[1][0]) if len(tempo_changes[1]) > 0 else 120.0
    fs = (tempo / 60.0) / resolution

    roll = pm.get_piano_roll(fs=fs)  # shape (128, T)

    active_pitches = roll.sum(axis=1).nonzero()[0]
    if len(active_pitches) == 0:
        return {
            "piano_roll": [],
            "pitch_min": 0,
            "pitch_max": 0,
            "time_steps": 0,
            "resolution": resolution,
        }

    pitch_min = int(active_pitches[0])
    pitch_max = int(active_pitches[-1])
    trimmed = roll[pitch_min:pitch_max + 1, :]

    return {
        "piano_roll": trimmed.astype(int).tolist(),
        "pitch_min": pitch_min,
        "pitch_max": pitch_max,
        "time_steps": int(trimmed.shape[1]),
        "resolution": resolution,
    }

"""
LivePilot - Notes domain handlers (8 commands).

Uses Live 12's modern note API: add_new_notes, get_notes_extended,
remove_notes_extended, remove_notes_by_id, apply_note_modifications.
"""

from .router import register
from .utils import get_clip


@register("add_notes")
def add_notes(song, params):
    """Add MIDI notes to a clip using Live 12's modern API."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    notes = params["notes"]
    if not notes:
        raise ValueError("notes list cannot be empty")

    clip = get_clip(song, track_index, clip_index)
    import Live
    clip.begin_undo_step()
    try:
        note_specs = []
        for note in notes:
            spec = Live.Clip.MidiNoteSpecification(
                pitch=int(note["pitch"]),
                start_time=float(note["start_time"]),
                duration=float(note["duration"]),
                velocity=float(note.get("velocity", 100)),
                mute=bool(note.get("mute", False)),
            )
            note_specs.append(spec)
        clip.add_new_notes(tuple(note_specs))
    finally:
        clip.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes_added": len(notes),
    }


@register("get_notes")
def get_notes(song, params):
    """Get MIDI notes from a clip region."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    from_pitch = int(params.get("from_pitch", 0))
    pitch_span = int(params.get("pitch_span", 128))
    from_time = float(params.get("from_time", 0.0))
    time_span = float(params.get("time_span", clip.length))

    raw_notes = clip.get_notes_extended(from_pitch, pitch_span, from_time, time_span)

    result = []
    for note in raw_notes:
        result.append({
            "note_id": note.note_id,
            "pitch": note.pitch,
            "start_time": note.start_time,
            "duration": note.duration,
            "velocity": note.velocity,
            "mute": note.mute,
            "probability": note.probability,
            "velocity_deviation": note.velocity_deviation,
            "release_velocity": note.release_velocity,
        })

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes": result,
    }


@register("remove_notes")
def remove_notes(song, params):
    """Remove MIDI notes from a clip region."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    from_pitch = int(params.get("from_pitch", 0))
    pitch_span = int(params.get("pitch_span", 128))
    from_time = float(params.get("from_time", 0.0))
    time_span = float(params.get("time_span", clip.length))

    clip.remove_notes_extended(from_pitch, pitch_span, from_time, time_span)

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "removed": True,
    }


@register("remove_notes_by_id")
def remove_notes_by_id(song, params):
    """Remove specific MIDI notes by their IDs."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    note_ids = params["note_ids"]
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")

    clip = get_clip(song, track_index, clip_index)
    clip.remove_notes_by_id(tuple(int(nid) for nid in note_ids))

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "removed_count": len(note_ids),
    }


@register("modify_notes")
def modify_notes(song, params):
    """Modify existing MIDI notes by ID."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    modifications = params["modifications"]
    if not modifications:
        raise ValueError("modifications list cannot be empty")

    clip = get_clip(song, track_index, clip_index)

    # Get all notes to find the ones we need to modify
    all_notes = clip.get_notes_extended(0, 128, 0.0, clip.length)

    # Build a lookup by note_id
    note_map = {}
    for note in all_notes:
        note_map[note.note_id] = note

    # Apply modifications
    notes_to_modify = []
    for mod in modifications:
        note_id = int(mod["note_id"])
        if note_id not in note_map:
            raise ValueError("Note ID %d not found in clip" % note_id)
        note = note_map[note_id]
        if "pitch" in mod:
            note.pitch = int(mod["pitch"])
        if "start_time" in mod:
            note.start_time = float(mod["start_time"])
        if "duration" in mod:
            note.duration = float(mod["duration"])
        if "velocity" in mod:
            note.velocity = float(mod["velocity"])
        if "probability" in mod:
            note.probability = float(mod["probability"])
        notes_to_modify.append(note)

    clip.apply_note_modifications(tuple(notes_to_modify))

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "modified_count": len(notes_to_modify),
    }


@register("duplicate_notes")
def duplicate_notes(song, params):
    """Duplicate specific notes by ID, with optional time offset."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    note_ids = params["note_ids"]
    time_offset = float(params.get("time_offset", 0.0))
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")

    clip = get_clip(song, track_index, clip_index)
    note_id_set = set(int(nid) for nid in note_ids)

    # Get all notes and filter to the requested IDs
    all_notes = clip.get_notes_extended(0, 128, 0.0, clip.length)
    source_notes = []
    for note in all_notes:
        if note.note_id in note_id_set:
            source_notes.append({
                "pitch": note.pitch,
                "start_time": note.start_time + time_offset,
                "duration": note.duration,
                "velocity": note.velocity,
                "mute": note.mute,
            })

    if not source_notes:
        raise ValueError("No matching notes found for the given IDs")

    # Add the duplicated notes
    import Live
    clip.begin_undo_step()
    try:
        note_specs = []
        for note in source_notes:
            spec = Live.Clip.MidiNoteSpecification(
                pitch=int(note["pitch"]),
                start_time=float(note["start_time"]),
                duration=float(note["duration"]),
                velocity=float(note["velocity"]),
                mute=bool(note["mute"]),
            )
            note_specs.append(spec)
        clip.add_new_notes(tuple(note_specs))
    finally:
        clip.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "duplicated_count": len(source_notes),
    }


@register("transpose_notes")
def transpose_notes(song, params):
    """Transpose notes in a time range by a number of semitones."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    semitones = int(params["semitones"])
    clip = get_clip(song, track_index, clip_index)

    from_time = float(params.get("from_time", 0.0))
    time_span = float(params.get("time_span", clip.length))

    all_notes = clip.get_notes_extended(0, 128, from_time, time_span)

    notes_to_modify = []
    for note in all_notes:
        new_pitch = note.pitch + semitones
        if new_pitch < 0 or new_pitch > 127:
            continue
        note.pitch = new_pitch
        notes_to_modify.append(note)

    if notes_to_modify:
        clip.apply_note_modifications(tuple(notes_to_modify))

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "transposed_count": len(notes_to_modify),
        "semitones": semitones,
    }


@register("quantize_clip")
def quantize_clip(song, params):
    """Quantize a clip to a grid."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    grid = float(params["grid"])
    amount = float(params.get("amount", 1.0))

    clip = get_clip(song, track_index, clip_index)
    clip.quantize(grid, amount)

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "grid": grid,
        "amount": amount,
        "quantized": True,
    }

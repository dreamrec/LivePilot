"""
LivePilot - Notes domain handlers (8 commands).

Uses Live 12's modern note API: add_new_notes, get_notes_extended,
remove_notes_extended, remove_notes_by_id, apply_note_modifications.
"""

from .router import register
from .utils import get_clip, get_track


@register("add_notes")
def add_notes(song, params):
    """Add MIDI notes to a clip using Live 12's modern API.

    BUG-2026-04-22#1c FIX: Auto-extends `clip.loop_end` if any incoming
    note's `start_time + duration` exceeds it. Without this, Live
    silently drops the out-of-range notes — the response would say
    "notes_added: N" but get_notes would return fewer. The extension
    is reported back in the response as `loop_end_extended_to` when it
    fires, so callers can see what happened.
    """
    from ._clip_helpers import _extend_loop_end_for_notes

    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    notes = params["notes"]
    if not notes:
        raise ValueError("notes list cannot be empty")

    clip = get_clip(song, track_index, clip_index)
    extended_to = _extend_loop_end_for_notes(clip, notes)

    import Live
    song.begin_undo_step()
    try:
        note_specs = []
        for note in notes:
            kwargs = dict(
                pitch=int(note["pitch"]),
                start_time=float(note["start_time"]),
                duration=float(note["duration"]),
                velocity=float(note.get("velocity", 100)),
                mute=bool(note.get("mute", False)),
            )
            if "probability" in note:
                kwargs["probability"] = float(note["probability"])
            if "velocity_deviation" in note:
                kwargs["velocity_deviation"] = float(note["velocity_deviation"])
            if "release_velocity" in note:
                kwargs["release_velocity"] = float(note["release_velocity"])
            spec = Live.Clip.MidiNoteSpecification(**kwargs)
            note_specs.append(spec)
        clip.add_new_notes(tuple(note_specs))
    finally:
        song.end_undo_step()

    result = {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes_added": len(notes),
    }
    if extended_to is not None:
        result["loop_end_extended_to"] = extended_to
    return result


@register("get_notes")
def get_notes(song, params):
    """Get MIDI notes from a clip region."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    from_pitch = int(params.get("from_pitch", 0))
    pitch_span = int(params.get("pitch_span", 128))
    from_time = float(params.get("from_time", 0.0))
    # Default to clip length, but use a large span if clip has no length yet
    default_span = clip.length if clip.length > 0 else 32768.0
    time_span = float(params.get("time_span", default_span))

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
    default_span = clip.length if clip.length > 0 else 32768.0
    time_span = float(params.get("time_span", default_span))

    song.begin_undo_step()
    try:
        clip.remove_notes_extended(from_pitch, pitch_span, from_time, time_span)
    finally:
        song.end_undo_step()

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
    song.begin_undo_step()
    try:
        clip.remove_notes_by_id(tuple(int(nid) for nid in note_ids))
    finally:
        song.end_undo_step()

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

    # Get all notes — returns a C++ NoteVector that must be passed back intact
    all_notes = clip.get_notes_extended(0, 128, 0.0, clip.length + 1.0)

    # Build a lookup by note_id
    note_map = {}
    for note in all_notes:
        note_map[note.note_id] = note

    # Two-pass: validate every note_id BEFORE mutating any notes. The previous
    # one-pass version raised ValueError mid-loop after some notes had already
    # been mutated in place on the C++ NoteVector — yielding a half-modified
    # state where the caller saw an error but earlier edits silently stuck
    # (until apply_note_modifications was called, which it never was in the
    # error path). Fail-all or apply-all is the safer contract.
    missing = [int(mod["note_id"]) for mod in modifications
               if int(mod["note_id"]) not in note_map]
    if missing:
        raise ValueError(
            "Note IDs not found in clip: %s. No modifications applied." % missing
        )

    # Apply modifications in-place on the original NoteVector's objects
    modified_count = 0
    for mod in modifications:
        note_id = int(mod["note_id"])
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
        if "mute" in mod:
            note.mute = bool(mod["mute"])
        if "velocity_deviation" in mod:
            note.velocity_deviation = float(mod["velocity_deviation"])
        if "release_velocity" in mod:
            note.release_velocity = float(mod["release_velocity"])
        modified_count += 1

    # Pass the original NoteVector back — Boost.Python requires the C++ type
    song.begin_undo_step()
    try:
        clip.apply_note_modifications(all_notes)
    finally:
        song.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "modified_count": modified_count,
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
    all_notes = clip.get_notes_extended(0, 128, 0.0, clip.length + 1.0)
    source_notes = []
    for note in all_notes:
        if note.note_id in note_id_set:
            source_notes.append({
                "pitch": note.pitch,
                "start_time": note.start_time + time_offset,
                "duration": note.duration,
                "velocity": note.velocity,
                "mute": note.mute,
                "probability": note.probability,
                "velocity_deviation": note.velocity_deviation,
                "release_velocity": note.release_velocity,
            })

    if not source_notes:
        raise ValueError("No matching notes found for the given IDs")

    # Add the duplicated notes with all attributes preserved
    import Live
    song.begin_undo_step()
    try:
        note_specs = []
        for note in source_notes:
            kwargs = dict(
                pitch=int(note["pitch"]),
                start_time=float(note["start_time"]),
                duration=float(note["duration"]),
                velocity=float(note["velocity"]),
                mute=bool(note["mute"]),
            )
            if note.get("probability") is not None:
                kwargs["probability"] = float(note["probability"])
            if note.get("velocity_deviation") is not None:
                kwargs["velocity_deviation"] = float(note["velocity_deviation"])
            if note.get("release_velocity") is not None:
                kwargs["release_velocity"] = float(note["release_velocity"])
            spec = Live.Clip.MidiNoteSpecification(**kwargs)
            note_specs.append(spec)
        clip.add_new_notes(tuple(note_specs))
    finally:
        song.end_undo_step()

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
    arrangement = bool(params.get("arrangement", False))

    if arrangement:
        track = get_track(song, track_index)
        arr_clips = list(track.arrangement_clips)
        if clip_index < 0 or clip_index >= len(arr_clips):
            raise IndexError(
                "Arrangement clip index %d out of range (0..%d)"
                % (clip_index, len(arr_clips) - 1)
            )
        clip = arr_clips[clip_index]
    else:
        clip = get_clip(song, track_index, clip_index)

    from_time = float(params.get("from_time", 0.0))
    # Default span covers from from_time to end of clip, not the full clip length
    default_span = max(0.0, clip.length - from_time) if clip.length > 0 else 32768.0
    time_span = float(params.get("time_span", default_span))

    # Get notes — returns C++ NoteVector that must be passed back intact
    all_notes = clip.get_notes_extended(0, 128, from_time, time_span)

    # Modify pitch in-place, skip notes that would go out of MIDI range
    transposed_count = 0
    skipped_count = 0
    total_in_range = 0
    for note in all_notes:
        total_in_range += 1
        new_pitch = note.pitch + semitones
        if new_pitch < 0 or new_pitch > 127:
            skipped_count += 1
            continue
        note.pitch = new_pitch
        transposed_count += 1

    if transposed_count > 0:
        # Pass the original NoteVector back — Boost.Python requires the C++ type
        song.begin_undo_step()
        try:
            clip.apply_note_modifications(all_notes)
        finally:
            song.end_undo_step()

    result = {
        "track_index": track_index,
        "clip_index": clip_index,
        "transposed_count": transposed_count,
        "semitones": semitones,
    }
    if skipped_count > 0:
        result["skipped_out_of_range"] = skipped_count
        result["warning"] = (
            "%d note(s) skipped — transposing by %+d semitones would "
            "exceed MIDI range (0-127)" % (skipped_count, semitones)
        )
    return result


@register("quantize_clip")
def quantize_clip(song, params):
    """Quantize a clip to a grid.

    grid is a RecordQuantization enum integer:
        0=None, 1=1/4, 2=1/8, 3=1/8T, 4=1/8+T,
        5=1/16, 6=1/16T, 7=1/16+T, 8=1/32
    """
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    grid = int(params["grid"])
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

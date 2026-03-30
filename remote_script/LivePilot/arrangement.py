"""
LivePilot - Arrangement domain handlers (19 commands).
"""

from .router import register
from .utils import get_track


@register("get_arrangement_clips")
def get_arrangement_clips(song, params):
    """Return all arrangement clips on a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    clips = []
    for i, clip in enumerate(track.arrangement_clips):
        info = {
            "index": i,
            "name": clip.name,
            "start_time": clip.start_time,
            "end_time": clip.start_time + clip.length,
            "length": clip.length,
            "color_index": clip.color_index,
            "is_audio_clip": clip.is_audio_clip,
        }
        # Add loop info if available
        try:
            if clip.looping:
                info["looping"] = True
                info["loop_start"] = clip.loop_start
                info["loop_end"] = clip.loop_end
        except (AttributeError, RuntimeError):
            pass
        clips.append(info)
    return {"track_index": track_index, "clips": clips}


@register("create_arrangement_clip")
def create_arrangement_clip(song, params):
    """Create MIDI clip(s) in arrangement view by duplicating a session clip.

    Uses Live 12's Track.duplicate_clip_to_arrangement(clip, time) API.
    When the requested length exceeds the source clip, multiple adjacent
    copies are placed to fill the timeline region seamlessly.

    Required: track_index, clip_slot_index, start_time, length
    Optional: loop_length (defaults to session clip length), name, color_index
    """
    track_index = int(params["track_index"])
    clip_slot_index = int(params["clip_slot_index"])
    start_time = float(params["start_time"])
    length = float(params["length"])
    if length <= 0:
        raise ValueError("length must be > 0")
    if start_time < 0:
        raise ValueError("start_time must be >= 0")

    track = get_track(song, track_index)

    # Get source session clip
    slots = list(track.clip_slots)
    if clip_slot_index < 0 or clip_slot_index >= len(slots):
        raise IndexError(
            "Clip slot index %d out of range (0..%d)"
            % (clip_slot_index, len(slots) - 1)
        )
    if not slots[clip_slot_index].has_clip:
        raise ValueError("No clip in slot %d" % clip_slot_index)
    source_clip = slots[clip_slot_index].clip
    source_length = source_clip.length

    # Use loop_length as the repeat unit (defaults to source clip length)
    loop_length = float(params.get("loop_length", source_length))
    if loop_length <= 0:
        raise ValueError("loop_length must be > 0")

    name = str(params.get("name", ""))
    color_index = params.get("color_index")

    # Place adjacent copies to fill the requested length
    song.begin_undo_step()
    try:
        pos = start_time
        end_pos = start_time + length
        clip_count = 0
        first_clip_index = None

        while pos < end_pos:
            # Snapshot clip IDs before duplication to identify the new one
            old_ids = set(id(c) for c in track.arrangement_clips)

            track.duplicate_clip_to_arrangement(source_clip, pos)

            # Find the NEW clip (not in old_ids) at the target position
            arr_clips = list(track.arrangement_clips)
            new_clip = None
            new_clip_idx = None
            for i, c in enumerate(arr_clips):
                if id(c) not in old_ids and abs(c.start_time - pos) < 0.01:
                    new_clip = c
                    new_clip_idx = i
                    break

            # Fallback: if id-based detection fails, match by position
            if new_clip is None:
                for i, c in enumerate(arr_clips):
                    if abs(c.start_time - pos) < 0.01:
                        new_clip = c
                        new_clip_idx = i
                        break

            if new_clip is not None:
                if first_clip_index is None:
                    first_clip_index = new_clip_idx
                if name:
                    new_clip.name = name
                if color_index is not None:
                    new_clip.color_index = int(color_index)

                # When loop_length < source_length, set the internal
                # loop region so only loop_length beats of content play.
                remaining = end_pos - pos
                target_len = min(loop_length, remaining)
                if target_len < source_length:
                    try:
                        new_clip.looping = True
                        new_clip.loop_start = 0.0
                        new_clip.loop_end = target_len
                    except (AttributeError, RuntimeError):
                        pass

            clip_count += 1
            pos += loop_length

        # Trim the last clip's overshoot: if the last duplicate extends
        # past end_pos, remove notes beyond the requested region and
        # set loop_end so only the needed portion plays.
        if clip_count > 0:
            arr_clips = list(track.arrangement_clips)
            for c in arr_clips:
                clip_end = c.start_time + c.length
                if c.start_time >= start_time and clip_end > end_pos + 0.01:
                    # This clip overshoots — trim its content
                    overshoot_start = end_pos - c.start_time
                    if overshoot_start > 0:
                        try:
                            c.looping = True
                            c.loop_start = 0.0
                            c.loop_end = overshoot_start
                        except (AttributeError, RuntimeError):
                            pass
                        # Remove notes beyond the trim point
                        try:
                            c.remove_notes_extended(
                                0, 128, overshoot_start, c.length
                            )
                        except Exception:
                            pass
    finally:
        song.end_undo_step()

    # Re-read to get accurate final state
    arr_clips = list(track.arrangement_clips)
    if first_clip_index is None or first_clip_index >= len(arr_clips):
        raise ValueError("Failed to place any clips in arrangement")
    first_clip = arr_clips[first_clip_index]

    return {
        "track_index": track_index,
        "clip_index": first_clip_index,
        "start_time": start_time,
        "length": length,
        "clip_count": clip_count,
        "source_length": source_length,
        "name": first_clip.name if first_clip else "",
    }


@register("add_arrangement_notes")
def add_arrangement_notes(song, params):
    """Add MIDI notes to an arrangement clip (by index in arrangement_clips)."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    notes = params["notes"]
    if not notes:
        raise ValueError("notes list cannot be empty")
    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]
    import Live
    song.begin_undo_step()
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
        song.end_undo_step()
    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes_added": len(notes),
    }


@register("get_arrangement_notes")
def get_arrangement_notes(song, params):
    """Get MIDI notes from an arrangement clip region."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]

    from_pitch = int(params.get("from_pitch", 0))
    pitch_span = int(params.get("pitch_span", 128))
    from_time = float(params.get("from_time", 0.0))
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


@register("remove_arrangement_notes")
def remove_arrangement_notes(song, params):
    """Remove MIDI notes from an arrangement clip region."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]

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


@register("remove_arrangement_notes_by_id")
def remove_arrangement_notes_by_id(song, params):
    """Remove specific MIDI notes from an arrangement clip by their IDs."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    note_ids = params["note_ids"]
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")

    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]
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


@register("modify_arrangement_notes")
def modify_arrangement_notes(song, params):
    """Modify existing MIDI notes in an arrangement clip by ID."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    modifications = params["modifications"]
    if not modifications:
        raise ValueError("modifications list cannot be empty")

    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]

    all_notes = clip.get_notes_extended(0, 128, 0.0, clip.length + 1.0)

    note_map = {}
    for note in all_notes:
        note_map[note.note_id] = note

    modified_count = 0
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
        modified_count += 1

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


@register("duplicate_arrangement_notes")
def duplicate_arrangement_notes(song, params):
    """Duplicate specific notes in an arrangement clip by ID, with optional time offset."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    note_ids = params["note_ids"]
    time_offset = float(params.get("time_offset", 0.0))
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")

    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]
    note_id_set = set(int(nid) for nid in note_ids)

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


@register("set_arrangement_automation")
def set_arrangement_automation(song, params):
    """Write automation points into an arrangement clip's envelope.

    Required: track_index, clip_index, parameter_type, points
    Optional: device_index, parameter_index, send_index

    parameter_type: "device", "volume", "panning", "send"
    points: list of {time, value, duration} — time relative to clip start
    """
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    parameter_type = str(params["parameter_type"])
    points = params["points"]
    if not points:
        raise ValueError("points list cannot be empty")

    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]

    # Resolve the target parameter
    if parameter_type == "device":
        device_index = int(params["device_index"])
        parameter_index = int(params["parameter_index"])
        devices = list(track.devices)
        if device_index < 0 or device_index >= len(devices):
            raise IndexError("Device index %d out of range" % device_index)
        device_params = list(devices[device_index].parameters)
        if parameter_index < 0 or parameter_index >= len(device_params):
            raise IndexError("Parameter index %d out of range" % parameter_index)
        parameter = device_params[parameter_index]
    elif parameter_type == "volume":
        parameter = track.mixer_device.volume
    elif parameter_type == "panning":
        parameter = track.mixer_device.panning
    elif parameter_type == "send":
        send_index = int(params["send_index"])
        sends = list(track.mixer_device.sends)
        if send_index < 0 or send_index >= len(sends):
            raise IndexError("Send index %d out of range" % send_index)
        parameter = sends[send_index]
    else:
        raise ValueError(
            "parameter_type must be 'device', 'volume', 'panning', or 'send'"
        )

    # Clamp values to parameter range
    p_min = float(parameter.min)
    p_max = float(parameter.max)

    # Try direct envelope access on the arrangement clip
    envelope = clip.automation_envelope(parameter)
    if envelope is None:
        try:
            envelope = clip.create_automation_envelope(parameter)
        except (AttributeError, RuntimeError):
            pass

    if envelope is not None:
        # Direct approach works — write points to the arrangement clip
        song.begin_undo_step()
        try:
            points_written = 0
            for pt in points:
                time = float(pt["time"])
                value = max(p_min, min(p_max, float(pt["value"])))
                duration = float(pt.get("duration", 0.125))
                envelope.insert_step(time, duration, value)
                points_written += 1
        finally:
            song.end_undo_step()
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "parameter_name": parameter.name,
            "points_written": points_written,
            "method": "direct",
        }

    # No fallback — direct envelope creation is the only safe approach.
    # Session-clip duplication can silently create overlapping clips.
    return {
        "error": (
            "Cannot create automation envelope for parameter '%s' on this "
            "arrangement clip. Direct envelope access is not supported for "
            "this parameter type or Live version."
            % parameter.name
        ),
        "code": "STATE_ERROR",
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_name": parameter.name,
    }


@register("transpose_arrangement_notes")
def transpose_arrangement_notes(song, params):
    """Transpose notes in an arrangement clip by semitones."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    semitones = int(params["semitones"])
    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    clip = arr_clips[clip_index]

    from_time = float(params.get("from_time", 0.0))
    time_span = float(params.get("time_span", clip.length))

    all_notes = clip.get_notes_extended(0, 128, from_time, time_span)

    transposed_count = 0
    skipped_count = 0
    for note in all_notes:
        new_pitch = note.pitch + semitones
        if new_pitch < 0 or new_pitch > 127:
            skipped_count += 1
            continue
        note.pitch = new_pitch
        transposed_count += 1

    if transposed_count > 0:
        song.begin_undo_step()
        try:
            clip.apply_note_modifications(all_notes)
        finally:
            song.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "transposed_count": transposed_count,
        "skipped_count": skipped_count,
        "semitones": semitones,
    }


@register("set_arrangement_clip_name")
def set_arrangement_clip_name(song, params):
    """Rename an arrangement clip by its index."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    name = str(params["name"])
    track = get_track(song, track_index)
    arr_clips = list(track.arrangement_clips)
    if clip_index < 0 or clip_index >= len(arr_clips):
        raise IndexError(
            "Arrangement clip index %d out of range (0..%d)"
            % (clip_index, len(arr_clips) - 1)
        )
    arr_clips[clip_index].name = name
    return {"track_index": track_index, "clip_index": clip_index, "name": name}


@register("jump_to_time")
def jump_to_time(song, params):
    """Jump to a specific beat time in the arrangement."""
    beat_time = float(params["beat_time"])
    if beat_time < 0:
        raise ValueError("beat_time must be >= 0")
    song.current_song_time = beat_time
    # Echo requested value — getter may return stale state before update propagates
    return {"current_song_time": beat_time}


@register("capture_midi")
def capture_midi(song, params):
    """Capture recently played MIDI notes into a clip."""
    song.capture_midi()
    return {"captured": True}


@register("start_recording")
def start_recording(song, params):
    """Start recording in session or arrangement mode.

    Live requires transport to be playing for record_mode to engage.
    If not playing, we start playback first.
    """
    arrangement = bool(params.get("arrangement", False))
    if arrangement:
        if not song.is_playing:
            song.start_playing()
        song.record_mode = True
    else:
        song.session_record = True
    # Verify and report
    result = {
        "record_mode": song.record_mode,
        "session_record": song.session_record,
    }
    if arrangement and not song.record_mode:
        result["warning"] = "Record mode did not engage — check that at least one track is armed"
    if not arrangement and not song.session_record:
        result["warning"] = "Session record did not engage — check that at least one track is armed"
    return result


@register("stop_recording")
def stop_recording(song, params):
    """Stop all recording."""
    song.record_mode = False
    song.session_record = False
    return {"record_mode": False, "session_record": False}


@register("get_cue_points")
def get_cue_points(song, params):
    """Return all cue points in the arrangement."""
    cue_points = list(song.cue_points)
    result = []
    for i, cue in enumerate(cue_points):
        result.append({
            "index": i,
            "name": cue.name,
            "time": cue.time,
        })
    return {"cue_points": result}


@register("jump_to_cue")
def jump_to_cue(song, params):
    """Jump to a cue point by index."""
    cue_index = int(params["cue_index"])
    cue_points = list(song.cue_points)
    if cue_index < 0 or cue_index >= len(cue_points):
        raise IndexError(
            "Cue point index %d out of range (0..%d)"
            % (cue_index, len(cue_points) - 1)
        )
    cue_points[cue_index].jump()
    return {"cue_index": cue_index, "jumped": True}


@register("toggle_cue_point")
def toggle_cue_point(song, params):
    """Set or delete a cue point at the current position."""
    song.set_or_delete_cue()
    return {"toggled": True}


@register("back_to_arranger")
def back_to_arranger(song, params):
    """Switch playback from session clips back to the arrangement timeline."""
    song.back_to_arranger = True
    return {"back_to_arranger": song.back_to_arranger}

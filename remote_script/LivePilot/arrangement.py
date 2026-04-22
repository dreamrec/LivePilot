"""
LivePilot - Arrangement domain handlers (21 commands).

As of 2026-04-22: adds the two-phase session-record workaround for
track-level arrangement automation (T5 handoff). Live's LOM can't
write track-level automation envelopes outside a clip directly —
this handler pair writes to a session clip, records it into
arrangement at a target beat, then cleans up.
"""

from .clip_automation import set_clip_automation as _set_clip_automation_handler
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
            track.duplicate_clip_to_arrangement(source_clip, pos)

            # Find the new clip by position (id()-based detection is unreliable
            # because CPython can reuse addresses of GC'd LOM wrappers)
            arr_clips = list(track.arrangement_clips)
            new_clip = None
            new_clip_idx = None
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

    # Re-read to get accurate final state — locate by start_time, not stored
    # index, because the trim pass (remove_notes_extended) can shift indices.
    arr_clips = list(track.arrangement_clips)
    first_clip = None
    for c in arr_clips:
        if abs(c.start_time - start_time) < 0.01:
            first_clip = c
            break
    if first_clip is None:
        raise ValueError("Failed to place any clips in arrangement")

    return {
        "track_index": track_index,
        "start_time": start_time,
        "length": length,
        "clip_count": clip_count,
        "source_length": source_length,
        "name": first_clip.name,
    }


@register("create_native_arrangement_clip")
def create_native_arrangement_clip(song, params):
    """Create an empty MIDI clip in arrangement using the native 12.1.10+ API.

    Unlike create_arrangement_clip (which duplicates a session clip),
    this creates a true native clip with full automation envelope support.

    Required: track_index, start_time, length
    Optional: name, color_index
    """
    from .version_detect import has_feature

    if not has_feature("create_midi_clip_arrangement"):
        raise RuntimeError(
            "create_native_arrangement_clip requires Live 12.1.10+. "
            "Use create_arrangement_clip (session clip duplication) instead."
        )

    track_index = int(params["track_index"])
    start_time = float(params["start_time"])
    length = float(params["length"])
    if length <= 0:
        raise ValueError("length must be > 0")
    if start_time < 0:
        raise ValueError("start_time must be >= 0")

    track = get_track(song, track_index)
    if not track.has_midi_input:
        raise ValueError(
            "Track %d is not a MIDI track — create_native_arrangement_clip "
            "only works on MIDI tracks" % track_index
        )

    song.begin_undo_step()
    try:
        clip = track.create_midi_clip(start_time, length)

        name = params.get("name")
        if name:
            clip.name = str(name)
        color_index = params.get("color_index")
        if color_index is not None:
            clip.color_index = int(color_index)
    finally:
        song.end_undo_step()

    # Find the clip index in arrangement_clips
    clip_index = None
    for i, c in enumerate(track.arrangement_clips):
        if abs(c.start_time - start_time) < 0.01:
            clip_index = i
            break

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "start_time": start_time,
        "length": length,
        "name": clip.name,
        "has_envelope_support": True,
        "native": True,
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

    # Two-pass: validate all note_ids BEFORE mutating any notes. See the
    # identical fix in notes.py:modify_notes — partial mid-loop mutation on
    # the C++ NoteVector was leaving the clip in a half-modified state that
    # never got committed.
    missing = [int(mod["note_id"]) for mod in modifications
               if int(mod["note_id"]) not in note_map]
    if missing:
        raise ValueError(
            "Note IDs not found in arrangement clip: %s. "
            "No modifications applied." % missing
        )

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

    # BUG-2026-04-22#1b: This is a LIVE API LIMITATION, not a LivePilot bug.
    #
    # Per Ableton's Python LOM documentation:
    #   "Clip.automation_envelope returns None for Arrangement clips
    #    and parameters from a different track."
    #
    # The Python LOM exposes value_at_time() for READING existing
    # arrangement automation, but does NOT expose a method to CREATE
    # new automation breakpoints programmatically in the arrangement
    # view. Automation in arrangement view lives on the track's
    # automation lane, which is only writable via the GUI or by
    # recording.
    #
    # The two viable workarounds:
    #
    # 1. session-clip path (programmatic, but requires manual record):
    #    a. Use set_clip_automation on a session clip to write the points
    #    b. Arm the track for recording
    #    c. Switch to arrangement view and start recording at the target
    #       position
    #    d. Fire the session clip — Live records the parameter changes
    #       into the arrangement automation lane
    #    e. Stop recording when the session clip completes
    #
    # 2. manual draw path (most reliable): the user draws the envelope
    #    in arrangement view by hand. No code can replace this for now.
    #
    # We surface this clearly rather than silently failing or attempting
    # an unreliable workaround that could leave the session in a half-
    # configured state.
    raise RuntimeError(
        "Cannot create automation envelope for parameter '%s' on this "
        "arrangement clip. This is a Live LOM limitation, not a "
        "LivePilot bug: per Ableton's Python API docs, "
        "Clip.automation_envelope returns None for arrangement clips, "
        "and the LOM does not expose a method to CREATE new automation "
        "breakpoints in arrangement view (only value_at_time for "
        "READING existing automation). "
        "Two workarounds: "
        "(1) Session-clip path — call set_clip_automation on a session "
        "clip with the same points, then arm the track, switch to "
        "arrangement view, start arrangement record, fire the session "
        "clip, stop record when it finishes. Live records the parameter "
        "changes into the arrangement track lane. "
        "(2) Section-clip path — slice the arrangement into multiple "
        "clips and set per-clip volume/parameter values per section "
        "(no envelope, just stepped values per region)."
        % parameter.name
    )


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
    # Default span covers from from_time to end of clip, not the full clip length
    default_span = max(0.0, clip.length - from_time) if clip.length > 0 else 32768.0
    time_span = float(params.get("time_span", default_span))

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
    return {"back_to_arranger": True}


@register("force_arrangement")
def force_arrangement(song, params):
    """Force ALL tracks to follow the arrangement timeline.

    Stops all session clips, releases every track from session override,
    sets back_to_arranger, and optionally jumps to a start position.

    This is the atomic "play the arrangement from the top" command.
    """
    # 1. Stop playback
    was_playing = song.is_playing
    if was_playing:
        song.stop_playing()

    # 2. Stop playing clip slots individually to release session overrides
    #    (track.stop_all_clips() throws STATE_ERROR when tracks have no clips)
    for track in list(song.tracks) + list(song.return_tracks):
        try:
            for slot in track.clip_slots:
                if slot.has_clip and slot.is_playing:
                    slot.clip.stop()
        except Exception:
            pass

    # 3. Global back-to-arranger
    song.back_to_arranger = True

    # 4. Jump to position (default: start)
    beat_time = float(params.get("beat_time", 0))
    song.current_song_time = max(0, beat_time)

    # 5. Set loop if requested
    if "loop_length" in params:
        song.loop_start = float(params.get("loop_start", 0))
        song.loop_length = float(params["loop_length"])
        song.loop = True

    # 6. Start playback if requested (default: yes)
    play = params.get("play", True)
    if play:
        song.start_playing()

    return {
        "arrangement_active": True,
        "position": song.current_song_time,
        "is_playing": song.is_playing,
        "loop": song.loop,
    }


# ── Session-record arrangement automation (T5 workaround) ────────────
#
# Two-phase protocol so the MCP server can sleep between the record
# start and stop without blocking Live's main thread.
#
#   Phase 1: _start — write session clip, arm, seek, record, fire
#   Phase 2: _complete — stop record, stop transport, locate new
#                       arrangement clip, clean up session clip
#
# The MCP tool layer orchestrates: start → asyncio.sleep(duration * 60/tempo + 0.5) → complete.


def _fire_slot(slot):
    """Fire a clip slot robustly — Live's API changed between versions."""
    # Newer Live: slot.fire() is the canonical way. `slot.clip.fire()`
    # also works when a clip is present. Try slot-level first so empty
    # slots (we may have just created a clip) fire the row reliably.
    try:
        slot.fire()
    except AttributeError:
        slot.clip.fire()


def _ensure_session_clip_length(slot, points, min_length=1.0):
    """Ensure slot has a session MIDI clip covering the points' time range.

    Returns (clip, was_created). If the slot is empty we call
    create_clip(length). If points extend past the existing clip
    we leave it alone — the user may have intentional content before.
    """
    if not slot.has_clip:
        max_t = 0.0
        for p in points or []:
            t = float(p.get("time", 0))
            d = float(p.get("duration", 0.125))
            max_t = max(max_t, t + d)
        length = max(min_length, max_t)
        slot.create_clip(length)
        return slot.clip, True
    return slot.clip, False


@register("arrangement_automation_via_session_record_start")
def arrangement_automation_via_session_record_start(song, params):
    """Phase 1 of the T5 workaround.

    Preps the record: ensures session clip exists with automation, arms
    the track, seeks the arrangement to target_beat, enables record, and
    fires the session clip. Returns tempo so the MCP layer can compute
    the sleep duration before phase 2.
    """
    track_index = int(params["track_index"])
    session_clip_slot = int(params.get("session_clip_slot", 0))
    target_beat = float(params["target_beat"])
    parameter_type = params["parameter_type"]
    points = params.get("points") or []
    if not points:
        raise ValueError("points cannot be empty")

    track = get_track(song, track_index)

    # Probe 1: can we arm this track?
    if not getattr(track, "can_be_armed", False):
        raise ValueError(
            "track %d cannot be armed — session-record workaround requires "
            "an armable (MIDI or audio input) track" % track_index
        )

    slots = list(track.clip_slots)
    if session_clip_slot < 0 or session_clip_slot >= len(slots):
        raise IndexError(
            "session_clip_slot %d out of range (0..%d)"
            % (session_clip_slot, len(slots) - 1)
        )
    slot = slots[session_clip_slot]

    # Probe 2: create a session clip if the slot is empty; otherwise reuse
    clip, created = _ensure_session_clip_length(slot, points)

    # Probe 3: write the automation envelope via the existing handler.
    # We need to tell set_clip_automation which clip_index to target.
    # set_clip_automation takes clip_index = the slot index. Perfect.
    clip_auto_params = dict(params)
    clip_auto_params["clip_index"] = session_clip_slot
    # Drop keys that set_clip_automation doesn't expect
    for k in ("target_beat", "duration_beats", "session_clip_slot",
              "cleanup_session_clip"):
        clip_auto_params.pop(k, None)
    write_result = _set_clip_automation_handler(song, clip_auto_params)

    # Probe 4: seek the arrangement to target_beat. Must be done
    # BEFORE enabling record, or the record starts at wherever the
    # playhead currently is.
    song.back_to_arranger = True
    song.current_song_time = max(0.0, target_beat)

    # Probe 5: arm the track. Some tracks need `current_monitoring_state`
    # clarification, but arming alone should route the session clip's
    # output into arrangement record on most setups.
    track.arm = True

    # Probe 6: enable arrangement record + start transport. Live needs
    # the transport playing for record_mode to engage.
    if not song.is_playing:
        song.start_playing()
    song.record_mode = True

    # Fire the session clip — its automation plays into arrangement.
    _fire_slot(slot)

    return {
        "status": "recording",
        "track_index": track_index,
        "session_clip_slot": session_clip_slot,
        "target_beat": song.current_song_time,
        "tempo": float(song.tempo),
        "session_clip_created": created,
        "automation_write": write_result,
        "record_mode": bool(song.record_mode),
        "is_playing": bool(song.is_playing),
    }


@register("arrangement_automation_via_session_record_complete")
def arrangement_automation_via_session_record_complete(song, params):
    """Phase 2 of the T5 workaround.

    Stops recording, stops transport, disarms the track, locates the
    newly-recorded arrangement clip, and optionally cleans up the
    temporary session clip used to source the automation.
    """
    track_index = int(params["track_index"])
    session_clip_slot = int(params.get("session_clip_slot", 0))
    cleanup = bool(params.get("cleanup_session_clip", True))
    target_beat = float(params["target_beat"])
    duration_beats = float(params.get("duration_beats", 0))

    track = get_track(song, track_index)
    slots = list(track.clip_slots)
    if session_clip_slot < 0 or session_clip_slot >= len(slots):
        raise IndexError(
            "session_clip_slot %d out of range" % session_clip_slot
        )
    slot = slots[session_clip_slot]

    # 1. Stop recording and transport
    song.record_mode = False
    was_playing = song.is_playing
    if was_playing:
        song.stop_playing()

    # 2. Stop the session clip if still playing
    try:
        if slot.has_clip and getattr(slot, "is_playing", False):
            slot.clip.stop()
    except Exception:
        pass

    # 3. Disarm the track (leave as-was if never armed)
    try:
        track.arm = False
    except Exception:
        pass

    # 4. Find the new arrangement clip at or near target_beat.
    # Tolerance: half a beat — Live may nudge start by quantization.
    track_clips = list(track.arrangement_clips)
    new_clip = None
    new_index = None
    tolerance = 0.5
    for i, c in enumerate(track_clips):
        if abs(float(c.start_time) - target_beat) < tolerance:
            new_clip = c
            new_index = i
            break

    # 5. Cleanup the session clip if requested
    session_clip_deleted = False
    if cleanup and slot.has_clip:
        try:
            slot.delete_clip()
            session_clip_deleted = True
        except Exception:
            pass

    result = {
        "status": "completed",
        "track_index": track_index,
        "arrangement_clip_found": new_clip is not None,
        "arrangement_clip_index": new_index,
        "session_clip_deleted": session_clip_deleted,
        "record_mode": bool(song.record_mode),
        "was_playing": was_playing,
    }
    if new_clip is not None:
        result["arrangement_clip_start"] = float(new_clip.start_time)
        result["arrangement_clip_length"] = float(new_clip.length)
        try:
            result["arrangement_clip_name"] = str(new_clip.name)
        except Exception:
            pass
    elif duration_beats > 0:
        # Guess based on expected range — helpful debug if the lookup missed
        result["expected_clip_start"] = target_beat
        result["expected_clip_end"] = target_beat + duration_beats
    return result

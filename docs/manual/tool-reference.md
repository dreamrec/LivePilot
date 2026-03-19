# Tool Reference

LivePilot gives you 127 tools that control every part of Ableton Live 12. You don't call these tools directly -- you describe what you want in plain language, and the AI picks the right tools behind the scenes. But knowing what's available helps you ask better questions and understand what's happening when the AI works on your session.

This chapter covers every tool, grouped by what it does. Each entry tells you the tool name, what it does in practice, what parameters it accepts, and when you'd want it.

> **Quick reference for common values:**
>
> - **Volume:** 0.0 (silence) to 1.0 (max). 0.85 is 0 dB -- Ableton's default fader position.
> - **Pan:** -1.0 (hard left) to 1.0 (hard right). 0.0 is center.
> - **Color:** 0 to 69. Ableton has a fixed palette of 70 colors.
> - **Tempo:** 20 to 999 BPM.
> - **Time values:** Always in beats. 1.0 = one quarter note, 4.0 = one bar in 4/4.
> - **Pitch:** MIDI numbers 0-127. 60 = Middle C (C3).
> - **Velocity:** 1-127. How hard the note is hit.
> - **Probability:** 0.0 to 1.0. A Live 12 feature -- notes can play randomly based on this value.
> - **Track index:** 0-based for regular tracks. Negative for return tracks (-1 = Return A, -2 = Return B). -1000 for master track.
> - **Scene/clip index:** Also 0-based. Scene 0 is the top row, clip 0 is the first slot.

---

## Transport

These tools control playback, tempo, time signature, looping, undo/redo, and session health checks. They're the foundation of every session.

### get_session_info

Returns a full snapshot of your session: tempo, time signature, track count, scene count, transport state (playing, recording, etc.), and more.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** Start here. Before making any changes, the AI reads session info to understand what you're working with. You can also ask "what's going on in my session?" to trigger this.

---

### set_tempo

Changes the song tempo.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tempo` | float | *(required)* | BPM value, 20 to 999 |

**When to use:** "Set the tempo to 128 BPM" or "slow it down to 90."

---

### set_time_signature

Changes the time signature for the whole song.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `numerator` | int | *(required)* | Top number (1-99) |
| `denominator` | int | *(required)* | Bottom number -- must be 1, 2, 4, 8, or 16 |

**When to use:** "Switch to 3/4 time" or "make it 6/8."

---

### start_playback

Starts playback from the beginning of the song.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** When you want to hear the session from the top.

---

### stop_playback

Stops playback entirely.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Stop" or "pause the session." Note: this stops playback completely. To resume from where you left off, use continue_playback.

---

### continue_playback

Resumes playback from the current playhead position, rather than jumping back to the start.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** When you want to pick up where you left off instead of restarting.

---

### toggle_metronome

Turns the click track on or off.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | *(required)* | `true` to turn on, `false` to turn off |

**When to use:** "Turn on the metronome" or "kill the click."

---

### set_session_loop

Enables or disables the global loop, and optionally sets the loop region.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | *(required)* | `true` to enable looping, `false` to disable |
| `start` | float | *(none)* | Loop start position in beats |
| `length` | float | *(none)* | Loop length in beats |

**When to use:** "Loop bars 5 through 8" or "turn off the loop." To loop bars 5-8 in 4/4, you'd set start to 16.0 and length to 16.0 (four bars of four beats each).

> **Tip:** Start and length are optional. If you just want to toggle the loop on/off without changing the region, only `enabled` is needed.

---

### undo

Undoes the last action in Ableton's undo history.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Undo that" or "go back." The AI can undo multiple steps if you ask.

---

### redo

Redoes the last undone action.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Redo" or "actually, put that back."

---

### get_recent_actions

Shows a log of recent commands that LivePilot has sent to Ableton, newest first.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Number of entries to return (1-50) |

**When to use:** "What did you just do?" or "show me the last 5 changes." Helpful for reviewing what the AI has done before deciding whether to undo.

---

### get_session_diagnostics

Scans your session for potential issues: tracks left armed, forgotten solos/mutes, unnamed tracks, empty clips, MIDI tracks without instruments, and other common problems.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Check my session for problems" or "anything look wrong?" Great to run before a mixdown or live performance.

---

## Tracks

Tools for creating, deleting, naming, coloring, and controlling tracks.

### get_track_info

Returns detailed info about a single track: its clips, devices, volume, pan, mute/solo/arm state, and routing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |

**When to use:** When the AI needs to inspect a specific track before making changes, or when you ask "what's on track 3?"

---

### create_midi_track

Creates a new empty MIDI track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `index` | int | -1 | Where to insert (-1 = end) |
| `name` | str | *(none)* | Track name |
| `color` | int | *(none)* | Color index (0-69) |

**When to use:** "Add a MIDI track for drums" or "create a new synth track." The AI will typically name and color it for you.

---

### create_audio_track

Creates a new empty audio track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `index` | int | -1 | Where to insert (-1 = end) |
| `name` | str | *(none)* | Track name |
| `color` | int | *(none)* | Color index (0-69) |

**When to use:** "Add an audio track for vocals" or "I need a track for recording guitar."

---

### create_return_track

Creates a new return track (for sends/effects buses).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Add a reverb bus" or "I need a new return track." The AI will typically load an effect onto it after creating it.

---

### delete_track

Removes a track from the session.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |

**When to use:** "Delete track 3" or "remove the bass track." You can undo this if it was a mistake.

---

### duplicate_track

Creates a full copy of a track, including all its clips, devices, and settings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track to duplicate (0-based) |

**When to use:** "Duplicate the synth track" or "make a copy of track 2 so I can try a different approach."

---

### set_track_name

Renames a track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `name` | str | *(required)* | New name |

**When to use:** "Rename track 0 to Kick" or "call the third track Lead Synth."

---

### set_track_color

Changes a track's color.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `color_index` | int | *(required)* | Color (0-69 from Ableton's palette) |

**When to use:** "Make the drums track red" or "color-code my tracks." The AI maps color names to Ableton's 70-color palette.

---

### set_track_mute

Mutes or unmutes a track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `muted` | bool | *(required)* | `true` to mute, `false` to unmute |

**When to use:** "Mute the bass" or "unmute track 4."

---

### set_track_solo

Solos or unsolos a track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `soloed` | bool | *(required)* | `true` to solo, `false` to unsolo |

**When to use:** "Solo the vocals" or "unsolo everything." Be careful with solo -- it's easy to forget and wonder why your mix sounds thin.

---

### set_track_arm

Arms or disarms a track for recording.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `armed` | bool | *(required)* | `true` to arm, `false` to disarm |

**When to use:** "Arm track 2 for recording" or "disarm all tracks."

---

### stop_track_clips

Stops all playing clips on a specific track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |

**When to use:** "Stop the clips on the drum track" or when you want to silence one track without stopping the whole session.

---

### set_group_fold

Folds or unfolds a group track to show or hide its child tracks.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) — must be a group track |
| `folded` | bool | *(required)* | `true` to fold (collapse), `false` to unfold (expand) |

**When to use:** "Collapse the drums group" or "unfold the synths folder." Only works on group tracks (`is_foldable` must be true).

---

### set_track_input_monitoring

Controls input monitoring for a track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `state` | int | *(required)* | 0=In (always monitor), 1=Auto (monitor when armed), 2=Off |

**When to use:** "Set monitoring to auto on the vocal track" or "turn off input monitoring." Essential for recording workflows — Auto is the most common choice.

**Monitoring modes explained:**
- **0 = In**: Always hear the input, regardless of arm state
- **1 = Auto**: Hear input only when the track is armed (most common)
- **2 = Off**: Never hear the input — only play back recorded material

---

## Clips

Tools for working with clip slots in Session View. Clips are the colored rectangles that hold your musical patterns.

### get_clip_info

Returns details about a clip: name, length, loop settings, launch mode, color, and whether it's playing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based, top = 0) |

**When to use:** When the AI needs to inspect a clip before editing it, or when you ask "what's in that clip?"

---

### create_clip

Creates a new empty MIDI clip in a clip slot.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `length` | float | *(required)* | Clip length in beats (4.0 = one bar in 4/4) |

**When to use:** The AI uses this as the first step when building patterns. "Create a 4-bar drum pattern" starts by creating a 16-beat clip.

> **Tip:** The clip must be on a MIDI track. You can't create MIDI clips on audio tracks.

---

### delete_clip

Removes a clip from a slot, deleting all its notes and automation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |

**When to use:** "Delete that clip" or "clear slot 2 on the bass track." Reversible with undo.

---

### duplicate_clip

Copies a clip from one slot to another. The target slot must be empty.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Source track (0-based) |
| `clip_index` | int | *(required)* | Source clip slot (0-based) |
| `target_track` | int | *(required)* | Destination track (0-based) |
| `target_clip` | int | *(required)* | Destination clip slot (0-based) |

**When to use:** "Copy the kick pattern to the next slot" or "duplicate this clip to scene 4."

---

### fire_clip

Launches a clip (starts it playing).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |

**When to use:** "Play the bass clip" or "fire scene 2's clip on track 0."

---

### stop_clip

Stops a playing clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |

**When to use:** "Stop that clip."

---

### set_clip_name

Renames a clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `name` | str | *(required)* | New clip name |

**When to use:** "Name this clip Verse 1" or "label the clips."

---

### set_clip_color

Changes a clip's color.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `color_index` | int | *(required)* | Color (0-69 from Ableton's palette) |

**When to use:** "Make the chorus clips blue."

---

### set_clip_loop

Enables or disables clip looping and optionally adjusts the loop region.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `enabled` | bool | *(required)* | `true` to loop, `false` for one-shot |
| `start` | float | *(none)* | Loop start in beats |
| `end` | float | *(none)* | Loop end in beats |

**When to use:** "Loop the first 2 bars of this clip" or "turn off looping on the intro clip."

> **Tip:** Start and end define the loop region within the clip. If you have a 16-beat clip but only want the first 8 beats to loop, set start=0.0 and end=8.0.

---

### set_clip_launch

Controls how a clip responds when you trigger it.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `mode` | int | *(required)* | Launch mode: 0=Trigger, 1=Gate, 2=Toggle, 3=Repeat |
| `quantization` | int | *(none)* | Launch quantization override |

**When to use:** Mostly for live performance setups. "Set this clip to gate mode" (plays only while you hold the button) or "make it a toggle."

**Launch modes explained:**
- **0 = Trigger** (default): Click to start, click again to relaunch
- **1 = Gate**: Plays only while held down
- **2 = Toggle**: Click to start, click to stop
- **3 = Repeat**: Retriggers on every quantization interval while held

---

### set_clip_warp_mode

Sets the warp mode for an audio clip. Only works on audio clips — MIDI clips don't have warp modes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `mode` | int | *(required)* | Warp mode (see below) |
| `warping` | bool | *(none)* | Optionally enable/disable warping itself |

**When to use:** "Set this clip to Complex Pro warp mode" or "use Re-Pitch for the vocal." Different modes suit different material.

**Warp modes explained:**
- **0 = Beats**: Best for rhythmic material (drums, percussion)
- **1 = Tones**: Good for monophonic instruments and vocals
- **2 = Texture**: For pads, ambient textures, and complex material
- **3 = Re-Pitch**: Changes speed like a turntable — changes pitch with tempo
- **4 = Complex**: General-purpose for full mixes and complex signals
- **6 = Complex Pro**: Highest quality, most CPU-intensive — best for final stems

> **Note:** Mode 5 is intentionally skipped — Ableton's internal numbering jumps from 4 to 6.

---

## Notes

Tools for writing and editing MIDI notes inside clips. This is where melodies, chords, drum patterns, and basslines get built.

### add_notes

Writes MIDI notes into a clip. This is the core tool for creating music.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `notes` | list | *(required)* | Array of note objects (see below) |

Each note object:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pitch` | int | *(required)* | MIDI note number (0-127, 60 = Middle C) |
| `start_time` | float | *(required)* | Position in beats from clip start |
| `duration` | float | *(required)* | Length in beats |
| `velocity` | float | 100 | How hard the note is hit (1-127) |
| `probability` | float | *(none)* | Chance the note plays (0.0-1.0, Live 12 feature) |
| `velocity_deviation` | float | *(none)* | Velocity randomization range (-127 to 127) |
| `release_velocity` | float | *(none)* | Note-off velocity (0-127) |

**When to use:** This is how the AI writes music. "Write a C minor chord at beat 1" or "make a four-on-the-floor kick pattern."

> **Tip:** Common MIDI note numbers -- C3=60, D3=62, E3=64, F3=65, G3=67, A3=69, B3=71. For drums on channel 10: Kick=36, Snare=38, Closed HH=42, Open HH=46, Crash=49, Ride=51.

---

### get_notes

Reads MIDI notes from a clip, optionally filtering by pitch range and time range.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `from_pitch` | int | 0 | Lowest pitch to include |
| `pitch_span` | int | 128 | Number of pitches to include |
| `from_time` | float | 0.0 | Start time in beats |
| `time_span` | float | *(none)* | Duration to query in beats (default: entire clip) |

**When to use:** "What notes are in this clip?" or "show me the bass notes." The AI reads notes before editing them, so it knows what's already there.

> **Tip:** Each returned note includes a `note_id` that you can use with modify_notes, remove_notes_by_id, and other editing tools.

---

### remove_notes

Removes all MIDI notes in a pitch/time region. With default parameters, this removes every note in the clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `from_pitch` | int | 0 | Lowest pitch in the region |
| `pitch_span` | int | 128 | Number of pitches in the region |
| `from_time` | float | 0.0 | Start time in beats |
| `time_span` | float | *(none)* | Duration in beats (default: entire clip) |

**When to use:** "Clear all the notes" or "remove the notes in bar 3." Reversible with undo.

---

### remove_notes_by_id

Removes specific notes using their IDs (returned by get_notes).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `note_ids` | list | *(required)* | Array of note IDs to remove |

**When to use:** When you want to surgically remove specific notes without affecting their neighbors. "Delete just the snare hits on beats 2 and 4."

---

### modify_notes

Changes properties of existing notes by their IDs. You can move them, retune them, change velocity -- anything except add or delete.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `modifications` | list | *(required)* | Array of modification objects |

Each modification object:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `note_id` | int | *(required)* | ID of the note to modify |
| `pitch` | int | *(unchanged)* | New MIDI pitch (0-127) |
| `start_time` | float | *(unchanged)* | New position in beats |
| `duration` | float | *(unchanged)* | New length in beats |
| `velocity` | float | *(unchanged)* | New velocity (0-127) |
| `probability` | float | *(unchanged)* | New probability (0.0-1.0) |

**When to use:** "Make the hi-hats quieter" or "move that note to beat 3." The AI reads the notes first, then modifies only what needs to change.

---

### duplicate_notes

Copies specific notes (by ID) within the same clip, with an optional time shift.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `note_ids` | list | *(required)* | Array of note IDs to duplicate |
| `time_offset` | float | 0.0 | How far to shift the copies (in beats) |

**When to use:** "Repeat that pattern 4 beats later" or "double the melody an octave up" (duplicate + transpose).

---

### transpose_notes

Shifts all notes in a time range up or down by a number of semitones.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot/arrangement clip index (0-based) |
| `semitones` | int | *(required)* | Semitones to shift (-127 to 127, positive = up) |
| `from_time` | float | 0.0 | Start of the range in beats |
| `time_span` | float | *(none)* | Length of the range in beats (default: entire clip) |
| `arrangement` | bool | false | Set to true to target an arrangement clip |

**When to use:** "Transpose the melody up a fifth" (semitones=7) or "drop the bass an octave" (semitones=-12).

> **Tip:** Common intervals in semitones -- minor 3rd=3, major 3rd=4, perfect 5th=7, octave=12.

---

### quantize_clip

Snaps notes to a rhythmic grid. You can quantize fully or partially to keep some human feel.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot number (0-based) |
| `grid` | int | *(required)* | Grid size (see below) |
| `amount` | float | 1.0 | Quantize strength (0.0 = no change, 1.0 = fully on grid) |

**Grid values:**
| Value | Grid |
|-------|------|
| 0 | None |
| 1 | 1/4 note |
| 2 | 1/8 note |
| 3 | 1/8 note triplet |
| 4 | 1/8 note + triplet |
| 5 | 1/16 note |
| 6 | 1/16 note triplet |
| 7 | 1/16 note + triplet |
| 8 | 1/32 note |

**When to use:** "Quantize the drums to 1/16" (grid=5) or "quantize the keys at 50%" (amount=0.5) to tighten timing while keeping some groove.

---

## Devices

Tools for working with instruments and effects on tracks. This covers everything from loading a synth to tweaking reverb parameters.

### get_device_info

Returns info about a device: its name, type (instrument, audio_effect, midi_effect), whether it's active, and how many parameters it has.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in the chain (0-based) |

**When to use:** "What's the first device on the bass track?"

---

### get_device_parameters

Lists every parameter on a device with its current value, min, max, and name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in the chain (0-based) |

**When to use:** The AI reads parameters before changing them to understand what's available. "What are the reverb settings?" triggers this.

---

### set_device_parameter

Changes a single parameter on a device. You can target by name or by index.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in the chain (0-based) |
| `value` | float | *(required)* | New parameter value |
| `parameter_name` | str | *(none)* | Parameter name (e.g., "Decay Time") |
| `parameter_index` | int | *(none)* | Parameter index (0-based) |

**When to use:** "Turn up the reverb decay" or "set the filter cutoff to 80%." You must provide either `parameter_name` or `parameter_index` (or both).

> **Tip:** Parameter values use the device's native range. The AI reads get_device_parameters first to know the correct min/max.

---

### batch_set_parameters

Changes multiple parameters on a device in a single call. Faster and more atomic than calling set_device_parameter repeatedly.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in the chain (0-based) |
| `parameters` | list | *(required)* | Array of `{name_or_index, value}` objects |

**When to use:** When the AI needs to set up a device with many parameters at once -- for example, dialing in a compressor with attack, release, threshold, and ratio all at once.

---

### toggle_device

Turns a device on or off (like clicking the device power button).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in the chain (0-based) |
| `active` | bool | *(required)* | `true` to enable, `false` to bypass |

**When to use:** "Bypass the compressor" or "turn the EQ back on."

---

### delete_device

Removes a device from a track's chain.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in the chain (0-based) |

**When to use:** "Remove the limiter" or "strip the effects off this track." Reversible with undo.

---

### load_device_by_uri

Loads a device onto a track using its browser URI. This is the precise way to load a specific preset or device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `uri` | str | *(required)* | Browser URI string |

**When to use:** The AI typically gets the URI from search_browser or get_device_presets first, then uses this to load it. You won't normally need to specify URIs yourself.

---

### find_and_load_device

Searches the browser for a device by name and loads the first match onto a track. A convenient shortcut when you know the device name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_name` | str | *(required)* | Device name to search for (e.g., "Wavetable", "Compressor") |

**When to use:** "Add a compressor to the drum bus" or "put Wavetable on this track."

---

### get_rack_chains

Lists all chains in a rack device (Instrument Rack, Audio Effect Rack, etc.) with their volume, pan, mute, and solo states.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Rack device position in the chain (0-based) |

**When to use:** "What chains are in this instrument rack?" or when the AI needs to understand a layered instrument before adjusting it.

---

### set_simpler_playback_mode

Switches Simpler between its three playback modes, and configures slicing options.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Simpler device position (0-based) |
| `playback_mode` | int | *(required)* | 0=Classic, 1=One-Shot, 2=Slice |
| `slice_by` | int | *(none)* | Slice mode: 0=Transient, 1=Beat, 2=Region, 3=Manual |
| `sensitivity` | float | *(none)* | Transient detection sensitivity (0.0-1.0, only for slice_by=0) |

**When to use:** "Switch Simpler to slice mode" or "set it to one-shot for the drum hit."

**Playback modes explained:**
- **0 = Classic**: Standard sampler behavior with pitch tracking
- **1 = One-Shot**: Plays the whole sample once, ignoring note-off (good for drums)
- **2 = Slice**: Chops the sample into slices mapped across the keyboard

---

### set_chain_volume

Sets the volume and/or pan for a specific chain inside a rack.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Rack device position (0-based) |
| `chain_index` | int | *(required)* | Chain number inside the rack (0-based) |
| `volume` | float | *(none)* | Volume (0.0-1.0) |
| `pan` | float | *(none)* | Pan (-1.0 to 1.0) |

**When to use:** "Turn down the second chain in the instrument rack" or "pan chain 1 to the left." You must provide at least one of volume or pan.

---

### get_device_presets

Lists all available presets for a built-in Ableton device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_name` | str | *(required)* | Device name (e.g., "Corpus", "Drum Buss", "Wavetable") |

**When to use:** "What Wavetable presets are available?" or when the AI wants to load a specific preset rather than building from scratch. Returns preset names and URIs.

---

## Scenes

Tools for managing scenes -- the horizontal rows of clip slots in Session View.

### get_scenes_info

Returns info about all scenes: names, tempo markers, and colors.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "How many scenes do I have?" or "list the scenes."

---

### create_scene

Creates a new empty scene.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `index` | int | -1 | Where to insert (-1 = end) |

**When to use:** "Add a new scene" or "I need another section."

---

### delete_scene

Removes a scene and all its clip slots.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scene_index` | int | *(required)* | Scene number (0-based, top = 0) |

**When to use:** "Delete the last scene." Reversible with undo.

---

### duplicate_scene

Creates a copy of a scene, duplicating all clips in every slot.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scene_index` | int | *(required)* | Scene to duplicate (0-based) |

**When to use:** "Duplicate the chorus scene so I can make a variation."

---

### fire_scene

Launches an entire scene, firing all clips in that row simultaneously.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scene_index` | int | *(required)* | Scene number (0-based) |

**When to use:** "Play the chorus" (if the AI knows which scene is the chorus) or "fire scene 3."

---

### set_scene_name

Renames a scene.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scene_index` | int | *(required)* | Scene number (0-based) |
| `name` | str | *(required)* | New scene name |

**When to use:** "Name this scene Intro" or "label all the scenes."

---

### set_scene_color

Sets the color of a scene using Ableton's 70-color palette.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scene_index` | int | *(required)* | Scene number (0-based) |
| `color_index` | int | *(required)* | Color index (0-69) |

**When to use:** "Color the intro scene blue" or "give each section a different color." Great for visual organization of song sections.

---

### set_scene_tempo

Assigns a tempo to a scene. When the scene is launched, Ableton automatically switches to this tempo.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scene_index` | int | *(required)* | Scene number (0-based) |
| `tempo` | float | *(required)* | BPM value (20-999) |

**When to use:** "Set the breakdown scene to 110 BPM" or "make the chorus faster at 140." This is the proper way to create tempo changes between sections — more reliable than embedding tempo in the scene name.

> **Tip:** Set tempo to 0 to clear a scene's tempo override, returning to the global song tempo.

---

## Mixing

Tools for setting levels, panning, sends, and routing. This is your virtual mixing console.

### set_track_volume

Sets a track's fader level.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `volume` | float | *(required)* | Volume level (0.0-1.0) |

**When to use:** "Turn the kick up" or "set the bass to -6 dB."

> **Important:** Volume 0.85 = 0 dB. This is Ableton's default fader position. Values above 0.85 add gain. Common reference points: 0.0 = silence (negative infinity dB), 0.85 = 0 dB, 1.0 = +6 dB.

---

### set_track_pan

Sets a track's stereo panning.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `pan` | float | *(required)* | Pan position (-1.0 = hard left, 0.0 = center, 1.0 = hard right) |

**When to use:** "Pan the hi-hats slightly right" or "center the bass."

---

### set_track_send

Sets how much signal a track sends to a return track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `send_index` | int | *(required)* | Send number (0 = Send A, 1 = Send B, etc.) |
| `value` | float | *(required)* | Send level (0.0-1.0) |

**When to use:** "Send the vocals to the reverb bus" or "turn up Send A on the snare."

---

### get_return_tracks

Lists all return tracks with their names, volumes, and panning.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "What return tracks do I have?" or before setting up sends.

---

### get_master_track

Returns info about the master track: volume, pan, and devices.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "What's on the master?" or "what's the master volume at?"

---

### set_master_volume

Sets the master track's volume.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `volume` | float | *(required)* | Volume level (0.0-1.0) |

**When to use:** "Turn down the master" or "set the master to 0 dB" (volume=0.85).

---

### get_track_routing

Shows a track's input and output routing configuration.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |

**When to use:** "Where is this track routing to?" or when debugging signal flow.

---

### set_track_routing

Configures a track's input and/or output routing by display name. You can set any combination of input type, input channel, output type, and output channel.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `input_type` | str | *(none)* | Input routing type (display name) |
| `input_channel` | str | *(none)* | Input routing channel (display name) |
| `output_type` | str | *(none)* | Output routing type (display name) |
| `output_channel` | str | *(none)* | Output routing channel (display name) |

**When to use:** "Route this track to the reverb return" or "set the input to my audio interface." At least one routing parameter must be provided.

> **Tip:** Use get_track_routing first to see the current routing and available options. The display names must match exactly what Ableton shows.

---

### get_track_meters

Returns real-time output levels (left/right peak) for a track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |

**When to use:** "Is this track producing sound?" or verifying levels after loading instruments.

---

### get_master_meters

Returns real-time output levels (left/right peak) for the master track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | — | — | — |

**When to use:** "How loud is the output?" or checking for clipping.

---

### get_mix_snapshot

Returns a complete overview of all tracks' levels, panning, routing, mute/solo state, and send levels in one call.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | — | — | — |

**When to use:** "Show me the current mix" or before making mixing decisions. Much faster than calling get_track_info on every track.

---

## Browser

Tools for finding and loading instruments, effects, samples, and presets from Ableton's browser.

### get_browser_tree

Returns an overview of the browser's top-level categories and their children.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category_type` | str | "all" | Category filter (e.g., "all", "instruments", "audio_effects") |

**When to use:** When the AI needs to understand what's available in the browser. Typically the first step before loading something.

---

### get_browser_items

Lists items at a specific browser path.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | str | *(required)* | Browser path (e.g., "instruments/Analog") |

**When to use:** "What instruments are available?" or "show me the drum rack presets."

---

### search_browser

Searches the browser tree under a given path, optionally filtering by name. This is the most flexible way to find things.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | str | *(required)* | Where to search (e.g., "instruments", "audio_effects") |
| `name_filter` | str | *(none)* | Text to match against item names |
| `loadable_only` | bool | false | If true, only return items that can be loaded |
| `max_depth` | int | 8 | How deep to recurse into subfolders |
| `max_results` | int | 100 | Maximum results to return |

**When to use:** "Find me a pluck preset" or "search for reverb effects." The AI uses this behind the scenes whenever you ask for a specific sound.

---

### load_browser_item

Loads a browser item (instrument, effect, or preset) onto a track using its URI.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `uri` | str | *(required)* | Browser item URI (from search_browser or get_browser_items) |

**When to use:** The final step after finding something in the browser. The AI handles the URI -- you just say what you want.

---

## Arrangement

Tools for working in Arrangement View: placing clips on the timeline, editing arrangement notes, recording, automation, cue points, and navigation.

### get_arrangement_clips

Lists all clips on a track's arrangement timeline.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |

**When to use:** "What's on the arrangement for track 2?" or when the AI needs to see what's already laid out.

---

### create_arrangement_clip

Places a clip on the arrangement timeline by duplicating a session clip to a specific position.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_slot_index` | int | *(required)* | Source session clip slot (0-based) |
| `start_time` | float | *(required)* | Beat position on the timeline (0.0 = song start) |
| `length` | float | *(required)* | Total clip length in beats |
| `loop_length` | float | *(none)* | Pattern length to loop within the clip |
| `name` | str | "" | Display name for the arrangement clip |
| `color_index` | int | *(none)* | Color (0-69) |

**When to use:** "Put the verse pattern at bar 1 for 16 bars." This is how the AI builds arrangement structure from session clips.

> **Tip:** If `length` is longer than the source clip, the pattern tiles (repeats) automatically. Use `loop_length` to control the repeating pattern size independently of the source.

---

### add_arrangement_notes

Writes MIDI notes directly into an arrangement clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (from get_arrangement_clips) |
| `notes` | list | *(required)* | Array of note objects: {pitch, start_time, duration, velocity, mute} |

**When to use:** When writing notes directly into the arrangement instead of session clips. Note that `start_time` is relative to the clip's start, not the song timeline.

---

### get_arrangement_notes

Reads MIDI notes from an arrangement clip, with optional pitch and time filtering.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `from_pitch` | int | 0 | Lowest pitch to include |
| `pitch_span` | int | 128 | Number of pitches to include |
| `from_time` | float | 0.0 | Start time in beats (relative to clip start) |
| `time_span` | float | *(none)* | Duration in beats (default: full clip) |

**When to use:** "Show me the notes in the first arrangement clip on track 0."

---

### remove_arrangement_notes

Removes MIDI notes in a pitch/time region of an arrangement clip. With defaults, clears all notes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `from_pitch` | int | 0 | Lowest pitch in the region |
| `pitch_span` | int | 128 | Number of pitches in the region |
| `from_time` | float | 0.0 | Start time in beats (relative to clip start) |
| `time_span` | float | *(none)* | Duration in beats (default: full clip) |

**When to use:** "Clear the notes in the second half of this arrangement clip."

---

### remove_arrangement_notes_by_id

Removes specific notes from an arrangement clip by their IDs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `note_ids` | list | *(required)* | Array of note IDs to remove |

**When to use:** Surgical removal of individual notes in the arrangement.

---

### modify_arrangement_notes

Changes properties of existing notes in an arrangement clip by their IDs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `modifications` | list | *(required)* | Array of {note_id, pitch?, start_time?, duration?, velocity?, probability?} |

**When to use:** "Change the velocity of those arrangement notes" or "move the melody notes in the arrangement."

---

### duplicate_arrangement_notes

Copies specific notes within an arrangement clip, with an optional time shift.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `note_ids` | list | *(required)* | Array of note IDs to duplicate |
| `time_offset` | float | 0.0 | How far to shift the copies (in beats) |

**When to use:** "Repeat that pattern later in the arrangement clip."

---

### transpose_arrangement_notes

Shifts notes in an arrangement clip up or down by semitones.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `semitones` | int | *(required)* | Semitones to shift (-127 to 127) |
| `from_time` | float | 0.0 | Start of range in beats (relative to clip start) |
| `time_span` | float | *(none)* | Length of range in beats (default: full clip) |

**When to use:** "Transpose the arrangement clip up a minor third."

---

### set_arrangement_clip_name

Renames an arrangement clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `name` | str | *(required)* | New name |

**When to use:** "Name the arrangement clips by section."

---

### set_arrangement_automation

Writes automation envelope points into an arrangement clip. This is how you automate device parameters, volume, panning, and sends over time in the arrangement.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Arrangement clip index (0-based) |
| `parameter_type` | str | *(required)* | What to automate: "device", "volume", "panning", or "send" |
| `points` | list | *(required)* | Array of {time, value, duration?} objects |
| `device_index` | int | *(none)* | Required when parameter_type="device" |
| `parameter_index` | int | *(none)* | Required when parameter_type="device" |
| `send_index` | int | *(none)* | Required when parameter_type="send" (0=A, 1=B, ...) |

Automation point object:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `time` | float | *(required)* | Position in beats (relative to clip start, 0.0 = first beat) |
| `value` | float | *(required)* | Parameter value (native range -- check get_device_parameters) |
| `duration` | float | 0.125 | Hold duration in beats before transitioning |

**When to use:** "Automate a filter sweep over 8 bars" or "fade the volume in over the intro."

> **Tip:** For smooth automation curves, use many closely spaced points. For step automation (instant jumps), the default duration of 0.125 beats works well.

**parameter_type options:**
- `"device"` -- automate a device parameter (requires device_index + parameter_index)
- `"volume"` -- automate track volume
- `"panning"` -- automate track pan
- `"send"` -- automate a send level (requires send_index)

---

### back_to_arranger

Switches playback from session clips back to the arrangement timeline. In Ableton, launching session clips overrides the arrangement until you press the "Back to Arrangement" button -- this tool does that.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Go back to the arrangement" or when clips are playing from session view and you want the arrangement to take over.

---

### jump_to_time

Moves the playhead to a specific beat position in the arrangement.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `beat_time` | float | *(required)* | Beat position to jump to (0.0 = start) |

**When to use:** "Jump to bar 17" (beat_time=64.0 in 4/4) or "go to the chorus."

---

### capture_midi

Captures recently played MIDI notes (from your controller or keyboard) into a new clip, even if you weren't recording. This is Ableton's "Capture MIDI" feature.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Capture what I just played" -- useful when you were jamming and realized you liked it.

---

### start_recording

Begins recording into session clips or the arrangement.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arrangement` | bool | false | `true` for arrangement recording, `false` for session recording |

**When to use:** "Start recording" or "record into the arrangement."

> **Tip:** Make sure the right tracks are armed before recording. The AI will typically check this for you.

---

### stop_recording

Stops all recording (both session and arrangement).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Stop recording."

---

### get_cue_points

Lists all cue points (locators) in the arrangement with their names and positions.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "What cue points do I have?" or "show me the arrangement markers."

---

### jump_to_cue

Jumps the playhead to a cue point by its index.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cue_index` | int | *(required)* | Cue point number (0-based) |

**When to use:** "Jump to the chorus marker" or "go to cue point 3."

---

### toggle_cue_point

Creates or deletes a cue point at the current playhead position. If there's already a cue point at the current position, it's removed; otherwise, a new one is created.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | | | |

**When to use:** "Drop a marker here" or "remove this cue point."

---

## Memory

Tools for saving, searching, and replaying production techniques. The memory system lets you build a persistent library of beats, device chains, mixing setups, and production preferences — each annotated with a rich stylistic analysis the agent writes at save time. See the README's "Train Your Own AI Producer" section for how this shapes the agent over time.

### memory_learn

Saves a new technique to your library with stylistic qualities and raw payload data.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | *(required)* | Human-readable name for the technique |
| `type` | str | *(required)* | Technique type: "beat_pattern", "device_chain", "mix_template", "preference", or "browser_pin" |
| `qualities` | dict | *(required)* | Stylistic analysis with `summary`, `mood`, `genre_tags`, and type-specific fields |
| `payload` | dict | *(required)* | Raw data (MIDI notes, device params, etc.) |
| `tags` | list | [] | Searchable tags for categorization |

**When to use:** When you say "save this beat" or "remember this reverb chain." The AI collects the raw data from Ableton, writes a stylistic analysis, and stores both.

---

### memory_recall

Searches your technique library by text query, type, and tags. Returns summaries (not full payloads) ranked by favorites, rating, replay count, and recency.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | "" | Text to search across names, tags, and qualities |
| `type` | str | *(none)* | Filter by technique type |
| `tags` | list | *(none)* | Filter by tags |
| `limit` | int | 20 | Maximum results to return |

**When to use:** The AI calls this before creative decisions (in Informed mode) to understand your taste. Also used when you say "find my dark moody beats" or "what reverb chains have I saved?"

---

### memory_get

Fetches a full technique by ID, including the complete payload for replay.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `technique_id` | str | *(required)* | UUID of the technique |

**When to use:** After finding a technique via recall, the AI uses this to get the full data before replaying it.

---

### memory_replay

Returns a technique with a structured replay plan the agent can execute using existing Ableton tools.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `technique_id` | str | *(required)* | UUID of the technique |
| `adapt` | bool | false | `false` for exact replay, `true` for agent to use it as inspiration |

**When to use:** "Use that boom bap beat I saved" (adapt=false) or "make something inspired by my saved lo-fi chain" (adapt=true). The replay plan tells the AI which tools to call and in what order — it doesn't execute them directly.

---

### memory_list

Browses your technique library with filtering and sorting.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | *(none)* | Filter by technique type |
| `tags` | list | *(none)* | Filter by tags |
| `sort_by` | str | "updated_at" | Sort by: "updated_at", "name", "rating", "replay_count", "created_at" |
| `limit` | int | 50 | Maximum results |

**When to use:** "Show me all my saved beats" or "what's in my technique library?"

---

### memory_favorite

Stars and/or rates a technique. Favorites and higher-rated techniques sort to the top in search results.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `technique_id` | str | *(required)* | UUID of the technique |
| `favorite` | bool | *(none)* | Set favorite status |
| `rating` | int | *(none)* | Rating from 0-5 |

**When to use:** "Favorite that beat" or "rate my reverb chain 5 stars."

---

### memory_update

Updates the name, tags, or qualities of an existing technique without changing its payload.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `technique_id` | str | *(required)* | UUID of the technique |
| `name` | str | *(none)* | New name |
| `tags` | list | *(none)* | New tags (replaces existing) |
| `qualities` | dict | *(none)* | Updated qualities (merged with existing) |

**When to use:** "Rename that beat to Dusty Groove" or "add the tag hip-hop to my saved kit."

---

### memory_delete

Removes a technique from the library. Creates a backup file first for safety.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `technique_id` | str | *(required)* | UUID of the technique to delete |

**When to use:** "Delete that old beat pattern." Reversible by restoring from backup.

---

## Analyzer

These 20 tools require the LivePilot Analyzer Max for Live device on the master track. They provide real-time DSP analysis, deep device introspection, sample manipulation, and warp marker control. All other tools work without the device.

### get_master_spectrum

Returns 8-band spectral analysis of the master output (sub, low, low-mid, mid, high-mid, high, presence, air).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | — | — | Reads from the spectral cache |

**When to use:** "Check the frequency balance" or "is there too much sub bass?"

---

### get_master_rms

Returns true RMS and peak amplitude levels of the master output.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | — | — | Reads from the spectral cache |

**When to use:** "How loud is the master?" or "check the peak levels."

---

### get_detected_key

Detects the musical key of the current audio using Krumhansl-Schmuckler algorithm.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| *(none)* | — | — | Analyzes pitch data from the spectral cache |

**When to use:** "What key is this in?" or before writing harmonies/bass to match the existing material.

---

### get_hidden_parameters

Returns all device parameters including hidden ones not shown in Ableton's GUI, with display strings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in chain (0-based) |

**When to use:** "Show me all the hidden parameters on this synth."

---

### get_automation_state

Returns only parameters that have automation (active or overridden) on a device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in chain (0-based) |

**When to use:** "Which parameters are automated?" or before overwriting a parameter that might have automation.

---

### walk_device_tree

Recursively walks the device tree including racks, drum pads, and nested devices (up to 6 levels deep).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in chain (0-based) |

**When to use:** "Show me everything inside this rack" or inspecting complex instrument setups.

---

### get_clip_file_path

Returns the audio file path on disk for a clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |

**When to use:** "Where is this audio file?" or before loading a sample into Simpler.

---

### replace_simpler_sample

Replaces the loaded sample in a Simpler device with a different audio file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Simpler device position (0-based) |
| `file_path` | str | *(required)* | Path to the new audio file |

**When to use:** "Load this sample into the Simpler." Requires an existing sample in the Simpler.

---

### load_sample_to_simpler

Full workflow tool: bootstraps a Simpler via the browser if needed, then replaces the sample. Works even when no Simpler exists on the track.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `file_path` | str | *(required)* | Path to the audio file to load |

**When to use:** "Put this sample in a Simpler" — handles the full setup automatically.

---

### get_simpler_slices

Returns all auto-detected slice points from a Simpler in Slice mode.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Simpler device position (0-based) |

**When to use:** "Show me the slice points" or before programming MIDI to trigger slices.

---

### crop_simpler

Crops the sample in a Simpler to the active region.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Simpler device position (0-based) |

**When to use:** "Crop this sample" to trim to the selected region.

---

### reverse_simpler

Reverses the sample loaded in a Simpler.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Simpler device position (0-based) |

**When to use:** "Reverse this sample" for creative effects.

---

### warp_simpler

Warps the sample in a Simpler to fit a specified number of beats.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Simpler device position (0-based) |
| `beats` | float | *(required)* | Target beat count |

**When to use:** "Warp this sample to 4 beats" to time-stretch to tempo.

---

### get_warp_markers

Returns all warp markers from an audio clip (beat_time and sample_time pairs).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |

**When to use:** "Show me the warp markers" to inspect timing.

---

### add_warp_marker

Adds a warp marker to an audio clip at a specific beat position.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |
| `beat_time` | float | *(required)* | Beat position for the marker |

**When to use:** "Pin the downbeat" or before stretching specific sections.

---

### move_warp_marker

Moves an existing warp marker to a new beat position.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |
| `old_beat` | float | *(required)* | Current beat position |
| `new_beat` | float | *(required)* | New beat position |

**When to use:** "Stretch this section" or "fix the timing on beat 3."

---

### remove_warp_marker

Removes a warp marker from an audio clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |
| `beat_time` | float | *(required)* | Beat position of the marker to remove |

**When to use:** "Remove that warp marker" to clean up timing edits.

---

### scrub_clip

Previews audio at a specific position in a clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |
| `beat_time` | float | *(required)* | Beat position to preview |

**When to use:** "Play from beat 8" to audition specific positions.

---

### stop_scrub

Stops a clip preview started by scrub_clip.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `clip_index` | int | *(required)* | Clip slot (0-based) |

**When to use:** After previewing, stop the scrub playback.

---

### get_display_values

Returns human-readable display strings for all device parameters (e.g., "440 Hz", "-6 dB", "Saw").

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | int | *(required)* | Track number (0-based) |
| `device_index` | int | *(required)* | Device position in chain (0-based) |

**When to use:** "What are the actual values?" to see parameters in the same format as Ableton's GUI.

---

Next: [Workflows](workflows.md) | Back to [Manual](index.md)

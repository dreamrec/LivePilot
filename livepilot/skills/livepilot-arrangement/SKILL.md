---
name: livepilot-arrangement
description: Constructive arrangement — actually building song structure in Ableton. Use when the user asks to "arrange", "structure a song", "add an intro", "build a verse", "create sections", "scene to arrangement", "record to arrangement", or wants to place clips on the timeline or organize scenes. For analysis of existing structure ("improve transitions", "detect motifs", "analyze composition"), use livepilot-composition-engine instead.
---

# Arrangement — Song Structure and Session Organization

Organize clips into scenes, build arrangements on the timeline, navigate with cue points, and record performances in Ableton Live.

## Session View vs Arrangement View

Ableton has two complementary views:

- **Session view** — a grid of clip slots organized by track (columns) and scene (rows). Clips loop independently. Fire scenes to trigger rows of clips simultaneously. Use for jamming, live performance, and building ideas.
- **Arrangement view** — a linear timeline where clips play in sequence from left to right. Use for final song structure, recording automation, and export.

Use `back_to_arranger` to switch from session playback to arrangement playback. When session clips are playing, they override arrangement content on their tracks.

## Scene Workflow

Scenes are horizontal rows in session view. Each scene can trigger all its clips at once.

### Creating and Managing Scenes

- `create_scene(index)` — insert a new scene at the given position
- `set_scene_name(scene_index, name)` — name scenes after song sections: "Intro", "Verse 1", "Chorus", "Bridge", "Drop", "Outro"
- `set_scene_color(scene_index, color_index)` — color-code sections (0-69 palette). Use consistent colors: green for verses, red for choruses, blue for bridges.
- `set_scene_tempo(scene_index, tempo)` — set a per-scene tempo change (triggers when scene fires)
- `duplicate_scene(scene_index)` — copy a scene for variations. Duplicate, rename, then modify clips in the copy.
- `delete_scene(scene_index)` — remove a scene

### Firing and Monitoring

- `fire_scene(scene_index)` — launch all clips in a scene simultaneously
- `fire_scene_clips(scene_index)` — launch only the clips that exist in a scene (skips empty slots)
- `stop_all_clips` — stop everything in session view
- `get_playing_clips` — see which clips are currently playing across all tracks

### Scene Inspection

- `get_scenes_info` — list all scenes with names, tempos, and colors
- `get_scene_matrix` — see which clips exist in which slots across the entire session grid. Returns a track-by-scene matrix showing clip presence, names, and states.

## Arrangement View

Build linear song structures on the timeline.

### Creating Arrangement Clips

- `create_arrangement_clip(track_index, clip_slot_index, start_time, length)` — duplicate a session clip into Arrangement View at a specific beat position
- `create_native_arrangement_clip(track_index, start_time, length)` — create arrangement clip with full automation envelope (12.1.10+)
- `set_arrangement_clip_name(track_index, clip_index, name)` — name arrangement clips for clarity
- `force_arrangement()` — force all tracks to play from arrangement (not session clips)

### Arrangement Notes

- `add_arrangement_notes(track_index, clip_index, notes)` — write MIDI notes into an arrangement clip
- `get_arrangement_notes(track_index, clip_index)` — read notes from an arrangement clip
- `remove_arrangement_notes(track_index, clip_index, start_time, duration, pitch_start, pitch_end)` — clear notes in a region
- `remove_arrangement_notes_by_id(track_index, clip_index, note_ids)` — surgical deletion
- `modify_arrangement_notes(track_index, clip_index, modifications)` — update existing notes by ID
- `duplicate_arrangement_notes(track_index, clip_index, time_offset)` — copy notes forward
- `transpose_arrangement_notes(track_index, clip_index, semitones, start_time, duration)` — pitch shift a region

### Arrangement Clips Inspection

- `get_arrangement_clips(track_index)` — list all clips on a track's arrangement timeline with positions, lengths, and names

### Arrangement Automation

- `set_arrangement_automation(track_index, parameter_name, points)` — write automation on the arrangement timeline. Points are `[{time, value}, ...]` pairs at absolute beat positions.

**Live LOM limitation (BUG-2026-04-22 #1b):** `set_arrangement_automation` only succeeds on arrangement clips that *already* have an envelope for the target parameter (typically clips recorded interactively or duplicated from session). For programmatically-created arrangement clips (via `create_arrangement_clip` or `create_native_arrangement_clip`), the Python LOM does NOT expose a path to create new automation breakpoints — this is a Live API limitation, not a LivePilot bug. Live's docs explicitly state `Clip.automation_envelope` returns None for arrangement clips, and only `value_at_time` exists for reading.

When the tool errors with "Direct envelope access is not supported for programmatically-created arrangement clips," reach for one of two patterns:

1. **Session-clip + record path** (programmatic + manual record):
   - Build the automation on a session clip via `set_clip_automation` (works fully — session clips support `create_automation_envelope`).
   - Tell the user: arm the track, switch to arrangement view, start recording at the target position, fire the session clip, stop recording when it completes. Live records the parameter changes into the arrangement track lane.

2. **Section-clip path** (no envelope, stepped values):
   - Slice the arrangement into multiple clips at section boundaries.
   - Set per-clip volume / parameter values per section using regular `set_track_volume` or `set_device_parameter` between clips.
   - Trades smooth automation for discrete steps but works fully programmatically.

For sweeps that absolutely need to be smooth and programmatic (filter cutoff arcs, send swells), use pattern 1 and accept that the agent has to hand off the record step to the user.

## Navigation

### Transport Position

- `jump_to_time(beat_time)` — move the playback cursor to a specific beat position on the timeline
- `start_playback` / `stop_playback` / `continue_playback` — basic transport control

### Cue Points

Cue points are markers on the arrangement timeline for quick navigation.

- `toggle_cue_point` — add or remove a cue point at the current playback position
- `get_cue_points` — list all cue points with their beat positions and names
- `jump_to_cue(cue_index)` — jump to a specific cue point by index

Use cue points to mark section boundaries: place one at beat 0 (Intro), beat 16 (Verse), beat 48 (Chorus), etc. This makes navigation fast during arrangement.

## Recording

### Live Recording

- `start_recording` — begin recording into the arrangement or session (depends on which view is active and which tracks are armed)
- `stop_recording` — stop recording
- `capture_midi` — retroactive MIDI capture. Grabs whatever was played on armed MIDI tracks even if recording was not active. Live 12 keeps a buffer of recent MIDI input.

### Recording Workflow

1. Arm tracks with `set_track_arm(track_index, arm=true)`
2. Optionally set input monitoring with `set_track_input_monitoring(track_index, mode)`
3. `start_recording` — records into arrangement if in arrangement view, into session slots if in session view
4. Play or trigger clips
5. `stop_recording` — finalize the take

For retroactive capture: if the user just played something without recording, call `capture_midi` immediately to grab it.

## Section Analysis

- `get_section_graph` — infer song structure from scene names and clip arrangement. Returns a graph of sections with their relationships, durations, and transitions.
- `analyze_composition` — deeper structural analysis including phrase lengths, repetition patterns, and harmonic arcs
- `get_phrase_grid` — see how phrases align across tracks

Use `get_section_graph` to understand the current form before adding new sections. It helps identify what is missing (e.g., no bridge, no outro, chorus only appears once).

## Common Song Structures

When building arrangements, use these as starting templates:

- **Pop:** Intro - Verse - Chorus - Verse - Chorus - Bridge - Chorus - Outro
- **EDM/Dance:** Intro (16 bars) - Build - Drop (16) - Break (8) - Build - Drop (16) - Outro (8)
- **Hip-hop:** Intro - Verse (16 bars) - Hook (8) - Verse (16) - Hook (8) - Bridge - Hook - Outro
- **Lo-fi:** Intro (4) - A (8) - B (8) - A (8) - B variation (8) - Outro (4)

Adapt these to the user's needs. Use `plan_arrangement` from the planner domain for algorithmic structure suggestions, and `transform_section` to create variations of existing sections.

## Section-Aware Sample Roles

`plan_arrangement` returns `sample_hints` per section — suggested roles for sample-based elements:

| Section | Default Hints |
|---------|--------------|
| Intro | `texture_bed`, `fill_one_shot` |
| Verse | `texture_bed`, `fill_one_shot` |
| Build | `transition_fx`, `texture_bed` |
| Chorus/Drop | `hook_sample`, `break_layer`, `fill_one_shot` |
| Bridge/Breakdown | `texture_bed`, `transition_fx` |
| Outro | `texture_bed`, `fill_one_shot` |

Use `plan_sample_workflow(section_type=..., desired_role=...)` to generate concrete sample plans for each role. Use `plan_slice_workflow(intent=..., target_section=...)` for slice-based patterns.

## When to hand off to composition-engine

This skill covers **constructive** arrangement. For analytical work — scoring a proposed move, analyzing transitions, inspecting the harmony field, detecting motifs, transforming sections — invoke `livepilot-composition-engine`. Don't re-implement its tools here; they are documented there with full context.

## Reference

Supporting references live in the `livepilot-core` skill's `references/` directory:
- `livepilot-core/references/ableton-workflow-patterns.md` — session/arrangement workflows, song structures by genre, follow actions, clip launch modes, export settings

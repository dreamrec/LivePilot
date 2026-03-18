---
name: livepilot-core
description: Core discipline for controlling Ableton Live 12 through LivePilot's 104 MCP tools. Use whenever working with Ableton Live through MCP tools.
---

# LivePilot Core — Ableton Live 12 AI Copilot

LivePilot gives you 104 MCP tools to control Ableton Live 12 in real-time: transport, tracks, clips, MIDI notes, devices, scenes, mixing, browser, arrangement, and technique memory.

## Golden Rules

1. **Always call `get_session_info` first** — know what you're working with before changing anything
2. **Verify after every write** — re-read state to confirm your change took effect
3. **Use `undo` liberally** — it's your safety net. Mention it to users when doing destructive ops
4. **One operation at a time** — don't batch unrelated changes. Verify between steps
5. **Track indices are 0-based** — track 0 is the first track. Use negative indices for return tracks (-1=A, -2=B). Use -1000 for master track.
6. **NEVER invent device/preset names** — always `search_browser` first, then use the exact `uri` from results with `load_browser_item`. Hallucinated names like "echomorph-hpf" will crash. The only exception is `find_and_load_device` for simple built-in effects ("Reverb", "Delay", "Compressor", "EQ Eight", "Saturator", "Utility").
7. **Color indices 0-69** — Ableton's fixed palette. Don't guess — use the index
8. **Volume is 0.0-1.0, pan is -1.0 to 1.0** — these are normalized, not dB
9. **Tempo range 20-999 BPM** — validated before sending to Ableton
10. **Always name your tracks and clips** — organization is part of the creative process

## Track Health Checks — MANDATORY

**Every track must be verified before you consider it "done".** A track with notes but no sound is a silent failure. Run these checks after building each track.

### After loading any instrument:
1. **`get_track_info`** — confirm the device loaded (`devices` array is not empty, `class_name` is correct)
2. **For Drum Racks: `get_rack_chains`** — confirm chains exist (an empty Drum Rack = silence). You need named chains like "Bass Drum", "Snare", etc.
3. **For synths: `get_device_parameters`** — confirm `Volume`/`Gain` parameter is not 0. Check oscillators are on.
4. **For effects: check `Dry/Wet` and `Drive`/key params** — a Saturator with Drive=0 or a Reverb with Dry/Wet=0 does nothing.

### After programming notes:
1. **`fire_clip` or `fire_scene`** — always listen. If the track has notes but the instrument has no samples/chains, you're playing silence.
2. **Check volume is audible** — `get_track_info` → `mixer.volume` should be > 0.5 for a primary track. Master volume should be > 0.5.

### Device loading rules:
- **NEVER load a bare "Drum Rack"** — it's empty. Always load a **kit preset** like "909 Core Kit", "808 Core Kit", "Boom Bap Kit", etc. Use `search_browser` with path "Drums" and `name_filter` containing "Kit" to find real kits with samples.
- **For synths, prefer `search_browser` → `load_browser_item`** over `find_and_load_device` when the name could match samples (e.g., "Drift" matches "Synth Bass Drift Pad Wonk Bass.wav" before the actual Drift synth).
- **After loading any effect**, verify its key parameters aren't at defaults that make it a pass-through. Set `Drive`, `Dry/Wet`, `Amount` etc. to meaningful values.

### Quick health check pattern:
```
1. get_track_info(track_index)          → has devices? has clips?
2. get_rack_chains (if Drum Rack)       → has chains with samples?
3. get_device_parameters                → volume > 0? key params set?
4. Check mixer.volume > 0              → track is audible?
5. fire_clip / fire_scene              → sound comes out?
```

### Red flags (things that produce silence):
- Empty Drum Rack (no chains)
- Synth with Volume/Gain at 0 or -inf dB
- Effect with Dry/Wet at 0%
- Track volume at 0
- Track muted
- Master volume at 0
- MIDI track with no instrument loaded
- Notes programmed but clip not fired

## Tool Domains (104 total)

### Transport (12)
`get_session_info` · `set_tempo` · `set_time_signature` · `start_playback` · `stop_playback` · `continue_playback` · `toggle_metronome` · `set_session_loop` · `undo` · `redo` · `get_recent_actions` · `get_session_diagnostics`

### Tracks (14)
`get_track_info` · `create_midi_track` · `create_audio_track` · `create_return_track` · `delete_track` · `duplicate_track` · `set_track_name` · `set_track_color` · `set_track_mute` · `set_track_solo` · `set_track_arm` · `stop_track_clips` · `set_group_fold` · `set_track_input_monitoring`

### Clips (11)
`get_clip_info` · `create_clip` · `delete_clip` · `duplicate_clip` · `fire_clip` · `stop_clip` · `set_clip_name` · `set_clip_color` · `set_clip_loop` · `set_clip_launch` · `set_clip_warp_mode`

### Notes (8)
`add_notes` · `get_notes` · `remove_notes` · `remove_notes_by_id` · `modify_notes` · `duplicate_notes` · `transpose_notes` · `quantize_clip`

### Devices (12)
`get_device_info` · `get_device_parameters` · `set_device_parameter` · `batch_set_parameters` · `toggle_device` · `delete_device` · `load_device_by_uri` · `find_and_load_device` · `set_simpler_playback_mode` · `get_rack_chains` · `set_chain_volume` · `get_device_presets`

### Scenes (8)
`get_scenes_info` · `create_scene` · `delete_scene` · `duplicate_scene` · `fire_scene` · `set_scene_name` · `set_scene_color` · `set_scene_tempo`

### Mixing (8)
`set_track_volume` · `set_track_pan` · `set_track_send` · `get_return_tracks` · `get_master_track` · `set_master_volume` · `get_track_routing` · `set_track_routing`

### Browser (4)
`get_browser_tree` · `get_browser_items` · `search_browser` · `load_browser_item`

### Arrangement (19)
`get_arrangement_clips` · `create_arrangement_clip` · `add_arrangement_notes` · `get_arrangement_notes` · `remove_arrangement_notes` · `remove_arrangement_notes_by_id` · `modify_arrangement_notes` · `duplicate_arrangement_notes` · `transpose_arrangement_notes` · `set_arrangement_clip_name` · `set_arrangement_automation` · `back_to_arranger` · `jump_to_time` · `capture_midi` · `start_recording` · `stop_recording` · `get_cue_points` · `jump_to_cue` · `toggle_cue_point`

### Memory (8)
`memory_learn` · `memory_recall` · `memory_get` · `memory_replay` · `memory_list` · `memory_favorite` · `memory_update` · `memory_delete`

## Workflow: Building a Beat

1. `get_session_info` — check current state
2. `set_tempo` — set your target BPM
3. `create_midi_track` — create tracks for drums, bass, chords, melody
4. Name and color each track with `set_track_name` / `set_track_color`
5. **Load instruments with PRESETS, not empty shells:**
   - **Drums:** `search_browser` path="Drums" name_filter="Kit" → pick a kit → `load_browser_item`. NEVER load bare "Drum Rack".
   - **Synths:** `search_browser` path="Instruments" name_filter="Drift" → `load_browser_item` with exact URI. Avoids sample name collisions.
   - **VERIFY:** `get_rack_chains` for drums (must have chains), `get_device_parameters` for synths (Volume > 0)
6. `create_clip` — create clips on each track (4 beats = 1 bar at 4/4)
7. `add_notes` — program MIDI patterns. Each note needs `pitch`, `start_time`, `duration`
8. **HEALTH CHECK per track:** `get_track_info` → confirm device loaded, mixer volume > 0, not muted
9. `fire_scene` or `fire_clip` — listen to your work
10. Iterate: `get_notes` → `modify_notes` / `transpose_notes` → listen again

## Workflow: Sound Design

1. Load a synth: `search_browser` path="Instruments" → `load_browser_item` with exact URI
2. **VERIFY:** `get_device_parameters` — confirm Volume/Gain > 0, oscillators on, filter not fully closed
3. `set_device_parameter` — tweak individual params by name or index
4. `batch_set_parameters` — set multiple params at once for a preset
5. Load effects: `find_and_load_device` with "Reverb", "Delay", "Compressor", etc.
6. **VERIFY each effect:** `get_device_parameters` — confirm Dry/Wet > 0, Drive/Amount set to meaningful values. An effect at default may be a pass-through.
7. Chain devices: they stack in order on the track's device chain
8. Use `get_device_info` to inspect rack devices, `get_rack_chains` for racks

## Workflow: Mixing

1. `get_session_info` — see all tracks and current levels
2. `set_track_volume` / `set_track_pan` — set levels and stereo position
3. `set_track_send` — route to return tracks for shared effects
4. `get_return_tracks` — check return track setup
5. `set_master_volume` — final output level
6. `set_track_routing` — configure input/output routing

## Live 12 Note API

Notes use this format when calling `add_notes`:
```json
{
  "pitch": 60,
  "start_time": 0.0,
  "duration": 0.5,
  "velocity": 100,
  "mute": false
}
```

When reading with `get_notes`, you also get:
- `note_id` — unique ID for modify/remove operations
- `probability` — 0.0-1.0, Live 12 per-note probability
- `velocity_deviation` — -127.0 to 127.0
- `release_velocity` — 0.0-127.0

Use `modify_notes` with `note_id` to update existing notes.
Use `remove_notes_by_id` for surgical deletion.
Use `transpose_notes` for pitch shifting a region.
Use `quantize_clip` to snap notes to a grid (grid is an enum: 1=1/4, 2=1/8, 5=1/16, 8=1/32).

## Technique Memory

LivePilot has a persistent memory system for saving and recalling techniques — beats, device chains, mixing setups, browser pins, and preferences — with rich stylistic analysis.

### Three Modes of Operation

**Informed (default):** Before creative decisions, consult memory:
```
memory_recall(query relevant to the task, limit=5)
```
Read the qualities of returned techniques. Let them INFLUENCE your choices — instrument selection, parameter ranges, rhythmic density, harmonic language — but always create something new. The memory shapes your understanding of this user's taste, not a template to copy.

**Fresh (user override):** When the user signals a clean slate:
- "ignore my history" / "something completely new" / "fresh"
- "don't look at my saved stuff" / "surprise me"
→ Skip memory_recall entirely. Use only the shipped corpus and your own musical knowledge.

**Explicit Recall:** When the user references a saved technique:
- "use that boom bap beat" / "load my lo-fi chain" / "remember that thing I saved?"
→ `memory_recall` to find it → `memory_get` for full payload → `memory_replay` (adapt=false for exact, adapt=true for variation)

### Saving Techniques

When the user says "save this" / "remember this" / "I like this":

1. Collect raw data using existing tools (get_notes, get_device_parameters, etc.)
2. Write the qualities analysis — see `references/memory-guide.md` for the template
3. Call `memory_learn` with type, qualities, payload, tags
4. Confirm to the user what was saved and how it was characterized

### Memory Tools (8)

| Tool | What it does |
|------|-------------|
| `memory_learn` | Save a technique with qualities + payload |
| `memory_recall` | Search by text query, type, tags — returns summaries |
| `memory_get` | Fetch full technique by ID (with payload) |
| `memory_replay` | Get replay plan for agent to execute |
| `memory_list` | Browse library with filtering and sorting |
| `memory_favorite` | Star and/or rate (0-5) a technique |
| `memory_update` | Update name, tags, or qualities |
| `memory_delete` | Remove (creates backup first) |

## Reference Corpus

Deep production knowledge lives in `references/`. Consult these when making creative decisions — they contain specific parameter values, recipes, and patterns. Use them as starting points, not rigid rules.

| File | What's inside | When to consult |
|------|--------------|-----------------|
| `references/overview.md` | All 104 tools mapped with params, units, ranges | Quick lookup for any tool |
| `references/midi-recipes.md` | Drum patterns by genre, chord voicings, scales, hi-hat techniques, humanization, polymetrics | Programming MIDI notes, building beats |
| `references/sound-design.md` | Stock instruments/effects, parameter recipes for bass/pad/lead/pluck, device chain patterns | Loading and configuring devices |
| `references/mixing-patterns.md` | Gain staging, parallel compression, sidechain, EQ by instrument, bus processing, stereo width | Setting volumes, panning, adding effects |
| `references/ableton-workflow-patterns.md` | Session/Arrangement workflow, song structures by genre, follow actions, clip launch modes, export | Organizing sessions, structuring songs |
| `references/m4l-devices.md` | Browser organization, MIDI effects, rack systems, device loading patterns | Finding and loading devices, using racks |
| `references/memory-guide.md` | Qualities template, good/bad examples for each technique type | Saving techniques, writing qualities |

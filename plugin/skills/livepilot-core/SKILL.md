---
name: livepilot-core
description: Core discipline for controlling Ableton Live 12 through LivePilot's 135 MCP tools, device atlas (280+ devices), M4L analyzer (spectrum/RMS/key detection), automation intelligence (16 curve types, 15 recipes), and technique memory. Use whenever working with Ableton Live through MCP tools.
---

# LivePilot Core — Ableton Live 12 AI Copilot

LivePilot is an agentic production system for Ableton Live 12. It combines 135 MCP tools with three layers of intelligence:

- **Device Atlas** — A structured knowledge corpus of 280+ instruments, 139 drum kits, and 350+ impulse responses. Consult the atlas before loading any device. It contains real browser URIs, preset names, and sonic descriptions. Never guess a device name — look it up.
- **M4L Analyzer** — Real-time audio analysis on the master bus (8-band spectrum, RMS/peak, key detection). Use it to verify mixing decisions, detect frequency problems, and find the key before writing harmonic content.
- **Technique Memory** — Persistent storage for production decisions. Consult `memory_recall` before creative tasks to understand the user's taste. Save techniques when the user likes something. The memory shapes future decisions without constraining them.

These layers sit on top of 135 deterministic tools across 12 domains: transport, tracks, clips, MIDI notes, devices, scenes, mixing, browser, arrangement, technique memory, real-time DSP analysis, and automation.

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

## Tool Domains (135 total)

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

### Mixing (11)
`set_track_volume` · `set_track_pan` · `set_track_send` · `get_return_tracks` · `get_master_track` · `set_master_volume` · `get_track_routing` · `set_track_routing` · `get_track_meters` · `get_master_meters` · `get_mix_snapshot`

### Browser (4)
`get_browser_tree` · `get_browser_items` · `search_browser` · `load_browser_item`

### Arrangement (19)
`get_arrangement_clips` · `create_arrangement_clip` · `add_arrangement_notes` · `get_arrangement_notes` · `remove_arrangement_notes` · `remove_arrangement_notes_by_id` · `modify_arrangement_notes` · `duplicate_arrangement_notes` · `transpose_arrangement_notes` · `set_arrangement_clip_name` · `set_arrangement_automation` · `back_to_arranger` · `jump_to_time` · `capture_midi` · `start_recording` · `stop_recording` · `get_cue_points` · `jump_to_cue` · `toggle_cue_point`

### Memory (8)
`memory_learn` · `memory_recall` · `memory_get` · `memory_replay` · `memory_list` · `memory_favorite` · `memory_update` · `memory_delete`

### Analyzer (20) — requires LivePilot Analyzer M4L device on master track
`get_master_spectrum` · `get_master_rms` · `get_detected_key` · `get_hidden_parameters` · `get_automation_state` · `walk_device_tree` · `get_clip_file_path` · `replace_simpler_sample` · `load_sample_to_simpler` · `get_simpler_slices` · `crop_simpler` · `reverse_simpler` · `warp_simpler` · `get_warp_markers` · `add_warp_marker` · `move_warp_marker` · `remove_warp_marker` · `scrub_clip` · `stop_scrub` · `get_display_values`

### Automation (8)
Clip automation CRUD + intelligent curve generation with 15 built-in recipes.

**Tools:** `get_clip_automation` · `set_clip_automation` · `clear_clip_automation` · `apply_automation_shape` · `apply_automation_recipe` · `get_automation_recipes` · `generate_automation_curve` · `analyze_for_automation`

**Key discipline:**

**The Feedback Loop (MANDATORY for all automation work):**
1. PERCEIVE: `get_master_spectrum` + `get_track_meters` -> understand current state
2. DIAGNOSE: What needs to change? Use diagnostic filter technique if unsure
3. DECIDE: Which parameter, which curve, which recipe?
4. ACT: `apply_automation_shape` or `apply_automation_recipe`
5. VERIFY: `get_master_spectrum` again -> did it work?
6. ADJUST: If not right, `clear_clip_automation` -> try different curve/params
7. NEVER write automation without reading spectrum first and after

**Rules:**
- Use `analyze_for_automation` before writing — let spectral data guide decisions
- Use recipes for common patterns (filter_sweep_up, dub_throw, sidechain_pump)
- Use `apply_automation_shape` for custom curves with specific math
- Clear existing automation before rewriting: `clear_clip_automation` first
- Load `references/automation-atlas.md` for curve theory, genre recipes, diagnostic technique, and cross-track spectral mapping

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
2. `get_mix_snapshot` — one-call overview of all levels, panning, routing, mute/solo
3. `set_track_volume` / `set_track_pan` — set levels and stereo position
4. `set_track_send` — route to return tracks for shared effects
5. `get_return_tracks` — check return track setup
6. `set_master_volume` — final output level
7. `set_track_routing` — configure input/output routing
8. `get_track_meters` / `get_master_meters` — check real-time output levels

### With LivePilot Analyzer (M4L device on master):
9. `get_master_spectrum` — check frequency balance across 8 bands (sub → air)
10. `get_master_rms` — true RMS and peak levels
11. `get_detected_key` — detect musical key before writing harmonies/bass
12. `get_hidden_parameters` — see ALL device params including hidden ones
13. `get_automation_state` — check which params have automation before overwriting
14. `walk_device_tree` — inspect nested racks and drum pads
15. `get_display_values` — human-readable parameter values ("440 Hz", "-6 dB")

## Workflow: Sample Chopping

1. Resample your beat to an audio track (set input to Resampling, arm, record)
2. `get_clip_file_path` — get the audio file path of the recorded clip
3. Load Simpler on a new MIDI track (with any sample pre-loaded)
4. `replace_simpler_sample` — load the resampled audio into Simpler
5. `set_simpler_playback_mode` — set to Slice mode
6. `get_simpler_slices` — see all auto-detected slice points
7. Program MIDI patterns targeting slice indices
8. Use `reverse_simpler` / `crop_simpler` / `warp_simpler` for transformations
9. `get_master_spectrum` — verify the result through the analyzer

## Workflow: Time Manipulation

1. `get_warp_markers` — see current timing map of an audio clip
2. `add_warp_marker` — pin key beats (downbeats, snare hits)
3. `move_warp_marker` — stretch/compress specific segments for tempo effects
4. `scrub_clip` / `stop_scrub` — preview specific positions
5. `get_master_spectrum` — verify the result sounds right
6. `remove_warp_marker` — clean up if needed

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
| `references/overview.md` | All 135 tools mapped with params, units, ranges | Quick lookup for any tool |
| `references/midi-recipes.md` | Drum patterns by genre, chord voicings, scales, hi-hat techniques, humanization, polymetrics | Programming MIDI notes, building beats |
| `references/sound-design.md` | Stock instruments/effects, parameter recipes for bass/pad/lead/pluck, device chain patterns | Loading and configuring devices |
| `references/mixing-patterns.md` | Gain staging, parallel compression, sidechain, EQ by instrument, bus processing, stereo width | Setting volumes, panning, adding effects |
| `references/ableton-workflow-patterns.md` | Session/Arrangement workflow, song structures by genre, follow actions, clip launch modes, export | Organizing sessions, structuring songs |
| `references/m4l-devices.md` | Browser organization, MIDI effects, rack systems, device loading patterns | Finding and loading devices, using racks |
| `references/memory-guide.md` | Qualities template, good/bad examples for each technique type | Saving techniques, writing qualities |
| `references/automation-atlas.md` | Curve theory, perception-action loop, genre recipes, diagnostic filter technique, spectral mapping | Writing automation, choosing curves, mixing with spectral feedback |

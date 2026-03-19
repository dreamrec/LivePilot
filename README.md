```
██╗     ██╗██╗   ██╗███████╗██████╗ ██╗██╗      ██████╗ ████████╗
██║     ██║██║   ██║██╔════╝██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██║     ██║██║   ██║█████╗  ██████╔╝██║██║     ██║   ██║   ██║
██║     ██║╚██╗ ██╔╝██╔══╝  ██╔═══╝ ██║██║     ██║   ██║   ██║
███████╗██║ ╚████╔╝ ███████╗██║     ██║███████╗╚██████╔╝   ██║
╚══════╝╚═╝  ╚═══╝  ╚══════╝╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

An agentic production system for Ableton Live 12.

168 tools. Device atlas. Spectral perception. Technique memory.
Neo-Riemannian harmony. Euclidean rhythm. Species counterpoint.

It doesn't assist — it produces.

<br>

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   KNOWLEDGE            PERCEPTION           MEMORY          │
│   ───────────          ──────────           ──────          │
│                                                             │
│   280+ devices         8-band FFT           recall by       │
│   139 drum kits        RMS / peak           mood, genre,    │
│   350+ impulse         pitch tracking       texture         │
│   responses            key detection                        │
│                                                             │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│   │   Device   │─────▶│    M4L     │─────▶│ Technique  │   │
│   │   Atlas    │      │  Analyzer  │      │   Store    │   │
│   └─────┬──────┘      └─────┬──────┘      └─────┬──────┘   │
│         └───────────────────┼───────────────────┘           │
│                             ▼                               │
│                    ┌─────────────────┐                      │
│                    │   168 MCP Tools  │                      │
│                    │   17 domains     │                      │
│                    └────────┬────────┘                      │
│                             │                               │
│             Remote Script ──┤── TCP 9878                    │
│             M4L Bridge ─────┤── UDP 9880 / OSC 9881         │
│                             │                               │
│                    ┌────────────────┐                       │
│                    │  Ableton Live  │                       │
│                    └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

The atlas gives the AI knowledge of every device in Ableton's library —
real names, real URIs, real parameters.

The analyzer gives it ears — spectral data from the master bus
via a Max for Live device.

The memory gives it history — a searchable library of production decisions
that persists across sessions.

All three feed into 168 deterministic tools that execute on Ableton's main thread
through the official Live Object Model API. Everything is reversible with undo.

<br>

---

## Tools

<br>

### CORE

The foundation. Session control, MIDI, device management, mixing.
Every tool maps directly to an LOM call — no abstraction, no guessing.

<br>

| Domain | # | Scope |
|--------|:-:|-------|
| Transport | 12 | playback, tempo, time sig, loop, metronome, undo/redo, cue points, diagnostics |
| Tracks | 14 | create MIDI/audio/return, delete, duplicate, arm, mute, solo, color, routing, monitoring |
| Clips | 11 | create, delete, duplicate, fire, stop, loop, launch mode, warp mode, quantize |
| Notes | 8 | add/get/remove/modify MIDI notes, transpose, duplicate, per-note probability |
| Devices | 12 | load by name or URI, get/set parameters, batch edit, racks, chains, presets, toggle |
| Scenes | 8 | create, delete, duplicate, fire, name, color, per-scene tempo |
| Browser | 4 | search library, browse tree, load items, filter by category |
| Mixing | 11 | volume, pan, sends, routing, meters, return tracks, master, full mix snapshot |

<br>

### PERCEPTION

The M4L Analyzer sits on the master track. UDP 9880 carries spectral data
from Max to the server. OSC 9881 sends commands back.

All 135 core tools work without it — the analyzer adds 20 more
and closes the feedback loop.

<br>

```
SPECTRAL ─────── 8-band frequency decomposition (sub → air)
                 true RMS / peak metering
                 Krumhansl-Schmuckler key detection

DEEP LOM ─────── hidden parameters beyond ControlSurface API
                 automation state per parameter
                 recursive device tree (6 levels into nested racks)
                 human-readable display values as shown in Live's UI

SIMPLER ──────── replace / load samples
                 get slice points, crop, reverse
                 warp to N beats, get audio file paths

WARP ─────────── get / add / move / remove markers
                 tempo manipulation at the sample level

PREVIEW ──────── scrub at beat position
                 stop scrub
```

<br>

### INTELLIGENCE

<br>

#### Theory — 7 tools

Krumhansl-Schmuckler key detection with 7 mode profiles:
major, minor, dorian, phrygian, lydian, mixolydian, locrian.

Roman numeral analysis via scale-degree chord matching
on a 1/32 note quantization grid.

Voice leading checks — parallel fifths, parallel octaves,
voice crossing, unresolved dominants.

Species counterpoint generation (1st and 2nd species).
SATB harmonization with smooth voice leading.
Diatonic transposition that preserves scale relationships.

```
analyze_harmony         suggest_next_chord      detect_theory_issues
identify_scale          harmonize_melody         generate_countermelody
transpose_smart
```

<br>

#### Harmony — 4 tools

Neo-Riemannian PRL transforms on the Tonnetz.

```
P  flips the third ─────── Cm ↔ C
L  shifts by semitone ──── C  ↔ Em
R  shifts by whole tone ── C  ↔ Am
```

All three are involutions — apply twice, return to origin.

BFS through PRL space finds the shortest voice-leading path
between any two triads. Cm to E major? That's PLP — the hexatonic pole.
Three steps, each moving one voice by a semitone.
The Hitchcock chord change.

Chromatic mediants for film-score harmony: chords a major/minor third away
sharing 0-1 common tones. Maximum color shift, minimal voice movement.

```
navigate_tonnetz        find_voice_leading_path
classify_progression    suggest_chromatic_mediants
```

<br>

#### Generative — 5 tools

**Euclidean Rhythm** — Bjorklund distributes N pulses across M steps.
Bresenham's line algorithm applied to rhythm.

```
E(3,8)  = tresillo          ×··×··×·
E(5,8)  = cinquillo          ×·××·××·
E(7,16) = Brazilian necklace ×·×·×××·×·×·×××·
```

Layer multiple patterns at different pitches for polyrhythmic textures.

**Tintinnabuli** (Arvo Pärt) — for each melody note, find the nearest tone
of a specified triad: above, below, or nearest. The T-voice gravitates toward
the triad while the M-voice moves stepwise. Two voices, one rule, infinite music.

**Phase Shifting** (Steve Reich) — identical voices with accumulating timing drift.
Voice 0 plays straight. Each subsequent voice shifts by N beats per repetition.
They start in unison, gradually separate, and eventually realign.

**Additive Process** (Philip Glass) — melody unfolds note by note.
Forward: 1, then 1-2, then 1-2-3.
Backward: full melody, then remove from front.
Both: forward then backward.
The structure *is* the composition.

```
generate_euclidean_rhythm    layer_euclidean_rhythms
generate_tintinnabuli        generate_phase_shift
generate_additive_process
```

<br>

#### Automation — 8 tools

16 curve types in 4 categories:

```
BASIC ──────────── linear · exponential · logarithmic · s_curve
                   sine · sawtooth · spike · square · steps

ORGANIC ─────────── perlin · brownian · spring

SHAPE ──────────── bezier · easing
                   (bounce, elastic, back, quad, cubic,
                    quart, quint, expo)

GENERATIVE ─────── euclidean · stochastic
```

15 built-in recipes:

```
filter_sweep_up     filter_sweep_down    dub_throw
tape_stop           build_rise           sidechain_pump
fade_in             fade_out             tremolo
auto_pan            stutter              breathing
washout             vinyl_crackle        stereo_narrow
```

Perception-action loop: `analyze_for_automation` reads the spectrum
and device chain, suggests what to automate, and maps each suggestion
to a recipe. The AI doesn't write automation blind — it knows what
to automate based on what it hears.

```
get_clip_automation      set_clip_automation       clear_clip_automation
apply_automation_shape   apply_automation_recipe   get_automation_recipes
generate_automation_curve                          analyze_for_automation
```

<br>

### MEMORY + I/O

<br>

#### Memory — 8 tools

Persistent technique library across sessions.

Five types: `beat_pattern` · `device_chain` · `mix_template` · `preference` · `browser_pin`

Each stores:
- **Identity** — name, tags, timestamps
- **Qualities** — mood, genre, texture, production notes
- **Payload** — raw MIDI, device params, tempo, URIs

Recall by text query matching mood, genre, texture — not just names.
Favorite, rate, replay.

```
memory_learn     memory_recall     memory_list       memory_get
memory_update    memory_delete     memory_favorite   memory_replay
```

<br>

#### MIDI I/O — 4 tools

Export session clips to standard .mid files.
Import .mid into session clips — auto-creates the clip, tempo-aware timing.

Offline analysis without Ableton: note count, duration, tempo,
pitch range, velocity stats, density curve, key estimate.

Piano roll extraction: 2D velocity matrix at configurable resolution
(default 1/32 note).

Dependencies lazy-loaded — graceful error if missing.

```
export_clip_midi     import_midi_to_clip
analyze_midi_file    extract_piano_roll
```

<br>

---

## Install

<br>

### 1. Remote Script

```bash
npx livepilot --install
```

Restart Ableton → Preferences → Link, Tempo & MIDI → Control Surface → **LivePilot**

<br>

### 2. MCP Client

<details open>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add LivePilot -- npx livepilot
```

Plugin (adds skills, slash commands, producer agent):

```bash
claude plugin add github:dreamrec/LivePilot/plugin
```

</details>

<details>
<summary><strong>Claude Desktop (macOS)</strong></summary>

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["livepilot"]
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Desktop (Windows)</strong></summary>

```cmd
npm install -g livepilot
livepilot --install
```

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "livepilot"
    }
  }
}
```

</details>

<details>
<summary><strong>Cursor</strong></summary>

`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["livepilot"]
    }
  }
}
```

</details>

<details>
<summary><strong>VS Code / Windsurf</strong></summary>

VS Code — `.vscode/mcp.json`:

```json
{
  "servers": {
    "LivePilot": {
      "command": "npx",
      "args": ["livepilot"]
    }
  }
}
```

Windsurf — `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["livepilot"]
    }
  }
}
```

</details>

<br>

### 3. M4L Analyzer (optional)

Drag `LivePilot_Analyzer.amxd` onto the master track.

Unlocks 20 additional tools: spectral analysis, key detection,
sample manipulation, deep device introspection.

All core tools work without it.

<br>

### 4. Verify

```bash
npx livepilot --status
```

<br>

---

## Plugin

```bash
claude plugin add github:dreamrec/LivePilot/plugin
```

<br>

| Command | What |
|---------|------|
| `/session` | Full session overview with diagnostics |
| `/beat` | Guided beat creation |
| `/mix` | Mixing assistant |
| `/sounddesign` | Sound design workflow |
| `/memory` | Technique library management |

<br>

**Producer Agent** — autonomous multi-step production.
Consults memory for style context, searches the atlas for instruments,
creates tracks, programs MIDI, chains effects, reads the spectrum to verify.
Ships with a reference corpus (drum patterns, chord voicings,
sound design recipes, mixing templates).

**Core Skill** — operational discipline connecting all three layers.
Consult atlas before loading. Read analyzer after mixing.
Check memory before creative decisions. Verify every mutation.

<br>

---

## Full Tool List

168 tools across 17 domains.

<br>

### Transport (12)

| Tool | Description |
|------|-------------|
| `get_session_info` | Session state: tempo, tracks, scenes, transport |
| `set_tempo` | Set tempo (20-999 BPM) |
| `set_time_signature` | Set time signature |
| `start_playback` | Start from beginning |
| `stop_playback` | Stop |
| `continue_playback` | Resume from current position |
| `toggle_metronome` | Enable/disable click |
| `set_session_loop` | Set loop start, length, on/off |
| `undo` | Undo last action |
| `redo` | Redo |
| `get_recent_actions` | Recent undo history |
| `get_session_diagnostics` | Analyze session for issues |

<br>

### Tracks (14)

| Tool | Description |
|------|-------------|
| `get_track_info` | Track details: clips, devices, mixer |
| `create_midi_track` | New MIDI track |
| `create_audio_track` | New audio track |
| `create_return_track` | New return track |
| `delete_track` | Delete a track |
| `duplicate_track` | Copy track with all content |
| `set_track_name` | Rename |
| `set_track_color` | Set color (0-69) |
| `set_track_mute` | Mute on/off |
| `set_track_solo` | Solo on/off |
| `set_track_arm` | Arm for recording |
| `stop_track_clips` | Stop all clips on track |
| `set_group_fold` | Fold/unfold group track |
| `set_track_input_monitoring` | Set monitoring mode |

<br>

### Clips (11)

| Tool | Description |
|------|-------------|
| `get_clip_info` | Clip details: length, loop, launch |
| `create_clip` | New empty MIDI clip |
| `delete_clip` | Delete a clip |
| `duplicate_clip` | Copy to another slot |
| `fire_clip` | Launch a clip |
| `stop_clip` | Stop a clip |
| `set_clip_name` | Rename |
| `set_clip_color` | Set color |
| `set_clip_loop` | Loop start, end, on/off |
| `set_clip_launch` | Launch mode and quantization |
| `set_clip_warp_mode` | Set warp algorithm |

<br>

### Notes (8)

| Tool | Description |
|------|-------------|
| `add_notes` | Add MIDI notes with velocity, probability |
| `get_notes` | Read notes from a region |
| `remove_notes` | Remove notes in a region |
| `remove_notes_by_id` | Remove specific notes by ID |
| `modify_notes` | Change pitch, time, velocity, probability |
| `duplicate_notes` | Copy notes to new position |
| `transpose_notes` | Shift pitch by semitones |
| `quantize_clip` | Quantize to grid |

<br>

### Devices (12)

| Tool | Description |
|------|-------------|
| `get_device_info` | Device name, class, parameters |
| `get_device_parameters` | All params with names, values, ranges |
| `set_device_parameter` | Set param by name or index |
| `batch_set_parameters` | Set multiple params in one call |
| `toggle_device` | Enable/disable |
| `delete_device` | Remove from chain |
| `load_device_by_uri` | Load by browser URI |
| `find_and_load_device` | Search and load by name |
| `get_rack_chains` | Get chains in a rack |
| `set_simpler_playback_mode` | Classic/1-shot/slice |
| `set_chain_volume` | Set chain volume in rack |
| `get_device_presets` | List available presets |

<br>

### Scenes (8)

| Tool | Description |
|------|-------------|
| `get_scenes_info` | All scenes: name, tempo, color |
| `create_scene` | New scene |
| `delete_scene` | Delete a scene |
| `duplicate_scene` | Copy scene with all clips |
| `fire_scene` | Launch all clips in scene |
| `set_scene_name` | Rename |
| `set_scene_color` | Set color |
| `set_scene_tempo` | Per-scene tempo |

<br>

### Mixing (11)

| Tool | Description |
|------|-------------|
| `set_track_volume` | Volume (0.0-1.0) |
| `set_track_pan` | Pan (-1.0 to 1.0) |
| `set_track_send` | Send level (0.0-1.0) |
| `get_return_tracks` | Return track info |
| `get_master_track` | Master track info |
| `set_master_volume` | Master volume |
| `get_track_routing` | Input/output routing |
| `set_track_routing` | Set routing by display name |
| `get_track_meters` | Live meter levels |
| `get_master_meters` | Master meter levels |
| `get_mix_snapshot` | Full mix state in one call |

<br>

### Browser (4)

| Tool | Description |
|------|-------------|
| `get_browser_tree` | Browse category tree |
| `get_browser_items` | List items in a category |
| `search_browser` | Search by name with filters |
| `load_browser_item` | Load item by URI |

<br>

### Arrangement (19)

| Tool | Description |
|------|-------------|
| `get_arrangement_clips` | List arrangement clips |
| `create_arrangement_clip` | New clip at timeline position |
| `add_arrangement_notes` | Add MIDI notes to arrangement clip |
| `get_arrangement_notes` | Read arrangement notes |
| `remove_arrangement_notes` | Remove notes in region |
| `remove_arrangement_notes_by_id` | Remove by ID |
| `modify_arrangement_notes` | Modify arrangement notes |
| `duplicate_arrangement_notes` | Copy notes |
| `transpose_arrangement_notes` | Shift pitch |
| `set_arrangement_clip_name` | Rename arrangement clip |
| `set_arrangement_automation` | Write arrangement automation |
| `back_to_arranger` | Switch to arrangement view |
| `jump_to_time` | Seek to beat position |
| `capture_midi` | Capture played MIDI |
| `start_recording` | Start recording |
| `stop_recording` | Stop recording |
| `get_cue_points` | List cue points |
| `jump_to_cue` | Jump to cue point |
| `toggle_cue_point` | Add/remove cue point |

<br>

### Automation (8)

| Tool | Description |
|------|-------------|
| `get_clip_automation` | List envelopes on a clip |
| `set_clip_automation` | Write automation points |
| `clear_clip_automation` | Clear envelopes |
| `apply_automation_shape` | Generate + write curve in one call |
| `apply_automation_recipe` | Apply named recipe |
| `get_automation_recipes` | List all 15 recipes |
| `generate_automation_curve` | Preview curve without writing |
| `analyze_for_automation` | Spectral analysis + suggestions |

<br>

### Memory (8)

| Tool | Description |
|------|-------------|
| `memory_learn` | Save a technique |
| `memory_recall` | Search by text/mood/genre |
| `memory_list` | Browse library |
| `memory_get` | Get full technique with payload |
| `memory_update` | Update a technique |
| `memory_delete` | Delete a technique |
| `memory_favorite` | Toggle favorite |
| `memory_replay` | Replay saved technique |

<br>

### Analyzer (20) `[M4L]`

| Tool | Description |
|------|-------------|
| `get_master_spectrum` | 8-band frequency analysis |
| `get_master_rms` | RMS and peak levels |
| `get_detected_key` | Krumhansl-Schmuckler key detection |
| `get_hidden_parameters` | All params including hidden ones |
| `get_automation_state` | Automation state per parameter |
| `walk_device_tree` | Recursive device chain tree (6 levels) |
| `get_display_values` | Human-readable param values |
| `get_clip_file_path` | Audio file path on disk |
| `replace_simpler_sample` | Load audio into Simpler |
| `load_sample_to_simpler` | Bootstrap Simpler + load sample |
| `get_simpler_slices` | Slice point positions |
| `crop_simpler` | Crop to active region |
| `reverse_simpler` | Reverse sample |
| `warp_simpler` | Time-stretch to N beats |
| `get_warp_markers` | Get all warp markers |
| `add_warp_marker` | Add warp marker |
| `move_warp_marker` | Move warp marker |
| `remove_warp_marker` | Remove warp marker |
| `scrub_clip` | Preview at beat position |
| `stop_scrub` | Stop preview |

<br>

### Theory (7)

| Tool | Description |
|------|-------------|
| `analyze_harmony` | Chord-by-chord Roman numeral analysis |
| `suggest_next_chord` | Theory-valid continuations with style presets |
| `detect_theory_issues` | Parallel 5ths, out-of-key, voice crossing |
| `identify_scale` | Key/mode detection with confidence ranking |
| `harmonize_melody` | 2 or 4-voice SATB harmonization |
| `generate_countermelody` | Species counterpoint (1st/2nd) |
| `transpose_smart` | Diatonic or chromatic transposition |

<br>

### Generative (5)

| Tool | Description |
|------|-------------|
| `generate_euclidean_rhythm` | Bjorklund algorithm, identifies named rhythms |
| `layer_euclidean_rhythms` | Stack patterns for polyrhythmic textures |
| `generate_tintinnabuli` | Arvo Pärt — triad voice from melody |
| `generate_phase_shift` | Steve Reich — drifting canon |
| `generate_additive_process` | Philip Glass — expanding/contracting melody |

<br>

### Harmony (4)

| Tool | Description |
|------|-------------|
| `navigate_tonnetz` | PRL neighbors at depth N |
| `find_voice_leading_path` | Shortest path between two chords |
| `classify_progression` | Identify neo-Riemannian pattern |
| `suggest_chromatic_mediants` | All chromatic mediant relations |

<br>

### MIDI I/O (4)

| Tool | Description |
|------|-------------|
| `export_clip_midi` | Export clip to .mid file |
| `import_midi_to_clip` | Import .mid into session clip |
| `analyze_midi_file` | Offline MIDI analysis |
| `extract_piano_roll` | 2D velocity matrix extraction |

<br>

---

## Coming

```
□  Real-time DSP analysis via LOM meters
□  M4L bridge expansion — deeper LiveAPI access
□  Arrangement view — clip placement, tempo automation
□  Audio clip manipulation — stretch, slice, resample
□  Plugin parameter mapping — VST/AU deep control
```

<br>

---

## CLI

```bash
npx livepilot              # Start MCP server (stdio)
npx livepilot --install    # Install Remote Script
npx livepilot --uninstall  # Remove Remote Script
npx livepilot --status     # Check Ableton connection
npx livepilot --doctor     # Full diagnostic check
npx livepilot --version    # Show version
```

<br>

## Compatibility

Live 12 all editions. Suite required for stock instruments
(Drift, Meld, Wavetable) and Max for Live.
Python 3.9+. Node.js 18+.

<br>

## Development

```bash
git clone https://github.com/dreamrec/LivePilot.git
cd LivePilot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest tests/ -v
```

<br>

---

[MIT](LICENSE) — Pilot Studio

Sister projects: [TDPilot](https://github.com/dreamrec/TDPilot) (TouchDesigner) · [ComfyPilot](https://github.com/dreamrec/ComfyPilot) (ComfyUI)

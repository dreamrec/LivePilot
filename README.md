```
██╗     ██╗██╗   ██╗███████╗██████╗ ██╗██╗      ██████╗ ████████╗
██║     ██║██║   ██║██╔════╝██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██║     ██║██║   ██║█████╗  ██████╔╝██║██║     ██║   ██║   ██║
██║     ██║╚██╗ ██╔╝██╔══╝  ██╔═══╝ ██║██║     ██║   ██║   ██║
███████╗██║ ╚████╔╝ ███████╗██║     ██║███████╗╚██████╔╝   ██║
╚══════╝╚═╝  ╚═══╝  ╚══════╝╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/dreamrec/LivePilot/actions/workflows/ci.yml/badge.svg)](https://github.com/dreamrec/LivePilot/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/dreamrec/LivePilot)](https://github.com/dreamrec/LivePilot/stargazers)
[![npm](https://img.shields.io/npm/v/livepilot)](https://www.npmjs.com/package/livepilot)

**AI copilot for Ableton Live 12** — 155 MCP tools, a deep device knowledge corpus, real-time audio analysis, generative algorithms, neo-Riemannian harmony, MIDI file I/O, and persistent technique memory.

Most Ableton MCP servers give the AI tools to push buttons. LivePilot gives it three things on top of that:

- **Knowledge** — A device atlas of 280+ instruments, 139 drum kits, and 350+ impulse responses. The AI doesn't guess device names or parameters. It looks them up.
- **Perception** — An M4L analyzer that reads the master bus in real-time: 8-band spectrum, RMS/peak metering, pitch tracking, key detection. The AI makes decisions based on what it hears, not just what's configured.
- **Memory** — A technique library that persists across sessions. The AI remembers how you built that bass sound, what swing you like on hi-hats, which reverb chain worked on vocals. It learns your taste over time.

These three layers sit on top of 155 deterministic MCP tools that cover transport, tracks, clips, MIDI, devices, scenes, mixing, browser, arrangement, sample manipulation, generative algorithms, neo-Riemannian harmony, and MIDI file I/O. Every command goes through Ableton's official Live Object Model API — the same interface Ableton's own control surfaces use. Everything is reversible with undo.

---

## The Three Layers

Most MCP servers are a flat list of tools. LivePilot is a production system with three layers that work together.

### 1. Device Atlas — What the AI knows

A structured knowledge corpus of 280+ Ableton devices, 139 drum kits, and 350+ impulse responses. When the AI needs to load an instrument, it doesn't hallucinate a name and hope for the best. It consults the atlas, finds the exact preset, and loads it by URI.

The atlas is organized by category (synths, drums, effects, samples) with metadata about each device: what it sounds like, what parameters matter, what presets are available. When you say "load something warm and analog", the AI can search the atlas for instruments tagged with those qualities and pick one that actually exists in your library.

This is the difference between an AI that says "I'll load Warm Analog Pad" (and crashes because it doesn't exist) and one that searches the drum kit index, finds "Kit-606 Tape.adg", and loads it by its real browser URI.

### 2. Analyzer — What the AI hears

The LivePilot Analyzer is an M4L device that sits on the master track and feeds real-time audio data back to the AI:

- **8-band spectrum** — sub, low, low-mid, mid, high-mid, high, presence, air
- **RMS and peak metering** — true loudness, not just parameter values
- **Pitch tracking and key detection** — Krumhansl-Schmuckler algorithm on accumulated pitch data

This means the AI can verify its own work. After adding an EQ cut at 400 Hz, it reads the spectrum to confirm the cut actually reduced the mud. After loading a bass preset, it checks that the low end is present. Before writing a bass line, it detects the key of what's already playing.

Without the analyzer, the AI is working blind — it can set parameters but can't hear the result. With it, the AI closes the feedback loop.

### 3. Technique Memory — What the AI learns

The memory system (`memory_learn` / `memory_recall` / `memory_replay`) stores production decisions as structured, searchable, replayable data. Not just parameter snapshots — the full context: what genre, what mood, what made it work, what the signal chain was, what MIDI pattern drove it.

Five technique types: `beat_pattern`, `device_chain`, `mix_template`, `preference`, `browser_pin`. Each stores three layers of data:

| Layer | Contents | Purpose |
|-------|----------|---------|
| **Identity** | UUID, name, type, tags, timestamps, rating | Indexing and filtering |
| **Qualities** | Mood, genre, rhythm feel, harmonic character, sonic texture, production notes | Search ranking and creative context |
| **Payload** | Raw MIDI notes, device params, tempo, kit URIs, send levels | Exact replay or adaptation |

The agent consults memory by default before creative decisions. `memory_recall(query="dark heavy 808")` matches against mood, genre, and texture — not just names. The results inform the AI's choices without constraining them. Say "ignore my history" and it works from a clean slate. Say "use that boom bap beat from last session" and it pulls the exact technique and replays it.

Over time, the library becomes a structured representation of your production taste: swing ranges, kit preferences, harmonic tendencies, arrangement density. The AI reads across this at decision time. New output is always generated; the memory shapes the generation.

### How the layers combine

"Make a boom bap beat at 86 BPM" triggers the full stack:

1. **Atlas** — finds the right drum kit (not a guess, a real preset with real samples)
2. **Memory** — recalls your previous boom bap patterns, checks your preferred swing amount and velocity curves
3. **Tools** — creates tracks, loads instruments, programs MIDI, chains effects, sets levels
4. **Analyzer** — reads the spectrum to verify the kick sits right, detects the key for the bass line, checks RMS to balance levels

No other Ableton MCP server does this. Others have tools. LivePilot has tools + knowledge + perception + memory.

---

## Automation Intelligence

Most DAW integrations let the AI set a parameter to a value. LivePilot lets the AI write **automation curves** — envelopes that evolve parameters over time inside clips. This is the difference between a static mix and a living one.

### The Curve Engine

16 mathematically precise curve types, organized in 4 categories:

| Category | Curves | What they do |
|----------|--------|-------------|
| **Basic Waveforms** | `linear` · `exponential` · `logarithmic` · `s_curve` · `sine` · `sawtooth` · `spike` · `square` · `steps` | The building blocks. Exponential for filter sweeps (perceptually even). Logarithmic for volume fades (matches the ear). Spike for dub throws. Sawtooth for sidechain pumps. |
| **Organic / Natural** | `perlin` · `brownian` · `spring` | What makes automation feel alive. Perlin noise for drifting textures. Brownian for analog-style parameter wander. Spring for realistic knob movements with overshoot and settle. |
| **Shape Control** | `bezier` · `easing` | Precision curves for intentional design. Bezier with arbitrary control points. 8 easing types from the animation world: bounce, elastic, back overshoot, ease in/out. |
| **Algorithmic** | `euclidean` · `stochastic` | Generative intelligence. Euclidean distributes automation events using the Bjorklund algorithm (the same math behind Euclidean rhythms). Stochastic applies Xenakis-inspired controlled randomness within narrowing bounds. |

Every curve generates normalized points (0.0–1.0) that map to any parameter in Ableton — volume, pan, sends, device parameters, anything with an envelope.

### 15 Production Recipes

Named presets for common techniques. One tool call instead of manual point calculation:

| Recipe | Curve | What it does |
|--------|-------|-------------|
| `filter_sweep_up` | exponential | LP filter opening over 8-32 bars |
| `filter_sweep_down` | logarithmic | LP filter closing, mirrors the sweep up |
| `dub_throw` | spike | Instant send spike for reverb/delay throws |
| `tape_stop` | exponential | Pitch dropping to zero — steep deceleration |
| `build_rise` | exponential | Tension build on HP filter + volume + reverb |
| `sidechain_pump` | sawtooth | Volume ducking per beat — fast duck, slow recovery |
| `fade_in` / `fade_out` | log / exp | Perceptually smooth volume fades |
| `tremolo` | sine | Periodic volume oscillation |
| `auto_pan` | sine | Stereo movement via pan |
| `stutter` | square | Rapid on/off gating |
| `breathing` | sine | Subtle filter movement — acoustic instrument feel |
| `washout` | exponential | Reverb/delay feedback increasing to wash |
| `vinyl_crackle` | sine | Slow bit reduction for lo-fi character |
| `stereo_narrow` | exponential | Collapse stereo to mono before drop |

### The Feedback Loop

`analyze_for_automation` reads the spectrum and device chain, then suggests what to automate:

1. **Reads the spectrum** — identifies frequency balance, sub content, dynamic range
2. **Scans the device chain** — detects filters, reverbs, synths, distortion
3. **Suggests automation targets** — "Filter detected → automate cutoff for movement", "Heavy sub content → HP filter sweep for builds"
4. **Recommends recipes** — maps each suggestion to the right named recipe

The AI doesn't just write automation — it knows what to automate based on what it hears.

---

## What You Can Do

- **Produce** — Create tracks, load instruments from the atlas, program drum patterns, bass lines, chord progressions, and melodies — informed by your saved techniques
- **Arrange** — Build full song structures in arrangement view with MIDI editing, cue points, automation, and timeline navigation
- **Design sounds** — Browse Ableton's library, load presets, tweak every device parameter, chain effects, walk nested racks 6 levels deep
- **Mix with ears** — Set levels, panning, sends, and routing. Read the spectrum, check RMS, detect the key. The analyzer tells the AI what changed, not just what was set
- **Automate intelligently** — Write clip automation with 16 mathematically precise curve types, apply named recipes (dub throws, filter sweeps, sidechain pumps), get spectral-aware suggestions for what to automate next
- **Remember and evolve** — Save techniques, build a personal style library, replay past decisions exactly or as variations
- **Chop samples** — Load audio into Simpler, slice, reverse, crop, warp, and reprogram — all from conversation
- **Iterate fast** — Transpose, humanize, quantize, duplicate, and reshape patterns through conversation

---

## Quick Start

### 1. Install the Remote Script

```bash
npx -y github:dreamrec/LivePilot --install
```

### 2. Enable in Ableton

Restart Ableton Live, then go to **Preferences > Link, Tempo & MIDI > Control Surface** and select **LivePilot**.

### 3. Add to your MCP client

<details open>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add LivePilot -- npx -y github:dreamrec/LivePilot
```

Or add to `.mcp.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

**Optional:** Install the Claude Code plugin for skills, slash commands, and the producer agent:

```bash
claude plugin add github:dreamrec/LivePilot/plugin
```

</details>

<details>
<summary><strong>Claude Desktop (macOS)</strong></summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

Restart Claude Desktop after saving.

</details>

<details>
<summary><strong>Claude Desktop (Windows)</strong></summary>

On Windows, `npx` can cause EBUSY file-locking errors. Install globally instead:

```cmd
npm install -g github:dreamrec/LivePilot
livepilot --install
```

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "livepilot"
    }
  }
}
```

Restart Claude Desktop after saving.

</details>

<details>
<summary><strong>Cursor</strong></summary>

Open Cursor Settings > MCP Servers > Add Server, then use:

- **Name:** LivePilot
- **Command:** `npx -y github:dreamrec/LivePilot`

Or add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

</details>

<details>
<summary><strong>VS Code (Copilot)</strong></summary>

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

</details>

<details>
<summary><strong>Windsurf</strong></summary>

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

</details>

### 4. Verify connection

```bash
npx -y github:dreamrec/LivePilot --status
```

---

## 155 Tools Across 16 Domains

| Domain | Tools | What you can do |
|--------|:-----:|-----------------|
| **Transport** | 12 | Play/stop, tempo, time signature, loop, undo/redo, metronome, diagnostics |
| **Tracks** | 14 | Create MIDI/audio/return tracks, name, color, mute, solo, arm, group fold, input monitoring |
| **Clips** | 11 | Create, delete, duplicate, fire, stop, loop settings, launch mode, warp mode |
| **Notes** | 8 | Add/get/remove/modify MIDI notes, transpose, quantize, duplicate |
| **Devices** | 12 | Load instruments & effects, tweak parameters, rack chains, presets — works on regular, return, and master tracks |
| **Scenes** | 8 | Create, delete, duplicate, fire, rename, color, per-scene tempo |
| **Mixing** | 11 | Volume, pan, sends, routing, meters, mix snapshot — return tracks and master fully supported |
| **Browser** | 4 | Search Ableton's library, browse categories, load presets |
| **Arrangement** | 19 | Create clips, full MIDI note CRUD, cue points, recording, automation |
| **Automation** | 8 | Clip envelope CRUD, 16-type curve engine, 15 named recipes, spectral-aware suggestions |
| **Memory** | 8 | Save, recall, replay, and manage production techniques |
| **Analyzer** | 20 | Real-time spectral analysis, key detection, sample manipulation, warp markers, device introspection (requires M4L device) |
| **Theory** | 7 | Harmony analysis, Roman numerals, scale identification, chord suggestions, countermelody, SATB harmonization, smart transposition |
| **Generative** | 5 | Euclidean rhythms (Bjorklund), polyrhythmic layering, Pärt tintinnabuli, Reich phase shift, Glass additive process |
| **Harmony** | 4 | Tonnetz navigation, voice leading paths, neo-Riemannian classification, chromatic mediants |
| **MIDI I/O** | 4 | Export clips to .mid, import .mid files, offline MIDI analysis, piano roll extraction |

<details>
<summary><strong>Full tool list</strong></summary>

### Transport (12)
`get_session_info` · `set_tempo` · `set_time_signature` · `start_playback` · `stop_playback` · `continue_playback` · `toggle_metronome` · `set_session_loop` · `undo` · `redo` · `get_recent_actions` · `get_session_diagnostics`

### Tracks (14)
`get_track_info` · `create_midi_track` · `create_audio_track` · `create_return_track` · `delete_track` · `duplicate_track` · `set_track_name` · `set_track_color` · `set_track_mute` · `set_track_solo` · `set_track_arm` · `stop_track_clips` · `set_group_fold` · `set_track_input_monitoring`

### Clips (11)
`get_clip_info` · `create_clip` · `delete_clip` · `duplicate_clip` · `fire_clip` · `stop_clip` · `set_clip_name` · `set_clip_color` · `set_clip_loop` · `set_clip_launch` · `set_clip_warp_mode`

### Notes (8)
`add_notes` · `get_notes` · `remove_notes` · `remove_notes_by_id` · `modify_notes` · `duplicate_notes` · `transpose_notes` · `quantize_clip`

### Devices (12)
`get_device_info` · `get_device_parameters` · `set_device_parameter` · `batch_set_parameters` · `toggle_device` · `delete_device` · `load_device_by_uri` · `find_and_load_device` · `get_rack_chains` · `set_simpler_playback_mode` · `set_chain_volume` · `get_device_presets`

### Scenes (8)
`get_scenes_info` · `create_scene` · `delete_scene` · `duplicate_scene` · `fire_scene` · `set_scene_name` · `set_scene_color` · `set_scene_tempo`

### Mixing (11)
`set_track_volume` · `set_track_pan` · `set_track_send` · `get_return_tracks` · `get_master_track` · `set_master_volume` · `get_track_routing` · `set_track_routing` · `get_track_meters` · `get_master_meters` · `get_mix_snapshot`

### Browser (4)
`get_browser_tree` · `get_browser_items` · `search_browser` · `load_browser_item`

### Arrangement (19)
`get_arrangement_clips` · `create_arrangement_clip` · `add_arrangement_notes` · `get_arrangement_notes` · `remove_arrangement_notes` · `remove_arrangement_notes_by_id` · `modify_arrangement_notes` · `duplicate_arrangement_notes` · `transpose_arrangement_notes` · `set_arrangement_clip_name` · `set_arrangement_automation` · `back_to_arranger` · `jump_to_time` · `capture_midi` · `start_recording` · `stop_recording` · `get_cue_points` · `jump_to_cue` · `toggle_cue_point`

### Automation (8)
`get_clip_automation` · `set_clip_automation` · `clear_clip_automation` · `apply_automation_shape` · `apply_automation_recipe` · `get_automation_recipes` · `generate_automation_curve` · `analyze_for_automation`

### Memory (8)
`memory_learn` · `memory_recall` · `memory_get` · `memory_replay` · `memory_list` · `memory_favorite` · `memory_update` · `memory_delete`

### Analyzer (20) — requires LivePilot Analyzer M4L device on master track
`get_master_spectrum` · `get_master_rms` · `get_detected_key` · `get_hidden_parameters` · `get_automation_state` · `walk_device_tree` · `get_clip_file_path` · `replace_simpler_sample` · `load_sample_to_simpler` · `get_simpler_slices` · `crop_simpler` · `reverse_simpler` · `warp_simpler` · `get_warp_markers` · `add_warp_marker` · `move_warp_marker` · `remove_warp_marker` · `scrub_clip` · `stop_scrub` · `get_display_values`

### Theory (7)
`analyze_harmony` · `suggest_next_chord` · `detect_theory_issues` · `identify_scale` · `harmonize_melody` · `generate_countermelody` · `transpose_smart`

### Generative (5)
`generate_euclidean_rhythm` · `layer_euclidean_rhythms` · `generate_tintinnabuli` · `generate_phase_shift` · `generate_additive_process`

### Harmony (4)
`navigate_tonnetz` · `find_voice_leading_path` · `classify_progression` · `suggest_chromatic_mediants`

### MIDI I/O (4)
`export_clip_midi` · `import_midi_to_clip` · `analyze_midi_file` · `extract_piano_roll`

</details>

---

## Plugin

The plugin adds a skill, an autonomous agent, and 5 slash commands on top of the MCP tools.

```bash
claude plugin add github:dreamrec/LivePilot/plugin
```

### Commands

| Command | Description |
|---------|-------------|
| `/session` | Full session overview with diagnostics |
| `/beat` | Guided beat creation — genre, tempo, instrumentation |
| `/mix` | Mixing assistant — levels, panning, sends |
| `/sounddesign` | Sound design workflow — instruments, effects, presets |
| `/memory` | Browse, search, and manage your technique library |

### Producer Agent

Autonomous agent that handles multi-step production tasks end-to-end. "Make a lo-fi hip hop beat at 75 BPM" triggers a full pipeline: consult the technique memory for style context, search the device atlas for the right drum kit and instruments, create tracks, program MIDI, chain effects, set levels — then read the spectrum through the analyzer to verify everything sounds right.

The agent ships with a 2,700-line reference corpus (drum patterns, chord voicings, sound design recipes, mixing templates) and consults the technique memory by default. Mandatory health checks between each stage verify every track produces audible output — the analyzer confirms what the meters suggest.

### Core Skill

`livepilot-core` encodes the operational discipline that connects all three layers. It teaches the AI to consult the device atlas before loading instruments, read the analyzer after mixing moves, check technique memory before creative decisions, and verify every mutation through state reads. It enforces the rules that prevent silent failures: never load empty Drum Racks, never hallucinate device names, always verify audio output. Without it, an LLM with access to the tools will produce silent tracks and load wrong devices.

---

## M4L Analyzer

The LivePilot Analyzer (`LivePilot_Analyzer.amxd`) gives the AI ears. Drop it on the master track and 20 additional tools unlock: 8-band spectral analysis, RMS/peak metering, Krumhansl-Schmuckler key detection, plus deep LOM access for sample manipulation, warp markers, device introspection, and human-readable parameter display values.

All 115 core tools work without it. The analyzer is what turns LivePilot from a remote control into a feedback loop — the AI can set an EQ curve and then read the spectrum to verify the result.

---

## The Landscape

There are **15+ MCP servers for Ableton Live** as of March 2026. Here's how the major ones compare:

### At a Glance

| | [LivePilot](https://github.com/dreamrec/LivePilot) | [AbletonMCP](https://github.com/ahujasid/ableton-mcp) | [MCP Extended](https://github.com/uisato/ableton-mcp-extended) | [Ableton Copilot](https://github.com/xiaolaa2/ableton-copilot-mcp) | [AbletonBridge](https://github.com/hidingwill/AbletonBridge) | [Producer Pal](https://github.com/adamjmurray/producer-pal) |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| **Tools** | 155 | ~20 | ~35 | ~45 | 322 | ~25 |
| **Device knowledge** | 280+ devices | -- | -- | -- | -- | -- |
| **Audio analysis** | Spectrum/RMS/key | -- | -- | -- | Metering | -- |
| **Technique memory** | Persistent | -- | -- | -- | -- | -- |
| **Stars** | new | 2.3k | 139 | 72 | 13 | 103 |
| **Language** | Python | Python | Python | TypeScript | Python | TypeScript |
| **Active** | Yes | Slow | Yes | Yes | Yes | Yes |

### Feature Comparison

| Capability | LivePilot | AbletonMCP | Extended | Copilot | Bridge | Producer Pal |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Transport | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tracks (MIDI/audio/return) | ✅ | Partial | ✅ | ✅ | ✅ | ✅ |
| Session clips | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Arrangement view** | ✅ | — | — | ✅ | ? | ? |
| **Arrangement automation** | ✅ | — | — | — | ? | — |
| **Clip automation (envelopes)** | ✅ | — | — | — | — | — |
| **Automation curve engine** | ✅ | — | — | — | — | — |
| MIDI notes (add/get) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **MIDI notes (modify/delete by ID)** | ✅ | — | — | ✅ | ? | — |
| **Per-note probability** | ✅ | — | — | — | — | — |
| Device loading | ✅ | ✅ | ✅ | ✅ | ✅ | ? |
| Device parameters | ✅ | Basic | ✅ | ✅ | ✅ | ? |
| **Batch parameter editing** | ✅ | — | — | — | ? | — |
| **Rack chains** | ✅ | — | — | — | ✅ | — |
| Browser (tree/search/URI) | ✅ | Basic | ✅ | ✅ | ✅ | — |
| **Plugin browser (AU/VST)** | ✅ | — | — | — | ? | — |
| Mixing (vol/pan/sends) | ✅ | Basic | ✅ | Basic | ✅ | ? |
| **Master track control** | ✅ | — | — | — | ✅ | — |
| Scenes | ✅ | — | ✅ | ? | ✅ | ✅ |
| **Undo wrapping** | ✅ | — | Partial | — | ? | — |
| **Session diagnostics** | ✅ | — | — | — | — | — |
| **Technique memory** | ✅ | — | — | — | — | — |
| **AI plugin (skills/agent)** | ✅ | — | — | — | — | — |
| **Device Atlas (built-in)** | ✅ | — | — | — | — | — |
| **Auto-detect installer** | ✅ | — | — | ✅ | — | — |
| Snapshots/rollback | — | — | — | ✅ | — | — |
| Voice generation | — | — | — | — | ✅ | — |
| **Real-time DSP analysis** | ✅ | — | — | — | ✅ | — |
| M4L-native install | — | — | — | — | — | ✅ |
| Multi-LLM support | Any MCP | Claude | Claude | Any MCP | Any MCP | Multi |

### Also Notable

- **[Simon-Kansara](https://github.com/Simon-Kansara/ableton-live-mcp-server)** (369★) — OSC-based, exhaustive address mapping, inactive since 2025
- **[jpoindexter](https://github.com/jpoindexter/ableton-mcp)** — 200+ tools, triple interface (MCP + REST + M4L), 13 scales
- **[cafeTechne](https://github.com/cafeTechne/ableton-11-mcp-for-windows-codex-and-antigravity)** — 220+ tools, Windows/Codex optimized, Live 11 focused
- **[FabianTinkl](https://github.com/FabianTinkl/AbletonMCP)** — AI-powered chord/melody generation, genre-specific composition
- **[nozomi-koborinai](https://github.com/nozomi-koborinai/ableton-osc-mcp)** — Only Go implementation, uses Google Genkit

### Where LivePilot Fits

Every server on this list gives the AI tools to control Ableton. LivePilot is the only one that also gives it **knowledge** (device atlas with 280+ devices, 139 kits, 350+ IRs), **perception** (real-time spectrum, RMS, key detection from the M4L analyzer), and **memory** (persistent technique library that accumulates production decisions across sessions).

The practical difference: other servers let the AI set a parameter. LivePilot lets the AI choose the right parameter based on what device is loaded (atlas), verify the result by reading the audio output (analyzer), and remember the technique for next time (memory).

AbletonBridge has more raw tools (322 vs 155). Producer Pal has the easiest install (drag a .amxd). The original AbletonMCP has the community (2.3k stars). LivePilot has the deepest integration — tools that execute, knowledge that informs, perception that verifies, and memory that accumulates.

---

## Architecture

```
AI Client
       │ MCP Protocol (stdio)
       ▼
┌─────────────────────┐
│   MCP Server        │  Python (FastMCP)
│   mcp_server/       │  Input validation, auto-reconnect
└────────┬────────────┘
         │ JSON over TCP (port 9878)
         ▼
┌─────────────────────┐
│   Remote Script     │  Runs inside Ableton's Python
│   remote_script/    │  Thread-safe command queue
│   LivePilot/        │  ControlSurface base class
└─────────────────────┘
```

All commands execute on Ableton's main thread via `schedule_message` — the same thread that handles the UI. This guarantees consistency with what you see on screen. Single-client TCP by design, because Ableton's Live Object Model is not thread-safe.

**Structured errors** with codes (`INDEX_ERROR`, `NOT_FOUND`, `INVALID_PARAM`, `STATE_ERROR`, `TIMEOUT`, `INTERNAL`) so the AI can understand what went wrong and recover.

---

## Compatibility

| | Live 12 (all editions) | Suite only |
|---|:---:|:---:|
| Transport, tracks, clips, scenes, mixing | Yes | — |
| MIDI notes (add, modify, remove, probability) | Yes | — |
| Device parameters, effects, browser | Yes | — |
| Arrangement (clips, notes, cue points) | Yes | — |
| Stock instruments (Drift, Meld, Wavetable) | — | Yes |
| Max for Live devices | — | Yes |
| Third-party VST/AU plugins | Yes | — |

**Requirements:** Ableton Live 12 · Python 3.9+ · Node.js 18+

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

---

## Documentation

**[Read the full manual](docs/manual/index.md)** — Getting started, tool reference, production workflows, MIDI programming, sound design, mixing, and troubleshooting.

---

## Development

```bash
git clone https://github.com/dreamrec/LivePilot.git
cd LivePilot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest tests/ -v
```

## Contributing

Contributions welcome. Please [open an issue](https://github.com/dreamrec/LivePilot/issues) first to discuss what you'd like to change.

## License

[MIT](LICENSE) — Pilot Studio

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

**AI copilot for Ableton Live 12** — 104 MCP tools for music production, sound design, and mixing.

Talk to your DAW. Create tracks, program MIDI, load instruments, tweak parameters, arrange songs, and mix — all through natural language. LivePilot connects any MCP-compatible AI client (Claude, Cursor, VS Code Copilot) to Ableton Live and gives it full control over your session.

Every command goes through Ableton's official Live Object Model API. No hacks, no injection — the same interface Ableton's own control surfaces use. Everything is deterministic and reversible with undo.

---

## Agent & Technique Memory

LivePilot is stateless by default — 104 tools, deterministic execution, no hidden context. The agent layer adds **persistent state** on top: a technique memory system that stores production decisions as typed, searchable, replayable data structures with structured metadata.

### How it works

The memory system stores five technique types: `beat_pattern`, `device_chain`, `mix_template`, `preference`, and `browser_pin`. Each technique consists of three layers:

| Layer | Contents | Purpose |
|-------|----------|---------|
| **Identity** | UUID, name, type, tags, timestamps, rating, replay count | Indexing, filtering, sorting |
| **Qualities** | Structured analysis — summary, mood, genre tags, rhythm feel, harmonic character, sonic texture, production notes, reference points | Search ranking, agent context at decision time |
| **Payload** | Raw data — MIDI notes, device params, tempo, kit URIs, send levels | Exact replay or adaptation |

When you save a technique, the agent collects raw data from Ableton using existing tools (`get_notes`, `get_device_parameters`, etc.) and writes a structured qualities analysis. The qualities are what make search useful — `memory_recall(query="dark heavy 808")` matches against mood, genre tags, sonic texture, and summary fields, not just names.

### Three operating modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Informed** (default) | Any creative task | Agent calls `memory_recall`, reads top results' qualities, lets them influence decisions (kit selection, parameter ranges, rhythmic density) without copying |
| **Fresh** | "ignore my history" / "something new" | Agent skips memory entirely — uses only the shipped reference corpus and its own knowledge |
| **Explicit recall** | "use that boom bap beat" / "load my reverb chain" | Direct retrieval via `memory_get` → `memory_replay` with `adapt=false` (exact) or `adapt=true` (variation) |

The agent consults memory by default but never constrains itself to it. Override is always one sentence away.

### Replay architecture

`memory_replay` does not execute Ableton commands directly. It returns a structured plan — an ordered list of tool calls (`search_browser`, `load_browser_item`, `create_clip`, `add_notes`, etc.) that the agent then executes through the existing MCP tools. This keeps the memory system decoupled from the Ableton connection and makes replay logic testable without a running DAW.

### Building the corpus over time

The shipped plugin includes a reference corpus (~2,700 lines): genre-specific drum patterns, chord voicings, sound design recipes, mixing templates, and workflow patterns. This is the baseline — the agent is competent from the first session.

The technique memory extends this with user-specific data. As you save techniques, rate them, and tag them, the library becomes a structured representation of your production preferences. The agent reads across saved qualities at decision time — not to copy stored patterns, but to understand tendencies: swing ranges, kit preferences, harmonic language, arrangement density. New output is always generated; the memory informs the generation.

---

## What You Can Do

- **Produce** — Create tracks, load instruments, program drum patterns, bass lines, chord progressions, and melodies
- **Arrange** — Build full song structures in arrangement view with MIDI editing, cue points, automation, and timeline navigation
- **Design sounds** — Browse Ableton's library, load presets, tweak every device parameter, chain effects
- **Mix** — Set levels, panning, sends, and routing across all track types including return tracks and master. Run diagnostics to catch silent tracks and stale solos
- **Remember and evolve** — Save techniques, build a personal style library, and let the agent learn your taste over time
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

## 104 Tools Across 10 Domains

| Domain | Tools | What you can do |
|--------|:-----:|-----------------|
| **Transport** | 12 | Play/stop, tempo, time signature, loop, undo/redo, metronome, diagnostics |
| **Tracks** | 14 | Create MIDI/audio/return tracks, name, color, mute, solo, arm, group fold, input monitoring |
| **Clips** | 11 | Create, delete, duplicate, fire, stop, loop settings, launch mode, warp mode |
| **Notes** | 8 | Add/get/remove/modify MIDI notes, transpose, quantize, duplicate |
| **Devices** | 12 | Load instruments & effects, tweak parameters, rack chains, presets — works on regular, return, and master tracks |
| **Scenes** | 8 | Create, delete, duplicate, fire, rename, color, per-scene tempo |
| **Mixing** | 8 | Volume, pan, sends, routing — return tracks and master fully supported |
| **Browser** | 4 | Search Ableton's library, browse categories, load presets |
| **Arrangement** | 19 | Create clips, full MIDI note CRUD, cue points, recording, automation |
| **Memory** | 8 | Save, recall, replay, and manage production techniques |

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

### Mixing (8)
`set_track_volume` · `set_track_pan` · `set_track_send` · `get_return_tracks` · `get_master_track` · `set_master_volume` · `get_track_routing` · `set_track_routing`

### Browser (4)
`get_browser_tree` · `get_browser_items` · `search_browser` · `load_browser_item`

### Arrangement (19)
`get_arrangement_clips` · `create_arrangement_clip` · `add_arrangement_notes` · `get_arrangement_notes` · `remove_arrangement_notes` · `remove_arrangement_notes_by_id` · `modify_arrangement_notes` · `duplicate_arrangement_notes` · `transpose_arrangement_notes` · `set_arrangement_clip_name` · `set_arrangement_automation` · `back_to_arranger` · `jump_to_time` · `capture_midi` · `start_recording` · `stop_recording` · `get_cue_points` · `jump_to_cue` · `toggle_cue_point`

### Memory (8)
`memory_learn` · `memory_recall` · `memory_get` · `memory_replay` · `memory_list` · `memory_favorite` · `memory_update` · `memory_delete`

</details>

---

## Claude Code Plugin

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

Autonomous agent that executes multi-step production tasks from high-level descriptions. Handles the full pipeline: session planning, track creation, instrument loading, MIDI programming, effect configuration, and mixing — with mandatory health checks between each stage to verify every track produces audible output.

The agent ships with a 2,700-line reference corpus covering genre-specific drum patterns, chord voicings, sound design parameter recipes, mixing templates, and song structures. It consults the technique memory by default (see above), and can be overridden to work from a clean slate.

### Core Skill

`livepilot-core` encodes operational discipline for the 104 tools: read state before writing, verify after every mutation, validate instrument loading (empty Drum Racks produce silence), never hallucinate device names (always `search_browser` first), use negative track indices for return tracks. Without it, an LLM with access to the tools will produce silent tracks and load wrong devices.

---

## How It Compares

| Feature | LivePilot | [AbletonMCP](https://github.com/ahujasid/ableton-mcp) | [Ableton MCP Extended](https://github.com/uisato/ableton-mcp-extended) |
|---------|:---------:|:---------:|:---------:|
| **Tools** | 104 | ~20 | ~50 |
| **Arrangement view** | Full (clips, notes, cue points, automation) | No | Partial (automation "not perfect yet") |
| **MIDI note editing** | Full CRUD with note IDs, probability, velocity deviation | Basic add/get | Add/get/modify |
| **Device control** | Load, params, batch edit, rack chains, presets, Simpler modes | Load, basic params | Load, params |
| **Browser search** | Tree navigation, path filtering, URI-based loading | Basic search | Search with categories |
| **Mixing** | Volume, pan, sends, routing, master, diagnostics | Volume, pan | Volume, pan, sends |
| **Undo support** | Full (begin/end_undo_step wrapping) | No | Partial |
| **Session diagnostics** | Built-in health checks (armed tracks, solos, silent tracks) | No | No |
| **Per-note probability** | Yes (Live 12 API) | No | No |
| **Plugin/skills** | Claude Code plugin with 5 commands + producer agent | No | No |
| **Voice generation** | No | No | Yes (ElevenLabs) |
| **UDP low-latency mode** | No (TCP, reliable) | No | Yes (experimental) |
| **Protocol** | JSON/TCP, single-client, structured errors | JSON/TCP | JSON/TCP + UDP |
| **Installation** | Auto-detect CLI (`--install`) | Manual copy | Manual copy |
| **Live version** | Live 12 (modern note API) | Live 11+ | Live 11+ |
| **License** | MIT | MIT | MIT |

LivePilot focuses on **comprehensive, deterministic control** with safety nets (undo wrapping, diagnostics, verification patterns). It trades real-time parameter streaming (Extended's UDP mode) and external service integration (Extended's ElevenLabs) for deeper coverage of Ableton's core operations — especially arrangement, device management, and MIDI editing with Live 12's modern note API.

---

## Architecture

```
Claude / AI Client
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

**Requirements:** Ableton Live 12 · Python 3.10+ · Node.js 18+

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

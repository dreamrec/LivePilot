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

## Train Your Own AI Producer

LivePilot ships with 104 tools and a deep reference corpus — genre-specific drum patterns, chord voicings, sound design recipes, mixing templates, song structures. Day one, it already knows how music works. But the tools are just the starting point.

**The real product is the agent you build on top of them.**

Every producer has a sonic identity — the swing amounts they reach for, the drum kits that feel right, the FX chains they keep coming back to, the way they EQ a vocal bus. Most AI tools ignore all of this. Every session starts blank. LivePilot is different: it has a technique memory system that turns your production decisions into a persistent, searchable stylistic palette the agent learns from over time.

Here's how you train it:

1. **Produce something you like** — a beat, a device chain, a mixing setup, a synth patch
2. **Tell the agent to save it** — "remember this groove" / "save this reverb chain"
3. **The agent writes a stylistic analysis** — not just raw MIDI data, but *what makes it work*: the rhythmic feel, the sonic texture, the mood, what it pairs with, what artists it evokes
4. **Your library grows** — rate and favorite the best techniques, tag them by genre or mood, build categories
5. **The agent develops taste** — next time you say "make me a beat", it checks your library, reads your tendencies, and creates something new that sounds like you

This isn't a preset recall system. The agent doesn't copy stored patterns — it understands the *qualities* across your saved techniques (the swing you prefer, the harmonic language you gravitate toward, the density of your arrangements) and uses that understanding to inform new creative decisions.

**Three modes, always under your control:**

- **Informed** (default) — the agent consults your memory and lets it influence creative choices naturally
- **Fresh** — "ignore my history" / "something completely new" — blank slate, pure musical knowledge, zero influence from saved techniques
- **Explicit recall** — "use that boom bap beat I saved" — direct retrieval and replay

The memory is both a drawer and a personality. You put things in, you take things out, and the agent develops taste from what you've collected — but you can always tell it to forget everything and start fresh.

**You're not configuring software. You're building a creative partner that gets better the more you use it.**

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

The plugin turns LivePilot from a tool collection into a **production partner that learns your style**.

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
| `/memory` | Browse, search, and manage your saved technique library |

### The Producer Agent

The heart of the plugin. An autonomous agent that builds tracks from high-level descriptions like *"Make me a 126 BPM rominimal track in D minor with hypnotic percussion"*. It handles the full pipeline: planning the arrangement, creating tracks, loading instruments, programming patterns, adding effects, and mixing — with mandatory health checks to make sure every track actually produces sound.

What makes it different from a generic AI with tools is **what it knows**. The agent ships with a deep reference corpus — genre-specific drum patterns, chord voicings, sound design recipes, mixing templates, song structures — so it doesn't start from zero every time. It knows that a boom bap kick lands on beat 1 and the "and" of 2, that a Drum Rack needs a kit preset (not an empty shell), that a Saturator with Drive at 0 is a pass-through doing nothing.

But the shipped corpus is just the floor. The real value builds over time.

### Technique Memory

8 tools for saving, searching, and replaying production techniques. Every saved technique includes a rich stylistic analysis written by the agent — not just raw data, but *what makes it work* and when to use it. See "Train Your Own AI Producer" above for how this shapes the agent over time.

### Core Skill

The `livepilot-core` skill teaches the AI how to work with Ableton properly: read session state before changing anything, verify after every write, check that instruments actually loaded, never invent device names. It's the difference between an AI that fumbles through the API and one that works like an experienced assistant.

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

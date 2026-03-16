# LivePilot — Ableton Live 12 AI Copilot

**Design Spec v1.0 | 2026-03-17**

Sister project to TDPilot and ComfyPilot. A complete MCP server + Claude Code plugin for controlling Ableton Live 12 through AI.

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Name | LivePilot | Matches Pilot family (TDPilot, ComfyPilot) |
| Relationship | Sister project — separate repo, shared branding | Same pattern as ComfyPilot |
| Target | Ableton Live 12 minimum | Modern note API (note IDs, probability, velocity_deviation), cleaner code |
| Architecture | Modular Remote Script + Smart MCP Server | Clean separation, testable domains, extensible |
| Tool count | 76 across 9 domains | Covers real production workflows without bloat |
| Knowledge | Skill references (markdown corpus) | Proven pattern from TDPilot, works everywhere |
| Distribution | `npx livepilot` + `npx livepilot --install` | npm package spawns Python MCP server; installer auto-detects Ableton path |
| Plugin | Claude Code plugin with skills, commands, agent | Full plugin like TDPilot |
| Port | 9878 | Distinct from old ableton-mcp (9877), avoids conflicts |
| Protocol | JSON over TCP, newline-delimited, request IDs | Structured errors, correlatable responses |
| License | MIT | Open source |

---

## Architecture

### System Diagram

```
Claude Code / AI Client
       │
       │ MCP Protocol (stdio)
       ▼
┌─────────────────────┐
│   MCP Server        │  Python (FastMCP)
│   mcp_server/       │  - Input validation
│   - tools/          │  - Compound operations
│   - connection.py   │  - Auto-reconnect
└────────┬────────────┘
         │ JSON over TCP (port 9878, newline-delimited)
         ▼
┌─────────────────────┐
│   Remote Script     │  Runs inside Ableton's Python
│   remote_script/    │  - Thread-safe command queue
│   LivePilot/        │  - Main-thread API execution
│   - 9 domain modules│  - ControlSurface base class
└────────┬────────────┘
         │ Live Object Model (LOM)
         ▼
┌─────────────────────┐
│   Ableton Live 12   │
└─────────────────────┘
```

### Thread Safety Model

```
Socket Thread (background)         Main Thread (Ableton)
──────────────────────────         ─────────────────────
recv JSON line            →
parse + validate          →
put (cmd, resp_queue)
  into command_queue      →        schedule_message(0, process_next)
                                   pop from command_queue
wait on resp_queue        ←        execute Live API call
                          ←        put result in resp_queue
send JSON response        ←
```

- ALL commands (read and write) route through command_queue → main thread → response_queue. The Live Object Model is NOT thread-safe — accessing any LOM property from a background thread can crash Ableton or return corrupt data. No exceptions.
- 10s timeout on response_queue.get() — returns TIMEOUT error if Ableton hangs

### Connection Lifecycle

The Remote Script's TCP server accepts one client at a time. Key lifecycle events:

- **Ableton restart / Live Set switch:** Remote Script re-initializes, TCP server restarts on same port. MCP server detects socket close, reconnects on next tool call.
- **MCP server restart:** Remote Script's client handler sees socket close, cleans up, returns to accept loop. No Ableton restart needed.
- **Ableton crash:** MCP server gets ConnectionResetError, sets socket to None, reconnects when Ableton is back.
- **Stale connection detection:** Before each command, MCP server sends a lightweight `ping` command (returns `{"pong": true}`). If ping fails → reconnect once → retry original command → fail if still broken.

### Protocol Format

```json
// Request
{"id": "abc123", "type": "set_tempo", "params": {"tempo": 140}}

// Success
{"id": "abc123", "status": "success", "result": {"tempo": 140.0}}

// Error
{"id": "abc123", "status": "error", "error": "Track index out of range", "code": "INDEX_ERROR"}
```

Error codes: `INDEX_ERROR`, `NOT_FOUND`, `INVALID_PARAM`, `STATE_ERROR`, `TIMEOUT`, `INTERNAL`

---

## Project Structure

```
LivePilot/
├── package.json                     # npx livepilot entry
├── bin/
│   └── livepilot.js                 # CLI: start server, --install, --status
├── installer/
│   ├── install.js                   # Detect OS + Ableton version, copy Remote Script
│   └── paths.js                     # Known Ableton Remote Script paths
├── remote_script/
│   └── LivePilot/                   # Copied to Ableton's Remote Scripts/
│       ├── __init__.py              # Entry: create_instance(), ControlSurface boot
│       ├── server.py                # TCP socket server, thread management
│       ├── router.py                # Command type → handler dispatch + registration
│       ├── transport.py             # play, stop, tempo, loop, metronome, undo/redo
│       ├── tracks.py                # create, delete, duplicate, rename, color, mute/solo/arm
│       ├── clips.py                 # create, delete, duplicate, fire, stop, loop, launch
│       ├── notes.py                 # add, get, remove, modify, quantize, transpose
│       ├── devices.py               # load, delete, params get/set, toggle, batch set
│       ├── scenes.py                # create, delete, duplicate, fire, rename, get info
│       ├── mixing.py                # volume, pan, sends, return tracks, master, routing
│       ├── browser.py               # tree, items at path, load by URI
│       ├── arrangement.py           # arrangement clips, recording, capture, cue points
│       └── utils.py                 # Validation helpers, error formatting
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                    # FastMCP entry, lifespan, tool registration
│   ├── connection.py                # AbletonConnection: TCP socket, reconnect, send_command
│   └── tools/
│       ├── __init__.py              # Auto-import all tool modules
│       ├── transport.py             # 10 MCP tools
│       ├── tracks.py                # 12 MCP tools
│       ├── clips.py                 # 10 MCP tools
│       ├── notes.py                 # 8 MCP tools
│       ├── devices.py               # 10 MCP tools
│       ├── scenes.py                # 6 MCP tools
│       ├── mixing.py                # 8 MCP tools
│       ├── browser.py               # 4 MCP tools
│       └── arrangement.py           # 8 MCP tools
├── plugin/
│   ├── plugin.json                  # Claude Code plugin manifest
│   ├── .mcp.json                    # MCP server config
│   ├── skills/
│   │   └── livepilot-core/
│   │       ├── SKILL.md             # Core discipline + workflow guides
│   │       └── references/
│   │           ├── overview.md
│   │           ├── m4l-devices.md
│   │           ├── midi-recipes.md
│   │           ├── sound-design.md
│   │           ├── mixing-patterns.md
│   │           └── ableton-workflow.md
│   ├── commands/
│   │   ├── session.md               # /session — full session overview
│   │   ├── beat.md                  # /beat — guided beat creation
│   │   ├── mix.md                   # /mix — mixing assistant
│   │   └── sounddesign.md           # /sounddesign — sound design workflow
│   ├── agents/
│   │   └── livepilot-producer/
│   │       └── AGENT.md             # Autonomous production agent
│   ├── README.md
│   └── CHANGELOG.md
├── tests/
│   ├── test_tools_contract.py       # Verify all 76 tools match expected signatures
│   ├── test_connection.py           # Mock socket tests
│   └── test_installer.py            # Path detection tests
├── README.md
├── CHANGELOG.md
└── LICENSE
```

---

## Tool Set — 76 Tools

**Thread column:** All commands execute on Ableton's main thread via the command queue (LOM is not thread-safe). The column indicates the command category:
- **write** — state-modifying, gets 100ms settle delay + 15s timeout
- **—** — read-only, standard 10s timeout, no settle delay

Both categories go through the main thread queue. The distinction only affects timeout/delay behavior.

### Transport (10 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 1 | `get_session_info` | — | `song.*` | read |
| 2 | `set_tempo` | `tempo: float` | `song.tempo` | write |
| 3 | `set_time_signature` | `numerator: int, denominator: int` | `song.signature_*` | write |
| 4 | `start_playback` | — | `song.start_playing()` | write |
| 5 | `stop_playback` | — | `song.stop_playing()` | write |
| 6 | `continue_playback` | — | `song.continue_playing()` | write |
| 7 | `toggle_metronome` | `enabled: bool` | `song.metronome` | write |
| 8 | `set_session_loop` | `enabled: bool, start?: float, length?: float` | `song.loop, loop_start, loop_length` | write |
| 9 | `undo` | — | `song.undo()` | write |
| 10 | `redo` | — | `song.redo()` | write |

### Tracks (12 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 11 | `get_track_info` | `track_index: int` | `track.*` | read |
| 12 | `create_midi_track` | `index?: int, name?: str, color?: int` | `song.create_midi_track()` | write |
| 13 | `create_audio_track` | `index?: int, name?: str, color?: int` | `song.create_audio_track()` | write |
| 14 | `create_return_track` | — | `song.create_return_track()` | write |
| 15 | `delete_track` | `track_index: int` | `song.delete_track()` | write |
| 16 | `duplicate_track` | `track_index: int` | `song.duplicate_track()` | write |
| 17 | `set_track_name` | `track_index: int, name: str` | `track.name` | write |
| 18 | `set_track_color` | `track_index: int, color_index: int` | `track.color_index` | write |
| 19 | `set_track_mute` | `track_index: int, muted: bool` | `track.mute` | write |
| 20 | `set_track_solo` | `track_index: int, soloed: bool` | `track.solo` | write |
| 21 | `set_track_arm` | `track_index: int, armed: bool` | `track.arm` | write |
| 22 | `stop_track_clips` | `track_index: int` | `track.stop_all_clips()` | write |

### Clips (10 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 23 | `get_clip_info` | `track_index: int, clip_index: int` | `clip.*` | read |
| 24 | `create_clip` | `track_index: int, clip_index: int, length: float` | `clip_slot.create_clip()` | write |
| 25 | `delete_clip` | `track_index: int, clip_index: int` | `clip_slot.delete_clip()` | write |
| 26 | `duplicate_clip` | `track_index: int, clip_index: int, target_track: int, target_clip: int` | `clip_slot.duplicate_clip_to()` | write |
| 27 | `fire_clip` | `track_index: int, clip_index: int` | `clip_slot.fire()` | write |
| 28 | `stop_clip` | `track_index: int, clip_index: int` | `clip_slot.stop()` | write |
| 29 | `set_clip_name` | `track_index: int, clip_index: int, name: str` | `clip.name` | write |
| 30 | `set_clip_color` | `track_index: int, clip_index: int, color_index: int` | `clip.color_index` | write |
| 31 | `set_clip_loop` | `track_index: int, clip_index: int, enabled: bool, start?: float, end?: float` | `clip.looping, loop_start, loop_end` | write |
| 32 | `set_clip_launch` | `track_index: int, clip_index: int, mode: int, quantization?: int` | `clip.launch_mode, launch_quantization` | write |

### Notes — MIDI Editing (8 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 33 | `add_notes` | `track_index, clip_index, notes: [{pitch, start_time, duration, velocity, probability?, velocity_deviation?, release_velocity?}]` | `clip.add_new_notes()` | write |
| 34 | `get_notes` | `track_index, clip_index, from_pitch?: int, pitch_span?: int, from_time?: float, time_span?: float` | `clip.get_notes_extended()` | read |
| 35 | `remove_notes` | `track_index, clip_index, from_pitch?: int, pitch_span?: int, from_time?: float, time_span?: float` | `clip.remove_notes_extended()` | write |
| 36 | `remove_notes_by_id` | `track_index, clip_index, note_ids: [int]` | `clip.remove_notes_by_id()` | write |
| 37 | `modify_notes` | `track_index, clip_index, modifications: [{note_id, pitch?, start_time?, duration?, velocity?, probability?}]` | `clip.apply_note_modifications()` | write |
| 38 | `duplicate_notes` | `track_index, clip_index, note_ids: [int], time_offset?: float` | Compound: `clip.get_notes_by_id(ids)` (internal LOM call) → `clip.add_new_notes()` with offset applied to start_time | write |
| 39 | `transpose_notes` | `track_index, clip_index, semitones: int, from_time?: float, time_span?: float` | get → modify → apply | write |
| 40 | `quantize_clip` | `track_index, clip_index, grid: float, amount?: float` | `clip.quantize()` | write |

### Devices & Parameters (10 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 41 | `get_device_info` | `track_index, device_index` | `device.*` | read |
| 42 | `get_device_parameters` | `track_index, device_index` | `device.parameters[]` | read |
| 43 | `set_device_parameter` | `track_index, device_index, value, parameter_name?: str, parameter_index?: int` | `param.value` | write |
| 44 | `batch_set_parameters` | `track_index, device_index, parameters: [{name_or_index, value}]` | loop `param.value` | write |
| 45 | `toggle_device` | `track_index, device_index, active: bool` | `device.parameters[0].value` | write |
| 46 | `delete_device` | `track_index, device_index` | `track.delete_device()` | write |
| 47 | `load_device_by_uri` | `track_index, uri: str` | `browser.load_item()` | write |
| 48 | `find_and_load_device` | `track_index, device_name: str` | Compound: walk browser tree matching name → load first loadable match. Max depth 4, 5s timeout. Falls back to error with suggestions if not found. | write |
| 49 | `get_rack_chains` | `track_index, device_index` | `rack.chains[]` | read |
| 50 | `set_chain_volume` | `track_index, device_index, chain_index, volume?: float, pan?: float` | `chain.mixer_device.*` | write |

### Scenes (6 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 51 | `get_scenes_info` | — | `song.scenes[]` | — |
| 52 | `create_scene` | `index?: int` | `song.create_scene()` | write |
| 53 | `delete_scene` | `scene_index: int` | `song.delete_scene()` | write |
| 54 | `duplicate_scene` | `scene_index: int` | `song.duplicate_scene()` | write |
| 55 | `fire_scene` | `scene_index: int` | `scene.fire()` | write |
| 56 | `set_scene_name` | `scene_index: int, name: str` | `scene.name` | write |

### Mixing (8 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 57 | `set_track_volume` | `track_index, volume: float` | `mixer.volume.value` | write |
| 58 | `set_track_pan` | `track_index, pan: float` | `mixer.panning.value` | write |
| 59 | `set_track_send` | `track_index, send_index, value: float` | `mixer.sends[i].value` | write |
| 60 | `get_return_tracks` | — | `song.return_tracks[]` | — |
| 61 | `get_master_track` | — | `song.master_track` | — |
| 62 | `set_master_volume` | `volume: float` | `master.mixer_device.volume.value` | write |
| 63 | `get_track_routing` | `track_index` | `track.input/output_routing_*` | — |
| 64 | `set_track_routing` | `track_index, input_type?: str, input_channel?: str, output_type?: str, output_channel?: str` | `track.input/output_routing_*` | write |

### Browser (4 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 65 | `get_browser_tree` | `category_type?: str` | `browser.*` | — |
| 66 | `get_browser_items` | `path: str` | `browser children` | — |
| 67 | `search_browser` | `path: str, name_filter?: str, loadable_only?: bool` | Compound: navigate to path via `.children`, optionally filter items by substring match on name, return only loadable items if flag set. Max tree depth 4, 5s timeout. | — |
| 68 | `load_browser_item` | `track_index, uri: str` | `browser.load_item()` | write |

### Arrangement & Recording (8 tools)

| # | Tool | Params | Live API | Thread |
|---|------|--------|----------|--------|
| 69 | `get_arrangement_clips` | `track_index` | `track.arrangement_clips[]` | — |
| 70 | `jump_to_time` | `beat_time: float` | `song.current_song_time` | write |
| 71 | `capture_midi` | — | `song.capture_midi()` | write |
| 72 | `start_recording` | `arrangement?: bool` | `song.record_mode / session_record` | write |
| 73 | `stop_recording` | — | toggle off | write |
| 74 | `get_cue_points` | — | `song.cue_points[]` | — |
| 75 | `jump_to_cue` | `cue_index: int` | `cue.jump()` | write |
| 76 | `toggle_cue_point` | — | `song.set_or_delete_cue()` | write |

**Note on `toggle_cue_point`:** The Live API `set_or_delete_cue()` is a toggle — it creates a cue at the current playhead position if none exists there, or deletes the existing one. The tool name reflects this dual behavior.

**Note on `get_arrangement_clips`:** Returns list of arrangement clips with fields: `name`, `start_time` (beats), `end_time` (beats), `length` (beats), `color_index`, `is_audio_clip` (bool). This maps to `track.arrangement_clips[]` properties.

---

## Claude Code Plugin

### plugin.json

```json
{
  "name": "livepilot",
  "version": "1.0.0",
  "description": "AI copilot for Ableton Live 12 — 76 tools for production, sound design, and mixing",
  "author": "Pilot Studio"
}
```

### .mcp.json

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

### Slash Commands

| Command | Purpose | Behavior |
|---------|---------|----------|
| `/session` | Session overview | Calls get_session_info, formats tracks/clips/devices/tempo as organized report |
| `/beat` | Guided beat creation | Asks genre, tempo, key → creates tracks → programs patterns → loads instruments |
| `/mix` | Mixing assistant | Reads all track levels → suggests balance → applies with confirmation |
| `/sounddesign` | Sound design workflow | Asks character/texture → loads instrument + effects → tweaks parameters |

### Agent: livepilot-producer

Autonomous production agent for complex multi-step tasks. Given a high-level description ("make a lo-fi hip hop beat with jazzy chords"), it:
1. Plans the arrangement (tracks, sections, tempo, key)
2. Creates tracks, names, colors
3. Loads instruments from browser
4. Programs MIDI patterns with appropriate note data
5. Adds effects chains
6. Tweaks parameters for the requested sound character
7. Mixes levels and panning
8. Reports progress at each step

Uses livepilot-core skill for all decisions. Confirms destructive operations.

---

## Installer

### CLI Interface

```
npx livepilot                # Start MCP server (stdio mode)
npx livepilot --install      # Install Remote Script to Ableton
npx livepilot --uninstall    # Remove Remote Script
npx livepilot --status       # Check Ableton connection status
npx livepilot --version      # Version info
```

### Auto-Detection Paths

The installer copies the `remote_script/LivePilot/` folder to `<detected_path>/LivePilot/`.

**macOS (searched in order):**
1. `~/Music/Ableton/User Library/Remote Scripts/` — Live 12 default location
2. `~/Library/Preferences/Ableton/Live 12.*/User Remote Scripts/` — version-specific alternate (note: the glob matches the exact version directory, e.g., `Live 12.0.25`)
3. If neither found → prompt user for manual path

**Windows (searched in order):**
1. `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\` — Live 12 default
2. `%APPDATA%\Ableton\Live 12.*\Preferences\User Remote Scripts\` — version-specific alternate
3. If neither found → prompt user for manual path

**Both platforms:** If multiple valid paths found, show list with detected Live version and let user pick.

### Install Flow

1. Detect OS
2. Search known paths for Ableton installation
3. If multiple found → show list, let user pick
4. If none found → ask user for path manually
5. Copy `remote_script/LivePilot/` folder to chosen path
6. Verify file integrity
7. Print next steps (restart Ableton, enable Control Surface)

---

## Validation Layer (MCP Server)

Input validation happens in the MCP server BEFORE sending to Ableton:

| Parameter | Validation |
|-----------|-----------|
| `pitch` | int, 0-127 |
| `velocity` | float, 0.0-127.0 (Live 12 uses float for fractional humanization) |
| `probability` | float, 0.0-1.0 |
| `velocity_deviation` | float, -127.0 to 127.0 |
| `release_velocity` | float, 0.0-127.0 |
| `duration` | float, > 0 |
| `tempo` | float, 20-999 |
| `volume` | float, 0.0-1.0 |
| `pan` | float, -1.0 to 1.0 |
| `color_index` | int, 0-69 |
| `track_index` | int, >= 0 |
| `clip_index` | int, >= 0 |
| `device_index` | int, >= 0 |
| `name` | str, non-empty |

Index bounds checked on Ableton side (only it knows current state).

---

## Skill: livepilot-core

### SKILL.md Contents

1. **Identity** — what LivePilot is, tool count, capabilities
2. **Golden Rules** — 9 rules for safe, effective session control
3. **Workflow: Building a Beat** — step-by-step from empty session to full beat
4. **Workflow: Sound Design** — device parameters, effect chains, iterative tweaking
5. **Workflow: Arrangement** — clip duplication, scenes, loop points, cue markers
6. **Workflow: Mixing** — levels, panning, sends, routing, master chain
7. **Live 12 Note API** — dict format, note IDs, probability, velocity_deviation
8. **Tool Quick Reference** — 76 tools organized by domain

### Reference Corpus

| File | Scope |
|------|-------|
| `overview.md` | LivePilot architecture and tool summary |
| `m4l-devices.md` | Stock M4L devices: name, category, key parameters, use cases |
| `midi-recipes.md` | MIDI patterns: hi-hat rolls, polymetrics, probability, humanization, ghost notes |
| `sound-design.md` | Chains with parameter values by character: pads, basses, leads, textures |
| `mixing-patterns.md` | Parallel compression, sidechain, send/return, stereo width, low-end |
| `ableton-workflow.md` | Session/Arrangement patterns, resampling, freeze/flatten, export |

---

## Error Handling

### Remote Script Errors

All handlers wrapped in try/except. Errors return structured response:
```json
{"id": "x", "status": "error", "error": "Track index 5 out of range (0-3)", "code": "INDEX_ERROR"}
```

### MCP Server Errors

- Validation errors caught before socket send → clear message to AI
- Socket timeout → auto-reconnect once → retry → fail with "Ableton not responding"
- Connection refused → "Ableton not running or Remote Script not loaded"
- JSON parse error → disconnect, reconnect on next call

### Recovery

- `undo` tool available for reverting mistakes
- All destructive operations (delete_track, delete_clip, delete_device) require explicit intent
- The skill instructs the AI to always verify state after modifications

---

## Future Roadmap

### v1.1 — Knowledge Brain
- SQLite FTS knowledge base queryable via MCP tool
- Richer M4L device reference with example parameter presets

### v1.2 — M4L Bridge Device
- Companion .amxd for deep M4L control
- JavaScript execution inside Max patches
- Patcher scripting for dynamic device creation

### v2.0 — State Cache + Observers
- Event-driven architecture with Live observer listeners
- Cached state model for instant reads
- Real-time notifications (clip finished, track armed, etc.)

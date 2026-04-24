# LivePilot v1.20.0 — Ableton Live 12

## Project
- **Repo:** This directory (LivePilot)
- **Type:** Agentic MCP production system for Ableton Live 12
- **Three layers:** Device Atlas (knowledge) + M4L Analyzer (perception) + Technique Memory (learning)
- **Sister projects:** TDPilot (TouchDesigner), ComfyPilot (ComfyUI)
- **Design spec:** `docs/specs/2026-03-17-livepilot-design.md`

## Architecture
- **Remote Script** (`remote_script/LivePilot/`): Runs inside Ableton's Python, ControlSurface base class, TCP socket on port 9878
- **MCP Server** (`mcp_server/`): Python FastMCP server, validates inputs, sends commands to Remote Script
- **M4L Bridge** (`m4l_device/`): Max for Live Audio Effect on master track, UDP/OSC bridge for deep LOM access
  - UDP 9880: M4L -> Server (spectral data, responses)
  - OSC 9881: Server -> M4L (commands)
  - `livepilot_bridge.js`: 22 bridge commands for LiveAPI access
  - `SpectralCache`: thread-safe, time-expiring data cache (5s max age)
  - Bridge is optional — all core tools work without it
- **Plugin** (`livepilot/`): Codex plugin (marketplace-compatible: `.Codex-plugin/plugin.json`)
- **Installer** (`installer/`): Auto-detects Ableton path, copies Remote Script

## Key Rules
- ALL Live Object Model (LOM) calls must execute on Ableton's main thread via schedule_message queue
- Live 12 minimum — use modern note API (add_new_notes, get_notes_extended, apply_note_modifications)
- 429 tools across 53 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory, analyzer, automation, theory, generative, harmony, midi_io, perception, agent_os, composition, motif, research, planner, project_brain, runtime, evaluation, mix_engine, sound_design, transition_engine, reference_engine, translation_engine, performance_engine, song_brain, preview_studio, hook_hunter, stuckness_detector, wonder_mode, session_continuity, creative_constraints, device_forge, sample_engine, atlas, composer, experiment, musical_intelligence, semantic_moves, diagnostics, follow_actions, grooves, scales, take_lanes, miditool, synthesis_brain, creative_director
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL

## M4L Bridge Notes
- OSC addresses must be sent WITHOUT leading `/` — Max `udpreceive` passes `/` as part of messagename
- `str_for_value` requires `call()` not `get()` (it's a function)
- `get()` in Max JS LiveAPI always returns arrays
- `warp_markers` is a dict property returning JSON string — use `JSON.parse()`
- `SimplerDevice.slices` lives on the `sample` child, not the device
- `replace_sample` only works on Simplers with existing samples
- Max freezes JS from search path cache, not source directory — copy to `~/Documents/Max 8/`

## Binary Patching Workflow (.amxd)
When modifying .amxd attributes that Max editor won't persist (e.g., `openinpresentation`):
1. Find the byte sequence in the .amxd binary
2. Replace with same-byte-count alternative (file size must not change)
3. Test by loading in Ableton
4. Structure: 24-byte `ampf` header + `ptch` chunk + `mx@c` header + JSON patcher + frozen deps

## Tool Count
Currently 429 tools. If adding/removing tools, update: README.md, package.json description, livepilot/.Codex-plugin/plugin.json, livepilot/.claude-plugin/plugin.json, server.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, AGENTS.md, CLAUDE.md, CHANGELOG.md, tests/test_tools_contract.py, docs/manual/index.md, docs/manual/tool-reference.md

# LivePilot v1.10.9 — Ableton Live 12

## Project
- **Repo:** This directory (LivePilot)
- **Type:** Agentic MCP production system for Ableton Live 12
- **Three layers:** Device Atlas (knowledge) + M4L Analyzer (perception) + Technique Memory (learning)
- **Sister projects:** TDPilot (TouchDesigner), ComfyPilot (ComfyUI)
- **Design spec:** `docs/specs/2026-03-17-livepilot-design.md`

## Architecture
- **Remote Script** (`remote_script/LivePilot/`): Runs inside Ableton's Python, ControlSurface base class, TCP socket on port 9878. Version detection at startup, three capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+)
- **MCP Server** (`mcp_server/`): Python FastMCP server, validates inputs, sends commands to Remote Script
- **M4L Bridge** (`m4l_device/`): Max for Live Audio Effect on master track, UDP/OSC bridge for deep LOM access
  - UDP 9880: M4L -> Server (spectral data, responses)
  - OSC 9881: Server -> M4L (commands)
  - `livepilot_bridge.js`: 30 bridge commands for LiveAPI access
  - `SpectralCache`: thread-safe, time-expiring data cache (5s max age)
  - Bridge is optional — all core tools work without it
- **Device Atlas** (`mcp_server/atlas/`): In-memory indexed JSON database — 1305 devices with URIs, 71 enriched with sonic intelligence (YAML). 6 indexes: by_id, by_name, by_uri, by_category, by_tag, by_genre
- **Sample Engine** (`mcp_server/sample_engine/`): Three-source sample intelligence — BrowserSource (Ableton browser), SpliceSource (local sounds.db SQLite), FilesystemSource (user dirs). 6-critic fitness battery, 29-technique library, Surgeon/Alchemist dual philosophy
- **Splice Client** (`mcp_server/splice_client/`): gRPC client for Splice desktop API. Port auto-detected from port.conf, TLS with self-signed certs. Credit safety floor of 5
- **Composer** (`mcp_server/composer/`): Prompt → plan pipeline. Parses NL into CompositionIntent (genre/mood/tempo/key), plans layers with role templates, compiles to executable tool sequences. 4 genre defaults
- **Corpus** (`mcp_server/corpus/`): Parsed device-knowledge markdown → queryable Python structures (EmotionalRecipe, GenreChain, PhysicalModelRecipe, AutomationGesture). Fed to Wonder Mode, Sound Design critics, Composer
- **Execution Router** (`mcp_server/runtime/execution_router.py`): Classifies steps as remote_command/bridge_command/mcp_tool/unknown, dispatches correctly
- **Plugin** (`livepilot/`): Codex plugin (primary manifest: `.Codex-plugin/plugin.json`, Claude mirror: `.claude-plugin/plugin.json`)
- **Installer** (`installer/`): Auto-detects Ableton path, copies Remote Script

## Key Rules
- ALL Live Object Model (LOM) calls must execute on Ableton's main thread via schedule_message queue
- Live 12 minimum — use modern note API (add_new_notes, get_notes_extended, apply_note_modifications)
- 325 tools across 45 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory, analyzer, automation, theory, generative, harmony, midi_io, perception, agent_os, composition, motif, research, planner, project_brain, runtime, evaluation, mix_engine, sound_design, transition_engine, reference_engine, translation_engine, performance_engine, song_brain, preview_studio, hook_hunter, stuckness_detector, wonder_mode, session_continuity, creative_constraints, device_forge, sample_engine, atlas, composer, experiment, musical_intelligence, semantic_moves
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL
- **LivePilot_Analyzer must be LAST on master** — always after ALL effects (EQ, Compressor, Utility) so it reads the final output, not pre-effect signal
- **Single TCP client** — Remote Script accepts one connection at a time on port 9878. The MCP server holds a persistent connection. Direct TCP calls will fail with "Another client is already connected" if the MCP server is active. Always use MCP tools, not raw TCP

## M4L Bridge Notes
- OSC addresses must be sent WITHOUT leading `/` — Max `udpreceive` passes `/` as part of messagename
- `str_for_value` requires `call()` not `get()` (it's a function)
- `get()` in Max JS LiveAPI always returns arrays
- `warp_markers` is a dict property returning JSON string — use `JSON.parse()`
- `SimplerDevice.slices` lives on the `sample` child, not the device
- `replace_sample` only works on Simplers with existing samples
- Max freezes JS from search path cache, not source directory — copy to `~/Documents/Max 9/`

## Binary Patching Workflow (.amxd)
When modifying .amxd attributes that Max editor won't persist (e.g., `openinpresentation`):
1. Find the byte sequence in the .amxd binary
2. Replace with same-byte-count alternative (file size must not change)
3. Test by loading in Ableton
4. Structure: 24-byte `ampf` header + `ptch` chunk + `mx@c` header + JSON patcher + frozen deps

## Version Bump
If bumping the version, update ALL of these: package.json, server.json (Marketplace reads this), livepilot/.Codex-plugin/plugin.json, livepilot/.claude-plugin/plugin.json, .claude-plugin/marketplace.json, mcp_server/__init__.py, remote_script/LivePilot/__init__.py, CLAUDE.md, AGENTS.md, CHANGELOG.md, livepilot/skills/livepilot-core/references/overview.md, docs/M4L_BRIDGE.md (ping version string)

## Tool Count
Currently 325 tools. If adding/removing tools, update: README.md, package.json description, livepilot/.Codex-plugin/plugin.json, livepilot/.claude-plugin/plugin.json, server.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, CLAUDE.md, CHANGELOG.md, tests/test_tools_contract.py, docs/manual/index.md, docs/manual/tool-reference.md

## Domain Count
Currently 45 domains. A domain = the subdirectory under `mcp_server/` (or file under `mcp_server/tools/`) that contains `@mcp.tool()`. Source of truth is the module layout — no hand-maintained list. If adding/removing domains, update: README.md, package.json, manifest.json, CLAUDE.md, AGENTS.md, .claude-plugin/marketplace.json, livepilot/.claude-plugin/plugin.json, livepilot/.Codex-plugin/plugin.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, livepilot/skills/livepilot-release/SKILL.md, docs/manual/index.md, docs/manual/tool-catalog.md, docs/manual/tool-catalog-generated.md, tests/test_tools_contract.py. Run `python scripts/sync_metadata.py --check` to enforce count + inline list (or `--fix` for mechanical fixes).

# Changelog

## 1.6.1 — Hotfix (March 2026)

- Fix: `clip_automation.py` imported `register` from `utils` instead of `router`, causing Remote Script to fail to load in Ableton (LivePilot disappeared from Control Surface list)

## 1.6.0 — Automation Intelligence (March 2026)

**8 new tools (127 -> 135), 16-type curve engine, 15 recipes, spectral feedback loop.**

### Automation Curve Engine
- 16 curve types in 4 categories: basic (9), organic (3), shape (2), generative (2)
- Pure math module — no Ableton dependency, fully testable offline
- 15 built-in recipes for common production techniques

### New Tools: Automation Domain (8 tools)
- `get_clip_automation` — list automation envelopes on a session clip
- `set_clip_automation` — write automation points to clip envelope
- `clear_clip_automation` — clear automation envelopes
- `apply_automation_shape` — generate + apply curve in one call
- `apply_automation_recipe` — apply named recipe (filter_sweep_up, dub_throw, etc.)
- `get_automation_recipes` — list all 15 recipes with descriptions
- `generate_automation_curve` — preview curve points without writing
- `analyze_for_automation` — spectral analysis + device-aware suggestions

### Automation Atlas
- Knowledge corpus: curve theory, perception-action loop, genre recipes
- Diagnostic filter technique: using EQ as a measurement instrument
- Cross-track spectral mapping for complementary automation
- Golden rules for musically intelligent automation

### Producer Agent
- New automation phase in production workflow
- Mandatory spectral feedback loop: perceive -> diagnose -> act -> verify -> adjust
- Spectral-driven automation decisions, not just blind curve application

---

## 1.5.0 — Agentic Production System (March 19, 2026)

**Three-layer intelligence: Device Atlas + M4L Analyzer + Technique Memory.**

LivePilot is no longer just a tool server. v1.5.0 reframes the architecture around three layers that give the AI context beyond raw API access:

### Device Atlas
- Structured knowledge corpus of 280+ Ableton devices, 139 drum kits, 350+ impulse responses
- Indexed by category with sonic descriptions, parameter guides, and real browser URIs
- The agent consults the atlas before loading any device — no more hallucinated preset names

### M4L Analyzer (new in v1.1.0, now integrated into the agentic workflow)
- 8-band spectral analysis, RMS/peak metering, pitch tracking, key detection on the master bus
- The agent reads the spectrum after mixing moves to verify results
- Key detection informs harmonic content decisions (bass lines, chord voicings)

### Technique Memory
- Persistent production decisions across sessions: beat patterns, device chains, mix templates, preferences
- `memory_recall` matches on mood, genre, texture — not just names
- The agent consults memory by default before creative decisions, building a profile of the user's taste over time

### Producer Agent
- Updated to use all three layers: atlas for instrument selection, analyzer for verification, memory for style context
- Mandatory health checks between stages now include spectral verification when the analyzer is present

### Documentation
- README rewritten around the three-layer architecture
- Manual updated with agentic approach section
- Skill description reflects the full stack: tools + atlas + analyzer + memory
- Comparison table updated to highlight knowledge, perception, and memory as differentiators

---

## 1.1.0 — M4L Bridge & Deep LOM Access (March 18-19, 2026)

**23 new tools (104 -> 127), M4L Analyzer device, deep LiveAPI access via Max for Live bridge.**

### M4L Bridge Architecture
- New `LivePilot_Analyzer.amxd` Max for Live Audio Effect for the master track
- UDP/OSC bridge: port 9880 (M4L -> Server), port 9881 (Server -> M4L)
- `livepilot_bridge.js` with 22 bridge commands for deep LOM access
- `SpectralCache` with thread-safe, time-expiring data storage (5s max age)
- Graceful degradation: all 104 core tools work without the analyzer device
- Base64-encoded JSON responses with chunked transfer for large payloads (>1400 bytes)
- OSC addresses sent WITHOUT leading `/` to fix Max `udpreceive` messagename dispatch

### New Tools: Analyzer Domain (20 tools)

**Spectral Analysis (3):**
- `get_master_spectrum` — 8-band frequency analysis (sub/low/low-mid/mid/high-mid/high/presence/air)
- `get_master_rms` — real-time RMS, peak, and pitch from the master bus
- `get_detected_key` — Krumhansl-Schmuckler key detection algorithm on accumulated pitch data

**Deep LOM Access (4):**
- `get_hidden_parameters` — all device parameters including hidden ones not in ControlSurface API
- `get_automation_state` — automation state for all parameters (active/overridden)
- `walk_device_tree` — recursive device chain tree walking (racks, drum pads, nested devices, 6 levels deep)
- `get_display_values` — human-readable parameter values as shown in Live's UI (e.g., "440 Hz", "-6.0 dB")

**Simpler Operations (7):**
- `replace_simpler_sample` — load audio file into Simpler by absolute path (requires existing sample)
- `load_sample_to_simpler` — full workflow: bootstrap Simpler via browser, then replace sample
- `get_simpler_slices` — get slice point positions (frames and seconds) from Simpler
- `crop_simpler` — crop sample to active region
- `reverse_simpler` — reverse sample in Simpler
- `warp_simpler` — time-stretch sample to fit N beats at current tempo
- `get_clip_file_path` — get audio file path on disk for a clip

**Warp Markers (4):**
- `get_warp_markers` — get all warp markers (beat_time + sample_time) from audio clips
- `add_warp_marker` — add warp marker at beat position
- `move_warp_marker` — move warp marker to new beat position (tempo manipulation)
- `remove_warp_marker` — remove warp marker at beat position

**Clip Preview (2):**
- `scrub_clip` — scrub/preview clip at specific beat position
- `stop_scrub` — stop scrub preview

### New Tools: Mixing Domain (3 tools)
- `get_track_routing` — get input/output routing info for a track
- `set_track_routing` — set input/output routing by display name
- `get_mix_snapshot` — one-call full mix state (all meters, volumes, pans, sends, master)

### Bugs Fixed

**M4L Bridge Fixes:**
- OSC addresses: removed leading `/` from outgoing commands — Max `udpreceive` passes the `/` as part of the messagename to JS, breaking the dispatch switch statement
- `str_for_value` requires `call()` not `get()` — it's a function, not a property in Max JS LiveAPI
- `warp_markers` is a dict property returning a JSON string, not LOM children — requires `JSON.parse()` on the raw `get()` result
- `SimplerDevice.slices` lives on the `sample` child object (`device sample slices`), not on the device directly
- `replace_sample` only works on Simplers that already have a sample loaded — silently fails on empty Simplers
- `get()` in Max JS LiveAPI always returns arrays — must index or convert appropriately
- `openinpresentation` attribute in .amxd doesn't persist from Max editor saves — requires binary patching

**M4L Analyzer Display Fixes:**
- Injected `settype Float` messages to fix spectrum bar display (was showing integer 0/1)
- Fixed `vexpr` scaling factor from 10 to 200 for proper bar visualization range
- Fixed freeze/JS caching: Max freezes JS from its search path cache (`~/Documents/Max 8/...`), not from the source file directory

**Tool Fixes:**
- Fixed key detection passthrough from streaming cache to bridge query fallback
- Fixed parameter name case-sensitivity in hidden parameter reads
- Fixed input validation on several analyzer tools (missing clip/track validation)
- Fixed `load_sample_to_simpler` bootstrap: searches browser for any sample, loads it to create Simpler, then replaces

### LiveAPI Insights Documented
- `get()` returns arrays in Max JS LiveAPI (even for scalar properties)
- `call()` vs `get()` distinction for functions vs properties
- `.amxd` binary format: 24-byte `ampf` header + `ptch` chunk + `mx@c` header + JSON patcher + frozen dependencies
- Binary patching technique: same-byte-count string replacements preserve file structure
- Max freezes JS from cache path, not source directory — must copy to `~/Documents/Max 8/`

### Technical
- New `mcp_server/m4l_bridge.py` module: `SpectralCache`, `SpectralReceiver`, `M4LBridge` classes
- New `mcp_server/tools/analyzer.py`: 20 MCP tools for the analyzer domain
- New `m4l_device/livepilot_bridge.js`: 22 bridge commands
- New `m4l_device/LivePilot_Analyzer.amxd`: compiled M4L device

---

## 1.0.0 — LivePilot

**AI copilot for Ableton Live 12 — 104 MCP tools for real-time music production.**

### Core
- 104 MCP tools across 10 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory
- Remote Script using Ableton's official Live Object Model API (ControlSurface base class)
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL

### Browser & Device Loading
- Breadth-first device search with exact-match priority
- Plugin browser support (AU/VST/AUv3) via `search_browser("plugins")`
- Max for Live browser via `search_browser("max_for_live")`
- URI-based loading with category hint parsing for fast resolution
- Case-insensitive parameter name matching

### Arrangement
- Full arrangement view support: create clips, add/remove/modify notes, automation envelopes
- Automation on device parameters, volume, panning, and sends
- Support for return tracks and master track across all tools

### Plugin
- 5 slash commands: /beat, /mix, /sounddesign, /session, /memory
- Producer agent for autonomous multi-step tasks
- Technique memory system (learn, recall, replay, favorite)
- Built-in Device Atlas covering native Ableton instruments and effects

### Installer
- Auto-detects Ableton Remote Scripts path on macOS and Windows
- Copies Remote Script files, verifies installation

# Changelog

## 1.9.5 — TCP Retry Fix + Arrangement Automation Fix (March 2026)

- Fix(P1): disconnect() now clears _recv_buf — prevents partial JSON corruption on TCP retry
- Fix(P1): set_arrangement_automation fallback copies notes + deletes original clip to avoid silent duplication
- Fix(P2): get_arrangement_clips reports effective length based on loop_end, not raw timeline length
- 2 new connection tests for recv_buf corruption
- 257 tests passing

## 1.9.4 — Doc Sync + M4L Analyzer Fix + Full Validation (March 2026)

**178 tools, all validated live in Ableton. M4L analyzer fully working.**

- Fix: multislider `settype` 0→1 (integer→float) — spectrum bars now render correctly
- Fix: added `loadbang → 1 → snapshot~` init chain for reliable auto-output
- Fix: panel z-order for visible UI in presentation mode
- Binary-patch `openinpresentation` for presentation mode
- Rebuilt .amxd with v1.9 bridge (3 new plugin parameter commands frozen)
- Full live validation: 77 PASS across all 17 domains, FluCoMa 6/6 streams, 255 pytest passing

## 1.9.0 — Scene Matrix, Freeze/Flatten, Plugin Deep Control (March 2026)

**10 new tools (168 → 178), 3 features shipped.**

### Scene Matrix Operations (+4 tools)
- `get_scene_matrix` — full N×M clip grid with states (empty/stopped/playing/triggered/recording)
- `fire_scene_clips` — fire a scene with optional track filter for selective launching
- `stop_all_clips` — stop all playing clips in the session (panic button)
- `get_playing_clips` — return all currently playing or triggered clips

### Track Freeze/Flatten (+3 tools)
- `freeze_track` — freeze a track (render devices to audio for CPU savings)
- `flatten_track` — flatten a frozen track (commit rendered audio permanently)
- `get_freeze_status` — check if a track is frozen

### Plugin Parameter Mapping (+3 tools, M4L)
- `get_plugin_parameters` — get ALL VST/AU plugin parameters including unconfigured ones
- `map_plugin_parameter` — add a plugin parameter to Ableton's Configure list for automation
- `get_plugin_presets` — list a plugin's internal presets and banks

### Infrastructure
- `SLOW_WRITE_COMMANDS` set for freeze_track (35s timeout vs 15s for normal writes)
- Removed "Coming" section from README — all roadmap features shipped or dropped

## 1.8.4 — Bug Fix Audit (March 2026)

**5 bugs fixed (2 P1, 3 P2), verified live in Ableton.**

### P1 — Safety-Critical
- Fix: `create_arrangement_clip` no longer hangs Ableton when `loop_length` is zero or negative — validation at MCP + Remote Script layers
- Fix: `import_midi_to_clip` now preserves the MIDI file's beat grid instead of scaling by session tempo — a 60 BPM MIDI imported at 120 BPM no longer doubles note positions

### P2 — Correctness
- Fix: `create_arrangement_clip` now sets `loop_end` on duplicated clips when `loop_length < source_length`, with documented LOM limitation for arrangement clip resizing
- Fix: `--status` / `--doctor` CLI commands no longer report success for error responses — only resolves true on valid pong
- Fix: `import_midi_to_clip` with `create_clip=True` now checks for existing clips before creating — clears notes if occupied, creates if empty

### Tests
- 2 new tests for MIDI tempo independence (`test_midi_io.py::TestImportTempoIndependence`)
- 255 total tests passing

## 1.8.3 — FluCoMa Wiring + Analyzer Fix (March 2026)

- Fix: wire 6 FluCoMa DSP objects into LivePilot_Analyzer.maxpat (spectral shape, mel bands, chroma, loudness, onset, novelty)
- Fix: onset/novelty Python handlers now accept 1 arg (fluid.onsetfeature~/noveltyfeature~ output single float)
- Fix: restore .amxd after binary corruption — .amxd must be rebuilt via Max editor, not programmatic JSON editing
- Fix: panel z-order in .maxpat — move background panel first in boxes array so multislider renders on top
- FluCoMa perception tools now fully functional when FluCoMa package is installed
- Note: after installing, rebuild .amxd from .maxpat via Max editor (see BUILD_GUIDE.md)

## 1.8.1 — Patch (March 2026)

- Fix: `parse_key()` now accepts shorthand key notation ("Am", "C#m", "Bbm") in addition to "A minor" / "C# major"
- Fix: re-freeze LivePilot_Analyzer.amxd with v1.8.0 bridge + patch openinpresentation
- Fix: address audit findings from fresh v1.8 code review
- Fix: update bridge version string
- Fix: restructure plugin directory for Claude Code marketplace compatibility (`plugin/` → `livepilot/.claude-plugin/`)

## 1.8.0 — Perception Layer (March 2026)

**13 new tools (155 → 168), 1 new domain (perception), FluCoMa real-time DSP, offline audio analysis, audio capture.**

### Perception Domain (4 tools)
- `analyze_loudness` — LUFS, sample peak, RMS, crest factor, LRA, streaming compliance
- `analyze_spectrum_offline` — spectral centroid, rolloff, flatness, bandwidth, 5-band balance
- `compare_to_reference` — mix vs reference: loudness/spectral/stereo deltas + suggestions
- `read_audio_metadata` — format, duration, sample rate, tags, artwork detection

### Analyzer — Capture (2 tools)
- `capture_audio` — record master output to WAV via M4L buffer~/record~
- `capture_stop` — cancel in-progress capture

### Analyzer — FluCoMa Real-Time (7 tools)
- `get_spectral_shape` — 7 descriptors (centroid, spread, skewness, kurtosis, rolloff, flatness, crest)
- `get_mel_spectrum` — 40-band mel spectrum (5x resolution of get_master_spectrum)
- `get_chroma` — 12 pitch class energies for chord detection
- `get_onsets` — real-time onset/transient detection
- `get_novelty` — spectral novelty for section boundary detection
- `get_momentary_loudness` — EBU R128 momentary LUFS + peak
- `check_flucoma` — verify FluCoMa installation status

### Architecture
- New `_perception_engine.py` — pure scipy/pyloudnorm/soundfile/mutagen analysis (no MCP deps)
- New `perception.py` — 4 MCP tool wrappers with format validation
- 6 FluCoMa OSC handlers in SpectralReceiver (`/spectral_shape`, `/mel_bands`, `/chroma`, `/onset`, `/novelty`, `/loudness`)
- Dedicated `/capture_complete` channel with `_capture_future` (separate from bridge responses)
- `--setup-flucoma` CLI command — auto-downloads and installs FluCoMa Max package
- New dependencies: pyloudnorm, soundfile, scipy, mutagen

## 1.7.0 — Creative Engine (March 2026)

**13 new tools (142 → 155), 3 new domains, MIDI file I/O, neo-Riemannian harmony, generative algorithms.**

### MIDI I/O Domain (4 tools)
- `export_clip_midi` — export session clip to .mid file
- `import_midi_to_clip` — load .mid file into session clip
- `analyze_midi_file` — offline analysis of any .mid file
- `extract_piano_roll` — 2D velocity matrix from .mid file

### Generative Domain (5 tools)
- `generate_euclidean_rhythm` — Bjorklund algorithm, identifies known rhythms
- `layer_euclidean_rhythms` — stack patterns for polyrhythmic textures
- `generate_tintinnabuli` — Arvo Pärt technique: triad voice from melody
- `generate_phase_shift` — Steve Reich technique: drifting canon
- `generate_additive_process` — Philip Glass technique: expanding melody

### Harmony Domain (4 tools)
- `navigate_tonnetz` — PRL neighbors in harmonic space
- `find_voice_leading_path` — shortest path between two chords through Tonnetz
- `classify_progression` — identify neo-Riemannian transform pattern
- `suggest_chromatic_mediants` — all chromatic mediant relations with film score picks

### Architecture
- Two new pure Python engines (`_generative_engine.py`, `_harmony_engine.py`)
- New dependencies: midiutil, pretty-midi, opycleid (~5 MB total, lazy-loaded)
- Opycleid fallback: harmony tools work without the package via pure Python PRL
- All generative tools return note arrays — LLM orchestrates placement

## 1.6.5 — Drop music21 (March 2026)

**Theory tools rewritten with zero-dependency pure Python engine.**

- Replace music21 (~100MB) with built-in `_theory_engine.py` (~350 lines)
- Krumhansl-Schmuckler key detection with 7 mode profiles (major, minor, dorian, phrygian, lydian, mixolydian, locrian)
- All 7 theory tools keep identical APIs and return formats
- Zero external dependencies — theory tools work on every install
- 2-3s faster cold start (no music21 import overhead)

## 1.6.4 — Music Theory (March 2026)

**7 new tools (135 -> 142), theory analysis on live MIDI clips.**

### Theory Domain (7 tools)
- `analyze_harmony` — chord-by-chord Roman numeral analysis of session clips
- `suggest_next_chord` — theory-valid chord continuations with style presets (common_practice, jazz, modal, pop)
- `detect_theory_issues` — parallel fifths/octaves, out-of-key notes, voice crossing, unresolved dominants
- `identify_scale` — Krumhansl-Schmuckler key/mode detection with confidence-ranked alternatives
- `harmonize_melody` — 2 or 4-voice SATB harmonization with smooth voice leading
- `generate_countermelody` — species counterpoint (1st or 2nd species) against a melody
- `transpose_smart` — diatonic or chromatic transposition preserving scale relationships

### Architecture
- Pure Python `_theory_engine.py`: Krumhansl-Schmuckler key detection, Roman numeral analysis, voice leading checks
- Chordify bridge: groups notes by quantized beat position (1/32 note grid)
- Key hint parsing: handles "A minor", "F# major", enharmonic normalization

## 1.6.3 — Audit Hardening (March 2026)

- Fix: cursor aliasing in M4L bridge `walk_device` — nested rack traversal now reads chain/pad counts before recursion clobbers shared cursors
- Fix: `clip_automation.py` — use `get_clip()` for bounds-checked access, add negative index guards, proper validation in `clear_clip_automation`
- Fix: `set_clip_loop` crash when `enabled` param omitted
- Fix: Brownian curve reflection escaping [0,1] for large volatility
- Fix: division by zero in M4L bridge when `sample_rate=0`
- Fix: `technique_store.get()` shallow copy allows shared mutation — now uses deepcopy
- Fix: `asyncio.get_event_loop()` deprecation — use `get_running_loop()` (Python 3.12+)
- Fix: dead code in `browser.py`, stale tool counts in docs (107 → 115 core)
- Fix: wrong param name in tool-reference docs (`soloed` → `solo`)
- Fix: social banner missing "automation" domain (11 → 12)
- Fix: tautological spring test, dead automation contract test, misleading clips test
- Add: `livepilot-release` skill registered in plugin.json
- Add: `__version__` to Remote Script `__init__.py`

## 1.6.2 — Automation Params Fix (March 2026)

- Fix: expose all curve-specific params in `generate_automation_curve` and `apply_automation_shape` MCP tools — `values` (steps), `hits`/`steps` (euclidean), `seed`/`drift`/`volatility` (organic), `damping`/`stiffness` (spring), `control1`/`control2` (bezier), `easing_type`, `narrowing` (stochastic)
- Fix: `analyze_for_automation` spectral getter used wrong method (`.get_spectrum()` → `.get("spectrum")`)

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

# Changelog

## 1.9.25 — Live 12.3 API Integration (April 2026)

### New Tools (+4, total 307)
- `create_native_arrangement_clip` — create arrangement clips with full automation envelope support (12.1.10+)
- `insert_device` — insert native devices by name, 10x faster than browser search (12.3+), supports chain-level insertion for drum rack construction
- `insert_rack_chain` — add chains to Instrument/Audio Effect/Drum Racks (12.3+)
- `set_drum_chain_note` — assign MIDI notes to Drum Rack chains (12.3+)

### Enhancements
- **Version Detection** — LivePilot now detects the Live version at startup and exposes feature flags via `get_session_info`. Three capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+)
- **Display Values** — `get_device_parameters`, `set_device_parameter`, and `batch_set_parameters` now include `display_value` (human-readable like "26.0 Hz") on Live 12.2+ without requiring the M4L bridge
- **Fast Device Loading** — `find_and_load_device` automatically uses `insert_device` on 12.3+ for native devices, giving a 10x speedup with no code changes needed
- **Backward Compatibility** — All existing tools continue working on Live 12.0.x. New features use try/except feature detection with clear fallback messages

## 1.9.26 — Sample Engine (April 2026)

### Sample Engine — AI Sample Manipulation Intelligence
- **feat(sample_engine):** New `sample_engine` domain with 6 tools: `analyze_sample`, `evaluate_sample_fit`, `search_samples`, `suggest_sample_technique`, `plan_sample_workflow`, `get_sample_opportunities`
- **feat(sample_engine):** SampleAnalyzer — filename metadata parser, spectral material classifier (vocal/drum/texture/etc.), Simpler mode/slice/warp recommender
- **feat(sample_engine):** 6-critic fitness battery — key fit, tempo fit, frequency fit, role fit, vibe fit, intent fit. Scores 0.0-1.0 per dimension with real computation (no stubs)
- **feat(sample_engine):** 29-technique library across 7 categories: rhythmic (Dilla, Burial, Premier), textural (Paulstretch, granular), melodic (Bon Iver), drum enhancement, vocal processing, resampling chains (Amon Tobin), creative constraints
- **feat(sample_engine):** Dual philosophy system — Surgeon (precision integration) and Alchemist (creative transformation), context-aware auto-switching
- **feat(sample_engine):** SpliceSource — reads Splice's local sounds.db SQLite database (read-only) for rich metadata: key, BPM, genre, tags, pack info, popularity. Searches by key+tempo for song-matched results
- **feat(sample_engine):** BrowserSource + FilesystemSource — Ableton browser search (samples, drums, packs, user_library) and local directory scanner with filename metadata extraction
- **feat(sample_engine):** SamplePlanner — technique selection scoring + compiled plan generation with recursive template variable resolution
- **feat(wonder_mode):** 6 new sample-domain semantic moves: chop_rhythm, texture_layer, vocal_ghost, break_layer, resample_destroy, one_shot_accent
- **feat(wonder_mode):** Sample-aware diagnosis — 4 new patterns in _DOMAIN_MAP: no_organic_texture, stale_drums, vocal_processing_monotony, dense_but_static
- **feat(skills):** New `livepilot-sample-engine` skill with technique catalog, critic reference, and Surgeon/Alchemist philosophy guide
- Tool count: 297 → 303 (41 domains), 131 sample engine tests

## 1.9.25 — Device Forge (April 2026)

### Device Forge — Programmatic M4L Device Generation
- **feat(device_forge):** New `device_forge` domain with 3 tools: `generate_m4l_effect`, `list_genexpr_templates`, `install_m4l_device`
- **feat(device_forge):** .amxd binary builder — generates valid Max for Live devices from pure Python using reverse-engineered binary format
- **feat(device_forge):** gen~ DSP template library — 15 building blocks: Lorenz attractor, Karplus-Strong, wavefolder, FDN reverb, bitcrusher, ring modulator, chorus, stochastic resonance, phase distortion, and more
- **feat(semantic_moves):** 7 new `device_creation` semantic moves for wonder mode: chaos modulator, feedback resonator, wavefolder, bitcrusher, Karplus-Strong string, stochastic texture, FDN reverb
- **feat(device_forge):** Safety: all generated gen~ code automatically gets `clip(out, -1, 1)` appended to prevent speaker damage
- **feat(device_forge):** Supports all 3 device types: Audio Effect, MIDI Effect, Instrument
- **feat(device_forge):** Auto-installs to Ableton User Library — devices appear in browser immediately
- Tool count: 294 → 297 (40 domains)

## 1.9.24 — Stability & Intelligence Upgrade (April 2026)

### Truth and Boundaries (Wave 1)
- **feat(runtime):** Capability contract — every advanced tool reports `full/fallback/analytical_only/unavailable` with confidence scores
- **feat(runtime):** Command boundary audit — CI catches any `send_command()` targeting a non-existent Remote Script command
- **fix(song_brain):** `get_motif_graph` now uses pure-Python engine instead of invalid TCP call
- **fix(hook_hunter):** Same motif routing fix
- **fix(musical_intelligence):** Same motif routing fix + `analyze_phrase_arc` now calls perception engine directly
- **fix(memory):** `record_positive_preference` actually updates taste dimensions (was a silent no-op due to key mismatch)
- **fix(metadata):** AGENTS.md synced to v1.9.23/293 tools, test docstring corrected

### Unified Execution Layer (Wave 2)
- **feat(runtime):** Execution router — classifies steps as `remote_command/bridge_command/mcp_tool/unknown`, dispatches correctly
- **feat(semantic_moves):** `apply_semantic_move` explore mode uses execution router
- **feat(preview_studio):** `render_preview_variant` uses execution router

### Persistent Memory (Waves 2-3)
- **feat(persistence):** Base persistent JSON store (atomic write, corruption recovery, thread-safe)
- **feat(persistence):** Taste store at `~/.livepilot/taste.json` — move outcomes, novelty band, device affinity, anti-preferences survive restart
- **feat(persistence):** Project store at `~/.livepilot/projects/<hash>/state.json` — threads, turns, Wonder outcomes per song
- **feat(memory):** TasteGraph.record_move_outcome writes to persistent backing
- **feat(session_continuity):** tracker flushes threads and turns to project store on write

### Move Annotations (Wave 3)
- **feat(semantic_moves):** All 20 moves annotated with explicit `backend` per compile_plan step
- **test:** Static audit verifies all annotations match the execution router classifier

### Intelligence Upgrade (Waves 3-4)
- **feat(services):** Shared motif service — one entry point consumed by SongBrain, HookHunter, musical_intelligence
- **feat(song_brain):** Evidence-weighted identity confidence (motif=0.4, composition=0.2, roles=0.15, scenes=0.15, moves=0.1)
- **feat(song_brain):** `evidence_breakdown` field shows per-source contributions
- **feat(hook_hunter):** Hooks carry `evidence_sources` (motif_recurrence, track_name, clip_reuse)
- **feat(hook_hunter):** Section-placement analysis boosts hooks recurring across sections
- **feat(detectors):** Motif appearing in >60% of sections triggers fatigue signal

### Preview and Doctor (Wave 4)
- **feat(preview_studio):** Three explicit preview modes: `audible_preview` (M4L+spectrum), `metadata_only_preview`, `analytical_preview`
- **feat(preview_studio):** `bars` parameter used for audible preview playback duration
- **feat(preview_studio):** `preview_mode` field in response — no ambiguity about what was measured
- **feat(runtime):** Capability probe — 6-area runtime detection (Ableton, Remote Script, M4L, numpy, persistence, tier)

### Release Infrastructure (Wave 5)
- **feat(scripts):** `sync_metadata.py` — single source of truth for version and tool count, CI-checkable
- **docs:** README Intelligence Layer section with all 12 engines described
- **docs:** Manual index rewritten with three-layer architecture and 39-domain map

## 1.9.23-wonder-v1.5 — Wonder Mode V1.5: Stuck-Rescue Workflow (April 2026)

### Wonder Mode Redesign (292->293 tools)
- **feat(wonder_mode):** Diagnosis-first workflow — stuckness detection drives variant generation
- **feat(wonder_mode):** Honest variant labeling — `analytical_only: true` for non-executable variants
- **feat(wonder_mode):** Real distinctness enforcement — variants must differ by move, family, or plan shape
- **feat(wonder_mode):** WonderSession lifecycle — diagnosis -> variants -> preview -> commit/discard
- **feat(wonder_mode):** `discard_wonder_session` tool — reject all variants, keep creative thread open
- **feat(preview_studio):** Wonder-aware preview — accepts `wonder_session_id`, refuses analytical variants
- **feat(preview_studio):** Commit lifecycle hooks — records outcome to continuity and taste
- **feat(session_continuity):** No more premature turn recording — only commit/reject record turns
- **feat(skills):** New `livepilot-wonder` skill with trigger conditions and honesty rules

## 1.9.23 — Stage 2: The Magic Layer (April 2026)

### Wonder Mode Rebuild
- **feat(wonder_mode):** Full engine rebuild — variants now built from real semantic moves matched by keyword+taste scoring, not templates
- **feat(wonder_mode):** Ranking uses bell-curve novelty centered on user's novelty_band, sacred element penalty, and coherence scoring
- **feat(wonder_mode):** Taste fit uses full TasteGraph (family preference, dimension alignment, anti-preferences, risk alignment)
- **feat(wonder_mode):** Each variant carries `targets_snapshot`, `compiled_plan`, and `score_breakdown` with all 4 component scores
- **breaking(wonder_mode):** Removed `generate_wonder_variants` tool (redundant with `enter_wonder_mode`)

### New Tools (10 new, -1 removed = net +9, 283→292)
- **feat(preview_studio):** `render_preview_variant` — render a short preview of a variant using Ableton's undo system
- **feat(hook_hunter):** `detect_hook_neglect` — check if a strong hook is underused across sections
- **feat(hook_hunter):** `compare_phrase_impact` — compare emotional impact across multiple sections
- **feat(stuckness_detector):** `start_rescue_workflow` — structured step-by-step rescue plan for a specific stuckness type
- **feat(wonder_mode):** `rank_wonder_variants` — rank wonder variants by taste + identity + phrase impact
- **feat(session_continuity):** `open_creative_thread` — open a new creative thread for exploration
- **feat(session_continuity):** `list_open_creative_threads` — list all open non-stale creative threads
- **feat(session_continuity):** `explain_preference_vs_identity` — explain taste vs identity tension for a candidate
- **feat(creative_constraints):** `generate_constrained_variants` — generate triptych variants under active constraints
- **feat(creative_constraints):** `generate_reference_inspired_variants` — generate variants inspired by distilled reference principles

### Fixes
- **fix(wonder_mode):** Fixed taste graph access to use session-scoped lifespan context instead of creating fresh stores
- **fix(session_continuity):** Fixed taste graph access to match preview_studio pattern

## 1.9.22 — Skill & Command Overhaul (April 2026)

### Skill Updates
- **feat(beat):** Added Step 0 "Session Prep" — for fresh projects, deletes all tracks and loads M4L Analyzer on master before starting. Includes perception check (Step 11) with spectral balance verification.
- **feat(mix):** Added analyzer auto-load (Step 2), spectral targets by genre (Step 6), mandatory meter verification after every change (Step 8), capture+analyze loop (Step 11)
- **feat(sounddesign):** Added mandatory `value_string` verification (Step 5), perception check (Step 11), organic movement with perlin curves (Step 8)
- **feat(arrange):** Added motif detection (Step 3), gesture template execution (Step 7), perlin organic movement (Step 8), emotional arc verification (Step 9), LRA check for dynamic range (Step 10)
- **feat(evaluate):** Added analyzer auto-load (Step 2), full perception snapshot with track meters (Step 6), capture+analyze offline as ground truth option

## 1.9.21 — Verification Discipline Pass (April 2026)

### Systemic Fixes
- **fix(devices):** `set_device_parameter` and `batch_set_parameters` now return `value_string`, `min`, `max` in response — the agent can immediately see "26.0 Hz" instead of just "75" and catch nonsensical values
- **fix(automation):** `apply_automation_recipe` now auto-scales 0-1 recipe curves to the target parameter's actual native range (e.g., Auto Filter 20-135, Bit Depth 1-16). Previously, a "0.3 center" vinyl_crackle on a 20-135 range wrote 0.3 literally, killing audio
- **fix(automation):** `auto_pan` recipe pan values now clamped to ±0.6 to prevent full L/R swing that makes tracks disappear from one channel
- **docs(skill):** Added Golden Rules 15-16 — mandatory post-write verification protocol: always read `value_string`, always check track meters after filter/effect changes, never apply automation recipes without understanding the target parameter's range

## 1.9.20 — Deep Production Test Pass (April 2026)

### New Tool
- **feat(analyzer):** `reconnect_bridge` — rebind UDP 9880 mid-session after port conflict clears, without restarting the MCP server

### Bug Fixes
- **fix(arrangement):** `set_arrangement_automation` now returns `STATE_ERROR` (not `INVALID_PARAM`) with clear workaround suggestions for the known Live API limitation
- **fix(router):** added `RuntimeError` → `STATE_ERROR` mapping so state-related errors don't masquerade as parameter validation failures
- **fix(browser):** `load_browser_item` now accepts negative track_index (-1/-2 for returns, -1000 for master) — was incorrectly rejected by MCP-side validator
- **fix(tracks):** `set_track_name` on return tracks strips auto-prefix letter to prevent doubling (e.g. "C-Resonators" stays as-is, not "C-C-Resonators")
- **fix(theory):** `suggest_next_chord` now uses mode-aware progression maps — separate major/minor chord tables for common_practice, jazz, modal, and pop styles
- **fix(research):** `research_technique` now searches instruments, audio_effects, AND drums categories (was instruments-only); deep scope notes that web search is agent-layer responsibility
- **fix(server):** improved port competition error messages — directs users to `reconnect_bridge` tool instead of requiring server restart
- **fix(analyzer):** M4L Analyzer User Library copy synced to latest version (presentation mode enabled, bridge JS updated)

### Documentation
- **docs(skill):** added "Volume reset on scene fire" and "M4L Analyzer auto-load" to error handling protocol in livepilot-core skill
- **docs(CLAUDE.md):** tool count updated from 236 to 237

## 1.9.19 — Theory Engine & Meters Fix Pass (April 2026)

### Bug Fixes
- **fix(mixing):** `get_track_meters` crashed on tracks with MIDI-only output — now guards `output_meter_*` with `has_audio_output` check
- **fix(mixing):** `get_mix_snapshot` same crash on MIDI-output tracks — same guard applied
- **fix(tracks):** `create_midi_track` / `create_audio_track` left newly created tracks armed — now auto-disarms unless `arm=true` param is passed
- **fix(theory):** `roman_numeral()` failed to recognize 7th chords (Dm7, Gm7, Bbmaj7) — now detects 7th intervals via triad-subset matching with scored best-match selection
- **fix(theory):** `roman_figure_to_pitches()` produced out-of-key pitches (C#, G#) for jazz figures in minor keys — now uses scale-derived chord quality and scale-derived 7th intervals instead of forcing quality from Roman numeral case
- **fix(harmony):** `parse_chord()` rejected "minor seventh", "dominant seventh" and other extended chord qualities — now normalizes to base triad for neo-Riemannian analysis
- **fix(harmony):** `classify_transform_sequence()` only detected single P/L/R transforms — now tries 2-step compound transforms (PL, PR, RL, etc.)
- **fix(theory):** `roman_numeral()` picked wrong chord when 7th created ambiguity (Bbmaj7 matched as Dm instead of Bb) — scoring prefers highest overlap + root-position bonus

## 1.9.18 — Deep Audit Fix Pass (April 2026)

### Critical Fixes
- **fix(tracks):** monitoring enum mismatch — MCP advertised `0=Off,1=In,2=Auto` but Remote Script uses `0=In,1=Auto,2=Off`; clients deterministically chose wrong mode
- **fix(connection):** retry logic could replay mutating commands after `sendall` succeeded — added `_send_completed` flag to prevent double mutations
- **fix(m4l_bridge):** `capture_stop` cancelled in-flight capture future instead of resolving it — callers got `CancelledError` instead of partial result

### Medium Fixes
- **fix(skills):** removed 6 phantom tool names from speed tiers (`analyze_dynamic_range`, `analyze_spectral_evolution`, `separate_stems`, `diagnose_mix`, `transcribe_to_midi`, `compare_loudness`)
- **fix(clip_automation):** added `int()` casts to `send_index`, `device_index`, `parameter_index` — prevented TypeError when MCP sends strings
- **fix(arrangement):** `add_arrangement_notes` now supports `probability`, `velocity_deviation`, `release_velocity` (parity with session `add_notes`)
- **fix(devices/browser):** reset `_iterations` counter per category in URI search — prevented premature cutoff for devices in later categories
- **fix(imports):** standardized 6 engine files from `mcp.server.fastmcp` to `fastmcp` import path
- **fix(docs):** corrected domain count from 32 to 31 (`memory_fabric` is an alias for `memory`) across 17 files
- **fix(server.json):** added missing `, MIDI I/O` to description to match package.json

### Low Fixes
- **fix(clips):** `delete_clip` now checks `has_clip` before deleting
- **fix(arrangement):** `back_to_arranger` no longer reads write-only trigger property
- **fix(utils):** return track error message no longer shows `(0..-1)` when none exist
- **fix(connection):** removed dead `send_command_async` and unused `asyncio` import

## 1.9.17 — Skills Architecture V2 (April 2026)

### Skills (9 new, 1 slimmed)
- **livepilot-core** — slimmed from 900 to ~150 lines. Golden rules, speed tiers, error protocol. Domain content moved to dedicated skills.
- **livepilot-devices** — NEW: device loading, browser workflow, plugin health, rack introspection
- **livepilot-notes** — NEW: MIDI content, theory integration, generative algorithms, harmony tools
- **livepilot-mixing** — NEW: volume/pan/sends, routing, metering, automation patterns
- **livepilot-arrangement** — NEW: song structure, scenes, arrangement view, navigation
- **livepilot-mix-engine** — NEW: critic-driven mix analysis loop (masking, dynamics, stereo, headroom)
- **livepilot-sound-design-engine** — NEW: critic-driven patch refinement loop (static timbre, modulation, filtering)
- **livepilot-composition-engine** — NEW: section analysis, transitions, motifs, form, translation checking
- **livepilot-performance-engine** — NEW: safety-first live performance with energy tracking and move classification
- **livepilot-evaluation** — NEW: universal before/after evaluation loop with capability-aware scoring

### Commands (3 new, 2 updated)
- `/arrange` — NEW: guided arrangement using composition engine
- `/perform` — NEW: safety-constrained performance mode
- `/evaluate` — NEW: before/after evaluation loop
- `/mix` — updated to use mix engine critics
- `/sounddesign` — updated to use sound design engine critics

### Agent
- **livepilot-producer** — updated to reference all 10 skills instead of inline loop definitions

### Plugin Stats
- 11 skills (was 2), 8 commands (was 5), 1 agent, 10 reference files for engine skills
- Total plugin skill metadata: ~1100 words always-in-context (lean triggers)
- Progressive disclosure: SKILL.md bodies ≤2000 words each, detailed content in references/

## 1.9.16 — Comprehensive Bug Fix Audit (April 2026)

### Critical Fixes
- **connection.py** — Don't retry TCP commands after timeout (prevents duplicate mutations in Ableton)
- **connection.py** — Add `send_command_async()` to avoid blocking the asyncio event loop
- **technique_store.py** — Thread-safe initialization with double-checked locking; add missing `_ensure_initialized()` in `increment_replay`
- **capability_state.py** — Fix inverted mode logic: offline analyzer is now correctly more restrictive than stale analyzer
- **server.py** — Fix thread safety: assign `_client_thread` inside lock
- **action_ledger_models.py** — Thread-safe unique IDs with UUID session suffix

### High-Priority Fixes
- **notes.py / arrangement.py** — `modify_notes` now applies `mute`, `velocity_deviation`, `release_velocity` (previously silently dropped)
- **clips.py** — `create_clip` checks `has_clip` first; `set_clip_loop` uses conditional ordering for shrink vs expand
- **notes.py / arrangement.py** — Fix `transpose_notes` default `time_span` when `from_time > 0`
- **m4l_bridge.py** — Clear stale response future after timeout
- **composition.py** — Fix `get_phrase_grid` using section_index as clip_index
- **devices.py** — Fix `_postflight_loaded_device` always reporting plugins as failed
- **tracks.py** — Correct input monitoring enum (0=Off, 1=In, 2=Auto); fix `set_group_fold` allowing return tracks
- **research.py** — Fix browser path casing (`"Instruments"` → `"instruments"`)
- **midi_io.py** — Fix path traversal check prefix collision
- **fabric.py** — Distinguish `measured` vs `measured_reject` decision modes
- **critics.py** — Fix dynamics critic double-counting `over_compressed` + `flat_dynamics`
- **refresh.py** — Deep-copy freshness objects to prevent mutation leak
- **mix_engine/tools.py** — Fix `track_count` key (always 0) → use `len(tracks)`
- **safety.py** — Distinguish `unknown` from `caution` for unrecognized move types
- **translation_engine** — Fix pan values always 0 (check nested `mixer.panning`)
- **livepilot_bridge.js** — Track selection by LiveAPI ID (not name); 4-byte UTF-8 support (emoji)

### Medium Fixes
- Version strings bumped across all files
- `hashlib.md5` calls use `usedforsecurity=False` (FIPS compat)
- `.mcp.json` uses portable `node` command
- README "32 additional tools" → "29"
- Lazy `asyncio.Lock` creation in M4L bridge
- `_friendly_error` now includes `command_type` in output

### Test Improvements
- Tests updated to match corrected capability_state, dynamics critic, and safety logic
- `test_default_name_detection` now imports production function instead of local copy

## 1.9.15 — V2 Engine Architecture (April 2026)

### New Engine Packages (12)
- **Project Brain** — shared state substrate with 5 subgraphs (session, arrangement, role, automation, capability), freshness tracking, scoped refresh
- **Capability State** — runtime capability model (5 domains: session, analyzer, memory, web, research), operating mode inference
- **Action Ledger** — semantic move tracking with undo groups, memory promotion candidates
- **Evaluation Fabric** — unified evaluation layer with 5 engine-specific evaluators (sonic, composition, mix, transition, translation)
- **Memory Fabric V2** — anti-memory (tracks user dislikes), promotion rules, session memory, taste memory (8 extended dimensions)
- **Mix Engine** — 6 critics (balance, masking, dynamics, stereo, depth, translation), move planner with ranking
- **Sound Design Engine** — timbral goals, patch model, layer strategy, 5 critics, move planner
- **Transition Engine** — boundary model, 7 archetypes, 5 critics, payoff scoring
- **Reference Engine** — audio/style profiles, gap analysis with identity warnings, tactic routing to target engines
- **Translation Engine** — playback robustness (mono, small speaker, harshness, low-end, front-element)
- **Performance Engine** — live-safe mode with scene steering, safety policies, energy path planning
- **Safety Kernel** — policy enforcement (blocked/confirm-required/safe action classification, scope limits, capability gating)

### New Infrastructure
- **Conductor** — intelligent request routing to engines with keyword classification (22 patterns across 8 engines)
- **Budget System** — 6 resource pools per turn (latency, risk, novelty, change, undo, research) shaped by mode
- **Snapshot Normalizer** — canonical input normalization for all evaluators
- **Evaluation Contracts** — shared types (EvaluationRequest, EvaluationResult, dimension measurability registry)
- **Research Provider Router** — 6-level provider ladder with mode-based routing and outcome feedback

### Composition Engine Extensions (Rounds 1-4)
- Round 1: HarmonyField, TransitionCritic, OutcomeAnalyzer
- Round 2: MotifGraph, 11 GestureTemplates, TechniqueCards, SectionOutcomes
- Round 3: ResearchEngine (targeted+deep), PlannerEngine (5 styles), EmotionalArcCritic
- Round 4: TasteModel, 6 StyleTactics, FormEngine (9 transforms), CrossSectionCritic, OrchestrationPlanner

### Bug Fixes
- Fix(High): Remove async/await from engine tools — send_command is sync
- Fix(High): Mix engine extracts mixer.volume/panning from nested Remote Script response
- Fix(High): Replace calls to nonexistent commands (get_device_reference, walk_device_tree)
- Fix(Med): Remove refs to nonexistent session fields (last_export_path, selected_scene)
- Fix(Med): Ledger key mismatch — memory promotion now reads correct 'action_ledger' key

### Stats
- 236 tools across 31 domains (was 194)
- 1,014 tests passing (was ~400)
- 12 new engine packages
- 36 new MCP tools

## 1.9.14 — Install Reliability + CI Expansion (April 2026)

- Fix(High): `--install` now shows all detected Ableton directories when multiple exist and accepts `LIVEPILOT_INSTALL_PATH` env var to override — previously silently picked the first candidate which could be wrong
- Fix(Med): FastMCP pinned to `>=3.0.0,<3.3.0` with documented private API dependency (`_tool_manager`, `_local_provider`) — prevents upstream drift from breaking schema coercion
- Fix(Med): CI expanded to multi-OS matrix (Ubuntu + macOS + Windows) and added JS entrypoint validation (syntax check, npm pack asset verification)
- Fix(Low/Med): `--setup-flucoma` now enforces SHA256 checksum (TOFU pattern) — first download records the hash, subsequent installs abort on mismatch
- Fix(Low): `--status` timeout path now resolves `true` when `lsof` detects another LivePilot client on the port — matches the explicit STATE_ERROR fix from v1.9.13
- Verification: 145 tests passing, 178 tools confirmed

## 1.9.13 — Security Hardening + Startup Safety (April 2026)

- Fix(P2): `--setup-flucoma` now pins to a known release tag (v1.0.7) instead of unpinned `latest`, prints SHA256 checksum for verification, and selects the platform-specific zip
- Fix(P2): memory subsystem now uses lazy initialization — `TechniqueStore` defers directory creation to first tool call instead of blocking server startup when HOME is read-only
- Fix(P3): `--status` and `--doctor` now return exit 0 when Ableton is reachable but another client is connected (STATE_ERROR = reachable, not failure)
- Fix(P3): negative `limit` values on `memory_recall` and `memory_list` now raise `ValueError` instead of using Python negative slicing
- Fix: Remote Script no longer logs "Server started" before bind succeeds — "Listening on..." is logged from the server loop after successful bind
- Fix: `requirements.txt` now documents dev dependencies (pytest, pytest-asyncio) as comments
- Verification: 145 tests passing, 178 tools confirmed

## 1.9.12 — Deep Audit: 21 Fixes Across 15 Files (April 2026)

**Full codebase audit — 5 critical, 10 important, 6 doc/test fixes.**

### Critical Fixes
- Fix(P1): `capture_stop` no longer deadlocks — `cancel_capture_future` removed lock acquisition that blocked behind `send_capture`
- Fix(P1): `import_midi_to_clip` now distinguishes empty-slot NOT_FOUND from INDEX_ERROR/TIMEOUT instead of swallowing all AbletonConnectionErrors
- Fix(P1): capture audio files now write to `~/Documents/LivePilot/captures/` (stable path) instead of beside the .amxd preset
- Fix(P1): `check_flucoma` now uses `Folder.end` to detect FluCoMa — `typelist` check was always true
- Fix(P1): CI workflow updated to `actions/checkout@v4` + `actions/setup-python@v5` (v6 doesn't exist)

### Safety & Validation
- Fix(P2): 5 automation tools now validate `track_index >= 0` and `clip_index >= 0` (matching all peer modules)
- Fix(P2): `cmd_stop_scrub` now checks `cursor_a.id === 0` for empty clip slots (matching all peer bridge functions)
- Fix(P2): `cmd_get_selected` now resolves return tracks (negative indices) and master track (-1000)
- Fix(P2): `duplicate_track` uses count-before/after delta for correct group track duplication index
- Fix(P2): `create_arrangement_clip` locates first clip by `start_time` instead of stale index after trim pass
- Fix(P2): `get_session_info` reuses already-built lists instead of re-iterating `song.tracks`/`song.scenes`
- Fix(P2): client disconnect race — socket now closes before clearing `_client_connected` flag

### Tests
- Fix: transport validation tests now import production `_validate_tempo`/`_validate_time_signature` instead of testing local copies
- Fix: added `load_sample_to_simpler` to analyzer tool contract (was 28/29)
- Fix: removed duplicate `test_release_quick_verify_checks_both_plugin_manifests`
- New: 5 automation negative tests (index validation, parameter_type validation)

### Documentation
- Fix: `docs/manual/index.md` domain map — Tracks 14→17, Devices 12→15, Scenes 8→12
- Fix: README perception split — 145+33 → 149+29 (actual analyzer tool count is 29)
- Fix: M4L_BRIDGE.md command count — 22→28 (6 commands undocumented)
- Fix: tool-reference.md MIDI docs — `export_clip_midi` and `import_midi_to_clip` parameter tables matched to actual signatures

### Deferred (documented, low-impact)
- Timed-out commands still execute on main thread (needs cancellation token redesign)
- Chunked UDP reassembly fragile on packet loss (loopback mitigates)
- Diatonic transpose octave correction edge case (needs musical test suite)
- `cmd_map_plugin_param` reports false success (LiveAPI lacks Configure mapping API)

Verification: 145 tests passing (non-fastmcp), 178 tools confirmed, 15 files changed

## 1.9.11 — Session Diagnostics + Client Conflict Clarity (March 2026)

**Live-tested against the open Ableton set after reloading the updated Remote Script.**

- Fix(P1): device loading now surfaces post-load plugin health hints, including `opaque_or_failed_plugin`, `sample_dependent`, `plugin_host_status`, and `mcp_sound_design_ready`
- Fix(P1): `get_session_diagnostics` now flags opaque/sample-dependent plugins and no longer crashes on track types that omit standard `arm`/`mute`/`solo` properties
- Fix(P1): analyzer tools now distinguish between “analyzer missing” and “analyzer loaded but bridge/client conflict” when UDP 9880 is unavailable
- Fix(P1): add Hijaz / Phrygian Dominant theory support across key parsing, scale construction, chord building, and `identify_scale`
- Fix(P2): `--status` and TCP timeout paths now explain when another LivePilot client appears to be connected instead of only reporting a generic timeout
- Docs: beat/sounddesign/core skill guidance now includes device-health checks, sample-dependent plugin cautions, and pitch-audit discipline from the live stress-test sessions
- Verification: `292 passed`, `npm pack --dry-run` passed, live set diagnostics succeeded, analyzer bridge streamed on the master track, and conflict reproduction now reports the competing client PID
- Fix(P1): brownian automation curve reflection loop now has 100-iteration guard with hard clamp fallback — high volatility values could previously hang the server
- Fix(P1): schema coercion now recurses into array `items` so `list[float]` params benefit from string-to-number widening for MCP clients that serialize as strings
- Fix(P1): `apply_automation_shape` and `apply_automation_recipe` now validate `parameter_type` and required companion params before sending to Ableton
- Fix(P2): Remote Script `AssertionError` fallbacks now return STATE_ERROR instead of running LOM calls on the TCP thread during ControlSurface disconnection
- Fix(P2): M4L bridge ping version corrected to 1.9.11; `check_flucoma` now probes disk for FluCoMa package instead of returning hardcoded `true`
- Verification: deep audit across 45+ files (3 parallel agents), 292 unit tests + 15 live integration tests against Ableton session, all passing

## 1.9.10 — Analyzer Capture Finalization + Release Sync (March 2026)

**Live-tested in Ableton after a full analyzer rebuild and master-track validation.**

- Fix(P1): `capture_audio` now writes finalized WAV files instead of header-only stubs by correcting the `sfrecord~` start/stop messages in the analyzer patch
- Fix(P1): add a small delayed record start in `LivePilot_Analyzer.maxpat` to avoid the open/start race on fresh capture writes
- Fix(P2): normalize Max-style `Macintosh HD:/Users/...` file paths to POSIX paths in the Python bridge and offline perception tools
- Fix(P2): make OSC string args Unicode-safe end to end with ASCII-safe `b64:` transport and Max-side UTF-8 decode
- Fix(P2): arrangement automation unsupported cases now surface as outer MCP errors instead of fake success payloads
- Fix(P2): missing required Remote Script params now return `INVALID_PARAM` consistently
- Fix(P3): release metadata now treats Codex as the primary plugin manifest with Claude as a mirrored manifest
- Verification: live `capture_audio` wrote a 1.48s WAV from the master track; offline loudness + metadata reads succeeded on the returned path

## 1.9.9 — M4L Bridge Hardening + Deep Audit (March 2026)

**87 tools tested live, 0 failures. 13 bugs fixed across JS bridge + Python tools.**

### M4L Bridge (livepilot_bridge.js)
- Fix(P0): Remove `str_for_value` from all batched JS readers — Auto Filter hangs Max's JS engine (uncatchable), binary-patched .amxd
- Fix(P1): Deferred `udpsend` socket re-initialization via `deferlow` — fixes UDP not sending when device loads from a saved Live Set (socket fails to bind on frozen device restore)
- Fix(P1): Add try-catch to ALL Task.schedule batch functions: cmd_get_params, cmd_get_hidden_params, cmd_get_display_values, cmd_get_auto_state, cmd_get_plugin_params — prevents silent crash on parameter read errors
- Fix(P1): cmd_get_chains_deep, cmd_get_track_cpu, cmd_map_plugin_param — added missing error handling
- Fix(P2): Add `dspstate~` → JS inlet 1 for sample rate reporting (was declared in JS but missing from patcher)
- Fix(P2): Deferred `snapshot~` re-activation via `live.thisdevice` → `deferlow` — safety net for frozen device reload
- Perf: Batch size 4→8, delay 50→20ms (2.5× faster parameter reads)
- Fix: Binary-patch openinpresentation 0→1 in .amxd

### Python MCP Server
- Fix(P1): classify_progression accepts dict inputs `{"root": "F#", "quality": "minor"}` in addition to strings
- Fix(P1): Higher bridge timeouts — hidden_params 15s, display_values 15s, auto_state 10s, plugin_params 20s, plugin_presets 15s, map_plugin 10s
- Fix(P1): load_sample_to_simpler wraps send_command calls in try-except (prevents AbletonConnectionError propagation)
- Fix(P2): _ensure_list catches json.JSONDecodeError → ValueError (6 files: notes, devices, generative, scenes, harmony, automation)
- Fix(P2): _get_m4l/_get_spectral raise ValueError instead of RuntimeError (FastMCP compatibility)

## 1.9.7 — Safe automation fallback + correct clip length reporting (March 2026)

- Fix(P1): set_arrangement_automation places replacement BEFORE deleting original — no data loss if placement fails
- Fix(P2): get_arrangement_clips reports timeline length (not loop span) as length/end_time; loop info as separate fields
- Reverted the effective-length mangling that misreported looped clip sizes

## 1.9.6 — Arrangement clip identification + expression data (March 2026)

- Fix(P1): create_arrangement_clip now identifies new clips by object identity, not position match — prevents mutating pre-existing overlapping clips
- Fix(P2): set_arrangement_automation fallback preserves probability, velocity_deviation, release_velocity when rebuilding notes
- Fix(P2): get_arrangement_clips effective length uses loop_end - loop_start (not just loop_end)

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

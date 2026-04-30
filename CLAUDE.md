# LivePilot v1.23.4 — Ableton Live 12

## Project
- **Repo:** This directory (LivePilot)
- **Type:** Agentic MCP production system for Ableton Live 12
- **Three layers:** Device Atlas (knowledge) + M4L Analyzer (perception) + Technique Memory (learning)
- **Sister projects:** TDPilot (TouchDesigner), ComfyPilot (ComfyUI)
- **Design spec:** `docs/specs/2026-03-17-livepilot-design.md`
- **Dev install runbook:** `docs/manual/dev-install.md` — run from a local checkout (venv + `node bin/livepilot.js --install` + point MCP client at `python -m mcp_server` directly); use this whenever iterating on `mcp_server/` or `remote_script/` without republishing to npm

## Architecture
- **Remote Script** (`remote_script/LivePilot/`): Runs inside Ableton's Python, ControlSurface base class, TCP socket on port 9878. Version detection at startup, four capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+), Collaborative (12.4+)
- **MCP Server** (`mcp_server/`): Python FastMCP server, validates inputs, sends commands to Remote Script
- **M4L Bridge** (`m4l_device/`): Max for Live Audio Effect on master track, UDP/OSC bridge for deep LOM access
  - UDP 9880: M4L -> Server (spectral data, responses)
  - OSC 9881: Server -> M4L (commands)
  - `livepilot_bridge.js`: 32 bridge commands for LiveAPI access
  - `SpectralCache`: thread-safe, time-expiring data cache (5s max age)
  - Bridge is optional — all core tools work without it
- **Device Atlas** (`mcp_server/atlas/`): In-memory indexed JSON database — 5264 devices with URIs (bundled baseline), 120 enriched with sonic intelligence (YAML), 47 with aesthetic-tagged `signature_techniques`. **7 indexes**: by_id, by_name, by_uri, by_category, by_tag, by_genre, by_pack . Reverse-index `device_techniques_index.json` (146 cross-references across 58 devices) powers `atlas_techniques_for_device`. Tools: `atlas_search`, `atlas_suggest`, `atlas_chain_suggest`, `atlas_compare`, `atlas_device_info`, `atlas_pack_info` (v1.17), `atlas_describe_chain` (v1.17 — free-text, mirror of `splice_describe_sound`), `atlas_techniques_for_device` (v1.17 — reverse-lookup), `scan_full_library`, `reload_atlas`. **v1.22.0**: atlas now resolves from `~/.livepilot/atlas/device_atlas.json` (user scan) if present, else the bundled baseline. `scan_full_library` writes to the user path — never the bundled one — so personal inventories (packs, user_library, plugins) stay out of the repo and survive npm updates. See `BUNDLED_ATLAS_PATH` / `USER_ATLAS_PATH` / `_resolve_atlas_path()` in `mcp_server/atlas/__init__.py`
- **Concept surface** (`livepilot/skills/livepilot-core/references/`): **v1.17+** translation layer between LLM training and LivePilot tools. `artist-vocabularies.md` maps ~25 producers (Villalobos, Hawtin, Basic Channel, Gas, Basinski, Hecker, Aphex, Autechre, OPN, Arca, Dilla, Premier, Madlib, Burial, Henke, Daft Punk, Photek, Com Truise, Boards of Canada) to `sonic_fingerprint` / `reach_for` / `avoid` / `key_techniques`. `genre-vocabularies.md` maps 15 genres (microhouse, dub_techno, deep_minimal, minimal_techno, ambient, idm, modern_classical, hip_hop, trap, dubstep, house, dnb, garage, experimental, synthwave) to tempo / kick / bass / percussion / harmonic / texture / reach-for / avoid. Read these BEFORE device selection when the user says "sound like X" or "make me a <genre> track"
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
- 453 tools across 54 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory, analyzer, automation, theory, generative, harmony, midi_io, perception, agent_os, composition, motif, research, planner, project_brain, runtime, evaluation, mix_engine, sound_design, transition_engine, reference_engine, translation_engine, performance_engine, song_brain, preview_studio, hook_hunter, stuckness_detector, wonder_mode, session_continuity, creative_constraints, device_forge, sample_engine, atlas, composer, experiment, musical_intelligence, semantic_moves, diagnostics, follow_actions, grooves, scales, take_lanes, miditool, synthesis_brain, creative_director, user_corpus
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL
- **LivePilot_Analyzer must be LAST on master** — always after ALL effects (EQ, Compressor, Utility) so it reads the final output, not pre-effect signal
- **Single TCP client** — Remote Script accepts one connection at a time on port 9878. The MCP server holds a persistent connection. Direct TCP calls will fail with "Another client is already connected" if the MCP server is active. Always use MCP tools, not raw TCP
- **Remote Script reload workflow** — after ANY edit to `remote_script/LivePilot/*.py`: run `npx livepilot --install` (NOT `node installer/install.js` — that file only exports the function and is a no-op as a script), then call the `reload_handlers` MCP tool. NEVER manually toggle the Control Surface in Live → Preferences → Link/MIDI. The `reload_handlers` tool uses pkgutil + importlib to re-fire `@register` decorators in-place while the MCP TCP connection stays open. Apply this standard procedure every time handlers change — bug fix, new tool, or release

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

### MCPB bundle (REQUIRED for every release)
After version files are synced and the GitHub release is created, build + attach the MCPB bundle. The README promises a `.mcpb` one-click install; from v1.17–v1.20.2 every release silently shipped without it. Never ship a release without this step:
```bash
bash scripts/build_mcpb.sh   # produces dist/livepilot-${VERSION}.mcpb (~4-5 MB)
VERSION=$(python3 -c "import json; print(json.load(open('manifest.json'))['version'])")
gh release upload "v${VERSION}" "dist/livepilot-${VERSION}.mcpb" --clobber
```
The script is the source of truth — it stages only the MCPB runtime (manifest, bin/livepilot.js, mcp_server, remote_script, m4l_device, installer, requirements.txt), strips caches, and post-build verifies the embedded manifest name/version/entry_point.

### Post-push marketplace mirror sync (REQUIRED — stale-mirror trap)
After `git push origin main` + `git push --tags` + `gh release create`, verify Claude Code's local marketplace mirror picked up the new commit:
```bash
cd ~/.claude/plugins/marketplaces/dreamrec-LivePilot && git fetch && git reset --hard origin/main
cat .claude-plugin/marketplace.json | python3 -c "import json,sys; print(json.load(sys.stdin)['plugins'][0]['version'])"
```
Expected output: the new version string. If the mirror is stale (happened silently across v1.18.0-v1.18.3 — panel stuck at "1.17.5 installed"), Claude Code's plugin panel will show the old version and `Update` button points at a stale target. The mirror is a git clone that Claude Code fetches from but does NOT auto-pull. Hard-reset is safe — nothing writes to it locally.

## Tool Count
Currently 453 tools (up from 437 in Phase F — added atlas_pack_aware_compose + atlas_cross_pack_chain; up from 434 in Phase C — added atlas_transplant; up from 433 in v1.23.3 — added atlas_macro_fingerprint in v1.23.4; up from 430 in v1.22.x — added 3 extension_atlas_* tools in v1.23.0; up from 403 in v1.15.0-beta originally). If adding/removing tools, update: README.md, package.json description, livepilot/.Codex-plugin/plugin.json, livepilot/.claude-plugin/plugin.json, server.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, CLAUDE.md, CHANGELOG.md, tests/test_tools_contract.py, docs/manual/index.md, docs/manual/tool-reference.md

## Splice plan-aware model (v1.15.0-beta)
Sample downloads now use plan-aware gating (`mcp_server/splice_client/client.py::decide_download`):
- **Ableton Live plan** ($12.99/mo): 100 samples/day via local daily-quota tracker (`mcp_server/splice_client/quota.py`), resets UTC midnight. Sample downloads do NOT deplete credits on this plan.
- **Sounds+ / Creator / Creator+**: `CREDIT_HARD_FLOOR=5` still applies — agent cannot drain monthly credits past the floor.
- **Free samples** (`IsPremium=False` OR `Price=0`): bypass both gates.
- Plan detection reads `User.SoundsStatus`, `User.SoundsPlan`, `User.Features` from `ValidateLogin`.

New Splice MCP tools: `splice_preview_sample` (zero-cost audition via `PreviewURL`), `splice_list_collections` / `splice_search_in_collection` / `splice_add_to_collection` / `splice_remove_from_collection` / `splice_create_collection` (taste-scoped search via user's Likes/bass/keys folders), `splice_list_presets` / `splice_preset_info` / `splice_download_preset` (purchased instrument presets), `splice_pack_info`.

## Domain Count
Currently 54 domains. A domain = the subdirectory under `mcp_server/` (or file under `mcp_server/tools/`) that contains `@mcp.tool()`. Source of truth is the module layout — no hand-maintained list. If adding/removing domains, update: README.md, package.json, manifest.json, CLAUDE.md, AGENTS.md, .claude-plugin/marketplace.json, livepilot/.claude-plugin/plugin.json, livepilot/.Codex-plugin/plugin.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, livepilot/skills/livepilot-release/SKILL.md, docs/manual/index.md, docs/manual/tool-catalog.md, docs/manual/tool-catalog-generated.md, tests/test_tools_contract.py. Run `python scripts/sync_metadata.py --check` to enforce count + inline list (or `--fix` for mechanical fixes).

---

# LivePilot — Behavioral Rules (always loaded, binding)

These rules are derived from feedback memories at
`~/.claude/projects/-Users-visansilviugeorge-Desktop-DREAM-AI-LivePilot/memory/feedback_*.md`.
Each rule corresponds to a specific incident the user had to correct manually —
they are not suggestions.

## §1 — Default Preset Energy is Forbidden

**Hard rule** (from `feedback_stop_loading_default_presets.md`): never reach for
Analog/Poli/Drift as a default for bass/pad/lead unless the user explicitly asked
for "analog subtractive". They read as "generic AI synth" and have been rejected
multiple times.

**Library hunting order BEFORE choosing any instrument:**
1. `search_browser(path="sounds", name_filter="<role>")` — factory `.adg` curated chains
2. `atlas_search(query="<sonic description>", category="instruments")` — scored matches
3. `search_browser(path="instruments", name_filter="<name>")` — named synths
4. Factory packs on disk (`~/Music/Ableton/Factory Packs/`) — Granulator III, Drone Lab,
   PitchLoop89, Inspired by Nature, etc.

For "alive" sounds prefer **sample-based / physical-modeling / granular** sources
over subtractive synthesis.

**Pad-specific:** Poli and Meld are M4L opaque devices the sound-design critic
can't analyze. Avoid them for that structural reason — you can't tune what you
can't measure.

## §2 — Sound Design = Instrument Programming, NOT Effects Chains

**From `feedback_sound_design_instrument_level.md`:** when the user asks for
"more sound design" or "fresher sound design", **OPEN THE INSTRUMENT FIRST**
and program these parameters BEFORE adding any audio effect:

**Simpler/Sampler:** `Pe < Env` + `Pe Decay` (pitch envelope), `Fe < Env` +
`Fe Attack` + `Fe Decay` (filter envelope), `Detune`, `Spread`, `S Start` +
modulation, LFO routing (`Pitch < LFO`, `Filt < LFO`, `Vol < LFO`,
`Pan < LFO`, `Pan < Rnd`), `Fade In`/`Fade Out`.

**Synth (Drift/Wavetable/Operator/Analog):** oscillator shape/position/sync/FM,
modulation matrix (env→osc, LFO→filter, vel→vol, keytrack), filter envelope
amount + decay shape, unison count + spread + detune, per-voice random.

**Signal:** "warmer/brighter/crunchier" → effect. "more characterful / more
alive / more YOU" → instrument parameters. Effects come AFTER the source is
sculpted.

## §3 — Analysis Before Action (Never write a value you haven't read)

- Before `set_device_parameter` → `get_device_parameters` first.
- Before mixing moves → `analyze_mix` / `get_mix_issues` / `get_masking_report`.
- Before slice programming on a sliced break → spectral classification per
  slice (`get_simpler_slices` + solo-trigger `get_master_spectrum` OR offline
  numpy spectral analysis on the source WAV). Never assume "slice 0 = kick".
  See `feedback_analyze_slices_before_programming.md` for the canonical
  classification thresholds.
- Before arrangement moves → `analyze_phrase_arc` / `get_section_outcomes` /
  `analyze_composition`.
- After `load_browser_item` → `get_track_info(track_index)` and verify
  `devices[0].name` matches the expected filename stem
  (`feedback_load_browser_item_is_source_of_truth.md` — the bootstrap-and-replace
  flow has a silent failure mode where the wrong sample loads).

## §4 — Modulation > Static (no static layers)

For any creative move that benefits from movement (basically all of them), prefer:

- **Automation curves**: `set_clip_automation`, `generate_automation_curve`,
  `apply_automation_recipe`, `set_arrangement_automation`
- **Modulation matrix**: wavetable mod targets, drift mod matrix (3 sources ×
  multiple destinations — every pad should have ≥1 routing), rack macro mod
- **Follow actions**: clip-level + scene-level
- **Euclidean rhythms**: `generate_euclidean_rhythm`, `layer_euclidean_rhythms`

Static MIDI at default velocity ≈ "didn't try". Every melodic/harmonic layer
should have AT LEAST one parameter moving over time (subtle pitch bend on key
notes, filter cutoff sweep, LFO on detune, envelope mod for evolving timbre,
volume-per-phrase, send automation on key moments).

## §5 — Layer-by-Layer Precision Standard

**From `feedback_layer_by_layer_precision.md`:** apply the depth of the
2026-04-25 hi-hat critique to **every** layer of every production. Per-layer
checklist before declaring it done:

1. **Timbre via spectrum** — solo + `get_master_spectrum`. Hat = AIR + PRESENCE
   should dominate (mid-dominant = wrong sample). Snare = MID body +
   PRESENCE/HIGH. Kick = SUB_LOW + MID click. Bass = SUB + LOW + LOW_MID.
2. **Sequence critique** — swing % (50% = robotic; 55-65% for groove),
   humanization (vel ±5, timing ±2-3%, no two notes byte-identical), ghost
   notes (16ths at vel 25-45), bar-by-bar variation, micro-timing pocket,
   dynamic shape, fills (bar 4 ≠ bars 1-3), note duration variation.
3. **Stereo image** — width via Spread/Unison, per-note pan automation where
   appropriate. Bass mono. Pad wide. Hocket layers panned hard L/R.
4. **Compounding on master** — un-soloed, do the layer's frequencies fight
   others (masking)? Same sub as kick = mud. Same air as cymbals = shrill.
5. **Automation/modulation** — see §4. Mandatory.
6. **Synth parameter knowledge** — read the device-knowledge reference BEFORE
   setting params. Do NOT guess parameter ranges. Always read `value_string`
   after a set to verify the actual value matches intent.
7. **Sample audition** — never grab "Hihat Closed 5" because it's the 5th in
   the list. Audition by spectrum (solo + spectrum read) before committing.
8. **Effects chain on individual tracks** — not just sends. EQ to shape,
   Saturator for character, Compressor for glue, Chorus/Delay for depth.

## §6 — Creative Director Path for Open-Ended Requests

When the user says **"make it interesting" / "develop this" / "mutate" /
"take it somewhere" / "more interesting" / "less generic" / "sound like X"**:

→ **INVOKE the `livepilot:livepilot-creative-director` skill.** It exists
exactly for this. Don't roll your own generic production move.

For "sound like X": read `livepilot/skills/livepilot-core/references/
artist-vocabularies.md` (~25 producers mapped to `sonic_fingerprint` /
`reach_for` / `avoid` / `key_techniques`) and `genre-vocabularies.md` (15
genres) BEFORE device selection.

## §7 — Production Workflow Standard (anti-patterns)

**From `feedback_workflow_standard.md`:** four chronic anti-patterns to break.

1. **Research broadly and continuously** — Ableton blog
   (`ableton.com/en/blog/tags/techniques/sound-design/`), artist features,
   forums, tutorial channels (Andrew Huang, Multiplier, Red Means Recording).
   Sweep the producer landscape, don't fixate on Caribou/Burial. Use
   `WebSearch`/`WebFetch` as a regular reflex.
2. **No repeated-preset defaults** — maintain a "USED THIS SESSION" mental
   list. For each role, pick something NOT used in recent sessions. Inspired
   by Nature pack (Pluck, Tree Tone, Drone Lab, Vector FM/Grain, Bouncy Notes,
   Frame), Tension, Granulator III, Electric, Drum Synths, Sampler, Collision —
   under-used.
3. **No layer accumulation with low volume** — 5–6 GREAT layers prominent >
   12 mediocre layers buried. If a layer needs to be at 0.15-0.25 volume, the
   answer is DELETE IT, not bury it.
4. **Vocals are the chronic weak point** — never "good enough" vocals. Either
   GREAT or DELETED. Real techniques: granular vocal cloud (Granulator III on
   long sustained vocal), vocoder + synth carrier, chopped phrase macro-edits,
   pitched vocal chops, stutter+reverse+glitch, resonator+vocoder cross-synth,
   layered vocal samples for chord harmonization (not pitch-shift one).
5. **Active feedback loop, not waterfall** — build ONE LAYER, ask for feedback,
   iterate, then move on. Don't batch 20 changes and re-fire the scene.
6. **Slow down** — quality > speed. A 4-bar loop done RIGHT > 64-bar
   arrangement done generic.

## §8 — Aesthetic-Register Match (genre ≠ emotion)

**From `feedback_pad_aesthetic_register.md`:** when the user references a
producer/genre but in the same breath asks for a clean emotional register
("sublime", "romantic", "dreamy"), match the **emotion** over the
**genre-accuracy gear chain**.

Example: "BoC" + "sublime romantic pad" → Isolée-school clean lush chain
(Drift + Chorus-Ensemble + Reverb), NOT BoC's actual cassette-as-preamp
(Vinyl Distortion + Erosion). The tape character kills the romantic feel.

## §9 — End-of-Session Verification

Before declaring done, run the depth audit:

- `analyze_mix` on master
- `analyze_loudness` (or `analyze_loudness_live`)
- `analyze_sound_design` (if synth work touched)
- `analyze_phrase_arc` (if arrangement work)
- `get_session_diagnostics`
- `evaluate_move` on the last significant change

A good session has analyzed itself. Ship the audit alongside the build.

## §10 — Research First (>=2 failed attempts)

Mirror of TDPilot CLAUDE.md §2. After 2 failed attempts on the same problem,
PIVOT to research:

1. `atlas_search` / `atlas_chain_suggest` / `atlas_techniques_for_device`
2. `search_browser` / `splice_describe_sound` / `splice_search_in_collection`
3. `WebSearch` / `WebFetch` for forum threads, artist interviews, technique demos
4. `mcp__plugin_context7_context7__query-docs` for any external library

Don't iterate blind past 2.

## §11 — End-of-Turn Discipline

End-of-turn summary: 1–2 sentences. What changed and what's next. The
transcript shows the diff. Do not re-explain every layer touched.

## §12 — Public Artifacts Stay Generic

**From `feedback_no_theme_in_public_artifacts.md`:** creative themes
(artist names, genre vocabularies, sonic descriptors) and the user's
prompt text NEVER go into artifacts pushed to a public remote.

**Banned in:** PR titles/bodies, commit messages (subject AND body),
`BUGS.md`, `CHANGELOG.md`, `README.md`, public docs, branch names if
shared, release notes.

**OK:** BPM, date (`YYYY-MM-DD`), time signature, tool/file/line counts,
generic role names ("kick"/"snare"/"vocal"/"atmos"), bug numbers,
technical artifact names (function names, parameter names).

**Banned content:** artist names from
`livepilot/skills/livepilot-core/references/artist-vocabularies.md`,
genre names from `genre-vocabularies.md`, sonic descriptors that imply
theme ("Memphis cowbell", "BoC sing-weep"), the user's literal prompt
text, sample lyrics / MC chants.

**Replacement template:** `<BPM> BPM production session, <YYYY-MM-DD>`.

**Retroactive cleanup if already pushed:** `gh pr edit <num>` to redact
title/body, soft-reset + recommit + `git push --force-with-lease` to
redact commit messages, push corrected `BUGS.md`/`CHANGELOG.md`. Verify
on GitHub web UI.

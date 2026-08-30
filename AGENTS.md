# LivePilot v1.30.0 — Ableton Live 12

## Project
- **Repo:** This directory (LivePilot)
- **Type:** Agentic MCP production system for Ableton Live 12
- **Three layers:** Device Atlas (knowledge) + M4L Analyzer (perception) + Technique Memory (learning)
- **Sister projects:** TDPilot (TouchDesigner), ComfyPilot (ComfyUI)
- **Historical design snapshot:** `docs/specs/2026-03-17-livepilot-design.md` (March 2026 baseline; current truth lives in README/CLAUDE/AGENTS/manual + `scripts/sync_metadata.py`)

## Architecture
- **Remote Script** (`remote_script/LivePilot/`): Runs inside Ableton's Python, ControlSurface base class, TCP socket on port 9878. Version detection at startup, four capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+), Collaborative (12.4+)
- **MCP Server** (`mcp_server/`): Python FastMCP server, validates inputs, sends commands to Remote Script
- **M4L Bridge** (`m4l_device/`): Max for Live Audio Effect on master track, UDP/OSC bridge for deep LOM access
  - UDP 9880: M4L -> Server (spectral data, responses)
  - OSC 9881: Server -> M4L (commands)
  - `livepilot_bridge.js`: 32 bridge commands for LiveAPI access
  - `SpectralCache`: thread-safe, time-expiring data cache (5s max age)
  - Bridge is optional — all core tools work without it
  - `ensure_analyzer_on_master` (v1.20.3) auto-loads the device on first use
- **Device Atlas** (`mcp_server/atlas/`): In-memory indexed JSON database — 5264 devices with URIs, 120 enriched with sonic intelligence (YAML), 47 with aesthetic-tagged `signature_techniques`. **7 indexes**: by_id, by_name, by_uri, by_category, by_tag, by_genre, by_pack . Reverse-index `device_techniques_index.json` (146 cross-references across 58 devices) powers `atlas_techniques_for_device`. Tools: `atlas_search`, `atlas_suggest`, `atlas_chain_suggest`, `atlas_compare`, `atlas_device_info`, `atlas_pack_info`, `atlas_describe_chain`, `atlas_techniques_for_device`, `scan_full_library`, `reload_atlas`
- **Concept surface** (`livepilot/skills/livepilot-core/references/`): translation layer between LLM training and LivePilot tools. `artist-vocabularies.md` maps ~25 producers (Villalobos, Hawtin, Basic Channel, Gas, Basinski, Hecker, Aphex, Autechre, OPN, Arca, Dilla, Premier, Madlib, Burial, Henke, Daft Punk, Photek, Com Truise, Boards of Canada) to `sonic_fingerprint` / `reach_for` / `avoid` / `key_techniques`. `genre-vocabularies.md` maps 15 genres (microhouse, dub_techno, deep_minimal, minimal_techno, ambient, idm, modern_classical, hip_hop, trap, dubstep, house, dnb, garage, experimental, synthwave) to tempo / kick / bass / percussion / harmonic / texture / reach-for / avoid. Read these BEFORE device selection when the user says "sound like X" or "make me a <genre> track"
- **Sample Engine** (`mcp_server/sample_engine/`): Three-source sample intelligence — BrowserSource (Ableton browser), SpliceSource (local sounds.db SQLite), FilesystemSource (user dirs). 6-critic fitness battery, 29-technique library, Surgeon/Alchemist dual philosophy
- **Splice Client** (`mcp_server/splice_client/`): gRPC client for Splice desktop API. Port auto-detected from port.conf, TLS with self-signed certs. Credit safety floor of 5. Plan-aware download gating (Ableton Live plan: 100 samples/day; Sounds+/Creator: credit floor); see §Splice plan-aware model below
- **Composer** (`mcp_server/composer/`): Prompt → plan pipeline. Parses NL into CompositionIntent (genre/mood/tempo/key), plans layers with role templates, compiles to executable tool sequences. 4 genre defaults
- **Corpus** (`mcp_server/corpus/`): Parsed device-knowledge markdown → queryable Python structures (EmotionalRecipe, GenreChain, PhysicalModelRecipe, AutomationGesture). Fed to Wonder Mode, Sound Design critics, Composer
- **Execution Router** (`mcp_server/runtime/execution_router.py`): Classifies steps as remote_command/bridge_command/mcp_tool/unknown, dispatches correctly. `CompiledStep.optional=True` supports soft-gated steps (e.g., analyzer pre-reads that skip-and-continue on failure)
- **Semantic Moves** (`mcp_server/semantic_moves/`, `mcp_server/sample_engine/moves.py`): 44 musical intents across 7 families (mix, arrangement, transition, sound_design, performance, device_creation, sample). `apply_semantic_move` compiles a move into concrete tool calls based on current session topology
- **Creative Director** (`livepilot/skills/livepilot-creative-director/`): Phase-based operational contract. Phase 1 calls `ensure_analyzer_on_master` at the top of every turn, then parallel ground reads. Phase 3 generates three plans with distinct move families. Phase 5 previews. Phase 6 commits with evaluation.
- **Plugin** (`livepilot/`): Codex plugin (primary manifest: `.Codex-plugin/plugin.json`, Claude mirror: `.claude-plugin/plugin.json`)
- **Installer** (`installer/`): Auto-detects Ableton path, copies Remote Script

## Key Rules
- ALL Live Object Model (LOM) calls must execute on Ableton's main thread via schedule_message queue
- Live 12 minimum — use modern note API (add_new_notes, get_notes_extended, apply_note_modifications)
- 474 tools across 57 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory, analyzer, automation, theory, generative, harmony, midi_io, perception, agent_os, composition, motif, research, planner, project_brain, runtime, evaluation, mix_engine, sound_design, transition_engine, reference_engine, translation_engine, performance_engine, song_brain, preview_studio, hook_hunter, stuckness_detector, wonder_mode, session_continuity, creative_constraints, device_forge, sample_engine, atlas, composer, experiment, musical_intelligence, semantic_moves, diagnostics, follow_actions, grooves, scales, take_lanes, miditool, synthesis_brain, creative_director, user_corpus, audit, grader, listening
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL
- **LivePilot_Analyzer must be LAST on master** — always after ALL effects (EQ, Compressor, Utility) so it reads the final output, not pre-effect signal. `ensure_analyzer_on_master` (v1.20.3) reports `is_last_on_master` and warns on violation
- **Single TCP client** — Remote Script accepts one connection at a time on port 9878. The MCP server holds a persistent connection. Direct TCP calls will fail with "Another client is already connected" if the MCP server is active. Always use MCP tools, not raw TCP
- **Remote Script reload workflow** — after ANY edit to `remote_script/LivePilot/*.py`: install, then call the `reload_handlers` MCP tool. **From a local checkout (this repo) the install command is `node bin/livepilot.js --install`** — `npx livepilot --install` downloads the PUBLISHED npm package and would overwrite your local edits with stale code (reload_handlers then "succeeds" on the old handlers). Use `npx livepilot --install` only when installing the published package for end-user use. (Either way, NOT `node installer/install.js` — that file only exports the function and is a no-op as a script.) NEVER manually toggle the Control Surface in Live → Preferences → Link/MIDI. The `reload_handlers` tool uses pkgutil + importlib to re-fire `@register` decorators in-place while the MCP TCP connection stays open. Apply this standard procedure every time handlers change — bug fix, new tool, or release. See `docs/manual/dev-install.md`

## M4L Bridge Notes
- OSC addresses must be sent WITHOUT leading `/` — Max `udpreceive` passes `/` as part of messagename
- `str_for_value` requires `call()` not `get()` (it's a function)
- `get()` in Max JS LiveAPI always returns arrays
- `warp_markers` is a dict property returning JSON string — use `JSON.parse()`
- `SimplerDevice.slices` lives on the `sample` child, not the device
- M4L `replace_sample` only works on Simplers with existing samples; Live 12.4+ native `replace_sample_native` can route around that limitation when available
- Max freezes JS from search path cache, not source directory — copy to `~/Documents/Max 9/`

## Binary Patching Workflow (.amxd)
When modifying .amxd attributes that Max editor won't persist (e.g., `openinpresentation`):
1. Find the byte sequence in the .amxd binary
2. Replace with same-byte-count alternative (file size must not change)
3. Test by loading in Ableton
4. Structure: 24-byte `ampf` header + `ptch` chunk + `mx@c` header + JSON patcher + frozen deps

## Version Bump

**Do not hand-maintain this list — verify with `python3 scripts/sync_metadata.py --check`.** That
script is the enforced source of truth and CI runs it (`metadata-drift`). The list below is a
reading aid; if the two ever disagree, the script wins.

Auto-enforced by `sync_metadata.py`: `package.json`, `package-lock.json` (must match
package.json), `server.json` (Marketplace reads this), `manifest.json`,
`livepilot/.Codex-plugin/plugin.json`, `livepilot/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `mcp_server/__init__.py`,
`remote_script/LivePilot/__init__.py`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`,
`README.md` ("What's New" header), `livepilot/skills/livepilot-core/references/overview.md`,
`livepilot/skills/livepilot-evaluation/references/capability-modes.md`, `docs/M4L_BRIDGE.md`
(ping version string).

**NOT covered by `--check`, and the one that silently breaks a release:**

- **`m4l_device/livepilot_bridge.js` — the `var VERSION` const.** This is the version the frozen
  device reports on `ping`, and Python gates capabilities on it
  (`TOKEN_AUTH_MIN_BRIDGE_VERSION` in `mcp_server/m4l_bridge.py`). **Bump it BEFORE freezing.**
  Freezing while it still holds the old string bakes that string into the binary permanently and
  silently disables every version-gated feature, while every manifest correctly reports the new
  version. This is the failure mode; treat it as step 1, not step 12.
- **`m4l_device/LivePilot_Analyzer.amxd`** — must be re-frozen in Max from the bumped JS. A
  version-string-only delta can be a 6-byte in-place binary patch (`docs/` has the procedure), but
  any real JS change requires a genuine re-freeze.

Verify the whole freeze chain with:

```bash
bash scripts/sync_amxd_targets.sh          # verify only
bash scripts/sync_amxd_targets.sh --apply  # propagate to all install targets
```

That script checks JS version == repo version, the frozen binary embeds it, every bridge command
AND every top-level JS identifier is present in the binary (catching a stale freeze that a version
patch would otherwise hide), the freeze is still FAT, and all install targets match.

**Ordering:** bump every file above (including `var VERSION`) → re-freeze in Max → run
`sync_amxd_targets.sh --apply` → then tag/release. The CI `amxd-freeze-drift` gate stays RED
between the bump and the freeze. That is intentional — it is the interlock that stops a release
shipping an unfrozen device.

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
Currently 474 tools. If adding/removing tools, update: README.md, package.json description, livepilot/.Codex-plugin/plugin.json, livepilot/.claude-plugin/plugin.json, server.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, AGENTS.md, CLAUDE.md, CHANGELOG.md, tests/test_tools_contract.py, docs/manual/index.md, docs/manual/tool-reference.md, docs/manual/tool-catalog.md

## Splice plan-aware model
Sample downloads use plan-aware gating (`mcp_server/splice_client/client.py::decide_download`):
- **Ableton Live plan** ($12.99/mo): 100 samples/day via local daily-quota tracker (`mcp_server/splice_client/quota.py`), resets UTC midnight. Sample downloads do NOT deplete credits on this plan.
- **Sounds+ / Creator / Creator+**: `CREDIT_HARD_FLOOR=5` still applies — agent cannot drain monthly credits past the floor.
- **Free samples** (`IsPremium=False` OR `Price=0`): bypass both gates.
- Plan detection reads `User.SoundsStatus`, `User.SoundsPlan`, `User.Features` from `ValidateLogin`.

Splice MCP tools: `get_splice_credits`, `splice_catalog_hunt`, `splice_download_sample`, `splice_preview_sample` (zero-cost audition), `splice_describe_sound` (GraphQL natural-language search), `splice_generate_variation` (find similar samples by UUID), `splice_list_collections` / `splice_search_in_collection` / `splice_add_to_collection` / `splice_remove_from_collection` / `splice_create_collection`, `splice_list_presets` / `splice_preset_info` / `splice_download_preset`, `splice_pack_info`, `splice_http_diagnose`.

## Domain Count
Currently 57 domains. A domain = the subdirectory under `mcp_server/` (or file under `mcp_server/tools/`) that contains `@mcp.tool()`. Source of truth is the module layout — no hand-maintained list. If adding/removing domains, update: README.md, package.json, manifest.json, CLAUDE.md, AGENTS.md, .claude-plugin/marketplace.json, livepilot/.claude-plugin/plugin.json, livepilot/.Codex-plugin/plugin.json, livepilot/skills/livepilot-core/SKILL.md, livepilot/skills/livepilot-core/references/overview.md, livepilot/skills/livepilot-release/SKILL.md, docs/manual/index.md, docs/manual/tool-catalog.md, tests/test_tools_contract.py. Run `python scripts/sync_metadata.py --check` to enforce count + inline list (or `--fix` for mechanical fixes).

# Changelog

## 1.10.7 — npm .amxd parity + domain-count consistency (April 18 2026)

Shipping release. Brings npm's tarball back in line with the fresh `.amxd`
freeze that landed on `main` after v1.10.6 tagged, and unifies the three
formerly-disagreeing sources of the domain count.

### Fixed

- **npm tarball parity with the GitHub release.** v1.10.6's npm publish
  predated commit `b0463ea` (the real fat `.amxd` freeze with matching ping
  bytes), so `npm install livepilot@1.10.6` shipped the stale Batch-22
  `.amxd` and `simpler_set_warp` silently no-op'd. v1.10.7 republishes with
  the fresh `.amxd` already present in the GitHub release assets.
- **Domain count unified at 45.** Three formerly-disagreeing sources: prose
  docs claimed "43 domains", `generate_tool_catalog.py` inferred "36" (via
  a hand-maintained whitelist that silently dropped ~10 domains —
  `atlas`, `composer`, `creative_constraints`, `device_forge`,
  `hook_hunter`, `preview_studio`, `sample_engine`, `session_continuity`,
  `song_brain`, `stuckness_detector`, `wonder_mode` — into an "Other"
  bucket), runtime module layout has 45. All three now agree.
- **Inline domain lists completed.** `CLAUDE.md:31` was missing
  `experiment`, `musical_intelligence`, and `semantic_moves`;
  `livepilot/skills/livepilot-release/SKILL.md:63` was missing
  `semantic_moves`.

### Infra

- **`scripts/sync_metadata.py` extended** with `check_domain_count()` and
  `check_domain_list()` that derive truth from `mcp_server` module paths.
  `--fix` mode now auto-corrects stale tool/domain counts and appends
  missing inline-list entries; extra entries are never auto-removed so a
  pattern miss can't silently delete a legitimate domain.
- **`scripts/generate_tool_catalog.py`** now uses the same module-layout
  rule (`mcp_server.<X>` / `mcp_server.tools.<Y>`) as `sync_metadata.py`
  so the two tools can't disagree on the domain set again.
- **`.mcpbignore`** excludes `m4l_device/*.pre-*-backup` rollback artifacts
  from the packaged `.mcpb`, keeping release bundles pristine across
  future freeze cycles.
- **`CLAUDE.md` gains `## Domain Count` section** documenting the drift
  enforcer alongside the existing `## Tool Count` and `## Version Bump`
  sections.

## 1.10.6 — Debuggability + Engine Modularization (April 17 2026)

Defensive-programming release. Zero behavior change for users; substantial
quality-of-life gains for developers and future debugging sessions.

### Debuggability

- **Silent-exception sweep.** All 79 `except Exception: pass` sites across
  `mcp_server/` now emit a `logger.debug("<func> failed: %s", exc)` breadcrumb
  while preserving the original body (pass / return X / continue). Previously
  invisible failures now leave a trail. Run with `LOG_LEVEL=DEBUG` to surface.
- **Credit-floor guard hardened.** `SpliceGRPCClient.download_sample()` now
  enforces `CREDIT_HARD_FLOOR` defensively via `can_afford(1, budget=1)` before
  the gRPC call. Tool-layer callers still gate upstream for UX; this closes
  the hole if any future caller forgets. The docstring claimed this guard
  existed — now the code matches.

### Engine modularization

Two single-file engines (2,477 LOC combined) split into packages while keeping
the public surface identical. Callers that did `from . import X as engine` or
`from .X import Symbol` continue to work unchanged.

- **`mcp_server/tools/_composition_engine/`** — 6 sub-modules (models, sections,
  critics, gestures, harmony, analysis) + facade. Was 1,530 LOC in one file;
  now no sub-module exceeds 522 LOC.
- **`mcp_server/tools/_agent_os_engine/`** — 6 sub-modules (models, world_model,
  critics, evaluation, techniques, taste) + facade. Was 947 LOC; now no
  sub-module exceeds 207 LOC. `_clamp` promoted to models.py to resolve a
  circular-dep risk between `evaluation` and `taste`.

### Infra

- **CI matrix adds Python 3.11.** Ableton 12.3's embedded Python is 3.11 on
  some platforms — catching drift pre-merge.
- **`livepilot.mcpb` removed from git tracking.** It was already excluded from
  `.npmignore` and `.mcpbignore`; now it's no longer bloating git history every
  release. Distribute via GitHub Releases.
- **`.git-backup-full/` deleted.** 3.4 MB worktree reclaim.

### Docs

- **OSC address convention** documented in both `m4l_device/livepilot_bridge.js`
  and `mcp_server/m4l_bridge.py` — the existing tolerant normalization at
  `_parse_osc` now has a written contract.

### Tests

1756 pass, 1 skipped (macOS-only path test on non-darwin), 0 failures.

## 1.10.5 — Splice online catalog unblocked + Simpler sample-loading fixes (April 14 2026)

The Splice integration was **never working online** in previous releases. The
`SpliceGRPCClient` existed in the codebase but silently fell back to a
SQLite-only path that returned only locally-downloaded samples (2 files on the
test user's machine). The bug was a missing `grpcio` dependency in the venv
combined with `sources.py` never checking for the gRPC client. Once unblocked,
a single query returns 19,690+ catalog hits. The "Beatles × Boards of Canada"
session that surfaced these bugs is archived at
`docs/2026-04-14-bugs-discovered.md` with 13 bugs categorized P0–P3.

Tool count: **317 → 320** (three new Splice catalog tools added).

### Added
- **`get_splice_credits`** — query the Splice user's subscription tier and
  remaining credit balance. Returns `{connected, username, plan,
  credits_remaining, credit_floor, can_download}`. Graceful degradation when
  Splice desktop isn't running or grpcio is missing.
- **`splice_catalog_hunt`** — search Splice's ONLINE catalog via gRPC (not
  just local downloads). Supports query, bpm_min/max, key, sample_type,
  genre filters. Returns full sample metadata including `file_hash` for
  downloads. This is the tool that unblocks 19,690+ results previously
  inaccessible.
- **`splice_download_sample`** — download a sample by `file_hash` (costs 1
  credit), with automatic credit-floor safety check. Optionally copies the
  downloaded file into `~/Music/Ableton/User Library/Samples/Splice/` so
  Ableton's browser indexes it, returning a `browser_uri` ready for
  `load_browser_item`.
- **Smart warped-loop defaults** in `load_sample_to_simpler` and
  `replace_simpler_sample`: when the filename contains a BPM marker (e.g.
  `86bpm`), Simpler's `S Start` is set to 0, `S Length` to 100%, and
  `S Loop On` to 1 so the full musical loop plays. Previously these tools
  used crop defaults designed for one-shots, which chopped warped loops.

### Fixed
- **P0-2 — Splice online catalog is finally reachable.** `grpcio>=1.60.0`
  and `protobuf>=4.25.0` are now REQUIRED dependencies (added to
  `requirements.txt`). `search_samples(source="splice")` now uses the gRPC
  client from `ctx.lifespan_context["splice_client"]` when connected and
  only falls back to SQLite when the gRPC path is unavailable. Before this
  fix, a query like `"mellotron"` returned 0 hits; after, it returns 851.
  Queries like `"lofi chord"` 80-92 BPM return 19,690 hits.
- **P0-1 — Simpler sample replacement is verified.** Both
  `replace_simpler_sample` and `load_sample_to_simpler` now verify by
  reading the device name back after the replace. If the name doesn't
  match the requested filename stem, the tool returns a clear error
  instead of silently shipping a wrong sample (the previous behavior
  caused the test session to play a kick drum named as a vocal for two
  consecutive rebuilds). The error message recommends
  `load_browser_item` as a more reliable alternative.
- **P1-1 — Simpler `Snap` is automatically turned OFF** after sample load.
  With Snap ON, the Sample Start position gets snapped to a zero-crossing
  outside the newly loaded sample's data, causing silent playback. This was
  the root cause of every "sample loaded but doesn't play" symptom in
  previous sessions. The fix also applies to `replace_simpler_sample`.
- **P2-6 — Warped-loop sample defaults** no longer crop arbitrary sections.
  When `load_sample_to_simpler` or `replace_simpler_sample` detects a BPM
  marker in the filename, it applies loop-appropriate defaults instead of
  one-shot-appropriate defaults.

### Removed
Nothing removed — all additions are additive.

### Verified
- `tests/test_tools_contract.py::test_total_tool_count` — 320 tools
  (up from 317)
- `tests/test_tools_contract.py::test_sample_engine_tools_registered` —
  includes `get_splice_credits`, `splice_catalog_hunt`,
  `splice_download_sample`
- Live gRPC round-trip: searched 3 queries against Splice online, found
  21,488 combined catalog hits, downloaded 3 samples (credits 100 → 97),
  copied into User Library, loaded onto 3 Ableton tracks via
  `load_browser_item` — all verified via `get_track_info` device name
  matching.

### Known limitations
- **Unlimited downloads inside Splice Sounds.vst3 are not yet drivable**
  programmatically. The gRPC download path always decrements monthly
  credits (100/month on most subscription tiers) regardless of
  `SoundsStatus: subscribed`. The Splice Sounds VST3 uses a separate HTTPS
  API that LivePilot cannot drive through Ableton's plugin boundary.
  Treat this as a research item — see P2-7 in
  `docs/2026-04-14-bugs-discovered.md`.
- **The M4L bridge `.amxd` still reports 1.10.4** in its ping response.
  Source code is at 1.10.5 but the frozen JS inside the .amxd wasn't
  re-exported. For users installing via `npm install -g livepilot@1.10.5`
  this is cosmetic — no bridge commands changed. If publishing a new
  `.mcpb`, re-freeze or binary-patch the version bytes first (see
  `feedback_amxd_freeze_drift.md`).

### Why a new patch version
The P0-2 fix (missing grpcio dependency) is a correctness bug: users
installed previous versions believed the Splice integration worked, when
in fact every "online" search returned only locally-downloaded files.
This is a silent incorrect-behavior bug — the tool returned 0-2 results
confidently without any warning. Users deserve a clearly-communicated
fix release and the ability to `npm install -g livepilot@1.10.5`.

## 1.10.4 — Bridge ping sync (April 14 2026)

A pure ship-fix release. The frozen JS inside `LivePilot_Analyzer.amxd` was
last re-exported during the v1.10.1 hardening pass and never re-frozen
during the 1.10.2 / 1.10.3 sweeps. The published `npm livepilot@1.10.3`
tarball therefore shipped with a stale `.amxd` whose `ping` returned
`{"version": "1.10.1"}`. End users installing via `npm install -g livepilot`
got the v1.10.3 source code but a v1.10.1 bridge.

### Fixed
- **M4L bridge ping reports 1.10.4 (was 1.10.1).** Source
  `m4l_device/livepilot_bridge.js` updated and the `.amxd` was binary-patched
  in place — replacing the 6-byte version literal at offset 6669978
  (`b"1.10.3" -> b"1.10.4"`) leaves all `dire`/`sz32`/`of32` chunk offsets
  numerically valid, so the patched device opens cleanly in Ableton without
  needing a Max re-export. Verified by `tests/test_bridge_parity.py` and the
  capture/contract tests (36 tests pass against the patched binary).
- **`livepilot.mcpb` no longer ships internal docs.** `.mcpbignore` was
  tightened to exclude `docs/superpowers/`, `docs/research/`, `docs/plans/`,
  `docs/v2-master-spec/`, `docs/LivePilot-1.7-Perception/`, `docs/2026-*`,
  `AGENT_OS_V1.md`, `COMPOSITION_ENGINE_V1.md`, `ableton-library-map.md`,
  `patreon-content.md`, and `m4l_device/*.adv` (Ableton presets users save
  into the dev folder). The bundle is back to lean shape: 4.66 MB / 403 files
  vs the bloated 5.56 MB / 491 files an unpatched repack produced. The
  `.mcp.json` exclusion is now root-only (`/.mcp.json`) so the
  plugin-internal `livepilot/.mcp.json` stays in the bundle.

### Why a new patch version
npm package versions are immutable. Once `livepilot@1.10.3` was published with
the stale `.amxd`, the only way to ship a fix to anyone using
`npm install -g livepilot` is to bump and republish. Same root cause and same
fix as the v1.10.1 → v1.10.2 jump.

### Deprecation
- `npm livepilot@1.10.3` deprecated with message: "stale M4L bridge .amxd
  ships v1.10.1 ping; please install 1.10.4".

### Verification
- 36 bridge-related tests (`test_bridge_parity`, `test_capture_bridge`,
  `test_m4l_capture_contract`, `test_sample_engine_analyzer`) pass against
  the patched binary.
- `unzip -p livepilot.mcpb m4l_device/LivePilot_Analyzer.amxd | grep 1.10.4`
  matches; `1.10.1` and `1.10.3` are absent.
- GitHub release `LivePilot_Analyzer.amxd` and bundled `livepilot.mcpb`
  asset SHAs match local artifacts.

## 1.10.3 — Truth Release (April 14 2026)

A correctness pass focused on making the top-layer workflows **trustworthy
in real use**. No new tool families, no new domains, no new breadth. Every
change is a truth-release fix: execution paths are real, emitted plans are
valid, sample matching is musically sane, and product language matches
implementation.

The four flagship workflows this release optimizes for:
  1. **Session understanding** — already strong, unchanged
  2. **Sample-guided section building** — fixed by §2 + §3
  3. **Wonder rescue** — fixed by §1
  4. **Targeted improvement ("tighten the low end")** — already strong, unchanged

If a feature couldn't be made true in this cycle, it was downgraded honestly
rather than preserved as fake capability.

### Fixed — Execution truth (§1)

- **Experiments now route through the async execution router.**
  `mcp_server/experiment/engine.py` had two code paths (`run_branch` and
  `commit_branch`) that called `ableton.send_command(tool, params)` directly
  and suppressed every failure with a silent `except Exception: pass`. They
  now go through `execute_plan_steps_async` with per-step results recorded
  on `branch.execution_log`. Branch status reflects reality: `evaluated`
  when steps ran, `failed` when zero succeeded, `committed_with_errors`
  when a commit was partial. Users can see exactly which tools succeeded
  and which didn't.
- **`commit_preview_variant` actually applies the variant now.**
  Previously this tool only marked the variant as chosen in an in-memory
  store and updated taste memory — the comment said *"the caller should
  then apply the variant's compiled plan"* which was a trust leak. Users
  reasonably expected `commit` to **apply** the variant. It now runs the
  variant's compiled plan through `execute_plan_steps_async` and returns
  `execution_log` + `steps_ok` / `steps_failed` + explicit `status`
  (`committed` / `committed_with_errors` / `failed`). Analytical-only
  variants (no compiled plan) return `status="analytical_only"` and
  `committed=False` instead of pretending to apply anything.

### Fixed — Composer truthfulness (§2)

- **`suggest_sample_technique` removed from the executable plan.**
  The composer was emitting `{"tool": "suggest_sample_technique", "params":
  {"technique_id": layer.technique_id}}` in both `compose()` and `augment()`.
  The real tool's signature is `(file_path required, intent, philosophy,
  max_suggestions)` — `technique_id` is not a parameter and `file_path` is
  required. This step would have always failed at runtime. It's now dropped
  from the executable plan entirely; `layer.technique_id` still surfaces
  in the descriptive `result.layers[*].technique_id` output for user
  inspection. The agent can call `suggest_sample_technique` separately with
  a real file path if it wants per-sample recipe advice.
  All 12 remaining composer tool emissions validated against real signatures
  — they're all correct.

### Fixed — Sample resolution quality (§3)

- **Role-aware scored ranking replaces naive first-hit substring matching.**
  The old `_filesystem_match` returned the first audio file whose name
  contained the layer's role OR any query token. This produced obvious
  musical mistakes: a `lead` layer asking for *"techno melody Am"* would
  get matched to `drums_techno.wav` because of the shared "techno" token.
  The new scorer considers:
  * role word in filename (+3.0)
  * filename's primary role matches layer role (+1.5 bonus)
  * filename's primary role is a **different** role (−5.0 penalty — this
    is what blocks the drums-for-lead failure)
  * role-adjacent hint words (kick/snare for drums, sub/808 for bass, etc.)
    (+2.0)
  * query token overlap excluding the role word (+0.5 per token)
  * tempo token overlap between filename and query (+1.0)
  A candidate must score strictly above 0.0 to be returned — files with
  no signal at all return `unresolved` instead of an arbitrary first pick.
  Six new regression tests lock out specific failure patterns.

### Fixed — Project identity stability (§5)

- **`project_hash` uses much more entropy.** The old hash was
  `tempo + track_count + sorted_track_names` — the author's own comment
  said *"this is imperfect"*. It collided whenever two songs shared the
  same tempo and track names, and it was invariant to track reordering,
  scene changes, and arrangement length. The new hash includes:
  * tempo (1 decimal)
  * time signature
  * song length in beats (arrangement duration — very distinguishing)
  * **ordered** track list: `(index, name, color, has_midi_input)` per track
  * return track count + names
  * **ordered** scene list: `(index, name, color)` per scene
  Six new tests lock out: track reordering collision, song-length collision,
  scene-list collision, time-signature collision, and track-rename detection.
  Not a true project ID (that still needs Live set file path access from
  the Remote Script, deferred) but substantially less fragile in practice.

### Changed — Product language (§6)

- **README.md**: "Producer Agent — autonomous multi-step production"
  rewritten as *"an orchestrated multi-step assistant for building,
  layering and refining sessions. [...] The agent proposes plans; the user
  confirms and listens. LivePilot is a high-trust operator, not an
  autonomous producer."*
- **docs/manual/getting-started.md**: "An autonomous agent that can build
  entire tracks from high-level descriptions" rewritten to frame output as
  a *"playable baseline — a starting point, not a finished track. You
  listen, decide what works, and iterate."*
- **docs/manual/intelligence.md**: `agentic_loop` workflow mode description
  changed from *"Full autonomous loop with evaluation"* to *"Multi-step
  plan-and-evaluate loop with explicit checkpoints"*.

### Tests

- **1756 passing**, 1 skipped (was 1740 in v1.10.2; +16 net new regressions):
  * +2 composer: `suggest_sample_technique` NOT in compose/augment plan
  * +6 sample resolver: role-aware ranking lockouts
  * +2 preview studio: `commit_preview_variant` executes + analytical-only honesty
  * +6 project persistence: hash collision-resistance

### Note — what was intentionally NOT fixed in this cycle

- **`mcp_dispatch` registry expansion.** Only `load_sample_to_simpler` is
  registered. The other 9 `MCP_TOOLS` entries are not currently emitted by
  any compiled plan I can find. The router returns a clear "not in dispatch"
  error if an unregistered MCP tool ever gets emitted, which is *honest
  failure* — not silent. Adding stub entries would be preemptive scope.
- **Wonder Mode full SessionKernel.** Wonder passes real `session_info` from
  Ableton to the variant compilers when connected — the kernel SHAPE is
  minimal (`{session_info, mode}`) but the semantic-move compilers only
  read `kernel.session_info.tracks`, so the extra fields don't change
  behavior. Low value, deferred.
- **Silent `except: pass` in non-execution paths.** `commit_preview_variant`
  has two silent excepts around taste-memory and turn-resolution updates.
  These are bookkeeping side effects, not execution-critical, and failing
  them shouldn't abort the commit. Left as-is.
- **Project identity via Live set file path.** The real fix for §5 would
  be to pull `song.song_document_path` from Live via a new Remote Script
  handler. Deferred — the stronger hash is a substantial improvement
  without adding new Remote Script surface area.

---

## 1.10.2 — npm Distribution Fix + Tool-Count Audit (April 14 2026)

Patch release. The orchestration hardening shipped in 1.10.1 was correct on
GitHub releases but the **npm-published 1.10.1 tarball had a stale `.amxd`
embedded at v1.9.14** because the package was published to npm BEFORE the
M4L Analyzer device was re-exported. Users installing via `npm install
livepilot` would have gotten the broken M4L analyzer.

This release republishes the package to npm with the corrected `.amxd`
(byte-identical to the GitHub release asset) and fixes a number of stale
tool-count references that have been wrong since the 1.10.0 line bumped
from 316 → 317.

`livepilot@1.10.1` on npm is being deprecated with a pointer to 1.10.2.

### Fixed
- **npm package now ships the correct M4L Analyzer device.** `livepilot@1.10.2`
  contains the re-exported `LivePilot_Analyzer.amxd` (6,723,726 bytes,
  embeds v1.10.2 `livepilot_bridge.js` byte-perfect). `livepilot@1.10.1`
  inadvertently shipped with the old v1.9.14 frozen device.
- **Git tag for the release is now properly created.** v1.10.1 was missing
  a git tag on origin (the GitHub release was created with `gh release
  create` against `target_commitish: main` instead of an actual tag).
  v1.10.2 has a proper annotated tag pushed to origin.
- **Tool-count drift across docs** (had been wrong since 1.10.0):
  - `tests/test_tools_contract.py` docstring said "316 MCP tools" while the
    assertion correctly checked 317 — docstring fixed.
  - `docs/patreon-content.md` said "316 tools" / "316-tool production system"
    in two places — both fixed to 317.
  - `README.md`, `docs/M4L_BRIDGE.md`, `docs/manual/getting-started.md` all
    claimed "286 core tools + 30 bridge tools" which sums to 316 — and
    contradicted the 317 total claim elsewhere. Recomputed from source:
    actual split is **281 core + 36 bridge = 317** (more bridge tools than
    we used to count because the spectral-cache readers were classified as
    core, but they require the M4L analyzer device to be present and so
    are correctly bridge-dependent).
  - `livepilot/skills/livepilot-release/SKILL.md` release-checklist updated
    to reference the correct 281/36 split.

### Tests
- 1740 passing, 1 skipped — same as 1.10.1, no functional code changes
- `test_tools_contract.py::test_total_tool_count` still asserts 317 ✅

### Note
1.10.1 → 1.10.2 contains **no Python source changes** and **no functional
M4L bridge changes**. The orchestration hardening fixes are unchanged from
1.10.1. This release exists purely to correct the npm distribution, the
git tag, and stale doc references.

The bundled `.amxd` is the same byte-for-byte file shipped in 1.10.1 (its
ping response still reports `"version": "1.10.1"`). The repo's
`livepilot_bridge.js` source has the ping string at `1.10.2`, which is a
one-line cosmetic difference; the .amxd will catch up on the next re-export.
All functional code (`get_selected` ID matching, 4-byte UTF-8 decoder, every
command handler) is identical between v1.10.1 and v1.10.2 — only the
version number constant differs.

If you're using LivePilot via the GitHub release `.mcpb` asset (not npm),
you already have the correct M4L analyzer in v1.10.1 and don't need to
upgrade for any user-visible functional reason.

---

## 1.10.1 — Orchestration Hardening (April 14 2026)

Pure correctness pass on the execution substrate. No new public tools,
no renames, no tool count change. Thirteen commits across thirteen phases
(nine Phase 1 + four Phase 2). All new response fields are additive.

**Test results:** 1690 → **1740 passing** (+50 net, +56 new tests, −6 sync-to-async
rewrites). No regressions.

**M4L Analyzer device re-exported.** `m4l_device/LivePilot_Analyzer.amxd`
was previously frozen at v1.9.14 (shipped that way in v1.10.0). For 1.10.1
the device was re-exported from Max for Live with the current
`livepilot_bridge.js` source, so the bundled `.amxd` now embeds the v1.10.1
JS including `get_selected` ID-matching (instead of name-matching, which
broke when track names duplicated) and the 4-byte UTF-8 decoder for emoji
in track/clip names. Embedded JS is byte-identical to the repo source.

### Fixed
- **Execution router: `load_sample_to_simpler` reclassified as MCP tool.** It
  was wrongly declared in `BRIDGE_COMMANDS` despite being an async Python
  function with no JS dispatch case. All six sample-family semantic moves
  that compiled this step now classify it correctly. Backend annotations
  in `mcp_server/sample_engine/moves.py` updated to match.
- **Execution router: dedupe `capture_audio` classification.** Removed the
  dead entry from `MCP_TOOLS` — `capture_audio` lives in `BRIDGE_COMMANDS`
  and is handled by `livepilot_bridge.js`.
- **Execution router: async-only substrate.** `execute_step` and
  `execute_plan_steps` (the sync path) are **deleted**. The only surviving
  entry point is `execute_plan_steps_async`. `apply_semantic_move` and
  `render_preview_variant` both became `async def` and dispatch through the
  async router. The dead sync path was the last place where a plan could
  silently produce steps that only worked on one transport.
- **Bridge dispatch unpacks params positionally.** Latent bug in the Phase 1
  async router: it passed the whole params dict as a single arg to
  `bridge.send_command`, which would have OSC-encoded the dict and failed on
  the real M4L bridge. Fixed in Phase 2 to unpack via `*list(params.values())` —
  plan authors construct params in the order the bridge command expects.
- **Preview Studio: `render_preview_variant` captures audible preview BEFORE
  undo.** The function previously ran undo in a `finally` block that
  executed before the "audible preview" section, so `preview_mode =
  "audible_preview"` was a lie — it captured pre-variant audio. Now
  restructured as: capture-before → apply → capture-after → play+sample
  while variant is applied → stop playback → undo applied steps. Callers
  can trust the `audible_preview` label.
- **SessionKernel: shares `ctx.lifespan_context` memory stores and fixes
  silent method-name bugs.** `get_session_kernel` used to instantiate fresh
  `TasteMemoryStore`, `AntiMemoryStore`, and `SessionMemoryStore` and call
  `list_all()` / `recent()` (neither method exists), all wrapped in silent
  `try/except: pass`. Users who recorded anti-preferences or session memory
  via the public tools always saw an empty kernel. Now reuses stores the
  same way `mcp_server/memory/tools.py` does, calls the correct methods
  (`get_anti_preferences`, `get_recent`), and surfaces store-load failures
  in a non-breaking `warnings` field.
- **Taste graph shape normalized across consumers.** Both
  `preview_studio/engine.py:_estimate_taste_fit` and
  `session_continuity/tracker.py` read `taste_graph.get("transition_boldness")`,
  but the canonical `TasteGraph.to_dict()` puts it under `dimension_weights`.
  Both consumers silently defaulted to 0.5, ignoring recorded user taste.
  New `mcp_server/memory/taste_accessors.get_dimension_pref` helper reads
  all three observed shapes; both consumers route through it.
- **Composer: plans are executable, not aspirational.** `compose()` and
  `augment_with_samples()` used to emit pseudo-tools
  (`_agent_pick_best_sample`, `_apply_technique`), placeholder strings
  (`{downloaded_path}`), invalid sentinels (`device_index: -1`,
  `track_index: -1`), and hardcoded `clip_slot_index: 0` on newly-created
  empty tracks. Plans are now rebuilt via `sample_resolver.resolve_sample_for_layer`
  at plan time. Unresolved layers are kept in the descriptive `layers`
  output and surfaced in `warnings`, but dropped from `plan`. Processing
  chains use `step_id` + `$from_step` bindings to resolve `device_index`
  from `insert_device` results at execution time.
- **Composer: arrangement clips finally work.** Re-enabled the arrangement
  emission path that was stubbed in Phase 7. Each resolved layer now emits
  `create_clip` → `add_notes` (C3 trigger) → `create_arrangement_clip` per
  section, tiling a 1-bar source clip across each section's bar count.
  Simpler in classic mode plays the full sample on every trigger, so the
  minimal pattern produces a playable baseline; the agent can replace it
  with a more musical pattern via `suggest_sample_technique` recipes later.
  Example: a techno prompt with one resolved sample now produces a 65-step
  plan with 5 arrangement clips tiling Intro / Build / Drop / Drop 2 / Outro.
- **ProjectBrain: `build_project_brain` fetches notes for role inference.**
  The tool never called `get_notes`, so `build_project_state_from_data`
  always ran with an empty `notes_map`, forcing `role_graph` into the
  "assume all tracks active in every section" fallback — destroying the
  section-scoped role confidence RoleGraph was supposed to compute.

### Added
- **Async execution router with step-result binding** —
  `mcp_server/runtime/execution_router.execute_plan_steps_async` dispatches
  `remote_command`, `bridge_command`, and `mcp_tool` backends through their
  correct transports. Supports step-result binding via
  `{"$from_step": "<id>", "path": "a.b"}` on any param.
- **MCP dispatch registry** — `mcp_server/runtime/mcp_dispatch.py` registers
  in-process Python tools (starting with `load_sample_to_simpler`) so plans
  can invoke them through the async router. Lifespan-installed at startup
  alongside `ableton`, `spectral`, `m4l`, and `splice_client`.
- **Splice remote download workflow in composer.** `sample_resolver` extended
  with `splice_local` and `splice_remote` sources. Resolution order:
  `filesystem > splice_local > splice_remote > browser`. Filesystem wins
  even when Splice has a hit (local files are free). Splice remote downloads
  cost 1 credit each and respect the 5-credit hard floor via
  `splice_client.can_afford(1, budget)` — the floor check is upfront so
  the resolver fails fast rather than thrashing per-layer.
- **`SpliceGRPCClient` wired into server lifespan.** `ctx.lifespan_context["splice_client"]`
  is now populated at startup. Graceful degradation: if grpcio is missing,
  Splice desktop isn't running, or the cert can't be read, `splice_client.connected`
  stays False and the resolver treats it as "no splice hits".
- **Composer credit-safety prelude.** New `_credit_safety_prelude()` helper
  in `composer/tools.py` runs once per compose/augment call: checks credits
  remaining, trims `max_credits` to respect the floor, returns a warnings
  list the tool merges into the plan output. No per-layer credit thrashing.
- **Additive return fields** (no breaking changes to existing callers):
  - `insert_device.device_index` — actual index of the inserted device in
    its chain/track. Composer plans bind to it.
  - `load_sample_to_simpler.device_index` and `.track_index` — the real
    Simpler position (was previously computed internally but not returned).
  - `preview_semantic_move.compiled_plan` and `.compiled_plan_executable` —
    the move compiled against a lightweight current-session kernel,
    alongside the existing static `plan_template`.
  - `get_session_kernel.warnings` — surfaced when memory/taste stores fail
    to load. Additive, callers can ignore.
- **`mcp_server/composer/sample_resolver.py`** — async sample resolver with
  filesystem-first preference, splice_local/remote hooks, and browser fallback.
- **`mcp_server/memory/taste_accessors.get_dimension_pref`** — canonical
  reader for taste-graph dimension preferences. All new consumers must
  use it.
- **Bridge parity test** — `tests/test_bridge_parity.py` compares Python
  `BRIDGE_COMMANDS` against the `case` labels in
  `m4l_device/livepilot_bridge.js`. Catches future misclassification drift.

### Changed (internal, no public tool changes)
- **`ComposerEngine.compose`, `augment`, and `get_plan` are async.** Sample
  resolution may now hit the network (Splice download), so the whole compose
  chain awaits. No production callers outside `composer/tools.py`; tests use
  `asyncio.run(...)` wrappers.
- **`CompositionResult.resolved_samples` shape changed** from
  `{role: path_str}` to `{role: {"path": str, "source": str}}` — callers
  can now tell filesystem vs splice_local vs splice_remote hits apart.

### Tests
- Router suite: 23/23 (async-only; 6 legacy sync tests rewritten as async)
- Composer resolver suite: 13/13 (7 filesystem + 6 splice paths)
- Composer engine suite: 14/14 (9 Phase 7 + 5 Phase 2B arrangement contracts)
- Project brain suite: 47/47 (+2 Phase 8 notes_map regression)
- Preview studio suite: 17/17 (+1 ordering regression)
- Session kernel suite: 11/11 (+3 hydration regression)
- Taste accessors suite: 9/9 (new in Phase 3)
- Bridge parity suite: 2/2 (new in Phase 9)
- **Full repo: 1740 passed, 1 skipped** (up from 1690)

---

## 1.10.0 — The Intelligence Release (April 13 2026)

316 tools across 43 domains. Device Atlas v2, Sample Intelligence, Auto-Composition, Splice Integration, Device Forge, Live 12.3 API, Corpus Intelligence.

### Device Atlas v2 — 1305 Devices, 81 Enriched (+6 tools)
- **`atlas_search`** — fuzzy search across all devices by name, sonic character, use case, or genre
- **`atlas_device_info`** — full knowledge entry for any device — parameters, recipes, gotchas
- **`atlas_suggest`** — intent-driven recommendation: "warm bass for techno" → Drift + recipe
- **`atlas_chain_suggest`** — full device chain for a track role: instrument + effects with rationale
- **`atlas_compare`** — side-by-side comparison of two devices for a given role
- **`scan_full_library`** — deep browser scan to build/refresh the atlas
- 32 instruments (16 enriched), 70 audio effects (35 enriched), 23 MIDI effects (12 enriched), 497 M4L devices, 683 drum kits
- 71 YAML enrichment files with parameter guides, recipes, and production knowledge

### Composer Engine — Prompt to Multi-Layer Session (+3 tools)
- **`compose`** — full multi-layer composition from text prompt ("dark minimal techno 128bpm with industrial textures")
- **`augment_with_samples`** — add sample-based layers to existing session
- **`get_composition_plan`** — dry run preview without executing
- NLP parser extracts genre, mood, tempo, key, energy from free text
- Layer planner with role templates (drums/bass/lead/pad/texture/vocal)
- 7 genre defaults: techno, house, hip hop, ambient, drum and bass, trap, lo-fi
- Credit safety system for Splice integration

### Sample Engine — AI Sample Intelligence (+6 tools)
- **`analyze_sample`**, **`evaluate_sample_fit`**, **`search_samples`**, **`suggest_sample_technique`**, **`plan_sample_workflow`**, **`get_sample_opportunities`**
- SpliceSource — reads Splice's local sounds.db (read-only) for key, BPM, genre, tags, pack info, popularity
- BrowserSource + FilesystemSource — Ableton browser and local directory scanning
- 6-critic fitness battery: key fit, tempo fit, frequency fit, role fit, vibe fit, intent fit
- 29-technique library: rhythmic (Dilla, Burial, Premier), textural (Paulstretch, granular), melodic (Bon Iver), resampling (Amon Tobin)
- Dual philosophy: Surgeon (precision integration) vs Alchemist (creative transformation)
- 6 sample-domain semantic moves for Wonder Mode: chop_rhythm, texture_layer, vocal_ghost, break_layer, resample_destroy, one_shot_accent
- Sample-aware stuckness diagnosis: no_organic_texture, stale_drums, vocal_processing_monotony, dense_but_static

### Splice gRPC Client
- Live connection to Splice desktop API for downloading new samples
- Port auto-detected from port.conf, TLS with self-signed certs
- Credit safety floor (never drain below 5 credits)
- Graceful degradation when Splice is not running

### Device Forge — Programmatic M4L Generation (+3 tools)
- **`generate_m4l_effect`**, **`list_genexpr_templates`**, **`install_m4l_device`**
- .amxd binary builder from pure Python (reverse-engineered binary format)
- gen~ DSP template library: 15 building blocks (Lorenz, Karplus-Strong, wavefolder, FDN reverb, bitcrusher, etc.)
- 7 device_creation semantic moves for Wonder Mode
- Safety: auto `clip(out, -1, 1)` on all generated gen~ code
- Auto-installs to Ableton User Library

### Live 12.3 API Integration (+4 tools)
- **`create_native_arrangement_clip`** — arrangement clips with automation envelope (12.1.10+)
- **`insert_device`** — insert native device by name, 10x faster than browser (12.3+)
- **`insert_rack_chain`** — add chains to Instrument/Audio/Drum Racks (12.3+)
- **`set_drum_chain_note`** — assign MIDI notes to Drum Rack chains (12.3+)
- Version detection at startup with feature flags via `get_session_info`
- Three capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+)
- Display values on device parameters (12.2+) — human-readable like "26.0 Hz"
- `find_and_load_device` auto-routes to `insert_device` on 12.3+ (10x speedup)

### Corpus Intelligence Layer
- Parses device-knowledge markdown into queryable Python structures at runtime
- EmotionalRecipe, GenreChain, PhysicalModelRecipe, AutomationGesture data types
- Consumed by Wonder Mode, Sound Design critics, and Composer Engine

### Wonder Mode Enhancements
- Corpus intelligence integration — emotional/genre/material hints in variants
- Sample-domain diagnosis patterns
- 13 new semantic moves (6 sample + 7 device creation)

### New Domains
- **atlas** — device knowledge database (6 tools)
- **composer** — auto-composition engine (3 tools)
- **sample_engine** — sample intelligence (6 tools)
- **device_forge** — M4L device generation (3 tools)

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

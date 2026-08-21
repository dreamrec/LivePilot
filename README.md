```
██╗     ██╗██╗   ██╗███████╗██████╗ ██╗██╗      ██████╗ ████████╗
██║     ██║██║   ██║██╔════╝██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██║     ██║██║   ██║█████╗  ██████╔╝██║██║     ██║   ██║   ██║
██║     ██║╚██╗ ██╔╝██╔══╝  ██╔═══╝ ██║██║     ██║   ██║   ██║
███████╗██║ ╚████╔╝ ███████╗██║     ██║███████╗╚██████╔╝   ██║
╚══════╝╚═╝  ╚═══╝  ╚══════╝╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

<p align="center">
  <a href="https://github.com/dreamrec/LivePilot/actions"><img src="https://img.shields.io/github/actions/workflow/status/dreamrec/LivePilot/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://www.npmjs.com/package/livepilot"><img src="https://img.shields.io/npm/v/livepilot?style=flat-square&color=blue" alt="npm version"></a>
  <a href="https://www.npmjs.com/package/livepilot"><img src="https://img.shields.io/npm/dm/livepilot?style=flat-square" alt="npm downloads"></a>
  <a href="https://github.com/dreamrec/LivePilot/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-BSL--1.1-blue?style=flat-square" alt="License"></a>
  <a href="https://github.com/dreamrec/LivePilot/releases"><img src="https://img.shields.io/github/v/release/dreamrec/LivePilot?style=flat-square&label=release" alt="Latest Release"></a>
</p>

<p align="center">
  <strong>Make the change. Hear what happened. Keep what works.</strong><br>
  LivePilot connects an AI client to Ableton Live 12. Sketch ideas, edit the set,
  compare versions, and learn from the choices you keep.<br><br>
  474 tools · 57 domains · macOS + Windows
</p>

<br>

> [!NOTE]
> LivePilot works with any MCP client, including Claude Code, Claude Desktop, Codex,
> Cursor, VS Code, and Windsurf. Changes inside the Live set use Ableton's undo stack.
> Downloads, saved memory, library scans, and installer changes happen outside the set
> and cannot be undone from Ableton.

> [!WARNING]
> LivePilot is moving quickly. Pin a version for repeatable studio or live-performance setups,
> and check the [changelog](CHANGELOG.md) before updating.

<br>

---

## Start Here

The setup wizard installs the Ableton Remote Script, creates the Python environment,
copies the Max for Live Analyzer, and checks the connection:

```bash
npx livepilot --setup
```

Using Claude Desktop? Download the latest `livepilot-<version>.mcpb` from
[Releases](https://github.com/dreamrec/LivePilot/releases/latest) and double-click it.

See [Install](#install) for client-specific setup and manual options.

---

## What's New in v1.29.0

LivePilot now learns from comparisons instead of inventing absolute taste scores, and it
adds named Arrangement locators.

- **Taste from real choices.** `taste_record_pair`, `taste_train`, and `taste_rank` learn from
  audio you kept versus audio you discarded.
- **Honest confidence.** Results are grouped by session, weak evidence stays inconclusive,
  and certification requires at least five independent sessions.
- **A better answer to “did this actually change?”** Optional CLAP embeddings add perceptual
  distance to `listen_capture` and `listen_ab` without adding model dependencies to the core install.
- **Named locators.** Create or rename Arrangement markers without moving the playhead.
- **Cleaner plumbing.** The MCP handshake reports LivePilot's own version, FastMCP 3.4.7 is the
  security baseline, and NumPy 2.5 is supported.

Previous release v1.28.0 introduced the offline Listening Engine, authenticated OSC 9881 bridge
commands, capture-pipeline fixes, and stalled-stream detection.

Full details in the [CHANGELOG](CHANGELOG.md).

---

## What LivePilot Does

LivePilot works at two levels: exact control when you know what you want, and informed
help when you do not.

| Job | What LivePilot brings |
|-----|-----------------------|
| **Work directly in Live** | Control transport, tracks, clips, notes, devices, routing, mixing, automation, and Arrangement View through explicit tools. |
| **Find the right sound** | Search Ableton's library, your own plugins and racks, local samples, and Splice before loading anything. |
| **Listen before judging** | Read live spectral data or analyze rendered audio, then compare the result with the state before the edit. |
| **Explore safely** | Preview alternatives, keep the winner, and route changes inside the set through Ableton's undo stack. |
| **Learn your taste** | Remember which moves, devices, and versions you keep across sessions without treating taste as a universal score. |
| **Stay aware of the song** | Track identity, open creative threads, section roles, and protected elements so local fixes do not flatten the whole piece. |

Under the hood: a 5,264-device atlas, 683 mapped drum kits, 29 sample-processing
techniques, 44 semantic moves, real-time and offline listening, and 12 planning and
evaluation systems. The sections below show how each part works.

<br>

---

## Two Ways to Talk to LivePilot

Start with the language that fits the moment. Both routes reach the same tool surface.

### Route A — Artist / aesthetic shorthand

> *"Sound like J Dilla."* &nbsp; *"Make this feel more like Burial."* &nbsp; *"BoC-style pads."*

Use a producer or genre as shorthand for rhythm, density, space, texture, and device
choices. LivePilot translates the reference into techniques rather than pretending to clone
someone's identity.

### Route B — Direct musical intent

> *"Push the snare 4 ms early, keep the kick on-grid, add ±2 ms timing variation to the hats,
> and cut 3 dB around 380 Hz on the snare."*

When the detail matters, name it: notes, milliseconds, dB, frequency, modulation depth,
envelope shape, send level, automation curve, scale degree, or voice leading.

### Mixing the routes

Most sessions use both. Start broad, listen, then get specific where the track needs it.

<br>

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  KNOWLEDGE               PERCEPTION              MEMORY              │
│  ──────────────          ──────────────          ──────────────       │
│                                                                      │
│  Device Atlas            9-band FFT              recall by mood,     │
│  5264 devices            RMS / peak              genre, texture      │
│  120 enriched             pitch tracking          29 techniques       │
│  683 drum kits           key detection           replay into session │
│                                                                      │
│  Sample Engine           Corpus Intelligence     Taste Graph          │
│  Splice (local SQLite)   EmotionalRecipe         move preferences    │
│  Browser search          GenreChain              device affinities   │
│  Filesystem scan         PhysicalModelRecipe     novelty tolerance   │
│  6 fitness critics       AutomationGesture                           │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Device      │  │  M4L         │  │  Technique   │               │
│  │  Atlas       │──│  Analyzer    │──│  Memory      │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                        │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐               │
│  │  Sample      │  │  Corpus      │  │  Composer    │               │
│  │  Engine      │  │  Intelligence│  │  Engine      │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         └─────────────────┼──────────────────┘                       │
│                           ▼                                          │
│                  ┌─────────────────┐                                  │
│                  │   474 MCP Tools  │                                  │
│                  │   57 domains     │                                  │
│                  └────────┬────────┘                                  │
│                           │                                          │
│           Remote Script ──┤── TCP 9878                                │
│           M4L Bridge ─────┤── UDP 9880 / OSC 9881                    │
│           Splice (local) ─┤── SQLite (downloaded samples)             │
│                           │                                          │
│                  ┌────────────────┐                                   │
│                  │  Ableton Live  │                                   │
│                  │      12        │                                   │
│                  └────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────┘
```

### How the pieces connect

**Remote Script** (`remote_script/LivePilot/`) — A Python ControlSurface that runs inside Ableton's process. Listens on TCP 9878. All Live Object Model calls execute on Ableton's main thread via `schedule_message`. Detects Ableton version at startup and enables four capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+), Collaborative (12.4+).

**MCP Server** (`mcp_server/`) — Python FastMCP server. Validates inputs, routes commands to the Remote Script over TCP, manages the M4L bridge, and runs the atlas, sample engine, composer, planning, and evaluation systems. This is what your AI client connects to.

**M4L Bridge** (`m4l_device/`) — Optional Max for Live Audio Effect on the master track. Provides deep LOM access through Max's LiveAPI that the ControlSurface API can't reach. UDP 9880 (M4L to server) carries spectral data and LiveAPI responses. OSC 9881 (server to M4L) sends commands. The 38 spectral/analyzer tools strictly require the bridge; device and sample tools that call the bridge also have graceful fallbacks, so core functionality works without it. Backed by 32 bridge commands for hidden parameters, Simpler internals, warp markers, display values, and Simpler warp / Compressor sidechain writes that live on child objects Python can't reach.

**Device Atlas** (`mcp_server/atlas/`) — In-memory indexed JSON database. 5264 devices with browser URIs (bundled baseline), 120 enriched with YAML sonic profiles (mood, genre, texture, recommended chains). 7 indexes: by_id, by_name, by_uri, by_category, by_tag, by_genre, by_pack. Reverse-index `device_techniques_index.json` powers `atlas_techniques_for_device` (146 cross-references across 58 devices). Device and preset choices resolve against the atlas before loading, which reduces guessed names and dead ends. **v1.22.0+**: run `scan_full_library` after install to index your packs, User Library, and plugins into `~/.livepilot/atlas/device_atlas.json` — your personal atlas overrides the baseline and survives npm updates.

**Sample Engine** (`mcp_server/sample_engine/`) — Searches three sources simultaneously: BrowserSource (Ableton's library), SpliceSource (local Splice catalog via SQLite), FilesystemSource (user directories). Every result passes through a 6-critic fitness battery (key, tempo, spectral, genre, mood, technical). 29 processing techniques (Surgeon precision vs. Alchemist experimentation). Builds complete sample processing plans with warp, slice, and effect recommendations.

**Splice Client** (`mcp_server/splice_client/`) — Searches Splice's catalog through two layers: the local SQLite database (`sounds.db`, already-downloaded samples) and the live gRPC API (full catalog, including samples you haven't downloaded yet). The gRPC client auto-detects Splice's dynamic port via `port.conf`, handles self-signed TLS, and enforces a 5-credit safety floor before any download. Per-call timeouts (5–10s) prevent a hung Splice process from stalling the MCP event loop. Graceful fallback to SQL-only if grpcio isn't installed. No API key needed — authentication comes from the running Splice desktop app.

**Composer** (`mcp_server/composer/`) — Prompt-to-plan pipeline. Parses natural language ("dark minimal techno 128bpm with industrial textures") into a CompositionIntent (genre, mood, tempo, key). Plans layers using role templates (kick, bass, percussion, texture, lead, pad, fx). Compiles to a step-by-step plan of tool calls that the agent executes. Does not execute autonomously — returns the plan. 4 genre defaults (house, techno, trap, ambient) — genres outside this set fall back to a neutral layer plan.

**Corpus** (`mcp_server/corpus/`) — Parsed device-knowledge markdown converted to queryable Python structures: EmotionalRecipe, GenreChain, PhysicalModelRecipe, AutomationGesture. Feeds Wonder Mode, Sound Design critics, and the Composer with structured production references at runtime.

**Execution Router** (`mcp_server/runtime/execution_router.py`) — Classifies each step in a multi-step plan as remote_command (TCP to Ableton), bridge_command (OSC to M4L), or mcp_tool (internal), then dispatches it through the correct channel.

<br>

---

## How LivePilot Makes Decisions

Tools make the edit. These 12 systems help decide what to try, what to protect, what to
compare, and what to remember.

### SongBrain — What the Song Is

Builds a real-time model of the session: identity core (what defines this track), sacred elements (what must not be casually damaged), section purposes (what each part is doing emotionally), energy arc (where the song is heading). Detects identity drift when edits pull the track away from what made it work.

### Taste Graph — What You Like

Learns your production preferences across sessions. Tracks which move families you keep vs. undo, which devices you gravitate toward, how experimental you want suggestions (novelty band), and which dimensions you avoid. Every accept/reject updates the graph. Two producers using the same tools get different recommendations.

### Semantic Moves — Musical Actions, Not Parameters

**44 high-level intents** across 7 families (mix, arrangement, transition, sound_design, performance, device_creation, sample) — "add contrast," "tighten the low end," "make kick and bass lock," "sample vocal ghost," "destroy then rebuild." Each move compiles into a concrete tool sequence with risk level, target dimensions, and protection thresholds. Analyzer-gated moves (`tighten_low_end`, `make_kick_bass_lock`) mark their spectrum pre-reads as optional so the plan continues even when the analyzer isn't available. The plan shows its tradeoffs before anything changes.

### Wonder Mode — Stuck-Rescue Workflow

When a session is stuck — repeated undos, overpolished loops, no structural progress — Wonder Mode activates:

1. **Diagnose** — classify the stuckness (loop trap? missing contrast? identity unclear?)
2. **Generate** — find semantic moves that address the diagnosis, enforcing real distinctness
3. **Preview** — apply each variant, capture, undo. Hear before committing
4. **Commit or Reject** — choice recorded into taste and session continuity

### Creative Engines

| Engine | What it does |
|--------|-------------|
| **Mix Engine** | Critic-driven analysis: masking, headroom, stereo, dynamics. Plans corrective moves with before/after evaluation |
| **Sound Design Engine** | Analyzes patches for static timbre, missing modulation, weak transients. Suggests parameter moves |
| **Transition Engine** | Classifies transition types (drop, build, breakdown). Scores quality, plans improvements from archetypes |
| **Composition Engine** | Section analysis, motif detection, emotional arcs. Plans structural moves |
| **Performance Engine** | Safety-constrained suggestions for live sets. Knows which moves risk audio dropouts |
| **Reference Engine** | Distills principles from reference tracks. Maps them to your session as concrete moves |

### Hook Hunter

Identifies the most salient musical idea — ranks candidates by recurrence across scenes, motif salience, and section placement (payoff-section boost). Tracks whether hooks are developed, neglected, or undermined, and flags when a transition fails to deliver expected payoff. Rhythm-side ranking is currently heuristic (drum-track detection + clip reuse); true onset-based rhythmic features are on the roadmap.

### Session Continuity

Maintains creative threads ("the chorus needs more lift") and turn resolutions across the session. When you return to a project: *"Last time, you kept the filter sweep for the bridge. The chorus lift thread is still open."*

### Evaluation Loop

Every engine follows: **measure before → act → measure after → compare**. If a change made things worse (more masking, lost headroom, identity drift), the system flags it before you move on.

<br>

---

## Tools

474 tools across 57 domains. Highlights below — [full catalog here](docs/manual/tool-catalog.md).

<br>

### Core Ableton Control — highlights

| Domain | # | What it covers |
|--------|:-:|----------------|
| Transport | 12 | playback, tempo, time sig, loop, metronome, undo/redo, cue points, diagnostics |
| Tracks | 17 | create MIDI/audio/return, delete, duplicate, arm, mute, solo, color, freeze, flatten |
| Clips | 11 | create, delete, duplicate, fire, stop, loop, launch mode, warp mode, quantize |
| Notes | 8 | add/get/remove/modify MIDI notes, transpose, duplicate, per-note probability |
| Devices | 19 | load by name or URI, insert native (12.3+), get/set parameters, batch edit, racks, chains, drum chain note assignment, presets, plugin deep control |
| Scenes | 12 | create, delete, duplicate, fire, name, color, tempo, scene matrix |
| Browser | 4 | search library, browse tree, load items, filter by category |
| Mixing | 11 | volume, pan, sends, routing, meters, return tracks, master, full mix snapshot |
| Arrangement | 21 | timeline clips, native arrangement clips (12.1.10+), arrangement notes, automation, recording, cue points |
| Automation | 8 | 16 curve types, 15 recipes (filter sweep, sidechain pump, dub throw...), spectral suggestions |
| Theory | 7 | Krumhansl-Schmuckler key detection, Roman numeral analysis, species counterpoint, SATB harmonization |
| Harmony | 4 | neo-Riemannian PRL transforms, Tonnetz navigation, voice leading paths, chromatic mediants |
| Generative | 5 | Euclidean rhythm (Bjorklund), tintinnabuli (Arvo Part), phase shift (Steve Reich), additive process (Philip Glass) |
| Memory | 8 | save, recall, replay, manage production techniques by mood/genre/texture |
| MIDI I/O | 4 | export/import .mid, offline analysis, piano roll extraction |
| Perception | 4 | offline loudness (integrated LUFS, LRA), spectral analysis, reference comparison |

<br>

### M4L Bridge — 38 analyzer tools `[optional]`, 32 bridge commands

The M4L Analyzer sits on the master track. UDP 9880 carries spectral data to the server. OSC 9881 sends commands back. The `ensure_analyzer_on_master` pre-flight (v1.20.3) loads the analyzer idempotently on first use — call it once at session start and forget about it.

> [!TIP]
> Most tools work without the analyzer — it adds 38 spectral/analyzer tools (frequency, loudness, perception, Simpler, warp) and closes the feedback loop.

```
SPECTRAL ─────── 9-band frequency decomposition (sub_low → air)
                 sub_low (20-60 Hz) split off so kick fundamentals don't hide inside sub
                 true RMS / peak metering
                 Krumhansl-Schmuckler key detection

DEEP LOM ─────── hidden parameters beyond ControlSurface API
                 automation state per parameter
                 recursive device tree (6 levels into nested racks)
                 human-readable display values as shown in Live's UI

SIMPLER ──────── replace / load samples
                 get slice points, crop, reverse
                 warp to N beats, get audio file paths

WARP ─────────── get / add / move / remove markers
                 tempo manipulation at the sample level
```

<br>

### Device Atlas — 13 tools

The atlas is an in-memory indexed database of Ableton's entire device library.

```
5264 devices total
  120 enriched with sonic intelligence (mood, genre, texture, chains)
   47 with aesthetic-tagged signature_techniques
  683 drum kits mapped with note assignments
    7 indexes: by_id, by_name, by_uri, by_category, by_tag, by_genre, by_pack
  146 technique cross-references across 58 devices (reverse-index)
```

```
atlas_search                   Search devices by name, category, or tag
atlas_device_info              Full enriched profile for a single device
atlas_suggest                  Suggest devices for a musical intent (e.g., "warm pad")
atlas_chain_suggest            Build a device chain from a genre, artist, or purpose
atlas_compare                  Compare two devices side-by-side
atlas_describe_chain           Free-text describe-a-chain ("granular pad like Tim Hecker")
atlas_techniques_for_device    Reverse-lookup: what techniques reference this device?
atlas_pack_info                Inspect a single Ableton pack — devices + enrichment coverage
scan_full_library              Scan what's actually installed on this machine
reload_atlas                   Hot-reload the atlas after adding enrichments
extension_atlas_search         [v1.23.0+] Search user-local atlas overlays
extension_atlas_get            [v1.23.0+] Fetch a single overlay entry by namespace
extension_atlas_list           [v1.23.0+] Enumerate overlay namespaces + entity_type counts

# Pack-Atlas Phase C-F (v1.23.4+) — corpus-driven orchestration
atlas_macro_fingerprint        [v1.23.4+] "More like this" — find similar presets across 3,813 sidecars by macro fingerprint
atlas_transplant               [v1.23.4+] Adapt a demo / preset / workflow to new BPM, scale, or aesthetic — PRESERVE / SCALE / REMAP / REPLACE decisions
atlas_demo_story               [v1.23.4+] Track-by-track narrative + production sequence inference for any of 104 factory demo .als
atlas_extract_chain            [v1.23.4+] Surgically rebuild a demo track's device chain as an executable plan (load_browser_item + insert_device + set_device_parameter)
atlas_pack_aware_compose       [v1.23.4+] Bootstrap a project with pack-coherent track selection from an aesthetic brief; supports `pack_diversity="eclectic"` mode
atlas_cross_pack_chain         [v1.23.4+] Execute any of 15 cross-pack workflow recipes step-by-step with aesthetic overrides (target_scale / target_bpm / transpose_semitones)
```

**v1.23.0 — User-local extensions:** Drop YAML files at `~/.livepilot/atlas-overlays/<namespace>/` to extend the atlas with custom hardware libraries, signature chains, or technique recipes — survives npm updates. See [`docs/EXTENSION_API.md`](docs/EXTENSION_API.md).

**v1.23.4 — Pack-Atlas Phases C/D/E/F:** Six new corpus-driven orchestration tools turn the 3,917 parsed pack sidecars + 104 demo `.als` parses into actionable artifacts — find similar presets, transplant aesthetics across BPM/scale/genre, narrate a demo, extract a track's chain as a runnable plan, bootstrap pack-coherent compositions, run any of 15 cross-pack workflow recipes. All execution is dry-run by default — returns plans, doesn't auto-mutate the session.

<br>

### User Corpus — 14 tools `[v1.23.4+]`

> **Why this exists.** The factory atlas covers what Ableton ships. Most studios also have
> third-party plugins, Max for Live devices, custom racks, presets, and sample packs. The corpus
> builder indexes that local library so recommendations can use tools you actually own.

The corpus builder turns what is installed on your machine into searchable production context:

```
Phase 1 — DETECT      Walk plugin folders + run `auval -a` for AUv3 / Mac Catalyst
                       coverage. Captures format (VST3/AU/AAX/CLAP/LV2),
                       vendor, version, bundle ID. ~40-200 plugins typical.

Phase 2 — CANONICALIZE Dedupe by vendor+name, prefer VST3 over AU, strip vendor
                       suffix variants ("Valhalla DSP, LLC" = "Valhalladsp" =
                       "Valhalla DSP"). Cluster by vendor for batch research.

Phase 3 — RESEARCH    Discover local manual files (PDFs, READMEs) per plugin.
                       Prepare focused plugin and technique research tasks.

Phase 4 — SYNTHESIZE  Build a per-plugin identity.yaml
                       with sonic_fingerprint / reach_for / avoid / key_techniques /
                       parameter_glossary / comparable_plugins / genre_affinity /
                       producer_anchors. Keep one primary format tag (no
                       dual-indexing across formats).
```

The result lives at `~/.livepilot/atlas-overlays/user/plugins/<plugin_id>/identity.yaml` and is available to `atlas_search`, `atlas_chain_suggest`, `atlas_macro_fingerprint`, and `atlas_describe_chain` alongside the factory atlas. Every result names its source (`factory_atlas` or `user_overlay:user`), so you can see whether a recommendation comes from Ableton stock or your own gear.

```
corpus_setup_wizard            One-shot orchestration — runs the full pipeline
corpus_init                    Initialize ~/.livepilot/corpus/ + manifest.yaml
corpus_status                  Inspect manifest, sources, scan history
corpus_list_scanners           Enumerate registered scanner types
corpus_add_source              Register a new scan source (project / racks / Max / samples)
corpus_remove_source           Remove a scan source from manifest
corpus_scan                    Run scanners on configured sources
corpus_detect_plugins          Phase 1 — VST3 / AU / AUv3 / VST2 / AAX / LV2 detection
corpus_canonicalize_plugins    Phase 2 — dedupe + VST3-preferred + suffix strip
corpus_cluster_plugins         Phase 2.5 — group by vendor for efficient research dispatch
corpus_trim_plugin_identity    Slim a yaml to the overlay-required minimum
corpus_discover_manuals        Phase 3 — locate local PDFs / READMEs per plugin
corpus_research_targets        Phase 3 — prepare research tasks for the agent
corpus_emit_synthesis_briefs   Phase 4 — prepare identity briefs per plugin
```

**Why this matters.** A static index goes stale when your library changes. Re-scan after adding
a plugin or rack and LivePilot can consider it alongside Ableton's factory devices.

**Quick start:**

```bash
# In your MCP client (Claude Code / Desktop / Cursor):
corpus_setup_wizard                              # one-shot orchestration
# OR fine-grained control:
corpus_detect_plugins use_auval=true             # finds AUv3 / Mac Catalyst plugins
corpus_canonicalize_plugins                      # VST3 preference + vendor dedup
corpus_cluster_plugins                           # vendor-grouped clusters
corpus_research_targets                          # → agent researches the plugins
corpus_emit_synthesis_briefs                     # → agent writes identity profiles
```

See [`docs/USER_CORPUS_GUIDE.md`](docs/USER_CORPUS_GUIDE.md) for full walk-through, [`docs/PLUGIN_KNOWLEDGE_ENGINE.md`](docs/PLUGIN_KNOWLEDGE_ENGINE.md) for engine internals, and [`livepilot/skills/livepilot-corpus-builder/SKILL.md`](livepilot/skills/livepilot-corpus-builder/SKILL.md) for the agent skill that drives the pipeline.

<br>

### Sample Engine — 23 tools

Search Ableton, local folders, and Splice together, then rank results against the musical
role instead of returning a pile of filenames.

```
SOURCES ─────────── BrowserSource  (Ableton's built-in library)
                    SpliceSource   (local Splice catalog via SQLite)
                    FilesystemSource (user-specified directories)
                    Splice LIVE    (gRPC + GraphQL for the full catalog)

CRITICS ─────────── key fitness · tempo fitness · spectral match
                    genre alignment · mood alignment · technical quality

TECHNIQUES ─────── 29 processing recipes:
                    Surgeon (precise, transparent) vs.
                    Alchemist (experimental, transformative)

PLAN-AWARE ─────── Ableton Live plan   100 samples/day (no credit drain)
                    Sounds+/Creator     CREDIT_HARD_FLOOR=5 safety gate
                    Free samples        bypass both gates
```

```
Sample analysis & planning
  analyze_sample            Build complete SampleProfile (material, key, BPM, spectral)
  search_samples            Multi-source search with critic scoring
  evaluate_sample_fit       Score a candidate sample against session context
  suggest_sample_technique  Recommend processing technique for a sample
  plan_sample_workflow      Full processing pipeline: warp + slice + effects
  plan_slice_workflow       Slice-specific workflow for breaks / drum loops
  get_sample_opportunities  Surface sample-friendly spots in the session

Splice LIVE (catalog, collections, presets)
  get_splice_credits        Plan + remaining credits + daily quota state
  splice_catalog_hunt       Query the full Splice catalog (gRPC)
  splice_download_sample    Plan-aware download (credit floor + quota check)
  splice_preview_sample     Zero-cost audition via PreviewURL
  splice_describe_sound     Natural-language search via Splice GraphQL
  splice_generate_variation Find catalog samples similar to a given UUID
  splice_list_collections   Enumerate user's Likes / bass / keys folders
  splice_search_in_collection / add_to_collection / remove_from_collection / create_collection
  splice_list_presets       Purchased instrument presets
  splice_preset_info · splice_download_preset
  splice_pack_info          Per-pack metadata
  splice_http_diagnose      Debug the Splice HTTPS bridge
```

<br>

### Splice Integration

LivePilot reads Splice's local SQLite database to search your downloaded samples with full metadata. No API key needed — it reads the database file directly.

**What it does:**
- Searches your downloaded Splice samples with key, BPM, genre, and tag metadata
- Integrates as a third source alongside Ableton's browser and filesystem scanning
- Works without a Splice subscription — any previously downloaded samples are searchable

**How it works:** The Sample Engine's `SpliceSource` reads `~/Library/Application Support/com.splice.Splice/users/default/*/sounds.db` — Splice's local SQLite catalog of downloaded samples. Read-only, no network calls.

**Requirements:** Splice desktop app running (the MCP server talks to it over gRPC at a dynamic port advertised via `port.conf`, with self-signed TLS). For fully offline search, previously-downloaded samples are always searchable via the local SQLite fallback even if the Splice app isn't running.

<br>

### Composer — three modes (v1.25.0)

Prompt-to-plan composition workflow. Three modes share the same safety checks: reconnect the
bridge, load the analyzer when needed, set monitoring correctly on new tracks, and return to
Arrangement View after the build. The work stays visible as a sequence of tool calls.

```
"dark minimal techno 128bpm with industrial textures and ghostly vocals"
    │
    ▼
┌─────────────────┐
│  Prompt Parser   │ → CompositionIntent (genre, mood, tempo, key)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Layer Planner   │ → role templates (kick, bass, perc, texture, lead, pad, fx)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Plan Compiler   │ → executable tool sequences
└────────┬────────┘
         ▼
┌─────────────────┐
│ Execution Router │ → dispatches: create tracks, search samples, load devices,
│                  │   program notes, set volumes, build arrangement
└─────────────────┘
```

#### fast mode — `compose_fast_apply`

Quick loop sketch. Single scene in session view. Intended for roughing out ideas quickly.

- Hunt order: curated `.adg` chains from the browser first, atlas devices second, bare instruments only as last resort
- Drum-role pitch repair included (Simpler default root vs. MIDI 36 offset)
- 4 genre defaults: house, techno, trap, ambient (unknown genres fall back to a neutral layer plan)
- Invoke with: *"Make me a [genre] loop at [tempo] BPM"*

#### full mode — `compose_full_apply`

Full track with song form: intro, verse, hook, breakdown, outro. Uses a two-phase LLM-creative brief flow — the LLM authors the form (sections, track list, per-section variants); the framework supplies the vocabulary (device hunt order, MIDI generation rules, arrangement conventions).

- Per-section MIDI variants prevent repeated tiles across the arrangement
- Native arrangement clips via `create_native_arrangement_clip` (one clip per section, looped to fill section length)
- Zombie-track cleanup in postflight (removes tracks with no clips and no instrument device)
- Drum-role pitch repair ported from fast mode
- **Atlas anchors:** role-level device knowledge is supplied through `KnowledgePack.atlas_anchors`, which consults the indexed atlas rather than filename matching. The older `atlas_candidates_per_role` field is a deprecated legacy stub, kept empty for back-compat.
- Invoke with: *"Write a full [genre] track at [tempo] BPM"* or *"Build a full arrangement"*

#### develop mode — `develop_apply`

Extends an existing 8-bar loop without disturbing the seed material.

- Introspects the existing session (classifies tracks by name and content)
- Pulls artist and stylistic references from the user prompt
- Writes per-track variants and new supporting layers alongside the seed
- Invoke with: *"Develop this loop"* or *"Extend what's here into a longer idea"*

#### KnowledgePack scaffolding (v1.25.0)

All three modes share a `KnowledgePack` that provides structured creative context at runtime:

- `event_lexicon` — 42 structural events across 7 categories (drum density, harmonic, texture, vocal, rhythm feel, tension, fx gesture)
- `genre_context` — parses the 15-genre `genre-vocabularies.md` at load time
- `artist_context` — parses the ~25-producer `artist-vocabularies.md` at load time
- `atlas_anchors` — indexed-atlas device anchors per role (replaced the legacy `atlas_candidates_per_role` stub)

#### Core composer tools

- `compose` — plan a multi-layer composition from text prompt (entry point, mode-agnostic)
- `compose_fast_apply` — execute fast mode directly
- `compose_full_apply` — execute full mode directly
- `develop_apply` — execute develop mode directly
- `augment_with_samples` — plan sample-based layers for an existing session
- `get_composition_plan` — dry-run preview (see the plan without credit checks)

<br>

### Device Forge — 3 tools

Generate M4L audio effect devices from `gen~` templates and install them into Ableton's browser.

```
forge_device           Generate a device from a gen~ template
forge_list_templates   Browse available gen~ templates
forge_install          Install generated device to browser
```

<br>

### Planning, Evaluation, and Learning — 79 tools

These tools read the session, diagnose problems, plan changes, compare results, and carry
useful context into the next decision.

| Domain | # | What it does |
|--------|:-:|-------------|
| Agent OS | 8 | session kernel, action ledger, capability state, routing, turn budget |
| Composition | 9 | section analysis, motif detection, emotional arc, form planning |
| Evaluation | 1 | before/after evaluation with structured scoring |
| Mix Engine | 6 | critic-driven mix analysis, masking, headroom, stereo, dynamics |
| Sound Design | 4 | patch analysis, modulation planning, timbre scoring |
| Transition Engine | 5 | transition classification, scoring, archetype-based planning |
| Reference Engine | 5 | reference profiling, principle distillation, gap analysis |
| Translation Engine | 3 | cross-domain translation, issue detection |
| Performance Engine | 3 | safety-constrained suggestions, safe moves, scene handoff |
| Song Brain | 3 | identity inference, sacred elements, drift monitoring |
| Hook Hunter | 9 | hook detection, salience scoring, neglect detection, phrase impact |
| Stuckness Detector | 3 | momentum analysis, rescue classification, rescue workflows |
| Wonder Mode | 3 | diagnosis-driven variants, taste-aware ranking |
| Session Continuity | 7 | creative threads, turn resolution, session story |
| Creative Constraints | 5 | constraint activation, reference-inspired variants |
| Preview Studio | 5 | variant creation, preview rendering, comparison, commit |

> **[View all 474 tools →](docs/manual/tool-catalog.md)**

<br>

---

## Install

### Claude Desktop: one-click install

Download the latest `livepilot-<version>.mcpb` from the [Releases page](https://github.com/dreamrec/LivePilot/releases/latest) and double-click it.
Claude Desktop installs everything automatically. Then:

1. Open Ableton Live 12
2. Preferences → Link, Tempo & MIDI → Control Surface → **LivePilot**
3. Start chatting

> [!TIP]
> The Desktop Extension auto-installs the Remote Script and M4L Analyzer on first launch.

### Terminal: one-command setup

```bash
npx livepilot --setup
```

Runs the full setup wizard: checks Python, installs the Remote Script, creates the Python environment, copies the M4L Analyzer, and tests the Ableton connection.

### Manual: Step by Step

<details>
<summary><strong>1. Remote Script</strong></summary>

```bash
npx livepilot --install
```

Restart Ableton → Preferences → Link, Tempo & MIDI → Control Surface → **LivePilot**

</details>

<details>
<summary><strong>2. MCP Client</strong></summary>

**Claude Code** — pick one (installing both registers the MCP server twice and collides on port 9878):
```bash
# MCP server only:
claude mcp add LivePilot -- npx livepilot

# Or the full plugin (MCP server + skills + slash commands):
claude plugin marketplace add github:dreamrec/LivePilot
claude plugin install livepilot@dreamrec-LivePilot
```

**Codex App:**
```bash
npx livepilot --install-codex-plugin
```

**Claude Desktop (macOS)** — `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "LivePilot": { "command": "npx", "args": ["livepilot"] }
  }
}
```

**Claude Desktop (Windows):**
```cmd
npm install -g livepilot
livepilot --install
```
`%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "LivePilot": { "command": "livepilot" }
  }
}
```

**Cursor** — `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "LivePilot": { "command": "npx", "args": ["livepilot"] }
  }
}
```

**VS Code** — `.vscode/mcp.json`:
```json
{
  "servers": {
    "LivePilot": { "command": "npx", "args": ["livepilot"] }
  }
}
```

</details>

<details>
<summary><strong>3. M4L Analyzer (optional — adds 38 tools)</strong></summary>

Drag `LivePilot_Analyzer.amxd` onto the master track for real-time spectral analysis.
The `--setup` wizard and Desktop Extension do this automatically. From v1.20.3, your AI client can also call `ensure_analyzer_on_master` — an idempotent pre-flight that loads the device if missing and no-ops otherwise. The Creative Director skill does this on every session's Phase 1 ground read so you can't forget.

> **Important:** The Analyzer must be the LAST device on the master track — after all effects (EQ, Compressor, Utility) so it reads the final output signal. The pre-flight tool reports `is_last_on_master: bool` and warns if the invariant is broken.

</details>

<details>
<summary><strong>4. Splice (optional — adds sample catalog)</strong></summary>

If you have Splice installed with downloaded samples, the Sample Engine can search them with full metadata (key, BPM, genre, tags) via the local SQLite database.

No API key, no configuration — the Sample Engine reads Splice's `sounds.db` file directly.

Without Splice, the Sample Engine still searches Ableton's browser and your filesystem.

</details>

### Verify

```bash
npx livepilot --status
```

<br>

---

## Plugin

**Codex App**

```bash
npx livepilot --install-codex-plugin
```

**Claude Code**

```bash
claude plugin marketplace add github:dreamrec/LivePilot
claude plugin install livepilot@dreamrec-LivePilot
```

| Command | What |
|---------|------|
| `/session` | Full session overview with diagnostics |
| `/beat` | Guided beat creation |
| `/arrange` | Guided arrangement and song structure |
| `/mix` | Mixing assistant |
| `/sounddesign` | Sound design workflow |
| `/perform` | Live performance mode with safety constraints |
| `/evaluate` | Before/after evaluation of recent changes |
| `/memory` | Technique library management |

**Producer Agent** — handles longer jobs in visible stages: reads the session,
checks what you kept, searches the library, proposes a plan, applies edits, and
listens back. You stay in charge of what remains in the set.

**Core Skill** — keeps the work disciplined: search before loading, measure before
and after, preserve undo, and verify every change.

<br>

---

## CLI

```bash
npx livepilot              # Start MCP server (stdio)
npx livepilot --setup      # Full setup wizard
npx livepilot --install    # Install Remote Script
npx livepilot --uninstall  # Remove Remote Script
npx livepilot --install-codex-plugin   # Install bundled Codex plugin
npx livepilot --uninstall-codex-plugin # Remove bundled Codex plugin
npx livepilot --status     # Check Ableton connection
npx livepilot --doctor     # Full diagnostic check
npx livepilot --version    # Show version
```

<br>

---

## Compatibility

| Requirement | Minimum |
|-------------|---------|
| Ableton Live | **12** (any edition). Suite required for Max for Live bridge and stock instruments |
| Python | 3.12+ (scipy>=1.18 requires Python 3.12) |
| Node.js | 18+ |
| OS | macOS / Windows |
| Splice | Desktop app with downloaded samples (optional — enables SQLite metadata search) |

**Version tiers:**
- **Core (12.0+):** All session tools, mixing, devices, MIDI, theory, generative, memory
- **Enhanced Arrangement (12.1.10+):** Native arrangement clips, arrangement automation
- **Full Intelligence (12.3+):** `insert_device_native`, complete device insertion pipeline
- **Collaborative (12.4+):** `replace_sample_native` and newer sample-editing routes that bypass the M4L fallback when Live exposes a native LOM path

<br>

---

## Development

```bash
git clone https://github.com/dreamrec/LivePilot.git
cd LivePilot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# Test runner is not in requirements.txt (runtime-only deps) — install it explicitly:
.venv/bin/pip install pytest pytest-asyncio
.venv/bin/pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture details, code guidelines, and how to add tools.

<br>

---

## Documentation

| Document | What's inside |
|----------|---------------|
| [Manual](docs/manual/index.md) | Complete reference: architecture, all 474 tools, workflows |
| [Planning & evaluation](docs/manual/intelligence.md) | How the 12 decision systems connect — conductor, moves, preview, evaluation |
| [Device Atlas](docs/manual/device-atlas.md) | 5264 devices indexed — search, suggest, chain building |
| [Samples & Slicing](docs/manual/samples.md) | 3-source search, fitness critics, slice workflows |
| [Automation](docs/manual/automation.md) | 16 curve types, 15 recipes, spectral suggestions |
| [Composition](docs/manual/composition.md) | Composer, section analysis, arrangement planning |
| [Getting Started](docs/manual/getting-started.md) | Zero to sound in five minutes |
| [Workflows](docs/manual/workflows.md) | Beats, session setup, sound design, arrangement, mixing |
| [MIDI Guide](docs/manual/midi-guide.md) | Drum patterns, scales, chords, humanization |
| [Sound Design](docs/manual/sound-design.md) | Instruments, effects, parameter recipes |
| [Mixing](docs/manual/mixing.md) | Gain staging, EQ, compression, sends, stereo width |
| [M4L Bridge](docs/M4L_BRIDGE.md) | Technical reference for the Max for Live analyzer |
| [Troubleshooting](docs/manual/troubleshooting.md) | Connection issues, common errors, diagnostics |

<br>

---

## Community

- [Discussions](https://github.com/dreamrec/LivePilot/discussions) — questions, ideas, show & tell
- [Bug reports](https://github.com/dreamrec/LivePilot/issues/new?template=bug_report.yml)
- [Feature requests](https://github.com/dreamrec/LivePilot/issues/new?template=feature_request.yml)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

<br>

---

## Support

LivePilot is source-available under the [Business Source License 1.1](LICENSE).
If it earns a place in your sessions, you can support its continued development:

<p align="center">
  <a href="https://github.com/sponsors/dreamrec"><strong>Sponsor on GitHub</strong></a>
</p>

Sponsorship funds deeper Ableton coverage, cross-platform testing, and maintained technique
libraries. Sponsors also get early builds and direct support.

<br>

---

<p align="center">
  <a href="LICENSE">BSL-1.1</a> — Pilot Studio
  <br><br>
  Sister projects: <a href="https://github.com/dreamrec/TDPilot">TDPilot</a> (TouchDesigner) · <a href="https://github.com/dreamrec/ComfyPilot">ComfyPilot</a> (ComfyUI)
</p>

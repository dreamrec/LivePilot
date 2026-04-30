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
  An agentic production system for Ableton Live 12.<br>
  453 tools. 54 domains. Device atlas. Plan-aware Splice integration. Auto-composition. Spectral perception. Technique memory. Drum-rack pad builder. Live dead-device detection.
</p>

<br>

> [!NOTE]
> LivePilot works with **any MCP client** — Claude Code, Claude Desktop, Cursor, VS Code, Windsurf.
> All tools execute on Ableton's main thread through the official Live Object Model API.
> Live-session mutations (clips, devices, mixer, arrangement) route through Ableton's undo stack.
> Side effects that touch state outside the Live project — Splice downloads, memory/ledger writes,
> installer actions, atlas scans, filesystem writes — persist beyond undo.

<br>

---

## What LivePilot Does

Most MCP servers are tool collections — they execute commands. LivePilot is an **agentic production system**. It has eight layers that work together:

| Layer | What it provides |
|-------|-----------------|
| **Deterministic Tools** | Direct control: transport, tracks, clips, notes, devices, scenes, mixing, arrangement, browser, automation |
| **Device Atlas** | Knowledge of every device in Ableton's library — 5264 devices indexed 7 ways (by_id, by_name, by_uri, by_category, by_tag, by_genre, by_pack). 120 enriched with YAML sonic intelligence (47 with aesthetic-tagged `signature_techniques`). 683 drum kits mapped. Free-text `atlas_describe_chain` ("a granular pad like Tim Hecker") and reverse-lookup `atlas_techniques_for_device` cross-reference 146 techniques across 58 devices |
| **User Corpus** `[v1.23.4+]` | Detects YOUR third-party plugins (VST3 / AU / AUv3 / VST2 / AAX / CLAP / LV2) via filesystem walk + `auval -a`, then auto-synthesizes per-plugin identity profiles (sonic_fingerprint, reach_for, avoid, key_techniques) into the same overlay system the factory atlas uses. The brain stops being limited to Ableton's shipped devices and learns *your* library — Valhalla, Glitchmachines, Cem Olcay, ChowDSP, Moog, your custom .adg racks, your Max for Live devices. Same query → different recommendations per user. **14 `corpus_*` tools.** See [User Corpus](#user-corpus--14-tools-v1234) below |
| **Concept Surface** | Two reference files let the LLM's training translate into LivePilot: `artist-vocabularies.md` maps ~25 producers (Villalobos, Hawtin, Basic Channel, Gas, Basinski, Hecker, Aphex, Autechre, Dilla, Burial, Henke, Daft Punk, …) to `reach_for` / `avoid` / `key_techniques`; `genre-vocabularies.md` maps 15 genres to tempo / kick / bass / percussion / harmonic / texture / devices. The LLM reads "sound like Gas" and gets a concrete device chain, not guesswork |
| **Sample Engine** | Three-source sample intelligence — Ableton's browser, your filesystem, and Splice's catalog (plan-aware: Ableton Live plan uses daily quota, Sounds+/Creator uses credits, free samples bypass both). 6 fitness critics. 29 processing techniques. Collections, presets, preview-URL audition, LIVE Describe-a-Sound + Variations via Splice GraphQL |
| **Spectral Perception** | Real-time ears via M4L — 9-band FFT (with sub_low split at 20-60 Hz for kick fundamentals), RMS/peak metering, Krumhansl-Schmuckler key detection, pitch tracking, FluCoMa mel/chroma/onset. Auto-loaded via `ensure_analyzer_on_master` (v1.20.3) — no more silently-degraded mix moves from forgotten analyzer |
| **Technique Memory** | Persistent library of production decisions. Save a beat pattern, device chain, or mix template. Recall by mood, genre, or texture across sessions |
| **Creative Intelligence** | 12 engines on top of the tools: SongBrain, Taste Graph, Wonder Mode, Mix/Sound-Design/Transition/Reference/Translation engines, Hook Hunter, Stuckness Detector, Session Continuity, Preview Studio. **44 semantic moves** (v1.21) — musical intents like "tighten the low end" or "make kick and bass lock" that compile into tool sequences with risk levels and target dimensions |

<br>

---

## Two Ways to Talk to LivePilot

Pick whichever is faster for the idea in your head — both reach the same 453-tool surface.

### Route A — Artist / aesthetic shorthand

> *"Sound like J Dilla."* &nbsp; *"Make this feel more like Burial."* &nbsp; *"BoC-style pads."*

The Concept Surface (`artist-vocabularies.md` + `genre-vocabularies.md`) maps ~25 producers and 15 genres to concrete `reach_for` / `avoid` / `key_techniques` lists. An artist name becomes a queryable label for a cluster of techniques. Useful when you know the aesthetic but not the parameters, or when one word is faster than the half-paragraph of reverb / sidechain / pitch-bend settings it implies.

### Route B — Direct musical intent

> *"Humanize the drum loop: 62% swing on the 16th hats, snare landing 4 ms ahead of the 2 and 4 for forward push, ghost snares filling every off-16th at velocity 25–40, kick locked to the grid, and add ±2 ms timing jitter to everything except the kick. EQ a 3 dB notch at 380 Hz on the snare to pull it back from the bass."*

The full Live Object Model is exposed. Swing percentages, micro-timing offsets in milliseconds, dB cuts, frequency ranges, modulation depths, envelope shapes, send levels, automation curves, scale degrees, voice leading — anything the LOM allows, plus the 44 semantic moves on top.

### Mixing the routes

Most sessions do both. Lead with shorthand to anchor the aesthetic, then refine with millisecond-precision intent once the shape is roughed in. Every artist tag resolves to moves you can also call directly — the shorthand is a convenience layer over the same parameters you reach with Route B.

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
│                  │   453 MCP Tools  │                                  │
│                  │   54 domains     │                                  │
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

**Remote Script** (`remote_script/LivePilot/`) — A Python ControlSurface that runs inside Ableton's process. Listens on TCP 9878. All Live Object Model calls execute on Ableton's main thread via `schedule_message`. Detects Ableton version at startup and enables three capability tiers: Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+).

**MCP Server** (`mcp_server/`) — Python FastMCP server. Validates inputs, routes commands to the Remote Script over TCP, manages the M4L bridge, runs the atlas, sample engine, composer, and all intelligence engines. This is what your AI client connects to.

**M4L Bridge** (`m4l_device/`) — Optional Max for Live Audio Effect on the master track. Provides deep LOM access through Max's LiveAPI that the ControlSurface API can't reach. UDP 9880 (M4L to server) carries spectral data and LiveAPI responses. OSC 9881 (server to M4L) sends commands. The 38 spectral/analyzer tools strictly require the bridge; device and sample tools that call the bridge also have graceful fallbacks, so core functionality works without it. Backed by 32 bridge commands for hidden parameters, Simpler internals, warp markers, display values, and Simpler warp / Compressor sidechain writes that live on child objects Python can't reach.

**Device Atlas** (`mcp_server/atlas/`) — In-memory indexed JSON database. 5264 devices with browser URIs (bundled baseline), 120 enriched with YAML sonic intelligence profiles (mood, genre, texture, recommended chains). 7 indexes: by_id, by_name, by_uri, by_category, by_tag, by_genre, by_pack. Reverse-index `device_techniques_index.json` powers `atlas_techniques_for_device` (146 cross-references across 58 devices). The AI never hallucinates a device name or preset — it always resolves against the atlas first. **v1.22.0+**: run `scan_full_library` after install to index YOUR packs + User Library + plugins into `~/.livepilot/atlas/device_atlas.json` — your personal atlas overrides the baseline and survives npm updates.

**Sample Engine** (`mcp_server/sample_engine/`) — Searches three sources simultaneously: BrowserSource (Ableton's library), SpliceSource (local Splice catalog via SQLite), FilesystemSource (user directories). Every result passes through a 6-critic fitness battery (key, tempo, spectral, genre, mood, technical). 29 processing techniques (Surgeon precision vs. Alchemist experimentation). Builds complete sample processing plans with warp, slice, and effect recommendations.

**Splice Client** (`mcp_server/splice_client/`) — Searches Splice's catalog through two layers: the local SQLite database (`sounds.db`, already-downloaded samples) and the live gRPC API (full catalog, including samples you haven't downloaded yet). The gRPC client auto-detects Splice's dynamic port via `port.conf`, handles self-signed TLS, and enforces a 5-credit safety floor before any download. Per-call timeouts (5–10s) prevent a hung Splice process from stalling the MCP event loop. Graceful fallback to SQL-only if grpcio isn't installed. No API key needed — authentication comes from the running Splice desktop app.

**Composer** (`mcp_server/composer/`) — Prompt-to-plan pipeline. Parses natural language ("dark minimal techno 128bpm with industrial textures") into a CompositionIntent (genre, mood, tempo, key). Plans layers using role templates (kick, bass, percussion, texture, lead, pad, fx). Compiles to a step-by-step plan of tool calls that the agent executes. Does not execute autonomously — returns the plan. 4 genre defaults (house, techno, trap, ambient) — genres outside this set fall back to a neutral layer plan.

**Corpus** (`mcp_server/corpus/`) — Parsed device-knowledge markdown converted to queryable Python structures: EmotionalRecipe, GenreChain, PhysicalModelRecipe, AutomationGesture. Feeds Wonder Mode, Sound Design critics, and the Composer with deep creative knowledge at runtime — not just LLM prompts, actual structured data.

**Execution Router** (`mcp_server/runtime/execution_router.py`) — Classifies each step in a multi-step plan as remote_command (TCP to Ableton), bridge_command (OSC to M4L), or mcp_tool (internal), then dispatches it through the correct channel.

<br>

---

## The Intelligence Layer

12 engines sit on top of the 453 tools. They give the AI musical judgment, not just musical execution.

### SongBrain — What the Song Is

Builds a real-time model of the session: identity core (what defines this track), sacred elements (what must not be casually damaged), section purposes (what each part is doing emotionally), energy arc (where the song is heading). Detects identity drift when edits pull the track away from what made it work.

### Taste Graph — What You Like

Learns your production preferences across sessions. Tracks which move families you keep vs. undo, which devices you gravitate toward, how experimental you want suggestions (novelty band), and which dimensions you avoid. Every accept/reject updates the graph. Two producers using the same tools get different recommendations.

### Semantic Moves — Musical Actions, Not Parameters

**44 high-level intents** across 7 families (mix, arrangement, transition, sound_design, performance, device_creation, sample) — "add contrast," "tighten the low end," "make kick and bass lock," "sample vocal ghost," "destroy then rebuild." Each move compiles into a concrete tool sequence with risk level, target dimensions, and protection thresholds. Analyzer-gated moves (`tighten_low_end`, `make_kick_bass_lock`) mark their spectrum pre-reads as optional so the plan continues even when the analyzer isn't available. The AI knows what it's risking with every action.

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

453 tools across 54 domains. Highlights below — [full catalog here](docs/manual/tool-catalog.md).

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

> **Why this exists.** The factory atlas (5264 devices, 33 packs) is what *Ableton ships*. Your real library is bigger — your VST/AU plugins, your Max for Live devices, your `.adg` racks, your custom presets, your Splice packs. Without the corpus builder, all of that is invisible to LivePilot. With it, the same query that previously routed to Operator + Saturator can route to *your* Valhalla Supermassive, *your* CHOWTapeModel, *your* Moog Model D — because LivePilot now knows what you have, what each tool sounds like, and which producer aesthetics it supports.

The corpus builder is a 4-phase pipeline that turns "what's installed on this Mac" into AI-queryable knowledge:

```
Phase 1 — DETECT      Walk plugin folders + run `auval -a` for AUv3 / Mac Catalyst
                       coverage. Captures format (VST3/AU/AAX/CLAP/LV2),
                       vendor, version, bundle ID. ~40-200 plugins typical.

Phase 2 — CANONICALIZE Dedupe by vendor+name, prefer VST3 over AU, strip vendor
                       suffix variants ("Valhalla DSP, LLC" = "Valhalladsp" =
                       "Valhalla DSP"). Cluster by vendor for batch research.

Phase 3 — RESEARCH    Discover local manual files (PDFs, READMEs) per plugin.
                       Emit WebSearch task packets for plugin+technique research.

Phase 4 — SYNTHESIZE  Sonnet subagent dispatch — write per-plugin identity.yaml
                       with sonic_fingerprint / reach_for / avoid / key_techniques /
                       parameter_glossary / comparable_plugins / genre_affinity /
                       producer_anchors. EXACTLY ONE primary format tag (no
                       dual-indexing across formats).
```

The result lives at `~/.livepilot/atlas-overlays/user/plugins/<plugin_id>/identity.yaml` and is loaded by every reasoning tool — `atlas_search`, `atlas_chain_suggest`, `atlas_macro_fingerprint`, `atlas_describe_chain` — alongside the factory atlas. Each result is tagged with its source (`factory_atlas` vs `user_overlay:user`), so the agent always knows whether it's recommending Ableton stock or your own gear.

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
corpus_research_targets        Phase 3 — emit WebSearch task packet for the agent
corpus_emit_synthesis_briefs   Phase 4 — emit sonnet-subagent briefs per plugin
```

**Why versatility outside Ableton matters.** A static knowledge base ages out the day you install a new plugin. The corpus builder makes LivePilot's knowledge boundary equal to *your library*, not *Ableton's library*. Every plugin you add can be re-scanned and synthesized in minutes; every saved `.adg` rack you build can be indexed alongside Ableton's factory chains. The brain becomes specifically yours.

**Quick start (3 commands):**

```bash
# In your MCP client (Claude Code / Desktop / Cursor):
corpus_setup_wizard                              # one-shot orchestration
# OR fine-grained control:
corpus_detect_plugins use_auval=true             # finds AUv3 / Mac Catalyst plugins
corpus_canonicalize_plugins                      # VST3 preference + vendor dedup
corpus_cluster_plugins                           # vendor-grouped clusters
corpus_research_targets                          # → agent runs WebSearch
corpus_emit_synthesis_briefs                     # → sonnet writes identity.yamls
```

See [`docs/USER_CORPUS_GUIDE.md`](docs/USER_CORPUS_GUIDE.md) for full walk-through, [`docs/PLUGIN_KNOWLEDGE_ENGINE.md`](docs/PLUGIN_KNOWLEDGE_ENGINE.md) for engine internals, and [`livepilot/skills/livepilot-corpus-builder/SKILL.md`](livepilot/skills/livepilot-corpus-builder/SKILL.md) for the agent skill that drives the pipeline.

<br>

### Sample Engine — 23 tools

Three-source sample intelligence with critic-driven fitness scoring, plus deep Splice integration (catalog search, preview, collections, preset downloads).

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

### Composer — 3 tools

Prompt-to-plan auto-composition engine.

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

- 4 genre defaults: house, techno, trap, ambient (unknown genres fall back to a neutral plan)
- Returns step-by-step plans — the agent executes each tool call in sequence
- `compose` — plan a multi-layer composition from text prompt
- `augment_with_samples` — plan sample-based layers for existing session
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

### Agentic Intelligence — 79 tools

The V2 intelligence layer. These tools analyze, diagnose, plan, evaluate, and learn.

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

> **[View all 453 tools →](docs/manual/tool-catalog.md)**

<br>

---

## Install

### Easiest: Claude Desktop Extension (1 click)

Download [`livepilot.mcpb`](https://github.com/dreamrec/LivePilot/releases/latest) and double-click it.
Claude Desktop installs everything automatically. Then:

1. Open Ableton Live 12
2. Preferences → Link, Tempo & MIDI → Control Surface → **LivePilot**
3. Start chatting

> [!TIP]
> The Desktop Extension auto-installs the Remote Script and M4L Analyzer on first launch.

### Quick: One Command Setup

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

**Claude Code:**
```bash
claude mcp add LivePilot -- npx livepilot
claude plugin add github:dreamrec/LivePilot/plugin
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
claude plugin add github:dreamrec/LivePilot/plugin
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

**Producer Agent** — an orchestrated multi-step assistant for building,
layering and refining sessions. Consults memory for style context, searches
the atlas for instruments, searches samples, creates tracks, programs MIDI,
chains effects, reads the spectrum to verify, and arranges sections. The
agent proposes plans; the user confirms and listens. LivePilot is a high-
trust operator, not an autonomous producer.

**Core Skill** — operational discipline connecting all layers.
Consult atlas before loading. Read analyzer after mixing.
Check memory before creative decisions. Verify every mutation.

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
| Python | 3.9+ |
| Node.js | 18+ |
| OS | macOS / Windows |
| Splice | Desktop app with downloaded samples (optional — enables SQLite metadata search) |

**Version tiers:**
- **Core (12.0+):** All session tools, mixing, devices, MIDI, theory, generative, memory
- **Enhanced Arrangement (12.1.10+):** Native arrangement clips, arrangement automation
- **Full Intelligence (12.3+):** `insert_device_native`, complete device insertion pipeline

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
| [Manual](docs/manual/index.md) | Complete reference: architecture, all 453 tools, workflows |
| [Intelligence Layer](docs/manual/intelligence.md) | How the 12 engines connect — conductor, moves, preview, evaluation |
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

LivePilot is source-available under the [Business Source License 1.1](LICENSE). If it saves you time in your sessions:

<p align="center">
  <a href="https://github.com/sponsors/dreamrec"><strong>Sponsor on GitHub</strong></a>
</p>

Sponsors get early access to new features, premium skills, curated technique libraries, and direct support.

<br>

---

<p align="center">
  <a href="LICENSE">BSL-1.1</a> — Pilot Studio
  <br><br>
  Sister projects: <a href="https://github.com/dreamrec/TDPilot">TDPilot</a> (TouchDesigner) · <a href="https://github.com/dreamrec/ComfyPilot">ComfyPilot</a> (ComfyUI)
</p>

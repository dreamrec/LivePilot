# LivePilot Manual

An agentic production system for Ableton Live 12.
430 tools. 53 domains. Device atlas. Sample intelligence. Auto-composition. Spectral perception. Technique memory. Creative intelligence.

---

## What LivePilot Is

LivePilot is not a tool collection with an AI wrapper. It is a **production system** — three perception layers feed into 430 tools, which are orchestrated by a dozen creative engines that understand song identity, learn your taste, diagnose session problems, and generate real musical options.

The difference: a tool collection executes "set volume to -6dB." LivePilot understands that turning down the drums might kill the groove that defines the track, suggests three genuinely different ways to create space instead, lets you preview each one, and remembers which approach you preferred.

---

## Architecture

```
AI Client  ──MCP──►  FastMCP Server  ──TCP/9878──►  Remote Script (inside Ableton)
                        (validates)                    (executes on main thread)
                            │
                            ├── Device Atlas (1305 devices, 120 enriched, 7 indexes)
                            ├── M4L Analyzer ──UDP/OSC──► LivePilot_Analyzer.amxd
                            └── Technique Memory (~/.livepilot/memory/)
```

The **atlas** resolves device names and browser URIs — the AI never hallucinates a preset. 641 devices are indexed by pack (Core Library + explicit-pack assignments) so "what's in Drone Lab?" is an instant lookup. Reverse-index `device_techniques_index.json` cross-references 146 techniques across 58 devices (the `atlas_techniques_for_device` tool).
The **analyzer** feeds back spectral data from the master bus so the AI hears its own changes — **9 frequency bands** (sub_low / sub / low / low_mid / mid / high_mid / high / presence / air); the sub_low band (20-60 Hz) separates kick fundamental from DC rumble. From v1.20.3 the analyzer is auto-loaded via `ensure_analyzer_on_master` — the Creative Director skill calls this at the top of every turn's Phase 1 ground read.
The **memory** persists production decisions across sessions as searchable, replayable data structures.

All 430 tools execute as deterministic LOM calls on Ableton's main thread. Everything is reversible with undo.

---

## The Three Layers

### Layer 1: Deterministic Tools

The foundation. Direct control over every aspect of Ableton Live through the Live Object Model: transport, tracks, clips, notes, devices, scenes, mixing, arrangement, browser, automation, scales, grooves, take-lanes, follow actions, MIDI tool generators. Also includes music theory (Krumhansl-Schmuckler key detection, neo-Riemannian harmony, species counterpoint), generative algorithms (Euclidean rhythm, tintinnabuli, phase shift, additive process), and MIDI I/O.

These tools do exactly what you ask. No interpretation, no judgment. They are the building blocks.

### Layer 2: Perception

The M4L Analyzer on the master track gives LivePilot ears: 9-band FFT spectrum (v1.17+), true RMS/peak metering, Krumhansl-Schmuckler key detection, pitch tracking, FluCoMa mel-spectrum + chroma + onset detection + spectral shape. Plus deep LOM access for hidden parameters, automation state, Simpler internals, and warp markers. Offline perception adds loudness analysis (integrated LUFS, LRA), spectral analysis, and reference comparison.

Perception closes the feedback loop. Without it, the AI is blind to the result of its own changes. With it, the AI can verify that a mix move actually reduced masking, that a filter sweep landed at the right frequency, that the overall loudness is broadcast-ready.

### Layer 3: Creative Intelligence

Sits on top of the tools and perception, adding musical judgment. This is what makes LivePilot agentic:

**Understanding the song:**
- **SongBrain** builds a real-time model of identity, sacred elements, section purposes, and energy arc
- **Composition Engine** detects motifs, infers emotional arcs, plans structural moves
- **Hook Hunter** finds the most salient musical idea and tracks whether it's being developed or neglected

**Understanding the producer:**
- **Taste Graph / Agent OS** learns move family preferences, device affinities, novelty tolerance, and dimension avoidances across sessions
- **Session Continuity** tracks creative threads, turn resolutions, and the session story
- **Technique Memory** stores and recalls production decisions by mood, genre, and texture

**Making musical decisions:**
- **Semantic Moves** express high-level intent ("add contrast," "tighten the low end") as executable tool sequences with risk levels and protection thresholds
- **Wonder Mode** diagnoses stuck sessions, generates genuinely distinct rescue options, and lets you preview before committing
- **Preview Studio** renders variants using Ableton's undo system — hear each option, compare, then choose
- **Creative Constraints** activate style gates and render reference-inspired variants

**Evaluating results:**
- **Mix Engine** runs critic-driven analysis — masking, headroom, stereo, dynamics — and plans corrective moves
- **Sound Design Engine** analyzes patches for static timbre, missing modulation, and weak transients
- **Synthesis Brain** extracts timbre fingerprints + proposes synth branches
- **Transition / Reference / Translation Engines** score transitions, distill principles from reference tracks, translate across domains
- **Evaluation Loop** enforces measure-before, act, measure-after discipline on every creative move

---

## Domain Map

All 430 tools across 53 domains, in source-truth per-domain counts:

### Core Ableton Control (Layer 1 — 218 tools)

| Domain | # | Scope |
|--------|:-:|-------|
| Devices | 42 | Load by name/URI, insert native (12.3+), params, racks, chains, drum pads, plugins, presets, wavetable mod matrix, replace_sample (12.4+), `add_drum_rack_pad`, `verify_device_alive` (v1.16+) |
| Arrangement | 21 | Timeline editing, arrangement notes, native clips (12.1.10+), cue points, recording, capture, `set_arrangement_automation_via_session_record` (v1.17+) |
| Transport | 21 | Playback, tempo, time sig, loop, metronome, undo/redo, diagnostics, capture MIDI |
| Tracks | 21 | Create MIDI/audio/return, delete, duplicate, arm, mute, solo, routing, sends, monitoring |
| Memory | 18 | Save, recall, replay, session memory, list/favorite/delete, update |
| Clips | 16 | Create, delete, duplicate, fire, stop, loop, launch mode, warp mode, pitch, color |
| Scenes | 12 | Create, delete, duplicate, fire, name, color, per-scene tempo, follow actions |
| Mixing | 11 | Volume, pan, sends, routing, meters, return tracks, mix snapshot |
| Automation | 9 | Clip envelopes, 16 curve types, 15 recipes, spectral suggestions |
| Composition | 9 | Section analysis, motif detection, emotional arc, form planning |
| Notes | 8 | Add/get/remove/modify MIDI, transpose, duplicate, per-note probability |
| Scales | 8 | Clip scales, song scales, scale modes, list available scales |
| Follow Actions | 8 | Clip + scene follow actions, presets, type listing |
| Theory | 7 | Harmony analysis, Roman numerals, scales, countermelody, transposition |
| Grooves | 7 | Groove templates, per-clip groove, groove amount, groove params |
| Take Lanes | 6 | Create, name, list, per-lane clips |
| Generative | 5 | Euclidean rhythm, tintinnabuli, phase shift, additive process |
| Browser | 4 | Search library, browse tree, load items |
| Harmony | 4 | Tonnetz navigation, voice leading, neo-Riemannian classification |
| MIDI I/O | 4 | Export/import .mid, offline analysis, piano roll extraction |
| MidiTool | 4 | Device install, generator registration, per-clip target mapping |

### Perception (Layer 2 — 45 tools)

| Domain | # | Scope |
|--------|:-:|-------|
| Analyzer | 37 | 9-band spectrum (v1.17+), RMS, key detection, Simpler ops, warp markers, capture, FluCoMa mel/chroma/onset `[M4L]` |
| Perception | 4 | Offline loudness, spectral analysis, reference comparison, metadata |
| Diagnostics | 3 | Device/session health verification, test-note fire-and-forget |
| Evaluation | 1 | Before/after evaluation with structured scoring |

### Creative Intelligence (Layer 3 — 161 tools, ~20 engines)

| Domain | # | Scope |
|--------|:-:|-------|
| Sample Engine | 23 | Multi-source search (Splice gRPC + browser + filesystem), Splice catalog hunt, downloads, previews, pack info, collections, presets, describe-a-sound (LIVE), variations (LIVE), http-diagnose (v1.17+) |
| Hook Hunter | 9 | Hook detection, salience scoring, neglect detection, phrase impact |
| Atlas | 10 | Search 1305 devices, suggest by intent, chain building, comparison, library scan, `atlas_pack_info`, `atlas_describe_chain` (free-text), `atlas_techniques_for_device` (reverse-lookup) — all v1.17+ |
| Agent OS | 8 | Session kernel, action ledger, capability state, routing, goal vectors, taste |
| Session Continuity | 7 | Creative threads, turn resolution, session story, anti-preferences |
| Musical Intelligence | 6 | Phrase arc, impact scoring, comparison, rendering, grid analysis, snapshot |
| Mix Engine | 6 | Critic-driven mix analysis, issue detection, move planning |
| Preview Studio | 5 | Variant creation, preview rendering, comparison, commit, discard |
| Runtime | 5 | Session kernel building, world model, capability, safety, resume intent |
| Experiment | 5 | Create, run, compare, commit, discard A/B experiment branches |
| Creative Constraints | 5 | Constraint activation, reference-inspired variants |
| Sound Design | 4 | Patch analysis, modulation planning, timbre scoring |
| Composer | 4 | Prompt → multi-layer composition plan, sample augmentation, plan preview, branches |
| Semantic Moves | 4 | Move listing, preview, application, next-best-move proposal |
| Transition Engine | 3 | Transition classification, scoring, archetype planning |
| Reference Engine | 3 | Reference profiling, principle distillation, gap analysis |
| Performance Engine | 3 | Safety-constrained suggestions, safe moves, scene handoff |
| Song Brain | 3 | Identity inference, sacred elements, drift monitoring |
| Stuckness Detector | 3 | Momentum analysis, rescue classification, rescue workflows |
| Wonder Mode | 3 | Diagnosis-driven variants, taste-aware ranking, session discard |
| Research | 3 | Technique research, style tactics |
| Synthesis Brain | 3 | Synth patch analysis, branch proposals, timbre fingerprint extraction |
| Device Forge | 3 | Generate M4L devices from gen~ templates, install to browser |
| Motif | 2 | Motif graph, motif transformation |
| Project Brain | 2 | Project-level analysis, section purpose inference |
| Planner | 2 | Gesture planning, arrangement planning |
| Translation Engine | 2 | Cross-domain translation, issue detection |

---

## Chapters

### Understanding the System

| Chapter | What's inside |
|---------|---------------|
| [The Intelligence Layer](intelligence.md) | How the engines connect — conductor, kernel, moves, preview, evaluation |
| [Device Atlas](device-atlas.md) | 1305 devices indexed — search, suggest, chain building, comparison, pack browsing |
| [Samples & Slicing](samples.md) | 3-source search, Splice describe-a-sound, variations, fitness critics |
| [Automation](automation.md) | 16 curve types, 15 recipes, spectral suggestions, two-phase arrangement-record workaround |
| [Composition & Arrangement](composition.md) | Composer, section analysis, arrangement planning with sample roles |

### Production Guides

| Chapter | What's inside |
|---------|---------------|
| [Workflows](workflows.md) | Step-by-step: beats, session setup, sound design, arrangement, mixing |
| [MIDI Guide](midi-guide.md) | Drum patterns, scales, chords, humanization techniques |
| [Sound Design](sound-design.md) | Instruments, effects, parameter recipes, device chains |
| [Mixing](mixing.md) | Gain staging, EQ, compression, sends, stereo width |

### Reference

| Chapter | What's inside |
|---------|---------------|
| [Tool Catalog](tool-catalog.md) | Every tool organized by domain (auto-generated from source) |
| [Tool Reference](tool-reference.md) | In-depth parameter docs, ranges, and usage notes for the most-used tools |
| [Troubleshooting](troubleshooting.md) | Connection issues, common errors, diagnostics |
| [Splice Endpoint Capture](splice-endpoint-capture.md) | mitmproxy runbook for capturing additional Splice GraphQL operations |

---

Next: [The Intelligence Layer](intelligence.md)

# LivePilot Manual

An agentic production system for Ableton Live 12.
316 tools. 43 domains. Device atlas. Sample intelligence. Auto-composition. Spectral perception. Technique memory. Creative intelligence.

---

## What LivePilot Is

LivePilot is not a tool collection with an AI wrapper. It is a **production system** — three perception layers feed into 316 tools, which are orchestrated by 12 creative engines that understand song identity, learn your taste, diagnose session problems, and generate real musical options.

The difference: a tool collection executes "set volume to -6dB." LivePilot understands that turning down the drums might kill the groove that defines the track, suggests three genuinely different ways to create space instead, lets you preview each one, and remembers which approach you preferred.

---

## Architecture

```
AI Client  ──MCP──►  FastMCP Server  ──TCP/9878──►  Remote Script (inside Ableton)
                        (validates)                    (executes on main thread)
                            │
                            ├── Device Atlas (1305 devices, 81 enriched with sonic intelligence)
                            ├── M4L Analyzer ──UDP/OSC──► LivePilot_Analyzer.amxd
                            └── Technique Memory (~/.livepilot/memory/)
```

The **atlas** resolves device names and browser URIs — the AI never hallucinates a preset.
The **analyzer** feeds back spectral data from the master bus so the AI hears its own changes.
The **memory** persists production decisions across sessions as searchable, replayable data structures.
All three feed into 316 deterministic LOM calls on Ableton's main thread. Everything is reversible with undo.

---

## The Three Layers

### Layer 1: Deterministic Tools (210 tools)

The foundation. Direct control over every aspect of Ableton Live through the Live Object Model: transport, tracks, clips, notes, devices, scenes, mixing, arrangement, browser, automation. Also includes music theory (Krumhansl-Schmuckler key detection, neo-Riemannian harmony, species counterpoint), generative algorithms (Euclidean rhythm, tintinnabuli, phase shift), and MIDI I/O.

These tools do exactly what you ask. No interpretation, no judgment. They are the building blocks.

### Layer 2: Perception (30 tools)

The M4L Analyzer on the master track gives LivePilot ears: 8-band FFT spectrum, true RMS/peak metering, Krumhansl-Schmuckler key detection, pitch tracking. Plus deep LOM access for hidden parameters, automation state, Simpler internals, and warp markers. Offline perception adds loudness analysis (integrated LUFS, LRA), spectral analysis, and reference comparison.

Perception closes the feedback loop. Without it, the AI is blind to the result of its own changes. With it, the AI can verify that a mix move actually reduced masking, that a filter sweep landed at the right frequency, that the overall loudness is broadcast-ready.

### Layer 3: Creative Intelligence (83 tools, 12 engines)

This is what makes LivePilot agentic. The intelligence layer sits on top of the tools and perception, adding musical judgment:

**Understanding the song:**
- **SongBrain** builds a real-time model of identity, sacred elements, section purposes, and energy arc
- **Composition Engine** detects motifs, infers emotional arcs, plans structural moves
- **Hook Hunter** finds the most salient musical idea and tracks whether it's being developed or neglected

**Understanding the producer:**
- **Taste Graph** learns move family preferences, device affinities, novelty tolerance, and dimension avoidances across sessions
- **Session Continuity** tracks creative threads, turn resolutions, and the session story
- **Technique Memory** stores and recalls production decisions by mood, genre, and texture

**Making musical decisions:**
- **Semantic Moves** express high-level intent ("add contrast," "tighten the low end") as executable tool sequences with risk levels and protection thresholds
- **Wonder Mode** diagnoses stuck sessions, generates genuinely distinct rescue options, and lets you preview before committing
- **Preview Studio** renders variants using Ableton's undo system — hear each option, compare, then choose

**Evaluating results:**
- **Mix Engine** runs critic-driven analysis — masking, headroom, stereo, dynamics — and plans corrective moves
- **Sound Design Engine** analyzes patches for static timbre, missing modulation, and weak transients
- **Transition Engine** scores transitions and plans improvements using archetype patterns
- **Reference Engine** distills principles from reference tracks and maps them to your session
- **Evaluation Loop** enforces measure-before, act, measure-after discipline on every creative move

---

## Domain Map

| Domain | # | Scope |
|--------|:-:|-------|
| Transport | 12 | Playback, tempo, time sig, loop, metronome, undo/redo, diagnostics |
| Tracks | 17 | Create MIDI/audio/return, delete, duplicate, arm, mute, solo, routing |
| Clips | 11 | Create, delete, duplicate, fire, stop, loop, launch mode, warp mode |
| Notes | 8 | Add/get/remove/modify MIDI, transpose, duplicate, per-note probability |
| Devices | 15 | Load by name or URI, params, batch edit, racks, chains, presets |
| Scenes | 12 | Create, delete, duplicate, fire, name, color, per-scene tempo |
| Browser | 4 | Search library, browse tree, load items |
| Mixing | 11 | Volume, pan, sends, routing, meters, return tracks, mix snapshot |
| Arrangement | 19 | Timeline editing, arrangement notes, cue points, recording, capture |
| Automation | 8 | Clip envelopes, 16 curve types, 15 recipes, spectral suggestions |
| Memory | 8 | Save, recall, replay, manage production techniques |
| Analyzer | 30 | Spectrum, RMS, key detection, Simpler ops, warp markers, capture `[M4L]` |
| Theory | 7 | Harmony analysis, Roman numerals, scales, countermelody, transposition |
| Generative | 5 | Euclidean rhythm, tintinnabuli, phase shift, additive process |
| Harmony | 4 | Tonnetz navigation, voice leading, neo-Riemannian classification |
| MIDI I/O | 4 | Export/import .mid, offline analysis, piano roll extraction |
| Perception | 4 | Offline loudness, spectral analysis, reference comparison, metadata |
| Agent OS | 8 | Session kernel, action ledger, capability state, routing |
| Composition | 9 | Section analysis, motif detection, emotional arc, form planning |
| Evaluation | 1 | Before/after evaluation with structured scoring |
| Mix Engine | 6 | Critic-driven mix analysis, issue detection, move planning |
| Sound Design | 5 | Patch analysis, modulation planning, timbre scoring |
| Transition Engine | 5 | Transition classification, scoring, archetype planning |
| Reference Engine | 5 | Reference profiling, principle distillation, gap analysis |
| Translation Engine | 3 | Cross-domain translation, issue detection |
| Performance Engine | 5 | Safety-constrained suggestions, safe moves, scene handoff |
| Song Brain | 4 | Identity inference, sacred elements, drift monitoring |
| Hook Hunter | 9 | Hook detection, salience scoring, neglect detection, phrase impact |
| Stuckness Detector | 3 | Momentum analysis, rescue classification, rescue workflows |
| Wonder Mode | 3 | Diagnosis-driven variants, taste-aware ranking, session discard |
| Session Continuity | 7 | Creative threads, turn resolution, session story |
| Creative Constraints | 5 | Constraint activation, reference-inspired variants |
| Preview Studio | 5 | Variant creation, preview rendering, comparison, commit |
| Semantic Moves | 4 | Move listing, preview, application, next-best-move proposal |
| Project Brain | 2 | Project-level analysis, section purpose inference |
| Runtime | 2 | Session kernel building, world model construction |
| Motif | 2 | Motif graph, motif transformation |
| Research | 4 | Technique research, style tactics |
| Planner | 3 | Gesture planning, arrangement planning, mix move planning |

---

## Chapters

| Chapter | What's inside |
|---------|---------------|
| [Tool Catalog](tool-catalog.md) | Every tool organized by domain |
| [Tool Reference](tool-reference.md) | Every tool with parameters, ranges, and usage notes |
| [Workflows](workflows.md) | Production workflows from session setup to arrangement |
| [MIDI Guide](midi-guide.md) | Drum patterns, scales, chords, humanization techniques |
| [Sound Design](sound-design.md) | Instruments, effects, parameter recipes, device chains |
| [Mixing](mixing.md) | Gain staging, EQ, compression, sends, stereo width |
| [Troubleshooting](troubleshooting.md) | Connection issues, common errors, diagnostics |

---

Next: [Tool Catalog](tool-catalog.md)

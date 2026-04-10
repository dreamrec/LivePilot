# LivePilot Manual

An agentic production system for Ableton Live 12.
292 tools. 39 domains. Device atlas. Spectral perception. Technique memory.

---

## Architecture

```
AI Client  ──MCP──►  FastMCP Server  ──TCP/9878──►  Remote Script (inside Ableton)
                        (validates)                    (executes on main thread)
                            │
                            ├── Device Atlas (280+ devices, 139 kits, 350+ IRs)
                            ├── M4L Analyzer ──UDP/OSC──► LivePilot_Analyzer.amxd
                            └── Technique Memory (~/.livepilot/memory/)
```

The atlas resolves device names and browser URIs — the AI never hallucinates a preset. The analyzer feeds back spectral data from the master bus so the AI hears the result of its own changes. The memory persists production decisions across sessions as searchable, replayable data structures. All three layers feed into 237 deterministic LOM calls on Ableton's main thread. Everything is reversible with undo.

---

## Domain Map

| Domain | # | Scope | Reference |
|--------|:-:|-------|-----------|
| Transport | 12 | playback, tempo, time sig, loop, metronome, undo/redo, diagnostics | [tool-reference](tool-reference.md#transport) |
| Tracks | 17 | create MIDI/audio/return, delete, duplicate, arm, mute, solo, routing | [tool-reference](tool-reference.md#tracks) |
| Clips | 11 | create, delete, duplicate, fire, stop, loop, launch mode, warp mode | [tool-reference](tool-reference.md#clips) |
| Notes | 8 | add/get/remove/modify MIDI, transpose, duplicate, per-note probability | [tool-reference](tool-reference.md#notes) |
| Devices | 15 | load by name or URI, params, batch edit, racks, chains, presets | [tool-reference](tool-reference.md#devices) |
| Scenes | 12 | create, delete, duplicate, fire, name, color, per-scene tempo | [tool-reference](tool-reference.md#scenes) |
| Browser | 4 | search library, browse tree, load items | [tool-reference](tool-reference.md#browser) |
| Mixing | 11 | volume, pan, sends, routing, meters, return tracks, mix snapshot | [tool-reference](tool-reference.md#mixing) |
| Arrangement | 19 | timeline editing, arrangement notes, cue points, recording, capture | [tool-reference](tool-reference.md#arrangement) |
| Automation | 8 | clip envelopes, 16 curve types, 15 recipes, spectral suggestions | [tool-reference](tool-reference.md#automation) |
| Memory | 8 | save, recall, replay, manage production techniques | [tool-reference](tool-reference.md#memory) |
| Analyzer | 29 | spectrum, RMS, key detection, Simpler ops, warp markers, FluCoMa DSP, capture `[M4L]` | [tool-reference](tool-reference.md#analyzer) |
| Theory | 7 | harmony analysis, Roman numerals, scales, countermelody, transposition | [tool-reference](tool-reference.md#theory) |
| Generative | 5 | Euclidean rhythm, tintinnabuli, phase shift, additive process | [tool-reference](tool-reference.md#generative) |
| Harmony | 4 | Tonnetz navigation, voice leading, neo-Riemannian classification | [tool-reference](tool-reference.md#harmony) |
| MIDI I/O | 4 | export/import .mid, offline analysis, piano roll extraction | [tool-reference](tool-reference.md#midi-io) |
| Perception | 4 | offline loudness analysis, spectral analysis, reference comparison, metadata | [tool-reference](tool-reference.md#perception) |

---

## Chapters

| Chapter | What's inside |
|---------|---------------|
| [Tool Reference](tool-reference.md) | Every tool with parameters, ranges, and usage notes |
| [Workflows](workflows.md) | Production workflows from session setup to arrangement |
| [MIDI Guide](midi-guide.md) | Drum patterns, scales, chords, humanization techniques |
| [Sound Design](sound-design.md) | Instruments, effects, parameter recipes, device chains |
| [Mixing](mixing.md) | Gain staging, EQ, compression, sends, stereo width |
| [Troubleshooting](troubleshooting.md) | Connection issues, common errors, diagnostics |

---

Next: [Tool Reference](tool-reference.md)

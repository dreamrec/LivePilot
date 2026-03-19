# LivePilot Manual

## What is LivePilot?

LivePilot connects AI to Ableton Live 12 — not as a remote control, but as a production partner with knowledge, perception, and memory.

Say *"set up a 126 BPM session with drums, bass, and a pad"* — and it builds it. It picks instruments from a knowledge base of 280+ devices (not by guessing names), programs patterns informed by your saved techniques, and reads the spectrum to verify the mix balance. Say *"add some swing to the hi-hats"* — and it remembers your preferred swing range from past sessions.

LivePilot is built on three layers that work together:

- **Device Atlas** — A deep corpus of 280+ instruments, 139 drum kits, and 350+ impulse responses. The AI looks up real device names and browser URIs instead of hallucinating them.
- **M4L Analyzer** — Real-time audio analysis on the master bus: 8-band spectrum, RMS/peak metering, pitch tracking, key detection. The AI hears the result of its own changes.
- **Technique Memory** — A persistent library of production decisions. The AI remembers how you built sounds, what patterns you liked, and how you mixed — and uses that context in future sessions.

On top of these sit 127 MCP tools across 11 domains. Every command is deterministic, goes through Ableton's official Live Object Model API, and is reversible with undo.

## What it actually does

LivePilot gives you **127 tools** organized across 11 domains:

| Domain | What it handles |
|--------|----------------|
| [Transport](getting-started.md#your-first-session) | Tempo, time signature, playback, loop, undo/redo |
| [Tracks](tool-reference.md#tracks) | Create, name, color, mute, solo, arm, delete, duplicate |
| [Clips](tool-reference.md#clips) | Create, fire, stop, loop, launch mode, duplicate |
| [Notes](midi-guide.md) | Add, read, modify, transpose, quantize, humanize MIDI |
| [Devices](sound-design.md) | Load instruments and effects, tweak every parameter, browse presets |
| [Scenes](tool-reference.md#scenes) | Create, fire, name, duplicate entire rows |
| [Mixing](mixing.md) | Volume, pan, sends, routing, return tracks, master |
| [Browser](sound-design.md#browsing-abletons-library) | Search the full Ableton library, load presets by name |
| [Arrangement](workflows.md#arrangement-workflow) | Timeline editing, MIDI notes in arrangement, cue points, recording |
| [Memory](tool-reference.md#memory) | Save, recall, replay, and manage production techniques |
| [Analyzer](tool-reference.md#analyzer) | Real-time spectral analysis, key detection, sample manipulation, warp markers (requires M4L device) |

Each tool maps directly to an Ableton Live API call. There's no abstraction layer that guesses what you mean — when you ask to set a parameter, it sets that parameter. When you ask to read notes, it reads the actual MIDI data from the clip. Everything is deterministic and reversible with undo.

## How it works

```
You (natural language)
  │
  ▼
AI Client ──MCP──► LivePilot MCP Server ──TCP──► Remote Script inside Ableton
                              (validates inputs)           (executes on main thread)
```

The MCP server validates your requests (range checks, type checks) before they reach Ableton. The Remote Script runs inside Ableton's Python environment and executes every command on the main thread — the same thread that handles the UI. This means your commands are always consistent with what you see on screen.

Everything goes through Ableton's official Live Object Model (LOM) API. LivePilot doesn't hack, inject, or work around the DAW — it uses the same interfaces that Ableton's own control surfaces use.

## Who this is for

Anyone curious about what happens when you put AI inside a DAW. Whether you're a seasoned producer or just getting started — if the idea of jamming with AI sounds interesting, this is for you.

## What's in this manual

| Chapter | What you'll learn |
|---------|-------------------|
| [Getting Started](getting-started.md) | Installation, setup, your first session |
| [Tool Reference](tool-reference.md) | Every tool explained with parameters and examples |
| [Workflows](workflows.md) | Real production workflows from idea to arrangement |
| [MIDI Guide](midi-guide.md) | Drum patterns, scales, chords, humanization |
| [Sound Design](sound-design.md) | Instruments, effects, and recipe starting points |
| [Mixing](mixing.md) | Levels, EQ, compression, sends, stereo width |
| [Troubleshooting](troubleshooting.md) | When things go wrong and how to fix them |

## The agentic approach

LivePilot is not a tool palette — it's an agentic system. The difference matters.

A tool palette exposes buttons: "set volume", "add note", "load device". The AI presses them one at a time, with no context about whether the device name is real, whether the result sounds right, or whether you've made something similar before.

LivePilot's agent operates differently. Before loading an instrument, it consults the device atlas to find one that actually exists. Before writing a bass line, it reads the key from the analyzer. Before choosing a drum pattern, it checks your technique memory for style preferences. After every change, it can verify the result through the spectrum and meters.

The three layers — atlas, analyzer, memory — give the agent the context it needs to make informed decisions rather than blind guesses. Your ears are still the final authority. But now the AI has ears too.

## How to think about it

Start with a rough idea. Listen. Adjust. Push further. It's a conversation — you set the direction, the agent handles the execution with the full context of what it knows, what it hears, and what it remembers.

---

Next: [Getting Started](getting-started.md)

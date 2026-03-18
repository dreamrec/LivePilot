# LivePilot Manual

## What is LivePilot?

LivePilot connects AI to Ableton Live 12. Talk to your DAW, and it talks back.

Say *"set up a 126 BPM session with drums, bass, and a pad"* — and it builds it. Say *"add some swing to the hi-hats"* — and it happens. You jam with AI the way you'd jam with another musician: throw out ideas, listen, react, push further.

It's 104 tools that let you create tracks, program MIDI, load instruments, tweak parameters, arrange, and mix — all through conversation. Think of it as co-creating with an impossibly fast session partner who knows every parameter name in every device.

## What it actually does

LivePilot gives you **104 tools** organized across 10 domains:

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

## How to think about it

Start with a rough idea. Listen. Adjust. Push further. It's a conversation — you set the direction, AI handles the execution. Your ears are the final authority.

---

Next: [Getting Started](getting-started.md)

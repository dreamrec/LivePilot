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
  <a href="https://github.com/dreamrec/LivePilot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dreamrec/LivePilot?style=flat-square" alt="License"></a>
  <a href="https://github.com/dreamrec/LivePilot/releases"><img src="https://img.shields.io/github/v/release/dreamrec/LivePilot?style=flat-square&label=release" alt="Latest Release"></a>
</p>

<p align="center">
  An agentic production system for Ableton Live 12.<br>
  255 tools. Device atlas. Spectral perception. Technique memory.
</p>

<br>

> [!NOTE]
> LivePilot works with **any MCP client** — Claude Code, Claude Desktop, Cursor, VS Code, Windsurf.
> All tools execute on Ableton's main thread through the official Live Object Model API.
> Everything is reversible with undo.

<br>

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   KNOWLEDGE            PERCEPTION           MEMORY          │
│   ───────────          ──────────           ──────          │
│                                                             │
│   280+ devices         8-band FFT           recall by       │
│   139 drum kits        RMS / peak           mood, genre,    │
│   350+ impulse         pitch tracking       texture         │
│   responses            key detection                        │
│                                                             │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│   │   Device   │─────▶│    M4L     │─────▶│ Technique  │   │
│   │   Atlas    │      │  Analyzer  │      │   Store    │   │
│   └─────┬──────┘      └─────┬──────┘      └─────┬──────┘   │
│         └───────────────────┼───────────────────┘           │
│                             ▼                               │
│                    ┌─────────────────┐                      │
│                    │   255 MCP Tools  │                      │
│                    │   32 domains     │                      │
│                    └────────┬────────┘                      │
│                             │                               │
│             Remote Script ──┤── TCP 9878                    │
│             M4L Bridge ─────┤── UDP 9880 / OSC 9881         │
│                             │                               │
│                    ┌────────────────┐                       │
│                    │  Ableton Live  │                       │
│                    └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

The **atlas** gives the AI knowledge of every device in Ableton's library —
real names, real URIs, real parameters.

The **analyzer** gives it ears — spectral data from the master bus
via a Max for Live device.

The **memory** gives it history — a searchable library of production decisions
that persists across sessions.

All three feed into 255 deterministic tools that execute on Ableton's main thread.

<br>

---

## Tools

255 tools across 32 domains. Highlights below — [full catalog here](docs/manual/tool-catalog.md).

<br>

### Core

| Domain | # | What it covers |
|--------|:-:|----------------|
| Transport | 12 | playback, tempo, time sig, loop, metronome, undo/redo, cue points, diagnostics |
| Tracks | 17 | create MIDI/audio/return, delete, duplicate, arm, mute, solo, color, freeze, flatten |
| Clips | 11 | create, delete, duplicate, fire, stop, loop, launch mode, warp mode, quantize |
| Notes | 8 | add/get/remove/modify MIDI notes, transpose, duplicate, per-note probability |
| Devices | 15 | load by name or URI, get/set parameters, batch edit, racks, chains, presets, plugin deep control |
| Scenes | 12 | create, delete, duplicate, fire, name, color, tempo, scene matrix |
| Browser | 4 | search library, browse tree, load items, filter by category |
| Mixing | 11 | volume, pan, sends, routing, meters, return tracks, master, full mix snapshot |
| Arrangement | 19 | timeline clips, arrangement notes, arrangement automation, recording, cue points |

<br>

### Perception — 30 tools `[M4L]`

The M4L Analyzer sits on the master track. UDP 9880 carries spectral data
from Max to the server. OSC 9881 sends commands back.

> [!TIP]
> All 207 core tools work without the analyzer — it adds 30 more and closes the feedback loop.

```
SPECTRAL ─────── 8-band frequency decomposition (sub → air)
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

### Intelligence

<details>
<summary><strong>Theory — 7 tools</strong></summary>

<br>

Krumhansl-Schmuckler key detection with 7 mode profiles:
major, minor, dorian, phrygian, lydian, mixolydian, locrian.

Roman numeral analysis via scale-degree chord matching
on a 1/32 note quantization grid.

Voice leading checks — parallel fifths, parallel octaves,
voice crossing, unresolved dominants.

Species counterpoint generation (1st and 2nd species).
SATB harmonization with smooth voice leading.
Diatonic transposition that preserves scale relationships.

```
analyze_harmony         suggest_next_chord      detect_theory_issues
identify_scale          harmonize_melody         generate_countermelody
transpose_smart
```

</details>

<details>
<summary><strong>Harmony — 4 tools</strong></summary>

<br>

Neo-Riemannian PRL transforms on the Tonnetz.

```
P  flips the third ─────── Cm ↔ C
L  shifts by semitone ──── C  ↔ Em
R  shifts by whole tone ── C  ↔ Am
```

All three are involutions — apply twice, return to origin.

BFS through PRL space finds the shortest voice-leading path
between any two triads. Cm to E major? That's PLP — the hexatonic pole.
Three steps, each moving one voice by a semitone.
The Hitchcock chord change.

Chromatic mediants for film-score harmony: chords a major/minor third away
sharing 0-1 common tones. Maximum color shift, minimal voice movement.

```
navigate_tonnetz        find_voice_leading_path
classify_progression    suggest_chromatic_mediants
```

</details>

<details>
<summary><strong>Generative — 5 tools</strong></summary>

<br>

**Euclidean Rhythm** — Bjorklund distributes N pulses across M steps.
Bresenham's line algorithm applied to rhythm.

```
E(3,8)  = tresillo          ×··×··×·
E(5,8)  = cinquillo          ×·××·××·
E(7,16) = Brazilian necklace ×·×·×××·×·×·×××·
```

Layer multiple patterns at different pitches for polyrhythmic textures.

**Tintinnabuli** (Arvo Pärt) — for each melody note, find the nearest tone
of a specified triad. Two voices, one rule, infinite music.

**Phase Shifting** (Steve Reich) — identical voices with accumulating timing drift.
They start in unison, gradually separate, and eventually realign.

**Additive Process** (Philip Glass) — melody unfolds note by note.
The structure *is* the composition.

```
generate_euclidean_rhythm    layer_euclidean_rhythms
generate_tintinnabuli        generate_phase_shift
generate_additive_process
```

</details>

<details>
<summary><strong>Automation — 8 tools</strong></summary>

<br>

16 curve types in 4 categories:

```
BASIC ──────────── linear · exponential · logarithmic · s_curve
                   sine · sawtooth · spike · square · steps

ORGANIC ─────────── perlin · brownian · spring

SHAPE ──────────── bezier · easing
                   (bounce, elastic, back, quad, cubic,
                    quart, quint, expo)

GENERATIVE ─────── euclidean · stochastic
```

15 built-in recipes:

```
filter_sweep_up     filter_sweep_down    dub_throw
tape_stop           build_rise           sidechain_pump
fade_in             fade_out             tremolo
auto_pan            stutter              breathing
washout             vinyl_crackle        stereo_narrow
```

Perception-action loop: `analyze_for_automation` reads the spectrum
and device chain, suggests what to automate, and maps each suggestion
to a recipe.

```
get_clip_automation      set_clip_automation       clear_clip_automation
apply_automation_shape   apply_automation_recipe   get_automation_recipes
generate_automation_curve                          analyze_for_automation
```

</details>

<details>
<summary><strong>Memory — 8 tools</strong></summary>

<br>

Persistent technique library across sessions.

Five types: `beat_pattern` · `device_chain` · `mix_template` · `preference` · `browser_pin`

Each stores:
- **Identity** — name, tags, timestamps
- **Qualities** — mood, genre, texture, production notes
- **Payload** — raw MIDI, device params, tempo, URIs

Recall by text query matching mood, genre, texture — not just names.

```
memory_learn     memory_recall     memory_list       memory_get
memory_update    memory_delete     memory_favorite   memory_replay
```

</details>

<details>
<summary><strong>MIDI I/O — 4 tools</strong></summary>

<br>

Export session clips to standard .mid files.
Import .mid into session clips — auto-creates the clip, tempo-aware timing.

Offline analysis without Ableton: note count, duration, tempo,
pitch range, velocity stats, density curve, key estimate.

Piano roll extraction: 2D velocity matrix at configurable resolution
(default 1/32 note).

```
export_clip_midi     import_midi_to_clip
analyze_midi_file    extract_piano_roll
```

</details>

<details>
<summary><strong>Perception — 4 tools</strong></summary>

<br>

Offline audio analysis — no M4L required.

```
analyze_loudness        Integrated LUFS, true peak, LRA, streaming compliance
analyze_spectrum_offline  Spectral centroid, rolloff, flatness, 5-band balance
compare_to_reference    Mix vs reference: loudness + spectral delta
read_audio_metadata     Format, duration, sample rate, tags
```

</details>

<br>

> **[View all 255 tools →](docs/manual/tool-catalog.md)**

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

This runs the full setup wizard: checks Python, installs the Remote Script, creates the Python environment, copies the M4L Analyzer, and tests the Ableton connection.

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
<summary><strong>3. M4L Analyzer (optional)</strong></summary>

Drag `LivePilot_Analyzer.amxd` onto the master track for real-time spectral analysis.
The `--setup` wizard and Desktop Extension do this automatically.

</details>

Unlocks 29 additional tools: spectral analysis, key detection,
sample manipulation, deep device introspection, plugin parameter mapping.

> [!IMPORTANT]
> All core tools work without the analyzer. It adds perception, not dependency.

### 4. Verify

```bash
npx livepilot --status
```

<br>

---

## Plugin

```bash
claude plugin add github:dreamrec/LivePilot/plugin
```

| Command | What |
|---------|------|
| `/session` | Full session overview with diagnostics |
| `/beat` | Guided beat creation |
| `/mix` | Mixing assistant |
| `/sounddesign` | Sound design workflow |
| `/memory` | Technique library management |

**Producer Agent** — autonomous multi-step production.
Consults memory for style context, searches the atlas for instruments,
creates tracks, programs MIDI, chains effects, reads the spectrum to verify.

**Core Skill** — operational discipline connecting all three layers.
Consult atlas before loading. Read analyzer after mixing.
Check memory before creative decisions. Verify every mutation.

<br>

---

## CLI

```bash
npx livepilot              # Start MCP server (stdio)
npx livepilot --install    # Install Remote Script
npx livepilot --uninstall  # Remove Remote Script
npx livepilot --status     # Check Ableton connection
npx livepilot --doctor     # Full diagnostic check
npx livepilot --version    # Show version
```

<br>

---

## Compatibility

- **Ableton Live 12** — all editions. Suite required for Max for Live and stock instruments (Drift, Meld, Wavetable).
- **Python** 3.9+
- **Node.js** 18+
- **macOS / Windows**

<br>

---

## Development

```bash
git clone https://github.com/dreamrec/LivePilot.git
cd LivePilot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture details, code guidelines, and how to add tools.

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

<p align="center">
  <a href="LICENSE">MIT</a> — Pilot Studio
  <br><br>
  Sister projects: <a href="https://github.com/dreamrec/TDPilot">TDPilot</a> (TouchDesigner) · <a href="https://github.com/dreamrec/ComfyPilot">ComfyPilot</a> (ComfyUI)
</p>

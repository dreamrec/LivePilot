```
██╗     ██╗██╗   ██╗███████╗██████╗ ██╗██╗      ██████╗ ████████╗
██║     ██║██║   ██║██╔════╝██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██║     ██║██║   ██║█████╗  ██████╔╝██║██║     ██║   ██║   ██║
██║     ██║╚██╗ ██╔╝██╔══╝  ██╔═══╝ ██║██║     ██║   ██║   ██║
███████╗██║ ╚████╔╝ ███████╗██║     ██║███████╗╚██████╔╝   ██║
╚══════╝╚═╝  ╚═══╝  ╚══════╝╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

# LivePilot v1.0.0

AI copilot for Ableton Live 12 — 78 MCP tools for production, sound design, and mixing.

Control your entire Ableton session from Claude Code. Create tracks, program MIDI, load instruments, tweak parameters, mix levels, navigate arrangements — all through natural language. Built for power users who want to move faster without leaving the keyboard.

## Quick Start

```bash
# Install the Remote Script into Ableton Live
npx livepilot --install

# Restart Ableton Live, then enable LivePilot in:
# Preferences > Link, Tempo & MIDI > Control Surface

# Check connection
npx livepilot --status
```

### Claude Code Plugin

Add LivePilot as a Claude Code plugin for skills, slash commands, and the producer agent:

```bash
claude plugin add ./plugin
```

### MCP Configuration

Add to your MCP client config (`.mcp.json`):

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["livepilot"]
    }
  }
}
```

## 78 Tools Across 9 Domains

| Domain | Count | Key Tools |
|--------|-------|-----------|
| **Transport** | 12 | get_session_info, set_tempo, play/stop, undo/redo, action log, diagnostics |
| **Tracks** | 12 | create/delete/duplicate, name, color, mute/solo/arm |
| **Clips** | 10 | create/delete/duplicate, fire/stop, loop, launch mode |
| **Notes** | 8 | add/get/remove/modify, transpose, quantize, duplicate |
| **Devices** | 10 | parameters, load by name/URI, racks, batch set |
| **Scenes** | 6 | create/delete/duplicate, fire, rename |
| **Mixing** | 8 | volume, pan, sends, routing, master, return tracks |
| **Browser** | 4 | tree, items, search, load |
| **Arrangement** | 8 | clips, recording, cue points, navigation |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/session` | Full session overview |
| `/beat` | Guided beat creation |
| `/mix` | Mixing assistant |
| `/sounddesign` | Sound design workflow |

## What It's Good At

**Session overview and navigation** — Summarize the set, find important tracks, report clip density, locate empty or duplicate sections. You often lose time understanding your own session state. LivePilot reads the whole session in one call.

**Repetitive build tasks** — Create track templates, duplicate and recolor tracks, load device chains, rename scenes, arm and route tracks. Repetitive actions are high-friction and low-creativity. This is where AI assistance feels immediately valuable.

**MIDI refinement** — Tighten timing, transpose selected notes, duplicate motifs, simplify busy passages, humanize or regularize a phrase. The AI improves your existing intent instead of pretending to invent taste from nothing.

**Session hygiene** — Detect tracks left armed, mute/solo leftovers, empty clips and unused scenes, inconsistent naming, MIDI tracks without instruments. Run `get_session_diagnostics` for a full health check.

## Architecture

```
Claude Code / AI Client
       │ MCP Protocol (stdio)
       ▼
┌─────────────────────┐
│   MCP Server        │  Python (FastMCP)
│   mcp_server/       │  Input validation, auto-reconnect
└────────┬────────────┘
         │ JSON over TCP (port 9878)
         ▼
┌─────────────────────┐
│   Remote Script     │  Runs inside Ableton's Python
│   remote_script/    │  Thread-safe command queue
│   LivePilot/        │  ControlSurface base class
└─────────────────────┘
```

Single-client TCP connection by design — Ableton's Live Object Model is not thread-safe.

## Compatibility

| Feature | Live 12 (all) | Suite only | Notes |
|---------|:-:|:-:|-------|
| Transport, tracks, clips, scenes | Yes | — | Core API, stable across all 12.x |
| MIDI notes (add, modify, remove) | Yes | — | Uses Live 12 note API |
| Device parameters, toggle, delete | Yes | — | Works with any device |
| Browser search & load | Yes | — | Results depend on installed content |
| Mixing (volume, pan, sends, routing) | Yes | — | |
| Arrangement (cue points, recording) | Yes | — | |
| Stock instruments (Analog, Operator, Wavetable, Drift, Meld) | — | Yes | Drift and Meld are Suite instruments |
| Max for Live devices | — | Yes | Requires Suite or M4L add-on |
| Stock effects (Compressor, Reverb, EQ Eight, etc.) | Yes | — | All editions include audio effects |
| Third-party VST/AU plugins | Yes | — | Loads via browser if installed |

**Python version:** Ableton Live 12 bundles Python 3.11. The MCP server runs outside Ableton and requires Python 3.10+.

## CLI

```bash
npx livepilot              # Start MCP server (stdio)
npx livepilot --install    # Install Remote Script
npx livepilot --uninstall  # Remove Remote Script
npx livepilot --status     # Check Ableton connection
npx livepilot --doctor     # Full diagnostic check
npx livepilot --version    # Version info
npx livepilot --help       # Show all commands
```

## Requirements

- **Ableton Live 12** (minimum)
- **Python 3.10+** (auto-detected; venv created on first run)
- **Node.js 18+**

## Development

```bash
# Set up Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run tests
.venv/bin/pytest tests/ -v
```

## License

MIT

# LivePilot

AI copilot for Ableton Live 12 — 76 MCP tools for production, sound design, and mixing.

Sister project to [TDPilot](https://github.com/your-org/TDPilot) (TouchDesigner) and ComfyPilot (ComfyUI).

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

## 76 Tools Across 9 Domains

| Domain | Count | Key Tools |
|--------|-------|-----------|
| **Transport** | 10 | get_session_info, set_tempo, play/stop, undo/redo |
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

## Requirements

- **Ableton Live 12** (minimum)
- **Python 3.10+** (auto-detected; venv created on first run)
- **Node.js 18+**

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

## Connection Model

LivePilot uses a **single-client** TCP connection. Only one MCP client can be connected to Ableton at a time. This is by design — Ableton's Live Object Model is not thread-safe, so serialized access prevents race conditions and data corruption.

If a second client attempts to connect while one is active, it receives an error message and is disconnected. To switch clients, disconnect the current one first.

## Development

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## License

MIT

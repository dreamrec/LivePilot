# Getting Started

This guide takes you from zero to making sound in about five minutes.

## What you need

- **Ableton Live 12** (any edition — Intro, Standard, or Suite)
- **Node.js 18+** ([download](https://nodejs.org/))
- **Python 3.10+** (usually pre-installed on macOS; [download](https://www.python.org/) for Windows)
- **An MCP-compatible AI client** — [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Claude Desktop](https://claude.ai/download), [Cursor](https://cursor.sh), VS Code with Copilot, or any other MCP client

## Step 1: Install the Remote Script

The Remote Script is a small Python program that runs inside Ableton and listens for commands from LivePilot. Run this once:

```bash
npx -y github:dreamrec/LivePilot --install
```

This auto-detects your Ableton installation and copies the script to the right folder. Works on macOS and Windows.

**What if it can't find Ableton?** The installer checks common paths. If your Ableton is installed somewhere unusual, you can manually copy the `remote_script/LivePilot/` folder to:
- **macOS:** `~/Music/Ableton/User Library/Remote Scripts/`
- **Windows:** `\Users\{you}\Documents\Ableton\User Library\Remote Scripts\`

## Step 2: Enable LivePilot in Ableton

1. **Restart Ableton Live** (required after installing the Remote Script)
2. Go to **Preferences > Link, Tempo & MIDI**
3. Under **Control Surface**, click the dropdown and select **LivePilot**
4. You should see `LivePilot: Listening on port 9878` in the status bar at the bottom

If you don't see LivePilot in the dropdown, the Remote Script wasn't copied to the right place. Double-check the path from Step 1.

## Step 3: Connect your AI client

### Claude Code

```bash
claude mcp add LivePilot -- npx -y github:dreamrec/LivePilot
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

Restart Claude Desktop after saving.

### Cursor / VS Code / Other MCP clients

Add to your MCP config file (`.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "github:dreamrec/LivePilot"]
    }
  }
}
```

## Step 4: Verify the connection

```bash
npx -y github:dreamrec/LivePilot --status
```

This pings Ableton over TCP. If you see `Connected`, you're good. If it says `Connection refused`, make sure:
1. Ableton Live is running
2. LivePilot is selected as Control Surface in Preferences
3. No firewall is blocking localhost port 9878

## Your first session

With Ableton open and LivePilot connected, try this conversation:

**You:** "What's in my session right now?"

The AI will call `get_session_info` and tell you the tempo, how many tracks you have, which scenes exist, and whether anything is playing. This is always a good starting point — it grounds the AI in your actual session state.

**You:** "Set the tempo to 120 and create a MIDI track called DRUMS"

Now you have a track. But it's empty — no instrument loaded, no clips, no notes.

**You:** "Search for a drum kit and load it onto the DRUMS track"

The AI will search Ableton's browser, find a kit (like "606 Core Kit" or "808 Core Kit"), and load it. Now the track has an instrument.

**You:** "Create an 8-beat clip and program a basic house kick pattern — four on the floor"

The AI creates a clip, programs kick notes (pitch 36) on every beat, and you should be able to hit play and hear it.

**You:** "Fire that clip"

Sound. You just made your first beat with LivePilot.

## Understanding the basics

### Everything is indexed from 0

The first track is `track_index: 0`. The first clip slot is `clip_index: 0`. The first scene is `scene_index: 0`. This matches how Ableton numbers things internally.

For return tracks, use negative indices: `-1` for Return A, `-2` for Return B, and so on. For the master track, use `-1000`. This works with device tools (load effects, tweak parameters) and mixing tools (volume, pan, routing).

### Time is measured in beats

All time values are in beats (quarter notes). At 4/4 time:
- 1.0 = one beat (quarter note)
- 4.0 = one bar
- 0.5 = one eighth note
- 0.25 = one sixteenth note

A "4-beat clip" is one bar. A "32-beat clip" is 8 bars.

### Volume is 0.0 to 1.0

It's not decibels. The scale is:
- `0.0` = silence (-inf dB)
- `0.50` = roughly -12 dB
- `0.70` = roughly -6 dB
- `0.85` = 0 dB (unity gain — what Ableton defaults to)
- `1.0` = +6 dB (louder than default — be careful)

### MIDI pitch is 0 to 127

Middle C is 60. Standard drum mapping (General MIDI):
- 36 = Kick
- 38 = Snare
- 42 = Closed Hi-Hat
- 46 = Open Hi-Hat
- 49 = Crash Cymbal

### Undo is your safety net

Every destructive operation can be undone. The AI has access to `undo` and `redo`. If something goes wrong, just say "undo that."

### Always verify after changes

Good practice: after creating or modifying something, the AI should read back the state to confirm it worked. This is built into LivePilot's design — the AI is taught to verify after every write operation.

## The Claude Code plugin

If you're using Claude Code, install the plugin for an enhanced experience:

```bash
claude plugin add github:dreamrec/LivePilot/plugin
```

This adds:

### Slash commands
- `/session` — Full session overview with diagnostics
- `/beat` — Guided beat creation workflow
- `/mix` — Mixing assistant
- `/sounddesign` — Sound design workflow

### The producer agent

An autonomous agent that can build entire tracks from high-level descriptions:

> "Make me a 126 BPM minimal techno track with a driving kick, shuffling hi-hats, and a deep bass line in A minor"

The agent handles track creation, instrument loading, pattern programming, arrangement, and basic mixing — the entire pipeline.

### The core skill

The `livepilot-core` skill teaches the AI how to use LivePilot properly: always check session state first, verify after writes, never load empty Drum Racks, check volumes, and more. It's the difference between an AI that fumbles through the API and one that works like an experienced producer's assistant.

## Keeping things updated

### When you update LivePilot

After pulling a new version:
1. Run `npx -y github:dreamrec/LivePilot --install` again to update the Remote Script
2. Restart Ableton to load the new handlers
3. Restart your AI client to pick up new MCP tools

The MCP server (Python process) and Ableton's Remote Script are separate. New tools need the MCP server restarted. New handler logic needs Ableton restarted. When in doubt, restart both.

### Checking your version

```bash
npx -y github:dreamrec/LivePilot --version
```

### Running diagnostics

```bash
npx -y github:dreamrec/LivePilot --doctor
```

This checks Python version, dependencies, Ableton connection, and Remote Script installation.

---

Next: [Tool Reference](tool-reference.md) | Back to [Manual](index.md)

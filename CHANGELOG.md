# Changelog

## 1.0.0 — LivePilot

**AI copilot for Ableton Live 12 — 104 MCP tools for real-time music production.**

### Core
- 104 MCP tools across 10 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory
- Remote Script using Ableton's official Live Object Model API (ControlSurface base class)
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL

### Browser & Device Loading
- Breadth-first device search with exact-match priority
- Plugin browser support (AU/VST/AUv3) via `search_browser("plugins")`
- Max for Live browser via `search_browser("max_for_live")`
- URI-based loading with category hint parsing for fast resolution
- Case-insensitive parameter name matching

### Arrangement
- Full arrangement view support: create clips, add/remove/modify notes, automation envelopes
- Automation on device parameters, volume, panning, and sends
- Support for return tracks and master track across all tools

### Plugin
- 5 slash commands: /beat, /mix, /sounddesign, /session, /memory
- Producer agent for autonomous multi-step tasks
- Technique memory system (learn, recall, replay, favorite)
- Built-in Device Atlas covering native Ableton instruments and effects

### Installer
- Auto-detects Ableton Remote Scripts path on macOS and Windows
- Copies Remote Script files, verifies installation

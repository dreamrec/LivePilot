# Changelog

## 1.0.0 — 2026-03-17

Initial release.

### Features
- **76 MCP tools** across 9 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement
- **Remote Script** for Ableton Live 12 with thread-safe command queue via `schedule_message`
- **MCP Server** (FastMCP) with input validation, auto-reconnect, and stale socket detection
- **CLI** (`npx livepilot`) with `--install`, `--uninstall`, `--status`, `--version`
- **Claude Code Plugin** with:
  - `livepilot-core` skill — core discipline and workflow guides
  - `livepilot-producer` agent — autonomous production from high-level descriptions
  - 4 slash commands: `/session`, `/beat`, `/mix`, `/sounddesign`
- **Installer** with auto-detection of Ableton paths on macOS and Windows
- **Live 12 modern note API** support: note IDs, probability, velocity_deviation
- **JSON over TCP** protocol on port 9878 with structured error codes

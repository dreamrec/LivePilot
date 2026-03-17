# LivePilot — Ableton Live 12 AI Copilot

## Project
- **Repo:** `/Users/visansilviugeorge/Desktop/LivePilot/`
- **Type:** MCP server + Claude Code plugin for Ableton Live 12
- **Sister projects:** TDPilot (TouchDesigner), ComfyPilot (ComfyUI)
- **Design spec:** `docs/specs/2026-03-17-livepilot-design.md`

## Architecture
- **Remote Script** (`remote_script/LivePilot/`): Runs inside Ableton's Python, ControlSurface base class, TCP socket on port 9878
- **MCP Server** (`mcp_server/`): Python FastMCP server, validates inputs, sends commands to Remote Script
- **Plugin** (`plugin/`): Claude Code plugin with skills, commands, agent
- **Installer** (`installer/`): Auto-detects Ableton path, copies Remote Script

## Key Rules
- ALL Live Object Model (LOM) calls must execute on Ableton's main thread via schedule_message queue
- Live 12 minimum — use modern note API (add_new_notes, get_notes_extended, apply_note_modifications)
- 78 tools across 9 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement
- JSON over TCP, newline-delimited, port 9878
- Structured errors with codes: INDEX_ERROR, NOT_FOUND, INVALID_PARAM, STATE_ERROR, TIMEOUT, INTERNAL

## Tool Count
Currently 78 tools. If adding/removing tools, update: README.md, package.json description, plugin/plugin.json, plugin/skills/livepilot-core/SKILL.md, CLAUDE.md, tests/test_tools_contract.py

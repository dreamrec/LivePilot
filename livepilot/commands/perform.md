---
name: perform
description: Performance mode — enter a safety-constrained live performance context with energy tracking and safe moves
---

Enter performance mode for live set support. All actions are constrained to safe and caution-level moves only.

1. **Get performance state** — `get_performance_state` to see scene roles, energy levels, and current position
2. **Show the dashboard** — present: current scene, energy level, energy direction (up/down/hold), available safe moves
3. **Get safe moves** — `get_performance_safe_moves` for what can be done right now
4. **Check before acting** — `check_safety(move_type)` before every action. Only execute safe or caution moves. Caution moves require user confirmation.

**BLOCKED during performance** (never execute, warn if requested):
- Creating or deleting tracks, clips, or scenes
- Editing notes or arrangement
- Adding or removing devices (device chain surgery)

**SAFE moves** (execute freely):
- Scene launches, mute/unmute, volume nudges, send adjustments, macro tweaks, filter sweeps

**Scene transitions:**
- `plan_scene_handoff(from_scene, to_scene)` — generates an energy path and gesture sequence
- Follow the energy path: if going up, suggest high-energy scenes; if going down, suggest breakdowns

**Always show:**
- Current energy level and direction
- What moves are available
- What moves are blocked and why

Use the livepilot-performance-engine skill for safety classification and move suggestions.

---
name: perform
description: Performance mode — enter a safety-constrained live performance context with energy tracking and safe moves
---

Enter performance mode with safety constraints and energy tracking.

## Orchestration Flow

1. **Session kernel** — `get_session_kernel(request_text="live performance", mode="improve")`
2. **Route** — `route_request("live performance")` → workflow_mode should be `performance_safe`
3. **Performance state** — `get_performance_state` for current scene, energy level, and safe moves

## Safety-First Rules

- **NEVER** execute moves rated "high risk" during performance
- **ALWAYS** use `get_performance_safe_moves` before ANY change
- Only fire scenes, adjust volumes, and trigger safe effects
- No device loading, track creation, or destructive operations

## Performance Tools

4. **Safe moves** — `get_performance_safe_moves` for available actions
5. **Scene handoff** — `plan_scene_handoff` for safe transitions between scenes
6. **Energy tracking** — monitor energy level across scene transitions
7. **Semantic moves** — only performance-safe semantic moves:
   - `smooth_scene_handoff` — safe transition between scenes
   - Gesture templates: `pre_arrival_vacuum`, `re_entry_spotlight`

## Live Dashboard

8. **Monitor** — `get_track_meters(include_stereo=true)` for real-time levels
9. **Spectrum** — `get_master_spectrum` for frequency balance during performance
10. **Playing clips** — `get_playing_clips` to see what's active

## Recovery

11. **If something goes wrong** — `undo` immediately
12. **Emergency** — `stop_all_clips` if audio goes haywire
13. **Check safety** — `check_safety` to verify constraints are holding

Keep the user informed of what's happening. Never make surprise changes during a live set.

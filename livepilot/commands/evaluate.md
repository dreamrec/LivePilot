---
name: evaluate
description: Evaluate recent changes — run the full before/after evaluation loop and recommend keep or undo
---

Run the universal evaluation loop on recent production changes.

1. **Check capability state** — `get_capability_state` to see what evaluation modes are available:
   - `normal` — full measured evaluation with analyzer data
   - `measured_degraded` — analyzer online but stale data
   - `judgment_only` — no analyzer, parameter-level heuristics only
   - `read_only` — session disconnected

2. **Ensure analyzer** — if mode is `judgment_only`, try to get full perception:
   - `find_and_load_device(track_index=-1000, device_name="LivePilot_Analyzer")`
   - Wait 2s, then `get_master_spectrum` to test the bridge
   - If bridge disconnected: `reconnect_bridge`
   - If still unavailable: proceed with `judgment_only` but tell the user

3. **Get the last move** — `get_last_move` to understand what was changed. If no recent move, `get_recent_actions` for history.

4. **Ask what the goal was** — what were they trying to achieve? More clarity? Wider stereo? Punchier drums?

5. **Compile the goal** — `compile_goal_vector(goal_description, mode="improve")`

6. **Capture current state** — full perception snapshot:
   - `get_master_spectrum` + `get_master_rms` (if analyzer available)
   - `get_track_meters(include_stereo=true)` — verify all tracks producing audio
   - `get_mix_snapshot` — full volume/pan/send state
   - Optionally: `capture_audio` + `analyze_loudness` + `analyze_spectrum_offline` for ground truth

7. **Undo the change** — `undo()` to restore the before state

8. **Capture before state** — same reads as step 6

9. **Redo the change** — `redo()` to restore the after state

10. **Evaluate** — `evaluate_move(before_snapshot, after_snapshot, goal)` or use engine-specific:
    - Mix changes: `evaluate_mix_move`
    - Composition changes: `evaluate_composition_move`
    - Multi-dimensional: `evaluate_with_fabric`

11. **Report results** — show: score (0-1), keep_change recommendation, goal_progress, collateral_damage, dimension changes

12. **Act on recommendation:**
    - If `keep_change=true` — keep, suggest `memory_learn` if score > 0.7
    - If `keep_change=false` — `undo()`, explain why (collateral damage, goal regression)

Use the livepilot-evaluation skill for the full evaluation loop details.

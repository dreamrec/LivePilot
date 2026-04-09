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

2. **Get the last move** — `get_last_move` to understand what was changed. If no recent move, `get_recent_actions` for history.

3. **Ask what the goal was** — what were they trying to achieve? More clarity? Wider stereo? Punchier drums?

4. **Compile the goal** — `compile_goal_vector(goal_description, mode="improve")`

5. **Capture current state** — `get_master_spectrum` + `get_master_rms` + `get_mix_snapshot`

6. **Undo the change** — `undo()` to restore the before state

7. **Capture before state** — same reads as step 5

8. **Redo the change** — `redo()` to restore the after state

9. **Evaluate** — `evaluate_move(before_snapshot, after_snapshot, goal)` or use engine-specific:
   - Mix changes: `evaluate_mix_move`
   - Composition changes: `evaluate_composition_move`
   - Multi-dimensional: `evaluate_with_fabric`

10. **Report results** — show: score (0-1), keep_change recommendation, goal_progress, collateral_damage, dimension changes

11. **Act on recommendation:**
    - If `keep_change=true` — keep, suggest `memory_learn` if score > 0.7
    - If `keep_change=false` — `undo()`, explain why (collateral damage, goal regression)

Use the livepilot-evaluation skill for the full evaluation loop details.

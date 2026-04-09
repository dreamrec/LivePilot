---
name: mix
description: Mixing assistant — analyze and balance track levels, panning, and sends
---

Help the user mix their session using the V2 orchestration pipeline.

## Orchestration Flow

1. **Session kernel** — `get_session_kernel(request_text=<user's request>, mode="improve")` for the full turn snapshot
2. **Route** — `route_request(<user's request>)` to get engine routes + semantic move recommendations
3. **Ensure analyzer** — if `get_master_spectrum` errors, load it: `find_and_load_device(track_index=-1000, device_name="LivePilot_Analyzer")`. If bridge disconnected, try `reconnect_bridge`.

## Analysis Phase

4. **Quick status** — `get_mix_summary` for track count, dynamics, stereo, issues
5. **Run critics** — `get_mix_issues` for problems. `get_masking_report` for frequency collisions.
6. **Spectral check** — `get_master_spectrum` for 8-band balance. Genre targets:
   - Hip-hop: sub dominant, centroid 400-800 Hz
   - Electronic: balanced, centroid 800-1500 Hz
   - Ambient: mid-focused, low sub, centroid 500-1000 Hz
7. **Musical intelligence** — `detect_role_conflicts` to find tracks competing for the same space. `detect_repetition_fatigue` if arrangement feels stale.

## Decision Phase

8. **Propose semantic moves** — `propose_next_best_move(request_text=<user's request>)` for ranked suggestions (e.g., `make_punchier`, `widen_stereo`, `tighten_low_end`)
9. **Preview chosen move** — `preview_semantic_move(move_id)` to see the full compile plan before executing
10. **Rank by taste** — if user has history, `rank_moves_by_taste(move_specs)` to personalize ordering

## Execution Phase

11. **Apply with approval** — `apply_semantic_move(move_id, mode="improve")` returns the compiled plan. Present it to the user: "I'd suggest: push Drums to 0.75, pull Pad to 0.25. Shall I do it?"
12. **Verify after EVERY change** — read `value_string` in response, call `get_track_meters(include_stereo=true)`, check no track went silent
13. **Capture + analyze** — `capture_audio` then `analyze_loudness` for LUFS/LRA, `analyze_spectrum_offline` for centroid/balance
14. **Evaluate** — `evaluate_mix_move` with before/after snapshots. If `keep_change` is false, `undo` immediately.

## Summary

15. **Report** — "What I did / what improved / what I protected / what remains"
16. **Session memory** — `add_session_memory` for notable decisions
17. **Taste update** — successful moves update the TasteGraph automatically

For deeper critic-driven iterative improvement, use the livepilot-mix-engine skill.
For exploratory mode (try multiple ideas), use `create_experiment` + `run_experiment` + `compare_experiments`.

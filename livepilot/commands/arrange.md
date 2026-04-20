---
name: arrange
description: Guided arrangement — build song structure with sections, transitions, and energy flow
---

Guide the user through arranging their session using the V2 orchestration pipeline.

## Orchestration Flow

1. **Session kernel** — `get_session_kernel(request_text=<user's request>, mode="improve")`
2. **Route** — `route_request(<user's request>)` for engine routes + semantic moves

## Analysis Phase

3. **Scene matrix** — `get_scene_matrix` for the full clip grid
4. **Section purposes** — `infer_section_purposes` to understand what each scene is doing
5. **Emotional arc** — `score_emotional_arc` — does the song have build → climax → resolve?
6. **Repetition check** — `detect_repetition_fatigue` — are patterns overused?
7. **Motif analysis** — `get_motif_graph` for recurring patterns and fatigue risk
8. **Role conflicts** — `detect_role_conflicts` to find competing tracks

## Planning Phase

9. **Ask about target** — what form? (verse-chorus, build-drop, through-composed). What energy arc?
10. **Plan arrangement** — `plan_arrangement(target_bars, style)` for section blueprint
11. **Propose moves** — `propose_next_best_move(request_text)` for arrangement semantic moves (e.g., `create_buildup_tension`, `smooth_scene_handoff`)
12. **Preview** — `preview_semantic_move(move_id)` to see the gesture plan

## Execution Phase

13. **Build sections** — duplicate scenes, set names/colors, use `transform_motif` for melodic development
14. **Apply gestures** — `apply_gesture_template` for transitions:
    - `pre_arrival_vacuum` — energy suck before drops
    - `harmonic_tint_rise` — filter opening for intros
    - `re_entry_spotlight` — highlight returning elements
    - `tension_ratchet` — stepped energy build
    - `outro_decay_dissolve` — gradual dissolution
15. **Add organic movement** — `apply_automation_shape(curve_type="perlin")` on filters/sends
16. **Verify arc** — `score_emotional_arc` again to confirm improvement
17. **Perception check** — `capture_audio` + `analyze_loudness` to verify LRA > 2 LU

## Summary

18. **Report** — "What I did / what improved / what I protected / what remains"
19. **Session memory** — `add_session_memory` for arrangement decisions

For exploratory arrangement, use the branch-native experiment path (see livepilot-core SKILL.md, Flow B). Each section-ordering variant becomes one `composer`-source seed; attach pre-compiled plans via `compiled_plans`. When the user's request is vague or exploratory ("what would you do?", "surprise me with a structure"), bias `get_session_kernel(freshness=0.7-0.9)` to surface less-conservative branches.

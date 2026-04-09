---
name: arrange
description: Guided arrangement — build song structure with sections, transitions, and energy flow
---

Guide the user through arranging their session into a full song structure.

1. **Read the session** — `get_session_info` to see all tracks and clips
2. **Analyze current structure** — `get_section_graph` to see inferred sections from scene names. If no sections, `get_scenes_info` for raw scene data.
3. **Ask about the target structure** — what form? (verse-chorus, AABA, build-drop, through-composed). What energy arc? (gradual build, peaks and valleys, flat)
4. **Plan the arrangement** — `plan_arrangement` with the target structure. Review the proposed section order and transitions.
5. **Build sections** — for each section, create or duplicate scenes, set scene names and colors. Use `duplicate_scene` for variations.
6. **Check transitions** — `analyze_transition(from_section, to_section)` for each adjacent pair. `score_transition` to evaluate quality.
7. **Plan weak transitions** — `plan_transition` for any scored below 0.6. Execute the suggested gestures (filter sweeps, energy ramps, rhythmic fills).
8. **Check emotional arc** — `get_emotional_arc` to verify the energy flow matches the target.
9. **Translation check** — `check_translation` to verify mono compatibility and spectral consistency across sections.
10. **Record to arrangement** — when the user is happy, guide them through `back_to_arranger` and recording the session performance to the timeline.

Use the livepilot-composition-engine skill for section analysis and transition planning. Present the arrangement as a visual timeline to the user.

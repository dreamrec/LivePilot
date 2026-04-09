---
name: arrange
description: Guided arrangement — build song structure with sections, transitions, and energy flow
---

Guide the user through arranging their session into a full song structure.

1. **Read the session** — `get_session_info` to see all tracks and clips. `get_scene_matrix` for the full clip grid.
2. **Analyze current structure** — `get_section_graph` to see inferred sections from scene names. `get_emotional_arc` to understand current energy flow.
3. **Detect motifs** — `get_motif_graph` to find recurring patterns, fatigue risk, and suggested developments (inversion, augmentation, fragmentation).
4. **Ask about the target structure** — what form? (verse-chorus, AABA, build-drop, through-composed). What energy arc? (gradual build, peaks and valleys, flat)
5. **Plan the arrangement** — `plan_arrangement` with the target bar count and style. Review the proposed section order, transitions, and gesture templates.
6. **Build sections** — for each section, create or duplicate scenes, set scene names and colors. Use `duplicate_scene` for variations. Use `transform_motif` for melodic development (inversion, retrograde, diminution, augmentation).
7. **Apply gesture templates** — for each transition, use `apply_gesture_template` with the planned template:
   - `pre_arrival_vacuum` — pull energy back before a drop
   - `harmonic_tint_rise` — gradually open filters for intro/build sections
   - `re_entry_spotlight` — darken then snap back to highlight returning elements
   - `tension_ratchet` — stepped build in 4-bar stages
   - `outro_decay_dissolve` — gradual dissolution for endings
   - `phrase_end_throw` — reverb/delay throw at section boundaries
   Then execute each gesture plan using `apply_automation_shape` with the suggested curve_family.
8. **Add organic movement** — use `apply_automation_shape` with `curve_type="perlin"` on filter/send/effect parameters so nothing repeats exactly the same each cycle.
9. **Check emotional arc** — `get_emotional_arc` to verify the energy flow matches the target. Address any issues flagged (no_clear_build, peak_too_early, no_resolution).
10. **Verify with perception** — `get_master_spectrum` during each section to confirm spectral differentiation. `capture_audio` + `analyze_loudness` to check LRA (should be >2 LU for dynamic arrangements).
11. **Translation check** — `check_translation` to verify mono compatibility and spectral consistency across sections.
12. **Record to arrangement** — when satisfied, use `create_arrangement_clip` to lay out clips on the timeline, or guide the user through `back_to_arranger` and recording the session performance.

Use the livepilot-composition-engine skill for section analysis and transition planning. Present the arrangement as a visual timeline to the user.

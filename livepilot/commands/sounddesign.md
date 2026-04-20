---
name: sounddesign
description: Sound design workflow — load instruments and effects, shape parameters for a target sound
---

Guide the user through designing a sound using the V2 orchestration pipeline.

## Orchestration Flow

1. **Session kernel** — `get_session_kernel(request_text=<user's request>, mode="improve")`
2. **Route** — `route_request(<user's request>)` for engine routes + semantic moves

## Design Phase

3. **Ask about target** — what character? (warm pad, aggressive bass, shimmering lead, etc.)
4. **Choose instrument** — `search_browser` to find devices, `load_browser_item` to load
5. **Verify health** — `get_device_info` to confirm plugin initialized. Read `value_string` from `get_device_parameters` to understand actual units.
6. **Shape sound** — `set_device_parameter` or `batch_set_parameters`. **ALWAYS read `value_string` in response** to confirm Hz/dB/% values make sense.
7. **Verify after every change** — `get_track_meters(include_stereo=true)` — if stereo drops to 0, the effect killed the signal.

## Critic Phase

8. **Run critics** — `analyze_sound_design(track_index)` for static timbre, missing modulation, spectral imbalance
9. **Plan improvements** — `plan_sound_design_move(track_index)` for suggested changes
10. **Patch model** — `get_patch_model(track_index)` to see chain structure and controllable blocks

## Effects & Automation

11. **Add effects** — load with `find_and_load_device(track_index, device_name)`. Verify health.
12. **Organic movement** — `apply_automation_shape(curve_type="perlin")` for filter/send drift
13. **Automation recipes** — `apply_automation_recipe` for breathing, vinyl_crackle, auto_pan. Verify after applying.

## Evaluation

14. **Perception check** — `get_master_spectrum` or `capture_audio` + `analyze_spectrum_offline`
15. **Evaluate** — `evaluate_move(goal_vector, before_snapshot, after_snapshot)` to score improvement

## Summary

16. **Report** — "What I changed / what improved / what I protected"
17. **Memory** — if score > 0.7, suggest `memory_learn` to save the technique

For critic-driven iterative refinement, use the livepilot-sound-design-engine skill.

## Branch-Native Exploratory Mode

For open-ended sound design ("design me something that feels like X", "make this more interesting", "surprise me"), use Flow B from livepilot-core SKILL.md. Prefer `source="synthesis"` seeds for any request that calls for genuinely different timbres — PR9+ introduces native-synth adapters (Wavetable, Operator, Analog, Drift, Meld) that can propose per-device parameter branches. Pass `synth_hints` on `get_session_kernel` when you know which tracks or devices to focus on:

```
get_session_kernel(
    request_text="make the pad more alive",
    freshness=0.75,
    creativity_profile="sculptor",
    synth_hints={"track_indices": [pad_track_idx], "preferred_devices": ["Wavetable", "Operator"]},
)
```

Seeds with `source="synthesis"` that arrive without a compiled plan will (post-PR9) be compiled by the synthesis_brain; pre-PR9 they must ship with a freeform plan attached via `compiled_plans`.

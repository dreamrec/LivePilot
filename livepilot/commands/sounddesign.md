---
name: sounddesign
description: Sound design workflow — load instruments and effects, shape parameters for a target sound
---

Guide the user through designing a sound. Follow these steps:

1. **Ask about the target sound** — what character? (warm pad, aggressive bass, shimmering lead, atmospheric texture, etc.)
2. **Choose an instrument** — pick the right synth for the job, load it with `search_browser` → `load_browser_item`
3. **Verify device loaded** — `get_device_info` to confirm plugin initialized (AU/VST with `parameter_count` <= 1 = dead plugin — delete and replace with native alternative)
4. **Get parameters** — `get_device_parameters` to see what's available. **Read `value_string`** to understand actual units (Hz, dB, %, ms) — raw values are often NOT in human units.
5. **Shape the sound** — `set_device_parameter` or `batch_set_parameters` to dial in the character
   - **ALWAYS read `value_string` in the response** to confirm the actual value makes sense
   - **ALWAYS call `get_track_meters(include_stereo=true)` after filter/effect changes** — verify the track still produces audio
   - If stereo output drops to 0, the effect is killing the signal. Check `value_string`, fix, re-verify.
6. **Run critics** — `analyze_sound_design(track_index)` to check for static timbre, missing modulation, spectral imbalance
7. **Address issues** — `plan_sound_design_move(track_index)` for suggested improvements, `get_patch_model` to see chain structure
8. **Add effects** — load effects and tweak. For automation, use `apply_automation_shape` with musically appropriate curve types:
   - Filter sweeps → exponential (perceptually even)
   - Volume fades → logarithmic (matches ear's response)
   - Organic movement → perlin (never repeats exactly)
   - If using `apply_automation_recipe`, verify the recipe didn't push parameters to extremes
9. **Create a test pattern** — `create_clip` + `add_notes` with a simple pattern to audition
10. **Fire the clip** to listen, iterate based on feedback
11. **Perception check** — `get_master_spectrum` or `capture_audio` + `analyze_spectrum_offline` to verify the sound sits correctly in the frequency spectrum
12. **Evaluate** — `evaluate_move` with before/after snapshots to verify improvement

Explain what each parameter does as you adjust it. Use `undo` liberally if something sounds wrong.

For iterative critic-driven patch refinement, use the livepilot-sound-design-engine skill.

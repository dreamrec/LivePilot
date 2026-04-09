---
name: sounddesign
description: Sound design workflow — load instruments and effects, shape parameters for a target sound
---

Guide the user through designing a sound. Follow these steps:

1. **Ask about the target sound** — what character? (warm pad, aggressive bass, shimmering lead, atmospheric texture, etc.)
2. **Choose an instrument** — pick the right synth for the job, load it with `search_browser` → `load_browser_item`
3. **Verify device loaded** — `get_device_info` to confirm plugin initialized (AU/VST with `parameter_count` <= 1 = dead plugin — delete and replace with native alternative)
4. **Get parameters** — `get_device_parameters` to see what's available
5. **Shape the sound** — `set_device_parameter` or `batch_set_parameters` to dial in the character
6. **Run critics** — `analyze_sound_design(track_index)` to check for static timbre, missing modulation, spectral imbalance
7. **Address issues** — `plan_sound_design_move(track_index)` for suggested improvements
8. **Add effects** — load effects (reverb, delay, chorus, distortion, etc.) and tweak their parameters
9. **Create a test pattern** — `create_clip` + `add_notes` with a simple pattern to audition
10. **Fire the clip** to listen, iterate based on feedback
11. **Evaluate** — `evaluate_move(engine="sound_design")` with before/after to verify improvement

Explain what each parameter does as you adjust it. Use `undo` liberally if something sounds wrong.

For iterative critic-driven patch refinement, use the livepilot-sound-design-engine skill.

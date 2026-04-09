---
name: livepilot-sound-design-engine
description: This skill should be used when the user asks to "design a sound", "analyze a patch", "fix a static sound", "add modulation", "check my timbre", "improve a synth patch", or wants critic-driven sound design feedback and iterative patch refinement.
---

# Sound Design Engine — Critic-Driven Patch Refinement

The sound design engine analyzes synth patches, identifies timbral weaknesses, and iteratively refines them through a measured critic loop. Every change is evaluated against the before state.

## The Sound Design Critic Loop

### Step 1 — Build Patch Model

Call `get_patch_model(track_index)` to build a PatchModel for the target track. The PatchModel maps every device on the track into typed blocks (oscillator, filter, envelope, lfo, saturation, spatial, effect) and classifies each as `controllable` or `opaque`.

Read the response carefully:
- `blocks`: ordered list of processing blocks with types and parameter names
- `controllable_params`: parameters you can modify via `set_device_parameter`
- `opaque_blocks`: third-party plugins where parameters may not map cleanly
- `modulation_sources`: detected LFOs, envelopes, and macro mappings
- `signal_flow`: how blocks connect (serial, parallel, or rack chains)

See `references/patch-model.md` for the full PatchModel structure and native device block map.

### Step 2 — Analyze

Call `analyze_sound_design(track_index)` to run all sound design critics against the patch. The response contains an `issues` array with `critic`, `severity`, `block`, and `evidence`.

Five critics run during analysis. See `references/sound-design-critics.md` for thresholds:

- **static_timbre** — sound does not evolve over time, no movement
- **no_modulation_sources** — no LFOs, envelopes, or automation detected
- **modulation_flatness** — modulation exists but ranges are too narrow to hear
- **missing_filter** — raw oscillator output with no spectral shaping
- **spectral_imbalance** — too much energy in one frequency region, or gaps

### Step 3 — Plan

Pick the highest-severity issue. Call `plan_sound_design_move(track_index)` with the issue. The planner returns a single intervention:

- `move_type`: one of the move vocabulary entries
- `target_device`: device index on the track
- `target_parameter`: parameter name or index
- `target_value`: the new value
- `rationale`: why this move addresses the issue

Move vocabulary:
- **modulation_injection** — add or increase LFO/envelope depth on a parameter
- **filter_shaping** — adjust cutoff, resonance, or filter type
- **parameter_automation** — create clip automation for time-varying timbral change
- **oscillator_tuning** — adjust pitch, detune, waveform, or unison settings

### Step 4 — Capture Before

1. Call `get_device_parameters(track_index, device_index)` — save current parameter state
2. Call `get_master_spectrum` — save spectral snapshot (if analyzer available)

### Step 5 — Execute

Apply the planned move using the appropriate tool:

- `set_device_parameter` for direct parameter changes (filter cutoff, LFO rate, oscillator shape)
- `toggle_device` for enabling/disabling processing blocks
- `batch_set_parameters` when the move requires coordinated changes (e.g., LFO depth + rate together)
- `set_clip_automation` for parameter automation moves
- `find_and_load_device` when the fix requires adding a new device (e.g., adding an Auto Filter)

Execute one move at a time. Verify before continuing.

### Step 6 — Capture After

Repeat the same measurements:

1. Call `get_device_parameters(track_index, device_index)` — confirm the change took effect
2. Call `get_master_spectrum` — save post-change spectral snapshot

### Step 7 — Evaluate

Call `evaluate_move(goal_vector, before_snapshot, after_snapshot)` where `goal_vector` is the compiled goal from Step 1 and snapshots contain `{spectrum: {...}, rms: float, peak: float}`. Read:

- `keep_change` (bool): whether the change improved the sound
- `score` (0.0-1.0): quality improvement magnitude
- `timbral_delta`: what changed spectrally
- `explanation`: human-readable summary

### Step 8 — Keep or Undo

If `keep_change` is `false`, call `undo()`. Explain what was tried and why it did not improve the sound.

If `keep_change` is `true`, report the improvement. If score > 0.7, consider calling `memory_learn(type="sound_design")` to save the technique.

### Step 9 — Repeat

Return to Step 2. Re-analyze after each kept change. The critic list updates as issues are resolved. Continue until the user is satisfied or no high-severity issues remain.

## Working with Opaque Plugins

Third-party AU/VST plugins may report as `opaque` in the PatchModel:

1. Check `get_plugin_parameters(track_index, device_index)` — some plugins expose parameters through the host
2. If `parameter_count <= 1`, the plugin is dead or unresponsive. Call `delete_device` and suggest a native alternative
3. If parameters are available but unnamed (Parameter 1, Parameter 2...), try `map_plugin_parameter` to identify them by ear
4. Report opaque status to the user — sound design critics cannot fully analyze what they cannot inspect

## Quick Sound Design Checks

- **"What's wrong with this sound?"** — Call `get_sound_design_issues(track_index)` for a diagnostic without executing fixes
- **"Show me the patch"** — Call `get_patch_model(track_index)` then `walk_device_tree(track_index)` for full device chain visibility
- **"What can I automate?"** — Read the `controllable_params` list from the PatchModel response

## Native Device Strengths

When adding processing blocks, prefer native Ableton devices for controllability:

- **Wavetable** — complex oscillator section with built-in modulation matrix
- **Operator** — FM synthesis with per-operator envelopes and LFO
- **Analog** — subtractive with two filters and two LFOs
- **Auto Filter** — standalone filter with envelope follower and LFO
- **Corpus** — resonant body modeling for physical character
- **Erosion** — high-frequency noise and distortion artifacts
- **Saturator** — waveshaping with multiple curve types

Always `search_browser` before loading — never guess device names.

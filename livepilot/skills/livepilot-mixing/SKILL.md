---
name: livepilot-mixing
description: This skill should be used when the user asks to "mix", "balance levels", "set volume", "pan a track", "EQ", "compress", "sends", "routing", "master volume", "gain staging", "sidechain", or wants to perform mixing operations in Ableton Live.
---

# Mixing — Levels, Panning, Routing, and Analysis

Balance track levels, configure routing, apply mix effects, and analyze frequency content in Ableton Live.

## Read Before Write

Always understand the current state before changing anything:

1. `get_session_info` — see all tracks, their types, and current configuration
2. `get_track_info(track_index)` — detailed info on a single track: devices, clips, mixer state
3. `get_mix_snapshot` — one-call overview of all levels, panning, routing, mute/solo state across the entire session
4. `get_device_parameters(track_index, device_index)` — read current parameter values before tweaking

Never set levels blindly. Read the current state, make informed adjustments, then verify the result.

## Volume and Pan

- `set_track_volume(track_index, value)` — value is normalized 0.0 to 1.0 (not dB). 0.85 is roughly unity gain. 0.0 is silence, 1.0 is max.
- `set_track_pan(track_index, value)` — value is -1.0 (hard left) to 1.0 (hard right). 0.0 is center.
- `set_master_volume(value)` — master output level, same 0.0-1.0 range.

Gain staging principle: keep individual tracks at moderate levels (0.5-0.85) and use the master for final output. Avoid pushing tracks to 1.0 — it leaves no headroom for summing.

## Sends and Return Tracks

Sends route signal from any track to a return track for shared processing (reverb bus, delay bus, parallel compression).

- `set_track_send(track_index, send_index, value)` — set send level (0.0-1.0). Send index 0 = Send A, 1 = Send B, etc.
- `get_return_tracks` — list all return tracks with their names, devices, and routing
- `create_return_track` — add a new return track to the session
- `get_master_track` — inspect the master track configuration

Return track workflow:
1. `create_return_track` — creates a new return (automatically assigned next letter: A, B, C...)
2. Load an effect on the return track (e.g., Reverb with Dry/Wet at 100%)
3. `set_track_send(track_index, send_index, value)` on each track that needs the effect
4. Adjust send levels per track for different amounts of the shared effect

## Routing

- `get_track_routing(track_index)` — see current input/output routing for a track
- `set_track_routing(track_index, input_routing, output_routing)` — configure where audio comes from and goes to

Common routing patterns:
- **Resampling:** set input routing to "Resampling" on an audio track to capture the master output
- **Sidechain:** route a track's output to another track's sidechain input for ducking compression
- **Sub-groups:** route multiple tracks to a group track for bus processing

## Metering

- `get_track_meters(track_index)` — read real-time output level of a specific track (left/right channels)
- `get_master_meters` — read the master output level in real-time

Use metering to verify your level adjustments. After setting volumes, check meters to confirm nothing is clipping and the balance sounds right.

## Mix Snapshot

`get_mix_snapshot` returns a complete picture of the session mix in one call:
- All track volumes and pan positions
- Mute and solo states
- Send levels
- Routing configuration
- Return track setup

Use this as your starting point for any mixing task. It shows the full picture without needing to query each track individually.

## Automation

### Clip Automation

- `get_clip_automation(track_index, clip_index, parameter_name)` — read existing automation for a parameter
- `set_clip_automation(track_index, clip_index, parameter_name, points)` — write automation points as `[{time, value}, ...]`
- `clear_clip_automation(track_index, clip_index, parameter_name)` — remove automation before rewriting

### Intelligent Curves

- `generate_automation_curve(shape, start_value, end_value, num_points)` — generate automation points using 16 curve types: linear, exponential, logarithmic, sine, cosine, s_curve, ease_in, ease_out, bounce, random_walk, step, triangle, sawtooth, reverse_sawtooth, pulse, and smooth_random
- `apply_automation_shape(track_index, clip_index, parameter_name, shape, start_value, end_value)` — generate and apply a curve in one call

### Recipes

`apply_automation_recipe(track_index, clip_index, recipe_name)` — apply a pre-built automation pattern. Available recipes:

- `filter_sweep_up` — low-pass filter opens over time, classic build
- `filter_sweep_down` — filter closes, darkening effect
- `sidechain_pump` — rhythmic volume ducking on each beat
- `dub_throw` — delay feedback spikes on specific beats
- `tremolo` — rhythmic volume oscillation
- `autopan` — stereo movement back and forth
- `fade_in` / `fade_out` — gradual volume transitions
- `stutter` — rapid volume gates for glitch effects
- `vinyl_crackle` — subtle noise modulation
- `tape_wow` — pitch/speed micro-variations
- `bit_crush_sweep` — sample rate reduction over time
- `resonance_peak` — filter resonance spike for emphasis
- `stereo_width_grow` — mono to wide stereo expansion
- `grain_scatter` — granular parameter randomization

### Automation Feedback Loop

Follow this cycle for all automation work:

1. **Perceive:** `get_master_spectrum` + `get_track_meters` to understand current state
2. **Diagnose:** identify what needs to change based on spectral data
3. **Act:** `apply_automation_shape` or `apply_automation_recipe`
4. **Verify:** `get_master_spectrum` again to confirm the change worked
5. **Adjust:** if not right, `clear_clip_automation` and try different parameters

Never write automation without reading spectrum before and after.

## Spectrum Analysis (Requires M4L Bridge)

When the LivePilot Analyzer M4L device is on the master track:

- `get_master_spectrum` — 9-band frequency analysis: sub_low (20-60 Hz), sub (60-120 Hz), low (120-250 Hz), low_mid (250-500 Hz), mid (500-1k Hz), high_mid (1-2k Hz), high (2-4k Hz), presence (4-8k Hz), air (8-20k Hz)
- `get_master_rms` — true RMS and peak levels for loudness assessment
- `get_detected_key` — detect musical key from audio content

Use spectrum data to make informed EQ decisions. If the low_mid band is 6 dB hotter than everything else, there is mud to clean up. If the air band is absent, the mix may sound dull.

## Mix Engine — Critic-Driven Analysis

For deeper mix analysis beyond basic levels and spectrum:

- `analyze_mix` — full spectral mix analysis with per-track breakdown
- `get_mix_issues` — identify specific problems (masking, imbalance, phase)
- `plan_mix_move` — get a suggested action to fix a detected issue
- `evaluate_mix_move` — score a proposed change before applying it
- `get_masking_report` — detect frequency masking between tracks
- `get_mix_summary` — quick overall mix health status

Use the mix engine when the user wants a critical evaluation of their mix, not just level adjustments. Start with `get_mix_summary` for a quick overview, escalate to `analyze_mix` for full detail.

## Quick Mix Status

`get_mix_summary` from the mix engine provides an overall health score, top issues, and priority recommendations in a single call. Use it as a fast check before diving into detailed analysis.

## Escalation Ladder

Follow this progression — start fast, go deeper only when needed:

1. **Instant:** `get_master_spectrum` + `get_track_meters` — frequency balance + levels. Answers 80% of mix questions.
2. **Fast (1-5s):** `analyze_loudness` + `analyze_mix` — LUFS, true peak, and full mix analysis. For mastering prep.
3. **Slow (5-15s):** `compare_to_reference` + `analyze_spectrum_offline` — reference matching, offline spectral analysis. Ask the user first.

Never skip levels. Start at the lowest appropriate level and offer to go deeper.

## Reference

Supporting references live in the `livepilot-core` skill's `references/` directory:
- `livepilot-core/references/mixing-patterns.md` — gain staging, parallel compression, sidechain, EQ by instrument, bus processing, stereo width
- `livepilot-core/references/automation-atlas.md` — curve theory, genre-specific recipes, diagnostic filter, cross-track spectral mapping

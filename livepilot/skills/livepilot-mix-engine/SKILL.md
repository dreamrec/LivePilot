---
name: livepilot-mix-engine
description: This skill should be used when the user asks to "analyze my mix", "find mix issues", "fix masking", "check frequency clashes", "improve dynamics", "check stereo width", "check headroom", or wants critic-driven mix analysis and evaluation. Provides the mix critic loop for iterative mix improvement.
---

# Mix Engine — Critic-Driven Mix Improvement

The mix engine runs an iterative critic loop: analyze, plan, execute, measure, evaluate, keep or undo. Every mix change is measured before and after. Nothing stays unless it scores better than the original.

## The Mix Critic Loop

Follow these steps in order. Do not skip the evaluation step.

### Step 1 — Analyze

Call `analyze_mix` or `get_mix_issues` to build a MixState and run all critics against the current session. The response contains an `issues` array, each with a `critic`, `severity`, `track_index`, and `evidence` dict.

If the M4L analyzer bridge is absent, critics fall back to role-based heuristics only (track names, device chains, volume/pan positions). Inform the user that spectral analysis is unavailable and recommendations are less precise.

For detailed frequency collision data, call `get_masking_report`. For a quick status overview without the full critic pass, call `get_mix_summary`.

### Step 2 — Plan

Pick the highest-severity issue from the `issues` array. Call `plan_mix_move` with the issue data. The planner returns the smallest intervention that addresses the problem — a single parameter change, not a chain of edits.

Read the `move` object: it contains `move_type`, `target_track`, `target_device`, `target_parameter`, `target_value`, and `rationale`. Consult the move vocabulary in `references/mix-moves.md` for parameter ranges.

### Step 3 — Capture Before

Take a measurement snapshot before executing anything:

1. Call `get_master_spectrum` — save the 8-band spectral data
2. Call `get_master_rms` — save the RMS and peak values

Optionally call `get_mix_snapshot` if you need per-track volume/pan/send state for the evaluation.

### Step 4 — Execute

Execute the planned move. Use the appropriate tool for the move type:

- `set_device_parameter` for EQ cuts/boosts, compressor thresholds, saturation drives
- `set_track_volume` for gain staging
- `set_track_pan` for stereo placement
- `set_track_send` for bus routing levels
- `toggle_device` for bypassing/enabling processors
- `batch_set_parameters` when the move requires multiple related parameter changes on the same device

Execute exactly one move. Do not chain multiple interventions before measuring.

### Step 5 — Capture After

Repeat the same measurements from Step 3:

1. Call `get_master_spectrum` — save the post-change spectral data
2. Call `get_master_rms` — save the post-change RMS and peak values

### Step 6 — Evaluate

Call `evaluate_mix_move` with the before and after snapshots:

```
evaluate_mix_move(
  before_snapshot: { spectrum: [...], rms: float, peak: float },
  after_snapshot:  { spectrum: [...], rms: float, peak: float },
  targets: { ... },     # what the move aimed to improve
  protect: { ... }      # what must not get worse
)
```

Read the response: `keep_change` (bool), `score` (0.0-1.0), `improvements` (list), `regressions` (list), `explanation` (string).

### Step 7 — Keep or Undo

If `keep_change` is `false`, call `undo()` immediately. Tell the user what was tried and why it was reverted, citing the `regressions` list.

If `keep_change` is `true`, report the improvement to the user with the score and explanation.

### Step 8 — Learn (Optional)

If the move scored above 0.7 and the user confirms satisfaction, call `memory_learn(name="...", type="mix_template", qualities={"summary": "..."}, payload={...})` to save the technique for future recall.

### Step 9 — Repeat

Return to Step 1 and re-analyze. The critic list updates after each change. Continue until no high-severity issues remain or the user says to stop.

## Quick Mix Checks

Not every request needs the full loop:

- **"How's my mix?"** — Call `get_mix_summary` for a one-shot status report with no changes
- **"What's clashing?"** — Call `get_masking_report` for detailed per-pair frequency collision data
- **"What are the issues?"** — Call `get_mix_issues` for the critic list without executing any fixes

## Critic Types

Six critics run during analysis. See `references/mix-critics.md` for thresholds and evidence format:

- **masking** — frequency collisions between overlapping tracks
- **over_compressed** — excessive compression reducing dynamic range
- **flat_dynamics** — insufficient volume variation across sections
- **low_headroom** — master peak too close to 0 dBFS
- **stereo_width** — mono collapse or excessive width on specific elements
- **spectral_balance** — overall tonal balance skew (too bright, too dark, mid-heavy)

## Move Vocabulary

The planner draws from six move types. See `references/mix-moves.md` for parameter ranges:

- **gain_staging** — volume adjustments to establish proper level hierarchy
- **bus_compression** — glue compression on groups or master
- **transient_shaping** — attack/sustain manipulation for punch or smoothness
- **eq_cut** — subtractive EQ to clear masking or remove resonances
- **eq_boost** — additive EQ to bring out character (use sparingly)
- **pan_spread** — stereo placement adjustments for width and separation

## Analyzer Dependency

The mix engine works in two modes:

- **Full mode** (M4L analyzer connected): spectral data, RMS, key detection available. Critics use measured evidence.
- **Heuristic mode** (no analyzer): critics infer from track names, device chains, and parameter positions. Always inform the user: "Spectral analysis unavailable — recommendations are based on track structure and device settings only."

Call `get_capability_state` to check which mode is active before starting the loop.

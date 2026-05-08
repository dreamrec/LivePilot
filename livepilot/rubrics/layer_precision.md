# §5 — Layer-by-Layer Precision

Wraps the seven `audit/checks.py` functions into one rubric. Each criterion
runs the relevant audit check across every track and aggregates per-track
results into a single criterion verdict (worst-case severity).

CLAUDE.md §5: "For EVERY layer (drums, bass, lead, pad, vox, perc): solo +
spectrum check tone, critique sequence (swing/humanization/ghosts/per-bar
variation/micro-timing), check stereo image, plan automation/pitch-bends/
filter sweeps. Same depth as the 2026-04-25 hi-hat critique. No layer is
'done' without this checklist."

This rubric is the most data-hungry of the set. Each criterion degrades to
n/a gracefully when the corresponding signal is missing on every track.

## Criteria

### `timbre_per_track` (§5.1)
Calls `audit_checks.check_timbre(role, fingerprint)`. Requires per-track
`fingerprint` (from `get_master_spectrum` after solo).

- All tracks pass → **pass**
- Any track has wrong-band dominance → **fail** (sample is wrong for role)
- Off-band but secondary in expected range → **warn**

### `sequence_per_track` (§5.2)
Calls `audit_checks.check_sequence(role, notes_per_clip)`. Requires per-track
`notes_per_clip` (from `get_notes` per clip slot).

- Drum-role tracks need humanization + ghost notes
- Pad/lead/bass need pitch + duration variation
- Audio tracks → n/a (no notes)

### `stereo_per_track` (§5.3)
Calls `audit_checks.check_stereo(role, track)`. Pure pan-position check.

- Bass panned > 0.05 → **warn** (sub should be center for translation)
- Kick/snare panned > 0.15 → **warn**

### `masking_per_track` (§5.4)
Calls `audit_checks.check_masking(track_index, masking_report)`. Requires
session-level `masking_report` from `get_masking_report`.

- Any high-severity collision → **fail**
- Mid-severity collision → **warn**
- No `masking_report` provided → criterion **n/a** (whole rubric still runs)

### `modulation_per_track` (§5.5 + §4)
Calls `audit_checks.check_modulation(role, devices, has_clip_automation,
wavetable_mod_routings)`. More accurate than the standalone
`modulation_presence` rubric — analyzes parameter routings (`Fe < Env`,
`Pe < Env`, etc.) on the actual instrument.

### `params_per_track` (§5.6 + §2)
Calls `audit_checks.check_params(role, devices)`. Detects "unprogrammed"
instruments — pad/lead/bass with ≥3 key shaping parameters at default values.
Drum roles auto-pass (single-sample minimal-shaping is correct by design).

### `effects_per_track` (§5.8)
Calls `audit_checks.check_effects(role, devices)`. Verifies role-appropriate
effect chain coverage:
- kick / snare / bass / vox / lead → EQ required
- bass / vox / lead → compressor required
- pad / atmos / vox / lead → reverb or delay required

## Aggregation

Per criterion: worst severity wins. If any track fails → criterion fails.
Otherwise if any warns → warns. Otherwise pass. Tracks where the audit
returns n/a (data missing, role doesn't apply) are filtered before
aggregation — they don't drag the criterion to n/a unless every track is n/a.

Whole-rubric `passed` is False iff any criterion is fail (blocking).

## What this rubric does NOT cover

- Sample audition (§5.7) — slice classification — niche, separate rubric later
- Aesthetic register (§8) — taste, never rubric-graded
- Per-track meter levels — that's the §7.3 `layer_accumulation` rubric

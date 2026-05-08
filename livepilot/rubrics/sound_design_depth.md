# §2 — Sound Design = Instrument Programming

Single-criterion rubric isolating the §5.6 instrument-parameter check from
the full layer-precision rubric. Runnable on its own when the agent claims
"I added sound design" but actually only added effects.

CLAUDE.md §2: "Sound design = instrument parameter programming, NOT effects
chains. Adding Saturator/Redux/Shifter is EFFECT DESIGN, not sound design.
Real sound design sculpts the source at the instrument/sampler level
(envelopes, LFO routing, filter envelope, pitch modulation, sample start
mod, spread, detune)."

## Criterion

### `params_per_track`
Calls `audit_checks.check_params(role, devices)`. Detection:
- Inspects the first native-instrument device on each track
- Looks at parameter values for `Fe < Env`, `Pe < Env`, `Spread`, `Detune`,
  `Unison`, etc. (the `_SUSPICIOUS_AT_ZERO` set)
- A param at exactly 0 / factory default is "untouched"
- For pad / lead / bass roles: ≥3 untouched key params → **fail** with
  `unprogrammed_instrument` issue
- For other roles: ≥4 untouched → **warn** with `many_default_params`
- Drum roles auto-pass — minimal shaping is correct by design

The check has built-in escape hatches: an `Fe < Env` of 0 is fine when
`Fe On` is also 0 (filter envelope deliberately disabled). Same for pitch.

## What this rubric does NOT check

- Effects chain depth — §5 `effects_per_track` covers that
- Whether the programmed values are musically right — taste
- 3rd-party VST/AU instruments — `check_params` returns n/a (no native
  parameter readouts available)

## Why this exists alongside §5

The full §5 rubric is heavyweight (7 criteria, 6+ data sources). When the
user is iterating fast on sound design specifically, running just this
rubric is faster and the brief is sharper.

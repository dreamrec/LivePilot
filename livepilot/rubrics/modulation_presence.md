# §4 — Modulation > Static

Mechanical check: every melodic/harmonic layer (bass / pad / lead / vox /
atmos) should have at least one form of motion — a modulation-matrix entry,
an LFO routing producing audible change, or a clip-automation envelope.

CLAUDE.md §4: "Static MIDI at default velocity ≈ 'didn't try'. Every
melodic/harmonic layer should have AT LEAST one parameter moving over time."

## Inputs

The grader requires per-track modulation signals to be populated by the
caller (the `audit_layer` orchestrator already computes both):

```
{
  "tracks": [
    {
      "index": int,
      "name": str,
      "devices": [...],
      "modulation_count": int,        # sum of mod-matrix non-zero entries
      "has_clip_automation": bool,    # any clip on track has automation
    }, ...
  ],
}
```

Missing fields are degraded gracefully:
- Track has neither key → reported as `unknown`, doesn't pass or fail
- All checked tracks unknown → criterion returns `n/a`

## Roles required to have motion

bass · pad · lead · vox · atmos

Drum-role tracks (kick / snare / hat / perc) are excluded — sequencer
humanization is critiqued by the §5 layer-precision rubric, not this one.
FX tracks are also excluded.

## Criterion

### `melodic_layers_have_motion`

- All checked melodic-role tracks have `modulation_count > 0` OR
  `has_clip_automation == True` → **pass**
- One or more static melodic-role tracks → **warn** (advisory; not blocking)
- No melodic-role tracks present, or all unknown → **n/a**

## Why advisory, not blocking

A stab patch with deliberate static behavior (one-shot pluck, plocked
bass) is musically valid. The grader can't distinguish "static by intent"
from "static by neglect" — so it surfaces the layer for review rather than
auto-undoing. Promote to blocking in a future phase if false-positive
rate stays low.

## What this rubric does NOT check

- Whether the modulation is **musical** — quality of motion is taste
- Internal LFOs of opaque curated presets (Vector / Wavetable .adg) —
  per the standing-rule memory, those are off-limits to modulate
- Pitch-bend / portamento — handled by the §5 sequence check

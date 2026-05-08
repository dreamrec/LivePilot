# §1 — Default Preset Energy is Forbidden

Mechanical check: when a melodic-role track (bass / pad / lead) is loaded
with a banned default synth and no preset has been applied, flag it.

CLAUDE.md §1: "Never reach for Analog / Poli / Drift / Meld as a default for
bass / pad / lead. They read as 'generic AI synth' and have been rejected
multiple times."

This rubric does NOT ban these synths outright — it bans them in their
**factory-default state** for melodic roles. A programmed Drift bass with a
preset name and modulated parameters is fine. A naked `Drift` device with
display name `"Drift"` is the chronic anti-pattern.

## Inputs

```
{
  "tracks": [
    {
      "index": int,
      "name": str,
      "devices": [
        {"class_name": str, "name": str, ...},
        ...
      ],
    }, ...
  ],
}
```

The first instrument-class device on each track is the candidate. `name` is
Ableton's display name for the device — for a freshly-loaded Drift it
equals `"Drift"`; for a preset-loaded Drift it equals the preset stem.

## Banned default class names

| Class name | Reason |
|------------|--------|
| Drift  | Generic subtractive — reach for Granulator III / Wavetable / sample-based instead |
| Analog | Same reason |
| Poli   | M4L opaque — sound-design critic can't analyze |
| Meld   | M4L opaque — sound-design critic can't analyze |

## Trigger conditions for banned roles

| Role | Triggers |
|------|----------|
| bass | banned class + default name |
| pad  | banned class + default name |
| lead | banned class + default name |

Other roles (kick, snare, hat, perc, vox, atmos, fx, unknown) are
**not flagged** by this rubric.

## Default-name detection

A device is considered "default-loaded" when its display `name` matches its
`class_name` exactly (case-insensitive). For example:
- `class_name="Drift", name="Drift"` → default
- `class_name="Drift", name="BoC Wash"` → preset applied → not default

## Criteria

### `no_banned_default_instruments`

- All tracks pass → **pass**
- One or more banned-default + banned-role tracks → **fail**

### `prefer_curated_or_under_used`

Advisory: when the first instrument is on the user's under-used list
(Operator, Wavetable, Sampler, Simpler, Granulator III, Tension, Collision,
Electric, Drum Synths, Inspired-by-Nature variants), praise it. This is a
**signal-only** check, never blocks — it surfaces in evidence.

## What this rubric does NOT check

- Sound-design depth — see §2 rubric (Phase 2b)
- Whether the preset is musically right for the genre — that's taste
- Whether the player has been told to use a banned class explicitly
  ("subtractive" / "analog texture") — context lives outside the snapshot

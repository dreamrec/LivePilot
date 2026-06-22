---
name: livepilot-track-intent
description: Use when the user describes what Ableton tracks are for, gives track/section/project references, marks parts as main/support/background/optional, asks to ingest notes about vocals, harmonies, guitars, bass, drums, layers, doubles, or wants LivePilot production decisions to honor sparse track intent during composition, sound design, arrangement, mixing, or experiments.
---

# LivePilot Track Intent

Capture track intent as sparse, durable production context, then use it before
making musical decisions.

## Core Rule

Before composition, sound design, mixing, arrangement, or experiment planning,
call `build_track_intent_map`. Treat user-explicit committed intent as stronger
than name-based role inference, analyzer heuristics, or generic mix rules.

## Ingest Workflow

1. Read current topology with `get_session_info`.
2. If the user describes a specific track, resolve it by current name/index and
   store the note with `set_track_annotation`.
3. Preserve uncertainty:
   - Use `decision_state="committed"` for clear instructions.
   - Use `decision_state="open"` when the user wants valid options auditioned.
   - Use `decision_state="hypothesis"` for agent guesses.
4. Store references as intent anchors. Do not claim the referenced audio was
   analyzed unless a separate analysis actually happened.
5. After creating a double, harmony, layer, or alternate, annotate the new track
   in the same turn.
6. Verify by calling `build_track_intent_map` and checking that the target track
   has the expected effective role or open options.

## Decision Workflow

Use the map this way:

- `decision_state="committed"`: follow the annotation unless the user overrides.
- `decision_state="open"`: do not silently choose. Create A/B branches or ask if
  a choice blocks the requested edit.
- `decision_state="hypothesis"`: use as weak evidence and say it is inferred if
  reporting it.
- `decision_state="rejected"`: keep for history but do not use as active intent.

When the user picks an open option, update the annotation with
`selected_option_id` and `decision_state="committed"`.

## Reference Schema

Read `references/schema.md` when writing rich annotations, references,
relationships, or open-option structures.

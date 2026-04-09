---
name: livepilot-notes
description: This skill should be used when the user asks to "write notes", "add a melody", "chord progression", "rhythm pattern", "MIDI notes", "transpose", "quantize", "Euclidean rhythm", "counterpoint", "scale", "key detection", "harmony", or wants to create, edit, or analyze MIDI content in Ableton Live.
---

# MIDI Notes — Create, Edit, and Analyze

Write melodies, chords, rhythms, and generative patterns in Ableton Live clips. Every note operation follows the Live 12 API.

## Note API Cycle

Four operations form the core CRUD cycle for MIDI notes:

1. **Create:** `add_notes(track_index, clip_index, notes)` — write new notes into a clip
2. **Read:** `get_notes(track_index, clip_index)` — retrieve all notes with IDs, pitches, timings
3. **Update:** `modify_notes(track_index, clip_index, modifications)` — change existing notes by `note_id`
4. **Delete:** `remove_notes(track_index, clip_index, start_time, duration, pitch_start, pitch_end)` — clear a region, or `remove_notes_by_id(track_index, clip_index, note_ids)` — surgical deletion by ID

Always create a clip first with `create_clip(track_index, clip_index, length)` before adding notes to it.

## Note Format

When calling `add_notes`, each note requires:

```json
{
  "pitch": 60,
  "start_time": 0.0,
  "duration": 0.5,
  "velocity": 100,
  "mute": false
}
```

When reading with `get_notes`, each note also returns Live 12 extended fields:
- `note_id` — unique identifier for modify/remove operations
- `probability` — 0.0 to 1.0, per-note trigger probability (Live 12 feature)
- `velocity_deviation` — -127.0 to 127.0, randomizes velocity on each trigger
- `release_velocity` — 0.0 to 127.0, note-off velocity

Use `modify_notes` with `note_id` to update any field on existing notes — pitch, velocity, timing, probability, mute state.

## Duplication and Transposition

- `duplicate_notes(track_index, clip_index, time_offset)` — copy all notes forward by `time_offset` beats. Use for pattern repetition: a 4-beat pattern duplicated at offset 4.0 creates an 8-beat loop.
- `transpose_notes(track_index, clip_index, semitones, start_time, duration)` — shift pitches in a region by semitones. Positive = up, negative = down.
- `transpose_smart(track_index, clip_index, semitones, key)` — transpose with scale awareness. Notes stay within the target key, avoiding chromatic collisions.

## Quantization

`quantize_clip(track_index, clip_index, grid, amount)` snaps note start times to a rhythmic grid.

Grid enum values:
- 0 = None (no quantize)
- 1 = 1/4 notes
- 2 = 1/8 notes
- 3 = 1/8 triplets
- 4 = 1/8 + triplets (combined grid)
- 5 = 1/16 notes
- 6 = 1/16 triplets
- 7 = 1/16 + triplets (combined grid)
- 8 = 1/32 notes

The `amount` parameter (0.0-1.0) controls how far notes move toward the grid. Use 1.0 for rigid quantize, 0.5-0.7 for humanized feel.

## Theory Integration

Run these checks before firing any clip with melodic content:

1. `identify_scale(track_index, clip_index)` — detect the scale from existing notes (Krumhansl-Schmuckler algorithm). Returns key, mode, and confidence.
2. `detect_theory_issues(track_index, clip_index, strict=true)` — check for out-of-key notes, parallel fifths, voice crossing, augmented/diminished accidents. The `strict` flag enables all checks.
3. Fix problems with `modify_notes` — adjust offending pitches before the user hears them.

The theory engine knows 7 standard modes. Exotic scales (Hijaz, Hungarian minor, whole tone) produce false "out of key" warnings. Cross-reference flagged pitches against the intended scale manually. Use `key="C hijaz"` for Hijaz/Phrygian Dominant keys.

## Harmony Analysis and Suggestions

- `analyze_harmony(track_index, clip_index)` — identify chords in a clip, returns chord names, qualities, root notes, and progression analysis
- `suggest_next_chord(track_index, clip_index, key)` — given the current harmonic context, suggest the next chord with voice leading and functional reasoning
- `harmonize_melody(track_index, clip_index, key, style)` — generate harmony notes for an existing melody. Returns a note array ready for `add_notes` on a separate track.
- `generate_countermelody(track_index, clip_index, key, species)` — generate a counterpoint line against existing notes. Species 1-5 follow classical counterpoint rules. Returns notes for `add_notes`.

Both `harmonize_melody` and `generate_countermelody` return note arrays — do not call them and discard the output. Place the results into a clip with `add_notes`.

## Generative Algorithms

### Euclidean Rhythms

`generate_euclidean_rhythm(pulses, steps, pitch, velocity, duration)` — distribute `pulses` as evenly as possible across `steps` using the Bjorklund algorithm. Returns a note array. The tool identifies named rhythms automatically (e.g., 3 pulses in 8 steps = "tresillo", 5 in 8 = "cinquillo").

`layer_euclidean_rhythms(layers)` — stack multiple Euclidean patterns for polyrhythmic textures. Each layer specifies pulses, steps, pitch, and velocity. Returns a combined note array spanning all layers, ready for a single `add_notes` call or split across tracks.

### Minimalist Techniques

`generate_tintinnabuli(melody_pitches, key, mode, position)` — implement Arvo Part's technique: a T-voice (triad arpeggio) against a M-voice (stepwise melody). Returns two-voice note data.

`generate_phase_shift(pattern, shift_amount, repetitions)` — implement Steve Reich's phasing: two identical patterns drifting apart over time. One voice holds steady while the other shifts by `shift_amount` per repetition.

`generate_additive_process(melody_pitches, iterations)` — implement Philip Glass's additive technique: melody expanded by adding one note per iteration, building complexity gradually.

All generative tools return note arrays. Place them in clips with `add_notes`.

## Neo-Riemannian Harmony

- `navigate_tonnetz(chord, transform)` — apply PRL (Parallel, Relative, Leading-tone) transforms to a chord. Returns the neighbor chord and its relationship.
- `find_voice_leading_path(start_chord, end_chord)` — find the shortest harmonic path between two chords through Tonnetz space. Returns intermediate chords.
- `classify_progression(chords)` — identify the neo-Riemannian transform pattern in a chord sequence (e.g., PRL cycle, hexatonic, octatonic).
- `suggest_chromatic_mediants(chord)` — return all chromatic mediant relations with film score usage notes. Useful for dramatic harmonic shifts.

## MIDI File I/O

- `export_clip_midi(track_index, clip_index, file_path)` — export a session clip's notes to a .mid file
- `import_midi_to_clip(track_index, clip_index, file_path)` — load a .mid file into a clip, replacing existing notes
- `analyze_midi_file(file_path)` — offline analysis of any .mid file (tempo, note count, structure). No Ableton connection needed.
- `extract_piano_roll(file_path)` — return a 2D velocity matrix (pitch x time) from a .mid file for visualization

## Pitch Audit — Mandatory Before Firing

Before playing any clip with melodic or harmonic content:

1. `identify_scale` on every melodic track — verify all tracks share the same tonal center
2. `analyze_harmony` on chordal tracks — verify chord quality (no accidental augmented/diminished)
3. `detect_theory_issues(strict=true)` — check all theory rules
4. Report a clear tuning summary to the user before proceeding
5. Fix wrong notes with `modify_notes` before firing

## Reference

Consult `references/midi-recipes.md` in the livepilot-core skill for drum patterns by genre, chord voicings by style, scale lookup tables, hi-hat articulation techniques, humanization recipes, and polymetric layering patterns.

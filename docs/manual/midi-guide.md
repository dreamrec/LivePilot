# MIDI Programming Guide

This is where LivePilot goes from useful to indispensable. Programming MIDI by hand in a piano roll is slow. Describing what you want in words and having it appear instantly is fast. But to get the most out of it, you need to understand how MIDI notes are represented, what the numbers mean, and how to think in beats, pitches, and velocities.

This chapter is your reference for all of it.

---

## 1. How MIDI Notes Work in LivePilot

Every MIDI note in LivePilot is a dictionary with these fields:

| Field | Type | Range | Required | Description |
|-------|------|-------|----------|-------------|
| `pitch` | int | 0-127 | Yes | MIDI note number. 60 = Middle C (C3) |
| `start_time` | float | 0.0+ | Yes | Position in beats from the clip start |
| `duration` | float | >0 | Yes | Length in beats |
| `velocity` | int | 1-127 | No (default 100) | How hard the note is struck |
| `mute` | bool | true/false | No (default false) | Muted notes are silent but visible |
| `probability` | float | 0.0-1.0 | No (default 1.0) | Chance the note triggers on each loop (Live 12) |
| `velocity_deviation` | float | -127 to 127 | No (default 0) | Random velocity offset range |
| `release_velocity` | float | 0-127 | No (default 64) | Velocity of the note-off event |

### Understanding beats and timing

All times are in **beats relative to the clip start**, not bars or seconds. In 4/4 time:

| Musical position | Beat value |
|-----------------|------------|
| Beat 1 (downbeat) | 0.0 |
| The "and" of beat 1 | 0.5 |
| Beat 2 | 1.0 |
| Beat 3 | 2.0 |
| Beat 4 | 3.0 |
| 1/16th note | 0.25 |
| 1/8th note triplet | 0.333 |
| End of one bar | 4.0 |
| Beat 1, bar 2 | 4.0 |
| Beat 1, bar 3 | 8.0 |

A standard 4-bar clip runs from beat 0.0 to beat 16.0.

### Understanding pitch

MIDI pitch 60 is Middle C, which Ableton labels **C3**. Each semitone is +1. Each octave is +12.

| Note | MIDI | Note | MIDI | Note | MIDI |
|------|------|------|------|------|------|
| C1 | 36 | C2 | 48 | C3 | 60 |
| D1 | 38 | D2 | 50 | D3 | 62 |
| E1 | 40 | E2 | 52 | E3 | 64 |
| F1 | 41 | F2 | 53 | F3 | 65 |
| G1 | 43 | G2 | 55 | G3 | 67 |
| A1 | 45 | A2 | 57 | A3 | 69 |
| B1 | 47 | B2 | 59 | B3 | 71 |

### The note_id field

When you read notes with `get_notes`, each note comes back with a `note_id`. This is Ableton's internal identifier for that specific note. You need it for:

- **`modify_notes`** -- change pitch, timing, velocity, or probability of specific notes
- **`remove_notes_by_id`** -- delete specific notes without touching others
- **`duplicate_notes`** -- copy specific notes with a time offset

The typical workflow: read the notes, find the ones you want to change, use their IDs to modify them.

---

## 2. Drum Rack MIDI Map

Ableton's Drum Rack maps each pad to a MIDI pitch. The standard General MIDI drum mapping is:

| Pitch | Note | Drum | Common abbreviation |
|-------|------|------|-------------------|
| 36 | C1 | Kick | K |
| 37 | C#1 | Side Stick | SS |
| 38 | D1 | Snare | S |
| 39 | D#1 | Clap | Cl |
| 40 | E1 | Snare (alt) | S2 |
| 41 | F1 | Low Tom | LT |
| 42 | F#1 | Closed Hi-Hat | CH |
| 43 | G1 | Mid Tom | MT |
| 44 | G#1 | Pedal Hi-Hat | PH |
| 45 | A1 | High Tom | HT |
| 46 | A#1 | Open Hi-Hat | OH |
| 47 | B1 | Low-Mid Tom | LMT |
| 48 | C2 | Hi-Mid Tom | HMT |
| 49 | C#2 | Crash Cymbal | Cr |
| 50 | D2 | High Tom 2 | HT2 |
| 51 | D#2 | Ride Cymbal | Ri |
| 52 | E2 | China Cymbal | Ch |
| 53 | F2 | Ride Bell | RB |
| 54 | F#2 | Tambourine | Tb |
| 55 | G2 | Splash Cymbal | Sp |
| 56 | G#2 | Cowbell | Cb |
| 75 | D#4 | Claves | Cv |

**Important:** Ableton's built-in kits often remap pads to different pitches. A "909 Kit" may put the kick on pad 1 but map it differently than GM standard. Always run `get_rack_chains` on a Drum Rack track to see exactly which pitch triggers which sample. Do not assume the mapping above holds for every kit.

---

## 3. Genre Drum Patterns

Each pattern below is a 4-bar or 2-bar clip at the genre's typical tempo. These are ready-to-use `add_notes` arrays. Copy them directly or ask LivePilot to adapt them.

### House / Techno (120-130 BPM)

Four-on-the-floor kick, offbeat hi-hats, snare/clap on 2 and 4. The backbone of dance music.

```json
[
  {"pitch": 36, "start_time": 0.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 1.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 2.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 3.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 4.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 5.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 6.0,  "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 7.0,  "duration": 0.5, "velocity": 110},

  {"pitch": 38, "start_time": 1.0,  "duration": 0.25, "velocity": 100},
  {"pitch": 38, "start_time": 3.0,  "duration": 0.25, "velocity": 100},
  {"pitch": 38, "start_time": 5.0,  "duration": 0.25, "velocity": 100},
  {"pitch": 38, "start_time": 7.0,  "duration": 0.25, "velocity": 100},

  {"pitch": 42, "start_time": 0.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 1.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 2.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 3.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 4.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 5.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 6.5,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 7.5,  "duration": 0.25, "velocity": 80},

  {"pitch": 46, "start_time": 3.75, "duration": 0.5,  "velocity": 70},
  {"pitch": 46, "start_time": 7.75, "duration": 0.5,  "velocity": 70}
]
```

Two bars. Kicks on every beat. Clap/snare on 2 and 4. Closed hats on the offbeats. Open hat at the end of bars for a lift. Extend to 4 bars by duplicating with `time_offset: 8.0`.

### Hip-Hop / Boom Bap (85-95 BPM)

Laid-back swing feel. The kick has a relaxed placement, snare on 2 and 4, hats running 8ths with ghost notes.

```json
[
  {"pitch": 36, "start_time": 0.0,   "duration": 0.5,  "velocity": 110},
  {"pitch": 36, "start_time": 0.75,  "duration": 0.25, "velocity": 85},
  {"pitch": 36, "start_time": 2.25,  "duration": 0.5,  "velocity": 105},
  {"pitch": 36, "start_time": 4.0,   "duration": 0.5,  "velocity": 110},
  {"pitch": 36, "start_time": 4.75,  "duration": 0.25, "velocity": 80},
  {"pitch": 36, "start_time": 6.5,   "duration": 0.5,  "velocity": 100},

  {"pitch": 38, "start_time": 1.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 38, "start_time": 3.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 38, "start_time": 5.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 38, "start_time": 7.0,   "duration": 0.25, "velocity": 110},

  {"pitch": 42, "start_time": 0.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 0.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 1.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 1.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 2.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 2.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 3.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 3.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 4.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 4.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 5.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 5.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 6.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 6.5,   "duration": 0.25, "velocity": 55},
  {"pitch": 42, "start_time": 7.0,   "duration": 0.25, "velocity": 75},
  {"pitch": 42, "start_time": 7.5,   "duration": 0.25, "velocity": 55}
]
```

Two bars. Notice the kick on beat 1.75 (the "and" of 2) -- that lazy placement is the boom bap feel. Hats alternate between strong and ghost velocity. At this BPM, the timing micro-shifts in Section 7 make a big difference.

### Trap (130-170 BPM, half-time feel)

Double-time hi-hats with velocity ramps, 808 kick patterns, layered snare and clap. The hi-hats are the star here.

```json
[
  {"pitch": 36, "start_time": 0.0,   "duration": 1.0,  "velocity": 127},
  {"pitch": 36, "start_time": 3.5,   "duration": 0.75, "velocity": 120},
  {"pitch": 36, "start_time": 4.0,   "duration": 1.0,  "velocity": 127},
  {"pitch": 36, "start_time": 6.0,   "duration": 0.5,  "velocity": 115},
  {"pitch": 36, "start_time": 6.75,  "duration": 0.5,  "velocity": 110},

  {"pitch": 38, "start_time": 1.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 39, "start_time": 1.0,   "duration": 0.25, "velocity": 95},
  {"pitch": 38, "start_time": 3.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 39, "start_time": 3.0,   "duration": 0.25, "velocity": 95},
  {"pitch": 38, "start_time": 5.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 39, "start_time": 5.0,   "duration": 0.25, "velocity": 95},
  {"pitch": 38, "start_time": 7.0,   "duration": 0.25, "velocity": 110},
  {"pitch": 39, "start_time": 7.0,   "duration": 0.25, "velocity": 95},

  {"pitch": 42, "start_time": 0.0,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 0.25,  "duration": 0.125, "velocity": 70},
  {"pitch": 42, "start_time": 0.5,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 0.75,  "duration": 0.125, "velocity": 70},
  {"pitch": 42, "start_time": 1.0,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 1.25,  "duration": 0.125, "velocity": 75},
  {"pitch": 42, "start_time": 1.5,   "duration": 0.125, "velocity": 80},
  {"pitch": 42, "start_time": 1.625, "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 1.75,  "duration": 0.125, "velocity": 95},
  {"pitch": 42, "start_time": 1.875, "duration": 0.125, "velocity": 105},
  {"pitch": 42, "start_time": 2.0,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 2.25,  "duration": 0.125, "velocity": 70},
  {"pitch": 42, "start_time": 2.5,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 2.75,  "duration": 0.125, "velocity": 70},
  {"pitch": 42, "start_time": 3.0,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 3.25,  "duration": 0.125, "velocity": 70},
  {"pitch": 42, "start_time": 3.5,   "duration": 0.125, "velocity": 90},
  {"pitch": 42, "start_time": 3.75,  "duration": 0.125, "velocity": 70},
  {"pitch": 46, "start_time": 1.75,  "duration": 0.25,  "velocity": 85},
  {"pitch": 46, "start_time": 3.75,  "duration": 0.25,  "velocity": 85}
]
```

One bar shown (duplicate across 4 bars, varying the hat rolls). Key details: snare and clap are layered at the same start time. The hi-hat velocity ramp at beats 1.5-1.875 creates the classic trap roll effect. 808 kicks have long duration because they're pitched, sustained sounds. Open hat at the end of each 2-beat phrase.

### Drum and Bass (170-180 BPM)

Fast breakbeat energy. The kick-snare interplay is syncopated, hats drive the top end.

```json
[
  {"pitch": 36, "start_time": 0.0,   "duration": 0.25, "velocity": 115},
  {"pitch": 36, "start_time": 1.25,  "duration": 0.25, "velocity": 100},
  {"pitch": 36, "start_time": 2.75,  "duration": 0.25, "velocity": 105},
  {"pitch": 36, "start_time": 4.0,   "duration": 0.25, "velocity": 115},
  {"pitch": 36, "start_time": 5.0,   "duration": 0.25, "velocity": 100},
  {"pitch": 36, "start_time": 6.5,   "duration": 0.25, "velocity": 110},
  {"pitch": 36, "start_time": 7.25,  "duration": 0.25, "velocity": 95},

  {"pitch": 38, "start_time": 1.0,   "duration": 0.25, "velocity": 120},
  {"pitch": 38, "start_time": 3.0,   "duration": 0.25, "velocity": 120},
  {"pitch": 38, "start_time": 3.75,  "duration": 0.25, "velocity": 85},
  {"pitch": 38, "start_time": 5.0,   "duration": 0.25, "velocity": 120},
  {"pitch": 38, "start_time": 7.0,   "duration": 0.25, "velocity": 120},
  {"pitch": 38, "start_time": 7.5,   "duration": 0.25, "velocity": 80},

  {"pitch": 42, "start_time": 0.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 0.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 1.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 1.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 2.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 2.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 3.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 3.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 4.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 4.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 5.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 5.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 6.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 6.5,   "duration": 0.125, "velocity": 65},
  {"pitch": 42, "start_time": 7.0,   "duration": 0.125, "velocity": 85},
  {"pitch": 42, "start_time": 7.5,   "duration": 0.125, "velocity": 65}
]
```

Two bars. At 174 BPM these fly by. The kick placement at 1.25 and 2.75 creates the broken feel. Ghost snares at 3.75 and 7.5 add swing. Hat velocity alternation keeps it from sounding machine-gun.

### Minimal / Rominimal (122-128 BPM)

Sparse, hypnotic, repetitive. The magic is in what you leave out. Per-note probability turns a simple loop into something that breathes.

```json
[
  {"pitch": 36, "start_time": 0.0,  "duration": 0.5,  "velocity": 100},
  {"pitch": 36, "start_time": 1.0,  "duration": 0.5,  "velocity": 100},
  {"pitch": 36, "start_time": 2.0,  "duration": 0.5,  "velocity": 100},
  {"pitch": 36, "start_time": 3.0,  "duration": 0.5,  "velocity": 100},

  {"pitch": 42, "start_time": 0.5,  "duration": 0.125, "velocity": 75},
  {"pitch": 42, "start_time": 1.5,  "duration": 0.125, "velocity": 75},
  {"pitch": 42, "start_time": 2.5,  "duration": 0.125, "velocity": 75},
  {"pitch": 42, "start_time": 3.5,  "duration": 0.125, "velocity": 75},

  {"pitch": 39, "start_time": 1.0,  "duration": 0.25,  "velocity": 80, "probability": 0.65},
  {"pitch": 39, "start_time": 3.0,  "duration": 0.25,  "velocity": 70, "probability": 0.5},

  {"pitch": 75, "start_time": 0.75, "duration": 0.125, "velocity": 40, "probability": 0.4},
  {"pitch": 75, "start_time": 1.75, "duration": 0.125, "velocity": 35, "probability": 0.35},
  {"pitch": 75, "start_time": 2.75, "duration": 0.125, "velocity": 45, "probability": 0.45},
  {"pitch": 75, "start_time": 3.25, "duration": 0.125, "velocity": 30, "probability": 0.3},

  {"pitch": 56, "start_time": 2.0,  "duration": 0.125, "velocity": 55, "probability": 0.5},

  {"pitch": 46, "start_time": 3.75, "duration": 0.5,   "velocity": 50, "probability": 0.4}
]
```

One bar. Four-on-the-floor kick, offbeat closed hats -- but the clap only appears 50-65% of the time. The claves (75) and cowbell (56) ghost at 30-50% probability, creating a pattern that shifts every loop. The open hat at 3.75 only opens up 40% of the time. This is how minimal stays interesting for 7 minutes.

---

## 4. Scales and Keys

Knowing your scale means every note you program will fit. Here are the common scales with their semitone intervals from the root.

### Semitone interval table

| Scale | Intervals from root | Steps pattern |
|-------|-------------------|---------------|
| Major (Ionian) | 0, 2, 4, 5, 7, 9, 11 | W-W-H-W-W-W-H |
| Natural Minor (Aeolian) | 0, 2, 3, 5, 7, 8, 10 | W-H-W-W-H-W-W |
| Harmonic Minor | 0, 2, 3, 5, 7, 8, 11 | W-H-W-W-H-WH-H |
| Dorian | 0, 2, 3, 5, 7, 9, 10 | W-H-W-W-W-H-W |
| Mixolydian | 0, 2, 4, 5, 7, 9, 10 | W-W-H-W-W-H-W |
| Pentatonic Major | 0, 2, 4, 7, 9 | W-W-WH-W-WH |
| Pentatonic Minor | 0, 3, 5, 7, 10 | WH-W-W-WH-W |
| Blues | 0, 3, 5, 6, 7, 10 | WH-W-H-H-WH-W |

W = whole step (2 semitones), H = half step (1 semitone), WH = whole + half (3 semitones)

### How to calculate pitches

Pick your root note's MIDI number, then add each interval.

**Example: D minor (D3 = 62)**

| Degree | Note | Calculation | MIDI pitch |
|--------|------|-------------|------------|
| 1 (root) | D | 62 + 0 | 62 |
| 2 | E | 62 + 2 | 64 |
| 3 (flat) | F | 62 + 3 | 65 |
| 4 | G | 62 + 5 | 67 |
| 5 | A | 62 + 7 | 69 |
| 6 (flat) | Bb | 62 + 8 | 70 |
| 7 (flat) | C | 62 + 10 | 72 |

**Example: G major (G2 = 55)**

| Degree | Note | Calculation | MIDI pitch |
|--------|------|-------------|------------|
| 1 | G | 55 + 0 | 55 |
| 2 | A | 55 + 2 | 57 |
| 3 | B | 55 + 4 | 59 |
| 4 | C | 55 + 5 | 60 |
| 5 | D | 55 + 7 | 62 |
| 6 | E | 55 + 9 | 64 |
| 7 | F# | 55 + 11 | 66 |

### Common root notes for producers

| Key | Root MIDI (octave 2) | Root MIDI (octave 3) | Notes |
|-----|---------------------|---------------------|-------|
| C | 48 | 60 | No sharps or flats |
| D | 50 | 62 | Very common for minor keys |
| E | 52 | 64 | Great for guitar-based music |
| F | 53 | 65 | Classic soul/R&B key |
| G | 55 | 67 | Bright, popular key |
| A | 57 | 69 | Standard tuning reference |
| Bb | 58 | 70 | Jazz, brass instruments |

---

## 5. Chord Voicings

Chords are just multiple notes at the same `start_time`. Here is how to build them from any root.

### Triads

| Chord type | Intervals | From C3 (60) | Sound |
|-----------|-----------|-------------|-------|
| Major | +0, +4, +7 | 60, 64, 67 | Happy, bright |
| Minor | +0, +3, +7 | 60, 63, 67 | Sad, dark |
| Diminished | +0, +3, +6 | 60, 63, 66 | Tense, unstable |
| Augmented | +0, +4, +8 | 60, 64, 68 | Dreamy, suspenseful |

### Seventh chords

| Chord type | Intervals | From C3 (60) | Common use |
|-----------|-----------|-------------|-----------|
| Major 7th | +0, +4, +7, +11 | 60, 64, 67, 71 | Jazz, neo-soul, lo-fi |
| Minor 7th | +0, +3, +7, +10 | 60, 63, 67, 70 | R&B, jazz, chill |
| Dominant 7th | +0, +4, +7, +10 | 60, 64, 67, 70 | Blues, funk, resolution |
| Diminished 7th | +0, +3, +6, +9 | 60, 63, 66, 69 | Tension, passing chords |

### Common progressions

Here are the most-used progressions with example pitches in C major:

**I - V - vi - IV** (Pop, rock, EDM -- "the hit progression")
- C major (60,64,67) -- G major (55,59,62) -- A minor (57,60,64) -- F major (53,57,60)

**ii - V - I** (Jazz, neo-soul, lo-fi)
- D minor (62,65,69) -- G dominant 7th (55,59,62,65) -- C major 7th (60,64,67,71)

**i - iv - VII - III** (Minor key EDM, dark pop)
- A minor (57,60,64) -- D minor (62,65,69) -- G major (55,59,62) -- C major (60,64,67)

**vi - IV - I - V** (Emotional pop, ballads)
- A minor (57,60,64) -- F major (53,57,60) -- C major (60,64,67) -- G major (55,59,62)

**i - VI - III - VII** (Cinematic, epic)
- A minor (57,60,64) -- F major (53,57,60) -- C major (48,52,55) -- G major (55,59,62)

### Voicing tips

**Pads and sustained chords:** Spread the notes across 2+ octaves. Instead of a tight C major (60,64,67), try (48, 60, 64, 67, 72) -- root in the bass, octave doubled at the top. Wide voicings sound fuller and leave room for other instruments.

**Stabs and plucks:** Keep it tight. (60,64,67) with short duration (0.125-0.25 beats) and high velocity (100-120). The compact voicing cuts through a mix.

**Inversions for smooth voice leading:** Instead of jumping between root position chords, invert them so the top note moves as little as possible:

```
C major: 60, 64, 67
F major (2nd inversion): 60, 65, 69   (top moves up 2)
G major (1st inversion): 59, 62, 67   (smooth drop)
```

This technique makes progressions sound connected instead of choppy. When you ask LivePilot to "make the chords flow smoothly," inversions are how it does it.

---

## 6. Bass Lines

Bass is the bridge between rhythm and harmony. Here are the fundamental patterns.

### Sub bass

The simplest bass line: root notes held long, sitting under everything.

```json
[
  {"pitch": 36, "start_time": 0.0, "duration": 4.0, "velocity": 100},
  {"pitch": 36, "start_time": 4.0, "duration": 4.0, "velocity": 100},
  {"pitch": 41, "start_time": 8.0, "duration": 4.0, "velocity": 100},
  {"pitch": 36, "start_time": 12.0, "duration": 4.0, "velocity": 100}
]
```

C1 (36) held for a full bar, resolving up to F1 (41) in bar 3. Low velocity variation -- sub bass should be steady. Duration covers the full bar so there are no gaps. Works in house, techno, and any 4/4 genre.

### Octave bass

Alternating the root and its octave on 8th notes. Classic dance music energy.

```json
[
  {"pitch": 36, "start_time": 0.0,  "duration": 0.375, "velocity": 110},
  {"pitch": 48, "start_time": 0.5,  "duration": 0.375, "velocity": 85},
  {"pitch": 36, "start_time": 1.0,  "duration": 0.375, "velocity": 110},
  {"pitch": 48, "start_time": 1.5,  "duration": 0.375, "velocity": 85},
  {"pitch": 36, "start_time": 2.0,  "duration": 0.375, "velocity": 110},
  {"pitch": 48, "start_time": 2.5,  "duration": 0.375, "velocity": 85},
  {"pitch": 36, "start_time": 3.0,  "duration": 0.375, "velocity": 110},
  {"pitch": 48, "start_time": 3.5,  "duration": 0.375, "velocity": 85}
]
```

Notice the octave notes (48) are lower velocity -- they're the "bounce," not the foundation. Duration is slightly less than 0.5 to leave a tiny gap between notes (staccato feel).

### Walking bass

Chromatic approach notes leading into each chord tone. Classic jazz/neo-soul feel.

```json
[
  {"pitch": 48, "start_time": 0.0,  "duration": 0.5,  "velocity": 100},
  {"pitch": 50, "start_time": 0.5,  "duration": 0.5,  "velocity": 90},
  {"pitch": 52, "start_time": 1.0,  "duration": 0.5,  "velocity": 95},
  {"pitch": 51, "start_time": 1.5,  "duration": 0.5,  "velocity": 85},
  {"pitch": 53, "start_time": 2.0,  "duration": 0.5,  "velocity": 100},
  {"pitch": 55, "start_time": 2.5,  "duration": 0.5,  "velocity": 90},
  {"pitch": 54, "start_time": 3.0,  "duration": 0.5,  "velocity": 85},
  {"pitch": 55, "start_time": 3.5,  "duration": 0.5,  "velocity": 95}
]
```

One bar over a C-F progression. The notes walk stepwise between chord tones, with chromatic approach notes (51 = Eb approaching F at beat 2, 54 = F# approaching G at beat 4). Velocity varies to give it a human, played feel.

### Syncopation techniques

Syncopation is what makes bass lines groove. The trick is placing notes *between* beats and tying them over the beat they "should" be on.

- **Anticipation:** Start a note 0.5 beats early. Instead of bass on beat 3, place it at 2.5 with duration 1.0 -- it arrives early and sustains through beat 3.
- **Delayed attack:** Place the note at 0.125 or 0.25 after the beat. A kick on 1.0 with bass at 1.125 creates a push-pull groove.
- **Rests as rhythm:** Leave beat 1 empty, start the bass on the "and" of 1 (0.5). The silence creates tension the note resolves.
- **Ties across bar lines:** A note starting at beat 3.5 with duration 1.5 ties into the next bar. This blurs bar boundaries and creates forward motion.

---

## 7. Humanization

Perfectly quantized MIDI sounds robotic. Real musicians have subtle timing and velocity variations. Here is how to add life to programmed parts.

### Velocity variation

Set a base velocity and vary notes around it. Different ranges for different goals:

| Style | Base velocity | Variation | Effect |
|-------|--------------|-----------|--------|
| Tight/mechanical | 100 | +/- 5 | Still very even, barely noticeable |
| Natural feel | 100 | +/- 10-15 | Sounds played, not programmed |
| Expressive | 100 | +/- 20-30 | Dynamic, emotional |
| Ghost notes | 35 | +/- 10 | Subtle background texture |

For drums, strong beats (kick on 1, snare on 2/4) should be higher velocity. Offbeats, ghost notes, and hat "ands" should be lower. This creates a natural accent pattern.

### Timing micro-shifts

Small timing offsets simulate a real player's imperfections. Values are in beats:

| Instrument | Offset range | Direction | Why |
|-----------|-------------|-----------|-----|
| Kick | -0.005 to -0.015 | Slightly early | Pushes the groove forward, feels urgent |
| Snare | +0.005 to +0.015 | Slightly late | Laid-back, relaxed |
| Hi-hats | -0.01 to +0.01 | Random | Loose, human feel |
| Bass | +0.005 to +0.01 | Slightly behind kick | Creates width between kick and bass |

These are tiny amounts. At 120 BPM, one beat is 0.5 seconds, so 0.01 beats is 5 milliseconds. You will not consciously hear it, but you will feel the difference.

### Per-note probability

Live 12's probability feature is powerful for generative variation. Each time the clip loops, notes with probability < 1.0 may or may not trigger.

| Probability | Behavior | Best for |
|-------------|----------|----------|
| 1.0 | Always plays | Core rhythm elements |
| 0.7-0.9 | Usually plays, occasionally drops | Fills, secondary percussion |
| 0.4-0.6 | Coin flip | Ghost notes, variation elements |
| 0.2-0.3 | Rare appearance | Surprise accents, ear candy |
| 0.05-0.1 | Almost never | Very occasional spice |

Combine probability with `velocity_deviation` for even more variation. A hat with velocity 60, probability 0.5, and velocity_deviation 20 will sometimes play loud, sometimes soft, and sometimes not at all.

### Ghost notes

Ghost notes are quiet, probability-gated notes that add texture without dominating the pattern. They are the secret to patterns that sound "produced."

```json
{"pitch": 38, "start_time": 0.75,  "duration": 0.125, "velocity": 30, "probability": 0.4},
{"pitch": 38, "start_time": 1.75,  "duration": 0.125, "velocity": 25, "probability": 0.35},
{"pitch": 38, "start_time": 2.5,   "duration": 0.125, "velocity": 35, "probability": 0.5},
{"pitch": 38, "start_time": 3.25,  "duration": 0.125, "velocity": 28, "probability": 0.45}
```

Velocity 20-50. Probability 0.3-0.6. Short duration. Placed between the main hits. These turn a basic kick-snare-hat pattern into something that grooves.

### The modify_notes workflow

To humanize existing notes already in a clip:

1. **Read the notes:** `get_notes` returns every note with its `note_id`
2. **Decide what to change:** Pick notes by pitch range, time range, or velocity
3. **Apply modifications:** Use `modify_notes` with an array of `{note_id, velocity?, start_time?, ...}` changes
4. **Listen and iterate:** Play the clip, adjust further if needed

This is non-destructive -- you can always undo with `undo`, or read the notes again and adjust further. No need to delete and re-enter patterns from scratch.

---

## 8. Quantization

Quantization snaps notes to a rhythmic grid. Use `quantize_clip` to tighten up loose playing or programmed patterns.

### Grid values

| Grid value | Division | Beats apart | Best for |
|-----------|----------|-------------|----------|
| 0 | None | -- | No quantization |
| 1 | 1/4 notes | 1.0 | Very loose, just the beats |
| 2 | 1/8 notes | 0.5 | General purpose |
| 3 | 1/8 note triplets | 0.333 | Shuffle, swing feels |
| 4 | 1/8 + triplet | mixed | Combines straight and triplet grid |
| 5 | 1/16 notes | 0.25 | Tight, most common for drums |
| 6 | 1/16 note triplets | 0.167 | Complex rhythms, hi-hat rolls |
| 7 | 1/16 + triplet | mixed | Combines straight 16ths and triplets |
| 8 | 1/32 notes | 0.125 | Very tight, trap hi-hats |

### Amount

The `amount` parameter (0.0 to 1.0) controls how far notes move toward the grid:

| Amount | Effect |
|--------|--------|
| 1.0 | Full quantize -- notes snap exactly to grid |
| 0.75 | Mostly quantized, some human feel remains |
| 0.5 | Halfway -- tighter but still loose |
| 0.25 | Light touch -- just cleans up the worst offenders |
| 0.0 | No effect |

### When to quantize and when to keep it loose

**Quantize (grid 5, amount 0.75-1.0):**
- Kick drums -- they need to hit precisely to anchor the groove
- Bass notes that lock with the kick
- Chord stabs in dance music
- Any pattern that sounds sloppy rather than loose

**Partial quantize (grid 5, amount 0.4-0.6):**
- Hi-hats and percussion -- keeps swing while removing chaos
- Boom bap drums -- too tight kills the feel
- Recorded MIDI performances that are close but not perfect

**Do not quantize:**
- Ghost notes -- their looseness is the point
- Intentionally humanized patterns (you just spent effort adding timing variation)
- Rubato or expressive passages
- Patterns you have already micro-shifted for groove

A common workflow: quantize the kick and snare to grid 5 at amount 1.0, then quantize the hats separately to grid 5 at amount 0.5. This locks the backbone while keeping the texture alive.

---

## 9. Euclidean Rhythms

Euclidean rhythms distribute a given number of hits as evenly as possible across a given number of steps. Many traditional rhythmic patterns from around the world turn out to be Euclidean.

### How it works

**E(k, n)** = k hits spread evenly across n steps.

| Pattern | Name / Origin | Resulting rhythm (x = hit, . = rest) |
|---------|--------------|--------------------------------------|
| E(3, 8) | Tresillo (Cuban) | x . . x . . x . |
| E(5, 8) | West African bell | x . x x . x x . |
| E(3, 4) | Cumbia | x . x x |
| E(4, 12) | | x . . x . . x . . x . . |
| E(5, 12) | | x . x . x . . x . x . . |
| E(7, 12) | West African bell (12/8) | x . x x . x . x x . x . |
| E(5, 16) | Bossa nova | x . . x . . x . . x . . x . . . |
| E(7, 16) | | x . x . x . x . . x . x . x . . |

### Calculating note positions

To place Euclidean hits in a clip:

```
step_position = step_index * (clip_length / total_steps)
```

**Example: E(3, 8) in a 4-beat (1 bar) clip:**
- The 3 hits land at steps 0, 3, 5 (from the Euclidean algorithm)
- Step 0: 0 * (4.0 / 8) = beat 0.0
- Step 3: 3 * (4.0 / 8) = beat 1.5
- Step 5: 5 * (4.0 / 8) = beat 2.5

```json
[
  {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 100},
  {"pitch": 36, "start_time": 1.5, "duration": 0.25, "velocity": 100},
  {"pitch": 36, "start_time": 2.5, "duration": 0.25, "velocity": 100}
]
```

That is the tresillo -- the rhythmic backbone of reggaeton, son cubano, and countless pop songs.

**Example: E(5, 8) in a 4-beat clip:**
- Hits at steps 0, 1, 3, 4, 6
- Positions: 0.0, 0.5, 1.5, 2.0, 3.0

```json
[
  {"pitch": 56, "start_time": 0.0, "duration": 0.25, "velocity": 90},
  {"pitch": 56, "start_time": 0.5, "duration": 0.25, "velocity": 75},
  {"pitch": 56, "start_time": 1.5, "duration": 0.25, "velocity": 90},
  {"pitch": 56, "start_time": 2.0, "duration": 0.25, "velocity": 75},
  {"pitch": 56, "start_time": 3.0, "duration": 0.25, "velocity": 90}
]
```

The West African bell pattern on a cowbell (56). The velocity accent on beats 0, 1.5, and 3.0 emphasizes the strong beats of the pattern.

### Using Euclidean rhythms in production

Euclidean patterns work best for:
- **Percussion layers** -- claves, shakers, cowbells, rimshots
- **Hi-hat variation** -- use E(5,16) or E(7,16) instead of straight 8ths or 16ths
- **Bass syncopation** -- E(3,8) tresillo bass is immediately musical
- **Polyrhythm** -- stack E(3,8) on one sound and E(5,8) on another for interlocking patterns

Combine with probability for generative results: give each Euclidean hit a probability of 0.7-0.8, and the pattern evolves each time through.

---

Next: [Sound Design](sound-design.md) | Back to [Manual](index.md)

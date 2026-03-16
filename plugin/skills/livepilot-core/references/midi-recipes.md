# MIDI Recipes — Patterns, Mappings & Techniques

Timeless MIDI programming knowledge for LivePilot. These patterns work across any version of Ableton Live and any genre. Use them as starting points — adapt to context, never apply rigidly.

## Drum Rack MIDI Mapping (General MIDI + Ableton Standard)

Ableton's Drum Rack maps MIDI notes to pads. The default layout (and General MIDI standard):

| Note | MIDI # | Element | Common Use |
|------|--------|---------|------------|
| C1 | 36 | Kick | Main kick drum |
| C#1 | 37 | Rim/Side Stick | Accent, Latin percussion |
| D1 | 38 | Snare | Main snare |
| D#1 | 39 | Clap | Layer with snare, upbeats |
| E1 | 40 | Snare (alt) | Ghost notes, rolls |
| F1 | 41 | Low Tom | Fills |
| F#1 | 42 | Closed Hi-Hat | Groove backbone |
| G1 | 43 | Mid Tom | Fills |
| G#1 | 44 | Pedal Hi-Hat | Foot splash |
| A1 | 45 | High Tom | Fills |
| A#1 | 46 | Open Hi-Hat | Off-beats, accents |
| B1 | 47 | Mid Tom (alt) | Fills |
| C2 | 48 | High Tom (alt) | Fills |
| C#2 | 49 | Crash | Accents, section starts |
| D2 | 50 | High Tom 2 | Fills |
| D#2 | 51 | Ride | Ride patterns |
| E2 | 52 | China | Effect crashes |
| F2 | 53 | Ride Bell | Accent ride |
| F#2 | 54 | Tambourine | Texture layer |
| G2 | 55 | Splash | Quick crashes |
| G#2 | 56 | Cowbell | Latin, accent |
| A2 | 57 | Crash 2 | Variety |
| B2 | 59 | Ride 2 | Variety |

**Ableton 808/electronic kits** often remap — always check `get_device_parameters` after loading a Drum Rack.

## Quantize Grid Values

The `quantize_clip` tool uses a `grid` parameter in beats:

| Grid | Value | Musical division |
|------|-------|-----------------|
| 1 bar | 4.0 | Whole note (at 4/4) |
| 1/2 | 2.0 | Half note |
| 1/4 | 1.0 | Quarter note |
| 1/8 | 0.5 | Eighth note |
| 1/16 | 0.25 | Sixteenth note |
| 1/32 | 0.125 | Thirty-second note |
| 1/4T | 0.667 | Quarter triplet |
| 1/8T | 0.333 | Eighth triplet |
| 1/16T | 0.167 | Sixteenth triplet |
| 1/4D | 1.5 | Dotted quarter |
| 1/8D | 0.75 | Dotted eighth |

`amount` controls how far notes snap toward the grid (0.0 = no change, 1.0 = full snap). Use 0.5-0.75 to tighten timing while keeping human feel.

## Beat Length Math (4/4 time)

| Bars | Beats | Typical use |
|------|-------|------------|
| 1 | 4.0 | Single pattern |
| 2 | 8.0 | Standard loop |
| 4 | 16.0 | Verse/chorus section |
| 8 | 32.0 | Extended section |
| 16 | 64.0 | Full arrangement section |

For other time signatures: bars × numerator = beats (e.g., 3/4 time: 4 bars = 12 beats).

## Genre Drum Patterns

### Four-on-the-floor (House, Techno, Disco)
```
Beat:    1    .    .    .    2    .    .    .    3    .    .    .    4    .    .    .
Kick:    X    .    .    .    X    .    .    .    X    .    .    .    X    .    .    .
Snare:   .    .    .    .    X    .    .    .    .    .    .    .    X    .    .    .
CHH:     X    .    X    .    X    .    X    .    X    .    X    .    X    .    X    .
OHH:     .    .    .    .    .    .    .    .    .    .    .    .    .    .    .    .
```
Notes (1 bar = 4.0 beats, 16th grid = 0.25):
- Kick: 36 at 0.0, 1.0, 2.0, 3.0 — vel 100-127
- Snare: 38 at 1.0, 3.0 — vel 100-120
- CHH: 42 at 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5 — vel 80-100

### Boom Bap (Hip-Hop)
```
Beat:    1    .    .    .    2    .    .    .    3    .    .    .    4    .    .    .
Kick:    X    .    .    .    .    .    X    .    .    .    .    .    .    .    .    .
Snare:   .    .    .    .    X    .    .    .    .    .    .    .    X    .    .    .
CHH:     X    .    X    .    X    .    X    .    X    .    X    .    X    .    X    .
```
Notes:
- Kick: 36 at 0.0, 1.5 — vel 110-127
- Snare: 38 at 1.0, 3.0 — vel 100-120
- CHH: 42 on eighth notes — vel 70-90, accent on beats

### Trap
```
Beat:    1    .    .    .    2    .    .    .    3    .    .    .    4    .    .    .
Kick:    X    .    .    .    .    .    X    X    .    .    .    .    .    .    X    .
Snare:   .    .    .    .    X    .    .    .    .    .    .    .    X    .    .    .
CHH:     XxXxXxXxXxXxXxXx    (rapid 16ths/32nds with velocity rolls)
```
Notes:
- Kick: 36 at 0.0, 1.5, 1.75, 3.5 — vel 110-127
- Snare/clap: 38+39 layered at 1.0, 3.0 — vel 100-127
- CHH: 42 on every 16th or 32nd — velocity ramps create rolls (see hi-hat section)

### Breakbeat (Drum & Bass, Jungle)
```
Beat:    1    .    .    .    2    .    .    .    3    .    .    .    4    .    .    .
Kick:    X    .    .    .    .    .    .    .    .    .    X    .    .    .    .    .
Snare:   .    .    .    .    X    .    .    .    .    .    .    .    .    .    X    .
CHH:     X    .    X    .    X    .    X    .    X    .    X    .    X    .    X    .
```
Notes (at 170 BPM for DnB):
- Kick: 36 at 0.0, 2.5 — vel 110-127
- Snare: 38 at 1.0, 3.5 — vel 100-120
- CHH: 42 on eighths — vel 70-90

### Reggaeton / Dembow
```
Beat:    1    .    .    .    2    .    .    .    3    .    .    .    4    .    .    .
Kick:    X    .    .    .    .    .    X    .    X    .    .    .    .    .    X    .
Snare:   .    .    .    X    .    .    .    X    .    .    .    X    .    .    .    X
CHH:     X    .    X    .    X    .    X    .    X    .    X    .    X    .    X    .
```

## Hi-Hat Techniques

### Velocity Rolls (Trap Style)
Create a ramp from low to high velocity over rapid notes:
```python
# 32nd note hi-hat roll building up over 1 beat
notes = []
for i in range(8):  # 8 x 32nd notes = 1 beat
    notes.append({
        "pitch": 42,
        "start_time": start + (i * 0.125),
        "duration": 0.1,
        "velocity": 40 + int(i * 11),  # 40 → 117 ramp
    })
```

### Open/Closed Alternation
Open hi-hat (46) and closed (42) alternate — in a real Drum Rack, they're in a choke group so open cuts when closed hits:
```
CHH: X . X . X . X .
OHH: . . . . . . . X    (open on the "and" of 4)
```
- Closed: vel 70-90, duration 0.1 (short)
- Open: vel 90-110, duration 0.25-0.5 (longer, ring out)

### Swing / Shuffle
Delay every other 16th note by a small amount (0.02-0.04 beats):
```python
for i in range(16):
    offset = 0.02 if i % 2 == 1 else 0.0  # swing the offbeats
    notes.append({
        "pitch": 42,
        "start_time": (i * 0.25) + offset,
        "duration": 0.1,
        "velocity": 90 if i % 4 == 0 else 70,  # accent downbeats
    })
```

## Ghost Notes

Quiet notes that add groove texture. Typically snare ghosts on 16th notes adjacent to main hits:

```python
# Ghost notes around main snare hits at beats 2 and 4
ghost_notes = [
    {"pitch": 40, "start_time": 0.75, "duration": 0.15, "velocity": 30},  # before beat 2
    {"pitch": 40, "start_time": 1.25, "duration": 0.15, "velocity": 25},  # after beat 2
    {"pitch": 40, "start_time": 2.75, "duration": 0.15, "velocity": 30},  # before beat 4
    {"pitch": 40, "start_time": 3.25, "duration": 0.15, "velocity": 25},  # after beat 4
]
```

Key principles:
- Velocity 20-50 (much quieter than main hits at 100-127)
- Use alternate snare sound (pitch 40) or same snare (38) at low velocity
- Place on 16th notes before/after main hits
- Uneven velocities feel more natural

## Humanization

### Velocity Variation
Add subtle randomness to velocity (±5-15 from base):
```python
import random
base_vel = 100
velocity = base_vel + random.randint(-10, 10)
velocity = max(1, min(127, velocity))
```

### Timing Micro-shifts
Shift note start times slightly off-grid (±0.005-0.02 beats):
- Drag kicks slightly early (-0.005) for urgency
- Delay snares slightly (+0.01) for laid-back feel
- Keep hi-hats on grid as rhythmic anchor

### Per-Note Probability (Live 12)
Use `modify_notes` to set probability < 1.0:
- Hi-hat fills: probability 0.5-0.7 (sometimes play, sometimes don't)
- Ghost notes: probability 0.3-0.6 (sparse, evolving)
- Main hits: probability 1.0 (always play)
- Generative beats: mix probabilities across the pattern for evolving grooves

## Chord Voicings (MIDI Pitch Values)

Middle C = MIDI 60 (C3). Each semitone = +1.

### Basic Triads (root position, root = C3/60)
| Chord | Notes | MIDI pitches |
|-------|-------|-------------|
| C major | C E G | 60, 64, 67 |
| C minor | C Eb G | 60, 63, 67 |
| C diminished | C Eb Gb | 60, 63, 66 |
| C augmented | C E G# | 60, 64, 68 |
| C sus2 | C D G | 60, 62, 67 |
| C sus4 | C F G | 60, 65, 67 |

### Seventh Chords
| Chord | Notes | Intervals from root |
|-------|-------|-------------------|
| Major 7 | 1 3 5 7 | +0, +4, +7, +11 |
| Minor 7 | 1 b3 5 b7 | +0, +3, +7, +10 |
| Dominant 7 | 1 3 5 b7 | +0, +4, +7, +10 |
| Diminished 7 | 1 b3 b5 bb7 | +0, +3, +6, +9 |
| Half-dim 7 | 1 b3 b5 b7 | +0, +3, +6, +10 |

### Extended Chords
| Chord | Intervals from root |
|-------|-------------------|
| Major 9 | +0, +4, +7, +11, +14 |
| Minor 9 | +0, +3, +7, +10, +14 |
| Dominant 9 | +0, +4, +7, +10, +14 |
| Add 9 | +0, +4, +7, +14 |
| 11th | +0, +4, +7, +10, +14, +17 |
| 13th | +0, +4, +7, +10, +14, +21 |

### Interval Quick Reference
| Interval | Semitones | Example (from C) |
|----------|-----------|------------------|
| Minor 2nd | 1 | C → C# |
| Major 2nd | 2 | C → D |
| Minor 3rd | 3 | C → Eb |
| Major 3rd | 4 | C → E |
| Perfect 4th | 5 | C → F |
| Tritone | 6 | C → F# |
| Perfect 5th | 7 | C → G |
| Minor 6th | 8 | C → Ab |
| Major 6th | 9 | C → A |
| Minor 7th | 10 | C → Bb |
| Major 7th | 11 | C → B |
| Octave | 12 | C → C |

### Voicing Strategies
- **Pads**: Spread voicings — wide intervals, notes across 2+ octaves. Start root low (C2/48), spread 3rd and 5th up.
- **Stabs**: Tight voicings — notes within one octave, rhythmic impact.
- **Bass + chord**: Root note on bass track (low octave), chord on separate track (mid octave).
- **Inversions**: Move lowest note up an octave. 1st inversion = 3-5-1, 2nd inversion = 5-1-3. Smoother voice leading between chords.

### Common Progressions (intervals from scale root)

| Name | Chords | Feel |
|------|--------|------|
| I-V-vi-IV | C G Am F | Pop, uplifting |
| ii-V-I | Dm7 G7 Cmaj7 | Jazz, sophisticated |
| i-iv-VII-III | Am Dm G C | Minor, emotional |
| I-vi-IV-V | C Am F G | Classic pop |
| vi-IV-I-V | Am F C G | Modern pop/EDM |
| i-III-VII-VI | Am C G F | Dark, driving |
| I-IV | C F | Dance, house |
| i-VII | Am G | Dark minimal |

To transpose: add semitones to all MIDI values. E.g., C major → D major: add 2 to every pitch.

## Bass Patterns

### Sub Bass (sustained)
```python
# One note per bar, low octave
{"pitch": 36, "start_time": 0.0, "duration": 3.75, "velocity": 100}
```

### Octave Bass (dance)
```python
# Alternating root and octave
notes = [
    {"pitch": 36, "start_time": 0.0, "duration": 0.4, "velocity": 110},
    {"pitch": 48, "start_time": 0.5, "duration": 0.4, "velocity": 90},
    {"pitch": 36, "start_time": 1.0, "duration": 0.4, "velocity": 110},
    {"pitch": 48, "start_time": 1.5, "duration": 0.4, "velocity": 90},
]
```

### Walking Bass
Move through chord tones: root → 3rd → 5th → octave (or chromatic approach notes).

### Staccato vs Legato
- **Staccato**: duration 0.1-0.2 (tight, percussive)
- **Legato**: duration fills gap to next note (smooth, flowing)
- **Portamento**: overlapping notes (duration extends past next note start) — triggers glide on monophonic synths

## Polymetric Patterns

Create two clips with different lengths — they cycle at different rates creating evolving patterns:

| Ratio | Clip A (beats) | Clip B (beats) | Realigns after |
|-------|---------------|---------------|----------------|
| 3:4 | 3.0 | 4.0 | 12 beats |
| 5:4 | 5.0 | 4.0 | 20 beats |
| 7:8 | 3.5 | 4.0 | 28 beats |
| 3:2 | 3.0 | 2.0 | 6 beats |

Create clips with `create_clip` using these lengths — Ableton loops them independently per track.

## Scale Patterns

### Common scales as semitone intervals from root
| Scale | Pattern | Notes (from C) |
|-------|---------|----------------|
| Major | 0,2,4,5,7,9,11 | C D E F G A B |
| Natural Minor | 0,2,3,5,7,8,10 | C D Eb F G Ab Bb |
| Harmonic Minor | 0,2,3,5,7,8,11 | C D Eb F G Ab B |
| Melodic Minor | 0,2,3,5,7,9,11 | C D Eb F G A B |
| Dorian | 0,2,3,5,7,9,10 | C D Eb F G A Bb |
| Mixolydian | 0,2,4,5,7,9,10 | C D E F G A Bb |
| Pentatonic Major | 0,2,4,7,9 | C D E G A |
| Pentatonic Minor | 0,3,5,7,10 | C Eb F G Bb |
| Blues | 0,3,5,6,7,10 | C Eb F F# G Bb |
| Whole Tone | 0,2,4,6,8,10 | C D E F# G# A# |
| Chromatic | 0-11 | All notes |

To generate notes in a scale: take root MIDI note + interval offsets, transpose to desired octave.

## Arpeggio Patterns

### Up pattern (C major triad)
```python
# 16th notes ascending
root = 60  # C3
intervals = [0, 4, 7, 12]  # root, 3rd, 5th, octave
for i, interval in enumerate(intervals):
    notes.append({
        "pitch": root + interval,
        "start_time": i * 0.25,
        "duration": 0.2,
        "velocity": 100 - (i * 5),  # slight decay
    })
```

### Common arpeggio styles
- **Up**: 1 → 3 → 5 → 8
- **Down**: 8 → 5 → 3 → 1
- **Up-Down**: 1 → 3 → 5 → 8 → 5 → 3
- **Random**: random order (use probability for generative)
- **Chord**: all notes simultaneously (stab)

Rate determines speed: 1/8 = 0.5 beat spacing, 1/16 = 0.25 beat spacing.

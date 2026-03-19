# Drop music21 — Replace with Pure Python Theory Engine

**Date:** 2026-03-19
**Status:** Approved (rev 3 — all review issues resolved)
**Scope:** Replace 100MB music21 dependency with ~350 lines of pure Python

## Problem

LivePilot v1.6.4 shipped 7 music theory tools powered by music21. But:
- music21 is ~100MB with heavy transitive deps (numpy, matplotlib)
- We use <1% of its API surface — just key detection, chord naming, interval math
- Claude already knows music theory from training — music21 is a calculator for things the LLM can reason about
- The optional dependency creates friction: users must `pip install music21` separately
- music21's first import takes 2-3s, slowing cold start
- music21 has a classical bias that doesn't match production music contexts

## Solution

New file `mcp_server/tools/_theory_engine.py` — zero-dependency pure Python module implementing the primitives our 7 tools actually need. The MCP tools in `theory.py` keep identical APIs and return formats.

**Output compatibility note:** Output is *functionally equivalent*, not byte-identical. Differences:
- `pitch_name()` always uses sharp spelling (`A#4` not `Bb4`) — music21 uses context-sensitive flats in flat-key contexts. This is acceptable since the output is for display/LLM interpretation, not round-trip parsing.
- K-S confidence values may differ slightly due to floating-point differences in Pearson correlation (same algorithm, same profiles).

## Architecture

```
theory.py (7 MCP tools — unchanged API)
    └── _theory_engine.py (pure Python music theory math)
            ├── detect_key()              — Krumhansl-Schmuckler with mode profiles
            ├── pitch_name()              — MIDI → "C4" (always sharp spelling)
            ├── parse_key()               — "A minor" → {tonic: 9, mode: "minor"}
            ├── get_scale_pitches()       — tonic + mode → pitch class set
            ├── build_chord()             — scale degree + key → concrete pitches
            ├── roman_figure_to_pitches() — "bVII7" + key → concrete MIDI pitches
            ├── roman_numeral()           — chord pitch classes → Roman figure
            ├── chord_name()              — pitch classes → "C major triad"
            ├── check_voice_leading()     — parallel 5ths/8ves, crossing, hidden 5th
            └── chordify()                — group notes by beat → list of chord dicts
```

## Engine Specification

### Constants

```python
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Full enharmonic mapping — every flat/double spelling → sharp canonical form
ENHARMONIC = {
    'Cb': 'B', 'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#',
    'Ab': 'G#', 'Bb': 'A#',
    'B#': 'C', 'E#': 'F',
    'Cbb': 'A#', 'Dbb': 'C', 'Ebb': 'D', 'Fbb': 'D#', 'Gbb': 'F',
    'Abb': 'G', 'Bbb': 'A',
    'C##': 'D', 'D##': 'E', 'E##': 'F#', 'F##': 'G', 'G##': 'A',
    'A##': 'B', 'B##': 'C#',
}

# Krumhansl-Schmuckler key profiles
# Major & minor: Krumhansl & Kessler (1982)
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

# Mode profiles: derived by rotating the major profile to the mode's
# starting degree. This is the standard approach used by Temperley (2007)
# and matches how music21 generates mode profiles internally.
# Dorian = major profile starting from degree 2, etc.
DORIAN_PROFILE     = MAJOR_PROFILE[2:] + MAJOR_PROFILE[:2]   # rotate by 2
PHRYGIAN_PROFILE   = MAJOR_PROFILE[4:] + MAJOR_PROFILE[:4]   # rotate by 4
LYDIAN_PROFILE     = MAJOR_PROFILE[5:] + MAJOR_PROFILE[:5]   # rotate by 5
MIXOLYDIAN_PROFILE = MAJOR_PROFILE[7:] + MAJOR_PROFILE[:7]   # rotate by 7
LOCRIAN_PROFILE    = MAJOR_PROFILE[11:] + MAJOR_PROFILE[:11]  # rotate by 11

MODE_PROFILES = {
    'major': MAJOR_PROFILE,
    'minor': MINOR_PROFILE,
    'dorian': DORIAN_PROFILE,
    'phrygian': PHRYGIAN_PROFILE,
    'lydian': LYDIAN_PROFILE,
    'mixolydian': MIXOLYDIAN_PROFILE,
    'locrian': LOCRIAN_PROFILE,
}

# Scale intervals (semitones from root)
SCALES = {
    'major':      [0,2,4,5,7,9,11],
    'minor':      [0,2,3,5,7,8,10],
    'dorian':     [0,2,3,5,7,9,10],
    'phrygian':   [0,1,3,5,7,8,10],
    'lydian':     [0,2,4,6,7,9,11],
    'mixolydian': [0,2,4,5,7,9,10],
    'locrian':    [0,1,3,5,6,8,10],
}

# Triad quality by scale degree (0-indexed)
TRIAD_QUALITIES = {
    'major':      ['major','minor','minor','major','major','minor','diminished'],
    'minor':      ['minor','diminished','major','minor','minor','major','major'],
    'dorian':     ['minor','minor','major','major','minor','diminished','major'],
    'phrygian':   ['minor','major','major','minor','diminished','major','minor'],
    'lydian':     ['major','major','minor','diminished','major','minor','minor'],
    'mixolydian': ['major','minor','diminished','major','minor','minor','major'],
    'locrian':    ['diminished','major','minor','minor','major','major','minor'],
}

# Chord interval patterns (semitones from root, normalized)
CHORD_PATTERNS = {
    (0,4,7):      'major triad',
    (0,3,7):      'minor triad',
    (0,3,6):      'diminished triad',
    (0,4,8):      'augmented triad',
    (0,2,7):      'sus2',
    (0,5,7):      'sus4',
    (0,4,7,11):   'major seventh',
    (0,3,7,10):   'minor seventh',
    (0,4,7,10):   'dominant seventh',
    (0,3,6,9):    'diminished seventh',
    (0,3,6,10):   'half-diminished seventh',
}

# Roman numeral labels
ROMAN_LABELS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
```

### Functions

#### `detect_key(notes, mode_detection=True) → dict`
- Build pitch-class histogram (12 bins) weighted by note duration
- For each of 12 possible tonics × N modes: rotate profile, compute Pearson correlation
- If `mode_detection=True`: test major + minor + 5 modes = 84 candidates
- If `mode_detection=False`: test major + minor only = 24 candidates
- Return: `{tonic: int, tonic_name: str, mode: str, confidence: float, alternatives: [{tonic, tonic_name, mode, confidence}]}`
- Pearson correlation: `r = Σ((x-x̄)(y-ȳ)) / √(Σ(x-x̄)² × Σ(y-ȳ)²)` — stdlib `math` only
- Alternatives sorted descending by confidence, top 8 returned

#### `pitch_name(midi) → str`
- Always uses sharp spelling: `NOTE_NAMES[midi % 12] + str(midi // 12 - 1)`
- `pitch_name(60)` → `"C4"`, `pitch_name(69)` → `"A4"`, `pitch_name(70)` → `"A#4"` (not "Bb4")

#### `parse_key(key_str) → dict`
- Parse: "C", "C major", "A minor", "D dorian", "f# minor", "Bb major", "gb minor"
- Normalize tonic through `ENHARMONIC` table: `Bb` → `A#` → tonic 10
- Complete flat → sharp mapping: Cb→B, Db→C#, Eb→D#, Fb→E, Gb→F#, Ab→G#, Bb→A#, B#→C, E#→F
- Return: `{tonic: int, mode: str}` where tonic is 0-11 (C=0, C#=1, ... B=11)
- Default mode: "major" if not specified

#### `get_scale_pitches(tonic, mode) → list[int]`
- Return pitch classes (0-11) for the scale: `[(tonic + iv) % 12 for iv in SCALES[mode]]`
- `get_scale_pitches(0, 'major')` → `[0, 2, 4, 5, 7, 9, 11]`

#### `build_chord(degree, tonic, mode) → dict`
- Build triad from scale degree (0-indexed, 0=I, 1=II, etc.)
- Root = scale pitch at `degree`, third = scale pitch at `(degree+2)%7`, fifth = scale pitch at `(degree+4)%7`
- Quality from `TRIAD_QUALITIES[mode][degree]`
- Return: `{root_pc: int, pitch_classes: [int], quality: str, root_name: str}`

#### `roman_figure_to_pitches(figure, tonic, mode) → dict`
- Parse a Roman numeral string like `"IV"`, `"bVII7"`, `"#ivo7"`, `"ii7"` into concrete MIDI pitches
- Parsing rules:
  - Leading `b` = flat (lower root by 1 semitone), `#` = sharp (raise by 1)
  - Case: uppercase = major quality, lowercase = minor quality
  - Trailing `7` = add diatonic 7th, `o7` = diminished 7th
  - Base numeral: I=0, II=1, ... VII=6 (maps to scale degree)
- Build chord from scale degree, apply chromatic alterations, add 7th if indicated
- Return: `{figure: str, root_pc: int, pitches: [str], midi_pitches: [int], quality: str}`
- Used by `suggest_next_chord` to convert progression map figures to concrete pitches

#### `roman_numeral(chord_pcs, tonic, mode) → dict`
- Match chord pitch classes against all 7 scale-degree triads
- For each degree: build expected triad, check if chord_pcs is a subset/match
- Detect inversions: if bass note (chord_pcs[0]) ≠ root → inversion
  - 1st inversion: bass = 3rd of chord
  - 2nd inversion: bass = 5th of chord
- Format: uppercase = major ("I", "IV", "V"), lowercase = minor ("ii", "iii", "vi"), ° = dim
- Return: `{figure: str, quality: str, degree: int, inversion: int, root_name: str}`

#### `chord_name(midi_pitches) → str`
- Normalize to pitch classes, find root via interval pattern matching
- Try all rotations of pitch classes against `CHORD_PATTERNS`
- Return: `"{root_name}-{pattern_name}"` e.g. "C-major triad", "A-minor seventh"
- Fallback for unrecognized patterns: `"{root_name} chord"` with pitch class list

#### `check_voice_leading(prev_pitches, curr_pitches) → list[dict]`
- Input: two sorted pitch lists (bass to soprano), from consecutive chords
- Extract outer voices: bass = `pitches[0]`, soprano = `pitches[-1]`
- Compute intervals as `(soprano - bass) % 12` (always positive, bass-to-soprano direction)
- Checks:
  - **Parallel 5th:** `prev_interval == 7 AND curr_interval == 7 AND both voices moved` (i.e., prev_bass ≠ curr_bass AND prev_soprano ≠ curr_soprano)
  - **Parallel 8ve:** `prev_interval % 12 == 0 AND curr_interval % 12 == 0 AND both voices moved` (same AND condition as parallel 5th)
  - **Voice crossing:** `curr_pitches[-1] < curr_pitches[0]` (soprano below bass in MIDI)
  - **Hidden 5th:** both voices moved in same direction (both deltas > 0 or both < 0) AND `curr_interval == 7`
- Returns: `[{type: "parallel_fifths"|"parallel_octaves"|"voice_crossing"|"hidden_fifth"}]`

#### `chordify(notes, quant=0.125) → list[dict]`
- Group notes by quantized beat position: `round(start_time / quant) * quant`
- Skip muted notes (`n.get("mute", False)`)
- Chord duration = `max(note["duration"] for note in group)`, minimum `quant`
- Return: `[{beat: float, duration: float, pitches: sorted([int]), pitch_classes: sorted(set([pc]))}]`

## Changes to `theory.py`

1. Remove ALL `from music21 import X` statements
2. Remove `_notes_to_stream()`, `_detect_key()`, `_pitch_name()`, `_parse_key_string()`, `_require_music21()`
3. Note: `test_theory.py` also imports `_notes_to_stream`, `_detect_key`, `_pitch_name` — these imports must be removed/replaced too
3. Replace with imports from `._theory_engine`
4. Tools work directly on note dicts from `get_notes` → pass to engine functions
5. Same 7 tools, same parameters, same return format — API is frozen

### Per-tool changes (internal only):

| Tool | Before (music21) | After (engine) |
|------|------------------|----------------|
| `analyze_harmony` | `s.chordify()` → `romanNumeralFromChord()` | `chordify(notes)` → `roman_numeral()` + `chord_name()` |
| `suggest_next_chord` | `RomanNumeral(fig, key).pitches` | `roman_figure_to_pitches(fig, tonic, mode)` |
| `detect_theory_issues` | `VoiceLeadingQuartet` | `check_voice_leading()` |
| `identify_scale` | `s.analyze('key')` | `detect_key(notes, mode_detection=True)` |
| `harmonize_melody` | `RomanNumeral(degree, key)` | `build_chord(degree, tonic, mode)` |
| `generate_countermelody` | `key.getScale().getPitches()` | `get_scale_pitches(tonic, mode)` |
| `transpose_smart` | `key.getScale().getPitches()` + pitch math | `get_scale_pitches()` + pitch math |

## Test Changes

### `tests/test_theory.py` — MCP tool integration tests
- Remove all `from music21 import` statements
- Update `TestNotesToStream` → `TestChordify` (test the engine's chordify via tools)
- Update `TestKeyDetection` to verify tool output format (not music21 objects)
- Update `TestRomanNumerals` to verify tool output format
- Update `TestPitchName` to test engine's `pitch_name()`
- Keep `TestTheoryToolsRegistered` (tool registration test) — unchanged
- `test_tools_contract.py` — zero changes (142 tools, 13 domains)

### New: `tests/test_theory_engine.py` — pure engine unit tests
Standalone tests for `_theory_engine.py`. No MCP server, no Ableton connection.

```
TestPitchName:
    test_middle_c:          pitch_name(60) == "C4"
    test_a440:              pitch_name(69) == "A4"
    test_sharp_spelling:    pitch_name(70) == "A#4"  (not "Bb4")
    test_low_range:         pitch_name(0) == "C-1"

TestParseKey:
    test_simple_major:      parse_key("C") == {tonic: 0, mode: "major"}
    test_minor:             parse_key("A minor") == {tonic: 9, mode: "minor"}
    test_flat_key:          parse_key("Bb major") == {tonic: 10, mode: "major"}
    test_dorian:            parse_key("D dorian") == {tonic: 2, mode: "dorian"}
    test_case_insensitive:  parse_key("f# minor") == {tonic: 6, mode: "minor"}

TestDetectKey:
    test_c_major_progression:  C-E-G + A-C-E + F-A-C + G-B-D → tonic=0, mode="major"
    test_confidence_range:     confidence between 0.0 and 1.0
    test_alternatives_sorted:  alternatives descending by confidence
    test_mode_detection:       D dorian input → mode="dorian" in top results

TestScalePitches:
    test_c_major:          get_scale_pitches(0, "major") == [0,2,4,5,7,9,11]
    test_a_minor:          get_scale_pitches(9, "minor") == [9,11,0,2,4,5,7]

TestBuildChord:
    test_c_major_triad:    build_chord(0, 0, "major") → root_pc=0, quality="major"
    test_a_minor_triad:    build_chord(5, 0, "major") → root_pc=9, quality="minor" (vi)

TestRomanNumeral:
    test_I_chord:          roman_numeral([0,4,7], 0, "major") → figure="I", quality="major"
    test_vi_chord:         roman_numeral([9,0,4], 0, "major") → figure="vi"
    test_inversion:        roman_numeral([4,7,0], 0, "major") → inversion=1

TestRomanFigureToPitches:
    test_IV:               roman_figure_to_pitches("IV", 0, "major") → midi has F,A,C
    test_bVII7:            roman_figure_to_pitches("bVII7", 0, "major") → Bb dom7
    test_ii7:              roman_figure_to_pitches("ii7", 0, "major") → D min7

TestChordName:
    test_major_triad:      chord_name([60,64,67]) == "C-major triad"
    test_minor_seventh:    chord_name([57,60,64,67]) contains "minor seventh"

TestVoiceLeading:
    test_parallel_fifths:  ([48,67],[50,69]) → finds parallel_fifths
    test_no_issues:        ([48,64],[47,67]) → empty list
    test_voice_crossing:   ([67,48]) → finds voice_crossing

TestChordify:
    test_groups_simultaneous:  notes at same time → single chord entry
    test_skips_muted:          muted notes excluded
    test_duration_is_max:      chord duration = max of group
```

## Documentation Updates

- `requirements.txt` — remove `# pip install music21>=9.3` comment
- All references to "requires music21" → "built-in, zero dependencies"
- SKILL.md theory section — remove music21 install note
- overview.md theory section — remove "Requires: pip install music21" line
- README.md theory row — remove "(requires music21)"
- CHANGELOG.md — entry for v1.6.5

## What We Lose

1. **Context-sensitive enharmonic spelling** — music21 returns "Bb4" in flat keys, our engine always returns "A#4". Functionally identical for MIDI pitch data; display-only difference.
2. **Exotic chord names** — music21's `pitchedCommonName` handles hundreds of chord types. Our `chord_name()` handles ~12 common patterns (triads, 7ths, sus, aug, dim). Edge case: a French augmented sixth won't get a name. Producers won't notice.
3. **30+ scale modes** — music21 tests against Hungarian minor, Japanese pentatonic, etc. We test 7 Western modes. Sufficient for 99.9% of Ableton production.
4. **Mode profile accuracy** — our mode profiles are rotations of the major profile (standard Temperley approach). Music21 may use independently calibrated mode profiles in some code paths. The difference is marginal for production music use.

## What We Gain

1. **Zero dependencies** — theory tools work on every install
2. **~100MB smaller** — no music21/numpy/matplotlib in .venv
3. **Instant cold start** — no 2-3s first-import delay
4. **Full control** — no classical music bias
5. **Debuggable** — ~350 lines vs 500K lines
6. **Cross-platform** — no compiled C extensions to worry about

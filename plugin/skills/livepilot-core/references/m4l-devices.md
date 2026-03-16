# Devices, Browser & Racks — Stock Instruments, Effects & MIDI Tools

Complete reference for Ableton Live's device ecosystem: browser organization, MIDI effects, rack systems, and how to find/load devices through LivePilot.

## Browser Organization

Ableton's browser is the source for all devices, presets, and samples. The `search_browser` and `get_browser_tree` tools navigate this structure.

### Top-Level Categories

| Category | Contains | Use with LivePilot |
|----------|---------|-------------------|
| **Sounds** | Instrument presets organized by character (Bass, Keys, Lead, Pad, etc.) | `search_browser("warm pad")` |
| **Drums** | Drum Rack presets (kits, single hits, percussion) | `search_browser("808 kit")` |
| **Instruments** | Raw instruments without presets (Analog, Wavetable, Operator, etc.) | `find_and_load_device("Wavetable")` |
| **Audio Effects** | All audio effects (Compressor, Reverb, EQ Eight, etc.) | `find_and_load_device("Compressor")` |
| **MIDI Effects** | MIDI processors (Arpeggiator, Chord, Scale, etc.) | `find_and_load_device("Arpeggiator")` |
| **Max for Live** | M4L instruments, effects, and tools | `search_browser("LFO max")` |
| **Plug-ins** | VST/AU plugins installed on the system | `search_browser("Serum")` |
| **Clips** | Pre-made clips (MIDI patterns, audio loops) | `search_browser("house beat")` |
| **Samples** | Audio samples organized by category | `search_browser("kick one shot")` |
| **Packs** | Content from installed Packs | `get_browser_items("Packs")` |
| **User Library** | User's saved presets, clips, samples | `get_browser_items("User Library")` |

### Audio Effects Sub-Categories

| Sub-Category | Devices |
|-------------|---------|
| **Dynamics** | Compressor, Glue Compressor, Limiter, Gate, Multiband Dynamics, Drum Buss |
| **EQ** | EQ Eight, EQ Three, Channel EQ |
| **Filter** | Auto Filter, Spectral Resonator |
| **Delay** | Delay, Echo, Grain Delay, Beat Repeat, Spectral Time |
| **Reverb** | Reverb, Convolution Reverb (M4L), Hybrid Reverb |
| **Distortion** | Saturator, Overdrive, Erosion, Redux, Pedal, Amp, Cabinet |
| **Modulation** | Chorus-Ensemble, Phaser-Flanger, Frequency Shifter, Ring Mod |
| **Utility** | Utility, Tuner, Spectrum, External Audio Effect |
| **Spatial** | Surround Panner (if available) |

### Instrument Sub-Categories

| Sub-Category | Devices |
|-------------|---------|
| **Synths** | Analog, Wavetable, Operator, Drift, Meld |
| **Samplers** | Simpler, Sampler |
| **Physical Modeling** | Tension, Collision, Electric |
| **Drums** | Drum Rack (container) |
| **Other** | Instrument Rack, External Instrument |

## MIDI Effects

MIDI effects go *before* the instrument in the device chain. They transform MIDI data before it reaches the sound generator.

### Arpeggiator
Transforms held chords into arpeggiated note sequences.

**Key parameters:**
- `Style` — Up, Down, UpDown, DownUp, Converge, Diverge, Con&Diverge, PinkyUp, PinkyUpDown, ThumbUp, ThumbUpDown, Random, Custom
- `Rate` — Speed of arpeggiation (1/1 to 1/32, including triplets and dotted)
- `Gate` — Note length as percentage of step length (1%-200%)
- `Steps` — Number of steps (1-8) for custom patterns
- `Offset` — Shift the start of the arpeggio pattern
- `Groove` — Amount of groove/swing applied
- `Transpose` — Pitch shift per octave repetition
- `Distance` — Interval distance for Transpose
- `Repeats` — Number of octave repetitions (1-inf)
- `Velocity` — Fixed velocity or follows input

**Common settings:**
- Basic up arp: Style=Up, Rate=1/8, Gate=80%, Repeats=2
- Trance arp: Style=UpDown, Rate=1/16, Gate=50%, Repeats=3
- Random generative: Style=Random, Rate=1/16, Gate=60%, Repeats=2

### Chord
Adds parallel intervals to incoming notes to build chords.

**Key parameters:**
- `Shift 1-6` — Semitone offset for each additional note (-36 to +36)
- `Velocity 1-6` — Velocity for each added note (1-127 or 0=off)

**Common settings:**
- Power chord (5th): Shift1=+7
- Major chord: Shift1=+4, Shift2=+7
- Minor chord: Shift1=+3, Shift2=+7
- Octave double: Shift1=+12
- Major 7th: Shift1=+4, Shift2=+7, Shift3=+11

### Note Length
Controls the duration and timing of MIDI notes.

**Key parameters:**
- `Mode` — Time-based (set fixed length) or Trigger (note-on generates fixed note)
- `Length` — Note duration (in ms or synced divisions)
- `Gate` — Percentage of original length
- `Timing` — Time delay or advance

**Use cases:**
- Force all notes to equal length (staccato patterns)
- Create gated synth effects
- Trigger one-shot samples consistently

### Pitch
Simple pitch transposition.

**Key parameters:**
- `Pitch` — Semitone offset (-48 to +48)
- `Range` — Limit the affected pitch range
- `Lowest` — Lower bound of affected range

### Random
Adds randomization to MIDI notes.

**Key parameters:**
- `Chance` — Probability that randomization occurs (0-100%)
- `Choices` — Number of possible random values (1-24)
- `Scale` — Semitone range of randomization
- `Mode` — Add (adds random offset), Toggle (randomly enables/disables notes), Randomize (random pitch within range)
- `Sign` — Bi (both directions), Add (only up), Sub (only down)

**Use cases:**
- Generative melody: moderate Chance, Scale=12 (octave), Choices=7 (diatonic)
- Humanize velocity: small random velocity offset
- Probability gates: Chance=50% creates evolving patterns

### Scale
Forces incoming MIDI to a specific musical scale.

**Key parameters:**
- `Base` — Root note (C, C#, D, etc.)
- `Scale Type` — Major, Minor, Dorian, Mixolydian, Pentatonic, Blues, Chromatic, etc.
- Per-note mapping grid — shows which notes map to which scale degrees

**Common scales:**
| Scale | Intervals (semitones from root) |
|-------|-------------------------------|
| Major | 0, 2, 4, 5, 7, 9, 11 |
| Minor (Natural) | 0, 2, 3, 5, 7, 8, 10 |
| Dorian | 0, 2, 3, 5, 7, 9, 10 |
| Mixolydian | 0, 2, 4, 5, 7, 9, 10 |
| Pentatonic Major | 0, 2, 4, 7, 9 |
| Pentatonic Minor | 0, 3, 5, 7, 10 |
| Blues | 0, 3, 5, 6, 7, 10 |
| Harmonic Minor | 0, 2, 3, 5, 7, 8, 11 |
| Whole Tone | 0, 2, 4, 6, 8, 10 |

**Tip:** Place Scale after Arpeggiator or Random to ensure generated notes stay in key.

### Velocity
Modifies note velocity.

**Key parameters:**
- `Drive` — Amplifies velocity curve
- `Compand` — Compresses (negative) or expands (positive) velocity range
- `Out Hi` / `Out Low` — Output velocity range limits
- `Random` — Adds random velocity offset
- `Operation` — Clip, Gate, Fixed

**Use cases:**
- Consistent velocity: Fixed at 100
- Dynamic compression: Compand negative, narrows velocity range
- Humanize: small Random value (5-15)

## Max for Live Devices (Stock with Suite)

### M4L Instruments
- **Drift** — Analog-modeled synth with character and instability
- **Meld** — MPE-capable dual-engine synth
- **Granulator II** — Granular synthesis instrument

### M4L Audio Effects
- **Convolution Reverb** — Impulse response reverb using real space recordings
- **Convolution Reverb Pro** — Extended version with EQ and modulation
- **Hybrid Reverb** — Combines convolution and algorithmic reverb
- **Spectral Resonator** — Spectral processing with pitched resonance
- **Spectral Time** — Spectral delay and freeze effects
- **PitchLoop89** — Creative pitch-shifting looper

### M4L MIDI Effects
- **Envelope MIDI** — Custom velocity/CC envelopes
- **Expression Control** — MPE expression mapping
- **Melodic Steps** — Step sequencer for melodies
- **MIDI Monitor** — Displays incoming MIDI data (debugging)

### M4L Tools & Utilities
- **LFO** — Free-running LFO that maps to any parameter
- **Envelope Follower** — Generates control signal from audio amplitude
- **Shaper** — Custom waveshaping LFO/envelope
- **DS Kick/Snare/HH/Clap/Cymbal** — Drum synthesis (drum rack compatible)
- **Instant Haus** — Auto-generates house beats

### M4L Control Surface Tools
- **Connection Kit** — OSC/MIDI routing tools
- **Max API** — Direct access to Live's API from Max

## Rack Systems

### Instrument Rack
- **Purpose**: Layer multiple instruments, create splits, build complex presets
- **Structure**: Multiple chains, each containing instruments and effects
- **Key features**:
  - **Chain selector** — Map MIDI velocity, note, or a selector value to different chains
  - **Key zones** — Different instruments for different pitch ranges (keyboard splits)
  - **Velocity zones** — Different instruments triggered by different velocity ranges
  - **Macros** — 8 (or 16 in Live 12) knobs that control parameters across all chains
- **Use case**: Layer a pad and a pluck — pad responds to low velocity, pluck to high

### Audio Effect Rack
- **Purpose**: Parallel processing, multi-band processing, A/B comparison
- **Structure**: Multiple chains, each with its own effect chain
- **Key features**:
  - **Parallel processing**: Audio splits to all chains simultaneously
  - **Chain selector**: Fade between different effect chains
  - **Macros**: Map to parameters across chains for unified control
- **Common patterns**:
  - Parallel compression (dry chain + compressed chain)
  - Multi-band processing (LP chain + BP chain + HP chain)
  - Wet/dry blend with effects
  - A/B comparison of different processing

### Drum Rack
- **Purpose**: Map samples/instruments to MIDI notes (pads)
- **Structure**: 128 pads (MIDI notes 0-127), each pad is a chain
- **Key features**:
  - **Choke groups**: Assign pads to groups — triggering one silences others (open/closed hi-hat)
  - **Send/return within rack**: Internal send effects shared between pads
  - **Pad chains**: Each pad has its own chain — sample + effects per pad
  - **Layering**: Multiple samples per pad by layering chains
  - **Receive note**: Each pad maps to a MIDI note
- **Standard mapping**: C1 (36) = Kick, D1 (38) = Snare, F#1 (42) = Closed HH (see midi-recipes.md)

### MIDI Effect Rack
- **Purpose**: Process MIDI in parallel or with velocity/key splitting
- **Structure**: Multiple chains of MIDI effects
- **Key features**:
  - Key zones for different MIDI processing per range
  - Velocity zones for velocity-dependent MIDI transformation
- **Common pattern**: Arpeggiator on high notes, Chord on low notes

### Macro Mapping
All rack types support macros:
- **Live 11 and earlier**: 8 macro knobs
- **Live 12**: Up to 16 macro knobs (expandable)
- **Mapping**: Right-click any parameter inside the rack → "Map to Macro X"
- **Ranges**: Each mapping has min/max values — macros can invert or limit parameter range
- **Use case**: One "Brightness" macro controlling filter cutoff, EQ, and reverb tone simultaneously

## Loading Devices with LivePilot

### `find_and_load_device` — Search by Name
Best for stock devices — searches browser and loads first match:
```
find_and_load_device(track_index=0, name="Wavetable")
find_and_load_device(track_index=0, name="Compressor")
find_and_load_device(track_index=0, name="Arpeggiator")
```

**Common device names** (exact search strings):
| Category | Device Names |
|----------|-------------|
| Synths | `Analog`, `Wavetable`, `Operator`, `Drift`, `Meld` |
| Samplers | `Simpler`, `Sampler` |
| Physical | `Tension`, `Collision`, `Electric` |
| Drums | `Drum Rack` |
| Dynamics | `Compressor`, `Glue Compressor`, `Limiter`, `Gate`, `Multiband Dynamics` |
| EQ | `EQ Eight`, `EQ Three`, `Channel EQ` |
| Filter | `Auto Filter` |
| Delay | `Delay`, `Echo`, `Grain Delay`, `Beat Repeat` |
| Reverb | `Reverb`, `Hybrid Reverb` |
| Distortion | `Saturator`, `Overdrive`, `Erosion`, `Redux`, `Pedal`, `Amp`, `Cabinet` |
| Modulation | `Chorus-Ensemble`, `Phaser-Flanger`, `Frequency Shifter` |
| Utility | `Utility`, `Tuner`, `Spectrum` |
| MIDI FX | `Arpeggiator`, `Chord`, `Note Length`, `Pitch`, `Random`, `Scale`, `Velocity` |
| Racks | `Instrument Rack`, `Audio Effect Rack`, `MIDI Effect Rack` |
| Drum | `Drum Buss` (audio effect, not Drum Rack) |

### `load_device_by_uri` — Load by URI
For specific presets or when you know the exact browser path:
```
load_device_by_uri(track_index=0, uri="...")
```
Get URIs by browsing with `search_browser` or `get_browser_items`.

### `search_browser` — Find Presets
Search for presets, sounds, and samples:
```
search_browser(query="warm pad")
search_browser(query="808 kick")
search_browser(query="techno lead")
```

### Device Chain Order
When loading multiple devices on a track, they're added in sequence. The order matters:

**MIDI Track chain:**
```
MIDI Effects → Instrument → Audio Effects
(Arpeggiator → Scale → Wavetable → Compressor → Reverb)
```

**Audio Track chain:**
```
Audio Effects only
(EQ Eight → Compressor → Saturator → Delay → Reverb)
```

Devices are indexed by position: first device = index 0, second = index 1, etc.

## Device Parameter Inspection

Always inspect parameters before setting them — parameter names and indices vary by device:

```
# Get all parameters for a device
get_device_parameters(track_index=0, device_index=0)

# Returns list of: name, value, min, max, is_quantized
# Use the exact name or index to set parameters
```

**Quantized parameters** (is_quantized=True) have discrete steps — set to integers or specific values from the allowed list. Examples: filter type selectors, waveform selectors, on/off toggles.

**Continuous parameters** (is_quantized=False) accept any float within min-max range. Examples: cutoff frequency, volume, drive amount.

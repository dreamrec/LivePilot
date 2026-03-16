# Ableton Live 12 — Devices, Browser & Rack Reference

Research compiled 2026-03-17 from ableton.com documentation, reference manuals, and API docs.

---

## 1. Stock Max for Live Devices (Ships with Live Suite)

### M4L Instruments — Drum Synths (DS Series)

| Device | Type | Description |
|--------|------|-------------|
| DS Kick | Drum Synth | Kick drum synthesizer |
| DS Snare | Drum Synth | Snare drum synthesizer |
| DS Clap | Drum Synth | Clap synthesizer |
| DS HH | Drum Synth | Hi-hat synthesizer |
| DS Cymbal | Drum Synth | Cymbal synthesizer |
| DS Tom | Drum Synth | Tom synthesizer |
| DS FM | Drum Synth | FM-based percussion synth |
| DS Clang | Drum Synth | Metallic percussion synth |
| DS Sampler | Drum Synth | Sample-based drum device |

### M4L Audio Effects

| Device | Category | Description |
|--------|----------|-------------|
| Align Delay | Utility | Precision alignment delay |
| Convolution Reverb | Reverb | Captures reverb of real physical spaces with advanced sound shaping |
| Convolution Reverb Pro | Reverb | Extended version with additional controls + utility for creating custom IRs |
| Envelope Follower | Modulation | Uses audio envelope to control device parameters |
| Gated Delay | Delay/Creative | Delay with gate sequencer that sends signal to delay on activated steps |
| LFO | Modulation | Low-frequency oscillator for parameter modulation |
| PitchLoop89 | Creative | Jittery glitch effects, delayed digital shimmers, outlandish vibrato |
| Shaper | Modulation | Waveshaping modulator |
| Color Limiter | Dynamics | Limiting inspired by hardware limiters with Saturation and Color params |

### M4L MIDI Effects

| Device | Category | Description |
|--------|----------|-------------|
| Envelope MIDI | Modulation | MIDI envelope generator |
| Expression Control | MPE/Control | Expression mapping for MPE controllers |
| Expression Control Legacy | MPE/Control | Legacy version of Expression Control |
| MIDI Monitor | Utility | Displays incoming MIDI data for debugging |
| MPE Control | MPE | MPE parameter control and mapping |
| Note Echo | MIDI Effect | MIDI note echo/delay |
| Shaper MIDI | Modulation | MIDI-rate waveshaper modulation |

### M4L MIDI Tools (Built-in with Live Standard + Suite)

| Device | Description |
|--------|-------------|
| Velocity Shaper | Shapes velocity curves of MIDI patterns |
| Euclidean | Euclidean rhythm generator |

### M4L Instruments (from Packs / Suite)

| Device | Description |
|--------|-------------|
| Bass | Monophonic virtual analog synthesizer for bass sounds |
| Granulator III | Robert Henke's granular synth — two granular playback modes, MPE modulation of grain size/shape/position |
| Vector Grain | Granular looper that visualizes sound modulation with particle interface |
| FlexGroove | Off-the-grid MIDI sequencer for expressive push-pull timing |

---

## 2. Stock Native Instruments (Not M4L)

| Instrument | Type | Edition | Key Features |
|------------|------|---------|--------------|
| Simpler | Sampler | All | Single-sample instrument, Classic/1-Shot/Slice modes |
| Sampler | Sampler | Suite | Multi-sample instrument, zones, modulation matrix |
| Analog | Subtractive Synth | Suite | Virtual analog, 2 oscillators, 2 filters, created w/ Applied Acoustics |
| Operator | FM Synth | Suite | 4-operator FM synthesis, flexible routing algorithms |
| Wavetable | Wavetable Synth | Suite | Wavetable synthesis, dual oscillators, sub oscillator |
| Collision | Physical Modeling | Suite | Mallet/resonator physical modeling |
| Tension | Physical Modeling | Suite | String physical modeling |
| Electric | Electric Piano | Suite | Tine/reed electric piano modeling |
| Drift | Analog Synth | Suite | Modern analog-style synth, MPE capable (new in Live 11/12) |
| Meld | Hybrid Synth | Suite | MPE-capable, 2 independent oscillators, extensive modulation matrix, textural soundscapes |

---

## 3. Stock Audio Effects (Native, Not M4L)

### Dynamics
| Device | Description |
|--------|-------------|
| Compressor | Versatile dynamics compressor |
| Glue Compressor | Bus compressor modeled on classic SSL design |
| Multiband Dynamics | 3-band dynamics processor (expansion, compression per band) |
| Limiter | Brick-wall limiter |
| Gate | Noise gate with sidechain |

### EQ & Filter
| Device | Description |
|--------|-------------|
| EQ Eight | 8-band parametric EQ with analyzer |
| EQ Three | DJ-style 3-band kill EQ |
| Channel EQ | Simple musical 3-band EQ (new in Live 10+), sidechain mono summing |
| Auto Filter | Resonant filter with LFO — overhauled in Live 12.2 with Resampling, Comb, Vowel, DJ filter types |

### Delay
| Device | Description |
|--------|-------------|
| Delay | Simple stereo delay |
| Echo | Modulation delay with envelope and filter modulation, dual independent delay lines |
| Filter Delay | 3-tap delay with independent filters per tap |
| Grain Delay | Granular delay effect |

### Reverb
| Device | Description |
|--------|-------------|
| Reverb | Algorithmic reverb |
| Hybrid Reverb | Convolution + algorithmic reverb in one device |

### Distortion & Saturation
| Device | Description |
|--------|-------------|
| Saturator | Waveshaping saturation with multiple curves |
| Overdrive | Analog-style overdrive |
| Amp | Guitar amplifier modeling |
| Cabinet | Speaker cabinet modeling (pairs with Amp) |
| Erosion | Digital degradation effect (aliasing, noise) |
| Redux | Bit crushing and sample rate reduction |
| Roar | 3-stage saturation — series/parallel/mid-side/multiband, feedback generator, modulation matrix (new in Live 12) |
| Pedal | Guitar pedal effects (Overdrive, Distortion, Fuzz) |

### Modulation
| Device | Description |
|--------|-------------|
| Chorus-Ensemble | Chorus effect (updated from Chorus in Live 11) |
| Phaser-Flanger | Combined phaser/flanger (updated from separate devices in Live 11) |
| Frequency Shifter | Frequency shifting and ring modulation |
| Auto Pan | Tremolo and auto-panning with LFO |

### Spectral (Suite Only)
| Device | Description |
|--------|-------------|
| Spectral Resonator | Spectral processing with resonant frequencies, granular mode |
| Spectral Time | Spectral delay and freeze effects |

### Creative / Performance
| Device | Description |
|--------|-------------|
| Beat Repeat | Glitch/stutter effect triggered by beat position |
| Corpus | Resonant body physical modeling (membrane, plate, tube) |
| Looper | Live looping pedal device |
| Vinyl Distortion | Vinyl noise and distortion emulation |
| Re-Enveloper | Dynamic envelope reshaping (envelope hold toggle for attack completion) |

### Utility
| Device | Description |
|--------|-------------|
| Utility | Gain, stereo width, phase, channel routing |
| Tuner | Chromatic tuner for audio input |
| Spectrum | FFT spectrum analyzer |
| External Audio Effect | Routes to external hardware processor |

---

## 4. Stock MIDI Effects (Native, Not M4L)

### Arpeggiator
- **Rate**: Speed of arpeggiation (ms or tempo-synced beat divisions, via Sync/Free toggle)
- **Style/Pattern**: Up, Down, UpDown, DownUp, Converge, Diverge, Con & Diverge, Pinky Up, Pinky UpDown, Thumb Up, Thumb UpDown, Random, Random Other (no immediate repeats), Random Once (one random pattern, repeats until input changes), Chord (plays all notes simultaneously)
- **Gate**: Note length as % of Rate (>100% = legato/overlap)
- **Transposition**: Distance (semitones or scale degrees) + Steps (number of transposed repeats, progressively higher/lower)
- **Velocity**: Toggle to enable. Decay (time to reach Target), Target velocity value. Long Decay + Target 0 = gradual fade-out
- **Offset**: Shifts arpeggiation start position within held notes
- **Repeats**: Number of times the pattern repeats before transposing
- **Scale Awareness**: "Use Current Scale" toggle — applies clip's scale, allows scale-degree parameter adjustment

### Chord
- **Shift 1-6**: Each adds a pitch offset in semitones (range: +/-36 semitones)
- **Velocity 1-6**: Velocity adjustment for each shifted note
- Example: Shift 1 = +4, Shift 2 = +7 yields a major chord
- **Scale Awareness**: "Use Current Scale" toggle for scale-degree shifting

### Note Length
- **Length**: Fixed duration in ms or synced beat divisions
- **Gate**: Percentage of original note length (when in relative mode)
- **Trigger Mode**: Toggle between Note On and Note Off triggering
- **Decay/Key Scale**: Release envelope options

### Pitch
- **Pitch**: Transposition in semitones (range: +/-128)
- **Range**: Random pitch offset range
- **Lowest/Highest**: Clamp output to pitch range
- **Scale Awareness**: "Use Current Scale" toggle for scale-degree transposition

### Random
- **Chance**: Probability (0-100%) that a note is randomized
- **Choices**: Number of possible random values
- **Scale**: Range of randomization in semitones
- **Mode**: Add (offset) or Absolute (replace pitch)
- **Sign**: Bi (both directions), Add (up only), Sub (down only)
- **Scale Awareness**: "Use Current Scale" toggle

### Scale
- **Base**: Root note (C through B)
- **Scale Type**: Major, Minor (Natural/Harmonic/Melodic), Dorian, Mixolydian, Phrygian, Lydian, Locrian, Whole Tone, Half-Whole Dim, Whole-Half Dim, Minor Blues, Minor Pentatonic, Major Pentatonic, Harmonic Minor, Harmonic Major, Chromatic, and more
- **Fold/Nearest**: How out-of-scale notes are mapped — fold to nearest scale degree vs. block
- **Scale Awareness**: "Use Current Scale" toggle

### Velocity
- **Mode**: Clip (compress/expand range), Gate (fixed range), Fixed (constant velocity), Random (random within range)
- **Out Low / Out High**: Output velocity range
- **Curve**: Response curve shape
- **Drive**: Amplification factor
- **Compand**: Compression/expansion of velocity curve
- **Random**: Random velocity offset range (0-64)
- **Lowest/Highest**: Filter notes below/above velocity thresholds

### CC Control (New in Live 12)
- Sends MIDI CC messages based on input
- Maps MIDI input to CC output values

---

## 5. Browser Organization (Live 12)

### Top-Level Categories (Labels)

| Category | Contents |
|----------|----------|
| **All** | Everything from every label |
| **Sounds** | All Instrument Racks and instrument presets |
| **Drums** | All drum presets, default drum devices, drum presets, drum samples |
| **Instruments** | Default Live instruments and their presets (organized by device type) |
| **Audio Effects** | Default Live audio effect devices and presets |
| **MIDI Effects** | Default Live MIDI effect devices and presets |
| **Modulators** | Default Live modulator devices (LFO, Shaper, Envelope Follower, etc.) |
| **Max for Live** | All Max for Live devices and presets |
| **Plug-Ins** | Third-party VST and Audio Units plug-ins |
| **Clips** | All Live Clips |
| **Samples** | All raw audio samples |
| **Grooves** | All groove templates |
| **Templates** | All template Live Sets |
| **Tunings** | All tuning systems (new in Live 12) |

### Browser Features (Live 12)
- **Tags**: Content is pre-tagged for identification; customizable via Tag Editor
- **Collections**: Up to 7 color-coded customizable categories for favorites/quick access
- **Search**: Text search across all browser content
- **Hot-Swap**: Button on devices to swap presets/devices inline

### Sounds Category — Preset Sub-Categories
Organized by sonic character/use:
- Bass, Brass, Guitar & Plucked, Keys, Lead, Mallet, Organ, Pad, Piano & Keys, Strings, Synth, Vocal & Choir, Winds, Other

### Drums Category — Sub-Categories
- Drum Hits (Kick, Snare, HH, Clap, Percussion, Tom, Cymbal)
- Drum Racks (by genre: Acoustic, Electronic, Lo-Fi, etc.)
- Drum presets by device

### Audio Effects — Browser Sub-Categories
- Delay, Distortion, Dynamics, EQ, Filter, Modulation, Reverb, Spectral, Utility, Pitch/Frequency

---

## 6. Device URI Patterns

### Browser API (Python, ControlSurface / Remote Script)

The Live Object Model exposes the Browser with these key classes:

```python
# Browser class (accessed via song.application.browser or self.application().browser)
class Browser:
    # Top-level category access
    instruments        # BrowserItem — root of Instruments tree
    audio_effects      # BrowserItem — root of Audio Effects tree
    midi_effects       # BrowserItem — root of MIDI Effects tree
    max_for_live       # BrowserItem — root of M4L tree
    sounds             # BrowserItem — root of Sounds tree
    drums              # BrowserItem — root of Drums tree
    plugins            # BrowserItem — root of Plug-ins tree
    samples            # BrowserItem — root of Samples tree
    clips              # BrowserItem — root of Clips tree
    packs              # BrowserItem — root of Packs tree
    user_library       # BrowserItem — root of User Library tree

    # Methods
    load_item(item: BrowserItem)     # Loads item onto selected track
    hotswap_target                    # Current hotswap target (observable)
    filter_type                       # Current browser filter (observable)

# BrowserItem class
class BrowserItem:
    name        # str — display name
    uri         # str — unique identifier (the device URI)
    is_device   # bool — True if this represents a loadable device
    is_loadable # bool — True if can be loaded via load_item()
    is_folder   # bool — True if this is a category/folder
    children    # tuple of BrowserItem — child items in hierarchy
    source      # str — source location
```

### Known URI Patterns

URIs follow these general formats (based on community documentation and API exploration):

| URI Pattern | Example | Notes |
|-------------|---------|-------|
| `query:Instruments` | Top-level instruments category | Browser filter category |
| `query:AudioEffects` | Top-level audio effects category | Browser filter category |
| `query:MidiEffects` | Top-level MIDI effects category | Browser filter category |
| `query:Drums` | Top-level drums category | Browser filter category |
| `query:Sounds` | Top-level sounds category | Browser filter category |

**Device-specific URIs** are opaque strings assigned by Ableton internally. They cannot be constructed — they must be discovered by walking the browser tree. The `find_and_load_device` tool in LivePilot handles this by:
1. Walking `browser.instruments.children` (or `audio_effects`, `midi_effects`, etc.)
2. Matching by name substring (case-insensitive)
3. Checking `is_loadable` flag
4. Calling `browser.load_item(matched_item)`
5. Max tree depth of 4, 5-second timeout

### Programmatic Device Loading Pattern

```python
# In Remote Script (ControlSurface context):
browser = self.application().browser

# Walk the tree to find a device
def find_device(root_item, name, depth=0, max_depth=4):
    if depth > max_depth:
        return None
    for child in root_item.children:
        if name.lower() in child.name.lower() and child.is_loadable:
            return child
        result = find_device(child, name, depth + 1, max_depth)
        if result:
            return result
    return None

# Find and load
item = find_device(browser.instruments, "Drift")
if item:
    browser.load_item(item)
    # Device appears on currently selected track
```

---

## 7. Rack Types

### Instrument Rack
- **Purpose**: Combines instruments with MIDI and audio effects into a single device
- **Signal flow**: MIDI Effects -> Instrument -> Audio Effects (must be in this order)
- **Chains**: Multiple parallel chains, each with independent device chains
- **Chain Selector**: Zone-based key/velocity/chain selection for layering and splitting
- **Macros**: Up to 16 macro knobs mapped to any parameter across all chains
- **Use cases**: Layered instruments, keyboard splits, complex sound design

### Audio Effect Rack
- **Purpose**: Combines multiple audio effects with parallel processing
- **Placement**: Audio tracks, or after an instrument on MIDI tracks
- **Chains**: Multiple parallel chains for parallel processing
- **Chain Selector**: Zone-based routing for splitting signal
- **Macros**: Up to 16 macro knobs
- **Use cases**: Parallel compression, multi-band processing, effect layering

### Drum Rack
- **Purpose**: 128-pad instrument rack optimized for drums/percussion
- **Pad View**: Each pad = one MIDI note (0-127), can hold instrument + effects chain
- **Chains**: Each pad is a chain with its own instrument, MIDI effects, audio effects
- **Per-Pad**: Individual volume, pan, send levels, MIDI assignment, choke groups
- **Macros**: Up to 16 macro knobs
- **Receives**: Internal send/return chains within the rack
- **Use cases**: Drum kits, sample triggering, chromatic percussion setups

### MIDI Effect Rack
- **Purpose**: Combines multiple MIDI effects with parallel processing
- **Placement**: MIDI tracks only, before instruments
- **Chains**: Multiple parallel MIDI effect chains
- **Macros**: Up to 16 macro knobs
- **Use cases**: Complex arpeggiator setups, MIDI transformation chains, layered MIDI routing

### Common Rack Features
- **Chain Activator**: Enable/disable individual chains
- **Solo/Mute**: Per-chain solo and mute
- **Macro Mapping**: Right-click any parameter -> Map to Macro; supports min/max range per mapping
- **Save as Preset**: Entire rack (with all devices and mappings) saves as a single .adg preset
- **Nested Racks**: Racks can contain other racks for complex routing
- **Key/Velocity Zones**: Each chain has key zone (pitch range) and velocity zone for dynamic layering
- **Chain Select Zone**: Allows automatable crossfading between chains

---

## 8. Arpeggiator Detailed Styles (18 Patterns)

The Arpeggiate Transformation in Live 12 offers these 18 style patterns:

1. **Up** — Lowest to highest pitch
2. **Down** — Highest to lowest pitch
3. **UpDown** — Ascending then descending (includes endpoints twice)
4. **DownUp** — Descending then ascending
5. **Up & Down** — Ascending then descending (endpoints played once)
6. **Down & Up** — Descending then ascending (endpoints played once)
7. **Converge** — Alternates between lowest and highest, moving inward
8. **Diverge** — Starts from middle, alternates outward
9. **Con & Diverge** — Converge then diverge
10. **Pinky Up** — Highest note repeated, ascending through others
11. **Pinky UpDown** — Highest note repeated, ascending then descending
12. **Thumb Up** — Lowest note repeated, ascending through others
13. **Thumb UpDown** — Lowest note repeated, ascending then descending
14. **Random** — Continuously randomized
15. **Random Other** — Random but no immediate note repeats
16. **Random Once** — One random pattern generated, repeats until input changes
17. **Chord** — All held notes play simultaneously
18. **Chord Trigger** — Chord triggered rhythmically

---

## Sources

- [Max for Live Devices Reference Manual v12](https://www.ableton.com/en/live-manual/12/max-for-live-devices/)
- [Live Audio Effect Reference v12](https://www.ableton.com/en/manual/live-audio-effect-reference/)
- [Live MIDI Effect Reference v12](https://www.ableton.com/en/manual/live-midi-effect-reference/)
- [Live Instrument Reference v12](https://www.ableton.com/en/manual/live-instrument-reference/)
- [Instrument, Drum and Effect Racks v12](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/)
- [Working with the Browser v12](https://www.ableton.com/en/live-manual/12/working-with-the-browser/)
- [The Live 12 Browser (Help)](https://help.ableton.com/hc/en-us/articles/12927340213660-The-Live-12-Browser)
- [Browser and Tags FAQ](https://help.ableton.com/hc/en-us/articles/11425042663708-Browser-and-Tags-in-Live-12-FAQ)
- [Max for Live Overview](https://www.ableton.com/en/live/max-for-live/)
- [All New Features in Live 12](https://www.ableton.com/en/live/all-new-features/)
- [Live 12 Release Notes](https://www.ableton.com/en/release-notes/live-12/)
- [Live API Documentation (Structure Void)](https://structure-void.com/PythonLiveAPI_documentation/Live10.0.1.xml)
- [AbletonLive-API-Stub (GitHub)](https://github.com/cylab/AbletonLive-API-Stub/blob/master/Live.xml)
- [MIDI Tools Reference v12](https://www.ableton.com/en/live-manual/12/midi-tools/)

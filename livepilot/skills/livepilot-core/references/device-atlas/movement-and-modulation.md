# Movement & Modulation — Device Atlas

Deep reference for chorus, phaser, flanger, pitch shifting, tremolo, panning, LFOs, envelope followers, loopers, and advanced M4L modulators available in this Live set.

---

## 1. Chorus-Ensemble (Native)

**Category:** Audio Effects > Modulation
**Introduced:** Live 11 (replaces legacy Chorus). Updated in Live 12.4 with improved delay time and structure controls.
**URI:** `Audio Effects/Modulation/Chorus-Ensemble`

### What It Does
Duplicates the incoming signal, applies time-modulated delays with subtle pitch variation to create width, thickness, and movement. Three distinct algorithms cover classic chorus, lush ensemble, and pitch vibrato.

### Modes

| Mode | Algorithm | Character |
|------|-----------|-----------|
| **Classic** | Two time-modulated delay lines | Traditional chorus — subtle doubling and width |
| **Ensemble** | Three delay lines with evenly split phase offsets (120 deg apart) | Thick, rich, '70s string-ensemble warmth |
| **Vibrato** | Single modulated delay, 100% wet | Pitch wobble — sine-to-triangle morph via Shape |

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Mode | Classic, Ensemble, Vibrato | Top selector |
| Rate | Hz (free) | Modulation speed of delay lines |
| Amount | 0-100% | Amplitude of modulation signal affecting delay times |
| Feedback | bipolar (invertible via phase button) | Channel output fed back to input; independent per L/R channel |
| Output | dB | Gain applied to processed signal |
| Warmth | 0-100% | Adds distortion + filtering ("more crunch") |
| Dry/Wet | 0-100% | Disabled in Vibrato mode (always 100% wet) |
| High-Pass Filter | 20 Hz - 2000 Hz | Reduces chorus effect below set frequency |
| Width | 0-200% (Classic/Ensemble only) | Stereo spread of wet signal; 0% = mono, 100% = balanced, 200% = sides 2x louder than center |
| Offset | 0-180 deg (Vibrato only) | Phase offset between L/R channels |
| Shape | continuous (Vibrato only) | Morphs waveform from sine to triangle |

### LivePilot Usage
```
find_and_load_device("Chorus-Ensemble")
set_device_parameter(track_index, device_index, "Rate", 1.2)
set_device_parameter(track_index, device_index, "D/W", 40)
```

### Tips
- Ensemble mode at low Rate (0.3-0.8 Hz) with moderate Amount gives classic string-machine sound.
- Vibrato mode with Shape toward triangle + fast Rate creates lo-fi pitch wobble.
- Use High-Pass Filter at 200-400 Hz to keep bass tight.
- Width at 200% is aggressive — useful on returns, risky on individual tracks.

---

## 2. Phaser-Flanger (Native)

**Category:** Audio Effects > Modulation
**Introduced:** Live 11 (replaces legacy Phaser and Flanger as separate devices).
**URI:** `Audio Effects/Modulation/Phaser-Flanger`

### What It Does
Combines phaser (allpass-filter notches), flanger (short modulated delay), and doubler (short fixed delay with modulation) in a single device. Features LFO, envelope follower, Earth/Space voicing, and Warmth saturation.

### Modes

| Mode | Mechanism | Character |
|------|-----------|-----------|
| **Phaser** | Cascaded allpass filters creating spectral notches | Sweeping, psychedelic, jet-like |
| **Flanger** | Short modulated delay mixed with dry signal | Metallic, jet-engine, comb-filter resonance |
| **Doubler** | Short modulatable delay (no feedback) | Subtle thickening, ADT, micro-pitch detune |

### Sub-Modes (Earth / Space)

| Sub-Mode | Effect |
|----------|--------|
| **Earth** | Evenly spaced notches — natural, classic voicing |
| **Space** | Unevenly spaced notches — exotic, alien, more colorful |

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Mode | Phaser, Flanger, Doubler | Top selector |
| Earth / Space | toggle | Changes notch spacing algorithm |
| Notches | 2-42 (Phaser mode) | Number of spectral notches |
| Center | Hz | Center frequency from which notches radiate |
| Spread | continuous | Spacing between notches |
| Blend | 0-100% | Crossfade of LFO modulation between Center and Spread |
| Feedback | bipolar | Amount of signal fed back; negative values invert phase |
| Color | continuous | Adds tonal character / distortion in feedback path |
| Warmth | 0-100% | Analog-style saturation and filtering |
| Safe Bass | on/off | High-pass filter protecting low frequencies from modulation |
| Width | 0-200% | Stereo spread of wet signal |
| Dry/Wet | 0-100% | Mix balance |
| **LFO Rate** | Hz or synced divisions | Modulation speed |
| **LFO Amount** | 0-100% | Depth of LFO modulation; 0% = frozen (manual sweep) |
| **LFO Shape** | sine, triangle, etc. | Waveform selector |
| **LFO Offset** | degrees | Phase offset between L/R |
| **LFO Spin** | Hz offset | Speeds up one channel relative to other |
| **Env Amount** | bipolar | Envelope follower depth |
| **Env Attack** | ms | Envelope follower attack time |
| **Env Release** | ms | Envelope follower release time |

### LivePilot Usage
```
find_and_load_device("Phaser-Flanger")
set_device_parameter(track_index, device_index, "Mode", "Flanger")
set_device_parameter(track_index, device_index, "Feedback", 60)
```

### Tips
- Doubler mode at 0% LFO Amount with slight Center offset gives static ADT doubling.
- Flanger + Space + high Feedback = aggressive metallic resonance.
- Phaser with 4-8 notches is musical; 20+ notches is extreme.
- Freeze the LFO (Amount = 0) and automate Center for manual filter sweeps.

---

## 3. Shifter (Native)

**Category:** Audio Effects > Modulation
**Introduced:** Live 11.1 (replaces legacy Frequency Shifter).
**URI:** `Audio Effects/Modulation/Shifter`

### What It Does
Real-time pitch/frequency shifting with built-in LFO, envelope follower, delay with feedback, stereo width controls, and MIDI sidechain for melodic pitch control.

### Pitch Modes

| Mode | Unit | Character |
|------|------|-----------|
| **Pitch** | Semitones | Musical pitch shifting (chromatic) |
| **Freq** | Hz | Wide-range frequency shifting (non-harmonic) |
| **Ring** | Hz | Ring modulation — shifts both up and down simultaneously; includes Drive |

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Mode | Pitch, Freq, Ring | Top selector |
| Coarse | semitones (Pitch mode) / Hz (Freq/Ring) | Main shift amount |
| Fine | cents | Fine tuning; replaced by Spread when Wide enabled |
| Wide | on/off | Enables stereo spread (L up / R down or vice versa) |
| Spread | cents (replaces Fine when Wide on) | Stereo pitch divergence |
| Window | continuous | Processing window size; longer = better for low freq, shorter = better for high freq |
| Tone | continuous | Low-pass filter in delay feedback path |
| Delay Time | ms or note values | Delay line time |
| Delay Feedback | 0-100% | Creates pitch-shifting delay cascades |
| Dry/Wet | 0-100% | Mix balance |
| **LFO Waveform** | 10 shapes (incl. 2 random) | Shape selector |
| **LFO Rate** | 0.01-50 Hz or synced divisions | Modulation speed |
| **LFO Amount** | +/- 24 semitones | Modulation depth |
| **LFO Phase** | 0-360 deg | Right channel delay; switchable to Spin mode |
| **LFO Spin** | Hz offset | Relative speed difference between channels |
| **LFO Duty Cycle** | continuous | Waveform distortion |
| **LFO Width** | continuous (S&H waveform only) | Smoothing of random steps |
| **Env Amount** | +/- 24 semitones | Envelope follower depth |
| **Env Attack** | ms | Envelope attack |
| **Env Release** | ms | Envelope release |
| **Sidechain** | Internal / MIDI | Source for pitch control |
| **Glide** | ms (MIDI mode) | Portamento between notes |
| **Pitchbend** | semitones (MIDI mode) | Maximum pitch bend range |

### LivePilot Usage
```
find_and_load_device("Shifter")
set_device_parameter(track_index, device_index, "Coarse", 7)  # shift up a fifth
set_device_parameter(track_index, device_index, "D/W", 50)
```

### Tips
- Ring mode + Drive creates aggressive metallic textures.
- MIDI sidechain turns any audio into a monophonic melodic instrument.
- Freq mode at small values (1-5 Hz) creates subtle beating / detuning.
- Delay + Feedback with pitch shift creates shimmer reverb-like cascades.

---

## 4. Auto Pan-Tremolo (Native)

**Category:** Audio Effects > Modulation
**Introduced:** Live 1.x as Auto Pan; renamed and expanded to Auto Pan-Tremolo in Live 12.3 with Tremolo-specific modes and Dynamic Frequency Modulation.
**URI:** `Audio Effects/Modulation/Auto Pan` (device name may appear as "Auto Pan" in browser)

### What It Does
LFO-driven amplitude modulation for stereo panning and tremolo effects with multiple waveform shapes, sync modes, and dynamic response.

### Modes

| Mode | What It Modulates |
|------|------------------|
| **Panning** | Stereo placement (L/R balance) via dual LFOs |
| **Tremolo** | Volume amplitude via single LFO |

### Tremolo Sub-Modes

| Sub-Mode | Character |
|----------|-----------|
| **Normal** | Standard amplitude modulation |
| **Harmonic** | Alternates modulation across high/low frequency bands (fixed crossover at 600 Hz) |
| **Vintage** | Non-linear curve adding warmth and grit |

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Mode | Panning, Tremolo | Top selector |
| Tremolo Type | Normal, Harmonic, Vintage | Tremolo mode only |
| Waveform | Sine, Triangle, Shark Tooth, Saw Up, Saw Down, Square, Random, Wander, S&H | LFO shape |
| Time Mode | Rate (Hz), Time (up to 200s), Synced, Dotted, Triplet, 16th | LFO timing |
| Amount | 0-100% | LFO modulation depth |
| Shape | bipolar continuous | Positive = rounded peaks; negative = angular/compressed peaks. Extreme values create gating/pumping |
| Stereo Offset | Phase (0-180 deg) or Spin | Phase offset or speed differential between L/R |
| Phase Offset | degrees (synced modes only) | Shifts LFO starting point relative to beat |
| Invert | on/off | Flips waveform polarity |
| Attack Time | ms or seconds | Time for LFO modulation to gradually increase; preserves transients in Tremolo mode |
| Dynamic Freq Mod | bipolar | Positive: louder input = faster LFO; Negative: louder input = slower LFO |

### LivePilot Usage
```
find_and_load_device("Auto Pan")
set_device_parameter(track_index, device_index, "Amount", 80)
set_device_parameter(track_index, device_index, "Shape", -60)  # pumping gate
```

### Tips
- Tremolo + Square wave + high Amount = hard gate / sidechain-pump effect.
- Dynamic Freq Mod creates responsive, expressive tremolo that reacts to playing dynamics.
- Harmonic mode at moderate depth creates tonal movement without obvious volume pumping.
- S&H waveform creates random choppy panning — great for glitch.

---

## 5. LFO (M4L Stock)

**Category:** Max for Live > Max Audio Effect (modulator)
**Included with:** Max for Live (ships with Live Suite)
**URI:** `Max Audio Effect/LFO`

### What It Does
Free-running or tempo-synced LFO that maps to up to 8 parameters anywhere in the Live set. The foundational modulation utility.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Click Map, then click target parameter |
| Min / Max (per map) | 0-100% of target range | Constrains modulation output range per mapping |
| Waveform | Sine, Saw Up, Saw Down, Triangle, Rectangle, Random, Binary Noise | 7 shapes |
| Rate | Hz (free) or synced beat divisions | LFO speed |
| Depth | 0-100% | Overall modulation intensity |
| Offset | degrees | Initial phase / starting point |
| Phase | degrees | Oscillator phase shift |
| Jitter | 0-100% | Adds randomness to waveform |
| Smooth | 0-100% | Smooths value transitions |
| R (Retrigger) | button | Re-triggers LFO phase on click |
| Hold | on/off | Freezes current output value |

### LivePilot Usage
```
search_browser("LFO")  # find in Max Audio Effect
# Load onto track, then map parameters manually in Live's UI
# LFO mapping is GUI-only — cannot be set via API
```

### Tips
- Rectangle wave = square-wave switching between two parameter states.
- Binary Noise = unpredictable random — great for generative patches.
- Jitter + Smooth together = organic, drifting modulation.
- Use multiple LFO instances at different rates for polyrhythmic modulation.

---

## 6. Shaper (M4L Stock)

**Category:** Max for Live > Max Audio Effect (modulator)
**Included with:** Max for Live (ships with Live Suite)
**URI:** `Max Audio Effect/Shaper`

### What It Does
Custom multi-breakpoint envelope that generates modulation data. Draw arbitrary waveshapes with curves, then use them as repeating LFOs or one-shot envelopes. Maps to up to 8 parameters.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Same mapping system as LFO |
| Min / Max (per map) | 0-100% of target range | Per-mapping output scaling |
| Breakpoint Display | click to add, Shift-click to delete | Custom waveshape editor |
| Curved Segments | Alt/Option + drag | Creates smooth curves between points |
| Grid | continuous | Quantize breakpoints to grid |
| Snap | on/off | Breakpoints lock to grid lines |
| Presets | 6 built-in shapes | Quick-start waveshapes |
| Clear | button | Resets display to flat |
| Rate | Hz (free) or synced beat divisions | Playback speed of shape |
| Depth | 0-100% | Overall modulation intensity |
| Offset | degrees | Initial phase point |
| Phase | degrees | Oscillator phase shift |
| Jitter | 0-100% | Randomness applied to shape |
| Smooth | 0-100% | Smooths output transitions |
| R (Retrigger) | button | Re-triggers phase (unavailable in Sync mode) |

### LivePilot Usage
```
search_browser("Shaper")  # find in Max Audio Effect
# Shape editing is GUI-only — design the curve in Live's device view
```

### Tips
- Draw a sharp spike for transient-like modulation hits.
- Curved ramp-up shapes create swell/build effects.
- Combine with tempo sync for rhythmic modulation patterns.
- Use the oscilloscope display (upper right) to verify output shape.

---

## 7. Envelope Follower (M4L Stock)

**Category:** Max for Live > Max Audio Effect (modulator)
**Included with:** Max for Live (ships with Live Suite)
**URI:** `Max Audio Effect/Envelope Follower`

### What It Does
Tracks the amplitude of incoming audio and converts it into a modulation signal. Maps to up to 8 parameters — the classic "sidechain anything" tool.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard mapping system |
| Min / Max (per map) | 0-100% of target range | Per-mapping output scaling |
| Gain | dB | Amplifies input signal before analysis |
| Rise | ms | Smooths attack envelope (how fast it responds to transients) |
| Fall | ms | Smooths release envelope (how fast it decays) |
| Delay | ms or synced beat divisions | Delays the modulation output |

### LivePilot Usage
```
search_browser("Envelope Follower")  # find in Max Audio Effect
# Place on track with audio source (e.g., kick drum track)
# Map to parameters on other tracks (e.g., synth filter cutoff)
```

### Tips
- Low Rise + moderate Fall = tight transient tracking (sidechain ducking).
- High Rise + high Fall = smooth, slow-responding modulation (ambient swells).
- Use Delay to offset the modulation timing for groove purposes.
- Place on a return track to derive modulation from a bus mix.

---

## 8. Looper (Native)

**Category:** Audio Effects > Looper
**URI:** `Audio Effects/Looper`

### What It Does
Real-time audio looper with overdub, speed/pitch manipulation, reverse playback, and feedback-path effects insert. Designed for live performance.

### Transport States

| State | Color | Behavior |
|-------|-------|----------|
| **Record** | Red | Captures audio into buffer; first recording sets loop length |
| **Overdub** | Orange | Layers new audio on top of existing loop |
| **Play** | Green | Plays back the loop |
| **Stop** | Gray | Stops playback; loop retained in buffer |

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Transport Button | Record > Overdub > Play cycle | Main multi-state button |
| Stop | button | Stops playback |
| Clear | button | Erases buffer; in Overdub mode, clears content but keeps length/tempo |
| Undo / Redo | button | One-step undo of last overdub layer |
| Speed | -3 oct to +3 oct (tape-style) | Pitch and speed locked together; half speed = octave down |
| Reverse | on/off | Plays loop backwards |
| Feedback | 0-100% | How much of the loop is retained per cycle; <100% = gradual fade |
| Record Length | bars (1, 2, 4, 8, etc.) or free | Pre-set loop length or record-to-stop |
| Song Control | None, Start, Start & Stop | How looper interacts with Live's transport |
| Tempo Control | None, Follow Song Tempo, Set & Follow Song Tempo | Tempo sync behavior |
| Monitor | on/off | Pass input audio through during playback |
| Drag Me | drag region | Drag completed loop to arrangement/clip slot |
| **FX Insert** | (device chain position) | Effects placed after Looper in chain process the feedback path |

### LivePilot Usage
```
find_and_load_device("Looper")
# Looper transport is best controlled via MIDI mapping or foot controller
# API access to Looper state is limited
```

### Tips
- Place effects (delay, reverb, filter) after Looper for iterative feedback processing — each pass adds more effect.
- Speed at -12 (octave down) creates ambient drones from any source.
- Feedback at 80-90% creates gradually evolving, decaying loops.
- Set Song Control to "None" for independent looper operation in live performance.

---

## 9. MFA Audio S&H (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio (Noah Pred)
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Generates random modulation values when the incoming audio signal exceeds a threshold. Audio-triggered sample-and-hold for reactive, probabilistic parameter changes.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Sensitivity / Gain | continuous | Threshold for audio trigger detection |
| Length | continuous | Duration / interval of S&H trigger windows |
| Probability | 0-100% | Chance of triggering on each threshold crossing |
| Delay | ms or synced | Offset before value change |
| Depth | 0-100% | Overall modulation amount |
| Offset | continuous | DC offset of output |
| Smoothing | continuous | Smooths value transitions |
| Randomization Mode | Luck, Drunk, Fluid | Style of random value generation |

### Tips
- Sensitivity controls how loud the signal must be to trigger — set low for constant triggering, high for accent-only.
- Drunk mode creates values that wander near the previous value (Brownian motion).
- Fluid mode interpolates smoothly between random targets.

---

## 10. MFA Audiodubber (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Creates maximum-value spikes (dub throws) when incoming audio exceeds a threshold. Probabilistic, audio-reactive parameter bursts for dub-style send throws and dramatic automation gestures.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Sensitivity / Gain | continuous | Audio threshold for spike trigger |
| Probability | 0-100% | Chance of triggering per threshold crossing |
| Length | continuous | Duration of each spike |
| Delay | ms or synced | Offset before spike fires |
| Depth | 0-100% | Overall modulation amount |
| Offset | continuous | Baseline value when not spiking |
| Smoothing | continuous | Smooths spike onset/release |

### Tips
- Map to reverb/delay send levels for classic dub throws that react to audio peaks.
- Low Probability creates sparse, unpredictable throws; high Probability is more rhythmic.
- Combine with short Length for staccato bursts or long Length for sustained throws.

---

## 11. MFA Autodubber (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Autonomously generates maximum-value spikes at probabilistic intervals. Unlike Audiodubber, it runs independently — no audio input needed to trigger. Self-running dub throw generator.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Interval | synced divisions | Roughly how often spikes occur |
| Duration | synced divisions | How long each spike lasts |
| Probability | 0-100% | Chance of spike at each interval |
| Depth | 0-100% | Overall modulation amount |
| Offset | continuous | Baseline (minimum) value |
| Smoothing | continuous | Smooths spike transitions |

### Tips
- Set Interval to 1/2 or 1 bar with low Probability for occasional dramatic dub throws.
- Map to send levels on multiple return tracks for varied throw destinations.
- Stack with Audiodubber for both reactive and autonomous dub effects.

---

## 12. MFA Follower (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Envelope follower with BPM-synchronized base rate and multiplier delay time. More tempo-aware than the stock Envelope Follower, with additional timing and rhythmic controls.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Base Rate | synced divisions | Tempo-synced envelope rate |
| Multiplier | continuous | Rate multiplier for fine-tuning |
| Jitter | 0-100% | Randomness in timing |
| Smoothing | continuous | Output smoothing |
| Flip | on/off | Inverts envelope output |
| Step Rate | continuous | Quantizes output to stepped values |
| Depth | 0-100% | Overall modulation amount |
| Offset | continuous | DC offset of output |

### Tips
- Tempo-synced rate makes this ideal for rhythmically locked envelope following.
- Flip inverts the response — loud passages push parameters down instead of up.
- Step Rate creates quantized, staircase-style modulation from smooth audio input.

---

## 13. MFA Gain Tracker (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Provides amplitude-based audio-rate modulation. Tracks the incoming signal's amplitude continuously and outputs it as a modulation signal. Faster and more direct than the Follower — operates at audio rate.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Depth | 0-100% | Overall modulation amount |
| Offset | continuous | DC offset |
| Smoothing | continuous | Output smoothing |

### Tips
- Audio-rate tracking means this responds to individual waveform cycles, not just envelope shape.
- Useful for creating amplitude-coupled modulation effects (e.g., louder = more filter cutoff).
- Lighter on parameters than Follower — use when you want direct, unprocessed amplitude tracking.

---

## 14. MFA LFOx (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Advanced BPM-synchronized LFO with probability, cycle reset triggers, and pitch-controlled rate. Goes beyond the stock LFO with tempo-locked curves, MIDI-triggered resets, and scale-quantized output.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Base Rate | synced divisions | Tempo-synced LFO rate |
| Multiplier | continuous | Rate multiplier |
| Waveform | multiple curves | LFO shape selector |
| Cycle Reset | MIDI trigger, MIDI pitch, bar count | When to restart the LFO cycle |
| Probability | 0-100% | Chance of output changing per cycle |
| Pitch Control | on/off | MIDI pitch controls LFO rate (audio-rate) |
| Scale/Key | selectable | Constrains pitch-rate mapping to musical scale |
| Depth | 0-100% | Overall modulation amount |
| Offset | continuous | Phase offset |
| Smoothing | continuous | Output smoothing |

**Pro version adds:** Draw, Lines, Steps, and Audio editable modulation modes for custom shapes, breakpoint patterns, step sequences, and audio waveforms as modulation sources.

### Tips
- Cycle Reset via MIDI = LFO restarts on every note, creating synced envelope-like shapes.
- Pitch-controlled rate turns the LFO into a pitch-tracking vibrato or filter sweep.
- Base Rate + Multiplier gives fine-grained tempo-locked control.

---

## 15. MFA X-Control (M4L — CLX_05 Mod Squad)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Manifest Audio
**Pack:** Mod Squad (free) / Mod Squad Pro (paid)

### What It Does
Macro knob that can be optionally quantized to synchronized rate divisions for ladder-style stepped parameter changes. Also available as a rack configuration (X-Control 4 / X-Control 8) for controlling 32 or 64 parameters from rack macros.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Map (x8) | any Live parameter | Standard 8-target mapping |
| Min / Max (per map) | constrainable range | Per-mapping output scaling |
| Rate | synced divisions | Quantization rate for value changes |
| Multiplier | continuous | Rate multiplier |
| Jitter | 0-100% | Randomness in stepped values |
| Smoothing | continuous | Transition smoothing between steps |

**X-Control 4 Rack:** 4 macro knobs, each mapped to 4 X-Control instances = 32 parameters. Remaining 4 macros control Rate, Multiplier, Jitter, Smoothing globally.
**X-Control 8 Rack:** 8 macro knobs, each mapped to 8 instances = 64 parameters.

### Tips
- Use as a master modulation controller — one knob drives many parameters with optional quantization.
- MIDI-map the macro for hardware control of complex, multi-parameter transitions.
- Jitter adds humanization to otherwise mechanical stepped changes.

---

## 16. Functions Audio / Functions MIDI (M4L — CLX_02 Movers)

**Category:** Max for Live > Max Audio Effect / Max MIDI Effect (modulator)
**Developer:** NOISS COKO (via Isotonik Studios)
**Pack:** The Movers

### What It Does
Versatile breakpoint function generator that works as both a classic LFO and a complex triggered envelope. Control values are drawn as custom shapes and distributed across five output layers. MIDI version triggers from incoming MIDI notes; Audio version runs freely or synced.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Function Display | breakpoint editor | Draw custom modulation shapes with curves |
| Output Layers (x5) | Map button or MIDI message | Each layer independently assignable |
| MIDI Output Formats | CC, Pitch Bend, Mod Wheel, Foot Control, Aftertouch | Available message types per layer |
| Rate / Speed | Hz or synced | Playback speed of the function |
| Trigger Mode | free-running, MIDI note, audio threshold | What starts the function cycle |
| Loop | on/off | Repeat or one-shot |
| Randomization | continuous | Amount of random variation per cycle |
| Precision / Smoothing | continuous | Output resolution and smoothing |

**Audio version:** No MIDI output options; maps to Live parameters only.
**MIDI version:** Can output MIDI messages to downstream instruments.

### Tips
- Draw complex multi-stage envelopes for evolving parameter changes over time.
- Use as a triggered envelope (MIDI) for synth-like modulation on any parameter.
- Five output layers means one function shape can drive five different parameters simultaneously.
- Randomization adds organic variation to repeated patterns.

---

## 17. Ministeps Audio / Ministeps MIDI (M4L — CLX_02 Movers)

**Category:** Max for Live > Max Audio Effect / Max MIDI Effect (modulator)
**Developer:** NOISS COKO (via Isotonik Studios)
**Pack:** The Movers

### What It Does
Three independent 8-step sequencers whose values are distributed across five output layers. Creates stepped, rhythmic modulation patterns from precise to fully randomized.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Sequencer A/B/C | 8 steps each (24 total) | Three independent step sequencers |
| Step Values | continuous per step | Set each step's output value |
| Output Layers (x5) | Map button or MIDI message | Each layer independently assignable |
| MIDI Output Formats | CC, Pitch Bend, Mod Wheel, Foot Control, Aftertouch | Per-layer message type |
| Rate | synced divisions | Step advancement speed |
| Randomization | continuous | From absolute precision to total randomness |
| Direction | forward, reverse, pendulum, random | Step playback order |
| Step Count | 1-8 per sequencer | Active number of steps |
| Slope Mode | selectable | Transition shape between steps |

**Audio version:** No MIDI output; maps to Live parameters only.
**MIDI version:** Can output MIDI messages.

### Tips
- Three sequencers at different lengths create polyrhythmic modulation.
- Ideal for parameters that don't support clip automation or MIDI mapping (via Map).
- High randomization = generative; zero randomization = precise, repeatable patterns.
- Pair with instruments like Wavetable, Operator, or Meld that have internal mod matrices.

---

## 18. Smooth Automator Audio / MIDI (M4L — CLX_02)

**Category:** Max for Live > Max Audio Effect / Max MIDI Effect (utility)
**Developer:** KB Devices (KB Live Solutions)
**Note:** This is a separate device from the Movers pack, but commonly grouped in CLX_02.

### What It Does
Creates smooth, timed transitions between macro variation states in Instrument, Drum, or MIDI Effect Racks. Place to the left of a Rack to enable gradual morphing between variation snapshots.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Transition Time | ms, seconds, or synced | Duration of the morph between variations |
| Transition Mode | Timed, Synced, Manual | How transitions are triggered |
| Manual Slider | 0-100% | Direct crossfade control in Manual mode |
| Variation Automation | clip-automatable | Automate which variation to transition to |

### Tips
- Automate the variation selector in arrangement view for evolving macro changes over time.
- Use synced transitions for beat-locked morphs between sound states.
- Manual mode via MIDI-mapped slider gives real-time performance control.
- Must be placed immediately to the left of the target Rack.

---

## 19. Slink LFO / Slink LFO CV / Slink Filter / Slink MIDI (M4L — User Pack)

**Category:** Max for Live (various types)
**Developer:** Hypnus Records (Michel Iseneld + Alexander Berg / Dorisburg + Chaos Culture)
**Pack:** Slink Devices (EUR 59)
**Requirements:** Live 12 Standard + Max for Live 12.0+

### What They Do
Four devices built on the "Slink wave engine" — a modulation source modeled on the natural movement of water. Produces organic, fluid, interconnected modulation signals.

### Slink LFO

| Parameter | Notes |
|-----------|-------|
| Slink Wave Engine | Core modulation generator — fluid, water-like motion |
| 16 Modulation Signals | Independent but interconnected modulation outputs |
| 32 Possible Outputs | Mappable to parameters throughout the project |
| Sample & Hold Section | Triggered by external MIDI input |
| Standard mapping | Map to any Live parameter |

**Slink LFO CV:** Same engine, outputs CV signals for hardware gear.

### Slink Filter

| Parameter | Notes |
|-----------|-------|
| 32 Bandpass Filters | Filter bank with amplitude automated by Slink wave |
| Advanced Tab | Extended controls for spectral stereo morphing |
| Frequency Spectrum Mod | From gentle analog drift to dramatic spectral changes |

### Slink MIDI

| Parameter | Notes |
|-----------|-------|
| Wave Engine 1 | Triggers notes when wave exceeds threshold |
| Wave Engine 2 | Modulates pitch within chosen musical scale |
| Scale / Root Note | Constrains pitch output to key |
| Color Knob | Emphasizes particular notes and harmonic intervals |
| 16 Clock Dividers | Each with 3 trigger conditions — creates organic rhythmic sequencing |

### Tips
- Slink LFO's interconnected signals mean parameters modulated by the same engine move in related but non-identical ways — creates coherent organic motion.
- Slink Filter is unique — no other device offers a 32-band filter bank automated by a fluid simulation.
- Slink MIDI generates melodies from the wave engine — use as a generative note source.
- The water-inspired engine excels at slow, evolving, ambient-style modulation.

---

## 20. Iris Devices Cellular Mod (M4L — User)

**Category:** Max for Live > Max MIDI Effect (modulator)
**Developer:** Iris Ipsum (IrisS02)
**Price:** Free
**Requirements:** Live 10.1.18+, Max 8.1.5+

### What It Does
Generates complex modulation signals through a 9-bit cellular automata system. Each new generation is triggered by incoming MIDI. 256 rule sets produce different behavioral patterns — from ordered to chaotic.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| Rule Set | 0-255 | Selects the cellular automaton rule (each produces unique patterns) |
| Trigger | incoming MIDI | New generations computed on MIDI input |
| Map | any Live parameter | Output mapped to device parameters |
| 9-bit State | visual display | Shows current automaton state |

### Tips
- Low rule numbers tend to produce simple, repeating patterns; higher numbers trend toward chaos.
- Rule 30 and Rule 110 are mathematically famous for producing complex behavior from simple rules.
- Because it triggers on MIDI, modulation rhythm is locked to your playing or MIDI clip.
- Experiment with rules — small changes can produce dramatically different modulation character.

---

## 21. IrisIpsum MCLFO (M4L — User)

**Category:** Max for Live > Max Audio Effect (modulator)
**Developer:** Iris Ipsum (IrisS02)
**Price:** Free
**Requirements:** Live 11.0.12+, Max 8.5.3+

### What It Does
Nine independent sine-wave LFOs, each mappable to a separate parameter. Frequency ratios between oscillators are linked via seven relationship modes, creating complex but coherent multi-parameter modulation from a single device.

### Parameters

| Parameter | Range / Values | Notes |
|-----------|---------------|-------|
| LFO Channels | 9 sine oscillators | Each independently mappable |
| Map (x9) | any Live parameter | One target per oscillator |
| Variable Range | per-mapping | Min/max output range per mapping |
| Frequency Ratio Mode | Harmonic, Subharmonic, Exponential, Deviate, Decide, Increment, Spread | How the 9 frequencies relate to each other |
| Base Frequency | Hz | Master rate that others derive from |

### Frequency Ratio Modes

| Mode | Relationship |
|------|-------------|
| **Harmonic** | Integer multiples of base frequency (1x, 2x, 3x...) |
| **Subharmonic** | Integer divisions of base frequency (1/1, 1/2, 1/3...) |
| **Exponential** | Exponentially increasing ratios |
| **Deviate** | Small random deviations from base |
| **Decide** | Random selection per channel |
| **Increment** | Linear incremental offsets |
| **Spread** | Even spread across a frequency range |

### Tips
- Harmonic mode creates musically related modulation — parameters move in rhythmic lockstep.
- Subharmonic mode creates slow, evolving polyrhythmic relationships.
- Deviate mode = organic drift — all LFOs near the same rate but slightly different.
- 9 channels means you can modulate an entire synth's parameters from one device.

---

## Quick Decision Matrix

| Need | Best Device | Why |
|------|------------|-----|
| **Thicken / widen a sound** | Chorus-Ensemble (Ensemble mode) | Three-voice chorus, instant width |
| **Classic phaser sweep** | Phaser-Flanger (Phaser, Earth) | Musical notch sweep, adjustable depth |
| **Metallic flanger jet** | Phaser-Flanger (Flanger, Space) | Comb filter + feedback resonance |
| **Subtle doubling / ADT** | Phaser-Flanger (Doubler) or Chorus-Ensemble (Classic, low Amount) | Micro-delay thickening |
| **Pitch harmony / shifting** | Shifter (Pitch mode) | Chromatic pitch shift with delay |
| **Ring mod / metallic texture** | Shifter (Ring mode) | Non-harmonic frequency shifting + drive |
| **Melodic pitch from audio** | Shifter (MIDI sidechain) | Play notes via MIDI, applied to audio |
| **Sidechain-pump without compressor** | Auto Pan-Tremolo (Tremolo, Square) | Volume gating synced to tempo |
| **Expressive tremolo** | Auto Pan-Tremolo (Tremolo, Vintage + Dynamic Freq Mod) | Amplitude-reactive rate |
| **Stereo movement / panning** | Auto Pan-Tremolo (Panning) | LFO-driven stereo placement |
| **Modulate any parameter (simple)** | LFO (M4L stock) | 7 waveforms, 8 mappings, reliable |
| **Custom modulation shape** | Shaper (M4L stock) | Draw arbitrary breakpoint envelopes |
| **Audio-reactive modulation** | Envelope Follower (M4L stock) or MFA Follower | Amplitude tracking to parameter |
| **Audio-reactive random** | MFA Audio S&H | Random values on audio threshold |
| **Dub throws (audio-triggered)** | MFA Audiodubber | Spike to max on audio peaks |
| **Dub throws (autonomous)** | MFA Autodubber | Self-running probabilistic spikes |
| **Audio-rate amplitude tracking** | MFA Gain Tracker | Direct, fast amplitude-to-modulation |
| **Advanced tempo-synced LFO** | MFA LFOx | BPM-locked, cycle reset, probability |
| **Multi-parameter macro** | MFA X-Control (rack) | 32-64 params from rack macros |
| **Step-sequenced modulation** | Ministeps (Movers) | 3x 8-step sequencers, 5 output layers |
| **Custom envelope modulation** | Functions (Movers) | Breakpoint functions, 5 output layers |
| **Rack variation morphing** | Smooth Automator | Timed transitions between rack variations |
| **Organic fluid modulation** | Slink LFO | Water-physics engine, 16 signals |
| **Spectral filter animation** | Slink Filter | 32 bandpass filters, wave-animated |
| **Generative melody from physics** | Slink MIDI | Wave engine generates notes in scale |
| **Cellular automata modulation** | Iris Cellular Mod | 256 rules, MIDI-triggered generations |
| **9-channel coherent LFOs** | IrisIpsum MCLFO | 9 sine LFOs with ratio relationships |
| **Live looping / layering** | Looper | Record, overdub, speed, reverse, feedback FX |

---

## Device Location Quick Reference

| Device | Browser Path | Type |
|--------|-------------|------|
| Chorus-Ensemble | Audio Effects > Chorus-Ensemble | Native |
| Phaser-Flanger | Audio Effects > Phaser-Flanger | Native |
| Shifter | Audio Effects > Shifter | Native |
| Auto Pan-Tremolo | Audio Effects > Auto Pan | Native |
| Looper | Audio Effects > Looper | Native |
| LFO | Max Audio Effect > LFO | M4L Stock |
| Shaper | Max Audio Effect > Shaper | M4L Stock |
| Envelope Follower | Max Audio Effect > Envelope Follower | M4L Stock |
| MFA Mod Squad devices | User Library > Presets > ... (CLX_05) | M4L User |
| Functions / Ministeps | User Library > Presets > ... (CLX_02) | M4L User |
| Smooth Automator | User Library > Presets > ... (CLX_02) | M4L User |
| Slink devices | Packs > Slink Devices | M4L User Pack |
| Iris Cellular Mod | User Library > ... | M4L User |
| IrisIpsum MCLFO | User Library > ... | M4L User |

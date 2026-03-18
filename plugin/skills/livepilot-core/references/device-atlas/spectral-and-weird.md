# Spectral & Weird — Device Atlas

> Spectral processors, granular effects, glitch engines, oscilloscope instruments, and experimental M4L devices in Ableton Live 12.
> Use this reference to choose, configure, and chain spectral/experimental devices via LivePilot.

---

## Native Devices

---

### Spectral Time

- **Type:** Native (Live 11+, Suite only)
- **Load via:** `find_and_load_device("Spectral Time")`
- **What it does:** FFT-based effect combining a spectral freeze engine and a spectral delay. Freeze captures and sustains incoming audio as a spectral snapshot; Delay applies per-frequency delay times with pitch shift, tilt, spray, and masking. Sections run independently or in series (Freeze into Delay or Delay into Freeze). Built-in sonogram display shows dry (yellow) and wet (blue) signals.
- **Signal flow:** Input → Pre Gain → [Freezer ↔ Delay (order switchable)] → Mix → Output
- **Key parameters:**
  - **Freezer Section:**
    - **Freezer On** (toggle) → enable/disable freeze engine
    - **Freeze** (toggle) → capture/hold current spectral snapshot (Manual mode) or re-freeze on trigger (Retrigger mode)
    - **Mode** (Manual / Retrigger) → Manual = button-press freeze; Retrigger = auto-freeze on onset or sync
    - **Retrig Mode** (Onsets / Sync) → Onsets triggers on transients with Sensitivity (0--100%); Sync triggers at regular Interval
    - **Sensitivity** (0--100%) → onset detection threshold → lower catches more transients
    - **Interval** (ms or beat-synced) → retrigger spacing in Sync mode
    - **Fade** (Crossfade / Envelope) → Crossfade blends old/new freezes smoothly; Envelope uses separate fade in/out
    - **Fade In** (0.002--10 s) → ramp-up time for new freeze
    - **Fade Out** (0.02--10 s) → ramp-down time for old freeze
    - **X-Fade** (0--100%) → crossfade duration as percentage of interval → supports up to 8 simultaneous stacked freezes
  - **Delay Section:**
    - **Delay On** (toggle) → enable/disable spectral delay
    - **Time** (0.01--3 s, or beat-synced: 16th / 16th-T / 16th-D / Notes) → delay duration
    - **Feedback** (0--100%) → output fed back to delay input → > 80% builds up, approaches infinity
    - **Shift** (-400 to +400) → frequency shift applied to delayed signal → successive repeats shift progressively
    - **Tilt** (-2 to +2) → skews delay times by frequency → positive = highs delayed more, negative = lows delayed more
    - **Spray** (0--0.4) → randomizes delay times per frequency bin → low = subtle smear, high = scattered chaos
    - **Mask** (-1 to +1) → limits Tilt/Spray to frequency range → negative = lows only, positive = highs only
    - **Spread** (0--100%) → stereo width of Tilt and Spray processing
  - **Global:**
    - **Order** (Freeze→Delay / Delay→Freeze) → processing chain sequence
    - **Resolution** (Low / Mid / High / Ultra) → FFT processing quality → Ultra = pristine, Low = lo-fi character
    - **Pre Gain** (-70.6 to 0 dB) → input signal level
    - **Dry/Wet** → 30--50% for subtle spectral sheen, 100% on send, 100% for drone/texture work
- **Presets:** "Spectral Wash" (ambient starting point), "Glitch Freeze" (retrigger stutters), "Pitch Cloud" (shift + spray chaos)
- **Reach for this when:** you need spectral freezes for drones/pads, glitchy retrigger stutters, per-frequency delay with tilt/spray, or otherworldly textures from any source
- **Don't use when:** you need a clean transparent delay (use Delay), simple reverb tails (use Reverb), or tempo-locked rhythmic repeats (use Echo)
- **Pairs well with:** Corpus (freeze into resonator), Reverb (post-freeze ambient wash), Auto Pan (movement on frozen textures), Utility (mono check for Spray width)
- **vs Grain Delay:** Spectral Time works in frequency domain (FFT), Grain Delay in time domain (granular). Spectral Time excels at freeze/sustain and per-frequency processing; Grain Delay excels at pitch-shifting textures and granular scatter.

---

### Spectral Resonator

- **Type:** Native (Live 11+, Suite only)
- **Load via:** `find_and_load_device("Spectral Resonator")`
- **What it does:** FFT-based pitched resonance processor. Breaks incoming audio into spectral partials, then resonates them at a tuned frequency with harmonic stretching, shifting, and modulation. Can be driven by internal frequency or external MIDI for pitched spectral effects. Turns any audio into a resonant, tonal instrument.
- **Signal flow:** Input → FFT analysis → Partial generation (Harmonics + Stretch + Shift) → Decay/Damping → Modulation (Chorus/Wander/Granular) → Unison → Dry/Wet Output
- **Key parameters:**
  - **Pitch Mode:**
    - **Internal Mode:** Freq dial sets pitch in Hz or note name; Frequency Dial Mode buttons toggle Hz/pitch display
    - **MIDI Mode:** MIDI router selects source track; Mono/Poly switch; Polyphony chooser (2/4/8/16 voices); MIDI Gate (only resonates while notes held); Glide (ms, Mono only); PB range (0--24 semitones)
  - **Harmonic Processing:**
    - **Harmonics** → number of generated partials → higher = brighter, more complex
    - **Stretch** (-100% to +100%) → compress or stretch harmonic spacing → 0 = natural harmonics, 100% = odd harmonics only (clarinet-like), negative = sub-harmonics emphasized
    - **Shift** (±48 semitones) → transpose entire spectrum up/down
  - **Decay & Damping:**
    - **Decay** (ms) → resonance sustain time → short (< 200 ms) for plucky, long (> 1 s) for sustained drones
    - **HF Damp** → high-frequency partial decay → increase for darker, warmer resonance
    - **LF Damp** → low-frequency partial decay → increase for thinner, brighter resonance
  - **Modulation (4 modes):**
    - **None** → static resonance
    - **Chorus** → gentle detuning movement
    - **Wander** → random sawtooth modulation on partials → organic, evolving texture
    - **Granular** → granular decomposition of resonance → glitchy, textural, broken
    - **Mod Rate** → modulation speed for active mode
    - **Pch. Mod** (±semitones) → pitch modulation range
  - **Output:**
    - **Input Send** → gain applied to processed signal
    - **Unison** (1/2/4/8 voices) → stacked voices for width and density
    - **Uni. Amt** (0--100%) → unison detuning intensity → high = thick chorus, low = subtle width
    - **Dry/Wet** → 35--50% for tonal coloring, 100% for full spectral instrument
- **Presets:** "Metallic Ring" (short decay, high harmonics), "Drone Machine" (long decay, wander), "Spectral Instrument" (MIDI mode, poly)
- **Reach for this when:** you need to add pitched resonance to percussion/noise, create spectral instruments from any audio, build drones from textures, or add metallic/harmonic coloring
- **Don't use when:** you want physical-body resonance (use Corpus), transparent reverb (use Hybrid Reverb), or simple EQ resonance (use EQ Eight with narrow peaks)
- **Pairs well with:** Spectral Time (chain for freeze-into-resonance), Beat Repeat (glitch source into resonator), Corpus (physical + spectral layering), Compressor (tame resonant peaks)
- **vs Corpus:** Spectral Resonator works in frequency domain with harmonic partials; Corpus uses physical modeling of real objects. Spectral Resonator is more "digital/alien," Corpus is more "acoustic/material."

---

### Corpus

- **Type:** Native (all Live editions)
- **Load via:** `find_and_load_device("Corpus")`
- **What it does:** Physical modeling resonator simulating 7 types of resonant objects. Developed with Applied Acoustics Systems. Adds the acoustic character of beams, strings, membranes, plates, pipes, and tubes to any input signal. Turns percussive hits into tuned metal, wood, or membrane sounds; turns sustained audio into vibrating physical objects.
- **Signal flow:** Input → Band-pass Filter (optional) → Resonator body (selected type) → LFO modulation → Bleed mix → Gain/Limiter → Dry/Wet Output. MIDI sidechain can control tuning and decay.
- **Key parameters:**
  - **Resonance Type** (7 models):
    - **Beam** → metal/wood beam → bright, bell-like overtones
    - **Marimba** → specialized beam with marimba-tuned overtones → warm, woody
    - **String** → vibrating string → rich harmonics, plucky to sustained
    - **Membrane** → rectangular drumhead → deep, boomy, thuddy
    - **Plate** → flat metal/glass plate → bright, shimmering, complex
    - **Pipe** → cylindrical tube (one end open) → hollow, breathy, flute-like
    - **Tube** → cylindrical tube (both ends open) → airy, more open than Pipe
  - **Resonator Parameters:**
    - **Quality** (Eco / Mid / High) → processing resolution → Eco for lo-fi, High for realism
    - **Decay** → internal damping → short for plucky percussion, long for sustained singing
    - **Material** → ratio of high-to-low frequency damping → low = rubber/wood (highs die fast), high = metal/glass (highs ring)
    - **Bright** → amplitude of frequency components → higher = more present upper partials
    - **Inharm** (Inharmonics) → stretches or compresses harmonic series → negative = compressed (bell-like), positive = stretched (metallic, dissonant)
    - **Radius** (Pipe/Tube only) → tube diameter → affects timbre and pitch
    - **Opening** (Pipe only, 0--100%) → how open the end is → 0% = closed (muted), 100% = fully open
    - **Ratio** (Membrane/Plate only) → aspect ratio of the surface → affects overtone pattern
    - **Hit** (0--100%) → excitation point on the body → different positions emphasize different modes
    - **Width** → stereo mix between left/right resonators
    - **Pos. L / Pos. R** → listening point positions → like moving microphones around the object
    - **Tune** (Hz) → fundamental frequency → set by ear or MIDI
    - **Fine** (cents) → fine-tuning for MIDI mode
    - **Spread** → detunes L/R resonators → positive = L higher / R lower, negative = opposite
  - **LFO Section:**
    - **Amount** → modulation depth on resonant frequency
    - **Rate** (Hz or tempo-synced) → LFO speed
    - **Waveform** → Sine, Square, Triangle, Sawtooth up/down, Noise variants
    - **Phase** (0--360 degrees) → offset between L/R channels
    - **Spin** → detunes LFO speeds between channels → creates stereo motion
  - **Filter Section:**
    - **Filter** (toggle) → enables band-pass filter on input before resonator
    - **Freq** → center frequency
    - **Bandwidth** → filter width → narrow = focused excitation, wide = full-spectrum
  - **Global:**
    - **Bleed** → unprocessed signal mixed in → restores highs lost to low tuning/quality
    - **Gain** → output level with built-in limiter
    - **Dry/Wet** → 50--80% for effect, 100% for full resonator instrument
  - **Sidechain (MIDI):**
    - **Frequency** (toggle) → MIDI controls resonator pitch
    - **Off Decay** (toggle) → Note Off triggers faster decay
    - **Last / Low** → note priority for polyphonic MIDI input
    - **PB Range** → pitch bend range in semitones
    - **Transpose / Fine** → MIDI offset controls
- **Presets:** "Metal Plate" (bright percussion), "Wooden Beam" (warm marimba-like), "Drum Membrane" (deep tom resonance), "Glass Tube" (ethereal, breathy)
- **Reach for this when:** you need tuned percussion from noise/clicks, physical material character on any source, acoustic resonance modeling, pitched MIDI-controlled resonation, or metallic/woody coloring
- **Don't use when:** you need spectral/FFT processing (use Spectral Resonator), simple reverb/space (use Reverb), or frequency-domain manipulation (use Spectral Time)
- **Pairs well with:** Drum Rack (Corpus on individual pads for tuned percussion), Operator (simple click/noise exciter → Corpus), Spectral Time (freeze → Corpus for sustained resonance), Utility (volume control after high-Gain resonances)
- **vs Spectral Resonator:** Corpus models physical objects (material, geometry); Spectral Resonator manipulates FFT partials (harmonics, stretch). Corpus sounds acoustic/organic, Spectral Resonator sounds digital/alien. Use both in series for hybrid textures.

---

### Grain Delay

- **Type:** Native (all Live editions)
- **Load via:** `find_and_load_device("Grain Delay")`
- **What it does:** Granular delay that chops incoming audio into tiny grains and replays them with delay, pitch shift, and randomization. Sits between a delay and a granular processor -- capable of subtle chorus-like effects, dramatic pitch-shifted textures, and complete signal destruction depending on settings.
- **Signal flow:** Input → Grain engine (Frequency sets grain rate) → Pitch shift → Spray (time randomization) → Random Pitch → Feedback → Dry/Wet Output
- **Key parameters:**
  - **Delay Time** (Sync mode: beat divisions; Time mode: 1--300 ms) → base delay time → 1--5 ms for timbre coloring, 10--35 ms for chorus/flam, synced divisions for rhythmic
  - **Frequency** (1--150 Hz) → grain rate (grains per second) → lower = larger/smoother grains, higher = smaller/buzzier grains → < 4 Hz for smooth texture, 10--30 Hz for standard granular, > 60 Hz for buzzy artifacts
  - **Pitch** (±semitones, 2 decimal places) → pitch shift per grain → +5 = perfect fourth up, -7 = perfect fifth down, ±1 = subtle detuning → stacks with feedback for cascading transposition
  - **Spray** (ms) → random jitter on delay time → low (1--5 ms) for subtle smear, high for full time-scatter and rhythmic destruction
  - **Random Pitch** (0--100) → random pitch variation per grain → low (5--15) for mutant chorus, high (> 50) for unintelligible pitch chaos
  - **Feedback** (0--100%) → delayed grains fed back → 30% for cascading echoes, 60% for phaser-like buildup, > 90% for self-oscillation
  - **Dry/Wet** → 50% starting point for effect; 100% on send; use clip envelope or automation for dynamic control
- **Sweet spots for experimental use:**
  - **Stereo widener:** Sync off, delay < 35 ms, low Spray, low Frequency, low Random Pitch
  - **Granular texture:** High Frequency (40--100 Hz), moderate Spray (10--30 ms), Pitch at harmony interval, feedback 40--60%
  - **Complete destruction:** Max Spray, max Random Pitch, high Frequency, high Feedback
  - **Pitch harmonizer:** Pitch at musical interval (+3, +5, +7, +12), low Spray, zero Random Pitch, feedback 0%, delay < 10 ms
- **Presets:** "Shimmer" (octave up pitch cascade), "Granular Wash" (texture pad), "Pitch Chaos" (full destruction)
- **Reach for this when:** you want granular textures, pitch-shifted delays, subtle chorus-like widening from granular processing, or controlled signal destruction
- **Don't use when:** you need clean transparent delay (use Delay), spectral freeze (use Spectral Time), or tempo-locked rhythmic echoes (use Echo)
- **Pairs well with:** Reverb (post-grain wash), Auto Filter (sweep the granular output), Compressor (tame feedback buildup), Utility (mono check for stereo widening mode)
- **vs Spectral Time:** Grain Delay works in time domain (grain slicing); Spectral Time works in frequency domain (FFT). Grain Delay is better for pitch shifting and granular scatter; Spectral Time is better for freeze and per-frequency processing.

---

### Beat Repeat

- **Type:** Native (all Live editions)
- **Load via:** `find_and_load_device("Beat Repeat")`
- **What it does:** Real-time audio buffer capture and loop effect. Grabs chunks of audio at configurable intervals and repeats them with grid slicing, pitch decay, filtering, and volume decay. The definitive glitch/stutter tool in Live -- can produce everything from subtle fills to extreme rhythmic destruction.
- **Signal flow:** Incoming audio → Interval-triggered capture → Gate-length repetition → Grid slicing → Variation (random grid) → Pitch shifting → Filter (HP + LP) → Volume Decay → Mix/Insert/Gate output
- **Key parameters:**
  - **Interval** (1/32 to 4 Bars) → how often Beat Repeat captures new audio → 1 Bar for fills at bar boundaries, 1/4 for frequent stutters
  - **Offset** (0--16 sixteenths) → shifts capture point forward in time → use to target specific beats
  - **Chance** (0--100%) → probability that a repetition actually occurs → 100% = always, 50% = half the time (random glitch feel)
  - **Gate** (sixteenth notes) → duration of the repetition burst → short (1--2) for tight stutters, long (4--8) for extended loops
  - **Repeat** (toggle) → manual capture/repeat override → map to MIDI for performance control
  - **Grid** (1/4 to 1/32) → size of the repeated slice → 1/16 for standard stutter, 1/32 for rapid-fire glitch, 1/8 for chunky chops
  - **No Triplets** (toggle) → restricts grid to binary divisions only
  - **Variation** (0--100%) → random fluctuation of grid size → adds organic inconsistency
  - **Variation Mode** (Trigger / 1/4 / 1/8 / 1/16 / Auto) → how often variation recalculates → Trigger = once per capture, Auto = every slice
  - **Pitch** (0 to -48 semitones) → downward pitch shift via resampling → -12 for octave-down drops, -24 for horror effects
  - **Pitch Decay** (%) → progressive pitch reduction per repeat → creates descending stutter effect
  - **Filter Freq** → center frequency of combined HP/LP filter
  - **Filter Width** → bandwidth → narrow for resonant telephone effect, wide for gentle shaping
  - **Volume** → output level control
  - **Decay** (%) → gradual volume fade per repeat → creates natural stutter decay
  - **Mix Mode:**
    - **Mix** → original audio + repetitions play together
    - **Insert** → original audio muted during repetitions → cleaner glitch cuts
    - **Gate** → only repetitions pass through, original is fully cut → use on send for parallel glitch processing
- **Sweet spots for glitch/experimental:**
  - **Classic stutter:** Grid 1/16, Gate 2, Interval 1 Bar, Chance 70%, Insert mode
  - **Glitch fill:** Grid 1/32, Variation 80%, Pitch Decay 20%, Gate 4, Chance 100%
  - **Bass drop:** Grid 1/8, Pitch -12 to -24, Pitch Decay 50%, Insert mode
  - **Random destruction:** Grid 1/16, Variation 100% Auto, Chance 50%, Pitch -12, Decay 30%
  - **Performance stutter:** Map Repeat to MIDI button, Grid 1/16, Gate 8, Insert mode
- **Presets:** "Glitch Fill" (random stutters), "Tape Stop" (pitch decay), "Break Chop" (beat slicing)
- **Reach for this when:** you need real-time stutters, glitch fills, rhythmic destruction, performance-triggered repeats, or audio buffer manipulation
- **Don't use when:** you need smooth delay repeats (use Delay/Echo), granular textures (use Grain Delay), or spectral freeze (use Spectral Time)
- **Pairs well with:** Auto Filter (filter sweeps on stutters), Redux (bit-crush the repeats), Grain Delay (granular after stutter for chaos), Utility (gain staging after pitch decay)
- **vs Grain Delay for glitch:** Beat Repeat is rhythmic and beat-aligned; Grain Delay is textural and pitch-oriented. Beat Repeat for stutters/fills, Grain Delay for textures/harmonics.

---

## User M4L — Confetti Suite (Rodrigo Constanzo)

> 14 free Max for Live devices based on modules from The Party Van, Cut Glove, and TPV2. FluCoMa-powered analysis, creative destruction, and lo-fi processing. All parameters automatable. Free / open-source on GitHub.

---

### Confetti: Analysis

- **Type:** M4L Audio Effect (FluCoMa-powered)
- **Load via:** `find_and_load_device("M4L_Confetti Analysis")`
- **What it does:** Real-time audio descriptor analysis engine. Extracts onset detection, loudness, spectral centroid, and spectral flatness from incoming audio. Outputs continuous signal-rate streams or sample-and-hold values triggered by onset detection. Use as a modulation source for other Confetti devices or parameter mapping.
- **Key parameters:** Onset sensitivity, descriptor selection (loudness / centroid / flatness), output mode (continuous / sample-and-hold), smoothing
- **Reach for this when:** you need audio-reactive modulation, feature extraction for driving other effects, or analytical monitoring of spectral content

---

### Confetti: Chopper

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Chopper")`
- **What it does:** Time-domain granular analysis/resynthesis. Segments incoming audio at zero-crossings (wavesets) and stores them, then plays back stored segments in various orders. Creates waveset-based effects from subtle timbral shifts to complete reconstruction of audio from individual waveform cycles.
- **Key parameters:** Segment size, playback order, waveset selection, mix
- **Reach for this when:** you need waveset manipulation, zero-crossing granular effects, or timbral deconstruction at the waveform level

---

### Confetti: Chorus

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Chorus")`
- **What it does:** Multi-mode modulation effect with three distinct algorithms: Digital (8-stage chorus), Analog (sine LFO), and LoFi (triangle LFO with wow/flutter). Includes saturation processing stage. More character-driven than Live's native Chorus-Ensemble.
- **Key parameters:** Mode (Digital / Analog / LoFi), rate, depth, saturation amount, mix
- **Reach for this when:** you want characterful chorus with lo-fi or analog flavor, wow/flutter tape effects, or saturated modulation

---

### Confetti: Cloud

- **Type:** M4L Audio Effect (FluCoMa-powered)
- **Load via:** `find_and_load_device("M4L_Confetti Cloud")`
- **What it does:** Real-time granulator that writes incoming audio to a buffer while simultaneously reading back grains. Uses FluCoMa harmonic/percussive/transient decomposition to balance spectral components before granulation. The core granular texture engine of the Confetti suite.
- **Key parameters:** Grain size, grain density, position, pitch, harmonic/percussive/transient balance (FluCoMa), spray, feedback, mix
- **Reach for this when:** you need real-time granular processing with spectral decomposition, textural clouds from any audio, or harmonic/percussive separation before granulation

---

### Confetti: Dirt

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Dirt")`
- **What it does:** Dual-algorithm distortion combining cubic nonlinear distortion and variable-hardness clipping. Both algorithms 4x oversampled to minimize aliasing. Includes post-distortion EQ for tonal shaping.
- **Key parameters:** Algorithm selection, drive, hardness (clip algorithm), post-EQ, mix
- **Reach for this when:** you need clean-aliasing distortion, variable clipping character, or post-EQ-shaped saturation

---

### Confetti: Dub

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Dub")`
- **What it does:** Dirty delay that responds to audio onsets for dub-style processing. Multiple delay modes with onset-triggered behavior create dub snare slapbacks and Karplus-Strong-like resonant string effects from transient material.
- **Key parameters:** Delay time, feedback, onset sensitivity, mode selection, filter, mix
- **Reach for this when:** you need onset-reactive delay, dub-style processing, or Karplus-Strong string synthesis from percussive input

---

### Confetti: Filter

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Filter")`
- **What it does:** Multi-mode filter combining 4 classic filter topologies: MS-20, Sallen-Key, Moog Ladder, and Butterworth. Each offers lowpass/highpass modes with adjustable character parameters unique to each topology. More colorful and aggressive than Live's Auto Filter.
- **Key parameters:** Topology (MS-20 / Sallen-Key / Moog / Butterworth), mode (LP / HP), cutoff, resonance, character/drive, mix
- **Reach for this when:** you need specific analog filter character, aggressive self-oscillating resonance (MS-20), or filter topology comparison

---

### Confetti: Lofi

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Lofi")`
- **What it does:** Combines bit depth reduction, sample rate reduction, audio-rate bitwise manipulation, and MP3-style compression artifacts. More destructive and flexible than Live's Redux.
- **Key parameters:** Bit depth, sample rate, bitwise mode, compression quality, mix
- **Reach for this when:** you need deep bit-crushing, codec artifacts, bitwise audio manipulation, or layered lo-fi degradation beyond Redux

---

### Confetti: Octaver

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Octaver")`
- **What it does:** Lo-fi analog octave effect roughly modeled on the Boss OC-2 pedal. Generates sub-octave from input with added drive and filtering for fuzz-like character. Monophonic tracking like the hardware original.
- **Key parameters:** Octave level (-1, -2), drive, filter, direct signal level, mix
- **Reach for this when:** you need analog-style sub-octave, lo-fi bass fattening, or OC-2 pedal character in the box

---

### Confetti: Pitch

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Pitch")`
- **What it does:** Pitch shifting using PSOLA (pitch-synchronous overlap-add) algorithm, modeled on the character of the Digitech Whammy pedal. Four modes: Clean, Dirty, Automatic, and Random. Glitchy artifacts are a feature, not a bug.
- **Key parameters:** Pitch interval (semitones), mode (Clean / Dirty / Auto / Random), glide, mix
- **Reach for this when:** you need Whammy-style pitch effects, glitchy PSOLA pitch shifting, or random pitch chaos

---

### Confetti: Resonator

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Resonator")`
- **What it does:** Onset-triggered oscillator bank with pitch detection. Detects incoming transients, analyzes pitch, then triggers a bank of oscillators with randomized partial frequencies that fade out over time. Creates harmonic ghosts from percussive input.
- **Key parameters:** Onset sensitivity, partial count, frequency randomization, decay time, pitch tracking, mix
- **Reach for this when:** you need harmonic resonance from percussion, pitched ghost tones from transients, or oscillator-bank effects driven by audio input

---

### Confetti: Skipper

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Skipper")`
- **What it does:** Models a skipping CD player. Attack detection causes the virtual disc to skip, creating buffer-repeat and stutter effects. Multiple Sony Discman models available with different skip characteristics. Nostalgia as an effect.
- **Key parameters:** Discman model, skip sensitivity, repeat length, attack threshold, mix
- **Reach for this when:** you need CD-skip glitch effects, nostalgic digital artifacts, or onset-triggered buffer stutters

---

### Confetti: Tremolo

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Tremolo")`
- **What it does:** VCA and low-pass gate (LPG) based tremolo with waveshaping LFOs. Optional stereo panning mode. More organic and characterful than simple volume modulation due to LPG filtering behavior.
- **Key parameters:** Rate, depth, LFO waveshape, VCA/LPG mode, stereo pan mode, mix
- **Reach for this when:** you need LPG-colored tremolo, waveshaped modulation, or organic volume/filter movement

---

### Confetti: Wavefolder

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("M4L_Confetti Wavefolder")`
- **What it does:** Multiple wavefolder algorithms inspired by Buchla, Madrona Labs Aalto, and Whimsical Raps Cold Mac, combined with sigmoid saturation. Creates complex harmonic overtones by folding waveforms back on themselves. Rich, aggressive, and unpredictable.
- **Key parameters:** Algorithm (Buchla / Aalto / Cold Mac), fold amount, symmetry, saturation, mix
- **Reach for this when:** you need complex harmonic generation, wavefolding distortion, or aggressive timbral transformation

---

## User M4L — Oscilloscopemusic (Jerobeam Fenderson)

> 11 Max for Live instrument devices that generate audio signals designed to produce visual patterns on an XY oscilloscope. Left channel = X axis, Right channel = Y axis. These are primarily visual-audio synthesis instruments -- they make sound AND images simultaneously. All based on mathematical equations (trigonometry, fractals, geometry).

---

### blubb 0.0

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("blubb")`
- **What it does:** Generates bubbly water-drop sounds and circular oscilloscope visuals. Uses sin/cos equations to draw circles; applies pitch and volume envelopes for short rising-frequency tones; jumps randomly between positions. Includes automatic sequencer.
- **Key parameters:** Pitch envelope, volume envelope, position randomization, sequencer rate
- **Reach for this when:** you need bubbly/water synthesis, circular oscilloscope patterns, or generative percussive textures

---

### boing 1.1

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("boing")`
- **What it does:** Renders bouncing-ball animation on oscilloscope with corresponding audio. Draws horizontal circles, moves them vertically to form spirals, adjusts width for ball appearance. Envelopes and LFOs control spiral density, rotation, and 3D depth.
- **Key parameters:** Bounce height, spiral density, rotation speed, 3D depth, LFO rate
- **Reach for this when:** you need bouncy percussive synthesis, spiral oscilloscope visuals, or physics-inspired sound generation

---

### butterfly 0.1

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("butterfly")`
- **What it does:** Generates butterfly-shaped patterns on oscilloscope based on the transcendental butterfly curve equation. Blends three different mathematical shapes together for visual and sonic complexity.
- **Key parameters:** Shape blend (3 shapes), curve parameters, morphing speed
- **Reach for this when:** you need mathematical curve synthesis, organic visual patterns, or transcendental function-based sound design

---

### fractal spiral 1.8

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("fractal spiral")`
- **What it does:** Creates fractal spiral patterns with continuous zoom capability. Draws circles moved along spiral lines with seamless zooming by blending spiral stages. Controls for spiral density, width, rotation, zoom speed, and 3D depth via envelopes and LFOs. The most versatile and visually complex of the oscilloscope instruments.
- **Key parameters:** Spiral density, width, rotation, zoom speed, 3D depth, envelope/LFO assignments
- **Reach for this when:** you need fractal visual synthesis, zooming spiral patterns, or complex evolving oscilloscope visuals

---

### Kepler-Bouwkamp 0.4

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("Kepler-Bouwkamp")`
- **What it does:** Renders interlocking polygons and inscribed circles based on the Kepler-Bouwkamp constant (nested polygon geometry). Draws and rotates lines to form polygons with circles inserted between them. Adjustable shape, polygon count, direction, and rotation.
- **Key parameters:** Polygon count, rotation speed, direction, shape morphing, nesting depth
- **Reach for this when:** you need geometric oscilloscope patterns, mathematical polygon synthesis, or sacred-geometry-inspired visuals

---

### line horizon 0.1

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("line horizon")`
- **What it does:** Displays horizontal line arrays creating perspective depth effect with Minecraft-style sunrise visuals. Lines compress near zero for perspective illusion. Creates circle/square shapes in center with bow and squeeze distribution functions for line spacing.
- **Key parameters:** Line count, perspective depth, beat sync, center shape, bow/squeeze distribution
- **Reach for this when:** you need horizon/landscape oscilloscope visuals, perspective-based synthesis, or beat-synced visual patterns

---

### mushrooms 0.3

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("mushrooms")`
- **What it does:** Draws mushroom shapes on oscilloscope via sin/cos circle generation, ellipses through unequal channel volumes, spirals through vertical movement. Width modulation shapes stems and heads. Includes rotation and bending controls.
- **Key parameters:** Stem width, head size, rotation, bending, channel volume ratio
- **Reach for this when:** you need organic mushroom-shaped oscilloscope visuals, or creative stereo-field synthesis

---

### Nyquist-Shannon 0.1

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("Nyquist-Shannon")`
- **What it does:** Educational tool demonstrating sampling rate, aliasing effects, and signal reconstruction on oscilloscope. Visualizes sine waves with sampling point indicators, includes phase shift control, demonstrates aliasing artifacts. Primarily instructional.
- **Key parameters:** Sampling rate, frequency, phase shift, reconstruction display
- **Reach for this when:** you need aliasing demonstration, sampling theory visualization, or educational oscilloscope content

---

### Oscilloscope 2.0

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("Oscilloscope 2.0")`
- **What it does:** Lissajous pattern oscilloscope visualization using stereo audio input. Routes left channel to horizontal deflection, right channel to vertical. Multiple drawing modes and color options. This is a visualizer/monitor, not a synthesizer -- put it at the end of a chain to see what your audio looks like on a scope.
- **Key parameters:** Drawing mode, color, persistence, zoom, trigger
- **Reach for this when:** you need to monitor oscilloscope patterns from other devices, visualize stereo audio as Lissajous figures, or verify XY output of other oscilloscope instruments

---

### radar 1.3

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("radar")`
- **What it does:** Versatile pattern generator for spirals, tunnels, radar screens, and percussion synthesis. Draws circles along lines forming spirals with phasing for direction/shape variation. Includes 3D rotation, bending, fading effects. Multiple trigger modes for varied sound synthesis. The most sonically useful oscilloscope instrument due to extensive preset library.
- **Key parameters:** Pattern type, spiral phase, 3D rotation, bending, fade, trigger mode, preset selection
- **Reach for this when:** you need versatile oscilloscope synthesis, radar/tunnel visuals, or percussion synthesis with visual feedback

---

### sincos 4001

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("sincos 4001")`
- **What it does:** Harmonic Lissajous pattern generator through additive synthesis. Creates circles with x=sin(t), y=cos(t) and combines up to 8 harmonic frequencies (each multiplied by harmonic number). Includes volume randomization, fine frequency control, and pattern animation. Produces the most complex and musically rich oscilloscope patterns.
- **Key parameters:** Harmonic count (up to 8), harmonic levels, fine frequency, volume randomization, animation speed
- **Reach for this when:** you need additive oscilloscope synthesis, complex Lissajous patterns, or harmonically rich visual-audio generation

---

## User M4L — Sonus Dept. Abstructs

> 12 Max for Live devices for abstract electronic music and sound art. All parameters automatable. Requires Live Suite 10.1.30+ or Standard with Max for Live. Price: 15 EUR.

---

### SpectroGlitch

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("SpectroGlitch")`
- **What it does:** Randomly suppresses or inverts the magnitude or phase of the incoming signal's spectrum. FFT-based destruction that operates on individual frequency bins, creating spectral holes, phase inversions, and unpredictable timbral mutations. The most immediately destructive spectral effect in the collection.
- **Key parameters:** Magnitude suppression probability, phase inversion probability, FFT size, randomization rate, mix
- **Reach for this when:** you need spectral destruction, random frequency-bin manipulation, glitchy timbral mutation, or unpredictable spectral effects
- **Pairs well with:** Reverb (smooth out the chaos), Compressor (tame transient spikes from phase inversion), Spectral Time (freeze then glitch)

---

### SpectroSynth

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("SpectroSynth")`
- **What it does:** Compact polyphonic synthesizer that creates sounds from a wide and complex spectral timbre. Generates dense spectral content ideal for rich atmospheres, drones, and evolving pads. Designed for abstract/ambient sound creation.
- **Key parameters:** Spectral complexity, timbre control, polyphony, envelope, filter, mix
- **Reach for this when:** you need dense spectral atmospheres, abstract polyphonic pads, or complex-timbre synthesis for ambient/experimental music

---

### BrokenDelays

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("BrokenDelays")`
- **What it does:** Delay effect featuring up to 16 delay lines that abruptly change their lengths and playback probability on rhythmic intervals. Creates never-repeating bizarre delay patterns from mundane audio input. Each delay line has independent chance-to-play, creating probabilistic rhythmic delay textures.
- **Key parameters:** Delay line count (up to 16), length range, change rate (rhythmic), probability per line, feedback, mix
- **Reach for this when:** you need chaotic multi-delay textures, probabilistic rhythmic delays, never-repeating echo patterns, or controlled delay-line randomization
- **Pairs well with:** SpectroGlitch (destroy then delay), Beat Repeat (stutter into broken delays), Filter (shape the chaotic output)

---

### Disturbances

- **Type:** M4L Audio Effect / Generator
- **Load via:** `find_and_load_device("Disturbances")`
- **What it does:** Generator of stutters and noise interference applied to incoming audio. Injects controlled disruptions -- buffer stutters, noise bursts, signal interruptions -- into the audio stream. Creates the sound of a malfunctioning system, broken transmission, or corrupted playback.
- **Key parameters:** Stutter rate, noise intensity, interference type, probability, mix
- **Reach for this when:** you need transmission-error aesthetics, controlled signal disruption, noise interference, or stutter generation layered onto existing audio
- **Pairs well with:** Lofi (Confetti), Redux, BrokenDelays (chain for maximum disruption)

---

### Other Abstructs Devices (brief reference)

- **AbstractSynth** (Instrument) → atmospheric polyphonic synth with dense evolving spectrum → drones, pads, atmospheres
- **BiShift** (Effect) → independent magnitude/phase spectrum shifting → strange pitch-shifting that separates spectral components
- **Essential** (Effect) → analyzes spectrum, returns only prominent features → spectral reduction, abstract spiraling textures with reverb
- **FromOuterSpace** (Instrument) → drone generator → sustained evolving drones
- **InfiniteTrain** (Generator) → pulse-train generator → abstract punctiform patterns for glitch/minimal music
- **MadHatter** (Instrument) → polyphonic hi-hat synth that doubles as unusual synthesizer → metallic textures, hi-hat synthesis
- **OneToMany** (Sampler) → 32-voice sample player with per-trigger parameter randomization → unpredictable variations from single sample
- **SineBursts** (Instrument) → high-pitched sounds, noises, and glitches → sine-based glitch generation

---

## User M4L — Altar of Wisdom

---

### GrainTable v0.6.1

- **Type:** M4L Instrument
- **Load via:** `find_and_load_device("GrainTable_AoW")`
- **What it does:** Recreates the Access Virus TI/TI2 graintable synthesis mode in Max for Live. Uses wavetable carrier modulated by slave wavetables with pulse-width compression for sync-like sounds. Historically significant in psytrance production. Supports up to 256 wavetable files per folder, drag-and-drop loading, and custom waveform drawing.
- **Key parameters:**
  - **Slave Wavetable:** wavetable file/folder, wavetable size, wave number, note-dependent randomization, two alternating oscillators with independent pitch detuning
  - **Carrier (AM):** waveform (Sine / Triangle / Saw up / Saw down / Custom), import/export custom waveforms, amplitude modulation depth
  - **GrainTable Engine:** Pulse Width (PW) → compresses slave wavetable for sync-like effect; PW amplitude, interpolation, glide smoothing
  - **Signal Processing:** ADSR envelope with velocity sensitivity, multimode multislope filter with cutoff randomization, waveshaper with S-curve saturation, output volume
  - **Display:** real-time oscilloscope
- **Compatibility:** Live 10.1.41+, Live 11, Live 12; Max 8.1.5+
- **Reach for this when:** you need Virus-style graintable synthesis, wavetable-based psytrance leads, or complex modulated wavetable timbres

---

### AUTOGLITCH v1.1

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("AUTOGLITCH_AoW")`
- **What it does:** Random multi-effect glitch generator built around a step sequencer engine (borrowed from AutoPlay). The sequencer controls not just volume but an entire chain of effects. At its heart is a stutter engine that decomposes each step into up to 32 sub-glitches played forward or backward at up to 8x speed. After stuttering: repanning, bitcrush/downsample, pitch/frequency shifting (±48 semitones), comb filter, multimode filter, and a delayed feedback loop that can feed back into 3 different sections.
- **Key parameters:**
  - **Step Sequencer:** step count, step length, random parameter section per step
  - **Stutter Engine:** sub-glitch count (up to 32), direction (forward/backward), speed multiplier (up to 8x), stutter probability
  - **Repan Section:** stereo repositioning per step
  - **Bitcrush/Downsample:** bit depth, sample rate reduction
  - **Pitch/Frequency Shifter:** ±48 semitones range
  - **Comb Filter:** delay, feedback, frequency
  - **Multimode Filter:** type, cutoff, resonance
  - **Feedback Loop:** routes output back to 3 selectable insertion points
  - **Loop Mode** (v1.3.2+): engine loops from 1/8th to 16 bars for repeatable stutter patterns
- **Compatibility:** Live 10.1.41+, Live 11, Live 12
- **Reach for this when:** you need automated multi-effect glitch sequences, complex stutter patterns with pitch/filter/bitcrush per step, or controllable chaos with repeatable loop option
- **Pairs well with:** AutoGrid (sequence the source), Beat Repeat (additional stutter layer), Reverb (smooth the chaos)

---

### AUTOGRID4 v1.8

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("AUTOGRID4_AoW")`
- **What it does:** Random grid pattern generator that creates stutter patterns from up to 4 incoming audio tracks mixed with the current track. Generates complex FM-style patterns, sequenced arpeggios, and basslines from multiple sources, ensuring sounds never overlap. Used by major psytrance artists (Tristan, Jumpstreet).
- **Key parameters:**
  - **Input Sources:** up to 4 incoming tracks (AutoGrid8 variant handles 8)
  - **Signal Levels:** per-source volume control
  - **Occurrence Weight:** probability control per source sound
  - **Time Allocation:** duration range from 1/32 to 8 bars including dotted and triplet notes
  - **Min/Max Length:** per-note minimum and maximum duration
  - **Mix Amount:** balance between current track and stutter output
  - **Stutter Probability:** chance of inserting random silences
  - **Ducking:** optional sidechain ducking of current track
- **Variants:** AutoGrid4 (4 inputs), AutoGrid8 (8 inputs), AutoGrid MIDI Edition (8 MIDI channels)
- **Compatibility:** Live 10.1.41+, Live 11, Live 12
- **Reach for this when:** you need multi-source grid stuttering, probabilistic pattern generation from multiple tracks, or psytrance-style grid sequencing

---

## User M4L — Other Experimental

---

### Grain Forest (Dillon Bastan / Isotonik)

- **Type:** M4L Audio Effect / Instrument
- **Load via:** `find_and_load_device("Grain Forest")`
- **What it does:** Granular synthesizer/effect driven by a simulated forest ecosystem. Each "tree" is an independent grain/voice with its own DNA that modulates playback and FX parameters. Trees cross-pollinate, mix DNA, and create new seeds with optional mutations, causing the sound to evolve organically over time. Supports up to 4 audio source mixes (Soil) that trees sample from.
- **Key parameters:**
  - **Soil (Audio Sources):** up to 4 mixes from: direct audio input, routed track audio, dropped audio file (repitchable)
  - **Forest Simulation:** tree count, DNA parameters per species (up to 4 species), pollination rate, mutation probability, generation speed
  - **Grain Controls:** grain size, direction, pitch, position
  - **FX Section:** multimode filter, delay, gain, pan per grain
  - **Motion:** 2 LFOs with Perlin noise option for dynamic movement
  - **Playback Modes:** Grain mode, Spectral mode, Time-based mode
- **Price:** $15+ USD
- **Compatibility:** Live 10+, Live 11, Live 12 with Max for Live
- **Reach for this when:** you need evolving granular textures that change over time without automation, nature-inspired generative processing, or multi-source granular with evolutionary behavior
- **Pairs well with:** Reverb (soften the granular edges), Spectral Resonator (resonate the grains), Compressor (tame evolving dynamics)

---

### Particle-Reverb 7.0 (Kentaro Suzuki)

- **Type:** M4L Audio Effect (also available as VST3/AU)
- **Load via:** `find_and_load_device("Particle-Reverb")`
- **What it does:** Granular network reverb built on 4 discrete granular units with distinct characteristics. Operates entirely in time-domain using granular synthesis (no FFT or conventional delay trains). Internal feedback logic tracks size and pitch adjustments with near-instantaneous response. Four units mapped to dual pitch-shift coordinates generate complex non-linear resonance. Includes 4 built-in modulator modules.
- **Key parameters:**
  - **4 Granular Units:** each with independent size, pitch, density, character
  - **Pitch Shift Coordinates:** dual-axis pitch mapping across units → non-linear resonance
  - **Modulator Modules:**
    - **mod-d3** → xyzw-axis controller (4D modulation)
    - **mod-atrg** → slew-modulated trigger
    - **lfo-morf** → compact dual-axis wavetable LFO
    - **lfo-pnoise** → structured chaos LFO (Perlin noise)
  - **Global:** size, feedback, mix, all parameters continuously modulatable
- **Price:** $60
- **Compatibility:** Live 10.1+, Live 11, Live 12; also VST3/AU for other DAWs; macOS 10.12+ (Universal), Windows 10+
- **Reach for this when:** you need granular reverb with non-linear resonance, pitch-shifted reverb networks, or heavily modulated spatial effects that go far beyond conventional reverb
- **Pairs well with:** Spectral Time (freeze into particle reverb), Grain Delay (granular chain), Auto Filter (shape the reverb tail)

---

### GrainFreeze 2.0 (Robert Henke / Monolake)

- **Type:** M4L Audio Effect
- **Load via:** `find_and_load_device("GrainFreeze")`
- **What it does:** Granular audio freezer that captures audio in real time and scrubs through the captured buffer using granular playback. Press "Ready" to capture a 3-second buffer, then manipulate position, grain size, and other parameters to create textures from rhythmic deconstruction to massive static sound smears. CPU-efficient, simple interface, hackable.
- **Key parameters:**
  - **Ready** (toggle) → arm/capture audio buffer (3-second default)
  - **Position** → scrub through captured buffer → automate for evolving textures
  - **Grain Size** → size of playback grains → small = buzzy/granular, large = smooth/sustained
  - **Pitch** → grain playback pitch
  - **Density** → grain overlap/density
  - **Mix** → dry/wet balance
- **Price:** Free (Creative Commons Attribution-ShareAlike)
- **Compatibility:** Live 8.1+, Max 5.1.8+ (works in all modern Live versions)
- **Reach for this when:** you need simple real-time granular freeze, textural sustain from any audio, or a lightweight granular buffer effect
- **Pairs well with:** Spectral Time (spectral freeze + granular freeze in series), Reverb (post-freeze wash), Auto Filter (movement on frozen textures)
- **vs Spectral Time Freeze:** GrainFreeze operates in time domain (grain buffer); Spectral Time freezes in frequency domain (FFT snapshot). GrainFreeze has position scrubbing; Spectral Time has per-frequency delay. Use both for different freeze characters.

---

## Quick Decision Matrix

| Need | First Choice | Why | Runner-Up |
|------|-------------|-----|-----------|
| **Spectral freeze / drone** | Spectral Time | FFT freeze with fade control, up to 8 stacked freezes | GrainFreeze (time-domain alternative) |
| **Per-frequency delay** | Spectral Time | Tilt, Spray, Mask give per-bin delay control | Grain Delay (time-domain granular delay) |
| **Pitched resonance from any audio** | Spectral Resonator | FFT partials with MIDI control, stretch, harmonics | Corpus (physical modeling resonance) |
| **Physical material resonance** | Corpus | 7 real object models, MIDI sidechain tuning | Spectral Resonator (digital/alien character) |
| **Granular texture** | Grain Delay | Simple, effective, built-in, automatable | Cloud (Confetti, FluCoMa decomposition) |
| **Evolving granular ecosystem** | Grain Forest | DNA/mutation system, multi-source, self-evolving | Particle-Reverb (granular network reverb) |
| **Glitch stutter (rhythmic)** | Beat Repeat | Beat-aligned capture, grid, chance, Insert mode | AUTOGLITCH (multi-effect stutter sequencer) |
| **Glitch stutter (multi-FX)** | AUTOGLITCH | 32 sub-glitches, pitch/filter/bitcrush per step | Beat Repeat (simpler, native) |
| **Multi-source grid stutter** | AUTOGRID4 | 4-track probabilistic pattern mixing | Beat Repeat + routing (manual approach) |
| **Spectral destruction** | SpectroGlitch | Random magnitude/phase suppression per bin | Grain Delay (high Spray + Random Pitch) |
| **Chaotic multi-delay** | BrokenDelays | 16 delay lines with probabilistic playback | Echo (feedback + modulation chaos) |
| **Signal disruption / noise** | Disturbances | Stutters + noise interference generator | Lofi (Confetti, codec artifacts) |
| **Waveset manipulation** | Chopper (Confetti) | Zero-crossing segmentation and resynthesis | Grain Delay (granular alternative) |
| **CD-skip glitch** | Skipper (Confetti) | Onset-triggered buffer skip, Discman models | Beat Repeat (similar stutter concept) |
| **Wavefolding distortion** | Wavefolder (Confetti) | Buchla/Aalto/Cold Mac algorithms | Saturator (simpler, native) |
| **Analog filter character** | Filter (Confetti) | MS-20, Moog, Sallen-Key topologies | Auto Filter (native, simpler) |
| **Whammy pitch glitch** | Pitch (Confetti) | PSOLA Whammy-style with dirty/random modes | Grain Delay (pitch parameter) |
| **Granular reverb** | Particle-Reverb | 4 granular units, non-linear resonance, 4D mod | Hybrid Reverb (native, convolution+algo) |
| **Granular buffer freeze** | GrainFreeze | Simple capture + scrub, CPU-light, free | Spectral Time (FFT freeze, more parameters) |
| **Virus graintable synth** | GrainTable | Virus TI2 graintable recreation, PW control | Wavetable (native, different character) |
| **Oscilloscope visuals** | sincos 4001 | 8 harmonics, most complex Lissajous patterns | radar (most versatile, extensive presets) |
| **Oscilloscope monitor** | Oscilloscope 2.0 | Visualizer for any stereo audio as XY scope | (put at end of chain) |
| **Dense spectral atmosphere** | SpectroSynth | Polyphonic, complex timbre, ideal for ambient | AbstractSynth (evolving spectrum) |
| **Onset-reactive delay** | Dub (Confetti) | Onset-triggered, dub snare + Karplus-Strong | Echo (native, character delay) |
| **Lo-fi degradation** | Lofi (Confetti) | Bit/sample rate + bitwise + MP3 compression | Redux (native, simpler) |

---

### Suggested Chains for Experimental Sound Design

**Spectral Drone Engine:**
Audio → Spectral Time (Freeze, Retrigger Sync 2 bars, Crossfade) → Spectral Resonator (long Decay, Wander mod, 4 Unison) → Hybrid Reverb (Shimmer algo) → Utility (Bass Mono)

**Glitch Destruction Chain:**
Audio → Beat Repeat (Grid 1/32, Variation 100%, Insert) → AUTOGLITCH (32 sub-glitches, feedback loop) → SpectroGlitch → BrokenDelays (8 lines) → Compressor (catch peaks)

**Granular Texture Stack:**
Audio → Grain Delay (high Freq, moderate Spray, +5 Pitch) → Grain Forest (4 species, high mutation) → Particle-Reverb (mod-d3 active) → EQ Eight (shape)

**Physical → Spectral Resonance:**
Noise/Click → Corpus (Plate, MIDI sidechain) → Spectral Resonator (MIDI, Granular mod) → Spectral Time (Delay, Tilt, Spray) → Reverb

**Lo-Fi Experimental:**
Audio → Lofi (Confetti, low bit depth) → Chopper (waveset resynthesis) → Skipper (CD skip) → Dirt (cubic distortion) → Filter (MS-20 LP, resonant) → Dub (onset delay)

**Oscilloscope Performance:**
MIDI → sincos 4001 (harmonics) → SpectroGlitch (subtle, 20% wet) → Grain Delay (shimmer) → Oscilloscope 2.0 (monitor)

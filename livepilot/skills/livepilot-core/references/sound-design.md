# Sound Design — Instruments, Effects & Recipes

Ableton Live's stock instruments and effects with key parameters, typical values, and sound design starting points. Use these as launch pads — every sound should be shaped by context.

## Stock Instruments

### Analog (Subtractive Synth)
Two oscillators + noise → two filters → two amplifiers. Classic analog-modeled subtractive synthesis.

**Key parameters:**
- `Osc1 Shape` / `Osc2 Shape` — Saw, Square/Pulse, Sine, Noise
- `Osc1 Octave` / `Osc2 Octave` — -3 to +3
- `Osc2 Detune` — Fine detune for thickness (-1.0 to 1.0 semitones)
- `Filter1 Type` — LP12, LP24, BP, HP, Notch
- `Filter1 Freq` — Cutoff frequency (20 Hz - 20 kHz)
- `Filter1 Res` — Resonance (0 to 1.0)
- `Fil1 Env Amount` — Filter envelope depth
- `Amp1 Attack` / `Decay` / `Sustain` / `Release` — ADSR envelope
- `LFO1 Rate` / `Amount` — Modulation speed and depth

### Wavetable (Wavetable Synth)
Two wavetable oscillators with continuous morphing, sub oscillator, and powerful modulation.

**Key parameters:**
- `Osc 1 Pos` — Wavetable position (0-1, morphs through waveforms)
- `Osc 1 Effect` — FM, Classic, Modern, formant effects on the wavetable
- `Sub Osc` — Sub oscillator (-2 to 0 octaves, sine/triangle)
- `Filter Type` — LP/HP/BP with various slopes
- `Filter Freq` — Cutoff
- `Filter Res` — Resonance
- `Mod Matrix` — Map any source (LFO, envelope, velocity, etc.) to any parameter
- `Unison Voices` — 1-8 voices for supersaw/thick sounds
- `Unison Amount` — Detune spread between voices

### Operator (FM Synth)
Four oscillators (operators) that can modulate each other's frequency. 11 algorithms define the routing.

**Key parameters:**
- `Algorithm` — Routing topology (1-11). Algorithm 1 = all serial (most harmonics). Algorithm 11 = all parallel (additive).
- `Osc A-D Coarse` — Frequency ratio (0.5, 1, 2, 3... harmonic ratios)
- `Osc A-D Level` — Output level / modulation amount
- `Osc A-D Waveform` — Sine, Saw, Square, Triangle, Noise
- `Filter Freq` / `Res` — Global filter
- `LFO Rate` / `Amount` — Vibrato, tremolo
- `ADSR per operator` — Each operator has its own envelope

### Drift (Analog-Modeled)
Simple, characterful analog synth with built-in instability and warmth.

**Key parameters:**
- `Shape` — Oscillator shape (continuous morph)
- `Drift` — Amount of analog-style instability
- `Filter` — Low-pass filter with resonance
- `Envelope` — Attack/Decay/Sustain/Release
- `Voice Mode` — Mono, Poly, Unison
- `Modulation` — Built-in LFO and envelope routing

### Simpler (Sample Player)
One-shot or looped sample playback with filter, envelope, LFO, and warp modes.

**Key parameters:**
- `Mode` — Classic (one-shot), One-Shot, Slicing
- `Start` / `End` — Sample region
- `Loop` — On/off, loop start/length
- `Filter Type` / `Freq` / `Res` — Sample filtering
- `Amp Envelope` — ADSR for amplitude
- `Warp` — Time-stretch sample to tempo
- `Voices` — Polyphony count
- `Spread` — Stereo spread for polyphonic voices

### Drum Rack
Container that maps samples/instruments to MIDI notes (pads). Each pad is a chain.

**Key concepts:**
- 128 pads (MIDI 0-127), typically using 36-51 (C1-D#2)
- **Choke groups**: Assign pads to same group — triggering one silences others (e.g., open/closed hi-hat)
- Each pad has its own chain: sample player + effects
- **Macro knobs**: 8 knobs that can control parameters across multiple chains
- Sends A/B per pad for internal effects routing

### Other Instruments
- **Sampler** — Advanced multi-sample instrument with zones, layers, modulation matrix
- **Tension** — Physical modeling of strings (pluck, bow, hammer)
- **Collision** — Physical modeling of mallet instruments (bars, membranes, plates)
- **Electric** — Electric piano modeling (tine, reed, pickup, damper)
- **Meld** — MPE-capable synth with two engines and a mixer

## Stock Audio Effects

### Dynamics

**Compressor**
- `Threshold` — Level where compression starts (dB)
- `Ratio` — Compression ratio (1:1 to inf:1)
- `Attack` — How fast compression engages (0.01-300ms)
- `Release` — How fast compression releases (1-3000ms)
- `Knee` — Soft/hard knee transition
- `Makeup` / `Output Gain` — Compensate for gain reduction
- `Sidechain` — External input for ducking (key for pumping effects)
- **Modes**: Peak, RMS, Expand, OTT-style multiband (Compressor modes)

**Glue Compressor**
Bus-style compressor modeled on classic mix bus compressors.
- `Threshold`, `Ratio` (2, 4, 10), `Attack`, `Release`
- `Range` — Limits maximum compression
- `Dry/Wet` — Parallel compression in one device
- **Best for**: Drum bus, mix bus, gluing groups together

**Limiter**
- `Gain` — Input gain before limiting
- `Ceiling` — Maximum output level
- `Release` — Auto or manual
- **Use for**: Final output protection, loudness maximizing

**Gate**
- `Threshold` — Level below which audio is muted
- `Attack` / `Hold` / `Release` — Gate timing
- `Return` — Hysteresis (how far below threshold to close)
- **Use for**: Removing bleed, tightening drums, creative gating

**Multiband Dynamics**
Three frequency bands, each with its own compressor/expander.
- `Low` / `Mid` / `High` — Frequency crossover points
- Per-band: `Threshold Above/Below`, `Ratio`, `Attack`, `Release`
- **Use for**: Mastering, de-essing, frequency-specific dynamics

### EQ & Filters

**EQ Eight**
8-band parametric EQ — the workhorse.
- Per band: `Frequency`, `Gain` (dB), `Q` (bandwidth)
- Filter types: LP, HP, Bell, Notch, Low Shelf, High Shelf
- Various slopes: 12dB, 24dB, 48dB per octave
- `Oversampling` — Reduce aliasing at high frequencies

**Auto Filter**
Resonant filter with LFO, envelope follower, and sidechain.
- `Filter Type` — LP/HP/BP/Notch, various slopes
- `Frequency` — Cutoff
- `Resonance` — Q factor
- `LFO Amount` / `Rate` / `Shape` — Filter movement
- `Envelope Amount` / `Attack` / `Release` — Envelope follower
- **Use for**: Sweeps, wobbles, auto-wah, rhythmic filtering

**Channel EQ**
Simple 3-band EQ for quick tonal shaping.
- `Low`, `Mid`, `High` — Gain knobs
- `Mid Freq` — Sweepable mid frequency

### Time-Based

**Reverb**
- `Decay Time` — Reverb tail length (0.2-60s)
- `Pre Delay` — Delay before reverb starts (0-500ms)
- `Room Size` — Early reflection size
- `Diffusion` — Density of reflections
- `High/Low Cut` — EQ the reverb tail
- `Dry/Wet` — Mix (100% wet on return tracks)
- `Freeze` — Infinite sustain of current reverb
- **Types**: Room (short, 0.5-1.5s), Hall (medium, 1.5-4s), Cathedral (long, 4-10s+)

**Delay**
- `Time Left/Right` — Delay time (sync or ms)
- `Feedback` — How much repeats (0-100%)
- `Filter` — LP/HP on feedback path
- `Dry/Wet` — Mix
- `Ping Pong` — Alternates between L/R
- **Common sync values**: 1/4, 1/8, 3/16 (dotted eighth), 1/4T (triplet)

**Echo** (combines delay + reverb + modulation)
- `Left/Right Time` — Delay times
- `Feedback` — Repeat amount
- `Reverb Level` — Built-in reverb
- `Modulation` — Chorus-like movement in delay
- `Ducking` — Delays get quieter when input is playing
- `Gate` — Rhythmic gating of the echo tail

### Distortion & Saturation

**Saturator**
- `Drive` — Amount of saturation
- `Curve Type` — Analog Clip, Soft Sine, Medium Curve, Hard Curve, Sinoid Fold, Digital Clip
- `Output` — Compensate volume
- `Dry/Wet` — Parallel blend
- **Soft Sine**: Warm, subtle. **Sinoid Fold**: Aggressive harmonics. **Analog Clip**: Tape-like.

**Overdrive**
- `Drive` — Distortion amount
- `Tone` — Brightness
- `Dynamics` — Preserves or compresses dynamics
- **Use for**: Guitar-amp style warmth, bass grit

**Erosion**
- Adds digital artifacts: noise, sine wave modulation
- `Amount`, `Frequency`, `Width`
- **Use for**: Lo-fi, bitcrushed textures, digital degradation

**Redux**
- `Downsample` — Reduces sample rate (aliasing)
- `Bit Reduction` — Reduces bit depth (quantization noise)
- **Use for**: 8-bit sounds, lo-fi, retro textures

### Modulation

**Chorus-Ensemble**
- `Rate 1/2` — LFO speeds
- `Amount 1/2` — Modulation depths
- `Feedback` — Flanging intensity
- `Dry/Wet` — Mix
- **Use for**: Thickening, stereo width, classic chorus

**Phaser-Flanger**
- `Rate` — LFO speed
- `Amount` — Modulation depth
- `Feedback` — Intensity/resonance
- **Phaser**: Sweeping notches. **Flanger**: Jet/whoosh effect.

**Frequency Shifter**
- `Frequency` — Shift amount in Hz (not semitones — inharmonic)
- `Drive` — Input gain
- `Dry/Wet` — Mix
- **Use for**: Metallic textures, detuned unease, ring-mod effects

### Utility

**Utility**
Essential for mixing — should be on every track during mix.
- `Gain` — Volume trim (-inf to +35dB)
- `Width` — Stereo width (0=mono, 100=normal, 200=wide)
- `Bass Mono` — Make frequencies below X Hz mono
- `Bass Mono Freq` — Cutoff for mono bass (typically 120-200 Hz)
- `Mute` — Kill switch
- `Phase Invert L/R` — Flip phase
- `Channel Mode` — Left, Right, Both, Swap

## Sound Design Recipes

These are starting points — load the instrument with `find_and_load_device`, then use `batch_set_parameters` to set values. Always `get_device_parameters` first to see exact parameter names.

### Sub Bass (Analog)
Deep, clean low-end foundation.
```
Oscillator 1: Sine wave
Oscillator 2: Off
Filter: LP24, cutoff ~200 Hz, no resonance
Amp Envelope: Attack 0ms, Decay 0ms, Sustain 100%, Release 100ms
Note range: C0-C2 (MIDI 24-48)
```
- Mono mode (one voice)
- Velocity sensitivity low/off for consistent level

### Reese Bass (Analog or Wavetable)
Thick, detuned, evolving bass for DnB/dubstep.
```
Oscillator 1: Saw wave
Oscillator 2: Saw wave, detune +5-15 cents
Filter: LP24, cutoff ~500 Hz, resonance 20%
Filter Envelope: moderate amount, medium attack (50-200ms)
Unison: 2-4 voices, moderate spread
```
- Automate filter cutoff for movement
- Layer with clean sub (separate track) for low-end clarity

### Pad (Wavetable or Analog)
Warm, evolving background texture.
```
Oscillator: Soft wavetable or saw + triangle
Unison: 4-8 voices, wide spread
Filter: LP, cutoff ~2 kHz, low resonance
Amp Envelope: Attack 200-800ms, Decay 0, Sustain 100%, Release 500-2000ms
LFO → Filter Cutoff: slow rate (0.1-0.5 Hz), subtle amount
```
- Add Chorus-Ensemble for extra width
- Add Reverb (hall, 3-5s decay, 30-50% wet)
- Velocity → filter cutoff for expressiveness

### Pluck (Analog or Wavetable)
Short, percussive melodic sound.
```
Oscillator: Saw or square
Filter: LP24, cutoff ~1 kHz, moderate resonance (30-50%)
Filter Envelope: Amount high, Attack 0, Decay 100-300ms, Sustain 0%, Release 50ms
Amp Envelope: Attack 0, Decay 200-400ms, Sustain 0%, Release 100ms
```
- Short decay = harp-like. Longer decay = guitar-like.
- Add short reverb (room, 0.5-1s) for space

### Lead (Analog or Operator)
Cutting melodic line that sits on top of the mix.
```
Oscillator: Square or saw
Filter: LP or BP, cutoff ~3 kHz, moderate resonance
Amp Envelope: Attack 5-20ms, Decay 200ms, Sustain 70%, Release 200ms
Portamento/Glide: On (50-100ms) for mono mode
```
- Add Delay (1/8 or dotted 1/8, 30% feedback, 20% wet)
- Add subtle Reverb (plate, 1-2s)
- Use Saturator lightly for presence

### Supersaw (Wavetable)
Classic trance/EDM lead/pad.
```
Oscillator: Saw wavetable
Unison: 7-8 voices
Unison Amount: High (wide detune)
Filter: LP, cutoff ~5 kHz, low resonance
Amp Envelope: Attack 2ms, Sustain 100%, Release 300ms
```
- Layer with sub sine one octave below
- Chorus or Ensemble for extra width
- Stereo Delay (1/8 L, dotted 1/8 R)

### Texture / Ambient (Wavetable + Effects)
Evolving atmospheric sound.
```
Oscillator: Complex wavetable, automate position slowly
Filter: BP, slowly sweeping frequency
Amp Envelope: Slow attack (500ms-2s), long release (3-5s)
LFO: Multiple slow LFOs mapped to position, filter, pitch (subtle)
```
- Heavy Reverb (5-10s decay, high diffusion, 80-100% wet)
- Delay with high feedback (60-80%), filtered
- Frequency Shifter at very small values (+/- 1-5 Hz) for movement
- Grain Delay for granular textures

### 808 Bass (Simpler or Drum Rack)
Pitched sub with distortion for trap/hip-hop.
```
Sample: 808 kick or sine with fast pitch envelope
Amp Envelope: Attack 0, Decay 1-3s (long tail), Sustain 0%
Tuning: Tune to song key
```
- Add Saturator (soft sine or analog clip) for upper harmonics
- Set Simpler to mono
- Duration determines how long the 808 rings

## Device Chain Patterns

### Standard Insert Chain (on a track)
```
EQ Eight (surgical cuts) → Compressor → Saturator (subtle) → EQ Eight (tonal shaping) → Utility (final trim)
```

### Vocal Chain
```
EQ Eight (HP at 80 Hz, cut mud at 300 Hz) → Compressor (4:1, medium attack) → De-esser (Multiband Dynamics, high band) → EQ Eight (presence boost at 3-5 kHz) → Reverb (20-30% wet, plate)
```

### Drum Bus Chain
```
EQ Eight (HP at 30 Hz) → Glue Compressor (4:1, 10ms attack, 100ms release) → Saturator (subtle drive for warmth) → Utility (trim)
```

### Parallel Compression Setup
Using Audio Effect Rack:
- Chain A: Dry (no processing)
- Chain B: Compressor (heavy — 10:1, fast attack, fast release, low threshold) → balance chain volume

Or using Return track:
1. `create_return_track` for parallel compression
2. Add Compressor with extreme settings on the return
3. Use `set_track_send` to feed signal to the return
4. Blend return level to taste

### Sidechain Ducking Setup
1. Load Compressor on the track to be ducked (bass, pads)
2. Enable Sidechain in Compressor
3. Route kick track to sidechain input
4. Settings: Ratio 4:1-inf:1, Attack 0.1ms, Release 50-200ms, Threshold low
5. Adjust release to match tempo (longer for slower tempos)

## Creative Effects Techniques

### Reverb Freeze
Set Reverb's Freeze parameter to capture and infinitely sustain the current sound. Automate on/off for dramatic transitions.

### Delay Feedback Washes
Automate Delay feedback above 100% briefly — the delay builds and self-oscillates. Pull back before it gets out of control. Great for transitions.

### Beat Repeat (Stock Effect)
Repeats/stutters incoming audio rhythmically.
- `Grid` — Repeat size (1/4 to 1/32)
- `Chance` — Probability of repeating
- `Gate` — How long the repeat runs
- Great for glitch, fills, and transitions

### Grain Delay
Granular delay that can pitch-shift and scatter audio.
- `Pitch` — Transpose the grains
- `Spray` — Randomize grain position
- `Frequency` — Grain rate
- Great for ambient textures and otherworldly effects

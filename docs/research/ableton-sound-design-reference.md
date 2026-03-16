# Ableton Live 12 — Sound Design & Device Parameter Reference

Research compiled 2026-03-17 from ableton.com documentation, reference manuals, blog posts, and community resources.

---

## 1. Stock Instruments — Detailed Parameters

### 1.1 Analog (Virtual Analog / Subtractive Synth)

Created with Applied Acoustics Systems. Physical modeling of analog synth components.

**Oscillators (Osc 1 & Osc 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Shape | Sine, Sawtooth, Square, Rectangle, Noise | Waveform type |
| Octave | -3 to +3 | Octave transposition |
| Semi | -12 to +12 | Semitone tuning |
| Detune | -100 to +100 cents | Fine pitch detune |
| Pulse Width | 0% to 100% | Width of pulse waveform (Square/Rectangle only) |
| Sub Level | 0% to 100% | Sub-oscillator level (one octave below) |
| Sub Shape | Sine, Square | Sub-oscillator waveform |
| Hard Sync | On/Off | Sync Osc 2 to Osc 1 |
| Pitch Env Amount | -48 to +48 st | Pitch envelope modulation depth |

**Noise Generator**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Level | -inf to 0 dB | Noise output level |
| Color | -100% to +100% | Noise brightness (neg = darker, pos = brighter) |

**Filters (Filter 1 & Filter 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | LP12, LP24, BP6, BP12, HP12, HP24, Notch, Formant | Filter mode |
| Frequency | 20 Hz to 20 kHz | Filter cutoff frequency |
| Resonance | 0% to 100% | Filter resonance / Q |
| Key Track | 0% to 100% | Keyboard tracking amount |
| Env Amount | -100% to +100% | Filter envelope modulation depth |
| Drive | 0 dB to +36 dB | Input saturation drive |
| Routing | Serial, Parallel | Filter signal routing |

**Amplifiers (Amp 1 & Amp 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Level | -inf to 0 dB | Output level |
| Pan | -100% to +100% | Stereo panning |
| Vel Sens | 0% to 100% | Velocity sensitivity |

**Envelopes (Filter Env, Amp Env per oscillator path)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Attack | 0 ms to 20 s | Attack time |
| Decay | 0 ms to 20 s | Decay time |
| Sustain | 0% to 100% | Sustain level |
| Release | 0 ms to 20 s | Release time |
| Mode | ADSR, ADS-R, Loop | Envelope mode (ADS-R replays attack on release) |
| Vel Mod | 0% to 100% | Velocity modulation of envelope |

**LFOs (LFO 1 & LFO 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Shape | Sine, Triangle, Square, Random S&H, Random Smooth | Waveform |
| Rate | 0.01 Hz to 30 Hz (or tempo-synced) | LFO speed |
| Sync | On/Off | Sync to song tempo |
| Retrigger | On/Off | Restart LFO on note-on |
| Offset | 0 to 360 degrees | Phase offset |
| Delay | 0 ms to 10 s | Delay before LFO onset |
| Attack | 0 ms to 10 s | Fade-in time |
| Width (PW) | 0% to 100% | Pulse width of square LFO |

**LFO Destinations:** Osc 1 Pitch, Osc 2 Pitch, Osc 1 PW, Osc 2 PW, Filter 1 Freq, Filter 2 Freq, Amp 1 Level, Amp 2 Level, Amp 1 Pan, Amp 2 Pan

**Global**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Voices | 2-8 | Polyphony |
| Unison | Off, 2, 4 | Unison mode |
| Unison Detune | 0% to 100% | Unison voice detuning |
| Glide | On/Off | Portamento enable |
| Glide Time | 0 ms to 5 s | Portamento time |
| Volume | -inf to +12 dB | Master output |

---

### 1.2 Wavetable (Wavetable Synth)

Dual wavetable oscillators with sub oscillator, analog-modeled filters, modulation matrix.

**Oscillators (Osc 1 & Osc 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Wavetable Category | Basic Shapes, Complex, Harmonics, Instruments, Noise, etc. | Table category (100+ wavetables total) |
| Wavetable Position | 0 to 255 | Position within wavetable (morphs between waveforms) |
| Osc Effect | None, FM, Classic, Modern, Noise AM, Noise FM | Per-oscillator effect |
| Effect Amount | 0% to 100% | Effect intensity |
| Semi | -24 to +24 st | Semitone tuning |
| Detune | -50 to +50 cents | Fine tuning |
| Gain | -inf to +12 dB | Oscillator level |
| Pan | -100% to +100% | Stereo placement |

**Sub Oscillator**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Shape | Sine, Triangle, Sawtooth, Rectangle | Sub waveform |
| Gain | -inf to +12 dB | Sub level |
| Tone | 0% to 100% | Brightness |
| Octave | -2, -1, 0 | Octave relative to oscillators |

**Filters (Filter 1 & Filter 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | Low Pass, High Pass, Band Pass, Notch, Morph | Filter mode |
| Circuit | Clean, OSR, MS2, SMP, PRD | Analog circuit model |
| Slope | 12 dB, 24 dB | Filter slope |
| Frequency | 20 Hz to 20 kHz | Cutoff frequency |
| Resonance | 0% to 100% | Resonance |
| Drive | 0% to 100% | Filter drive |
| Morph | 0% to 100% | Morphs between LP→BP→HP→Notch→LP (Morph type only) |
| Routing | Serial, Parallel, Split | How oscillators feed into filters |

**Modulation Matrix**

| Sources | Targets (any clickable parameter) |
|---------|----------------------------------|
| Env 1, Env 2, Env 3 | Osc 1/2 Position, Gain, Pan, Effect Amount |
| LFO 1, LFO 2 | Filter 1/2 Frequency, Resonance, Drive |
| Key (MIDI note) | Sub Gain, Tone |
| Velocity | Amp Level |
| Mod Wheel | LFO Rate |
| Aftertouch / Pressure | Master Volume |
| Pitch Bend | Unison Amount |
| Slide (MPE) | Any matrix target |

**Envelopes (Env 1-3)**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Attack | 0 ms to 20 s | Attack time |
| Decay | 0 ms to 60 s | Decay time |
| Sustain | 0% to 100% | Sustain level |
| Release | 0 ms to 60 s | Release time |
| Initial | 0% to 100% | Start level |
| Peak | 0% to 100% | Attack peak level |
| Loop | Off, AD-Loop, ADS-Loop, Beat Sync | Envelope looping |
| Slope | -100% to +100% | Curve shape |

**LFOs (LFO 1 & LFO 2)**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Shape | Sine, Triangle, Saw Up, Saw Down, Square, Random S&H, Random Smooth | Waveform |
| Rate | 0.01 Hz to 30 Hz (or synced) | Speed |
| Amount | -100% to +100% | Per-destination modulation depth |
| Phase | 0 to 360 degrees | Phase offset |
| Offset | -100% to +100% | DC offset |
| Retrigger | On/Off | Reset on note-on |

**Global / Unison**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Voices | 2-8 | Polyphony |
| Unison | Off, Classic, Shimmer, Noise, Phase Sync, Position Spread, Random Note | Unison mode |
| Unison Amount | 0% to 100% | Unison intensity |
| Mono | On/Off | Mono mode |
| Glide | On/Off | Portamento |
| Glide Time | 0 ms to 5 s | Slide time |

---

### 1.3 Operator (FM / Additive / Subtractive Synth)

Four oscillators (operators A-D) with 11 routing algorithms. Each operator can be a carrier (audible) or modulator (modulates another operator's frequency).

**Algorithms (11 total)**

| # | Topology | Character |
|---|----------|-----------|
| 1 | D→C→B→A (all series) | Maximum FM depth, metallic/complex |
| 2 | (C+D)→B→A | Two modulators into one chain |
| 3 | C→B→A, D→A | Parallel + series hybrid |
| 4 | (C→B)+(D)→A | Blended modulation |
| 5 | (C→B)+(D→A) | Two independent FM pairs |
| 6 | D→(A+B+C) | One modulator, three carriers |
| 7 | (D→C)+(A+B) | One FM pair + two additive |
| 8 | A+B+C+D (all parallel) | Pure additive synthesis |
| 9 | (D→C→B)+A | Three-deep FM + one additive |
| 10 | (D→C)+(B→A) | Two 2-deep FM pairs |
| 11 | D→(C→A + B) | Shared modulator branching |

**Operators (A, B, C, D)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Waveform | Sine, Saw, Square, Triangle, Noise, User-drawn (64 partials) | Oscillator waveform |
| Coarse | 0.5 to 48 (ratio) | Frequency ratio to note pitch |
| Fine | -1000 to +1000 cents | Fine frequency offset |
| Fixed | On/Off | Fixed frequency mode (Hz, not ratio) |
| Fixed Freq | 1 Hz to 20 kHz | Frequency when in Fixed mode |
| Level | -inf to 0 dB | Output level (critical for FM depth) |
| Vel Sens | 0% to 100% | Velocity sensitivity of level |
| Key Scaling | 0% to 100% | Higher notes = lower modulator level |
| Feedback | 0% to 100% | Self-modulation feedback (adds harmonics) |

**Operator Envelopes (per operator)**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Attack | 0 ms to 20 s | Attack time |
| Decay | 0 ms to 60 s | Decay time |
| Sustain | -inf to 0 dB | Sustain level |
| Release | 0 ms to 60 s | Release time |
| Initial | -inf to 0 dB | Start level |
| Peak | -inf to 0 dB | Peak level after attack |
| Loop | Off, Loop, Beat, Sync | Envelope looping mode |
| Rate < Key | 0% to 100% | Higher keys = faster envelope |

**Filter Section**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | LP12, LP24, HP12, HP24, BP12, BP24, Notch, Morph | Filter type |
| Frequency | 20 Hz to 20 kHz | Cutoff frequency |
| Resonance | 0% to 100% | Q factor |
| Env Amount | -100% to +100% | Filter envelope modulation |
| Key Track | 0% to 100% | Keyboard tracking |

**LFO**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Shape | Sine, Square, Triangle, Saw Up, Saw Down, Random S&H | Waveform |
| Rate | 0.01 Hz to 30 Hz (or synced) | Speed |
| Amount | 0% to 100% | Depth |
| Destination | Osc A-D Pitch, Filter Freq, Osc A-D Level | Modulation target |

**Pitch Envelope**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Initial | -48 to +48 st | Start pitch offset |
| Peak | -48 to +48 st | Peak pitch after attack |
| Attack | 0 ms to 20 s | Time to peak |
| Sustain | -48 to +48 st | Sustain pitch offset |
| Release | -48 to +48 st | Final release pitch offset |

**Global**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Voices | 1-20 | Polyphony |
| Tone | -100% to +100% | Global brightness |
| Volume | -inf to +12 dB | Master output |
| Glide | On/Off | Portamento |
| Glide Time | 0 ms to 5 s | Portamento time |
| Spread | 0% to 100% | Stereo spread |
| Time | 0% to 200% | Global envelope time scaling |

---

### 1.4 Drift (Analog-Modeled Subtractive Synth)

Lightweight, MPE-capable. Designed for quick sound design with low CPU. Features voice-level drift/instability.

**Oscillators (Osc 1 & Osc 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Osc 1 Shape | Sine, Triangle, Shark Tooth, Saturated, Saw, Pulse, Rectangle | Waveform (Shark Tooth & Saturated are unique to Drift) |
| Osc 2 Shape | Sine, Triangle, Saw, Pulse, Noise | Waveform |
| Shape | 0% to 100% | Shape modulation (e.g., pulse width for Pulse) |
| Octave | -3 to +3 | Octave tuning |
| Semi | -12 to +12 | Semitone tuning |
| Detune | -100 to +100 cents | Fine pitch |
| Osc Mix | 0% to 100% | Balance between Osc 1 and Osc 2 |
| Noise Level | 0% to 100% | Noise generator mix |
| Drift | 0% to 100% | Analog pitch/freq instability per voice (signature control) |

**Filter**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type I | 12 dB LP (DFM-1) | Warm, broad distortion, subtle sweeps to drive |
| Type II | 24 dB LP (Cytomic MS2 Sallen-Key) | Tighter, soft-clipped resonance |
| Frequency | 20 Hz to 20 kHz | Low-pass cutoff |
| Resonance | 0% to 100% | Resonance / self-oscillation |
| HP Freq | 20 Hz to 2 kHz | High-pass filter frequency |
| Key Track | 0.00 to 1.00 | Filter freq follows keyboard pitch |
| Env Amount | -100% to +100% | Filter envelope depth |
| LFO Mod | -100% to +100% | LFO modulation of filter freq |

**Envelopes**

| Envelope | Parameters | Description |
|----------|-----------|-------------|
| Amp Env | Attack (0-10s), Decay (0-60s), Sustain (0-100%), Release (0-60s) | Amplitude envelope |
| Filter Env | Attack (0-10s), Decay (0-60s), Sustain (0-100%), Release (0-60s) | Filter modulation envelope |
| Mod Env | Attack (0-10s), Decay (0-60s), Sustain (0-100%), Release (0-60s) | Assignable modulation envelope |

**LFO**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Shape | Sine, Triangle, Saw, Square, Random S&H, Random Smooth | Waveform |
| Rate | 0.01 Hz to 30 Hz (or synced) | LFO speed |
| Retrigger | On/Off | Restart per note |
| Destinations | Filter Freq, Osc Pitch, Shape, Pan | Modulation targets |

**Modulation Section**

| Source | Targets |
|--------|---------|
| Mod Env | Pitch, Filter Freq, Shape, Osc Mix, Pan |
| LFO | Pitch, Filter Freq, Shape, Amp, Pan |
| Velocity | Filter Freq, Amp, Mod Env Amount |
| Key | Filter Freq |
| Pressure (MPE) | Filter Freq, Pitch, Volume |
| Slide (MPE) | Filter Freq, Shape, Pan |

**Global**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Voices | 1-16 | Polyphony |
| Mono | On/Off | Monophonic mode |
| Glide | On/Off | Portamento |
| Glide Time | 0 ms to 5 s | Portamento speed |
| Hi-Quality | On/Off (context menu) | Higher quality rendering |

---

### 1.5 Meld (MPE Bi-Timbral Hybrid Synth)

Live 12 addition. Two independent macro oscillator engines with extensive modulation matrix. Excels at textural, harmonic, atonal, and rhythmic sounds.

**Engines (A & B)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Oscillator Type | 24 types per engine (6 are scale-aware) | Synthesis algorithm |
| Macro 1 | Context-dependent (changes per osc type) | Primary timbre control |
| Macro 2 | Context-dependent | Secondary timbre control |
| Octave | -3 to +3 | Octave |
| Semi | -12 to +12 | Semitone |
| Detune | -100 to +100 cents | Fine tuning |
| Level | -inf to 0 dB | Engine volume |
| Pan | -100% to +100% | Stereo position |

**Oscillator Types Include:**
- Dual Basic Shapes (subtractive waveforms)
- FM oscillators (2-op, 3-op configurations)
- Granular engines
- Noise looping
- Ambient generation algorithms
- Swarm/unison engines
- Harmonic/inharmonic generators
- Scale-aware oscillators (quantize to current scale)

**Filters (per engine)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | LP, HP, BP, Notch, Morph | Filter mode |
| Frequency | 20 Hz to 20 kHz | Cutoff |
| Resonance | 0% to 100% | Q |
| Routing | Pre-Mix, Post-Mix | Filter position in signal path |

**Modulation Matrix**

| Sources | Targets |
|---------|---------|
| Env A, Env B (per-engine) | Engine A/B Macros 1 & 2 |
| Mod Env A, Mod Env B | Engine A/B Level, Pan, Pitch |
| LFO 1, LFO 2 | Filter A/B Freq, Resonance |
| Velocity | Any matrix target |
| Key | Any matrix target |
| Aftertouch / Pressure (MPE) | Any matrix target |
| Slide (MPE) | Any matrix target |
| Mod Wheel | Any matrix target |
| Random (per-voice) | Any matrix target |

**Global**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Engine Mix | 0% to 100% | A/B balance |
| Voices | 2-16 | Polyphony |
| Mono | On/Off | Mono mode |
| Glide | On/Off | Portamento |
| Scale Awareness | On/Off | Quantize scale-aware oscillators |

---

### 1.6 Simpler (Sample Instrument)

Three playback modes: Classic, 1-Shot, Slice.

**Sample Controls**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Mode | Classic, 1-Shot, Slice | Playback mode |
| Start | 0% to 100% | Sample start point |
| End | 0% to 100% | Sample end point |
| Loop Start | 0% to 100% | Loop region start |
| Loop Length | 0% to 100% | Loop region length |
| Loop Fade | 0% to 100% | Crossfade at loop point |
| Warp | On/Off | Time-stretch to tempo |
| Warp Mode | Beats, Tones, Texture, Re-Pitch, Complex, Complex Pro | Stretch algorithm |
| Transpose | -48 to +48 st | Pitch transposition |
| Detune | -50 to +50 cents | Fine tuning |
| Voices | 1-32 | Polyphony |
| Retrigger | On/Off | Retrigger on same note |
| Gain | -inf to +36 dB | Sample gain |

**Slice Mode**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Slice By | Transient, Beat, Region, Manual | Slicing method |
| Sensitivity | 0% to 100% | Transient detection sensitivity |
| Division | 1/4, 1/8, 1/16, etc. | Beat division for beat-slicing |
| Regions | 2-64 | Number of equal regions |
| Playback | Mono, Poly, Thru | Slice playback mode |
| Trigger | Gate, Trigger | Note behavior |
| Nudge | -100 to +100 ms | Slice offset |
| Fade In / Out | 0 ms to 100 ms | Per-slice crossfade |

**Filter**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | LP12, LP24, HP12, HP24, BP12, BP24, Notch, Morph | Filter type |
| Frequency | 20 Hz to 20 kHz | Cutoff |
| Resonance | 0% to 100% | Q |

**Envelopes**

| Envelope | Params | Description |
|----------|--------|-------------|
| Amp | Attack, Decay, Sustain, Release | Volume envelope |
| Filter | Attack, Decay, Sustain, Release, Amount | Filter modulation |
| Pitch | Initial, Peak, Time, Amount | Pitch envelope |

**LFO**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Shape | Sine, Square, Triangle, Saw Up, Saw Down, Random | Waveform |
| Rate | Free or synced | LFO speed |
| Destinations | Filter Freq, Pitch, Pan, Volume | Targets |

---

### 1.7 Sampler (Advanced Multi-Sample Instrument)

Multi-zone sample mapping with extensive modulation. Zones: Sample, Pitch, Filter, Oscillator, Modulation.

**Zone System**

| Zone Type | Purpose |
|-----------|---------|
| Key Zone | Map samples across keyboard range |
| Velocity Zone | Map samples by velocity range |
| Sample Select Zone | Crossfade between layers via chain selector |

**Sample Tab**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Root Key | C-2 to G8 | Reference pitch for sample |
| Detune | -50 to +50 cents | Fine tuning |
| Volume | -inf to +36 dB | Per-sample level |
| Pan | -100% to +100% | Per-sample panning |
| Reverse | On/Off | Reverse playback |
| Snap | On/Off | Snap to zero-crossings |

**Modulation Tab (3 Envelopes, 3 LFOs, 3 Aux Sources)**

| Source | Destinations |
|--------|-------------|
| Env 1-3 (AHDSR) | Volume, Pan, Pitch, Filter Freq, Res, LFO Rate, Sample Offset |
| LFO 1-3 | Volume, Pan, Pitch, Filter Freq, Res, Sample Offset |
| Aux: Velocity, Key, Random, Aftertouch, Mod Wheel | All modulation targets |

**Pitch Tab**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Spread | 0 to 100 cents | Random pitch spread |
| Pitch Bend Range | 0 to 24 st | Pitch bend range |
| Glide | On/Off | Portamento |
| Glide Time | 0 ms to 5 s | Portamento speed |

---

### 1.8 Drum Rack

128 pads (MIDI notes 0-127), each with independent instrument/effects chain.

**Per-Pad Controls**

| Parameter | Description |
|-----------|-------------|
| Receive | MIDI note assignment (C-2 to G8, or "All Notes") |
| Play | Which note the pad's instrument receives |
| Choke | Choke group (1-16). Pads in same group cut each other off |
| Volume | Pad volume (-inf to +6 dB) |
| Pan | Pad panning (-50 to +50) |
| Send A-F | Send levels to internal return chains |
| Solo | Solo this pad |
| Mute | Mute this pad |

**Return Chains**

| Parameter | Description |
|-----------|-------------|
| Up to 6 return chains | Audio effect chains fed by per-pad sends |
| Each has independent volume, pan, mute, solo | Parallel effects processing |

**Macro Controls:** Up to 16 macro knobs mappable to any parameter in any pad's device chain.

---

### 1.9 Tension (Physical Modeling — Strings)

Created with Applied Acoustics Systems. Models exciter + string + body.

**Exciter Section**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | Bow, Hammer, Plectrum | Excitation method |
| Force / Velocity | 0% to 100% | Excitation intensity |
| Friction (Bow) | 0% to 100% | Bow friction |
| Stiffness (Hammer) | 0% to 100% | Hammer hardness |
| Position | 0% to 100% | Excitation position on string |
| Damping | 0% to 100% | Exciter damping |
| Protrusion (Plectrum) | 0% to 100% | Pick protrusion depth |

**String Section**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Decay | 0 ms to 30 s | String decay time |
| Ratio | 0.01 to 10 | Inharmonicity ratio |
| Damping | 0% to 100% | Damping (brightness) |
| Vibrato | On/Off + Rate + Amount | String vibrato |
| Unison | Off, 2 | Unison voices |
| Unison Detune | 0 to 50 cents | Unison detuning |
| Termination | 0% to 100% | Fret/finger position |

**Body Section**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | Acoustic guitar, Violin, Cello, Piano, Generic, and more | Resonating body type |
| Size | 0.1x to 10x | Body size multiplier |
| Decay | 0% to 100% | Body resonance decay |
| Brightness | 0% to 100% | Body tone |
| Volume | 0% to 100% | Body level |

**Filter**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Type | LP/HP/BP 2-pole, 4-pole | Filter mode |
| Frequency | 20 Hz to 20 kHz | Cutoff |
| Resonance | 0% to 100% | Q |

---

### 1.10 Collision (Physical Modeling — Mallets/Percussion)

Mallet + Noise exciters into two linked resonators.

**Mallet Exciter**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Volume | -inf to 0 dB | Mallet level |
| Noise Amount | 0% to 100% | Impact noise |
| Stiffness | 0% to 100% | Mallet hardness (brighter/duller) |
| Color | -100% to +100% | Spectral tilt of noise |

**Noise Exciter**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Volume | -inf to 0 dB | Noise level |
| Filter Type | LP, HP, BP | Noise shaping filter |
| Filter Freq | 20 Hz to 20 kHz | Noise filter cutoff |
| Envelope | Attack, Decay | Noise envelope |

**Resonators (1 & 2)**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Type | Beam, Marimba, String, Membrane, Plate, Pipe, Tube | Resonator model |
| Tune | -48 to +48 st | Pitch tuning |
| Fine | -50 to +50 cents | Fine tuning |
| Decay | 0 ms to 30 s | Decay time |
| Ratio | 0.01 to 10 | Controls inharmonicity / geometry |
| Brightness | 0% to 100% | High-frequency content |
| Inharmonics | -100% to +100% | Partial detuning |
| Radius | 0.01 to 1.0 | Object radius (Membrane, Plate) |
| Opening | 0% to 100% | Tube/Pipe opening size |
| Listening Position (L/R) | 0% to 100% | Pickup placement |
| Hit Position | 0% to 100% | Strike location |
| Spread | 0% to 100% | Stereo spread between resonators |

**LFO**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Shape | Sine, Square, Triangle, Saw, Random | Waveform |
| Rate | Free or synced | Speed |
| Amount | Modulates resonator frequency | Depth |

---

### 1.11 Electric (Electric Piano — Physical Modeling)

Models tine/reed fork + pickup system. No samples.

**Mallet Section**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Stiffness | 0% to 100% | Mallet hardness (mellow to bright) |
| Force | 0% to 100% | Impact force |
| Noise | 0% to 100% | Mechanical impact noise |
| Key Scale | 0% to 100% | Stiffness varies across keyboard |

**Fork Section**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Tine Color | 0% to 100% | Tine brightness |
| Tine Decay | 0 ms to 30 s | Tine ring time |
| Tine Level | -inf to 0 dB | Tine volume |
| Tone Color | 0% to 100% | Tone bar brightness |
| Tone Decay | 0 ms to 30 s | Tone bar ring time |
| Tone Level | -inf to 0 dB | Tone bar volume |
| Release | 0 ms to 10 s | Damper release time |

**Pickup Section**

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Model | Electrostatic (Wurlitzer), Electromagnetic (Rhodes) | Pickup type |
| Symmetry | 0% to 100% | Pickup position relative to tine |
| Distance | 0% to 100% | Pickup distance from tine |
| Input Level | 0% to 200% | Pre-amp input gain |
| Output Level | 0% to 200% | Output level |

**Global**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Voices | 1-20 | Polyphony |
| Semi | -12 to +12 | Global transpose |
| Detune | -50 to +50 cents | Fine tuning |
| Stretch | -100% to +100% | Octave stretching |

---

## 2. Stock Audio Effects — Detailed Parameters

### 2.1 Compressor

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Threshold | -inf to 0 dB | Level where compression begins |
| Ratio | 1:1 to inf:1 | Compression ratio |
| Attack | 0.01 ms to 1000 ms | Time to reach full compression |
| Release | 1 ms to 3000 ms (or Auto) | Time to release compression |
| Knee | 0 dB to 12 dB | Soft knee width around threshold |
| Makeup Gain | -inf to +24 dB | Output gain compensation |
| Dry/Wet | 0% to 100% | Parallel compression mix |
| Model | Peak, RMS, Expand | Detection mode |
| Lookahead | 0 ms, 1 ms, 10 ms | Look-ahead time |
| Sidechain | On/Off | External sidechain input |
| SC EQ | On/Off | Sidechain EQ (HP/BP/LP/Peak) |
| SC Freq | 20 Hz to 20 kHz | Sidechain filter frequency |
| SC Q | 0.1 to 10 | Sidechain filter Q |
| SC Gain | -15 dB to +15 dB | Sidechain input gain |

**Typical Starting Points:**
- Gentle bus compression: Threshold -20 dB, Ratio 2:1, Attack 30 ms, Release 100 ms, Knee 6 dB
- Vocal taming: Threshold -18 dB, Ratio 3:1, Attack 5 ms, Release 50 ms
- Drum punch: Threshold -15 dB, Ratio 4:1, Attack 10-30 ms, Release 50 ms
- Limiting: Threshold -6 dB, Ratio inf:1, Attack 0.01 ms, Release 50 ms

---

### 2.2 Glue Compressor

Modeled on classic SSL G-Series bus compressor.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Threshold | -30 dB to 0 dB | Compression threshold |
| Ratio | 2:1, 4:1, 10:1 | Fixed ratio options |
| Attack | 0.01 ms, 0.1 ms, 0.3 ms, 1 ms, 3 ms, 10 ms, 30 ms | Fixed attack options |
| Release | 0.1 s, 0.2 s, 0.4 s, 0.6 s, 0.8 s, 1.2 s, Auto | Fixed release options |
| Makeup | 0 dB to +15 dB | Output gain |
| Range | -inf to 0 dB | Limits maximum gain reduction |
| Dry/Wet | 0% to 100% | Parallel compression blend |
| Soft Clip | On/Off | Analog-style clipping at output |
| Sidechain | On/Off + EQ | External/internal sidechain |
| Oversampling | On/Off | 2x oversampling for cleaner sound |

**Typical Bus Glue:** Threshold -3 to -6 dB, Ratio 2:1, Attack 10-30 ms, Release Auto, just 1-3 dB GR

---

### 2.3 EQ Eight

8-band parametric EQ with spectrum analyzer.

| Parameter (per band) | Range / Options | Description |
|----------------------|----------------|-------------|
| Filter Type | LP48, LP24, LP12, HP48, HP24, HP12, Bell, Notch, Low Shelf, High Shelf | Filter shape |
| Frequency | 20 Hz to 20 kHz | Center/cutoff frequency |
| Gain | -15 dB to +15 dB | Boost/cut amount (Bell, Shelf modes) |
| Q | 0.1 to 18 | Bandwidth / resonance |
| Band On/Off | Toggle per band | Enable/disable each band |
| Mode | Stereo, L/R, M/S | Processing mode |
| Oversampling | Off, 2x, 4x | Anti-aliasing quality |
| Scale | 0% to 200% | Scales all band gains proportionally |
| Output | -12 dB to +12 dB | Master output level |
| Analyzer | On/Off | Spectrum display |
| Analyzer Range | 12 dB to 90 dB | Vertical display range |

---

### 2.4 Reverb

Algorithmic reverb with input filtering, early reflections, diffusion network.

| Section | Parameter | Range / Options | Description |
|---------|-----------|----------------|-------------|
| **Input** | HP Freq | 20 Hz to 20 kHz | Input high-pass filter |
| | LP Freq | 20 Hz to 20 kHz | Input low-pass filter |
| **Early Reflections** | Spin | 0% to 100% | Modulation of early reflections |
| | Shape | 0.5 to 1.0 | ER envelope shape |
| **Diffusion** | Decay Time | 200 ms to inf | Reverb tail duration |
| | Size | 0% to 500% | Virtual room size |
| | Diffusion | 0% to 100% | Density of reflections (low = distinct echoes) |
| | High Shelf | -inf to 0 dB | High-frequency damping in tail |
| | Low Shelf | -inf to 0 dB | Low-frequency damping in tail |
| | Density | Sparse, Dense | Reflection density character |
| | Scale | 5% to 500% | ER time scaling |
| **Chorus** | Rate | 0.01 to 10 Hz | Reverb chorus modulation rate |
| | Amount | 0% to 100% | Chorus depth |
| **Global** | Pre-Delay | 0 ms to 500 ms | Gap before first reflection |
| | ER Level | -inf to +6 dB | Early reflections volume |
| | Diffuse Level | -inf to +6 dB | Diffuse tail volume |
| | Stereo | 0% to 120% | Stereo image width |
| | Freeze | On/Off | Infinite reverb hold |
| | Quality | Eco, Mid, High | CPU/quality tradeoff |
| | Dry/Wet | 0% to 100% | Mix balance |

---

### 2.5 Delay

Simple stereo delay.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Delay Time L | 1 ms to 10 s (or synced) | Left channel delay time |
| Delay Time R | 1 ms to 10 s (or synced) | Right channel delay time |
| Link | On/Off | Link L/R delay times |
| Sync | On/Off | Sync to tempo |
| Feedback | 0% to 100% | Delay feedback amount |
| Filter | On/Off | Enable feedback filter |
| HP Freq | 20 Hz to 15 kHz | Feedback high-pass |
| LP Freq | 50 Hz to 20 kHz | Feedback low-pass |
| Ping Pong | On/Off | Bounce between L/R |
| Repitch | On/Off | Pitch-shift when changing delay time |
| Dry/Wet | 0% to 100% | Mix balance |

---

### 2.6 Echo

Modulation delay with dual delay lines, filter, reverb, and modulation.

| Section | Parameter | Range / Options | Description |
|---------|-----------|----------------|-------------|
| **Delay** | Time L / R | 1 ms to 10 s (or synced) | Delay times |
| | Sync Mode | Notes, Triplet, Dotted, 16th | Sync division modifier |
| | Link | On/Off | Link channels |
| | Feedback | 0% to 100% | Delay feedback |
| | Stereo | 0% to 200% | Stereo offset between taps |
| | Repitch | On/Off | Tape-style pitch shift |
| **Filter** | HP | 20 Hz to 15 kHz | Feedback high-pass |
| | LP | 50 Hz to 20 kHz | Feedback low-pass |
| **Modulation** | Mod Rate | 0.01 Hz to 30 Hz (or synced) | LFO rate |
| | Mod Amount | 0% to 100% | LFO depth |
| | Mod Filter | 0% to 100% | LFO amount on filter |
| | Mod Time | 0% to 100% | LFO amount on delay time |
| | Env Mix | -100% to +100% | Envelope follower blend |
| **Character** | Noise | 0% to 100% | Analog noise amount |
| | Wobble | 0% to 100% | Tape wow/flutter |
| | Gate | On/Off | Triggered gate |
| | Ducking | 0% to 100% | Input-ducked wet signal |
| | Reverb | 0% to 100% | Post-delay reverb |
| | Dry/Wet | 0% to 100% | Mix balance |

---

### 2.7 Saturator

Waveshaping saturation with multiple curve modes.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Drive | -inf to +36 dB | Input drive amount |
| Curve Type | Analog Clip, Soft Sine, Medium Curve, Hard Curve, Sinoid Fold, Digital Clip | Shaping algorithm |
| Output | -inf to 0 dB | Output level |
| Dry/Wet | 0% to 100% | Mix balance |
| Soft Clip | On/Off | Additional output clipping |
| Color | On/Off | Enable tone shaping |
| Base | 0 Hz to 20 kHz | Tone base frequency |
| Width | 0% to 100% | Tone bandwidth |
| Depth | 0% to 100% | Tone depth |

**Waveshaper Mode (replaces Curve Type selector)**

| Parameter | Range | Description |
|-----------|-------|-------------|
| Drive | 0% to 100% | Waveshaper drive |
| Curve | -100% to +100% | Adds 3rd order harmonics |
| Depth | -100% to +100% | Superimposed sine amplitude |
| Lin | -100% to +100% | Linear portion of shaping curve |
| Damp | -100% to +100% | Noise gate effect at center |
| Period | 1 to 20 | Density of sine ripples |

**Curve Character Summary:**
- **Analog Clip**: Warm, soft saturation, most "analog" feel
- **Soft Sine**: Subtle harmonic enrichment
- **Medium Curve**: Moderate saturation
- **Hard Curve**: Aggressive saturation
- **Sinoid Fold**: Wavefold-style, unique overtone generation
- **Digital Clip**: Harsh, hard clipping

---

### 2.8 Auto Filter

Resonant filter with LFO, envelope follower, sidechain. Overhauled in Live 12.2.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Filter Type | Low Pass, High Pass, Band Pass, Notch, Morph, Comb, Vowel, DJ (Live 12.2+), Resampling (12.2+) | Filter mode |
| Circuit Type | SVF (clean), DFM (warm drive), MS2 (Cytomic Sallen-Key), PRD (ladder) | Analog model |
| Frequency | 20 Hz to 20 kHz | Center/cutoff frequency |
| Resonance | 0% to 100% | Self-oscillation at max |
| Drive | 0% to 100% | Pre-filter saturation |
| Env Amount | -100% to +100% | Envelope follower depth |
| Env Attack | 0.1 ms to 100 ms | Envelope follower attack |
| Env Release | 1 ms to 3000 ms | Envelope follower release |
| LFO Amount | -100% to +100% | LFO modulation depth |
| LFO Rate | 0.01 Hz to 30 Hz (or synced) | LFO speed |
| LFO Shape | Sine, Square, Triangle, Saw Up, Saw Down, Random S&H | LFO waveform |
| LFO Phase | 0 to 360 degrees | LFO stereo phase offset |
| LFO Offset | -100% to +100% | LFO DC offset |
| Quantize Beat | Off, 1/1 to 1/32 | Quantize LFO to beat grid |
| Sidechain | On/Off | External envelope follower input |
| Dry/Wet | 0% to 100% | Mix balance |

---

### 2.9 Corpus

Physical modeling resonant body effect.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Resonator Type | Beam, Marimba, String, Membrane, Plate, Pipe, Tube | Physical model |
| Tune | -48 to +48 st | Resonator pitch |
| Fine | -50 to +50 cents | Fine tuning |
| Spread | -100% to +100% | L/R detuning |
| Decay | 0 ms to 30 s | Ring-out time |
| Ratio | 0.01 to 10 | Geometry / inharmonicity |
| Brightness | 0% to 100% | High-frequency content |
| Inharm | -100% to +100% | Partial detuning |
| Radius | 0% to 100% | Object size (Membrane/Plate) |
| Opening | 0% to 100% | Tube opening |
| Hit Position | 0% to 100% | Where the "hit" occurs |
| Listening L/R | 0% to 100% | Pickup position |
| Bleed | 0% to 100% | Dry signal through resonator |
| Gain | -inf to +12 dB | Output gain |
| Dry/Wet | 0% to 100% | Mix balance |
| LFO | Rate, Amount, Shape | Modulates resonator frequency |
| Filter | On/Off, Freq, Bandwidth | Band-pass filter on output |
| MIDI Freq | On/Off | MIDI note controls resonator pitch |

---

### 2.10 Erosion

Digital degradation / aliasing effect.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Mode | Sine, Noise, Wide Noise | Modulation source |
| Frequency | 20 Hz to 20 kHz | Center frequency of degradation |
| Amount | 0% to 100% | Effect intensity |
| Width | 0% to 100% | Noise bandwidth (Noise modes only) |

---

### 2.11 Frequency Shifter

Shifts all frequencies by a fixed Hz amount (not pitch-shift).

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Mode | Shift, Ring | Processing mode |
| Coarse | -2000 to +2000 Hz | Frequency shift amount |
| Fine | -10 to +10 Hz | Fine shift |
| Drive | 0% to 100% | Input saturation |
| LFO Rate | 0.01 Hz to 30 Hz (or synced) | Modulation LFO speed |
| LFO Amount | 0% to 100% | LFO modulation depth |
| LFO Shape | Sine, Square, Triangle, Saw Up, Saw Down, Random | LFO waveform |
| Spin | 0% to 100% | Stereo modulation |
| Dry/Wet | 0% to 100% | Mix balance |

---

### 2.12 Grain Delay

Granular delay effect.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Delay Time | 1 ms to 1000 ms (or synced) | Base delay time |
| Frequency | 0.1 Hz to 150 Hz | Grain generation rate |
| Pitch | -24 to +24 st | Grain pitch transposition |
| Random Pitch | 0 to 100% | Random pitch variation per grain |
| Spray | 0 ms to 500 ms | Random delay time variation |
| Feedback | 0% to 100% | Delay feedback |
| Dry/Wet | 0% to 100% | Mix balance |

---

### 2.13 Hybrid Reverb

Convolution + algorithmic reverb in one device.

| Section | Key Parameters | Description |
|---------|---------------|-------------|
| **Convolution** | IR (impulse response), Size, Pre-Delay, Decay | Real space emulation |
| **Algorithmic** | Decay, Size, Damping, Diffusion, Mod, Shape | Synthetic reverb tail |
| **Routing** | Serial, Parallel, Algorithm Only, IR Only | How the two engines combine |
| **EQ** | Low/High cut with slopes from 6 to 96 dB/oct | Post-reverb filtering |
| **Global** | Blend (IR vs Algo), Dry/Wet, Vintage, Bass X | Overall control |

---

### 2.14 Roar (Live 12 — Multi-Stage Saturation)

3-stage saturation engine with multiple routing configurations.

| Parameter | Range / Options | Description |
|-----------|----------------|-------------|
| Routing | Series, Parallel, Mid-Side, Multiband | Stage configuration |
| Stage Type (per stage) | Various saturation algorithms | Distortion character |
| Drive (per stage) | 0% to 100% | Saturation intensity |
| Tone (per stage) | 0% to 100% | Brightness post-saturation |
| Feedback | On/Off | Feedback generator |
| FB Freq | 20 Hz to 20 kHz | Feedback frequency |
| FB Amount | 0% to 100% | Feedback level |
| MIDI > FB Note | On/Off | MIDI controls feedback pitch |
| Modulation Matrix | Sources → Targets | Internal modulation routing |
| Env Hold | On/Off | Envelope hold behavior |
| Dry/Wet | 0% to 100% | Mix balance |

---

### 2.15 Other Notable Effects (Summary)

| Effect | Key Parameters | Use Case |
|--------|---------------|----------|
| **Drum Buss** | Drive, Crunch, Boom (sub), Transients, Dry/Wet | One-stop drum processing |
| **Dynamic Tube** | Drive, Bias, Envelope, Tone, Tube Type (A/B/C) | Tube-style warmth |
| **Chorus-Ensemble** | Rate, Amount, Feedback, Mode (Classic/Ensemble/Vibrato), Warmth | Chorus/ensemble |
| **Phaser-Flanger** | Rate, Amount, Feedback, Center, Mode (Phaser/Flanger), Earth/Space | Phase/flange |
| **Beat Repeat** | Interval, Offset, Gate, Grid, Variation, Chance, Filter, Decay | Glitch/stutter |
| **Multiband Dynamics** | 3 bands (Low/Mid/High), each with Above/Below threshold, ratio, attack, release | Multiband compression/expansion |
| **Limiter** | Gain, Ceiling, Release, Lookahead, Stereo Link | Brick-wall limiting |
| **Gate** | Threshold, Return, Attack, Hold, Release, Floor, Sidechain | Noise gate |
| **Overdrive** | Drive, Tone, Dynamics, Dry/Wet | Analog overdrive |
| **Pedal** | Gain, Output, Bass, Mid, Treble, Type (OD/Dist/Fuzz) | Guitar pedal modeling |
| **Amp** | Gain, Bass, Middle, Treble, Presence, Volume, Model (Clean/Boost/Blues/Rock/Lead/Heavy) | Amp modeling |
| **Cabinet** | Model, Microphone, Mic Position, Dry/Wet | Speaker cabinet simulation |
| **Redux** | Bit Depth (1-16), Sample Rate (off to extreme), Quantization | Lo-fi / bit crush |
| **Spectral Resonator** | Frequency, Decay, Stretch, Shift, Unison, MIDI input, FFT | Spectral processing |
| **Spectral Time** | Freeze, Delay, Feedback, Fade, Tilt, Spray, FFT | Spectral freeze/delay |
| **Filter Delay** | 3 taps with independent L/R/pan, filter type/freq per tap, feedback, dry/wet | Filtered delay taps |
| **Auto Pan/Tremolo** | Rate, Amount, Shape, Phase, Offset, Mode (Pan/Tremolo) | Panning/tremolo LFO |
| **Re-Enveloper** | Attack, Decay, Sustain, Release, Output, Env Hold | Dynamic envelope reshaping |

---

## 3. Sound Design Recipes

### 3.1 Sub Bass

**Instrument: Analog**
```
Osc 1: Sine, Octave -1
Osc 2: Off
Filter 1: LP24, Freq 200 Hz, Res 0%, Drive 0%
Amp Env: Attack 2 ms, Decay 0 ms, Sustain 100%, Release 50 ms
No LFO modulation
Glide: On, Time 30 ms (for smooth note transitions)
Mono: On
```

**Instrument: Operator**
```
Algorithm 8 (all parallel) or Algorithm 1 (series)
Osc A: Sine, Level 100%, Coarse 1
Osc B: Off (or Sine at Coarse 0.5 for sub-octave weight)
Osc C, D: Off
Filter: LP24, Freq 150-300 Hz, Res 0%
No modulation — clean and pure
```

---

### 3.2 Reese Bass

**Instrument: Analog**
```
Osc 1: Sawtooth, Octave -1
Osc 2: Sawtooth, Octave -1, Detune +50 cents
Filter 1: LP24, Freq 800-2000 Hz (automate this), Res 20-40%
Filter Env: Attack 0, Decay 500 ms, Sustain 40%, Release 200 ms, Amount +60%
Amp Env: Attack 5 ms, Decay 0 ms, Sustain 100%, Release 150 ms
LFO 1 → Filter 1 Freq: Rate 0.5 Hz, Amount 30% (slow movement)
Mono: On, Glide: On, Time 50 ms
```

**Instrument: Meld**
```
Engine A: Dual Basic Shapes, Octave -3, Shape 100% (square)
Engine B: Dual Basic Shapes, Octave -3, Shape 100% (square)
Engine A Detune: +2 cents
Engine B Detune: +4 cents
Filter: LP, Freq modulated by LFO
```

**Effect chain:** Saturator (Analog Clip, Drive +6 dB) → EQ Eight (low shelf boost at 60 Hz) → Compressor

---

### 3.3 Pad Sounds

**Instrument: Wavetable**
```
Osc 1: Harmonics or Complex table, Position modulated by LFO (slow, 0.1 Hz)
Osc 2: Basic Shapes, slight detune (+7 cents)
Sub: Off or low Sine
Filter: LP24, Freq 3-5 kHz, Res 10%
Amp Env: Attack 500 ms - 2 s, Decay 2 s, Sustain 80%, Release 2-5 s
Unison: Shimmer or Classic, Amount 50%
Voices: 6-8
```

**Instrument: Drift**
```
Osc 1: Saw, Osc 2: Saw, Detune +15 cents
Osc Mix: 50%
Drift: 30-50% (adds organic movement)
Filter: Type I, Freq 2-4 kHz, Res 15%
Amp Env: Attack 1 s, Decay 3 s, Sustain 70%, Release 3 s
LFO → Filter Freq: Sine, Rate 0.2 Hz, Amount 20%
```

**Effect chain:** Chorus-Ensemble (Rate 0.5 Hz, Amount 40%) → Reverb (Decay 4-8 s, Dry/Wet 40-60%) → EQ Eight (HP at 100 Hz, gentle LP at 10 kHz)

---

### 3.4 Pluck Sounds

**Instrument: Analog**
```
Osc 1: Sawtooth
Filter 1: LP24, Freq 1 kHz, Res 30%
Filter Env: Attack 0 ms, Decay 100-300 ms, Sustain 0%, Release 100 ms, Amount +80%
Amp Env: Attack 0 ms, Decay 200-500 ms, Sustain 0%, Release 200 ms
```

**Instrument: Operator**
```
Algorithm 1 (D→C→B→A)
Osc A: Sine, Level 100%, Coarse 1
Osc B: Sine, Level 70%, Coarse 2 (or 3 for brightness)
Osc B Env: Attack 0, Decay 150 ms, Sustain -inf (fast decay = pluck character)
Filter: LP24, Freq 2 kHz, Key Track 50%
Amp Env: Attack 0, Decay 300 ms, Sustain 0%, Release 200 ms
```

**Instrument: Collision**
```
Mallet: Stiffness 60%, Noise 20%
Resonator: String or Marimba, Decay 500 ms, Brightness 60%
```

**Effect chain:** Auto Filter (slight envelope follower on LP) → Delay (1/8 note, Feedback 20%, Dry/Wet 15%) → Reverb (short, Decay 1 s, Dry/Wet 20%)

---

### 3.5 Lead Sounds

**Instrument: Analog**
```
Osc 1: Square, PW 40%
Osc 2: Sawtooth, Detune +10 cents
Filter 1: LP24, Freq 3-5 kHz, Res 25%
Filter Env: Attack 0, Decay 200 ms, Sustain 50%, Release 200 ms, Amount +50%
Amp Env: Attack 5-20 ms, Decay 200 ms, Sustain 70%, Release 200 ms
Mono: On, Glide: On, Time 40-80 ms
Unison: 2, Detune 20%
```

**Instrument: Drift**
```
Osc 1: Saw or Pulse, Shape 30%
Osc 2: Saw, Detune +8 cents
Drift: 10-20%
Filter: Type II (24 dB), Freq 4 kHz, Res 20%
Mono: On, Glide: On, Time 50 ms
LFO → Pitch: Sine, Rate 5 Hz, Amount 5% (subtle vibrato)
```

**Effect chain:** Saturator (Soft Sine, Drive +3 dB) → EQ Eight (presence boost at 2-5 kHz) → Delay (1/4 dotted, Feedback 25%, Dry/Wet 20%) → Reverb (Decay 1.5 s, Dry/Wet 15%)

---

### 3.6 Texture / Ambient

**Instrument: Wavetable**
```
Osc 1: Noise or Complex table, Position modulated by LFO (Random, slow)
Osc 2: Harmonics table, Position modulated by Env 2 or separate LFO
Osc Effect: FM or Noise AM, Amount 40%
Filter: Morph type, Freq modulated by LFO, Res 30%
Amp Env: Attack 3-5 s, Decay 10 s, Sustain 60%, Release 5-10 s
Unison: Shimmer, Amount 70%
```

**Instrument: Meld**
```
Engine A: Granular type oscillator, Macro 1 modulated by LFO
Engine B: Ambient/noise generation oscillator
Engine Mix: 40-60%
Modulation: LFO → Macros, Pressure → Filter Freq
```

**Effect chain:** Spectral Resonator (Decay 3 s, Stretch 200%) → Echo (long delay, Noise 40%, Wobble 30%) → Hybrid Reverb (long algorithmic tail, 6+ s) → EQ Eight (gentle roll-offs both ends)

---

### 3.7 808 Kick

**Instrument: Operator**
```
Algorithm 8 (parallel)
Osc A: Sine, Level 100%, Coarse 1
Osc A Env: Attack 0, Decay 800-1200 ms, Sustain -inf
Pitch Env: Initial +24 st, Peak +24, Time 30 ms (fast pitch drop = click)
Filter: LP24, Freq 200 Hz, Res 0%
Mono: On
```

**Effect chain:** Saturator (Analog Clip, Drive +3-6 dB for warmth) → EQ Eight (boost at 50-60 Hz, cut at 300 Hz) → Compressor (fast attack, medium release)

---

### 3.8 FM Bell / Electric Piano

**Instrument: Operator**
```
Algorithm 1 (D→C→B→A) or Algorithm 5 (two FM pairs)
Osc A: Sine, Level 100%, Coarse 1
Osc B: Sine, Level 40-70%, Coarse 1 (EP) or 3.5-7 (bell/metallic)
Osc B Env: Attack 0, Decay 1 s, Sustain 20%
Amp Env: Attack 0, Decay 1.5-3 s, Sustain 30%, Release 500 ms
Non-integer ratios (e.g., 1.41, 3.14) = inharmonic/bell-like
Integer ratios (1, 2, 3, 4) = harmonic/EP-like
```

**Instrument: Electric**
```
Pickup: Electromagnetic (Rhodes) or Electrostatic (Wurlitzer)
Mallet Stiffness: 50% (mellow) to 80% (bright)
Tine Color: 40-60%
Symmetry: 50% (centered) — adjust for bark/growl
```

**Effect chain:** Chorus-Ensemble (subtle, Amount 15%) → Phaser-Flanger (slow rate) → Reverb (medium, Decay 2 s, Dry/Wet 25%)

---

## 4. Device Chain Patterns

### 4.1 Standard Insert Chain

```
Signal → [Subtractive EQ] → [Compressor] → [Saturation] → [Additive EQ] → [Time FX] → [Output]
```

**Detailed:**
1. **EQ Eight** (subtractive) — Remove problem frequencies, HP filter rumble
2. **Compressor** — Tame dynamics, add consistency
3. **Saturator** — Harmonic enrichment, warmth
4. **EQ Eight** (additive) — Boost desired character frequencies
5. **Delay / Reverb** — Spatial effects (or use return tracks)

### 4.2 Vocal Chain

```
EQ Eight (HP 80-100 Hz, notch problem freqs)
→ Compressor (Ratio 3:1, Attack 5 ms, Release 50 ms, ~6 dB GR)
→ De-esser (Compressor with SC EQ BP at 5-8 kHz)
→ Saturator (Soft Sine, Drive +1-2 dB for warmth)
→ EQ Eight (presence boost 2-5 kHz, air boost 10-12 kHz)
→ [Send to] Reverb Return (Decay 1.5-2.5 s, Pre-delay 30 ms)
→ [Send to] Delay Return (1/4 or 1/8 dotted)
```

### 4.3 Drum Bus Chain

```
EQ Eight (HP at 30 Hz to remove sub rumble)
→ Drum Buss (Crunch for parallel saturation, Boom for sub enhancement)
→ Glue Compressor (Ratio 2:1, Attack 10 ms, Release Auto, 2-4 dB GR)
→ EQ Eight (shelf boosts for top-end sparkle)
→ Limiter (Ceiling -0.3 dB, safety)
```

### 4.4 Parallel Compression (Audio Effect Rack)

```
Audio Effect Rack:
  Chain 1 "Dry": [Utility — no processing]
  Chain 2 "Crushed": [Compressor (Ratio 10:1, Attack 1 ms, Release 50 ms, heavy GR)]
  → Adjust chain volumes to blend
```

### 4.5 Parallel Saturation Rack

```
Audio Effect Rack:
  Chain 1 "Clean": [Utility]
  Chain 2 "Warm": [Saturator (Analog Clip, Drive +6 dB)]
  Chain 3 "Gritty": [Dynamic Tube (Drive 60%, Bias 30%)]
  → Blend chain volumes to taste
```

### 4.6 Mid-Side Processing Rack

```
Audio Effect Rack:
  Chain 1 "Mid": [Utility (Width 0%)] → [EQ Eight] → [Compressor]
  Chain 2 "Side": [Utility (extract sides via M/S trick)] → [EQ Eight (boost air)] → [Saturator]

  Alternative: Use EQ Eight in M/S mode for simpler mid-side EQ
```

### 4.7 Multi-Band Saturation

```
Audio Effect Rack (using Chain Select zones by frequency split):
  Chain 1 "Low" (0-200 Hz): [Auto Filter LP 200 Hz] → [Saturator (Analog Clip, light)]
  Chain 2 "Mid" (200-4000 Hz): [Auto Filter BP] → [Saturator (Medium Curve)]
  Chain 3 "High" (4000+ Hz): [Auto Filter HP 4000 Hz] → [Saturator (Soft Sine)]
```

### 4.8 Bass Processing Chain

```
EQ Eight (HP at 25-30 Hz)
→ Compressor (Ratio 4:1, Attack 10-30 ms, Release 100 ms)
→ Saturator (Analog Clip or Medium Curve, Drive +3-6 dB — adds harmonics audible on small speakers)
→ EQ Eight (scoop at 250-400 Hz, presence boost at 700-1200 Hz)
→ Limiter (safety, Ceiling -1 dB)
```

### 4.9 Ambient / Texture Chain

```
Spectral Resonator (or Corpus for physical character)
→ Chorus-Ensemble (wide, Amount 30-50%)
→ Echo (long delay, Noise 30%, Wobble 20%, Reverb 40%)
→ Hybrid Reverb (long tail, 4-10 s)
→ Auto Filter (slow LFO on LP, subtle movement)
→ EQ Eight (gentle roll-offs, remove harshness)
→ Utility (Width 120-150% for wide stereo)
```

### 4.10 Return Track Templates

```
Return A — Short Reverb: Reverb (Decay 1 s, Pre-delay 10 ms, HP 200 Hz, LP 8 kHz)
Return B — Long Reverb: Reverb (Decay 4-6 s, Pre-delay 40 ms, HP 300 Hz, LP 6 kHz)
Return C — Slapback Delay: Delay (80-120 ms, Feedback 10%, Filter on)
Return D — Rhythmic Delay: Echo (1/8 dotted, Feedback 30%, Filter HP 400 Hz LP 6 kHz)
Return E — Parallel Compression: Compressor (heavy ratio, fast attack, blended via send)
Return F — Saturation: Saturator (Analog Clip, moderate drive)
```

---

## 5. Key Frequency Ranges for EQ

| Range | Frequency | Character |
|-------|-----------|-----------|
| Sub bass | 20-60 Hz | Felt more than heard, rumble |
| Bass | 60-200 Hz | Fundamental bass energy |
| Low mids | 200-500 Hz | Warmth, can be muddy |
| Midrange | 500-2000 Hz | Body, presence, nasal quality |
| Upper mids | 2-5 kHz | Presence, clarity, harshness zone |
| Presence | 5-8 kHz | Definition, sibilance, brightness |
| Air | 8-20 kHz | Sparkle, air, sheen |

---

## Sources

- [Live Instrument Reference v12](https://www.ableton.com/en/manual/live-instrument-reference/)
- [Live Audio Effect Reference v12](https://www.ableton.com/en/manual/live-audio-effect-reference/)
- [Meld: A Look at Live 12's New Bi-Timbral Synth](https://www.ableton.com/en/blog/meld-a-look-at-live-12s-new-bi-timbral-synth/)
- [Drift: Exploring Live's New Synth](https://www.ableton.com/en/blog/drift-exploring-the-new-synth-in-live-113/)
- [Shaping Surprises: Sound Design with Meld](https://www.ableton.com/en/blog/shaping-surprises-sound-design-concepts-with-meld/)
- [Smooth Operator: FM Synth Sound Design](https://www.ableton.com/en/blog/smooth-operator-watch-sound-design-maestro-lives-fm-synth/)
- [Low End Theory: Classic Bass Sounds in Live](https://www.ableton.com/en/blog/low-end-theory-make-four-classic-bass-sounds-in-live/)
- [The New Wave: In-Depth Look at Wavetable](https://www.ableton.com/en/blog/new-wave-depth-look-wavetable/)
- [Spectral Sound: Live 11's Spectral Devices](https://www.ableton.com/en/blog/spectral-sound-a-look-at-live-11s-new-spectral-devices/)
- [Cytomic on Ableton Partnership](https://www.ableton.com/en/blog/cytomic-on-ableton-partnership/)
- [Instrument, Drum and Effect Racks v12](https://www.ableton.com/en/manual/instrument-drum-and-effect-racks/)
- [Learning Synths (Interactive)](https://learningsynths.ableton.com/)
- [What's New in Live 12](https://www.ableton.com/en/live/)
- [Live 12 Release Notes](https://www.ableton.com/en/release-notes/live-12/)
- [Live 12.2 — Auto Filter, New Devices](https://www.ableton.com/en/blog/live-12-2-is-out-now/)

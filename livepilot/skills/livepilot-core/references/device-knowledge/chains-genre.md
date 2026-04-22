# Genre-Specific Effect Chains & Artist Techniques

## Dub Techno (Basic Channel, Deepchord, Echospace)

### The Dub Chord (fundamental technique)
1. **Source:** Analog or Drift — short chord stab (attack 0ms, decay 80-150ms, sustain 20%)
2. **Filter:** Lowpass at 300-600Hz (dark, submerged)
3. **Echo:** Ping Pong, 3/16 time, Feedback 65-75%, Repitch mode, Wobble 15%
4. **Reverb:** (on return) Decay 5-8s, Chorus 0.02Hz, ER Spin 0.2Hz
5. **The key:** The delay tail IS the pad. The source stab is just the trigger. Open the delay filter slowly over 32 bars — the chord "wakes up."

### The Dusty Loop
1. **Drum source** → Vinyl Distortion (Tracing 20%, Crackle 8%)
2. → Auto Filter (Lowpass, 4kHz, Res 15%, LFO at 0.08Hz depth 10%)
3. → Reverb send (35-45%) with long decay
4. → Result: Drums sound like they're playing on a worn record in a concrete room

### The Sub Breath
1. **Analog:** Sine osc, -2 octave, mono, glide ON
2. **F1:** LP24, Freq 28%, F1 Freq < Env 30%, Fast attack, 200ms decay
3. → Drum Buss (Boom at 60%, Freq 52Hz)
4. → Saturator (Analog Clip, Drive 5dB)
5. → Result: Sub bass that "breathes" — each note has a momentary brightness then settles into deep sub

---

## Minimal Techno (Perlon, Kompakt, Raum·Musik)

### Micro-Groove Percussion
1. **Operator:** Algorithm 1, Osc A Sine 8bit, Osc B Sine Coarse 5 Fine 70
2. Short envelopes (30-80ms decay on all)
3. Pitch Env: +12st, 15ms decay
4. → Erosion (12%, 8kHz) — adds digital texture
5. → Auto Filter (Bandpass, 1.5kHz, Res 40%, LFO at 0.1Hz depth 8%)
6. **Sequence:** Off-grid 32nd notes with varying velocity (40-100)
7. **Pan:** Random per hit (±30%)

### The Organic Filter Sweep
1. **Any pad or texture** → Auto Filter (Lowpass, OSR circuit)
2. Freq: Automated with Perlin/brownian noise curve over 32-64 bars
3. Res: 35-50% (enough to hear the sweep, not enough to ring)
4. Env Amount: 15-25% (filter follows the input dynamics slightly)
5. **LFO:** 0.05-0.15 Hz, Amount 8-12% (micro-breathing on top of the macro sweep)
6. **Result:** A filter movement that feels like a human hand slowly turning a knob — not a computer drawing a line

---

## SOPHIE / PC Music / Hyperpop

### The Plastic Bass
1. **Wavetable:** Digital wavetable, Position 80%, Osc Effect = Sync at 60%
2. Filter: Lowpass, OSR circuit, Freq 50%, Res 65%
3. Pitch Env: +24st, Decay 40-60ms (the "zap")
4. → Saturator (Sinoid Fold, Drive 15-20dB, Color +30%)
5. → Erosion (Wide Noise, 25%, Freq 6kHz)
6. → Redux (Bit 8, Sample Rate 4x) at Dry/Wet 25%
7. **Result:** Bubbly, metallic, hyperreal bass that sounds like liquid plastic

### The Maximal OTT Wall
1. **Any synth chord** → Multiband Dynamics (OTT preset)
2. Stack 10-30 instances (yes, really)
3. Insert different effects between some instances:
   - Between #5 and #6: Phaser-Flanger (Phaser mode, Rate 0.3Hz)
   - Between #15 and #16: Chorus-Ensemble (Rate 0.5Hz)
   - Between #20 and #21: Frequency Shifter (Ring mode, 1.5Hz)
4. Record the output as audio
5. **Use the audio as source material** — chop, pitch, filter, process further
6. This creates sounds that literally cannot be designed any other way

### SOPHIE Distortion Chain
1. **Source:** Simple sine wave at bass frequencies
2. → Saturator (Sinoid Fold, Drive 18dB)
3. → Roar (Multiband: Low=Tube 40%, Mid=Feedback 50%, High=BitReduce 30%)
4. → Compressor (Fast attack, fast release — glues the chaos)
5. → Auto Filter (Lowpass 3kHz, Res 50%, LFO 2Hz at 20%)
6. **Result:** The simple sine becomes a living, morphing, metallic entity

---

## Arca / Experimental / Deconstructed

### Warped Texture (Simpler stretch technique)
1. Load ANY sample into Simpler → Switch to **Texture** mode
2. Set Grain size to minimum, Flux to 50-80%
3. Transpose ±12-24 semitones (extreme pitch shift)
4. → Saturator (Soft Sine, 10-15dB)
5. → Spectral Resonator (MIDI-controlled, Decay 300ms, Stretch 70%)
6. → Grain Delay (Pitch -7, Spray 60ms, Feedback 55%)
7. **Result:** Any source material becomes an alien, warped, pitched texture

### Glitch Percussion
1. **Operator:** Very short envelopes (5-30ms), multiple FM oscillators
2. → Beat Repeat (1/32 or 1/64 interval, Chance 40%, Variation 60%)
3. → Redux (Bit 6, Sample 4x, Dry/Wet 40%)
4. → Grain Delay (very short time, Pitch ±random, Spray 30ms)
5. Play rapid 64th note sequences with varying velocity
6. **Result:** Stuttering, bitcrushed, granular percussion clouds

---

## Trap / 808 / Brazilian Bass

### The Growling 808
1. **Operator:** Osc A = Sine, Coarse 1
2. AEG: Attack 0ms, Decay 1.9s, Sustain -10dB, Release 1.5s
3. Pitch Env: +24st peak, 50ms decay (the "hit")
4. Voices: 1 (Mono), Glide ON at 15%
5. → Pedal (Fuzz mode, Gain 35%, Sub ON)
6. → Saturator (Hard Curve, Drive 8dB)
7. → EQ Eight: HP at 30Hz (clean sub), gentle boost at 80-120Hz
8. **Result:** Fat sub with audible harmonics and the growl that cuts on small speakers

### The Multiband 808 (trap producer technique)
1. 808 source → Audio Effect Rack with two chains:
   - Chain A: Utility (Mono) → nothing else (clean sub, mono below 120Hz)
   - Chain B: EQ Eight (HP at 120Hz) → Chorus-Ensemble (subtle) → Delay (1ms L / 10ms R, 0% feedback, 100% wet — Haas effect for width)
2. Zone the chains: Chain A receives only frequencies below 120Hz, Chain B above
3. **Result:** Mono sub for club systems + wide harmonics for stereo interest

### Brazilian Bass (baile funk distortion)
1. **808 or sub bass** → Saturator (Digital Clip, Drive 12-18dB)
2. → Roar (Serial: Stage 1=Tube 40%, Stage 2=Gate 30%, Stage 3=Tube 20%)
3. → Compressor (aggressive — ratio 8:1, fast attack, auto release)
4. → Drum Buss (Drive 30%, Crunch Medium 50%, Boom 60% at 55Hz)
5. **Result:** Hyper-compressed, distorted, chest-rattling bass that's characteristic of Brazilian electronic music

---

## Ambient / Drone / Film Score

### The Infinite Shimmer
1. **Any source** → send to Return with:
2. Grain Delay (Pitch +12, Time 40ms, Feedback 75%, Spray 20ms)
3. → Reverb (Decay 8-12s, Diffusion 90%, Chorus ON at 0.03Hz)
4. → Auto Filter (Lowpass 4kHz, gentle slope — prevents shimmer from getting harsh)
5. Send at 30-40% — source stays dry, shimmer builds in the return
6. **Automate send** to increase over 32 bars — sound gradually dissolves into shimmer

### The Drone Machine
1. **Short percussive hit** → Spectral Blur (Full range, Halo 500ms+, Freeze ON)
2. → Resonators (tuned to root + fifth, Decay 2-5s)
3. → Reverb (Decay 10-15s, Freeze ON)
4. One hit becomes an infinite evolving drone
5. **Modulate** Spectral Blur Freeze on/off to capture new content periodically

### Film Score Tension
1. **Collision** (Mallet exciting Membrane, Decay 3-5s)
2. → Spectral Time (Spectral Delay, Tilt 40%, Spray 20%, Feedback 60%)
3. → Roar (Parallel: Stage 1=Feedback 20%, Stage 2=Dispersion 30%)
4. → Convolution Reverb with large hall IR
5. Play low, sparse notes — each one evolves into a complex, tense texture
6. **This is the Jason Graves technique** (Dead Space composer) for horror/tension scoring

---

## Warp Records / IDM (Aphex Twin, Autechre, Boards of Canada)

### The Aphex Glitch
1. **Any drum sample** → Load into Simpler (Classic mode)
2. Sequence with 64th and 128th notes (grid at minimum)
3. Vary velocity wildly (30-127)
4. → Beat Repeat (1/32, Grid 1/32, Chance 25%)
5. → Redux (Bit 8, Sample 8x, Dry/Wet 30%)
6. → Auto Pan (Rate synced to 1/16, Amount 80% — extreme panning)
7. **Result:** Rapid-fire, bitcrushed, spatially scattered percussion — the IDM signature

### Boards of Canada Nostalgia
1. **Any synth pad** → Vinyl Distortion (Tracing 30%, Crackle 15%, Pinch 10%)
2. → Auto Filter (Lowpass 3kHz, LFO 0.06Hz at 15% — very slow filter drift)
3. → Chorus-Ensemble (Rate 0.3Hz, Amount 30%, Dry/Wet 25%)
4. → Reverb (short decay 1.5s, high diffusion — tight room)
5. Detune the synth by 5-10 cents (deliberately out of tune)
6. **Result:** Warm, warbly, nostalgic pad that sounds like it was recorded on deteriorating tape in the 1970s

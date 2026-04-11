# Synthesizer Instruments — Deep Parameter Knowledge

## Wavetable

Wavetable is Live's most versatile synth. Two oscillators scan through wavetable positions, each with independent effects, filtered through two analog-modeled filters, modulated by three envelopes, two LFOs, and MIDI sources.

### Core Sound Design Parameters

**Osc Position (Osc 1 Pos / Osc 2 Pos):** The most important parameter. Sweeping through the wavetable creates timbral evolution — this IS the sound design. Automate this with a slow LFO (0.05-0.3 Hz) for evolving pads. For aggressive sounds, use fast LFO (2-8 Hz) with high depth.

**Osc Effect 1 / Effect 2:** These transform the wavetable in real-time:
- **FM (Frequency Modulation):** Adds harmonics and metallic overtones. Low values (5-15%) add subtle complexity. High values (50%+) create aggressive, digital textures. Modulate with an envelope for plucky FM bass.
- **Classic:** Phase distortion — fattens the sound without adding harsh harmonics. Good for warm pads (10-30%).
- **Modern:** Waveshaping distortion — more aggressive than Classic. Good for leads and bass (20-50%).
- **Sync:** Hard sync effect — creates screaming, tearing overtones when swept. Classic for aggressive leads.

**Filter 1 Freq / Filter 2 Freq:** Lowpass is the default. Key insight: use Filter 1 as lowpass and Filter 2 as highpass simultaneously (parallel routing) for bandpass-like resonant sounds. Or use split mode to send each oscillator through its own filter.

**Filter Circuit types:** Each emulates specific analog hardware:
- **Clean:** Transparent, precise. Good for surgical work.
- **OSR:** Emulates an MS-20 style filter — aggressive, screamy when resonance is high. Great for acid-style sounds.
- **MS2:** Another MS-20 variant, slightly different character.
- **SMP:** Sallen-Key topology — warm, rounded. Classic for pads.
- **PRD:** Ladder filter emulation — creamy, musical. Classic for bass.

**Unison modes:** Six types, each dramatically different:
- **Classic:** Standard detuned voices — instant width and fatness.
- **Shimmer:** Subtle pitch randomization — ethereal, glassy quality.
- **Noise:** Adds noise to each voice — gritty, textured.
- **Phase Sync:** Voices sync phases — hollow, metallic.
- **Position Spread:** Each voice reads a different wavetable position — creates a choir-like spread. VERY powerful for evolving textures.
- **Random:** Each note has slightly different characteristics — organic, alive.

### Creative Applications

**Evolving dub pad (Villalobos style):**
- Osc 1: "Basic Shapes" wavetable, Position 25%, Effect 1 = Classic at 15%
- Osc 2: "Vintage" wavetable, Position 60%, Effect 1 = FM at 8%
- Filter 1: Lowpass, Freq 35-45%, Res 15-25%, Circuit = SMP
- LFO 1 → Osc 1 Pos at 20%, Rate 0.15 Hz (breathing wavetable)
- LFO 2 → Filter 1 Freq at 10%, Rate 0.08 Hz (filter drift)
- Unison: Position Spread, Amount 30-40%
- Env 1 attack: 500ms-2s for slow pad entrance

**SOPHIE-style metallic bass:**
- Osc 1: "Digital" wavetable, Position 80%+, Effect 1 = Sync at 70%
- Filter 1: Lowpass, Freq 55%, Res 70%+, Circuit = OSR
- Short attack, medium decay, low sustain — plucky character
- Pitch envelope: +12 to +24 semitones, 30-60ms decay — the "zap"
- Post-processing: Saturator (Sinoid Fold at 60%) → Erosion (Wide Noise)

**Aphex Twin glitch texture:**
- Osc 1: "Noise" wavetable category, random position
- Effect 1 = FM at 40-60%, modulated by Env 2 with fast decay
- Filter: Bandpass, high resonance (70%+), freq modulated by fast LFO (4-12 Hz)
- Very short notes (32nd, 64th) with random velocity
- Unison: Noise mode, Amount 50%+

---

## Drift

Drift is designed for organic, analog-sounding synthesis. Its standout feature is the **Drift** parameter — built-in oscillator instability that adds analog warmth automatically. Two oscillators, one noise generator, one filter, one LFO, one cyclic envelope, two standard envelopes.

### Core Sound Design Parameters

**Drift (0-100%):** The signature parameter. At 0% it's perfectly digital. At 25-35% it sounds like a well-maintained analog synth. At 50-70% it sounds like a temperamental vintage unit. At 100% it's beautifully unstable — each note is slightly different. For minimal techno, 35-55% is the sweet spot.

**Osc 1 Wave:** Sine, Triangle, Saw, Square, Pulse, PWM (pulse width modulation), Noise. The Saw and Pulse waves are the bread and butter. PWM with slow shape modulation creates classic analog pad movement.

**Osc 1 Shape (0-100%):** Morphs the wave shape continuously. For Saw, it adds even harmonics (warmer). For Pulse, it changes pulse width. Automate this with the cyclic envelope for timbral evolution.

**Shape Mod Amt:** How much the LFO or cyclic envelope modulates the shape. At 5-15%, it's subtle organic movement. At 30-50%, it's obvious PWM-style modulation. At 70%+, it's aggressive waveshaping.

**LP Freq / LP Reso:** Single lowpass filter. Key insight: Drift's filter has two "types" (I and II) that sound quite different. Type I is smoother, Type II has more resonance character. For dub techno, Type I at medium-low freq (200-500 Hz) with moderate resonance (25-40%).

**LP Mod Amt 1 / LP Mod Amt 2:** How much Env 2 and the LFO modulate the filter. This is where the character lives. High Env 2 modulation = plucky, percussive. High LFO modulation = rhythmic filter movement.

**Cyclic Envelope:** A unique feature — a looping envelope that creates rhythmic or pseudo-random modulation. At low rates (0.1-1 Hz) it adds slow organic movement. At higher rates (2-20 Hz) it creates tremolo or rhythmic pulsing.

**Thickness / Strength / Spread:** Voice stacking parameters:
- **Thickness:** Adds detuned copies — instant fatness (20-40% for pads)
- **Strength:** How aggressively the thickness voices detune (10-25% for subtle, 40%+ for aggressive)
- **Spread:** Stereo width of the thickness voices (30-60% for natural width)

**Noise Gain:** Adding noise at very low levels (-30 to -40 dB) creates the impression of "air" and vintage character without muddying the mix.

### Creative Applications

**Deep minimal techno stab:**
- Osc 1: Saw, Shape 20%, Drift 40%
- Osc 2: Sine, -1 octave, slight detune (+2-3 cents) for sub weight
- Filter: Type I, Freq 400 Hz, Reso 30%
- Env 2: Fast attack, short decay (80-150ms), low sustain → LP Mod Amt 1 at 50%
- Result: Short, dark, characterful stab that changes slightly every time (thanks to Drift)

**Organic atmospheric pad:**
- Osc 1: PWM wave, Shape 40%, Shape Mod 20%
- Osc 2: Triangle, -1 octave for depth
- Drift: 55% (very analog, each note is unique)
- LFO: 0.12 Hz, Amount 35% → filter
- Cyclic Env: 0.3 Hz, Tilt 60% → shape mod
- Noise: -35 dB (barely there, adds air)
- Thickness 30%, Spread 50%

---

## Analog

Two oscillators, two filters, two amplifiers, two LFOs — a classic subtractive architecture that mirrors real analog polysynths. Each section (osc/filter/amp) has its own envelope.

### Core Sound Design Parameters

**Oscillator Shapes:** Sine, Saw, Square/Pulse, Noise per oscillator. Key insight: enabling **both** oscillators and setting them to slightly different tunings creates instant width and depth. Classic technique: Osc 1 = Saw, Osc 2 = Saw detuned +3-7 cents.

**Sub/Sync modes:**
- **Sub:** Osc 2 generates a sub-octave — instant bass weight
- **Sync:** Osc 1 hard-syncs to Osc 2 — classic screaming sync sound when you sweep Osc 1's coarse frequency

**Filter (F1/F2):** Each has 10 types including LP12, LP24, HP12, HP24, BP, Notch, and various drive types (Sym1, Sym2, Asym). The drive types add different saturation characters:
- **Off:** Clean, transparent
- **Sym1:** Gentle soft clipping — warm
- **Sym2:** Harder clipping — crunchy
- **Asym:** Asymmetric clipping — even harmonics, tube-like warmth

**F1 Freq < Env / F1 Freq < LFO:** Filter modulation sources. Key: the filter envelope amount goes from -1 to +1. Negative values make the filter close on attack (unusual but useful for reversed-sounding plucks).

**Glide:** Portamento between notes. Essential for 808-style bass slides. 10-20% for subtle, 30-50% for obvious glide. Enable **Legato** so glide only happens when notes overlap.

### Creative Applications

**808 bass from scratch:**
- Osc 1: Sine, Octave -1 (or -2 for very deep sub)
- Osc 2: Sine, Octave -2, Mode = Sub
- F1: LP24, Sym2 drive, Freq 28% (≈190 Hz)
- F1 Freq < Env: 30-40% (pluck character)
- FEG: Fast attack, short decay (150-250ms), low sustain
- AEG: Fast attack, long decay (1.5-3s), medium sustain
- Voices: 1 (mono), Glide ON at 15%
- Post: Saturator → Pedal (Fuzz at 30%) for harmonics and grit

**Acid bass (303 style):**
- Osc 1: Saw (or Square for hollow variant)
- F1: LP24, OSR circuit if available (or Sym2 for aggressive), Freq 30%, Reso 65%+
- F1 Freq < Env: 60-80% (the acid squelch)
- FEG: Zero attack, very short decay (30-80ms), zero sustain
- Accent via velocity → filter cutoff mapping
- Voices: 1 (mono), Legato ON, Glide 20%

---

## Operator

Four-oscillator FM synth. Each oscillator can be a carrier (audible) or modulator (shapes another oscillator). 11 algorithms determine the routing. Also includes a filter and LFO.

### Core Concept: FM Synthesis

FM synthesis creates complex timbres from simple waveforms by modulating one oscillator's frequency with another. The **ratio** between modulator and carrier determines the harmonic content:
- Integer ratios (1:1, 2:1, 3:1) = harmonic, musical sounds
- Non-integer ratios (1:1.41, 3:2.7) = inharmonic, metallic, bell-like sounds

The **modulator level** (Osc B/C/D Level when they modulate Osc A) determines intensity:
- 0-20%: Subtle timbral coloring
- 20-50%: Clear FM character, metallic harmonics
- 50-80%: Aggressive, complex, potentially harsh
- 80-100%: Extreme, noisy, glitchy

### Core Sound Design Parameters

**Algorithm:** Determines which oscillators modulate which. Key algorithms:
- **Alg 1:** D→C→B→A (serial) — maximum complexity, each modulator stacks
- **Alg 7:** All four independent carriers — additive synthesis, organ-like
- **Alg 3:** Two pairs (C→A, D→B) — two independent FM voices, good for layering
- **Alg 11:** Three modulators into one carrier — most extreme FM

**Osc Coarse/Fine tuning:** The ratio control. Setting Osc B Coarse to 2, 3, 4 creates harmonic FM. Setting it to 1.41 or 7.13 creates metallic/bell timbres. The Fine tune (0-1000) allows micro-detuning for beating and organic quality.

**Feedback (per oscillator):** Self-modulation — the oscillator modulates itself. Low values (5-15%) add warmth and body. High values (30-50%) add noise and grit. Very high values (70%+) create noise generators.

**Pitch Envelope:** Essential for electronic sounds. A pitch drop on the carrier creates kick drums (Amount 100%, Peak +24st, Decay 15-50ms). A pitch rise on a modulator creates zaps and laser sounds.

**Filter:** Operator's filter is the same engine as Wavetable's — Clean, OSR, MS2, SMP, PRD circuits. Using it after FM synthesis tames harsh harmonics while keeping character.

**Tone:** Global brightness control (0-100%). At 50% it's neutral. Below 50% it progressively filters high harmonics (warmer). Above 50% it boosts presence. Quick way to shape without touching the filter.

### Creative Applications

**Glitch percussion (Autechre style):**
- Algorithm 1 (serial): D→C→B→A
- Osc A: Sine 8bit wave, Coarse 1, Feedback 15%, Short decay (30ms)
- Osc B: Sine, Coarse 7, Fine 130 (inharmonic), Level 70%, Short decay (47ms)
- Osc C: Sine, Coarse 3, Fine 50, Level 50%, Very short decay (27ms)
- Osc D: Sine, Coarse 1, Level 0% (inactive but available for modulation)
- Pitch Env: +24st, Decay 15ms (click/zap transient)
- LFO: SwDown wave, High range, Rate 100 → filter for rhythmic gating
- Shaper: Hard at 60% drive for digital crunch

**FM bell/metallic hit:**
- Algorithm 3 (two pairs)
- Osc A: Sine, Coarse 1 (fundamental)
- Osc B: Sine, Coarse 3.51 (inharmonic), Level 45%, Decay 800ms
- Osc C: Sine, Coarse 1 (second fundamental, detuned +5 Fine)
- Osc D: Sine, Coarse 7.03 (inharmonic), Level 30%, Decay 400ms
- Long release on carriers (2-4s) for sustaining bell tone
- Post: Reverb with long decay for shimmering bell

**Sub bass with character:**
- Algorithm 7 (all carriers — additive)
- Osc A: Sine, Coarse 1, Level 85% (fundamental)
- Osc B: Sine, Coarse 2, Level 30% (first harmonic — adds audibility on small speakers)
- Osc C: Off
- Osc D: Sine, Coarse 1, Feedback 40% (noise-like, level 15% for sub rumble)
- Filter: LP24, Freq 65% (cuts harsh harmonics), Drive 6dB

---

## Meld

Two "macro oscillators" with multiple synthesis methods per oscillator. The oscillators are named "engines" and each provides a different synthesis approach. Extensive modulation matrix.

### Core Concept

Meld's power is in combining two different synthesis engines. Each oscillator slot can be:
- **Swarm:** Multiple detuned voices — supersaw-like
- **Noise:** Filtered noise with tonal character
- **Sub:** Clean sub oscillator
- **FM:** Frequency modulation
- **Virtual Analog:** Classic waveforms
- **Grain:** Granular-like texture

### Creative Applications

**Wall of sound chords (from Ableton's tutorial):**
- Engine 1: Swarm with high voice count, moderate detune
- Engine 2: FM with subtle modulation
- Matrix: LFO → Engine 1 detune amount for slow chorus movement
- Post-processing: Roar (parallel mode, gentle saturation) → Hybrid Reverb

**Sub bass with harmonics:**
- Engine 1: Sub (clean sine)
- Engine 2: Virtual Analog (saw, heavily filtered) for harmonic content
- Matrix: Velocity → Engine 2 filter cutoff (harder hits = brighter harmonics)
- Post: Saturator (Soft Sine curve) for gentle warmth

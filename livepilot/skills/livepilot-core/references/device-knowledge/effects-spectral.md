# Spectral & Experimental Effects — Deep Parameter Knowledge

These are Live's most unique devices — they operate in the frequency domain rather than the time domain. They don't just process sound — they transform it into something fundamentally different.

## Spectral Resonator

Turns any input into a pitched, resonant instrument. The input excites a bank of tuned resonators — like hitting a piano with a drum stick.

### Core Concept

Feed ANY sound (drums, noise, speech) into Spectral Resonator and it becomes pitched and tonal. The input's dynamics and rhythm are preserved, but the frequencies are replaced by the resonator's tuning.

### Key Parameters

**Frequency / MIDI Input:** The fundamental pitch of the resonators. Can be controlled by MIDI — play notes and the resonators retune in real-time. THIS is the key creative feature: drum loops become melodic patterns.

**Decay:** How long the resonators ring. Short (10-50ms) = percussive, plucky. Medium (100-500ms) = piano/mallet-like. Long (1-5s) = pad/drone-like.

**Partials:** How many resonant frequencies are generated.
- 1-4: Simple, clear tones
- 8-16: Complex, bell-like harmonics
- 32-64: Dense, almost reverb-like harmonic clouds

**Stretch:** Shifts the spacing of the partials.
- 100% = natural harmonic series
- Below 100% = compressed harmonics (metallic, inharmonic — bell/gamelan character)
- Above 100% = stretched harmonics (bright, airy)
- 50% = octaves only (hollow, organ-like)
- 200% = extreme stretch (very bright, almost white noise-like)

**Fine Shift:** Detunes all partials together. Even small amounts (1-5%) add chorusing and width. Large amounts (10-30%) create obvious detuning — dissonant, experimental.

### Creative Applications

**Turn drums into a melodic instrument:**
1. Route a drum loop into Spectral Resonator
2. Set to MIDI input
3. Play a chord — the drums now play that chord, with the rhythm of the original drums
4. Adjust Decay: short for rhythmic melodic percussion, long for pad-like drones
5. Post-process: Reverb → subtle distortion

**Vocal formants on synths:**
1. Route a synth pad into Spectral Resonator
2. Set Stretch to 80-90% and Decay to 200-400ms
3. Adjust Partials to 8-12
4. Modulate Frequency with a slow LFO — creates formant-shifting, vowel-like sounds
5. This is a simplified version of what SOPHIE did with vocal processing

**Metallic texture from noise:**
1. White noise → Spectral Resonator
2. Stretch: 40-60% (highly inharmonic — metallic)
3. Partials: 16-32
4. Decay: 50-150ms (percussive metallic hits)
5. MIDI-controlled pitch — play metallic melodies from pure noise

---

## Spectral Time

Two effects in one: spectral delay (different delay times per frequency band) and spectral freeze.

### Spectral Delay Mode

Each frequency bin gets its own delay time. This means the lows can be delayed differently from the highs, creating impossible spectral smearing.

**Delay Time / Tilt / Spray:** 
- **Time:** Overall delay
- **Tilt:** Positive = highs delayed more than lows (creates rising spectral sweep). Negative = lows delayed more (creates falling sweep).
- **Spray:** Randomizes the per-bin delay times — creates a spectral scatter that's unlike any normal delay

**Feedback:** Creates spectral echo buildup. At high values with Tilt, the feedback builds up in specific frequency regions — creates evolving, shifting spectral clouds.

### Freeze Mode

Captures a spectral snapshot and holds it — but unlike Reverb Freeze, you can manipulate the frozen spectrum:
- **Resolution:** How many spectral bins are captured — more = higher fidelity
- **Fade In/Out:** How the freeze crossfades
- Automate Freeze on/off in rhythm — capture → hold → release → capture new content

### Creative Applications

**Arca-style spectral wash:**
1. Spectral Time in Delay mode on a pad or vocal
2. Tilt: 40-60% (highs smear, lows stay tight)
3. Spray: 30-50% (randomize the smearing)
4. Feedback: 50-70% (build up the spectral wash)
5. Result: The sound dissolves into a spectral cloud while maintaining rhythmic energy in the lows

**Rhythmic spectral freeze:**
1. Spectral Time in Freeze mode on a drum loop
2. Automate Freeze: ON for 1 bar, OFF for 1 bar
3. While frozen, the captured spectrum sustains — creates a drone from drum content
4. When released, the live drums return
5. Alternating between frozen and live creates hypnotic section contrast

---

## Spectral Blur

Creates reverb-like effects from spectral blurring. A user-defined frequency range is smeared into a dense cloud.

### Key Parameters

**Freq Range (Start / End):** Which frequencies get blurred. This is the key creative control:
- Full range (20Hz-20kHz): Everything blurs — wall of sound
- Narrow band (e.g., 200-800Hz): Only the mids blur — creates a focused tonal cloud while leaving bass and highs clear
- High only (4kHz-20kHz): Shimmer effect — highs smear into a bright haze while lows and mids stay tight

**Halo:** Length of the blur grains. Short (10-50ms) = subtle smearing, almost like a room reverb. Long (200-500ms+) = extreme, drone-like blur.

**Residual:** Level of the unblurred signal mixed back in. At 0%, only the blur is heard. At 50%, half blur / half original. At 100%, full original with blur layered on top.

**Freeze:** Same concept as Spectral Time — captures and holds the blurred spectrum.

### Creative Applications

**Selective frequency smearing:**
1. Spectral Blur on a busy mix element
2. Range: 800Hz - 3kHz (only mid frequencies)
3. Halo: 150-300ms
4. Residual: 60-80% (mostly original, with mid-frequency blur)
5. Result: The mids develop a "halo" while bass and highs stay precise — creates depth without muddiness

**Frozen harmonic drone:**
1. Spectral Blur on any input (even a single hit)
2. Full frequency range
3. Halo: 500ms+
4. Freeze ON after a resonant hit
5. Result: A sustained drone built from the spectral content of one moment

---

## Resonators

Five tuned resonators excited by the input signal. Creates pitched, metallic, or tonal resonance from any source.

### Key Parameters

**Note / Fine:** Tuning of each resonator. Key insight: tune them to a chord:
- Resonator I: Root (C3)
- Resonator II: Third (E3)
- Resonator III: Fifth (G3)
- Resonator IV: Octave (C4)
- Resonator V: Minor seventh (Bb3)
- Now ANY input (drums, noise, speech) becomes harmonized in that chord

**Decay:** How long each resonator rings. Short = percussive. Long = sustaining drone.

**Color:** Brightness of the resonance. Low = dark, warm. High = bright, metallic.

**Filter (Input):** Filters what frequencies excite the resonators:
- Lowpass: Only bass/mid content triggers resonance — warm, round
- Highpass: Only high content triggers resonance — bright, metallic
- Bandpass: Specific frequency range — focused, precise excitation

### Creative Applications

**Auto Shift + Resonators (from Ableton 12.1 tutorial):**
1. Audio input → Auto Shift (pitch tracking + correction)
2. Auto Shift MIDI output → Resonators (controls tuning)
3. Result: The resonators retune in real-time to match the pitch of the incoming audio — creates a harmonized, resonant shadow of whatever passes through

**Drum-to-melody conversion:**
1. Drum loop → Resonators (tuned to a chord)
2. Short decay (20-50ms) so resonance is percussive
3. Color high (70-80%) for metallic character
4. Mix with original drums for pitched percussion overlay
5. Automate Note parameter to change the chord every 8 bars — drums play different harmonies

---

## Corpus

Physical modeling resonator — simulates the vibration of physical objects: tubes, plates, membranes, strings.

### Types

**Beam / Marimba / String / Membrane / Plate / Tube / Pipe**

Each type has different resonant behavior:
- **Beam/Marimba:** Bright, percussive. Good for turning any hit into a mallet instrument.
- **String:** Sustained, warm. Creates bowed or plucked string-like resonance.
- **Membrane:** Drum-head resonance. Adds body and tone to drum sounds.
- **Plate:** Bright, dense, long decay. Creates plate-reverb-like effects.
- **Tube/Pipe:** Hollow, wind-instrument-like. Adds breathy, airy character.

### Key Parameters

**Tune / Fine:** Pitch of the resonator. Crucial: the resonance only works musically when tuned to match the song's key.

**Decay:** How long it rings. Combined with the type, this determines if the sound is percussive or sustained.

**Brightness:** High-frequency content of the resonance.

**Ratio:** Changes the ratio of the partials — makes the resonance more or less metallic.

### Creative Application

**Physical body for electronic sounds:**
1. Dry synth stab → Corpus (Plate type)
2. Tune to match the synth's pitch
3. Decay 200-500ms
4. Dry/Wet 30-40%
5. Result: The synth stab gains a physical, wooden/metallic body — it sounds like it exists in a physical space. This is the difference between "electronic sound" and "electronic sound played through a physical object."

---

## Vocoder

Imposes the spectral shape of one signal (modulator — usually voice) onto another (carrier — usually synth).

### Creative Uses Beyond Vocals

**Drum-shaped synths:**
1. Carrier: Sustained pad or synth chord
2. Modulator: Drum loop
3. The synth's timbre is shaped by the drum's dynamics — it "speaks" the rhythm of the drums while maintaining the pitch of the synth

**Noise-to-speech:**
1. Carrier: White noise
2. Modulator: Spoken word / vocal
3. Bands: 16-40 for intelligibility
4. The noise "speaks" with the vocal's spectral shape — creates whispered, ghost-like speech

**Cross-synthesis between any two signals:**
1. Carrier: Signal A (e.g., a pad)
2. Modulator: Signal B (e.g., a different pad or a recording)
3. Creates a hybrid that has Signal A's pitch but Signal B's spectral character
4. This is the foundation of spectral morphing between sounds

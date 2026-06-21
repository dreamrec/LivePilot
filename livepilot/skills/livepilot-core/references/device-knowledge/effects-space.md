# Space & Time Effects — Deep Parameter Knowledge

## Reverb

Live's algorithmic reverb. Surprisingly deep when you understand the parameter interactions.

### Key Parameters That Most People Ignore

**ER Spin (Early Reflections Spin):** A modulation effect on the early reflections. Rate and Amount controls create subtle movement in the reverb's initial character. This is what makes the difference between a "dead" reverb and a "living" space.
- Rate 0.1-0.3 Hz, Amount 2-4: Natural room movement
- Rate 0.5-1 Hz, Amount 5-8: Dreamy, swirling early reflections
- Rate 2-5 Hz, Amount 10+: Chorus-like shimmer on the reverb itself

**Chorus (in the reverb):** Modulates the diffuse field. This is the "secret" dub techno ingredient.
- Rate 0.02-0.05 Hz, Amount 0.1-0.3: Extremely slow pitch modulation inside the reverb tail — creates the Basic Channel "underwater" quality
- Rate 0.1-0.3 Hz, Amount 0.5-1.0: More obvious modulation — dreamy, ethereal
- Key: Keep the rate VERY slow. Fast chorus in a reverb creates seasickness, not depth.

**Diffusion:** How quickly the reflections smear together.
- Low (20-40%): Distinct echoes visible in the tail — creates a "flutter" reverb, good for drums
- Medium (50-70%): Smooth but with character — the most musical range
- High (80-100%): Completely smooth, wash-like — good for pads, dangerous for drums (muddiness)

**Scale:** Shrinks or expands the "room size" without changing decay time. At 20-40%, it's a small, tight space. At 80-100%, it's a cathedral. Combined with long decay, low scale creates an impossible space — long reverb in a small room. This is physically impossible but sonically interesting.

**Freeze:** Captures the current reverb tail and holds it indefinitely. The sound becomes a drone. Automate this: Freeze ON for 2-4 bars, then OFF — creates a momentary "wall of reverb" that fades naturally.

### Dub Techno Reverb Recipe (Return Track)

- Predelay: 10-20ms
- Input filter: LowCut ON, HighCut ON, Freq 800-1200 Hz, Width 5-6 (bandpass-like — only mids enter the reverb)
- ER Spin: Rate 0.2 Hz, Amount 3.5
- Chorus: Rate 0.02 Hz, Amount 0.15 (VERY slow)
- Decay: 4-8s
- Diffusion: 65-75%
- HiShelf: ON, Freq 4kHz, Gain 0.3-0.4 (darken the tail)
- Room Size: 80-100
- Dry/Wet: 100% (it's on a return track)

Send to this return in bursts (delay throws) for the classic dub techno wash.

---

## Convolution Reverb (Hybrid Reverb includes this)

Uses impulse response recordings of real spaces. The IR determines everything about the reverb character.

### Creative IRs

The stock IRs include rooms, halls, plates, springs. But the creative use is loading **non-standard IRs**:
- Record your own: clap in a stairwell, snap near a metal object, record the result → use as IR
- Use any audio as IR: a drum break, a vocal phrase, a synth chord — the convolution imprints that audio's spectral character onto whatever passes through it
- Short IRs (0.1-0.5s) act more like EQ/filtering than reverb — they add the tonal character of the source without the spatial tail

### Hybrid Reverb

Combines convolution (early reflections from real spaces) with algorithmic (customizable tail). Best of both worlds.
- Use convolution for realistic early reflections
- Use algorithmic tail with chorus/modulation for the evolving, musical tail
- The crossover between convolution and algorithmic is the key parameter — adjust where one takes over from the other

---

## Delay

Updated in 12.4 with new LFO modes. The most creative delay in Live.

### Key Parameters

**Repitch vs Fade vs Jump modes:**
- **Repitch:** Changing delay time pitches the delayed signal (tape delay behavior). THIS is the dub techno delay. Modulate the delay time and you get pitch-warped echoes.
- **Fade:** Changing delay time crossfades between old and new time — smooth, no pitch artifacts. Better for mixing, less creative.
- **Jump:** Instant change — creates a hard rhythmic shift. Good for glitch-style delays.

**Ping Pong:** Alternates echoes left-right. Essential for stereo width. But the real trick: combine Ping Pong with slightly different L/R delay times (use L Offset / R Offset at ±2-3%) for a more natural, wide stereo delay.

**Mod Freq / Dly < Mod / Filter < Mod:** The modulation section.
- **Dly < Mod:** Modulates delay time — creates pitch wobble on echoes. At 5-15%, subtle tape-like wow. At 20-40%, obvious pitch warping — dub character. At 50%+, extreme — pitch spirals.
- **Filter < Mod:** Modulates the filter cutoff with the same LFO — echoes alternately brighten and darken. Combined with Dly < Mod, this creates echoes that are never the same twice.

**Filter Freq / Width:** Bandpass filter in the feedback loop. This shapes how each echo changes:
- Freq 500-1000 Hz, Width 4-6: Dark, telephone-like echoes that thin out over time (classic dub)
- Freq 2000-4000 Hz, Width 8+: Bright, present echoes
- Very narrow Width (1-2) at specific frequencies: Resonant, almost pitched echoes — creates melodic delays

**Feedback:** How many echoes repeat.
- 30-50%: Standard delay tail
- 60-75%: Long, evolving tail — the dub zone
- 80-90%: Near self-oscillation — echoes build up dangerously. Automate this: push to 85% for 2 beats then pull back to 50% — creates a momentary feedback spiral that resolves
- 95-100%: Self-oscillation — infinite echoes that build until they clip. Use Freeze instead for controlled infinite delay.

---

## Echo

Combines delay + modulation + reverb + ducking + noise in one device. More character than Delay, less precise.

### Key Parameters

**Character section:** Adds specific analog/tape quality to the delay:
- **Noise:** Adds noise to the feedback loop — each echo gets noisier (tape hiss character)
- **Wobble:** Pitch instability in the delay — tape wow/flutter. At 10-20%, subtle vintage. At 40%+, extreme warping.
- **Repitch:** Same as Delay's repitch — pitch shifts when time changes.

**Reverb (built-in):** A small reverb INSIDE the delay. This means each echo goes through reverb before feeding back. Creates incredibly dense, washy delay tails. Turn this up for instant dub character.

**Ducking:** The delay ducks (gets quieter) when new audio comes in, then swells when the audio stops. This is automatic delay throw behavior — no need for send automation. The dry signal stays clear, and the delay fills the gaps.
- Threshold: How loud the input must be to trigger ducking
- Release: How fast the delay comes back after the input stops
- This is THE feature for adding delay to lead elements — keeps them clear while adding space in the gaps.

---

## Grain Delay

Not just a delay — a real-time granular processor that happens to have delay.

### The Granular Part

**Pitch:** Transposes the delayed grains independently of delay time. Set to +12 for octave-up shimmer delays. Set to -12 for octave-down drones. Set to +7 for fifth-up harmonization.

**Spray:** Randomizes the timing of grains. At 0, grains are precise. At 10-30ms, they're slightly scattered (organic). At 50-100ms, they're chaotic — creates a granular cloud rather than distinct echoes.

**Frequency:** The grain size. Small grains (high frequency) = detailed, glitchy texture. Large grains (low frequency) = smooth, flowing. Automate this for evolving texture.

### Creative Applications

**Shimmer reverb (Grain Delay on return):**
- Delay Time: 30-60ms (very short, almost reverb-like)
- Pitch: +12 (octave up)
- Feedback: 65-80% (builds up octave harmonics)
- Spray: 15-30ms (softens the repetitions)
- Random Pitch: 5-10% (adds slight detuning to each grain — shimmering)
- Filter: Lowpass around 6kHz (tames harshness from octave stacking)
- Result: Each echo is an octave higher than the last — builds a shimmering harmonic tower

**Alien texture generator (from Ableton blog):**
- Pitch: +5 or -7 (non-octave intervals create dissonance)
- Spray: 80-150ms (chaotic timing)
- Feedback: 70-85%
- Random Pitch: 20-40%
- Input: Any percussive source
- Result: A cloud of pitched, scattered, feeding-back grains that creates an organic, alien texture from simple source material

---

## Creative Delay Chains

### The Dub Space (Return Track)
1. Delay (Repitch mode, Ping Pong, 3/16 time, Feedback 65%, Filter 800Hz/Width 5, Mod 0.2Hz/Dly<Mod 12%/Filter<Mod 20%)
2. Reverb (Decay 4s, Diffusion 70%, Chorus 0.02Hz/0.15, ER Spin 0.2Hz/3.5)
3. EQ Eight (HP at 200Hz, gentle -2dB shelf above 6kHz)

### The Shimmer Space (Return Track)
1. Grain Delay (Pitch +12, Time 45ms, Feedback 72%, Spray 20ms)
2. Reverb (Decay 6s, Diffusion 85%, Freeze OFF)
3. Auto Filter (Lowpass 5kHz, gentle slope — tames the octave buildup)

### The Chaos Delay (for WTF moments)
1. Echo (Time 3/16, Feedback 80%, Wobble 30%, Reverb 40%, Noise 15%)
2. Frequency Shifter (Ring mode, Freq 0.5-2 Hz — very slow shifting)
3. Use as a send — brief bursts only (1-2 beats), then pull the send back to zero

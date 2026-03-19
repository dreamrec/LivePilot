# Automation Atlas — LivePilot v1.6

Complete knowledge corpus for musically intelligent automation. Load this reference when working with automation tools.

---

## 1. Curve Theory

### Why exponential for filters
Filter frequency perception is logarithmic (octaves). 100Hz → 200Hz is the same perceptual distance as 1kHz → 2kHz. An exponential curve in the normalized 0–1 range maps to perceptually even movement across the frequency spectrum. Linear automation on a filter sounds like it's rushing through the highs and crawling through the lows. Use `exponential` with `factor` 2.0–3.0 for filter cutoff.

### Why logarithmic for volume
Human loudness perception follows a logarithmic curve (Weber-Fechner law). -6dB = half perceived loudness, not half amplitude. A logarithmic fade-in sounds smooth; a linear fade-in sounds like nothing happens then suddenly gets loud. Use `logarithmic` with `factor` 2.5–3.5 for volume fades.

### Why S-curve for crossfades
Natural acceleration/deceleration. Avoids the "hole in the middle" of linear crossfades where combined energy dips. The smoothstep function (3t² - 2t³) ensures the rate of change is zero at both endpoints, so the transition feels organic. Use `s_curve` for any A→B crossfade.

### Why spike for throws
Dub production technique — instant send level spike creates a single reflection that decays naturally through the reverb/delay tail. Any other shape creates unnatural sustained reflections. The exponential decay (peak × e^(-decay×t)) models how real acoustic energy dissipates.

### Pan is linear
Stereo position perception is roughly linear. A pan pot moving at constant speed sounds even. No need for perceptual correction on pan automation.

### Resonance is dangerous
Filter resonance is non-linear — subtle changes at low values, dramatic and potentially destructive at high values. Self-oscillation begins above ~0.85 on most filters. Never automate resonance above 0.85 without explicit user intent. Use `breathing` recipe with reduced amplitude (0.05–0.10) for subtle resonance movement.

---

## 2. The Perception-Action Loop (5 levels)

**MANDATORY for all automation work.** Never write automation blind — always perceive first.

### Level 1: Reactive
Single read, single action. The simplest loop.
1. `get_master_spectrum` → read frequency content
2. Identify one issue (e.g., "mud below 200Hz")
3. Apply one automation (e.g., HP filter sweep)
4. `get_master_spectrum` → verify improvement

### Level 2: Diagnostic
Multi-step investigation using EQ as a microscope. See Section 3 (Diagnostic Filter Technique).

### Level 3: Verification
Act → measure → adjust cycle. For every automation written:
1. Read spectrum BEFORE
2. Write automation
3. Read spectrum AFTER
4. Compare: did the problem frequency range improve?
5. If not, `clear_clip_automation` → adjust parameters → try again
6. Log the successful parameters in memory for reuse

### Level 4: Cross-Track
Solo each track, build spectral map, write complementary automation.
1. For each track: solo → `get_master_spectrum` → record fingerprint
2. Find frequency overlaps between tracks (masking)
3. Write complementary automation: as kick's filter opens, bass's filter narrows
4. Verify no new masking was introduced
5. Store the cross-track map in memory

### Level 5: Full Pipeline
Per-track analysis across entire session.
1. Run Level 4 for all tracks
2. Build session-wide spectral map
3. Write automation considering all interactions
4. Verify global mix spectrum
5. Iterate until balanced

---

## 3. Diagnostic Filter Technique

Using EQ Eight as a measurement instrument. Step-by-step:

1. **Load EQ Eight** on target track via `find_and_load_device`
2. **Configure band 1** as narrow bandpass: Q=8, gain=0dB, frequency=100Hz
   - Use `set_device_parameter` to set Filter Type to Band Pass, Q to 8.0
3. **Solo the track** via `set_track_solo`
4. **Read spectrum** at 100Hz: `get_master_spectrum` → note the `sub` value
5. **Sweep frequency** through key ranges:
   - 100Hz, 200Hz, 300Hz, 500Hz, 1kHz, 2kHz, 5kHz, 10kHz
   - At each: `set_device_parameter` (frequency) → `get_master_spectrum` → record
6. **Build frequency map**: `{100Hz: 0.18, 200Hz: 0.25, 300Hz: 0.09, ...}`
7. **Identify problems**: resonance buildup, mud, harshness, dead zones
8. **Remove diagnostic EQ** — always clean up: `delete_device`
9. **Un-solo the track**: `set_track_solo` (toggle off)
10. **Write targeted automation** addressing what was found

### What to look for:
- **Mud** (200-400Hz): values > 0.20 suggest buildup → HP filter automation
- **Resonance** (narrow peak in 300-800Hz): ringing → notch filter or gentle sweep
- **Harshness** (2-5kHz): values > 0.25 suggest brightness → LP filter or shelf automation
- **Dead zone** (any range with 0.00): frequency hole → boost or different device

---

## 4. Genre Recipes

### Techno
- `filter_sweep_up` on LP cutoff, 32 bars, factor 2.0 — the classic build
- `sidechain_pump` on pad volume via Utility gain, 1 beat loop
- `stutter` on vocals before drop, 0.5 beats, frequency 16
- `stereo_narrow` on master bus, 8 bars before drop → instant widen at drop
- Long transitions: combine HP filter + reverb send + stereo width, all exponential

### Dub
- `dub_throw` on Send A at each snare position, 1 beat duration
- `tape_stop` on clip transpose for transitions, 0.5 beats
- `washout` on delay feedback, 4 bars → cut at phrase boundary
- `breathing` on filter cutoff, 4 bars — everything breathes in dub
- Tip: never automate delay feedback above 0.85 (infinite feedback risk)

### Ambient
- `breathing` on filter cutoff, 4 bars, amplitude 0.10 — subtle is key
- `perlin` noise on reverb mix, 8 bars, amplitude 0.15, seed varies
- `brownian` drift on wavetable position, 16 bars, volatility 0.05
- Polyrhythmic automation: 3-beat filter + 5-beat reverb + 7-beat pan = 105-beat cycle
- Less is more. Ambient automation should be felt, not heard.

### Hip Hop
- `tape_stop` on clip transpose, 0.5 beats — classic vinyl stop
- `vinyl_crackle` on Redux bit depth, 16 bars — lo-fi character
- `sidechain_pump` on bass under kick, 0.5 beat — tight pocket
- `fade_out` on filter for transitions between sections
- Keep automation sparse — hip hop is about groove, not modulation

### IDM / Experimental
- `stutter` on volume, 0.5 beats, frequency 16 — micro-editing
- `euclidean` on filter cutoff: 5 hits across 8 steps — rhythmic intelligence
- `stochastic` on grain parameters, narrowing 0.7 — controlled chaos
- `spring` on filter cutoff for overshoot character
- Layer multiple polyrhythmic automations for generative evolution

---

## 5. Sound Design Automation

### Wavetable position
Exponential sweep for timbral morphing over 8–16 bars. The timbral change is often perceptually logarithmic, so exponential automation creates even-sounding evolution.

### Grain size
Sine modulation at 0.5–2Hz for alive textures. The slow oscillation prevents the grainular artifacts from sounding static. Use `breathing` recipe adapted: center 0.5, amplitude 0.15.

### Reverb decay
Link inversely to volume: quieter passages get longer tails for natural space. As volume drops, reverb decay increases. Automate both with complementary curves.

### Delay feedback
Spike for throws (dub technique). NEVER exceed 0.9 on feedback — infinite feedback creates dangerous signal buildup. Use `dub_throw` recipe with peak capped at 0.85.

### Filter resonance
Subtle sine modulation creates vocal/crying quality. Watch for self-oscillation above 0.85. Use amplitude 0.05–0.10 for subtle character, 0.15–0.25 for expressive.

---

## 6. Arrangement Techniques

### The Build (16–32 bars before drop)
Combine multiple automations, all exponential:
1. HP filter: 0→0.6 (remove low end gradually)
2. Volume: 0.7→1.0 (subtle lift)
3. Reverb send: 0→0.5 (add wash)
4. Stereo width: 1.0→0.0 (collapse to mono)
5. At drop: instant step back to defaults

### The Drop (instant)
Step automation restoring all build parameters to default values. No curves — immediate snap. Use `steps` curve with a single value at time 0.

### The Strip (8–16 bars)
Gradual HP filter rise removing elements one by one:
1. First: HP filter on bass track (removes bass)
2. Then: HP filter on drums (removes kick)
3. Then: HP filter on pads (removes mids)
4. Only high frequencies remain → transition point

### The Crossfade (2–8 bars)
S-curve volume automation between two sections:
- Outgoing track: s_curve from 1.0 to 0.0
- Incoming track: s_curve from 0.0 to 1.0
- S-curve prevents the energy dip of linear crossfades

---

## 7. Micro-Editing and Humanization

### Velocity vs volume
Velocity is timbre — it changes how the sound is generated (harder hits, brighter tone). Volume automation is loudness — it changes amplitude after generation. They are different tools.

### Per-note filter accent
Automate filter cutoff to spike on accented notes. Use `spike` with duration matching the note length. Creates timbral accents without touching velocity.

### Spatial punctuation
Send spikes on specific hits create spatial depth variation. Snare → reverb throw on beat 2 and 4. Hi-hat → delay throw on off-beats. Use `dub_throw` recipe.

### Humanization via Perlin noise
Tiny pitch/filter variations make programmed music feel human:
- `perlin` on detune: amplitude 0.02, frequency 0.5
- `perlin` on filter cutoff: amplitude 0.05, frequency 0.3
- Different seeds per track — each voice drifts independently

---

## 8. Polyrhythmic Automation

### The concept
Unlinked automation envelopes with different loop lengths create long, non-repeating cycles:
- 4-beat clip loop + 3-beat filter envelope + 5-beat reverb envelope
- Total cycle: LCM(4, 3, 5) = 60 beats before exact repetition
- 60 beats ≈ 15 bars at 4/4 — feels evolving, never static

### Prime number rule
Use prime-number beat lengths for maximum non-repetition:
- 3, 5, 7, 11, 13 beats
- LCM of primes = their product (all coprime)
- 3 × 5 × 7 = 105 beats ≈ 26 bars before exact repeat

### Implementation
1. Create clip with N-beat loop (your base rhythm)
2. `apply_automation_shape` with `duration` = M beats (M ≠ N, preferably prime)
3. The automation loops at M beats, the clip loops at N beats
4. Add another automation with duration = P beats (another prime)
5. Total cycle = LCM(N, M, P) beats

### Use cases
Essential for ambient, installation, generative work. Creates the sense of "always evolving" that distinguishes produced music from loops.

---

## 9. Cross-Track Spectral Mapping

### Process
1. **Solo each track** one at a time
2. **Read spectrum**: `get_master_spectrum` → record {sub, low, mid, high, presence, air}
3. **Build spectral fingerprint** for each track:
   ```
   Kick:  sub=0.45, low=0.30, mid=0.05, high=0.02
   Bass:  sub=0.35, low=0.40, mid=0.15, high=0.03
   Pad:   sub=0.05, low=0.15, mid=0.35, high=0.25
   ```
4. **Find overlaps**: kick and bass both strong in sub/low = masking
5. **Write complementary automation**: as kick opens, bass narrows
6. **Verify**: un-solo all, check master spectrum for improvement

### Complementary automation patterns
- **Kick + Bass**: sidechain pump on bass volume, or complementary filter sweeps
- **Vocals + Pads**: automate pad filter to duck in vocal frequency range (1–4kHz)
- **Multiple synths**: different breathing rates (frequency 0.3, 0.5, 0.7) to weave in/out

### Store findings
Use `memory_learn` to save spectral maps and successful automation combinations. Build a knowledge base about the session's sounds for consistent decisions.

---

## 10. Golden Rules

1. **Always use Utility gain for volume automation** — preserve the mixer fader for mixing. Automate the Utility device's Gain parameter, not track volume.

2. **Exponential for filters, logarithmic for volume** — never linear for either. This is perceptual science, not preference.

3. **Subtle automation (5–15% range) for organic feel; dramatic (full range) for transitions.** Most automation should be felt, not heard. Save the big sweeps for builds and drops.

4. **ALWAYS verify with `get_master_spectrum` after writing automation.** The feedback loop is mandatory, not optional.

5. **Use `clear_clip_automation` before rewriting.** Don't stack conflicting curves — clear first, then write fresh.

6. **Use the diagnostic filter technique before guessing at problem frequencies.** Measurement beats intuition.

7. **Store spectral findings in memory.** Build a knowledge base about this session's sounds. Cross-session awareness makes every future decision better.

8. **Delay feedback NEVER above 0.9.** Infinite feedback creates dangerous signal buildup. Cap at 0.85 for safety, even in experimental contexts.

9. **density 16–32 for most curves.** 16 points per bar gives smooth results for gentle curves. 32 for fast modulations or detailed shapes. Above 64 is rarely worth the overhead.

10. **When in doubt, use a recipe.** The 15 built-in recipes encode production wisdom. Start with the recipe, then customize if needed.

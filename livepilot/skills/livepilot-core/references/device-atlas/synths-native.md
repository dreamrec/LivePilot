# Ableton Live 12 — Native Synthesizers Deep Reference

> For LivePilot agent use. Covers sonic character, signal flow, key parameters,
> sound recipes, and decision guidance for every built-in synth instrument.

---

## Table of Contents

1. [Analog](#analog)
2. [Wavetable](#wavetable)
3. [Operator](#operator)
4. [Drift](#drift)
5. [Meld](#meld)
6. [Tension](#tension)
7. [Collision](#collision)
8. [Electric](#electric)
9. [Simpler](#simpler)
10. [Sampler](#sampler)
11. [Impulse](#impulse)
12. [Quick Decision Matrix](#quick-decision-matrix)

---

## Analog

- **Type:** Native (Suite)
- **Synthesis:** Subtractive — physical-modeled analog oscillators
- **Character:** Warm, fat, vintage. Captures the beating, drift, and saturation of real analog hardware. Sits naturally in a mix without much processing. Can go from polished polysynth pads to gritty acid bass.

### Signal Flow

```
Osc 1 ──┐                    ┌── Filter 1 → Amp 1 ──┐
         ├─ (F1/F2 balance) ─┤                       ├─ Output
Osc 2 ──┘                    └── Filter 2 → Amp 2 ──┘
Noise ───────────────────────────→ (routable to F1/F2)

LFO 1 → modulates Osc / Filter / Amp
LFO 2 → modulates Osc / Filter / Amp
Each Filter and Amp has its own ADSR envelope.
```

Routing modes: **Parallel** (Osc1→Fil1→Amp1, Osc2→Fil2→Amp2), **Series** (both Oscs→Fil1→Fil2→Amp), or any blend via the F1/F2 slider per oscillator.

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Osc Shape** | Sine, saw, rectangle, noise | Saw for leads/bass, rectangle for hollow tones |
| **Sub Oscillator** | Adds one octave below Osc 1 | Turn up for bass weight; level ~60-80% |
| **Pulse Width** | Rectangle width (PWM via LFO) | 40-60% for classic PWM pads |
| **F1/F2 Slider** | Routes each osc to Filter 1, Filter 2, or both | Center = both filters; extremes = dedicated routing |
| **Filter Type** | LP, BP, Notch, HP, Formant in 2-pole/4-pole | LP4 for bass; Formant for vowel textures |
| **Filter Drive** | Sym1-3, Asym1-3 saturation curves | Sym2 for warmth; Asym2 for grit |
| **Resonance** | Filter peak emphasis | 30-50% for character; 80%+ for acid squelch |
| **Error** | Simulates vintage oscillator drift | 5-15% for subtle analog feel |
| **Unison** | Stacked detuned voices | 2-4 voices, detune 10-20% for fatness |
| **Glide** | Portamento (mono mode) | 50-150ms for bass slides |

### Sound Recipes

- **Analog Bass:** Osc1 saw, Sub osc on, LP4 filter, cutoff ~300Hz, resonance 30%, short filter env decay (200ms), mono mode, glide 80ms.
- **PWM Pad:** Osc1+2 rectangle, detune Osc2 +5 cents, LFO1→PW at rate ~0.3Hz, LP4 cutoff ~2kHz, slow attack (500ms), long release (2s).
- **Acid Lead:** Osc1 saw, LP4 filter, resonance 70%+, short filter env with high amount, Sym2 drive, mono mode, glide 60ms.
- **Formant Pad:** Osc1 saw, Formant filter, resonance ~40%, slow LFO→cutoff, EXP envelope mode for vowel sweeps.
- **Jungle Bass:** Osc1 saw + sub, pitch envelope with fast decay diving 1-2 octaves, LP4 filter tight, mono mode.

### Reach for This When

- You want something that sounds like a real analog polysynth (Prophet, Juno, OB-X).
- Classic subtractive patches: basses, leads, pads, brass.
- You need dual-filter routing for complex timbres.
- Formant/vowel sounds without samples.

### Don't Use When

- You need wavetable morphing, FM metallic tones, or physical modeling.
- CPU is very tight (Analog is moderate; Drift is lighter).
- You want quick, modern digital textures (reach for Wavetable or Meld instead).

### vs Other Synths

- **vs Drift:** Analog has dual filters, more routing options, and a more complex architecture. Drift is simpler, lighter on CPU, and has built-in per-voice instability. Choose Analog for complex patches, Drift for quick analog vibes.
- **vs Wavetable:** Analog excels at classic subtractive warmth; Wavetable excels at evolving digital textures and morphing timbres.
- **vs Operator:** Analog for warm/fat; Operator for metallic/crystalline FM tones.

---

## Wavetable

- **Type:** Native (Suite)
- **Synthesis:** Wavetable — morphable wavetable oscillators with effect processors
- **Character:** Versatile chameleon. Can be warm and lush (slow wavetable sweeps), aggressive and digital (fast modulation, warp/fold), or anywhere in between. The morphing engine gives it a constantly evolving quality that subtractive synths lack.

### Signal Flow

```
Osc 1 (wavetable + effect) ──┐
                              ├─ Filter 1 ─┐
Sub Osc (sine) ───────────────┤             ├─ Amp → Output
                              ├─ Filter 2 ─┘
Osc 2 (wavetable + effect) ──┘

Filter routing: Serial (F1→F2), Parallel (F1+F2), Split (Osc1→F1, Osc2→F2)
Mod Matrix: 3 Envelopes + 2 LFOs + MIDI sources → any parameter
```

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Wavetable Position** | Scrolls through waveforms in the table | Automate or modulate this — it IS the sound |
| **Wavetable Category** | Basic Shapes, Complex, Distortion, Noise, User... | Basic Shapes for clean, Distortion for aggressive |
| **Osc Effect: FM** | FM from internal oscillator (Tune + Amount) | Tune 50%, Amount 10-30% for harmonic richness |
| **Osc Effect: Classic** | Pulse Width + Sync | PW 60%, Sync 15% for rave/retro buzz |
| **Osc Effect: Modern** | Warp + Fold (phase distortion / wavefold) | Fold 30-60% for digital grit |
| **Sub Osc** | Pure sine sub layer with Tone and Octave | Tone 0 for clean sub, Tone up for harmonics |
| **Filter Type** | LP/HP/BP/Notch/Morph in 12dB or 24dB | Morph filter for sweepable variety |
| **Filter Drive** | OSR, MS2, SMP, PRD (analog-modeled) | MS2 for Moog-style warmth |
| **Unison Mode** | Classic, Shimmer, Noise, Phase Sync, Position Spread, Random Note | Shimmer for pads; Noise for glitch drones |
| **Unison Voices** | Number of stacked voices | 4-8 voices for lush; 2 for subtle |
| **Mod Matrix** | Route any mod source to any parameter | Env2→Position is the fundamental Wavetable move |

### Sound Recipes

- **Evolving Pad:** Osc1 position modulated by slow Env2 (loop mode, 4s cycle), Shimmer unison 4 voices, LP filter ~3kHz, slow LFO→filter cutoff. Osc2 on different wavetable for thickness.
- **Supersaw Lead:** Both oscs on Basic Shapes saw, Classic unison 8 voices, LP filter ~5kHz with env, moderate drive. Classic mode PW at 50%.
- **Digital Bass:** Osc1 Distortion wavetable, Modern effect (Fold ~40%), Sub osc on (octave -1), LP24 filter ~800Hz, short env decay.
- **Glitch Drone:** Noise unison mode, both oscs on textural wavetables, slow position modulation, Split filter routing with different cutoffs.
- **Pluck:** Short Env1 decay (150ms), Env2→Position (short decay), LP filter with env amount, no sustain.

### Reach for This When

- You need evolving, morphing textures (wavetable position modulation is unmatched).
- Modern electronic production: EDM, future bass, dubstep, ambient.
- You want massive unison sounds with character options (Shimmer, Noise, etc.).
- Complex modulation routing needed (the mod matrix is deep).
- Aggressive digital basses and leads.

### Don't Use When

- You want pure analog warmth (Analog or Drift will sound more authentic).
- You need FM bell/metallic sounds specifically (Operator is more direct for FM).
- Physical modeling / acoustic instrument simulation (Tension, Collision, Electric).

### vs Other Synths

- **vs Analog:** Wavetable is more versatile and modern-sounding; Analog is warmer and more focused on classic subtractive.
- **vs Operator:** Wavetable for broad timbral variety and morphing; Operator for precise FM harmonics and metallic tones.
- **vs Drift:** Wavetable is the big, deep option; Drift is the quick, characterful option.
- **vs Meld:** Both are modern and versatile, but Wavetable has deeper wavetable morphing while Meld has more experimental oscillator types and better MPE integration.

---

## Operator

- **Type:** Native (Suite)
- **Synthesis:** FM (Frequency Modulation) + Additive + Subtractive hybrid
- **Character:** Crystalline, metallic, percussive, bell-like at its core. But deceptively versatile — can produce warm pads (additive mode), punchy basses, crisp percussion, and evolving textures. The quintessential "Swiss army knife" synth.

### Signal Flow

```
4 Oscillators (A, B, C, D) arranged per selected Algorithm:
  - Modulators: oscillators that modulate other oscillators' frequencies
  - Carriers: oscillators that output audio directly

Oscillators → Filter (optional) → Output

Each oscillator has:
  - Waveform (sine default, or custom 64-harmonic additive)
  - Independent ADSR envelope
  - Coarse/Fine tuning (harmonic ratios)
  - Level (both output volume AND modulation depth)
  - Feedback (self-modulation, typically on top oscillator)

LFO → can modulate any oscillator, filter, or pitch
```

### The 11 Algorithms

Algorithms are read top-to-bottom. Top oscillators modulate those below. Bottom-row oscillators are carriers (audio output). Side-by-side oscillators run in parallel.

| # | Configuration | Character | Best For |
|---|--------------|-----------|----------|
| 1 | D→C→B→A (serial chain) | Maximum FM complexity, harsh metallic | Metallic textures, extreme FM |
| 2 | D→C→B, D→A (branching) | Complex FM with parallel carrier | Rich evolving timbres |
| 3 | D→B→A, C→A (dual mod paths) | Two modulation sources into one carrier | Complex bells, plucks |
| 4 | D→C→B→A, D→A (feedback loop feel) | Dense, clangorous | Industrial, noise textures |
| 5 | D→C, B→A (dual pairs) | Two independent FM pairs | Layered sounds, dual timbres |
| 6 | D→C, D→B, D→A (one mod, three carriers) | One modulator shapes three voices | Organs, rich harmonics |
| 7 | D→C, B+A (partial FM + additive) | Mix of FM and clean tones | Warm FM with clean bottom |
| 8 | D+C→B→A (two mods into chain) | Complex modulation, controlled output | Evolving textures |
| 9 | D+C+B→A (three mods, one carrier) | Rich harmonic stacking | Bells, chimes, complex tones |
| 10 | D+C→B, A (partial FM + clean) | FM pair with independent clean osc | Hybrid patches |
| 11 | A+B+C+D (all parallel, no FM) | Pure additive/subtractive | Organs, analog-style, layered |

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Oscillator Level** | Both volume AND modulation depth | Carrier: set for mix balance. Modulator: 0-30% subtle, 50%+ harsh |
| **Coarse Ratio** | Harmonic relationship (1=fundamental) | Integer ratios (1,2,3,4) = harmonic. Non-integer = inharmonic/metallic |
| **Fine Tuning** | Micro-detune (1000 = 1 octave) | Small values (1-10) for beating; large for dissonance |
| **Fixed Frequency** | Pitch-independent oscillator | Essential for drum/percussion synthesis |
| **Waveform Editor** | Draw 64 harmonics per oscillator | Add odd harmonics only for square-like; all for saw-like |
| **Feedback** | Self-modulation on top oscillator | 0% = pure sine; 50% ≈ saw; 100% = noise |
| **Modulator Envelope** | Shapes FM intensity over time | Short decay = percussive attack. Long = sustained timbre |
| **Filter** | Post-FM filtering (analog-modeled) | LP for warmth; OSR drive for aggression |
| **LFO at Audio Rate** | Becomes a 5th oscillator for FM | Rate >20Hz for timbral FM effects |

### Sound Recipes

- **FM Bass:** Algorithm 1, Osc A carrier (sine), Osc B modulator at ratio 1, level ~40%, short Osc B envelope decay (300ms). Filter LP ~1kHz. Punchy and round.
- **DX7 Electric Piano:** Algorithm 5 (dual pairs), carriers at ratio 1, modulators at ratio 1 with ~25% level, moderate decay envelopes. Add velocity→modulator level.
- **Bell/Chime:** Algorithm 9, carrier A at ratio 1, modulators B/C/D at non-integer ratios (3.5, 7.1, 11.0), short-to-medium decays, no sustain. Resonant, inharmonic.
- **Organ:** Algorithm 11 (all parallel), all sines at ratios 1, 2, 4, 8 (drawbar equivalents). Adjust levels for registration.
- **Kick Drum:** Algorithm 11, Osc A sine, coarse 0.5, pitch envelope with instant attack and fast decay dropping 2+ octaves. Fixed freq mode on other oscs for click layer.
- **Metallic Pad:** Algorithm 1, slow attack on all envelopes, slight detuning on modulators, low modulation amounts (10-20%), filter LP with slow LFO.

### Reach for This When

- FM sounds: electric pianos, bells, chimes, metallic textures, plucks.
- Percussion and drum synthesis (kick, snare, hi-hat from scratch).
- You need precise harmonic control (additive mode with 64 harmonics per osc).
- DX7/FM nostalgia or modern FM bass.
- You want one synth that can do everything (steep learning curve, but deepest).

### Don't Use When

- You need quick results and don't understand FM (Wavetable or Drift are faster).
- You want lush analog warmth without effort (Analog is more immediate for this).
- Wavetable morphing textures (Wavetable is purpose-built for that).

### vs Other Synths

- **vs Analog:** Operator can emulate subtractive (Algorithm 11 + filter), but Analog sounds more authentically warm. Operator wins for metallic, crystalline, percussive.
- **vs Wavetable:** Operator for precise FM harmonics; Wavetable for morphing timbral evolution.
- **vs Drift:** Operator is deep/complex; Drift is immediate/characterful. Opposite ends of the accessibility spectrum.

---

## Drift

- **Type:** Native (Suite, included with Live 11.3+)
- **Synthesis:** Subtractive with analog-modeled instability
- **Character:** Warm, alive, breathing. Every note slightly different due to per-voice randomization. Sits between digital precision and analog unpredictability. Sounds effortlessly musical — the synth equivalent of an instrument that's been "played in."

### Signal Flow

```
Osc 1 (7 shapes + Shape mod) ──┐
                                ├─ LP Filter (Type I or II) → HP Filter → Amp → Output
Osc 2 (fewer shapes) ──────────┘
Noise ──────────────────────────┘

Envelope 1 (Amp ADSR)
Envelope 2 (assignable, can cycle as LFO)
LFO (9 waveforms, can reach audio rate)
Mod Matrix: 3 source→destination pairs
Drift control: per-voice random detune on both oscs + filter
```

### What Makes Drift Different from Analog

| Aspect | Drift | Analog |
|--------|-------|--------|
| **Complexity** | Simple, fast, musical | Deep, flexible, complex |
| **Filters** | 1 LP (2 types) + 1 HP | 2 full multi-mode filters |
| **Routing** | Fixed signal path | Configurable series/parallel |
| **CPU** | Very light | Moderate |
| **Instability** | Built-in per-voice Drift parameter | Manual Error parameter |
| **Oscillators** | More waveform variety, shape morphing | Classic shapes, less variety |
| **Character** | Effortlessly analog, organic | Precise, controllable analog |
| **Cycling Env** | Yes (Env2 becomes synced LFO) | No |

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Drift** | Per-voice random detune on oscs + filter | 20-40% for subtle warmth; 60%+ for obvious wobble |
| **Shape (Osc1)** | Morphs waveform character continuously | Depends on selected waveform — experiment |
| **Osc1 Waveforms** | Sine, triangle, shark tooth, saturated, saw, pulse, rectangle | Saw/pulse for leads; sine/triangle for subs |
| **LP Filter Type** | Type I (12dB gentle) vs Type II (24dB steep) | Type I for open sounds; Type II for bass/acid |
| **Filter Saturation** | Progressive saturation from osc levels above -6dB | Push osc levels to -3dB to 0dB for warmth |
| **Resonance** | Self-oscillates below -12dB osc input | Lower osc level + high resonance = tuned filter ping |
| **Cycling Envelope** | Env2 loops as tempo-synced modulator | Tilt control shapes triangle↔ramp; use as extra LFO |
| **Voice Modes** | Poly, Mono, Stereo, Unison | Stereo for wide pads; Unison for leads |
| **Amount (Mono)** | Blends in sub-oscillator content | 30-60% for bass reinforcement in mono mode |

### Sound Recipes

- **Warm Pad:** Osc1 saw + Osc2 saw detuned, Drift 30%, LP Type I cutoff ~3kHz, slow attack (400ms), long release (3s), Stereo voice mode.
- **Analog Bass:** Osc1 saw, Mono mode with Amount ~50% (sub), LP Type II cutoff ~500Hz, short filter env, Drift 15%.
- **Drifting Lead:** Osc1 pulse, Shape ~40%, Drift 50%, LP Type II cutoff ~2kHz, resonance 40%, Unison 4 voices, glide 80ms.
- **Generative Texture:** High Drift (70%+), cycling envelope modulating filter cutoff + osc shape, slow LFO on pitch, Poly mode.
- **Lo-fi Keys:** Osc1 triangle, Osc2 sine +12 semitones, Drift 40%, LP Type I cutoff ~4kHz, moderate decay envelope.

### Reach for This When

- Quick, characterful analog sounds without deep-diving into parameters.
- You want every note to feel alive and slightly different (the Drift parameter).
- Lo-fi, indie, synthwave, ambient — anything that benefits from organic imperfection.
- CPU budget is tight.
- MPE expression (Drift is MPE-capable).

### Don't Use When

- You need dual filters or complex routing (use Analog).
- You want digital precision or wavetable morphing (use Wavetable).
- You need FM synthesis (use Operator).

### vs Other Synths

- **vs Analog:** Drift trades complexity for character. If Analog is a modular system, Drift is a vintage monosynth you just plug in and play.
- **vs Meld:** Drift is focused and immediate; Meld is experimental and bi-timbral. Drift for quick analog; Meld for sound design exploration.

---

## Meld

- **Type:** Native (Suite, Live 12+)
- **Synthesis:** Bi-timbral macro oscillator — dual independent synth engines with 24 oscillator types each
- **Character:** Experimental, textural, otherworldly. Not trying to emulate analog or any specific hardware — Meld occupies its own sonic territory. Excellent at evolving textures, rhythmic drones, harmonic surprises, and sounds that defy easy categorization. Think Noise Engineering modules, Mutable Instruments Plaits, or Korg Wavestate.

### Signal Flow

```
Engine A:                          Engine B:
  Oscillator (1 of 24 types)        Oscillator (1 of 24 types)
  ↓                                 ↓
  Filter A                          Filter B
  ↓                                 ↓
  Amp A                             Amp B
  ↓                                 ↓
  ────────────── Mixer ──────────────
                   ↓
                 Output

Per-engine: LFO 1 (+ FX1/FX2 that modulate LFO1 shape), LFO 2, Mod Envelope
Cross-modulation: Engine A's LFOs can target Engine B's parameters and vice versa
Mod Matrix: MIDI/MPE sources assignable to any target
```

### The 24 Oscillator Types

Each engine can load any of 24 oscillator algorithms. Six are scale-aware (marked with a sharp/flat symbol). Each oscillator type has two macro knobs that control its most important parameters — the macros change function based on the loaded type.

**Categories include:**
- **Basic waveforms** — sine, triangle, ramp, square with Shape/Tone macros
- **Harmonic FM** — two-operator FM with Amount/Ratio macros
- **Swarm/Granular** — layered granular wave clusters
- **Noise Loop** — looped noise segments for textural rhythm
- **Ambient generators** — Bubbles, Rain, Crackles
- **Spectral** — Shepard's Pi (ever-rising pitch illusion), Bitgrunge (digital artifacts)
- **Chord** — four-voice chord oscillator
- **Rhythmic** — Euclid, Alternate (pattern-based amplitude)
- **Scale-aware** (6 types) — quantize output to selected scale

### Filter Types

Each engine has independent filters with diverse types:
- Low-pass, High-pass, Band-pass
- Phasers, Comb filters
- Vocal formant
- **Plate resonator** (scale-aware)
- **Membrane resonator** (scale-aware)

The plate and membrane resonators with "Play By Key" mode create pitched resonance that tracks the keyboard — unique to Meld among Ableton's synths.

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Oscillator Type** | Selects one of 24 algorithms per engine | Start with Basic, then explore FM and ambient types |
| **Macro 1 & 2** | Context-dependent (Shape/Tone, Amount/Ratio, etc.) | Modulate these — they define the oscillator's character |
| **LFO 1 FX 1/2** | Modulate LFO1's own shape for complex patterns | Creates compound modulation without extra LFOs |
| **LFO Speed** | Up to 200Hz (audio rate for FM effects) | Audio rate for timbral, slow for movement |
| **Cross-Engine Mod** | Engine A LFOs → Engine B parameters | Key to making both engines interact musically |
| **Mixer** | Blend and tone-shape engines A+B | Built-in limiter and drive for glue |
| **MPE Mapping** | Pressure, slide, per-note pitch to any target | Map pressure→filter cutoff for expressive playing |

### Sound Recipes

- **Textural Drone:** Engine A: Noise Loop osc, slow LFO→macros. Engine B: Bubbles osc, membrane resonator filter. Cross-mod Engine A LFO→Engine B filter.
- **Rhythmic Pad:** Engine A: Euclid osc for rhythmic amplitude. Engine B: Basic osc for tone. Blend 60/40.
- **Digital Bass:** Engine A: Harmonic FM, high Amount, LP filter ~600Hz. Engine B off. Short envelope, mono mode.
- **Evolving Ambient:** Both engines on different ambient osc types (Rain + Shepard's Pi), slow cross-modulation, plate resonator filters, long release.
- **MPE Lead:** Engine A: Basic osc, map MPE slide→Macro 1 (Shape), pressure→filter cutoff. Mono/legato mode.

### Reach for This When

- You want sounds that don't come from conventional synthesis.
- Textural, ambient, experimental electronic music.
- MPE controller expression (Meld's MPE integration is the deepest of any Live synth).
- Rhythmic drones and evolving soundscapes.
- You want two independent timbres blended on one track.
- Scale-aware synthesis (oscillators and filters that respect musical scales).

### Don't Use When

- You want classic analog warmth (use Analog or Drift).
- You need precise FM control with carrier/modulator ratios (use Operator).
- You want straightforward subtractive synthesis (Meld's experimental nature can slow you down).
- Sample-based sounds (use Simpler/Sampler).

### vs Other Synths

- **vs Wavetable:** Wavetable has deeper wavetable morphing and unison; Meld has more diverse oscillator types and bi-timbral architecture.
- **vs Drift:** Opposite philosophies — Drift is familiar and immediate, Meld is exploratory and surprising.
- **vs Operator:** Both can do FM, but Operator gives you precise control of 4 operators, while Meld's FM is macro-level (Amount/Ratio knobs).

---

## Tension

- **Type:** Native (Suite)
- **Synthesis:** Physical modeling — stringed instruments
- **Character:** Organic, resonant, alive. Ranges from eerily realistic plucked/bowed strings to completely alien hybrid instruments. Always retains a physical, tactile quality even at extreme settings. Responds dynamically to velocity and playing style in a way synths don't.

### Signal Flow

```
Excitator (Bow / Hammer / Plectrum)
  ↓
String (vibrating element)
  ↓
Vibrato → Damper → Termination → Pickup → Body
  ↓
Filter (multimode) → LFO → Output

Additional: Unison, portamento, keyboard range settings
```

**Co-developed with Applied Acoustics Systems (AAS).**

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Excitator Type** | Bow (sustained), Hammer (struck), Plectrum (plucked) | Plectrum for guitar/harp; Bow for violin/cello; Hammer for piano/dulcimer |
| **Excitator Position** | Where on the string the excitation occurs | Near bridge = bright/thin; center = warm/fundamental |
| **Stiffness** | Mallet/plectrum hardness | Low = soft/muted; High = bright/metallic. Below 50% sounds weak |
| **Force/Velocity** | Impact intensity | Higher = more harmonics. Map to velocity for expression |
| **String Decay** | How long the string rings | Short for plucks (0.5-2s); Long for sustain (5-10s) |
| **String Damping** | High-frequency energy loss over time | Higher = duller, more natural decay |
| **String Ratio** | Affects harmonic overtone structure | Subtly changes the string's inharmonicity |
| **Damper Mass/Stiff** | Emulates felt (piano) or finger (guitar) damping | High mass = slow damping; High stiff = abrupt stop |
| **Damper Position** | Where damper contacts string | Near bridge = affects high harmonics first |
| **Body Type/Size** | Resonating chamber model | Small = bright, focused; Large = warm, boomy |
| **Body Decay** | How long body resonates | Longer = more sustained reverb-like tail |
| **Pickup Position** | Where the virtual mic is placed | Near bridge = bright; Near center = warm |
| **Vibrato Error** | Adds human variation to vibrato | 5-15% for realistic imperfection |
| **Termination** | End condition of string | Affects overtone pattern and sustain behavior |

### Sound Recipes

- **Acoustic Guitar:** Plectrum excitator, position 30%, stiffness 60%, medium string decay, body size medium, pickup position 40%.
- **Bowed Cello:** Bow excitator, low position (near bridge for sul ponticello, center for normal), large body, slow vibrato with slight error.
- **Piano:** Hammer excitator (from above), high stiffness, medium body, damper engaged (map sustain pedal to damper on/off).
- **Alien Harp:** Plectrum, extreme stiffness, small body, high inharmonicity, long decay. Unison 2-3 voices detuned.
- **Ambient Drone:** Bow excitator, very long string decay, large body, slow LFO on excitator position, vibrato with high error.

### Reach for This When

- Realistic or semi-realistic string instruments (guitar, violin, cello, harp, piano, clavinet, harpsichord).
- Organic, physical-sounding textures that respond naturally to playing dynamics.
- Cinematic scoring requiring acoustic-feeling instruments.
- Hybrid acoustic/electronic patches.
- You want sounds with inherent physicality — resonance, body, and natural decay.

### Don't Use When

- You need electronic/synthetic sounds (use any other synth).
- Mallet percussion (use Collision instead).
- Electric piano specifically (use Electric).
- Quick preset browsing — Tension requires understanding its parameters for best results.

### vs Other Synths

- **vs Collision:** Tension = strings (plucked, bowed, struck). Collision = membranes, plates, tubes (mallet percussion). Different physical models entirely.
- **vs Electric:** Electric specifically models electric pianos with pickups. Tension can approximate piano but Electric is more authentic for Rhodes/Wurli sounds.

**Warning:** Tension can produce unpredictable volume spikes. Always put a Limiter after it.

---

## Collision

- **Type:** Native (Suite)
- **Synthesis:** Physical modeling — mallet percussion and resonant objects
- **Character:** Metallic, wooden, crystalline, percussive. From realistic marimbas and vibraphones to otherworldly gamelan-like tones and abstract resonant sculptures. The resonators define the character far more than the exciters.

### Signal Flow

```
Mallet Excitator ──┐
                    ├─ Structure ─┐
Noise Excitator ───┘              │
                                  ├─ Resonator 1 ──┐
                                  │                 ├─ (Coupled or Parallel) → Output
                                  └─ Resonator 2 ──┘

LFO 1 → modulates resonator/excitator parameters
LFO 2 → modulates resonator/excitator parameters
```

**Co-developed with Applied Acoustics Systems (AAS).**

### Resonator Types

| Type | Character | Real-World Analog | Key Parameter |
|------|-----------|-------------------|---------------|
| **Beam** | Generic pitched tone, bright | Xylophone bars | Material slider |
| **Marimba** | Warm, woody, tuned overtones | Marimba bars specifically | Hit position, Material |
| **String** | Wire/gut-like resonance | Zither, dulcimer | Decay, Damping |
| **Membrane** | Drum-like, pitched | Drumheads, tom-toms | Material, Radius |
| **Plate** | Complex metallic, rich harmonics | Gongs, metal sheets | Ratio (width:length) |
| **Pipe** | Breathy, wind-like | Organ pipes, flutes | Opening (0 = closed, pitch bends) |
| **Tube** | Open resonance, hollow | Open cylinders | Opening, Radius |

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Mallet Stiffness** | Hardness of strike | Low (<25%) enhances noise; High = bright attack |
| **Mallet Noise** | Adds impact noise | 10-30% for realism; higher for experimental |
| **Noise Color** | HP filter on noise excitator | Higher = brighter, thinner noise component |
| **Material/Radius** | Most dramatic tonal control per resonator | Experiment widely — this defines the sound |
| **Brightness** | Spectral tilt | Positive = brighter; Negative = darker |
| **Inharmonics** | Overtone spacing | Low = pitched/tonal; High = metallic/dissonant |
| **Hit Position** | Where the resonator is struck | Center = fundamental; Edge = more overtones |
| **Decay** | Resonator ring time | Short for clicks; Long for sustain/drone |
| **Listening L/R** | Stereo mic placement on resonator | Spread apart for wide stereo image |
| **Coupled vs Parallel** | Resonator interaction mode | Coupled (1>2): resonators feed each other. Parallel: independent |

### Sound Recipes

- **Vibraphone:** Mallet stiffness ~60%, Beam resonator, Material center, moderate decay, slight LFO on pitch for vibrato.
- **Marimba:** Mallet stiffness ~40%, Marimba resonator, hit position ~35%, warm brightness setting.
- **Gamelan Bell:** Mallet stiffness 80%+, Plate resonator, high inharmonics, long decay, coupled with Tube resonator 2.
- **Abstract Percussion:** Noise excitator with short envelope, Membrane resonator, fast decay, Pipe resonator 2 in parallel.
- **Metallic Drone:** Plate resonator, very long decay, Noise excitator with slow attack/sustain, low stiffness, coupled mode.
- **Drum Kit Element:** Stiff mallet + Membrane resonator, 0% key tracking (fixed pitch), short decay + Pipe resonator for body.

### Reach for This When

- Mallet percussion: vibraphone, marimba, xylophone, glockenspiel, gamelan.
- Metallic, bell-like, or crystalline textures.
- Experimental percussion that doesn't exist in the real world.
- Cinematic metallic hits and impacts.
- You want sounds with natural resonance and decay characteristics.

### Don't Use When

- You need string instruments (use Tension).
- You want standard electronic synth sounds (use any other synth).
- Electric piano (use Electric).
- You need sustaining tones without natural decay (Collision always wants to ring and die).

### vs Other Synths

- **vs Tension:** Collision = struck/mallet instruments; Tension = string instruments. Complementary, not competing.
- **vs Operator:** Operator can produce bell-like FM tones but lacks the physical resonance character. Collision bells sound more real; Operator bells sound more synthetic.
- **vs Electric:** Electric specifically models electric pianos. Collision can approximate them but isn't designed for it.

---

## Electric

- **Type:** Native (Suite)
- **Synthesis:** Physical modeling — electric piano mechanism
- **Character:** Warm, bell-like, dynamic, expressive. Nails the Rhodes/Wurlitzer sound that sits perfectly in soul, neo-soul, jazz, R&B, lo-fi hip-hop. Velocity-sensitive in a way that feels natural — soft playing is mellow, hard playing adds bark and harmonics.

### Signal Flow

```
Mallet (hammer strikes tine)
  ↓
Fork:
  Tine (initial strike sound) + Tone Bar (resonating body)
  ↓
Damper (key release behavior)
  ↓
Pickup (R = electro-dynamic / W = electro-static)
  ↓
Global (volume, voices, tuning)
  ↓
Output
```

**Co-developed with Applied Acoustics Systems (AAS).**

### MKI vs MKII vs Wurlitzer

| Aspect | Rhodes MKI | Rhodes MKII | Wurlitzer |
|--------|-----------|------------|-----------|
| **Pickup Type** | R (electro-dynamic) | R (electro-dynamic) | W (electro-static) |
| **Character** | Warm, mellow, round | Brighter, more presence | Reedy, biting, dynamic |
| **Bark** | Subtle | More pronounced | Aggressive, distinctive |
| **Genre** | Jazz, soul, ambient | Funk, fusion, pop | Rock, soul, gospel |
| **Attack** | Soft bell-like | Crisper bell | Reed-like snap |

Select R or W pickup type to switch between Rhodes and Wurlitzer models. The entire instrument responds differently.

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Mallet Stiffness** | Hammer hardness | 50-70% for natural; >80% for metallic. Below 50% sounds weak |
| **Mallet Force** | Impact intensity → more harmonics | Map to velocity for expression. 60-80% range for most playing |
| **Mallet Noise** | Impact noise amount | 10-20% for subtle realism |
| **Tine Color** | Balance of high/low partials in strike | Center for balanced; High for bright attack |
| **Tine Decay** | How long tine vibration lasts | 50-70% for natural; shorter for clav-like |
| **Tine Level** | Strike component volume | Balance against Tone level |
| **Tone Decay** | How long resonating tone bar sustains | Higher = longer sustain; the "body" of the note |
| **Tone Level** | Resonance component volume | Higher = warmer, more body |
| **Pickup Symmetry** | Pickup alignment relative to tine | Off-center creates asymmetric distortion (classic Rhodes bark) |
| **Pickup Distance** | How close pickup is to tine | Closer = hotter signal, more harmonics/distortion |
| **Damper Tone/Level** | Character of key-release sound | Subtle but adds realism. Raise for audible damper click |

### Sound Recipes

- **Classic Rhodes (MKI):** R pickup, stiffness ~55%, force ~65%, Tine/Tone balanced, Symmetry centered, moderate distance. Add Tremolo effect for classic sound.
- **Bright Rhodes (MKII):** R pickup, stiffness ~70%, higher Tine Color, slightly closer pickup distance.
- **Wurlitzer Bark:** W pickup, stiffness ~65%, force ~70%, pickup distance close, add slight overdrive/amp simulation.
- **Lo-fi Keys:** R pickup, reduce stiffness to ~45%, increase Tone decay, add Vinyl Distortion or Redux after.
- **Clav-like:** R pickup, high stiffness (~85%), very short Tine/Tone decay, close pickup, bright tone color.

### Reach for This When

- Electric piano sounds — period. Rhodes MKI, MKII, Wurlitzer.
- Neo-soul, jazz, lo-fi hip-hop, R&B, gospel, funk keys.
- You want velocity-responsive keys that feel natural.
- The sound needs to sit in a band/ensemble context without processing.

### Don't Use When

- Acoustic piano (use a sample-based piano instrument).
- Organ sounds (use Operator in additive mode).
- You need synthesis beyond electric piano (Electric does ONE thing, but does it superbly).
- Synth keys / polysynth sounds (use Analog, Drift, or Wavetable).

### vs Other Synths

- **vs Operator:** Operator can approximate EP sounds via FM (Algorithm 5, DX7-style), but Electric's physical model is more authentic and velocity-responsive.
- **vs Tension:** Tension could theoretically model struck strings, but Electric is purpose-built for the EP mechanism and sounds better for this specific use case.
- **vs Collision:** Collision can make bell-like tones, but lacks the tine/pickup/damper specificity that makes Electric sound like a real electric piano.

---

## Simpler

- **Type:** Native (all editions)
- **Synthesis:** Sample playback with subtractive processing
- **Character:** Depends entirely on the loaded sample, but Simpler adds warmth through its filter, movement through its LFO, and shape through its envelope. The warping engine is unique — no other Ableton instrument time-stretches samples while playing them chromatically.

### Signal Flow

```
Sample (with start/end/loop points)
  ↓
Warp Engine (optional — pitch-independent playback)
  ↓
Filter (12 types)
  ↓
LFO → Filter / Pitch / Pan / Volume
  ↓
Amp Envelope (ADSR)
  ↓
Output
```

### Three Modes

| Mode | Behavior | Best For |
|------|----------|----------|
| **Classic** | Polyphonic, loopable, chromatic playback | Pads, leads, melodic instruments from samples |
| **1-Shot** | Monophonic, full sample playback every trigger, no loop | Drums, one-shots, stabs, risers |
| **Slice** | Chops sample into segments mapped to keys | Breakbeats, vocal chops, rhythmic sampling |

**Slicing methods:** Transient (auto-detect peaks), Beat (musical divisions), Region (equal segments), Manual (user-placed markers).

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Start/End** | Sample playback region | Trim silence; set loop points for Classic |
| **Loop Mode** | Off, Forward, Back-Forth | Forward for pads; Back-Forth for smoother loops |
| **Warp** | Pitch-independent time-stretch | ON for rhythmic material played chromatically |
| **Warp Mode** | Beats, Tones, Texture, Re-Pitch, Complex, Complex Pro | Tones for melodic; Texture for pads; Beats for drums |
| **Filter Type** | LP, HP, BP, Notch (12 types) | LP for warmth; BP for telephone effect |
| **Filter Freq** | Cutoff frequency | Modulate with LFO or envelope for movement |
| **LFO Rate** | Modulation speed | Sync to tempo for rhythmic effects |
| **LFO Destinations** | Filter, Pitch, Pan, Volume amounts | Filter 30-50% for subtle wobble; Pitch for vibrato |
| **Voices** | Polyphony limit | 1 for mono bass; 6-8 for pads; 1 for drums |
| **Fade** | Crossfade at loop/slice boundaries | Increase to eliminate clicks |

### Sound Recipes

- **Sampled Pad:** Classic mode, loop a sustaining portion, LP filter ~3kHz, slow LFO→filter, long attack/release.
- **Drum One-Shot:** 1-Shot mode, trim sample tight, no filter, short or no envelope.
- **Chopped Break:** Slice mode, Transient detection, map to pads, rearrange via MIDI.
- **Textural Instrument:** Classic mode, Warp on (Texture mode), loop a noise/texture sample, play chromatically, LP filter + LFO.
- **Lo-fi Bass:** Classic mode, mono, LP filter ~800Hz, sample a bass note, Re-Pitch warp mode for classic sampler feel.

### Reach for This When

- Quick sample playback and manipulation.
- Drum programming (1-Shot mode in Drum Rack cells).
- Chopping breaks and vocal samples (Slice mode).
- Turning any sample into a playable instrument quickly.
- You need warped/time-stretched chromatic sample playback (unique to Simpler).

### Don't Use When

- You need velocity layers or multiple samples mapped across the keyboard (use Sampler).
- Complex modulation routing (Sampler has a full mod matrix).
- You need more than one filter or advanced sample manipulation.
- Building a realistic multi-sampled instrument (Sampler with zones).

### vs Other Synths

- **vs Sampler:** Simpler is fast and focused (one sample). Sampler is deep (unlimited zones, mod matrix, filter morphing). Use Simpler for 90% of sampling tasks; Sampler when you need multisampling or complex modulation.
- **vs Drum Rack:** Drum Rack is a container that holds Simplers (or other instruments) per pad. Use Simpler inside Drum Rack for drum kits.

---

## Sampler

- **Type:** Native (Suite)
- **Synthesis:** Advanced sample playback with multisampling, modulation, and filter morphing
- **Character:** As varied as the samples loaded, but Sampler's processing adds a layer of sophistication — morphing filters create smooth timbral transitions, the mod matrix enables complex parameter interactions, and velocity/key zones produce instruments that respond realistically to playing.

### Signal Flow

```
Sample Zones (Key / Velocity / Sample Select / Chain)
  ↓
Modulation Oscillator (FM or AM on samples — optional)
  ↓
Filter 1 (16+ types including Morph)
  ↓
Filter 2 (optional, serial or parallel)
  ↓
Amp Envelope
  ↓
Output

Modulation:
  3 LFOs → any parameter
  Amp Envelope + Filter Envelope + Aux Envelope
  Mod Matrix: comprehensive source→destination routing
```

### Zone Editor

| Zone Type | What It Does | Use Case |
|-----------|-------------|----------|
| **Key Zone** | Maps samples across keyboard range | Multi-sampled instruments (piano, guitar) |
| **Velocity Zone** | Layers samples by velocity | pp/mf/ff dynamic layers |
| **Sample Select** | Switches samples via MIDI CC or mod | Round-robin, texture switching |
| **Chain** | Legacy zone type for compatibility | Rarely used directly |

Zones support **crossfades** at boundaries for smooth transitions between layers.

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Zone Crossfade** | Smooth transitions between samples | 10-20% overlap for natural velocity response |
| **Morph Filter** | Single knob sweeps LP→BP→HP→Notch | Modulate with LFO or envelope for dramatic sweeps |
| **Filter Drive/Morph** | Drive becomes Morph knob on Morph filter type | Automate for evolving filter character |
| **Mod Oscillator** | FM or AM applied to samples | FM for metallic enrichment; AM for tremolo |
| **Mod Osc Frequency** | Modulation oscillator pitch | Integer ratios for harmonic; non-integer for inharmonic |
| **Aux Envelope** | Third envelope for flexible modulation | Route to sample start, loop position, or filter |
| **LFO 1/2/3** | Three independent LFOs with full waveform options | One to filter, one to pitch (vibrato), one to pan |
| **Mod Matrix** | Route any source to any destination | Velocity→filter cutoff is essential for expression |
| **Sample Start Mod** | Modulate where sample playback begins | Map to velocity for "harder = later start" effect |
| **Loop Position Mod** | Modulate loop window | Creates granular-like movement within loops |

### Sound Recipes

- **Multi-Sampled Piano:** Key zones every 3-4 semitones, velocity zones for pp/mf/ff, crossfades 15%, subtle LP filter ~8kHz, velocity→filter cutoff.
- **Morphing Pad:** Load atmospheric samples, Morph filter, LFO1→Morph amount, slow rate, Aux envelope→loop position for movement.
- **FM-Enhanced Texture:** Load any sample, enable Mod Oscillator in FM mode, low amount, modulate Mod Osc frequency with LFO for evolving harmonics.
- **Expressive Lead:** Velocity zones with soft/hard articulations, mod matrix: velocity→filter cutoff + attack time, aftertouch→vibrato depth.
- **Granular-ish Texture:** Short loop, modulate loop start/length with LFOs at different rates, Morph filter with envelope.

### Reach for This When

- Building realistic multi-sampled instruments (the zone editor is essential).
- You need velocity layers, round-robin, or key-split instruments.
- Advanced sample modulation (FM/AM on samples, morph filter, full mod matrix).
- Complex instruments that respond dynamically to playing nuance.
- Filter morphing (LP→BP→HP in one sweep) is desired.

### Don't Use When

- Simple one-shot playback (Simpler is faster).
- You need time-stretching/warping (Simpler has Warp; Sampler does not).
- Quick chopping/slicing (Simpler's Slice mode).
- Drum hits in a Drum Rack (Simpler is lighter and sufficient).

### vs Other Synths

- **vs Simpler:** Sampler is Simpler's big sibling. Everything Simpler does, Sampler does with more depth — except Warp mode (Simpler only). Right-click Simpler → "Simpler → Sampler" to upgrade.
- **vs Operator:** Both can create instruments from scratch, but Operator synthesizes while Sampler manipulates recordings. Sampler's FM mod oscillator can add synthetic character to samples.

---

## Impulse

- **Type:** Native (all editions)
- **Synthesis:** Sample-based drum machine with per-slot processing
- **Character:** Immediate, punchy, purpose-built for drums. Less flexible than Drum Rack but faster to set up and lighter on CPU. Has a specific "drum machine" feel with its fixed 8-slot layout and per-slot saturation/filtering.

### Signal Flow

```
8 Sample Slots (mapped to keyboard C3-C4)
  ↓ (per slot)
Start Position → Transpose (±48st) → Stretch
  ↓
Filter (per slot, multiple types)
  ↓
Saturator (per slot, with Drive)
  ↓
Envelope (Trigger or Gate mode with Decay)
  ↓
Pan → Volume
  ↓
Master Output

Modulation: Velocity and Random can modulate most per-slot parameters.
```

### Key Parameters

| Parameter | What It Does | Sweet Spot |
|-----------|-------------|------------|
| **Start** | Sample playback start point | Trim attack transient for different feel |
| **Transpose** | Pitch shift ±48 semitones | Tune kicks/snares to song key |
| **Stretch** | Time-stretch with 2 algorithms | Stretch for longer/shorter hits without pitch change |
| **Filter Type** | Per-slot filtering | LP for boomy kicks; HP to thin hi-hats |
| **Filter Freq** | Cutoff frequency | Shape each drum independently |
| **Saturator Drive** | Per-slot distortion/saturation | 10-30% for warmth; 50%+ for crunch |
| **Decay Mode** | Trigger (fixed length) vs Gate (held) | Trigger for consistent drums; Gate for expressive rolls |
| **Decay Time** | How long the hit rings | Short for tight; Long for roomy |
| **Velocity→Volume** | Velocity sensitivity per slot | Higher for hi-hats/snare expression; Lower for consistent kick |
| **Random** | Adds random variation to parameters | 5-15% for humanized feel |
| **Slot 8→7 Link** | Slot 8 silences slot 7 | Classic open/closed hi-hat choke behavior |

### Sound Recipes

- **Basic Kit:** Kick in slot 1, snare in slot 3, closed hat in slot 7, open hat in slot 8 (linked), toms in 4-6, percussion in 2.
- **Saturated Boom Bap:** Drive up on kick (40%), snare filter LP ~4kHz, reduce hi-hat decay, increase random 10%.
- **Electronic Kit:** Transpose kicks down -5st, stretch snares longer, heavy filter on all slots, drive for character.
- **Lo-fi Drums:** Reduce all filter frequencies, moderate drive on everything, increase decay randomization.

### Reach for This When

- Quick 8-piece drum kit setup.
- You want per-slot processing without the overhead of Drum Rack chains.
- Light CPU usage matters.
- Simple drum programming with velocity/random humanization.
- The 8-slot constraint is sufficient (most kits don't need more).

### Don't Use When

- You need more than 8 drum sounds (use Drum Rack — 128 slots).
- You want per-slot effects chains (Drum Rack has device chains per pad).
- You need sample layering per hit (Drum Rack can stack instruments per pad).
- You want to use synth-generated drums (load Operator/Analog in Drum Rack instead).
- You need individual track outputs per drum (Drum Rack supports this natively).

### Impulse vs Drum Rack

| Aspect | Impulse | Drum Rack |
|--------|---------|-----------|
| **Slots** | 8 | 128 |
| **Per-slot effects** | Built-in filter + saturator only | Full device chain per pad |
| **Per-slot instruments** | Samples only | Any instrument (Simpler, Operator, etc.) |
| **CPU** | Very light | Can be heavy with full chains |
| **Time stretch** | Yes (unique feature) | No (Simpler inside Drum Rack lacks stretch) |
| **Setup speed** | Very fast | Slower, more configuration |
| **Individual outputs** | No | Yes |
| **Choke groups** | Slot 8→7 only | Configurable any-to-any |
| **Use case** | Quick sketches, simple kits | Full production drum design |

---

## Quick Decision Matrix

### "I want [sound type]" → use [synth]

| I Want... | First Choice | Second Choice | Why |
|-----------|-------------|---------------|-----|
| **Warm analog bass** | Drift | Analog | Drift is faster; Analog for complex routing |
| **Acid bass/lead** | Analog | Drift | Analog's dual filters + drive nail the acid sound |
| **FM electric piano** | Electric | Operator | Electric is purpose-built; Operator for DX7 style |
| **Metallic bells/chimes** | Collision | Operator | Collision for physical resonance; Operator for synthetic |
| **Evolving pad** | Wavetable | Analog | Wavetable position morphing is unmatched for evolution |
| **Warm analog pad** | Analog | Drift | Analog's PWM + dual filters = classic pad |
| **Aggressive digital bass** | Wavetable | Operator | Wavetable Modern mode (Fold/Warp) for grit |
| **Plucked string** | Tension | Collision | Tension for realistic; Collision for metallic pluck |
| **Bowed instrument** | Tension | — | Only Tension models bowing |
| **Marimba/vibraphone** | Collision | — | Purpose-built for mallet percussion |
| **Rhodes/Wurlitzer** | Electric | Operator | Electric for authentic; Operator for FM approximation |
| **Supersaw lead** | Wavetable | Analog | Wavetable unison is deeper; Analog is warmer |
| **Textural drone** | Meld | Wavetable | Meld's experimental oscs; Wavetable for morphing |
| **Lo-fi keys** | Drift | Electric | Drift for synth keys; Electric for piano keys |
| **Drum synthesis** | Operator | Collision | Operator for kicks/snares; Collision for metallic perc |
| **Sample playback** | Simpler | Sampler | Simpler for quick; Sampler for multi-zone |
| **Breakbeat chopping** | Simpler (Slice) | — | Slice mode is purpose-built |
| **Multi-sampled instrument** | Sampler | — | Zone editor is essential |
| **Quick drum kit** | Impulse | Drum Rack | Impulse for speed; Drum Rack for depth |
| **MPE expression** | Meld | Drift | Meld deepest MPE; Drift also supports it |
| **Ambient/experimental** | Meld | Wavetable | Meld for weird; Wavetable for lush |
| **Organ** | Operator | — | Algorithm 11 (additive) with drawbar-style harmonics |
| **Cinematic impact** | Collision | Tension | Collision for metallic hits; Tension for string stabs |
| **Generative/random** | Drift | Meld | Drift's per-voice randomization; Meld's rhythmic oscs |
| **Chip-tune/8-bit** | Meld | Operator | Meld's Bitgrunge osc; Operator with square waves |
| **Noise/texture** | Meld | Wavetable | Meld's Rain/Crackles/Bubbles oscs |

### By Genre

| Genre | Primary Synths | Why |
|-------|---------------|-----|
| **House/Techno** | Analog, Drift, Operator | Classic subtractive + FM stabs |
| **Ambient/Cinematic** | Meld, Wavetable, Tension | Evolving textures, physical resonance |
| **Hip-Hop/Trap** | Operator, Wavetable, Simpler | 808 bass synthesis, sample chopping |
| **Neo-Soul/R&B** | Electric, Drift, Analog | Rhodes keys, warm pads |
| **EDM/Future Bass** | Wavetable, Operator | Supersaws, FM bass, complex leads |
| **Lo-fi** | Drift, Electric, Simpler | Warm imperfection, vinyl-quality keys |
| **Jazz** | Electric, Tension, Analog | Piano, strings, warm synth |
| **Synthwave/Retro** | Analog, Drift | Vintage analog character |
| **Experimental** | Meld, Collision, Operator | Unusual timbres, physical modeling |
| **Drum & Bass** | Operator, Simpler, Analog | Bass synthesis, break chopping, reese bass |
| **Film Scoring** | Tension, Collision, Meld, Wavetable | Orchestral modeling, metallic textures, pads |

### By CPU Budget

| Budget | Recommended | Avoid |
|--------|------------|-------|
| **Minimal** | Drift, Simpler, Impulse | Wavetable (high unison), Collision (high quality) |
| **Normal** | All instruments work fine | — |
| **Unlimited** | Wavetable (max unison), Collision (High quality), Sampler (large multisample) | — |

---

*Reference compiled for LivePilot agent. Sonic descriptions based on Ableton Live 12 documentation, Sound On Sound reviews, and community sound design knowledge.*

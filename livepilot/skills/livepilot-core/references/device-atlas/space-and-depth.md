# Space & Depth — Device Atlas

> Reverbs, delays, resonators, spatial processors, and spectral effects in Ableton Live 12.
> Use this reference to choose, configure, and chain space/depth devices via LivePilot.

---

## Native Devices

---

### Reverb

- **Type:** Native
- **Load via:** `find_and_load_device("Reverb")`
- **What it does:** Algorithmic reverb with separate early-reflections and diffusion-network stages. Warm, slightly dark character; good general-purpose verb that sits well in a mix without eating headroom. Not the most realistic room sim, but flexible and low-CPU.
- **Signal flow:** Input → Lo/Hi Cut filters → Early Reflections (with Spin modulation) → Diffusion Network (with Chorus modulation) → Reflect/Diffuse level mix → Dry/Wet output
- **Key parameters:**
  - **Pre Delay** (0.5 -- 250 ms) → separation between dry transient and first reflection → 10--25 ms for natural rooms, 50--80 ms for vocals, 0 for pads
  - **Size** → perceived room volume → small (< 30) for tight spaces, 50--80 for rooms, > 100 for halls
  - **Decay Time** (200 ms -- 60 s) → tail length → 1--2 s for mix glue, 3--6 s for ambient, > 10 s for drones
  - **Lo Cut / Hi Cut** → input filtering before reverb → Hi Cut 4--6 kHz tames sibilance; Lo Cut 200--400 Hz keeps mud out
  - **Reflect** → early reflections level → 30--60% for presence, lower for smoother wash
  - **Diffuse** → diffusion network level → 60--100% for lush tail
  - **Shape** → blend between early reflections and tail → low = gap between ER and tail (more defined), high = smooth continuous verb
  - **Spin** (X-Y: Amount + Rate) → modulates early reflections for movement → subtle amounts (< 30%) prevent metallic artifacts
  - **Chorus** (X-Y: Amount + Rate) → modulates diffusion network → adds shimmer and width; keep < 40% for natural sound
  - **Density / Scale** → reflection density in diffusion → higher = denser cloud, more noticeable at small Size
  - **Freeze** → infinite sustain → toggle Cut to stop new input; Flat to bypass shelf filters during freeze
  - **Hi Shelf / Lo Shelf** (in Diffusion) → frequency-dependent decay → cut highs for darker tail, cut lows for thinner tail
  - **Stereo** (0 -- 120%) → output stereo width → 0% = mono, 60--80% for focused placement, 120% for wide wash
  - **Quality** → Eco / Mid / High → Eco has lo-fi charm, High for final mix
  - **Dry/Wet** → 15--25% on inserts, 100% on sends
- **Presets:** "Large Hall" (ambient starting point), "Drum Room" (tight), "Vocal Plate" (bright mid-range shimmer)
- **Reach for this when:** you need a simple, CPU-friendly reverb that blends into the mix; quick vocal or drum room; lo-fi aesthetic on Eco quality
- **Don't use when:** you need realistic acoustic spaces (use Hybrid Reverb with IR), you need shimmer/pitch-shifted tails, or you want spectral effects
- **Pairs well with:** EQ Eight (post-verb high cut), Compressor (sidechain ducking the verb), Chorus-Ensemble (pre-verb width)
- **vs Hybrid Reverb:** Reverb is simpler, lighter on CPU, more vintage-digital character. Hybrid Reverb wins on realism (convolution) and creative algorithms (Shimmer, Tides).

---

### Hybrid Reverb

- **Type:** Native (Live 11+, Suite only)
- **Load via:** `find_and_load_device("Hybrid Reverb")`
- **What it does:** Dual-engine reverb combining a convolution engine (real-space IRs) with an algorithmic engine (5 creative algorithms). Can run engines independently, in serial, or in parallel. The most versatile reverb in Live.
- **Signal flow:** Input → Send gain → Convolution Engine + Algorithmic Engine (routed Serial/Parallel/Blend) → 4-band EQ → Stereo / Vintage / Bass Mono → Dry/Wet output
- **Key parameters:**
  - **Convolution Engine:**
    - **IR Browser** → select from built-in categories or drag-drop custom audio files
    - **Attack** → fade-in of IR → increase to remove early transient of IR
    - **Decay** → fade-out envelope → shorter = tighter space
    - **Size** → time-stretch the IR → < 100% compresses, > 100% stretches
  - **Algorithmic Engine (5 algorithms):**
    - **Dark Hall** → lush, warm, long-tail hall → the "set and forget" natural reverb
    - **Quartz** → crystalline, bright, defined → turn Diffusion to 0 for a multitap delay effect
    - **Shimmer** → pitch-shifted reverb tail → ethereal pads, post-rock guitars; Shift parameter sets pitch interval
    - **Tides** → modulated reverb with swelling movement → organic, evolving textures; Mod Rate/Depth control the swell
    - **Prism** → bright, dispersive, spectral → colorful and synthetic; good for sound design
    - *Shared params:* Decay, Size, Delay (pre-delay for algo section), Freeze, Freeze In, Diffusion, Damping
  - **Routing:** Serial (conv → algo) / Parallel / Blend knob between engines
  - **EQ Section:** 4 bands — low/high toggleable between pass filters (6--96 dB/oct slopes) and shelving EQs; 2 mid peak EQs
  - **Vintage** → emulates lower sample rates, re-pitches frozen tails for tape-loop effects
  - **Stereo** → output width
  - **Bass Mono** → collapses low frequencies to mono → essential for club/festival mixes
  - **Dry/Wet** → 20--30% insert, 100% on send
- **Presets:** "Bright Hall" (clean starting point), "Shimmer Verb" (ethereal), "Dark Plate" (warm vocal), "Frozen Landscape" (drone/texture)
- **Reach for this when:** you need realistic spaces (load real room IRs), creative tails (Shimmer, Tides), or a single device that replaces multiple reverbs
- **Don't use when:** CPU is tight (convolution is heavier than Reverb), you only need a quick simple verb
- **Pairs well with:** Spectral Time (freeze into spectral delay), Auto Filter (movement on send), Utility (Bass Mono if not using built-in)
- **vs Reverb:** Hybrid Reverb is more versatile and realistic but heavier on CPU. Use Reverb for quick/light tasks, Hybrid Reverb for hero sounds.

---

### Delay

- **Type:** Native (updated in Live 12)
- **Load via:** `find_and_load_device("Delay")`
- **What it does:** Clean stereo delay with tempo sync, band-pass filter, LFO modulation, and three transition modes. The workhorse delay — transparent, precise, and flexible.
- **Signal flow:** Input → Band-pass filter → Dual delay lines (L/R, linkable) → LFO modulation (filter + time) → Ping Pong option → Dry/Wet output
- **Key parameters:**
  - **Sync** (on/off) → tempo-synced divisions or free ms (1--300 ms)
  - **Delay Time L/R** → synced: 1 = 16th, 2 = 8th, 3 = dotted 8th, 4 = quarter; free: milliseconds
  - **Stereo Link** → locks L/R to same time
  - **Offset** (+/- 33%) → swing/triplet feel on delay taps
  - **Feedback** → repeat count → 0% = single echo, 50--70% = rhythmic repeats, > 90% = builds up
  - **Filter** (X-Y: Frequency + Bandwidth) → band-pass on delay line → drag left = remove highs, right = remove lows; narrow bandwidth for telephone/radio effect
  - **LFO Rate** (Hz) → modulation speed → slow (0.1--0.5 Hz) for gentle chorus, fast (2--8 Hz) for warble
  - **LFO → Filter** → modulation depth on filter frequency
  - **LFO → Time** → modulation depth on delay time → creates pitch wobble
  - **Transition Mode:**
    - **Repitch** → tape-like pitch shift when changing delay time → classic dub behavior
    - **Fade** → crossfade between old/new time → smooth, no pitch artifacts
    - **Jump** → instant switch → hard cuts, glitchy
  - **Ping Pong** → alternates L/R → great stereo spread
  - **Freeze** → infinite loop of current buffer
  - **Dry/Wet** → 20--35% for subtle depth, 50% for obvious echo, 100% on send
- **Presets:** "Dotted Eighth" (standard guitar delay), "Ping Pong Eighth" (stereo bounce), "Slapback" (rockabilly)
- **Reach for this when:** you need a clean, transparent delay; rhythmic echoes; slapback; basic stereo widening
- **Don't use when:** you want character/color (use Echo), filtered multi-band delay (use Filter Delay), or granular textures (use Grain Delay)
- **Pairs well with:** EQ Eight (darken repeats on send), Auto Pan (after Ping Pong for rhythmic movement), Saturator (warm up feedback)
- **vs Echo:** Delay is cleaner and simpler. Echo adds noise, wobble, gate, ducking, reverb, and modulation character. Use Delay for transparent utility, Echo for vibe.

---

### Echo

- **Type:** Native (Live 10+)
- **Load via:** `find_and_load_device("Echo")`
- **What it does:** Character delay with deep modulation, noise/wobble for analog flavor, built-in reverb, gate, and ducking. Ableton's most feature-rich delay — it can go from subtle tape echo to self-oscillating chaos.
- **Signal flow:** Input (with optional distortion) → Dual delay lines (L/R or Mid/Side) → HP/LP filters with resonance → LFO/Envelope modulation → Character processing (Noise, Wobble, Gate, Ducking) → Reverb (Pre/Post/Feedback) → Stereo/Output → Dry/Wet
- **Key parameters:**
  - **Channel Mode:** Stereo / Ping Pong / Mid/Side
  - **Delay Time L/R** → Notes, Triplet, Dotted, 16th divisions or free ms
  - **Offset** (+/- 33%) → swing timing
  - **Input** → drive into delay → overdrives for saturation
  - **D button** → determines if dry signal passes through Input gain
  - **Feedback** → echo regeneration → > 100% with phase invert (O button) creates interesting cancellations
  - **HP / LP Filters** → shape echo tone → with resonance for emphasis → sweet spot: HP 200--500 Hz, LP 3--6 kHz for vintage
  - **Modulation Tab:**
    - **LFO Waveforms:** Sine, Triangle, Saw Up, Saw Down, Square, Noise
    - **Rate** (Hz or synced) → modulation speed
    - **Phase** (0--360 deg) → L/R offset → 180 deg for maximum stereo movement
    - **Mod Delay** → LFO depth on delay time → subtle chorus to wild pitch
    - **Mod Filter** → LFO depth on filter → auto-wah on echoes
    - **x4** → multiplies delay mod depth by 4 → deep flanging at short delay times
    - **Env Mix** → crossfade LFO vs Envelope Follower → 100% = envelope only
  - **Character Tab:**
    - **Gate** → threshold + release → silences echo below threshold → rhythmic gating
    - **Ducking** → threshold + release → reduces wet signal when input is present → clean-playing, echoey tails
    - **Noise** → analog noise amount + Morph → lo-fi character
    - **Wobble** → irregular delay time modulation → tape machine instability
    - **Repitch** → pitch shifts delays when time changes during playback
  - **Reverb** → amount + Decay → placement: Pre (before delay), Post (after delay), Feedback (inside feedback loop — builds up dramatically)
  - **Stereo** → output width (same as Utility Width)
  - **Dry/Wet** → 25--40% insert, 100% send
- **Presets:** "Analog Echo" (warm tape), "Space Echo" (dub classic), "Ducking Delay" (mix-friendly), "Infinite Rise" (feedback chaos)
- **Reach for this when:** you want delay with personality — dub, tape echo, lo-fi, rhythmic gated delay, self-oscillating feedback; when you need built-in reverb on the delay
- **Don't use when:** you need a clean transparent delay (use Delay), or independent multi-band delays (use Filter Delay)
- **Pairs well with:** Auto Filter (before Echo for vowel-like echoes), Utility (mid/side processing post-Echo), Beat Repeat (rhythmic source into Echo)
- **vs Delay:** Echo has far more character and creative potential. Delay is cleaner and simpler. Echo's Ducking alone makes it indispensable for mixing.

---

### Filter Delay

- **Type:** Native
- **Load via:** `find_and_load_device("Filter Delay")`
- **What it does:** Three independent filtered delay lines — one for Left input, one for Right input, one for L+R (stereo sum). Each line has its own band-pass filter, delay time, feedback, pan, and volume. Creates rich, frequency-separated delay textures.
- **Signal flow:** Input splits into 3 channels (L / L+R / R) → per-channel Band-pass Filter → per-channel Delay Line → per-channel Pan/Volume → Feedback routing (Individual or Sum) → Output mix
- **Key parameters:**
  - **3 Channel Toggles** → enable/disable each delay line independently
  - **Per-channel Filter** (Frequency + Width) → band-pass isolates frequency range for that delay → narrow band = telephone, wide = subtle shaping
  - **Global Frequency** → ties all 3 filters together for unified sweeps
  - **Per-channel Delay Time** → grid base (16th, dotted 16th, 16th triplet, 32nd) x multiplier (1--32)
  - **Global Delay Time** → offsets all 3 delay times together
  - **Per-channel Pan** → output panning → values > 50 or < -50 fold with inverted phase; 99/-99 = center with 180-degree phase inversion
  - **Per-channel Volume** → individual delay level
  - **Feedback** (single shared control) → regeneration for all lines
  - **Feedback Routing:** Individual (each line feeds itself) or Sum (all outputs feed all inputs — complex, dense patterns)
  - **Channel Swap** → per-line L/R output swap (affects feedback too)
  - **Dry/Wet** → 20--40% insert, 100% send
- **Presets:** "Filtered Echoes" (separated frequency delays), "Stereo Spread" (wide panoramic)
- **Reach for this when:** you want different delay times for different frequency ranges (e.g., fast highs, slow lows); stereo-separated delay textures; dub-style filtered echoes; pseudo room simulation (1--25 ms, low feedback)
- **Don't use when:** you want a single clean delay (use Delay), or need modulation/character (use Echo)
- **Pairs well with:** Auto Filter (movement on the filters), Reverb (post for space), Utility (mono check the phase tricks)
- **vs Delay:** Filter Delay is more complex with 3 independent lines and frequency separation. Delay is simpler but has LFO modulation and transition modes that Filter Delay lacks.

---

### Grain Delay

- **Type:** Native
- **Load via:** `find_and_load_device("Grain Delay")`
- **What it does:** Granular delay that chops incoming audio into tiny grains, applies pitch shifting and randomization, then delays the grains. Creates textures ranging from subtle shimmer to total sonic destruction.
- **Signal flow:** Input → Grain slicing (at Frequency rate) → Pitch shift per grain → Spray (time randomization) + Random Pitch → Delay line with Feedback → Dry/Wet output
- **Key parameters:**
  - **Delay Time** → synced (note values) or free (ms) → 1 ms for pure pitch-shifting without audible delay; 25--30 ms for musical delay
  - **Frequency** (Hz) → grain rate / grains per second → higher = smaller grains, more artifacts; lower = larger grains, more stable → sweet spot: 20--60 Hz for stable pitch shifting, > 100 Hz for glitchy textures
  - **Pitch** (semitones, supports decimals) → transpose grains → +12 or -12 for octave shimmer; +7 for fifth; small values (0.1--0.5) for subtle detuning/chorus
  - **Spray** (ms) → random delay time variation per grain → 0 = clean, 1--5 ms = subtle smear, > 50 ms = rhythmic chaos → adds noisiness at low values, breaks structure at high values
  - **Random Pitch** → random pitch offset per grain → 0 = clean, 10--30 = mutant chorus, > 60 = unintelligible pitch
  - **Feedback** → 0% = single pass, 30% for playable shimmer, 60% for phaser/flanger-like buildup, > 90% for cascading pitch spirals
  - **Dry/Wet** → 30--50% for texture layering, 100% for full effect on send
- **Presets:** "Shimmer" (octave up, low spray), "Granular Wash" (heavy spray + random), "Pitch Cascade" (feedback + pitch shift)
- **Reach for this when:** you want shimmer/octave effects, granular textures, pitch-shifted delays, subtle detuning/chorus, or total sound destruction
- **Don't use when:** you need clean transparent delay (use Delay), precise rhythmic repeats, or convolution-quality spaces
- **Pairs well with:** Reverb (post for ethereal wash), Auto Filter (pre for frequency-focused granulation), Compressor (tame wild dynamics), Corpus (resonant body on grains)
- **vs Spectral Resonator:** Grain Delay works in time domain (actual grain slicing); Spectral Resonator works in frequency domain (FFT partials). Grain Delay is more destructive and textural; Spectral Resonator is more melodic and harmonic.

---

### Beat Repeat

- **Type:** Native
- **Load via:** `find_and_load_device("Beat Repeat")`
- **What it does:** Rhythmic buffer repeat/stutter effect synchronized to song tempo. Captures audio slices and repeats them with optional pitch decay and filtering. Not a traditional delay — it is a performance/glitch tool.
- **Signal flow:** Input → Buffer capture (at Interval + Offset) → Grid slicing → Repetition (for Gate length) → Pitch processing → Filter → Mix mode output
- **Key parameters:**
  - **Interval** (1/32 to 4 Bars) → how often new material is captured → 1 Bar for periodic glitches, 1/4 for frequent stutters
  - **Offset** (16th note steps) → shifts capture point within Interval → e.g., Interval 1 Bar + Offset 8/16 = capture on beat 3
  - **Gate** (16th note steps) → total length of repetitions → 2/16 for short burst, 8/16 for full bar stutter
  - **Grid** (note values) → size of each repeated slice → 1/8 for rhythmic loops, 1/16 for faster stutter, 1/32 for buzz/roll
  - **Variation** → random grid size fluctuation → 0 = fixed, higher = unpredictable grid sizes
  - **Variation Mode:** Trigger (new random per interval), 1/4, 1/8, 1/16, Auto
  - **Chance** (0--100%) → probability of repetitions occurring → 50% for intermittent glitches, 100% for guaranteed
  - **Repeat** (button) → bypasses all timing, immediately captures and repeats until released → performance tool
  - **Pitch** → resampling-based pitch reduction per repeat → negative values = each repeat drops pitch
  - **Pitch Decay** → progressive pitch lowering across repetitions → DJ brake/tape-stop effect
  - **Filter** (center frequency + width) → HP/LP on repeated material
  - **Volume / Decay** → amplitude envelope on repetitions
  - **Mix Mode:** Mix (original + repeats), Insert (mutes original during repeats), Gate (only repeats, no original)
  - **Dry/Wet** → when using Mix mode
- **Presets:** "Basic Stutter" (1/16 grid), "Tape Brake" (pitch decay), "Random Glitch" (high variation + chance)
- **Reach for this when:** you need stutter/glitch effects, DJ-style brake downs, rhythmic repetition, live performance tools, build-ups and transitions
- **Don't use when:** you need smooth delay/reverb, sustained tails, or subtle spatial effects
- **Pairs well with:** Echo (feed stutters into delay), Auto Filter (sweep filter on repeats), Redux (bit-crushing the repeats), Gate (sidechain for rhythmic ducking)
- **vs Gated Delay:** Beat Repeat captures and replays audio buffer. Gated Delay sends existing signal to a delay line rhythmically. Beat Repeat is more destructive; Gated Delay is more musical.

---

### Corpus

- **Type:** Native
- **Load via:** `find_and_load_device("Corpus")`
- **What it does:** Physical modeling resonator that simulates vibrating objects (beams, strings, membranes, plates, pipes, tubes). Excites the audio input through a modeled resonant body. Adds pitched, metallic, or woody resonance to any sound.
- **Signal flow:** Input → Band-pass Filter → Resonance Type modeling → LFO modulation on frequency → Bleed mix → Gain/Limiter → Dry/Wet output. Optional MIDI sidechain controls pitch.
- **Key parameters:**
  - **Resonance Type:** Beam, Marimba, String, Membrane, Plate, Pipe, Tube → each has distinct overtone structure
  - **Quality:** Eco / Mid / High → overtone richness vs CPU
  - **Tune** (Hz) → resonant frequency → sets the "note" of the resonant body
  - **Fine** (cents) → fine tuning for MIDI mode
  - **Spread** → detunes L/R resonators → positive = L up / R down; creates stereo width
  - **Decay** → resonance sustain time → short for percussive ping, long for sustained tone
  - **Material / Radius** → tonal character → affects overtone brightness and distribution
  - **Bright** → high-frequency content of resonance
  - **Inharmonics (Inharm)** → detune overtones from harmonic series → 0 = pure, higher = bell-like/metallic
  - **Hit** → excitation point on the body → changes overtone emphasis
  - **Ratio** (Membrane/Plate only) → aspect ratio of the surface
  - **Opening** (Pipe only) → how open the far end is → affects tube resonance character
  - **Width** → stereo spread of output
  - **Pos. L / Pos. R** → listening position on the resonant body
  - **LFO:** Amount, Rate (Hz or synced), Waveform, Phase/Spin, Offset → modulates resonant frequency
  - **Filter:** Band-pass toggle, Frequency, Bandwidth → shapes input before resonator
  - **Bleed** → amount of dry signal bypassing the resonator
  - **MIDI Sidechain:** Frequency on/off, Note priority (Last/Low), Transpose, PB Range, Off Decay → external MIDI controls resonator pitch
  - **Dry/Wet** → 30--60% for subtle body, 100% for full resonator effect
- **Presets:** "Metallic Body" (Plate, bright), "Wooden Marimba" (Marimba type), "Droning Pipe" (Pipe, long decay)
- **Reach for this when:** you want to add pitched resonance to drums/percussion, create tuned metallic textures, make any sound "ring" at a pitch, or build physical modeling instruments (exciter + Corpus)
- **Don't use when:** you need reverb (Corpus is not a space simulator), you want unpitched effects, or you need subtle spatial placement
- **Pairs well with:** Impulse/Simpler (exciter → Corpus for instrument building), Resonators (layer for richer harmonics), EQ Eight (tame resonant peaks), Compressor (control dynamics of resonant output)
- **vs Resonators:** Corpus models a single physical object with complex overtones. Resonators provides 5 parallel tuned resonances at musical intervals. Corpus = one rich body; Resonators = chord-like harmonic stacking.

---

### Resonators

- **Type:** Native
- **Load via:** `find_and_load_device("Resonators")`
- **What it does:** Five parallel resonators tuned to musical intervals. Turns any input (noise, drums, speech) into pitched, chord-like resonance. The full stereo signal feeds Resonator I; II--V alternate between L and R channels.
- **Signal flow:** Input → Multimode Filter → 5 parallel resonators (I = stereo, II--V = alternating L/R) → Width control → Dry/Wet output
- **Key parameters:**
  - **Filter** (input) → multimode (LP/BP/HP/Notch) → shapes what frequencies excite the resonators
  - **Resonator I Note** → root pitch (sets base for all resonators, active even when I is off)
  - **Resonators II--V** → semitones + cents relative to root → e.g., +4, +7, +12, -12 = major chord with octave doubling
  - **On/Off toggles** → per resonator → saves CPU
  - **Mode** → A or B → Mode B radically changes character and drops pitch by one octave
  - **Decay** → resonance tail length → 0.00 to hear just the filter; increase for sustain → short for percussive, long for pads
  - **Const** → keeps delay time constant regardless of pitch → affects timbre consistency across pitch changes
  - **Colour** → high-frequency roll-off → higher = brighter/twangier, lower = muted/warm
  - **Width** → stereo output width → 0% = mono (but II--V still process L/R separately)
  - **Dry/Wet** → 50--80% for harmonic overlay, 100% for full transformation
- **Presets:** "Chord Resonance" (major chord intervals), "Metallic Ring" (dissonant intervals), "Octave Stack"
- **Reach for this when:** you want to harmonize any sound into a chord, add pitched resonance to drums, create drone/pad textures from noise, or build physical modeling instruments
- **Don't use when:** you need spatial reverb, clean delay, or non-pitched effects
- **Pairs well with:** Impulse (drums → Resonators for tuned percussion), Simple Delay (post-Resonators for arpeggiator-like effects), Corpus (layer for complex resonance), EQ Eight (notch out harsh resonant peaks)
- **vs Corpus:** Resonators gives you 5 discrete pitched resonances at musical intervals (chords). Corpus gives you one complex physical body. Use Resonators for harmony, Corpus for timbre.

---

### Spectral Resonator

- **Type:** Native (Live 11+, Suite only)
- **Load via:** `find_and_load_device("Spectral Resonator")`
- **What it does:** FFT-based spectral processor that decomposes audio into partials, then resonates, stretches, shifts, and blurs them. Can be controlled by internal frequency or external MIDI for melodic spectral effects. Creates metallic delays, boxy reverbs, pitched spectral textures, and alien harmonics.
- **Signal flow:** Input → FFT analysis → Spectral processing (frequency shift, stretch, blur) → Unison voicing → IFFT resynthesis → Dry/Wet output. Optional MIDI sidechain for pitch control.
- **Key parameters:**
  - **Mode:** Internal (Freq knob sets pitch) or MIDI (external MIDI track controls pitch)
  - **Freq** → fundamental frequency for resonance → lower = dirtier, higher = brighter/more defined
  - **Decay** → spectral resonance sustain → 200--800 ms for delay-like, > 2 s for reverb-like wash
  - **Stretch** → shifts partials' spacing → 1.0 = natural harmonic series, < 1 = compressed (bell-like), > 1 = expanded (metallic)
  - **Shift** → shifts all partials up or down → detuning and inharmonic effects
  - **Chorus** → spectral chorus on partials → lush thickening
  - **Wander** → random sawtooth modulation on partials → organic movement and shimmer
  - **Granular** → granular processing of spectral data → glitchy, surprising textures
  - **Unison** (1--8 voices) → stacks detuned copies → massive sound
  - **Uni. Amt** (0--100%) → unison detune amount
  - **Dry/Wet** → 25--40% for subtle spectral color, 100% for full transformation
- **Presets:** "Spectral Chorus" (lush thickening), "Metallic Resonance" (tight, ringing), "MIDI Harmonizer" (pitched spectral)
- **Reach for this when:** you want spectral harmonics, pitched resonance controlled by MIDI, metallic or bell-like textures, spectral chorus/thickening, or alien sound design
- **Don't use when:** you need a natural-sounding reverb, clean delay, or transparent processing
- **Pairs well with:** Spectral Time (chain for full spectral processing), Hybrid Reverb (post for spatial context), Corpus (layer time-domain and spectral resonance)
- **vs Corpus/Resonators:** Spectral Resonator works in the frequency domain (FFT on partials). Corpus/Resonators work in the time domain (physical modeling). Spectral Resonator is more alien/digital; Corpus/Resonators are more organic/physical.

---

### Spectral Time

- **Type:** Native (Live 11+, Suite only)
- **Load via:** `find_and_load_device("Spectral Time")`
- **What it does:** Spectral delay with freeze capability. Decomposes audio via FFT, then applies frequency-dependent delay, pitch shifting, and spectral freeze. Two independent sections (Freeze + Delay) that can be used separately or combined.
- **Signal flow:** Input → FFT analysis → Freeze section (capture/hold/retrigger) → Spectral Delay (frequency-dependent delay lines with pitch shift) → IFFT resynthesis → Dry/Wet output
- **Key parameters:**
  - **Freeze Section:**
    - **Freeze** (button) → captures and holds current spectral content
    - **Mode:** Manual (hold button) or Retrigger (rhythmic freeze)
    - **Sync** → freeze interval synced to tempo
    - **Interval** → note value for retrigger → 1/8 for rhythmic freeze, longer for evolving pads
    - **X-Fade** → crossfade between freeze captures → smooths rhythmic retrigger
    - **Onset** → triggers freeze on transient detection
  - **Delay Section:**
    - **Time** → delay duration (ms or synced)
    - **Feedback** → spectral delay regeneration
    - **Shift** → pitch-shifts each successive delay → creates rising/falling spectral cascades
    - **Tilt** → skews delay time by frequency → positive = high freqs delayed more; negative = low freqs delayed more
    - **Spray** → randomizes delay times per frequency bin → smears time across spectrum
    - **Mask** → limits effect to high or low frequencies only
    - **Stereo** → pushes Tilt and Spray into stereo field
  - **Dry/Wet** → 25--40% for subtle spectral delay, 100% for full effect
  - **Zero Dry Signal Latency** (context menu) → reduces dry latency to 0 for live performance
- **Presets:** "Spectral Slapback" (short delay), "Frozen Pad" (freeze + long decay), "Pitch Cascade" (shift + feedback), "Spray Field" (randomized spectral delay)
- **Reach for this when:** you want spectral freeze effects, frequency-dependent delays (different delay times for different partials), pitch-shifted spectral cascades, or rhythmic glitch via retrigger freeze
- **Don't use when:** you need a standard clean delay, natural reverb, or transparent processing
- **Pairs well with:** Spectral Resonator (chain for full spectral toolkit), Reverb (post for spatial context), Auto Filter (pre for frequency-focused spectral work)
- **vs Grain Delay:** Spectral Time processes in frequency domain (per-partial delay). Grain Delay processes in time domain (grain slicing). Spectral Time is more precise and controllable per-frequency; Grain Delay is more chaotic and textural.

---

### Align Delay

- **Type:** M4L Stock (Max for Live Essentials)
- **Load via:** `find_and_load_device("Align Delay")`
- **What it does:** Utility delay for phase alignment and time correction. Not a creative effect — it is a mixing tool for correcting timing/phase issues between tracks, compensating for latency, or aligning PA systems.
- **Signal flow:** Input → Per-channel delay (L/R independent or linked) → Output
- **Key parameters:**
  - **Delay Mode:**
    - **Time** → milliseconds → for AV sync, subtle stereo maker (0.5--5 ms offset between L/R)
    - **Samples** → sample-level precision → for latency compensation and phase alignment between parallel mic signals
    - **Distance** → meters or feet (toggle m/ft) → for PA system alignment, monitor-to-main alignment
  - **L/R Delay Sliders** → independent per channel
  - **Stereo Link** → locks both channels → right channel greyed out
  - **Temperature** (Distance mode) → Celsius/Fahrenheit → compensates for speed of sound in warm/cold environments
- **Reach for this when:** fixing phase issues between multi-mic recordings, compensating for device latency, aligning PA speakers, creating subtle stereo widening via Haas effect (1--15 ms offset)
- **Don't use when:** you want creative delay effects (use Delay, Echo, or Filter Delay)
- **Pairs well with:** Utility (phase inversion + Align Delay for phase correction), EQ Eight (check frequency response after alignment)
- **vs Delay:** Completely different purpose. Align Delay is a mixing utility with sample-accurate timing. Delay is a creative echo effect.

---

## M4L Devices — Dub Machines Pack

---

### Diffuse

- **Type:** M4L User (CLX_02 / Dub Machines by Surreal Machines)
- **Load via:** `find_and_load_device("Diffuse")`
- **What it does:** Lush feedback-network reverb/smear effect with a sophisticated delay network under the hood. Creates short virtual spaces, long atmospheric swells, and everything between. All audio passes through a tape-tone preamp for warmth. Sounds like a cross between a reverb and a multi-tap delay.
- **Signal flow:** Input → Tape-tone preamp → Feedback delay network (multiple delay lines with size/diffusion/phase control) → Damping → Modulation → Rectify/Pump processing → Output mix
- **Key parameters:**
  - **Repeat** (56--1000 ms) → initial delay time → quantized to 1/32nd note steps; default = 1/16 note at current BPM; beat-sync available
  - **Size** → calculates each delay line's time from Repeat, pitch, and time factors → low Size + high Diffuse = rough; large Size + medium Diffuse = buttery smooth
  - **Diffuse** → primary character control → adjusts size, sign, and phase of each delay line's feedback and wet/direct mix → central to the entire sound
  - **Regen** (global feedback) → 0--100% = dry to sustained; > 100% = screeching distortion and self-oscillation
  - **Send** → input attenuation to wet signal → dub-style send behavior; with Regen > 100%, turning Send down creates constantly evolving tail
  - **High / Low** (damping) → frequency-specific damping with dB sliders → higher % = more damping → controls brightness/warmth of tail
  - **Mod** → internal LFO amplitude on delay line sizes → low = subtle detuning, high = 1980s digital smearing; Stereo/Mono switch for LFO behavior
  - **Modes** → selectable routing modes with subtle differences in stereo balance, delay offsets, amplitude, and phase
  - **Rectify** → digital processing for top-end sizzle
  - **Pump** → dynamics tool that ducks delay under dry signal and pulls it back for sustained trails
  - **Character Tab + Slider** → 4 machine styles → slider range exaggerates effects; default 25% = most hardware-accurate
- **Reach for this when:** you want a reverb with analog character, dub-style smearing, evolving atmospheric tails, feedback-network textures, or a reverb that sounds "alive"
- **Don't use when:** you need realistic room simulation (use Hybrid Reverb with IR), clean transparent reverb, or precise control over early reflections
- **Pairs well with:** Magnetic (same pack — chain for full dub processing), Echo (pre-Diffuse for delay-into-reverb), EQ Eight (post for final shaping)
- **vs Reverb:** Diffuse has more analog character, tape saturation, and a feedback-network architecture vs Reverb's cleaner algorithmic approach. Diffuse self-oscillates beautifully; Reverb stays controlled.

---

### Magnetic

- **Type:** M4L User (CLX_02 / Dub Machines by Surreal Machines)
- **Load via:** `find_and_load_device("Magnetic")`
- **What it does:** Tape delay modeled after a beloved 1970s tape echo unit. Multiple gain stages, tape hysteresis, capstan wobble, and 3 virtual tape heads. Includes a high-quality convolution reverb with spring, plate, and hall IRs. All signal passes through a custom tape-tone preamp.
- **Signal flow:** Input → Tape-tone preamp → 3 playback heads (selectable via Mode) → Tape modeling (hysteresis, wobble, saturation) → Convolution reverb (optional, routed Pre/Post/Parallel) → Bass/Treble tone → Mix output
- **Key parameters:**
  - **Mode** (1--12) → selects head combinations: 1--4 = Echo only, 5--11 = Echo + Reverb, 12 = Reverb only → some modes produce exaggerated stereo spread
  - **Input** (0--200%) → 0--100% = dub-style send; 100--200% = increases saturation in wet chain
  - **Repeat** (10--1000 ms) → delay time → ms or beat-synced; snap arrows quantize to 1/64, 1/32, 1/16, 1/8 values
  - **Intensity** (feedback) → 0--100% = dry to infinite sustain; > 100% = heavy distortion and self-oscillation
  - **Bass / Treble** → 12 dB shelf filters on wet signal pre-mix
  - **Echo dB / Reverb dB** → independent level controls for echo and reverb sections
  - **Character Tab + Slider** → 4 machine styles → slider default 25% = most hardware-accurate; modifies tone, saturation, signal mixing, feedback response
  - **Reverb Route:** Parallel (input → echo + reverb summed), Pre (reverb → echo), Post (echo → reverb)
  - **Reverb IR categories** → spring, plate, early digital halls, character spaces
  - **Width** → stereo imperfection control → mono to wide
  - **Pump** → dynamics tool: ducks delay under dry signal, pulls back for sustained trails
  - **Rectify** → digital processing for top-end sizzle
  - **Processing Tab:** Oversampling (1x, 2x, 4x) → 2x recommended for high gain; 4x for fast modulation or HF content
  - **Mix** → parabolic crossfade dry/wet → note: "dry" still passes through tape preamp
- **Reach for this when:** you want authentic tape echo character, dub delay with spring/plate reverb, warm saturated repeats, or a delay that sounds like real hardware
- **Don't use when:** you need clean digital delay (use Delay), precise rhythmic delays without character, or very low CPU usage
- **Pairs well with:** Diffuse (same pack — Magnetic for echo, Diffuse for reverb), Auto Filter (pre for dub filter sweeps), Utility (gain staging into Magnetic for saturation control)
- **vs Echo:** Magnetic is more authentically analog-sounding with real tape modeling and convolution reverb. Echo is more flexible and lighter on CPU. Magnetic wins for dub/tape authenticity; Echo wins for versatility.

---

## M4L Devices — Creative Extensions

---

### Gated Delay

- **Type:** M4L Stock (Creative Extensions, free with Suite)
- **Load via:** `find_and_load_device("Gated Delay")`
- **What it does:** Gate sequencer that rhythmically sends signal to a delay line on activated steps. Like a tempo-synced send to a delay that turns on/off in a pattern. Creates rhythmic, sequenced delay patterns impossible with standard delays.
- **Signal flow:** Input → Step sequencer gate → Delay line (rate-multiplied) → Feedback → Volume/Ducking → Mix mode output
- **Key parameters:**
  - **Steps** → number of steps in the gate sequence
  - **Rate** → speed of step traversal (tempo-synced)
  - **Step toggles** → activate/deactivate individual steps → draw rhythmic patterns
  - **Delay Time** → whole or fractional multiplier of current step size
  - **Random** → fluctuates delay time multiplication factor → shifting rhythmic delay patterns
  - **Feedback** → delay regeneration
  - **Delay Volume** → wet signal level
  - **Mix Mode:** Insert (mutes dry on active steps) or Gate (only delay output)
  - **Ducking** → reduces delay level when dry signal is present
  - **Dry/Wet** → balance control
- **Reach for this when:** you want rhythmic, sequenced delay patterns; tempo-synced gated echoes; complex polyrhythmic delay textures; trance-gate-style delay effects
- **Don't use when:** you want a standard delay, continuous reverb, or non-rhythmic spatial effects
- **Pairs well with:** Echo (post for character on the gated delays), Auto Filter (pre for filtered rhythmic delays), Beat Repeat (different rhythmic approach, layer both)
- **vs Beat Repeat:** Gated Delay sends to a delay line rhythmically. Beat Repeat captures and replays buffer slices. Gated Delay is more musical and controllable; Beat Repeat is more chaotic and destructive.

---

### Spectral Blur

- **Type:** M4L Stock (Creative Extensions, free with Suite)
- **Load via:** `find_and_load_device("Spectral Blur")`
- **What it does:** Spectral smearing effect that grabs grains from a defined frequency range and extends/blurs them into a dense cloud. Creates reverb-like textures through spectral processing rather than traditional reflections. Has a Freeze mode for infinite sustain.
- **Signal flow:** Input → FFT analysis → Frequency band selection (Freq1/Freq2) → Grain extension/blurring → Residual mix → Halo decay → Delay Compensation → Dry/Wet output
- **Key parameters:**
  - **Freq1 / Freq2** → define the spectral band to blur → narrow band = surgical, wide = full-spectrum wash
  - **In / Out mode** → In = blur frequencies inside the band; Out = blur frequencies outside the band (notch-type effect)
  - **Halo** → decay length of blurred grains → short = subtle smear, long = dense reverb-like cloud
  - **Freeze** → holds current buffer indefinitely regardless of Halo setting → infinite sustain pad
  - **Residual** → level of initial un-smeared grains → higher = more clarity/definition mixed with blur
  - **Wet Gain** → output level of wet signal
  - **Delay Compensation** → corrects timing inconsistencies
  - **Dry/Wet** → 20--40% for subtle blur, 100% for full cloud
- **Reach for this when:** you want spectral reverb-like textures, frequency-selective blurring, drone/pad creation from any source, freeze effects, or reverb that only affects certain frequencies
- **Don't use when:** you need traditional reverb with early reflections and tail, clean delay, or transparent processing
- **Pairs well with:** EQ Eight (pre for frequency-focused input), Hybrid Reverb (post for spatial context on the blur), Auto Filter (modulate the frequency band)
- **vs Spectral Time:** Spectral Blur is simpler and focused on smearing/freezing. Spectral Time has delay, freeze, pitch shifting, and frequency-dependent timing. Use Spectral Blur for quick spectral washes; Spectral Time for complex spectral manipulation.

---

## M4L Community Devices

---

### ml.Distance

- **Type:** M4L User (CLX_02 / community device by alkman, based on Robert Henke's original)
- **Load via:** Load from User Library (M4L device, not in browser by default)
- **What it does:** Emulates the psychoacoustic effects of distance — as a sound source moves farther away, you hear reduced volume AND reduced high frequencies (air absorption). More realistic than just turning down a fader. Includes panning for spatial positioning.
- **Signal flow:** Input → Distance processing (volume attenuation + frequency-dependent HF roll-off) → Panning → Output
- **Key parameters:**
  - **Distance** → perceived distance from listener → 0 = close/present, 20 = subtle distance, 60+ = far away and muffled
  - **Pan** → stereo position of the sound source
  - **Smooth** → interpolation time for parameter changes → prevents clicks when automating distance/pan → higher = smoother transitions
- **Reach for this when:** you want realistic depth placement in a mix, cinematic distance effects, automating a sound moving toward or away from the listener, or creating front-to-back depth without reverb
- **Don't use when:** you need reverb/echo, creative effects, or lateral-only panning (use standard pan)
- **Pairs well with:** Reverb (distance + reverb for full spatial placement), Auto Pan (combine distance + lateral movement), Hybrid Reverb (longer reverb for "far away" sounds)
- **vs Utility (volume + EQ):** ml.Distance models psychoacoustic distance curves automatically. Manually reducing volume + cutting highs with EQ approximates this but is less accurate and harder to automate as a single "distance" control.

---

### Steroid (STEREOID by DIFF Devices)

- **Type:** M4L User (CLX_02)
- **Load via:** Load from User Library (M4L device)
- **What it does:** Multiband stereo width processor — NOT a reverb despite the name suggestion. Precisely adjusts stereo width across 4 independent frequency bands with correlation monitoring. Use it to widen or narrow specific frequency ranges.
- **Signal flow:** Input → 4-band frequency split → per-band stereo width processing → Bass Mono option → Correlation Meter → Mix → Output
- **Key parameters:**
  - **Stereo Width per band** (4 bands) → independently widen or narrow each frequency range
  - **Frequency band boundaries** → adjustable crossover points
  - **Bass Mono** → collapses low frequencies to mono → essential for club/vinyl compatibility
  - **Spectrum Display** → visual frequency analysis
  - **Correlation Meter** → monitors phase relationship → stay above 0 to avoid mono-compatibility issues
  - **Mix** → blend processed and original signal
- **Reach for this when:** you need frequency-selective stereo widening, bass mono for club tracks, checking stereo correlation, or making specific frequency ranges wider/narrower independently
- **Don't use when:** you need reverb, delay, or spatial depth effects
- **Pairs well with:** ml.Distance (width + depth for full spatial control), Utility (overall width after per-band adjustment), EQ Eight (frequency shaping + stereo width)
- **vs Utility (Width):** STEREOID offers per-band control over 4 frequency ranges with a correlation meter. Utility is broadband only. Use STEREOID for surgical stereo work, Utility for quick overall width.

---

### Vbap Doppler Panner

- **Type:** M4L User (CLX_02 / community device by alkman)
- **Load via:** Load from User Library (M4L device)
- **What it does:** 2D surround panner using Vector Base Amplitude Panning (VBAP) algorithm by Ville Pulkki. Includes Doppler shift simulation for realistic motion effects. Supports up to 12 output channels with custom speaker arrangements. For multichannel/immersive audio.
- **Signal flow:** Input → VBAP position calculation → Per-speaker amplitude → Doppler processing (highpass filter + variable delay for distance) → Multi-channel output routing
- **Key parameters:**
  - **Position** (X/Y or azimuth) → 2D position of sound source among speakers
  - **Speaker Configuration** → define speaker coordinates in degrees (-180 to 180 or 0 to 360) → predefined setups included
  - **Doppler Window** → controls doppler shift intensity for moving sources
  - **Distance** → perceived distance from center → applies HF roll-off and level reduction
  - **Up to 12 channels** → per-channel output routing
  - **RMS Meters** → per-speaker level monitoring
- **Setup note:** Device auto-routes output to "Sends Only" — must manually configure output routing through setup window.
- **Reach for this when:** multichannel/surround mixing, immersive audio installations, spatial audio performances, realistic source movement with Doppler, sound design for film/games
- **Don't use when:** working in standard stereo (use standard panning or Auto Pan), you only need simple L/R placement
- **Pairs well with:** ml.Distance (combine VBAP panning + distance simulation), Reverb on return tracks (per-speaker reverb for room simulation), Spectral Time (spectral processing on moving sources)
- **vs Surround Panner (Ableton):** Both do multichannel panning. Vbap Doppler Panner adds Doppler shift simulation and uses the VBAP algorithm (mathematically optimal for arbitrary speaker layouts). Surround Panner is simpler to set up for standard configurations.

---

## Quick Decision Matrix

| Scenario | First Choice | Alternative | Avoid |
|---|---|---|---|
| **Clean rhythmic delay** | Delay | Echo (Ducking on) | Grain Delay |
| **Tape/dub echo** | Echo or Magnetic | Delay (Repitch mode) | Filter Delay |
| **Multi-band filtered delay** | Filter Delay | Echo + EQ Eight | Delay |
| **Shimmer / octave delay** | Grain Delay | Spectral Time (Shift) | Delay |
| **Rhythmic gated delay** | Gated Delay | Beat Repeat | Reverb |
| **Stutter / glitch** | Beat Repeat | Gated Delay | Delay |
| **Natural room reverb** | Hybrid Reverb (IR) | Reverb | Spectral Blur |
| **Creative / evolving reverb** | Hybrid Reverb (Shimmer/Tides) | Diffuse | Reverb |
| **Lush analog reverb** | Diffuse | Hybrid Reverb (Dark Hall) | Align Delay |
| **Spectral freeze / pad** | Spectral Time (Freeze) | Spectral Blur (Freeze) | Reverb (Freeze) |
| **Spectral harmonic resonance** | Spectral Resonator | Resonators | Corpus |
| **Pitched resonance on drums** | Corpus (MIDI sidechain) | Resonators | Reverb |
| **Chord-like harmonic stacking** | Resonators | Spectral Resonator | Corpus |
| **Physical body resonance** | Corpus | Resonators | Spectral Resonator |
| **Realistic distance placement** | ml.Distance | Utility + EQ Eight | Reverb alone |
| **Multiband stereo width** | STEREOID | Utility (broadband) | ml.Distance |
| **Surround / immersive panning** | Vbap Doppler Panner | Surround Panner | Auto Pan |
| **Phase alignment / latency fix** | Align Delay | — | Delay |
| **Frequency-selective blur** | Spectral Blur | Spectral Time | Reverb |
| **Spectral pitch cascade** | Spectral Time (Shift + Feedback) | Grain Delay (Pitch + Feedback) | Delay |
| **Self-oscillating feedback** | Echo (Feedback > 100%) | Diffuse (Regen > 100%) | Delay |
| **Vocal delay (stays out of way)** | Echo (Ducking on) | Delay + Compressor sidechain | Filter Delay |
| **Build-up / transition FX** | Beat Repeat + Echo | Spectral Time (Freeze retrigger) | Align Delay |

---

## Chaining Recipes

| Chain | Use Case |
|---|---|
| **Grain Delay → Hybrid Reverb (Shimmer)** | Ethereal shimmer wash — Grain Delay adds octave pitch, Hybrid Reverb extends into infinite shimmer tail |
| **Echo (Ducking) → Diffuse** | Dub delay into lush analog reverb — Echo stays clean during playing, Diffuse smears the tails |
| **Beat Repeat → Echo (Feedback loop reverb)** | Glitch stutter into self-oscillating delay chaos — performance build-up tool |
| **Corpus (MIDI sidechain) → Resonators** | Tuned physical resonance + harmonic chord stacking — turns any percussive source into a melodic instrument |
| **Spectral Resonator → Spectral Time** | Full spectral processing chain — resonate partials then apply frequency-dependent delay and freeze |
| **ml.Distance → Hybrid Reverb** | Psychoacoustic depth — Distance handles HF roll-off and volume, Hybrid Reverb adds room context |
| **Filter Delay → Diffuse** | Frequency-separated delays into analog feedback reverb — complex, evolving dub textures |
| **Spectral Blur (narrow band) → Echo** | Selective frequency smear fed into characterful delay — isolate and repeat specific spectral content |
| **STEREOID → Vbap Doppler Panner** | Stereo width shaping before surround distribution — control per-band width before spatial placement |

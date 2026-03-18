# Drums & Percussion — Device Atlas

> Deep reference for every drum and percussion device, instrument, and processor in this Ableton Live 12 installation.
> Covers Drum Rack, DS Drum Synths (M4L), Drum Sampler (12.1), Impulse, Drum Buss, third-party M4L drum tools, and the full 139-kit library organized by genre/character.

---

## Core Architecture

---

### Drum Rack

- **Type:** Native (Instrument Rack variant)
- **Load via:** `find_and_load_device("Drum Rack")`
- **What it does:** The container system for all drum programming in Live. Each pad hosts an independent instrument chain with its own effects, mixer controls, and routing. Maps 128 MIDI notes to individual pads, supports layering, choke groups, and internal send/return processing. The backbone of every drum kit in Live.
- **Signal flow:** MIDI In -> Pad Note Assignment (Receive) -> Per-Pad Instrument Chain (with per-chain FX) -> Per-Chain Mixer (Volume/Pan/Sends) -> Send/Return Chains (up to 6) -> Main Output
- **Key concepts:**
  - **Pad View:** 16 pads visible at once; navigate 128 total pads via the pad overview on the left. Each pad = one MIDI note. Drop samples, instruments, or presets directly onto pads.
  - **Standard GM Mapping:** C1 (MIDI 36) = Kick, C#1 (37) = Sidestick, D1 (38) = Snare, D#1 (39) = Clap, E1/F1 (40/41) = Toms, F#1 (42) = Closed HH, G#1 (44) = Pedal HH, A#1 (46) = Open HH, C#2 (49) = Crash, D#2 (51) = Ride
  - **Choke Groups:** 16 groups available. Chains in the same choke group silence each other when triggered. Classic use: closed hi-hat (F#1) chokes open hi-hat (A#1) by assigning both to Choke Group 1.
  - **Layering:** Alt/Cmd-drag multiple samples onto a single pad to create a nested Instrument Rack (all play simultaneously). Without modifier, samples map chromatically from the target pad.
  - **Send/Return Chains:** Up to 6 return chains for shared processing (reverb, delay, saturation). Each pad chain gets independent send level knobs. Return output can route to Rack main out or directly to Set return tracks.
  - **Chain List Columns:** Receive (incoming MIDI note), Play (outgoing note to instrument), Choke (group assignment), output routing
  - **Macro Controls:** Up to 16 macros (8 shown by default) that can map to any parameter across all pad chains. Support randomization, snapshots/variations.
  - **Hot-Swap:** Press D to toggle hot-swap target between the Rack itself and the selected pad.
  - **Individual Pad Routing:** Each chain has Volume, Pan, and Send sliders in the mixer section.
- **Presets:** Every drum kit in the browser is a Drum Rack preset. See the Kit Guide below for the full 139-kit breakdown.
- **LivePilot workflow:**
  - Load a kit: `find_and_load_device("Kit Name")` on a MIDI track
  - Add device to specific pad: Load instrument into Drum Rack chain, set Receive note
  - Set choke groups: Access chain list, set Choke column value (1-16) for related pads
  - Layer sounds: Load multiple instruments on one pad chain via nested Instrument Rack
  - Notes always target pad MIDI notes (e.g., C1=36 for kick, D1=38 for snare)
- **Reach for this when:** building any drum kit, you need per-pad processing, you want choke groups, you need internal send/return for shared reverb/delay
- **Don't use when:** you need a quick 8-slot sketch (use Impulse), you want a single synthesized drum voice (use DS synths or Drum Sampler directly)

---

## DS Drum Synths (Max for Live)

> Nine lightweight synthesizers designed to drop into Drum Rack pads. Each generates a specific percussion voice from synthesis (no samples needed except DS Sampler). All share a consistent interface: visual waveform display (click to preview), Decay knob, Volume knob, and Pitch control.

---

### DS Kick

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Kick")`
- **What it does:** Kick drum synth built on a modulated sine wave. Produces everything from deep sub-bass 808 kicks to punchy acoustic-style kicks. The OT (overtone) control adds a mid-range resonant tone reminiscent of a 909 kick.
- **Signal flow:** Sine Oscillator -> Pitch Envelope (Env) -> Drive/Saturation -> Click Layer -> Volume -> Output
- **Key parameters:**
  - **Pitch** (Hz) -> fundamental frequency of the kick -> lower = deeper sub, higher = punchier
  - **Env** -> pitch modulation envelope amount -> higher = more dramatic pitch sweep (classic 808 boom), lower = flatter thud
  - **Drive** -> adds distortion/saturation -> subtle warmth at low values, aggressive grit at high values
  - **OT** (Overtone) -> adds mid-range resonant harmonic -> 909-style presence, helps kick cut through on small speakers
  - **Click** (switch) -> toggles a transient click layer -> ON for defined attack that cuts through mix, OFF for softer rounded onset
  - **Attack** -> smooths the initial sine wave transient -> higher = softer attack
  - **Decay** -> length of the kick tail -> short for tight electronic, long for boomy sub
  - **Volume** -> output level
- **Presets:** 808 Kick, 909 Kick, Acoustic Kick, Sub Kick, Punchy Kick
- **Reach for this when:** you need a synthesized kick with control over sub content, pitch sweep, and drive character
- **Don't use when:** you need a sampled acoustic kick (use Drum Sampler), you want complex layered kicks (build in Drum Rack with multiple chains)
- **Pairs well with:** Drum Buss (Boom section for sub reinforcement), Saturator (additional harmonic control), EQ Eight (surgical low-end shaping)

---

### DS Snare

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Snare")`
- **What it does:** Snare synth combining a pitched oscillator with noise. Covers the range from traditional acoustic snare sounds to gated noise electronic snares common in EDM.
- **Signal flow:** Pitched Oscillator + Noise Generator -> Filter (LP/HP/BP selectable) -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Tune** -> global pitch of the snare body -> lower for fat snares, higher for cracking snares
  - **Color** -> tone/character of the pitched signal -> shapes the body harmonic content
  - **Tone** -> presence/level of the noise signal -> 0% = pure pitched body, 100% = dominated by noise (electronic snare)
  - **Filter Type** (LP / HP / BP toggle) -> shapes the overall frequency response -> LP for warm/dark, HP for bright/thin, BP for focused mid-range
  - **Decay** -> snare tail length -> short for tight, long for roomy
  - **Volume** -> output level
- **Reach for this when:** you need a snare from synthesis, blending tonal body with noise rattle
- **Pairs well with:** Compressor (transient emphasis), Reverb (room character), Gate (tightening the tail)

---

### DS Clap

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Clap")`
- **What it does:** Clap synth using filtered noise and impulses through panned delay lines. Creates everything from tight electronic claps to loose, humanized handclaps with natural spread.
- **Signal flow:** Impulse + Filtered Noise (Tail) -> Panned Delay Lines (Sloppy) -> Stereo Spread -> Tone Filter -> Volume -> Output
- **Key parameters:**
  - **Tune** -> pitch of the clap
  - **Sloppy** -> delay time between the panned delay lines -> 0% = tight, synchronized electronic clap; high = loose, humanized feel with audible flamming
  - **Tail** -> amount of filtered noise added to the impulse -> adds sustain and body
  - **Spread** (0-100%) -> stereo width -> 0% = mono, 100% = wide stereo image
  - **Tone** -> color/brightness of the clap -> adjusts high-frequency content
  - **Decay** -> combined with Tail to control overall duration
  - **Volume** -> output level
- **Reach for this when:** you need a clap with natural humanization (Sloppy) and stereo width
- **Pairs well with:** Reverb (room ambience), Chorus-Ensemble (thickening), Drum Buss (glue)

---

### DS HH (Hi-Hat)

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS HH")`
- **What it does:** Hi-hat synth blending noise and sine waveforms through a resonant high-pass filter. Produces sharp closed hats to sizzling open hats.
- **Signal flow:** Noise Generator (White/Pink) + Sine Oscillator -> Resonant High-Pass Filter (12/24 dB) -> Attack Shaping -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Pitch** -> global pitch control -> higher = brighter, more present
  - **Noise Type** (White / Pink toggle) -> White = conventional metallic hat; Pink = more focused, cuts through mix with metallic edge
  - **Tone** -> high-pass filter cutoff -> higher = removes more low end, thinner/brighter
  - **Filter Slope** (12 dB / 24 dB toggle) -> steepness of the HP filter -> 24 dB = sharper, more defined; 12 dB = gentler roll-off
  - **Attack** -> attack time of the resonant HP filter -> shapes the onset character
  - **Decay** -> hat length -> very short for tight closed hats, longer for open hats, medium for pedal hats
  - **Volume** -> output level
- **Tip:** Use two DS HH instances on different pads — one with short Decay (closed hat, F#1) and one with long Decay (open hat, A#1) — then set both to the same Choke Group so closed chokes open.
- **Reach for this when:** you need synthesized hi-hats with precise control over metallic character
- **Pairs well with:** Saturator (add grit), Auto Pan (movement), Erosion (lo-fi texture)

---

### DS Cymbal

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Cymbal")`
- **What it does:** Electronic cymbal synth for splashes, crashes, and rides. Simple three-knob design for quick results.
- **Signal flow:** Noise/Oscillator Core -> Tone Filter -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Pitch** -> cymbal pitch
  - **Tone** -> high-pass filter cutoff -> shapes brightness and metallic character
  - **Decay** -> cymbal sustain length -> short for splashes, long for crashes/rides
  - **Volume** -> output level
- **Reach for this when:** you need a quick electronic cymbal without fuss
- **Don't use when:** you need realistic cymbal sounds (use sampled cymbals in Drum Sampler)

---

### DS Tom

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Tom")`
- **What it does:** Tom synth with pitched oscillator, noise layer, and pitch envelope. Fills the mid-range with resonant, punchy toms. Pitch displayed in both note name and Hz for diatonic tuning.
- **Signal flow:** Pitched Oscillator -> Pitch Envelope (Bend) -> Resonant Band-Pass Filters (Tone) -> Color Filter -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Pitch** (note/Hz) -> fundamental frequency -> tune toms to musical intervals for melodic fills
  - **Bend** -> pitch envelope amount -> high = taut-skinned punch with dramatic pitch sweep; low = flatter resonant thud
  - **Color** -> filter gain and cutoff -> shapes the character of both noise and primary timbre
  - **Tone** -> level of resonant band-pass filters -> mimics drum membrane tuning; adds filtered noise texture
  - **Decay** -> tom tail length
  - **Volume** -> output level
- **Reach for this when:** you need synthesized toms, especially for tribal or electronic percussion with tunable pitch
- **Pairs well with:** Reverb (big room toms), Drum Buss (punch and body), Delay (rhythmic tom patterns)

---

### DS FM

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS FM")`
- **What it does:** FM synthesis percussion generator inspired by classic Japanese FM synthesizers (DX7/TX81Z). Creates everything from tuned claves and woodblocks to laser blasts and futuristic bleeps. Pitch displayed in note values for diatonic use.
- **Signal flow:** FM Algorithm (Carrier + Modulator) -> Feedback -> Low-Pass Filter (Tone) -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Pitch** (note display) -> global pitch -> tune to key for melodic percussion
  - **Tone** -> low-pass filter cutoff -> higher = more high-frequency content; lower = warmer/darker
  - **Feedb.** (Feedback) -> FM algorithm feedback amount -> increases harmonic complexity and metallic character
  - **Amnt** (Amount) -> FM modulation depth -> subtle = bell-like; extreme = noisy, chaotic
  - **Mod** (Modulation) -> blends between modulation types -> warps the timbral character
  - **Decay** -> percussion length
  - **Volume** -> output level
- **Reach for this when:** you need metallic, bell-like, or otherworldly synthesized percussion; tuned percussion elements; sci-fi sound effects
- **Don't use when:** you need organic-sounding percussion (use DS Tom or sampled sounds)
- **Pairs well with:** Chorus-Ensemble (detuned bells), Delay (rhythmic patterns), Reverb (space)

---

### DS Clang

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Clang")`
- **What it does:** Metallic percussion synth with two independent tones, white noise, and a filter. Creates cowbells, claves, rimshots, and noise percussion. Has a dedicated Clave mode with repeats.
- **Signal flow:** Tone A + Tone B + White Noise -> HP/BP Filter -> Clave Repeat (optional) -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Pitch** -> global pitch of the instrument
  - **Tone A / Tone B** (sliders) -> independent volume for each cowbell tone -> balance between two pitched components
  - **Filter** -> high-pass and band-pass filter cutoff -> shapes metallic character; higher = brighter
  - **Noise** -> amount of white noise added -> adds sizzle and texture
  - **Clave** (switch) -> activates clave mode with metallic ping on top
  - **Repeat** -> adds rattling repeats to the clave sound -> creates flam-like percussion patterns
  - **Decay** -> sound length
  - **Volume** -> output level
- **Reach for this when:** you need cowbell, clave, rimshot, or tuned metallic percussion
- **Pairs well with:** Saturator (grit), Auto Filter (movement), Delay (rhythmic cowbell patterns)

---

### DS Sampler

- **Type:** M4L Instrument (Drum Synth)
- **Load via:** `find_and_load_device("DS Sampler")`
- **What it does:** Sample-based drum voice that fits the DS Drum Synth form factor. Drag and drop any sample into the display. Provides Start, Length, Tuning, Loop mode, and a Shaper for saturation. The bridge between synthesis and sampling within the DS ecosystem.
- **Signal flow:** Sample Playback (Start/Length) -> Tuning -> Loop (optional) -> Shaper/Saturation -> Decay Envelope -> Volume -> Output
- **Key parameters:**
  - **Start** -> sample playback start position -> find the sweet spot of the transient
  - **Length** -> sample playback length -> trim unwanted tail
  - **Tune** (+-48 semitones) -> pitch shift the sample
  - **Loop** (switch) -> enables sample looping -> creates digital, stuttering textures at short lengths
  - **Shaper** -> saturation/distortion -> adds punch and grit; thickens thin samples
  - **Decay** -> amplitude decay time
  - **Volume** -> output level
- **Reach for this when:** you want to use a custom sample in the DS Drum Synth visual format, maintaining consistent UI with the other DS synths
- **Don't use when:** you need advanced sample manipulation (use Drum Sampler 12.1 or Simpler)
- **vs Drum Sampler (12.1):** DS Sampler is simpler, fits the DS form factor. Drum Sampler has 9 playback effects, filter section, AHD envelope, and modulation matrix.

---

## Drum Sampler (Live 12.1+)

---

### Drum Sampler

- **Type:** Native Instrument (Live 12.1+, all editions)
- **Load via:** `find_and_load_device("Drum Sampler")`
- **What it does:** Purpose-built one-shot sample playback device for percussion. The modern replacement for dropping samples into Simpler in Slice mode. Features 9 playback effects with X/Y pad control, a filter section, AHD envelope, velocity/MPE modulation, and similarity-based sample swapping. Designed to be the default instrument on new Drum Rack pads (set via context menu: "Save as Default Pad").
- **Signal flow:** Sample (Start/Length) -> Playback Effect -> Filter -> AHD Envelope -> Velocity-to-Volume -> Pan -> Output
- **Key parameters:**
  - **Sample Section:**
    - **Sample Start** (% of length) -> where playback begins
    - **Sample Length** (% of total) -> playback region length
    - **Sample Gain** (-70 to +24 dB) -> pre-processing level
    - **Transpose** (-48 to +48 semitones) -> pitch shift
    - **Detune** (-50 to +50 cents) -> fine tuning
    - **Swap Next/Previous** -> browse similar samples automatically
    - **Save as Similarity Reference** -> set reference for similarity search
  - **Envelope (AHD):**
    - **Attack** -> time to reach peak level
    - **Hold** -> sustain duration at peak (can be set to infinite); disabled in Gate mode
    - **Decay** -> return time from peak to zero
    - **Trigger Mode** -> sample plays for Hold duration after note release
    - **Gate Mode** -> sample fades per Decay time once note is released
  - **9 Playback Effects** (toggle on/off, X/Y pad control):
    - **Stretch** -> Factor (time-stretch multiplier) + Grain Size (ms) -> change length without changing pitch
    - **Loop** -> Loop Offset (start point) + Loop Length (ms) -> repeat a portion of the sample
    - **Pitch Env** -> Amount (-100 to +100%) + Decay (return time) -> pitch sweep over time (808-style boom)
    - **Punch** -> Amount (ducking intensity) + Release (recovery) -> emphasizes transient attack
    - **8-Bit** -> Sample Rate (bit crush rate) + Decay (LP filter decay) -> lo-fi reduction
    - **FM** -> Amount (FM depth) + Frequency (modulator freq) -> sine-wave pitch modulation
    - **Ring Mod** -> Amount (mod depth) + Frequency (mod freq) -> ring modulation
    - **Sub Osc** -> Amount (level) + Frequency (30-120 Hz) -> layers a sub oscillator
    - **Noise Osc** -> Amount (level) + Color (filter freq) -> layers noise
  - **Filter Section** (toggle on/off):
    - **Types:** 12 dB LP, 24 dB LP, 24 dB HP, Peak
    - **Frequency** -> cutoff/center frequency
    - **Resonance** (LP/HP) or **Peak Gain** (Peak mode)
  - **Modulation:**
    - **Sources:** Velocity, Slide (MPE)
    - **Destinations:** Filter, Attack, Hold, Decay, FX1, FX2
    - **Amount slider** -> intensity of source-to-destination routing
  - **Output:**
    - **Volume** (-36 to +36 dB)
    - **Pan** -> stereo position
    - **Velocity to Volume** -> how much velocity affects level
  - **Context Menu Options:** Enable Per-Note Pitch Bend, Envelope Follows Pitch, Convert to Simpler, Save as Default Pad
- **Presets:** Factory presets organized by percussion type
- **Reach for this when:** building custom drum kits from samples, you want playback effects (Punch, 8-Bit, FM, Sub Osc), you need MPE support on drum pads, quick sample browsing with similarity search
- **Don't use when:** you need multi-sample layering (use Simpler/Sampler in Drum Rack), you want pure synthesis (use DS drum synths)
- **Pairs well with:** Drum Buss (after the Drum Rack for glue), Saturator (per-pad grit), Auto Filter (per-pad movement)
- **vs Simpler:** Drum Sampler is streamlined for one-shots with built-in playback effects and similarity search. Simpler offers multi-mode playback (Classic/One-Shot/Slice), warping, and more sample manipulation. Use Drum Sampler for drums, Simpler for melodic sampling.
- **vs DS Sampler:** DS Sampler is the legacy M4L version with minimal controls (Start, Length, Tune, Loop, Shaper). Drum Sampler adds 9 playback effects, proper filter, AHD envelope, modulation matrix. Drum Sampler is the modern choice.

---

## Drum Processing

---

### Drum Buss

- **Type:** Native Audio Effect
- **Load via:** `find_and_load_device("Drum Buss")`
- **What it does:** Analog-style drum processor that adds body, character, and cohesion to drum groups. Combines distortion (3 types), mid-high transient shaping, and a resonant low-end enhancer in one device. Designed specifically for drum bus processing — does what would normally require 4-5 separate devices in a single, intuitive interface.
- **Signal flow:** Input -> Trim -> Fixed Compressor (optional) -> Drive Distortion (Soft/Medium/Hard) -> Crunch (mid-high sine distortion) -> Damp (LP filter) -> Transient Shaping (>100 Hz) -> Boom (resonant bass filter + decay) -> Dry/Wet -> Output Gain
- **Key parameters:**
  - **Trim** -> reduces input level before processing -> use to prevent over-driving
  - **Comp** (toggle) -> fixed compressor optimized for drums -> fast attack, medium release, moderate ratio, ample makeup gain -> ON for tighter, more balanced drums
  - **Drive** -> distortion amount applied before the distortion type
  - **Drive Type** (Soft / Medium / Hard):
    - **Soft** -> waveshaping distortion -> gentle warmth, subtle harmonic addition, transparent at low Drive
    - **Medium** -> limiting distortion -> moderate saturation with level control, good all-rounder
    - **Hard** -> clipping distortion with bass boost -> aggressive, adds weight to low end, best for hard-hitting genres
  - **Crunch** -> sine-shaped distortion on mid-high frequencies -> adds presence and bite where drums cut through mix; the "excitement" control
  - **Damp** -> low-pass filter -> removes harsh high frequencies introduced by Drive and Crunch -> tame fizz while keeping warmth
  - **Transients** (bipolar) -> shapes transients above 100 Hz:
    - **Center (0)** -> no change
    - **Positive** -> boosts attack AND sustain -> full, "punchy" sound with extended body
    - **Negative** -> boosts attack, reduces sustain -> tight, crisp drums with less room/rattle
  - **Boom Section:**
    - **Boom** (knob) -> level of resonant bass filter -> 0% = dry low end, higher = dramatic sub reinforcement
    - **Freq** -> center frequency of the bass enhancer (30-90 Hz) -> match to kick fundamental
    - **Force to Note** (button) -> snaps Freq to nearest MIDI note -> ensures musical bass tuning
    - **Decay** -> decay rate of low frequencies -> affects incoming signal when Boom=0%; affects both incoming and processed when Boom>0%
    - **Boom Audition** (headphone icon) -> solos the bass enhancer output -> dial in Boom in isolation
    - **Bass Meter** -> visual feedback showing Boom's effect
  - **Dry/Wet** -> blend -> 100% for insert, 30-60% for parallel color
  - **Output Gain** -> post-processing level compensation
- **Presets:** Punchy, Warm, Tight, Boom Box, Crunch Time, Subtle
- **Reach for this when:** processing drum buses/groups, you want one-device drum coloring, you need sub reinforcement (Boom), you want quick transient shaping without a dedicated transient designer
- **Don't use when:** you need precise multiband dynamics (use Multiband Dynamics), you want transparent processing (use Compressor), you need frequency-specific transient control (use Re-Enveloper)
- **Pairs well with:** Glue Compressor (before or after for bus cohesion), EQ Eight (surgical corrections), Limiter (peak control after Drum Buss)
- **vs Glue Compressor on drums:** Drum Buss adds color, saturation, transient shaping, and bass enhancement. Glue Compressor adds cohesion and leveling. Use both: Drum Buss first for character, Glue Compressor after for glue.

---

### Impulse

- **Type:** Native Instrument
- **Load via:** `find_and_load_device("Impulse")`
- **What it does:** Classic 8-slot drum sampler with per-slot processing. Each slot has independent Stretch, Saturate, Filter, Pan, Volume, and envelope controls. Simpler than Drum Rack but faster for quick sketches. Samples auto-map to C3-C4 on the keyboard.
- **Signal flow:** Per Slot: Sample -> Start Offset -> Time Stretch -> Filter -> Saturator -> Decay Envelope -> Pan -> Volume -> Global Output
- **Key parameters (per slot):**
  - **Start** (0-100 ms offset) -> sample playback start position
  - **Transp** (Transpose, +-48 semitones) -> pitch shift -> can be modulated by velocity or random value
  - **Stretch** (-100% to +100%) -> time-stretch without pitch change -> negative = shorter, positive = longer
    - **Mode A** -> optimized for low sounds (kicks, toms, bass)
    - **Mode B** -> optimized for high sounds (hats, cymbals, snares)
  - **Filter Section:**
    - **Filter Type** -> multiple types for frequency shaping
    - **Frequency** -> where the filter is applied in the spectrum
    - **Resonance** -> boosts frequencies near cutoff point
    - Filter Frequency accepts velocity or random modulation
  - **Saturator:**
    - **Drive** -> adds distortion and fatness -> extreme settings on low-pitched sounds = overdriven analog synth drum character
  - **Envelope:**
    - **Decay** (up to 10.0 s) -> fade time
    - **Trigger Mode** -> sample decays with the note (one-shot behavior)
    - **Gate Mode** -> waits for Note Off before beginning decay (hold-to-play)
  - **Pan** -> stereo position -> modulated by velocity and random value
  - **Volume** -> output level -> modulated by velocity only
  - **Slot 8 Link** -> links Slot 8 with Slot 7 -> triggering one stops the other (built-in choke for open/closed hat)
- **Global controls:** Master Volume, master Transpose, global Time (scales all stretch and decay values)
- **MIDI mapping:** C3 = Slot 1 (leftmost), chromatically through C4 = Slot 8
- **Reach for this when:** quick drum sketching, 8 sounds or fewer, you want per-slot processing without the complexity of Drum Rack, live performance with velocity-sensitive processing
- **Don't use when:** you need more than 8 sounds, you need choke groups beyond Slot 7/8, you need send/return chains, you need macro control
- **vs Drum Rack:** Impulse is simpler (8 slots, fixed processing per slot). Drum Rack is infinitely extensible (128 pads, any devices, choke groups, sends/returns, macros). Use Impulse for sketches, Drum Rack for production.

---

## Max for Live Drum Tools

---

### AmenMachine (CLX_04)

- **Type:** M4L Instrument (User Library — CLX_04 collection)
- **Load via:** `find_and_load_device("AmenMachine")`
- **What it does:** Breakbeat slicer instrument designed for chopping and rearranging break loops, particularly the Amen break and similar breakbeats. Slices a loaded loop into segments and allows real-time rearrangement, stutter, and manipulation via MIDI triggering or internal sequencing.
- **Key features:**
  - Automatic transient-based slicing of loaded breakbeat loops
  - Real-time slice rearrangement and triggering via MIDI
  - Stutter and repeat effects for glitch/drill-style patterns
  - Pitch control per slice
  - Designed for jungle, drum and bass, breakcore, and any genre using chopped breaks
- **Reach for this when:** you want to chop and rearrange breakbeats in real time, jungle/DnB production, glitch percussion
- **Pairs well with:** Drum Buss (grit and punch), Saturator (tape warmth), Beat Repeat (additional stuttering)

---

### trnr.Hatster

- **Type:** M4L Instrument (TRNR)
- **Load via:** `find_and_load_device("Hatster")`
- **What it does:** Hi-hat synthesizer inspired by modular synthesizers. Uses a noise oscillator core fed into a modeled Low-Pass Gate (LPG) filter/VCA that reacts uniquely to each incoming hit, especially with velocity variation. All parameters can be modulated by integrated sine-wave LFOs for evolving hi-hat patterns.
- **Key parameters:**
  - **Noise Oscillator** -> core sound source
  - **LPG Filter/VCA** -> modeled Vactrol-style filter/amplifier -> natural, fluid character with velocity-dependent response
  - **Attack / Decay** -> shape the hit envelope
  - **LFO Modulation** -> separate sine-wave LFOs on all parameters -> creates evolving, non-repetitive hat patterns
  - **Velocity Sensitivity** -> LPG responds dynamically to velocity input -> softer hits = more muted/closed, harder hits = brighter/open
- **Pro version extras:** 3 distinct noise oscillators, tempo-synced LFOs, selectable LFO shapes, phase alignment control, linear/exponential/logarithmic envelope curves
- **Reach for this when:** you want modular-style hi-hats with natural velocity response and evolving LFO modulation
- **Pairs well with:** Step sequencers with velocity variation, Auto Pan (additional movement), Drum Buss

---

### trnr.Kickster

- **Type:** M4L Instrument (TRNR)
- **Load via:** `find_and_load_device("Kickster")`
- **What it does:** 4-operator FM synthesis kick drum synth with a uniquely shaped integrated envelope generator. Optimized for short, snappy kicks that leave room for other elements, but the tail can be extended for experimentation. The "boom" and "click" portions of the kick are independently controllable.
- **Key parameters:**
  - **Boom controls** -> shape the body/sub portion of the kick
  - **Click controls** -> shape the transient/attack portion
  - **6 main controls** -> streamlined interface covering the essential sound-shaping parameters
  - **Integrated envelope** -> unique compression-like shaping that makes the kick sound pre-processed
- **Reach for this when:** you need a synthesized techno/electronic kick with FM character, quick results with minimal controls
- **Pairs well with:** Drum Buss (additional punch), EQ Eight (surgical sub shaping), Saturator (harmonics)

---

### trnr.DmmG

- **Type:** M4L Audio Effect (TRNR)
- **Load via:** `find_and_load_device("DmmG")`
- **What it does:** Digital multi-mode gate audio effect. A logarithmic A/D envelope triggered by external MIDI opens the integrated VCA and VCF, letting you play an audio track like a subtractive synthesizer. Inspired by Vactrol filters/VCAs from modular synthesizers. Note: this is an audio effect, not an instrument — it processes existing audio.
- **Key parameters:**
  - **Highpass / Lowpass Filters** -> multi-mode filtering
  - **A/D Envelope** -> velocity-sensitive with logarithmic response
  - **External MIDI trigger** -> selectable MIDI track to trigger the envelope
  - **VCA** -> voltage-controlled amplifier gating
  - **VCF** -> voltage-controlled filter
- **Pro version extras:** Bandpass and Notch filters, resonance/drive/frequency inversion controls, toggles to add/remove VCA and VCF from signal chain, full ADSR envelope
- **Reach for this when:** you want to rhythmically gate audio using MIDI triggering, create subtractive synth-like drum processing, creative gating effects
- **Pairs well with:** Long sustained audio sources, reverb tails, noise textures as input

---

### drumk 2 (K-Devices)

- **Type:** M4L Instrument (K-Devices)
- **Load via:** `find_and_load_device("drumk 2")`
- **What it does:** Grid-based sample manipulation instrument for beat-oriented sound design. Uses a multislider grid where each step has independent parameters and playback modes. Supports 2 simultaneous samples with crossfade, 8 snapshots per preset with gesture morphing, and step-sequenced effects.
- **Key parameters:**
  - **Grid/Multislider System** -> per-step parameter editing for granular control over playback
  - **Envelope** -> per-slice waveform shaping with Peak and Shape generators
  - **XFade** -> interpolate amplitude between two loaded samples
  - **Playback Modes** -> various modes per step for different behaviors
  - **Randomization** -> random buttons, drunkwalk, walker mode, time variation probabilities
  - **Snapshots** -> up to 8 per preset with gesture-based morphing (up to 8 gestures)
  - **External Parameter Control** -> modulate up to 4 parameters in Live's GUI or third-party plugins
  - **Sync** -> slices triggered in sync with Live transport or via MIDI notes
- **Reach for this when:** experimental/glitch percussion, generative drum patterns, sample mangling, granular beat design
- **Pairs well with:** Return effects (reverb/delay for processed slices), Drum Buss (cohesion), Auto Filter (movement)

---

### Drum Articulate (Max for Cats)

- **Type:** M4L MIDI Effect
- **Load via:** `find_and_load_device("Drum Articulate")`
- **What it does:** MIDI effect for programming sophisticated drum articulations. Creates drum rolls, flams, random triggers, and complex rhythmic embellishments. Can be placed on individual Drum Rack pads for per-pad articulation, or globally on a whole kit. Also works with synths and effects.
- **Key features:**
  - **4 Triggers** -> each with freely adjustable delay time between triggers
  - **Quantized switch** -> auto-quantize trigger timing to Live's master tempo
  - **Flams** -> short delay between triggers creates natural flam articulation
  - **Rolls** -> rapid repeated triggers for drum rolls
  - **Random triggers** -> probabilistic triggering for humanized patterns
  - **Per-pad or global** -> place on individual Drum Rack pad chains or on the whole track
- **Reach for this when:** you need realistic drum articulations (flams, rolls, drags), humanized pattern programming, rhythmic embellishments
- **Pairs well with:** Drum Rack (on individual pad chains), Velocity MIDI effect (dynamic variation), any drum instrument

---

## Drum Kit Guide by Genre/Character

> Complete catalog of the 139 drum kits available in this installation. Kits are grouped by sonic character and intended genre. All are Drum Rack presets loaded via `find_and_load_device("Kit Name")`.

---

### Classic Drum Machine Kits

> Sampled recreations of iconic hardware drum machines. These kits replicate the tonal controls of the original units.

#### Roland TR-505 Kits
- **Sound:** Budget digital PCM drum machine (1986). Thin, crispy, lo-fi digital samples. Cheap and cheerful character — thinner than 707/909.
- **Genre:** Early house, synth-pop, lo-fi electronic, industrial
- **Kits:** 505 Core Kit
- **Character:** Brittle digital, narrow frequency range, nostalgic lo-fi charm

#### Roland TR-606 Kits
- **Sound:** Analog companion to the TB-303 Bassline (1981). Delicate, thin analog voices — lighter and more polite than the 808/909. Crisp hi-hats, gentle kick, snappy snare.
- **Genre:** Acid house (paired with 303), minimal techno, lo-fi electronic
- **Kits:** 606 Core Kit
- **Character:** Light analog, paired historically with acid basslines, understated

#### Roland TR-707 Kits
- **Sound:** Digital PCM samples of real drums (1984). Famous for booming tom-toms. Cleaner and more "real" sounding than purely analog machines, but with a distinctly 80s digital sheen.
- **Genre:** Early Chicago house, Italo disco, synth-pop, freestyle
- **Kits:** 707 Core Kit
- **Character:** Digital realism with 80s character, booming toms, clean

#### Roland TR-808 Kits
- **Sound:** The most iconic drum machine ever (1980). Fully analog synthesis — deep, booming kick that doubles as bass, crisp handclap, sizzling hi-hats, cowbell. The kick's long decay makes it function as a bass instrument.
- **Genre:** Hip-hop (foundational), trap, electro, Miami bass, boom bap, R&B, Latin freestyle
- **Kits:** 808 Core Kit
- **Character:** Deep sub kick, punchy snare/clap, iconic cowbell, warm analog — THE hip-hop drum machine

#### Roland TR-909 Kits
- **Sound:** Hybrid analog/digital (1983). Analog kick/snare/toms with 6-bit sampled cymbals and hi-hats. The kick is punchier and tighter than the 808, with less sub. The digital cymbals have a distinctive crunchy sizzle.
- **Genre:** Techno (definitive), house, trance, acid, EBM, industrial
- **Kits:** 909 Core Kit
- **Character:** Punchy analog body + gritty digital cymbals, the techno standard

#### Roland CR-78 Kits
- **Sound:** First programmable drum machine (1978). Delicate, almost childlike analog voices. Kicks that pop, hi-hats that sizzle, snares that politely spit. Warm and textured but not aggressive.
- **Genre:** New wave, synth-pop, post-punk, art rock, ambient
- **Kits:** C78 Core Kit
- **Character:** Vintage, delicate, warm, unobtrusive — carries the beat without getting in the way

#### Oberheim DMX Kits
- **Sound:** 8-bit PCM samples of real drums, companded to ~12-bit quality (1981). Punchy, funky, warm bass drum, crunchy snares, boxy toms. Humanizing features (rolls, flams, timing variations).
- **Genre:** Hip-hop (early, foundational alongside 808), new wave, synth-pop, dancehall reggae, electro-funk
- **Kits:** DMX Core Kit
- **Character:** Punchy and funky, warm and raw, the other hip-hop drum machine (alongside 808)

#### LinnDrum / LM-1 ER Kits
- **Sound:** First drum machine with digitally sampled real drums (1980/1982). 8-bit samples with distinctive "sizzle" from aliasing artifacts above Nyquist frequency. Very punchy and prominent. Individual voice tuning.
- **Genre:** 80s pop (Prince, Michael Jackson), synth-pop, new wave, R&B, funk
- **Kits:** ER Core Kit (Electronic Rhythm), LD Core Kit (LinnDrum)
- **Character:** Punchy 8-bit real drum samples, 80s pop definition, the Prince drum machine

---

### Electronic / Techno Kits

> Designed and processed kits optimized for electronic music production.

| Kit Name | Character | Best For |
|---|---|---|
| AG Techno Kit | Aggressive, hard-hitting, processed | Peak-time techno, hard techno |
| Beastly Kit | Heavy, distorted, aggressive | Industrial techno, hard dance |
| Chicago Kit | Classic house elements, warm | Chicago house, deep house |
| Clockwork Kit | Precise, mechanical, tight | Minimal techno, tech house |
| Control Kit | Clean, controlled, versatile | Tech house, minimal |
| Controller Kit | Digital, precise, modern | Contemporary electronic |
| Dirty South Kit | Gritty, heavy, Southern character | Dirty south hip-hop/electronic |
| Diskette Kit | Lo-fi digital, crunchy | Lo-fi house, retro electronic |
| Dub System Kit | Spacious, delayed, sub-heavy | Dub techno, dub house |
| Dusty Kit | Aged, gritty, textured | Lo-fi, chill beats |
| Electric Kit | Bright, snappy, electronic | Electro, synth-pop |
| Execute Kit | Hard, punchy, aggressive | Hard techno, industrial |
| Gritter Kit | Gritty, distorted, rough | Industrial, noise-influenced |
| Headroom Kit | Clean, dynamic, spacious | House, techno, any electronic |
| Interface Kit | Clean, digital, precise | IDM, experimental electronic |
| Jackpot Kit | Fun, energetic, bright | Disco house, nu-disco |
| Kit-1 Analog Core | Pure analog synthesis | Analog-focused electronic |
| Kit-1 Dub Plates | Dub-influenced, spacious | Dub techno, dub |
| Kit-1 Elektro | Electro character, punchy | Electro, breakbeat |
| Kit-1 FM Kinetic | FM synthesis, metallic | IDM, experimental |
| Kit-1 Get Down | Funky, groovy | Disco, funk-influenced electronic |
| Kit-1 Kraft | Kraftwerk-inspired, minimal | Minimal electronic, synth-pop |
| Kit-1 Stripped | Minimal, clean, essential | Minimal techno/house |
| Kit-2 House | Classic house drums | House, deep house |
| Kit-2 Techno | Classic techno drums | Techno, tech house |
| Kit-3 Session | Live/electronic hybrid | Live electronic, crossover |
| Loose Kit | Relaxed timing feel, swing | Hip-hop, boom bap, neo-soul |
| Mainframe Kit | Digital, computational | IDM, glitch, experimental |
| Plastique Kit | Synthetic, plastic-like | Electro-pop, synth-pop |
| Probe Kit | Exploratory, unusual timbres | Experimental, sound design |
| Real Loud Kit | Maximized, compressed, loud | EDM, festival-style |
| Schematic Kit | Technical, precise, clean | Tech house, minimal |
| Servo Kit | Mechanical, robotic | Industrial, EBM |
| Sharp Kit | Bright, cutting, transient-focused | Any electronic needing presence |
| Surface Kit | Textured, layered | Ambient electronic, textural |
| Switches Kit | Glitchy, digital artifacts | Glitch, IDM |
| Synth Lab Kit | Synthesized, experimental | Sound design, experimental |
| Tandem Kit | Layered, paired sounds | Any electronic |
| Tangent Kit | Angular, unusual | Experimental, art electronic |
| Transit Kit | Movement, evolving | Progressive electronic |
| Warehouse Kit | Raw, spacious, reverberant | Warehouse techno, rave |
| Wire Kit | Metallic, thin, high-frequency | Industrial, noise, experimental |

---

### Hip-Hop / Boom Bap Kits

| Kit Name | Character | Best For |
|---|---|---|
| Boom Bap Kit | Classic SP-1200/MPC style, crunchy | 90s boom bap, golden era hip-hop |
| Heritage Kit | Vintage, warm, soulful samples | Sample-based hip-hop, neo-soul |
| Street Mind Kit | Gritty, urban, hard | East coast hip-hop, grime |
| Loose Kit | Swung, relaxed, humanized | Boom bap, lo-fi hip-hop |
| Dirty South Kit | Heavy, sub-focused, gritty | Southern hip-hop, crunk |
| Dusty Kit | Aged, vinyl-textured, lo-fi | Lo-fi hip-hop, chill beats |

---

### Acoustic / Live Kits

| Kit Name | Character | Best For |
|---|---|---|
| Dry Session Kit | Close-miked, tight, no room | Pop, rock, R&B, singer-songwriter |
| Gen Purpose Kit | Versatile, balanced, neutral | Any genre needing realistic drums |
| Plymouth Kit | Warm, mid-focused, vintage | Indie, folk-rock, singer-songwriter |
| Kit-3 Session | Acoustic/electronic hybrid | Live electronic, crossover |

---

### Experimental / Artist Kits

> Signature kits by guest artists and sound designers with distinctive sonic identities.

| Kit Name | Artist/Designer | Character | Best For |
|---|---|---|---|
| Epistrophe Kit | Ivo Ivanov | Field recordings, found sounds, concrete | Musique concrete, experimental, ambient |
| Minimal Berlin Drums | Bobinger | Ultra-minimal, clinical, Berlin aesthetic | Berlin minimal techno, microhouse |
| Sinner Rack | Piezo | Distorted, harsh, uncompromising | Industrial, noise, experimental |

---

### MPE-Enabled Kits

> Drum Racks with MPE (MIDI Polyphonic Expression) support. Respond to per-note pressure, slide, and pitch bend for expressive drum performance.

| Kit Name | Character | Best For |
|---|---|---|
| MPE Analog Kit | Analog synth drums with MPE response | Expressive performance, Push 3 |
| MPE Meld Kit | Meld synth-based drums with MPE | Textural, evolving drum sounds |
| MPE Synth Lab Kit | Synthesized drums with full MPE control | Sound design, experimental performance |

---

### User-Created Kits

> Custom kits created by the user. Sonic character varies — inspect contents in Drum Rack to understand what is loaded.

| Kit Name | Notes |
|---|---|
| clan kit | User custom |
| ioi kit | User custom |
| kok kit | User custom |
| non kit | User custom |
| ooo kit | User custom |
| zzon kit | User custom |

---

## Quick Decision Matrix

### "I need a kick drum"

| Situation | Device | Why |
|---|---|---|
| Deep 808 sub kick | DS Kick (long Decay, high Env) | Sine-based, sub-focused |
| Punchy techno kick | trnr.Kickster | FM synthesis, pre-shaped envelope |
| Sampled acoustic kick | Drum Sampler + kick sample | Full sample control with Punch effect |
| Quick electronic kick | DS Kick (short Decay, Click ON) | Fast, no fuss |
| Layered production kick | Drum Rack (multiple chains on one pad) | Sub + body + click layers |

### "I need hi-hats"

| Situation | Device | Why |
|---|---|---|
| Classic electronic hats | DS HH (2 instances, choke group) | Quick, chokeable open/closed pair |
| Evolving modular-style hats | trnr.Hatster | LPG + LFO modulation |
| Sampled acoustic/processed hats | Drum Sampler + hat samples | Sample-based with effects |
| Glitchy hat patterns | drumk 2 with hat sample | Grid-based manipulation |

### "I need a snare"

| Situation | Device | Why |
|---|---|---|
| Electronic noise snare | DS Snare (high Tone) | Noise-dominated synthesis |
| Acoustic body snare | DS Snare (low Tone, tune the body) | Pitched oscillator focus |
| Sampled snare with processing | Drum Sampler + 8-Bit or Punch effect | Sample + built-in coloring |
| Layered snare with flam | Drum Articulate MIDI FX -> DS Snare | Articulation control |

### "I need to process my drum bus"

| Situation | Device | Why |
|---|---|---|
| Quick color and punch | Drum Buss | All-in-one: drive, transients, boom |
| SSL-style bus glue | Glue Compressor | Musical cohesion |
| Sub reinforcement only | Drum Buss (Boom section, Drive off) | Resonant bass enhancer |
| Transparent leveling | Compressor (RMS mode, gentle ratio) | Clinical dynamics |
| Transient emphasis + saturation | Drum Buss (Transients positive, Crunch up) | Combined processing |

### "I need percussion"

| Situation | Device | Why |
|---|---|---|
| Cowbell / clave | DS Clang | Two-tone metallic synth with Clave mode |
| FM metallic percussion | DS FM | DX7-style tuned percussion |
| Tom fills | DS Tom | Tunable pitched toms |
| Breakbeat chops | AmenMachine | Slice and rearrange breaks |
| Complex articulations | Drum Articulate -> any drum | Flams, rolls, random triggers |

### "Which drum machine kit do I pick?"

| Genre | First Choice Kit | Runner-Up |
|---|---|---|
| Hip-hop / Trap | 808 Core Kit | Boom Bap Kit |
| Techno | 909 Core Kit | AG Techno Kit |
| House | Chicago Kit | Kit-2 House |
| Minimal | Clockwork Kit | Minimal Berlin Drums |
| Lo-fi / Chill | Dusty Kit | Loose Kit |
| Synth-pop / New Wave | C78 Core Kit | 707 Core Kit |
| Industrial | Beastly Kit | Execute Kit |
| DnB / Jungle | AmenMachine + 909 hats | Warehouse Kit |
| Experimental | Epistrophe Kit | Probe Kit |
| Electro | Kit-1 Elektro | DMX Core Kit |
| Pop / Acoustic | Dry Session Kit | Gen Purpose Kit |
| Dub | Dub System Kit | Kit-1 Dub Plates |
| 80s Pop | ER Core Kit / LD Core Kit | 707 Core Kit |

---

## LivePilot Integration Notes

### Loading Drums
```
# Load a complete drum kit
find_and_load_device("808 Core Kit")

# Load a DS synth onto a specific Drum Rack pad
# First load Drum Rack, then load DS device into a pad chain
find_and_load_device("Drum Rack")
find_and_load_device("DS Kick")  # loads into selected pad

# Load Drum Buss on the drum group bus
find_and_load_device("Drum Buss")
```

### Programming Drums
```
# Standard drum note mapping (GM-compatible)
# C1 (36) = Kick
# D1 (38) = Snare
# E1 (40) = Low Tom
# F1 (41) = Mid Tom
# F#1 (42) = Closed HH
# A1 (45) = High Tom
# A#1 (46) = Open HH
# C#2 (49) = Crash
# D#2 (51) = Ride
# D#1 (39) = Clap / Rimshot

# Add a kick pattern (quarter notes in 4/4, 1 bar)
add_notes(track=0, clip=0, notes=[
    {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 100},
    {"pitch": 36, "start_time": 1.0, "duration": 0.25, "velocity": 100},
    {"pitch": 36, "start_time": 2.0, "duration": 0.25, "velocity": 100},
    {"pitch": 36, "start_time": 3.0, "duration": 0.25, "velocity": 100}
])
```

### Setting Device Parameters
```
# Drum Buss example: punchy drums with sub boost
set_device_parameter(track=0, device=1, parameter="Drive", value=0.4)
set_device_parameter(track=0, device=1, parameter="Crunch", value=0.3)
set_device_parameter(track=0, device=1, parameter="Transients", value=0.5)
set_device_parameter(track=0, device=1, parameter="Boom", value=0.6)
set_device_parameter(track=0, device=1, parameter="Freq", value=60)

# DS Kick: 808-style sub kick
set_device_parameter(track=0, device=0, parameter="Pitch", value=48)
set_device_parameter(track=0, device=0, parameter="Env", value=0.7)
set_device_parameter(track=0, device=0, parameter="Decay", value=0.8)
set_device_parameter(track=0, device=0, parameter="Drive", value=0.2)
```

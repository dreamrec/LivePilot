# MIDI Tools — Device Atlas

> 45 devices: 13 Native MIDI Effects + 12 All MIDI Tools (Meyer) + 5 J74 Suite + 7 CLX_03 LDM/zsteinkamp + 4 Soundmanufacture + 4 Generative

---

## Native Ableton MIDI Effects

---

### Arpeggiator
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Arpeggiator")`
- **What it does:** Takes held notes/chords and plays them as a rhythmic pattern, cycling through pitches in the chosen style at the set rate.
- **Key parameters:**
  - **Style** — Up, Down, UpDown, DownUp, Converge, Diverge, Con+Diverge, PinkyUp, PinkyUpDown, ThumbUp, ThumbUpDown, Play Order, Chord Trigger, Random, Random Other, Random Once. Sweet spot: *Random Other* for melodies that don't repeat until all notes are used; *Converge* for cinematic builds.
  - **Rate** — 1/1 to 1/128 (synced) or 10-1000ms (free). Sweet spot: 1/16 for standard arps, 1/8T for shuffle feel.
  - **Gate** — 1-200%. Controls note overlap. >100% = legato. Sweet spot: 80% for staccato plucks, 130% for pads.
  - **Steps** — How many times the pattern transposes. 1-2 for guitar strums, higher for cascading sequences.
  - **Distance** — Transposition per step in semitones or scale degrees. +12 for octave jumps, +7 for fifths.
  - **Repeats** — Number of pattern repeats (default infinite). 1-2 emulates guitar strumming.
  - **Retrigger** — Off / Note / Beat. Beat retrigger resyncs on downbeats.
  - **Velocity Decay/Target** — Shape dynamics over time. Decay fades velocity; Target pulls toward a fixed value.
  - **Hold** — Pattern continues after key release until new key pressed.
  - **Groove** — Apply groove patterns with Amount control.
- **Use cases:** Classic trance arps, guitar strums, generative ambient sequences, EDM risers.
- **Reach for this when:** "arpeggiate", "arp", "strum", "cycle through notes", "sequence a chord".
- **Pairs well with:** Scale (constrain pitches), Note Echo (add repeats), Chord (build input chords), any synth pad.
- **vs Note Echo:** Arpeggiator cycles through chord *tones*; Note Echo repeats the *same note* with decay.

---

### Chord
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Chord")`
- **What it does:** Adds up to 6 parallel notes (intervals) to every incoming MIDI note, instantly building chords from single keys.
- **Key parameters:**
  - **Shift 1-6** — Each adds a note at +/-36 semitones (or scale degrees with Use Current Scale). Set to +4, +7 for major triads; +3, +7 for minor.
  - **Velocity 1-6** — 1-200% relative velocity per added note. Lower velocities on upper notes create natural voicings.
  - **Chance 1-6** — 0-100% probability each note fires. 50-80% adds organic variation.
  - **Strum** — 0-400ms delay between notes. 20-60ms for guitar-like strums.
  - **Tension** — Accelerates/decelerates strum speed. Positive = accelerating (natural pick attack).
  - **Crescendo** — Velocity ramp across strummed notes. Positive = louder on later notes.
  - **Learn** — Capture chord from MIDI controller input.
- **Use cases:** One-finger chord playing, parallel harmony, power chords, cluster voicings, strum emulation.
- **Reach for this when:** "add harmony", "build chords", "parallel thirds", "octave double", "power chord".
- **Pairs well with:** Scale (keep chords diatonic), Arpeggiator (arpeggiate built chords), Velocity (shape dynamics).
- **vs Chord-O-Mat 3:** Native Chord adds fixed intervals; Chord-O-Mat knows scale degrees and maps diatonic chords to single keys.

---

### Note Echo
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Note Echo")`
- **What it does:** Creates MIDI note echoes (delays) with pitch transposition and velocity decay per repeat. The MIDI equivalent of a delay effect.
- **Key parameters:**
  - **Input** — Thru (original + echoes) or Mute (echoes only).
  - **Pitch** — Transposition per echo in semitones. +12 for octave-climbing echoes, +/-7 for fifths.
  - **Delay** — Echo time (synced divisions or ms). 1/8 or 1/16 most common.
  - **Feedback** — Number of repeats (higher = more echoes). 4-6 for rhythmic interest, 8+ for washy trails.
  - **Velocity** — Velocity decay per echo. Lower values = faster fadeout.
  - **MPE Toggle** — Echoes MPE data (Press, Slide, Note PB) with independent feedback amounts per dimension.
- **Use cases:** Rhythmic MIDI delays, dub-style echoes, pitch-shifting cascades, polyrhythmic fills, ambient trails.
- **Reach for this when:** "echo", "midi delay", "repeat notes", "cascading", "dub delay".
- **Pairs well with:** Scale (keep echoes in key), Velocity (shape echo dynamics), any melodic instrument.
- **vs Fibonacci/Fractal Note Echo (zsteinkamp):** Native is regular spacing; Fibonacci/Fractal use mathematical sequences for organic, non-uniform timing.

---

### Note Length
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Note Length")`
- **What it does:** Forces all MIDI notes to a specific duration regardless of how long keys are held, or triggers on note-off events.
- **Key parameters:**
  - **Trigger** — Note On or Note Off. Note Off mode enables release-based triggering (useful for ghost notes, percussion).
  - **Mode** — Time (ms) or Sync (beat divisions).
  - **Length** — Duration value. 50-100ms for percussion, 1/4-1/2 for sustained pads.
  - **Gate** — Percentage of length value. 50% for staccato, 100% for full sustain.
  - **Latch** — Sustains notes until next trigger (infinite sustain mode).
  - **Release Velocity** (Note Off mode) — Balance between Note On/Off velocities.
  - **Decay Time** (Note Off mode) — Velocity fade from Note On to Note Off.
  - **Key Scale** (Note Off mode) — Lower notes = longer, higher = shorter (or inverted).
- **Use cases:** Uniform note lengths for sequenced patterns, percussion gate control, sustain-pedal-free pad holds, note-off triggering for creative rhythm.
- **Reach for this when:** "make all notes same length", "staccato", "gate", "sustain", "trigger on release", "latch".
- **Pairs well with:** Arpeggiator (control arp note lengths), Velocity (shape attack/release feel).
- **vs Gate in Arpeggiator:** Note Length is standalone and works on any MIDI; Arpeggiator Gate only affects arpeggiated notes.

---

### Pitch
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Pitch")`
- **What it does:** Transposes all incoming MIDI notes by a fixed interval. Simplest pitch-shifting tool.
- **Key parameters:**
  - **Pitch** — +/-128 semitones (or +/-30 scale degrees with Use Current Scale). +12 = octave up, +7 = fifth up.
  - **Step Up/Down** — Buttons for incremental transposition by Step Width amount.
  - **Step Width** — 1-48 semitones per step. Set to 12 for octave stepping.
  - **Lowest** — Bottom note boundary for range filtering.
  - **Range** — Span of notes affected (from Lowest). Notes outside range: Block (mute), Fold (wrap), or Limit (clamp).
- **Use cases:** Octave layering, quick key changes, range-limited transposition for creative remapping.
- **Reach for this when:** "transpose", "octave up/down", "shift pitch", "change key".
- **Pairs well with:** Scale (correct after transposition), Chord (stack with transposed layers).
- **vs Scale:** Pitch shifts everything uniformly; Scale remaps out-of-key notes to fit.

---

### Random
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Random")`
- **What it does:** Randomly alters pitch of incoming MIDI notes within a defined range and probability.
- **Key parameters:**
  - **Chance** — 0-100% probability of randomization. 0% = pass-through, 100% = every note randomized. Sweet spot: 30-60% for subtle variation.
  - **Choices** — 1-24 possible random pitch outcomes.
  - **Interval** — Pitch spacing between choices (in semitones or scale degrees).
  - **Mode** — Random (true random) or Alt (round-robin cycling through choices).
  - **Sign** — Add (higher only), Sub (lower only), Bi (both directions).
  - **Use Current Scale** — Constrains random choices to scale degrees.
- **Use cases:** Generative melodies, adding human imperfection, probability-based variations, aleatoric composition.
- **Reach for this when:** "randomize", "add randomness", "generative melody", "unpredictable", "chance-based".
- **Pairs well with:** Scale (constrain randomness to key), Velocity (randomize dynamics too), Arpeggiator.
- **vs DEVIATE:** Random is single-parameter (pitch only); DEVIATE transforms entire MIDI clips across all note attributes.

---

### Scale
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Scale")`
- **What it does:** Forces all incoming MIDI notes into a specific musical scale by remapping out-of-scale notes to the nearest in-scale pitch.
- **Key parameters:**
  - **Base** — Root note of the scale (C through B).
  - **Scale Name** — Predefined scales (Major, Minor, Dorian, Mixolydian, Pentatonic, etc.) or User-defined.
  - **Note Matrix** — 13x13 grid for custom pitch remapping. Each input pitch maps to a specific output pitch.
  - **Transpose** — +/-36 semitones global shift.
  - **Lowest / Range** — Limit which octaves are affected.
  - **Fold** — Auto-fold notes exceeding 6-semitone remapping distance.
- **Use cases:** Force any MIDI to a key, jam without wrong notes, quantize generative output, modal exploration.
- **Reach for this when:** "force to scale", "keep in key", "scale lock", "no wrong notes", "constrain to scale".
- **Pairs well with:** Random (constrain random output), Arpeggiator, Chord, any generative M4L device.
- **vs Scale-O-Mat (Soundmanufacture):** Native Scale works per-track; Scale-O-Mat controls ALL Scale devices project-wide from one interface with 128 presets.

---

### Velocity
- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Velocity")`
- **What it does:** Reshapes MIDI velocity values through curve manipulation, compression, expansion, randomization, and range limiting.
- **Key parameters:**
  - **Operation** — Process Note On, Note Off, or both.
  - **Mode** — Clip (clamp to range), Gate (block notes outside range), Fixed (all notes same velocity).
  - **Lowest / Range** — Input velocity range (X-axis).
  - **Out Low / Out Hi** — Output velocity range (Y-axis).
  - **Drive** — Push velocities toward extremes. Positive = louder, negative = softer. Sweet spot: +20 for punchier drums.
  - **Compand** — Above 0 = expand (more dynamic range), below 0 = compress. Sweet spot: -30 for more consistent dynamics.
  - **Random** — Add random velocity variation. 10-20 for humanization, 40+ for dramatic variation.
- **Use cases:** Normalize velocity, add dynamics, humanize quantized parts, velocity gating, consistent drum hits.
- **Reach for this when:** "velocity", "dynamics", "humanize", "make louder/softer", "even out velocity", "random dynamics".
- **Pairs well with:** Note Length (combined velocity + duration shaping), Arpeggiator (shape arp dynamics).
- **vs Feel (Meyer):** Velocity shapes dynamics globally; Feel adjusts microtiming for groove.

---

### CC Control
- **Type:** Native (Live 12+)
- **Load via:** `find_and_load_device(track_index, "CC Control")`
- **What it does:** Sends and automates MIDI CC messages to hardware synths, software instruments, or other MIDI devices. A dedicated CC automation surface.
- **Key parameters:**
  - **Mod Wheel** — CC 1 control.
  - **Pitch Bend** — Pitch bend range.
  - **Pressure** — Channel aftertouch/pressure.
  - **Custom A** — On/off button (default CC 64 sustain, reassignable).
  - **Custom B-M** — 12 knobs, each assignable to any CC number via dropdown.
  - **Controls 1-8 / 9-16** — Title bar toggle to show two banks of controls.
  - **Learn** — Map incoming CC from hardware controller.
  - **Send** — Transmit all current CC values at once (useful for initializing hardware state).
- **Use cases:** Hardware synth parameter control, CC automation lanes, initializing external gear, filter sweeps on hardware.
- **Reach for this when:** "send CC", "control hardware", "MIDI CC automation", "external synth", "mod wheel".
- **Pairs well with:** External Instrument (route audio back), any hardware synth or external MIDI device.
- **vs Expression Control:** CC Control sends CC messages; Expression Control maps incoming MIDI expressions to Live parameters.

---

### Expression Control
- **Type:** Native (Live 12+)
- **Load via:** `find_and_load_device(track_index, "Expression Control")`
- **What it does:** Maps incoming MIDI expression data (velocity, mod wheel, pitch bend, aftertouch, keytrack) to any parameter in your Live set with custom transformation curves.
- **Key parameters:**
  - **Input Sources** — Velocity, Modwheel, Pitchbend, Pressure (aftertouch), Keytrack, Expression, Random, Increment, Slide, Sustain.
  - **5 assignment rows** — Each selects an input source and maps to a Live parameter.
  - **Map switch** — Click to assign target parameter.
  - **Min / Max** — Output range scaling per mapping.
  - **Log / Lin** — Logarithmic or linear response curve.
  - **Rise / Fall** — Smoothing for attack and release of the modulation signal.
- **Use cases:** Velocity-to-filter mapping, mod wheel expression, aftertouch control, pitch-tracking filter, MPE integration.
- **Reach for this when:** "map velocity to", "expression", "mod wheel controls", "aftertouch mapping", "MPE".
- **Pairs well with:** Any instrument or effect with automatable parameters, MPE controllers (Seaboard, Linnstrument).
- **Limitation:** Monophonic with last-note priority when controlling effects.
- **vs Shaper MIDI:** Expression Control maps *incoming* MIDI data; Shaper MIDI generates its *own* modulation envelopes.

---

### Shaper MIDI
- **Type:** Native (Live 12+)
- **Load via:** `find_and_load_device(track_index, "Shaper MIDI")`
- **What it does:** Generates custom multi-breakpoint modulation envelopes that can be mapped to up to 8 parameters. Triggered by MIDI notes or free-running.
- **Key parameters:**
  - **Breakpoint display** — Click to add points, Shift-click to delete, Alt/Option-drag for curves.
  - **Map (x8)** — Up to 8 parameter mappings via Multimap button.
  - **Min / Max** — Output range per mapping.
  - **Offset** — Takes over mapped parameter's current value as modulation center.
  - **Rate** — LFO speed in Hz (free) or beat divisions (synced).
  - **Echo** — Amount of envelope echo/feedback.
  - **Time** — Echo time in ms.
  - **Loop** — Loop envelope while MIDI note held.
  - **Sync** — Lock to tempo.
- **Use cases:** Custom LFO shapes, rhythmic parameter modulation, MIDI-triggered filter sweeps, sidechain-like pumping via mapping.
- **Reach for this when:** "custom modulation shape", "draw LFO", "parameter automation", "rhythmic modulation", "envelope follower on MIDI".
- **Pairs well with:** Any instrument or effect parameter, Arpeggiator (modulate while arpeggiated).
- **vs Expression Control:** Shaper MIDI *generates* modulation; Expression Control *routes* incoming MIDI data.

---

### Envelope MIDI
- **Type:** Native (Live 12+)
- **Load via:** `find_and_load_device(track_index, "Envelope MIDI")`
- **What it does:** Generates ADSR-style or custom envelopes triggered by MIDI notes, outputting modulation data to mapped parameters. Velocity-sensitive envelope shaping.
- **Key parameters:**
  - **Attack / Decay / Sustain / Release** — Standard ADSR envelope controls.
  - **Map** — Assign to any Live parameter.
  - **Min / Max** — Output range scaling.
  - **Velocity Switch** — When enabled, note velocity modulates envelope intensity.
  - **Amount** — Velocity modulation depth.
  - **Loop** — Cycle the envelope.
- **Use cases:** MIDI-triggered volume swells, filter envelopes independent of synth, velocity-sensitive modulation, pluck-like parameter animation.
- **Reach for this when:** "envelope", "ADSR modulation", "velocity-sensitive control", "pluck shape", "swell".
- **Pairs well with:** Any synth/effect parameter, Velocity (pre-shape velocity before envelope).
- **vs Shaper MIDI:** Envelope MIDI is ADSR-focused with velocity sensitivity; Shaper MIDI is freeform breakpoint drawing.

---

### MIDI Monitor
- **Type:** Native (M4L, included with Suite)
- **Load via:** `find_and_load_device(track_index, "MIDI Monitor")`
- **What it does:** Displays incoming MIDI data in real time for debugging. Shows notes, velocities, CCs, pitch bend, aftertouch, and MPE data.
- **Key parameters:**
  - **Note Display** — Keyboard layout showing incoming notes, root note, and chord detection.
  - **Flow Diagram** — Continuous scrolling list of all MIDI events (notes, CC, pitch bend, aftertouch).
  - No effect on MIDI signal — pass-through only.
- **Use cases:** Debugging MIDI controller connections, verifying CC assignments, checking MIDI routing, confirming MPE data.
- **Reach for this when:** "debug MIDI", "check what's coming in", "MIDI not working", "verify controller", "monitor".
- **Pairs well with:** Place anywhere in MIDI chain to inspect signal at that point.
- **vs External MIDI monitors:** Integrated in Live, no external software needed.

---

## All MIDI Tools Bundle (Meyer Devices)

> 12 Live 12 MIDI Tools by Philip Meyer. 6 generators + 6 transformers. Operate on clips via the MIDI Tools framework (not real-time MIDI effects).

---

### Blocks
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Generates rhythms using additive/proportional divisions of the clip length, creating uneven time segments that produce complex rhythmic patterns.
- **Key parameters:**
  - **Block proportions** — Define relative sizes of rhythmic cells. E.g., 3:2:1 creates three blocks of decreasing length.
  - **Pitch / Velocity** — Assignable per block.
  - **Fill mode** — How notes populate each block.
- **Use cases:** Polymetric percussion, West African/Carnatic-inspired additive rhythms, irregular time signatures.
- **Reach for this when:** "additive rhythm", "uneven divisions", "proportional beat", "complex time".
- **Pairs well with:** Feel (add groove to generated blocks), Polyrhythm (layer on top).
- **vs Polyrhythm:** Blocks creates *one* pattern from proportions; Polyrhythm layers *multiple independent* patterns.

---

### Condition Transform
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Selectively transforms notes that match specific conditions (pitch range, velocity range, duration, probability). Non-matching notes are left untouched.
- **Key parameters:**
  - **Condition selectors** — Filter by pitch, velocity, duration, position, probability.
  - **Transform actions** — Ratchet, subdivide, delete, transpose, velocity shift.
  - **Probability** — Per-condition chance of transformation firing.
- **Use cases:** Add ratchets only to hi-hats, transpose only low-velocity notes, probabilistic ghost notes.
- **Reach for this when:** "transform only some notes", "conditional edit", "selective ratchet", "probability per note".
- **Pairs well with:** Segment (duration-based selection), Pattern Transform (broader variation).
- **vs Pattern Transform:** Condition Transform targets *specific notes* by attribute; Pattern Transform creates *global variations*.

---

### Develop
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Gradually increases or decreases pattern complexity over successive loop iterations. Notes appear or disappear each cycle.
- **Key parameters:**
  - **Direction** — Build up (add notes) or break down (remove notes).
  - **Rate** — How many notes change per loop.
  - **Order** — Which notes appear/disappear first (random, low-to-high, etc.).
- **Use cases:** Arrangement builds, gradual breakdowns, evolving loops, tension/release over time.
- **Reach for this when:** "build up gradually", "evolve pattern", "add notes over time", "strip down".
- **Pairs well with:** Any generator (Polyrhythm, Turing Machine) to evolve their output.
- **vs DEVIATE (Novel Music):** Develop is deterministic build/strip; DEVIATE is stochastic variation.

---

### Divs
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Subdivides existing notes into ratchets, tuplets, and nested rhythmic patterns. Takes a note and splits it into faster subdivisions.
- **Key parameters:**
  - **Division** — 2, 3, 4, 5, 6, etc. (tuplets, triplets, quintuplets).
  - **Nesting** — Apply subdivisions within subdivisions.
  - **Velocity curve** — Shape dynamics across subdivisions (accent first, decay, random).
- **Use cases:** Drum ratchets, glitchy subdivisions, EDM fills, rhythmic ornamentation, tuplet generation.
- **Reach for this when:** "ratchet", "subdivide", "tuplets", "make notes faster", "fill", "rolls".
- **Pairs well with:** Condition Transform (subdivide only certain notes), Feel (groove the result).
- **vs Note Length:** Divs *creates new notes* by subdivision; Note Length *changes duration* of existing notes.

---

### Draw
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Fast mouse-based editor for painting pitch, velocity, and chance values across notes in a clip.
- **Key parameters:**
  - **Mode** — Pitch, Velocity, or Chance drawing.
  - **Brush** — Paint values by dragging across notes.
  - **Snap** — Quantize drawn values to grid or scale.
- **Use cases:** Quick velocity curves, pitch melody drawing, probability painting, rapid prototyping.
- **Reach for this when:** "draw velocity curve", "paint pitches", "quick edit", "mouse-draw melody".
- **Pairs well with:** Any generator (edit output), Scale (constrain drawn pitches).

---

### Feel
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Applies swing and microtiming adjustments. Basic mode is a simple swing knob; Advanced mode offers per-step timing offsets.
- **Key parameters:**
  - **Basic mode** — Swing amount (0-100%). 55-65% for subtle groove.
  - **Advanced mode** — Per-step timing offsets with visual grid.
  - **Template** — MPC, TR-808, custom feel presets.
- **Use cases:** Add groove to quantized parts, MPC swing, humanization, J Dilla-style timing.
- **Reach for this when:** "swing", "groove", "humanize timing", "feel", "MPC groove", "make it less robotic".
- **Pairs well with:** Any generated/quantized pattern, Velocity (combine timing + dynamics humanization).
- **vs Native Groove Pool:** Feel operates as a MIDI Tool on clip data; Groove Pool applies globally with less granularity.

---

### Pattern Transform
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Multi-function clip variation tool. Adjusts density, adds/removes notes, creates melodic variations while respecting harmonic constraints.
- **Key parameters:**
  - **Density** — Increase or decrease note count.
  - **Variation** — Amount of melodic/rhythmic deviation.
  - **Pitch constraint** — Lock to scale for harmonic safety.
  - **Seed** — Deterministic randomization (same seed = same result).
- **Use cases:** Generate B-sections from A-sections, create fills, instant variations for arrangement.
- **Reach for this when:** "create variation", "make it different but similar", "new version of this pattern".
- **Pairs well with:** Condition Transform (targeted), Develop (over time), any MIDI clip.
- **vs Condition Transform:** Pattern Transform modifies the *whole pattern*; Condition Transform targets *specific notes*.

---

### Phase Pattern
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Creates accelerating/decelerating rhythmic patterns (bouncing ball, phase shifting) by warping note timing.
- **Key parameters:**
  - **Phase amount** — Degree of time-warping.
  - **Direction** — Accelerating or decelerating.
  - **Shape** — Linear, exponential, bouncing ball.
- **Use cases:** Bouncing ball fills, Steve Reich-style phasing, drum fills with acceleration, riser effects.
- **Reach for this when:** "bouncing ball", "accelerating rhythm", "phase shift", "Steve Reich".
- **Pairs well with:** Divs (subdivide then phase), any percussion part.
- **vs G_Delay (LDM):** Phase Pattern warps *clip timing*; G_Delay creates *real-time* bouncing ball echoes.

---

### Polyrhythm
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Multi-track algorithmic sequencer where each pattern has independent length, creating polyrhythmic relationships.
- **Key parameters:**
  - **Tracks** — Multiple independent sequences.
  - **Steps per track** — Independent length (up to 64).
  - **Algorithm** — Euclidean (evenly distributed) or Omni (any pattern up to 16 steps).
  - **Pitch / Velocity** — Per-step control.
  - **Rotation** — Shift pattern start point.
- **Use cases:** Polymetric drum patterns, evolving loops that don't repeat quickly, Euclidean beats, West African cross-rhythms.
- **Reach for this when:** "polyrhythm", "euclidean", "different lengths", "cross-rhythm", "evolving beat".
- **Pairs well with:** Feel (groove the output), Develop (build up complexity), drum racks.
- **vs Euclidean Sequencer Pro (Alkman):** Polyrhythm is a MIDI Tool (clip-based); Alkman's is a real-time M4L device with live voice routing.

---

### Segment
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Combines Divs and Condition Transform — selects notes by duration then applies subdivision and transformation.
- **Key parameters:**
  - **Duration filter** — Select notes by length (short, medium, long).
  - **Subdivision** — Divide selected notes.
  - **Transform** — Apply velocity/pitch changes to segments.
- **Use cases:** Target long notes for subdivision, process short notes differently, duration-aware clip editing.
- **Reach for this when:** "edit notes by length", "subdivide only long notes", "duration-based transform".
- **Pairs well with:** Condition Transform (combine criteria), Divs (pure subdivision).

---

### Shift
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Rotates note attributes independently — shift pitch sequence without moving rhythm, or rotate rhythm without changing pitches.
- **Key parameters:**
  - **Attribute** — Pitch, Velocity, Duration, Position, Chance.
  - **Offset** — Number of steps to rotate.
  - **Direction** — Forward or backward.
- **Use cases:** Create variations by pitch rotation, rhythmic remix by position shift, polymetric offset effects.
- **Reach for this when:** "rotate pitch", "shift rhythm", "offset melody", "remix clip attributes".
- **Pairs well with:** Any generated pattern, Pattern Transform (broader variation).
- **vs Phase Pattern:** Shift rotates *discretely by steps*; Phase Pattern warps *continuous timing*.

---

### Turing Machine
- **Type:** M4L User (All MIDI Tools)
- **Load via:** MIDI Tools panel in clip view
- **What it does:** Emulates the Music Thing Modular Turing Machine — uses a 16-bit shift register with controllable randomness to generate evolving pitch and rhythm sequences.
- **Key parameters:**
  - **Big Knob** — Controls randomness amount. Center = fully random. Left/right = decreasing randomness (locked pattern).
  - **Length** — Shift register length (sequence loop length).
  - **Pulse count** — Number of active steps.
  - **Scale** — Pitch output quantization.
  - **Voltage range** — Output pitch range.
- **Use cases:** Generative melodies, evolving sequences that slowly mutate, semi-random bass lines, ambient note generation.
- **Reach for this when:** "turing machine", "generative sequence", "evolving melody", "shift register", "controlled randomness".
- **Pairs well with:** Scale (constrain output), Feel (humanize timing), any melodic instrument.
- **vs Random (Native):** Turing Machine has *memory* (shift register) so patterns evolve; Random is *stateless*.

---

## J74 Suite (M4L_J74)

---

### ARPlines J74
- **Type:** M4L User (M4L_J74)
- **Load via:** Load `.amxd` from `M4L_J74/` folder
- **What it does:** Four independent arpeggiator lines, each with its own step count, direction, speed, and probability, enabling complex polymetric/polyrhythmic arpeggios.
- **Key parameters:**
  - **4 Lines** — Each with: step number (up to 32), step offset, playback direction, speed, time signature, trigger probability, pattern shift.
  - **Pattern Memory** — 10 slots per line; up to 15,000 combinations through mixing.
  - **Groove** — Timing and velocity adjustment with 12 swing modes including MPC-style.
  - **Random** — Per-line and global pattern randomization.
  - **Presets** — Custom saving/recall, device snapshots.
- **Use cases:** Polymetric arpeggios, generative melodic patterns, complex rhythmic interplay, live performance arp morphing.
- **Reach for this when:** "polyrhythmic arp", "four-line arpeggio", "complex arp pattern", "independent arp speeds".
- **Pairs well with:** Scale (constrain), J74 Progressive (provide chord input), any polyphonic synth.
- **vs Native Arpeggiator:** ARPlines has 4 independent polyphonic lines; native Arpeggiator is single-line.

---

### J74 Progressive
- **Type:** M4L User (M4L_J74)
- **Load via:** Load `.amxd` from `M4L_J74/` folder (multiple components)
- **What it does:** Suite of tools for chord progression creation, harmonic analysis, and MIDI clip processing. Includes: Chord Progression Editor, MIDI Clip Modifier, MIDI Clip Analyser, Audio Analyser.
- **Key parameters:**
  - **Progression Editor** — Any key/octave/scale (40+ presets), Circle of Fifths visualization, chord shape selection (triads through 13ths), automatic inversions, MIDI-mappable Chord Explorer.
  - **MIDI Clip Modifier** — Scale-based transposition, humanization (dynamics, groove, swing).
  - **MIDI Clip Analyser** — Scale and chord detection from MIDI clips.
  - **Audio Analyser** — Real-time note/chord/scale detection from audio input.
  - **Performance modes** — Hold chords, arpeggio styles, humanized timing.
- **Use cases:** Songwriting chord progressions, harmonic analysis of audio, transposing clips to new keys, reverse-engineering chord progressions from recordings.
- **Reach for this when:** "chord progression", "what chords are in this", "detect scale from audio", "harmonize", "circle of fifths".
- **Pairs well with:** ARPlines (arpeggiate generated chords), Scale (enforce detected scale).
- **vs Chord-O-Mat 3:** Progressive has audio analysis + clip modification; Chord-O-Mat is focused on real-time chord triggering.

---

### J74 PatDrummer
- **Type:** M4L User (M4L_J74)
- **Load via:** Load `.amxd` from `M4L_J74/` folder
- **What it does:** MIDI drum machine with 16 steps and 10 parallel drum sequences. Pattern-based beat programming with massive preset library.
- **Key parameters:**
  - **10 parallel sequences** — Independent drum lanes.
  - **16 steps** per sequence.
  - **Pattern memory** — 12 Kick patterns, 12 Snare patterns, 24 Hats patterns, 12 Percussion patterns = 41,472 unique combinations.
  - **Polyrhythmic sequencing** — Independent lengths per lane.
  - **Random patterns** — Generate random rhythms per lane.
  - **Export** — Direct MIDI clip export to Session View.
- **Use cases:** Rapid beat prototyping, pattern-mixing drum machine, polyrhythmic percussion, random beat generation.
- **Reach for this when:** "drum pattern", "beat machine", "generate drums", "mix-and-match drum patterns".
- **Pairs well with:** Drum Racks, Feel (groove output), any percussion kit.
- **vs Polyrhythm (Meyer):** PatDrummer has curated preset patterns to mix; Polyrhythm generates algorithmically.

---

### J74 StepSequencer64
- **Type:** M4L User (M4L_J74)
- **Load via:** Load `.amxd` from `M4L_J74/` folder
- **What it does:** 64-step analog-style step sequencer with 8 layers, per-step parameter control, and step-envelope modulation.
- **Key parameters:**
  - **64 steps** with ON/OFF activators.
  - **8 layers** — Monophonic alternative sequences or polyphonic parallel lines.
  - **Per-step control** — Pitch, velocity, duration, two step-envelopes for parameter modulation.
  - **Playback directions** — Forward, backward, random, up-and-down.
  - **Loop start/end** — Adjustable per layer.
  - **In-Key mode** — Automatic scale quantization with random generation.
  - **Swing** — 12 modes including MPC-like swing.
- **Use cases:** Analog-style sequencing, Berlin school sequences, generative patterns, per-step parameter modulation.
- **Reach for this when:** "step sequencer", "64 steps", "analog sequencer", "per-step modulation".
- **Pairs well with:** Any mono synth, J74 Progressive (harmonic context), Scale.
- **vs Modular Sequencer (Soundmanufacture):** StepSequencer64 is linear with deep per-step control; Modular Sequencer is fully patchable with cross-modulation.

---

### J74 SliceShuffler
- **Type:** M4L User (M4L_J74)
- **Load via:** Load `.amxd` from `M4L_J74/` folder
- **What it does:** Real-time audio slice sequencer. Buffers incoming audio and allows free re-sequencing of slices with probability lanes.
- **Key parameters:**
  - **Buffer** — Up to 32 beats (2 bars) of audio.
  - **32 steps** for slice re-sequencing.
  - **Probability lanes** — Add variation per step.
  - **Snapshots** — Store and recall slice arrangements.
  - **Real-time** — Hitless, instantaneous changes for live performance.
- **Use cases:** Live beat chopping, glitch performance, audio remix, drum break rearrangement.
- **Reach for this when:** "chop audio", "rearrange slices", "beat shuffle", "live audio remix".
- **Pairs well with:** Drum breaks, rhythmic audio material.
- **Note:** This is an *audio effect*, not a MIDI effect. Included here as part of J74 Suite.

---

## CLX_03 MIDI Collection

### LDM Design Devices

---

### Afterburner
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Reverse-trigger MIDI effect — notes are triggered by Note OFF instead of Note ON. Hold duration charges velocity.
- **Key parameters:**
  - **Velocity charging** — Longer hold = higher velocity on release-triggered note.
  - **Parameter mapping** — Map charged velocity to any Live parameter.
- **Use cases:** Unconventional sequencing, velocity-through-duration control, performance technique, reverse feel.
- **Reach for this when:** "trigger on note off", "reverse trigger", "hold-to-charge velocity".
- **Pairs well with:** Note Length (control input durations), any expressive instrument.

---

### AutoSputter
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** 4-button stutter/glitch looper. Each button captures and loops audio at a different note length, with reverse, half-speed, and double-speed options.
- **Key parameters:**
  - **4 stutter buttons** — Each assignable to a different note division.
  - **Reverse** — Play stutter backward.
  - **Half / Double speed** — Time-stretch stutter.
- **Use cases:** Live glitch performance, stutter fills, beat repeat alternatives, DJ-style effects.
- **Reach for this when:** "stutter", "glitch", "loop a moment", "beat repeat".
- **Note:** Audio effect, not MIDI. Included as part of CLX_03.

---

### Drumfoldr
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` in a Drum Rack cell
- **What it does:** Overcomes Sampler's 128-sample chain limit. Point at a folder of drum samples and browse/select any hit from the folder.
- **Key parameters:**
  - **Folder path** — Select source folder.
  - **Sample browser** — Scroll through all hits in folder.
  - **Auto-update** — Detects new files added to folder.
- **Use cases:** Large drum libraries, sample auditioning, rapid sound design iteration.
- **Reach for this when:** "browse drum folder", "lots of samples", "sample browser in rack".

---

### G_Delay / G_Ripplecoil / G_Rippler (Gravity Pack)
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What they do:** Polyphonic MIDI delay devices simulating bouncing ball physics.
  - **G_Delay** — Multi-tap delay (up to 24 taps) with gravitational deceleration. Notes bounce closer together like a ball losing energy.
  - **G_Rippler** — Inverse gravity. Notes expand outward, accelerating apart.
  - **G_Ripplecoil** — Combines both: expand then contract in one cycle (Rippler then G_Delay in sequence).
- **Key parameters:**
  - **Time** — Base delay time.
  - **Taps** — Number of echoes (up to 24).
  - **Gravity** — Physics simulation strength.
  - **Pitch** — Transposition per tap.
  - **Velocity decay** — Echo fadeout.
- **Use cases:** Bouncing ball fills, organic MIDI delays, cinematic tension builds, natural-feeling echo patterns.
- **Reach for this when:** "bouncing ball", "gravity delay", "accelerating/decelerating echoes", "physics-based delay".
- **Pairs well with:** Pitched instruments (melodic bouncing), drums (fills), Scale (constrain pitched echoes).
- **vs Note Echo (Native):** Gravity devices use *physics-based timing*; Note Echo uses *constant timing*.

---

### MIDIHack (Pro)
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Probability-driven MIDI processor. Each incoming note passes through randomized filters for pitch, octave, repetition, arpeggio generation, with controllable probability per effect.
- **Key parameters:**
  - **Probability sliders** — Per-effect chance of activation.
  - **Note repeater** — 10 speed options with velocity ramping and per-speed probability.
  - **Delay** — Adjustable note delay.
  - **Velocity randomization** — Random dynamics.
  - **Swing** — Timing humanization.
  - **Two sequencers** — One bypasses filters; another routes to up to 3 Return Tracks.
  - **Scale/Mode filtering** — Constrain output to scales.
  - **Block section** — Gate notes in/out.
- **Use cases:** Semi-generative MIDI processing, probability-based variations, chance-based arpeggiation, live improvisation aid.
- **Reach for this when:** "probability MIDI", "random chance effects", "semi-generative processor".
- **Pairs well with:** Any melodic instrument, Scale (double-constrain output).
- **vs Random (Native):** MIDIHack affects *multiple* note attributes with independent probabilities; Random only affects pitch.

---

### mLPr
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Live looping performance tool based on the MLR monome patch. Record and manipulate audio loops in real time.
- **Use cases:** Live looping, performance sampling, monome-style grid performance without hardware.
- **Note:** Audio looper, not MIDI effect. Included as part of CLX_03.

---

### zsteinkamp Devices

---

### ChordRipper
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Decomposes chords across multiple tracks. Each instance receives one voice from any chord played into any instance in the same group.
- **Key parameters:**
  - **Voice** — Which note in the chord this instance receives (1st, 2nd, 3rd, etc.).
  - **Group** — Independent chord groups for multiple simultaneous decompositions.
  - **Broadcasting** — Any instance can receive the chord; all instances in group get their assigned voice.
- **Use cases:** Send chord root to bass track, third to pad, fifth to lead. Decompose piano chords across an ensemble.
- **Reach for this when:** "split chord across tracks", "decompose chord", "voice separation", "orchestrate a chord".
- **Pairs well with:** Any chord-generating device, J74 Progressive, Chord-O-Mat 3.

---

### FibonacciNoteEcho
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** MIDI note echo where delay times follow the Fibonacci sequence (1, 1, 2, 3, 5, 8, 13...). Creates naturally accelerating/decelerating patterns.
- **Key parameters:**
  - **Time Base** — Base delay unit that Fibonacci numbers multiply.
  - **Repeats** — Number of echoes.
  - **Pitch shift** — Transposition per echo.
  - **Velocity decay** — Fadeout per echo.
- **Use cases:** Organic-feeling echoes, golden ratio rhythms, ambient cascades, nature-inspired patterns.
- **Reach for this when:** "fibonacci", "golden ratio rhythm", "organic echo", "natural delay pattern".
- **Pairs well with:** Scale (constrain pitch shifts), ambient instruments.
- **vs Note Echo (Native):** Fibonacci creates *mathematically organic* spacing; Native Note Echo is *uniform*.

---

### FractalNoteEcho
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Triggers notes in fractal patterns with configurable base shape, iterations, and scaling. Each echo triggers further sub-echoes.
- **Key parameters:**
  - **Base shape** — Define the initial timing pattern between echo taps.
  - **Iterations** — Fractal depth (each echo spawns sub-echoes).
  - **Scale** — Size reduction per iteration.
  - **Pitch / Velocity** — Per-iteration transposition and decay.
- **Use cases:** Self-similar rhythmic textures, complex cascading patterns, ambient generative textures, fractal-inspired composition.
- **Reach for this when:** "fractal", "self-similar echo", "cascading pattern", "recursive delay".
- **Pairs well with:** Scale (keep fractal output in key), ambient/textural instruments.
- **vs FibonacciNoteEcho:** Fractal creates *recursive branching* patterns; Fibonacci follows a *single sequence*.

---

### Modulation Delay / Lerp / Math / Stepper
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What they do:** Modulation signal processing utilities.
  - **Modulation Delay** — Feedback echo for modulation data. Turns pulses into evolving modulation waves.
  - **Modulation Lerp** — Constrains modulation between adjustable high/low boundaries.
  - **Modulation Math** — Combines two modulation signals (Min, Avg, Max operators) with mappable output.
  - **Modulation Stepper** — Converts continuous modulation into stair-stepped output at chosen frequency.
- **Use cases:** Complex modulation routing, S&H effects (Stepper), modulation mixing (Math), smoothing (Lerp), echo effects on automation (Delay).
- **Reach for this when:** "process modulation", "step modulation", "combine LFOs", "modulation delay".
- **Pairs well with:** Shaper MIDI, Expression Control, any modulation source.

---

### Other CLX_03 Devices

---

### CHORDimist
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Advanced chord generator and arpeggiator. Design custom chords, fire off harmonies, sustain them, or arpeggiate them with extensive direction and variation controls.
- **Key parameters:**
  - **Chord design** — Build custom chord shapes.
  - **Modes** — Fire (instant), Sustain (hold), Arpeggiate (cycle).
  - **Arpeggio direction** — Up, down, random, various patterns.
  - **Variation controls** — Modify chord voicings and patterns over time.
- **Use cases:** One-finger chord performance, advanced arpeggio design, harmonic exploration, live chord improvisation.
- **Reach for this when:** "design chords", "custom arpeggio", "chord generator", "one-finger chords".
- **Pairs well with:** Scale (constrain), any polyphonic instrument.
- **vs Chord (Native):** CHORDimist has modes (fire/sustain/arp) and variation; Native Chord is simpler fixed-interval stacking.

---

### ChordsInKey
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Converts single notes into appropriate diatonic chords within a selected key. Play one note, get the correct chord for that scale degree.
- **Key parameters:**
  - **Scale modes** — All 7 modes (Ionian through Locrian).
  - **Chord types** — Multiple voicing options.
  - **Inversions** — Automatic voicing spread.
  - **Strumming** — Guitar-like note offset.
  - **Randomization** — Strum pattern variation.
- **Use cases:** Theory-free chord playing, diatonic harmony from single keys, live harmonic exploration.
- **Reach for this when:** "chords in key", "diatonic chords from single notes", "one-finger diatonic".
- **Pairs well with:** Arpeggiator (arpeggiate diatonic chords), any polyphonic instrument.
- **vs Chord-O-Mat 3:** ChordsInKey is simpler (automatic diatonic mapping); Chord-O-Mat has library + Push integration + slave devices.

---

### Deviate
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Creates endless stochastic variations on MIDI clips or live MIDI input. Uses a 128-step memory buffer for controlled deviation. Part of the SEEDS collection (8 devices).
- **Key parameters:**
  - **Deviation amount** — How far from the original the variations drift.
  - **Pattern soft lock** — 128-step memory buffer for semi-predictable deviations.
  - **4 parameter mappings** — Map deviation to other Live parameters.
  - **Push 2/3 support** — Full control surface integration.
- **Use cases:** Humanize MIDI, generate arrangement variations, evolving loops, controlled randomness, organic builds.
- **Reach for this when:** "create variations", "humanize MIDI", "evolve this clip", "make it organic".
- **Pairs well with:** Any MIDI clip, Scale (constrain variations).
- **vs Random (Native):** DEVIATE transforms *entire clip attributes* with memory; Random changes *individual note pitch* statelessly.

---

### MIDI Tenderizer
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** MIDI velocity and timing humanization tool. "Tenderizes" rigid MIDI by adding subtle velocity and timing variations.
- **Key parameters:**
  - **Velocity variation** — Amount of random velocity offset.
  - **Timing variation** — Amount of random timing offset.
  - **Character** — Shape of randomization distribution.
- **Use cases:** Humanize quantized MIDI, add organic feel, soften rigid sequences.
- **Reach for this when:** "humanize", "tenderize", "make less mechanical", "add feel".
- **Pairs well with:** Any quantized MIDI clip, sequenced instruments.
- **vs Feel (Meyer):** Tenderizer adds *random* timing variation; Feel applies *structured* swing/groove.

---

### Sting 2 (by Iftah)
- **Type:** M4L User (CLX_03)
- **Load via:** Load `.amxd` from `CLX_03/` folder
- **What it does:** Expressive acid line performance system and pattern generator. Generates and morphs between random and classic acid patterns with 16-step sequencing across note, velocity, gate, and octave lanes.
- **Key parameters:**
  - **Type / Density knobs** — Control pattern character from structured acid to random.
  - **16 steps** — Note, velocity, gate, and octave per step.
  - **Accent / Gate / Slide** — Classic TB-303 sequencer parameters.
  - **Generation algorithm** — Morphs fluidly between pattern types.
  - **Push takeover mode** — Dedicated Push 2/3/Standalone control surface.
- **Use cases:** Acid lines, TB-303 emulation, generative bass patterns, live acid performance, improvisation.
- **Reach for this when:** "acid line", "303 pattern", "acid bass", "generate bass sequence", "acid techno".
- **Pairs well with:** Any 303-style synth (TAL-BassLine, ABL3, Wavetable in acid mode), distortion/filter effects.
- **vs Arpeggiator:** Sting is specialized for *acid patterns* with accent/slide; Arpeggiator is general-purpose.

---

## Soundmanufacture Devices

---

### Chord-O-Mat 3
- **Type:** M4L User (Soundmanufacture)
- **Load via:** Load `.amxd` from Soundmanufacture folder
- **What it does:** Chord library and trigger device. Maps all diatonic chords of a scale to individual keys for one-finger chord performance. Includes Push integration and slave devices for project-wide harmony control.
- **Key parameters:**
  - **Scale library** — 40+ scales including all Push 1+2 scales, plus Tobias Hunke collection.
  - **Auto-mapping** — All chords from selected scale mapped to keyboard.
  - **Octave Designer** — Add/remove notes from chord voicings.
  - **Slave Devices** — Control harmony changes across entire Live project.
  - **Push integration** — Direct mapping to Push pads.
- **Use cases:** Live chord performance, one-finger harmony, project-wide key changes, Push-based composition.
- **Reach for this when:** "one-finger chords in scale", "chord trigger", "Push chord performance", "project-wide harmony".
- **Pairs well with:** Scale-O-Mat (project scale control), ChordRipper (decompose triggered chords), ARPlines.
- **vs Chord (Native):** Chord-O-Mat knows *music theory* (scale-aware chords); Native Chord stacks *fixed intervals*.

---

### InstantScale
- **Type:** M4L User (Soundmanufacture)
- **Load via:** Load `.amxd` from Soundmanufacture folder
- **What it does:** Quick scale correction and display tool. Shows the current scale on a keyboard display and corrects incoming MIDI to fit.
- **Key parameters:**
  - **Scale selection** — Preset scales and custom.
  - **Correction mode** — Nearest note correction.
  - **Display** — Visual keyboard showing active scale notes.
- **Use cases:** Quick scale lock, visual scale reference, simple correction without full Scale-O-Mat setup.
- **Reach for this when:** "quick scale lock", "show me the scale", "simple scale correction".
- **Pairs well with:** Any MIDI input, Scale-O-Mat (for more complex setups).
- **vs Scale (Native):** InstantScale provides better *visual feedback*; Native Scale has more *remapping options*.

---

### Modular Sequencer
- **Type:** M4L User (Soundmanufacture)
- **Load via:** Load `.amxd` from Soundmanufacture folder
- **What it does:** Fully patchable modular step sequencer with 8 sequencers, cross-modulation, logical operators, and 4 outputs with scale correction.
- **Key parameters:**
  - **8 sequencers** — 4 trigger + 4 value sequencers. Sync or independent tempo per sequencer.
  - **Patch chords** — Route any output to any input via visual patching.
  - **4 outputs** — Each with assignable note/velocity/octave/length control and scale correction.
  - **8 modulators** — Signal inversion, probability, trigger-step filtering.
  - **4 logical operators** — Combine two sequence values (AND, OR, XOR, etc.).
  - **Scale correction** — Per-output. Learns scales from incoming MIDI. Integrates with Chord-O-Mat 3 and Scale-O-Mat.
  - **Randomization** — Per-parameter generative capability.
- **Use cases:** Complex generative sequencing, modular-style patching in software, polyrhythmic generation, experimental composition.
- **Reach for this when:** "modular sequencer", "patch cables", "cross-modulation sequencer", "generative patching".
- **Pairs well with:** Chord-O-Mat 3 (harmonic input), Scale-O-Mat (project-wide scale), any instrument.
- **vs J74 StepSequencer64:** Modular Sequencer is *fully patchable* with cross-modulation; StepSequencer64 is *linear* with deeper per-step control.

---

### Scale-O-Mat 4
- **Type:** M4L User (Soundmanufacture)
- **Load via:** Load `.amxd` from Soundmanufacture folder
- **What it does:** Project-wide scale library controller. One device controls ALL native Scale MIDI effects in your entire Live set. Switch scales globally with one action.
- **Key parameters:**
  - **40+ scales** — Full library including Push scales and Tobias Hunke collection.
  - **Device detection** — Automatically finds all Scale MIDI effects in project.
  - **Groups** — Assign different scales to different track groups.
  - **Filter / Pitch modes** — Filter out-of-scale notes or pitch them to nearest scale note.
  - **Transpose** — Global key shifting.
  - **Two preset systems** — 128 mapping presets + 128 scale presets.
  - **MPE support** — Works with MPE controllers.
  - **MIDI learn** — Learn scales from incoming MIDI.
- **Use cases:** Live performance key changes, project-wide scale management, global harmonic control, multi-track scale enforcement.
- **Reach for this when:** "change scale globally", "project-wide key", "control all scales at once", "global scale management".
- **Pairs well with:** Chord-O-Mat 3 (chord triggering), Modular Sequencer (scale input), all Scale devices.
- **vs Scale (Native):** Scale-O-Mat controls *all Scale devices project-wide*; Native Scale works *per-track only*.

---

## Generative M4L Devices

---

### Euclidean Sequencer Pro (Alkman)
- **Type:** M4L User (Generative)
- **Load via:** Load `.amxd` from generative M4L folder
- **What it does:** 4-voice Euclidean rhythm generator with polyrhythm/polymeter switching, per-voice clock division, swing, and Juno-style arpeggiator.
- **Key parameters:**
  - **4 voices** — Each with steps, pulses, rotation, and independent clock divider/multiplier.
  - **Euclidean algorithm** — Distributes pulses as evenly as possible across steps.
  - **Polyrhythm / Polymeter toggle** — Switch between common timebase and independent lengths.
  - **Clock divider/multiplier** — Common multiple or non-divisible values per voice.
  - **Note duration** — Per-voice, measured in step multiples/divisors.
  - **Swing** — Per-voice swing amount.
  - **Arpeggiator** — Juno-style per-voice arp.
  - **Euclidean Out** — Companion device for routing voices to separate tracks.
- **Use cases:** Euclidean drum patterns, polyrhythmic percussion, generative rhythms, West African/electronic rhythm exploration.
- **Reach for this when:** "euclidean rhythm", "Bjorklund algorithm", "even pulse distribution", "polyrhythmic drums".
- **Pairs well with:** Drum Racks, any percussion instrument, Scale (for melodic Euclidean patterns).
- **vs Polyrhythm (Meyer):** Alkman is *real-time* with per-voice routing; Meyer's is a *clip-based MIDI Tool*.

---

### Grids (Mutable Instruments)
- **Type:** M4L User (Generative)
- **Load via:** Load `.amxd` from generative M4L folder
- **What it does:** Topographic drum sequencer ported from Mutable Instruments eurorack module. Navigates a learned map of thousands of drum patterns; moving through X/Y coordinates morphs between rhythms.
- **Key parameters:**
  - **X / Y position** — Navigate the pattern map. Different coordinates = different rhythms.
  - **Density (Kick / Snare / HiHat)** — Three knobs controlling event density per drum voice.
  - **Chaos** — Amount of random variation.
  - **Accent** — Extends to 6 voices (3 base + 3 accent variations).
  - **Map interpolation** — 5x5 grid of static patterns with linear interpolation between them.
- **Use cases:** Instant drum patterns, morphing between styles, live beat exploration, generative percussion.
- **Reach for this when:** "topographic drums", "morph between patterns", "Grids", "drum map", "instant beat".
- **Pairs well with:** Drum Racks, any percussion kit.
- **vs PatDrummer (J74):** Grids *morphs continuously* through a pattern space; PatDrummer *mixes discrete* pattern presets.

---

### TOPO SEQ
- **Type:** M4L User (Generative)
- **Load via:** Load `.amxd` from generative M4L folder
- **What it does:** Topographic sequencer variant. Generates patterns by navigating a multi-dimensional map of rhythmic possibilities, similar in concept to Grids but with different topology.
- **Key parameters:**
  - **Map navigation** — X/Y coordinates for pattern selection.
  - **Density** — Per-voice event density.
  - **Variation** — Pattern mutation amount.
- **Use cases:** Generative drum patterns, beat exploration, pattern morphing.
- **Reach for this when:** "topographic sequencer", "pattern map", "morph drums".
- **Pairs well with:** Drum Racks, Grids (compare approaches).
- **vs Grids:** Both use topographic approaches; TOPO SEQ may offer different map topology and interface.

---

### Natural Selection P / S
- **Type:** M4L User (Generative)
- **Load via:** Load `.amxd` from generative M4L folder
- **What they do:** Genetic algorithm-based preset evolution. Treat synth parameters as DNA — breed, mutate, and evolve sounds across generations.
  - **Natural Selection P** — Evolves parameters of *external* devices/racks in Live. Maps to any automatable parameter.
  - **Natural Selection S** — Internal poly synth + rhythm engine. Built-in oscillators (morphable FM, resonator, Karplus-Strong, wavetable, noise), filters, and note generator.
- **Key parameters (both):**
  - **Mutation amount** — How much offspring deviate from parents. Two mutation modes.
  - **Generation limits** — Control which ancestors can breed.
  - **Family tree** — Visual lineage tracking.
  - **Rating system** — Bias selection toward preferred sounds.
  - **Morphing** — 8-preset XY quadrant blending.
  - **Seed methods** — Random or device-value-based initialization.
- **Key parameters (S only):**
  - **5 oscillator types** — Morphable FM, resonator+mallet, Karplus-Strong+mallet, wavetable (user-droppable), noise.
  - **Partials system** — Harmonic distribution manipulation.
  - **2 filters** — Basic, ladder, vowel/formant.
  - **Note generator** — Euclidean + random gating, pitch, velocity, duration randomization, scale/tonic locking.
- **Use cases:** Sound design exploration, evolving presets over time, discovering unexpected timbres, algorithmic composition.
- **Reach for this when:** "evolve sounds", "genetic algorithm", "breed presets", "mutate parameters", "sound evolution".
- **Pairs well with:** Natural Selection P with any instrument/rack; S is self-contained.
- **vs Turing Machine (Meyer):** Natural Selection evolves *entire parameter sets*; Turing Machine generates *pitch/rhythm sequences*.

---

## Quick Decision Matrix

| I want to... | Reach for | Why |
|---|---|---|
| Arpeggiate a chord | **Arpeggiator** (simple) / **ARPlines** (complex polymetric) | Native for basics; ARPlines for 4 independent lines |
| Build chords from single notes | **Chord** (fixed intervals) / **ChordsInKey** (diatonic) / **Chord-O-Mat 3** (library + Push) | Chord for parallel intervals; ChordsInKey for theory-free; Chord-O-Mat for performance |
| Echo/delay MIDI notes | **Note Echo** (regular) / **Fibonacci/Fractal** (organic) / **Gravity Pack** (physics) | Note Echo for standard delays; math echoes for texture; Gravity for bouncing ball |
| Force notes to a scale | **Scale** (per-track) / **Scale-O-Mat** (project-wide) / **InstantScale** (quick visual) | Scale for simple; Scale-O-Mat for global control |
| Generate drum patterns | **Grids** (topographic) / **PatDrummer** (preset mixing) / **Euclidean Pro** (algorithmic) / **Polyrhythm** (clip-based) | Grids for exploration; PatDrummer for curated; Euclidean for math; Polyrhythm for MIDI Tools |
| Add randomness/variation | **Random** (pitch only) / **DEVIATE** (whole clip) / **MIDIHack** (probability chains) / **Turing Machine** (evolving) | Random for simple; DEVIATE for subtle; MIDIHack for wild; Turing for memory |
| Generate acid lines | **Sting 2** | Purpose-built TB-303 pattern generator with Push integration |
| Humanize timing | **Feel** (structured groove) / **MIDI Tenderizer** (random variation) | Feel for deliberate swing; Tenderizer for organic randomness |
| Subdivide/ratchet notes | **Divs** (pure subdivision) / **Segment** (duration-filtered) / **Condition Transform** (conditional) | Divs for simple; Segment for smart; Condition Transform for selective |
| Create generative melodies | **Turing Machine** (shift register) / **Random** + **Scale** (simple) / **Swarmalators** (agent-based) | Turing for evolving; Random+Scale for quick; Swarmalators for emergent |
| Chord progression writing | **J74 Progressive** (analysis + editor) / **Chord-O-Mat 3** (trigger + library) | Progressive for composition; Chord-O-Mat for performance |
| Modular-style sequencing | **Modular Sequencer** (patchable) / **StepSequencer64** (deep linear) | Modular for patching; StepSequencer for per-step detail |
| Evolve sounds over time | **Natural Selection P/S** (genetic) / **Develop** (complexity curve) | Natural Selection for timbre; Develop for density |
| Split chords across tracks | **ChordRipper** | Purpose-built for voice decomposition |
| Control hardware CC | **CC Control** | Native Live 12 CC automation surface |
| Map expression to parameters | **Expression Control** (incoming MIDI) / **Shaper MIDI** (generated envelopes) | Expression Control for controllers; Shaper for designed modulation |
| Debug MIDI signal | **MIDI Monitor** | Drop anywhere in chain to inspect |
| Build up/break down patterns | **Develop** (density over time) / **Condition Transform** (selective removal) | Develop for gradual; Condition for targeted |
| Euclidean rhythms (real-time) | **Euclidean Sequencer Pro** | 4-voice real-time with per-voice routing |
| Euclidean rhythms (clip-based) | **Polyrhythm** | MIDI Tool with Euclidean + Omni algorithms |
| Phase shifting / bouncing ball (clip) | **Phase Pattern** / **Micro Stretch** | Phase Pattern for time-warp; Micro Stretch for Steve Reich |
| Phase shifting (real-time) | **G_Ripplecoil** / **G_Rippler** / **G_Delay** | Physics-based real-time MIDI delays |
| Draw custom modulation | **Shaper MIDI** (native) / **Envelope MIDI** (ADSR-style) | Shaper for freeform; Envelope for ADSR |
| Process modulation signals | **Modulation Delay/Lerp/Math/Stepper** (zsteinkamp) | Utility suite for modulation routing and processing |

# Genre Vocabularies — Aesthetic → Tool Manifold

A genre-level complement to `artist-vocabularies.md`. Where the artist file says
"Villalobos uses X", this file says "microhouse aesthetic uses X regardless of who
is making it."

Each genre entry has:
- **Tempo / time** — the sonic starting point
- **Kick** — character + frequency / tempo recommendations
- **Bass** — character + register
- **Percussion** — style, layering, aesthetic
- **Harmonic material** — synth/sampled, tonal vs atonal, key tendencies
- **Texture / atmosphere** — what fills space
- **Reach for** — LivePilot devices by role
- **Avoid** — anti-patterns that kill the genre

LLMs encountering "make me a <genre> track" should read this before choosing tools.
**These are not recipes.** Every entry is a set of constraints and opinions that
leave creative choice to the LLM + user.

> **v1.18+ structured packets:** each genre below also has a machine-readable
> YAML packet at `concepts/genres/<slug>.yaml`. The narrative here is the
> human-facing overview; the YAML is the source-of-truth for director
> compilation. When updating a genre, update BOTH. Schema: `concepts/_schema.md`.

---

## Microhouse
**Tempo / time:** 122-128 BPM, straight 4/4 with constant micro-variation.
**Kick:** Minimal, short decay, ~55 Hz fundamental. Not the feature.
**Bass:** Filtered mid-bass, occasional sub-layer. Warm, sometimes tonal.
**Percussion:** Hyper-chopped vocal snippets, glass/metal percussion, shakers,
conga/cuica hits. The PERCUSSION is the genre, not the kick.
**Harmonic:** Chord stabs filtered, sometimes pitched vocal fragments as hooks.
In-key D minor / A minor / F minor common.
**Texture:** Field recordings, vinyl crackle, reverb tails at -20 to -30 dB hidden
under main elements.
**Reach for:**
- Instruments: Simpler (slicing, One-Shot for pitched chops), Snipper, Drift, Poli,
  Granulator III
- FX: PitchLoop89, Auto Filter (band-pass sweeps), Convolution Reverb, Gated Delay,
  Variations (for stab morphing)
- Packs: Voice Box, Chop and Swing, Latin Percussion, Lost and Found, Mood Reel
**Avoid:** Loud kicks, sidechain, long-sustain melody, bright overtones, repeated
8-bar loops.
**Canonical artists:** Akufen, Isolée, Luomo, Villalobos (microhouse-leaning tracks),
Robag Wruhme, Dimbiman.
**Key techniques:** `"Vocal micro-chop (Akufen)"` (simpler), `"micro_chop"`, `"dub_throw"`,
`"Hat replay pitch drift"` (snipper).

---

## Dub Techno
**Tempo / time:** 120-130 BPM, rigid 4/4.
**Kick:** Low mid (60-80 Hz fundamental), short, not aggressive. Serves the dub not
the rave.
**Bass:** Pure sine sub at fundamental, no modulation, very long release. Felt not
heard.
**Percussion:** 909-style hat, minimal closed/open interplay, occasional hand
percussion, stick-click ghost hits.
**Harmonic:** Single chord stab (minor 7th or suspended 4th) feeding delay → filter
→ reverb. The FX chain IS the arrangement.
**Texture:** Vinyl crackle, rain/nature field recordings, hiss, long reverb tails at
-10 to -20 dB.
**Reach for:**
- Instruments: Poli (warm chord), Drift (simple stab), Simpler for dub-sub samples,
  Harmonic Drone Generator (Drone Lab)
- FX: Convolution Reverb (Farfisa Spring, Stocktronics), Echo (long delay with filter
  on return), Auto Filter (on delay return), Utility (sub → mono)
- Packs: Drone Lab, Chop and Swing (crackle), Lost and Found (found-sound texture)
**Avoid:** Bright EQ, crisp transients, complex melody, fast tempo, sidechain
compression.
**Canonical artists:** Basic Channel, Rhythm & Sound, Deepchord, Porter Ricks,
Yagya.
**Key techniques:** `"The dub chord"` (sound-design-deep.md), `"Reverb as harmony"`,
`"Delay throws"`, `"Dub sub-bass"` (bass).

---

## Deep Minimal / Villalobos-school
**Tempo / time:** 125-135 BPM, 4/4 with extreme micro-timing variation and polyrhythms
suggested via percussion.
**Kick:** Deep fundamental (40-50 Hz — use `sub_low` analyzer band to verify), short
envelope, sometimes with internal pitch movement.
**Bass:** Sub at fundamental + mid-bass layer, often tonal.
**Percussion:** Latin hand percussion (cuica, conga, guiro, claves) + digital glass/
metal + heavily chopped vocals. Off-grid micro-timing on most hits.
**Harmonic:** Chopped vocals AS melody, occasional chord stab, microtonal moments.
**Texture:** Constant field-recording / found-sound subtext, reverb tails layered
at -25 to -30 dB.
**Reach for:**
- Instruments: Simpler (slicing), Bass (Creative Extensions), Drone Lab (sub-bed),
  Operator (Haas-style deep bass)
- FX: PitchLoop89, Convolution Reverb, Phase Pattern (off-grid percussion), Microtuner
- Packs: Latin Percussion, Lost and Found, Voice Box, Drone Lab, Chop and Swing,
  Glitch and Wash
**Avoid:** Quantized drums, 8-bar repetition, bright kicks, dry mix, sidechain.
**Canonical artists:** Villalobos, Margaret Dygas, Zip, Petre Inspirescu, Raresh,
rpr soundsystem.
**Key techniques:** `"Villalobos sub-bass layer"` (simpler), `"Phase Pattern on drum
clips"`, `"micro_chop"`, `"Arpiar dusty-horn"` (trumpet pp through PitchLoop89).

---

## Minimal Techno
**Tempo / time:** 128-132 BPM, 4/4.
**Kick:** Punchy-but-restrained, clean, ~60 Hz.
**Bass:** Filtered sub with LFO-driven movement, moderate compression.
**Percussion:** 909 hats, occasional hand percussion, no clutter.
**Harmonic:** Single evolving source (filter automation IS the melody), occasional
stab.
**Texture:** Minimal — one or two background elements, always subtly evolving.
**Reach for:**
- Instruments: Analog (Hawtin subtractive), Drift, Operator, Simpler
- FX: Auto Filter with slow LFO, Convolution Reverb, Echo, Saturator
- Packs: Core Library synths, Drone Lab
**Avoid:** Additive arrangement, thick layering, busy percussion, preset chains.
**Canonical artists:** Plastikman / Richie Hawtin, Robert Hood, Lawrence, Daniel Avery.
**Key techniques:** `"Hawtin subtractive pad"` (analog), `"Micro-Modulation"`,
`"Subtraction over addition"`.

---

## Ambient / Drone
**Tempo / time:** 60-90 BPM or no perceptible tempo. Duration 5-30+ minutes per piece.
**Kick:** None, or very sparse.
**Bass:** Sub-bass drone, sustained. Sometimes absent.
**Percussion:** Absent, or occasional distant bell/chime/rim-shot.
**Harmonic:** Sustained pads, drones, evolving harmonic fields. Modal or microtonal
common.
**Texture:** IS the composition. Reverb, granular, delay, tape degradation.
**Reach for:**
- Instruments: Granulator III (Cloud mode), Harmonic Drone Generator, Vector Grain,
  Emit, Tension (bowed cello), Sampler (orchestral)
- FX: Convolution Reverb (cathedral/hall), Vector Delay, Delay, Erosion, Dynamic Tube
- Packs: Drone Lab, Inspired by Nature, Mood Reel, Orchestral Strings/Woodwinds
  (pp only)
**Avoid:** Drums, rhythmic patterns, fast elements, bright EQ, hard cuts.
**Canonical artists:** Stars of the Lid, Tim Hecker, William Basinski, Wolfgang Voigt
(Gas), Jóhann Jóhannsson, Aphex Twin (ambient phase), Thomas Köner.
**Key techniques:** `"Grain cloud (Tim Hecker)"` (emit), `"Basinski tape degradation"`
(vector_grain), `"Slow-motion sustain"`, `"extreme_stretch"`, `"tail_harvest"`.

---

## IDM
**Tempo / time:** 80-150 BPM, complex rhythms (quintuplets, polyrhythms, non-4/4 common).
**Kick:** Varied — sometimes 808, sometimes Amen chop, sometimes synthesized.
**Bass:** Heavy low-end, FM-generated common, sub-modulated.
**Percussion:** Hyper-detailed, often computer-generated rhythms, non-quantized
micro-timing, metal/glass samples.
**Harmonic:** Atonal or microtonal common, melodic fragments rather than sustained
melody.
**Texture:** Granular, glitchy, digital artifacts embraced.
**Reach for:**
- Instruments: Operator (FM), Vector FM, Wavetable, Emit, Vector Grain, Simpler,
  Tension, Collision
- FX: Erosion, Pitch Hack, Roar, Spectral Blur, Grain Delay, Ring Modulator via
  Operator
- Packs: Inspired by Nature, Performance Pack (Variations), MIDI Tools (Polyrhythm,
  Phase Pattern)
**Avoid:** Clean production, simple 4/4, traditional harmony.
**Canonical artists:** Aphex Twin, Autechre, Boards of Canada, μ-Ziq, Squarepusher,
Venetian Snares, Oneohtrix Point Never.
**Key techniques:** `"Aphex ambient FM pad"` (operator), `"Modulated bell cluster"`
(vector_fm), `"Chaotic lock-in"` (vector_map), `"granular_scatter"`,
`"euclidean_slice_trigger"`.

---

## Modern Classical / Cinematic
**Tempo / time:** 60-90 BPM or rubato (no fixed tempo).
**Kick:** None, or timpani.
**Bass:** Cello, double-bass pizzicato, or orchestral bass drum. Not electronic.
**Percussion:** Absent or orchestral (mallets, timpani, cymbals at pp).
**Harmonic:** Sustained strings, piano fragments, occasional brass swells. Major/minor
tonal with occasional chromatic motion.
**Texture:** Natural hall acoustic, sustained strings, grand piano resonance.
**Reach for:**
- Instruments: Sampler (multi-velocity orchestral libraries), Tension (bowed cello),
  Collision (mallets), Upright Piano (Spitfire), Orchestral Mallets
- FX: Convolution Reverb (hall / cathedral IR), EQ Eight (gentle high-shelf), Compressor
  (string bus)
- Packs: Spitfire Strings/Brass, Orchestral Mallets, Upright Piano, SONiVOX Orchestral
  Strings/Brass/Woodwinds (pp only)
**Avoid:** Electronic drums, synthesizers (unless sparse & atmospheric), compressed
mix, bright EQ.
**Canonical artists:** Max Richter, Jóhann Jóhannsson, Hildur Guðnadóttir, Nils Frahm,
Max Cooper.
**Key techniques:** `"Orchestral multi-velocity"` (sampler), `"Bowed cello low register"`
(tension), `"Single sustained note pedal-down"` (Upright Piano).

---

## Hip-Hop (Boom Bap / Lo-Fi)
**Tempo / time:** 85-95 BPM, swing 60-70% (Dilla-feel requires manual micro-timing,
not groove template).
**Kick:** Warm, sometimes dusty. ~55-65 Hz fundamental.
**Bass:** Electric bass samples, 808 alternative on modern tracks.
**Percussion:** Chopped breaks (Amen, Funky Drummer, Impeach the President, The
Mexican, Apache), dusty snares, vinyl-saturated hats.
**Harmonic:** Chopped soul/jazz loops, Rhodes/Wurly samples, sometimes unintentional
key clashes that become the sound.
**Texture:** Vinyl crackle, tape hiss, saturator on drum bus.
**Reach for:**
- Instruments: Simpler (classic mode for stabs, slicing for drum breaks), Electric
  Keyboards, Bass
- FX: Saturator, Vinyl Distortion, Erosion, Dynamic Tube, Tape Delay via Grain Delay,
  Gated Delay (Creative Extensions)
- Packs: Chop and Swing, Golden Era Hip-Hop Drums, Drum Booth, Electric Keyboards,
  Core Library samples
**Avoid:** Quantized drums, clean production, modern trap hats, synth bass.
**Canonical artists:** J Dilla, DJ Premier, Madlib, RZA, Pete Rock, Nujabes.
**Key techniques:** `"J Dilla micro-timed kit"` (simpler), `"Tape-warped EP"` (electric),
`"slice_and_sequence"`, `"stab_isolation"`.

---

## Trap / Modern Hip-Hop
**Tempo / time:** 130-160 BPM (half-time feel = 65-80 BPM perceived).
**Kick:** 808 sub-bass (sine with pitch envelope down), long decay.
**Bass:** 808 IS the bass. No separate bassline.
**Percussion:** Crisp snappy snares, hyper-fast hi-hat rolls (1/32, 1/64), metal shakers,
claps doubled with snare.
**Harmonic:** Minor-key melody, heavily-tuned synth stabs, sometimes strings/piano.
**Texture:** Atmospheric pads, vocal chops, ad-lib snippets.
**Reach for:**
- Instruments: Bass (Creative Extensions — 808), Simpler (trap one-shots), Wavetable
  (stabs), Drum Rack (programmed hats)
- FX: Compressor (aggressive), Saturator, Reverb, Pitch Hack (ad-lib chops)
- Packs: Trap Drums, Beat Tools, Splice 808 kits (via sample engine)
**Avoid:** Live drums, major-key dominance, slow tempo.
**Canonical artists:** Metro Boomin, Southside, 808 Mafia, Travis Scott (production
style).
**Key techniques:** `"808 sub replacement"` (bass), `"Wobble bass"` at reduced depth
for tonal 808, hat-roll 1/32 programming.

---

## Dubstep / Bass Music (Modern)
**Tempo / time:** 140 BPM, half-time feel (snare on 3).
**Kick:** Punchy ~55 Hz, often layered with sub.
**Bass:** Wobble bass (filter-modulated saw), growl bass (FM-heavy), sub drone.
**Percussion:** Heavy snare on 3, snappy claps, 909 hi-hats, occasional glitch
percussion.
**Harmonic:** Minor-key stabs, filtered chords on breakdowns.
**Texture:** Industrial atmosphere, noise risers.
**Reach for:**
- Instruments: Wavetable (wobble), Operator (FM growl), Bass, Drum Rack
- FX: Auto Filter (wobble), Compressor (heavy), Saturator, Limiter, Ring Modulator
- Packs: Drum Essentials (dubstep kits), Skitter and Step, Punch and Tilt
**Avoid:** Full-step kick pattern, major key, clean mix.
**Canonical artists:** Skrillex (modern), Skream (OG), Mala, Rusko, Excision.
**Key techniques:** `"Wobble bass"` (wavetable), `"Reese-style bass"` (bass), half-time
drum programming.

---

## House / Deep House
**Tempo / time:** 120-126 BPM, 4/4 straight.
**Kick:** Full-bodied, ~60 Hz fundamental, compressed, sidechain-friendly.
**Bass:** Sub + mid-bass layer, tonal, follows chord changes.
**Percussion:** Open hat on the off-beat, clap on 2+4, shakers.
**Harmonic:** Chord pads (7th / 9th chords common), Rhodes-style keys, vocal samples.
**Texture:** Clean digital, occasional vinyl samples.
**Reach for:**
- Instruments: Poli (pad), Drift, Electric Keyboards (Rhodes), Bass, Simpler
- FX: Compressor (sidechained via Envelope Follower), Auto Filter, Reverb, Chorus-
  Ensemble
- Packs: Synth Essentials, Electric Keyboards, Core Library
**Avoid:** Minor 7th dominance (unless jazz-house), dry production.
**Canonical artists:** Larry Heard, Kerri Chandler, Moodymann, Theo Parrish (deep
house), Masters at Work.
**Key techniques:** `"Classic Rhodes"` (electric), `"Juno-style detuned chord"` (poli),
sidechain compression on pad triggered by kick.

---

## Drum and Bass / Jungle
**Tempo / time:** 160-180 BPM, 4/4 with half-time perception on Amen breaks.
**Kick:** Punchy, layered with break kick.
**Bass:** Reese bass (two detuned saws), sub-bass under the Reese.
**Percussion:** Amen, Funky Drummer, Apache break chopped and rearranged.
**Harmonic:** Minimal melody, occasional jazz/orchestral pad.
**Texture:** Atmospheric pads, jungle vocal samples ("lick shot", "dread").
**Reach for:**
- Instruments: Simpler (Amen chopping), Analog (Reese), Bass, SONiVOX Strings (pp
  pad)
- FX: Compressor (drum bus glue), Saturator, Roar (modern neurofunk), Convolution
  Reverb
- Packs: Drum Essentials, Splice break packs
**Avoid:** Quantized drums (Amen must be chopped and rearranged), synth bass in
place of Reese.
**Canonical artists:** Photek, Source Direct, Goldie, Roni Size (jungle/jazzstep),
Noisia, Phace (modern neurofunk).
**Key techniques:** `"Reese bass (drum & bass)"` (analog), `"slice_and_sequence"` on
Amen at 174 BPM.

---

## Garage / UK Garage / 2-Step
**Tempo / time:** 130-140 BPM, 2-step shuffle pattern (kick on 1, snare on 3, but
broken hat pattern).
**Kick:** Punchy, often offset off-grid.
**Bass:** Sub-bass with slide + filter modulation.
**Percussion:** Shuffled hats (NOT straight 16ths), occasional tom fills.
**Harmonic:** R&B-chord influence, vocal samples chopped.
**Texture:** Skippy, vibrant, sometimes dub-influenced reverb.
**Reach for:**
- Instruments: Simpler (vocal chops), Bass, Drift
- FX: Auto Filter, Ping-Pong Delay, Compressor, Convolution Reverb
- Packs: Skitter and Step (the pack literally for this genre), Voice Box
**Avoid:** Straight 16th hats, trap-style snares, minor-9th minor dominance.
**Canonical artists:** Todd Edwards, MJ Cole, Artful Dodger, Burial (post-garage).
**Key techniques:** `"vocal_chop_rhythm"`, shuffled hat programming, bass-glide
automation.

---

## Experimental / Noise / Found-Sound
**Tempo / time:** Variable or no tempo.
**Kick:** Absent or found-sound substitute.
**Bass:** Drone, sub-bass, or absent.
**Percussion:** Found-sound percussion (metal, glass, objects), not kit drums.
**Harmonic:** Often atonal, microtonal, or noise-based.
**Texture:** IS everything. Granular, spectral, saturated, reversed.
**Reach for:**
- Instruments: Vector Grain, Emit, Corpus, Tension (weird settings), Collision,
  Bell Tower
- FX: Erosion, Roar, Spectral Blur, Spectral Resonator, Shifter, Pitch Hack, Grain
  Delay
- Packs: Lost and Found, Glitch and Wash, Inspired by Nature, Building Max Devices
**Avoid:** Predictable arrangement, traditional harmony, clean signal chains.
**Canonical artists:** Arca, SOPHIE, Oneohtrix Point Never, Fennesz, Alva Noto, Pan
Sonic.
**Key techniques:** `"Noise Bow"` (corpus), `"Chaotic lock-in"` (vector_map),
`"granular_scatter"`, `"Modulated bell cluster"` (vector_fm).

---

## How to use this file

When asked for a specific genre:

1. Find the entry (or closest genre).
2. Use the **tempo**, **kick character**, **bass character**, **percussion** sections
   to set session parameters (`set_tempo`, time signature, track structure).
3. Use the **Reach for** list to populate device chains via `atlas_search` +
   `load_browser_item`.
4. Cross-reference the **Key techniques** with `signature_techniques` in per-device
   YAML files or named techniques in `sample-techniques.md` / `sound-design-deep.md`.
5. Respect the **Avoid** list — it represents the genre's negative constraints, not
   just opinions.

Genres blend. "Deep-minimal-dub-techno" borrows from deep_minimal, minimal_techno,
and dub_techno simultaneously. Read multiple entries and synthesize.

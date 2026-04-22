# Artist Vocabularies — Producer → Tool Translation

A reference that bridges what the LLM knows about named producers (from training data)
to what LivePilot can do in Ableton. For each artist: **sonic fingerprint** (what the
sound IS), **reach for** (LivePilot devices / tools to use), **avoid** (what kills the
aesthetic), **key techniques** (specific technique names from `sample-techniques.md`,
`sound-design-deep.md`, or the atlas `signature_techniques` field).

This is NOT a recipe book. The LLM still makes every creative decision. These entries
just ensure "make it sound like X" has a concrete translation path into LivePilot's
tool surface, instead of the LLM guessing at device names.

> Cross-references: when a technique appears in quotes like `"dub_throw"`, grep
> `sample-techniques.md` or device `signature_techniques` for the full recipe.

---

## Deep Minimal / Microhouse

### Ricardo Villalobos
**Sonic fingerprint:** Micro-sampled vocals and found sounds, off-grid percussion with
South American polyrhythms, sub-bass at 40-50 Hz, tracks that evolve across 15+ minutes
without repetition.
**Reach for:** Simpler (slice mode), Snipper, PitchLoop89, Latin Percussion pack, Drone Lab
(Harmonic Drone Generator for sub-bed), Lost and Found (found-sound palette),
Convolution Reverb. `sub_low` analyzer band for kick fundamental diagnostics.
**Avoid:** Quantized 4/4 drums, bright kicks, repetitive 8-bar loops, stock presets,
aggressive sidechain.
**Key techniques:** `"Vocal micro-chop (Akufen)"` (simpler), `"Villalobos sub-bass layer"`
(simpler), `"dub_throw"` (mixing), micro-modulation (filter + pitch at <5% depth).
**Genre affinity:** `minimal_techno`, `deep_minimal`, `microhouse`.

### Akufen (Marc Leclair)
**Sonic fingerprint:** Micro-second vocal/radio clippings triggered percussively to form
melodic + rhythmic content simultaneously. "My Way" album is the canonical reference.
**Reach for:** Simpler (slicing mode, 1/64 length), Snipper (Building Max Devices),
PitchLoop89 on sliced material, Auto Filter on drum bus.
**Avoid:** Coherent vocal samples (longer than one syllable), pitched singing,
long-sustain material.
**Key techniques:** `"Vocal micro-chop (Akufen)"` (the NAME of this technique literally
comes from this artist), `"micro_chop"` (sample-techniques.md), `"stab_isolation"`.
**Genre affinity:** `microhouse`.

### Isolée / Luomo
**Sonic fingerprint:** Lush, slow-evolving microhouse with melodic pads, warm filtered
bass, constant micro-variation (no 4-bar loop ever sounds identical to the last).
**Reach for:** Drift + Chorus-Ensemble for warm pads, Poli for melodic stabs,
Variations (Performance Pack) for morph-across-bars, Tree Tone for asymmetric
note cascades, Wavetable with slow position LFO.
**Avoid:** Rigid quantization, static patches, dry mixes.
**Key techniques:** `"Neo-soul Rhodes-adjacent keys"` (drift), `"Morphing ambient pad"`
(wavetable), `"reverse_layer"`, Variations-driven chord morph across 16 bars.
**Genre affinity:** `microhouse`, `deep_house`.

---

## Dub Techno / Dub

### Basic Channel / Rhythm & Sound (Moritz von Oswald + Mark Ernestus)
**Sonic fingerprint:** Space IS the instrument. Chord stabs feeding long filtered delay
and reverb tails that carry the harmonic and melodic content. Kick-snare 4/4 but
swimming in cavernous space.
**Reach for:** Convolution Reverb (Farfisa Spring IR, Stocktronics RX-4000), Ping-Pong
Delay with filter on return, Auto Filter on delay send, Utility for narrow-to-mono sub,
Drift/Poli for chord stab.
**Avoid:** Dry signals, short tails, bright top-end, pre-mixed "finished" presets.
**Key techniques:** `"The dub chord"` (sound-design-deep.md — chord → filtered delay →
return-filter becomes the melody), `"Reverb as harmony"`, `"Delay throws"`,
`"Dub sub-bass"` (bass.yaml).
**Genre affinity:** `dub_techno`, `dub`, `deep_minimal`.

### Wolfgang Voigt (Gas)
**Sonic fingerprint:** Orchestral loops (Wagner, Mahler) sampled, crushed into 4/4 kick,
blurred by heavy reverb into undifferentiated harmonic drone. Forest-deep ambient
with a pulse.
**Reach for:** Granulator III (Cloud mode, 200-500 ms grains), Harmonic Drone Generator
(Drone Lab), Convolution Reverb (cathedral IR), Auto Filter (slow LFO sweep),
Convolution Reverb at 100% wet on a send.
**Avoid:** Crisp transients, bright EQ, dry tails, anything recognizable as a sample source.
**Key techniques:** `"Grain cloud (Tim Hecker)"` (emit), `"Basinski tape degradation"`
(vector_grain), `"extreme_stretch"`, `"tail_harvest"`, `"drum_to_pad"`.
**Genre affinity:** `ambient`, `dub_techno`, `modern_classical`.

### Shackleton
**Sonic fingerprint:** Polyrhythmic 3-over-4 percussion, Middle-Eastern / ritual
aesthetics, low-end heavy, off-kilter kick placement, vocal samples treated as
found-sound.
**Reach for:** Polyrhythm (MIDI Tools), Phase Pattern (MIDI Tools), Latin Percussion,
Voice Box (vocal samples), Convolution Reverb, Microtuner (19-TET for ritual feel).
**Avoid:** 4/4 kick grid, Western equal-temperament melody, stock drum racks.
**Key techniques:** `"Make it weird without making it wrong"` (pack-knowledge.md),
`"euclidean_slice_trigger"`, asymmetric polymeter.
**Genre affinity:** `dub_techno`, `experimental`, `techno`.

---

## Ambient / Drone / Modern Classical

### William Basinski
**Sonic fingerprint:** Tape loops degrading across long durations. The DECAY of the
source IS the piece. Usually a single 2-8 second loop played for 30-60 minutes
with the tape physically eroding.
**Reach for:** Vector Grain (Inspired by Nature), Looper, Convolution Reverb (long
decay), Erosion, Dynamic Tube, Vinyl Distortion, cassette-IR Convolution.
**Avoid:** Crisp digital playback, fresh samples (use degraded/compressed source),
cuts between sections.
**Key techniques:** `"Basinski tape degradation"` (vector_grain.yaml), `"tail_harvest"`,
`"extreme_stretch"`, `"reverse_layer"`. Pair with Looper on a return for literal
tape-loop emulation.
**Genre affinity:** `ambient`, `drone`, `modern_classical`.

### Stars of the Lid
**Sonic fingerprint:** Sustained orchestral drones, no percussion, glacial pace,
string tremolos blurred into single sustained note, 10-20 minute pieces.
**Reach for:** Sampler (multi-velocity orchestral multi-sample), Vector Grain,
Granulator III, Convolution Reverb (cathedral/warehouse), SONiVOX Orchestral
Strings (pizzicato double-bass as bed), Tension (bowed cello).
**Avoid:** Any percussion, drum samples, rhythmic elements, short sounds.
**Key techniques:** `"Orchestral multi-velocity"` (sampler), `"Bowed cello low register"`
(tension), `"Slow-motion sustain"` (vector_grain), `"spectral_freeze"`.
**Genre affinity:** `ambient`, `drone`, `modern_classical`.

### Tim Hecker
**Sonic fingerprint:** Loud-but-fuzzy drone clouds, distorted harmonic content,
digital grain from deliberately overloaded DSP, melody hidden inside noise.
**Reach for:** Vector Grain, Granulator III (Cloud mode with pitch spread), Emit
(Inspired by Nature), Erosion, Saturator, Convolution Reverb with custom IRs,
Dynamic Tube.
**Avoid:** Clean signal chains, dry tracks, traditional mix philosophy (subtlety).
**Key techniques:** `"Grain cloud (Tim Hecker)"` (emit.yaml — this technique literally
named for this artist), `"granular_scatter"`, `"extreme_stretch"`, `"spectral_freeze"`,
harmonic saturation on every bus.
**Genre affinity:** `ambient`, `drone`, `experimental`, `idm`.

### Jóhann Jóhannsson / Max Richter
**Sonic fingerprint:** Sustained string orchestral beds, neo-classical piano fragments,
occasional brass swells. Contemporary film-score aesthetic.
**Reach for:** Sampler (multi-velocity string libraries), Tension (bowed cello, pp),
SONiVOX Orchestral Strings, Upright Piano (Spitfire Bechstein), Convolution Reverb
(hall IR), Orchestral Brass / Woodwinds (pp only).
**Avoid:** Electronic percussion, modern production polish, compressed mix.
**Key techniques:** `"Bowed cello low register"` (tension), `"Orchestral multi-velocity"`
(sampler), `"Single sustained note pedal-down"` (Upright Piano from pack-knowledge.md).
**Genre affinity:** `modern_classical`, `cinematic`, `ambient`.

---

## IDM / Experimental Electronic

### Aphex Twin (Richard D. James)
**Sonic fingerprint:** Fast shifting timbres, melodic acid lines, detailed micro-percussion,
gliding portamento leads, FM-heavy sound design, occasional brutal distortion.
**Reach for:** Operator (FM with 6+ operators if layered), Analog (303-style acid),
Simpler with MIDI auto-trigger for rapid drum variation, Erosion, Pitch Hack, Roar
for distortion, Microtuner for non-equal temperament moments.
**Avoid:** Single-textured drones, slow-evolving pads (opposite of Hecker), preset
factory drum racks.
**Key techniques:** `"Aphex ambient FM pad"` (operator — algorithm-specific), `"303 acid
bass"` (analog), `"micro_chop"`, `"DX7 bell cluster"`, portamento-heavy mono leads.
**Genre affinity:** `idm`, `electronic`, `ambient`, `acid_techno`.

### Autechre
**Sonic fingerprint:** Abstract rhythmic programming, non-quantized micro-timing,
granular textures, generative processes where the track evolves by computation
not composition.
**Reach for:** Euclidean Rhythm generator (Sequencers pack), Phase Pattern, Slice
Shuffler, Vector FM, Vector Grain, Bouncy Notes (Inspired by Nature), Performer
(Performance Pack) for macro morphing, Microtuner (19-TET or larger).
**Avoid:** Quantized beats, equal temperament, straightforward arrangement.
**Key techniques:** `"euclidean_slice_trigger"`, `"Chaotic lock-in"` (vector_map),
`"Modulated bell cluster"` (vector_fm), asymmetric polymeter.
**Genre affinity:** `idm`, `experimental`, `electronic`.

### Oneohtrix Point Never (Daniel Lopatin)
**Sonic fingerprint:** Synth-as-voice, dense harmonic stacking, vapor-wave tonality,
sudden tempo shifts, cinematic sample work.
**Reach for:** Wavetable (morphing pads), Meld (dual-engine layering), Emit (grain
cloud vocals), Voice Box (vocal samples), Poli (retro pad), Pitch Hack, PitchLoop89.
**Avoid:** Minimal production philosophy, subtractive thinking.
**Key techniques:** `"Morphing ambient pad"` (wavetable), `"Retro stab"` (poli),
`"Layered evolving pad"` (meld), `"vocoder"` chain with synth carrier.
**Genre affinity:** `experimental`, `ambient`, `electronic`.

### Arca / SOPHIE
**Sonic fingerprint:** Hyper-detailed rhythmic programming, metallic percussion,
vocal pitch extremes, physical-sounding hits, impossible textures.
**Reach for:** Collision (mallet + metal percussion), Tension (plucked prepared string),
Corpus (physical modeling on non-pitched sources), Vector FM, Vocoder, Pitch Hack,
Snipper.
**Avoid:** Sampled drums, acoustic percussion realism, conservative mixing.
**Key techniques:** `"Inharmonic bell drone"` (collision), `"Metal-string drone"`
(tension), `"Noise Bow"` (corpus), extreme pitch shifts on vocals.
**Genre affinity:** `experimental`, `hyperpop`, `electronic`.

---

## Hip-Hop / Sampled Music

### J Dilla
**Sonic fingerprint:** Sampled breaks and soul loops, intentionally "drunk"
off-grid drum programming, warm saturated mix, chopped chord stabs from records.
**Reach for:** Simpler (slicing mode on classic breaks — Amen, Funky Drummer,
Impeach the President), Saturator, Vinyl Distortion, Erosion, Electric Keyboards
(for Rhodes chopped from vinyl), Tape Delay simulation via Grain Delay.
**Avoid:** Quantized drums, bright mixes, modern trap-style hi-hats.
**Key techniques:** `"J Dilla micro-timed kit"` (simpler.yaml — literally named for
this artist), `"slice_and_sequence"`, `"stab_isolation"`, `"Tape-warped EP"`
(electric).
**Genre affinity:** `hip_hop`, `lo_fi`, `soul`, `downtempo`.

### DJ Premier / RZA
**Sonic fingerprint:** Dusty chopped-soul loops, dirty kicks, snappy snares with
reverb, chord-stab-driven arrangement (the stab IS the song).
**Reach for:** Simpler (classic mode, crop tight around stab), Saturator, Erosion,
Vinyl Distortion, Convolution Reverb (plate or spring IR on snare), Golden Era
Hip-Hop Drums pack.
**Avoid:** Clean samples, modern drum samples, synth bass.
**Key techniques:** `"stab_isolation"` (sample-techniques.md), `"slice_and_sequence"`,
snare-through-Convolution-Reverb-at-100%-wet-on-send.
**Genre affinity:** `hip_hop`, `boom_bap`.

### Madlib
**Sonic fingerprint:** Obscure-sample-flipping, dense percussion layers, dusty mix,
hip-hop-adjacent-but-weird (jazz samples, library music, world music sources).
**Reach for:** Simpler (slicing on any non-obvious source), Chop and Swing pack
(sampled-soul samples), Latin Percussion, Voice Box, Roar for saturation.
**Avoid:** Obvious sample sources (Dilla-style soul loops), clean production.
**Key techniques:** `"micro_chop"`, `"vocal_chop_rhythm"`, `"reverse_layer"`,
unusual source material + straightforward drums.
**Genre affinity:** `hip_hop`, `lo_fi`, `experimental`.

---

## Dubstep / Bass Music

### Burial
**Sonic fingerprint:** Vinyl-crackle 2-step garage shuffle, ghostly pitched vocals,
low-mid bass (not extreme sub), atmospheric urban-decay aesthetic, rhythmic
imperfection.
**Reach for:** Simpler (vocal chopping), Grain Delay, Convolution Reverb (long
atmospheric tail), Vinyl Distortion, Chop and Swing pack (vinyl crackle racks),
Skitter and Step pack (garage hats), Erosion.
**Avoid:** Pristine digital, modern dubstep wobble bass, 128 BPM.
**Key techniques:** `"vocal_chop_rhythm"` (sample-techniques.md — Burial-inspired,
literally), `"granular_scatter"`, `"reverse_layer"`, vinyl-crackle-at--36dB-under-track.
**Genre affinity:** `dubstep`, `uk_garage`, `ambient`, `downtempo`.

### Skream / Mala (DMZ-era dubstep)
**Sonic fingerprint:** Sub-bass wobbles, half-time drums (140 BPM with beat on 3),
reggae/dub influence, heavy sidechain.
**Reach for:** Wavetable (wobble bass), Drum Essentials (dubstep kits), Echo
(dub-style delay), Auto Filter synced, Saturator, Ring Modulator via Operator.
**Avoid:** Full-step beats, bright overtones, fast tempos.
**Key techniques:** `"Wobble bass"` (wavetable), `"Reese-style bass"` (bass.yaml),
`"Delay throws"`, half-time drum programming.
**Genre affinity:** `dubstep`, `bass_music`, `dub`.

---

## Techno / House Canon

### Richie Hawtin (Plastikman)
**Sonic fingerprint:** Subtractive minimalism, single evolving source, percussive
percussion, dub-influenced space, long arrangements that progress by subtraction.
**Reach for:** Analog + Simpler, Convolution Reverb, Auto Filter with long LFO,
Utility for narrow-to-mono sub, Drone Lab for sustained sub-bed, Minimal techno kits.
**Avoid:** Thick layering, preset chains, reverb washes, additive arrangement thinking.
**Key techniques:** `"Hawtin subtractive pad"` (analog.yaml — literally named for
this artist), `"Micro-Modulation"` (sound-design-deep.md), `"Subtraction over
addition"` principle, single-source filter-automation as melody.
**Genre affinity:** `minimal_techno`, `deep_minimal`.

### Robert Henke (Monolake)
**Sonic fingerprint:** Detailed granular textures, pitch-shift-delay signatures,
generative-adjacent sound design, cinematic electronic.
**Reach for:** Granulator III (Henke made this), PitchLoop89 (Henke emulated hardware
his influences used), Convolution Reverb, Ableton's core synths via elaborate
mod-matrix setups.
**Avoid:** Simple preset chains.
**Key techniques:** `"PitchLoop89 dual detune"` (from pack-knowledge.md —
canonical Henke pair with Convolution Reverb), `"Granulator III Cloud mode"`,
`"tail_harvest"`.
**Genre affinity:** `minimal_techno`, `experimental`, `ambient`.

### Jeff Mills
**Sonic fingerprint:** Relentless percussive techno, minimal melody, sci-fi synth
stabs, unbroken 4/4 drive, layered hi-hat patterns, long arrangements.
**Reach for:** Drift (stabs), Operator (sci-fi bells), Drum Essentials 909 samples,
Phase Pattern (organic hat timing), Echo (tight delay on stabs), Saturator.
**Avoid:** Melodic harmony, breaks, restful moments.
**Key techniques:** `"Retro stab"` (poli), relentless 909 programming,
`"phase_pattern"` for hi-hat humanization.
**Genre affinity:** `techno`, `detroit_techno`.

### Moodymann / Theo Parrish
**Sonic fingerprint:** Dusty house with live soul samples, lo-fi aesthetic, warm
bass, organic feel from sample manipulation not quantization.
**Reach for:** Simpler (classic soul chops), Electric Keyboards (Rhodes), Saturator,
Chop and Swing pack, Vinyl Distortion, Bass (Creative Extensions), Live Drums kits.
**Avoid:** Pristine digital synthesis, quantized drums, modern house production.
**Key techniques:** `"Tape-warped EP"` (electric), `"slice_and_sequence"`,
`"stab_isolation"`, vinyl-saturated drum bus.
**Genre affinity:** `deep_house`, `soulful_house`, `hip_hop`.

### Daft Punk
**Sonic fingerprint:** Filtered disco loops, vocoder vocals, funk guitar samples,
side-chained 4/4, pitched-down vocal hooks.
**Reach for:** Vocoder, Auto Filter (band-pass sweeps), Simpler (disco loop chops),
Bass (Creative Extensions), Chorus-Ensemble, Compressor (heavy sidechain via
Envelope Follower).
**Avoid:** Non-sidechained kick/bass, clean vocals (use vocoder), long arrangements
without filter automation.
**Key techniques:** `"Classic Robot Voice"` (vocoder), `"Noise-Carried Drums"`,
band-pass-filter automation on disco samples, `"Reese-style bass"` (bass).
**Genre affinity:** `french_house`, `disco`, `nu_disco`.

---

## Footwork / Juke / Jungle

### Rashad / Spinn / Traxman (footwork)
**Sonic fingerprint:** 160 BPM, vocal-chop hyper-rhythms, sparse kick programming
(unpredictable), stuttered soul/hip-hop samples, triplet feels inside 4/4.
**Reach for:** Simpler (slicing on vocal/soul samples — short chops), Slice Shuffler
(MIDI Tools), Polyrhythm at 3:2 ratios, Trap Drums 808 samples (sparse use).
**Avoid:** Quantized-on-grid drums, sustained elements, bright leads.
**Key techniques:** `"vocal_chop_rhythm"` at aggressive tempo, `"slice_shuffler"`
on 1/16 chops, `"micro_chop"`.
**Genre affinity:** `footwork`, `juke`, `drum_and_bass`.

### Photek / Source Direct (jungle / atmospheric DnB)
**Sonic fingerprint:** Chopped amen breaks, sub-bass on long held notes, jazz/string
samples in melodic role, technical drum programming.
**Reach for:** Simpler (Amen break slicing), Bass for sub, SONiVOX Strings (pp
pizzicato as ghost layer), Convolution Reverb.
**Avoid:** Stock breakbeats, synth bass in place of sub-bass.
**Key techniques:** `"slice_and_sequence"` at 174 BPM on Amen, `"Reese bass"` (analog),
`"Villalobos sub-bass layer"` (simpler) for sub.
**Genre affinity:** `drum_and_bass`, `jungle`.

---

## Synthwave / 80s / Retro

### Com Truise / Tycho
**Sonic fingerprint:** 80s analog polysynth nostalgia, gated reverb on drums,
chorus-heavy leads, warm analog bass, arpeggiated sequences.
**Reach for:** Poli (Juno-style), Analog, Drift (warm synthwave pad), Chorus-Ensemble,
Gated Delay (Creative Extensions — the gated-reverb-drum aesthetic), Arpeggiator.
**Avoid:** Modern dance production, aggressive compression, digital-only chains.
**Key techniques:** `"Juno-style detuned chord"` (poli), `"Warm synthwave pad"`
(drift), `"Supersaw trance lead"` (wavetable) at reduced spread.
**Genre affinity:** `synthwave`, `vaporwave`, `electronic`.

### Boards of Canada
**Sonic fingerprint:** Degraded-tape analog warmth, detuned synthesizers, child-voice
samples, 70s children's TV aesthetic, slow tempos.
**Reach for:** Drift (warm detune), Simpler (degraded samples with Erosion), Tape-
Delay via Echo, Grain Delay, Vinyl Distortion, Electric Keyboards (tape-warped).
**Avoid:** Pristine samples, modern drum production, bright mixes.
**Key techniques:** `"Tape-warped EP"` (electric), `"reverse_layer"`, `"Dense grain
cloud"` (vector_grain) for vocal processing.
**Genre affinity:** `downtempo`, `lo_fi`, `electronica`.

---

## How to use this file

When an LLM-invoked workflow includes language like "make it sound like X" or
references a specific producer/group:

1. Match the artist name (or closest analog) to an entry here.
2. Read the **Sonic fingerprint** and the **Reach for** device list.
3. Query the atlas: `atlas_search(artist_device_name)` to confirm availability.
4. Read the named **Key techniques** — each one references either the
   per-device `signature_techniques` in the atlas or a technique name from
   `sample-techniques.md` / `sound-design-deep.md` for concrete steps.
5. **Avoid** section is a negative-prior — don't fight against it.

This file is intentionally incomplete. Add artists as workflows surface them.
The structure matters more than exhaustive coverage.

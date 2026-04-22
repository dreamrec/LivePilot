# Pack Knowledge — 44 Installed Ableton Packs

Machine-readable reference for all 44 packs installed in Live 12.4. Each entry has:
- **Essence** — one-line summary
- **Scores** — minimal / dub / cinematic (0-5)
- **Top devices** — best items to reach for from this pack
- **Aesthetic use** — when to open this pack, when to skip

Scores sourced from `docs/research/2026-04-22-ableton-packs-deep-analysis.md`. Individual device details in `mcp_server/atlas/enrichments/` (grep by `pack:` field for pack-to-device mapping).

---

## Tier S — Essential for deep-minimal / microhouse / ambient

### Granulator III (Robert Henke)
- **Essence:** THE granular synth. Three modes (Classic/Loop/Cloud), MPE, built-in capture.
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Cloud mode with 200-500ms grains on any sustained source.
- **Use when:** need evolving texture, drone bed, vocal cloud, or to de-recognize a sample.
- **Atlas entry:** [granulator_iii](mcp_server/atlas/enrichments/instruments/granulator_iii.yaml)

### PitchLoop89 (Robert Henke)
- **Essence:** Publison DHM 89 B2 emulation. Dual independent pitch-delay voices.
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Dual detune (+5 / -7 cents) on stabs; infinite feedback on clicks for pitched cascades.
- **Use when:** any sustained/pitched element that needs spatial character. Henke-canonical pair with Convolution Reverb.
- **Atlas entry:** [pitchloop89](mcp_server/atlas/enrichments/audio_effects/pitchloop89.yaml)

### Drone Lab
- **Essence:** 600+ samples, 70+ racks, **Harmonic Drone Generator** (Expert Math, 8-voice synth, microtonal tunings: Pelog/Pythagorean/JI/Solfeggio/Indian/EQ).
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Harmonic Drone Generator in Pelog/JI as sub-bed; bowed guitar samples through Granulator III Cloud mode.
- **Use when:** need a sustained harmonic shadow under the track at -30 dB, or microtonal drone that equal-tempered synths cannot produce.
- **Atlas entry:** [harmonic_drone_generator](mcp_server/atlas/enrichments/instruments/harmonic_drone_generator.yaml)

### Convolution Reverb
- **Essence:** 200+ IRs, Convolution Reverb Pro hybrid mode, IR Measurement Tool (sample your own rooms).
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Farfisa Spring IR on percussion (Christian Kleine's set); Stocktronics RX-4000 on stabs; any long cathedral/warehouse IR on click tails.
- **Use when:** the built-in Reverb is too digital. Always in the chain for minimal/dub.
- **Atlas entry:** [convolution_reverb](mcp_server/atlas/enrichments/audio_effects/convolution_reverb.yaml), [convolution_reverb_pro](mcp_server/atlas/enrichments/audio_effects/convolution_reverb_pro.yaml)

### Lost and Found
- **Essence:** 28 foley/DIY multisampled instruments — music box, melodica, Capri fan organ, DIY plastic guitar, kazoo, metal xylophone. 7 Drum Racks built from everyday objects (steel water bottle, analog clock, submerged objects).
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Capri fan organ as chord bed through long reverb; music box pitched down -24 semitones as hypnotic bass.
- **Use when:** need found-sound character without recording your own. Villalobos-pack hiding in the library.

### Inspired by Nature (Dillon Bastan)
- **Essence:** 7 visual/generative M4L devices — Vector FM, Vector Grain, Vector Delay, Vector Map, Emit, Bouncy Notes, Tree Tone.
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Bouncy Notes for asymmetric note cascades; Tree Tone for organic harmonic resonance; Vector Map for coupled multi-parameter modulation.
- **Use when:** need never-the-same-twice generative behavior. The most under-utilized pack for microhouse.
- **Atlas entries:** vector_fm, vector_grain, [vector_map](mcp_server/atlas/enrichments/utility/vector_map.yaml), vector_delay, emit, bouncy_notes, tree_tone (all in enrichments/).

### Glitch and Wash
- **Essence:** The closest official Ableton pack to the target aesthetic. Field recordings, bit-crushed clicks, resonant pads, drones.
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Field-recording loops as-is; bit-crushed clicks as ghost hats; resonant drone pads at -25 dB.
- **Use when:** first pack to raid in any minimal session.

### Voice Box
- **Essence:** 1100 vocal samples, 82 multisampled singers, 9 vocal-percussion Drum Racks, 47 vocal processing racks.
- **Scores:** Minimal 5 / Dub 4 / Cinematic 5
- **Top:** Breath/mouth samples as ghost hats; vocal-percussion drum racks as primary kit for "all-mouth" tracks; sustained vowels through Granulator III Cloud for vocal atmosphere beds.
- **Use when:** Akufen-style micro-vocal aesthetic. Critical.

### Latin Percussion
- **Essence:** 107 multisampled hand percussion — cuica, congas, claves, shakers, guiro, pandeiro, bells.
- **Scores:** Minimal 5 / Dub 3 / Cinematic 3
- **Top:** Cuica (friction drum, low + high) as Villalobos signature; clave through reverb; guiro scrape as ghost-hat alternative.
- **Use when:** traditional drum kit feels too rigid. Villalobos + Perlon-era minimal built on this.

### Upright Piano (Spitfire Bechstein)
- **Essence:** Single multisampled Bechstein Model 7 upright. Mechanical noise sampled separately.
- **Scores:** Minimal 5 / Dub 5 / Cinematic 5
- **Top:** Single sustained note pedal-down + slow-attack macro at 50% + Convolution Reverb = floating piano halo. Mechanical-noise-only passes as percussion.
- **Use when:** single-note piano statements. Best piano for minimal house.

---

## Tier A — High-value specialist tools

### Creative Extensions
- **Essence:** 8 devices — Pitch Hack, Gated Delay, Colour Limiter, Re-Enveloper, Spectral Blur, Melodic Steps, Bass, Poli.
- **Scores:** Minimal 4 / Dub 4 / Cinematic 4
- **Top:** [pitch_hack](mcp_server/atlas/enrichments/audio_effects/pitch_hack.yaml) for Akufen stutter; [spectral_blur](mcp_server/atlas/enrichments/audio_effects/spectral_blur.yaml) for reverse-reverb alternatives; [re_enveloper](mcp_server/atlas/enrichments/audio_effects/re_enveloper.yaml) for per-band envelope reshaping.
- **Use when:** need a creative FX that stock effects can't deliver.

### MIDI Tools (Philip Meyer)
- **Essence:** 5 clip-based MIDI generators/transformers — Polyrhythm, Phase Pattern, Stages, Retrigger, Slice Shuffler.
- **Scores:** Minimal 5 / Dub 4 / Cinematic 3
- **Top:** [phase_pattern](mcp_server/atlas/enrichments/midi_effects/phase_pattern.yaml) for organic timing; [polyrhythm](mcp_server/atlas/enrichments/midi_effects/polyrhythm.yaml) with Euclidean at asymmetric ratios; [slice_shuffler](mcp_server/atlas/enrichments/midi_effects/slice_shuffler.yaml) for one-bar reverse glitches.
- **Use when:** need organic humanization or asymmetric pattern generation. Requires Live 12.1+.

### Sequencers
- **Essence:** 3 M4L sequencers — Step Arp, SQ Sequencer, Rhythmic Steps.
- **Scores:** Minimal 4 / Dub 4 / Cinematic 3
- **Top:** [sq_sequencer](mcp_server/atlas/enrichments/midi_effects/sq_sequencer.yaml) with asymmetric per-lane step lengths (16/15/11); Rhythmic Steps with probability per step; Step Arp with Chance < 80% for organic missing-note arpeggios.
- **Use when:** need polymeric/polyrhythmic patterns that go beyond standard quantize.

### Performance Pack (Iftah)
- **Essence:** 4 live-performance tools — Performer, Variations, Arrangement Looper, Prearranger.
- **Scores:** Minimal 4 / Dub 4 / Cinematic 3
- **Top:** [variations](mcp_server/atlas/enrichments/utility/variations.yaml) is the studio gem — morph chord-stab effect chains across 8-16 bars without 50 automation lanes.
- **Use when:** live performance, but Variations especially useful in studio for chord-is-different-every-time behavior.

### CV Tools (Ableton)
- **Essence:** 10 M4L devices for Eurorack bridging. 4 work standalone without modular gear.
- **Scores:** Minimal 5 (w/ modular) / 3 (w/o) / Dub 5 / Cinematic 3
- **Top w/o modular:** [cv_lfo](mcp_server/atlas/enrichments/utility/cv_lfo.yaml) for extra LFOs, [cv_envelope_follower](mcp_server/atlas/enrichments/utility/cv_envelope_follower.yaml) for audio-driven modulation, [rotating_rhythm_generator](mcp_server/atlas/enrichments/utility/rotating_rhythm_generator.yaml) for standalone polyrhythm, [cv_shaper](mcp_server/atlas/enrichments/utility/cv_shaper.yaml) for custom envelope shapes.
- **Use when:** hybrid modular + DAW rig, OR when you need modulation options beyond what a synth exposes.

### Generators by Iftah
- **Essence:** Patterns (one-click drum generator) + Sting (acid-line performance tool).
- **Scores:** Minimal 4 / Dub 3 / Cinematic 2
- **Top:** [patterns_iftah](mcp_server/atlas/enrichments/midi_effects/patterns_iftah.yaml) for sparse minimal-techno patterns; [sting_iftah](mcp_server/atlas/enrichments/instruments/sting_iftah.yaml) detuned + low as mutating sub-bass.
- **Use when:** quick drum or bassline ideation.

### Microtuner
- **Essence:** Scala import, dual-deck scale blend, Lead/Follow MPE.
- **Scores:** Minimal 4 / Dub 3 / Cinematic 5
- **Top:** [microtuner](mcp_server/atlas/enrichments/midi_effects/microtuner.yaml) — 19-TET for minimal; Partch 43-tone for drones; automated Blend for harmonic drift.
- **Use when:** standard equal temperament feels wrong.

---

## Tier B — Useful in specific contexts

### Chop and Swing
- **Essence:** 3000+ elements, 24 Drum Racks, 100+ instrument racks, 340+ loops, 212 Tonal MIDI clips. Sampled-soul pocket.
- **Scores:** Minimal 4 / Dub 2 / Cinematic 3
- **Top:** Tonal MIDI clips on dry Rhodes; dusty break loops → Simpler Slice → re-sequence into Akufen-style micro-patterns; vinyl crackle effect racks at -36 dB under the track.

### Electric Keyboards
- **Essence:** 3 multisampled E-pianos — Suitcase Piano (Rhodes Stage 73), Wurly Piano (Wurlitzer 200A), Tonewheel Organ.
- **Scores:** Minimal 4 / Dub 5 / Cinematic 3
- **Top:** Single-note hold through chorus + tape sat + Convolution Reverb = Raresh-style chord stab. Never play chords.

### Drone Lab's Improvisation Sets
- **Essence:** 4 prepopulated Live Sets using clips + Follow Actions + mixer as generative ambience engines.
- **Scores:** Minimal 5 / Dub 4 / Cinematic 5
- **Use:** Load the set, tweak, bring layers in and out. Autonomous ambient bed factory.

### Building Max Devices
- **Essence:** 92 example M4L devices — tutorial pack. Some unexpectedly good: Snipper, Bell Tower, Filler.
- **Scores:** Minimal 3 / Dub 2 / Cinematic 2
- **Top:** [snipper](mcp_server/atlas/enrichments/audio_effects/snipper.yaml) for micro-chop re-pitching; [bell_tower](mcp_server/atlas/enrichments/instruments/bell_tower.yaml) FM bell through Convolution Reverb; [filler](mcp_server/atlas/enrichments/midi_effects/filler.yaml) for free MIDI drum generation.

### Chop and Swing's vinyl racks
- **Scores:** Minimal 4 / Dub 2 / Cinematic 3
- **Use:** Vinyl crackle effect racks at -36 dB under the track. Texture subtext.

### Golden Era Hip-Hop Drums (Sound Oracle)
- **Essence:** 20 dusty boom-bap kits. Despite the hip-hop branding, the texture is perfect for minimal.
- **Scores:** Minimal 4 / Dub 3 / Cinematic 2
- **Top:** Dusty rim/brush snares; tight compressed kicks; vinyl-bite hat samples as ghost top-end. Extract individual samples, rebuild into minimal kit.

### Drum Booth
- **Essence:** 20 kits with 16/32/64 pads. Recorded DRY — no room, no FX. Pure acoustic source.
- **Scores:** Minimal 4 / Dub 3 / Cinematic 3
- **Top:** Brush snare through long Convolution Reverb; rim click as ghost hat; experimental recordings as off-kit textures.

### Orchestral Mallets
- **Essence:** Vibraphone, marimba, crotales, glockenspiel, tubular bells, timpani. Multi-articulation.
- **Scores:** Minimal 4 / Dub 4 / Cinematic 5
- **Top:** Vibraphone single note + motor wobble through tape delay; crotales as high-freq shimmer; marimba low octave for warm plucked accents.

### Spitfire Brass / String Quartet
- **Essence:** Intimate chamber brass/strings, Air Edel Studios, vintage mics. Dry not Hollywood.
- **Scores:** Minimal 4 / Dub 3 / Cinematic 5
- **Top:** Single muted flugelhorn note (pp) through PitchLoop89 + Convolution Reverb = Arpiar dusty-horn. Cello sustain for bass-register warmth.

### Mood Reel
- **Essence:** 295+ instrument racks, designed in part by Aimée Portioli (Grand River) and Arovane — serious minimal/ambient pedigree.
- **Scores:** Minimal 4 / Dub 4 / Cinematic 5

---

## Tier C — Wrong aesthetic but still mineable

These packs were commissioned for genres far from minimal/microhouse/ambient, but every one contains *raw material* (one-shots, noise beds, dry multisamples) worth extracting. Never load the preset chains. Never use the genre MIDI. Strip the kits.

### Build and Drop (Puremagnetik)
- **Essence:** Festival EDM construction kits — 808s, saw-leads, risers, drops.
- **Scores:** Minimal 1 / Dub 2 / Cinematic 2
- **Top:** Riser/downlifter **sample folders** only — strip the kick+lead presets. 808 sub-tails repitched as minimal bass layers.
- **Use when:** need a risk-free atmospheric riser or noise sweep. Everything else is throwaway.
- **Avoid:** All preset racks — saturation chains are over-cooked for minimal.

### Drive and Glow (Native Instruments / Ableton)
- **Essence:** Saturated indie/synthwave chains — soft-clipped leads, tape-emulation pads.
- **Scores:** Minimal 2 / Dub 3 / Cinematic 3
- **Top:** Effect Racks for the saturation chains only — copy the guts (Saturator → Shifter → tape delay) and drop into your own signal path. Tape-flutter pads at -30 dB as hidden glue.
- **Use when:** want soft warmth without building the chain yourself.
- **Avoid:** All synthwave lead presets — wrong decade.

### Punch and Tilt (Ableton)
- **Essence:** Warehouse techno kit generator — rave stabs, distorted kicks, tilted hats.
- **Scores:** Minimal 3 / Dub 4 / Cinematic 1
- **Top:** Distorted kick one-shots (Drum Rack extraction), not the preset kicks-through-Drum-Buss chains. Tilted/pitched ride-cymbal samples as alien hi-hats.
- **Use when:** need warehouse grit without going full hardcore. Villalobos occasionally pitches these down 2 octaves.
- **Avoid:** MIDI clips — 130 BPM warehouse patterns, wrong tempo for minimal.

### Skitter and Step (Ableton)
- **Essence:** UK garage / 2-step / UKG percussion — hats, shuffled snares, vocal chops.
- **Scores:** Minimal 2 / Dub 2 / Cinematic 1
- **Top:** Shuffled closed-hat samples (built for 2-step, work for microhouse). Vocal "chop-and-cut" one-shots for Akufen stutter inputs.
- **Use when:** need shuffled hi-hat character that standard 909/606 doesn't give.
- **Avoid:** Garage bassline presets — wrong frequency balance for minimal bass.

### Trap Drums (Sound Oracle / Ableton)
- **Essence:** Modern trap kits — sub 808s, snappy snares, tight rolls.
- **Scores:** Minimal 1 / Dub 2 / Cinematic 1
- **Top:** **808 sub-tails only** as sub-bass layers under a minimal kick. Snappy clap one-shots as high-velocity accents (strip from kits).
- **Use when:** need sub-heavy low end without building an 808 from scratch.
- **Avoid:** Entire kits, all hi-hat MIDI rolls (trap signature, wrong for minimal).

### Beat Tools
- **Essence:** Generic drum-programming toolkit — kicks, snares, hats, claps, percs.
- **Scores:** Minimal 2 / Dub 2 / Cinematic 2
- **Top:** Raw one-shots — cherry-pick specific samples (a particular snap, a particular hat) and ignore the preset kits. Good "neutral" source material if you don't want a pack with opinions.
- **Use when:** building a kit from scratch, want neutral one-shots without aesthetic opinion.
- **Avoid:** Preset Drum Racks — too generic, no character.

### Drum Essentials
- **Essence:** Live 12's baseline drum kit library — acoustic + electronic + percussion across 30+ kits.
- **Scores:** Minimal 1 / Dub 2 / Cinematic 1
- **Top:** Goldbaby 606 and 808 samples (hidden in the electronic kit folders). Acoustic side-stick and rim-shot one-shots.
- **Use when:** need a specific drum-machine sample, not an entire kit.
- **Avoid:** Default kits — too safe, no character.

### SONiVOX Orchestral Brass
- **Essence:** 11 multisampled brass instruments — trumpet, French horn, trombone, tuba, ensembles.
- **Scores:** Minimal 3 / Dub 2 / Cinematic 5
- **Top:** Solo **muted French horn** pp for dusty Arpiar/Cinematic moments. Solo trumpet pp with long release as sustained pitch drone.
- **Use when:** need a single sustained brass note as a foreground texture — NEVER as ensemble.
- **Avoid:** All ensemble patches — too Hollywood for minimal.

### SONiVOX Orchestral Strings
- **Essence:** 12 multisampled strings — violins, violas, cellos, double basses, ensembles.
- **Scores:** Minimal 3 / Dub 2 / Cinematic 5
- **Top:** **Pizzicato double-bass** as ghost/kick layer in minimal — short, warm, percussive. **Solo cello sustain pp** for bass-register atmosphere bed.
- **Use when:** need pizzicato accents or single-note sustained string pad at low dynamic.
- **Avoid:** Ensemble sustains, legato patches — Hollywood energy.

### SONiVOX Orchestral Woodwinds
- **Essence:** 10 multisampled woodwinds — flute, oboe, clarinet, bassoon, ensembles.
- **Scores:** Minimal 3 / Dub 2 / Cinematic 5
- **Top:** **Solo flute pp sustained** through PitchLoop89 for drifting high register. **Solo bass clarinet pp** as low-register hidden-voice color.
- **Use when:** need a specific single woodwind color for a single note or short phrase.
- **Avoid:** Fast articulations, ensembles — too classical.

### Grand Piano (e-instruments)
- **Essence:** Steinway-style multisampled concert grand.
- **Scores:** Minimal 3 / Dub 2 / Cinematic 5
- **Top:** **Single staccato note** with fast release at velocity 60-90 as percussive 'tock'/'thunk'. Lid-open for resonance. Use Upright Piano (Spitfire Bechstein, Tier S) for anything sustained.
- **Use when:** need a percussive pitched hit, not a piano performance.
- **Avoid:** Sustained chords (too bright/concert-hall), legato phrases.

### Synth Essentials
- **Essence:** Default Live preset collection across Operator/Analog/Wavetable/Drift.
- **Scores:** Minimal 2 / Dub 2 / Cinematic 3
- **Top:** **Tension + Collision physical-modeling presets** for unusual bowed/struck sounds that aren't obvious presets. Otherwise build from scratch — Operator sine + one-op FM is more useful than any preset here.
- **Use when:** need a quick physical-modeling starter; otherwise build from scratch.
- **Avoid:** "Lead" / "Pad" category — too finished, all the same.

### Session Drums Club
- **Essence:** Acoustic drum kit recorded in a live club/medium room — ambient kit with baked-in room mics.
- **Scores:** Minimal 3 / Dub 3 / Cinematic 3
- **Top:** **Side-stick / rim-shot** as main snare or accent in minimal. Tambourine + delay as ghost rattles. Room ambience is already baked in — don't add more reverb.
- **Use when:** want a drum bed that fights your space (room mics add their own reverb character).
- **Avoid:** Full kits through Drum Buss — too rock.

### Session Drums Studio
- **Essence:** Dry studio-recorded acoustic kit — clean, no room, close-mic'd.
- **Scores:** Minimal 3 / Dub 3 / Cinematic 3
- **Top:** **Dry rim/brush snare** as starting point for Convolution Reverb experiments (apply your own space). Brush one-shots as percussion texture.
- **Use when:** want a drum source you can fully control spatially — apply your own reverb, don't fight theirs.
- **Avoid:** Direct preset use — the dryness feels sterile without post-processing.

### Core Library
- **Essence:** Everything that ships with Live 12 — all native presets across Analog/Operator/Wavetable/Drift/Simpler/Sampler + all native effect presets + the bundled sample library (Ambient & Atmospheres, Noise & FX, Live Essentials samples).
- **Scores:** Minimal 3 / Dub 3 / Cinematic 3
- **Top:** **Ambient & Atmospheres + Noise & FX sample folders** — the unsung gold. "Ethereal Voice 01-04 Dmin 90bpm", "FX Vocal Chant Backwards", "Vocal Chant Aye", "Ethereal Adlib Vocal" are hidden Villalobos bait. Search `samples` path first in `search_browser` before reaching for Splice.
- **Use when:** hunt these folders BEFORE opening any other pack. Most of Live's best texture material is hiding here.
- **Avoid:** Named genre presets ("Lead", "Pad", "Bass" categories in each synth) — too generic. Also avoid "Drum Kit Essentials" defaults — go to dedicated drum packs instead.

---

## Workflow: what to do when

**"Build me a minimal-techno track"**
1. Drone Lab (Harmonic Drone Generator bed) + Glitch and Wash (field recording atmosphere) + Latin Percussion (cuica + claves)
2. Add Granulator III on a return for vocal clouds
3. PitchLoop89 + Convolution Reverb at end of any sustained element
4. Phase Pattern on drum clips for organic timing
5. Variations on chord stabs for evolution without automation

**"Build a drum kit from samples"**
1. Golden Era Hip-Hop Drums (dusty snares) + Drum Booth (dry acoustic) + Latin Percussion (unusual hits)
2. Use `add_drum_rack_pad` tool — never repeated `load_browser_item`
3. Each sample → role-aware Simpler defaults via `load_browser_item(role="drum")`

**"Make it evolve"**
1. Granulator III Cloud mode on sustained elements
2. Variations with quantized morph on effect chains
3. Vector Map for coupled multi-parameter physical motion
4. SQ Sequencer with asymmetric per-lane lengths

**"Make it weird without making it wrong"**
1. Microtuner with 19-TET or Pelog scale
2. Harmonic Drone Generator in just intonation
3. Bouncy Notes / Tree Tone for unpredictable pattern generation
4. Inspired by Nature generally — physics-driven sound design

---

**End of reference.** Devices with atlas entries are linked. For per-device parameter details, grep `mcp_server/atlas/enrichments/` by device `id`.

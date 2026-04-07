# The Organism — LivePilot 1.9.14 Comprehensive Track & Stress-Test

**Date:** 2026-04-08
**Status:** Design
**Goal:** Build a 9-minute track fusing Ricardo Villalobos, Dabrye, Boards of Canada, and Depeche Mode — while stress-testing all 178 LivePilot tools across 17 domains.

---

## 1. Concept

### Musical Vision
A track that evolves like a living organism — starting from a single harmonic seed, growing through feedback loops where LivePilot's analysis, theory, and generative engines drive compositional decisions. No two 16-bar sections sound alike. The track never loops back on itself.

### Artist DNA Fusion
| Artist | Contribution | Production Signature |
|--------|-------------|---------------------|
| Ricardo Villalobos | Hypnotic minimal loops, micro-edits, long arcs | 120 BPM, Euclidean rhythms, phase drift, perlin automation |
| Dabrye | Detroit beat science, crunchy sampling | Resampled loops, bit-crush, off-grid swing, sidechain |
| Boards of Canada | Degraded nostalgia, detuned warmth | Tape hiss, Redux, detuned pads, lo-fi delays |
| Depeche Mode | Dark synth-pop, industrial bass, structure | Analog bass, Collision atmospheres, dramatic arrangement |

### Approach: Bottom-Up Evolutionary ("The Organism")
Tools don't just execute orders — they make creative decisions. Analyzer feedback drives mixing, theory engines choose harmony, generative algorithms compose rhythms, and perception validates the result. The track is a collaboration between human intent and tool intelligence.

---

## 2. Parameters

- **Tempo:** 120 BPM
- **Time Signature:** 4/4
- **Key:** Decided by theory tools (Tonnetz exploration from C minor and F# minor seeds)
- **Duration:** ~9 minutes (~270 bars)
- **Structure:** 7 acts, each with distinct emotional function
- **Test Coverage Target:** All 178 tools, all 17 domains

---

## 3. Seven-Act Structure

### Act I — "The Signal" (bars 1–32, ~1 min)
- **Mood:** Radio between stations. BoC's degraded nostalgia.
- **Elements:** Single detuned pad chord (key chosen by theory tools), filtered white noise, tape hiss, subliminal sub pulse
- **Tool Focus:** `detect_key_and_mode()`, `navigate_tonnetz()`, `find_and_load_device()`, `set_parameter()`, `apply_automation_shape()` (perlin on filter)
- **Compositional Intent:** Establish harmonic DNA. The pad chord seeds everything.

### Act II — "Pulse Emerges" (bars 33–80, ~1.5 min)
- **Mood:** Villalobos' hypnotic minimalism. Kick appears from sub frequencies.
- **Elements:** Euclidean kick, hihat micro-rhythms via phase-shift, pad evolves via neo-Riemannian P/L/R transforms every 8 bars
- **Tool Focus:** `generate_euclidean_rhythm()`, `generate_phase_shift()`, `layer_euclidean_rhythms()`, `navigate_tonnetz()`, `get_master_spectrum()` → analyze → adjust kick EQ
- **Compositional Intent:** Rhythm crystallizes from noise. Analyzer feedback tunes the kick's spectral slot.

### Act III — "The Machine Wakes" (bars 81–128, ~1.5 min)
- **Mood:** Dabrye's crunchy Detroit. Depeche Mode's industrial pulse.
- **Elements:** Resampled/chopped beat, dark bass sequence (harmony-guided), sidechain pump, bit-crushed percussion
- **Tool Focus:** `capture_audio()` → `analyze_spectrum_offline()` → resample, `suggest_next_chord()`, `apply_automation_recipe('sidechain_pump')`, `batch_set_parameters()`, MIDI I/O round-trip
- **Compositional Intent:** Introduce grit and harmonic movement. Bass line is theory-guided.

### Act IV — "False Dawn" (bars 129–176, ~1.5 min)
- **Mood:** BoC's melancholic beauty. A melodic theme appears.
- **Elements:** Tintinnabuli melody, lush reverb/delay sends, stereo widening, pad transforms via chromatic mediants
- **Tool Focus:** `generate_tintinnabuli()`, `suggest_chromatic_mediants()`, `analyze_harmony()`, `check_counterpoint()`, `set_track_send()`, `apply_automation_recipe('washout')`, FluCoMa `get_spectral_shape()`
- **Compositional Intent:** Peak beauty before the break. Voice-leading ensures mathematical smoothness.

### Act V — "The Break" (bars 177–208, ~1 min)
- **Mood:** Everything collapses. Tape-stop, filters close, elements dissolve.
- **Elements:** Tape stop on master, filter sweeps down, stutter effects, reversed samples, noise floor rises
- **Tool Focus:** `apply_automation_recipe('tape_stop')`, `apply_automation_recipe('stutter')`, `apply_automation_recipe('filter_sweep_down')`, `reverse_simpler()`, `crop_simpler()`, `get_momentary_loudness()`
- **Compositional Intent:** Controlled destruction. Every automation recipe tested in dramatic context.

### Act VI — "Resurrection" (bars 209–256, ~1.5 min)
- **Mood:** Villalobos meets Depeche Mode. Everything returns harder, denser, transformed.
- **Elements:** All previous elements mutated — transposed melody, new Euclidean layers, additive counter-melody, heavy automation on every device
- **Tool Focus:** `generate_additive_process()`, `transpose_notes_smart()`, `find_voice_leading_path()`, `classify_progression()`, ALL 16 curve types, `get_mix_snapshot()`, `get_track_meters()`
- **Compositional Intent:** Climax. Maximum density, maximum tool coverage.

### Act VII — "Dissolve" (bars 257–270+, ~1 min)
- **Mood:** Signal returns to static. BoC's endings.
- **Elements:** Elements remove one by one, final pad chord is Tonnetz-traveled version of opening
- **Tool Focus:** `apply_automation_recipe('fade_out')`, `apply_automation_recipe('stereo_narrow')`, `compare_to_reference()`, `analyze_loudness()`, `memory_learn()`, `export_clip_midi()`
- **Compositional Intent:** Clean closure + full perception/memory domain coverage.

---

## 4. Sonic Palette

### Rhythm Section

**Kick** (layered)
- Layer 1: Operator — sine sub kick, long decay, ~50Hz fundamental (Villalobos floor)
- Layer 2: Drum Rack — processed 808/909 one-shot (Dabrye transient)
- Chain: Saturator (warm tube) → EQ Eight (surgical low-mid cut) → Compressor (fast attack)
- Sidechain source for entire mix

**Hats & Micro-Percussion** (phase-shifted polyrhythm)
- Drum Rack with metallic/found-sound hits
- Chain: Redux (bit reduction) → Corpus (metallic resonance) → Auto Pan (micro-movement)
- Multiple Euclidean layers: 7/16, 5/16, 3/8

**Clap/Snare** (industrial snap)
- Simpler with layered clap + noise burst
- Chain: Overdrive → Reverb (short dark plate) → Gate (tight)

**Percussion Loop** (resampled from own session in Act III)
- Capture rhythm section → Simpler → chop/warp/reverse
- Chain: Beat Repeat → Grain Delay → Erosion

### Bass

**Sub Bass** (Villalobos hypnotic pulse)
- Analog: saw + sub oscillator, low-pass filtered, slow envelope
- Chain: Saturator (soft clip) → EQ Eight (HPF 30Hz, notch mud)
- Automation: filter cutoff via perlin, resonance via brownian

**Mid Bass / Acid Line** (Dabrye × Depeche Mode)
- Wavetable: gritty wavetable position modulated by LFO
- Chain: Pedal (distortion) → Auto Filter (resonant LP, envelope follower) → Chorus-Ensemble
- Automation: wavetable position via stochastic, filter via exponential

### Pads & Atmosphere

**Main Pad** (BoC detuned warmth)
- Wavetable or Drift: analog-style with pitch drift
- Chain: Chorus-Ensemble → Spectral Blur (M4L) → Reverb (hall, long decay) → Utility (width)
- Harmony: chords driven by `navigate_tonnetz()` — P/L/R every 8 bars
- Automation: blur via s_curve, reverb decay via spring, width via sine

**Tape Texture Layer** (BoC degraded nostalgia)
- Simpler with vinyl/tape noise sample
- Chain: Redux (12-bit, low SR) → EQ Eight (bandpass 200Hz–4kHz) → Utility (-18dB)
- Runs throughout as subliminal texture

**Dark Atmosphere** (Depeche Mode brooding undertow)
- Collision or Tension (physical modeling, metallic)
- Chain: Frequency Shifter → Echo (ping-pong, dark) → Reverb
- Sparse notes, long sustains, Acts IV–VI

### Melodic Elements

**Tintinnabuli Melody** (Act IV theme)
- Electric or Analog: clean bell-like tone
- Chain: Delay (dotted eighth, tape) → Reverb (medium plate) → Phaser (subtle)
- Generated by `generate_tintinnabuli()`, verified by `check_counterpoint()`

**Additive Counter-Melody** (Act VI build)
- Operator: FM, glassy harmonics
- Chain: Grain Delay → Auto Pan → Reverb
- Generated by `generate_additive_process()` — one note added per repetition

### Return Tracks

| Return | Purpose | Devices | Targets |
|--------|---------|---------|---------|
| A "Space" | Reverb | Hybrid Reverb (dark IR), pre-delay 40ms, decay 4-6s | Pads, melody, snare |
| B "Echo" | Delay | Echo (sync'd, filter in feedback, modulation, repitch) | Percussion, melody, bass stabs |
| C "Destroy" | Creative | Beat Repeat → Corpus → Saturator → Utility | Glitch moments Acts III, V, VI |
| D "Wash" | Ambient | Spectral Resonator/Resonators → Reverb (infinite) | Transitions, Act I/VII |

### Sidechain Architecture
- Kick → Bass (Compressor, `sidechain_pump` recipe)
- Kick → Pad (Compressor, gentler, slower release)
- Kick → Tape (Compressor, very subtle)
- All via `set_track_routing()` sidechain input

---

## 5. Compositional Intelligence — Feedback Loops

### Loop 1: Harmonic Evolution Engine
```
Act I:   navigate_tonnetz("C", "minor", depth=3) → map reachable chords
         navigate_tonnetz("F#", "minor", depth=2) → alternative palette
         → Pick darkest cluster → KEY DECIDED

Act II:  suggest_next_chord(style="modal") per 8-bar phrase
         classify_progression() validates no pop cliches

Act IV:  suggest_chromatic_mediants() → "False Dawn" chromatic shift
         analyze_voice_leading() ensures smoothness < 0.3

Act VI:  find_voice_leading_path(act_I_chord, most_distant_chord, max_steps=6)
         → Climax progression = shortest path between opening and furthest point
```

### Loop 2: Spectral Feedback
```
After each element added:
  get_master_spectrum() → 8-band analysis

  sub > -6dB relative    → reduce bass or HPF
  low_mid buildup        → cut mud frequencies via EQ Eight
  high too bright        → add Redux or reduce sample rate
  air absent             → boost tape hiss or add exciter

  get_spectral_shape() → centroid, spread, flatness
  centroid > 3000Hz      → too bright for minimal techno
  flatness > 0.7         → too much noise, need tonal content
  spread < 500Hz         → too narrow, need harmonic movement
```

### Loop 3: Rhythmic Intelligence
```
Act II:  generate_euclidean_rhythm(16, 4, 0) — 4-on-floor kick
         layer_euclidean_rhythms([{16,7,2}, {16,5,1}, {16,3,0}]) — hat web
         generate_phase_shift(hat_pattern, voices=2, drift=1) — Reich drift

Act VI:  New Euclidean patterns with different step counts
         generate_additive_process() — Glass technique on percussion
```

### Loop 4: Automation Intelligence
```
analyze_for_automation() → tool suggests what needs movement
→ Follow suggestions + add own choices

All 16 curve types mapped to parameters:
  linear → volume fade (I), exponential → filter sweep up (III),
  logarithmic → filter sweep down (V), s_curve → crossfade (IV→V),
  sine → tremolo (II), sawtooth → sidechain pump (III),
  spike → dub throw (IV), square → stutter gate (V),
  steps → wavetable position (VI), perlin → filter drift (II),
  brownian → resonance wander (III), spring → post-break open (VI),
  bezier → custom melodic arc (IV), easing → reverb decay ease (VII),
  euclidean → Beat Repeat gate (V), stochastic → bit reduction (VI)

All 15 recipes applied across acts.
```

### Loop 5: Perception Validation (Act VII)
```
analyze_loudness() → integrated LUFS, true peak, LRA, streaming compliance
analyze_spectrum_offline() → offline spectral balance vs real-time consistency
compare_to_reference() → full comparison engine exercise
read_audio_metadata() → verify WAV integrity
```

### Loop 6: Memory & Learning
```
Throughout: memory_learn() for notable techniques
End: memory_list(), memory_recall(), memory_get(), memory_replay(),
     memory_favorite(), memory_update()
```

---

## 6. Execution Phases

### Phase 0: Session Setup & Diagnostics
- `get_session_info()`, `set_tempo(120)`, `set_time_signature(4,4)`
- `get_session_diagnostics()`, `toggle_metronome()`
- `get_browser_tree()`, `get_master_spectrum()`, `check_flucoma()`

### Phase 1: Harmonic DNA
- `navigate_tonnetz()` × 2 seeds → map chords
- `classify_progression()` → pick key
- `suggest_next_chord()` × 4 → 32-bar cycle
- `analyze_voice_leading()`, `suggest_chromatic_mediants()`

### Phase 2: Track Architecture
- `create_midi_track()` × ~10, `create_audio_track()` × ~2
- `create_return_track()` × 4
- `set_track_name()` × 16, `set_track_color()` × 16
- `create_scene()` × 7+, `set_scene_name()` × 7

### Phase 3: Device Loading & Sound Design
- `search_browser()` × ~10, `find_and_load_device()` × ~48
- `batch_set_parameters()` × ~10, `set_parameter()` × many
- `get_device_info()`, `set_track_routing()` × 3, `set_track_send()` × multiple
- `walk_device_tree()`, `get_hidden_parameters()`, `get_display_values()`

### Phase 4: Composition — Acts I–IV
- Euclidean rhythms, phase shifts, layered rhythms → `add_notes()`
- Theory-guided bass and chord sequences
- `generate_tintinnabuli()` for melody
- `check_counterpoint()`, `set_note_velocity()`, note probability
- `quantize_notes()`, `transpose_notes()`

### Phase 5: Composition — Acts V–VII + Resampling
- `generate_additive_process()`, `transpose_notes_smart()`
- `find_voice_leading_path()`, `classify_progression()`
- MIDI I/O round-trip: `export_clip_midi()` → `analyze_midi_file()` → `import_midi_file()` → `get_piano_roll()`
- Audio capture: `capture_audio()` → `capture_stop()`
- Simpler workflow: `load_sample_to_simpler()` → `get_simpler_slices()` → `reverse_simpler()` → `crop_simpler()` → `warp_simpler()`
- `duplicate_clip()`, `duplicate_notes()`

### Phase 6: Automation & Movement
- `analyze_for_automation()` → tool-driven suggestions
- `apply_automation_recipe()` × 15 (all recipes)
- `apply_automation_shape()` × 16 (all curve types)
- `generate_automation_curve()` (preview)
- `get_clip_automation()`, `clear_clip_automation()` (CRUD cycle)
- `set_arrangement_automation()`, `get_arrangement_automation()`, `clear_arrangement_automation()`

### Phase 7: Mixing & Spectral Balancing
- Real-time: `get_master_spectrum()`, `get_master_rms()`, `get_detected_key()`
- FluCoMa: `get_spectral_shape()`, `get_mel_spectrum()`, `get_chroma()`, `get_momentary_loudness()`
- Mix adjustments: `set_track_volume()`, `set_track_pan()`, `set_track_send()`, `set_master_volume()`
- Monitoring: `get_track_meters()`, `get_master_meters()`, `get_mix_snapshot()`
- Verification: `get_return_tracks()`, `get_master_track()`

### Phase 8: Arrangement & Scenes
- `get_scene_matrix()`, `fire_scene()` × 7, `get_playing_clips()`
- `toggle_cue_point()` × 7, `jump_to_cue()`, `jump_to_time()`
- `create_arrangement_clip()`, `fire_scene_clips()`, `stop_all_clips()`
- `set_session_loop()`, `set_clip_launch()` (all modes), `set_clip_warp_mode()`
- `get_cue_points()`, `set_scene_tempo()`, `duplicate_scene()`
- `start_recording()` → `stop_recording()`, `capture_midi()`

### Phase 9: Final Analysis & Memory
- Capture: `capture_audio()` → offline analysis
- Perception: `analyze_loudness()`, `analyze_spectrum_offline()`, `compare_to_reference()`, `read_audio_metadata()`
- FluCoMa: `get_onsets()`, `get_novelty()`
- Memory: `memory_learn()` × 5-8, `memory_recall()`, `memory_get()`, `memory_replay()`, `memory_list()`, `memory_favorite()`, `memory_update()`
- Warp: `get_warp_markers()`, `add_warp_marker()`, `move_warp_marker()`, `remove_warp_marker()`
- Preview: `scrub_clip()`, `stop_scrub()`

### Phase 10: Session Housekeeping
- Verification: `get_notes()`, `get_clip_info()`, `get_track_info()`, `get_scenes_info()`
- State: `get_automation_state()`, `get_arrangement_undo_state()`
- Undo/redo: `undo()`, `redo()`, `get_recent_actions()`
- Final: `get_session_diagnostics()`, `freeze_track()`, `get_freeze_status()`, `flatten_track()`
- Extra: `randomize_device()`, `save_preset()`, `get_clip_file_path()`
- End: `stop_playback()`

---

## 7. Tool Domain Coverage Matrix

| Domain | Tools | Phases | Coverage |
|--------|-------|--------|----------|
| Transport (12) | All 12 | 0, 8, 10 | 100% |
| Tracks (17) | All 17 | 2, 10 | 100% |
| Clips (11) | All 11 | 4–8 | 100% |
| Notes (8) | All 8 | 4–5 | 100% |
| Devices (15) | All 15 | 3, 10 | 100% |
| Scenes (12) | All 12 | 2, 8 | 100% |
| Mixing (11) | All 11 | 7 | 100% |
| Arrangement (19) | All 19 | 6, 8 | 100% |
| Browser (4) | All 4 | 3 | 100% |
| Analyzer (29) | All 29 | 0, 2–9 | 100% |
| Automation (8) | All 8 | 6 | 100% |
| Perception (4) | All 4 | 9 | 100% |
| Theory (7) | All 7 | 1, 4 | 100% |
| Harmony (4) | All 4 | 1, 4, 5 | 100% |
| Generative (5) | All 5 | 4–5 | 100% |
| Memory (8) | All 8 | 9 | 100% |
| MIDI I/O (4) | All 4 | 5 | 100% |
| **TOTAL** | **178** | **0–10** | **100%** |

---

## 8. Success Criteria

### Musical
- Track is listenable and cohesive across 9 minutes
- All four artist influences are identifiable
- Harmonic progression is theoretically sound (verified by tools)
- Dynamic arc from silence → climax → dissolution is effective

### Technical (LivePilot Stress-Test)
- All 178 tools called at least once without error
- All 17 domains exercised
- All 16 automation curve types generated and applied
- All 15 automation recipes applied
- Feedback loops function: analyze → decide → create → verify
- MIDI I/O round-trip preserves data
- Audio capture → offline analysis pipeline works
- Memory system stores and retrieves techniques
- FluCoMa descriptors return valid data (if available)
- Perception tools validate streaming compliance

### Bugs/Issues Found
- Document any tool failures, unexpected behaviors, or missing capabilities
- Track response times for each tool call
- Note any parameter validation issues
- Flag any thread-safety or timing problems

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| M4L bridge not connected | All core tools work without it; analyzer tools gracefully degrade |
| FluCoMa not installed | `check_flucoma()` first; skip FluCoMa-specific tools if absent |
| Theory tools pick an awkward key | We explore 2 seeds; can manually override if result is unmusical |
| Too many devices → CPU overload | Freeze/flatten tracks after completing each act |
| Audio capture fails | Verified in v1.9.12; `capture_stop()` deadlock fixed |
| Session gets messy | `get_session_diagnostics()` at phase boundaries |
| Track exceeds 9 minutes | Strict bar counts per act; trim in arrangement |

---

## 10. Track Metadata

- **Working Title:** "Organism"
- **Tempo:** 120 BPM
- **Key:** TBD (theory-engine-decided)
- **Duration:** ~9:00
- **Influences:** Ricardo Villalobos, Dabrye, Boards of Canada, Depeche Mode
- **LivePilot Version:** 1.9.14
- **Tool Coverage:** 178/178 (target)

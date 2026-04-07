# The Organism — LivePilot 1.9.14 Comprehensive Track & Stress-Test

**Date:** 2026-04-08
**Status:** Design (rev 2 — post spec review, canonical tool names verified)
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

> **Sequencing note:** Spectral feedback loops (Loop 2) require active playback. During composition phases, we build clips first, then `fire_scene()` + `start_playback()` to run analyzer passes. Analysis informs adjustments, not real-time monitoring during clip construction.

### Act I — "The Signal" (bars 1–32, ~1 min)
- **Mood:** Radio between stations. BoC's degraded nostalgia.
- **Elements:** Single detuned pad chord (key chosen by theory tools), filtered white noise, tape hiss, subliminal sub pulse
- **Tool Focus:** `navigate_tonnetz()`, `find_and_load_device()`, `set_device_parameter()`, `apply_automation_shape()` (perlin on filter), `identify_scale()`
- **Compositional Intent:** Establish harmonic DNA. The pad chord seeds everything.

### Act II — "Pulse Emerges" (bars 33–80, ~1.5 min)
- **Mood:** Villalobos' hypnotic minimalism. Kick appears from sub frequencies.
- **Elements:** Euclidean kick, hihat micro-rhythms via phase-shift, pad evolves via neo-Riemannian P/L/R transforms every 8 bars
- **Tool Focus:** `generate_euclidean_rhythm()`, `generate_phase_shift()`, `layer_euclidean_rhythms()`, `navigate_tonnetz()`, spectral feedback after playback pass
- **Compositional Intent:** Rhythm crystallizes from noise. Analyzer feedback tunes the kick's spectral slot.

### Act III — "The Machine Wakes" (bars 81–128, ~1.5 min)
- **Mood:** Dabrye's crunchy Detroit. Depeche Mode's industrial pulse.
- **Elements:** Resampled/chopped beat, dark bass sequence (harmony-guided), sidechain pump, bit-crushed percussion
- **Tool Focus:** `fire_scene()` + `capture_audio()` → `analyze_spectrum_offline()` → resample via `load_sample_to_simpler()`, `suggest_next_chord()`, `apply_automation_recipe('sidechain_pump')`, `batch_set_parameters()`, MIDI I/O round-trip
- **Compositional Intent:** Introduce grit and harmonic movement. Bass line is theory-guided.

### Act IV — "False Dawn" (bars 129–176, ~1.5 min)
- **Mood:** BoC's melancholic beauty. A melodic theme appears.
- **Elements:** Tintinnabuli melody, lush reverb/delay sends, stereo widening, pad transforms via chromatic mediants
- **Tool Focus:** `generate_tintinnabuli()`, `suggest_chromatic_mediants()`, `analyze_harmony()`, `detect_theory_issues()`, `set_track_send()`, `apply_automation_recipe('washout')`, FluCoMa `get_spectral_shape()`
- **Compositional Intent:** Peak beauty before the break. Voice-leading analysis ensures mathematical smoothness.

### Act V — "The Break" (bars 177–208, ~1 min)
- **Mood:** Everything collapses. Tape-stop, filters close, elements dissolve.
- **Elements:** Pitch device automation for tape-stop effect, filter sweeps down, stutter effects, reversed samples, noise floor rises
- **Tool Focus:** `apply_automation_recipe('tape_stop')` (on Pitch device), `apply_automation_recipe('stutter')`, `apply_automation_recipe('filter_sweep_down')`, `reverse_simpler()`, `crop_simpler()`, `get_momentary_loudness()`
- **Compositional Intent:** Controlled destruction. Automation recipes tested in dramatic context.
- **Note:** `tape_stop` recipe requires a Pitch MIDI effect loaded on target track; automate its Semitones parameter.

### Act VI — "Resurrection" (bars 209–256, ~1.5 min)
- **Mood:** Villalobos meets Depeche Mode. Everything returns harder, denser, transformed.
- **Elements:** All previous elements mutated — transposed melody, new Euclidean layers, additive counter-melody, heavy automation on every device
- **Tool Focus:** `generate_additive_process()`, `transpose_smart()`, `transpose_notes()`, `find_voice_leading_path()`, `classify_progression()`, ALL 16 curve types, `get_mix_snapshot()`, `get_track_meters()`
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
- `fire_scene()` to play rhythm → `capture_audio()` → `load_sample_to_simpler()` → chop/warp/reverse
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
- Generated by `generate_tintinnabuli()`, verified by `detect_theory_issues()`

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
         identify_scale() to confirm scale from chosen chord set

Act II:  suggest_next_chord(style="modal") per 8-bar phrase
         classify_progression() validates no pop cliches

Act IV:  suggest_chromatic_mediants() → "False Dawn" chromatic shift
         find_voice_leading_path() to verify smoothness of shift

Act VI:  find_voice_leading_path(act_I_chord, most_distant_chord, max_steps=6)
         → Climax progression = shortest path between opening and furthest point
```

### Loop 2: Spectral Feedback (requires playback — run after building clips)
```
After building clips for an act:
  fire_scene() → start_playback()
  get_master_spectrum() → 8-band analysis

  sub > -6dB relative    → reduce bass or HPF via set_device_parameter()
  low_mid buildup        → cut mud frequencies via EQ Eight
  high too bright        → add Redux or reduce sample rate
  air absent             → boost tape hiss or add exciter

  get_spectral_shape() → centroid, spread, flatness
  centroid > 3000Hz      → too bright for minimal techno
  flatness > 0.7         → too much noise, need tonal content
  spread < 500Hz         → too narrow, need harmonic movement

  stop_playback() → resume building
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

All 16 curve types mapped to specific parameters:
  linear      → volume fade in on Tape track (I)
  exponential → filter sweep up on Sub Bass (III)
  logarithmic → filter sweep down on Pad (V)
  s_curve     → crossfade Pad old→new chord (IV→V)
  sine        → tremolo on Pad volume (II), auto_pan recipe on hats
  sawtooth    → sidechain_pump shape on Bass Compressor (III)
  spike       → dub_throw send to Return D "Wash" (IV)
  square      → stutter gate on percussion (V)
  steps       → wavetable position on Acid Bass (VI)
  perlin      → filter cutoff drift on Sub Bass (II)
  brownian    → resonance wander on Acid Bass Auto Filter (III)
  spring      → post-break filter re-open on Pad (VI)
  bezier      → custom melodic filter arc on Melody delay (IV)
  easing      → reverb decay ease-out on Return A (VII)
  euclidean   → Beat Repeat gate pattern on Return C (V)
  stochastic  → bit reduction movement on Redux (VI)

All 15 recipes mapped to specific acts/tracks:
  filter_sweep_up   → Sub Bass filter, Act III build
  filter_sweep_down → Pad filter, Act V collapse
  dub_throw         → Send to Return D, Act IV transitions
  tape_stop         → Pitch device on Melody track, Act V (requires Pitch MIDI effect)
  build_rise        → HP filter + volume + reverb on all tracks, Act II→III transition
  sidechain_pump    → Bass Compressor via kick, Act III onward
  fade_in           → Master volume, Act I opening
  fade_out          → Master volume, Act VII closing
  tremolo           → Pad volume, Act II subtle breathing
  auto_pan          → Hats panning, Act II stereo movement
  stutter           → Percussion via Beat Repeat, Act V breakdown
  breathing         → Acid Bass filter cutoff, Act IV subtle movement
  washout           → Return A reverb feedback, Act IV→V transition
  vinyl_crackle     → Redux on Tape texture, Act I–III subtle
  stereo_narrow     → Utility width on master, Act VII final collapse
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
     memory_favorite(), memory_update(), memory_delete() (test on a duplicate)
```

---

## 6. Execution Phases

### Phase 0: Session Setup & Diagnostics
- `get_session_info()` — baseline state
- `set_tempo(120)` — lock tempo
- `set_time_signature(4, 4)` — lock time sig
- `get_session_diagnostics()` — check for leftover state
- `toggle_metronome()` — clean monitoring
- `get_browser_tree()` — verify browser access
- `get_browser_items()` — browse a specific category
- `get_master_spectrum()` — verify M4L bridge alive
- `check_flucoma()` — verify advanced descriptors
- `start_playback()` / `stop_playback()` — verify transport

### Phase 1: Harmonic DNA (stateless theory tools — no clips needed)
- `navigate_tonnetz("C", "minor", depth=3)` — map reachable chords from seed 1
- `navigate_tonnetz("F#", "minor", depth=2)` — map from seed 2
- `classify_progression()` on candidate sequences — pick darkest
- `suggest_next_chord()` × 4 — build 32-bar harmonic cycle
- `suggest_chromatic_mediants()` — bank distant chords for Act IV
- `identify_scale()` — confirm scale from chosen chord set

### Phase 2: Track Architecture
- `create_midi_track()` × ~10 — Kick, Hat, Clap, Perc, Sub, Acid, Pad, Tape, Dark, Melody
- `create_audio_track()` × ~2 — Resample, Bounce
- `create_return_track()` × 4 — Space, Echo, Destroy, Wash
- `set_track_name()` × 16
- `set_track_color()` × 16
- `set_track_arm()` on Resample track
- `set_track_input_monitoring()` on audio tracks
- `set_track_mute()` — mute Resample initially
- `set_track_solo()` — test solo (then unsolo)
- `stop_track_clips()` — ensure clean state
- `set_group_fold()` — group rhythm tracks, fold
- `create_scene()` × 7+ — one per act
- `set_scene_name()` × 7 — "Act I" through "Act VII"
- `set_scene_color()` × 7 — visual coding
- `duplicate_scene()` — clone Act II for variation

### Phase 3: Device Loading & Sound Design
- `search_browser()` × ~10 — find instruments and effects
- `load_browser_item()` × ~5 — load by URI (alternative to find_and_load)
- `find_and_load_device()` × ~40 — place instruments and effects on tracks
- `get_device_info()` × spot checks — verify loaded device parameters
- `get_device_parameters()` × several — read all param names/ranges
- `batch_set_parameters()` × ~10 — configure instruments (oscillators, filters, envelopes)
- `set_device_parameter()` × many — fine-tune individual params
- `toggle_device()` — bypass/enable effect for comparison
- `set_track_routing()` × 3 — sidechain kick → bass/pad/tape
- `set_track_send()` × multiple — return track routing
- `walk_device_tree()` — inspect Drum Rack nested structure
- `get_rack_chains()` — enumerate Drum Rack chains
- `set_chain_volume()` — balance Drum Rack layers
- `get_hidden_parameters()` — explore non-automatable params
- `get_display_values()` — verify human-readable param strings
- `get_plugin_parameters()` — inspect any AU/VST plugins loaded
- `map_plugin_parameter()` — map a plugin param for automation
- `get_plugin_presets()` — browse plugin presets
- `get_device_presets()` — browse native device presets
- `set_simpler_playback_mode()` — configure Simpler (Classic/1-Shot/Slice)
- `delete_device()` — remove a placeholder device, replace with correct one

### Phase 4: Composition — Acts I–IV + Playback Passes

**Build clips:**
- `create_clip()` × many — MIDI clips for each element per act
- `set_clip_name()` × many — label every clip
- `set_clip_color()` × many — visual coding by act
- `set_clip_loop()` — configure loop regions
- `add_notes()` × many — all note data (supports velocity, probability, release_velocity fields)

**Generate rhythms:**
- `generate_euclidean_rhythm(16, 4, 0)` → kick pattern → `add_notes()`
- `layer_euclidean_rhythms([...])` → hat polyrhythm → `add_notes()`
- `generate_phase_shift(hat_pattern, voices=2, drift=1)` → phase drift → `add_notes()`

**Generate melody and harmony:**
- `generate_tintinnabuli(melody_notes, triad)` → Act IV melody → `add_notes()`
- `harmonize_melody()` — generate harmony part for melody
- `generate_countermelody()` — create countermelody for Act IV
- `suggest_next_chord(style="modal")` — each 8-bar phrase

**Verify composition:**
- `detect_theory_issues()` on melody vs bass — check parallel 5ths/octaves
- `analyze_harmony()` on clips with notes — chord detection, Roman numerals
- `modify_notes()` — adjust velocities, probability per note for humanization
- `quantize_clip()` — snap selected clips to grid
- `transpose_notes()` — pitch variations between acts
- `get_notes()` — read back to verify

**Playback analysis pass (after building each act's clips):**
- `fire_scene()` → `continue_playback()`
- `get_master_spectrum()` → 8-band analysis
- `get_master_rms()` → level check
- `get_detected_key()` → confirm harmonic center
- `stop_playback()`
- Adjust EQ/levels based on analysis

### Phase 5: Composition — Acts V–VII + Resampling

**Prerequisite:** `fire_scene()` Act I–III → `start_playback()` for capture material

**Resampling workflow:**
- `capture_audio(duration=8)` — record master bus
- `capture_stop()` — or let timer finish
- `load_sample_to_simpler()` — load captured audio
- `get_simpler_slices()` — examine slice points
- `reverse_simpler()` — BoC texture
- `crop_simpler()` — trim to sweet spot
- `warp_simpler()` — time-stretch
- `replace_simpler_sample()` — swap sample in existing Simpler (test with another capture)

**Continued composition:**
- `generate_additive_process()` — Glass counter-melody → `add_notes()`
- `transpose_smart()` — transpose Act IV melody preserving function (theory domain)
- `find_voice_leading_path(open_chord, distant_chord)` — climax progression
- `classify_progression()` on full sequence — validate harmonic structure
- `duplicate_notes()` — layer/thicken parts
- `remove_notes()` — thin out Act V breakdown
- `remove_notes_by_id()` — surgical removal of specific notes
- `duplicate_clip()` — copy across scenes

**MIDI I/O round-trip:**
- `export_clip_midi()` — write session clip to .mid
- `analyze_midi_file()` — statistics on exported file
- `extract_piano_roll()` — visualize as grid
- `import_midi_to_clip()` — reimport modified version

### Phase 6: Automation & Movement

**Intelligence-driven:**
- `analyze_for_automation()` — tool suggests what needs movement
- `get_automation_recipes()` — list all available recipes

**All 15 recipes applied to specific targets:**
- `apply_automation_recipe('fade_in')` — Master volume, Act I
- `apply_automation_recipe('filter_sweep_up')` — Sub Bass, Act III
- `apply_automation_recipe('sidechain_pump')` — Bass Compressor, Act III+
- `apply_automation_recipe('build_rise')` — HP + volume + reverb, Act II→III
- `apply_automation_recipe('tremolo')` — Pad volume, Act II
- `apply_automation_recipe('auto_pan')` — Hats panning, Act II
- `apply_automation_recipe('breathing')` — Acid Bass filter, Act IV
- `apply_automation_recipe('dub_throw')` — Send to Return D, Act IV
- `apply_automation_recipe('washout')` — Return A reverb, Act IV→V
- `apply_automation_recipe('vinyl_crackle')` — Redux on Tape, Acts I–III
- `apply_automation_recipe('filter_sweep_down')` — Pad filter, Act V
- `apply_automation_recipe('tape_stop')` — Pitch device Semitones, Act V
- `apply_automation_recipe('stutter')` — Beat Repeat, Act V
- `apply_automation_recipe('fade_out')` — Master volume, Act VII
- `apply_automation_recipe('stereo_narrow')` — Utility width, Act VII

**All 16 curve types via `apply_automation_shape()`:**
- linear, exponential, logarithmic, s_curve, sine, sawtooth, spike, square
- steps, perlin, brownian, spring, bezier, easing, euclidean, stochastic
- (each mapped to specific parameter/track/act per Loop 4 above)

**Preview and CRUD:**
- `generate_automation_curve()` — preview without writing
- `set_clip_automation()` — write custom envelope
- `get_clip_automation()` — read back envelopes
- `clear_clip_automation()` — clear and rewrite (test CRUD)

**Arrangement automation:**
- `set_arrangement_automation()` — long-form arrangement curves (Act transitions)
- Note: no `get_arrangement_automation` or `clear_arrangement_automation` exist; use session clip equivalents for CRUD testing

### Phase 7: Mixing & Spectral Balancing

**Real-time analysis (with playback running):**
- `get_master_spectrum()` — 8-band balance
- `get_master_rms()` — overall level
- `get_detected_key()` — confirm harmonic center

**FluCoMa descriptors (if available):**
- `get_spectral_shape()` — centroid, spread, flatness, kurtosis, rolloff, crest
- `get_mel_spectrum()` — 40-band detail
- `get_chroma()` — 12 pitch class energies
- `get_momentary_loudness()` — EBU R128 LUFS + true peak

**Mix adjustments:**
- `set_track_volume()` × all tracks — level balance
- `set_track_pan()` × selected tracks — stereo image
- `set_track_send()` × multiple — effect send levels
- `set_master_volume()` — final level
- `get_track_routing()` — verify routing setup
- `set_track_routing()` — adjust if needed

**Monitoring:**
- `get_track_meters()` × all — per-track peak check
- `get_master_meters()` — master peak check
- `get_mix_snapshot()` — full state capture
- `get_return_tracks()` — verify return setup
- `get_master_track()` — master device chain

### Phase 8: Arrangement & Scenes

**Scene operations:**
- `get_scene_matrix()` — full clip grid overview
- `get_scenes_info()` — all scene metadata
- `fire_scene()` × 7 — test each act
- `fire_scene_clips()` with track filter — partial scene launch
- `get_playing_clips()` — verify what's running
- `stop_all_clips()` — panic test
- `set_scene_tempo()` on Act V — slight tempo drop for drama
- `delete_scene()` — remove a test scene

**Clip control:**
- `fire_clip()` — launch individual clips
- `stop_clip()` — stop individual clips
- `set_clip_launch()` — test all modes (Trigger/Gate/Toggle/Repeat)
- `set_clip_warp_mode()` — test on audio clips (Beats/Texture/Complex)
- `get_clip_info()` × several — metadata check

**Navigation:**
- `toggle_cue_point()` × 7 — mark each act boundary
- `get_cue_points()` — verify markers
- `jump_to_cue()` — navigate between acts
- `jump_to_time()` — jump to specific bar
- `set_session_loop()` — loop individual acts
- `back_to_arranger()` — switch to arrangement view

**Arrangement composition:**
- `create_arrangement_clip()` for key elements — timeline layout
- `add_arrangement_notes()` — write notes to arrangement clips
- `get_arrangement_notes()` — read back arrangement notes
- `modify_arrangement_notes()` — adjust velocities/timing
- `duplicate_arrangement_notes()` — copy patterns
- `transpose_arrangement_notes()` — pitch shift sections
- `remove_arrangement_notes()` — thin out sections
- `remove_arrangement_notes_by_id()` — surgical removal
- `set_arrangement_clip_name()` — label arrangement clips

**Recording:**
- `start_recording()` → fire scenes → `stop_recording()` — capture performance
- `capture_midi()` — capture recently-played MIDI

### Phase 9: Final Analysis & Memory

**Audio capture for offline analysis:**
- `fire_scene()` Act VI (densest) → `start_playback()`
- `capture_audio(duration=30)` — grab a section
- `capture_stop()` (or let timer finish)
- `stop_playback()`

**Offline perception:**
- `analyze_loudness()` — LUFS, peak, LRA, streaming compliance (Spotify/Apple/YouTube/Tidal)
- `analyze_spectrum_offline()` — spectral balance
- `compare_to_reference()` — full comparison engine
- `read_audio_metadata()` — verify WAV integrity

**FluCoMa analysis (with playback):**
- `get_onsets()` — transient detection
- `get_novelty()` — section boundary detection

**Warp marker operations (on captured audio clip):**
- `get_warp_markers()` — read timing
- `add_warp_marker()` — add new marker
- `move_warp_marker()` — shift timing
- `remove_warp_marker()` — clean up

**Simpler inspection:**
- `get_clip_file_path()` — get audio file path
- `scrub_clip()` — preview at specific beat
- `stop_scrub()` — stop preview

**Analyzer deep inspection:**
- `get_automation_state()` on key devices — check overrides
- `get_hidden_parameters()` — final check of non-automatable params

**Memory operations:**
- `memory_learn()` × 5-8 — save beat patterns, device chains, mix templates
- `memory_recall("minimal techno kick")` — test search
- `memory_get(id)` — full payload retrieval
- `memory_replay(id)` — get replay instructions
- `memory_list()` — browse saved library
- `memory_favorite(id, rating=5)` — rate best techniques
- `memory_update(id)` — modify a saved technique's tags
- `memory_delete(id)` — delete a test duplicate (test cleanup)

### Phase 10: Session Housekeeping

**Track operations:**
- `get_track_info()` × several — state verification
- `duplicate_track()` — clone a track for variation
- `delete_track()` — remove the clone
- `freeze_track()` on a dense track — test freeze
- `get_freeze_status()` — monitor progress
- `flatten_track()` on frozen — commit to audio

**Undo/redo:**
- `undo()` — test undo
- `redo()` — test redo
- `get_recent_actions()` — command log

**Final verification:**
- `get_session_diagnostics()` — clean session check
- `get_session_info()` — final state snapshot
- `stop_playback()` — clean end

---

## 7. Complete Tool Coverage — All 178 Tools

### Transport (12/12)
| Tool | Phase | Context |
|------|-------|---------|
| `get_session_info` | 0, 10 | Baseline + final state |
| `set_tempo` | 0 | Lock 120 BPM |
| `set_time_signature` | 0 | Lock 4/4 |
| `start_playback` | 0, 4, 5, 7 | Transport control |
| `stop_playback` | 0, 4, 5, 7, 10 | Transport control |
| `continue_playback` | 4, 7 | Resume from position |
| `toggle_metronome` | 0 | Clean monitoring |
| `set_session_loop` | 8 | Loop individual acts |
| `undo` | 10 | Test undo |
| `redo` | 10 | Test redo |
| `get_recent_actions` | 10 | Command log |
| `get_session_diagnostics` | 0, 10 | Health check |

### Tracks (17/17)
| Tool | Phase | Context |
|------|-------|---------|
| `get_track_info` | 10 | State verification |
| `create_midi_track` | 2 | All MIDI tracks |
| `create_audio_track` | 2 | Resample + Bounce |
| `create_return_track` | 2 | 4 returns |
| `delete_track` | 10 | Remove test clone |
| `duplicate_track` | 10 | Clone for variation |
| `set_track_name` | 2 | All tracks |
| `set_track_color` | 2 | All tracks |
| `set_track_mute` | 2 | Mute Resample initially |
| `set_track_solo` | 2 | Test solo/unsolo |
| `set_track_arm` | 2 | Arm Resample |
| `stop_track_clips` | 2 | Clean state |
| `set_group_fold` | 2 | Group rhythm tracks |
| `set_track_input_monitoring` | 2 | Audio tracks |
| `freeze_track` | 10 | Freeze dense track |
| `flatten_track` | 10 | Commit to audio |
| `get_freeze_status` | 10 | Monitor progress |

### Clips (11/11)
| Tool | Phase | Context |
|------|-------|---------|
| `get_clip_info` | 8 | Metadata check |
| `create_clip` | 4 | All MIDI clips |
| `delete_clip` | 8 | Remove test clip |
| `duplicate_clip` | 5 | Copy across scenes |
| `fire_clip` | 8 | Launch individual |
| `stop_clip` | 8 | Stop individual |
| `set_clip_name` | 4 | Label clips |
| `set_clip_color` | 4 | Visual coding |
| `set_clip_loop` | 4 | Loop regions |
| `set_clip_launch` | 8 | All launch modes |
| `set_clip_warp_mode` | 8 | Audio clip warp |

### Notes (8/8)
| Tool | Phase | Context |
|------|-------|---------|
| `add_notes` | 4 | All note data |
| `get_notes` | 4 | Read back verify |
| `remove_notes` | 5 | Thin Act V |
| `remove_notes_by_id` | 5 | Surgical removal |
| `modify_notes` | 4 | Velocity/probability |
| `duplicate_notes` | 5 | Layer/thicken |
| `transpose_notes` | 4 | Pitch variations |
| `quantize_clip` | 4 | Snap to grid |

### Devices (15/15)
| Tool | Phase | Context |
|------|-------|---------|
| `get_device_info` | 3 | Verify loaded devices |
| `get_device_parameters` | 3 | Read param names/ranges |
| `set_device_parameter` | 3, 4 | Fine-tune params |
| `batch_set_parameters` | 3 | Configure instruments |
| `toggle_device` | 3 | Bypass/enable comparison |
| `delete_device` | 3 | Replace placeholder |
| `load_device_by_uri` | 3 | Load by browser URI |
| `find_and_load_device` | 3 | Search + load |
| `set_simpler_playback_mode` | 3 | Configure Simpler mode |
| `get_rack_chains` | 3 | Drum Rack chains |
| `set_chain_volume` | 3 | Balance Drum Rack |
| `get_device_presets` | 3 | Browse native presets |
| `get_plugin_parameters` | 3 | Inspect AU/VST |
| `map_plugin_parameter` | 3 | Map for automation |
| `get_plugin_presets` | 3 | Browse plugin presets |

### Scenes (12/12)
| Tool | Phase | Context |
|------|-------|---------|
| `get_scenes_info` | 8 | All scene metadata |
| `create_scene` | 2 | 7+ scenes |
| `delete_scene` | 8 | Remove test scene |
| `duplicate_scene` | 2 | Clone for variation |
| `fire_scene` | 4, 5, 8 | Launch acts |
| `set_scene_name` | 2 | Label acts |
| `set_scene_color` | 2 | Visual coding |
| `set_scene_tempo` | 8 | Act V tempo drop |
| `get_scene_matrix` | 8 | Full clip grid |
| `fire_scene_clips` | 8 | Partial launch |
| `stop_all_clips` | 8 | Panic test |
| `get_playing_clips` | 8 | Verify playing |

### Mixing (11/11)
| Tool | Phase | Context |
|------|-------|---------|
| `set_track_volume` | 7 | Level balance |
| `set_track_pan` | 7 | Stereo image |
| `set_track_send` | 3, 7 | Return routing |
| `get_return_tracks` | 7 | Verify returns |
| `get_master_track` | 7 | Master chain |
| `set_master_volume` | 7 | Final level |
| `get_track_routing` | 7 | Verify routing |
| `set_track_routing` | 3 | Sidechain setup |
| `get_track_meters` | 7 | Per-track peaks |
| `get_master_meters` | 7 | Master peaks |
| `get_mix_snapshot` | 7 | Full state capture |

### Arrangement (19/19)
| Tool | Phase | Context |
|------|-------|---------|
| `get_arrangement_clips` | 8 | Timeline overview |
| `create_arrangement_clip` | 8 | Timeline layout |
| `add_arrangement_notes` | 8 | Write arrangement notes |
| `get_arrangement_notes` | 8 | Read back |
| `remove_arrangement_notes` | 8 | Thin sections |
| `remove_arrangement_notes_by_id` | 8 | Surgical removal |
| `modify_arrangement_notes` | 8 | Adjust velocity/timing |
| `duplicate_arrangement_notes` | 8 | Copy patterns |
| `transpose_arrangement_notes` | 8 | Pitch shift sections |
| `set_arrangement_clip_name` | 8 | Label clips |
| `set_arrangement_automation` | 6 | Long-form curves |
| `back_to_arranger` | 8 | Switch to arrangement view |
| `jump_to_time` | 8 | Navigate to bar |
| `capture_midi` | 8 | Capture recent MIDI |
| `start_recording` | 8 | Record performance |
| `stop_recording` | 8 | Stop recording |
| `get_cue_points` | 8 | Verify markers |
| `jump_to_cue` | 8 | Navigate acts |
| `toggle_cue_point` | 8 | Set markers |

### Browser (4/4)
| Tool | Phase | Context |
|------|-------|---------|
| `get_browser_tree` | 0 | Category overview |
| `get_browser_items` | 0 | Browse category |
| `search_browser` | 3 | Find devices |
| `load_browser_item` | 3 | Load by URI |

### Analyzer (29/29)
| Tool | Phase | Context |
|------|-------|---------|
| `get_master_spectrum` | 0, 4, 7 | 8-band analysis |
| `get_master_rms` | 4, 7 | Level check |
| `get_detected_key` | 4, 7 | Key confirmation |
| `get_hidden_parameters` | 3, 9 | Non-automatable params |
| `get_automation_state` | 9 | Override check |
| `walk_device_tree` | 3 | Nested rack structure |
| `get_clip_file_path` | 9 | Audio file path |
| `replace_simpler_sample` | 5 | Swap sample |
| `get_simpler_slices` | 5 | Slice points |
| `crop_simpler` | 5 | Trim |
| `reverse_simpler` | 5 | BoC texture |
| `warp_simpler` | 5 | Time-stretch |
| `get_warp_markers` | 9 | Read timing |
| `add_warp_marker` | 9 | Add marker |
| `move_warp_marker` | 9 | Shift timing |
| `remove_warp_marker` | 9 | Clean up |
| `scrub_clip` | 9 | Preview |
| `stop_scrub` | 9 | Stop preview |
| `get_display_values` | 3 | Human-readable params |
| `capture_audio` | 5, 9 | Record master bus |
| `capture_stop` | 5, 9 | Stop capture |
| `get_spectral_shape` | 7 | Centroid/spread/flatness |
| `get_mel_spectrum` | 7 | 40-band detail |
| `get_chroma` | 7 | Pitch class energies |
| `get_onsets` | 9 | Transient detection |
| `get_novelty` | 9 | Section boundaries |
| `get_momentary_loudness` | 7 | LUFS monitoring |
| `check_flucoma` | 0 | Verify FluCoMa |
| `load_sample_to_simpler` | 5 | Load captured audio |

### Automation (8/8)
| Tool | Phase | Context |
|------|-------|---------|
| `get_clip_automation` | 6 | Read envelopes |
| `set_clip_automation` | 6 | Write custom envelope |
| `clear_clip_automation` | 6 | Clear + rewrite |
| `apply_automation_shape` | 6 | All 16 curve types |
| `apply_automation_recipe` | 6 | All 15 recipes |
| `get_automation_recipes` | 6 | List recipes |
| `generate_automation_curve` | 6 | Preview without writing |
| `analyze_for_automation` | 6 | Tool-driven suggestions |

### Theory (7/7)
| Tool | Phase | Context |
|------|-------|---------|
| `analyze_harmony` | 4 | Chord detection on clips |
| `suggest_next_chord` | 1, 4 | Harmonic progression |
| `detect_theory_issues` | 4 | Parallel 5ths/octaves check |
| `identify_scale` | 1 | Scale from chord set |
| `harmonize_melody` | 4 | Generate harmony part |
| `generate_countermelody` | 4 | Create countermelody |
| `transpose_smart` | 5 | Function-preserving transpose |

### Perception (4/4)
| Tool | Phase | Context |
|------|-------|---------|
| `analyze_loudness` | 9 | LUFS/peak/LRA/compliance |
| `analyze_spectrum_offline` | 9 | Offline spectral balance |
| `compare_to_reference` | 9 | Full comparison |
| `read_audio_metadata` | 9 | WAV integrity |

### Generative (5/5)
| Tool | Phase | Context |
|------|-------|---------|
| `generate_euclidean_rhythm` | 4 | Kick + clap patterns |
| `layer_euclidean_rhythms` | 4 | Hat polyrhythm |
| `generate_tintinnabuli` | 4 | Act IV melody |
| `generate_phase_shift` | 4 | Reich hat drift |
| `generate_additive_process` | 5 | Glass counter-melody |

### Harmony (4/4)
| Tool | Phase | Context |
|------|-------|---------|
| `navigate_tonnetz` | 1 | Map reachable chords |
| `find_voice_leading_path` | 5 | Climax progression |
| `classify_progression` | 1, 5 | Validate harmonic structure |
| `suggest_chromatic_mediants` | 1 | Act IV distant chords |

### Memory (8/8)
| Tool | Phase | Context |
|------|-------|---------|
| `memory_learn` | 9 | Save techniques |
| `memory_recall` | 9 | Search library |
| `memory_get` | 9 | Full payload |
| `memory_replay` | 9 | Replay instructions |
| `memory_list` | 9 | Browse library |
| `memory_favorite` | 9 | Rate techniques |
| `memory_update` | 9 | Modify tags |
| `memory_delete` | 9 | Test cleanup |

### MIDI I/O (4/4)
| Tool | Phase | Context |
|------|-------|---------|
| `export_clip_midi` | 5 | Write to .mid |
| `import_midi_to_clip` | 5 | Load .mid to clip |
| `analyze_midi_file` | 5 | Statistics |
| `extract_piano_roll` | 5 | Grid visualization |

**TOTAL: 178/178 tools — 100% coverage**

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
- All 15 automation recipes applied to specific musical contexts (not bulk invocation)
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
| Spectral feedback before playback | All analyzer passes require `fire_scene()` + playback first |
| `tape_stop` recipe needs Pitch device | Load Pitch MIDI effect before applying recipe; specify device_index |
| `get_arrangement_automation` doesn't exist | Use `get_clip_automation` on session clips for CRUD testing |
| Plugin not available/opaque | `get_device_info()` reports health flags; substitute native device |

---

## 10. Track Metadata

- **Working Title:** "Organism"
- **Tempo:** 120 BPM
- **Key:** TBD (theory-engine-decided)
- **Duration:** ~9:00
- **Influences:** Ricardo Villalobos, Dabrye, Boards of Canada, Depeche Mode
- **LivePilot Version:** 1.9.14
- **Tool Coverage:** 178/178 (verified against test_tools_contract.py)

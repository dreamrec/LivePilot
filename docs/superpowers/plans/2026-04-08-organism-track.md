# The Organism — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 9-minute track (120 BPM, 7 acts) fusing Villalobos/Dabrye/BoC/Depeche Mode while stress-testing all 178 LivePilot tools across 17 domains.

**Architecture:** Bottom-up evolutionary ("The Organism") — generative/theory tools seed composition, analyzer feedback drives mixing, every tool call is a stress-test. 11 execution phases, each with specific domain coverage targets. The livepilot-core skill governs all MCP tool interactions.

**Tech Stack:** LivePilot 1.9.14 MCP server, Ableton Live 12, M4L Analyzer bridge, FluCoMa (optional)

**Spec:** `docs/superpowers/specs/2026-04-08-organism-track-design.md`

**Skill dependency:** Use `livepilot:livepilot-core` for all MCP tool calls. Use `livepilot:beat` as reference for rhythm construction patterns.

---

## Important Notes for Implementor

1. **This is MCP tool execution, not code writing.** Each step calls LivePilot MCP tools via the livepilot-core skill's livepilot-producer agent. There are no source files to create — the "artifact" is the Ableton Live session.
2. **Ableton must be running** with the LivePilot Remote Script installed and the M4L Analyzer on the master track.
3. **Tool calls are the tests.** A tool that returns successfully IS the test passing. A tool that errors IS a test failure. Document all errors.
4. **Spectral feedback requires playback.** Always `fire_scene()` + `start_playback()` before any analyzer call.
5. **Order matters.** Phases are sequential. Within a phase, steps are sequential unless marked "parallel-safe."
6. **Track all tool coverage** in a running tally. Target: 178/178 by end of Phase 10.

---

## Chunk 1: Foundation (Phases 0–2)

### Task 1: Session Setup & Diagnostics (Phase 0)

**Domain coverage target:** Transport (partial), Browser (partial), Analyzer (partial)
**Tools exercised:** 10

- [ ] **Step 1: Get baseline session state**
Call `get_session_info()`. Record: current tempo, track count, transport state.
Expected: JSON with session metadata. No errors.

- [ ] **Step 2: Set tempo to 120 BPM**
Call `set_tempo(bpm=120)`.
Expected: Confirmation. Verify with `get_session_info()`.

- [ ] **Step 3: Set time signature 4/4**
Call `set_time_signature(numerator=4, denominator=4)`.
Expected: Confirmation.

- [ ] **Step 4: Run session diagnostics**
Call `get_session_diagnostics()`.
Expected: Report on armed tracks, solo/mute leftovers, unnamed tracks, empty clips. Fix any issues found.

- [ ] **Step 5: Toggle metronome off**
Call `toggle_metronome()`.
Expected: Metronome disabled.

- [ ] **Step 6: Verify browser access**
Call `get_browser_tree()`. Then call `get_browser_items(path="instruments")` to browse a specific category.
Expected: JSON tree of all browser categories. Items list for instruments.

- [ ] **Step 7: Verify M4L bridge**
Call `get_master_spectrum()`.
Expected: 8-band frequency data OR graceful error if M4L not loaded. If error → load LivePilot_Analyzer.amxd onto master track first.

- [ ] **Step 8: Verify FluCoMa**
Call `check_flucoma()`.
Expected: Status indicating available or not. If not available, note: FluCoMa tools (get_spectral_shape, get_mel_spectrum, get_chroma, get_onsets, get_novelty, get_momentary_loudness) will be skipped or will return graceful errors.

- [ ] **Step 9: Test transport cycle**
Call `start_playback()`. Wait 1 second. Call `stop_playback()`.
Expected: Both succeed. Transport works.

**Running tool tally: ~10/178**

---

### Task 2: Harmonic DNA — Let Theory Tools Decide the Key (Phase 1)

**Domain coverage target:** Harmony (all 4), Theory (partial)
**Tools exercised:** 6

- [ ] **Step 1: Explore Tonnetz from C minor**
Call `navigate_tonnetz(root="C", quality="minor", depth=3)`.
Expected: Map of reachable chords via P/L/R transforms. Record all results — these are our harmonic palette options.

- [ ] **Step 2: Explore Tonnetz from F# minor**
Call `navigate_tonnetz(root="F#", quality="minor", depth=2)`.
Expected: Alternative chord palette. Compare darkness/tension of both seed results.

- [ ] **Step 3: Choose key — classify candidate progressions**
From the Tonnetz results, pick the 2-3 darkest chord clusters. For each, build a 4-chord sequence and call `classify_progression(chords=[...])`.
Expected: Classification (hexatonic, octatonic, diatonic). **Pick the sequence that returns the most minor/dark classification.** This becomes our key.

- [ ] **Step 4: Build 32-bar harmonic cycle**
Starting from the chosen key chord, call `suggest_next_chord(current_chord=<chosen>, style="modal")` × 4 to get 4 chords (one per 8 bars).
Expected: 4 theoretically valid chord names. Record the full progression.

- [ ] **Step 5: Bank distant chords for Act IV**
Call `suggest_chromatic_mediants(chord=<chosen_key_chord>)`.
Expected: All chromatic mediant relations. Pick the most distant (0 common tones) for the "False Dawn" moment.

- [ ] **Step 6: Identify scale**
Call `identify_scale(notes=<notes_from_chosen_chords>)`.
Expected: Scale name and mode. Confirms our harmonic territory.

**Decision point:** Record the chosen key, 4-chord cycle, and banked distant chord. All subsequent composition uses these.

**Running tool tally: ~16/178**

---

### Task 3: Track Architecture (Phase 2)

**Domain coverage target:** Tracks (all 17), Scenes (partial)
**Tools exercised:** ~30+

- [ ] **Step 1: Create all MIDI tracks**
Call `create_midi_track()` for each:
1. "Kick" (color: 3 — red family)
2. "Hats" (color: 3)
3. "Clap" (color: 3)
4. "Perc" (color: 3)
5. "Sub Bass" (color: 14 — blue family)
6. "Acid Bass" (color: 14)
7. "Pad" (color: 25 — green family)
8. "Tape" (color: 25)
9. "Dark Atmo" (color: 25)
10. "Melody" (color: 46 — purple family)
Expected: 10 tracks created. Note their indices.

- [ ] **Step 2: Create audio tracks**
Call `create_audio_track(name="Resample", color=60)`.
Call `create_audio_track(name="Bounce", color=60)`.
Expected: 2 audio tracks. Note indices.

- [ ] **Step 3: Create return tracks**
Call `create_return_track()` × 4. Then name them:
- `set_track_name()` → "Space" (Return A)
- `set_track_name()` → "Echo" (Return B)
- `set_track_name()` → "Destroy" (Return C)
- `set_track_name()` → "Wash" (Return D)
Expected: 4 returns created and named.

- [ ] **Step 4: Color all tracks**
If not already colored in creation, call `set_track_color()` for each track with the colors specified in Step 1. Use consistent color families: reds for rhythm, blues for bass, greens for pads/atmo, purples for melody.
Expected: Visual grouping in Ableton.

- [ ] **Step 5: Track state operations**
- Call `set_track_arm(track_index=<Resample>, arm=true)` — arm Resample track
- Call `set_track_input_monitoring(track_index=<Resample>, state="In")` — monitor audio tracks
- Call `set_track_mute(track_index=<Resample>, mute=true)` — mute Resample initially
- Call `set_track_solo(track_index=<Kick>, solo=true)` — test solo
- Call `set_track_solo(track_index=<Kick>, solo=false)` — unsolo
- Call `stop_track_clips(track_index=<Kick>)` — ensure clean state
Expected: All operations succeed. Solo is toggled on/off.

- [ ] **Step 6: Group rhythm tracks**
Call `set_group_fold()` if rhythm tracks are in a group. (If no group exists, skip — groups require manual creation in Ableton.)
Expected: Success or skip if no group.

- [ ] **Step 7: Create scenes**
Call `create_scene()` × 8 (7 acts + 1 variation). Then:
- `set_scene_name()` × 7 → "Act I - Signal", "Act II - Pulse", "Act III - Machine", "Act IV - Dawn", "Act V - Break", "Act VI - Resurrection", "Act VII - Dissolve"
- `set_scene_color()` × 7 → distinct colors per act
Expected: 8 scenes created, named, colored.

- [ ] **Step 8: Duplicate a scene for variation**
Call `duplicate_scene(scene_index=1)` — clone Act II.
Expected: New scene created as copy. Note: we'll delete this later in Phase 8 testing.

- [ ] **Step 9: Verify architecture**
Call `get_track_info(track_index=0)` on a couple of tracks to verify state.
Call `get_scenes_info()` to verify all scenes.
Expected: Correct names, colors, arm/mute states.

**Running tool tally: ~46/178**

---

## Chunk 2: Sound Design (Phase 3)

### Task 4: Load Instruments (Phase 3, Part 1)

**Domain coverage target:** Browser (remaining), Devices (partial)
**Tools exercised:** ~20

- [ ] **Step 1: Search and load Kick instruments**
Call `search_browser(query="Operator")` → find Operator synth.
Call `find_and_load_device(track_index=<Kick>, device_name="Operator")`.
Expected: Operator loaded on Kick track.

- [ ] **Step 2: Configure Kick Operator as sub sine**
Call `get_device_parameters(track_index=<Kick>, device_index=0)` — read all Operator params.
Call `batch_set_parameters(track_index=<Kick>, device_index=0, parameters={...})`:
- Oscillator A: Sine wave, level 100%
- Oscillator B/C/D: Off
- Filter: Low-pass, cutoff ~200Hz
- Amp envelope: Attack 0ms, Decay ~300ms, Sustain 0, Release 50ms
Expected: Operator configured as deep sub kick.

- [ ] **Step 3: Load Drum Rack on Hats track**
Call `find_and_load_device(track_index=<Hats>, device_name="Drum Rack")`.
Call `get_device_info(track_index=<Hats>, device_index=0)` — verify loaded.
Call `walk_device_tree(track_index=<Hats>, device_index=0)` — inspect nested structure.
Call `get_rack_chains(track_index=<Hats>, device_index=0)` — enumerate chains.
Expected: Empty Drum Rack ready for samples/instruments.

- [ ] **Step 4: Load Simpler on Clap track**
Call `find_and_load_device(track_index=<Clap>, device_name="Simpler")`.
Call `set_simpler_playback_mode(track_index=<Clap>, device_index=0, mode="Classic")`.
Expected: Simpler in Classic mode.

- [ ] **Step 5: Load bass instruments**
Call `find_and_load_device(track_index=<Sub_Bass>, device_name="Analog")`.
Call `find_and_load_device(track_index=<Acid_Bass>, device_name="Wavetable")`.
Expected: Analog on Sub Bass, Wavetable on Acid Bass.

- [ ] **Step 6: Load pad and atmosphere instruments**
Call `find_and_load_device(track_index=<Pad>, device_name="Drift")` (or Wavetable if Drift not found).
Call `find_and_load_device(track_index=<Tape>, device_name="Simpler")`.
Call `find_and_load_device(track_index=<Dark_Atmo>, device_name="Collision")` (or Tension).
Expected: Instruments loaded on all pad/atmo tracks.

- [ ] **Step 7: Load melody instruments**
Call `find_and_load_device(track_index=<Melody>, device_name="Analog")` (clean bell-like tone).
Expected: Melody instrument loaded.

- [ ] **Step 8: Load a device by URI (alternative path)**
Call `search_browser(query="Electric")` to find a device.
Call `load_browser_item(uri=<found_uri>, track_index=<Melody>)` — load Electric as second option.
Then `delete_device(track_index=<Melody>, device_index=1)` — remove it (we already have Analog).
Expected: Tests `load_browser_item()` and `delete_device()` paths.

- [ ] **Step 8b: Load device by URI (Devices domain path)**
Call `load_device_by_uri(uri=<found_uri_from_search>, track_index=<Dark_Atmo>)` — this is the Devices-domain URI loader, distinct from Browser's `load_browser_item()`.
Then `delete_device()` to remove it if not needed.
Expected: Tests `load_device_by_uri` (Devices domain) as separate tool from `load_browser_item` (Browser domain).

- [ ] **Step 9: Inspect plugin parameters (if AU/VST loaded)**
If any AU/VST plugin was loaded: call `get_plugin_parameters(track_index=<X>, device_index=<Y>)`.
Call `get_plugin_presets(track_index=<X>, device_index=<Y>)`.
Call `map_plugin_parameter(track_index=<X>, device_index=<Y>, parameter_index=0)`.
If no plugins: call these on any device to verify graceful handling.
Expected: Plugin inspection tools exercised.

- [ ] **Step 10: Browse device presets**
Call `get_device_presets(track_index=<Pad>, device_index=0)`.
Expected: List of available presets for the instrument.

**Running tool tally: ~66/178**

---

### Task 5: Load Effects & Configure Sound Design (Phase 3, Part 2)

**Domain coverage target:** Devices (remaining), Mixing (partial)
**Tools exercised:** ~15

- [ ] **Step 1: Load effect chains on rhythm tracks**
For each rhythm track, load effects via `find_and_load_device()`:
- Kick: Saturator → EQ Eight → Compressor
- Hats: Redux → Corpus → Auto Pan
- Clap: Overdrive → Reverb → Gate
Expected: ~9 effects loaded across 3 tracks.

- [ ] **Step 2: Load effect chains on bass tracks**
- Sub Bass: Saturator → EQ Eight
- Acid Bass: Pedal → Auto Filter → Chorus-Ensemble
Expected: ~5 effects loaded.

- [ ] **Step 3: Load effect chains on pad/atmo tracks**
- Pad: Chorus-Ensemble → Reverb → Utility
- Tape: Redux → EQ Eight → Utility
- Dark Atmo: Frequency Shifter → Echo → Reverb
Expected: ~9 effects loaded.

- [ ] **Step 4: Load effects on Melody track + Pitch device for Act V**
- Melody: Delay → Reverb → Phaser
- Also load a Pitch MIDI effect (for tape_stop recipe in Act V): `find_and_load_device(track_index=<Melody>, device_name="Pitch")`.
Expected: 4 devices on Melody.

- [ ] **Step 5: Load return track effects**
- Return A "Space": `find_and_load_device()` → Hybrid Reverb (or Reverb)
- Return B "Echo": `find_and_load_device()` → Echo
- Return C "Destroy": Beat Repeat → Corpus → Saturator → Utility
- Return D "Wash": Resonators → Reverb
Expected: ~8 effects on returns.

- [ ] **Step 6: Configure key effect parameters**
Use `set_device_parameter()` for surgical adjustments:
- Redux on Hats: bit_depth=12, sample_rate_reduction=low
- Saturator on Kick: drive=medium, type=Warm Tube
- Compressor on Kick: attack=fast, ratio=4:1
Use `batch_set_parameters()` for multi-param sets on bass instruments.
Expected: Sound design configured.

- [ ] **Step 7: Toggle device bypass test**
Call `toggle_device(track_index=<Hats>, device_index=<Redux>)` — bypass.
Call `toggle_device(track_index=<Hats>, device_index=<Redux>)` — re-enable.
Expected: Device toggles on/off.

- [ ] **Step 8: Set up sidechain routing**
Call `set_track_routing(track_index=<Sub_Bass>, routing_type="input", ...)` to configure sidechain from Kick.
Repeat for Pad and Tape compressor sidechains.
Call `get_track_routing(track_index=<Sub_Bass>)` to verify.
Expected: Sidechain routing established.

- [ ] **Step 9: Set initial send levels**
Call `set_track_send(track_index=<Pad>, send_index=0, value=0.3)` — Pad → Space reverb.
Call `set_track_send(track_index=<Melody>, send_index=1, value=0.25)` — Melody → Echo delay.
Set sends for other tracks as appropriate.
Expected: Return tracks receiving signal.

- [ ] **Step 10: Deep device inspection**
Call `get_hidden_parameters(track_index=<Kick>, device_index=0)` — non-automatable params.
Call `get_display_values(track_index=<Kick>, device_index=0)` — human-readable values.
Call `set_chain_volume(track_index=<Hats>, device_index=0, chain_index=0, volume=0.8)` — Drum Rack chain level.
Expected: Deep device access working.

**Running tool tally: ~81/178**

---

## Chunk 3: Composition Acts I–IV (Phase 4)

### Task 6: Compose Act I — "The Signal" & Act II — "Pulse Emerges"

**Domain coverage target:** Notes (partial), Clips (partial), Generative (partial)
**Tools exercised:** ~20

- [ ] **Step 1: Create Pad clip for Act I**
Call `create_clip(track_index=<Pad>, clip_index=0, length=32.0)` — 32 bars.
Call `set_clip_name(track_index=<Pad>, clip_index=0, name="Signal Pad")`.
Call `set_clip_color(track_index=<Pad>, clip_index=0, color=25)`.
Call `set_clip_loop(track_index=<Pad>, clip_index=0, loop=true, start=0.0, end=32.0)`.
Expected: Empty 32-bar clip, looped.

- [ ] **Step 2: Write pad chord from Phase 1 harmony**
Using the key chord from Task 2 (e.g., Cm = C3, Eb3, G3), call:
`add_notes(track_index=<Pad>, clip_index=0, notes=[{pitch: 48, start_time: 0.0, duration: 32.0, velocity: 80}, {pitch: 51, start_time: 0.0, duration: 32.0, velocity: 75}, {pitch: 55, start_time: 0.0, duration: 32.0, velocity: 75}])`.
Expected: Sustained chord across 32 bars.

- [ ] **Step 3: Create Tape texture clip for Act I**
Call `create_clip(track_index=<Tape>, clip_index=0, length=32.0)`.
Call `set_clip_name()`, `add_notes()` — single sustained note to trigger tape noise sample.
Expected: Texture layer established.

- [ ] **Step 4: Generate Kick pattern for Act II**
Call `generate_euclidean_rhythm(steps=16, pulses=4, rotation=0, pitch=36, velocity=110, clip_length=4.0)`.
Expected: 4-on-floor kick pattern as note array.
Call `create_clip(track_index=<Kick>, clip_index=1, length=4.0)`.
Call `add_notes(track_index=<Kick>, clip_index=1, notes=<generated>)`.
Call `set_clip_loop(track_index=<Kick>, clip_index=1, loop=true)`.
Expected: Kick pattern in Act II scene slot.

- [ ] **Step 5: Generate Hat polyrhythm for Act II**
Call `layer_euclidean_rhythms(layers=[{steps: 16, pulses: 7, rotation: 2, pitch: 42, velocity: 90}, {steps: 16, pulses: 5, rotation: 1, pitch: 44, velocity: 70}, {steps: 16, pulses: 3, rotation: 0, pitch: 46, velocity: 60}], clip_length=4.0)`.
Expected: Layered polyrhythmic hat pattern.
Call `create_clip()` + `add_notes()` on Hats track, Act II.

- [ ] **Step 6: Generate phase-shifted hat variation**
Call `generate_phase_shift(pattern=<hat_main_pattern>, voices=2, drift_amount=1, clip_length=16.0)`.
Expected: Two hat voices with progressive drift.
Create second clip on Hats track for variation.

- [ ] **Step 7: Generate Clap pattern**
Call `generate_euclidean_rhythm(steps=16, pulses=2, rotation=4, pitch=39, velocity=100, clip_length=4.0)`.
Expected: Off-beat clap. Add to Clap track, Act II.

- [ ] **Step 8: Write Sub Bass notes from harmony**
Using root notes from the 4-chord cycle (Task 2 Step 4):
- Chord 1 root → bars 1-8
- Chord 2 root → bars 9-16
... etc.
Call `create_clip(track_index=<Sub_Bass>, clip_index=1, length=32.0)`.
Call `add_notes()` with long, sustained root notes (one per 8-bar phrase).
Expected: Sub bass follows harmonic cycle.

- [ ] **Step 9: Write Pad chord evolution for Act II**
Using `navigate_tonnetz()` results from Phase 1, apply P/L/R transforms per 8-bar phrase.
Create Pad clip for Act II with 4 different chord voicings (one per 8 bars).
Call `add_notes()` with the evolving chords.
Expected: Pad harmonically mutates every 8 bars.

- [ ] **Step 10: Humanize — modify velocities and add probability**
Call `modify_notes(track_index=<Hats>, clip_index=<Act_II>, modifications=[...])` — vary hat velocities for swing feel.
When adding notes in previous steps, use `probability` field < 1.0 on ghost hats (e.g., 0.6-0.8) for Villalobos micro-variation.
Call `get_notes(track_index=<Hats>, clip_index=<Act_II>)` — read back and verify.
Expected: Humanized dynamics with probabilistic ghost notes.

**Running tool tally: ~101/178**

---

### Task 7: Compose Acts III–IV + Theory Verification

**Domain coverage target:** Theory (remaining), Generative (remaining partial), Notes (remaining)
**Tools exercised:** ~15

- [ ] **Step 1: Write Acid Bass sequence for Act III**
Call `suggest_next_chord(current_chord=<last_chord_from_cycle>, style="modal")` to extend harmony.
Arpeggiate the chord tones into a 16th-note bass sequence.
Call `create_clip(track_index=<Acid_Bass>, clip_index=2, length=8.0)`.
Call `add_notes()` with the arpeggiated sequence.
Expected: Theory-guided acid bass line.

- [ ] **Step 2: Write Dark Atmosphere for Acts III–IV**
Long sustained notes (4-8 bar durations) on Collision/Tension.
Call `create_clip()` + `add_notes()` on Dark Atmo track.
Expected: Brooding metallic undertow.

- [ ] **Step 3: Generate Tintinnabuli melody for Act IV**
Take the root notes of the 4-chord cycle as the melody voice.
Call `generate_tintinnabuli(melody_notes=<roots>, triad=<key_triad>, mode="superior", position=1)`.
Expected: Arvo Pärt-style melody+T-voice combination.
Create Melody clip for Act IV, add the generated notes.

- [ ] **Step 4: Generate harmony and countermelody**
Call `harmonize_melody(track_index=<Melody>, clip_index=<Act_IV>)` — four-part harmony.
Call `generate_countermelody(track_index=<Melody>, clip_index=<Act_IV>)` — counter voice.
Expected: Rich melodic material for Act IV. Add results to appropriate clips.

- [ ] **Step 5: Analyze harmony on completed clips**
Call `analyze_harmony(track_index=<Pad>, clip_index=<Act_II>)`.
Expected: Chord detection, Roman numeral analysis, progression string.

- [ ] **Step 6: Detect theory issues**
Call `detect_theory_issues(track_index=<Melody>, clip_index=<Act_IV>)`.
Expected: Check for parallel 5ths/octaves, voice crossing. Fix any issues.

- [ ] **Step 7: Quantize selected clips**
Call `quantize_clip(track_index=<Acid_Bass>, clip_index=<Act_III>)`.
Expected: Notes snapped to grid (auto-detected grid size).

- [ ] **Step 8: Transpose notes for variation**
Call `transpose_notes(track_index=<Pad>, clip_index=<Act_III>, semitones=<to_next_chord_root>)` on a duplicate.
Expected: Pad variation for Act III.

- [ ] **Step 9: Playback analysis pass — Acts I–II**
Call `fire_scene(scene_index=1)` (Act II — has most elements).
Call `continue_playback()`.
Call `get_master_spectrum()` — check 8-band balance.
Call `get_master_rms()` — level check.
Call `get_detected_key()` — confirm harmonic center matches theory choice.
Call `stop_playback()`.
**Note:** `fire_scene()` launches clips but may not start transport. Use `start_playback()` explicitly if transport is stopped, or `continue_playback()` only if transport was paused mid-position.
Expected: Spectral data confirms balanced low end, key matches chosen key.
**Adjust:** If sub is too loud, `set_device_parameter()` on EQ Eight. If key mismatch, investigate.

**Running tool tally: ~116/178**

---

## Chunk 4: Composition Acts V–VII + Resampling (Phase 5)

### Task 8: Resampling Workflow & Act V–VII Composition

**Domain coverage target:** Analyzer (Simpler ops, capture), MIDI I/O (all 4), Generative (remaining)
**Tools exercised:** ~25

- [ ] **Step 1: Capture audio for resampling**
Call `fire_scene(scene_index=2)` (Act III — has rhythm + bass).
Call `start_playback()`.
Wait for playback to establish (~2 bars).
Call `capture_audio(duration=8)` — 8 seconds of master bus.
Call `capture_stop()` (or let timer finish).
Call `stop_playback()`.
Expected: WAV file saved to ~/Documents/LivePilot/captures/.

- [ ] **Step 2: Load captured audio into Simpler**
Call `load_sample_to_simpler(track_index=<Perc>, file_path=<captured_wav>)`.
Call `get_simpler_slices(track_index=<Perc>, device_index=0)` — examine slice points.
Call `set_simpler_playback_mode(track_index=<Perc>, device_index=0, mode="Slice")`.
Expected: Resampled material loaded, slices visible.

- [ ] **Step 3: Manipulate Simpler sample**
Call `reverse_simpler(track_index=<Perc>, device_index=0)` — BoC texture.
Call `crop_simpler(track_index=<Perc>, device_index=0)` — trim to best section.
Call `warp_simpler(track_index=<Perc>, device_index=0, beats=4)` — time-stretch to 4 beats.
Expected: Sample reversed, cropped, warped.

- [ ] **Step 4: Replace sample test**
Capture another short audio clip (2 seconds).
Call `replace_simpler_sample(track_index=<Perc>, device_index=0, file_path=<new_wav>)`.
Expected: Sample swapped in existing Simpler.

- [ ] **Step 5: Write Perc clip from resampled material**
Call `create_clip(track_index=<Perc>, clip_index=2, length=4.0)`.
Call `add_notes()` — trigger the Simpler at various pitches for chopped beats.
Expected: Resampled percussion pattern.

- [ ] **Step 6: Generate Additive Counter-Melody for Act VI**
Call `generate_additive_process(seed_notes=<melody_fragment>, repetitions=8, notes_per_step=1)`.
Expected: Philip Glass-style building melody.
Create clip on Melody track for Act VI.

- [ ] **Step 7: Transpose melody for Act VI — smart transpose**
Call `transpose_smart(track_index=<Melody>, clip_index=<Act_IV>, interval="P4", key=<chosen_key>)` — function-preserving transpose.
Expected: Melody transposed while maintaining harmonic function.

- [ ] **Step 8: Find voice-leading path for climax**
Call `find_voice_leading_path(start_chord=<Act_I_chord>, end_chord=<most_distant_mediant>, max_steps=6)`.
Expected: Shortest voice-leading path between opening and most distant chord.
Use this progression for Act VI pads.

- [ ] **Step 9: Classify the full progression**
Call `classify_progression(chords=<all_chords_used_across_acts>)`.
Expected: Hexatonic/octatonic/diatonic classification of entire track harmony.

- [ ] **Step 10: Write Act V breakdown clips**
Sparse clips with `remove_notes()` — thin out existing patterns for the break.
Call `remove_notes(track_index=<Kick>, clip_index=<Act_V>, ...)` — remove some kick hits.
Call `remove_notes_by_id(track_index=<Hats>, clip_index=<Act_V>, note_ids=[...])` — surgical removal of specific hat notes.
Expected: Sparser patterns for the breakdown section.

- [ ] **Step 11: Duplicate notes and clips for layering**
Call `duplicate_notes(track_index=<Melody>, clip_index=<Act_VI>, ...)` — double melody notes for thickness.
Call `duplicate_clip(track_index=<Kick>, clip_index=<Act_II>, target_clip_index=<Act_VI>)` — copy kick to Act VI.
Expected: Layered/duplicated material for climax.

- [ ] **Step 12: MIDI I/O round-trip**
Call `export_clip_midi(track_index=<Melody>, clip_index=<Act_IV>, file_path="~/Documents/LivePilot/exports/melody_act_iv.mid")`.
Call `analyze_midi_file(file_path="~/Documents/LivePilot/exports/melody_act_iv.mid")`.
Call `extract_piano_roll(file_path="~/Documents/LivePilot/exports/melody_act_iv.mid")`.
Call `import_midi_to_clip(track_index=<Melody>, clip_index=<Act_VII>, file_path="~/Documents/LivePilot/exports/melody_act_iv.mid")`.
Expected: Full MIDI I/O round-trip. Exported file matches original. Piano roll visualization returned.

**Running tool tally: ~141/178**

---

## Chunk 5: Automation, Mixing, Arrangement & Finalization (Phases 6–10)

### Task 9: Automation — All 16 Curves, All 15 Recipes (Phase 6)

**Domain coverage target:** Automation (all 8)
**Tools exercised:** 8

- [ ] **Step 1: Get automation suggestions**
Call `analyze_for_automation(track_index=<Pad>)`.
Expected: Suggestions for which parameters would benefit from movement. Follow the top suggestions.

- [ ] **Step 2: List all available recipes**
Call `get_automation_recipes()`.
Expected: All 15 recipes with descriptions. Verify count.

- [ ] **Step 3: Apply all 15 recipes to specific musical contexts**
Execute each recipe call per the spec's Loop 4 mapping:
1. `apply_automation_recipe(recipe="fade_in", track_index=<master>, ...)` — Act I
2. `apply_automation_recipe(recipe="filter_sweep_up", track_index=<Sub_Bass>, ...)` — Act III
3. `apply_automation_recipe(recipe="sidechain_pump", track_index=<Sub_Bass>, ...)` — Act III+
4. `apply_automation_recipe(recipe="build_rise", track_index=<Pad>, ...)` — Act II→III
5. `apply_automation_recipe(recipe="tremolo", track_index=<Pad>, ...)` — Act II
6. `apply_automation_recipe(recipe="auto_pan", track_index=<Hats>, ...)` — Act II
7. `apply_automation_recipe(recipe="breathing", track_index=<Acid_Bass>, ...)` — Act IV
8. `apply_automation_recipe(recipe="dub_throw", track_index=<Melody>, send_index=3, ...)` — Act IV
9. `apply_automation_recipe(recipe="washout", track_index=<return_A>, ...)` — Act IV→V
10. `apply_automation_recipe(recipe="vinyl_crackle", track_index=<Tape>, ...)` — Act I–III
11. `apply_automation_recipe(recipe="filter_sweep_down", track_index=<Pad>, ...)` — Act V
12. `apply_automation_recipe(recipe="tape_stop", track_index=<Melody>, device_index=<Pitch>, ...)` — Act V
13. `apply_automation_recipe(recipe="stutter", track_index=<Perc>, ...)` — Act V
14. `apply_automation_recipe(recipe="fade_out", track_index=<master>, ...)` — Act VII
15. `apply_automation_recipe(recipe="stereo_narrow", track_index=<master>, ...)` — Act VII master Utility width collapse
Expected: All 15 recipes applied successfully.

- [ ] **Step 4: Apply all 16 curve types via apply_automation_shape**
Execute each curve per the spec's curve-to-parameter mapping:
1. `apply_automation_shape(shape="linear", ...)` — volume fade on Tape
2. `apply_automation_shape(shape="exponential", ...)` — filter sweep up on Sub Bass
3. `apply_automation_shape(shape="logarithmic", ...)` — filter sweep down on Pad
4. `apply_automation_shape(shape="s_curve", ...)` — crossfade
5. `apply_automation_shape(shape="sine", ...)` — tremolo on Pad
6. `apply_automation_shape(shape="sawtooth", ...)` — sidechain shape
7. `apply_automation_shape(shape="spike", ...)` — dub throw send
8. `apply_automation_shape(shape="square", ...)` — stutter gate
9. `apply_automation_shape(shape="steps", ...)` — wavetable position
10. `apply_automation_shape(shape="perlin", ...)` — filter drift
11. `apply_automation_shape(shape="brownian", ...)` — resonance wander
12. `apply_automation_shape(shape="spring", ...)` — post-break open
13. `apply_automation_shape(shape="bezier", ...)` — custom arc
14. `apply_automation_shape(shape="easing", ...)` — reverb decay
15. `apply_automation_shape(shape="euclidean", ...)` — Beat Repeat gate
16. `apply_automation_shape(shape="stochastic", ...)` — bit reduction
Expected: All 16 curve types generated and applied.

- [ ] **Step 5: Preview and CRUD cycle**
Call `generate_automation_curve(shape="perlin", ...)` — preview without writing.
Call `set_clip_automation(track_index=<Pad>, clip_index=<Act_II>, ...)` — write custom envelope.
Call `get_clip_automation(track_index=<Pad>, clip_index=<Act_II>)` — read back.
Call `clear_clip_automation(track_index=<Pad>, clip_index=<Act_II>, ...)` — clear it.
Call `set_clip_automation()` — rewrite.
Expected: Full CRUD cycle on clip automation.

- [ ] **Step 6: Arrangement automation**
Call `set_arrangement_automation(track_index=<Pad>, parameter_index=<filter_cutoff>, points=[...])` — long-form curve across acts.
Expected: Arrangement-level automation written.

**Running tool tally: ~149/178**

---

### Task 10: Mixing & Spectral Balancing (Phase 7)

**Domain coverage target:** Mixing (all 11), Analyzer (FluCoMa tools)
**Tools exercised:** ~17

- [ ] **Step 1: Start playback for analysis**
Call `fire_scene(scene_index=5)` (Act VI — densest).
Call `start_playback()`.

- [ ] **Step 2: Real-time spectrum analysis**
Call `get_master_spectrum()` — 8-band balance.
Call `get_master_rms()` — overall level.
Call `get_detected_key()` — verify key.
Expected: Spectral data for mix decisions.

- [ ] **Step 3: FluCoMa descriptors (if available)**
Call `get_spectral_shape()` — centroid, spread, flatness, kurtosis, rolloff, crest.
Call `get_mel_spectrum()` — 40-band detail.
Call `get_chroma()` — 12 pitch class energies for chord verification.
Call `get_momentary_loudness()` — EBU R128 LUFS + true peak.
Expected: Detailed spectral data. If FluCoMa unavailable, graceful errors.

- [ ] **Step 4: Mix adjustments based on analysis**
Call `set_track_volume()` on each track — balance levels based on spectrum.
Call `set_track_pan()` — hats slightly left/right, bass center, pad wide.
Call `set_track_send()` — adjust return levels based on overall balance.
Call `set_master_volume()` — set final level to avoid clipping.
Expected: Balanced mix.

- [ ] **Step 5: Monitoring and verification**
Call `get_track_meters()` on each track — verify per-track peaks.
Call `get_master_meters()` — master peaks under 0dB.
Call `get_mix_snapshot()` — full state capture.
Call `get_return_tracks()` — verify return setup.
Call `get_master_track()` — master device chain info.
Call `get_track_routing()` on a track — verify routing.
Expected: Complete mix state documented.

- [ ] **Step 6: Stop playback**
Call `stop_playback()`.

**Running tool tally: ~166/178**

---

### Task 11: Arrangement & Scenes (Phase 8)

**Domain coverage target:** Arrangement (all 19), Scenes (remaining), Clips (remaining)
**Tools exercised:** ~12 (remaining arrangement/scene tools)

- [ ] **Step 1: Scene operations**
Call `get_scene_matrix()` — full clip grid.
Call `fire_scene(scene_index=0)` through all 7 — test each act.
Call `fire_scene_clips(scene_index=2, track_indices=[0,1,2])` — partial launch (rhythm only).
Call `get_playing_clips()` — verify.
Call `stop_all_clips()` — panic test.
Call `delete_scene(scene_index=<duplicate>)` — remove the test duplicate from Task 3.
Call `set_scene_tempo(scene_index=4, tempo=118)` — Act V slight tempo drop.
Expected: All scene operations work.

- [ ] **Step 2: Clip control operations**
Call `fire_clip(track_index=<Kick>, clip_index=1)` — launch individual.
Call `stop_clip(track_index=<Kick>, clip_index=1)` — stop individual.
Call `set_clip_launch(track_index=<Kick>, clip_index=1, launch_mode="Gate")` — test gate mode.
Call `set_clip_launch(track_index=<Kick>, clip_index=1, launch_mode="Trigger")` — restore.
Call `set_clip_warp_mode(track_index=<Resample>, clip_index=<audio_clip>, mode="Complex")` — on audio clip.
Call `get_clip_info(track_index=<Kick>, clip_index=1)` — metadata.
Create a throwaway test clip: `create_clip(track_index=<Kick>, clip_index=7, length=1.0)`.
Call `delete_clip(track_index=<Kick>, clip_index=7)` — exercises delete_clip.
Expected: All clip control modes exercised, including delete.

- [ ] **Step 3: Navigation**
Call `toggle_cue_point()` at bar 0, 32, 80, 128, 176, 208, 256 — mark act boundaries.
Call `get_cue_points()` — verify.
Call `jump_to_cue(cue_index=3)` — jump to Act IV.
Call `jump_to_time(beat_time=128.0)` — jump to bar 128.
Call `set_session_loop(loop=true, start=128.0, end=176.0)` — loop Act IV.
Call `set_session_loop(loop=false)` — disable loop.
Call `back_to_arranger()` — switch to arrangement view.
Expected: All navigation works.

- [ ] **Step 4: Arrangement composition**
Call `create_arrangement_clip(track_index=<Pad>, start_time=0.0, length=32.0)` — Act I pad.
Call `set_arrangement_clip_name(...)` — label it.
Call `add_arrangement_notes(track_index=<Pad>, ...)` — write notes.
Call `get_arrangement_notes(track_index=<Pad>, ...)` — read back.
Call `modify_arrangement_notes(...)` — adjust velocities.
Call `duplicate_arrangement_notes(...)` — copy pattern.
Call `transpose_arrangement_notes(...)` — pitch shift.
Call `remove_arrangement_notes(...)` — thin out.
Call `remove_arrangement_notes_by_id(...)` — surgical removal.
Call `get_arrangement_clips(track_index=<Pad>)` — verify timeline.
Expected: Full arrangement note CRUD.

- [ ] **Step 5: Recording**
Call `start_recording()`.
Call `fire_scene(scene_index=0)` — trigger Act I.
Wait ~4 bars.
Call `stop_recording()`.
Call `capture_midi()` — capture recently-played MIDI.
Expected: Performance recorded to arrangement.

**Running tool tally: ~178/178** (target reached!)

---

### Task 12: Final Analysis, Memory & Housekeeping (Phases 9–10)

**Domain coverage target:** Perception (all 4), Memory (all 8), remaining Analyzer tools
**Tools exercised:** Verification of full coverage

- [ ] **Step 1: Capture audio for offline analysis**
Call `fire_scene(scene_index=5)` + `start_playback()`.
Call `capture_audio(duration=30)` — grab 30 seconds of Act VI.
Call `capture_stop()` — cleanly terminate capture before stopping transport.
Call `stop_playback()`.

- [ ] **Step 2: Offline perception analysis**
Call `analyze_loudness(file_path=<captured_wav>)` — LUFS, peak, LRA, streaming compliance.
Call `analyze_spectrum_offline(file_path=<captured_wav>)` — spectral balance.
Call `compare_to_reference(file_path=<captured_wav>)` — comparison engine (even without reference, exercises the tool).
Call `read_audio_metadata(file_path=<captured_wav>)` — verify WAV integrity.
Expected: Loudness data, spectral profile, metadata. Note streaming compliance results.

- [ ] **Step 3: FluCoMa onset/novelty (with playback)**
Call `start_playback()`.
Call `get_onsets()` — transient detection.
Call `get_novelty()` — section boundary detection.
Call `stop_playback()`.

- [ ] **Step 4: Warp marker operations**
On the captured audio clip:
Call `get_warp_markers(...)` — read timing markers.
Call `add_warp_marker(...)` — add a new marker.
Call `move_warp_marker(...)` — shift it.
Call `remove_warp_marker(...)` — clean up.
Expected: Full warp marker CRUD.

- [ ] **Step 5: Clip preview**
Call `scrub_clip(track_index=<Perc>, clip_index=<resampled>, beat=2.0)` — preview at beat 2.
Call `stop_scrub()`.
Expected: Audible preview, then stop.

- [ ] **Step 6: Analyzer state inspection**
Call `get_automation_state(track_index=<Pad>, device_index=0)` — check overrides.
Call `get_clip_file_path(track_index=<Resample>, clip_index=0)` — audio file path.
Expected: Automation state and file path returned.

- [ ] **Step 7: Save techniques to memory**
Call `memory_learn()` for each notable technique:
1. Beat pattern: Euclidean kick + layered hats + phase drift
2. Device chain: Pad → Chorus → Reverb → Utility
3. Device chain: Redux → EQ → Utility (tape texture)
4. Mix template: 4 returns + sidechain architecture
5. Beat pattern: Resampled chopped percussion
Expected: 5 techniques saved.

- [ ] **Step 8: Exercise memory retrieval**
Call `memory_recall(query="minimal techno kick")` — search.
Call `memory_get(id=<saved_id>)` — full payload.
Call `memory_replay(id=<saved_id>)` — replay instructions.
Call `memory_list()` — browse all.
Call `memory_favorite(id=<best_technique>, rating=5)` — rate.
Call `memory_update(id=<any>, tags=["organism", "stress-test"])` — modify tags.
Call `memory_delete(id=<duplicate>)` — delete one test entry.
Expected: Full memory CRUD + search exercised.

- [ ] **Step 9: Session housekeeping**
Call `duplicate_track(track_index=<Perc>)` — clone track.
Call `delete_track(track_index=<clone>)` — remove clone.
Call `freeze_track(track_index=<Pad>)` — freeze dense track.
Call `get_freeze_status(track_index=<Pad>)` — check progress.
Call `flatten_track(track_index=<Pad>)` — commit to audio (WARNING: destructive — confirm pad is backed up via duplicate first).
Expected: Freeze/flatten cycle complete.

- [ ] **Step 10: Final verification**
Call `undo()` — undo flatten.
Call `redo()` — redo flatten.
Call `get_recent_actions()` — review command log.
Call `get_session_diagnostics()` — final health check.
Call `get_session_info()` — final state snapshot.
Call `stop_playback()` — clean end.
Expected: Session healthy, all 178 tools exercised.

- [ ] **Step 11: Coverage audit**
Review the running tool tally. Verify every tool from the canonical 178 list (spec Section 7) was called at least once. Document any that were skipped and why.
Expected: 178/178 or documented gaps with reasons.

---

## Tool Coverage Verification

At the end of execution, cross-reference against this checklist (all 178 tools from `test_tools_contract.py`):

### Transport (12): get_session_info, set_tempo, set_time_signature, start_playback, stop_playback, continue_playback, toggle_metronome, set_session_loop, undo, redo, get_recent_actions, get_session_diagnostics

### Tracks (17): get_track_info, create_midi_track, create_audio_track, create_return_track, delete_track, duplicate_track, set_track_name, set_track_color, set_track_mute, set_track_solo, set_track_arm, stop_track_clips, set_group_fold, set_track_input_monitoring, freeze_track, flatten_track, get_freeze_status

### Clips (11): get_clip_info, create_clip, delete_clip, duplicate_clip, fire_clip, stop_clip, set_clip_name, set_clip_color, set_clip_loop, set_clip_launch, set_clip_warp_mode

### Notes (8): add_notes, get_notes, remove_notes, remove_notes_by_id, modify_notes, duplicate_notes, transpose_notes, quantize_clip

### Devices (15): get_device_info, get_device_parameters, set_device_parameter, batch_set_parameters, toggle_device, delete_device, load_device_by_uri, find_and_load_device, set_simpler_playback_mode, get_rack_chains, set_chain_volume, get_device_presets, get_plugin_parameters, map_plugin_parameter, get_plugin_presets

### Scenes (12): get_scenes_info, create_scene, delete_scene, duplicate_scene, fire_scene, set_scene_name, set_scene_color, set_scene_tempo, get_scene_matrix, fire_scene_clips, stop_all_clips, get_playing_clips

### Mixing (11): set_track_volume, set_track_pan, set_track_send, get_return_tracks, get_master_track, set_master_volume, get_track_routing, set_track_routing, get_track_meters, get_master_meters, get_mix_snapshot

### Arrangement (19): get_arrangement_clips, create_arrangement_clip, add_arrangement_notes, get_arrangement_notes, remove_arrangement_notes, remove_arrangement_notes_by_id, modify_arrangement_notes, duplicate_arrangement_notes, transpose_arrangement_notes, set_arrangement_clip_name, set_arrangement_automation, back_to_arranger, jump_to_time, capture_midi, start_recording, stop_recording, get_cue_points, jump_to_cue, toggle_cue_point

### Browser (4): get_browser_tree, get_browser_items, search_browser, load_browser_item

### Analyzer (29): get_master_spectrum, get_master_rms, get_detected_key, get_hidden_parameters, get_automation_state, walk_device_tree, get_clip_file_path, replace_simpler_sample, get_simpler_slices, crop_simpler, reverse_simpler, warp_simpler, get_warp_markers, add_warp_marker, move_warp_marker, remove_warp_marker, scrub_clip, stop_scrub, get_display_values, capture_audio, capture_stop, get_spectral_shape, get_mel_spectrum, get_chroma, get_onsets, get_novelty, get_momentary_loudness, check_flucoma, load_sample_to_simpler

### Automation (8): get_clip_automation, set_clip_automation, clear_clip_automation, apply_automation_shape, apply_automation_recipe, get_automation_recipes, generate_automation_curve, analyze_for_automation

### Theory (7): analyze_harmony, suggest_next_chord, detect_theory_issues, identify_scale, harmonize_melody, generate_countermelody, transpose_smart

### Perception (4): analyze_loudness, analyze_spectrum_offline, compare_to_reference, read_audio_metadata

### Generative (5): generate_euclidean_rhythm, layer_euclidean_rhythms, generate_tintinnabuli, generate_phase_shift, generate_additive_process

### Harmony (4): navigate_tonnetz, find_voice_leading_path, classify_progression, suggest_chromatic_mediants

### Memory (8): memory_learn, memory_recall, memory_get, memory_replay, memory_list, memory_favorite, memory_update, memory_delete

### MIDI I/O (4): export_clip_midi, import_midi_to_clip, analyze_midi_file, extract_piano_roll

**TOTAL: 178/178**

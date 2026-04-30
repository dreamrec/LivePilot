---
name: livepilot-sound-design-engine
description: This skill should be used when the user asks to "design a sound", "analyze a patch", "fix a static sound", "add modulation", "check my timbre", "improve a synth patch", or wants critic-driven sound design feedback and iterative patch refinement.
---

# Sound Design Engine — Critic-Driven Patch Refinement

The sound design engine analyzes synth patches, identifies timbral weaknesses, and iteratively refines them through a measured critic loop. Every change is evaluated against the before state.

## Atlas-first reflex (v1.23.x+, MANDATORY before any creative move)

Before producing ANY creative response, query the user's atlas overlays. The corpus contains 337 entries across 3 namespaces, plus 3,917 parameter-level JSON sidecars — far richer than anything inferable from training data alone.

**Query order:**

1. **`extension_atlas_search(namespace="packs", query=<intent>)`** — pack identity, signature workflows, hidden gems, anti-patterns, notable presets with macro deep-data, demo projects
2. **`extension_atlas_search(namespace="packs", query=<intent>, entity_type="cross_pack_workflow")`** — multi-pack signature recipes (15 entries: dub-techno spectral drone bed, BoC decayed pad, Mica Levi orchestral dread, etc.)
3. **`extension_atlas_search(namespace="m4l-devices", query=<sonic descriptor>)`** — M4L instrument/effect/midi-effect device catalog (155 entries)
4. **`atlas_search(...)`** — bundled atlas (Core Library, fallback)

**Multi-grain traversal:**

When an aesthetic-level query lands a pack-level result, AUTO-DRILL: pack → its `notable_presets` → those preset macro states → load via `load_browser_item`. Don't stop at "I found a relevant pack" — drill to the actual preset/parameter level the user can immediately use.

```python
# Example — agent received "design a BoC pad — sublime, decayed, harmonic warmth"
hit = extension_atlas_search(namespace="packs", query="BoC sublime decayed pad harmonic warmth")
# → boc_decayed_pad cross-pack-workflow + inspired_by_nature pack

workflow = extension_atlas_get("packs", "boc_decayed_pad")
# → reveals signal flow + which notable_presets to start from

drone_lab = extension_atlas_get("packs", "drone_lab")
# → notable_presets reveals Razor Wire Drone with macros Filter Control=108, Movement=53...

# Now propose the patch with concrete preset names + macro starting values, not vague descriptions
```

**When the user mentions a producer or pack by name:**

- "BoC sublime pad" → atlas hit: `boc_decayed_pad` cross-pack-workflow + `inspired_by_nature` pack
- "Henke spectral chain" → atlas hit: `pitchloop89` + `granulator_iii` + 2 Henke cross-pack workflows
- "Mica Levi orchestral dread" → atlas hit: `mica_levi_orchestral_dread` workflow + the orchestral suite packs
- "Drone Lab" → atlas hit: `drone_lab` pack + 4 Drone Lab demo_project entries

The atlas knows the user's installed library at parameter depth. **Producer-anchor queries land specific moves, not vague descriptions.**

**Anti-pattern surfacing:**

Every pack entry has an `anti_patterns` body field listing "don't reach for this when X." Surface the relevant anti-pattern when proposing a move so the user knows the move's domain. (E.g. "Drone Lab is sustain-only — don't use for percussive content.")

**For deliberately rule-breaking creative requests** ("eclectic", "ignore the limits", "weird combo", "mix incompatible aesthetics"): switch to **Eclectic Mode** — the dedicated rule-breaker skill at `livepilot-eclectic` (private). Anti-patterns become prompt tension rather than guardrails. See that skill's reasoning loop.

## The Sound Design Critic Loop

### Step 1 — Build Patch Model

Call `get_patch_model(track_index)` to build a PatchModel for the target track. The PatchModel maps every device on the track into typed blocks (oscillator, filter, envelope, lfo, saturation, spatial, effect) and classifies each as `controllable` or `opaque`.

Read the response carefully:
- `blocks`: ordered list of processing blocks with types and parameter names
- `controllable_params`: parameters you can modify via `set_device_parameter`
- `opaque_blocks`: third-party plugins where parameters may not map cleanly
- `modulation_sources`: detected LFOs, envelopes, and macro mappings
- `signal_flow`: how blocks connect (serial, parallel, or rack chains)

See `references/patch-model.md` for the full PatchModel structure and native device block map.

### Step 2 — Analyze

Call `analyze_sound_design(track_index)` to run all sound design critics against the patch. The response contains an `issues` array with `critic`, `severity`, `block`, and `evidence`.

Five critics run during analysis. See `references/sound-design-critics.md` for thresholds:

- **static_timbre** — sound does not evolve over time, no movement
- **no_modulation_sources** — no LFOs, envelopes, or automation detected
- **modulation_flatness** — modulation exists but ranges are too narrow to hear
- **missing_filter** — raw oscillator output with no spectral shaping
- **spectral_imbalance** — too much energy in one frequency region, or gaps

### Step 3 — Plan

Pick the highest-severity issue. Call `plan_sound_design_move(track_index)` with the issue. The planner returns a single intervention:

- `move_type`: one of the move vocabulary entries
- `target_device`: device index on the track
- `target_parameter`: parameter name or index
- `target_value`: the new value
- `rationale`: why this move addresses the issue

Move vocabulary:
- **modulation_injection** — add or increase LFO/envelope depth on a parameter
- **filter_shaping** — adjust cutoff, resonance, or filter type
- **parameter_automation** — create clip automation for time-varying timbral change
- **oscillator_tuning** — adjust pitch, detune, waveform, or unison settings

### Step 4 — Capture Before

1. Call `get_device_parameters(track_index, device_index)` — save current parameter state
2. Call `get_master_spectrum` — save spectral snapshot (if analyzer available)

### Step 5 — Execute

Apply the planned move using the appropriate tool:

- `set_device_parameter` for direct parameter changes (filter cutoff, LFO rate, oscillator shape)
- `toggle_device` for enabling/disabling processing blocks
- `batch_set_parameters` when the move requires coordinated changes (e.g., LFO depth + rate together)
- `set_clip_automation` for parameter automation moves
- `find_and_load_device` when the fix requires adding a new device (e.g., adding an Auto Filter)

Execute one move at a time. Verify before continuing.

### Step 6 — Capture After

Repeat the same measurements:

1. Call `get_device_parameters(track_index, device_index)` — confirm the change took effect
2. Call `get_master_spectrum` — save post-change spectral snapshot

### Step 7 — Evaluate

Call `evaluate_move(goal_vector, before_snapshot, after_snapshot)` where `goal_vector` is the compiled goal from Step 1 and snapshots contain `{spectrum: {...}, rms: float, peak: float}`. Read:

- `keep_change` (bool): whether the change improved the sound
- `score` (0.0-1.0): quality improvement magnitude
- `timbral_delta`: what changed spectrally
- `explanation`: human-readable summary

### Step 8 — Keep or Undo

If `keep_change` is `false`, call `undo()`. Explain what was tried and why it did not improve the sound.

If `keep_change` is `true`, report the improvement. If score > 0.7, consider calling `memory_learn(name="...", type="device_chain", qualities={"summary": "..."}, payload={...})` to save the technique.

### Step 9 — Repeat

Return to Step 2. Re-analyze after each kept change. The critic list updates as issues are resolved. Continue until the user is satisfied or no high-severity issues remain.

## Working with Opaque Plugins

Third-party AU/VST plugins may report as `opaque` in the PatchModel:

1. Check `get_plugin_parameters(track_index, device_index)` — some plugins expose parameters through the host
2. If `parameter_count <= 1`, the plugin is dead or unresponsive. Call `delete_device` and suggest a native alternative
3. If parameters are available but unnamed (Parameter 1, Parameter 2...), try `map_plugin_parameter` to identify them by ear
4. Report opaque status to the user — sound design critics cannot fully analyze what they cannot inspect

## Quick Sound Design Checks

- **"What's wrong with this sound?"** — Call `get_sound_design_issues(track_index)` for a diagnostic without executing fixes
- **"Show me the patch"** — Call `get_patch_model(track_index)` then `walk_device_tree(track_index)` for full device chain visibility
- **"What can I automate?"** — Read the `controllable_params` list from the PatchModel response

## Native Device Strengths

When adding processing blocks, prefer native Ableton devices for controllability:

- **Wavetable** — complex oscillator section with built-in modulation matrix
- **Operator** — FM synthesis with per-operator envelopes and LFO
- **Analog** — subtractive with two filters and two LFOs
- **Auto Filter** — standalone filter with envelope follower and LFO
- **Corpus** — resonant body modeling for physical character
- **Erosion** — high-frequency noise and distortion artifacts
- **Saturator** — waveshaping with multiple curve types

Always `search_browser` before loading — never guess device names.

## M4L Instruments in the Library — When the Standard Synths Are the Wrong Aesthetic

Wavetable / Operator / Analog cover most subtractive and FM work, but several installed packs ship M4L instruments that produce sounds those three architecturally cannot. Reach for them when the standard list is the wrong starting point:

- **Granulator III** (Live Suite + Max for Live) — granular synthesis as a first-class instrument. Loop / Cloud / Classic modes, MPE per-note grain control, built-in audio capture. Use when the source needs to *be* a sample but evolve as a sustained voice.
- **Harmonic Drone Generator** (Drone Lab pack) — 8-voice M4L drone synth by Expert Math. Just intonation, Pythagorean, Pelog, equal temperament. Use when the patch is a sustained tonal bed and standard equal-tempered subtractive sounds wrong (microtonal beating is the point).
- **Bouncy Notes** (Inspired by Nature, Dillon Bastan) — gravity-based MIDI sequencer. Drop a ball, it bounces on a piano roll producing asymmetric never-repeating note cascades. Use as a generative source instead of writing notes by hand.
- **Tree Tone** (Inspired by Nature) — fractal-plant-growth resonator. Each branch is a tunable resonator (frequency / decay / amplitude). Use when you want resonance/body that evolves under itself, instead of static Corpus.
- **Vector FM / Vector Grain / Vector Map** (Inspired by Nature) — particle-physics modulation systems. Vector Map can route one particle to multiple parameters at once — useful when the patch needs *coupled* modulation that LFOs cannot produce.
- **PitchLoop89** (Live Suite) — Henke pitch-shift delay (Publison DHM 89 emulation). Use as the spatial/pitched-echo block on any sustained voice when standard delay + Auto Pan is too rigid.

These do not replace the modulation_injection / filter_shaping / parameter_automation move vocabulary. They change what "the source" can be — which is upstream of the critic loop.

## Deep Sound Design Reference

Consult `references/sound-design-deep.md` for advanced techniques when working on creative requests. Key principles:

### Making Sounds Breathe
Every static sound can become alive with modulation below conscious perception:
- **Filter breathing:** LFO at 0.1-0.5 Hz on filter cutoff, 5-15% depth
- **Oscillator drift:** ±1-3 cent detune with very slow LFO (0.05-0.2 Hz)
- **Amplitude micro-variation:** Perlin/brownian noise on volume, ±1-3 dB
- **Rule:** If the listener can hear the modulation, it's too much. The best modulation is felt, not heard.

### Space as Composition
Reverb and delay are not decorations — in dub/minimal they ARE the composition:
- **Dub chord:** Short stab → long delay (70-80% feedback) + filter on the delay return
- **Delay throws:** Momentary send spikes (0→70% for half a beat) — the echo IS the event
- **Sidechain reverb:** Dry drums trigger sidechain compression on reverb returns — the room pulses
- **Feedback modulation:** Delay feedback at 75-85% + modulate delay time ±5-10% for warped echoes

### Creative Sidechain (Beyond Pump)
Sidechain compression is a modulation source, not just a mix tool:
- **Sidechain filter:** Envelope follower from kick modulates pad filter cutoff — pad brightens between kicks
- **Ghost sidechain:** Muted kick as sidechain source for textures — phantom groove on non-rhythmic elements
- **Multiband sidechain:** Only duck sub frequencies from pad — shimmer stays, sub clears for kick

### Effects as Instruments
- **Self-oscillating filter:** Push resonance until it rings, play notes by changing cutoff
- **Feedback loops:** Route output back to input through effects + compressor to control
- **Convolution as synthesis:** Load non-IR files (speech, drum break) into convolution reverb — imprints spectral character
- **Granular reverb:** Very short reverb (0.1-0.3s) high diffusion on percussion — smears transient into tonal cloud

### The Frequency Dance
At any moment, each frequency band should have one primary element. When one opens up, another pulls back:
- Chord filter opens into highs → pull hi-hat back
- Bass drops → kick shortens
- Reverb tail fills → dry elements duck
This is mix engineering as composition.

### When to Apply These
- User says "make it breathe" or "it sounds static" → micro-modulation
- User says "more space" or "deeper" → dub techniques (delay throws, reverb composition)
- User says "more groove" or "make it pump" → creative sidechain
- User says "more texture" or "more complex" → textural layering
- User says "surprise me" or "WTF moment" → brief textural disruption (2-8 beats max)
- User says "warmer" or "more analog" → oscillator drift + subtle saturation + filter breathing

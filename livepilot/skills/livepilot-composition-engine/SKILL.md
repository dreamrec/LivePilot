---
name: livepilot-composition-engine
description: Compositional analysis, transition planning, and translation checking — the diagnostic/analytical side of form. Use when the user wants to "analyze song structure", "improve transitions", "check song flow", "detect motifs", "transform a section", or "score phrase impact". For constructive arrangement work (arrange, build a verse, add an intro, scene-to-arrangement), use livepilot-arrangement instead.
---

# Composition Engine — Structure, Transitions, and Form

The composition engine operates three sub-engines: compositional analysis (structure and motifs), transition planning (section-to-section flow), and translation checking (how the mix survives different playback systems). It also provides form-level tools for emotional arc and arrangement planning.

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
# Example — agent received "evolving polyrhythmic ambient at 120 BPM, build the section arc"
hit = extension_atlas_search(namespace="packs", query="evolving polyrhythmic ambient generative")
# → midi_tools_by_philip_meyer + drone_lab + cross-pack workflows for generative form

workflow = extension_atlas_get("packs", "dub_techno_spectral_drone_bed")
# → reveals signal_flow: HDG → PitchLoop89 cross-feedback → Convolution Reverb

drone_lab = extension_atlas_get("packs", "drone_lab")
# → notable_presets reveals Razor Wire Drone with macros Filter Control=108, Movement=53...

# Now plan the section/transition with concrete preset names + macro values, not vague descriptions
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

## Composition Sub-Engine

Analyze and transform the structural elements of a track.

### Analysis Flow

1. Call `analyze_composition` — runs a full structural pass returning sections, motifs, phrase grid, and form classification
2. Call `get_section_graph` — returns the section map: intro, verse, chorus, bridge, drop, breakdown, outro with bar ranges
3. Call `get_phrase_grid` — returns the rhythmic and melodic phrase boundaries within each section
4. Call `get_motif_graph` — returns detected melodic and rhythmic motifs with their occurrence locations and transformation history

### Transformation

Once you understand the structure:

- `transform_motif(motif_id, transformation)` — apply a transformation to a detected motif. Transformations include: inversion, retrograde, augmentation, diminution, transposition, fragmentation, sequence
- `transform_section(section_id, transformation)` — apply a structural transformation to an entire section. Transformations include: extend, compress, strip_down, build_up, reharmonize, rhythmic_variation

Always capture before state with `get_notes` or `get_arrangement_notes` before transforming. Evaluate the result with `evaluate_composition_move`.

### Motif Work

The motif graph tracks recurring melodic and rhythmic patterns:

- Each motif has an `id`, `pitches`, `rhythms`, `first_occurrence`, and `occurrences` list
- Related motifs are linked by transformation edges (e.g., motif_2 is an inversion of motif_1)
- Use the motif graph to ensure thematic coherence — transformations should derive from existing material

## Transition Sub-Engine

Plan and execute smooth transitions between sections.

### Transition Flow

1. `analyze_transition(from_section, to_section)` — examine the current transition between two sections. Returns energy delta, timbral shift, harmonic distance, and detected issues
2. `plan_transition(from_section, to_section)` — generate a transition plan based on detected issues. Returns an ordered list of moves (filter sweeps, risers, drum drops, fills, automation curves)
3. `score_transition(from_section, to_section)` — rate the current transition quality (0.0-1.0) with breakdown by energy, harmony, rhythm, and timbral continuity
4. Execute the planned moves using appropriate tools (`set_clip_automation`, `add_notes`, `set_device_parameter`, `apply_automation_shape`)
5. `evaluate_composition_move` — judge whether the transition improved

See `references/transition-archetypes.md` for common transition patterns and when to use each.

### Transition Principles

- Energy changes should be gradual unless a hard cut is intentional
- Harmonic transitions need a pivot chord or shared tone
- Rhythmic transitions benefit from a fill or break at the boundary
- Timbral shifts should start 1-2 bars before the section change
- The most effective transitions prepare the listener's ear before the change lands

## Translation Sub-Engine

Check how the mix translates across playback systems.

### Translation Flow

1. `check_translation` — run translation analysis on the current mix
2. `get_translation_issues` — return specific problems:
   - **mono_collapse**: elements that disappear or phase-cancel in mono playback
   - **spectral_consistency**: frequency balance shifts between monitoring contexts
   - **low_end_translation**: bass content that may vanish on small speakers
   - **loudness_consistency**: perceived loudness variation across systems

Translation issues feed back into the mix engine — a mono collapse issue becomes a stereo_width critic issue for the mix loop.

## Form Sub-Engine

High-level arrangement and emotional arc tools.

### Form Flow

1. `get_emotional_arc` — map the energy/intensity curve across the entire track, identifying peaks, valleys, and plateaus
2. `plan_arrangement` — generate an arrangement plan based on the current form, suggesting section order, lengths, and energy targets
3. `apply_gesture_template` — apply a predefined arrangement gesture (build, drop, breakdown, outro_fade, intro_build) to a bar range

See `references/form-patterns.md` for common song forms and energy curves by genre.

### Arrangement Principles

- Every section should have a clear purpose: introduce, develop, contrast, resolve, release
- The energy arc should have at least one clear peak — flat energy across the entire track lacks emotional impact
- Contrast drives interest: loud/quiet, dense/sparse, bright/dark
- Repetition builds familiarity but needs variation to avoid fatigue — transform on repeat, do not copy verbatim
- Transitions are as important as sections — budget time for them in the arrangement

## Combining Sub-Engines

A typical compositional improvement session:

1. `analyze_composition` to understand current structure
2. `get_emotional_arc` to see the energy shape
3. Identify the weakest section or transition
4. Use the transition sub-engine to fix section boundaries
5. Use motif transformations to add thematic development
6. `check_translation` to verify the changes survive mono/small speakers
7. `evaluate_composition_move` after each change

Always work one change at a time. Verify and evaluate before moving to the next intervention.

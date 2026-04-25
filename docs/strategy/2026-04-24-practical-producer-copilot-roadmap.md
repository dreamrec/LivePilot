# LivePilot Practical Producer Copilot Roadmap

**Status:** Strategy / product architecture draft  
**Date:** 2026-04-24  
**Scope:** How to evolve LivePilot from a large Ableton MCP tool system into a practical, producer-facing copilot.  
**Core stance:** LivePilot should help producers make better decisions faster. It should not try to replace the producer or promise full autonomous track creation.

---

## 1. Executive Position

LivePilot is strongest when it acts as a high-agency studio assistant:

- it understands the Ableton session,
- it can perform concrete DAW operations,
- it can generate musical options,
- it can listen back through analyzer data,
- it can compare versions,
- it can remember what the user keeps or rejects,
- and it keeps the producer in control.

The wrong direction is "AI producer that makes finished tracks by itself."

The right direction is:

> LivePilot is the practical Ableton copilot for starting ideas, building parts, shaping sounds, arranging sections, comparing options, and improving mixes while the producer remains the final musical authority.

This is more realistic, more useful, and more defensible than autonomy-first positioning.

---

## 2. Honest Current-State Review

### What LivePilot Already Has

LivePilot has unusually deep infrastructure compared with most AI DAW-control projects:

| Area | Current asset | Why it matters |
|------|---------------|----------------|
| DAW control | Remote Script + FastMCP server | Real Ableton operations, not vague advice |
| Tool coverage | 430 tools across 53 domains | Broad control surface for production tasks |
| Device knowledge | Device Atlas | Reduces hallucinated device/preset names |
| Analyzer | M4L master analyzer, RMS, spectrum, key, pitch, FluCoMa descriptors, capture | Gives the agent feedback beyond session metadata |
| Semantic moves | 44 high-level musical intents | Better interface than raw tool calls |
| Sample intelligence | Browser, filesystem, Splice, fitness critics, techniques | Useful for sound selection and sample workflows |
| Composer | Prompt-to-plan pipeline | Can scaffold multi-layer ideas |
| Preview/experiment | Preview Studio, experiment branches, compare/commit | Right shape for safe agentic workflows |
| Memory/taste | SessionLedger, Taste Graph, anti-preferences | Foundation for personalization |
| Reference engine | Reference profiles and gap planning | Right direction for production matching |

This is a strong base. The problem is not lack of capability. The problem is product shape.

### Main Weaknesses

1. Too much of the system is exposed as a tool catalog.
2. Musical generation is not yet organized around "players" with role-specific taste.
3. Analyzer output is still closer to measurement than production judgment.
4. Preview/branching exists, but the user experience is not yet centered around A/B decision making.
5. Memory stores useful signals, but it is not yet clearly presented as taste learning.
6. Reference matching needs to become stem-aware and action-oriented.
7. The public story leads with scale instead of usefulness.

The current product reads like:

> "LivePilot can do almost everything in Ableton."

The more compelling product should read like:

> "LivePilot helps you create, revise, compare, and finish better Ableton ideas."

---

## 3. Product Principles

### Principle 1: Producer Control First

Every meaningful creative change should be previewable, explainable, and easy to keep or reject.

LivePilot should generate options, not force outcomes.

### Principle 2: Fewer User-Facing Actions, More Internal Tools

Keep 430 tools internally. Expose producer-level actions externally.

The agent should usually think in terms of:

- create a loop,
- build a bassline,
- make a drum variation,
- tighten the low end,
- compare this to the reference,
- turn this loop into an arrangement,
- make this sound more dub techno,
- keep the darker version.

Not:

- call tool 1,
- call tool 2,
- call tool 3,
- manually coordinate low-level state.

### Principle 3: Listen, Then Act, Then Listen Again

The core agent loop should become:

1. measure,
2. propose,
3. preview,
4. apply,
5. measure after,
6. compare,
7. ask user to keep/revise/revert.

This is realistic agentic production. It turns analysis into decision support.

### Principle 4: Musical Roles Beat Generic Generation

"Generate notes" is too generic.

LivePilot should generate parts through role-aware players:

- Drum Player,
- Bass Player,
- Chord/Keys Player,
- Texture Player,
- Hook Player,
- FX/Transition Player,
- Arrangement Director,
- Mix Assistant.

Each player should understand musical responsibility, genre, density, interaction with other parts, and taste.

### Principle 5: Taste Is Learned From Decisions

The best taste signal is not what the agent generates. It is what the user keeps, rejects, undoes, regenerates, or edits.

LivePilot should treat every production decision as training data for the user's taste.

---

## 4. Product Repositioning

### Current Risky Positioning

"Agentic production system with 430 tools."

This is impressive technically, but it does not tell a producer why they should use it.

### Better Positioning

"An AI studio assistant for Ableton that helps you start ideas, build parts, shape sounds, compare versions, and improve mixes while you stay in control."

### Messaging Hierarchy

Lead with:

1. Start ideas faster.
2. Generate better variations.
3. Find and shape sounds faster.
4. Turn loops into arrangements.
5. Compare changes before committing.
6. Learn the producer's taste over time.

Move tool count lower on the page. Tool count is proof, not the promise.

---

## 5. Tool Profiles: Make 430 Tools Usable

### Problem

A model seeing hundreds of tools can over-plan, pick too low-level a route, or lose musical intent in API mechanics.

### Direction

Create tool profiles that expose a focused subset based on the current mode.

Suggested profiles:

| Profile | Purpose |
|---------|---------|
| `start_idea` | Build an initial loop or sketch |
| `drums` | Drum programming, groove, kit building |
| `bass` | Bassline generation, kick/bass lock |
| `chords` | Harmony, pads, keys, voicing |
| `sound_design` | Device chains, timbre shaping |
| `sample` | Search, chop, slice, flip, stem extract |
| `arrange` | Turn clips/scenes into sections |
| `mix` | Balance, EQ, masking, loudness, width |
| `reference` | Compare with target track/style |
| `perform` | Safe live-performance operations |
| `diagnose` | Read-only inspection and issue finding |

### Producer-Level Actions

Add a layer above raw tools:

```text
create_loop
make_variation
build_drum_pattern
build_bassline
build_chord_part
build_texture_layer
build_device_chain
find_sample_for_role
extract_part_from_audio
analyze_stem_mix
compare_before_after
commit_or_revert
arrange_loop_into_song
```

These should compile internally into existing tool sequences.

### Acceptance Criteria

- The default agent mode exposes no more than 40-60 tools.
- Every profile has a clear "when to use" contract.
- All profile actions are previewable where practical.
- The full 430-tool surface remains available for expert/debug mode.

---

## 6. Producer Players

The most important musical upgrade is moving from generic note generation to role-specific musical players.

### 6.1 Drum Player

Responsible for:

- kick pattern,
- snare/clap placement,
- hats,
- percussion density,
- swing,
- fills,
- ghost hits,
- genre groove conventions,
- drum sound selection,
- interaction with bass.

Inputs:

```text
genre
tempo
energy
reference_profile
current_bass_role
desired_density
humanization
user_taste
```

Outputs:

```text
drum_clip
kit_or_samples
groove_metadata
variation_controls
```

Key features:

- generate 3 groove variants,
- classify each as restrained / driving / broken,
- explain rhythmic differences,
- let the user regenerate only hats, only kick, only percussion, or only fills.

### 6.2 Bass Player

Responsible for:

- root motion,
- register,
- sub sustain,
- kick relationship,
- octave jumps,
- ghost notes,
- groove interaction,
- genre bass grammar.

The Bass Player should explicitly decide:

- follow kick,
- answer kick,
- avoid kick,
- hold long sub,
- play syncopated stabs,
- double chord roots,
- create counter-movement.

### 6.3 Chord / Keys Player

Responsible for:

- harmonic rhythm,
- voicing,
- inversion,
- register,
- density,
- chord extensions,
- comping rhythm,
- pad vs stab vs keys behavior.

It should understand that "deep house keys" and "ambient pad" are different musical jobs, not just different presets.

### 6.4 Texture Player

Responsible for:

- atmosphere,
- noise,
- field recordings,
- resampled tails,
- granular layers,
- reverse swells,
- dub delays,
- spectral motion.

This player is important because electronic music often lives or dies by background texture.

### 6.5 Hook Player

Responsible for:

- motif creation,
- call-and-response,
- memorable phrase placement,
- variation over sections,
- avoiding overcrowding.

It should work with Hook Hunter and motif tools already in the repo.

### 6.6 FX / Transition Player

Responsible for:

- risers,
- impacts,
- filter sweeps,
- delay throws,
- breakdown-to-drop energy,
- scene transitions,
- automation gestures.

### 6.7 Arrangement Director

Responsible for:

- turning loops into sections,
- deciding when to add/remove layers,
- building contrast,
- preserving identity,
- avoiding static 8-bar loops.

### 6.8 Mix Assistant

Responsible for:

- gain staging,
- masking,
- stereo width,
- low-end discipline,
- harshness,
- loudness,
- reference comparison.

The Mix Assistant should never claim it can "master" taste. It should frame itself as evidence-driven mix help.

---

## 7. One Excellent Loop Starter

Before chasing full-song autonomy, LivePilot should make one workflow excellent:

> Create a strong editable 8-bar idea in Ableton.

### User Flow

1. User says: "Start a dark garage loop, 132 BPM, moody, not too busy."
2. LivePilot creates:
   - drums,
   - bass,
   - chord/texture layer,
   - optional vocal/sample accent,
   - simple mix balance.
3. LivePilot renders or captures the loop.
4. LivePilot creates 2-3 variants:
   - safer,
   - darker,
   - more energetic.
5. User previews.
6. User can regenerate a single lane.
7. User commits one version.

### Internal Pipeline

```text
parse_intent
build_reference_profile_if_needed
activate_tool_profile(start_idea)
Drum Player -> Bass Player -> Chord/Texture Player
rough_mix
capture_loop
analyze_loop
generate_variants
compare_variants
commit_chosen_variant
write_taste_signal
```

### Why This Matters

This is demo-friendly, musically useful, and realistic. It proves the whole system without promising a finished song.

---

## 8. Analyzer Evolution: From Meter to Listening Model

### Current State

The analyzer can read the master bus and provide real-time DSP signals:

- spectrum,
- RMS/peak,
- loudness,
- pitch/key,
- chroma,
- mel spectrum,
- onset,
- novelty,
- capture.

This is useful, but the master signal is ambiguous. If the mix is muddy, the analyzer may know the frequency range but not the responsible musical element.

### Target State

The analyzer should answer:

- What changed?
- Which musical role caused it?
- Did the move help?
- What should we try next?

### 8.1 Before/After Audio Delta

Add a first-class before/after comparison pipeline.

Proposed tools:

```text
capture_analysis_window
analyze_rendered_section
compare_before_after
score_move_impact
explain_audio_delta
```

Output shape:

```json
{
  "goal": "tighten_low_end",
  "before": {
    "low_end_clarity": 0.42,
    "mud_200_400": 0.68,
    "peak_headroom_db": -1.2
  },
  "after": {
    "low_end_clarity": 0.61,
    "mud_200_400": 0.49,
    "peak_headroom_db": -2.4
  },
  "verdict": "improved",
  "confidence": 0.72,
  "next_move": "keep_or_make_small_followup_cut"
}
```

### 8.2 Stem-Aware Analysis With Ableton Stem Separation

Ableton Live 12.3 Suite can separate audio into:

- vocals,
- drums,
- bass,
- other.

This is a major opportunity. Stem separation gives source attribution.

Without stems:

> "There is low-mid buildup."

With stems:

> "The bass stem and other stem are colliding around 180-300 Hz. The drums are not the source."

Proposed tools:

```text
separate_clip_to_stems
discover_stem_tracks
analyze_stem_balance
analyze_stem_groove
analyze_kick_bass_relationship
analyze_vocal_masking
analyze_other_stem_density
build_reference_stem_profile
compare_to_reference_stems
suggest_stem_aware_mix_moves
```

Practical automation note:

- If Live exposes stem separation through Python LOM or Max API, implement `separate_clip_to_stems`.
- If not, support a manual-first flow:
  1. user runs "Separate Stems to New Audio Tracks,"
  2. LivePilot detects and labels the resulting tracks,
  3. LivePilot analyzes them.
- Avoid fragile UI automation as a core release feature.

### 8.3 Stem Balance Profile

For each section or reference track:

```json
{
  "section": "drop_1",
  "stem_balance": {
    "drums_lufs": -10.5,
    "bass_lufs": -13.2,
    "vocals_lufs": null,
    "other_lufs": -16.4
  },
  "ratios": {
    "drums_to_bass_db": 2.7,
    "bass_to_other_db": 3.2
  },
  "notes": [
    "drums dominate energy",
    "bass is sustained but controlled",
    "other stem is wide and quiet"
  ]
}
```

### 8.4 Kick/Bass Relationship

This is one of the most practical analyzer features for electronic music.

Inputs:

- drum stem,
- bass stem,
- tempo/grid,
- onset detection,
- spectrum.

Detect:

- kick fundamental,
- bass fundamental,
- overlap in 40-120 Hz,
- bass note timing relative to kick,
- sub sustain,
- sidechain-like ducking,
- kick transient masking,
- bass notes that obscure kick hits.

Suggested outputs:

```text
kick_bass_lock_score
sub_overlap_score
timing_conflict_beats
recommended_fix
```

Recommended fixes:

- shorten bass envelope,
- move bass note after kick,
- sidechain bass,
- cut bass harmonics around kick fundamental,
- tune kick or transpose bass,
- remove bass note under heavy kick.

### 8.5 Drum Analyzer

The Drum Analyzer should work from:

- a drum stem,
- a drum bus,
- a selected clip,
- or a solo-captured drum track.

Detect:

- kick positions,
- snare/clap positions,
- hat density,
- swing,
- ghost hits,
- transient sharpness,
- fill locations,
- groove repetition,
- empty-beat tension,
- overly rigid timing.

Outputs:

```json
{
  "kick_pattern": "four_on_floor_with_variation",
  "snare_backbeat_confidence": 0.91,
  "hat_density": "medium_high",
  "swing_estimate": 0.57,
  "fill_density": "low",
  "groove_stability": 0.82,
  "humanization_need": "slight",
  "suggestions": [
    "add 1-2 ghost hats before bar 4",
    "reduce velocity on offbeat hats",
    "add a short fill into the next section"
  ]
}
```

This is more musically valuable than raw spectral descriptors.

### 8.6 Track-Level Analysis Without Per-Track Analyzers

Do not add an analyzer to every track by default. That is CPU-heavy and fragile.

Use a solo-capture scan:

1. save mute/solo state,
2. solo one track,
3. capture a short window,
4. analyze,
5. move to next track,
6. restore state.

Tools:

```text
analyze_tracks_sequentially
build_track_fingerprint_map
build_masking_matrix
rank_mix_problems_by_track
```

This gives track attribution without persistent per-track DSP devices.

---

## 9. Reference-Aware Production

The reference engine should become more concrete and stem-aware.

### Reference Profile

A reference profile should contain:

```json
{
  "genre": "dub_techno",
  "tempo_range": [124, 130],
  "stem_balance": {
    "drums_to_bass_db": 2.0,
    "other_width": "wide",
    "vocal_presence": "none_or_sparse"
  },
  "groove": {
    "swing": "subtle",
    "hat_density": "medium",
    "kick_role": "steady_anchor"
  },
  "mix": {
    "low_end": "deep_controlled",
    "midrange": "recessed",
    "highs": "soft",
    "space": "long_dub_tails"
  },
  "arrangement": {
    "evolution": "slow_filter_motion",
    "contrast": "low_to_medium",
    "hook_style": "texture_identity"
  },
  "avoid": [
    "bright EDM leads",
    "busy fills",
    "wide sub bass"
  ]
}
```

### Reference Comparison

Useful comparison should say:

- your drums are quieter/louder than the reference,
- your bass sustain is longer,
- your other stem is brighter,
- your low mids are denser,
- your groove is straighter,
- your transition impact is weaker,
- your section contrast is lower.

It should not say vague things like:

> "Make it warmer and more polished."

It should say:

> "The reference keeps the other stem 4-6 dB below the drums and uses a long, dark delay tail. Your other stem is louder and brighter. Try lowering the pad bus 2 dB, low-passing the delay return, and adding slow filter automation."

---

## 10. Audio Extraction and Transcription Policy

Live now has strong native workflows:

- audio-to-MIDI conversion,
- stem separation,
- warping,
- slicing,
- Simpler,
- clip analysis.

LivePilot should not blindly prefer external models.

### Recommended Hierarchy

```text
extract_musical_part_from_audio(source, target, method="auto")
```

Decision rules:

| Target | Preferred path |
|--------|----------------|
| drums | Ableton drum conversion, onset/slice classifier, drum stem analysis |
| bass | stem separation first if full mix, then melody/audio-to-MIDI path |
| melody/vocal | Ableton melody conversion or Basic Pitch fallback |
| harmony | Ableton harmony conversion, then key/chord cleanup |
| sample flip | stem separation + slicing + role analysis |
| reference analysis | stem separation + offline descriptors |

### Basic Pitch Role

Spotify Basic Pitch should be optional, not the default.

Use it when:

- the input is vocal, guitar, lead, or monophonic/polyphonic melodic audio,
- pitch bends/slides matter,
- offline batch extraction is useful,
- Ableton's native conversion gives poor melodic results.

Do not use it for drums.

### Cleanup Is More Important Than Extraction

The key differentiator is not raw transcription. It is musical cleanup:

- remove tiny accidental notes,
- quantize gently,
- snap to key when desired,
- preserve expressive timing,
- simplify over-dense harmony,
- choose playable register,
- make the result fit the current track.

---

## 11. Branching, Preview, and Decision UX

The experiment system is already pointed in the right direction. The next step is making it feel like a producer workflow.

### Required Concepts

- named branches,
- rendered audio previews,
- branch notes,
- before/after analysis,
- keep/revise/revert,
- partial merge of useful parts,
- user taste capture.

### Example Branch Set

```text
Experiment: "make the loop darker"

A: safer
   - lower pad brightness
   - add short dub delay
   - keep drums unchanged

B: heavier
   - saturate bass
   - reduce hats
   - widen texture

C: stranger
   - resample chord tail
   - reverse into bar 4
   - add filtered vocal ghost
```

User can say:

> Keep B's bass, but use A's drums and C's transition.

That is the practical magic. Not full autonomy, but composable decision support.

---

## 12. Sidecar UI

Chat alone is not enough for trust.

LivePilot should eventually have a small sidecar/panel showing:

- current mode/profile,
- analyzer connection,
- stem-separation availability,
- current plan,
- pending changes,
- preview buttons,
- A/B comparison,
- commit/revert,
- last action ledger,
- sample/Splice quota warnings,
- reference target,
- taste notes.

This UI does not need to be visually heavy. It needs to make invisible agent state visible.

### Minimal UI States

```text
Idle
Inspecting
Planning
Preview ready
Applying
Comparing
Awaiting commit
Committed
Reverted
Needs user action
```

---

## 13. Taste Memory

Memory should become practical taste learning.

### Signals To Capture

| User behavior | Taste signal |
|---------------|--------------|
| keeps a variant | positive preference |
| rejects a variant | anti-preference |
| asks for "less busy" | density preference |
| undoes a bright lead | anti-preference: bright lead |
| repeatedly keeps sparse drums | groove/density preference |
| chooses stock devices | device preference |
| rejects heavy compression | dynamics preference |

### Example Taste Inference

```json
{
  "producer_profile": {
    "drums": {
      "density": "sparse_to_medium",
      "swing": "moderate",
      "fills": "rare"
    },
    "sound_design": {
      "brightness": "dark",
      "reverb": "long_but_lowpassed",
      "distortion": "parallel_subtle"
    },
    "arrangement": {
      "novelty": "moderate",
      "section_changes": "gradual"
    },
    "avoid": [
      "busy top loops",
      "bright supersaw leads",
      "over-compressed drums"
    ]
  }
}
```

LivePilot should be able to say:

> I kept this version darker because you usually reject bright high-mid leads and keep low-passed texture layers.

That makes the system feel personal and useful.

---

## 14. Plugin Inventory and Third-Party Reality

Device Atlas is valuable, but many producers use third-party plugins.

LivePilot should learn:

- installed plugins,
- favorite plugins,
- broken plugins,
- CPU-heavy plugins,
- user-preferred chains,
- stock-only mode,
- project-safe mode,
- plugin categories.

### Plugin Inventory Model

```json
{
  "plugin": "Valhalla VintageVerb",
  "type": "reverb",
  "status": "available",
  "cpu_profile": "medium",
  "user_affinity": 0.82,
  "roles": ["dark_room", "long_tail", "dub_send"],
  "avoid": ["subtle_insert_space"]
}
```

This should feed device selection:

- "use only stock Ableton,"
- "use my favorites,"
- "avoid CPU-heavy plugins,"
- "use safe live-performance devices."

---

## 15. Concrete New Workflows

### 15.1 Create Loop

```text
create_loop(
  style="dark UK garage",
  tempo=132,
  energy="medium",
  density="not too busy",
  reference="Burial-ish but cleaner",
  output="3 variants"
)
```

Expected behavior:

- builds drums, bass, texture, optional hook,
- rough balances,
- captures audio,
- compares variants,
- asks which to keep.

### 15.2 Stem-Aware Reference Match

```text
analyze_reference_track("/path/ref.wav")
compare_current_loop_to_reference()
suggest_reference_moves()
```

Expected output:

```text
Your drums are close in loudness, but the bass sustain is longer than the reference and the other stem is 3 dB too bright. Suggested moves:
1. shorten bass release,
2. low-pass texture bus,
3. add darker delay return.
```

### 15.3 Drum Improvement

```text
analyze_drum_groove()
make_drums_less_stiff()
compare_before_after()
```

Expected behavior:

- identifies rigid timing or flat velocities,
- proposes groove/humanization,
- previews,
- user commits or rejects.

### 15.4 Kick/Bass Fix

```text
analyze_kick_bass_relationship()
tighten_low_end()
compare_before_after()
```

Expected behavior:

- finds whether conflict is timing, frequency, sustain, or level,
- applies a focused fix,
- measures improvement.

### 15.5 Loop To Arrangement

```text
arrange_loop_into_song(
  target_length="2:30",
  structure="intro, groove, break, return, outro",
  preserve_identity=true
)
```

Expected behavior:

- creates sections,
- introduces/removes layers,
- adds transitions,
- uses arrangement energy analysis.

---

## 16. Implementation Phases

### Phase 1: Truth and Product Shape

Goal: make the system easier for agents and users to reason about.

Tasks:

1. Finish metadata/doc truth cleanup.
2. Define producer-level actions.
3. Add tool-profile infrastructure.
4. Create `start_idea`, `mix`, `sample`, `arrange`, and `diagnose` profiles.
5. Update skills so agents default to profiles, not raw tool sprawl.

Deliverable:

- user can ask for common production tasks and LivePilot routes through a clean profile.

### Phase 2: Loop Starter

Goal: one excellent musical entry point.

Tasks:

1. Implement `create_loop`.
2. Add Drum Player v1.
3. Add Bass Player v1.
4. Add Chord/Texture Player v1.
5. Add simple variant generation.
6. Add capture + compare.

Deliverable:

- LivePilot can generate 3 usable 8-bar loop variants and let the user keep one.

### Phase 3: Analyzer as Decision Engine

Goal: make analysis action-oriented.

Tasks:

1. Add before/after comparison.
2. Add track solo-capture scan.
3. Add masking matrix.
4. Add kick/bass analysis.
5. Add drum groove analysis.
6. Add verdicts tied to semantic move goals.

Deliverable:

- semantic moves can verify whether they helped.

### Phase 4: Stem-Aware Intelligence

Goal: use Ableton stem separation as source attribution.

Tasks:

1. Probe whether stem separation is callable through LOM/Max.
2. If callable, implement `separate_clip_to_stems`.
3. If not callable, implement manual-first stem discovery.
4. Add stem balance analysis.
5. Add reference stem profiles.
6. Add stem-aware mix suggestions.

Deliverable:

- LivePilot can analyze drums/bass/vocals/other separately and make concrete mix/composition suggestions.

### Phase 5: Reference and Taste

Goal: make suggestions personal and stylistically grounded.

Tasks:

1. Extend reference profiles with stem/groove/mix descriptors.
2. Connect kept/rejected branches to taste dimensions.
3. Add explanations for taste-driven choices.
4. Add anti-preference enforcement in players.

Deliverable:

- LivePilot adapts to producer taste and explains why.

### Phase 6: Sidecar UI

Goal: make agent state visible and safe.

Tasks:

1. Build minimal panel.
2. Show active mode, analyzer state, pending plan.
3. Add preview/commit/revert controls.
4. Add branch A/B controls.
5. Add taste/reference summary.

Deliverable:

- producer can use LivePilot without trusting a black-box chat thread.

---

## 17. Success Metrics

### Product Metrics

- Time from prompt to usable 8-bar loop.
- Number of user actions needed to preview variants.
- Keep rate of generated variants.
- Regenerate rate per lane.
- Percent of semantic moves with before/after verification.
- Percent of suggestions grounded in analyzer or session evidence.

### Musical Metrics

- Fewer static 8-bar loops.
- Better kick/bass clarity after low-end moves.
- Better stem balance against reference profiles.
- Higher user keep rate over time.
- Fewer repeated rejected move types.

### Trust Metrics

- Every destructive operation is previewed or undoable where practical.
- Every external side effect is disclosed.
- Every analyzer-gated decision states confidence.
- Every failed analyzer/stem operation degrades gracefully.

---

## 18. Demo Plan

The market will believe videos more than architecture.

Create demos around workflows:

1. "Start a dark garage loop from scratch."
2. "Make these drums less stiff."
3. "Fix kick and bass conflict using analyzer feedback."
4. "Separate a reference into stems and match the low-end balance."
5. "Turn an 8-bar loop into a 90-second arrangement."
6. "Find a vocal sample, chop it, and build a texture."
7. "A/B three versions and keep the best one."
8. "LivePilot remembers that I prefer sparse drums."

Each demo should show:

- the user prompt,
- the plan,
- the audio preview,
- the before/after comparison,
- the commit decision.

---

## 19. Risks

### Risk: Overclaiming Autonomy

Mitigation:

- use "copilot," "assistant," "preview," "compare," and "producer in control."
- avoid "finished song from prompt."

### Risk: Analyzer Overconfidence

Mitigation:

- show confidence,
- separate measurement from taste,
- phrase verdicts as evidence, not truth.

### Risk: Stem Separation Artifacts

Mitigation:

- detect artifact risk,
- support High Speed vs High Quality mode,
- recommend shorter clips,
- never treat stems as perfect ground truth.

### Risk: Too Much UI/Workflow Complexity

Mitigation:

- start with one flagship flow,
- keep advanced modes hidden,
- make branch/preview concepts visual.

### Risk: Tool Count Still Dominates Agent Behavior

Mitigation:

- default to profiles,
- expose high-level actions,
- reserve raw tools for expert/debug mode.

---

## 20. Near-Term Build List

If we had to pick only the next 10 concrete items:

1. Add tool profiles.
2. Add `create_loop`.
3. Add Drum Player v1.
4. Add Bass Player v1.
5. Add before/after capture comparison.
6. Add track solo-capture scan.
7. Add kick/bass relationship analysis.
8. Add drum groove analysis.
9. Add manual-first stem discovery and stem balance analysis.
10. Add branch preview/commit UX contract.

This sequence makes LivePilot more useful without pretending it can autonomously finish songs.

---

## 21. Final Product Thesis

LivePilot should not compete with prompt-to-song systems.

It should compete in a different category:

> AI-assisted production inside a real DAW.

That category is not won by generating a whole song. It is won by making the producer faster, more decisive, and more exploratory without breaking flow.

The strongest LivePilot is:

- role-aware,
- reference-aware,
- stem-aware,
- taste-aware,
- preview-first,
- reversible where possible,
- honest where not,
- and deeply Ableton-native.

That is a practical and differentiated tool.

---

## 22. External Implementation References

These are useful references, not dependencies that must be adopted:

- Ableton Stem Separation: https://www.ableton.com/stem-separation-in-ableton-live/
- Ableton Stem Separation FAQ: https://help.ableton.com/hc/en-us/articles/23730994755996-Stem-Separation-in-Ableton-Live-FAQ
- Ableton Audio to MIDI manual: https://www.ableton.com/en/manual/converting-audio-to-midi/
- Spotify Basic Pitch: https://github.com/spotify/basic-pitch
- Essentia: https://essentia.upf.edu/
- librosa feature extraction: https://librosa.org/doc/main/feature.html
- Demucs: https://github.com/facebookresearch/demucs


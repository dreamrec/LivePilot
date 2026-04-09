# LivePilot Skills Architecture V2 — Design Spec

**Date:** 2026-04-09
**Status:** Draft
**Goal:** Decompose the monolithic `livepilot-core` skill into focused domain skills and add V2 engine skills that teach Claude how to orchestrate multi-step agentic loops.

---

## Problem

LivePilot has 236 tools across 31 domains but only 2 skills:
- `livepilot-core` — 900+ line monolith covering everything (golden rules, device atlas, recipes, theory, mixing, all in one)
- `livepilot-release` — internal release checklist

The V2 engine architecture added 12 new subsystems (mix_engine, sound_design, performance_engine, reference_engine, transition_engine, translation_engine, evaluation fabric, project brain, action ledger, capability state, memory fabric, conductor) — none of which have corresponding skills. Claude has no procedural knowledge for how to orchestrate these powerful agentic loops.

**Key gap:** Claude knows what tools exist (from MCP tool descriptions) but has zero guidance on:
- How to chain tools into evaluation loops (before → act → after → evaluate → keep/undo)
- When to run critics vs planners vs evaluators
- What the correct orchestration sequence is for each engine
- How to use capability state to adapt behavior to what's available

## Design Principles

1. **Progressive disclosure** — SKILL.md body ≤2000 words. Detailed content in `references/`
2. **Non-overlapping triggers** — Each skill triggers on distinct intent patterns. "Mix my track" loads exactly one skill, not five
3. **Engine skills teach loops, not tools** — Tool descriptions already explain parameters. Engine skills teach the multi-step orchestration pattern
4. **Imperative writing style** — Verb-first instructions per Anthropic guidelines
5. **Reference-heavy** — Device atlas, recipes, patterns all live in `references/`, not SKILL.md body

## Architecture

### Tier 1 — Foundation (1 skill)

#### `livepilot-core` (slimmed)

**Triggers:** Any Ableton Live / LivePilot work (always-on foundation skill)

**SKILL.md body (~1500 words):**
- Golden rules (14 rules, condensed)
- Tool speed tiers (instant/fast/slow/heavy)
- Error handling protocol
- Index conventions (0-based tracks, negative returns, -1000 master)
- Pointer to domain skills for specific workflows
- Pointer to engine skills for agentic loops

**References (moved from current SKILL.md body):**
- `references/overview.md` — (existing) full architecture overview
- `references/device-atlas/` — (existing) 280+ device reference corpus
- `references/automation-atlas.md` — (existing) 16 curve types, 15 recipes
- `references/midi-recipes.md` — (existing) note patterns and rhythmic recipes
- `references/mixing-patterns.md` — (existing) gain staging, EQ, compression patterns
- `references/sound-design.md` — (existing) synthesis and design patterns
- `references/ableton-workflow-patterns.md` — (existing) session/arrangement workflows
- `references/memory-guide.md` — (existing) technique memory usage
- `references/m4l-devices.md` — (existing) M4L bridge reference

**What gets removed from current core:** Domain-specific workflow procedures (moved to domain skills), engine orchestration (moved to engine skills). Keep only the universal rules and conventions.

### Tier 2 — Domain Skills (4 skills)

These replace the domain-specific sections currently embedded in the monolithic `livepilot-core`.

#### `livepilot-devices`

**Triggers:** "load a device", "add an effect", "find a plugin", "device chain", "rack", "preset", "sound design setup", "load instrument"

**SKILL.md body (~1800 words):**
- Browser workflow: search_browser → load_browser_item (with exact URI)
- find_and_load_device shortcut (built-in effects only)
- Plugin health verification protocol (parameter_count, health_flags)
- Rack introspection (walk_device_tree, get_rack_chains)
- Simpler/sampler operations (load_sample, crop, reverse, slices)
- Device atlas lookup procedure
- Common pitfalls (hallucinated device names, AU/VST failure modes)

**References:**
- Points to `livepilot-core/references/device-atlas/` for the full corpus

#### `livepilot-notes`

**Triggers:** "write notes", "add a melody", "chord progression", "rhythm pattern", "MIDI", "transpose", "quantize", "Euclidean", "counterpoint", "scale", "key"

**SKILL.md body (~1800 words):**
- Note API: add_notes → get_notes → modify_notes → remove_notes cycle
- Modern API fields (probability, velocity_deviation, release_velocity, mute)
- Theory integration: identify_scale → detect_theory_issues → transpose_smart
- Generative tools: generate_euclidean_rhythm, generate_tintinnabuli, generate_phase_shift, generate_countermelody
- Harmony tools: suggest_next_chord, navigate_tonnetz, harmonize_melody, classify_progression
- MIDI I/O: export_clip_midi, import_midi_to_clip, analyze_midi_file
- Common patterns: chord voicing, bass line from chords, rhythmic layering

**References:**
- Points to `livepilot-core/references/midi-recipes.md`

#### `livepilot-mixing`

**Triggers:** "mix", "balance", "levels", "EQ", "compress", "panning", "sends", "master", "gain staging", "routing", "sidechain"

**SKILL.md body (~1800 words):**
- Read-before-write: get_session_info → get_track_info → get_device_parameters
- Volume/pan/send workflow (normalized ranges: vol 0-1, pan -1 to 1)
- Return track routing (create_return_track, set_track_send, set_track_routing)
- Metering workflow: get_track_meters, get_master_meters, get_master_spectrum
- Automation: set_clip_automation, generate_automation_curve (16 curve types)
- When to use mix_engine skill (for critic-driven analysis)

**References:**
- Points to `livepilot-core/references/mixing-patterns.md`
- Points to `livepilot-core/references/automation-atlas.md`

#### `livepilot-arrangement`

**Triggers:** "arrange", "structure", "intro", "verse", "chorus", "bridge", "drop", "breakdown", "sections", "scene to arrangement"

**SKILL.md body (~1500 words):**
- Session vs arrangement view mental model
- Scene workflow: create_scene → fire_scene → scene matrix
- Arrangement workflow: create_arrangement_clip → add_arrangement_notes
- Section graph: get_section_graph → understand song structure
- Scene-to-arrangement transfer: back_to_arranger workflow
- Cue points and navigation: toggle_cue_point, jump_to_cue
- When to use composition_engine skill (for form analysis and section transforms)

**References:**
- Points to `livepilot-core/references/ableton-workflow-patterns.md`

### Tier 3 — V2 Engine Skills (5 skills)

These are the core of the upgrade. Each teaches Claude how to orchestrate a specific agentic evaluation loop.

#### `livepilot-mix-engine`

**Triggers:** "analyze my mix", "mix issues", "masking", "frequency clash", "dynamics", "stereo width", "headroom", "mix feedback", "what's wrong with my mix"

**SKILL.md body (~2000 words):**
- **The Mix Critic Loop:**
  1. `get_mix_snapshot` or `analyze_mix` — build MixState
  2. Read `issues` from response — critics already ran
  3. `plan_mix_move` — get smallest intervention for top issue
  4. Capture before: `get_master_spectrum` + `get_master_rms`
  5. Execute the move (set_device_parameter, set_track_volume, etc.)
  6. Capture after: same reads
  7. `evaluate_mix_move` — pass before/after + goal
  8. If `keep_change=false` → `undo()`
  9. If kept → optionally `memory_learn(type="mix_template")`
- **Critics vocabulary:** masking, dynamics (over_compressed, flat_dynamics, low_headroom), stereo_width, spectral_balance
- **Move types:** gain_staging, bus_compression, transient_shaping, eq_cut, eq_boost, pan_spread
- **When M4L analyzer is absent:** Mix engine falls to heuristic mode (role-based masking only). State this to user.

**References:**
- `references/mix-critics.md` — detailed critic thresholds and evidence format
- `references/mix-moves.md` — complete move vocabulary with parameter ranges

#### `livepilot-sound-design-engine`

**Triggers:** "design a sound", "patch design", "timbre", "modulation", "synthesizer programming", "sound design feedback", "static sound", "make it move"

**SKILL.md body (~2000 words):**
- **The Sound Design Critic Loop:**
  1. `get_patch_model` — build PatchModel from current device state
  2. `analyze_sound_design` — run critics (static_timbre, no_modulation, missing_filter, etc.)
  3. `plan_sound_design_move` — get intervention for top issue
  4. Capture before: `get_device_parameters` + `get_master_spectrum`
  5. Execute (set_device_parameter, toggle_device, etc.)
  6. Capture after
  7. `evaluate_move(engine="sound_design")` — judge the change
  8. Keep or undo
- **Critics:** static_timbre, no_modulation_sources, modulation_flatness, missing_filter, spectral_imbalance
- **Moves:** modulation_injection, filter_shaping, parameter_automation, oscillator_tuning
- **Patch model structure:** blocks (oscillators, filters, effects), modulation sources, parameter values

**References:**
- `references/sound-design-critics.md` — critic details
- `references/patch-model.md` — PatchModel structure and block types

#### `livepilot-composition-engine`

**Triggers:** "compose", "section analysis", "phrase structure", "motif", "form", "transitions", "how does my song flow", "arrange sections", "song structure feedback"

**SKILL.md body (~2000 words):**
- **Three sub-engines in one skill:**
  - **Composition:** section graph, phrase grid, motif detection/transformation
  - **Transition:** transition planning, scoring, archetypes (energy ramp, filter sweep, etc.)
  - **Translation:** mono collapse check, stereo width, timbral consistency
- **The Composition Analysis Loop:**
  1. `analyze_composition` — build section graph + phrase grid
  2. `get_section_graph` / `get_phrase_grid` — understand structure
  3. `get_motif_graph` — detect recurring patterns
  4. `analyze_transition(from_section, to_section)` — evaluate transitions
  5. `plan_transition` → `score_transition` → execute → evaluate
- **Form engine:** `get_emotional_arc`, `transform_section`, `plan_arrangement`
- **Translation checks:** `check_translation` → `get_translation_issues` (mono compat, spectral balance across sections)

**References:**
- `references/transition-archetypes.md` — transition types and scoring criteria
- `references/form-patterns.md` — common song forms (AABA, verse-chorus, through-composed)

#### `livepilot-performance-engine`

**Triggers:** "perform live", "live set", "scene handoff", "energy flow", "safe moves", "what can I do live", "performance mode"

**SKILL.md body (~1500 words):**
- **Safety-first model:** Every move is classified as safe/caution/blocked/unknown
  - **Safe:** scene_launch, send_nudge, macro_nudge, filter_sweep, mute_toggle, volume_nudge
  - **Caution:** tempo_nudge, device_toggle, pan_nudge
  - **Blocked:** device_chain_surgery, arrangement_edit, track_create_delete, note_edit, clip_create_delete
  - **Unknown:** anything not in the above sets — treat as blocked
- **The Performance Loop:**
  1. `get_performance_state` — current scene, energy, playing clips
  2. `get_performance_safe_moves` — what interventions are available
  3. `check_safety(move_type)` — verify classification before acting
  4. Execute only safe/caution moves; caution moves require user confirmation
  5. `plan_scene_handoff` — for scene transitions
- **Energy model:** `get_emotional_arc` → track energy trajectory → suggest next scene
- **Never in performance mode:** Create/delete tracks, edit notes, add/remove devices, arrangement edits

**References:**
- `references/performance-safety.md` — full move classification tables

#### `livepilot-evaluation`

**Triggers:** "evaluate", "was that good", "keep or undo", "A/B compare", "rate my change", "did that help", "before and after"

**SKILL.md body (~2000 words):**
- **The Universal Evaluation Loop** (works across all engines):
  1. `compile_goal_vector(goal, mode)` — what are we trying to achieve
  2. `build_world_model` — current session state + capability snapshot
  3. `get_turn_budget(mode)` — how many moves this turn
  4. Capture before: `get_master_spectrum`, `get_master_rms`, `get_mix_snapshot`
  5. Execute intervention
  6. Capture after: same reads
  7. `evaluate_move(before_snapshot, after_snapshot, goal)` — universal evaluator
  8. Read `keep_change`, `score`, `goal_progress`, `collateral_damage`
  9. If `keep_change=false` → `undo()`, report why
  10. If `keep_change=true` and `score > 0.7` → `memory_learn` candidate
- **Engine-specific evaluators:**
  - `evaluate_mix_move` — for mixing changes
  - `evaluate_composition_move` — for compositional changes
  - `evaluate_with_fabric` — full multi-dimensional evaluation
- **Capability state awareness:**
  - `get_capability_state` → check `overall_mode`
  - `normal` → full measured evaluation
  - `measured_degraded` → stale data, wider confidence intervals
  - `judgment_only` → no analyzer, rely on parameter-level heuristics
  - `read_only` → session disconnected, can only read memory
- **Action ledger:** `get_action_ledger_summary` → review past moves, `get_recent_actions` → context for next move
- **Memory promotion:** `get_promotion_candidates` → techniques worth saving long-term

**References:**
- `references/evaluation-contracts.md` — goal vector format, dimension definitions
- `references/capability-modes.md` — mode descriptions and scope limits
- `references/memory-promotion.md` — promotion criteria and workflow

### Commands (Slash Commands)

**Existing (keep, update to reference new skills):**
- `/beat` — guided beat creation
- `/mix` — mixing assistant (update to invoke mix_engine skill)
- `/memory` — technique library browser
- `/session` — session overview
- `/sounddesign` — sound design workflow (update to invoke sound_design engine skill)

**New:**
- `/arrange` — guided arrangement using composition engine. Interactive: asks about target structure, builds section graph, plans transitions.
- `/perform` — enters performance-safe mode. Shows safe moves, energy state, scene suggestions. Constrains all subsequent actions to safe/caution only.
- `/evaluate` — runs the full evaluation loop on the most recent changes. Shows before/after comparison, score, and keep/undo recommendation.

### Agent Enhancement

**`livepilot-producer`** (existing agent) — update to:
- Reference engine skills by name instead of containing inline loop definitions
- Use `get_capability_state` at start to adapt strategy
- Use `get_turn_budget` to manage intervention count
- Use `get_taste_profile` to personalize decisions

## File Structure

```
livepilot/
├── .Codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── .mcp.json
├── agents/
│   └── livepilot-producer/AGENT.md (updated)
├── commands/
│   ├── beat.md (existing)
│   ├── mix.md (updated — references mix-engine skill)
│   ├── memory.md (existing)
│   ├── session.md (existing)
│   ├── sounddesign.md (updated — references sound-design-engine skill)
│   ├── arrange.md (NEW)
│   ├── perform.md (NEW)
│   └── evaluate.md (NEW)
└── skills/
    ├── livepilot-core/ (slimmed)
    │   ├── SKILL.md (~1500 words)
    │   └── references/ (existing corpus, unchanged)
    ├── livepilot-devices/
    │   └── SKILL.md (~1800 words)
    ├── livepilot-notes/
    │   └── SKILL.md (~1800 words)
    ├── livepilot-mixing/
    │   └── SKILL.md (~1800 words)
    ├── livepilot-arrangement/
    │   └── SKILL.md (~1500 words)
    ├── livepilot-mix-engine/
    │   ├── SKILL.md (~2000 words)
    │   └── references/
    │       ├── mix-critics.md
    │       └── mix-moves.md
    ├── livepilot-sound-design-engine/
    │   ├── SKILL.md (~2000 words)
    │   └── references/
    │       ├── sound-design-critics.md
    │       └── patch-model.md
    ├── livepilot-composition-engine/
    │   ├── SKILL.md (~2000 words)
    │   └── references/
    │       ├── transition-archetypes.md
    │       └── form-patterns.md
    ├── livepilot-performance-engine/
    │   ├── SKILL.md (~1500 words)
    │   └── references/
    │       └── performance-safety.md
    ├── livepilot-evaluation/
    │   ├── SKILL.md (~2000 words)
    │   └── references/
    │       ├── evaluation-contracts.md
    │       ├── capability-modes.md
    │       └── memory-promotion.md
    └── livepilot-release/ (existing, unchanged)
        └── SKILL.md
```

## Migration Plan

1. **Phase 1 — Create new skills** (non-breaking): Add the 9 new skill directories alongside the existing livepilot-core. Test that triggers work correctly.

2. **Phase 2 — Slim livepilot-core**: Move domain-specific procedures out of livepilot-core SKILL.md into domain skills. Keep golden rules, speed tiers, error protocol. Add pointers to new skills.

3. **Phase 3 — Add commands**: Create `/arrange`, `/perform`, `/evaluate` commands.

4. **Phase 4 — Update agent**: Update livepilot-producer AGENT.md to reference engine skills.

5. **Phase 5 — Sync and publish**: Sync plugin to ~/.claude/plugins/livepilot/, bump version, push, publish.

## Success Criteria

- [ ] Each skill triggers on its intended phrases and NOT on unrelated phrases
- [ ] No skill exceeds 2500 words in SKILL.md body
- [ ] Engine skills contain complete orchestration loops (not just tool lists)
- [ ] All reference files exist and are discoverable from SKILL.md
- [ ] `/arrange`, `/perform`, `/evaluate` commands work interactively
- [ ] livepilot-producer agent successfully uses engine skills
- [ ] Total skill count visible in marketplace: 11 skills (up from 2)
- [ ] All 1055 tests still pass (skills are metadata-only, no code changes)

## Version Impact

This is a skill/plugin-only change — no MCP server code modifications. Version bump to 1.9.17 for the skill architecture upgrade.

## Risks

- **Token budget**: 10 skills with ~1800 word average = ~18k words of potential context if all loaded simultaneously. Mitigation: non-overlapping triggers ensure only 1-2 skills load per task.
- **Trigger overlap**: "design a bass sound" could trigger both `livepilot-devices` and `livepilot-sound-design-engine`. Mitigation: device skill handles loading/finding devices, engine skill handles iterative patch refinement. Description wording must disambiguate.
- **Reference sprawl**: New reference files add to plugin size. Mitigation: reference files are derived from existing engine code documentation, not new content.

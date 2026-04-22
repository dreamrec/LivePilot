---
name: livepilot-core
description: Core discipline for LivePilot — agentic production system for Ableton Live 12. 426 tools across 52 domains. This skill should be used whenever working with Ableton Live through MCP tools. Provides golden rules, tool speed tiers, error handling protocol, and pointers to domain and engine skills.
---

# LivePilot Core — Ableton Live 12

Agentic production system for Ableton Live 12. 426 tools across 52 domains, three layers:

- **Device Atlas** — 1305 devices indexed (135 enriched with sonic intelligence, 683 drum kits). Consult `atlas_search` or `atlas_suggest` before loading any device. Never guess a device name.
- **M4L Analyzer** — Real-time audio analysis on the master bus (9-band spectrum sub_low → air, RMS/peak, key detection). Optional — all core tools work without it.
- **Technique Memory** — Persistent storage for production decisions. Consult `memory_recall` before creative tasks to understand user taste.

## Golden Rules

1. **Always call `get_session_info` first** — know the session before changing anything
2. **Verify after every write** — re-read state to confirm changes took effect
3. **Use `undo` liberally** — mention it to users when doing destructive ops
4. **One operation at a time** — verify between steps
5. **Track indices are 0-based** — negative for return tracks (-1=A, -2=B), -1000 for master
6. **NEVER invent device/preset names** — always `search_browser` first, use exact `uri` from results. Exception: `find_and_load_device` for built-in effects only ("Reverb", "Delay", "Compressor", "EQ Eight", "Saturator", "Utility")
7. **Color indices 0-69** — Ableton's fixed palette
8. **Volume 0.0-1.0, pan -1.0 to 1.0** — normalized, not dB
9. **Tempo range 20-999 BPM**
10. **Always name tracks and clips** — organization is part of the process
11. **Respect tool speed tiers** — see below
12. **ALWAYS report tool errors** — never silently swallow errors. Include: tool name, error message, fallback plan
13. **Verify plugin health after loading** — check `health_flags`, `mcp_sound_design_ready`, `plugin_host_status`. If `parameter_count` <= 1 on AU/VST → dead plugin, delete and replace
14. **Use `C hijaz` for Hijaz/Phrygian Dominant keys** — avoids false out-of-key warnings
15. **VERIFY AFTER EVERY WRITE** — mandatory, non-negotiable:
    - After `set_device_parameter` or `batch_set_parameters`: read `value_string` in the response to confirm the actual Hz/dB/% value makes sense
    - After any filter, EQ, or effect parameter change: call `get_track_meters(include_stereo=true)` and verify the target track has non-zero left AND right levels
    - After `apply_automation_recipe`: check that the recipe didn't push the parameter to an extreme that kills audio
    - If a track's stereo output drops to 0: the effect is killing the signal — check `get_device_parameters` for `value_string`, fix, re-verify
    - **Parameter ranges are NOT always 0-1.** Auto Filter Frequency is 20-135. Bit Depth is 1-16. Always read `value_string` to see actual units.
16. **NEVER apply automation recipes without understanding the target parameter's range** — recipes generate 0-1 curves that get auto-scaled for device parameters, but always verify the result
17. **LivePilot_Analyzer must be LAST on master chain** — always place after ALL effects (EQ, Compressor, Utility, etc.) so it measures the final post-processing output, not the raw signal. When loading effects on master, either load them before the analyzer or move the analyzer to end afterward
18. **Remote Script reload workflow** — after any edit to `remote_script/LivePilot/*.py`: run `npx livepilot --install` (NOT `node installer/install.js` — that raw file only module-exports the install function and silently no-ops as a script), then call `reload_handlers` (MCP tool, domain: diagnostics). NEVER instruct the user to toggle the Control Surface in Live Preferences. The tool uses pkgutil + importlib to re-fire `@register` decorators in-place in <1s while the TCP connection stays open. Standard procedure for every handler change — not just releases

## Tool Speed Tiers

### Instant (<1s) — Use freely
All 426 tools plus M4L perception tools.

### Fast (1-5s) — Use freely
`analyze_loudness` · `analyze_mix` · `analyze_sound_design`

### Slow (5-15s) — Tell the user first
`compare_to_reference` · `analyze_spectrum_offline` · `read_audio_metadata`

**Escalation pattern:** Start fast, escalate only with consent:
```
Level 1 (instant):  get_master_spectrum + get_track_meters
Level 2 (fast):     analyze_loudness + analyze_mix
Level 3 (slow):     compare_to_reference + analyze_spectrum_offline
```

## Error Handling Protocol

Report ALL errors to the user immediately. Common failure modes:
- **Dead AU/VST plugin** — `parameter_count` <= 1 → delete, replace with native
- **Sample-dependent plugin** — granular synths produce silence without samples → use self-contained synths (Wavetable, Operator, Drift, Analog)
- **Empty Drum Rack** — bare rack = silence → always load a kit preset
- **M4L bridge timeout** — device may be busy or removed → retry or skip analyzer features
- **Connection timeout** — Ableton unresponsive → check if session is heavy
- **Volume reset on scene fire** — Ableton restores mixer state when firing scenes. Always re-apply `set_track_volume`/`set_track_pan` after `fire_scene` if your mix settings differ from what was stored in the clips
- **M4L Analyzer not connected** — if `get_master_spectrum` errors with "Analyzer not detected", auto-load it: `find_and_load_device(track_index=-1000, device_name="LivePilot_Analyzer")`. If it errors with "UDP bridge not connected", try `reconnect_bridge` first
- **Another client connected** — Remote Script only accepts one TCP client on port 9878. If you see this error, the MCP server is already connected. Use MCP tools instead of raw TCP

## Technique Memory

Three modes:
- **Informed (default):** `memory_recall` before creative tasks, let past decisions influence new ones
- **Fresh:** Skip memory when user wants something new ("ignore my history", "surprise me")
- **Explicit recall:** `memory_recall` → `memory_get` → `memory_replay` when user references a saved technique

## Wonder Mode — Stuck-Rescue Routing

- Use Wonder (`enter_wonder_mode`) for creative ambiguity and session rescue
- Do not fabricate three variants when only one real option exists
- Do not describe a branch as previewable unless it has a valid `compiled_plan`
- Prefer Wonder when `detect_stuckness` confidence > 0.5
- Prefer Wonder when the user's request is emotionally-shaped, not parametric
- Load `livepilot-wonder` skill for full workflow guidance

## Creative Sound Design Knowledge

Before setting device parameters, consult the knowledge corpus for informed creative choices. Read the relevant file BEFORE making changes:

| User says | Read this file |
|-----------|---------------|
| "make it breathe" / "organic" / "alive" / "warm" / "cold" / "anxious" / "nostalgic" | `references/device-knowledge/creative-thinking.md` — emotional-to-technical mapping, physical world modeling |
| "what effect chain for [genre]" / "dub techno" / "trap" / "SOPHIE" / "Arca" / "ambient" | `references/device-knowledge/chains-genre.md` — complete chains per genre |
| "how to use Wavetable/Drift/Analog/Operator/Meld" | `references/device-knowledge/instruments-synths.md` — parameter-level recipes |
| "distortion" / "saturation" / "Roar" / "Saturator" / "Redux" | `references/device-knowledge/effects-distortion.md` — every curve type, creative applications |
| "reverb" / "delay" / "echo" / "space" / "dub" | `references/device-knowledge/effects-space.md` — dub recipes, shimmer chains |
| "spectral" / "Resonators" / "Corpus" / "Vocoder" / "weird" / "experimental" | `references/device-knowledge/effects-spectral.md` — drum-to-melody, cross-synthesis |
| "automate" / "evolve" / "arc" / "movement" / "filter sweep" | `references/device-knowledge/automation-as-music.md` — shapes, macro gestures, density mapping |
| "sound design" / "make it interesting" / "more complex" | `references/sound-design-deep.md` — minimal-techno, SOPHIE, Basic Channel master techniques |

**Rule:** Never set effect parameters from memory alone when the corpus has specific guidance. Read the file first, then apply the technique.

## Domain Skills

For domain-specific workflows, load the appropriate skill:

| Skill | When to use |
|-------|-------------|
| `livepilot-devices` | Loading, browsing, configuring devices and presets |
| `livepilot-notes` | Writing notes, theory, generative algorithms, MIDI I/O |
| `livepilot-mixing` | Volume, pan, sends, routing, automation |
| `livepilot-arrangement` | Song structure, scenes, arrangement view |

## V2 Engine Skills

For agentic evaluation loops, load the appropriate engine skill:

| Skill | When to use |
|-------|-------------|
| `livepilot-mix-engine` | Critic-driven mix analysis and iterative improvement |
| `livepilot-sound-design-engine` | Critic-driven patch analysis and refinement |
| `livepilot-composition-engine` | Section analysis, transitions, motifs, form |
| `livepilot-performance-engine` | Live performance with safety constraints |
| `livepilot-evaluation` | Universal before/after evaluation loop |

## Reference Corpus

Deep production knowledge in `references/`:

| File | Content |
|------|---------|
| `references/overview.md` | All 426 tools with params and ranges |
| `references/device-atlas/` | 280+ device corpus with URIs and presets |
| `references/device-knowledge/` | Per-device parameter + technique knowledge |
| `references/pack-knowledge.md` | All 44 installed packs scored for aesthetic fit (Tier S / A / B / C), with Top / Use-when guidance |
| `references/artist-vocabularies.md` | **v1.17+** — ~25 producers (Villalobos, Hawtin, Basic Channel, Gas, Basinski, Hecker, Aphex, Dilla, Burial, Henke, Daft Punk, …) mapped to `reach_for` LivePilot devices + `avoid` anti-patterns + `key_techniques` cross-refs. The LLM's bridge from "sound like X" to concrete tool calls. |
| `references/genre-vocabularies.md` | **v1.17+** — 15 genres (microhouse, dub_techno, deep_minimal, minimal_techno, ambient, idm, modern_classical, hip_hop, trap, dubstep, house, dnb, garage, experimental, synthwave) with tempo / kick / bass / percussion / harmonic / texture / reach-for / avoid structure |
| `references/sound-design-deep.md` | Masters-level sound design principles (Basic Channel space-as-composition, Hawtin subtraction-over-addition, micro-modulation, space as composition) — explicitly "not a recipe book" |
| `references/sample-manipulation.md` | 29 sample techniques (slice_and_sequence, micro_chop, vocal_chop_rhythm, extreme_stretch, dub_throw, tail_harvest, granular_scatter, …) with producer references (Burial, Dilla, Amon Tobin, Stars of the Lid) |
| `references/midi-recipes.md` | Drum patterns, chord voicings, humanization |
| `references/sound-design.md` | Synth recipes, device chain patterns |
| `references/mixing-patterns.md` | Gain staging, compression, EQ, stereo |
| `references/automation-atlas.md` | 16 curve types, 15 recipes, spectral mapping |
| `references/ableton-workflow-patterns.md` | Session/arrangement workflows |
| `references/memory-guide.md` | Technique memory usage and quality templates |
| `references/m4l-devices.md` | M4L bridge command reference |

**For aesthetic queries ("sound like X", "make me a <genre> track"), read
`artist-vocabularies.md` + `genre-vocabularies.md` BEFORE selecting devices.**
They're structured translation layers between the LLM's training and
LivePilot's atlas — not recipe scripts.

## V2 Orchestration Layer

For complex requests, use the V2 orchestration flow instead of ad-hoc tool calls. There are **two peer flows** — choose based on intent:

### Flow A — Targeted (recipe-first, for specific fixes)
Use when the user has a concrete, specific request ("tighten the low end", "make the drums punchier", "fix the masking").

1. **`route_request`** — classify the request, get recommended engines and workflow mode
2. **`get_session_kernel`** — build the unified turn snapshot
3. **`propose_next_best_move`** — get ranked semantic move suggestions (taste-aware)
4. **`preview_semantic_move`** — see what a move will do before committing
5. **`apply_semantic_move`** — compile and execute the move
6. **Evaluate** — use the appropriate evaluator to check the result

### Flow B — Exploratory (branch-native, for creative search)
Use when the user wants options, variants, or is stuck ("surprise me", "try some things", "I don't know what I want", "make it more like X"). **Flow B is also correct when `route_request` returns `workflow_mode="creative_search"`.**

1. **`get_session_kernel`** — include creative controls when relevant:
   - `freshness=0.8` to bias toward surprise (default 0.5)
   - `creativity_profile="alchemist"` / `"surgeon"` / `"sculptor"` to set producer philosophy
   - `sacred_elements=[...]` if the user named protected parts
   - `synth_hints={"track_indices": [...], "preferred_devices": [...]}` for synth work
2. **`create_experiment`** with *seeds*, not just move_ids:
   - Each seed is a `BranchSeed` dict (or let Wonder emit them for you)
   - Seeds with source `"semantic_move"` compile via the registry at run time
   - Seeds with source `"freeform" / "synthesis" / "composer" / "technique"` must arrive with a pre-compiled plan attached via the parallel `compiled_plans=[...]` list
3. **`run_experiment`** — trials each branch; respects pre-compiled plans
4. **`compare_experiments`** — rank by score
5. **`commit_experiment`** — apply winner; or `discard_experiment` to throw everything away

**Rule of thumb**: if the user asked for a specific fix, Flow A. If they asked "what would you do?" or mentioned feel/vibe without parameters, Flow B.

### Semantic Moves
High-level musical intents that compile to deterministic tool sequences. 5 families:
- **mix** — `tighten_low_end`, `widen_stereo`, `make_punchier`, `darken_without_losing_width`, `reduce_repetition_fatigue`, `make_kick_bass_lock`, `reduce_foreground_competition`
- **arrangement** — `create_buildup_tension`, `smooth_scene_handoff`, `increase_contrast_before_payoff`, `refresh_repeated_section`
- **transition** — `increase_forward_motion`, `open_chorus`, `create_breakdown`, `bridge_sections`
- **sound_design** — `add_warmth`, `add_texture`, `shape_transients`, `add_space`
- **performance** — `recover_energy`, `decompress_tension`, `safe_spotlight`, `emergency_simplify`

Use `list_semantic_moves(domain="mix")` to discover available moves.

### Experiment Branching — Seed-Based (canonical, PR3+)

Experiments support both the legacy `move_ids` path and the new `seeds` path. Prefer `seeds` for anything exploratory:

```
# Legacy / targeted — one semantic_move per branch:
create_experiment(request_text="make it punchier", move_ids=["make_punchier", "widen_stereo"])

# Branch-native / exploratory — mixed sources, pre-compiled plans allowed:
create_experiment(
    request_text="surprise me",
    seeds=[
        {"seed_id": "a", "source": "semantic_move", "move_id": "make_punchier",
         "novelty_label": "safe", "risk_label": "low"},
        {"seed_id": "b", "source": "freeform", "hypothesis": "Audio-rate LFO into filter cutoff",
         "novelty_label": "unexpected", "risk_label": "medium"},
        {"seed_id": "c", "source": "synthesis", "hypothesis": "Wavetable morph across positions",
         "novelty_label": "strong"},
    ],
    compiled_plans=[None, {"steps": [...], "step_count": N}, {"steps": [...], "step_count": M}],
)
```

**Never claim a branch is previewable unless it has a valid `compiled_plan`.** Analytical-only branches (no plan, or seed marked `analytical_only=true`) short-circuit to a neutral evaluation — they're directional suggestions, not executable paths.

### Branch Status Vocabulary
Branches carry a status string that governs lifecycle:
- `pending` — created, not yet run
- `running` — apply pass in progress
- `evaluated` — ran and was scored; may be kept or discarded
- `committed` / `committed_with_errors` — winner was applied permanently
- `discarded` — rolled back or abandoned
- `interesting_but_failed` — (PR7+) failed hard technical gates but surfaced novel ideas; kept for audit, not re-applied
- `failed` — couldn't apply any steps; do not claim success

### Taste-Aware Ranking
The system learns user preferences from kept/undone moves:
- `get_taste_graph()` — current taste model
- `explain_taste_inference()` — human-readable explanation
- `rank_moves_by_taste(move_specs)` — sort options by preference fit
- `propose_next_best_move` automatically applies taste ranking when evidence exists

### Musical Intelligence
Song-level analysis beyond parameters:
- `detect_repetition_fatigue()` — clip overuse, section staleness
- `detect_role_conflicts()` — tracks fighting for the same space
- `infer_section_purposes()` — label sections as setup/tension/payoff/contrast/release
- `score_emotional_arc()` — does the song have a satisfying build→climax→resolve?
- `analyze_phrase_arc()` — capture and evaluate musical phrases
- `compare_phrase_renders()` — compare phrase variants side by side

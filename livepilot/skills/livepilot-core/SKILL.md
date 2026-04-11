---
name: livepilot-core
description: Core discipline for LivePilot — agentic production system for Ableton Live 12. 293 tools across 39 domains. This skill should be used whenever working with Ableton Live through MCP tools. Provides golden rules, tool speed tiers, error handling protocol, and pointers to domain and engine skills.
---

# LivePilot Core — Ableton Live 12

Agentic production system for Ableton Live 12. 293 tools across 39 domains, three layers:

- **Device Atlas** — 280+ instruments, 139 drum kits, 350+ impulse responses. Consult `references/device-atlas/` before loading any device. Never guess a device name.
- **M4L Analyzer** — Real-time audio analysis on the master bus (8-band spectrum, RMS/peak, key detection). Optional — all core tools work without it.
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

## Tool Speed Tiers

### Instant (<1s) — Use freely
All 293 tools plus M4L perception tools.

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
| `references/overview.md` | All 293 tools with params and ranges |
| `references/device-atlas/` | 280+ device corpus with URIs and presets |
| `references/midi-recipes.md` | Drum patterns, chord voicings, humanization |
| `references/sound-design.md` | Synth recipes, device chain patterns |
| `references/mixing-patterns.md` | Gain staging, compression, EQ, stereo |
| `references/automation-atlas.md` | 16 curve types, 15 recipes, spectral mapping |
| `references/ableton-workflow-patterns.md` | Session/arrangement workflows |
| `references/memory-guide.md` | Technique memory usage and quality templates |
| `references/m4l-devices.md` | M4L bridge command reference |

## V2 Orchestration Layer

For complex requests, use the V2 orchestration flow instead of ad-hoc tool calls:

### Standard V2 Flow
1. **`route_request`** — classify the request, get recommended engines and workflow mode
2. **`get_session_kernel`** — build the unified turn snapshot (session, capabilities, taste, memory)
3. **`propose_next_best_move`** — get ranked semantic move suggestions (taste-aware)
4. **`preview_semantic_move`** — see what a move will do before committing
5. **`apply_semantic_move`** — compile and execute the move (mode-dependent)
6. **Evaluate** — use the appropriate evaluator to check the result

### Semantic Moves
High-level musical intents that compile to deterministic tool sequences. 5 families:
- **mix** — `tighten_low_end`, `widen_stereo`, `make_punchier`, `darken_without_losing_width`, `reduce_repetition_fatigue`, `make_kick_bass_lock`, `reduce_foreground_competition`
- **arrangement** — `create_buildup_tension`, `smooth_scene_handoff`, `increase_contrast_before_payoff`, `refresh_repeated_section`
- **transition** — `increase_forward_motion`, `open_chorus`, `create_breakdown`, `bridge_sections`
- **sound_design** — `add_warmth`, `add_texture`, `shape_transients`, `add_space`
- **performance** — `recover_energy`, `decompress_tension`, `safe_spotlight`, `emergency_simplify`

Use `list_semantic_moves(domain="mix")` to discover available moves.

### Experiment Branching
For creative exploration, use experiment branching to compare multiple approaches:
1. `create_experiment(request_text="make it punchier")` — auto-proposes branches
2. `run_experiment(experiment_id)` — trials each branch (apply → capture → undo)
3. `compare_experiments(experiment_id)` — rank branches by score
4. `commit_experiment(experiment_id, branch_id)` — apply winner permanently

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

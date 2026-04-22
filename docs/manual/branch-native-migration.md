# Branch-Native Architecture — v1.13.0 Migration Notes

This release moves LivePilot's planning layer from a recipe-first pipeline
(`match request → pick move → compile move → preview`) to a branch-native
substrate (`understand intent → generate branches → compile branches →
compare`). The execution router, safety checks, and move registry are all
preserved — the change is in how the *planning* above them works.

## What changed

### New shared types

`mcp_server.branches`:

- `BranchSeed` — pre-compilation creative intent. Fields: `seed_id`,
  `source` (semantic_move / freeform / synthesis / composer / technique),
  `move_id`, `hypothesis`, `protected_qualities`, `affected_scope`,
  `distinctness_reason`, `risk_label`, `novelty_label`, `analytical_only`.
- `CompiledBranch` — post-compilation branch pairing a seed with a plan.
  `compiled_plan=None` ⇒ analytical-only.
- Factories: `seed_from_move_id`, `freeform_seed`, `analytical_seed`.

### Producers

Four branch-native producers, all callable from Python:

- **`mcp_server.wonder_mode.engine.generate_branch_seeds`** — assembles
  seeds from semantic moves, technique memory, sacred-element inversion,
  and corpus hints.
- **`mcp_server.synthesis_brain.propose_synth_branches`** — per-device
  adapters (Wavetable, Operator, Analog, Drift, Meld) emit seed +
  pre-compiled plan tuples.
- **`mcp_server.composer.propose_composer_branches`** — N distinct
  compositional hypotheses per prompt (canonical / energy_shift /
  layer_contrast).
- Legacy semantic_move path — `seed_from_move_id(move_id, ...)`.

### New MCP tool parameters (backward compatible)

- `get_session_kernel`: `freshness`, `creativity_profile`,
  `sacred_elements`, `synth_hints` (all optional).
- `create_experiment`: `seeds=[...]` and `compiled_plans=[...]` (optional;
  legacy `move_ids=[...]` path unchanged).
- `run_experiment`: `exploration_rules: bool = False` — when True,
  softens score/measurable failures to `interesting_but_failed`.
- `compare_experiments`: response now includes
  `interesting_but_failed: [...]` for retained exploration branches.

### Conductor

- `classify_request` — unchanged.
- `classify_request_creative(request, kernel)` — new parallel path;
  returns `CreativeSearchPlan` with `branch_sources`, `seed_hints`,
  `target_branch_count`, `freshness`, `creativity_profile`.

### Evaluation

- New `classify_branch_outcome(score, *, protection_violated,
  measurable_count, target_count, goal_progress, exploration_rules)` in
  `mcp_server/evaluation/policy.py` returns a `BranchOutcome` with
  status `keep` / `undo` / `interesting_but_failed`.
- Protection violations always force undo (safety invariant).

### Taste

- `TasteGraph.novelty_bands` dict replaces the single `novelty_band`
  float as the canonical source of truth; `novelty_band` remains as a
  property view over `novelty_bands["improve"]`.
- `TasteGraph.rank_moves(move_specs, goal_mode="improve")` — per-mode
  band threading.
- `TasteGraph.bypass_taste_in_generation: bool` — uniform 0.5 scores
  when set (use during branch generation so taste doesn't prune novelty).

## What did NOT change

- `classify_request()` behavior and every regex pattern. Pre-v1.13 callers
  see identical `ConductorPlan` output.
- `ExperimentBranch` construction API. `ExperimentBranch("b", "n",
  "move_id")` positional still works; `ExperimentBranch(branch_id="b",
  name="n")` (no move_id) now works too.
- `create_experiment(move_ids=[...])` — identical behavior; internally
  delegates via `seed_from_move_id`.
- `enter_wonder_mode` response shape — all pre-v1.13 keys preserved.
  `branch_seeds` is additive.
- The execution router (`mcp_server/runtime/execution_router.py`) —
  untouched. Every branch (semantic_move / freeform / synthesis / composer)
  compiles to the same step format with `$from_step` bindings as before.

## Decision guide

When should a caller use Flow A vs Flow B?

**Flow A (targeted, move-first)** — use when:

- The user named a specific fix ("tighten the low end", "make the drums
  punchier").
- `route_request` returned `workflow_mode="guided_workflow"` or
  `"quick_fix"`.
- The change is measurable via a single dimension (brightness, punch,
  width) and the evaluator can score it.

**Flow B (exploratory, branch-native)** — use when:

- The user asked for options ("surprise me", "what would you do?",
  "try a few things").
- `route_request` returned `workflow_mode="creative_search"`.
- The request is emotionally shaped rather than parametric ("make it
  more haunted", "give me something like Burial's reverb tails").
- `detect_stuckness.confidence > 0.5`.

## For producer authors

If you want to emit branches from a new source:

1. Decide a source label from `BranchSource` or add one.
2. Emit `BranchSeed` objects with a stable `seed_id`, a concrete
   `hypothesis`, and a `distinctness_reason` that explains how this
   seed differs from siblings.
3. If you can pre-compile a plan, return `(seed, plan)` tuples compatible
   with `execute_plan_steps_async`.
4. Otherwise mark `analytical_only=True` on the seed — `run_experiment`
   will short-circuit cleanly with a neutral evaluation.

## Known limitations

### Synthesis-brain adapters are canned, not algorithm-aware

Each native adapter ships with 1–2 hardcoded proposers:

- `WavetableAdapter`: `osc_position_shift` moves Osc 1 Position by a
  fixed `+0.2` (low freshness) or `+0.45` (high freshness). It does
  not inspect which wavetable is loaded or what spectral region the
  current position occupies — a +0.2 shift can land anywhere.
- `OperatorAdapter`: `ratio_shift` always targets `Oscillator B Coarse`,
  regardless of which oscillator acts as a modulator in the current
  algorithm. FM topology isn't decoded yet.
- `AnalogAdapter` / `DriftAdapter` / `MeldAdapter`: single canned
  proposers each, same limitation — parameter paths are fixed.

Future PRs will decode algorithm topology, inspect wavetable content,
and choose which oscillator / operator to modify based on the profile.
Treat current proposers as "known-useful, not yet intelligent."

### Composer branches are scaffolding-only

`propose_composer_branches` emits plans that contain only `set_tempo` +
`create_midi_track` (one per layer) + `create_scene` (one per section).
**No instruments are loaded. No clips are populated. No samples are
resolved.** Committing a composer branch leaves you with a named,
coloured skeleton — the sound design and arrangement work happens
after you pick a winner.

The async `ComposerEngine.compose()` pipeline is still the path for
full layer builds with Splice / browser / filesystem sample resolution.
A future PR will wire that in as a "commit composer branch" hook that
re-runs `compose()` on the winning intent.

### Timbre fingerprint is single-channel

`extract_timbre_fingerprint` always returns `width=0.0` and
`movement=0.0`. The band-energy spectrum input (9-band real-time or
legacy 8-band offline) doesn't carry stereo information, and a single
capture can't show temporal change. Stereo
width and movement land when the timbre extractor ingests multi-capture
sequences and a stereo-aware spectrum source.

### No MCP tools for synthesis_brain or composer producers yet

The Python functions — `analyze_synth_patch`,
`propose_synth_branches`, `extract_timbre_fingerprint`,
`propose_composer_branches` — are callable from other server code
(Wonder's `generate_branch_seeds`, the tools layer, etc.) but not
exposed as standalone `@mcp.tool()` entry points.

This is deliberate: wiring four new tools would trigger the 14-file
tool-count metadata sweep three separate times (PR9 / PR10 / PR11).
The next release cycle batches the wiring + sweep into one PR so the
metadata contract stays tight.

Practical effect: the LLM reaches these producers via
`enter_wonder_mode` (which embeds synthesis seeds in its
`branch_seeds` response) and via `create_experiment(seeds=[...],
compiled_plans=[...])` (which accepts any seed source). Direct
invocation from the LLM is a next-release item.

### No render-based verification loop yet

`extract_timbre_fingerprint` + `diff_fingerprint` give the substrate
for "capture → extract → diff" verification. Nothing in the branch
pipeline calls them yet. A future PR will capture audio before/after
each branch and attach the fingerprint diff to `compare_experiments`
output so exploration mode has evidence beyond the inline heuristic
score.

## Future work

- **PR of the next release cycle** — wire dedicated MCP tools for
  `analyze_synth_patch`, `propose_synth_branches`,
  `extract_timbre_fingerprint`, `propose_composer_branches`, with the
  full 14-file tool-count metadata sweep.
- **Render-based branch verification** — capture audio before/after on
  each branch, run `extract_timbre_fingerprint` on both, present
  `diff_fingerprint` in `compare_experiments`.
- **Sacred-element detection** — currently sourced from `song_brain`;
  could be ML-inferred from hook salience + repetition + role.
- **Technique memory as a first-class branch source** — PR6 already
  emits `source="technique"` seeds from session memory; later PRs
  can promote the persistent technique library (`memory_recall`) to
  the same path.

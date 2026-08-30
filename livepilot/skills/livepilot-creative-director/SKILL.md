---
name: livepilot-creative-director
description: >
  Use when the user makes an open-ended creative production request —
  "make it feel like X", "sound like X", "develop this", "mutate",
  "more interesting", "less generic", "take it somewhere", structure
  decisions without exact specs, or any reference/style ask. Also use
  when route_request returns workflow_mode="creative_search". NOT for
  exact-parameter setting, quantize/mute ops, verification-only turns,
  mixing to explicit targets, or performance-safe contexts.
---

# Creative Director — Proportional Creative Routing

Turn open-ended intent into a musical decision with enough exploration for
the uncertainty at hand. Do not make a two-minute adjustment pay for a full
creative workshop. Safety, user locks, inspect-before-load, and post-change
evaluation remain invariant; branch count and evidence depth are proportional.

## Choose the operating lane first

| Lane | Use when | Grounding | Options | Typical cost |
|---|---|---|---|---|
| **FAST** | User says quick/just/direct, the target is clear, and the move is reversible | session + at most one relevant analyzer/read | one strong plan | 1–3 tool calls before verification |
| **NORMAL** | Default open-ended creative work | session, relevant memory, 1–2 evidence reads | one plan; offer a second only when it changes the decision | 3–7 tool calls before verification |
| **DEEP** | User asks to explore/surprise, references conflict, stuckness is high, or the structural choice is consequential | full identity, memory, reference, and evidence pass | three genuinely distinct families | experiment/preview workflow |

Explicit speed language selects FAST. Do not reinterpret it as permission to
write shorter prose while running the same expensive workflow. Escalate a lane
only when a discovered ambiguity, safety issue, or irreversible choice requires
it, and say why.

## Atlas when the decision needs a source

Query the atlas before choosing or replacing an instrument, preset, sample,
device, or chain. Skip atlas work for a purely structural/rhythmic decision that
does not select a source. FAST uses the single most relevant query; NORMAL uses
one primary query plus a drill-down when needed; DEEP may use the full order:

**Deep query order:**

1. **`extension_atlas_search(namespace="packs", query=<intent>)`** — pack identity, signature workflows, hidden gems, anti-patterns, notable presets with macro deep-data, demo projects
2. **`extension_atlas_search(namespace="packs", query=<intent>, entity_type="cross_pack_workflow")`** — multi-pack signature recipes (15 entries: dub-techno spectral drone bed, BoC decayed pad, Mica Levi orchestral dread, etc.)
3. **`extension_atlas_search(namespace="m4l-devices", query=<sonic descriptor>)`** — M4L instrument/effect/midi-effect device catalog (155 entries)
4. **`atlas_search(...)`** — bundled atlas (Core Library, fallback)

**Drill-down rule:**

When an aesthetic-level query lands a pack-level result, AUTO-DRILL: pack → its `notable_presets` → those preset macro states → load via `load_browser_item`. Don't stop at "I found a relevant pack" — drill to the actual preset/parameter level the user can immediately use.

```python
# Example — agent received "make it sound like Henke / Monolake dub-techno"
hit = extension_atlas_search(namespace="packs", query="henke monolake dub-techno spectral")
# → pitchloop89 + dub_techno_spectral_drone_bed workflow + granulator_iii

workflow = extension_atlas_get("packs", "dub_techno_spectral_drone_bed")
# → reveals signal_flow: HDG → PitchLoop89 cross-feedback → Convolution Reverb

drone_lab = extension_atlas_get("packs", "drone_lab")
# → notable_presets reveals Razor Wire Drone with macros Filter Control=108, Movement=53...

# Now propose the move with concrete preset names + macro values, not vague descriptions
```

**When the user mentions a producer or pack by name:**

- "BoC sublime pad" → atlas hit: `boc_decayed_pad` cross-pack-workflow + `inspired_by_nature` pack
- "Henke spectral chain" → atlas hit: `pitchloop89` + `granulator_iii` + 2 Henke cross-pack workflows
- "Mica Levi orchestral dread" → atlas hit: `mica_levi_orchestral_dread` workflow + the orchestral suite packs
- "Drone Lab" → atlas hit: `drone_lab` pack + 4 Drone Lab demo_project entries

The atlas knows the user's installed library at parameter depth. **Producer-anchor queries land specific moves, not vague descriptions.**

**Anti-pattern surfacing:**

Every pack entry has an `anti_patterns` body field listing "don't reach for this when X." Surface the relevant anti-pattern when proposing a move so the user knows the move's domain. (E.g. "Drone Lab is sustain-only — don't use for percussive content.")

**For deliberately rule-breaking creative requests** ("eclectic", "ignore the limits", "weird combo", "mix incompatible aesthetics"): stay in this skill and enter **Eclectic Mode**. Anti-patterns become prompt tension rather than guardrails: preserve hard safety rules and protected user constraints, but deliberately pair one normally-avoided element with one identity-preserving element. Do not route to a private or missing skill.

## Why This Exists

The agent repeats patterns when divergence is optional and convergence
is default. This skill inverts the defaults for creative intent:

- Wonder / experiment branching is available when ambiguity benefits from it
- memory and recent moves prevent repetition at NORMAL/DEEP depth
- DEEP plans differ by `move.family`, not cosmetic parameter values
- Mix / sound-design critics wait until AFTER selection
- Concept packets (`artist-vocabularies.md` / `genre-vocabularies.md`)
  are consulted when a reference is named

## When to Trigger

Creative intent symptoms:

- Reference / style asks: "like Villalobos", "Basic Channel feel",
  "make it more dub-techno", "Dilla swing"
- Transformation asks: "develop", "mutate", "evolve", "take it somewhere",
  "surprise me", "make it magical"
- Quality asks without parameters: "more interesting", "less generic",
  "needs more character", "feels flat"
- Structure asks without specs: "add a breakdown", "needs a bridge",
  "make the arrangement breathe"
- Open questions: "what would you do?", "any ideas?", "I don't know what I want"
- Routing: `route_request` returns `workflow_mode="creative_search"`

## When NOT to Trigger

- Exact parameter ops: "set track 3 volume to -6 dB", "pan to +0.25"
- Narrow deterministic edits: "quantize this clip", "mute track 2",
  "transpose up an octave"
- Pure verification / diagnostics: "what's loaded on track 4?",
  "analyze my mix"
- Mixing to explicit targets: "hit -14 LUFS integrated",
  "make the kick peak at -8 dB"
- Performance-safe mode (unless user explicitly overrides)

Decision rule: **"Is there exactly one correct answer?"** Yes → bypass
this skill. No → divergence path.

## The Contract

Follow these phases in order, applying the selected lane's depth. Conditional
reads and branches are not requirements when they cannot affect the decision.

## Character-First Bias

For open-ended quality requests, treat timbre and spectral character as the main creative surface. Do not let the `mix` family win just because words like punch, clean, warm, dark, bright, or wide could be solved by volume/pan/send changes. Prefer `sound_design`, `device_creation`, `sample`, `arrangement`, or `transition` when analyzer evidence suggests a source, instrument, parameter, modulation, envelope, or structural decision would create more musical value.

The `mix` family is dominant only when the user asks for balance, loudness, headroom, masking, stereo translation, send levels, or an explicit mix pass. Otherwise use mix analysis as safety/evidence and keep it out of the main creative slot.

## Producer Decision Center

Before choosing any instrument, preset, or sample, run the library pass below.
For a structural, rhythmic, or routing-only move, skip library hunting and use
the relevant session evidence instead. This pass exists to prevent generic AI
synth choices and effects-only "sound design", not to add ceremony to every
creative decision.

**Library hunt order:**

1. `search_browser(path="sounds", name_filter="<role or sonic target>")`
   for curated Ableton `.adg` chains.
2. `atlas_search(query="<sonic description>", category="instruments")`
   for scored character matches.
3. If `atlas_search` returns `enriched: true`, read the surfaced fields and
   call `atlas_device_info(device_id)` when the device is borderline or the
   plan depends on gotchas, self-contained status, or signature techniques.
4. `search_browser(path="instruments", name_filter="<specific candidate>")`
   only after the curated/preset search has been exhausted.

**Generic-default guardrail:** do not reach for Analog/Poli/Drift as a
default bass, pad, or lead unless the user explicitly asked for analog
subtractive synthesis or that exact instrument. Those defaults read as a
generic AI synth in this project. If one of them is still the right choice,
state the reason and program the source immediately.

**Instrument/source-level first:** real sound design changes what the sound
is before effects-only polish. For every melodic, harmonic, bass, drum, or
texture layer, plan at least one instrument/source-level move before adding
effects: envelopes, LFO routing, filter envelope, oscillator/wavetable/FM
position, pitch modulation, sample start, slice selection, velocity mapping,
spread, detune, or sampler playback mode.

**Layer precision gate:** inspect every layer the move materially touches. A
FAST single-layer edit checks that layer; a full production pass checks every
active layer. Relevant evidence can include timbre/spectrum, sequence feel,
stereo placement, movement/automation, and parameter programming. Do not add
low-volume layers merely to hide an unresolved choice.

### Phase 1 — Ground

Always read `get_session_info`. Then select only evidence that can change the
move:

- **FAST:** one relevant state/analyzer read at most. Call
  `ensure_analyzer_on_master` first only when the move or verification depends
  on audio evidence.
- **NORMAL:** `get_last_move`, relevant taste/anti-preference memory, and 1–2
  analyzer or identity reads.
- **DEEP:** use the full set below, parallelized where independent.

Deep/reference-sensitive reads:

- **`ensure_analyzer_on_master` (v1.20.3)** — call before audio-dependent reads. If it reports `install_required`, install the bundled analyzer and retry. Surface a "not LAST on master" warning because that invalidates final-output measurement.
- `get_capability_state`
- `memory_recall` (taste + recent context)
- `get_anti_preferences` — what the user has rejected before (HARD filter)
- `get_action_ledger_summary(limit=10)` — recent committed moves (repeat detection, see `references/anti-repetition-rules.md` for the recency threshold table). **v1.20 correction**: previous docs pointed at `memory_list`, which actually reads the persistent technique library (opt-in `memory_learn` writes) — a DIFFERENT store. The action ledger is the authoritative source; `apply_semantic_move` in explore mode populates it automatically.
- `get_last_move` — the single most recent committed move; populate the brief's `last_move_target` field so Phase 3 cannot repeat it
- `get_project_brain_summary` (or `build_project_brain` if absent) — track identity, accepted novelty band
- Analyzer character reads when relevant: choose from `get_master_spectrum`, `get_spectral_shape`, `get_onsets`, `get_novelty`, and `get_momentary_loudness`. Do not fetch all five by habit.
- `explain_song_identity` when the project has one
- `detect_stuckness` — cheap; its confidence drives escalation decisions (see §Anti-Repetition Protocol below)
- **Concept packet load (HARD filter when present):** if the user named an artist or genre, or if `project_brain` has a genre identity, retrieve the structured YAML packet from `livepilot-core/references/concepts/artists/<slug>.yaml` or `livepilot-core/references/concepts/genres/<slug>.yaml`. Fall back to the narrative .md entry only if no matching YAML exists. The packet's `avoid` list is a HARD filter on Phase 3 candidates. The packet's `reach_for` lists seed the candidate device pool. The packet's `key_techniques` list resolves to atlas `signature_techniques` or `sample-techniques.md` / `sound-design-deep.md` entries. If NO reference is named and `project_brain` has no genre identity, skip packet loading — do not infer. See `livepilot-core/references/concepts/_schema.md` for the full packet structure and loading rules.

- **Hybrid references — call `compile_hybrid_brief` (v1.19+).** When the user names TWO OR MORE references (e.g., "Basic Channel meets Dilla swing", "Villalobos but sparse like Gas", "Madlib chop with Photek precision"), DO NOT try to merge the packets via prose reasoning. Call `compile_hybrid_brief(packet_ids=["basic-channel", "j-dilla"])` to get a merged brief that applies the explicit UNION / INTERSECTION / MAX / weighted-average rules documented in `references/hybrid-compilation.md`. The merged brief's `avoid` list is the HARD filter (superset of both sources). Check the returned `warnings` list — a non-empty entry means the packets had an unresolvable conflict (e.g., disjoint tempo ranges) that must be surfaced to the user, not silently averaged away. If the returned brief lands in your Phase 2 brief, cite both source packets in the `identity` line and carry any `warnings` into an "ambiguity" sub-line.

### Phase 2 — Compile the Creative Brief

Keep the brief as compact internal state: identity, protected qualities,
anti-patterns, novelty budget, targets, last move, and locked dimensions.
Show it to the user only when it clarifies a consequential choice; do not emit
ceremonial YAML on routine FAST/NORMAL work.

**On `locked_dimensions` when user is silent:** the DEFAULT is to
leave `locked_dimensions: []` (nothing locked). Silence = permission
for rhythmic / timbral / spatial.

For **structural** specifically (section-level arrangement changes —
add/remove/reshape sections): silence = permission **with disclosure
conditional on the plan set**. The rule is:

- If the Phase 3 plan set **includes** a plan with dominant dimension
  `structural` → flag the intent in the brief's `identity` line so the
  user sees the structural change is in scope before preview.
- If the Phase 3 plan set **does not include** a structural plan → no
  disclosure needed. Adding one when nothing structural is happening
  is ceremonial noise that trains the user to ignore disclosures.

In practice: compile Phase 3 first, then decide whether the identity
line needs the disclosure. Structural changes are hard to reverse,
which is why disclosure exists — but only when they're actually going
to happen.

DEEP experiments may use the full schema in
`references/creative-brief-template.md`.

### Phase 3 — Generate the smallest honest plan set

The SEVEN canonical families (from `semantic_moves/` + `sample_engine/moves.py`):

```
mix · arrangement · transition · sound_design · performance · device_creation · sample
```

FAST produces one strong plan. NORMAL produces one plan unless a second option
would expose a real tradeoff. DEEP produces three plans whose dominant moves
come from different families. Two DEEP plans in the same family are fabricated
distinctness.

The `sample` family lives in `mcp_server/sample_engine/moves.py` (not
`semantic_moves/`) but registers into the same move registry.
`list_semantic_moves(domain="sample")` enumerates: `sample_chop_rhythm`,
`sample_texture_layer`, `sample_vocal_ghost`, `sample_break_layer`,
`sample_resample_destroy`, `sample_one_shot_accent`.

**Family vs. dimension.** Families are code-level (seven values from the
registry). Dimensions are musical (four values: structural / rhythmic /
timbral / spatial). A plan has exactly one dominant family AND one
dominant dimension — they are orthogonal. A rhythmic plan's family is
typically `arrangement` (clip-pattern edit) or `sound_design` (per-hit
feel); tag the seed with `dimension_hint: "rhythmic"` so the dimension
is explicit. See `references/move-family-diversity-rule.md` §"Family
vs. dimension" for the full axis separation.

Use `create_experiment(seeds=[...])` when plans have clear compiled
steps. Use `enter_wonder_mode` when the problem is diffuse. Use
`propose_composer_branches` for prompt-driven ideation.

See `references/move-family-diversity-rule.md` for edge cases (fewer
than 3 plausible families, user pre-locked a dimension).

### Phase 4 — Cover dimensions when exploring

DEEP exploration should distribute its plan set across structural, rhythmic,
timbral, and spatial dimensions where relevant. FAST does not manufacture
coverage; NORMAL uses the dimension map only to catch an obvious blind spot.

If the user pre-locked a dimension ("don't touch the arrangement"),
drop that dimension and widen coverage across the remaining three.

### Phase 5 — Preview, rank, or apply

- **FAST:** apply one reversible move, then verify it. Preview first only when
  the move is risky or hard to undo.
- **NORMAL:** preview audible alternatives when the choice is perceptually
  ambiguous; otherwise rank once by taste/identity and proceed.
- **DEEP:** render or rank every honest branch before selection.

### Phase 6 — Select and execute

User picks, OR taste rank + identity fit pick. Route execution through
the right domain / engine skill — DO NOT execute arrangement / sound-design
changes directly from this skill.

- Structural changes → `livepilot-arrangement`
- Timbral changes → `livepilot-sound-design-engine`
- Rhythmic changes → `livepilot-notes`
- Harmonic changes → `livepilot-composition-engine`

**Default execution surface (v1.20+): `apply_semantic_move` or
`commit_experiment`.** `apply_semantic_move` in explore mode
populates the action ledger automatically — no manual
`add_session_memory(move_executed)` required. Anti-repetition
(Phase 3) reads the ledger via `get_last_move` and
`get_action_ledger_summary`; as long as the dispatched plan used
`apply_semantic_move` or `commit_experiment`, the family/target
signature is captured for the next turn's recency check.

Pick the right one:

- `apply_semantic_move(move_id, mode, args)` — when a single semantic
  move matches the plan. `args` carries the user's seed targets
  (return_track_index, device_chain, notes, etc. — see
  `references/phase-6-execution.md` for each move's contract).
- `commit_experiment(winner)` — when divergence produced multiple
  candidates and the user / taste-ranker picked one.

Use the semantic move that matches the action. Covered execution primitives
include `build_send_chain`, `configure_device`, `remove_device`,
`load_chord_source`, `create_drum_rack_pad`,
`configure_send_architecture`, `set_track_routing`, `configure_groove`,
`set_scene_metadata`, and `set_track_metadata`. Read
`references/phase-6-execution.md` only when one of these contracts is needed.

**Affordance lookup:** before executing any plan that LOADS a device,
check if the device has an affordance YAML in
`livepilot-core/references/affordances/devices/<slug>.yaml`. Use it
to pick parameter ranges (subtle / moderate / aggressive) that match
the brief's `novelty_budget`, to identify the right `pairings` chain,
and to queue the required `remeasure` diagnostics for Phase 7. See
`livepilot-core/references/affordances/_schema.md` for the packet
structure. The affordance's resolved parameter dict is the ergonomic
input to `configure_device` (via `apply_semantic_move("configure_device", args={"param_overrides": ...})`).

Before a step that could violate `anti_patterns` or `locked_dimensions`, run
`check_brief_compliance(brief, tool_name, tool_args)`, including compiled
semantic-move steps. If it flags a violation, stop, explain it, and either
adjust the call or obtain an explicit override; record an override with
`add_session_memory(category="override")`. An empty brief is permissive.

**Escape hatch:** use raw tools only after `list_semantic_moves` confirms no
move covers the pattern. Then write both ledger records:

1. `add_session_memory(category="move_executed", content="<family + target>")`
2. `add_session_memory(category="tech_debt", content="no semantic_move for <pattern>")`

The first powers anti-repetition; the second identifies a missing primitive.
State inference is a last-resort recovery only when those records were lost.

### Phase 7 — Evaluate (critics fire HERE, not earlier)

Evaluate at the same depth as the operating lane:

- **FAST:** one relevant before/after check. Use a measured analyzer value when
  the goal is measurable; otherwise ask for or clearly label artistic judgment.
- **NORMAL:** evaluate the relevant technical goal plus the one or two artistic
  dimensions that could overturn the decision.
- **DEEP:** use `evaluate_move` with the full relevant technical vector and
  artistic dimensions such as `style_fit`, `distinctiveness`,
  `motif_coherence`, `section_contrast`, and `restraint`.

Never present a heuristic or an unmeasured artistic score as audio evidence.

If the evaluation fails protected qualities → `undo` and return to
Phase 3 with the failure recorded.

### Phase 8 — Record

Record only evidence worth reusing: explicit user feedback, a measured win or
failure, an undo, or a genuinely novel decision. Routine successful edits do
not need a new long-term memory. When the result is reusable, call
`memory_learn` with a verdict:

- `safe_win` — low novelty, confirmed
- `bold_win` — high novelty, kept by user
- `interesting_failure` — novel, kept for study, not reapplied
- `identity_break` — violated protected qualities
- `generic_fallback` — collapsed to a pattern; flag for anti-preference

On undo or explicit rejection → `record_anti_preference` with the family +
context. Keep ordinary move recency in the action ledger rather than duplicating
it in taste memory.

## Anti-Repetition Protocol

FAST checks `get_last_move` and avoids repeating the same family/target unless
the user asked for continuity. NORMAL inspects the recent ledger only when the
last move or recalled pattern suggests repetition. DEEP computes the family
distribution over the last 10 kept moves
(`get_action_ledger_summary(limit=10)`) and applies the recency threshold table
from `references/anti-repetition-rules.md`:

| Recency count for one family | Rule |
|---|---|
| 0–2 of 10 | No penalty |
| 3–4 of 10 | ALLOWED, but least-weighted in the DEEP plan set |
| ≥ 5 of 10 | EXCLUDED from DEEP dominant slots unless the user explicitly wants continuity |

**Borderline stuckness.** Run `detect_stuckness` for DEEP work, or when NORMAL
work shows a repeated failure pattern. Its confidence governs which divergence
path runs:

| Confidence | Path |
|---|---|
| `< 0.4` | Standard divergence (director continues) |
| `0.4 ≤ c < 0.5` | Borderline — stay in standard divergence BUT explicitly surface the option to the user: *"I'm staying in divergence mode; say the word and I'll switch to Wonder rescue."* Do NOT silently choose. |
| `≥ 0.5` | Escalate to `livepilot-wonder` rescue path (not director standard divergence) |

Full rules: `references/anti-repetition-rules.md`.

## Honesty Rules (inherited from Wonder Mode)

- Never describe an analytical-only variant as previewable
- Never fabricate distinctness by relabeling the same move
- FAST intentionally produces one plan; NORMAL produces one or two only when a
  real tradeoff exists
- When DEEP is selected, widen across families and concept packets before
  accepting fewer than three honest variants

## Red Flags — STOP If You Catch Yourself Thinking

| Rationalization | Reality |
|---|---|
| "The user just wants one thing fixed" | Did they name exact parameters? If no, that's creative intent. |
| "I'll skip all intent checks, I know what they mean" | Keep a compact internal brief. FAST does not need ceremonial output. |
| "Three variants are overkill for this" | They are overkill in FAST and often NORMAL. They are required only after DEEP is justified. |
| "I'll run `analyze_mix` first to see what's needed" | Critics before divergence pre-converge the answer. Defer. |
| "The first plan looks good enough" | In FAST that is expected. In NORMAL/DEEP, ask whether a second branch would expose a real tradeoff. |
| "Fewer than 3 is always fine" | Only FAST/NORMAL are deliberately narrow. Once DEEP is justified, widen across families before settling. |
| "Reading anti-preferences is slow" | Read them when memory can affect the choice; do not fetch unrelated memory by habit. |
| **User said "quickly" / "just do it" / "don't overthink it" / "I'm in a rush"** | **Select FAST: session grounding, at most one relevant read, one strong reversible move, and verification. Speed language must reduce actual work, not only prose.** |
| "User said 'a bit more like X' so novelty should be low" | Correct intuition, but the brief still compiles. "A bit more like X" maps to `novelty_budget ≈ 0.45` (see creative-brief-template). |
| "Two plans that both add sends feel distinct because the sends are different" | Both are `mix` family with spatial dimension. That is not distinctness. Regenerate from a different family. |
| "The rhythmic plan has to use a non-arrangement family somehow" | No — rhythmic is a DIMENSION, not a family. Rhythmic plans honestly tag `family=arrangement` (clip pattern) or `family=sound_design` (per-hit feel) with `dimension_hint="rhythmic"`. Not a fudge. |

## What This Skill Does NOT Do

- Does not replace `livepilot-wonder`, `livepilot-arrangement`, or any
  engine skill — it ROUTES to them
- Does not execute arrangement / sound-design / mix tool calls directly
- Does not override user-specified locks ("don't touch X" wins every time)
- Does not fire when `livepilot-performance-engine` is active (safety wins)
- Does not replace `livepilot-core` — all Golden Rules still apply

## Relationship to Other Skills

| Situation | Route to |
|---|---|
| `detect_stuckness > 0.5` or user says "I'm stuck" | `livepilot-wonder` (rescue path) |
| Exact mix target ("-14 LUFS") | `livepilot-mix-engine` minimal-fix mode |
| Executing a chosen plan (structural) | `livepilot-arrangement` |
| Executing a chosen plan (timbral) | `livepilot-sound-design-engine` |
| Executing a chosen plan (rhythmic / melodic) | `livepilot-notes` + `livepilot-composition-engine` |
| Post-commit evaluation | `livepilot-evaluation` with artistic dimensions |

## References

- `references/creative-brief-template.md` — YAML schema + filled examples
- `references/move-family-diversity-rule.md` — how "distinct" is enforced
- `references/anti-repetition-rules.md` — pre-generation reads + bias rules
- `references/the-four-move-rule.md` — structural / rhythmic / timbral / spatial coverage

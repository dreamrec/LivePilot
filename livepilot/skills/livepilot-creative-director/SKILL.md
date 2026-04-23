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

# Creative Director — Divergence-First Routing

Routes creative intent through MANDATORY divergence before any commit.
Three plans with distinct `move.family` are the minimum output. Critics
defer until after selection. No new tools — this skill enforces a
discipline on top of existing `experiment`, `wonder_mode`, `preview_studio`,
`semantic_moves`, `evaluation`, and `memory` machinery.

## Why This Exists

The agent repeats patterns when divergence is optional and convergence
is default. This skill inverts the defaults for creative intent:

- Wonder / experiment branching becomes REQUIRED, not rescue-only
- `get_anti_preferences` and recent `memory_list` are READ before generating
- Three plans must differ by `move.family` (not by parameter values)
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

When triggered, these phases are REQUIRED in order. Skip none.

### Phase 1 — Ground

Read in parallel (all are fast). All of these are REQUIRED, not
advisory — skipping them is how pattern-repetition survives:

- `get_session_info` · `get_capability_state`
- `memory_recall` (taste + recent context)
- `get_anti_preferences` — what the user has rejected before (HARD filter)
- `memory_list(limit=10)` — what was tried recently (repeat detection, see `references/anti-repetition-rules.md` for the recency threshold table)
- `get_last_move` — the single most recent committed move; populate the brief's `last_move_target` field so Phase 3 cannot repeat it
- `get_project_brain_summary` (or `build_project_brain` if absent) — track identity, accepted novelty band
- `explain_song_identity` when the project has one
- `detect_stuckness` — cheap; its confidence drives escalation decisions (see §Anti-Repetition Protocol below)
- **Concept packet load (HARD filter when present):** if the user named an artist or genre, or if `project_brain` has a genre identity, retrieve the structured YAML packet from `livepilot-core/references/concepts/artists/<slug>.yaml` or `livepilot-core/references/concepts/genres/<slug>.yaml`. Fall back to the narrative .md entry only if no matching YAML exists. The packet's `avoid` list is a HARD filter on Phase 3 candidates. The packet's `reach_for` lists seed the candidate device pool. The packet's `key_techniques` list resolves to atlas `signature_techniques` or `sample-techniques.md` / `sound-design-deep.md` entries. If NO reference is named and `project_brain` has no genre identity, skip packet loading — do not infer. See `livepilot-core/references/concepts/_schema.md` for the full packet structure and loading rules.

### Phase 2 — Compile the Creative Brief

**Timing:** after Phase 1 parallel reads complete, before any Phase 3
tool call. The brief appears ONCE per creative turn, inline in the
assistant message, at the top of the response body.

Emit an inline YAML block (not a tool call) with: identity, reference
anchors, protected qualities, anti-patterns, novelty budget, target
dimensions, `last_move_target` (from Phase 1 `get_last_move`),
locked dimensions, recommended skill chain.

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

See `references/creative-brief-template.md` for the schema and filled
examples.

### Phase 3 — Generate three plans with distinct `move.family`

The SEVEN canonical families (from `semantic_moves/` + `sample_engine/moves.py`):

```
mix · arrangement · transition · sound_design · performance · device_creation · sample
```

Each plan's dominant move MUST come from a different family. Two plans
in the same family is fabricated distinctness — see Honesty Rule below.

The `sample` family lives in `mcp_server/sample_engine/moves.py` (not
`semantic_moves/`) but registers into the same move registry.
`list_semantic_moves(domain="sample")` enumerates: `sample_chop_rhythm`,
`sample_texture_layer`, `sample_vocal_ghost`, `sample_break_layer`,
`sample_resample_destroy`, `sample_one_shot_accent`.

**Family vs. dimension.** Families are code-level (six values from the
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

### Phase 4 — Cover the four dimensions

A creative pass should distribute the three plans across structural +
rhythmic + timbral + spatial. See `references/the-four-move-rule.md`
for the family-to-dimension map.

If the user pre-locked a dimension ("don't touch the arrangement"),
drop that dimension and widen coverage across the remaining three.

### Phase 5 — Preview or rank

Audible → `create_preview_set` + `render_preview_variant` for each plan,
then `compare_preview_variants`.

Non-audible or fast → `rank_by_taste_and_identity`.

Never silently skip preview / ranking. Either run it or document why.

### Phase 6 — Select and execute

User picks, OR taste rank + identity fit pick. Route execution through
the right domain / engine skill — DO NOT execute arrangement / sound-design
changes directly from this skill.

- Structural changes → `livepilot-arrangement`
- Timbral changes → `livepilot-sound-design-engine`
- Rhythmic changes → `livepilot-notes`
- Harmonic changes → `livepilot-composition-engine`

**Affordance lookup:** before executing any plan that LOADS a device,
check if the device has an affordance YAML in
`livepilot-core/references/affordances/devices/<slug>.yaml`. Use it
to pick parameter ranges (subtle / moderate / aggressive) that match
the brief's `novelty_budget`, to identify the right `pairings` chain,
and to queue the required `remeasure` diagnostics for Phase 7. See
`livepilot-core/references/affordances/_schema.md` for the packet
structure.

**Brief compliance check (v1.18.3):** before any tool call that could
plausibly violate the brief's `anti_patterns` or `locked_dimensions`,
call `check_brief_compliance(brief, tool_name, tool_args)`. The tool
returns `{"ok": bool, "violations": [...]}` — best-effort keyword
heuristic, NOT semantic understanding. Use it especially for:

- `set_device_parameter` calls on EQ/saturation/filter parameters
  (catches "bright top-end", "aggressive transient" style anti_patterns)
- `load_browser_item` for new devices (check against `avoid` device
  lists in concept packets)
- `create_scene` / `set_scene_*` / `refresh_repeated_section`
  (catches `locked_dimensions: [structural]` violations)
- `add_notes` / `modify_notes` / `quantize_clip` when
  `locked_dimensions: [rhythmic]` is set

When a violation fires:
1. **Do NOT auto-proceed.** Surface the violation to the user with
   the reason + suggestion from the check response.
2. Offer three paths: (a) adjust the call to avoid the pattern,
   (b) user explicitly overrides this anti_pattern for this turn,
   (c) pick a different tool/plan.
3. Record the user's choice via `add_session_memory(category="override")`
   so future anti-preference writes know this was an explicit decision.

The check is STATELESS — you pass the brief each time. Empty brief
(no anti_patterns, no locked_dimensions) always returns ok=True.
Full session-state active-brief storage is v1.19 scope.

**Ledger-marker discipline (v1.18.1):** the action ledger (`get_last_move`,
`memory_list`) is populated by `apply_semantic_move` and `commit_experiment`.
When Phase 6 executes via raw tool calls (`set_device_parameter`,
`load_browser_item`, `set_track_send`, etc.) — for example when affordance
parameters are being applied directly — NOTHING gets written to the ledger
automatically. This blinds subsequent anti-repetition detection on the
next creative turn.

**Mandatory ledger marker for raw-tool execution:** after a raw-tool
execution batch, call `add_session_memory` with a one-line summary
covering the move's family + target + brief identity:

```
add_session_memory(
    category="move_executed",
    content="device_creation:return-A dub-chain (Echo + Auto Filter + "
            "Convolution Reverb) — brief: Basic Channel dub architecture",
    engine="creative_director",
)
```

Keep the `content` field terse but include: family (from move-family-
diversity-rule.md), target (track / return / master), and the brief's
identity sentence. This is the minimum-effective ledger marker until
v1.19 routes all director execution through semantic_move commits.

Prefer `apply_semantic_move` or `commit_experiment` when a semantic-move
exists that matches the plan — they populate the ledger for free.
`add_session_memory` is the fallback when no semantic-move matches
(e.g., device-creation sequences, custom preset loads, signal-chain
architecture).

### Phase 7 — Evaluate (critics fire HERE, not earlier)

`evaluate_move` with artistic dimensions (`style_fit`, `distinctiveness`,
`motif_coherence`, `section_contrast`, `restraint`) in addition to the
technical goal vector.

If the evaluation fails protected qualities → `undo` and return to
Phase 3 with the failure recorded.

### Phase 8 — Record

`memory_learn` with a verdict:

- `safe_win` — low novelty, confirmed
- `bold_win` — high novelty, kept by user
- `interesting_failure` — novel, kept for study, not reapplied
- `identity_break` — violated protected qualities
- `generic_fallback` — collapsed to a pattern; flag for anti-preference

On undo or explicit rejection → `record_anti_preference` with the
family + context.

## Anti-Repetition Protocol

Before Phase 3 generation, compute the family distribution over the
last 10 kept moves (`memory_list(limit=10)`). Apply the recency
threshold table from `references/anti-repetition-rules.md`:

| Recency count for one family | Rule |
|---|---|
| 0–2 of 10 | No penalty |
| 3–4 of 10 | ALLOWED as a plan's dominant family, but only as the **least-weighted** of the three |
| ≥ 5 of 10 | EXCLUDED from all three dominant slots (fully hard-biased away) |

**Borderline stuckness.** After computing the recency penalty, run
`detect_stuckness`. Its confidence governs which divergence path runs:

| Confidence | Path |
|---|---|
| `< 0.4` | Standard divergence (director continues) |
| `0.4 ≤ c < 0.5` | Borderline — stay in standard divergence BUT explicitly surface the option to the user: *"I'm staying in divergence mode; say the word and I'll switch to Wonder rescue."* Do NOT silently choose. |
| `≥ 0.5` | Escalate to `livepilot-wonder` rescue path (not director standard divergence) |

Full rules: `references/anti-repetition-rules.md`.

## Honesty Rules (inherited from Wonder Mode)

- Never describe an analytical-only variant as previewable
- Never fabricate distinctness by relabeling the same move
- Fewer than 3 variants is ACCEPTABLE only when, after honestly widening
  across families AND checking concept packets, fewer real options exist
- On first-pass creative-director calls, actively widen BEFORE accepting
  a smaller variant set (stuck-rescue is a separate context)

## Red Flags — STOP If You Catch Yourself Thinking

| Rationalization | Reality |
|---|---|
| "The user just wants one thing fixed" | Did they name exact parameters? If no, that's creative intent. |
| "I'll skip the brief, I know what they mean" | The brief pins protected qualities. Skipping them = pattern repetition. |
| "Three variants are overkill for this" | That's the collapse-to-mode instinct. Generate them anyway, then honestly cull. |
| "I'll run `analyze_mix` first to see what's needed" | Critics before divergence pre-converge the answer. Defer. |
| "The first plan looks good enough" | That's the most-likely completion, by definition. Generate two more. |
| "Fewer than 3 is fine per Wonder's honesty rule" | True for stuck-rescue. On first-pass, widen FIRST across families, fall back only after. |
| "Reading anti-preferences is slow" | It's an instant tool. The alternative is generating a rejected pattern. |
| **User said "quickly" / "just do it" / "don't overthink it" / "I'm in a rush"** | **User pressure framing. The brief is STILL mandatory. Compress PROSE (fewer words around each plan), not STRUCTURE (never skip the brief, Phase 1 reads, 3-family diversity, or preview). Phase 1 reads are instant — "quickly" buys nothing by skipping them.** |
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

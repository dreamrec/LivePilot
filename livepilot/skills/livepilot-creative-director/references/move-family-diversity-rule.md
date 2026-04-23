# Move-Family Diversity Rule

The single mechanical rule that prevents pattern-repetition: when the
director generates three plans, their DOMINANT moves must come from
three DIFFERENT `move.family` values.

This is not taste. This is a structural constraint enforced before
preview or ranking.

## Family vs. dimension — two different axes

The director reasons on two orthogonal axes:

- **`move.family`** — WHERE in the semantic_moves registry the dominant
  move lives. Six stable values, code-enforced. This is what the
  diversity rule operates on.
- **`dimension`** — WHAT kind of musical consequence the plan has.
  Four values: structural / rhythmic / timbral / spatial. This is what
  the four-move rule operates on.

A rhythmic plan has a rhythmic DIMENSION but its FAMILY is typically
`arrangement` (clip-level pattern change) or `sound_design` (per-hit
timbre variation that changes feel). That is **not** a fudge — it is
the correct taxonomy, because rhythmic work in Ableton happens via
note editing + grooves, which are tooled through those families. Tag
such a seed with `dimension_hint: "rhythmic"` so downstream evaluation
knows what dimension was touched.

## The six canonical families

Source of truth: `mcp_server/semantic_moves/*.py`. Never invent a
seventh family at the director level.

| Family | What it covers | Typical moves | Maps to dimension |
|---|---|---|---|
| `mix` | Level / EQ / dynamics / space-via-send / stereo | `tighten_low_end`, `widen_stereo`, `make_punchier`, `darken_without_losing_width`, `reduce_repetition_fatigue`, `make_kick_bass_lock`, `reduce_foreground_competition` | spatial (usually) |
| `arrangement` | Section-level structure, clip density, and clip-level rhythmic edits | `refresh_repeated_section`, plus structural moves in `mix_moves.py`. Rhythmic plans that edit notes / grooves / motifs sit here via `dimension_hint: "rhythmic"`. | structural — or rhythmic with dimension_hint |
| `transition` | Between-section energy and motion | `create_buildup_tension`, `smooth_scene_handoff`, `increase_contrast_before_payoff`, `bridge_sections`, `open_chorus`, `create_breakdown`, `increase_forward_motion` | structural |
| `sound_design` | Timbre of individual sources. Per-hit velocity / probability / micro-timing variations also sit here when they change feel, not pattern. | `add_warmth`, `add_texture`, `shape_transients`, `add_space` | timbral — or rhythmic with dimension_hint when per-hit-timing oriented |
| `performance` | Live-safe energy shaping | `recover_energy`, `decompress_tension`, `safe_spotlight`, `emergency_simplify` | (context-specific) |
| `device_creation` | New device / rack / instrument load | `add_*_device` moves | timbral |

**Discovery:** always call `list_semantic_moves(domain=<family>)` at
runtime to enumerate — do not hardcode move IDs. Families are stable;
the move catalog grows.

**Why the director never invents a seventh `rhythmic` family:** the
semantic_moves registry is the execution substrate. A family that
exists in documentation but not in `mcp_server/semantic_moves/*.py`
cannot be compiled into an experiment seed via the registry path. It
would force every rhythmic seed onto the `freeform` / `technique`
source path with a hand-assembled `compiled_plan`. Cleaner to keep the
family set code-aligned and use `dimension_hint` to record the musical
consequence.

## The rule

Generate three seeds. For each seed, identify its DOMINANT move (the
first step in the compiled plan, or the single `move_id` for
`source="semantic_move"` seeds). The `.family` attribute of those three
dominant moves must be three different values from the canonical set.

```
plan_A.dominant.family != plan_B.dominant.family
plan_B.dominant.family != plan_C.dominant.family
plan_A.dominant.family != plan_C.dominant.family
```

If any two match → regenerate the offending plan from a different family.

## How to pick the dominant move for a multi-step seed

For `source="freeform"` / `"synthesis"` / `"composer"` / `"technique"`
seeds that arrive with a compiled plan:

1. The dominant move is the step with the **highest musical consequence**,
   not the first step in execution order.
2. Heuristic: a step that changes identity (new device, new section,
   new timbre) outranks a step that tunes parameters.
3. If ambiguous: tag the seed with a `family_hint` in the seed dict and
   use that.

## Anti-examples — fabricated distinctness

**REJECT these seed sets.** They look different but collapse to one pattern:

- Three `mix` plans with different EQ curves on the same track
  → all `family="mix"` — the agent is converging to "mixing".
- `add_warmth` + `add_texture` + `add_space` — all three are `sound_design`.
  The agent found the sound-design hammer and is hitting everything.
- Three seeds using different references (Villalobos / Basic Channel /
  Gas) but all routing to `sound_design` moves — reference diversity
  is not family diversity.
- Two plans that both add a send to the same reverb with different levels.

**ACCEPT these:** family is actually different.

- Plan A: `arrangement` (breakdown at bar 48) + Plan B: `sound_design`
  (dub chord on pad) + Plan C: `mix` (widen_stereo on hats bus)
- Plan A: `transition` (increase_forward_motion into drop) + Plan B:
  `device_creation` (add Granulator III on vocal) + Plan C:
  `sound_design` (shape_transients on kick)

## Edge cases

### User pre-locked a dimension

If the brief's `locked_dimensions` excludes one or more dimensions
(e.g., "don't touch the arrangement"), the families that map to those
dimensions are off-limits. See `the-four-move-rule.md` for the map.

With one lock: the remaining families still must differ across three plans.
With two locks: only 2 dimensions left — ship 2 plans, not 3 (honesty rule).

### Mix excluded by recency — family-collision risk

When the recency rule excludes `mix` (≥ 5 of 10 in `memory_list`), the
natural fallback plans often collapse into two `arrangement`-family
plans — one structural (insert a breakdown) and one rhythmic (clip
groove + probability edits). Both are honest `arrangement` with
different `dimension_hint` tags, but the diversity rule requires three
distinct families.

**Pre-empt the collision:** when `mix` is excluded and you want both
structural AND rhythmic coverage, route the structural plan through
`transition` family (`create_breakdown`, `create_buildup_tension`,
`bridge_sections`, `increase_forward_motion`) rather than
`arrangement`. Both families can deliver structural consequence;
`transition` is the one that leaves `arrangement` free for the
rhythmic plan.

Allowed combinations when mix is excluded:
- `transition` (structural) + `arrangement` (rhythmic) + `sound_design` (timbral) ✅
- `arrangement` (structural) + `sound_design` (rhythmic, per-hit) + `device_creation` (timbral) ✅
- `arrangement` (structural) + `arrangement` (rhythmic) — ❌ family collision, regenerate

### Fewer than three families plausibly apply

Example: the user's "more warmth on the master" request genuinely only
has `mix` and `sound_design` as credible families. Do NOT fabricate a
`device_creation` plan to hit three.

- Ship two plans across the two real families
- Document explicitly: "Only 2 plans — the ask narrows to {mix,
  sound_design}; forcing a third would be theatre."
- This is inherited from Wonder's honesty rule
- This is ACCEPTABLE on stuck-rescue contexts; on a first-pass creative
  call, re-read the concept packet and check whether a third family
  was overlooked before giving up

### The concept packet mandates a family

If the packet's `reach_for.techniques` cluster in one family, use that
family for the dominant plan — but the OTHER two plans still vary.
Packet specifies the center; diversity rule specifies the spread.

### Sample-heavy workflows

`sample_engine` is not a semantic_move family. Sample-based creative
moves usually dominate as `sound_design` or `device_creation` (loading
Simpler, chopping). Tag the seed's `family_hint` accordingly.

### Rhythmic plans

A rhythmic plan (one whose primary consequence is swing / ghost-note
programming / probability / motif transformation / groove assignment)
dominates as `arrangement` if it edits clip content or pattern, OR as
`sound_design` if it shapes per-hit timbre/velocity in a way that
changes feel. Always attach `dimension_hint: "rhythmic"` to the seed.

Two rhythmic plans across a diverse set are fine IF their dominant
families differ (one `arrangement`, one `sound_design`). Two rhythmic
plans both tagged `arrangement` = fabricated distinctness by the same
rule that forbids two `mix` plans.

## What to write into the turn

After Phase 3 generation, explicitly state the family split. Example:

> Three plans:
> - **A (sound_design):** Dub chord stab into filtered delay send.
> - **B (arrangement):** Negative-space breakdown at bar 48, ghost percussion only.
> - **C (mix):** Widen stereo on hats bus, narrow sub to mono under 80 Hz.

This makes the diversity legible and auditable by the user.

## Why this works

"Pattern repetition" is a signal that the agent keeps choosing the same
family (usually `mix` or `sound_design`, because those are the
easiest/safest). Forcing three families forces the agent to consider
structural and transitional moves it would otherwise skip. That is
where the "distinct musical idea, not just distinct parameters"
property comes from.

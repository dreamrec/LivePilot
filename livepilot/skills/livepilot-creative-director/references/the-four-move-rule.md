# The Four-Move Rule

A creative pass should touch four dimensions: **structural**,
**rhythmic**, **timbral**, **spatial**. The three plans generated in
Phase 3 distribute across these dimensions — they do not duplicate one.

This is the complement to the move-family diversity rule. Family
diversity enforces "different machinery"; four-move coverage enforces
"different musical consequence."

## The four dimensions

Dimensions are orthogonal to `move.family`. A plan has ONE dominant
dimension and ONE dominant family. Multiple dimensions can map to the
same family (e.g. an `arrangement`-family plan can be structural OR
rhythmic depending on what it does). See
`move-family-diversity-rule.md` §"Family vs. dimension" for the split.

| Dimension | What it is | Dominant family typically | Tag with | Also uses |
|---|---|---|---|---|
| **Structural** | Section-level form — adds, removes, reshapes sections or clip density | `arrangement` or `transition` | `dimension_hint` optional (family implies it) | `livepilot-arrangement`, `livepilot-composition-engine`, scene/arrangement tools |
| **Rhythmic** | Timing, groove, swing, motif patterns, polyrhythm, per-hit velocity/probability | `arrangement` (clip pattern edits) OR `sound_design` (per-hit feel) | `dimension_hint: "rhythmic"` REQUIRED — there is no rhythmic family in the registry | `livepilot-notes`, `assign_clip_groove`, `modify_notes`, motif tools, Euclidean rhythm |
| **Timbral** | Source character — instrument choice, patch, saturation, texture | `sound_design` or `device_creation` | `dimension_hint` optional | `livepilot-sound-design-engine`, `livepilot-devices`, atlas lookups |
| **Spatial** | Space and stereo field — reverb, delay, pan, width, depth | `mix` (space-oriented moves) | `dimension_hint: "spatial"` recommended when family=mix (distinguishes from level/EQ mix plans) | `set_track_send`, `set_track_pan`, return-track routing, `add_space` |

Note that `performance` family is orthogonal — it rarely applies on
first-pass creative work; it's for live contexts.

**The fudge is not a fudge:** earlier drafts of this rule described
rhythmic plans as "fudged" because they borrow the `arrangement` or
`sound_design` family. That framing was wrong. The family axis and the
dimension axis are orthogonal by design — a rhythmic plan has an
honest family tag AND an honest dimension tag, via `dimension_hint`.
State both explicitly in the turn. No apology needed.

## The rule

For a creative pass of 3 plans, coverage should span at least 3 of the
4 dimensions. Plans may overlap only after all four dimensions have
been considered.

```
dimensions_touched = {dominant_dimension(p) for p in plans}
len(dimensions_touched) >= 3      # default
len(dimensions_touched) >= 4      # ideal
```

Falling below 3 distinct dimensions is the same failure mode as
falling below 3 distinct families — the agent is clustering.

## How to identify a plan's dominant dimension

Use the move-family → dimension map, then confirm against the plan's
audible consequence:

1. If dominant move's family is `arrangement` or `transition` → **structural**
2. If dominant move's family is `sound_design` or `device_creation` → **timbral**
3. If dominant move's family is `mix` AND the move is space-oriented
   (`add_space`, `widen_stereo`, reverb-related) → **spatial**
4. If dominant move's family is `mix` AND the move is level / EQ /
   dynamics → still **spatial** for this taxonomy (mix's audible
   consequence is positional)
5. If the plan is primarily MIDI-editing (notes, grooves, motif
   transforms) → **rhythmic**, regardless of family tagging

Ambiguous? Tag the seed explicitly in `seed.dimension_hint`.

## Interaction with `locked_dimensions`

If the brief's `locked_dimensions` includes a dimension, that dimension
is off-limits. The remaining three must be covered across the three
plans.

| Locked | Must cover |
|---|---|
| (nothing) | any 3 of 4 (all 4 ideal) |
| `structural` | rhythmic + timbral + spatial |
| `timbral` | structural + rhythmic + spatial |
| `rhythmic` | structural + timbral + spatial |
| `spatial` | structural + rhythmic + timbral |
| two locks | the remaining two — ship 2 plans, not 3 |

Two locks on a 4-dimension space means the problem is narrow. Two
plans is honest; faking a third by sneaking into a locked dimension
violates both this rule AND the user's explicit constraint.

## Example 1 — "Make it feel like Basic Channel if Dilla touched the swing"

No locked dimensions. Ideal coverage = 4/4 but we only have 3 plans.
Each plan tagged `family / dimension`:

- Plan A (`arrangement` / **structural**): Add an 8-bar breakdown at bar 48 where kick drops out and only ghost hats + dub-chord tail remain.
- Plan B (`arrangement` / **rhythmic**, dimension_hint="rhythmic"): Micro-shift hi-hat notes by −8 to +12 ticks, add ghost notes at 62% probability, assign a "Dilla-esque" groove.
- Plan C (`sound_design` / **timbral**): Load Drift for the chord, route to a send with Ping Pong Delay + Auto Filter on the return, print 25% wet.

Family-diversity note: Plans A and B are BOTH `arrangement` family —
this is a rule violation unless corrected. Swap Plan B to tag
`sound_design` family instead (per-hit velocity + micro-timing counts
as feel-shaping sound_design per the family→dimension map), OR swap
Plan A to `transition` family (create_breakdown semantic move). Either
fix keeps all three dimensions covered. The point: rhythmic as a
dimension does not exempt the plan from the three-distinct-families
constraint — the director must still land family diversity, just via
the appropriate tag.

Corrected version:
- Plan A (`transition` / **structural**): `create_breakdown` semantic move at bar 48.
- Plan B (`arrangement` / **rhythmic**, dimension_hint="rhythmic"): groove + probability edits to clip.
- Plan C (`sound_design` / **timbral**): Drift + send chain.

Spatial dimension is not directly touched by a plan — but Plan C's
send-chain IS spatial in consequence. Coverage is honest: 3 explicit
dimensions, one implicit.

## Example 2 — "Make the drums more interesting, don't touch the arrangement"

Locked: `structural`. Must cover rhythmic + timbral + spatial.

- Plan A (`arrangement` / **rhythmic**, dimension_hint="rhythmic"): Add probability 70-90% to the hat and clap clip; apply a 58% swing groove from `list_grooves`. Family is `arrangement` because the target is clip content; dimension is rhythmic because the audible consequence is feel. The `structural` lock concerns SECTION-level arrangement, not clip-level edits — locked_dimensions semantics resolve at the dimension level, not the family level.
- Plan B (`sound_design` / **timbral**): Layer a parallel drum bus with Saturator + Drum Bus; per-hit velocity mod on snare.
- Plan C (`mix` / **spatial**, dimension_hint="spatial"): Send hats and ghost snares to a short plate reverb at -14 dB; narrow the kick to mono under 80 Hz.

All three dimensions hit. Section arrangement untouched. Three families
distinct. Honest.

## Example 3 — Narrow request: "the pad is too static"

Ambiguous whether "static" means timbre or space. The agent should
compile a brief that acknowledges this and generate plans across both:

- Plan A (`sound_design` / **timbral**): Enable wavetable position LFO + macro
  modulation on Drift.
- Plan B (`mix` / **spatial**, dimension_hint="spatial"): Send the pad to a long convolution reverb on a
  return with Auto Filter LFO.
- Plan C (`arrangement` / **rhythmic**, dimension_hint="rhythmic"): Automate a slow 8-bar amplitude envelope so
  the pad breathes with the section.

This is an explicit case where the structural dimension is not
relevant (it's one sound, not an arrangement decision). Three of four
is the natural coverage. Shipping a structural plan would be
fabricated.

## When to drop below three dimensions

Drop to 2 of 4 (or 1 of 4) ONLY in these situations. In all cases:
ship fewer plans honestly. Do not fake coverage.

1. **Two or more dimensions locked.** User explicitly locked two
   dimensions → at most 2 dimensions remain → at most 2 honest plans.

2. **Genuinely narrow task AND concept packet confirms no other
   dimension is in scope.** Example: "make this one reverb return
   less muddy" is spatial-only.

3. **Low novelty_budget + narrow-idiom concept packet.** When the
   user's request is reference-adjacent (`novelty_budget` ≤ 0.50) AND
   the concept packet explicitly de-prioritizes certain dimensions,
   dropping those dimensions is idiomatic, not fabricated. Examples:

   - **Dub-techno packets** (Basic Channel / Rhythm & Sound) explicitly
     de-emphasize the rhythmic dimension ("percussion implied not
     stated"). Three plans may legitimately cluster in
     timbral + spatial + (optional) structural. Rhythmic absent is
     idiomatic honesty.
   - **Ambient packets** (Gas / Basinski / Stars of the Lid) explicitly
     de-emphasize rhythmic AND structural (static with very slow
     evolution). Three plans clustering in timbral + spatial is
     idiomatic.
   - **Beat-focused packets** (Dilla / Premier) explicitly
     de-emphasize the spatial dimension (dry intimacy is the aesthetic).
     Three plans clustering in rhythmic + timbral + structural is
     idiomatic.

   When this rule fires, document the decision in the turn: *"The
   packet's aesthetic de-prioritizes <dimension>; dropping it here is
   idiomatic rather than coverage failure."* This prevents future
   agents from mistaking the under-coverage for a skill bug.

**Never-drop rule:** even when dropping dimensions, the family
diversity rule still applies to whatever plans you DO ship. Two plans
must have different families; three plans must have three different
families. Narrow doesn't excuse fabricated distinctness.

## Why this rule works

"Layered and complex output" — what the user asks for when they say
"more interesting" — is almost always a DISTRIBUTION problem, not a
depth problem. A pass that touches rhythm + timbre + space feels
three-dimensional even if each individual change is small. A pass that
stacks three `mix` moves feels thin even when the changes are large.

Force distribution. Depth emerges.

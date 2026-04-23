# Creative Brief — Schema and Examples

The Creative Brief is an inline YAML block emitted during Phase 2 of the
director contract. It is NOT a tool call and NOT stored in memory until
Phase 8 (`memory_learn`). It is a conditioning payload that downstream
skills read in the same turn.

## Why an inline block

The brief's only job is to pin the artistic thesis and constraints
BEFORE generation so the three plans can be judged against it. If it
lives in memory or in a tool response, the agent can ignore it. Inline
in the turn, the agent cannot.

## Schema

```yaml
creative_brief:
  identity:            # one-line artistic thesis (not a genre label)
  reference_anchors:   # list — artists/genres/tracks user named
    - type: artist      # artist | genre | track | description
      name:             # e.g. "Basic Channel"
      source:           # user | inferred_from_memory | inferred_from_session
  protected_qualities: # list — things that must survive all changes
    -                   # e.g. "low-end weight", "restraint", "sparseness"
  anti_patterns:       # list — things that would break the brief
    -                   # drawn from concept packet `avoid` + anti_preferences + last_move_target
  novelty_budget:      # 0.0 (conservative) to 1.0 (strange-but-plausible)
  target_dimensions:   # evaluation bias — what "better" means here
    groove:            # 0.0 to ~0.25 (weights sum loosely to 1)
    depth:
    contrast:
    novelty:
    cohesion:
    motion:
    clarity:
  structure_hypothesis: # optional — only if structure is in scope
    - section:          # intro | groove_body | breakdown | return | outro
      bars:
      intent:
  locked_dimensions:   # list — dimensions user said don't touch
    -                   # "structural" | "rhythmic" | "timbral" | "spatial"
  last_move_target:    # from Phase 1 get_last_move — do NOT re-target this combo
    family:             # e.g. "mix"
    target:             # e.g. "track_index=2" / "master" / "bass group"
    move_id:            # e.g. "make_kick_bass_lock"
  recommended_skill_chain: # ordered skills to execute the winning plan
    -
```

### Why `last_move_target`

`anti-repetition-rules.md` §3 forbids Phase 3 plans from repeating the
exact family + target combination of the most recent committed move.
That constraint lives in Phase 1 read results and can be lost between
phases. Putting `last_move_target` in the brief makes it survive — and
makes the violation visible on review. If Phase 1 returns no prior
move (fresh session), leave the field as `null`.

## Rules for filling each field

| Field | Source |
|---|---|
| `identity` | User prompt + concept packet `sonic_identity`. One sentence. Not a genre label. |
| `reference_anchors` | Explicit user references, OR inferred from `project_brain` if returning to an existing track |
| `protected_qualities` | Concept packet `sonic_identity` + `project_brain` identity statement. Also anything user said "keep". |
| `anti_patterns` | UNION of concept packet `avoid` + `get_anti_preferences` results + user's "don't" asks + the `last_move_target` combo (do not re-target) |
| `novelty_budget` | See the novelty_budget table below. |
| `target_dimensions` | Concept packet `evaluation_bias.target_dimensions` if packet is loaded; else derive from intent. Dub/ambient → depth/motion; club/dance → groove/contrast; pop → clarity/motion. |
| `structure_hypothesis` | Only if the request is structural. Otherwise omit. |
| `locked_dimensions` | Read user's prompt literally. "Don't touch the arrangement" → `structural`. Silence = no locks. Silence for rhythmic/timbral/spatial = permission. Silence for structural = permission with **conditional** disclosure: flag the intent in the `identity` line ONLY IF the Phase 3 plan set actually includes a structural plan. Compile plans first, then decide whether the disclosure is warranted — no structural plan means no disclosure. |
| `last_move_target` | From Phase 1 `get_last_move`. Populate family + target + move_id. If no prior move, set to `null`. |
| `recommended_skill_chain` | Map target_dimensions to skills. See the-four-move-rule.md family-to-dimension table. |

### Novelty budget — full table

User framing maps to `novelty_budget` values. Choose the nearest match:

| User says | novelty_budget | Notes |
|---|---|---|
| "keep the vibe, just cleaner" / "same energy, tighten it" | 0.25 – 0.35 | Conservative; bias toward `mix` and `sound_design` refinement |
| "a bit more like X" / "lean it slightly toward X" | 0.40 – 0.50 | Reference-adjacent; packet avoid filters matter MORE than novelty |
| "make it more interesting" / "develop this" / "more character" | 0.50 – 0.65 | Default creative ask; 0.55 is a safe midpoint |
| "take it somewhere" / "evolve this" / "mutate" | 0.60 – 0.75 | Moderately high novelty; cross-domain moves allowed |
| "surprise me" / "make it magical" / "I'm stuck" | 0.70 – 0.85 | High novelty; strange-but-plausible plans welcome. If `detect_stuckness > 0.5`, route to Wonder rescue instead |
| "I don't know what I want" / open-ended "ideas?" | 0.55 | Default to mid; let divergence surface options |

If the user frame spans two categories, pick the lower novelty. Under
speed pressure ("quickly"), do NOT change the novelty_budget — it is
the artistic posture, not the effort level.

## Example 1 — "Make it feel like Basic Channel if Dilla touched the swing"

```yaml
creative_brief:
  identity: "Dub-techno space with human swing tension — chord stabs as harmonic vehicle, percussion implied not stated (structural change in scope — will add a breakdown section)"
  reference_anchors:
    - type: artist
      name: "Basic Channel"
      source: user
    - type: artist
      name: "J Dilla"
      source: user
  protected_qualities:
    - low-end weight
    - space as instrument
    - restraint (subtraction over addition)
  anti_patterns:
    - bright transient-heavy hats
    - crisp EDM clap dominance
    - full-grid quantization
    - obvious boom-bap clichés
  novelty_budget: 0.65
  target_dimensions:
    depth: 0.22
    groove: 0.20
    motion: 0.14
    contrast: 0.12
    novelty: 0.12
    cohesion: 0.10
    clarity: 0.10
  locked_dimensions: []        # silent = no locks, BUT structural change flagged in identity (see silent-locks rule)
  last_move_target: null        # fresh session
  recommended_skill_chain:
    - livepilot-sound-design-engine   # chord stab + filtered delay + reverb tails
    - livepilot-notes                 # swing + micro-timing shifts on hats
    - livepilot-arrangement           # negative-space section logic
    - livepilot-evaluation            # artistic dimensions must pass
```

## Example 2 — "Make the drums more interesting, don't touch the arrangement"

```yaml
creative_brief:
  identity: "Increase drum character without destabilizing the track's form"
  reference_anchors: []   # no external reference named
  protected_qualities:
    - current arrangement shape
    - overall density
  anti_patterns:
    - every-bar fills
    - ornamental velocity rides that don't alter feel
    - sterile quantization
  novelty_budget: 0.55
  target_dimensions:
    groove: 0.25
    novelty: 0.18
    motion: 0.15
    contrast: 0.12
    depth: 0.10
    cohesion: 0.10
    clarity: 0.10
  locked_dimensions:
    - structural       # user said "don't touch the arrangement" — section-level off-limits; rhythmic clip edits still allowed
  last_move_target: null
  recommended_skill_chain:
    - livepilot-notes             # swing, ghost notes, probability, micro-timing
    - livepilot-sound-design-engine  # drum timbre variations per hit
    - livepilot-evaluation
```

## Example 3 — "Just quickly, make it sound a bit more like Basic Channel"

Speed pressure ("just quickly" / "don't overthink it") does NOT skip
the brief; it compresses prose. Reference-adjacent ask ("a bit more
like") maps to `novelty_budget ≈ 0.45`.

```yaml
creative_brief:
  identity: "Basic Channel-adjacent dub-techno posture — space and tail as harmonic vehicle, restrained top end"
  reference_anchors:
    - type: artist
      name: "Basic Channel"
      source: user
  protected_qualities:
    - existing chord content (reference-adjacent, not reference-replacement)
    - low-end weight / mono sub
    - current arrangement shape (structural not named in scope)
  anti_patterns:
    - bright transient-heavy hats        # packet avoid
    - dry signals / short tails           # packet avoid
    - pre-mixed "finished" presets        # packet avoid
  novelty_budget: 0.45   # "a bit more like" → reference-adjacent
  target_dimensions:
    depth: 0.24
    motion: 0.18
    cohesion: 0.14
    groove: 0.12
    contrast: 0.12
    novelty: 0.10
    clarity: 0.10
  locked_dimensions: []
  last_move_target: null
  recommended_skill_chain:
    - livepilot-devices                  # return track setup (Ping-Pong Delay → Convolution Reverb)
    - livepilot-sound-design-engine      # chord routing, filter-on-return
    - livepilot-mix-engine               # narrow-to-mono sub
    - livepilot-evaluation
```

## Example 4 — Exact-parameter request (NO BRIEF)

> "Set track 3 volume to -6 dB."

This is operational, not creative. The director does not fire. No brief.
The agent routes directly to `set_track_volume`.

## Field-absence rules

- If `reference_anchors` is empty AND no concept packet loads → `identity`
  comes from current `project_brain` identity statement, or from
  re-reading the user prompt's most recent aesthetic adjective
- If `anti_patterns` is empty → fall back to recent `get_anti_preferences`
  results; if that is empty too, the brief is brittle — flag the gap
- If `target_dimensions` cannot be inferred → use a flat weight (all
  ≈0.14) and note the weakness in the turn

## Emit rule

The brief appears ONCE per creative turn, at the top of the assistant
message, before any Phase 3 tool call. It is for the user to see and
correct. Treat user edits to the brief as authoritative.

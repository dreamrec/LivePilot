# Hybrid Concept Packet Compilation

**Tool:** `compile_hybrid_brief(packet_ids: list[str], weights: list[float] | None = None)`
**Module:** `mcp_server/creative_director/hybrid.py`
**Shipped:** v1.19.0 (Item B from `docs/plans/v1.19-structural-plan.md` §3)

---

## When to call it

Phase 1 of the creative director skill. If the user names **two or more**
reference points in their request, call this tool before Phase 2 brief
compilation. Examples:

| User prompt | Call |
|---|---|
| "Basic Channel meets Dilla swing" | `compile_hybrid_brief(["basic-channel", "j-dilla"])` |
| "Villalobos but sparse like Gas" | `compile_hybrid_brief(["villalobos", "gas"])` |
| "Madlib chop with Photek precision" | `compile_hybrid_brief(["madlib", "photek-source-direct"])` |
| "Boards-of-Canada sound design, Basic Channel space, Dilla drums" | `compile_hybrid_brief(["boards-of-canada", "basic-channel", "j-dilla"])` |

Do NOT call this when:

- Only one reference is named (just load the single packet)
- The user names references but asks for a move that doesn't use the
  brief's `reach_for` or `avoid` (e.g., "make the kick louder" — trivial
  direct action, no packet merge needed)
- You're in a continuation turn on an already-compiled hybrid
  brief — reuse the brief from the session record

---

## Merge rules (canonical)

These rules are enforced in
`mcp_server/creative_director/hybrid.py::_compile_from_packets`. The
table shows what each packet field does when N packets are merged.

| Field | Merge strategy | Rationale |
|---|---|---|
| `sonic_identity` | UNION | hybrids describe the envelope of both sounds |
| `reach_for.instruments` / `effects` / `packs` / `utilities` | UNION | candidate pool widens; let Phase 3 filter |
| `avoid` | UNION | both packets' hard filters apply — stricter wins |
| `rhythm_idioms` / `harmony_idioms` / `arrangement_idioms` / `texture_idioms` | UNION | all stylistic tendencies remain available |
| `sample_roles` | UNION | all source roles valid |
| `dimensions_in_scope` | UNION | scope widens to cover both |
| `dimensions_deprioritized` | INTERSECTION | deprioritize only when ALL packets agree — otherwise one packet wants what the other ignores |
| `move_family_bias.deprioritize` | INTERSECTION | same logic — don't starve a family one packet depends on |
| `move_family_bias.favor` | INTERSECTION when non-empty, UNION fallback with warning | focus where both agree; when disjoint, span both (warn — hybrid may blur) |
| `evaluation_bias.target_dimensions` | WEIGHTED AVERAGE (default uniform) | continuous blend, weights sum to 1.0 |
| `evaluation_bias.protect` | MAX per dimension | stricter floor wins (protect=0.80 beats 0.75) |
| `novelty_budget_default` | MAX | hybrid asks skew exploratory — let the more adventurous packet lead |
| `tempo_hint` | NEAREST-OVERLAP: intersect overlapping ranges, else midpoint + warn | disjoint tempos = real ambiguity to surface |

---

## Output shape

```yaml
type: hybrid
source_packets: [basic-channel, j-dilla]
weights: [0.5, 0.5]
name: "Basic Channel / Rhythm & Sound × J Dilla"

sonic_identity: [...]               # UNION
reach_for:                          # UNION per-subfield
  instruments: [...]
  effects: [...]
  packs: [...]
  utilities: [...]

avoid: [...]                        # UNION
anti_patterns: [...]                # alias of avoid — compat with
                                    #   check_brief_compliance

rhythm_idioms: [...]                # UNION
harmony_idioms: [...]
arrangement_idioms: [...]
texture_idioms: [...]
sample_roles: [...]

evaluation_bias:
  target_dimensions:                # WEIGHTED AVERAGE
    groove: 0.19                    #   e.g., (0.12 + 0.26) / 2
    depth: 0.20
    ...
  protect:                          # MAX per dimension
    low_end: 0.80                   #   e.g., max(0.80, 0.75)
    cohesion: 0.68
    ...

move_family_bias:
  favor: [sound_design, device_creation]   # INTERSECTION
  deprioritize: [performance]              # INTERSECTION

dimensions_in_scope: [...]          # UNION
dimensions_deprioritized: []        # INTERSECTION (often empty for hybrids)
locked_dimensions: []               # NEVER locked by hybrid itself

novelty_budget_default: 0.6         # MAX
tempo_hint:
  min: 107.5                        # or overlap range, or midpoint+disjoint flag
  max: 110.0
  time_signature: "4/4"
  disjoint: true                    # present only when tempo ranges didn't overlap

warnings:                           # human-readable ambiguity notes
  - "Tempo ranges don't overlap (Basic Channel 120-130; J Dilla 85-95)
     — defaulting to midpoint 108 BPM. Specify which anchor you want
     or pick a single packet."
```

---

## Handling the `warnings` list

`warnings` is a signal the merge algorithm had to make a choice the
user's prompt didn't disambiguate. Surface every entry in your Phase 2
brief — DO NOT silently accept the defaulted value.

| Warning kind | What it means | What to do in the brief |
|---|---|---|
| **Tempo disjoint** | Source packets' tempo ranges don't overlap | Cite the ranges in the identity line, ask the user to pick an anchor or state a target tempo |
| **Favor union fallback** | `favor` lists had empty intersection, fell back to UNION | Note that the hybrid may span more move families than either source intends; lean harder on user framing in Phase 3 |
| **(Future warnings)** | Any future ambiguity the merge algorithm detects | Surface literally — don't paraphrase |

---

## Interoperability

- **`check_brief_compliance`** (v1.18.3): the hybrid brief passes
  directly. The merged `avoid` list is also exposed as `anti_patterns`
  for compat; `locked_dimensions` is always `[]` (hybrids don't lock).
- **Phase 3 plan candidates**: use `reach_for` to seed devices,
  `avoid` as HARD filter on each candidate, `move_family_bias.favor` to
  weight family diversity.
- **Phase 7 learning**: `source_packets` is preserved on the brief, so
  when the user accepts a plan you can record which hybrid produced it
  (taste over time).

---

## Example: BC × Dilla

```python
brief = compile_hybrid_brief(["basic-channel", "j-dilla"])

# Merged avoid (UNION):
#   bright top-end, dry signals, short tails, ... (BC)
#   quantized drums, bright mixes, trap hi-hats, ... (Dilla)
#   → result: both sets enforced

# Dimensions:
#   BC deprioritizes [rhythmic]; Dilla deprioritizes [spatial]
#   → INTERSECTION is empty → neither deprioritized in hybrid
#   → UNION of in_scope is {structural, rhythmic, timbral, spatial}

# Favor:
#   BC favor = {sound_design, device_creation, mix}
#   Dilla favor = {arrangement, sound_design, device_creation}
#   → INTERSECTION = {sound_design, device_creation}
#   → hybrid plans cluster on sound_design + device_creation

# Tempo:
#   BC 120-130, Dilla 85-95 → DISJOINT
#   → warning surfaces; midpoint ~108 BPM returned
#   → Brief must ask user to pick an anchor
```

---

## What this is NOT

- **Not a taste classifier.** The merge is a syntactic operation over
  packet fields. It doesn't judge whether the hybrid "makes sense" as
  an artistic direction — that's the user's call.
- **Not a replacement for packet curation.** If the user asks for a
  hybrid you've never heard of that doesn't resolve to existing
  packets, `compile_hybrid_brief` raises `ValueError`. Fall back to
  the narrative `.md` files and note the missing packet as v1.20+
  scope.
- **Not for more than ~4 packets.** The merge runs at any N, but
  target_dimensions weighted average gets noisy as N grows
  ("nothing is emphasized"). Prompts with 4+ references usually
  deserve clarification, not automatic merging.

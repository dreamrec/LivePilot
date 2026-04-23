# Anti-Repetition Protocol

The director's Phase 1 reads are not advisory. They are the mechanism
that breaks pattern repetition, because LLM-driven generation collapses
to the most-likely completion by default — and "most-likely" is almost
always "what I did last time."

## Ledger-state inference fallback (v1.18.1)

The detection mechanisms below (`get_last_move`, `memory_list`) ONLY
see moves that went through `apply_semantic_move` or `commit_experiment`.
If a prior Phase 6 executed via raw tool calls WITHOUT an
`add_session_memory` ledger marker (per director SKILL.md Phase 6
ledger discipline), the ledger will appear empty even though creative
work happened.

**Fallback when `get_last_move` returns `{}` and `memory_list` shows
no recent creative entries**: perform session-state inference. Compare
the current session state (track count, return track device chains,
clip slot contents) against a naive "blank session" baseline. Any
non-default device loadout or non-empty return track suggests recent
creative work that the ledger missed. Infer the move family from
what's loaded:

| Session-state signal | Inferred recent family |
|---|---|
| Non-empty return tracks with delay/reverb chains | `device_creation` / `mix` (spatial) |
| New devices on MIDI tracks (Drift, Meld, Operator, etc.) | `sound_design` / `device_creation` (timbral) |
| Modified mixer state (volume/pan/sends non-default) | `mix` |
| Clips with notes in previously-empty slots | `arrangement` / `sound_design` (rhythmic) |
| New scenes / renamed scenes | `arrangement` (structural) |

State inference is a best-effort fallback, not a replacement for the
ledger. Director SHOULD use `add_session_memory` after raw-tool
execution to populate the ledger properly — the fallback exists to
reduce blast radius when Phase 6 discipline was skipped.

## Mandatory pre-generation reads

Run all three in parallel during Phase 1. Skipping any of them = the
agent will repeat.

### 1. `get_anti_preferences`

Returns moves, device families, patches, and aesthetic directions the
user has previously rejected (via `record_anti_preference` or implicit
undo signals). Treat the response as a HARD filter on Phase 3 seeds.

If a candidate plan's dominant move appears in anti-preferences → do
not include it. Regenerate from a different family.

### 2. `memory_list(limit=10)`

Returns the last 10 saved techniques / moves. The window is fixed at
the last 10 committed (or kept) moves. Inspect their `move_family`
distribution:

| Recency count for one family | Rule |
|---|---|
| 0 of 10 | Family is cold. No penalty. |
| 1–2 of 10 | Family is lightly used. No penalty; prefer-other-if-tied. |
| 3–4 of 10 | Family is a "recent hot zone." ALLOWED as a plan's dominant family, but only as the **least-weighted** of the three. Two of the three plans must come from other families. |
| ≥ 5 of 10 | Family is a **stuck pattern**. EXCLUDED from all three dominant slots — the other two or three plans must cover different families. Also: run `detect_stuckness`. If confidence > 0.5, escalate to Wonder rescue. If 0.4 ≤ confidence < 0.5, see the borderline-stuckness rule in `SKILL.md` §Anti-Repetition Protocol. |

The `≥5 of 10` threshold is the same threshold Wonder's stuck-rescue
path expects, but the director applies it proactively on creative
intent — the user does not need to say "I'm stuck" for the recency
rule to bite.

### 3. `get_last_move`

The most recent committed move. Phase 3 plans MUST NOT exactly repeat
the last move's family + target combination, even with different
parameters. That is the clearest pattern-repetition signal.

Populate the brief's `last_move_target` field (see
`creative-brief-template.md`) so the constraint survives between Phase
1 reads and Phase 3 generation.

## The bias rule

After Phase 1 reads, compute a "recency family vector":

```
recent_families = {family: count for move in last 10 committed moves}
```

Apply a penalty to seeds whose dominant family has a high recency
count. The penalty is informal (not a numeric score) — it just means:
when two families are equally good choices for a plan, prefer the one
NOT in `recent_families`.

This is the mirror of taste-aware ranking. Taste says "lean toward
what the user liked." Recency bias says "don't converge back to it
every time."

## Concept packet `avoid` is a HARD filter

When a packet is loaded (from `artist-vocabularies.md` or
`genre-vocabularies.md`), its `avoid` list is not a suggestion.

- A candidate plan whose techniques fall in `avoid` → drop it, no
  negotiation.
- Example: dub_techno packet's `avoid: [bright transient-heavy hats]`.
  A plan that loads Drum Bus with boosted transients on hats is
  rejected even if otherwise diverse.

Packets compile. Vibes compile to filters.

## Recording anti-preferences

On these signals, write to `record_anti_preference` with enough context
that future sessions learn from it:

| Signal | What to record |
|---|---|
| User calls `discard_preview_set` | The family + technique of every variant in the set, tagged as "rejected in context X" |
| User runs `undo` within 2 turns of `commit_preview_variant` | The specific move + family + context |
| User says "no, not that" / "try something else" after preview | The preview-set's dominant family |
| Evaluation verdict = `generic_fallback` | The family and technique pattern |

Do NOT record anti-preferences on:

- Simple operational `undo` (volume / pan adjustments)
- `undo` in service of A/B comparison
- User re-ordering or renaming without rejection signal

## Example — detecting the stuck pattern

Session history shows the last 5 committed moves:

1. `widen_stereo` (family=`mix`)
2. `tighten_low_end` (family=`mix`)
3. `darken_without_losing_width` (family=`mix`)
4. `make_punchier` (family=`mix`)
5. `reduce_foreground_competition` (family=`mix`)

Phase 1 detects: `mix` is 5/5 of recent history. The user just said
"more interesting". Without anti-repetition, the most-likely
completion is ANOTHER `mix` move.

Correct Phase 3 response per the recency threshold table above:

- 5 of 10 (or 5 of 5, same conclusion) → `mix` is **EXCLUDED** from
  all three dominant slots. Not "allowed as least-weighted" — that
  rule applies at 3–4/10, not at 5/10.
- Three seeds must come from `{arrangement, transition, sound_design,
  device_creation, performance}` — all three different.
- Run `detect_stuckness`:
  - `> 0.5` → route to Wonder rescue (not standard divergence)
  - `0.4 ≤ confidence < 0.5` → borderline — stay in standard
    divergence BUT flag to the user ("I'm staying in divergence; say
    the word to switch to Wonder rescue mode")
  - `< 0.4` → standard divergence, no escalation

The "allow one mix plan as least-weighted" escape hatch that earlier
drafts mentioned applies ONLY at 3–4/10 recency, not at ≥ 5/10.
At 5/10 the family is fully excluded.

## Example — respecting user-specified deepening

User says: "I like where the timbre is going — push it further."

This is an explicit opt-in to stay in `sound_design`. The family
diversity rule still applies (three plans, different families), BUT:

- The dominant plan (the one recommended to the user) stays
  `sound_design`
- The other two plans are framed as "alternative directions if the
  deepening direction stops paying off"
- No anti-preference penalty applied this turn

Explicit deepening requests ALWAYS override recency bias. Silence does
not.

## What NOT to do

- Do not skip Phase 1 reads because "it's obvious what the user wants"
- Do not treat anti-preferences as soft suggestions
- Do not record every discarded variant as an anti-preference — that
  floods the store with noise. Record only when the user actively
  rejected something (see table above).
- Do not record anti-preferences for moves the user never actually
  heard (analytical-only variants that were never rendered)

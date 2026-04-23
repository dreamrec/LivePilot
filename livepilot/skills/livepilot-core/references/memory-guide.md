# Technique Memory Guide — Qualities Template & Examples

How to write rich, searchable stylistic analyses when saving techniques.

## The Qualities Template

Every technique gets an agent-written `qualities` object. All fields are optional
except `summary` (required). Fill what's relevant to the technique type.

| Field | What to write | Example |
|-------|--------------|---------|
| summary | One sentence — what this is and why it's good | "Dusty boom bap groove with lazy swing and ghost snares" |
| mood | 2-4 mood/feeling words | ["laid-back", "dusty", "head-nodding"] |
| genre_tags | Genre associations | ["boom-bap", "hip-hop", "lo-fi"] |
| rhythm_feel | How the groove feels — swing, syncopation, density | "Syncopated kick with lazy hat swing, ghost snares anticipate the backbeat" |
| harmonic_character | Key, scale, chord quality, movement | "C minor dorian, jazzy 7th chords, descending bass line" |
| sonic_texture | Timbral character — warm/bright/gritty/clean | "Dusty vinyl-crackle hats, boomy 808 kick, dry snare with room verb" |
| production_notes | When/how to use this, what it pairs with | "Works as verse beat, needs sparse melody on top — Rhodes or muted guitar" |
| reference_points | Artists, songs, styles it evokes | "J Dilla 'Donuts' era meets Madlib 'Madvillainy' drums" |

## Good vs Bad Qualities

### Beat Pattern

**GOOD:**
```json
{
  "summary": "Dusty boom bap groove — lazy swing on the hats, ghost snares anticipate the backbeat, 85 BPM slow-roll energy",
  "mood": ["laid-back", "dusty", "head-nodding"],
  "genre_tags": ["boom-bap", "hip-hop"],
  "rhythm_feel": "Syncopated kick at 0 and the 'and' of 1. Hi-hats on 8ths with +0.02 swing on offbeats. Ghost snares (vel 30) on 16ths before beats 2 and 4. The whole thing leans back.",
  "production_notes": "Works as a verse beat. Needs sparse melody on top — Rhodes, muted guitar, or pitched sample. Leave headroom in low-mids for vocals.",
  "reference_points": "J Dilla 'Donuts' era meets Madlib on 'Madvillainy'"
}
```

**BAD:**
```json
{
  "summary": "Hip hop beat at 85 BPM with kick, snare, and hi-hats"
}
```
The bad version is factual but tells the agent nothing about *feel*. It can't distinguish this from any other hip-hop beat.

### Device Chain

**GOOD:**
```json
{
  "summary": "Warm tape-style lo-fi chain — subtle saturation into gentle filtering, makes anything sound like it's playing through a dusty speaker",
  "mood": ["warm", "nostalgic", "lo-fi"],
  "sonic_texture": "Soft Sine saturation adds even harmonics without harshness. Auto Filter rolls off highs gently around 3kHz. Erosion adds subtle digital artifacts like worn tape. The chain darkens and warms without killing presence.",
  "production_notes": "Put this on Rhodes, guitar samples, or pads. Not great for drums — kills transients. Works beautifully on chord progressions.",
  "reference_points": "Lo-fi hip-hop study beats aesthetic, Nujabes-style warmth"
}
```

**BAD:**
```json
{
  "summary": "Saturator then Auto Filter then Erosion"
}
```

### Mix Template

**GOOD:**
```json
{
  "summary": "Deep house return setup — long lush reverb on A, filtered ping-pong delay on B, subtle parallel compression on C",
  "mood": ["spacious", "deep", "hypnotic"],
  "genre_tags": ["deep-house", "tech-house"],
  "sonic_texture": "Reverb is dark and long (4s decay, heavy high-cut) for depth without brightness. Delay is filtered (LP at 3kHz) so echoes sit behind the mix. Parallel compression adds density to drums without crushing transients.",
  "production_notes": "Send drums to C at 0.3, pads to A at 0.5, synth stabs to B at 0.3. Keep kick dry (no sends). Return levels around -8dB for subtlety."
}
```

### Preference

**GOOD:**
```json
{
  "summary": "Always use Valhalla VintageVerb instead of stock Reverb on return tracks — stock Reverb sounds too metallic in the highs for my taste"
}
```

### Browser Pin

**GOOD:**
```json
{
  "summary": "808 Core Kit — my go-to drum kit for trap and hip-hop. Has a punchy kick that sits well with Saturator, crispy hats, and a tight clap."
}
```

## When to Save

- User says "save this" / "remember this" / "I like this"
- A beat, sound, or chain turns out particularly well
- User discovers a browser item they want to use again
- User states a preference about how they work

## When NOT to Save

- Generic, unfinished, or placeholder work
- Things that are already in the shipped reference corpus
- Exact duplicates of existing saved techniques

## Reflection Promotion Rubric (for creative-director turns)

When a move is driven by `livepilot-creative-director`, the evaluation
engine assigns a **verdict** (see `livepilot-evaluation/SKILL.md` §8b).
The verdict drives promotion decisions — not the raw score alone.

### Promotion matrix

| Verdict | Promote? | Required conditions | Payload fields |
|---|---|---|---|
| `safe_win` | Conditional | User kept move for ≥ 2 subsequent turns (avoid over-promotion of minor moves) | technique type, context, concept_packet id (if any), novelty_budget |
| `bold_win` | Immediate | One turn is enough — boldness + user-kept = high signal | technique type, full context, concept_packet id, novelty_budget, what-made-it-bold paragraph |
| `interesting_failure` | Curiosity store only | User kept BUT low technical score — novel-but-untested | store as "curiosity" note; do NOT add to `memory_learn` promotion candidates |
| `identity_break` | Never promote | Protected quality violated | instead call `record_anti_preference` with the violated quality |
| `generic_fallback` | Never promote | Low both scores + collapse-to-pattern signature | instead call `record_anti_preference` with the family+target combo |

### Why this discipline matters

The "stuck in patterns" failure mode (the core problem the creative
director exists to solve) happens when memory fills up with
`safe_win`-adjacent moves that reinforce the same family over time.
Unfiltered promotion turns memory into a convergence engine.
Verdict-gated promotion keeps memory biased toward useful diversity.

Specifically:
- `safe_win` without the 2-turn requirement pollutes memory with moves
  the user only tolerated in the moment
- `bold_win` without immediate promotion loses the signal when the
  session moves on
- `interesting_failure` without a clear "do not auto-replay" flag
  trains the agent to reach for failures
- `identity_break` and `generic_fallback` without anti-preference
  records let the same bad pattern reappear next session

### Cross-check before promoting

Before calling `memory_learn`, run these checks:

1. **Verdict is `safe_win` or `bold_win`** — other verdicts don't promote
2. **Context is recorded** — concept_packet id, novelty_budget, brief's
   identity line. Without context, the memory is noise.
3. **Payload is interpretable** — someone reading the `qualities` field
   in 3 months should understand why it worked, not just what it was
4. **No duplicate** — `memory_list` for similar techniques; if one
   already exists for this family+target combo, update it instead

### Recording anti-preferences correctly

When verdict is `identity_break` or `generic_fallback`:

```python
record_anti_preference(
    dimension=<the violated protected quality or family>,
    direction=<"increase" or "decrease">,
    context=<brief's identity line + move family + target>,
)
```

The `context` field is what lets future sessions know WHEN to apply
this anti-preference — rejecting "bright hats" blanketly is too
aggressive; rejecting "bright hats on dub-techno context" is correct.

### Cross-refs

- `livepilot-creative-director/references/anti-repetition-rules.md` —
  when to record anti-preferences
- `livepilot-evaluation/SKILL.md` §"Memory Promotion" — verdict-driven
  promotion from the evaluator side
- `livepilot-creative-director/SKILL.md` Phase 8 — the director's
  recording step

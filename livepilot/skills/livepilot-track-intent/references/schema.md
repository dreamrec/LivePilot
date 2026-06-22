# Track Intent Annotation Schema

Track intent fields are sparse. Store only what the user or agent actually
knows.

## Common Fields

```json
{
  "scope": "track",
  "decision_state": "committed",
  "source": "user_explicit",
  "confidence": 1.0,
  "role": "lead_vocal",
  "priority": "foreground",
  "notes": "Main emotional anchor; keep intelligible and present.",
  "mix_intent": "upfront, raw, not glossy",
  "composition_intent": "other parts should leave space",
  "sound_design_intent": "human, strained, intimate",
  "constraints": ["preserve_timing", "do_not_replace"],
  "references": [],
  "relationships": [],
  "options": []
}
```

## Scope

- `track`: one resolved track.
- `relationship`: multiple tracks working together.
- `section`: a song section.
- `project`: global production direction.

## Decision State

- `committed`: active instruction.
- `open`: valid creative alternatives exist; audition or ask before choosing.
- `hypothesis`: weak agent inference.
- `rejected`: historical note; do not use as active guidance.

## Open Harmony Example

```json
{
  "role": "harmony_vocal",
  "decision_state": "open",
  "priority": "undecided",
  "role_candidates": ["support_harmony", "ensemble_harmony"],
  "notes": "Could be tucked behind the lead or become a bigger ensemble part.",
  "decision_policy": "audition_before_commit",
  "options": [
    {
      "option_id": "tucked_support",
      "label": "Barely-there support",
      "role": "support_harmony",
      "priority": "background",
      "mix_intent": "felt more than heard"
    },
    {
      "option_id": "ensemble_harmony",
      "label": "Beatles-style ensemble",
      "role": "ensemble_harmony",
      "priority": "co_foreground",
      "mix_intent": "blend as one vocal stack"
    }
  ]
}
```

## Reference Example

Use references as production direction, not as claims of analysis.

```json
{
  "scope": "relationship",
  "references": [
    {
      "scope": "relationship",
      "artist": "Arcade Fire",
      "song": "The Suburbs",
      "section": "verse",
      "part": "drums+bass+piano",
      "borrow": ["restrained pulse", "worn low-mid edge", "ensemble glue"],
      "avoid": ["modern sub-heavy polish", "busy fills"]
    }
  ]
}
```

## Relationship Example

```json
{
  "relationships": [
    {
      "type": "plays_off",
      "target": {"track_name": "vox1"},
      "notes": "Lead line should answer the vocal, not compete with it."
    }
  ]
}
```

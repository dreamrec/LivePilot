# Memory Promotion Reference

Memory promotion saves successful production moves to persistent storage for recall in future sessions.

## Promotion Flow

1. A move scores > 0.7 in evaluation
2. Call `get_promotion_candidates` to list all eligible moves from this session
3. Present the candidate to the user with score and description
4. If the user confirms, call `memory_learn(type, data)` to save
5. The technique is now available via `memory_recall` in future sessions

## Promotion Candidates

`get_promotion_candidates` returns moves that meet all criteria:

- Evaluation score > 0.7
- `keep_change` was `true`
- The move has not already been promoted
- The move does not conflict with any anti-preference

Response format:
```json
{
  "candidates": [
    {
      "action_id": "act_001",
      "move_type": "eq_cut",
      "score": 0.85,
      "goal": "reduce masking between bass and kick",
      "parameters": {
        "track": "Bass",
        "device": "EQ Eight",
        "band": 3,
        "frequency": 250,
        "gain_db": -4.5,
        "q": 2.0
      },
      "explanation": "4.5 dB cut at 250 Hz on bass cleared kick presence without losing bass warmth"
    }
  ]
}
```

## Memory Types

When calling `memory_learn`, specify the type:

- `mix_template` — mixing techniques (EQ curves, compression settings, gain staging recipes)
- `sound_design` — patch design moves (modulation settings, filter configurations, oscillator tuning)
- `composition` — structural techniques (transition patterns, arrangement gestures, motif transformations)
- `automation` — automation curves and recipes
- `performance` — live performance patterns (scene orderings, safe macro ranges)

## Anti-Preferences

Anti-preferences are the inverse of promotion — they record moves the user explicitly rejected.

### Recording

Call `record_anti_preference(dimension, direction)` when:
- The user says "I hate that", "never do that again", "that's wrong"
- A move is undone and the user expresses displeasure (not just neutral undo)
- The user explicitly states a preference against a technique

### Checking

Call `get_anti_preferences` before suggesting any move. The response lists all recorded anti-preferences with descriptions and creation dates.

### Format
```json
{
  "anti_preferences": [
    {
      "id": "ap_001",
      "description": "Never boost above 10 kHz on vocals — user finds it harsh",
      "created": "2026-04-08T14:30:00Z"
    },
    {
      "id": "ap_002",
      "description": "No sidechain compression on pads — user prefers volume automation for ducking",
      "created": "2026-04-09T09:15:00Z"
    }
  ]
}
```

### Rules

1. Always check anti-preferences before planning any move
2. If a planned move matches an anti-preference, skip it and choose an alternative
3. Anti-preferences are permanent until the user explicitly asks to remove one
4. When skipping a move due to anti-preference, tell the user: "Skipping [move] because you previously indicated [anti-preference]."

## Promotion Best Practices

1. **Do not auto-promote.** Always ask: "That scored [score] — want me to save this technique?"
2. **Include context in the saved data.** A raw parameter value without context (genre, source material, goal) is less useful on recall.
3. **Group related moves.** If three EQ cuts together solved a masking problem, save them as one technique, not three.
4. **Tag with genre and role.** A bass EQ technique for house music may not apply to jazz. Include tags for future filtering.
5. **Review periodically.** Suggest `memory_list` to the user occasionally to prune outdated techniques.

## Recall Integration

When starting a new production task:

1. Call `memory_recall(type, query)` to find relevant past techniques
2. Present matches with their past scores: "I found a similar technique from a past session (scored 0.85). Want me to try it here?"
3. If the user agrees, apply the recalled technique and evaluate as normal
4. If the recalled technique scores lower in the new context, note this — context sensitivity means not all techniques transfer

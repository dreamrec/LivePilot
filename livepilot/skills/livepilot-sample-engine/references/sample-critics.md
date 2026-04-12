# Sample Critics — Scoring Reference

## Key Fit Critic

Uses circle-of-fifths distance between sample key and song key.

| Distance | Score | Relationship | Action |
|----------|-------|-------------|--------|
| 0 fifths | 1.0 | Same key | Load directly |
| 1 fifth | 0.85 | Relative major/minor, dominant/subdominant | Layer with care |
| 2 fifths | 0.7 | Closely related | Works for most intents |
| 3 fifths | 0.55 | Moderately distant | Transpose or use as texture |
| 4 fifths | 0.4 | Distant | Heavy filtering needed |
| 5+ fifths | 0.25-0.3 | Chromatic clash | Intentional tension only |
| Unknown | 0.0 | Key not detected | Verify by ear |

**Weight adjustment:** For "texture" intent, key_fit weight drops 50% (pitch matters less).

## Tempo Fit Critic

Compares sample BPM against session tempo including half/double time relationships.

| Deviation | Score | Action |
|-----------|-------|--------|
| <1% | 1.0 | Exact match, no warping |
| <2% | 0.95 | Near-exact, minimal warp |
| <5% | 0.8 | Light warp, quality preserved |
| <10% | 0.6 | Moderate warp, choose mode carefully |
| <15% | 0.4 | Significant — use Texture mode for ambient |
| >15% | 0.2 | Extreme — texture use only |
| Half time | 0.9 | Set warp to half-time |
| Double time | 0.9 | Set warp to double-time |
| Unknown | 0.0 | Estimate from onsets or verify |

## Frequency Fit Critic

Requires M4L bridge spectral data. Without it, returns neutral 0.5.

| Situation | Score | Action |
|-----------|-------|--------|
| Fills empty frequency gap | 1.0 | Perfect complement |
| Partial overlap, manageable | 0.7 | Suggest EQ carving |
| Heavy masking | 0.3 | Aggressive filtering or texture use |
| Full spectrum into dense mix | 0.1 | Transformation source only |

## Role Fit Critic

Cross-references material_type against existing track names/roles.

| Situation | Score | Action |
|-----------|-------|--------|
| Fills missing role | 1.0 | "No percussion texture — this fills the gap" |
| Complements existing | 0.7 | "Adds variety to palette" |
| Redundant | 0.3 | "Already 3 synth layers — use as texture" |

## Vibe Fit Critic

Uses TasteGraph when evidence exists (>0 entries). Otherwise neutral 0.5.

Compares brightness, density, complexity of sample against user's taste profile.

## Intent Fit Critic

Compatibility matrix — how well the material serves the stated intent:

| Material \ Intent | rhythm | texture | layer | melody | vocal | atmosphere | transform |
|-------------------|--------|---------|-------|--------|-------|------------|-----------|
| vocal | 0.6 | 0.6 | 0.8 | 0.9 | 1.0 | 0.5 | 0.9 |
| drum_loop | 1.0 | 0.5 | 0.6 | 0.2 | — | 0.3 | 0.9 |
| instrument_loop | 0.5 | 0.6 | 1.0 | 1.0 | 0.3 | 0.5 | 0.9 |
| one_shot | 0.9 | 0.4 | 0.3 | 0.5 | — | 0.3 | 0.8 |
| texture | 0.2 | 1.0 | 0.7 | 0.3 | 0.2 | 1.0 | 0.8 |
| foley | 0.5 | 0.8 | 0.4 | — | — | 0.9 | 0.8 |
| fx | 0.3 | 0.7 | 0.3 | — | — | 0.8 | 0.7 |

## Composite Score

Default weights:
```
overall = key_fit(0.20) + tempo_fit(0.20) + frequency_fit(0.20)
        + role_fit(0.15) + vibe_fit(0.10) + intent_fit(0.15)
```

Weights shift by intent:
- **texture/atmosphere:** key_fit 0.10, tempo_fit 0.10, frequency_fit 0.25
- **rhythm:** tempo_fit 0.25, key_fit 0.10
- **melody:** key_fit 0.30, intent_fit 0.20

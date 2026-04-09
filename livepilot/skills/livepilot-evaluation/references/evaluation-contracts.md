# Evaluation Contracts Reference

Every evaluator returns the same base contract. Engine-specific evaluators extend it with additional fields.

## Base Evaluation Contract

Returned by `evaluate_move`:

```json
{
  "keep_change": true,
  "score": 0.72,
  "goal_progress": 0.6,
  "collateral_damage": [],
  "explanation": "Filter cut at 250 Hz reduced masking by 4 dB without affecting bass body.",
  "before_metrics": {
    "master_rms_db": -12.4,
    "master_peak_db": -3.2,
    "spectrum": [...]
  },
  "after_metrics": {
    "master_rms_db": -12.8,
    "master_peak_db": -3.5,
    "spectrum": [...]
  }
}
```

### Field Definitions

- **keep_change** (bool): `true` if the change improved the target without unacceptable regression. `false` if the change should be undone.
- **score** (float 0.0-1.0): 0.0 = catastrophic regression, 0.5 = neutral (no change), 1.0 = perfect improvement. Scores below 0.4 trigger automatic undo recommendation.
- **goal_progress** (float 0.0-1.0): how much of the stated goal has been achieved. 1.0 means the goal is fully met. Use this to decide whether to continue iterating.
- **collateral_damage** (list of strings): side effects that got worse. Empty list means no regressions detected. Examples: "bass lost 2 dB of body", "stereo width narrowed by 15%".
- **explanation** (string): one-sentence human-readable summary of the judgment. Always report this to the user.

## Mix Evaluation Contract

Returned by `evaluate_mix_move`, extends base with:

```json
{
  "targets": {
    "reduce_masking": { "before": 0.72, "after": 0.35, "improved": true },
    "maintain_headroom": { "before": -3.2, "after": -3.5, "ok": true }
  },
  "protect": {
    "bass_body": { "before": -14.2, "after": -14.8, "ok": true },
    "vocal_presence": { "before": -8.1, "after": -8.0, "ok": true }
  },
  "spectral_delta_db": {
    "sub": 0.1, "low": -0.3, "low_mid": -2.1,
    "mid": 0.2, "high_mid": 0.1, "high": 0.0
  }
}
```

- **targets**: what the move aimed to improve, with before/after measurements
- **protect**: what must not get worse, with tolerance checking
- **spectral_delta_db**: per-band change in spectral energy

## Composition Evaluation Contract

Returned by `evaluate_composition_move`, extends base with:

```json
{
  "structural_coherence": 0.85,
  "thematic_continuity": 0.78,
  "energy_delta": 0.15,
  "transition_smoothness": 0.82,
  "note_count_delta": 12
}
```

- **structural_coherence**: how well the change fits the overall form
- **thematic_continuity**: whether existing motifs are maintained or developed (not broken)
- **energy_delta**: change in section energy level
- **transition_smoothness**: quality of section boundaries after the change

## Fabric Evaluation Contract

Returned by `evaluate_with_fabric`, extends base with:

```json
{
  "taste_alignment": 0.88,
  "anti_preference_violations": [],
  "similar_past_moves": [
    { "memory_id": "mix_001", "similarity": 0.91, "past_score": 0.85 }
  ],
  "novelty_score": 0.3
}
```

- **taste_alignment**: how well the move matches the user's saved taste profile
- **anti_preference_violations**: list of anti-preferences this move conflicts with (should be empty)
- **similar_past_moves**: techniques from memory that resemble this move, with their past scores
- **novelty_score**: how different this move is from past approaches (high = novel, low = familiar)

## Scoring Thresholds

| Score Range | Interpretation | Action |
|------------|---------------|--------|
| 0.0 - 0.3 | Significant regression | Auto-undo, explain damage |
| 0.3 - 0.45 | Mild regression | Undo recommended, ask user |
| 0.45 - 0.55 | Neutral / no effect | Keep but note it had no impact |
| 0.55 - 0.7 | Mild improvement | Keep, continue iterating |
| 0.7 - 0.85 | Clear improvement | Keep, suggest memory promotion |
| 0.85 - 1.0 | Excellent improvement | Keep, strongly suggest promotion |

## Collateral Damage Categories

Common side effects to check for:

- **bass_body_loss**: EQ cuts in the low-mid range reduced bass warmth
- **stereo_narrowing**: mono compatibility fix reduced perceived width
- **headroom_reduction**: boost increased master peak level
- **transient_loss**: compression removed punch from drums
- **vocal_masking**: frequency boost created new masking with vocal track
- **phase_issue**: stereo manipulation introduced phase cancellation

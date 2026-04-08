# Transition Engine v1

Status: proposal

Audience: composition, automation, arrangement, evaluation, and taste owners

Purpose: define the specialized subsystem responsible for arrivals, exits, handoffs, and other section-boundary intelligence.

## 1. Why This Deserves A Dedicated Plan

Transitions are where many tracks stop sounding like loops and start sounding like records.

They sit at the intersection of:

- arrangement
- automation
- FX usage
- harmonic pacing
- subtraction
- narrative payoff

A weak transition can make otherwise solid material feel amateur.

## 2. Product Role

The user should be able to say:

- "make this drop feel earned"
- "smooth the handoff into the verse"
- "make this transition more dramatic but not cheesy"

Internally, the engine should understand:

- outgoing role collapse
- incoming role reveal
- tension preparation
- release/payoff
- boundary clarity

## 3. Core Model

Transition Engine v1 should model each transition as:

- `boundary`
- `lead_in_window`
- `arrival_window`
- `departing_roles`
- `arriving_roles`
- `gesture_candidates`
- `payoff_strength`

## 4. Transition Archetypes

Start with a curated library:

- subtractive inhale
- fill and reset
- tail throw
- width bloom
- harmonic suspend and release
- impact vacuum
- delayed foreground handoff

Each archetype should include:

- use case
- risk profile
- devices/tools
- verification cues

## 5. Critics v1

Implement:

- `boundary_clarity_critic`
- `payoff_critic`
- `overtelegraphing_critic`
- `energy_redirection_critic`
- `gesture_fit_critic`

## 6. Move Library v1

Move classes:

- subtractive transition setup
- one-bar gesture automation
- fill insertion/revision
- tail/send punctuation
- staged reveal on arrival

## 7. Data Contracts

```json
{
  "transition_candidate": {
    "boundary_start_bar": 15,
    "boundary_end_bar": 17,
    "from_section": "build",
    "to_section": "drop",
    "issues": ["weak_payoff", "flat_lead_in"],
    "recommended_moves": ["subtractive_inhale", "delay_throw", "arrival_width_bloom"]
  }
}
```

## 8. Evaluation

Score:

- arrival clarity
- energy redirection
- payoff strength
- identity preservation
- cliche risk

Transition Engine must avoid "more FX = better transition."

## 9. Integration

This engine should start as a Composition Engine specialization.

Split it into a standalone runtime surface only after:

- transition critics are stable
- gesture evaluation is reliable
- users are clearly invoking transition-specific goals

## 10. Build Order

1. Add transition boundary model to composition state.
2. Implement critics.
3. Implement gesture/archetype library.
4. Add evaluation hooks.
5. Promote into a dedicated engine if usage justifies it.

## 11. Exit Criteria

Transition Engine v1 is done when:

- the system can identify weak boundaries
- it can improve a transition with small, musical gestures
- the evaluator can distinguish stronger payoff from superficial FX clutter

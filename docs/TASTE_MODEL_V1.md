# LivePilot Taste Model v1

Status: proposal

Audience: product, runtime, memory, planning, and personalization owners

Purpose: define the first implementation of a real personalization layer for LivePilot.

Taste Model is the system that answers:

- what this user tends to like
- what this user tends to reject
- how bold the system should be
- which ideas should be ranked up or down

## Related Materials

- [LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md](./LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md)
- [LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md](./LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md)
- [REFERENCE_ENGINE_V1.md](./REFERENCE_ENGINE_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)

## 1. Mission

Taste Model v1 should make LivePilot feel more like a long-term collaborator than a generic assistant.

## 2. Non-Goals

Taste Model v1 should not:

- lock the user into one style
- overwrite explicit instructions
- make planning fully deterministic

## 3. Core Outputs

Taste Model should provide:

- ranking priors
- caution flags
- anti-pattern memory
- preferred intensity levels
- preferred tactic families

## 4. Core Inputs

- accepted changes
- undone changes
- explicit user feedback
- repeated references
- saved directions
- project-level patterns

## 5. Taste Dimensions

At minimum, v1 should track:

- transition boldness
- automation density preference
- density tolerance
- harmonic boldness
- width preference
- dryness vs wash preference
- native vs plugin-heavy preference

## 6. Anti-Memory

Anti-memory is required, not optional.

Examples:

- user dislikes obvious risers
- user dislikes overwide choruses
- user dislikes bright top-end hype

This should affect planning immediately.

## 7. Storage Evolution

Current memory is technique-oriented.

Taste Model v1 should evolve memory toward:

- `outcome`
- `preference`
- `anti_preference`
- `style_tactic`

## 8. Suggested Modules

- `taste_model/profile.py`
- `taste_model/updater.py`
- `taste_model/ranker.py`
- `taste_model/anti_memory.py`

## 9. Acceptance Tests

- repeated dislikes reduce future ranking of similar moves
- explicit positive signals increase ranking of similar moves
- taste priors never override direct user commands

## 10. Exit Criteria

- planning is measurably more personalized after interaction history exists
- anti-memory is live and tested

## 11. Summary

Taste Model v1 is what turns LivePilot from "smart" into "yours."

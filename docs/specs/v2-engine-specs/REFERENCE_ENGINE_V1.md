# LivePilot Reference Engine v1

Status: proposal

Audience: product, runtime, reference, composition, mix, and research owners

Purpose: define the first implementation of LivePilot's reference-aware intelligence layer.

Reference Engine should translate references into useful, session-specific moves instead of vague comparison prose.

## Related Materials

- [LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md](./LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md)
- [LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md](./LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md)
- [MIX_ENGINE_V1.md](./MIX_ENGINE_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)
- [TASTE_MODEL_V1.md](./TASTE_MODEL_V1.md)

## 1. Mission

Reference Engine v1 should answer:

- how is the current project different from the reference in the ways that matter?
- which differences are actually relevant to the user's goal?
- what is the smallest change that moves us closer without flattening identity?

## 2. Inputs

Reference Engine should support:

- audio file references
- artist/style references
- user-described references
- project-internal section references

## 3. Non-Goals

Reference Engine v1 should not:

- blindly imitate references
- reduce all reference work to spectrum matching
- erase project identity

## 4. Core Objects

### ReferenceProfile

Stores:

- loudness posture
- spectral contour
- width/depth posture
- density arc
- section pacing
- transition tendencies
- harmonic character

### GapReport

Stores:

- relevant deltas
- irrelevant deltas
- identity-preserving warnings
- candidate tactics

### StyleTacticCard

Stores:

- style
- musical problem
- tactic
- why it matters
- likely engines to invoke

## 5. Comparison Domains

Reference Engine should compare across:

- spectral balance
- loudness contour
- density arc
- section pacing
- transition behavior
- width behavior
- harmonic color
- motif development density

## 6. Implementation Strategy

### Phase 1A

- support offline audio comparison using existing perception tooling
- build `ReferenceProfile` for audio refs

### Phase 1B

- support style references and tactic cards
- route differences into Composition and Mix engines

## 7. Existing Repo Touchpoints

- `mcp_server/tools/perception.py`
- `mcp_server/tools/_perception_engine.py`
- Project Brain section and role graphs
- Taste Model

## 8. Suggested Modules

- `reference_engine/models.py`
- `reference_engine/profile_builder.py`
- `reference_engine/gap_analyzer.py`
- `reference_engine/tactic_router.py`
- `reference_engine/evaluator.py`

## 9. Acceptance Tests

Scenarios:

- "make this feel more like X without copying it"
- "why is my chorus not landing like the reference?"
- "use this reference for width and pacing, not for harmony"

## 10. Exit Criteria

- reference work produces concrete, ranked, engine-routable moves
- the engine distinguishes relevant vs irrelevant differences

## 11. Summary

Reference Engine v1 should make references actionable, not ornamental.

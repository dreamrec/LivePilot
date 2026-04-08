# LivePilot Mix Engine v1

Status: proposal

Audience: product, runtime, mix-engine, perception, and evaluation owners

Purpose: define the first implementation of a dedicated mixing intelligence layer for LivePilot.

The Mix Engine should be the engine that turns requests like:

- "make this cleaner"
- "make it hit harder"
- "make the low end tighter"
- "make this wider but keep the center solid"
- "make it more glued"
- "make it more expensive"

into:

- explicit mix hypotheses
- ranked reversible actions
- measurable before/after evaluation

## Related Materials

- [LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md](./LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md)
- [LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md](./LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)
- [AGENT_OS_V1.md](./AGENT_OS_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)

## 1. Mission

Mix Engine v1 should improve sonic quality in a structured, low-regret way.

It should focus on:

- balance
- masking
- depth
- punch
- width
- cohesion
- translation
- preservation of identity

## 2. Non-Goals

Mix Engine v1 should not:

- pretend to be full mastering automation
- rebuild the mix from scratch
- use wide-scope moves by default
- replace user taste with generic polish

## 3. Core Internal State

Mix Engine v1 should maintain:

- `BalanceState`
- `MaskingMap`
- `DynamicsState`
- `StereoState`
- `DepthState`
- `BusState`
- `TranslationState`

## 4. BalanceState

Tracks:

- track level balance
- bus level balance
- rough role-weighted loudness balance

Inputs:

- track meters
- master RMS
- role graph
- track grouping

## 5. MaskingMap

Tracks:

- likely frequency collisions
- role collisions
- persistent low-mid congestion
- transient masking

Inputs:

- spectrum
- track roles
- arrangement density

## 6. DynamicsState

Tracks:

- crest factor
- likely over-compression
- transient loss risk
- bus flattening risk

## 7. StereoState

Tracks:

- center anchor integrity
- side activity
- likely phase/mono risks
- width distribution by section

## 8. DepthState

Tracks:

- send usage
- wet/dry balance
- foreground/background depth separation
- depth flattening risk

## 9. BusState

Tracks:

- drum bus condition
- music bus condition
- mix bus condition
- group cohesion opportunities

## 10. TranslationState

Tracks:

- mono survival
- low-end speaker translation risk
- harshness risk
- front-element presence risk

## 11. Critics

Mix Engine v1 should include these critics.

## 11.1 Balance Critic

Looks for:

- anchor elements too weak
- support layers too dominant
- unstable section-to-section balance

## 11.2 Masking Critic

Looks for:

- kick/bass overlap
- bass/chord low-mid congestion
- lead/vocal presence masking
- excessive broad-band stacking

## 11.3 Dynamics Critic

Looks for:

- flatness
- transient loss
- overlimited feel
- uncontrolled peaks

## 11.4 Stereo Critic

Looks for:

- center collapse risk
- underused width
- overwide support layers
- imbalanced side energy

## 11.5 Depth Critic

Looks for:

- no front/back separation
- constant ambience with no contrast
- excessive wash around focal elements

## 11.6 Translation Critic

Looks for:

- mono weakness
- low-end instability
- harshness that will exaggerate elsewhere

## 12. Move Library

Mix Engine should choose from explicit move classes.

### Track-level moves

- EQ correction
- transient shaping
- saturation adjustment
- width narrowing or widening
- send rebalance

### Bus-level moves

- bus compression
- glue saturation
- bus EQ contouring
- bus send shaping

### Master-safe moves

- gain staging
- subtle tonal correction
- stereo safety adjustments

## 13. Ranking Policy

Rank moves by:

- estimated goal impact
- risk to protected qualities
- scope size
- reversibility
- confidence
- taste fit

Prefer:

- smallest relevant move
- track-level before bus-level
- one variable at a time

## 14. Evaluation

Mix Engine v1 should use Evaluation Fabric and score:

- masking reduction
- punch change
- headroom condition
- stereo stability
- clarity preservation
- translation proxy improvement

## 15. Existing Repo Touchpoints

Minimum current integrations:

- `mcp_server/tools/analyzer.py`
- `mcp_server/tools/perception.py`
- `mcp_server/tools/automation.py`
- `mcp_server/tools/mixing.py`
- `mcp_server/tools/tracks.py`
- Project Brain role and device state

## 16. Suggested New Modules

- `mix_engine/models.py`
- `mix_engine/state_builder.py`
- `mix_engine/critics.py`
- `mix_engine/planner.py`
- `mix_engine/evaluator.py`
- `mix_engine/move_library.py`

## 17. Acceptance Tests

Scenario tests:

- "make the drums hit harder without losing clarity"
- "make this cleaner"
- "make this wider but keep kick/bass centered"
- "make this more glued without flattening transients"

## 18. Exit Criteria

Mix Engine v1 is done when:

- high-level mix requests route through explicit critics and move ranking
- measurable sonic changes are evaluated consistently
- the engine often produces keepable first or second moves

## 19. Summary

Mix Engine v1 should be the first strong sonic-specialist engine after Composition.

It will likely be one of the highest-value additions in the whole stack.

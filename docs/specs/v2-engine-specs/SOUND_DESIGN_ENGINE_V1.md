# Sound Design Engine v1

Status: proposal

Audience: sound-design, runtime, plugin-intelligence, research, and evaluation owners

Purpose: define the first concrete implementation plan for LivePilot's timbral and patch-level intelligence layer.

## 1. Product Role

Sound Design Engine should make LivePilot feel capable of real timbral authorship, not just parameter automation.

Externally, the user should be able to say:

- "make this synth feel more haunted"
- "give this bass more movement without losing weight"
- "make this patch more expensive"
- "design a wider, unstable layer that still folds to mono"

Internally, the system should:

- understand patch structure
- map language to timbral targets
- know what controls are relevant
- plan reversible timbral experiments
- evaluate audible outcome

## 2. Immediate Scope

v1 should focus on:

- timbral goal compilation
- patch structure modeling
- modulation design basics
- layer strategy suggestions
- plugin/device-specific tactic cards where available

v1 should not yet attempt:

- blind synthesis from zero in every plugin
- universal deep reverse engineering of opaque third-party devices
- complex AI-generated wavetable design

## 3. Core Concepts

### 3.1 Timbral Goal Vector

Translate language into sound dimensions such as:

- brightness
- warmth
- bite
- softness
- instability
- width
- texture density
- movement
- perceived cost/polish

### 3.2 Patch Model

Represent an instrument/effect chain as:

- source generators
- spectral shapers
- time-domain shapers
- modulation sources
- macro controls
- spatializers
- saturation/character blocks

### 3.3 Layer Strategy

Model how multiple layers divide labor:

- sub anchor
- body layer
- transient layer
- texture layer
- width layer

## 4. Module Layout

Suggested modules:

- `mcp_server/sound_design/models.py`
- `mcp_server/sound_design/goal_compiler.py`
- `mcp_server/sound_design/patch_model.py`
- `mcp_server/sound_design/modulation_planner.py`
- `mcp_server/sound_design/layer_planner.py`
- `mcp_server/sound_design/evaluator.py`

## 5. Data Contracts

```json
{
  "timbral_goal_vector": {
    "brightness": -0.15,
    "movement": 0.35,
    "width": 0.18,
    "protect": {
      "weight": 0.85,
      "mono_center": 0.8
    }
  }
}
```

```json
{
  "patch_model": {
    "track_id": 4,
    "device_chain": ["Wavetable", "Saturator", "Chorus"],
    "roles": ["lead", "width_layer"],
    "controllable_blocks": [
      "oscillator",
      "filter",
      "envelope",
      "lfo",
      "spatial"
    ],
    "opaque_blocks": []
  }
}
```

## 6. Critics v1

Start with:

- `static_timbre_critic`
- `weak_identity_critic`
- `masking_role_critic`
- `modulation_flatness_critic`
- `layer_overlap_critic`

## 7. Move Library v1

Initial move classes:

- source balance adjustment
- filter contour redesign
- envelope shape refinement
- subtle modulation injection
- spatial-role separation
- layer split/reassignment recommendation

## 8. Evaluation

Evaluation should combine:

- spectrum changes
- motion/novelty shifts
- role preservation
- mono robustness
- user taste fit

Sound Design Engine should never keep a move that makes the patch "more interesting" but destroys its musical role.

## 9. Research Integration

This engine is one of the biggest beneficiaries of targeted research.

Use research for:

- unfamiliar plugins
- device best-practice tactics
- style-specific timbral goals

Distill findings into plugin tactic cards, not raw notes.

## 10. Build Order

1. Implement timbral goal vector.
2. Build patch-model abstraction for native devices first.
3. Add critics and small move library.
4. Add evaluator.
5. Add plugin tactic-card hooks.

## 11. Exit Criteria

Sound Design Engine v1 is done when:

- it can handle common native-device timbral requests with structured reasoning
- it distinguishes patch identity from generic brightness/loudness changes
- it can propose layer roles instead of only parameter tweaks
- evaluation catches obvious timbral regressions

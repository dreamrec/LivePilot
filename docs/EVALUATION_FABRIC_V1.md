# Evaluation Fabric v1

Status: proposal

Audience: runtime, evaluation, engine, and testing owners

Purpose: define the shared evaluation subsystem that all future LivePilot engines should use.

The Evaluation Fabric is the system that answers:

- what changed
- whether it helped
- whether it hurt something important
- whether to keep or undo
- what should be remembered

This is one of the most important pieces of the future architecture.

## Related Materials

- [AGENT_OS_V1.md](./AGENT_OS_V1.md)
- [AGENT_OS_PHASE0_HARDENING_PLAN.md](./AGENT_OS_PHASE0_HARDENING_PLAN.md)
- [LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md](./LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md)
- [LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md](./LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)
- [COMPOSITION_ENGINE_V1_INTEGRATION_PLAN.md](./COMPOSITION_ENGINE_V1_INTEGRATION_PLAN.md)
- [ACTION_LEDGER_V1.md](./ACTION_LEDGER_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

## 1. Mission

Evaluation Fabric should provide a unified, explicit, reusable evaluation layer for all LivePilot engines.

It should support:

- online fast evaluation
- offline deeper evaluation
- engine-specific scoring
- keep/undo recommendations
- benchmark replay

Without it, every engine will invent its own incompatible scoring logic.

## 2. Non-Goals

Evaluation Fabric v1 should not:

- solve every musical judgment problem perfectly
- replace human artistic preference
- make all subjective goals measurable immediately

It should make evaluation:

- explicit
- structured
- safer
- more reusable

## 3. Architectural Role

Evaluation Fabric sits between:

- action execution
- memory writing
- user-facing keep/undo decisions

It should be used by:

- Agent OS Core
- Composition Engine
- Mix Engine
- Reference Engine
- Translation Engine
- later Sound Design and Transition engines

## 4. Core Responsibilities

1. normalize snapshots
2. derive features
3. run engine-specific scoring
4. enforce hard rules
5. produce explicit decision records
6. emit memory candidates

## 5. Layer Model

Evaluation Fabric should have five layers.

## 5.1 Snapshot Layer

Purpose:

- normalize inputs from analyzer, offline perception, symbolic tools, and project state

Examples:

- sonic snapshots
- phrase snapshots
- section snapshots
- reference snapshots

## 5.2 Feature Layer

Purpose:

- derive measurable features from normalized snapshots

Examples:

- crest factor
- low-mid congestion
- novelty delta
- section identity score
- transition sharpness score

## 5.3 Scoring Layer

Purpose:

- compute engine-specific scores

Examples:

- mix score
- composition score
- reference-gap score
- translation score

## 5.4 Policy Layer

Purpose:

- apply hard rules
- determine keep, undo, or defer

## 5.5 Logging Layer

Purpose:

- write evaluation records
- emit memory candidates
- support benchmark replay

## 6. Core Contracts

## 6.1 SonicSnapshot

```json
{
  "spectrum": {},
  "rms": 0.0,
  "peak": 0.0,
  "detected_key": null,
  "source": "analyzer",
  "age_ms": null
}
```

## 6.2 SectionSnapshot

```json
{
  "section_id": "sec_01",
  "energy_curve": [],
  "density_curve": [],
  "foreground_roles": [],
  "novelty_score": 0.0,
  "transition_potential": 0.0
}
```

## 6.3 EvaluationRequest

```json
{
  "engine": "mix",
  "goal": {},
  "before": {},
  "after": {},
  "protect": {},
  "context": {}
}
```

## 6.4 EvaluationResult

```json
{
  "engine": "mix",
  "score": 0.71,
  "decision_mode": "measured_keep",
  "keep_change": true,
  "goal_progress": 0.63,
  "collateral_damage": 0.08,
  "hard_rule_failures": [],
  "dimension_changes": {},
  "notes": []
}
```

## 7. Engine-Specific Evaluators

Evaluation Fabric v1 should support multiple evaluator types.

## 7.1 Mix Evaluator

Scores:

- masking reduction
- headroom health
- punch improvement
- low-end stability
- stereo coherence
- translation safety

## 7.2 Composition Evaluator

Scores:

- section identity
- phrase completion
- repetition fatigue reduction
- transition strength
- emotional direction

## 7.3 Reference Evaluator

Scores:

- gap reduction
- identity preservation
- overfitting risk

## 7.4 Translation Evaluator

Scores:

- mono compatibility
- low-end translation
- harshness risk
- vocal/front-element presence

## 8. Hard Rules

Every evaluator may have custom scoring, but hard-rule semantics must be consistent.

### Examples

- protected measurable damage -> force undo
- no measurable improvement in measured mode -> force undo
- unsupported high-risk action without verification data -> force defer or undo

## 9. Repo Modules

Suggested layout:

- `mcp_server/evaluation/contracts.py`
- `mcp_server/evaluation/snapshot_normalizer.py`
- `mcp_server/evaluation/feature_extractors.py`
- `mcp_server/evaluation/policy.py`
- `mcp_server/evaluation/mix_evaluator.py`
- `mcp_server/evaluation/composition_evaluator.py`
- `mcp_server/evaluation/reference_evaluator.py`
- `mcp_server/evaluation/translation_evaluator.py`
- `mcp_server/evaluation/logging.py`

## 10. Build Order

### Phase A

- canonical snapshot contracts
- normalizer
- policy refactor for current Agent OS evaluator

### Phase B

- feature extractors for existing measurable dimensions
- evaluation record model

### Phase C

- mix evaluator
- composition evaluator

### Phase D

- reference and translation evaluators

## 11. Tests

### Unit

- normalizers
- feature extractors
- hard-rule policies

### Scenario

- before/after mix improvements
- before/after arrangement changes
- reference gap reduction scenarios

### Regression

- evaluator outputs stay stable on fixed fixtures

## 12. Exit Criteria

Evaluation Fabric v1 is done when:

- current Agent OS evaluation is subsumed by the fabric or aligned to it
- one snapshot normalization path exists
- at least mix and composition evaluation paths are explicit
- decision outputs are structured and replayable

## 13. Summary

Evaluation Fabric is the backbone of trustworthy autonomy.

If LivePilot gets this right, every future engine becomes easier to build and safer to deploy.

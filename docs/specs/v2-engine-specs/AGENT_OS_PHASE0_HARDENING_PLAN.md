# Agent OS Phase 0 Hardening Plan

Status: proposal

Audience: runtime, MCP/server, agent, and test owners

Purpose: define the immediate implementation plan for hardening the current Agent OS v1 phase before additional engines are built on top of it.

This is not a long-range architecture doc.

It is a concrete stabilization plan for the current implementation surface centered on:

- [AGENT_OS_V1.md](./AGENT_OS_V1.md)
- [LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md](./LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md)
- `mcp_server/tools/_agent_os_engine.py`
- `mcp_server/tools/agent_os.py`
- `livepilot/agents/livepilot-producer/AGENT.md`

## 1. Why Phase 0 Exists

Agent OS v1 already introduced important structure:

- goal vectors
- world model
- critic loop
- evaluator
- prompt-level closed-loop behavior

That is the right direction.

But phase 1 architecture work must not proceed until the current core loop is internally consistent.

The current implementation has several high-risk issues:

- evaluator safety can be bypassed
- analyzer snapshots are not normalized consistently
- measurable/unmeasurable dimension reporting is inaccurate
- world model output overclaims what it actually fetches
- one dynamics heuristic is mathematically wrong

If these issues are left in place, every future engine will inherit false confidence and brittle interfaces.

## 2. Scope

Phase 0 should only do the following:

1. fix current safety and contract drift
2. unify snapshot and evaluator contracts
3. make the world model honest and useful
4. improve test coverage around the actual loop

Phase 0 should not:

- add new high-level engines
- redesign the whole prompt stack
- add open-ended autonomy
- expand the tool surface dramatically

## 3. Current Issues To Fix

## 3.1 Evaluator Safety Override

### Problem

Current behavior:

- protected measurable damage can be detected
- `keep_change` is set to `False`
- then an "all target dimensions unmeasurable" fallback can flip it back to `True`

This violates the stated hard-rule semantics.

### Desired Behavior

If a protected measurable dimension is violated beyond threshold:

- `keep_change` must remain `False`
- regardless of target measurability

### Implementation Change

Refactor `compute_evaluation_score()` so decision logic is ordered like:

1. collect measurable target deltas
2. collect protected-dimension drops
3. determine measurable availability
4. compute score
5. apply irreversible hard rules
6. apply unmeasurable fallback only when no hard rule has already failed

### Proposed Decision Logic

```text
if protection_violated:
    keep_change = False
elif measurable_count > 0 and measurable_delta <= 0:
    keep_change = False
elif score < threshold:
    keep_change = False
elif measurable_count == 0:
    keep_change = "defer"
else:
    keep_change = True
```

Important:

- `defer` may be represented as a bool plus explicit flag, but the semantic should be different from "safe to keep"

### Suggested Output Additions

Add:

- `decision_mode`: `measured_keep`, `measured_undo`, `defer_to_agent`
- `hard_rule_failures`: array

This makes evaluator output easier to reason about than only a boolean.

## 3.2 Snapshot Schema Mismatch

### Problem

Current analyzer tools naturally produce:

- `get_master_spectrum` -> `bands`
- `get_master_rms` -> `rms`, `peak`

But `evaluate_move()` expects snapshots shaped like:

```json
{
  "spectrum": {...},
  "rms": 0.6,
  "peak": 0.8
}
```

This means the closed loop silently degrades unless the agent manually reshapes payloads correctly.

### Desired Behavior

There should be one canonical snapshot schema used by:

- analyzer capture
- world model
- evaluation
- action ledger
- future evaluation fabric

### Implementation Change

Introduce a dedicated snapshot normalizer.

Suggested new module:

- `mcp_server/evaluation/snapshot_normalizer.py`

Responsibilities:

- accept raw analyzer outputs
- accept combined or partial payloads
- emit canonical `SonicSnapshot`

### Canonical Snapshot Contract

```json
{
  "spectrum": {
    "sub": 0.0,
    "low": 0.0,
    "low_mid": 0.0,
    "mid": 0.0,
    "high_mid": 0.0,
    "high": 0.0,
    "presence": 0.0,
    "air": 0.0
  },
  "rms": 0.0,
  "peak": 0.0,
  "detected_key": null,
  "age_ms": null,
  "source": "analyzer"
}
```

### Normalizer Inputs To Support

Accept:

- raw `get_master_spectrum` output
- raw `get_master_rms` output
- merged dicts using `bands`
- already-canonical snapshots

### API Options

Option A:

- keep `evaluate_move()` as-is but normalize inside it

Option B:

- add a new explicit tool such as `capture_sonic_snapshot`

Recommended:

- do both
- normalize defensively inside `evaluate_move()`
- add `capture_sonic_snapshot` as the preferred tool for agent usage

This removes prompt-level schema glue from the agent loop.

## 3.3 Measurability Registry Drift

### Problem

Some dimensions are currently advertised as measurable without implemented extractors.

Observed example:

- `width` is listed in measurable dimensions
- no `width` extractor exists in `_extract_dimension_value()`

### Desired Behavior

The system should never claim a dimension is measurable unless:

- there is an implemented extractor
- the extractor has tests
- the required inputs are documented

### Implementation Change

Replace the current loose `MEASURABLE_PROXIES` map with a stronger registry.

Suggested shape:

```python
DIMENSION_REGISTRY = {
    "weight": {"measurable": True, "extractor": "weight_v1", "requires": ["spectrum"]},
    "groove": {"measurable": False, "extractor": None, "requires": []},
}
```

### Rules

- `compile_goal_vector()` should derive measurable/unmeasurable dimensions from this registry
- evaluator should derive extractor availability from the same registry
- docs should not list a dimension as measurable by hand in multiple places

### Width Decision

For phase 0:

- either demote `width` to unmeasurable
- or implement a real width proxy

Recommended:

- demote for now unless a safe width extractor already exists in local offline/perception tooling

## 3.4 World Model Contract Drift

### Problem

`build_world_model()` currently documents more than it actually fetches.

Examples:

- track/device/plugin health implied but not fetched
- topology described more richly than current implementation supplies

### Desired Behavior

The world model should either:

- fetch the required state
- or narrow its contract immediately

### Implementation Change

Phase 0 should add a minimum-honest world model.

The current wrapper should fetch:

- `get_session_info`
- targeted `get_track_info` for active/visible/primary tracks or all tracks if cheap enough

If plugin health flags are exposed there, feed them through into the model.

### Recommended Two-Step Strategy

Step 1:

- make the current world model honest and complete within the current scope

Step 2:

- defer richer topology/device graphs to `Project Brain`

### Minimum Honest Output

- transport/session summary
- track names and lightweight role inference
- analyzer state
- plugin health flags when available
- critic results derived from actually fetched data

## 3.5 Dynamics Heuristic Math

### Problem

The current `dynamics_flat` heuristic computes crest factor incorrectly.

### Desired Behavior

Use standard log-domain crest-factor math.

### Implementation Change

Replace:

```python
crest_db = 20 * (peak / rms)
```

With:

```python
crest_db = 20 * log10(peak / rms)
```

### Additional Work

- recalibrate thresholds with realistic mix examples
- separate "too flat" from "too spiky" over time

### Suggested Thresholding

Phase 0 can keep this simple:

- `< 3 dB` -> likely too flat
- `3-6 dB` -> usable but potentially constrained
- `> 6 dB` -> healthy enough depending on genre

This can be engine-tuned later.

## 4. Implementation Plan

## 4.1 New/Updated Modules

### Update

- `mcp_server/tools/_agent_os_engine.py`
- `mcp_server/tools/agent_os.py`
- `livepilot/agents/livepilot-producer/AGENT.md`
- `tests/test_agent_os_engine.py`
- `tests/test_agent_os_tools.py`

### Add

- `mcp_server/evaluation/snapshot_normalizer.py`
- `tests/test_snapshot_normalizer.py`
- `tests/test_agent_os_e2e.py`

Optional:

- `mcp_server/evaluation/contracts.py`

## 4.2 Suggested Refactor Order

1. add canonical snapshot normalizer
2. wire `evaluate_move()` through the normalizer
3. fix measurable registry
4. fix evaluator hard-rule ordering
5. fix dynamics heuristic
6. tighten world-model fetching and contract
7. update prompt/doc references
8. add end-to-end tests

## 4.3 Tool Contract Changes

### `evaluate_move()`

Should accept:

- canonical snapshots
- analyzer raw payloads
- mixed partial payloads

Should return:

- `score`
- `keep_change`
- `decision_mode`
- `goal_progress`
- `collateral_damage`
- `measurable_delta`
- `hard_rule_failures`
- `dimension_changes`
- `notes`

### `build_world_model()`

Should return only fields that are actually populated.

If a future richer topology is desired, that belongs in a distinct phase and possibly a new tool.

## 5. Test Plan

## 5.1 Unit Tests

### Evaluator safety

Add tests for:

- protected measurable damage + unmeasurable targets
- score threshold failure
- negative measurable delta
- defer mode when targets are unmeasurable and protections are preserved

### Snapshot normalization

Add tests for:

- raw `bands` input
- raw `rms`/`peak` input
- combined raw payload
- already-canonical payload
- partial payloads with missing bands

### Measurability registry

Add tests for:

- compile and evaluator stay in sync
- dimensions flagged measurable always have extractors

## 5.2 End-To-End Tests

Create a new test slice that simulates:

1. compile goal
2. build before snapshot from raw analyzer outputs
3. run evaluation after change
4. verify hard-rule behavior

This should not require live Ableton.

### Example scenarios

- "make it hit harder" with actual measurable improvement
- "make it more alive" with unmeasurable target but protected weight collapse
- "make it wider" when width is unmeasurable
- "make it cleaner" with low-mid congestion reduction

## 5.3 Contract Tests

Add tests that ensure:

- prompt-expected capture flow matches real tool contracts
- no unsupported snapshot shape is silently treated as valid without normalization

## 6. Prompt And Docs Alignment

Phase 0 should update the producer-agent prompt to avoid any hidden contract mismatch.

### Required Prompt Changes

- teach the canonical snapshot path, not raw analyzer merge assumptions
- explain `defer_to_agent` behavior precisely
- avoid overstating what `build_world_model()` currently contains

### Suggested Producer Prompt Wording

Instead of:

- "call get_master_spectrum + get_master_rms and then evaluate_move"

Prefer:

- "capture a canonical sonic snapshot using the supported snapshot path, then evaluate"

If no new capture tool exists yet:

- at least document the normalization behavior explicitly

## 7. Acceptance Criteria

Phase 0 is complete when all of the following are true:

- protected measurable damage cannot be overridden by fallback logic
- `evaluate_move()` handles supported analyzer payloads robustly
- measurable-dimension reporting matches real extractors
- `width` is either implemented or honestly marked unmeasurable
- `build_world_model()` does not overclaim missing fields
- end-to-end tests cover the core loop
- producer prompt no longer teaches mismatched tool usage

## 8. Risks

### Risk: patching too much world-model richness too early

Mitigation:

- keep Phase 0 focused on honesty and consistency
- defer richer state to `Project Brain`

### Risk: snapshot logic gets duplicated across tools

Mitigation:

- one normalizer module
- one canonical snapshot contract

### Risk: evaluator becomes too complex too early

Mitigation:

- keep Phase 0 evaluator simple but correct
- deeper scoring belongs in Evaluation Fabric

## 9. Deliverables Summary

Phase 0 should produce:

- a safe evaluator
- a canonical snapshot contract
- synchronized measurable-dimension logic
- an honest world model
- stronger tests
- aligned docs and prompt policy

If this phase is done well, all future engines will inherit a much safer and cleaner base.

# Project Brain v1

Status: proposal

Audience: runtime, shared systems, agent, and evaluation owners

Purpose: define the first implementation of the shared long-lived state substrate for LivePilot.

`Project Brain` is the answer to:

"What does LivePilot know about the current project right now, and how does that knowledge persist across turns?"

This doc is a concrete implementation plan, not just a concept note.

## Related Materials

- [LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md](./LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md)
- [LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md](./LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md)
- [AGENT_OS_V1.md](./AGENT_OS_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)
- [AGENT_OS_PHASE0_HARDENING_PLAN.md](./AGENT_OS_PHASE0_HARDENING_PLAN.md)
- [CAPABILITY_STATE_V1.md](./CAPABILITY_STATE_V1.md)
- [ACTION_LEDGER_V1.md](./ACTION_LEDGER_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)

## 1. Mission

Project Brain should provide one coherent, inspectable, updateable representation of the current LivePilot project state.

It should unify:

- session structure
- arrangement structure
- role understanding
- device and routing awareness
- automation awareness
- active issues and opportunities
- capabilities and uncertainty
- recent actions

Without Project Brain, each engine will keep rebuilding partial state from scratch and drifting out of sync.

## 2. Non-Goals

Project Brain v1 should not:

- be a full database-backed knowledge platform yet
- store arbitrary raw audio blobs
- replace the action ledger
- replace memory or tactic cards
- attempt fully autonomous reasoning on its own

It is a shared state substrate, not a second agent.

## 3. Core Responsibilities

Project Brain v1 should:

1. maintain a canonical project snapshot
2. support incremental updates after actions
3. expose subgraphs to engines
4. track confidence and freshness
5. remain serializable and debuggable

## 4. Design Principles

### 4.1 Explicit Graphs

State should be divided into explicit subgraphs rather than one giant nested blob.

### 4.2 Freshness Matters

Every major component should track:

- when it was built
- what it was built from
- whether it is stale

### 4.3 Partial Updates Beat Full Rebuilds

The system should support refreshing:

- only the changed tracks
- only the changed section
- only the changed automation map

instead of rebuilding everything after every move.

### 4.4 Confidence Is First-Class

Every important inference should include:

- confidence
- evidence
- provenance

## 5. Core Subgraphs

Project Brain v1 should ship with five required subgraphs.

## 5.1 SessionGraph

The `SessionGraph` is the physical/session topology.

It should store:

- track list
- return tracks
- group relationships
- scene list
- device list by track
- routing and sends
- master state

### SessionGraph node types

- `TrackNode`
- `ReturnNode`
- `SceneNode`
- `DeviceNode`
- `RouteEdge`

## 5.2 ArrangementGraph

The `ArrangementGraph` is the time-structure layer.

It should store:

- arrangement clips
- inferred sections
- phrases
- cue points
- section boundaries
- transition boundaries

### ArrangementGraph node types

- `SectionNode`
- `PhraseNode`
- `BoundaryNode`
- `ClipSpanNode`

## 5.3 RoleGraph

The `RoleGraph` maps musical functions to tracks and sections.

It should store:

- global role guesses
- section-specific role assignments
- foreground/background status
- salience ranking

Role examples:

- kick
- bass anchor
- lead
- harmony bed
- rhythmic punctuation
- texture wash
- transition fx

## 5.4 AutomationGraph

The `AutomationGraph` stores automation presence and gesture density.

It should store:

- which parameters are automated
- automation density by section
- conflict regions
- likely gesture peaks

## 5.5 CapabilityGraph

The `CapabilityGraph` should live inside Project Brain even if it is also owned conceptually by a separate capability subsystem.

It should store:

- analyzer status
- FluCoMa status
- arrangement automation limitations
- plugin opacity/health
- reference availability
- research provider availability

## 6. Data Model

## 6.1 ProjectState

```json
{
  "project_id": "current",
  "revision": 12,
  "created_at": "2026-04-08T00:00:00Z",
  "updated_at": "2026-04-08T00:04:12Z",
  "session_graph": {},
  "arrangement_graph": {},
  "role_graph": {},
  "automation_graph": {},
  "capability_graph": {},
  "freshness": {},
  "confidence": {},
  "active_issues": [],
  "recent_action_ids": []
}
```

## 6.2 Freshness Model

Every subgraph should have:

```json
{
  "built_at": "2026-04-08T00:04:12Z",
  "source_revision": 12,
  "stale": false,
  "stale_reason": null
}
```

## 6.3 Confidence Model

Each inference-bearing graph should expose confidence summaries:

```json
{
  "role_graph": {
    "overall": 0.74,
    "low_confidence_nodes": ["track_7"]
  }
}
```

## 7. Update Model

Project Brain should support three update styles.

### 7.1 Full Rebuild

Use when:

- session first loads
- state is clearly stale
- large unknown edits occurred externally

### 7.2 Scoped Refresh

Use when:

- one track changed
- one section changed
- one automation region changed

### 7.3 Inference Patch

Use when:

- a higher engine derives new role or section understanding without direct session mutation

## 8. Build Pipeline

The initial Project Brain build should run in this order:

1. session graph
2. capability graph
3. arrangement graph
4. role graph
5. automation graph
6. issue summaries

This order matters because later graphs depend on earlier ones.

## 9. Repo Modules

Suggested module layout:

- `mcp_server/project_brain/__init__.py`
- `mcp_server/project_brain/models.py`
- `mcp_server/project_brain/builder.py`
- `mcp_server/project_brain/session_graph.py`
- `mcp_server/project_brain/arrangement_graph.py`
- `mcp_server/project_brain/role_graph.py`
- `mcp_server/project_brain/automation_graph.py`
- `mcp_server/project_brain/capability_graph.py`
- `mcp_server/project_brain/freshness.py`
- `mcp_server/project_brain/store.py`

## 10. Data Sources

Minimum v1 inputs:

- `get_session_info`
- `get_track_info`
- `get_arrangement_clips`
- `get_cue_points`
- `get_clip_automation`
- `get_automation_state`
- `get_master_spectrum`
- `get_master_rms`
- memory/taste metadata as needed

## 11. Storage Strategy

Project Brain v1 should start as in-memory state with serialization support.

### 11.1 Why In-Memory First

- simpler
- lower latency
- easier debugging
- easier to evolve schema

### 11.2 Persistence

Optional v1 persistence:

- lightweight JSON snapshot under `~/.livepilot/project_state/`

Not required for first delivery, but serialization should be supported from day one.

## 12. Integration Points

Project Brain should be read by:

- Agent OS Core
- Composition Engine
- Mix Engine
- Reference Engine
- Taste Model
- Transition Engine

Project Brain should be updated by:

- Conductor runtime
- post-action refresh hooks
- capability refresh hooks

## 13. API Surface

Suggested internal API:

- `build_project_state(ctx) -> ProjectState`
- `refresh_tracks(project_state, track_indices) -> ProjectState`
- `refresh_arrangement(project_state) -> ProjectState`
- `apply_inference_patch(project_state, patch) -> ProjectState`
- `serialize_project_state(project_state) -> dict`

## 14. Acceptance Tests

### Build tests

- full build from a representative session fixture
- missing analyzer still produces valid capability graph
- arrangement-less session still builds

### Refresh tests

- track-only refresh updates only targeted areas
- automation refresh updates automation graph without full rebuild

### Inference tests

- role graph can store low-confidence and high-confidence nodes
- section graph supports unknown section type cleanly

## 15. Exit Criteria

Project Brain v1 is done when:

- there is one canonical project state object
- engines stop rebuilding duplicate partial state ad hoc
- state supports scoped refresh
- freshness and confidence are represented explicitly
- the object is serializable and test-covered

## 16. Risks

### Risk: overfitting Project Brain to one engine

Mitigation:

- keep graphs engine-neutral

### Risk: state explosion

Mitigation:

- keep v1 focused on essential graphs
- defer exotic derived features to engine-local layers

### Risk: stale state confusion

Mitigation:

- freshness metadata is mandatory

## 17. Summary

Project Brain v1 is the shared substrate that makes every future engine cheaper, safer, and more coherent.

Without it, LivePilot becomes a pile of smart subsystems.

With it, LivePilot becomes a system.

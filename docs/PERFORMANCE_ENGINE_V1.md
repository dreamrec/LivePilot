# Performance Engine v1

Status: proposal

Audience: live-set, runtime, scene-control, latency, and safety owners

Purpose: define the subsystem that adapts LivePilot for live performance and improvisational session control.

## 1. Product Role

Performance Engine should make LivePilot useful during live playback and scene-based work, not just in production/edit mode.

It should help with:

- scene energy steering
- safe live transitions
- macro recommendations
- low-latency improvisational variation
- performance-safe mutation policies

## 2. Design Constraints

Performance mode has fundamentally different constraints:

- lower latency tolerance
- lower failure tolerance
- much tighter mutation safety
- stronger need for deterministic behavior

## 3. Capability Requirements

Performance Engine must depend on Capability State.

If transport, analyzer, or bridge health is unstable, it should degrade to:

- advisory-only
- read-only
- scene suggestion only

## 4. Core Concepts

- `scene_role`
- `energy_window`
- `live_safe_move`
- `macro_surface`
- `handoff_plan`

## 5. Move Classes

Initial safe classes:

- scene launch suggestions
- send/macro nudges
- filter sweeps within bounded ranges
- low-risk transition cues
- temporary texture layer mutes/unmutes

Avoid in v1:

- destructive editing
- device-chain surgery
- large-scale arrangement mutations

## 6. Module Layout

- `mcp_server/performance/models.py`
- `mcp_server/performance/safety.py`
- `mcp_server/performance/planner.py`
- `mcp_server/performance/scene_logic.py`

## 7. Evaluation

Performance evaluation is lighter-weight.

Score:

- latency safety
- energy-direction success
- transition continuity
- recoverability

## 8. Build Order

1. Define performance-safe capability gates.
2. Implement live-safe move classes.
3. Add scene-role and energy-window logic.
4. Add advisory summaries.

## 9. Exit Criteria

Performance Engine v1 is done when:

- the system can operate in a clearly bounded live-safe mode
- unsafe edit classes are excluded automatically
- the user can get meaningful scene and transition help without risking the set

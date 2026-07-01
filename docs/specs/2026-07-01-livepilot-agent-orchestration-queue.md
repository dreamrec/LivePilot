# LivePilot Agent Orchestration Queue

Status: Draft
Date: 2026-07-01

## Summary

LivePilot should support multiple specialist agents working on the same Ableton project without letting them fight over Ableton's shared mutable state. The core model is parallel analysis with serialized DAW execution.

Agents can analyze a frozen project snapshot in parallel, submit proposals, and ask for auditions. A single conductor/broker owns the Ableton write path and executes transport, audition, and mutation jobs through explicit queues.

This keeps the workflow fast where parallelism is safe, and deterministic where Ableton requires a single writer.

## Problem

The current LivePilot stack has useful agentic primitives: `get_session_kernel`, Project Brain, Song Brain, Session Continuity, Action Ledger, Experiment, Preview Studio, cockpit focus/context, and semantic moves. These help one agent reason well.

They do not yet provide a coordination layer for several agents working at once. The missing pieces are:

- Durable task/proposal objects.
- Track, layer, section, transport, and master-bus leases.
- A serialized executor for Ableton mutation and playback jobs.
- Stale-snapshot detection.
- Conflict reporting when two agents want the same target.
- Cockpit visibility into queued work, auditions, and applied decisions.

Without this, parallel agents could overwrite solo/mute state, move the transport while another agent is reading meters, apply plugin/device changes to the same track, or evaluate a stale version of the project.

## Goals

- Let multiple agents analyze the same project concurrently.
- Keep all Ableton writes behind one conductor-owned execution path.
- Batch plugin loads, parameter changes, clip edits, and audition setup into larger jobs to reduce round trips.
- Queue transport-dependent work so playback, loop selection, meter reads, and captures happen in the intended section.
- Preserve the human cockpit as the source of current intent: target layer, target section, brief, guardrails, audition count, and desired output mode.
- Make auditions DAW-visible when the user asks to listen to variants.
- Provide enough state for Codex to answer: what is queued, what is running, what changed, what failed, and what needs a human decision.

## Non-Goals

- No simultaneous mutation of Ableton from multiple agents.
- No distributed scheduler in the first version.
- No attempt to make Ableton transport multi-tenant.
- No automatic application of high-risk creative proposals without a conductor decision.
- No replacement for existing LivePilot tools; this wraps and coordinates them.

## Current Constraints

- The Remote Script accepts one TCP client at a time. The MCP server should remain the only Ableton client.
- The Live set has shared global state: transport position, loop brace, record state, Automation Arm, solo/mute, Back to Arrangement, and selected tracks.
- M4L bridge commands are serialized at the bridge layer and should not be treated as concurrently safe.
- Analyzer/meter reads are only meaningful when playback is in the intended section and solo/mute state is known.
- Cockpit context is project-scoped and should remain the user's primary pointing surface.

## Architecture

```text
User brief / cockpit context
        |
        v
Snapshot service
        |
        +--> Mix agent analysis
        +--> Arrangement agent analysis
        +--> Sound-design agent analysis
        +--> Vocal agent analysis
        |
        v
Proposal store
        |
        v
Conductor
        |
        +--> Offline analysis queue     parallel-safe
        +--> Playback/audition queue    serialized transport
        +--> Mutation queue             serialized writer
        |
        v
Ableton via existing LivePilot MCP tools
        |
        v
Verification + action ledger + cockpit update
```

## Lanes

### Snapshot Lane

Captures a project snapshot once for a user brief. The snapshot should include:

- `get_session_kernel`
- current cockpit production context
- agent focus
- layer groups
- section map
- track annotations / track intent map
- relevant project brain or song brain summaries
- optional recent action ledger

Agents should reason from this immutable snapshot instead of each repeatedly querying Ableton.

### Offline Analysis Lane

Runs in parallel when it only touches files or immutable snapshots.

Examples:

- Analyze a rendered section for LUFS, crest factor, spectrum, onset density, or masking.
- Compare MIDI note overlap between candidate layer tracks.
- Inspect track/device metadata.
- Draft alternative plans.
- Review another agent's proposal.

### Playback / Audition Queue

Serialized because it touches shared transport and monitoring state.

Examples:

- Set loop to a section.
- Clear Back to Arrangement.
- Solo or mute a target layer for meter capture.
- Render or capture a section.
- Play a user-selected audition.
- Run a looped listening verification.

### Mutation Queue

Serialized because it writes to Ableton.

Examples:

- Duplicate a track.
- Create visible `AUD A/B/C` audition lanes.
- Load plugins/devices.
- Batch-set parameters.
- Edit MIDI notes or clips.
- Record automation.
- Commit a selected audition.

The queue entry should contain a whole compiled plan, not one job per knob turn.

### Review / Decision Lane

Does not touch Ableton. Presents proposals and results to the human or conductor.

Examples:

- Rank three proposed ways to make a guitar pop out.
- Ask whether a rejected track should remain ignored.
- Summarize why an audition failed.
- Convert a user-selected winner into a mutation job.

## Core Objects

### Orchestration Snapshot

```json
{
  "snapshot_id": "snap_...",
  "project_id": "project_...",
  "project_revision": 42,
  "created_at_ms": 0,
  "brief": {
    "text": "make the intro handoff guitar pop out",
    "workflow_mode": "audition",
    "target_mode": "layer",
    "target_layer": "intro_handoff",
    "section": "intro",
    "audition_count": 3
  },
  "session_kernel": {},
  "cockpit_context": {},
  "section_map": [],
  "layer_groups": [],
  "track_intent_map": {}
}
```

### Agent Task

```json
{
  "task_id": "task_...",
  "snapshot_id": "snap_...",
  "agent_role": "mix | arrangement | sound_design | vocal | reviewer",
  "instruction": "Propose three ways to make this layer more audible.",
  "scope": {
    "track_indices": [21],
    "layer_id": "intro_handoff",
    "section_id": "intro"
  },
  "constraints": {
    "read_only": true,
    "requires_audio_capture": false
  },
  "status": "queued | running | done | failed"
}
```

### Proposal

```json
{
  "proposal_id": "prop_...",
  "task_id": "task_...",
  "agent_role": "sound_design",
  "summary": "Create three visible guitar audition lanes.",
  "confidence": 0.72,
  "risk": "low | medium | high",
  "write_set": ["track:21:devices", "track:21:clips"],
  "transport_required": false,
  "suggested_jobs": [
    {
      "job_type": "mutation",
      "title": "Create guitar lift auditions",
      "plan": []
    }
  ],
  "requires_user_decision": false
}
```

### Ableton Job

```json
{
  "job_id": "job_...",
  "project_id": "project_...",
  "snapshot_id": "snap_...",
  "submitted_by": "conductor",
  "job_type": "offline_analysis | playback_analysis | audition | mutation",
  "priority": 50,
  "scope": {
    "track_indices": [21],
    "layer_id": "intro_handoff",
    "section_id": "intro"
  },
  "requires_transport": false,
  "requires_write": true,
  "write_set": ["track:21:devices", "track:21:clips"],
  "leases": ["track:21", "layer:intro_handoff"],
  "plan": [
    {
      "tool": "duplicate_track",
      "args": {"track_index": 21},
      "summary": "Create AUD A source duplicate"
    }
  ],
  "status": "queued | running | awaiting_decision | done | failed | canceled",
  "result": null
}
```

### Lease

```json
{
  "lease_id": "lease_...",
  "resource": "transport | master | track:21 | layer:intro_handoff | section:intro",
  "job_id": "job_...",
  "owner": "conductor",
  "expires_at_ms": 0
}
```

## Resource Model

Resources should be conservative:

- `transport`: loop, playback, record, solo/mute audition state, Back to Arrangement.
- `master`: master devices, master volume, analyzer placement.
- `track:<index>`: any track-level device, clip, note, automation, volume, pan, send, mute, solo, routing edit.
- `layer:<id>`: all tracks resolved by the current layer group.
- `section:<id>`: section map edits or section-scoped playback/capture.
- `project`: global arrangement changes, tempo map, cue points, major structural edits.

Read-only jobs do not need leases unless they require transport.

## Conflict Rules

- Jobs requiring `transport` cannot run concurrently with any other transport job.
- Two write jobs conflict if their write sets overlap.
- A layer write conflicts with writes to any member track in that layer.
- A master write conflicts with every playback/capture job because it affects monitoring.
- If a job's `snapshot_id` is stale, the conductor must revalidate before execution.
- User-triggered jobs have higher priority than background analysis.

## Project Revision

The broker needs a lightweight project revision counter.

Increment on:

- successful mutation job
- accepted audition commit
- track intent or layer map save
- section map save
- automation recording

Do not increment on:

- read-only analysis
- failed jobs with no applied changes
- cockpit draft edits that were not sent

Stale proposals should remain visible but marked `stale_needs_revalidation`.

## Tool Surface

Initial MCP tools:

- `create_orchestration_snapshot(request_text, mode?)`
- `submit_agent_task(snapshot_id, agent_role, instruction, scope, constraints?)`
- `submit_agent_proposal(task_id, proposal)`
- `list_agent_tasks(status?, snapshot_id?)`
- `list_agent_proposals(snapshot_id?, status?)`
- `submit_ableton_job(job)`
- `list_ableton_jobs(status?)`
- `cancel_ableton_job(job_id)`
- `run_next_ableton_job()` for manual/conductor-driven execution
- `get_orchestration_state()` for cockpit and Codex status

Later:

- `approve_proposal(proposal_id)`
- `reject_proposal(proposal_id, reason?)`
- `promote_proposal_to_job(proposal_id)`
- `claim_resource(resource, owner, ttl_ms)`
- `release_resource(lease_id)`

## Execution Contract

Every mutation or playback job should follow the same lifecycle:

1. Validate the project ID and snapshot revision.
2. Resolve track/layer/section references against the current session.
3. Acquire required leases.
4. Capture preflight state needed for restoration.
5. Execute the compiled plan.
6. Verify expected result.
7. Clear Back to Arrangement when applicable.
8. Restore non-target transport/solo/mute state unless the job explicitly changes it.
9. Log the result to the action ledger/session continuity.
10. Release leases.

Failed jobs must report:

- failed step
- whether any changes were applied
- restoration status
- recommended recovery action

## Cockpit Behavior

The cockpit should gain an orchestration panel with:

- current snapshot/brief
- active target layer/section
- queued/running/done jobs
- pending proposals
- audition count and output mode
- stale proposal warnings
- one primary action: `Send Brief to Codex`

For auditions:

- User selects a Song Layer and section.
- User chooses audition count.
- `Send Brief to Codex` creates a snapshot and task packet.
- Specialist agents submit proposals.
- Conductor creates visible muted audition lanes.
- Cockpit shows audition job status and winner/promotion actions.

The cockpit should not expose implementation details like raw leases by default. Advanced mode can show them for debugging.

## Storage

Use project-scoped storage under the existing `~/.livepilot/projects/<project_id>/` pattern.

Proposed files:

- `orchestration.json` for snapshots, tasks, proposals, jobs, leases, and revision.
- Keep action history in the existing action ledger/session continuity where possible.

Storage should be append-friendly and resilient to Codex restarts. In-memory queues are acceptable only for a first proof of concept.

## MVP

The first useful version should support:

1. Create a snapshot from cockpit context.
2. Store tasks and proposals.
3. Submit visible audition jobs for a selected layer.
4. Serialize playback and mutation jobs through one executor.
5. Show queue/proposal status in the cockpit.
6. Mark stale proposals after a successful mutation.

Do not implement generalized background workers yet. Let Codex or the conductor explicitly run jobs.

## Phase Commit Discipline

Implementation should be split into small phases, with a Git commit at the end of each phase before starting the next one. Each phase commit should include:

- the code/docs/tests for only that phase
- passing targeted tests or a clearly documented reason tests could not run
- a short evidence note in the commit body when behavior was manually verified
- no unrelated worktree changes

If a phase changes Ableton-facing behavior, the phase must also include either a mocked integration test or a manual LivePilot verification note. If a phase is blocked, commit only completed preparatory work that is independently useful; do not commit half-wired execution paths.

Recommended phase boundaries:

1. Persistence models and project revision store.
2. MCP tool surface for snapshots, tasks, proposals, jobs, leases, and read-only state.
3. Lease/conflict/stale-snapshot logic.
4. Manual `run_next_ableton_job` executor for a limited safe plan format.
5. Cockpit queue/proposal visibility.
6. Visible layer-audition job generation.
7. Verification/logging integration with action ledger and session continuity.

Do not begin phase N+1 until phase N has been committed or explicitly abandoned.

## Test Plan

Unit tests:

- Snapshot creation includes cockpit context, focus, layers, and section map.
- Job validation rejects unknown tracks/layers/sections.
- Lease acquisition blocks conflicting jobs.
- Non-conflicting read-only jobs can be queued together.
- Mutation job completion increments project revision.
- Stale snapshot proposals are marked stale after revision changes.
- Queue ordering respects priority and FIFO within priority.
- Failed jobs release leases.

Integration tests with mocked Ableton:

- Playback job acquires `transport`, sets loop, runs verification, restores state.
- Mutation job batches multiple tool steps and logs one result.
- Visible audition proposal becomes N muted audition-track creation steps.
- Cockpit state endpoint includes pending proposals and queued jobs.

Manual acceptance:

- Select a layer and section in `/cockpit/intent`.
- Request three auditions.
- Confirm the queue shows one mutation job.
- Run the job.
- Verify Ableton gets three visible muted audition lanes.
- Verify another transport job cannot run while a playback job is active.
- Verify a second proposal against the same layer is marked conflicting or queued behind the first.

## Open Questions

- Should the first executor run automatically, or only when Codex/conductor explicitly calls `run_next_ableton_job`?
- Should leases expire automatically, or require explicit cleanup plus stale-job recovery?
- How should we represent section identity when no saved section map exists?
- Should proposal review be human-only at first, or should a reviewer agent rank proposals before the human sees them?
- Should offline audio renders be cached per snapshot and section to avoid repeated capture jobs?
- What is the right maximum job size before we split a plan into smaller verifiable chunks?

## Recommended First Implementation Slice

Build the broker as project-scoped persistence plus manual execution:

1. Add persistence models for snapshots, proposals, jobs, leases, and project revision.
2. Add MCP tools for create/list/submit/cancel/run-next.
3. Add a conductor executor that can run a limited plan format using existing MCP dispatch.
4. Wire cockpit to show proposals/jobs and submit audition-count intent.
5. Implement visible audition job generation for layer-scoped variants.
6. Add tests before enabling auto-execution.

This gives us real coordination without turning LivePilot into a distributed system too early.

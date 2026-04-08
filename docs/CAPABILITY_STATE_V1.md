# Capability State v1

Status: proposal

Audience: runtime, tool, agent, evaluation, research, and UX owners

Purpose: define the shared capability model that lets LivePilot reason honestly about what the current runtime can and cannot trust.

Capability State is the guardrail between architecture intent and runtime reality.

It answers questions like:

- is analyzer data currently available and fresh
- are composition metrics partially degraded
- can the runtime safely inspect plugin state
- is web research available
- should the agent stay in a measured loop or downgrade to guided judgment

## 1. Why This Exists

Agent OS, Composition Engine, Mix Engine, Reference Engine, and Research Engine all make decisions that depend on external conditions.

Today those conditions are too implicit.

The result is predictable:

- prompts over-assume what the tools can do
- evaluators overstate confidence
- research modes assume providers that may not exist
- users are not told clearly when the system is operating in degraded mode

Capability State v1 fixes that by creating one explicit shared source of truth.

## 2. Design Goals

Capability State v1 should:

- unify runtime availability and health checks
- represent confidence, freshness, and trust level
- degrade gracefully instead of failing theatrically
- expose both machine-facing and user-facing status
- make agent decisions easier to test

Capability State v1 should not:

- become a general metrics warehouse
- replace the World Model
- duplicate every tool response payload verbatim

## 3. Capability Domains

At minimum, v1 should model these domains:

- `session_access`
- `arrangement_access`
- `note_access`
- `device_access`
- `automation_access`
- `analyzer`
- `offline_perception`
- `memory`
- `reference_inputs`
- `research`
- `web`
- `live_performance_safe`

Each domain should expose:

- availability
- freshness
- confidence
- degradation reason
- preferred operating mode

## 4. Core Data Model

```json
{
  "capability_state": {
    "generated_at_ms": 0,
    "overall_mode": "normal",
    "domains": {
      "analyzer": {
        "available": true,
        "confidence": 0.92,
        "freshness_ms": 240,
        "mode": "measured",
        "reasons": []
      },
      "research": {
        "available": true,
        "confidence": 0.71,
        "freshness_ms": null,
        "mode": "targeted_only",
        "reasons": ["web_unavailable", "local_docs_available", "memory_available"]
      }
    },
    "gating_flags": {
      "allow_measured_keep_undo": true,
      "allow_open_web_research": false,
      "allow_performance_mode_mutations": true
    }
  }
}
```

## 5. Domain Semantics

### 5.1 `session_access`

Can the runtime read core Live session state at all.

Required evidence:

- `get_session_info` success
- non-stale transport
- expected session fields present

### 5.2 `device_access`

Can the runtime reliably inspect devices and parameters.

Substates:

- `healthy`
- `partial`
- `opaque`
- `unavailable`

Used by:

- Mix Engine
- Sound Design Engine
- Research Engine

### 5.3 `analyzer`

Can the runtime gather live sonic evidence for fast-loop evaluation.

Must track:

- analyzer online/offline
- snapshot freshness
- band schema compatibility
- partial data availability

### 5.4 `offline_perception`

Can the runtime render/capture and run deeper analysis.

Must distinguish:

- unavailable
- available but slow
- available and trustworthy

### 5.5 `research`

This is not just `web`.

It summarizes provider availability across:

- session state
- local docs
- memory
- user-supplied references
- structured connectors
- web

### 5.6 `live_performance_safe`

Can the system safely run in a low-latency, non-destructive live context.

Must include:

- latency budget
- mutation safety class
- transport stability

## 6. Mode Mapping

Capability State should help the conductor choose an operating mode:

- `normal`
- `measured_degraded`
- `judgment_only`
- `research_local_only`
- `live_safe_only`
- `read_only`

Examples:

- Analyzer unavailable but session access healthy:
  `measured_degraded`
- Session read works, writes blocked:
  `read_only`
- Web unavailable, local docs and memory present:
  `research_local_only`
- Live show mode with unstable transport:
  `live_safe_only`

## 7. Runtime Ownership

Suggested module layout:

- `mcp_server/runtime/capability_state.py`
- `mcp_server/runtime/capability_checks.py`
- `mcp_server/runtime/capability_contracts.py`

Responsibilities:

- gather raw capability signals
- normalize them into the shared contract
- expose one builder callable for all engines

## 8. Input Sources

Capability State v1 should gather evidence from:

- tool call success/failure rates
- analyzer freshness timestamps
- snapshot normalization success
- device inspection success
- recent bridge errors
- memory availability
- presence of user-provided references
- presence of local documentation
- availability of web or structured providers

It should not require every engine to discover this independently.

## 9. API Surface

Suggested functions:

- `build_capability_state()`
- `summarize_capability_state()`
- `get_capability(domain)`
- `can_use_measured_evaluation()`
- `can_run_research(mode)`
- `can_mutate_in_live_mode()`

Suggested MCP wrapper:

- `get_capability_state`

## 10. UX Contract

The agent should surface degradations simply.

Good:

- "I can inspect the session and make composition moves, but live analyzer feedback is currently unavailable, so I’ll verify more conservatively."
- "I can research from the project, memory, and local docs, but not from the open web in this environment."

Bad:

- silent fallback
- fake certainty
- low-level stack traces as user explanations

## 11. Integration Points

### 11.1 Agent OS

Uses capability state to decide:

- whether measured keep/undo is allowed
- whether research should be local-only
- whether to ask for confirmation before risky mutations

### 11.2 Composition Engine

Uses capability state to decide:

- whether to trust sonic tension proxies
- whether to prefer symbolic critics
- whether musical automation proposals should be preview-only

### 11.3 Research Engine

Uses capability state to rank provider ladders.

### 11.4 Performance Engine

Uses capability state to lock out unsafe operations.

## 12. Test Matrix

Must cover:

- analyzer online vs offline
- partial device inspection
- web unavailable but local docs present
- render/perception available vs unavailable
- transport unstable during live-safe mode
- stale analyzer snapshot freshness

## 13. Phase 1 Build Order

1. Define contracts and enums.
2. Implement domain builders.
3. Wire analyzer + evaluation gates first.
4. Add research provider ladder state.
5. Add performance-safe gating.
6. Add user-facing summary formatter.

## 14. Exit Criteria

Capability State v1 is done when:

- the conductor can determine degraded modes without prompt hacks
- research behavior no longer assumes web availability
- measured evaluation gates are driven by shared state
- the user sees clear, honest degradation messaging
- tests cover at least one degraded path for each critical domain

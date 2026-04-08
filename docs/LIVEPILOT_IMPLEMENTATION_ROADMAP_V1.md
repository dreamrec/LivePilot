# LivePilot Implementation Roadmap v1

Status: proposal

Audience: product, engineering, agent/runtime, MIR/DSP, and evaluation owners

Purpose: turn the long-range LivePilot architecture into a concrete implementation program.

This document answers:

- what to build first
- what to avoid building too early
- which modules should exist
- how to phase work so the system stays coherent
- how to verify that each phase is actually improving LivePilot

This roadmap assumes the system direction laid out in:

- [LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md](./LIVEPILOT_SYSTEM_ARCHITECTURE_V1.md)
- [AGENT_OS_V1.md](./AGENT_OS_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)

This roadmap is complemented by concrete implementation-spec documents:

- [AGENT_OS_PHASE0_HARDENING_PLAN.md](./AGENT_OS_PHASE0_HARDENING_PLAN.md)
- [COMPOSITION_ENGINE_V1_INTEGRATION_PLAN.md](./COMPOSITION_ENGINE_V1_INTEGRATION_PLAN.md)
- [PROJECT_BRAIN_V1.md](./PROJECT_BRAIN_V1.md)
- [CAPABILITY_STATE_V1.md](./CAPABILITY_STATE_V1.md)
- [ACTION_LEDGER_V1.md](./ACTION_LEDGER_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)
- [MIX_ENGINE_V1.md](./MIX_ENGINE_V1.md)
- [REFERENCE_ENGINE_V1.md](./REFERENCE_ENGINE_V1.md)
- [TASTE_MODEL_V1.md](./TASTE_MODEL_V1.md)
- [SOUND_DESIGN_ENGINE_V1.md](./SOUND_DESIGN_ENGINE_V1.md)
- [TRANSITION_ENGINE_V1.md](./TRANSITION_ENGINE_V1.md)
- [TRANSLATION_ENGINE_V1.md](./TRANSLATION_ENGINE_V1.md)
- [PERFORMANCE_ENGINE_V1.md](./PERFORMANCE_ENGINE_V1.md)
- [RESEARCH_ENGINE_V1.md](./RESEARCH_ENGINE_V1.md)

## 1. Planning Assumptions

This roadmap is built around a few explicit assumptions.

### 1.1 Product Assumptions

- LivePilot should remain simple for the user and complex internally.
- The best early wins come from making the existing loop more trustworthy, not more theatrical.
- Composition and mix quality matter more than tool count.
- Taste adaptation is a force multiplier across all engines.

### 1.2 Technical Assumptions

- Ableton Live remains the primary execution environment.
- MCP tools remain the deterministic action layer.
- Analyzer, perception, theory, harmony, automation, and memory tooling remain important foundations.
- The system will need to function even when analyzer or web access is partially unavailable.

### 1.3 Strategy Assumptions

- One Conductor runtime should remain the primary live owner of mutation.
- Specialized engines should be structured modules, not independent free-roaming agents.
- Explicit state and evaluators should grow before deep autonomy.

## 2. Current State Snapshot

At a high level, the repo already contains:

- a large MCP tool surface
- Remote Script + M4L bridge plumbing
- analyzer/perception tools
- theory/harmony tools
- automation primitives and curve generation
- memory tooling
- a first Agent OS phase
- a composition design document

That is a very strong foundation.

But from an implementation perspective, the highest-leverage next move is to harden the current Agent OS loop before layering more engines on top.

## 3. Immediate Phase 0 Fixes

These are the changes that should land before any large architecture expansion.

### 3.1 Why Phase 0 Exists

If the current loop has safety or interface drift problems, every higher engine will inherit them.

### 3.2 Current Must-Fix Issues

#### A. Protected-dimension safety violation

Current risk:

- unmeasurable-target fallback can override protected-dimension failure

Required change:

- protected measurable damage must remain a hard undo condition even when target dimensions are unmeasurable

#### B. Snapshot normalization gap

Current risk:

- `get_master_spectrum` returns `bands`
- `evaluate_move` expects `spectrum`
- the agent loop can silently enter "nothing measurable" mode

Required change:

- normalize analyzer outputs at the tool or evaluator boundary
- never require the agent prompt to hand-reshape the snapshots correctly

#### C. Measurability contract drift

Current risk:

- dimensions such as `width` are marked measurable without an implemented extractor

Required change:

- either implement the metric or mark the dimension unmeasurable in phase 1

#### D. World model overclaiming

Current risk:

- `build_world_model` claims device/plugin awareness that it does not actually fetch

Required change:

- either fetch the relevant device/track health state
- or narrow the contract until it is true

#### E. Incorrect dynamics heuristic

Current risk:

- the flat-dynamics heuristic uses an incorrect crest-factor calculation

Required change:

- use log-based crest-factor math and recalibrate thresholds

### 3.3 Phase 0 Deliverables

- evaluator safety fix
- snapshot normalizer
- corrected measurable-dimension registry
- corrected world-model data fetching or contract
- corrected crest-factor heuristic
- end-to-end tests for the actual goal -> capture -> evaluate path

### 3.4 Exit Criteria

Phase 0 is done when:

- protected-dimension damage can never return `keep_change=true`
- raw analyzer outputs can be passed into evaluation through one supported path
- measurable/unmeasurable dimension reporting matches the real implementation
- world model behavior matches its documented contract
- the end-to-end loop has regression tests

## 4. Workstreams

To keep the roadmap coherent, work should be organized into explicit workstreams.

| Workstream | Scope |
|---|---|
| `A` Foundation hardening | Agent OS fixes, snapshot normalization, capability state, contracts |
| `B` Shared substrates | Project Brain, Action Ledger, Memory Fabric, Evaluation Fabric |
| `C` Composition | section/phrase/role/motif/gesture intelligence |
| `D` Mix | masking, depth, glue, translation, bus logic |
| `E` Sound design | patch analysis, timbral goals, modulation, plugin tactics |
| `F` References and taste | reference gap analysis, taste adaptation, style tactic cards |
| `G` Transitions and translation | arrival/exit logic, playback robustness |
| `H` Performance | live-set-safe operation and scene intelligence |
| `I` Research and evals | tactic extraction, benchmark suites, telemetry |

## 5. Delivery Model

Each phase in this roadmap should have:

- product goal
- technical scope
- module list
- data contracts
- tests
- telemetry hooks
- exit criteria

No phase should be treated as complete based on "prompt feels smarter."

## 6. Phase 0: Agent OS Hardening

This phase is about making the current base safe and trustworthy.

Primary implementation spec:

- [AGENT_OS_PHASE0_HARDENING_PLAN.md](./AGENT_OS_PHASE0_HARDENING_PLAN.md)

### 6.1 Product Goal

Make the current Agent OS loop reliable enough that it can safely become the execution substrate for future engines.

### 6.2 Technical Scope

- fix evaluator safety logic
- fix snapshot schema mismatch
- fix measurable-dimension registry
- fix world-model contract drift
- fix dynamics heuristic
- add end-to-end tests

### 6.3 Likely Files

- `mcp_server/tools/_agent_os_engine.py`
- `mcp_server/tools/agent_os.py`
- `mcp_server/tools/analyzer.py`
- `livepilot/agents/livepilot-producer/AGENT.md`
- `tests/test_agent_os_engine.py`
- new end-to-end agent loop tests

### 6.4 Suggested New Helpers

- `snapshot_normalizer.py`
- `evaluation_contracts.py`

### 6.5 Acceptance Tests

- protected measurable damage always forces undo
- valid analyzer payloads produce measurable evaluation where metrics exist
- "make it wider" is either truly measurable or honestly unmeasurable
- `build_world_model` does not overpromise unavailable state

### 6.6 Exit Criteria

- green tests
- documentation aligned
- no known evaluator-safety mismatch remaining

## 7. Phase 1: Shared Substrate Foundation

This is the most important architecture phase after hardening.

Primary implementation specs:

- [PROJECT_BRAIN_V1.md](./PROJECT_BRAIN_V1.md)
- [CAPABILITY_STATE_V1.md](./CAPABILITY_STATE_V1.md)
- [ACTION_LEDGER_V1.md](./ACTION_LEDGER_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

### 7.1 Product Goal

Create the reusable shared substrate layer that every future engine depends on.

### 7.2 Why This Comes Before More Engines

If new engines are built before shared substrates exist, they will each reinvent:

- world state
- evaluation
- memory
- safety
- capability handling

That would create fragmentation and long-term chaos.

### 7.3 Deliverables

- `Project Brain` v1
- `Capability State` v1
- `Action Ledger` v1
- `Evaluation Fabric` v1
- `Memory Fabric` v2

### 7.4 Project Brain v1 Scope

Minimum subgraphs:

- session graph
- arrangement graph
- role graph
- device graph
- automation graph

### 7.5 Capability State v1 Scope

Track:

- analyzer availability
- FluCoMa availability
- capture availability
- plugin health
- arrangement automation limitations
- memory availability
- research provider availability

### 7.6 Action Ledger v1 Scope

Log:

- action intent
- owning engine
- affected scope
- before/after references
- evaluation result
- kept/undone

### 7.7 Memory Fabric v2 Scope

Move beyond technique-only storage:

- outcome memory
- anti-memory
- style tactic cards
- project-local state

### 7.8 Module Candidates

- `mcp_server/project_brain/`
- `mcp_server/capabilities/`
- `mcp_server/evaluation/`
- `mcp_server/ledger/`
- `mcp_server/memory/` expansion

### 7.9 Acceptance Tests

- every evaluated action can be traced in the ledger
- project brain updates incrementally after controlled mutations
- capability state updates cleanly when analyzer or bridge state changes
- memory retrieval can filter by goal, context, and outcome

### 7.10 Exit Criteria

- new substrate modules exist and are used by Agent OS
- core interactions are observable and serializable
- no engine-specific duplicated state layer is introduced

## 8. Phase 2: Composition Engine Phase 1

This is the first major specialized engine phase.

Primary implementation specs:

- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)
- [COMPOSITION_ENGINE_V1_INTEGRATION_PLAN.md](./COMPOSITION_ENGINE_V1_INTEGRATION_PLAN.md)
- [TRANSITION_ENGINE_V1.md](./TRANSITION_ENGINE_V1.md)
- [PROJECT_BRAIN_V1.md](./PROJECT_BRAIN_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

### 8.1 Product Goal

Make LivePilot capable of turning loops into convincing sections and making structural changes that feel intentional and musical.

### 8.2 Scope

- section graph
- phrase grid
- role inference
- basic motif tracking
- composition critic stack v1
- gesture authoring v1
- composition evaluation records

### 8.3 Must-Have Features

- loop-to-section inference
- section identity critique
- phrase completion detection
- subtractive arrangement moves
- response-phrase moves
- transition-aware automation gestures

### 8.4 Likely Modules

- `composition_world_model.py`
- `section_inference.py`
- `phrase_engine.py`
- `role_inference.py`
- `composition_critics.py`
- `gesture_library.py`
- `composition_evaluator.py`

### 8.5 Acceptance Tests

Scenarios:

- "turn this loop into a verse"
- "make this build tension"
- "make this section less repetitive"
- "make the automation feel more musical"

Success should mean:

- first or second move is often keepable
- section identity improves
- transitions become more intentional

### 8.6 Exit Criteria

- composition engine can drive real arrangement moves
- gesture authoring works in actual phrase/section context
- evaluation records capture composition-specific outcomes

## 9. Phase 3: Mix Engine Phase 1

Primary implementation specs:

- [MIX_ENGINE_V1.md](./MIX_ENGINE_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)
- [TRANSLATION_ENGINE_V1.md](./TRANSLATION_ENGINE_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

### 9.1 Product Goal

Make LivePilot consistently useful for improvement requests like:

- cleaner
- wider
- more punch
- less muddy
- more glued
- more expensive

### 9.2 Scope

- balance critic
- masking critic
- dynamics critic
- stereo/depth critic
- bus-state representation
- track/bus/master move ranking

### 9.3 Minimum Required Internal State

- balance state
- masking map
- dynamics state
- stereo state
- send/depth state

### 9.4 Likely Modules

- `mix_world_model.py`
- `masking_engine.py`
- `mix_critics.py`
- `mix_planner.py`
- `mix_evaluator.py`

### 9.5 Acceptance Tests

Scenarios:

- "make this cleaner"
- "make the drums hit harder"
- "make this wider but keep the center solid"
- "make this more glued without flattening it"

### 9.6 Exit Criteria

- mix requests no longer rely only on generic parameter pokes
- the engine can justify and verify mix changes
- translation-aware warnings start to appear in the loop

## 10. Phase 4: Taste Model Phase 1

Primary implementation specs:

- [TASTE_MODEL_V1.md](./TASTE_MODEL_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)
- [ACTION_LEDGER_V1.md](./ACTION_LEDGER_V1.md)

### 10.1 Product Goal

Make LivePilot meaningfully personal.

### 10.2 Scope

- capture accepted vs rejected changes
- learn transition boldness preference
- learn density tolerance
- learn automation density preference
- learn device-family preference
- store explicit anti-memory

### 10.3 Deliverables

- taste profile schema
- ranking priors in planning
- anti-pattern warnings
- user-facing `save this direction` support

### 10.4 Acceptance Tests

- same request on similar material ranks different moves after user history accumulates
- clearly disliked patterns are not repeatedly suggested

### 10.5 Exit Criteria

- planning visibly changes in a user-specific way
- anti-memory is live and queried in ranking

## 11. Phase 5: Reference Engine Phase 1

Primary implementation specs:

- [REFERENCE_ENGINE_V1.md](./REFERENCE_ENGINE_V1.md)
- [RESEARCH_ENGINE_V1.md](./RESEARCH_ENGINE_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

### 11.1 Product Goal

Make reference-based work intelligent rather than superficial.

### 11.2 Scope

- reference ingestion
- style gap reports
- section-aware comparison
- tactic-card creation
- routing hints into composition, mix, and transition engines

### 11.3 Deliverables

- `ReferenceProfile`
- `GapReport`
- `StyleTacticCard`
- reference-conditioned planner hooks

### 11.4 Acceptance Tests

Scenarios:

- "make this feel more like reference A"
- "why doesn’t this chorus feel as big as the reference?"
- "use this track as a direction but keep my identity"

### 11.5 Exit Criteria

- reference work yields actionable differences, not just descriptive summaries
- reference-conditioned moves are tested and scored in-session

## 12. Phase 6: Sound Design Engine Phase 1

Primary implementation specs:

- [SOUND_DESIGN_ENGINE_V1.md](./SOUND_DESIGN_ENGINE_V1.md)
- [RESEARCH_ENGINE_V1.md](./RESEARCH_ENGINE_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

### 12.1 Product Goal

Make LivePilot capable of real timbral development and plugin-aware sound design.

### 12.2 Scope

- patch inspection
- timbral-goal translation
- modulation-state modeling
- layer strategy
- plugin tactic cards
- macro gesture design

### 12.3 Deliverables

- `PatchModel`
- `ModulationState`
- `LayerStrategy`
- `PluginConfidenceState`

### 12.4 Acceptance Tests

Scenarios:

- "make this synth darker and more alive"
- "make this pad feel haunted"
- "make this bass more expensive without losing weight"

### 12.5 Exit Criteria

- sound-design requests produce patch-aware or chain-aware moves
- modulation is used as intention, not random movement

## 13. Phase 7: Transition Engine Phase 1

Primary implementation specs:

- [TRANSITION_ENGINE_V1.md](./TRANSITION_ENGINE_V1.md)
- [COMPOSITION_ENGINE_V1.md](./COMPOSITION_ENGINE_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)

### 13.1 Product Goal

Make section boundaries and arrivals feel earned.

### 13.2 Scope

- boundary map
- arrival strength scoring
- handoff graph
- pre-impact subtraction strategies
- transition gesture templates

### 13.3 Acceptance Tests

Scenarios:

- "make this drop feel earned"
- "the transition is there but not exciting"
- "give this section change more narrative"

### 13.4 Exit Criteria

- transitions can be improved with small, explainable moves
- section boundaries are evaluated explicitly, not indirectly

## 14. Phase 8: Translation Engine Phase 1

Primary implementation specs:

- [TRANSLATION_ENGINE_V1.md](./TRANSLATION_ENGINE_V1.md)
- [MIX_ENGINE_V1.md](./MIX_ENGINE_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)

### 14.1 Product Goal

Make LivePilot reliable for final-stage robustness checks.

### 14.2 Scope

- mono checks
- low-end translation checks
- loudness posture checks
- harshness checks
- headphone/small-speaker proxy checks

### 14.3 Acceptance Tests

Scenarios:

- "is this ready to export?"
- "why does this fall apart in mono?"
- "make this hold up on small speakers"

### 14.4 Exit Criteria

- translation warnings are actionable and accurate enough to trust

## 15. Phase 9: Performance Engine Phase 1

Primary implementation specs:

- [PERFORMANCE_ENGINE_V1.md](./PERFORMANCE_ENGINE_V1.md)
- [CAPABILITY_STATE_V1.md](./CAPABILITY_STATE_V1.md)
- [ACTION_LEDGER_V1.md](./ACTION_LEDGER_V1.md)

### 15.1 Product Goal

Make LivePilot useful during live performance or scene-driven work.

### 15.2 Scope

- performance-safe mode
- scene role inference
- macro-safe action selection
- set pacing support
- lower-latency runtime policies

### 15.3 Acceptance Tests

Scenarios:

- scene launch refinement
- set pacing suggestions
- safe live automation or transition assistance

### 15.4 Exit Criteria

- live mode is clearly different from studio mode
- no risky slow-path behavior is triggered by default in performance mode

## 16. Phase 10: Research Engine And Deep Evaluation

Primary implementation specs:

- [RESEARCH_ENGINE_V1.md](./RESEARCH_ENGINE_V1.md)
- [EVALUATION_FABRIC_V1.md](./EVALUATION_FABRIC_V1.md)
- [MEMORY_FABRIC_V2.md](./MEMORY_FABRIC_V2.md)

### 16.1 Product Goal

Create a compounding intelligence loop that improves over time.

### 16.2 Scope

- tactic extraction from local and external sources
- research trajectory logging
- benchmark suite expansion
- offline scenario replay
- pairwise preference evaluation

### 16.3 Deliverables

- research provider router
- tactic distillation layer
- benchmark harness
- replay datasets
- longitudinal telemetry dashboards

### 16.4 Acceptance Tests

- research outputs are reusable across sessions
- benchmark scores are improving on real scenario suites
- regression detection is possible before release

## 17. Cross-Cutting Engineering Requirements

Every phase should satisfy the following.

### 17.1 Contract Discipline

- every new engine needs explicit schemas
- every new engine must declare measurable vs unmeasurable outputs
- every new engine must state its failure modes

### 17.2 Explainability

The user should be able to ask:

- "why did you do that?"

And the system should answer with:

- musical rationale
- evidence used
- expected effect

### 17.3 Observability

Every important action should be traceable through:

- project state
- action ledger
- evaluation result
- memory write

### 17.4 Safety

- no new engine should bypass the Conductor for session mutation
- no new engine should bypass evaluation for non-trivial changes
- no engine should silently overwrite user-authored automation or structure

## 18. Recommended Team Lanes

This roadmap becomes much easier to execute if ownership is explicit.

### Lane A: Runtime And Shared Systems

Own:

- Agent OS hardening
- Project Brain
- Capability State
- Action Ledger
- Evaluation Fabric

### Lane B: Musical Intelligence

Own:

- Composition Engine
- Transition Engine
- Taste Model

### Lane C: Sonic Intelligence

Own:

- Mix Engine
- Translation Engine
- reference-conditioned sonic comparisons

### Lane D: Timbral Intelligence

Own:

- Sound Design Engine
- plugin tactic cards
- modulation systems

### Lane E: Research And Evaluation

Own:

- Research Engine
- benchmark suites
- telemetry
- preference studies

## 19. Milestone View

This is a practical milestone ordering rather than a calendar promise.

### Milestone 1

- Phase 0 complete
- Agent OS safe and contract-correct

### Milestone 2

- Phase 1 complete
- Shared substrates exist

### Milestone 3

- Phase 2 complete
- Composition Engine phase 1 live

### Milestone 4

- Phase 3 complete
- Mix Engine phase 1 live

### Milestone 5

- Phases 4 and 5 complete
- Taste + Reference become differentiators

### Milestone 6

- Phases 6, 7, and 8 live
- LivePilot starts to feel like a genuinely integrated producer system

### Milestone 7

- Phases 9 and 10 mature
- system is performance-capable and continuously improvable

## 20. Risks And Mitigations

### Risk 1: Overbuilding prompts instead of systems

Mitigation:

- require module and contract design before prompt expansion

### Risk 2: Engine fragmentation

Mitigation:

- shared substrates first
- one Conductor for mutation

### Risk 3: False confidence from weak evals

Mitigation:

- invest in evaluator quality early
- require end-to-end tests and scenario benchmarks

### Risk 4: Too much autonomy too soon

Mitigation:

- keep the default move size small
- preserve strong undo and explanation behavior

### Risk 5: Research bloat

Mitigation:

- force research outputs into tactic cards and ranked candidates
- do not let raw browsing become the product

## 21. What Not To Build Yet

Avoid these too early:

- uncontrolled multi-agent swarms
- massive autonomous song generation
- fully automatic arrangement rewrites
- deep performance mode before shared safety is ready
- flashy agent theatrics without evaluation

These can create impressive demos but weak real-world trust.

## 22. Definition Of Done

A phase is only done when:

- the product behavior is meaningfully better
- the architecture boundary is explicit
- the contracts are documented
- tests exist
- telemetry exists
- failure modes are understood

## 23. Summary

The core strategic sequence is:

1. fix the current loop
2. build the shared substrate layer
3. ship composition and mix as the first true specialized engines
4. make the system personal with taste and references
5. deepen timbre, transitions, translation, and live behavior
6. make research and evaluation compounding advantages

This order matters.

If LivePilot follows it, the product should become:

- more coherent
- more musical
- more trustworthy
- more personal
- and much harder to copy

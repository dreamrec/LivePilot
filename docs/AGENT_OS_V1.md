# LivePilot Agent OS v1

Status: proposal

Audience: product, agent design, MCP/runtime, research, and workflow authors

Purpose: define a comprehensive operating system for LivePilot's next-generation autonomous production agent. The goal is simple externally and sophisticated internally:

- Externally: the user gives one natural-language goal.
- Internally: the agent compiles intent, models the session, critiques it through multiple lenses, plans reversible experiments, evaluates the result, learns from outcomes, and optionally performs deep research when needed.

This document is intentionally broader than a prompt. Agent OS is a system design spanning:

- prompt policy
- internal state and schemas
- decision loops
- research behavior
- memory and knowledge
- safety and trust
- product UX

## Related Materials

This proposal is meant to sit alongside the current LivePilot architecture and documentation:

- [TOOL_REFERENCE.md](./TOOL_REFERENCE.md)
- [M4L_BRIDGE.md](./M4L_BRIDGE.md)
- [v2-master-spec/README.md](./v2-master-spec/README.md)
- [../livepilot/agents/livepilot-producer/AGENT.md](../livepilot/agents/livepilot-producer/AGENT.md)
- [../livepilot/skills/livepilot-core/SKILL.md](../livepilot/skills/livepilot-core/SKILL.md)

It should be read as an operating-system layer above the current tool surface, not as a replacement for the existing MCP and Ableton integration model.

## 1. Vision

LivePilot should feel like talking to a brilliant producer inside Ableton Live:

- The user says: "make this more alive"
- The agent figures out what "more alive" means in context
- The agent inspects the session before acting
- The agent tries the smallest strong move first
- The agent verifies whether the move actually helped
- The agent keeps good changes, undoes bad ones, and learns what worked

The system should not feel like "AI with 178 tools." It should feel like "a producer with taste, ears, memory, and discipline."

## 2. Product Principle

Agent OS v1 is built around one central product principle:

- Advanced internally
- Simple externally

### External experience

The user should be able to say things like:

- "make this hit harder"
- "turn this into a real verse"
- "clean this up"
- "make it wider but still solid in mono"
- "research the best way to do this with the devices already loaded"
- "push this toward Burial / Kaytranada / Four Tet"

The user should not need to think in tool domains, parameter indices, or analyzer streams.

### Internal experience

Internally, the system should maintain explicit state and run a rigorous loop:

1. Compile goal
2. Build world model
3. Run critics
4. Generate candidate moves
5. Choose the best next move
6. Execute a reversible experiment
7. Evaluate before vs after
8. Keep, undo, or refine
9. Learn outcome

## 3. Non-Goals

Agent OS v1 does not attempt to:

- replace deterministic tools with opaque generation
- browse the web by default for every production task
- act without verification
- optimize for tool count as a product story
- maximize autonomy at the expense of trust

## 4. System Overview

Agent OS v1 has one primary agent runtime and seven core services:

1. Intent Compiler
2. World Model Builder
3. Critic Stack
4. Experiment Planner
5. Execution Engine
6. Evaluation Engine
7. Memory and Knowledge System

These services sit on top of the current LivePilot architecture:

- MCP server
- Remote Script inside Ableton Live
- M4L Analyzer and FluCoMa streams
- Device Atlas
- Technique Memory
- Browser, mixing, arrangement, theory, generative, and perception tools

### High-level flow

```text
User Goal
  -> Intent Compiler
  -> Goal Vector + Constraints

Session Reads
  -> World Model Builder
  -> Session Graph + Capability Map

World Model
  -> Critic Stack
  -> Issue Graph + Opportunity Graph

Issue / Opportunity Graph
  -> Experiment Planner
  -> Ranked Candidate Moves

Candidate Move
  -> Execution Engine
  -> Verification Reads
  -> Evaluation Engine

Evaluation Result
  -> Keep / Undo / Refine
  -> Memory Write Candidate
```

## 5. Modes

Agent OS v1 should support explicit internal modes. The user does not need to name them, but the system should route behavior through them.

### 5.1 Observe

Use when:

- the request is ambiguous
- the session state is unknown
- the system detects elevated technical fragility

Behavior:

- read-heavy
- minimal writes
- lower autonomy

### 5.2 Improve

Default mode.

Behavior:

- targeted diagnosis
- small reversible changes
- strong verification

### 5.3 Explore

Use when the user wants surprise, experimentation, freshness, or creative discovery.

Behavior:

- higher novelty budget
- looser constraints
- still reversible

### 5.4 Finish

Use for polish, cleanup, translation, prep, and finalization.

Behavior:

- lower novelty
- stronger preservation constraints
- increased technical and structural weighting

### 5.5 Diagnose

Use for "what is wrong here?", "why doesn't this work?", "what is masking what?"

Behavior:

- analysis-first
- minimal intervention
- highly explanatory

### 5.6 Research

Use for explicit knowledge gathering.

Behavior:

- no action until knowledge gaps are mapped
- source selection and synthesis
- technique distillation

### 5.7 Research-Augmented Improve

Use when the user wants both action and outside knowledge.

Behavior:

- inspect session first
- research only what is missing
- convert findings into candidate experiments
- test the best ones

### 5.8 Deep Research

Use for:

- multi-source synthesis
- unfamiliar plugins/devices
- artist/style study
- longer-form planning

Behavior:

- broader search
- source comparison
- distilled findings
- optional deferred action

## 6. Intent Compiler

The Intent Compiler converts natural language into explicit machine-usable goals.

The agent should not reason directly on vague adjectives. It should map them into `quality dimensions`.

### 6.1 Quality Dimensions

Core dimensions:

- energy
- punch
- weight
- density
- brightness
- warmth
- width
- depth
- motion
- contrast
- clarity
- cohesion
- groove
- tension
- novelty
- polish
- emotion

### 6.2 Goal Vector

Every request becomes a `GoalVector`.

```json
{
  "request_text": "make this more alive and more expensive",
  "targets": {
    "motion": 0.35,
    "contrast": 0.20,
    "depth": 0.18,
    "polish": 0.22
  },
  "protect": {
    "clarity": 0.90,
    "groove": 0.92,
    "headroom": 0.78
  },
  "mode": "improve",
  "research_mode": "none",
  "aggression": 0.45,
  "time_budget_sec": 25
}
```

### 6.3 Compiler Outputs

The compiler must always determine:

- primary target dimensions
- protected qualities
- aggression level
- novelty budget
- risk budget
- time budget
- whether research is required

### 6.4 Examples

`"make this hit harder"`

- punch up
- weight up
- energy up slightly
- preserve clarity and headroom

`"make this more emotional"`

- tension up
- contrast up
- depth up
- emotion up
- preserve coherence and groove

`"research how to make this pad sound more like a modern ambient texture"`

- mode = research-augmented improve
- style comparison required
- plugin/device technique lookup may be required

## 7. World Model Builder

The World Model is the agent's live representation of the session at a given moment.

It should be rebuilt every major loop and selectively refreshed after writes.

### 7.1 World Model Sections

- topology
- sonic state
- musical state
- structural state
- technical state
- taste state
- confidence state

### 7.2 Topology

Contains:

- tracks and inferred roles
- devices and order
- clip occupancy
- scenes
- routing
- sends and returns
- arrangement/session focus

### 7.3 Sonic State

Built from:

- `get_master_spectrum`
- `get_master_rms`
- `get_track_meters`
- `get_momentary_loudness`
- `get_onsets`
- `get_novelty`
- `get_chroma`
- `analyze_loudness`
- `analyze_spectrum_offline`
- `compare_to_reference`

Sonic state fields may include:

- frequency balance
- crest behavior
- transient activity
- stereo width proxy
- novelty/motion proxy
- loudness and headroom

### 7.4 Musical State

Built from:

- notes
- clip lengths and density
- theory and harmony tools
- tempo and timing

Fields may include:

- detected key
- harmonic density
- phrase repetition
- rhythmic density
- syncopation estimate
- motif repetition

### 7.5 Structural State

The system should infer:

- is this a loop, section, or full form?
- which section role is this material behaving like?
- where is contrast missing?
- where are transitions weak?

Structural inference is important because "better" changes by context:

- a loop needs variation and identity
- a verse needs support and space
- a drop needs impact and release
- a bridge needs contrast and recontextualization

### 7.6 Technical State

Contains:

- analyzer availability
- FluCoMa availability
- plugin health
- automation occupancy
- device controllability
- destructive-risk areas
- latency-sensitive areas

### 7.7 Taste State

Built from memory and current conversation.

Contains:

- user preferences
- prior accepted outcomes
- disliked moves
- genre/style priors

### 7.8 Confidence State

For every important subsystem, maintain a confidence estimate:

- goal interpretation confidence
- sonic diagnosis confidence
- plugin controllability confidence
- style transfer confidence
- research confidence

If confidence is low, autonomy should narrow.

## 8. Critic Stack

The Critic Stack is what makes Agent OS v1 "smart overall" instead of just procedural.

Each critic should emit:

- issues
- opportunities
- severity
- confidence
- evidence
- recommended move classes

### 8.1 Sonic Critic

Focus:

- spectrum
- masking
- harshness
- mud
- staticness
- width/depth
- transient behavior
- motion
- loudness/headroom

Example outputs:

- weak low-mid body
- kick and bass overlap
- top end too static
- stereo field underused
- dynamic contour flat

### 8.2 Musical Critic

Focus:

- groove quality
- rhythmic interest
- harmonic coherence
- melodic contour
- phrase shape
- call-and-response
- tension/release

Example outputs:

- groove too quantized
- phrase repeats without variation
- harmony lacks tension
- lead contour is flat

### 8.3 Structural Critic

Focus:

- section function
- contrast over time
- transitions
- pacing
- repetition fatigue

Example outputs:

- intro reveals too much too early
- drop lacks pre-release contrast
- verse loop never evolves

### 8.4 Technical Critic

Focus:

- plugin health
- analyzer gaps
- automation conflicts
- risk hotspots
- controllability constraints

Example outputs:

- plugin opaque or failed
- analyzer unavailable, perception confidence reduced
- parameter already automated

### 8.5 Taste Critic

Focus:

- user preference match
- genre convention fit
- prior success fit
- likely user reaction

Example outputs:

- current plan too bright for this user
- prior accepted drum treatments suggest drier space

## 9. Issue and Opportunity Graph

The outputs of all critics should be merged into a graph.

Each node:

- type
- scope
- severity
- confidence
- affected dimensions
- suggested move classes

This lets the planner reason explicitly about tradeoffs instead of chasing one sentence of prose.

## 10. Experiment Planner

The planner converts issues and opportunities into candidate interventions.

### 10.1 Candidate Move Schema

```json
{
  "name": "parallel_drum_glue",
  "intent": "increase weight and cohesion while preserving groove",
  "scope": {"tracks": [0], "devices": []},
  "actions": ["load_device", "set_params", "verify"],
  "expected_gain": 0.71,
  "risk": 0.22,
  "reversible": true,
  "confidence": 0.82,
  "verification_plan": ["spectrum", "rms", "novelty"]
}
```

### 10.2 Move Classes

- parameter tweak
- activate existing device
- insert device
- automation write
- note edit
- clip edit
- arrangement move
- routing/send move
- sample operation
- research-derived experiment

### 10.3 Ranking Logic

Rank candidates by:

- expected goal improvement
- risk
- reversibility
- confidence
- taste fit
- execution cost

Planner rule:

- choose the smallest high-confidence reversible move that meaningfully attacks the highest-severity issue without violating protected constraints

### 10.4 Budgets

Every loop should maintain:

- risk budget
- novelty budget
- latency budget
- change budget

These prevent overcooking.

## 11. Execution Engine

The Execution Engine performs the chosen move while maintaining strict discipline.

### 11.1 Rules

- never execute a move without a verification plan
- never batch unrelated changes
- re-read affected state after every write
- do not trust a loaded device until health-checked
- when in doubt, narrow scope

### 11.2 Execution Pattern

1. capture before-state
2. execute move
3. re-read affected objects
4. run verification reads
5. send everything to Evaluation Engine

### 11.3 Default Move Policy

Prefer this order for first intervention:

1. parameter tweak
2. subtle automation
3. activate/repair existing device
4. insert one device
5. note edit
6. arrangement edit

Avoid leading with:

- destructive sample ops
- large chain rebuilds
- multi-track changes
- heavy research
- broad automation rewrites

## 12. Evaluation Engine

The Evaluation Engine determines whether a move was truly beneficial.

### 12.1 Core Outputs

- goal progress
- collateral damage
- confidence
- keep or undo
- memory write candidate

### 12.2 Score Formula

Base score:

- `0.30 * goal_fit`
- `0.25 * measurable_delta`
- `0.15 * preservation`
- `0.10 * taste_fit`
- `0.10 * confidence`
- `0.10 * reversibility`

### 12.3 Hard Rules

- keep only if total score is above the current acceptance threshold
- undo if measurable improvement is zero or negative
- undo if protected qualities are harmed beyond tolerance
- narrow autonomy after repeated failures

### 12.4 Hybrid Evaluation Sources

Use:

- live analyzer metrics
- offline capture and perception
- symbolic/music heuristics
- structural heuristics
- taste priors
- user reaction

The engine must never rely only on one of these.

## 13. Research System

Research is a first-class subsystem, not an ad hoc fallback.

### 13.1 Research Modes

- none
- targeted
- deep
- background mining

### 13.2 Trigger Conditions

Trigger research when:

- the user explicitly requests it
- confidence is low around a plugin or technique
- style transfer is requested
- knowledge gaps block planning
- multiple candidate plans need outside evidence

### 13.3 Research Loop

```text
1. define research question
2. identify missing knowledge
3. inspect current session and available tools/devices
4. search selectively
5. extract relevant findings
6. normalize into LivePilot actions
7. rank for session fit
8. optionally test best findings
9. distill into technique cards
```

### 13.4 Source Policy

Prefer:

- official documentation
- device/plugin manuals
- high-signal forum threads
- respected producer tutorials
- multi-source corroboration

Avoid:

- generic SEO-style articles
- low-signal listicles
- advice that cannot be operationalized in-session

### 13.5 Research Output

Research should not end as links. It should end as `Technique Cards`.

```json
{
  "problem": "static percussion",
  "context": ["minimal house", "high-frequency percussion"],
  "devices": ["Auto Pan", "Utility", "modify_notes"],
  "method": "subtle unsynced auto-pan plus micro-timing variance",
  "why_it_works": "adds motion without destabilizing core groove",
  "risk": "low",
  "verification": ["motion up", "groove preserved", "mono center preserved"],
  "evidence": {"sources": 4, "in_session_tested": true}
}
```

## 14. Memory and Knowledge System

Memory should move beyond "save this chain" toward "remember what worked, for whom, and why."

### 14.1 Memory Types

- Identity Memory
- Taste Memory
- Outcome Memory
- Session Memory
- Technique Library
- Anti-Memory

### 14.2 Identity Memory

How the user likes to work:

- exploratory vs decisive
- subtle vs bold
- native vs plugin-heavy
- prefers dry vs wet space

### 14.3 Taste Memory

Stylistic preferences:

- favorite textures
- mix tendencies
- rhythmic feel
- harmonic language
- preferred devices

### 14.4 Outcome Memory

The most important type.

Store:

- goal
- context
- action
- measured result
- user reaction

### 14.5 Session Memory

Short-lived memory for:

- what was tried already
- what failed this session
- what is currently staged or newly changed

### 14.6 Anti-Memory

Store failures and dislikes explicitly so the agent does not repeat bad ideas.

### 14.7 Retrieval Policy

Memory should shape plans, not dominate them. It provides priors, not scripts.

## 15. Safety and Trust

Agent OS v1 should feel safe enough to use in a real session.

### 15.1 Safety Rules

- no blind writes
- no silent fallback
- no pretending unknown plugins are understood
- no hidden research actions
- no destructive bundles
- no heavy analysis without warning
- no irreversible experimentation without clear justification

### 15.2 Default Safety Pattern

For any non-trivial request:

1. read session
2. explain interpretation
3. try small reversible move
4. verify
5. report result
6. offer next direction

### 15.3 Failure Handling

When a move fails:

- undo if needed
- report what failed
- state confidence drop
- narrow the next move

## 16. User Experience Contract

Externally the system should remain extremely simple.

### 16.1 User Controls

Minimal steering vocabulary:

- push harder
- be more subtle
- go deeper
- research this
- undo last direction
- save this
- fresh approach

### 16.2 Response Pattern

At major checkpoints, the agent should communicate:

1. what it thinks the goal means
2. what it found
3. what it is trying next
4. what changed
5. what it recommends

The tone should feel like a producer, not a debugger.

## 17. Prompt Policy

The prompt layer should enforce:

- explicit goal compilation
- explicit world model
- critic stack invocation
- candidate ranking
- keep/undo discipline
- memory-writing rules
- research mode switching

The prompt is a policy layer, not the whole system.

## 18. Minimal Runtime Schemas

### 18.1 GoalVector

```json
{
  "request_text": "make this wider and cleaner",
  "targets": {"width": 0.30, "clarity": 0.25},
  "protect": {"weight": 0.80, "mono_compatibility": 0.88},
  "mode": "improve",
  "research_mode": "none",
  "aggression": 0.35,
  "time_budget_sec": 20
}
```

### 18.2 Issue

```json
{
  "type": "kick_bass_masking",
  "critic": "sonic",
  "scope": {"tracks": [0, 1]},
  "severity": 0.63,
  "confidence": 0.81,
  "evidence": ["sub overlap", "low-mid congestion"],
  "recommended_move_classes": ["parameter_tweak", "automation", "routing"]
}
```

### 18.3 CandidateMove

```json
{
  "name": "bass_duck_under_kick",
  "move_class": "automation",
  "intent": "preserve groove while reducing kick/bass masking",
  "expected_gain": 0.69,
  "risk": 0.18,
  "confidence": 0.79,
  "reversible": true,
  "verification_plan": ["spectrum", "rms", "groove_check"]
}
```

### 18.4 EvaluationRecord

```json
{
  "before": {"sub": 0.42, "clarity": 0.51},
  "after": {"sub": 0.39, "clarity": 0.64},
  "goal_progress": 0.72,
  "collateral_damage": 0.09,
  "keep_change": true,
  "notes": "Masking improved without flattening groove"
}
```

## 19. Phased Rollout

### Phase 1

- new agent prompt
- goal vector
- world model skeleton
- critic stack v1
- simple evaluation + undo policy

### Phase 2

- outcome memory
- technique cards
- targeted research mode
- stronger structural critic

### Phase 3

- deep research mode
- background technique mining
- richer scoring and user-personalization
- broader section and form intelligence

## Implementation Touchpoints

The most likely initial implementation touchpoints in the current repo are:

- `livepilot/agents/livepilot-producer/AGENT.md`
- `livepilot/skills/livepilot-core/SKILL.md`
- `mcp_server/server.py`
- `mcp_server/tools/perception.py`
- `mcp_server/tools/analyzer.py`
- `mcp_server/tools/automation.py`

This proposal does not require an immediate rewrite. It can be introduced incrementally by:

1. tightening the producer-agent policy and response contract
2. adding explicit runtime schemas for goal, issue, candidate move, and evaluation
3. introducing an evaluator loop and outcome memory before deeper autonomy work

## 20. Success Metrics

Agent OS v1 is succeeding if:

- users can make high-level requests with fewer clarifying turns
- more interventions are kept on first or second attempt
- fewer accepted changes are later undone
- user taste alignment improves over time
- research produces reusable internal knowledge rather than one-off links
- the product feels simpler externally while becoming more capable internally

## 21. Summary

LivePilot Agent OS v1 is not "a better prompt."

It is an operating system for production intelligence:

- compile goals explicitly
- model the session deeply
- critique from multiple angles
- plan reversible experiments
- evaluate outcomes rigorously
- learn what works
- research intelligently when needed

The result should be a LivePilot experience that feels simple to the user, advanced under the hood, and trustworthy in real creative work.

---

## Appendix: Phase 1 Implementation (v1.9.15)

### What Was Built

- **`_agent_os_engine.py`** — Pure-computation engine with GoalVector, WorldModel, SonicCritic (6 heuristics), TechnicalCritic, and evaluation scorer with hard-rule enforcement
- **`agent_os.py`** — 3 MCP tools: `compile_goal_vector`, `build_world_model`, `evaluate_move`
- **Producer agent rewrite** — AGENT.md transformed from linear 11-step pipeline to cyclical evaluation loop with mode-specific behavior
- **Outcome memory** — New `outcome` technique type for storing evaluation results
- **38 unit tests + 8 contract tests** covering all engine logic and tool registration

### Phase 1 Limitations

- **8 of 17 quality dimensions are measurable** (brightness, warmth, weight, width, clarity, density, energy, punch). The remaining 9 (motion, contrast, groove, tension, novelty, polish, emotion, cohesion, depth) get `confidence=0.0` — the agent defers to its own musical judgment for those.
- **No taste memory integration** — Phase 2 will add user preference tracking via outcome memory analysis
- **No research system** — Phase 2 will add targeted research mode
- **Structural critic absent** — Phase 2 will add section-role inference and arrangement analysis
- **Musical critic absent** — Phase 2 will add groove/harmony quality analysis from theory tools

### Tool Count Change

178 → 181 (3 new tools in `agent_os` domain).

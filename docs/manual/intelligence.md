# The Intelligence Layer

LivePilot has 12 engines that sit on top of 320 tools. This chapter explains how they work together — not what each one does in isolation, but how a production request flows through them.

---

## The Flow

Every request follows this path:

```
Your request
    │
    ▼
Conductor (route_request)
    │ → which engines? which workflow?
    ▼
Session Kernel (get_session_kernel)
    │ → full snapshot: tracks, capabilities, taste, memory
    ▼
Engine Analysis (analyze_mix, analyze_sound_design, detect_stuckness...)
    │ → what's the problem? what are the options?
    ▼
Semantic Moves (propose_next_best_move)
    │ → high-level intents ranked by taste fit
    ▼
Preview Studio (create_preview_set, render_preview_variant)
    │ → hear each option before committing
    ▼
Commit or Reject
    │ → taste graph and session continuity updated
    ▼
Evaluation (evaluate_move)
    │ → did it actually help?
```

You don't need to call these tools manually. Describe what you want and the AI follows this flow. But understanding it helps you ask better questions and troubleshoot when things feel off.

---

## Conductor — Where Requests Go

When you say "tighten the low end" or "find me a dark vocal sample," the conductor classifies your request and routes it to the right engines.

```
route_request(request_text="tighten the low end")
→ primary_engine: mix_engine
→ entry_tool: analyze_mix
→ workflow_mode: guided_workflow
```

```
route_request(request_text="slice this break into a groove")
→ primary_engine: sample_engine
→ entry_tool: plan_slice_workflow
→ workflow_mode: slice_workflow
```

The conductor knows about every engine and matches keywords to routing patterns. Mixed requests get multi-engine routing — "find a vocal and chop it for the chorus" routes to both `sample_engine` and `composition`.

### Workflow modes

| Mode | When | Behavior |
|------|------|----------|
| `guided_workflow` | Default | Step-by-step with your approval at each stage |
| `quick_fix` | "just fix," "undo" | Minimal steps, fast execution |
| `creative_search` | "try," "explore," "surprise me" | Multiple variants, experiment-friendly |
| `agentic_loop` | "polish everything," "finish it" | Multi-step plan-and-evaluate loop with explicit checkpoints |
| `performance_safe` | "live," "performing" | Safety constraints, no risky moves |
| `sample_discovery` | "find me a sample" | Sample Engine first |
| `slice_workflow` | "slice this," "chop" | Slice-focused pipeline |
| `sample_plus_arrangement` | "chop this for the chorus" | Sample + arrangement planning |

---

## Session Kernel — The Snapshot

`get_session_kernel` assembles everything the engines need to make decisions:

- **Session info** — tempo, tracks, scenes, devices, clips
- **Capability state** — what's available (analyzer? bridge? memory?)
- **Action ledger** — what was just done, what was undone
- **Taste graph** — which moves/devices/families you prefer
- **Anti-preferences** — what you've explicitly rejected
- **Session memory** — observations and decisions from this session
- **Routing hints** — recommended engines and workflow from the conductor

The kernel is the shared context that all engines read from. It prevents engines from contradicting each other or repeating rejected moves.

---

## Semantic Moves — What, Not How

A semantic move is a musical intent — "add contrast," "tighten the low end," "recover energy" — that compiles into a sequence of concrete tool calls.

```
list_semantic_moves(domain="mix")
→ make_punchier, tighten_low_end, widen_stereo, darken_without_losing_width, ...

preview_semantic_move(move_id="make_punchier")
→ steps: [set_device_parameter(Compressor, Attack, 2ms), ...]
→ risk_level: low
→ targets: {punch: +0.5, energy: +0.3}
→ protect: {clarity: 0.7}
```

Each move carries:
- **Targets** — what dimensions it pushes (energy, clarity, tension, etc.)
- **Protection thresholds** — what dimensions it must not damage
- **Risk level** — low/medium/high, affecting how much identity can change
- **Compiled plan** — real tool calls from the semantic compiler

### Available domains

`list_semantic_moves()` shows all registered moves. Current families: mix, arrangement, transition, sound_design, performance, sample, device_creation.

### Applying a move

```
apply_semantic_move(move_id="make_punchier", mode="improve")
→ returns compiled plan for your approval

apply_semantic_move(move_id="make_punchier", mode="explore")
→ executes immediately, captures before/after
```

Modes: `improve` (plan + approval), `explore` (execute + capture), `observe` (plan only, never execute), `diagnose` (plan only).

---

## Wonder Mode — Stuck Rescue

When a session is stuck — repeated undos, overpolished loops, no structural progress — Wonder Mode activates.

```
enter_wonder_mode(request_text="I keep tweaking this loop and it's not going anywhere")
```

### What happens inside

1. **Diagnosis** — classifies why you're stuck (loop trap? missing contrast? identity unclear? stale drums?)
2. **Move discovery** — searches the semantic move registry for moves that address the diagnosis
3. **Sample search** — if diagnosis involves samples (stale drums, no organic texture), auto-searches for candidates
4. **Distinct selection** — ensures each variant is genuinely different (different move family or execution shape)
5. **Compilation** — each move is compiled through the semantic compiler with real session context
6. **Taste ranking** — variants scored by taste fit, identity preservation, novelty, and coherence

### What you get back

Up to 3 variants labeled `safe`, `strong`, `unexpected`:
- **Safe** — low risk, preserves identity, familiar approach
- **Strong** — moderate risk, pushes one dimension meaningfully
- **Unexpected** — high novelty, may reframe the track's direction

Each variant has a `compiled_plan` with real tool calls, or is marked `analytical_only` if no executable plan could be built.

### Preview, commit, or reject

```
create_preview_set(request_text="...", wonder_session_id="ws_...")
render_preview_variant(set_id="...", variant_id="...")
→ applies variant → captures audio → undoes → returns comparison

commit_preview_variant(set_id="...", variant_id="...")
→ applies permanently, records taste signal

discard_wonder_session(wonder_session_id="ws_...")
→ rejects all variants, records negative taste signal
```

---

## SongBrain — What the Song Is

```
build_song_brain()
→ identity_core: "driving minimal techno with hypnotic hi-hat patterns"
→ sacred_elements: [{element: "the main groove", reason: "defines the track"}]
→ section_purposes: [{section: "intro", purpose: "build anticipation"}]
→ energy_arc: [0.3, 0.5, 0.8, 1.0, 0.6]
```

SongBrain builds a real-time model of what the track IS, what must not be casually damaged (sacred elements), and where the energy is heading. Other engines read this to avoid identity drift.

```
detect_identity_drift()
→ drift_detected: true
→ reason: "recent changes pulled energy arc away from building tension"
```

---

## Taste Graph — What You Like

The taste graph learns your preferences across sessions. Every accept/reject/undo updates it.

```
get_taste_graph()
→ move_family_preferences: {mix: 0.7, arrangement: 0.3, sample: 0.8}
→ device_affinities: {Drift: 0.9, Wavetable: 0.6}
→ novelty_band: 0.45 (moderate — you like some surprise but not too much)
```

```
record_positive_preference(dimension="punch", context="drum bus compression")
record_anti_preference(dimension="harsh_highs", context="too much air EQ")
```

Two producers using the same tools get different recommendations because their taste graphs diverge.

---

## Evaluation — Did It Help?

Every engine follows: measure before → act → measure after → compare.

```
evaluate_move(
    move_description="Added parallel compression to drums",
    before_snapshot={...},
    after_snapshot={...}
)
→ improved: ["punch", "cohesion"]
→ degraded: ["headroom"]
→ recommendation: "keep — punch improvement outweighs slight headroom reduction"
```

If a change made things worse, the system flags it before you move on.

---

## Mix Engine — Critic-Driven Analysis

The Mix Engine goes beyond manual mixing. It runs automated critics:

```
analyze_mix()
→ masking_issues: [{tracks: [0, 1], range: "200-400Hz", severity: "high"}]
→ headroom: -2.1 dB (too hot)
→ stereo_balance: 0.12 (slightly right-heavy)
→ dynamics_range: 6.2 dB (compressed)

plan_mix_move(issue="masking between kick and bass at 200-400Hz")
→ steps: [EQ cut on bass at 300Hz, slight boost on kick at 80Hz]

evaluate_mix_move(before=..., after=...)
→ masking reduced by 40%, headroom improved
```

The critics are `get_masking_report`, `get_mix_issues`, `get_mix_summary`. The planner is `plan_mix_move`. The evaluator is `evaluate_mix_move`.

---

## How They Connect

Here's the key insight: **the engines don't run in isolation.** A typical "I'm stuck" session might flow like this:

1. Conductor routes to `stuckness_detector` + `wonder_mode`
2. Stuckness detector identifies "overpolished loop" pattern
3. Wonder Mode searches for rescue moves across mix, arrangement, and sample domains
4. Sample Engine finds a texture candidate from your Splice library
5. Semantic compiler builds 3 variant plans with real tool calls
6. Taste graph ranks them (you prefer sample-based moves, moderate novelty)
7. Preview Studio lets you hear each variant
8. You commit one → taste graph updated, creative thread resolved
9. Evaluation confirms the change improved the session

No single engine could do all of that. The power is in the connections.

---

Next: [Device Atlas](device-atlas.md) | Back to [Manual](index.md)

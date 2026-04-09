---
name: livepilot-evaluation
description: This skill should be used when the user asks to "evaluate a change", "was that good", "keep or undo", "A/B compare", "rate my change", "check if that helped", or wants to use the universal evaluation loop to judge production moves.
---

# Evaluation Engine — Universal Move Judgment

The evaluation engine is the shared decision layer used by all other engines (mix, sound design, composition, performance). It determines whether a change improved the session, and whether to keep it, undo it, or learn from it.

## The Universal Evaluation Loop

Every production move follows this loop regardless of which engine initiated it.

### Step 1 — Compile Goal Vector

Call `compile_goal_vector(goal, mode)` to establish what you are trying to achieve.

**Goal**: a plain-text description of the intended improvement (e.g., "reduce masking between bass and kick in 100-200 Hz range").

**Modes** control how aggressively you act:

- `observe` — read-only analysis, no changes. Use for diagnostics and status checks.
- `improve` — targeted fixes for specific issues. The default mode. Make the smallest change that addresses the problem.
- `explore` — creative experimentation. Wider parameter ranges, more tolerance for unexpected results. Use when the user says "try something", "experiment", or "surprise me".
- `finish` — polish and finalize. Conservative moves only, protect what already works. Use when the user says "almost done", "final touches", or "wrap it up".
- `diagnose` — identify problems without fixing them. Like observe but with critic analysis. Use when the user says "what's wrong" without asking for fixes.

### Step 2 — Build World Model

Call `build_world_model` to snapshot the current session state and available capabilities:

- Session info: tracks, clips, devices, tempo, time signature
- Capability state: analyzer connected, M4L bridge active, FluCoMa available
- Recent actions: last moves taken and their outcomes
- Active constraints: performance mode safety limits, user anti-preferences

The world model determines what tools are available and what measurements are possible.

### Step 3 — Get Turn Budget

Call `get_turn_budget(mode)` to determine how many moves you should make this turn:

- `observe` / `diagnose`: 0 moves (read-only)
- `improve`: 1-3 moves per turn, evaluate after each
- `explore`: 1-5 moves per turn, wider tolerance
- `finish`: 1 move per turn, strict evaluation

Do not exceed the turn budget. If more work is needed, complete the current turn, report progress, and start a new turn.

### Step 4 — Capture Before

Take measurements appropriate to the engine context:

- **Mix engine**: `get_master_spectrum` + `get_master_rms`
- **Sound design**: `get_device_parameters` + `get_master_spectrum`
- **Composition**: `get_notes` or `get_arrangement_notes` + `get_section_graph`
- **Universal**: `get_mix_snapshot` for full session state

Always capture before executing. Without a before snapshot, evaluation is meaningless.

### Step 5 — Execute Intervention

Apply the planned change using the appropriate tool. Execute exactly one move, then proceed to evaluation.

### Step 6 — Capture After

Repeat the same measurements from Step 4. Use identical tool calls to ensure comparable data.

### Step 7 — Evaluate

Call the appropriate evaluator:

- `evaluate_move(before_snapshot, after_snapshot, goal)` — universal evaluator, works for any engine
- `evaluate_mix_move(before_snapshot, after_snapshot, targets, protect)` — mix-specific with protection constraints
- `evaluate_composition_move(before_snapshot, after_snapshot, goal)` — composition-specific
- `evaluate_with_fabric(before_snapshot, after_snapshot, goal)` — uses memory fabric for taste-aware judgment

### Step 8 — Read the Verdict

Every evaluator returns:

- `keep_change` (bool): whether the change should stay
- `score` (0.0-1.0): magnitude of improvement (0.5 = neutral, >0.5 = better, <0.5 = worse)
- `goal_progress` (0.0-1.0): how much closer to the stated goal
- `collateral_damage` (list): things that got worse as a side effect
- `explanation` (string): human-readable judgment summary

### Step 9 — Keep or Undo

If `keep_change` is `false`:
1. Call `undo()` immediately
2. Report to the user: what was tried, why it was undone, citing `collateral_damage`
3. Consider an alternative approach for the same goal

If `keep_change` is `true`:
1. Report the improvement with score and explanation
2. If `score > 0.7`, this is a memory promotion candidate (see below)

### Step 10 — Repeat or Stop

Check turn budget remaining. If budget allows and goal_progress < 1.0, return to Step 4 for the next move. Otherwise, summarize progress and stop.

## Capability Modes

The world model includes a capability state that affects what measurements are available. Call `get_capability_state` to check.

### normal
Full measured evaluation. M4L analyzer connected, all spectral/RMS/key tools available. Critics use real data. This is the best mode.

### measured_degraded
Analyzer data is stale (older than 5 seconds) or intermittent. Measurements may not reflect current state. Re-trigger analysis before trusting cached values. Inform the user that data freshness is limited.

### judgment_only
No analyzer connected. Evaluation relies on device parameter changes, track structure, and role-based heuristics. Critics cannot use spectral evidence. Inform the user: "Evaluation is based on parameter analysis only — spectral verification unavailable."

### read_only
Session disconnected or in an error state. No tools can modify the session. Only read operations from cached data. Inform the user and suggest reconnecting.

## Action Ledger

Every move is recorded in the action ledger for accountability and learning.

- `get_action_ledger_summary` — summary of all actions taken this session with scores
- `get_recent_actions` — last N actions with full detail
- `get_last_move` — the most recent action and its evaluation result

Use the ledger to avoid repeating failed approaches. If a move type has been undone twice for the same issue, try a different strategy.

## Memory Promotion

Successful moves can be promoted to persistent memory for future sessions.

- `get_promotion_candidates` — list moves from this session that scored > 0.7 and are eligible for saving
- `memory_learn(type, data)` — save a technique to memory (mix_template, sound_design, composition, etc.)
- `record_anti_preference(description)` — record something the user explicitly rejected, so it is never suggested again

### Promotion Rules

1. Only promote moves the user confirmed satisfaction with — a high score alone is not enough
2. Anti-preferences are permanent until explicitly deleted
3. Check `get_anti_preferences` before suggesting any move to avoid repeating rejected ideas
4. Promotion is optional — never force it. Suggest when appropriate: "That scored 0.85 — want me to save this technique for future sessions?"

## A/B Comparison

When the user asks "was that good?" or "A/B compare":

1. The before snapshot is A, the after snapshot is B
2. Call the evaluator to get the score
3. Present the comparison: "Before: [metrics]. After: [metrics]. Score: [score]. [explanation]"
4. If the user prefers A, call `undo()` to revert to it
5. If the user prefers B, keep the current state

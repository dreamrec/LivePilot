# Action Ledger v1

Status: proposal

Audience: runtime, evaluation, memory, debugging, and UX owners

Purpose: define the durable record of what the agent tried, why it tried it, what changed, and whether the system kept or undid the move.

Action Ledger is the system’s memory of behavior inside a session.

It is not long-term taste memory.
It is the per-session execution spine that makes the agent debuggable, reversible, and learnable.

## 1. Why This Exists

Without an action ledger, LivePilot loses track of:

- what it already tried
- which move caused which result
- whether a bad state came from the user or the agent
- what to undo safely
- which outcomes are worthy of memory

Every advanced engine depends on this.

Composition needs it to avoid repeating failed structure moves.
Mix needs it to attribute sonic change correctly.
Research needs it to distinguish applied tactics from untested ideas.

## 2. Design Goals

Action Ledger v1 should:

- record every agent-initiated mutation
- group related low-level tool calls into one semantic move
- capture before/after references and evaluation results
- support safe undo grouping
- expose a clean audit trail for debugging and review

It should not:

- become a giant raw log dump
- store all transport messages
- duplicate the full session state on every step

## 3. Core Unit: Semantic Move

The ledger should not think in terms of individual tool calls first.

Its core unit is a `semantic move`.

Examples:

- "subtractive verse setup on drums and hats"
- "low-mid cleanup on bass bus"
- "bar-8 delay throw transition"
- "reference-informed width refinement on lead bus"

Each semantic move may contain many low-level actions, but it should be evaluated and remembered as one deliberate intervention.

## 4. Data Model

```json
{
  "ledger_entry": {
    "id": "move_0012",
    "timestamp_ms": 0,
    "engine": "composition",
    "move_class": "transition_gesture",
    "intent": "make the section arrival feel earned",
    "scope": {
      "tracks": [3, 5],
      "clips": ["clip_17"],
      "devices": ["track_3.device_2"]
    },
    "planning_context": {
      "goal_vector_id": "goal_01",
      "critic_findings": ["weak_transition", "repetition_fatigue"],
      "capability_mode": "normal"
    },
    "before_refs": {
      "snapshot_id": "snap_before_12",
      "world_model_hash": "abc123"
    },
    "actions": [
      {"tool": "set_automation", "summary": "opened low-pass over 1 bar"},
      {"tool": "adjust_send", "summary": "added delay throw on final hit"}
    ],
    "after_refs": {
      "snapshot_id": "snap_after_12",
      "world_model_hash": "def456"
    },
    "evaluation": {
      "decision_mode": "measured_keep",
      "kept": true,
      "goal_progress": 0.68,
      "collateral_damage": 0.09
    },
    "undo_group_id": "undo_12",
    "memory_candidate": true
  }
}
```

## 5. Required Fields

Every entry should include:

- unique id
- owning engine
- semantic intent
- scope
- normalized action summaries
- before/after refs
- evaluation result
- undo grouping

Optional fields:

- research provenance
- reference provenance
- user confirmation requirement
- taste-prior contribution

## 6. Storage Model

Suggested implementation:

- in-memory session ledger for fast writes
- optional persisted session artifact for debugging

Suggested modules:

- `mcp_server/runtime/action_ledger.py`
- `mcp_server/runtime/action_ledger_models.py`

Suggested artifacts:

- `SessionLedger`
- `LedgerEntry`
- `UndoGroup`

## 7. Relationship To Undo

Undo needs a stronger abstraction than "last tool call".

The ledger should group low-level mutations into logical undo scopes:

- `micro`
- `phrase`
- `section`
- `mix`
- `project`

This lets the conductor say:

- undo last composition move
- revert the last mix pass
- compare before and after the last transition experiment

## 8. Relationship To Memory

Only kept ledger entries with enough evidence should become memory candidates.

Promotion rule:

- semantic move exists
- evaluation exists
- keep decision is explicit
- context is rich enough to be useful later

This keeps memory clean and grounded.

## 9. Relationship To Research

If a move comes from research, the ledger should store:

- provider type
- technique-card id
- source confidence

This is important because the system must later answer:

- did the researched tactic actually work here
- which research patterns lead to good outcomes

## 10. API Surface

Suggested methods:

- `start_move_entry()`
- `append_action_to_move()`
- `finalize_move_entry()`
- `record_evaluation()`
- `get_last_move()`
- `get_recent_moves(engine=None, kept=None)`
- `get_undo_group(id)`

Suggested MCP wrapper later:

- `get_action_ledger_summary`

## 11. UX Surface

User-facing summaries should read like:

- "I tried a subtractive arrangement move on the drums and hats, and kept it because the section now has a clearer arrival."
- "The last widening pass hurt center stability, so I rolled it back."

Not:

- "set parameter x from 0.13 to 0.42"

Low-level detail can still exist for debugging.

## 12. Testing Requirements

Must cover:

- one semantic move with multiple tool calls
- kept vs undone moves
- proper undo grouping
- research-attributed move entries
- memory promotion candidates
- interleaving composition and mix moves in one session

## 13. Build Order

1. Define contracts.
2. Implement in-memory ledger store.
3. Add move lifecycle hooks to Agent OS.
4. Attach evaluation records.
5. Wire memory promotion hooks.
6. Add user-facing summary formatter.

## 14. Exit Criteria

Action Ledger v1 is done when:

- every agent mutation produces one semantic ledger entry
- the system can explain what it changed and why
- undo can operate on move scopes, not just raw transport order
- memory promotion depends on ledger-backed evidence

# Memory Fabric v2

Status: proposal

Audience: memory, runtime, research, evaluation, and product owners

Purpose: define the shared memory substrate that turns session outcomes into reusable musical intelligence without turning LivePilot into a generic vector-store project.

Memory Fabric v2 is where LivePilot becomes personally and musically cumulative.

## 1. Why This Exists

Current memory is useful, but too narrow if the system is expected to grow into:

- Agent OS
- Composition Engine
- Mix Engine
- Sound Design Engine
- Reference Engine
- Research Engine

Those systems do not just need "saved techniques."

They need:

- preference priors
- outcome priors
- anti-patterns
- context-aware retrieval
- clean promotion rules

## 2. Design Goals

Memory Fabric v2 should:

- store outcomes, not only recipes
- distinguish short-lived session memory from durable memory
- support taste adaptation without hard-locking creativity
- track failures and user dislikes
- provide structured retrieval for planners and critics

It should not:

- become an uncurated dumping ground
- save low-evidence memories automatically
- collapse all memory types into one record

## 3. Memory Classes

v2 should explicitly separate:

- `session_memory`
- `outcome_memory`
- `taste_memory`
- `anti_memory`
- `technique_cards`
- `reference_memory`

### 3.1 Session Memory

Short-lived memory for the current project/session.

Examples:

- what has already been tried
- which section the user is focusing on
- current reference choices

### 3.2 Outcome Memory

The most important class.

Stores:

- goal
- context
- move
- evaluation result
- user reaction

### 3.3 Taste Memory

Longer-lived user preferences such as:

- automation boldness tolerance
- density preference
- favored device families
- section pacing taste

### 3.4 Anti-Memory

What should not be repeated lightly.

Examples:

- user repeatedly rejects hard stereo widening on leads
- user dislikes over-busy drum fills
- certain plugin chains tend to degrade clarity in this workflow

### 3.5 Technique Cards

Distilled operational knowledge.

These can come from:

- repeated successful outcomes
- explicit research
- curated internal library

### 3.6 Reference Memory

Stores reusable knowledge about artist/style references:

- common density arc
- transition language
- arrangement pacing
- mix posture

## 4. Data Contracts

### 4.1 Outcome Memory

```json
{
  "type": "outcome_memory",
  "goal": ["clearer_transition", "more_tension"],
  "context": {
    "engine": "composition",
    "material": "8-bar build",
    "genre": "garage",
    "tempo": 132
  },
  "move": {
    "class": "transition_gesture",
    "summary": "one-bar filter inhale plus tail throw"
  },
  "evaluation": {
    "goal_progress": 0.73,
    "collateral_damage": 0.11,
    "kept": true
  },
  "user_reaction": "liked",
  "evidence_refs": ["move_0012"]
}
```

### 4.2 Taste Memory

```json
{
  "type": "taste_memory",
  "dimension": "automation_boldness",
  "preference": "moderate_to_high",
  "confidence": 0.77,
  "evidence_count": 9
}
```

### 4.3 Anti-Memory

```json
{
  "type": "anti_memory",
  "pattern": "wide_lead_on_every_phrase",
  "reason": "repeatedly reduced focus and user rejected it",
  "confidence": 0.83
}
```

## 5. Retrieval Model

Retrieval must be structured, not vague semantic search only.

Preferred retrieval keys:

- goal type
- engine
- material role
- genre/style
- tempo zone
- section type
- device family
- user taste profile

Retrieval should answer:

- what worked in similar contexts
- what failed in similar contexts
- what the user usually prefers

## 6. Promotion Rules

No memory should be promoted without enough evidence.

Suggested minimums:

- ledger-backed move
- explicit keep/undo result
- context-rich metadata
- no contradiction from repeated user feedback

For durable taste memory, require:

- repeated evidence across multiple sessions or situations

## 7. Module Layout

Suggested modules:

- `mcp_server/memory/fabric.py`
- `mcp_server/memory/models.py`
- `mcp_server/memory/retrieval.py`
- `mcp_server/memory/promotion.py`
- `mcp_server/memory/taste_inference.py`

## 8. Engine Integration

### 8.1 Composition Engine

Uses outcome memory to rank motif, transition, and section moves.

### 8.2 Mix Engine

Uses taste memory for density, width, brightness, and glue preferences.

### 8.3 Research Engine

Uses technique cards and prior outcome evidence to filter external findings.

### 8.4 Reference Engine

Uses reference memory to translate artist/style requests into concrete deltas.

## 9. Safety Rules

- low-confidence memories must not override live evidence
- anti-memory should lower ranking, not permanently ban experimentation
- research-derived technique cards should be tagged separately until validated in-session

## 10. Testing

Must cover:

- promotion from ledger to outcome memory
- anti-memory retrieval lowering candidate rank
- taste inference across repeated accepted moves
- conflict resolution between memory and current measured evidence

## 11. Build Order

1. Define models.
2. Implement session vs durable memory separation.
3. Add ledger-backed outcome promotion.
4. Add taste inference.
5. Add anti-memory.
6. Add research-backed technique-card promotion.

## 12. Exit Criteria

Memory Fabric v2 is done when:

- the planner can retrieve relevant successful and failed prior outcomes
- taste affects ranking without becoming dogma
- accepted research tactics can become reusable local knowledge
- session memory and durable memory are cleanly separated

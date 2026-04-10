# Wonder Mode V1.5 Design Spec

## Summary

Wonder Mode becomes a **preview-first stuck-rescue workflow** for active Ableton sessions. Its job is to take a user who is circling, under-inspired, or asking for lift, and produce 1-3 genuinely distinct, executable, identity-aware options that can be previewed, compared, committed, and learned from.

This is a surgical upgrade (Approach 1): existing modules keep their engine/tools separation. A thin `WonderSession` coordinator adds the missing lifecycle glue without forcing modules to lose independence.

## Product Decisions

- Wonder is primarily a **stuck-rescue tool**, not the default mode for all creative requests.
- The main UX is **preview-first A/B/C**: safe, strong, unexpected — but only when all three are genuinely distinct.
- It is **local/session-first**. External inspiration and providers are out of scope.
- If the system cannot produce three distinct executable variants, it returns fewer and explains why. Analytical variants are returned with honest `analytical_only: true` labeling.
- The default commit flow is **manual user choice after preview/comparison**, not automatic application.
- Turn resolution is only recorded when the user commits or rejects — never at proposal time.

## Problems This Solves

| Current problem | Root cause | Fix |
|---|---|---|
| Same move under 3 labels | `assign_moves_to_tiers` reuses moves when <3 match | `select_distinct_variants` enforces real difference by move_id, family, or plan shape |
| Analytical variants pretend to be executable | `build_analytical_variant` returns same structure, no flag | `analytical_only: true` field; preview/commit refuse analytical variants |
| Session continuity noise | `enter_wonder_mode` records "proposed" turn before user sees anything | No turn recorded at generation; only commit/reject record turns |
| Two variant types, no unification | Wonder returns dicts, Preview Studio uses PreviewVariant dataclass | WonderSession holds canonical variant list; Preview Studio adapts at boundary |
| No diagnosis | Wonder starts from raw keyword matching | New diagnosis builder consults stuckness, SongBrain, action ledger, creative threads |
| Wonder and Preview Studio disconnected | No shared lifecycle | WonderSession links them via `wonder_session_id` and `preview_set_id` |

## Architecture

### Approach: Surgical Upgrade

Keep all existing modules and their engine/tools separation. Add:
- `WonderSession` dataclass + in-memory store (thin coordinator)
- `WonderDiagnosis` dataclass + builder (structured diagnosis)
- Distinctness enforcement in variant generation
- Lifecycle hooks in Preview Studio's commit/discard paths
- Session continuity discipline (no premature turn recording)

Modules remain independently testable and usable outside Wonder.

## Section 1: WonderSession + Diagnosis

### WonderSession (`wonder_mode/session.py`)

A thin runtime object that ties the lifecycle together. Stored in-memory with eviction like `PreviewSet`.

```python
@dataclass
class WonderSession:
    session_id: str
    request_text: str
    kernel_id: str = ""

    # Diagnosis (filled at creation)
    diagnosis: WonderDiagnosis | None = None

    # Lifecycle references
    creative_thread_id: str = ""
    preview_set_id: str = ""

    # Variants (the canonical list)
    variants: list[dict] = field(default_factory=list)
    recommended: str = ""
    variant_count_actual: int = 0  # how many are executable

    # Outcome
    selected_variant_id: str = ""
    outcome: str = "pending"  # pending, committed, rejected_all, abandoned

    # Degradation
    degraded_reason: str = ""  # why fewer variants or analytical-only

    status: str = "diagnosing"  # diagnosing, variants_ready, previewing, resolved
```

### WonderDiagnosis (`wonder_mode/session.py`)

```python
@dataclass
class WonderDiagnosis:
    trigger_reason: str          # "user_request", "stuckness_detected", "repeated_undos"
    problem_class: str           # from stuckness rescue types, or "exploration"
    current_identity: str        # from SongBrain.identity_core
    sacred_elements: list[dict]  # from SongBrain
    blocked_dimensions: list[str]  # dimensions that aren't progressing
    candidate_domains: list[str]   # which move families to search
    variant_budget: int = 3
    confidence: float = 0.0
    degraded_capabilities: list[str] = field(default_factory=list)
```

### Diagnosis builder (`wonder_mode/diagnosis.py`)

Builds a `WonderDiagnosis` from available session state. Each input is optional — the builder degrades gracefully.

**Logic:**
1. Run stuckness detection on action ledger -> get `problem_class` and `confidence`
2. Read SongBrain -> get `current_identity`, `sacred_elements`, `identity_confidence`
3. Check open creative threads -> prioritize domains with unresolved threads
4. Map `problem_class` -> `candidate_domains`:
   - `overpolished_loop` -> `[arrangement, transition]`
   - `identity_unclear` -> `[sound_design, mix]`
   - `contrast_needed` -> `[transition, arrangement, sound_design]`
   - `hook_underdeveloped` -> `[sound_design, mix]`
   - `too_dense_to_progress` -> `[mix, arrangement]`
   - `too_safe_to_progress` -> `[sound_design, transition]`
   - `section_missing` -> `[arrangement, transition]`
   - `transition_not_earned` -> `[transition, arrangement]`
   - `exploration` -> `None` (no domain restriction, search all)
5. Record `degraded_capabilities` if SongBrain, stuckness, or taste data is missing

**Key rule:** If stuckness confidence is 0 (user just asked, not actually stuck), diagnosis still runs with `trigger_reason: "user_request"` and `problem_class: "exploration"`.

## Section 2: Variant Generation + Distinctness Enforcement

### Changes to `wonder_mode/engine.py`

**`discover_moves`** — accepts optional `candidate_domains` from diagnosis to narrow search by move family.

**`assign_moves_to_tiers` replaced by `select_distinct_variants`:**

```python
def select_distinct_variants(
    scored_moves: list[dict],
    diagnosis: dict | None = None,
) -> list[dict]:
    """Select genuinely distinct moves for variant generation.

    Rules:
    - Each variant must differ by move_id, family, or compile_plan shape
    - Novelty envelope scaling alone is NOT enough for distinctness
    - Returns 0-3 moves. Caller pads with analytical variants if needed.
    """
```

**Distinctness logic:**
1. Group scored moves by `(move_id, family)`
2. Pick the top move -> slot 1
3. From remaining, pick first with different family OR different compile_plan shape -> slot 2
4. From remaining, pick one different from both -> slot 3
5. Return only what was genuinely found (0, 1, 2, or 3)

**Compile plan shape** = the set of tool names in the plan. Two moves with `[set_track_volume, set_track_send]` vs `[set_device_parameter, set_track_mute]` are shape-distinct. Same tools = not distinct.

**New variant fields:**

```python
# On every variant dict:
"analytical_only": bool  # True = directional suggestion, not executable
"distinctness_reason": str  # why this variant differs from others
```

**`generate_and_rank` renamed to `generate_wonder_variants`:**

Takes diagnosis as input. Builds executable variants from distinct moves, pads with analytical variants (honestly labeled) up to 3, ranks all.

Returns:
```python
{
    "variants": ranked_list,
    "recommended": variant_id,
    "variant_count_actual": int,  # executable count (0-3)
    "degraded_reason": str,       # empty if >= 2 executable
}
```

**`_with_envelope` is kept** but no longer drives distinctness. It still scales targets for safe/strong/unexpected tiers, but two variants that only differ by envelope are not considered distinct.

## Section 3: Lifecycle, Session Continuity, and Preview Integration

### `enter_wonder_mode` tool rewrite

The tool becomes the lifecycle entry point:

1. Build diagnosis from stuckness + SongBrain + ledger + threads
2. Generate variants with diagnosis driving domain selection
3. Create WonderSession with all context
4. Open creative thread (exploration event, NOT turn resolution)
5. Store session
6. Return `wonder_session_id`, `creative_thread_id`, `diagnosis`, `variants`, `recommended`, `variant_count_actual`, `degraded_reason`

**Critical:** No `record_turn_resolution` at generation time.

### Preview Studio integration

Preview Studio stays independent but gains Wonder-awareness at the tool boundary.

**`create_preview_set`** — accepts optional `wonder_session_id`. When provided, reads executable variants from WonderSession and creates PreviewVariant objects from them. Updates WonderSession status to `"previewing"`.

**`render_preview_variant`** — refuses variants with `compiled_plan is None` (analytical-only), returning an explicit error with `analytical_only: true`.

**`commit_preview_variant`** — when linked to a WonderSession:
- Records turn resolution with `outcome: "accepted"`
- Updates taste graph via `record_move_outcome(kept=True)`
- Resolves the creative thread
- Updates WonderSession status to `"resolved"`

### New tool: `discard_wonder_session`

When the user rejects all variants:
- Marks WonderSession `outcome: "rejected_all"`, status `"resolved"`
- Creative thread stays **open** (the problem isn't solved)
- Records turn resolution with `outcome: "rejected"`, `user_sentiment: "disliked"`
- Discards linked preview set if any
- Returns `{"discarded": true, "thread_still_open": true}`

### Session continuity rules

| Event | What gets recorded |
|---|---|
| `enter_wonder_mode` | Creative thread opened. No turn resolution. |
| Preview rendered | Nothing — exploration, not outcome |
| `commit_preview_variant` | Turn resolution (accepted). Taste updated. Thread resolved. |
| `discard_wonder_session` | Turn resolution (rejected). Thread stays open. |
| Committed variant later undone | Counts against confidence. Taste updated (kept=False). |

## Section 4: Skill, Agent, and Command Updates

### New Wonder skill (`livepilot/skills/livepilot-wonder/SKILL.md`)

Behavioral guidance for agents on when and how to use Wonder:

**When to trigger:**
- User says "I'm stuck", "surprise me", "make it magical", "give me options"
- Stuckness confidence > 0.5
- 3+ consecutive undos in action ledger
- Multiple plausible next moves with no clear winner

**When NOT to trigger:**
- Exact operational requests ("set track 3 volume to -6dB")
- Narrow deterministic edits ("quantize this clip")
- Performance-safe-only context (unless explicitly requested)

**Workflow discipline:**
1. `enter_wonder_mode` -> diagnosis + variants
2. Explain diagnosis in musical language, not tool language
3. Present variants honestly (executable vs analytical)
4. `create_preview_set` with `wonder_session_id` for executable variants
5. `render_preview_variant` for each
6. `compare_preview_variants` -> present recommendation
7. User chooses -> `commit_preview_variant` OR `discard_wonder_session`
8. Never describe a variant as previewable unless `analytical_only` is false

**Fewer than 3 is correct:**
- 1 executable + 2 analytical is honest
- Never fabricate distinctness by relabeling the same move

### Core skill update (`livepilot-core/SKILL.md`)

Add Wonder routing section:
- Use Wonder for creative ambiguity and session rescue
- Do not fabricate three variants when only one real option exists
- Do not describe a branch as previewable unless it has a valid `compiled_plan`
- Prefer Wonder when `detect_stuckness` confidence > 0.5

### Producer agent update

Route into Wonder when:
- Request is emotionally-shaped ("make it bigger", "it needs magic")
- Session is stuck (stuckness confidence > 0.5)
- Previous attempt was undone
- Multiple creative directions viable with no clear winner

Behavior: diagnosis first, song language not tool language, commit only after preview.

### Command surface updates

| Skill | Wonder integration |
|---|---|
| `livepilot-mix` | Use Wonder for emotional requests, not corrective ones |
| `livepilot-arrangement` | Use Wonder for chorus lift, transition rescue, contrast, repetition-fatigue |
| `livepilot-sounddesign` | Use Wonder for identity-shaping requests ("more haunted", "more alive") |
| `livepilot-performance` | Restrict to performance-safe moves; require explicit request |
| `livepilot-evaluation` | Add Wonder evaluation: previewed, committed, rejected, analytical-only outcomes |

## Section 5: Test Plan

### New test files

**`tests/test_wonder_session.py`** — WonderSession lifecycle:
- Creation, storage, retrieval
- Status transitions: `diagnosing -> variants_ready -> previewing -> resolved`
- Outcome recording: committed, rejected_all, abandoned
- Store eviction at capacity
- `degraded_reason` populated when <2 executable variants

**`tests/test_wonder_diagnosis.py`** — Diagnosis builder:
- Stuckness data drives `problem_class` and `candidate_domains`
- Missing SongBrain -> degraded, lower confidence
- Missing stuckness -> `trigger_reason: "user_request"`, `problem_class: "exploration"`
- All rescue types map to valid candidate domain lists

**`tests/test_wonder_distinctness.py`** — Variant distinctness:
- 3 moves from different families -> 3 distinct variants
- 2 moves from different families -> 2 executable + 1 analytical
- 1 move -> 1 executable + 2 analytical
- 0 moves -> 3 analytical, all `analytical_only: true`
- Same `move_id` never in two executable variants
- Same compile_plan shape never in two executable variants
- `distinctness_reason` non-empty for every executable variant

**`tests/test_wonder_lifecycle.py`** — End-to-end (pure computation):
- `enter_wonder_mode` returns `wonder_session_id`, `diagnosis`, `variants`
- `analytical_only` variants refused by `render_preview_variant`
- Commit records accepted turn + updates taste + resolves thread
- Discard records rejected turn, thread stays open
- No turn resolution at generation time

### Updates to existing tests

- `test_tools_contract.py` — tool count 292 -> 293
- `test_wonder_engine.py` — renamed pipeline, new distinctness function, `analytical_only` field
- `test_preview_studio.py` — analytical variant refused by render

## Degradation Behavior

| Missing input | Behavior |
|---|---|
| No SongBrain | Diagnosis has empty identity/sacred. Variants still generated. `degraded_capabilities: ["song_brain"]` |
| No stuckness data | `trigger_reason: "user_request"`, no domain narrowing. All families searched |
| No taste graph | Taste scoring defaults to 0.5. Ranking works on identity + novelty + coherence |
| No action ledger | Undo/tweaking signals unavailable. Lower stuckness confidence |
| No analyzer/bridge | Preview rendering may fail. Analytical fallback with `degraded_reason` |
| 0 semantic moves match | 3 analytical variants, `variant_count_actual: 0`, clear `degraded_reason` |

**Rule:** Wonder never refuses to run. It always returns something useful, honestly labeled.

## Tool Count

| Change | Count |
|---|---|
| Current | 292 |
| Add `discard_wonder_session` | +1 |
| **Total** | **293** |

## Files Touched

| File | Change |
|---|---|
| `mcp_server/wonder_mode/session.py` | **New** — WonderSession, WonderDiagnosis, in-memory store |
| `mcp_server/wonder_mode/diagnosis.py` | **New** — build_diagnosis |
| `mcp_server/wonder_mode/engine.py` | **Modify** — `select_distinct_variants`, `analytical_only`, `generate_wonder_variants`, domain filtering |
| `mcp_server/wonder_mode/tools.py` | **Modify** — rewrite `enter_wonder_mode`, add `discard_wonder_session` |
| `mcp_server/preview_studio/tools.py` | **Modify** — `wonder_session_id` param, refuse analytical, commit writes outcome |
| `livepilot/skills/livepilot-wonder/SKILL.md` | **New** — Wonder skill |
| `livepilot/skills/livepilot-core/SKILL.md` | **Modify** — Wonder routing section |
| `tests/test_wonder_session.py` | **New** |
| `tests/test_wonder_diagnosis.py` | **New** |
| `tests/test_wonder_distinctness.py` | **New** |
| `tests/test_wonder_lifecycle.py` | **New** |
| `tests/test_wonder_engine.py` | **Modify** |
| `tests/test_preview_studio.py` | **Modify** |
| `tests/test_tools_contract.py` | **Modify** — 292 -> 293 |
| 14+ manifest/doc files | **Modify** — tool count |

## Out of Scope

- External research/provider integration
- Auto-trigger (agent decides based on skill guidance)
- New slash commands
- PreviewVariant -> WonderVariant unification (Approach 2)
- Orchestrator layer (Approach 3)
- `_with_envelope` removal (still runs, just not a distinctness signal)

## Assumptions

- Existing 20 semantic moves remain the source of executable plans
- Wonder does not invent execution paths outside the semantic moves system
- Preview-first is the standard UX; auto-apply is not part of this phase
- Session continuity tracks real outcomes, not proposal noise
- Default branch shape is safe/strong/unexpected only when all three are genuinely distinct

# LivePilot Integration: Orchestrator + Wonder + Arrangement + Sample Intelligence + Slicing

**Date:** April 13, 2026
**Status:** Approved for implementation
**Target:** 317 tools (316 + plan_slice_workflow)

## Problem

The orchestration layer has a split-source problem: Wonder Mode reads stale `SemanticMove.compile_plan` metadata as runtime truth instead of running moves through the semantic compiler. Sample Engine exists as a standalone subsystem but is not wired into Wonder, arrangement planning, or the conductor. Splice integration is local SQLite only but some code paths reference nonexistent gRPC lifespan clients.

## Design Decision

- The semantic compiler (`compiler.compile()`) is the **single source of executable plans**.
- Wonder and Preview are **clients** of the compiler, not parallel planning systems.
- Sample Engine is the **canonical sample discovery/planning layer**.
- Splice stays **local-first** (SQLite) for this pass. gRPC references are cleaned up.
- Phase 5 extends `plan_sample_workflow` with section params instead of adding a new tool.

## Codebase Validation

All referenced code paths verified at commit `7b0e878` (April 13, 2026):

| Path | Status | Location |
|------|--------|----------|
| Wonder uses `move.compile_plan` as runtime truth | Confirmed | `engine.py:242` |
| Preview consumes `compiled_plan` directly | Confirmed | `preview_studio/tools.py:357-371` |
| `SemanticMove.compile_plan` is static metadata | Confirmed | `models.py:24` |
| `compiler.compile(move, kernel) -> CompiledPlan` exists | Confirmed | `compiler.py:91` |
| Conductor has zero sample routing patterns | Confirmed | `_conductor.py:70-113` |
| `SessionKernel.recommended_engines/workflow` exist but empty | Confirmed | `session_kernel.py:45-46` |
| Wonder diagnosis maps to sample domains | Confirmed | `diagnosis.py:27-30` |
| `get_sample_opportunities` tool exists | Confirmed | `sample_engine/tools.py:371` |
| Sample compilers emit `{sample_file_path}` placeholder | Confirmed | `sample_compilers.py` (fixed in truthfulness pass 2) |

---

## Phase 1: Single-Source Orchestration Path

### Goal
Wonder and Preview consume compiled plans from `compiler.compile()`, not stale move metadata.

### Changes
1. In Wonder variant generation (`engine.py`), after move discovery and distinct selection:
   - Build a lightweight kernel from session info
   - Call `compiler.compile(move_obj, kernel)` for each selected move
   - Store `compiled_plan` on the variant as a normalized dict: `{"steps": [...], "summary": ..., "risk_level": ..., "warnings": ...}`
2. In Preview Studio, expect the normalized compiled-plan shape. Remove direct reads of `move_dict["compile_plan"]`.
3. Rename `SemanticMove.compile_plan` to `SemanticMove.plan_template` to signal it's metadata, not runtime truth.
4. Keep `apply_semantic_move` as the reference implementation.

### Files to modify
- `mcp_server/wonder_mode/engine.py` — variant build path
- `mcp_server/preview_studio/tools.py` — plan consumption
- `mcp_server/semantic_moves/models.py` — field rename
- `mcp_server/semantic_moves/compiler.py` — no changes expected
- `mcp_server/semantic_moves/tools.py` — align `to_dict()` output
- Tests: add test that Wonder variant plan matches `apply_semantic_move(mode="observe")` output

### Acceptance criteria
- Wonder variant `compiled_plan` matches `apply_semantic_move(mode="observe")` output shape.
- Preview rendering uses normalized compiled plans, not raw `compile_plan`.
- No code path reads `move_dict["compile_plan"]` as runtime truth.

---

## Phase 2: Sample-Aware Conductor Routing

### Goal
Sample and slice requests route to the correct engine automatically.

### Changes
1. Add sample routing patterns to `_ROUTING_PATTERNS`:
   ```
   sample|splice|slice|chop|flip|break|breakbeat|one.?shot|vocal.?sample|foley|field.?recording|found.?sound
   ```
2. Add mixed arrangement+sample patterns:
   ```
   (section/form words) + (sample words) -> composition + sample_engine
   ```
3. Populate `SessionKernel.recommended_engines` and `recommended_workflow` in `get_session_kernel`.

### Workflow values
- `sample_discovery` — pure sample search/evaluate
- `slice_workflow` — slice-focused production
- `sample_plus_arrangement` — section-aware sample use
- `composition_first_then_sample` — structure first, then fill with samples
- `guided_workflow` — fallback

### Files to modify
- `mcp_server/tools/_conductor.py` — routing patterns + workflow inference
- `mcp_server/runtime/tools.py` — populate kernel fields
- Tests: assert sample routing, multi-engine routing, workflow population

### Acceptance criteria
- "find me a dark vocal sample" routes to `sample_engine`.
- "slice this loop into percussion" routes to `sample_engine`.
- "find a vocal and chop it for the chorus" routes to `composition + sample_engine`.
- `recommended_engines` and `recommended_workflow` are populated.

---

## Phase 3: Wonder Mode Auto-Sample Intelligence

### Goal
When Wonder detects sample-relevant stuckness, it invokes sample intelligence automatically.

### Pipeline
1. Build diagnosis.
2. If `candidate_domains` includes `sample`, call `get_sample_opportunities`.
3. Derive search queries from opportunities.
4. Call `search_samples(source="splice")` first, then browser/filesystem fallback.
5. Pick best candidate (source priority > material match > key/BPM match > first result).
6. Inject resolved values into compiler context: `sample_file_path`, `sample_name`, `material_type`.
7. Compile the move via `compiler.compile()`.
8. Mark variant `executable` if real path exists, `analytical_only` otherwise.

### Files to modify
- `mcp_server/wonder_mode/engine.py` — sample pipeline in variant generation
- `mcp_server/wonder_mode/tools.py` — pass Ableton context for sample search
- Tests: sample diagnosis triggers search, resolved candidates produce executable variants, missing candidates produce analytical-only

### Acceptance criteria
- Wonder with sample diagnosis auto-includes real sample candidates when available.
- At least one variant becomes executable without manual sample selection.
- Missing candidates produce honest analytical-only response.

---

## Phase 4: First-Class Slice Workflow

### Goal
One new tool: `plan_slice_workflow` — the canonical slice orchestrator. Tool count: 316 -> 317.

### Interface
```python
def plan_slice_workflow(
    ctx: Context,
    file_path: Optional[str] = None,
    track_index: Optional[int] = None,
    device_index: int = 0,
    intent: str = "rhythm",       # rhythm|hook|texture|percussion|melodic
    target_section: Optional[str] = None,
    target_track: Optional[int] = None,
    bars: int = 4,
    style_hint: str = "",
) -> dict:
```

### Behavior
1. Analyze sample profile.
2. Recommend Simpler mode + slice strategy based on intent.
3. Load/target Simpler.
4. Get slice points via `get_simpler_slices`.
5. Derive MIDI note map from slice count.
6. Generate starter MIDI content based on intent.
7. Return: compiled steps, slice metadata, note map, follow-up suggestions, arrangement hints.

### Intent defaults
| Intent | Slice mode | Pattern style | Density |
|--------|-----------|---------------|---------|
| rhythm | transient/beat | sparse groove | medium |
| hook | region/manual | repeated motif | high |
| texture | long regions | sustained, filtered | low |
| percussion | transient | kick/snare/hat distribution | medium-high |
| melodic | region | pitch contour phrase | medium |

### Files to create/modify
- `mcp_server/sample_engine/slice_workflow.py` — new module
- `mcp_server/sample_engine/tools.py` — register new tool
- Tests: file-based workflow, existing-Simpler workflow, intent variations, real MIDI notes in output

### Acceptance criteria
- Plan from file path includes actual `add_notes` payloads.
- Plan from existing Simpler works with `track_index + device_index`.
- Different intents produce different note-generation defaults.

---

## Phase 5: Section-Aware Sample + Arrangement Integration

### Goal
Arrangement planning proposes sample roles per section; sample workflows target specific sections.

### Changes
1. Extend `plan_arrangement` output with sample-role hints per section:
   - `hook_sample`, `texture_bed`, `transition_fx`, `break_layer`, `fill_one_shot`
2. Extend `plan_sample_workflow` with optional section params:
   - `section_type`, `desired_role`, `material_type`
3. Section defaults:
   - Intro: texture bed, restrained one-shot
   - Verse: sparse chop, atmosphere
   - Build: transition FX, riser texture
   - Chorus/Drop: hook chop, break layer, one-shot punctuation
   - Bridge: reversed vocal, stretched tail
   - Outro: dissipating texture, sparse accents

### Files to modify
- `mcp_server/tools/arrangement.py` — `plan_arrangement` output augmentation
- `mcp_server/sample_engine/tools.py` — extend `plan_sample_workflow` params
- `mcp_server/sample_engine/planner.py` — section-aware planning logic
- Tests: section plans include sample hints, section-aware sample plans generate correctly

### Acceptance criteria
- "arrange this chopped sample into verse and chorus" produces section-specific behavior.
- Section-aware sample plans can be previewed via Preview Studio.

---

## Cross-Cutting Cleanup

### Splice
- Remove Composer references to `ctx.lifespan_context["splice"]` and `get_credits_remaining()`.
- Keep `SpliceSource` (SQLite) as the only live Splice path.
- Isolate gRPC client code — do not delete, but do not wire.

### Execution Router
- Extend `mcp_tool` dispatch (currently errors at `execution_router.py:91`).
- Move experiment execution onto the shared router path.

### Skills
Update after each phase ships:
- `livepilot-core` — single-source plan path
- `livepilot-sample-engine` — auto-invocation, slice workflow
- `livepilot-wonder` — sample-aware variants
- `livepilot-arrangement` — section sample roles
- `livepilot-devices` — slice workflow reference

### Tool Count
Phase 4 adds 1 tool: `plan_slice_workflow`. Update 317 in all locations per release checklist.
Phase 5 extends existing `plan_sample_workflow` — no new tools.

---

## Test Plan

| Area | Tests |
|------|-------|
| Conductor routing | sample-only, slice, mixed arrangement+sample, workflow population |
| Wonder integration | compiled plans from compiler, sample diagnosis triggers search, analytical-only fallback |
| Preview integration | normalized plans, refuses analytical for execution |
| Sample compiler validity | all steps match real tool signatures, no missing required params |
| Slice workflow | file-based, existing-Simpler, intent variations, real MIDI notes |
| Arrangement integration | section sample hints, section-aware sample plans |

## Assumptions

- Local Splice SQLite is the only "Splice" source for this pass.
- Semantic compiler is sole runtime source of executable plans.
- Wonder and Preview are preview-first — no auto-execution defaults.
- One new tool (slice workflow), one extended tool (sample workflow).
- Each phase ships independently in a working state.

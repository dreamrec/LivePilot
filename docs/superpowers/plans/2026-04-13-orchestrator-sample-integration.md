# Orchestrator + Sample Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the orchestration path so Wonder/Preview use compiled plans from the semantic compiler, wire Sample Engine into Wonder/conductor/arrangement, and add a first-class slice workflow tool.

**Architecture:** The semantic compiler (`compiler.compile()`) becomes the single source of executable plans. Wonder and Preview consume normalized `CompiledPlan.to_dict()` output. The conductor gains sample-aware routing. Wonder auto-invokes sample intelligence when diagnosis includes sample domains. A new `plan_slice_workflow` tool provides end-to-end slice orchestration.

**Tech Stack:** Python 3.9+, FastMCP, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-13-orchestrator-sample-integration-design.md`

---

## Chunk 1: Phase 1 — Single-Source Orchestration Path

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `mcp_server/semantic_moves/models.py` | Modify | Rename `compile_plan` → `plan_template` |
| `mcp_server/semantic_moves/compiler.py` | Read only | Reference: `compile()` signature, `CompiledPlan.to_dict()` |
| `mcp_server/wonder_mode/engine.py` | Modify | Build variants with `compiler.compile()` output |
| `mcp_server/preview_studio/tools.py` | Modify | Consume normalized compiled-plan dicts |
| `mcp_server/semantic_moves/tools.py` | Modify | Align `to_dict()` output (rename field) |
| `mcp_server/semantic_moves/sample_compilers.py` | Modify | Rename field reference |
| `mcp_server/semantic_moves/mix_compilers.py` | Read only | Verify no `compile_plan` refs |
| `mcp_server/sample_engine/moves.py` | Modify | Rename field reference |
| `tests/test_wonder_engine.py` | Modify | Update for new compiled-plan shape |
| `tests/test_orchestration_single_source.py` | Create | New: verify Wonder + apply_semantic_move alignment |

---

### Task 1.1: Rename SemanticMove.compile_plan → plan_template

**Files:**
- Modify: `mcp_server/semantic_moves/models.py:24`
- Modify: `mcp_server/semantic_moves/models.py:37,44` (to_dict references)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestration_single_source.py
"""Tests for single-source orchestration path (Phase 1)."""
import pytest
from mcp_server.semantic_moves.models import SemanticMove


def test_semantic_move_has_plan_template_not_compile_plan():
    """SemanticMove uses plan_template, not compile_plan."""
    move = SemanticMove(
        move_id="test_move",
        family="test",
        intent="test intent",
        targets=["energy"],
        plan_template=[{"tool": "set_tempo", "params": {"tempo": 120}}],
    )
    assert hasattr(move, "plan_template")
    assert not hasattr(move, "compile_plan")
    d = move.to_dict()
    assert "plan_template" in d
    assert "compile_plan" not in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestration_single_source.py::test_semantic_move_has_plan_template_not_compile_plan -v`
Expected: FAIL — `plan_template` not recognized, `compile_plan` still exists

- [ ] **Step 3: Rename in models.py**

In `mcp_server/semantic_moves/models.py`, change:
- Line 24: `compile_plan: list` → `plan_template: list`
- Line 37: `len(self.compile_plan)` → `len(self.plan_template)`
- Line 44: `d["compile_plan"] = self.compile_plan` → `d["plan_template"] = self.plan_template`

- [ ] **Step 4: Update all references to compile_plan in move registration files**

Search and replace `compile_plan=` in:
- `mcp_server/sample_engine/moves.py` — any `SemanticMove(... compile_plan=...)` → `plan_template=`
- `mcp_server/semantic_moves/__init__.py` or any file registering moves
- Grep: `grep -rn 'compile_plan' mcp_server/semantic_moves/ mcp_server/sample_engine/moves.py mcp_server/device_forge/`

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestration_single_source.py::test_semantic_move_has_plan_template_not_compile_plan -v`
Expected: PASS

- [ ] **Step 6: Run full suite to check for breakage**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -3`
Expected: All pass. If failures, they'll be in tests that reference `compile_plan` — fix them.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: rename SemanticMove.compile_plan → plan_template"
```

---

### Task 1.2: Make Wonder variants use compiler.compile()

**Files:**
- Modify: `mcp_server/wonder_mode/engine.py:229-248` (build_variant function)
- Modify: `mcp_server/wonder_mode/engine.py:80-101` (move enrichment)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestration_single_source.py (append)
from mcp_server.wonder_mode.engine import build_variant
from mcp_server.semantic_moves import registry


def test_wonder_variant_has_compiled_plan_from_compiler():
    """Wonder variants should carry compiled plans from compiler.compile(),
    not raw plan_template metadata."""
    # Get a real registered move that has a compiler
    moves = registry.list_moves()
    # Find one with a registered compiler
    from mcp_server.semantic_moves.compiler import _COMPILERS
    compilable = [m for m in moves if m.get("move_id") in _COMPILERS]
    if not compilable:
        pytest.skip("No moves with registered compilers")

    move_dict = compilable[0]
    kernel = {"session_info": {"tempo": 120, "tracks": []}, "mode": "improve"}

    variant = build_variant(
        move_dict=move_dict,
        label="Test",
        sacred=[],
        identity_confidence=0.5,
        kernel=kernel,
    )

    plan = variant["compiled_plan"]
    # Must be a dict with "steps" key (CompiledPlan.to_dict() shape)
    assert isinstance(plan, dict), f"Expected dict, got {type(plan)}"
    assert "steps" in plan, f"Missing 'steps' key, got: {list(plan.keys())}"
    assert "summary" in plan
    assert "risk_level" in plan
    assert isinstance(plan["steps"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_orchestration_single_source.py::test_wonder_variant_has_compiled_plan_from_compiler -v`
Expected: FAIL — `compiled_plan` is a list (raw plan_template), not a dict with "steps"

- [ ] **Step 3: Modify build_variant to accept kernel and compile**

In `mcp_server/wonder_mode/engine.py`, update the `build_variant` function signature to accept `kernel: dict = None`. Then replace line 242:

```python
# OLD:
"compiled_plan": move_dict.get("compile_plan"),

# NEW:
"compiled_plan": _compile_variant_plan(move_dict, kernel),
```

Add helper function above `build_variant`:

```python
def _compile_variant_plan(move_dict: dict, kernel: dict | None) -> dict | None:
    """Compile a move through the semantic compiler if possible."""
    if kernel is None:
        return None

    move_id = move_dict.get("move_id", "")
    from ..semantic_moves.compiler import compile as sem_compile, _COMPILERS
    from ..semantic_moves import registry

    if move_id not in _COMPILERS:
        # No compiler registered — return None (analytical only)
        return None

    move_obj = registry.get_move(move_id)
    if move_obj is None:
        return None

    try:
        plan = sem_compile(move_obj, kernel)
        return plan.to_dict()
    except Exception:
        return None
```

- [ ] **Step 4: Update all callers of build_variant to pass kernel**

Search: `grep -n 'build_variant(' mcp_server/wonder_mode/`
Update each call site to pass the kernel (typically from the wonder session context or from `get_session_info`).

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_orchestration_single_source.py::test_wonder_variant_has_compiled_plan_from_compiler -v`
Expected: PASS

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -3`
Expected: All pass. Fix any wonder test breakage from shape change.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(wonder): compile variants through semantic compiler"
```

---

### Task 1.3: Align Preview Studio to normalized compiled plans

**Files:**
- Modify: `mcp_server/preview_studio/tools.py:355-371`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestration_single_source.py (append)
def test_preview_handles_compiled_plan_dict_shape():
    """Preview should handle CompiledPlan.to_dict() shape (dict with 'steps')."""
    from mcp_server.preview_studio.tools import _should_refuse_analytical

    # Dict shape from compiler — should NOT be refused
    compiled = {"steps": [{"tool": "set_tempo", "params": {"tempo": 120}}], "summary": "test"}
    assert not _should_refuse_analytical(compiled, wonder_linked=True)

    # None — should be refused when wonder-linked
    assert _should_refuse_analytical(None, wonder_linked=True)

    # Empty dict with no steps — should be refused
    assert _should_refuse_analytical({"steps": []}, wonder_linked=True)
```

- [ ] **Step 2: Run and verify fail**

Run: `python3 -m pytest tests/test_orchestration_single_source.py::test_preview_handles_compiled_plan_dict_shape -v`
Expected: May pass or fail depending on current `_should_refuse_analytical` logic

- [ ] **Step 3: Update _should_refuse_analytical**

```python
def _should_refuse_analytical(compiled_plan, wonder_linked: bool) -> bool:
    """Refuse if no executable plan and this is wonder-linked."""
    if not wonder_linked:
        return False
    if compiled_plan is None:
        return True
    if isinstance(compiled_plan, dict):
        return len(compiled_plan.get("steps", [])) == 0
    if isinstance(compiled_plan, list):
        return len(compiled_plan) == 0
    return True
```

- [ ] **Step 4: Update render_preview_variant plan extraction (lines ~360)**

Ensure the plan extraction handles both old list shape (backward compat) and new dict shape:

```python
plan = variant.compiled_plan
if isinstance(plan, dict):
    steps = plan.get("steps", [])
elif isinstance(plan, list):
    steps = plan
else:
    steps = []
```

This code already exists at line 361 — verify it matches. If so, no change needed.

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_orchestration_single_source.py tests/test_wonder_engine.py tests/test_wonder_lifecycle.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(preview): handle normalized compiled-plan dict shape"
```

---

### Task 1.4: Clean up stale compile_plan references

- [ ] **Step 1: Grep for remaining compile_plan references**

```bash
grep -rn 'compile_plan' mcp_server/ tests/ --include='*.py' | grep -v 'plan_template\|__pycache__'
```

- [ ] **Step 2: Fix each remaining reference**

Expected locations:
- `mcp_server/wonder_mode/engine.py` — the `_compile_plan_shape` helper function name is fine (it's internal), but update it to read `plan_template` from move dicts
- `mcp_server/semantic_moves/tools.py` — `to_dict()` output should use `plan_template`
- Any test file referencing `compile_plan`

- [ ] **Step 3: Run full suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -3`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove all stale compile_plan references"
```

---

## Chunk 2: Phase 2 — Sample-Aware Conductor Routing

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `mcp_server/tools/_conductor.py:70-113` | Modify | Add sample routing patterns |
| `mcp_server/tools/_conductor.py:153-172` | Modify | Add sample workflow inference |
| `mcp_server/runtime/tools.py` | Modify | Populate kernel recommended fields |
| `mcp_server/runtime/session_kernel.py` | Read only | Verify fields exist |
| `tests/test_conductor_routing.py` | Create | Sample routing tests |

---

### Task 2.1: Add sample routing patterns to conductor

**Files:**
- Modify: `mcp_server/tools/_conductor.py:70-113`
- Create: `tests/test_conductor_routing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_conductor_routing.py
"""Tests for conductor sample-aware routing."""
import pytest
from mcp_server.tools._conductor import classify_request


def test_sample_request_routes_to_sample_engine():
    plan = classify_request("find me a dark vocal sample")
    assert plan.primary_engine == "sample_engine"


def test_slice_request_routes_to_sample_engine():
    plan = classify_request("slice this loop into percussion hits")
    assert plan.primary_engine == "sample_engine"


def test_splice_request_routes_to_sample_engine():
    plan = classify_request("search my Splice library for a techno kick")
    assert plan.primary_engine == "sample_engine"


def test_mixed_arrangement_sample_routes_multi():
    plan = classify_request("find a vocal chop and build a hook for the chorus")
    engines = [r.engine for r in plan.routes]
    assert "sample_engine" in engines
    assert "composition" in engines


def test_pure_mix_does_not_route_to_sample():
    plan = classify_request("clean up the muddy low mids")
    assert plan.primary_engine == "mix_engine"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_conductor_routing.py -v`
Expected: FAIL — no sample patterns in routing table

- [ ] **Step 3: Add sample routing patterns**

In `_ROUTING_PATTERNS`, add after the research section:

```python
# Sample requests
(r"sample|splice|loop|slice|chop|flip|break(?:beat)?|one.?shot", "sample_engine", "sample", "search_samples", ["analyze_sample", "plan_sample_workflow"]),
(r"vocal.?sample|foley|field.?record|found.?sound", "sample_engine", "sample", "search_samples", ["analyze_sample"]),
(r"texture.?sample|ambient.?sample|atmo", "sample_engine", "sample", "search_samples", ["suggest_sample_technique"]),
```

- [ ] **Step 4: Add mixed arrangement+sample detection in classify_request**

After the single-engine match loop, add multi-engine detection:

```python
# Check for mixed arrangement + sample requests
has_sample = bool(re.search(r"sample|splice|slice|chop|break|one.?shot|vocal|foley", request_lower))
has_arrangement = bool(re.search(r"chorus|verse|drop|intro|bridge|arrange|hook|section", request_lower))
if has_sample and has_arrangement and primary_engine != "sample_engine":
    # Add sample_engine as secondary
    routes.append(Route(engine="sample_engine", ...))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_conductor_routing.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(conductor): add sample-aware routing patterns"
```

---

### Task 2.2: Add sample workflow inference and populate kernel

**Files:**
- Modify: `mcp_server/tools/_conductor.py:153-172` (`_infer_workflow_mode`)
- Modify: `mcp_server/runtime/tools.py` (`get_session_kernel`)

- [ ] **Step 1: Write failing test**

```python
# tests/test_conductor_routing.py (append)
def test_sample_request_has_sample_discovery_workflow():
    plan = classify_request("find me a warm pad sample")
    assert plan.workflow_mode in ("sample_discovery", "slice_workflow", "sample_plus_arrangement")


def test_slice_request_has_slice_workflow():
    plan = classify_request("slice this break into hits")
    assert plan.workflow_mode == "slice_workflow"
```

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Add sample workflow inference**

In `_infer_workflow_mode`, add before the default return:

```python
# Sample workflow keywords
if re.search(r"slice|chop|transient|hit", request_lower):
    return "slice_workflow"
if re.search(r"sample|splice|foley|found.?sound", request_lower):
    if re.search(r"arrange|section|verse|chorus|drop", request_lower):
        return "sample_plus_arrangement"
    return "sample_discovery"
```

- [ ] **Step 4: Populate kernel recommended fields**

In `mcp_server/runtime/tools.py` where `get_session_kernel` builds the kernel, add after kernel construction:

```python
# Populate routing hints from conductor if request context available
if request_text:
    from ..tools._conductor import classify_request
    plan = classify_request(request_text)
    kernel.recommended_engines = [r.engine for r in plan.routes[:3]]
    kernel.recommended_workflow = plan.workflow_mode
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_conductor_routing.py -v`
Expected: All PASS

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -3`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(conductor): sample workflow inference + kernel routing hints"
```

---

## Chunk 3: Phase 3 — Wonder Auto-Sample Intelligence

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `mcp_server/wonder_mode/engine.py` | Modify | Add sample pipeline in variant generation |
| `mcp_server/wonder_mode/tools.py` | Modify | Pass Ableton context for sample search |
| `tests/test_wonder_sample_integration.py` | Create | Sample-aware Wonder tests |

---

### Task 3.1: Add sample resolution to Wonder variant generation

**Files:**
- Modify: `mcp_server/wonder_mode/engine.py`
- Create: `tests/test_wonder_sample_integration.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_wonder_sample_integration.py
"""Tests for Wonder Mode sample intelligence integration."""
import pytest
from mcp_server.wonder_mode.engine import build_variant


def test_sample_variant_with_resolved_path_is_executable():
    """When a sample file path is resolved, the variant should be executable."""
    move_dict = {
        "move_id": "sample_texture_layer",
        "family": "sample",
        "intent": "Add textural sample layer",
        "targets": ["texture"],
        "risk_level": "low",
    }
    kernel = {
        "session_info": {"tempo": 120, "tracks": []},
        "mode": "improve",
        "sample_context": {
            "resolved_file_path": "/path/to/sample.wav",
            "sample_name": "ambient_pad",
            "material_type": "texture",
        },
    }
    variant = build_variant(
        move_dict=move_dict,
        label="Texture Layer",
        sacred=[],
        identity_confidence=0.5,
        kernel=kernel,
    )
    plan = variant["compiled_plan"]
    assert plan is not None
    assert plan.get("executable", False) is True


def test_sample_variant_without_path_is_analytical():
    """When no sample can be resolved, variant should be analytical_only."""
    move_dict = {
        "move_id": "sample_texture_layer",
        "family": "sample",
        "intent": "Add textural sample layer",
        "targets": ["texture"],
        "risk_level": "low",
    }
    kernel = {
        "session_info": {"tempo": 120, "tracks": []},
        "mode": "improve",
        # No sample_context — resolution failed
    }
    variant = build_variant(
        move_dict=move_dict,
        label="Texture Layer",
        sacred=[],
        identity_confidence=0.5,
        kernel=kernel,
    )
    plan = variant.get("compiled_plan")
    # Either None or has executable=False
    if plan is not None:
        assert plan.get("executable", True) is False
```

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Add sample context injection to compiler**

In `_compile_variant_plan` (from Task 1.2), extend the kernel with sample context before compiling sample-family moves:

```python
def _compile_variant_plan(move_dict: dict, kernel: dict | None) -> dict | None:
    if kernel is None:
        return None

    move_id = move_dict.get("move_id", "")
    from ..semantic_moves.compiler import compile as sem_compile, _COMPILERS
    from ..semantic_moves import registry

    if move_id not in _COMPILERS:
        return None

    move_obj = registry.get_move(move_id)
    if move_obj is None:
        return None

    # Inject sample context into kernel for sample-family moves
    compile_kernel = dict(kernel)
    sample_ctx = kernel.get("sample_context")
    if sample_ctx and sample_ctx.get("resolved_file_path"):
        compile_kernel["sample_file_path"] = sample_ctx["resolved_file_path"]

    try:
        plan = sem_compile(move_obj, compile_kernel)
        result = plan.to_dict()
        # Mark executable based on whether sample paths are resolved
        if move_dict.get("family") == "sample":
            has_real_path = any(
                "{sample_file_path}" not in str(s.get("params", {}))
                for s in result.get("steps", [])
                if s.get("tool") == "load_sample_to_simpler"
            )
            result["executable"] = has_real_path
        return result
    except Exception:
        return None
```

- [ ] **Step 4: Update sample compilers to use kernel file path**

In `mcp_server/semantic_moves/sample_compilers.py`, update each compiler to check for `kernel.get("sample_file_path")`:

```python
# In each sample compiler, replace:
params={"track_index": new_idx, "file_path": "{sample_file_path}"},
# With:
params={"track_index": new_idx, "file_path": kernel.get("sample_file_path", "{sample_file_path}")},
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_wonder_sample_integration.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(wonder): auto-resolve sample paths in variant compilation"
```

---

### Task 3.2: Wire sample opportunity search into Wonder tools

**Files:**
- Modify: `mcp_server/wonder_mode/tools.py` — `enter_wonder_mode`

- [ ] **Step 1: Add sample search to enter_wonder_mode**

In `enter_wonder_mode`, after diagnosis and before variant generation, add:

```python
# If diagnosis suggests sample domains, search for candidates
sample_context = {}
if "sample" in (diagnosis.get("candidate_domains") or []):
    try:
        from ..sample_engine.tools import get_sample_opportunities, search_samples
        opportunities = await get_sample_opportunities(ctx)
        if opportunities.get("opportunities"):
            # Take first opportunity and search
            opp = opportunities["opportunities"][0]
            query = opp.get("search_query", opp.get("description", "sample"))
            results = await search_samples(ctx, query=query, limit=3)
            candidates = results.get("results", [])
            if candidates:
                best = candidates[0]
                sample_context = {
                    "resolved_file_path": best.get("file_path", ""),
                    "sample_name": best.get("name", ""),
                    "material_type": best.get("material_type", ""),
                }
    except Exception:
        pass  # Graceful degradation — analytical variants still work

# Pass sample_context into kernel for compilation
kernel["sample_context"] = sample_context
```

- [ ] **Step 2: Run full suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -3`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(wonder): auto-search samples when diagnosis includes sample domains"
```

---

## Chunk 4: Phase 4 — Slice Workflow Tool

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `mcp_server/sample_engine/slice_workflow.py` | Create | Slice planning logic |
| `mcp_server/sample_engine/tools.py` | Modify | Register new tool |
| `tests/test_slice_workflow.py` | Create | Slice workflow tests |

---

### Task 4.1: Create slice workflow planner

**Files:**
- Create: `mcp_server/sample_engine/slice_workflow.py`
- Create: `tests/test_slice_workflow.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_slice_workflow.py
"""Tests for plan_slice_workflow tool."""
import pytest
from mcp_server.sample_engine.slice_workflow import plan_slice_steps


def test_rhythm_intent_produces_sparse_pattern():
    result = plan_slice_steps(
        slice_count=8, intent="rhythm", bars=4, tempo=120,
    )
    assert "steps" in result
    assert "note_map" in result
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    assert len(notes_step) > 0
    # Rhythm should have actual notes
    notes = notes_step[0]["params"]["notes"]
    assert len(notes) > 0


def test_texture_intent_produces_sparse_long_notes():
    result = plan_slice_steps(
        slice_count=4, intent="texture", bars=4, tempo=120,
    )
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    notes = notes_step[0]["params"]["notes"]
    # Texture = fewer, longer notes
    assert len(notes) <= 8


def test_hook_intent_produces_repeated_motif():
    result = plan_slice_steps(
        slice_count=16, intent="hook", bars=4, tempo=120,
    )
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    notes = notes_step[0]["params"]["notes"]
    assert len(notes) >= 4


def test_note_map_matches_slice_count():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    assert len(result["note_map"]) == 8


def test_all_notes_have_required_fields():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    for note in notes_step[0]["params"]["notes"]:
        assert "pitch" in note
        assert "start_time" in note
        assert "duration" in note
        assert "velocity" in note
```

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Implement slice_workflow.py**

```python
# mcp_server/sample_engine/slice_workflow.py
"""Slice workflow planner — generates MIDI patterns for sliced samples."""
from __future__ import annotations
import random


# Simpler maps slices to MIDI notes starting at C3 (60)
SLICE_BASE_NOTE = 60


def plan_slice_steps(
    slice_count: int,
    intent: str = "rhythm",
    bars: int = 4,
    tempo: float = 120.0,
    track_index: int = 0,
    clip_slot_index: int = 0,
) -> dict:
    """Generate a slice workflow plan with real MIDI notes."""
    note_map = _build_note_map(slice_count)
    beats = bars * 4  # 4/4 time
    notes = _generate_notes(note_map, intent, beats, slice_count)

    steps = []

    # Create clip
    steps.append({
        "tool": "create_clip",
        "params": {
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "length": float(beats),
            "name": f"Slice {intent}",
        },
        "description": f"Create {bars}-bar clip for {intent} slice pattern",
    })

    # Add notes
    steps.append({
        "tool": "add_notes",
        "params": {
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "notes": notes,
        },
        "description": f"Program {len(notes)} notes across {slice_count} slices",
    })

    return {
        "steps": steps,
        "note_map": note_map,
        "slice_count": slice_count,
        "intent": intent,
        "bars": bars,
        "note_count": len(notes),
        "suggested_techniques": _suggest_techniques(intent),
    }


def _build_note_map(slice_count: int) -> list[dict]:
    """Map slice indices to MIDI notes."""
    return [
        {"slice_index": i, "midi_note": SLICE_BASE_NOTE + i, "label": f"Slice {i+1}"}
        for i in range(slice_count)
    ]


def _generate_notes(
    note_map: list[dict], intent: str, beats: int, slice_count: int,
) -> list[dict]:
    """Generate MIDI notes based on intent."""
    generators = {
        "rhythm": _gen_rhythm,
        "hook": _gen_hook,
        "texture": _gen_texture,
        "percussion": _gen_percussion,
        "melodic": _gen_melodic,
    }
    gen = generators.get(intent, _gen_rhythm)
    return gen(note_map, beats, slice_count)


def _gen_rhythm(note_map: list, beats: int, sc: int) -> list[dict]:
    """Sparse groove — hits on downbeats and off-beats."""
    notes = []
    step = 0.5  # 8th notes
    for t in range(int(beats / step)):
        time = t * step
        # Kick-like on downbeats, varied on off-beats
        if t % 4 == 0:
            idx = 0  # First slice (usually kick)
        elif t % 4 == 2:
            idx = min(1, sc - 1)  # Second slice
        elif t % 8 in (3, 7) and sc > 2:
            idx = random.randint(2, min(3, sc - 1))
        else:
            continue
        notes.append({
            "pitch": note_map[idx]["midi_note"],
            "start_time": time,
            "duration": step * 0.8,
            "velocity": 90 + random.randint(-10, 10),
        })
    return notes


def _gen_hook(note_map: list, beats: int, sc: int) -> list[dict]:
    """Repeated motif contour — short phrase looped."""
    phrase_len = min(4, beats)
    motif_slices = list(range(min(4, sc)))
    notes = []
    for rep in range(int(beats / phrase_len)):
        offset = rep * phrase_len
        for i, idx in enumerate(motif_slices):
            notes.append({
                "pitch": note_map[idx]["midi_note"],
                "start_time": offset + i * (phrase_len / len(motif_slices)),
                "duration": phrase_len / len(motif_slices) * 0.9,
                "velocity": 100 - i * 5,
            })
    return notes


def _gen_texture(note_map: list, beats: int, sc: int) -> list[dict]:
    """Sparse, long notes — sustained atmosphere."""
    notes = []
    used = min(3, sc)
    spacing = beats / used
    for i in range(used):
        notes.append({
            "pitch": note_map[i]["midi_note"],
            "start_time": i * spacing,
            "duration": spacing * 0.95,
            "velocity": 60 + random.randint(-5, 10),
        })
    return notes


def _gen_percussion(note_map: list, beats: int, sc: int) -> list[dict]:
    """Kick/snare/hat-like distribution."""
    notes = []
    step = 0.25  # 16th notes
    for t in range(int(beats / step)):
        time = t * step
        if t % 8 == 0 and sc > 0:
            notes.append({"pitch": note_map[0]["midi_note"], "start_time": time,
                         "duration": 0.2, "velocity": 110})
        if t % 8 == 4 and sc > 1:
            notes.append({"pitch": note_map[min(1, sc-1)]["midi_note"], "start_time": time,
                         "duration": 0.2, "velocity": 100})
        if t % 2 == 0 and sc > 2:
            notes.append({"pitch": note_map[min(2, sc-1)]["midi_note"], "start_time": time,
                         "duration": 0.15, "velocity": 70 + random.randint(-10, 10)})
    return notes


def _gen_melodic(note_map: list, beats: int, sc: int) -> list[dict]:
    """Pitch contour phrase — ascending/descending motion."""
    notes = []
    phrase_notes = min(8, sc)
    step = beats / phrase_notes
    for i in range(phrase_notes):
        notes.append({
            "pitch": note_map[i % sc]["midi_note"],
            "start_time": i * step,
            "duration": step * 0.85,
            "velocity": 85 + random.randint(-5, 10),
        })
    return notes


def _suggest_techniques(intent: str) -> list[str]:
    """Suggest follow-up techniques based on intent."""
    suggestions = {
        "rhythm": ["quantize_clip", "add reverb send for depth", "layer with acoustic hits"],
        "hook": ["duplicate for variation", "add filter automation", "pitch shift for call-response"],
        "texture": ["heavy reverb send", "low-pass filter automation", "pan automation"],
        "percussion": ["parallel compression", "transient shaping", "send to short room reverb"],
        "melodic": ["add delay send", "pitch correction if needed", "double with octave layer"],
    }
    return suggestions.get(intent, [])
```

- [ ] **Step 4: Run tests to verify pass**

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(sample-engine): add slice workflow planner with intent-based MIDI generation"
```

---

### Task 4.2: Register plan_slice_workflow as MCP tool

**Files:**
- Modify: `mcp_server/sample_engine/tools.py`

- [ ] **Step 1: Add the MCP tool wrapper**

```python
@mcp.tool()
async def plan_slice_workflow(
    ctx: Context,
    file_path: Optional[str] = None,
    track_index: Optional[int] = None,
    device_index: int = 0,
    intent: str = "rhythm",
    target_section: Optional[str] = None,
    target_track: Optional[int] = None,
    bars: int = 4,
    style_hint: str = "",
) -> dict:
    """Plan an end-to-end slice workflow for a sample.

    Analyzes the sample, recommends Simpler mode and slice strategy,
    generates starter MIDI content based on intent, and returns a
    compiled workflow. Does NOT execute — returns the plan.

    Accepts either file_path (new sample) or track_index + device_index
    (existing Simpler). intent: rhythm|hook|texture|percussion|melodic.
    """
    # ... implementation that calls slice_workflow.plan_slice_steps
```

- [ ] **Step 2: Update tool count references (316 → 317)**

Run the release skill quick verify command and update all tool count references.

- [ ] **Step 3: Run full suite including skill contract test**

Run: `python3 -m pytest tests/test_skill_contracts.py tests/test_slice_workflow.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(sample-engine): register plan_slice_workflow MCP tool (317 tools)"
```

---

## Chunk 5: Phase 5 — Section-Aware Integration + Cleanup

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `mcp_server/tools/arrangement.py` | Modify | Add sample-role hints to plan_arrangement |
| `mcp_server/sample_engine/tools.py` | Modify | Extend plan_sample_workflow with section params |
| `mcp_server/sample_engine/planner.py` | Modify | Section-aware planning logic |
| `mcp_server/composer/tools.py` | Modify | Clean Splice lifespan references |
| `mcp_server/runtime/execution_router.py` | Modify | Support mcp_tool dispatch |
| Skills: 5 SKILL.md files | Modify | Match runtime truth |
| `tests/test_arrangement_sample_integration.py` | Create | Section-aware sample tests |

---

### Task 5.1: Add sample-role hints to plan_arrangement

- [ ] **Step 1: Write test**

```python
# tests/test_arrangement_sample_integration.py
def test_plan_arrangement_includes_sample_hints():
    """Arrangement sections should include sample-role suggestions."""
    # Call plan_arrangement or its internal planner
    from mcp_server.tools.arrangement import _build_section_plan  # or equivalent
    section = _build_section_plan("chorus", bars=8, tempo=128)
    assert "sample_hints" in section
    hints = section["sample_hints"]
    assert any(h in hints for h in ["hook_sample", "break_layer", "fill_one_shot"])
```

- [ ] **Step 2: Implement section sample hints**

Add a `_section_sample_hints` function and call it from arrangement planning:

```python
_SECTION_SAMPLE_DEFAULTS = {
    "intro": ["texture_bed", "fill_one_shot"],
    "verse": ["texture_bed", "fill_one_shot"],
    "build": ["transition_fx", "texture_bed"],
    "chorus": ["hook_sample", "break_layer", "fill_one_shot"],
    "drop": ["hook_sample", "break_layer", "fill_one_shot"],
    "bridge": ["texture_bed", "transition_fx"],
    "breakdown": ["texture_bed"],
    "outro": ["texture_bed", "fill_one_shot"],
}
```

- [ ] **Step 3: Commit**

### Task 5.2: Extend plan_sample_workflow with section params

- [ ] **Step 1: Add optional params to existing tool**

Add `section_type: Optional[str] = None` and `desired_role: Optional[str] = None` to `plan_sample_workflow`.

- [ ] **Step 2: Use section context in planning**

When `section_type` is provided, adjust technique selection and processing chain based on section defaults.

- [ ] **Step 3: Test and commit**

### Task 5.3: Clean Splice lifespan references

- [ ] **Step 1: In composer/tools.py, replace splice lifespan reads with graceful no-ops**

```python
# Replace:
splice_client = lifespan["splice"]
# With:
splice_client = lifespan.get("splice")  # Not wired yet — always None
```

- [ ] **Step 2: Replace get_credits_remaining() with get_credits()**

Or remove the call entirely since splice is not in lifespan.

- [ ] **Step 3: Commit**

### Task 5.4: Update skills to match runtime truth

- [ ] Update each of the 5 SKILL.md files per the spec's cross-cutting cleanup section
- [ ] Commit

### Task 5.5: Final integration test + push

- [ ] **Run full suite**: `python3 -m pytest tests/ -v`
- [ ] **Run release checklist quick verify**
- [ ] **Commit and push to main**

---

## Execution Notes

- Each chunk is independently shippable.
- Phase 1 is the foundation — do not skip to Phase 2+ without it.
- The `random` module in slice_workflow should use a seed for test reproducibility.
- Tool count bumps from 316 → 317 in Phase 4 Task 4.2. Update all locations per release checklist.
- The Splice cleanup (Task 5.3) is defensive — it prevents runtime errors without removing code.

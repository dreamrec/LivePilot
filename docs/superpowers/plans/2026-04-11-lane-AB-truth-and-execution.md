# Lane A+B: Truth, Boundaries, and Unified Execution

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every broken wire in the intelligence layer — no MCP tool sent through raw TCP, no silent exception swallowing, every compile plan step routed to the correct backend, and a static audit in CI that prevents regressions.

**Architecture:** Build a shared execution router (`runtime/execution_router.py`) that understands three step backends: `remote_command` (TCP to Remote Script), `mcp_tool` (direct Python call), and `bridge_command` (M4L OSC). Refactor `apply_semantic_move` and `render_preview_variant` to use this router. Fix the 3 misrouted `get_motif_graph` calls and the 2 wrong function names in `analyze_phrase_arc`. Add a static boundary audit test that fails CI if any `send_command` target doesn't exist in the Remote Script, or any compile plan step targets an invalid backend.

**Tech Stack:** Python 3.10+, FastMCP, pytest. Pure computation engines (zero I/O). All Ableton interaction stays in existing tool wrappers.

**Depends on:** Nothing — this is the foundation.
**Blocks:** Lane D (Rich Intelligence), Lane E (UX & Validation).

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `mcp_server/runtime/execution_router.py` | **New** — unified step executor with backend routing |
| `mcp_server/runtime/remote_commands.py` | **New** — canonical set of all valid Remote Script commands |
| `mcp_server/semantic_moves/mix_moves.py` | **Modify** — annotate steps with backend type |
| `mcp_server/semantic_moves/transition_moves.py` | **Modify** — annotate steps with backend type |
| `mcp_server/semantic_moves/sound_design_moves.py` | **Modify** — annotate steps with backend type |
| `mcp_server/semantic_moves/performance_moves.py` | **Modify** — annotate steps with backend type |
| `mcp_server/semantic_moves/mix_compilers.py` | **Modify** — annotate compiled steps with backend type |
| `mcp_server/semantic_moves/compiler.py` | **Modify** — CompiledStep gains `backend` field |
| `mcp_server/semantic_moves/tools.py` | **Modify** — use execution router in explore mode |
| `mcp_server/preview_studio/tools.py` | **Modify** — use execution router in render |
| `mcp_server/song_brain/tools.py` | **Modify** — fix `get_motif_graph` call |
| `mcp_server/hook_hunter/tools.py` | **Modify** — fix `get_motif_graph` call |
| `mcp_server/musical_intelligence/tools.py` | **Modify** — fix `get_motif_graph` + `analyze_phrase_arc` |
| `mcp_server/memory/tools.py` | **Modify** — fix `record_positive_preference` bug |
| `AGENTS.md` | **Modify** — fix stale v1.9.18, 257 tools |
| `tests/test_tools_contract.py` | **Modify** — fix stale docstring |
| `tests/test_boundary_audit.py` | **New** — static audit: send_command targets vs Remote Script |
| `tests/test_execution_router.py` | **New** — router unit tests |
| `tests/test_move_executability.py` | **New** — compile plan steps vs valid backends |

---

## Chunk 1: Quick Fixes (Findings 3, 4, 7, 8)

These are direct bug fixes with no architectural dependency. Do them first to stop the bleeding.

### Task 1: Fix `get_motif_graph` misroutes (Finding 3)

**Files:**
- Modify: `mcp_server/song_brain/tools.py:91-95`
- Modify: `mcp_server/hook_hunter/tools.py:56-60`
- Modify: `mcp_server/musical_intelligence/tools.py:48-53`
- Test: `tests/test_song_brain.py`, `tests/test_hook_hunter_engine.py`

The motif graph tool (`mcp_server/tools/motif.py`) works by calling `get_session_info` and `get_notes` through TCP (valid Remote Script commands), then running `_motif_engine.detect_motifs()` in pure Python. The callers should invoke the engine directly instead of `ableton.send_command("get_motif_graph")`.

- [ ] **Step 1: Create a shared motif service function**

Create a helper in `mcp_server/tools/motif.py` that extracts the motif engine logic without MCP/Ableton dependency:

```python
def get_motif_data_from_session(session_info: dict, notes_by_track: dict) -> dict:
    """Extract motif data from pre-fetched session info and notes.
    
    This is the pure computation path — no Ableton calls needed.
    Callers should fetch session_info and notes themselves.
    """
    try:
        return _motif_engine.detect_motifs(session_info, notes_by_track)
    except Exception:
        return {}
```

- [ ] **Step 2: Fix song_brain/tools.py**

Replace line 93:
```python
data["motif_data"] = ableton.send_command("get_motif_graph")
```
With:
```python
# Motif data — from pure-Python engine, not TCP
from ..tools.motif import get_motif_data_from_session
notes_by_track = {}
for i, t in enumerate(data.get("tracks", [])):
    try:
        notes = ableton.send_command("get_notes", {"track_index": i, "clip_index": 0})
        if notes and notes.get("notes"):
            notes_by_track[i] = notes
    except Exception:
        pass
data["motif_data"] = get_motif_data_from_session(
    data.get("session_info", {}), notes_by_track
)
```

- [ ] **Step 3: Fix hook_hunter/tools.py**

Replace line 58:
```python
motif_data = ableton.send_command("get_motif_graph")
```
With the same pattern — fetch notes via valid TCP commands, then call the pure-Python engine.

- [ ] **Step 4: Fix musical_intelligence/tools.py**

Replace line 51:
```python
motif_graph = ableton.send_command("get_motif_graph")
```
With the same pattern.

- [ ] **Step 5: Run existing tests**

Run: `python -m pytest tests/test_song_brain.py tests/test_hook_hunter_engine.py -x -q`
Expected: all pass (existing tests are pure computation, don't hit TCP)

- [ ] **Step 6: Commit**

```bash
git add mcp_server/tools/motif.py mcp_server/song_brain/tools.py mcp_server/hook_hunter/tools.py mcp_server/musical_intelligence/tools.py
git commit -m "fix: route get_motif_graph through pure-Python engine, not TCP

SongBrain, HookHunter, and musical_intelligence were sending
get_motif_graph through raw TCP to the Remote Script, which has
no handler for it. Now calls the motif engine directly."
```

---

### Task 2: Fix `analyze_phrase_arc` wrong function names (Finding 4)

**Files:**
- Modify: `mcp_server/musical_intelligence/tools.py:174-186`

- [ ] **Step 1: Fix the two wrong TCP calls**

Replace lines 174-186:
```python
try:
    loudness_data = ableton.send_command("analyze_loudness_offline", {
        "file_path": file_path, "detail": "full",
    })
except Exception:
    pass

try:
    spectrum_data = ableton.send_command("analyze_spectrum_offline_internal", {
        "file_path": file_path,
    })
except Exception:
    pass
```

With direct calls to the perception engine functions:
```python
try:
    from ..tools.perception import _analyze_loudness_internal, _analyze_spectrum_internal
    loudness_data = _analyze_loudness_internal(file_path, detail="full")
except Exception:
    pass

try:
    spectrum_data = _analyze_spectrum_internal(file_path)
except Exception:
    pass
```

**Note:** Check if `perception.py` has internal functions that can be called without the MCP wrapper. If the logic is inside the `@mcp.tool()` function body, extract it into a standalone function first.

- [ ] **Step 2: Verify perception.py has callable internals**

Read `mcp_server/tools/perception.py` to confirm extraction points. If the analysis logic is inline in the tool function, extract it first.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add mcp_server/musical_intelligence/tools.py mcp_server/tools/perception.py
git commit -m "fix: route analyze_phrase_arc through perception engine, not TCP

analyze_loudness_offline and analyze_spectrum_offline_internal don't
exist as Remote Script commands. Now calls perception internals directly."
```

---

### Task 3: Fix `record_positive_preference` bug (Finding 7)

**Files:**
- Modify: `mcp_server/memory/tools.py:194`
- Test: `tests/test_taste_memory.py` (new or existing)

- [ ] **Step 1: Write a failing test**

```python
def test_record_positive_preference_actually_updates_taste():
    """record_positive_preference must actually change taste dimensions."""
    from mcp_server.memory.taste_memory import TasteMemoryStore
    store = TasteMemoryStore()
    initial = {d.name: d.value for d in store.get_taste_dimensions()}
    
    # The function builds a signal and calls update_from_outcome
    # It should use "signals" (plural, list), not "signal" (singular, string)
    store.update_from_outcome({"signals": ["bold_transition_kept"]})
    updated = {d.name: d.value for d in store.get_taste_dimensions()}
    
    assert updated["transition_boldness"] > initial["transition_boldness"]
```

- [ ] **Step 2: Fix line 194 in memory/tools.py**

Change:
```python
taste_store.update_from_outcome({"signal": signal})
```
To:
```python
# Map dimension+direction to the closest known outcome signal
from ..memory.taste_memory import _OUTCOME_SIGNALS
matching_signals = []
for dim_name, dim_signals in _OUTCOME_SIGNALS.items():
    for sig_name, adjustment in dim_signals.items():
        if dimension in sig_name and direction in sig_name:
            matching_signals.append(sig_name)
            break
if matching_signals:
    taste_store.update_from_outcome({"signals": matching_signals})
```

If `_OUTCOME_SIGNALS` is not importable, define the mapping inline or use the most obvious signal for the dimension.

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_taste_memory.py -x -q`

- [ ] **Step 4: Commit**

```bash
git add mcp_server/memory/tools.py tests/test_taste_memory.py
git commit -m "fix: record_positive_preference now actually updates taste

Was passing {\"signal\": ...} but update_from_outcome expects
{\"signals\": [...]}. Also fixed signal name to match OUTCOME_SIGNALS."
```

---

### Task 4: Fix stale metadata (Finding 8)

**Files:**
- Modify: `AGENTS.md:1,25,46`
- Modify: `tests/test_tools_contract.py:1`

- [ ] **Step 1: Fix AGENTS.md**

Line 1: `# LivePilot v1.9.18` → `# LivePilot v1.9.23`
Line 25: Update domain list to include all 39 domains
Line 46: `Currently 257 tools.` → `Currently 293 tools.`

- [ ] **Step 2: Fix test docstring**

Line 1: `"""Verify all 289 MCP tools are registered across 39 domains."""` → `"""Verify all 293 MCP tools are registered across 39 domains."""`

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_tools_contract.py -x -q`

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md tests/test_tools_contract.py
git commit -m "fix: sync AGENTS.md to v1.9.23/293 tools, fix test docstring"
```

---

## Chunk 2: Boundary Audit (A2, A3)

### Task 5: Build the Remote Script command registry

**Files:**
- Create: `mcp_server/runtime/remote_commands.py`
- Test: `tests/test_boundary_audit.py`

- [ ] **Step 1: Create the canonical command set**

```python
"""Canonical set of all valid Remote Script commands.

Generated from remote_script/LivePilot/router.py @register decorators.
This is the source of truth for what can be called via
ableton.send_command().
"""

REMOTE_COMMANDS: frozenset[str] = frozenset({
    # transport
    "get_session_info", "set_tempo", "set_time_signature",
    "start_playback", "stop_playback", "continue_playback",
    "toggle_metronome", "set_session_loop", "undo", "redo",
    # tracks
    "get_track_info", "create_midi_track", "create_audio_track",
    "create_return_track", "delete_track", "duplicate_track",
    "set_track_name", "set_track_color", "set_track_mute",
    "set_track_solo", "set_track_arm", "stop_track_clips",
    "set_group_fold", "set_track_input_monitoring",
    "get_freeze_status", "freeze_track", "flatten_track",
    # clips
    "get_clip_info", "create_clip", "delete_clip", "duplicate_clip",
    "fire_clip", "stop_clip", "set_clip_name", "set_clip_color",
    "set_clip_loop", "set_clip_launch", "set_clip_warp_mode",
    # notes
    "add_notes", "get_notes", "remove_notes", "remove_notes_by_id",
    "modify_notes", "duplicate_notes", "transpose_notes", "quantize_clip",
    # mixing
    "set_track_volume", "set_track_pan", "set_track_send",
    "get_return_tracks", "get_master_track", "set_master_volume",
    "get_track_routing", "get_track_meters", "get_master_meters",
    "get_mix_snapshot", "set_track_routing",
    # scenes
    "get_scenes_info", "create_scene", "delete_scene", "duplicate_scene",
    "fire_scene", "set_scene_name", "set_scene_color", "set_scene_tempo",
    "get_scene_matrix", "fire_scene_clips", "stop_all_clips",
    "get_playing_clips",
    # devices
    "get_device_info", "get_device_parameters", "set_device_parameter",
    "batch_set_parameters", "toggle_device", "delete_device",
    "move_device", "load_device_by_uri", "find_and_load_device",
    "set_simpler_playback_mode", "get_rack_chains", "set_chain_volume",
    # clip_automation
    "get_clip_automation", "set_clip_automation", "clear_clip_automation",
    # browser
    "get_browser_tree", "get_browser_items", "search_browser",
    "load_browser_item", "get_device_presets",
    # arrangement
    "get_arrangement_clips", "create_arrangement_clip",
    "add_arrangement_notes", "get_arrangement_notes",
    "remove_arrangement_notes", "remove_arrangement_notes_by_id",
    "modify_arrangement_notes", "duplicate_arrangement_notes",
    "set_arrangement_automation", "transpose_arrangement_notes",
    "set_arrangement_clip_name", "jump_to_time",
    "capture_midi", "start_recording", "stop_recording",
    "get_cue_points", "jump_to_cue", "toggle_cue_point",
    "back_to_arranger",
    # diagnostics
    "get_session_diagnostics",
    # ping (built-in)
    "ping",
})
```

- [ ] **Step 2: Write the boundary audit test**

```python
"""Static boundary audit: every ableton.send_command() target must exist
in the Remote Script, and every semantic move step must target a valid backend."""

import ast
import re
from pathlib import Path

from mcp_server.runtime.remote_commands import REMOTE_COMMANDS


MCP_SERVER = Path(__file__).resolve().parents[1] / "mcp_server"

# Files that legitimately call send_command for Remote Script commands
_SCAN_DIRS = [
    MCP_SERVER / "song_brain",
    MCP_SERVER / "hook_hunter",
    MCP_SERVER / "musical_intelligence",
    MCP_SERVER / "preview_studio",
    MCP_SERVER / "semantic_moves",
    MCP_SERVER / "tools",
    MCP_SERVER / "mix_engine",
    MCP_SERVER / "evaluation",
]


def _find_send_command_targets() -> list[tuple[str, int, str]]:
    """Find all ableton.send_command("...", ...) calls and extract the command string."""
    results = []
    for scan_dir in _SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.glob("*.py"):
            source = py_file.read_text()
            for i, line in enumerate(source.splitlines(), 1):
                match = re.search(r'send_command\(\s*["\']([^"\']+)["\']', line)
                if match:
                    results.append((str(py_file.relative_to(MCP_SERVER.parent)), i, match.group(1)))
    return results


def test_all_send_command_targets_are_valid_remote_commands():
    """Every ableton.send_command target must be a registered Remote Script command."""
    violations = []
    for filepath, line, cmd in _find_send_command_targets():
        if cmd not in REMOTE_COMMANDS:
            violations.append(f"  {filepath}:{line} — send_command(\"{cmd}\") is NOT a Remote Script command")
    
    assert not violations, (
        f"Found {len(violations)} send_command calls targeting non-existent Remote Script commands:\n"
        + "\n".join(violations)
    )
```

- [ ] **Step 3: Run the audit test (expect it to find existing violations BEFORE fixes)**

Run: `python -m pytest tests/test_boundary_audit.py -x -v`
Expected: FAIL — should catch the remaining violations if any exist after Tasks 1-2.

After Tasks 1-2 are done, this should PASS.

- [ ] **Step 4: Commit**

```bash
git add mcp_server/runtime/remote_commands.py tests/test_boundary_audit.py
git commit -m "test: add static boundary audit for send_command targets

CI now fails if any MCP code calls a non-existent Remote Script
command through ableton.send_command(). Canonical command set in
runtime/remote_commands.py."
```

---

### Task 6: Add semantic move executability audit (A3)

**Files:**
- Create: `tests/test_move_executability.py`

- [ ] **Step 1: Write the move executability test**

```python
"""Verify every semantic move compile_plan step targets a valid execution backend."""

from mcp_server.runtime.remote_commands import REMOTE_COMMANDS
from mcp_server.semantic_moves import registry


# MCP-only tools that can be called as direct Python functions
# (not through TCP). These are valid step targets IF the execution
# router handles them.
MCP_TOOLS: frozenset[str] = frozenset({
    "analyze_mix", "get_master_spectrum", "apply_automation_shape",
    "apply_gesture_template", "get_emotional_arc", "capture_audio",
    # Add more as needed
})

VALID_BACKENDS = REMOTE_COMMANDS | MCP_TOOLS


def test_all_move_steps_have_valid_targets():
    """Every compile_plan step must target a known command or MCP tool."""
    violations = []
    all_moves = registry._REGISTRY
    
    for move_id, move in all_moves.items():
        for i, step in enumerate(move.compile_plan):
            tool = step.get("tool", "")
            if tool and tool not in VALID_BACKENDS:
                violations.append(f"  {move_id} step {i}: tool=\"{tool}\" is not a known command or MCP tool")
        
        for i, step in enumerate(move.verification_plan):
            tool = step.get("tool", "")
            if tool and tool not in VALID_BACKENDS:
                violations.append(f"  {move_id} verify {i}: tool=\"{tool}\" is not a known command or MCP tool")
    
    assert not violations, (
        f"Found {len(violations)} move steps targeting unknown backends:\n"
        + "\n".join(violations)
    )
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_move_executability.py -x -v`

- [ ] **Step 3: Commit**

```bash
git add tests/test_move_executability.py
git commit -m "test: add semantic move executability audit

CI fails if any compile_plan step targets a tool that isn't
a valid Remote Script command or declared MCP tool."
```

---

## Chunk 3: Execution Router (B1, B3, B4)

### Task 7: Build the execution router

**Files:**
- Create: `mcp_server/runtime/execution_router.py`
- Test: `tests/test_execution_router.py`

- [ ] **Step 1: Write execution router tests**

```python
"""Tests for the unified execution router."""

from mcp_server.runtime.execution_router import (
    ExecutionResult,
    classify_step,
    execute_step,
)


def test_classify_remote_command():
    assert classify_step("set_track_volume") == "remote_command"


def test_classify_mcp_tool():
    assert classify_step("apply_automation_shape") == "mcp_tool"


def test_classify_unknown():
    assert classify_step("nonexistent_xyz") == "unknown"


def test_execute_step_without_ableton_returns_unavailable():
    result = execute_step(
        tool="set_track_volume",
        params={"track_index": 0, "volume": 0.5},
        ableton=None,
        ctx=None,
    )
    assert result.ok is False
    assert result.backend == "remote_command"
    assert "unavailable" in result.error.lower()


def test_execution_result_structure():
    r = ExecutionResult(ok=True, backend="remote_command", tool="set_track_volume", result={"volume": 0.5})
    assert r.to_dict()["ok"] is True
    assert r.to_dict()["backend"] == "remote_command"
```

- [ ] **Step 2: Run tests (expect failure)**

Run: `python -m pytest tests/test_execution_router.py -x -q`
Expected: FAIL — module doesn't exist yet

- [ ] **Step 3: Write the execution router**

```python
"""Unified execution router for compiled plan steps.

Classifies each step by backend (remote_command, mcp_tool, bridge_command,
pure_analysis) and dispatches to the correct execution path. This replaces
the pattern of sending everything through ableton.send_command().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .remote_commands import REMOTE_COMMANDS


# MCP-only tools that have direct Python callables
_MCP_TOOLS: dict[str, str] = {
    "apply_automation_shape": "mcp_server.tools.automation",
    "apply_gesture_template": "mcp_server.tools.composition",
    "analyze_mix": "mcp_server.mix_engine.tools",
    "get_master_spectrum": "mcp_server.tools.analyzer",
    "get_emotional_arc": "mcp_server.tools.composition",
    "capture_audio": "mcp_server.tools.transport",
}


@dataclass
class ExecutionResult:
    """Result of executing a single plan step."""
    ok: bool = False
    backend: str = ""  # remote_command, mcp_tool, bridge_command, pure_analysis, unknown
    tool: str = ""
    result: Any = None
    error: str = ""
    
    def to_dict(self) -> dict:
        d = {"ok": self.ok, "backend": self.backend, "tool": self.tool}
        if self.ok:
            d["result"] = self.result
        else:
            d["error"] = self.error
        return d


def classify_step(tool: str) -> str:
    """Classify a step's execution backend."""
    if tool in REMOTE_COMMANDS:
        return "remote_command"
    if tool in _MCP_TOOLS:
        return "mcp_tool"
    return "unknown"


def execute_step(
    tool: str,
    params: dict,
    ableton=None,
    ctx=None,
) -> ExecutionResult:
    """Execute a single plan step through the correct backend."""
    backend = classify_step(tool)
    
    if backend == "remote_command":
        if ableton is None:
            return ExecutionResult(ok=False, backend=backend, tool=tool,
                                  error="Ableton connection unavailable")
        try:
            result = ableton.send_command(tool, params)
            return ExecutionResult(ok=True, backend=backend, tool=tool, result=result)
        except Exception as e:
            return ExecutionResult(ok=False, backend=backend, tool=tool, error=str(e))
    
    elif backend == "mcp_tool":
        # MCP tools need the ctx for lifespan_context access
        # For now, mark as requiring MCP dispatch
        return ExecutionResult(
            ok=False, backend=backend, tool=tool,
            error=f"MCP tool '{tool}' requires direct Python dispatch (not yet wired)"
        )
    
    else:
        return ExecutionResult(
            ok=False, backend="unknown", tool=tool,
            error=f"Unknown tool '{tool}' — not a Remote Script command or registered MCP tool"
        )


def execute_plan_steps(
    steps: list[dict],
    ableton=None,
    ctx=None,
) -> list[ExecutionResult]:
    """Execute a list of plan steps, returning results for each.
    
    Stops on first failure unless step is marked optional.
    """
    results = []
    for step in steps:
        tool = step.get("tool") or step.get("command", "")
        params = step.get("params") or step.get("args", {})
        
        result = execute_step(tool, params, ableton=ableton, ctx=ctx)
        results.append(result)
        
        if not result.ok:
            break  # stop on first failure
    
    return results
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_execution_router.py -x -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add mcp_server/runtime/execution_router.py mcp_server/runtime/remote_commands.py tests/test_execution_router.py
git commit -m "feat: add unified execution router for plan steps

Classifies steps as remote_command, mcp_tool, or unknown.
Routes through correct backend. Foundation for B3/B4."
```

---

### Task 8: Rewire `apply_semantic_move` to use execution router (B3)

**Files:**
- Modify: `mcp_server/semantic_moves/tools.py:180-204`

- [ ] **Step 1: Replace the explore-mode execution loop**

Replace lines 180-204 (the `for step in plan.steps` loop) with:

```python
    # explore mode — execute through the unified router
    from ..runtime.execution_router import execute_plan_steps
    
    step_dicts = [
        {"tool": step.tool, "params": step.params, "description": step.description}
        for step in plan.steps
    ]
    exec_results = execute_plan_steps(step_dicts, ableton=ableton, ctx=ctx)
    
    executed_steps = []
    for i, er in enumerate(exec_results):
        executed_steps.append({
            "tool": er.tool,
            "backend": er.backend,
            "description": step_dicts[i].get("description", ""),
            "result": er.result if er.ok else None,
            "error": er.error if not er.ok else None,
            "ok": er.ok,
        })
    
    result = plan.to_dict()
    result["executed"] = True
    result["execution_results"] = executed_steps
    result["success_count"] = sum(1 for s in executed_steps if s["ok"])
    result["failure_count"] = sum(1 for s in executed_steps if not s["ok"])
    return result
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/ -x -q`

- [ ] **Step 3: Commit**

```bash
git add mcp_server/semantic_moves/tools.py
git commit -m "feat: rewire apply_semantic_move to use execution router

Explore mode now routes each step through the correct backend
instead of blindly sending everything via TCP."
```

---

### Task 9: Rewire `render_preview_variant` to use execution router (B4)

**Files:**
- Modify: `mcp_server/preview_studio/tools.py:354-375`

- [ ] **Step 1: Replace the render execution loop**

Replace the step execution section with:

```python
        from ..runtime.execution_router import execute_plan_steps
        
        step_dicts = [
            {"tool": step.get("tool") or step.get("command", ""),
             "params": step.get("params") or step.get("args", {})}
            for step in steps
        ]
        
        exec_results = execute_plan_steps(step_dicts, ableton=ableton, ctx=ctx)
        applied_count = sum(1 for r in exec_results if r.ok)
```

Keep the existing undo logic (undo `applied_count` times in finally block).

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_preview_studio.py -x -q`

- [ ] **Step 3: Commit**

```bash
git add mcp_server/preview_studio/tools.py
git commit -m "feat: rewire render_preview_variant to use execution router

Preview now routes steps through correct backends and accurately
tracks how many steps actually succeeded for undo."
```

---

## Chunk 4: Structured Degradation (A1, A4)

### Task 10: Add capability/degradation contract

**Files:**
- Create: `mcp_server/runtime/capability.py`

- [ ] **Step 1: Define the degradation contract**

```python
"""Capability and degradation reporting for advanced tools.

Every advanced tool should report its operational state:
- full: all data sources available, highest confidence
- fallback: some data missing, degraded but still useful
- analytical_only: no live data, pure heuristic
- unavailable: cannot operate at all
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityReport:
    """Operational state of an advanced tool invocation."""
    level: str = "full"  # full, fallback, analytical_only, unavailable
    confidence: float = 1.0
    available_sources: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    fallback_used: str = ""
    reason: str = ""
    
    def to_dict(self) -> dict:
        d = {"capability": self.level, "confidence": round(self.confidence, 2)}
        if self.missing_sources:
            d["missing"] = self.missing_sources
        if self.fallback_used:
            d["fallback"] = self.fallback_used
        if self.reason:
            d["reason"] = self.reason
        return d


def build_capability(
    required: list[str],
    available: dict[str, bool],
) -> CapabilityReport:
    """Build a capability report from required vs available data sources."""
    missing = [r for r in required if not available.get(r, False)]
    present = [r for r in required if available.get(r, False)]
    
    if not missing:
        return CapabilityReport(level="full", confidence=1.0, available_sources=present)
    
    if len(missing) == len(required):
        return CapabilityReport(
            level="analytical_only", confidence=0.2,
            available_sources=[], missing_sources=missing,
            reason="No required data sources available",
        )
    
    # Partial — calculate confidence from available ratio
    ratio = len(present) / len(required)
    return CapabilityReport(
        level="fallback", confidence=round(ratio * 0.8, 2),
        available_sources=present, missing_sources=missing,
        fallback_used="degraded inference from partial data",
    )
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/runtime/capability.py
git commit -m "feat: add capability/degradation reporting contract

Advanced tools can now report full/fallback/analytical_only/unavailable
with confidence scores and missing data sources."
```

---

### Task 11: Replace silent exception swallowing in key tools (A4)

**Files:**
- Modify: `mcp_server/song_brain/tools.py` — replace `except Exception: pass` with structured degradation
- Modify: `mcp_server/hook_hunter/tools.py` — same
- Modify: `mcp_server/musical_intelligence/tools.py` — same

For each file, the pattern is the same: replace bare `except Exception: pass` blocks with capability tracking. Instead of silently swallowing, accumulate `missing_sources` and include a `capability` field in the response.

- [ ] **Step 1: Update build_song_brain tool**

Add capability tracking to the data gathering section:

```python
from ..runtime.capability import build_capability

available = {
    "session_info": bool(data.get("session_info")),
    "scenes": bool(data.get("scenes")),
    "tracks": bool(data.get("tracks")),
    "motif_data": bool(data.get("motif_data")),
}
capability = build_capability(
    required=["session_info", "scenes", "tracks", "motif_data"],
    available=available,
)
# Include in response
result = brain.to_dict()
result["capability"] = capability.to_dict()
```

- [ ] **Step 2: Update hook_hunter and musical_intelligence similarly**

Same pattern — track what data was available, include `capability` in response.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -x -q`

- [ ] **Step 4: Commit**

```bash
git add mcp_server/song_brain/tools.py mcp_server/hook_hunter/tools.py mcp_server/musical_intelligence/tools.py mcp_server/runtime/capability.py
git commit -m "feat: replace silent exception swallowing with structured degradation

SongBrain, HookHunter, and musical_intelligence now report
capability level (full/fallback/analytical_only) with missing
data sources instead of silently dropping to empty."
```

---

## Chunk 5: Final Verification

### Task 12: Run full test suite + boundary audit

- [ ] **Step 1: Full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 2: Boundary audit clean**

Run: `python -m pytest tests/test_boundary_audit.py tests/test_move_executability.py -x -v`
Expected: all pass — no misrouted commands

- [ ] **Step 3: Import check**

```bash
python -c "
from mcp_server.runtime.execution_router import execute_step, classify_step
from mcp_server.runtime.remote_commands import REMOTE_COMMANDS
from mcp_server.runtime.capability import build_capability
print(f'Remote commands: {len(REMOTE_COMMANDS)}')
print('All imports OK')
"
```

- [ ] **Step 4: Final commit if needed**

---

## What This Plan Does NOT Cover (Deferred to Later Plans)

| Deferred | Why | Plan |
|----------|-----|------|
| Lane C: Persistence | Independent lane, no dependency on A+B | Plan 2 |
| Lane D: Rich Intelligence | Depends on A+B being done first | Plan 3 |
| Lane E: UX, Docs, Validation | Must be last — docs should match runtime | Plan 4 |
| B2: Annotate moves with backend type | Nice-to-have, execution router handles classification at runtime | Follow-up |
| MCP tool direct dispatch in router | Router currently marks MCP tools as "requires wiring" — full dispatch needs ctx threading | Follow-up |

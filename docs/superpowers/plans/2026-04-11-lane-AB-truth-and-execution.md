# Lane A+B: Truth, Boundaries, and Unified Execution

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every broken wire in the intelligence layer — no MCP tool sent through raw TCP, no silent exception swallowing, every compile plan step routed to the correct backend, and a static audit in CI that prevents regressions.

**Architecture:** Build a shared execution router that understands step backends (remote_command, mcp_tool, bridge_command, pure_analysis). Add a capability/degradation contract. Fix all misrouted calls. Add CI boundary audits.

**Tech Stack:** Python 3.10+, FastMCP, pytest.

**Depends on:** Nothing — this is the foundation.
**Blocks:** Lane D (PR8-9), Lane E (PR10-12).

**PR sequence in this plan:** PR1 → PR2 → PR3, PR4 (parallel after PR2), PR5 (after PR3).

---

## PR1: Capability Contract and Degraded Results

**Goal:** Standardize how advanced tools report `full`, `fallback`, `analytical_only`, `unavailable`.

**Files:**
- Create: `mcp_server/runtime/capability.py`
- Create: `tests/test_capability.py`
- Modify: `mcp_server/song_brain/tools.py`
- Modify: `mcp_server/hook_hunter/tools.py`
- Modify: `mcp_server/musical_intelligence/tools.py`
- Modify: `mcp_server/preview_studio/tools.py`
- Modify: `mcp_server/wonder_mode/tools.py`

**Acceptance criteria:**
- [ ] `CapabilityReport` dataclass with `level`, `confidence`, `available_sources`, `missing_sources`, `fallback_used`, `reason`
- [ ] `build_capability(required, available)` function that computes level from data availability
- [ ] SongBrain `build_song_brain` tool includes `capability` field in response showing what data was available vs missing
- [ ] HookHunter `find_primary_hook` includes `capability` field
- [ ] Musical intelligence tools include `capability` field
- [ ] Preview Studio `render_preview_variant` includes `capability` field
- [ ] Wonder Mode `enter_wonder_mode` already has `degraded_reason` — extend with `capability` field
- [ ] Every `except Exception: pass` in advanced tools replaced with structured degradation that tracks `missing_sources`
- [ ] Tests verify: full capability when all data present, fallback when partial, analytical_only when no data
- [ ] All existing tests still pass

**Implementation notes:**
- The pattern: each tool gathers data in try/except blocks. Instead of `pass`, accumulate what's missing. After gathering, call `build_capability()` and include it in the response.
- Don't change tool signatures or return types — add `capability` as an additional field in the response dict.
- The silent `except Exception: pass` blocks in `song_brain/tools.py` (lines 81-108), `hook_hunter/tools.py` (lines 53-60), `musical_intelligence/tools.py` (lines 48-53) are the primary targets.

---

## PR2: Command Boundary Audit

**Goal:** CI fails if any MCP code calls a non-existent Remote Script command.

**Files:**
- Create: `mcp_server/runtime/remote_commands.py` — canonical frozenset of all valid Remote Script commands
- Create: `tests/test_command_boundary_audit.py` — static audit scanning all `send_command` calls
- Modify: `.github/workflows/ci.yml` — ensure audit test runs in CI

**Acceptance criteria:**
- [ ] `REMOTE_COMMANDS` frozenset contains all ~85 registered commands from `remote_script/LivePilot/router.py`
- [ ] Static test scans all `.py` files under `mcp_server/` for `send_command("...")` patterns
- [ ] Test extracts the command string and asserts it's in `REMOTE_COMMANDS`
- [ ] Test catches the known violations: `get_motif_graph`, `analyze_loudness_offline`, `analyze_spectrum_offline_internal` (these will fail until PR4 fixes them)
- [ ] Second assertion checks semantic move compile_plan tool names against `REMOTE_COMMANDS ∪ MCP_TOOLS`
- [ ] CI runs this test automatically

**Implementation notes:**
- Parse `send_command` calls with regex: `send_command\(\s*["']([^"']+)["']`
- The `REMOTE_COMMANDS` set should be maintained manually (from `@register` decorators) — not auto-parsed, since the Remote Script uses Ableton's Python which can't be imported in CI.
- PR4 will fix the violations this test catches. Until PR4 lands, mark known violations as `xfail` or skip.

---

## PR3: Execution Router

**Goal:** One backend-aware executor handles all high-level plan execution.

**Depends on:** PR1 (capability contract), PR2 (command registry).

**Files:**
- Create: `mcp_server/runtime/execution_router.py`
- Create: `tests/test_execution_router.py`
- Modify: `mcp_server/semantic_moves/tools.py:180-204` — `apply_semantic_move` explore mode
- Modify: `mcp_server/preview_studio/tools.py:354-375` — `render_preview_variant` execution loop

**Acceptance criteria:**
- [ ] `classify_step(tool)` returns `remote_command`, `mcp_tool`, `bridge_command`, or `unknown`
- [ ] `execute_step(tool, params, ableton, ctx)` dispatches to correct backend
- [ ] `execute_plan_steps(steps, ableton, ctx)` returns `list[ExecutionResult]` with per-step `ok`, `backend`, `error`
- [ ] Remote commands go through `ableton.send_command()`
- [ ] MCP tools are called through direct Python imports (not TCP)
- [ ] Unknown tools return explicit error results (not silent failure)
- [ ] `apply_semantic_move` explore mode uses `execute_plan_steps` instead of raw loop
- [ ] `render_preview_variant` uses `execute_plan_steps` instead of raw loop
- [ ] Partial failure: if step 2 of 4 fails, undo count = 1 (only step 1 applied)
- [ ] Each `ExecutionResult` carries `backend` field so caller knows what ran
- [ ] Tests cover: all-remote plan, mixed-backend plan, unknown tool, partial failure, empty plan

**Implementation notes:**
- Step schema tolerance: accept both `{tool, params}` and `{command, args}` (existing dual-key pattern)
- The `_MCP_TOOLS` dict maps tool names to their importable module paths
- MCP tool dispatch: import the module, find the function, call it with `ctx` if needed
- For now, `bridge_command` classification exists but dispatch is deferred (M4L bridge needs OSC)

---

## PR4: Miswired Advanced Calls

**Goal:** Fix known wrong-layer calls without waiting on broader intelligence work.

**Depends on:** PR2 (boundary audit should pass after this).

**Files:**
- Create: shared helper in `mcp_server/tools/motif.py` — `get_motif_data_from_notes()`
- Create: shared helpers in `mcp_server/tools/perception.py` — `_analyze_loudness_internal()`, `_analyze_spectrum_internal()`
- Modify: `mcp_server/song_brain/tools.py:91-95` — fix `get_motif_graph` call
- Modify: `mcp_server/hook_hunter/tools.py:56-60` — fix `get_motif_graph` call
- Modify: `mcp_server/musical_intelligence/tools.py:48-53` — fix `get_motif_graph` call
- Modify: `mcp_server/musical_intelligence/tools.py:174-186` — fix `analyze_phrase_arc` calls
- Modify: `mcp_server/memory/tools.py:194` — fix `record_positive_preference` bug
- Modify: `AGENTS.md:1,25,46` — fix stale v1.9.18 / 257 tools
- Modify: `tests/test_tools_contract.py:1` — fix docstring 289→293

**Acceptance criteria:**
- [ ] `get_motif_graph` calls in song_brain, hook_hunter, musical_intelligence use pure-Python motif engine, not TCP
- [ ] `analyze_phrase_arc` calls `_analyze_loudness_internal` and `_analyze_spectrum_internal` directly, not through TCP with wrong names
- [ ] `record_positive_preference` passes `{"signals": [signal_name]}` (plural key, list value) and the signal name matches `_OUTCOME_SIGNALS`
- [ ] Boundary audit test (PR2) passes — no more invalid `send_command` targets
- [ ] `AGENTS.md` header says `v1.9.23`, tool count says `293`, domain list complete
- [ ] `test_tools_contract.py` docstring says `293`
- [ ] Regressions added: test that motif helper returns valid data, test that positive preference updates taste, test that boundary audit is clean
- [ ] All existing tests pass

**Implementation notes:**
- Motif fix: extract `_motif_engine.detect_motifs()` call from `mcp_server/tools/motif.py` into a standalone `get_motif_data_from_notes(session_info, notes_by_track)`. Callers fetch notes via valid TCP commands (`get_notes`), then call the pure-Python function.
- Perception fix: extract the file-based analysis logic from `analyze_loudness` and `analyze_spectrum_offline` MCP tools into internal functions that can be imported directly.
- Preference fix: two bugs — wrong key (`signal` → `signals`) AND signal string format doesn't match `_OUTCOME_SIGNALS` keys. Need to map `dimension_direction` to the closest known signal.

---

## PR5: Semantic Move Backend Annotations

**Goal:** Make move plans self-describing and safe.

**Depends on:** PR3 (execution router).

**Files:**
- Modify: `mcp_server/semantic_moves/models.py` — add `backend` field to step schema
- Modify: `mcp_server/semantic_moves/compiler.py` — `CompiledStep` gains `backend` field
- Modify: `mcp_server/semantic_moves/mix_moves.py` — annotate each step
- Modify: `mcp_server/semantic_moves/transition_moves.py` — annotate each step
- Modify: `mcp_server/semantic_moves/sound_design_moves.py` — annotate each step
- Modify: `mcp_server/semantic_moves/performance_moves.py` — annotate each step
- Modify: `mcp_server/semantic_moves/mix_compilers.py` — compiled steps carry backend
- Create: `tests/test_move_annotations.py`

**Acceptance criteria:**
- [ ] `SemanticMove` step schema: `{tool, params, description, backend}` where backend is `remote_command` or `mcp_tool`
- [ ] `CompiledStep` dataclass has `backend: str` field (default `remote_command`)
- [ ] All 20 semantic moves annotated with correct backend per step
- [ ] Steps targeting `apply_automation_shape`, `analyze_mix`, `get_master_spectrum`, `apply_gesture_template` are marked `backend: "mcp_tool"`
- [ ] Steps targeting `set_track_volume`, `set_device_parameter`, etc. are marked `backend: "remote_command"`
- [ ] Execution router reads `step.backend` if present (uses `classify_step` as fallback)
- [ ] Static test: every move step has an explicit `backend` annotation
- [ ] No move can accidentally send an MCP tool through TCP
- [ ] All existing tests pass

**Implementation notes:**
- The annotation is additive — existing moves just get a `backend` key in each step dict
- The execution router already classifies steps; annotations make it explicit and auditable
- Compilers should set `backend` on each `CompiledStep` based on the tool name
- This is the last PR that touches the move system — after this, the execution path is fully honest

---

## Dependency Map for This Plan

```
PR1 (Capability Contract) ─────┐
                                ├──► PR3 (Execution Router) ──► PR5 (Move Annotations)
PR2 (Boundary Audit) ──────────┤
                                └──► PR4 (Miswired Calls)
```

PR1 and PR2 have no dependencies — start them in parallel.
PR3 depends on both PR1 and PR2.
PR4 depends on PR2 (boundary audit defines what's broken).
PR5 depends on PR3 (router must exist before annotating moves for it).

---

## Recommended Starting Slice

Start with PR1, PR2, and PR4 simultaneously. PR4 is the highest-value fix (stops real bugs), PR1 and PR2 build the safety net that prevents regressions. PR3 and PR5 follow once the foundation is solid.

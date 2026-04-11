# Lane E: Audible Preview, UX, and Validation

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Docs match runtime, preview matches expectations, doctor reports real capabilities, CI covers the seams unit tests miss.

**Architecture:** Explicit preview modes, extended --doctor, capability-tier documentation, integration tests, release smoke board.

**Tech Stack:** Python 3.10+, pytest, Node.js (bin/livepilot.js), GitHub Actions CI.

**Depends on:** All other lanes. This is the finishing layer.

**PR sequence in this plan:** PR10 (after PR3+PR5+PR8), PR11 (after PR1+PR2+PR6), PR12 (last).

---

## PR10: Real Preview and Evaluation Loop

**Goal:** Preview can truthfully say "heard and measured" when capabilities exist, and clearly labels when it can't.

**Depends on:** PR3 (execution router), PR5 (move annotations), PR8 (motif service).

**Files:**
- Modify: `mcp_server/preview_studio/tools.py` — three explicit preview modes
- Modify: `mcp_server/preview_studio/models.py` — add `preview_mode` field to `PreviewVariant`
- Modify: `mcp_server/preview_studio/engine.py` — comparison includes preview mode context
- Modify: `mcp_server/evaluation/fabric.py` — evidence quality in verdicts
- Modify: `tests/test_preview_studio.py`
- Create: `tests/test_preview_modes.py`

**Acceptance criteria:**
- [ ] Three explicit preview modes in `render_preview_variant`:

| Mode | When | What it does |
|------|------|-------------|
| `audible_preview` | M4L present + all steps are valid remote commands | Apply → start playback for `bars` duration → capture via M4L (spectrum + loudness) → stop → undo → return spectral comparison |
| `metadata_only_preview` | No M4L but valid remote commands | Apply → `get_session_info` + `get_track_meters` → undo → return metadata diff |
| `analytical_preview` | No compiled plan or MCP-only steps | Describe expected impact, return analytical estimates |

- [ ] Response includes `"preview_mode": "audible" | "metadata_only" | "analytical"` — no ambiguity
- [ ] `bars` parameter actually used in `audible_preview` mode: controls playback duration before capture
- [ ] `audible_preview` captures: pre/post spectrum (8 bands), pre/post RMS, key detection if available
- [ ] `metadata_only_preview` captures: pre/post session_info + track meters (volume, pan per track)
- [ ] `analytical_preview` includes: expected dimension changes, risk assessment, identity effect estimate
- [ ] `PreviewVariant` model gains `preview_mode: str` field
- [ ] Evaluation fabric gains `evidence_quality` field: what was measured vs inferred
- [ ] Tests: each preview mode produces correct structure, `bars` is used in audible mode, analytical mode has no Ableton calls
- [ ] All existing tests pass

**Implementation notes:**
- Mode selection logic: check capabilities at render time. If M4L bridge is connected (`ctx.lifespan_context.get("m4l_bridge")`), all compiled steps are remote commands → `audible_preview`. If no bridge but valid commands → `metadata_only_preview`. Otherwise → `analytical_preview`.
- For `audible_preview`: use `start_playback` → `time.sleep(bars * 60 / tempo)` → `get_master_spectrum` + `get_master_rms` → `stop_playback` → undo all. This is the only mode that actually "hears" the change.
- The evaluation fabric should carry `evidence_quality: "measured" | "inferred" | "mixed"` so downstream consumers know what to trust.

---

## PR11: Doctor and Runtime Capability Reporting

**Goal:** `--doctor` reflects real runtime capability, not just file existence.

**Depends on:** PR1 (capability contract), PR2 (boundary audit), PR6 (persistence).

**Files:**
- Modify: `bin/livepilot.js` — extend `--doctor` with capability tier reporting
- Create: `mcp_server/runtime/capability_probe.py` — Python-side capability detection
- Modify: `mcp_server/server.py` — expose capability state at startup
- Create: `tests/test_doctor_output.py`

**Acceptance criteria:**
- [ ] `--doctor` reports 6 capability areas:

| Area | What it checks |
|------|---------------|
| Ableton reachability | TCP 9878 connection test |
| Remote Script parity | Expected command count vs detected |
| M4L bridge | UDP 9880 / OSC 9881 connectivity |
| Offline perception | numpy available, FluCoMa optional |
| Persistence | `~/.livepilot/` writable, taste.json exists, techniques.json valid |
| Runtime state | Which capability tier is active (Core/Analyzer/Intelligence/Memory) |

- [ ] Output format: clear pass/warn/fail per area with actionable suggestions
- [ ] `capability_probe.py` can be called from both JS doctor and Python server
- [ ] MCP server startup logs capability state summary
- [ ] Tests: mock environments for each capability combo

---

## PR12: Docs, Metadata Sync, and Release Gates

**Goal:** Product story matches runtime truth. Single source of truth for metadata.

**Depends on:** Everything — this lands last.

**Files:**
- Modify: `README.md` — rewrite around capability tiers
- Modify: `docs/manual/index.md` — match runtime truth
- Modify: `docs/manual/tool-reference.md` — add capability tier per domain
- Modify: `AGENTS.md` — current state
- Modify: `livepilot/skills/livepilot-release/SKILL.md` — updated release checklist
- Create: `scripts/sync_metadata.py` — generates version/count from source of truth
- Modify: `.github/workflows/ci.yml` — metadata sync check + all new tests
- Create: `docs/manual/release-smoke-board.md` — manual validation checklist

**Acceptance criteria:**
- [ ] README structured around 5 capability tiers:

| Tier | Tools | Requires |
|------|:-----:|----------|
| Core Control | ~210 | Ableton + Remote Script |
| Analyzer-Enhanced | ~30 | + M4L Analyzer |
| Offline Analysis | 4 | + numpy |
| Creative Intelligence | ~49 | + Core (heuristic without Analyzer) |
| Persistent Memory | — | + ~/.livepilot/ writable |

- [ ] Every feature claim says which tier it belongs to
- [ ] "Hear it before committing" → labeled Tier 2 (Analyzer-Enhanced)
- [ ] "Learns your preferences" → labeled Tier 5 (Persistent Memory)
- [ ] "Session continuity across restarts" → labeled Tier 5
- [ ] `scripts/sync_metadata.py` reads version from `package.json`, tool count from `test_tools_contract.py`, writes to all locations per CLAUDE.md checklist
- [ ] CI runs `sync_metadata.py --check` (fails if any file is stale)
- [ ] Release smoke board covers: empty set, drum loop, arranged song, plugin-heavy, M4L absent, M4L active
- [ ] Release skill updated with full checklist including capability validation
- [ ] All existing tests pass

**Implementation notes:**
- The metadata sync script should be the LAST thing anyone runs before a release. It reads `package.json` for version, runs a quick tool count, and sed-replaces across all known locations.
- The smoke board is a markdown checklist — not automated. It requires a human with Ableton to validate.
- README rewrites should be conservative: keep the existing structure, but add tier labels next to each feature claim. Don't remove features — label them honestly.

---

## Full PR Dependency Map

```
PR1 (Capability) ───────┬──► PR3 (Router) ──► PR5 (Move Annotations) ──────────┐
                         │                                                       ├──► PR10 (Real Preview)
PR2 (Boundary Audit) ───┤──► PR4 (Miswired) ──► PR8 (Motif+SongBrain) ─────────┤
                         │                           │                           │
                         │                           └──► PR9 (Hook+Repetition)  │
                         │                                                       │
PR1 ────► PR6 (Taste) ──┼──► PR7 (Project Continuity)                           │
                         │                                                       │
PR1+PR2+PR6 ────────────┼──► PR11 (Doctor)                                      │
                         │                                                       │
                         └──────────────────────────────────────────────────────► PR12 (Docs — LAST)
```

## Recommended Execution Order

**Wave 1 (parallel):** PR1, PR2, PR4
**Wave 2 (after wave 1):** PR3, PR6
**Wave 3 (after wave 2):** PR5, PR7, PR8
**Wave 4 (after wave 3):** PR9, PR10, PR11
**Wave 5 (last):** PR12

## Release Smoke Board (for PR12)

| Scenario | What to validate |
|----------|-----------------|
| Empty Ableton set | Wonder mode activates, stuckness low confidence, SongBrain analytical_only |
| Drum loop (4 tracks) | Beat recognition, hook detection, motif analysis works |
| Arranged song (8+ scenes) | Section purposes, transition scoring, emotional arc, repetition detection |
| Plugin-heavy (AU/VST) | Device loading, plugin parameter control, health check |
| M4L absent | All core tools work, perception reports unavailable, preview = metadata_only |
| M4L active | Spectral analysis, key detection, audible preview with spectrum comparison |
| Server restart | Taste persists, project threads resume, technique library intact |

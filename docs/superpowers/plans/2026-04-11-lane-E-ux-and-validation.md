# Lane E: Audible Preview, UX, and Validation

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make docs match runtime, preview match expectations, doctor report real capabilities, and CI cover the seams that unit tests miss.

**Architecture:** Redesign preview into explicit modes (audible/analytical/metadata). Extend --doctor to report runtime capability state. Rewrite README/manual around capability tiers. Add integration tests for routing, persistence, degradation, and bridge absence.

**Tech Stack:** Python 3.10+, pytest, GitHub Actions CI.

**Depends on:** Lanes A+B+C+D complete. This is the finishing layer — docs and validation must reflect what's actually true.

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `mcp_server/preview_studio/tools.py` | **Modify** — explicit preview modes |
| `mcp_server/preview_studio/models.py` | **Modify** — add `preview_mode` field |
| `bin/livepilot.js` | **Modify** — extend --doctor with capability reporting |
| `README.md` | **Modify** — capability tier framing |
| `docs/manual/index.md` | **Modify** — match runtime truth |
| `AGENTS.md` | **Modify** — current state |
| `tests/test_integration_routing.py` | **New** — integration tests |
| `tests/test_integration_persistence.py` | **New** — persistence integration |
| `tests/test_integration_degraded.py` | **New** — degraded mode behavior |

---

## Tasks

### Task 1: Explicit preview modes (E1, E2)

Redesign `render_preview_variant` to support three explicit modes:

| Mode | When | What it does |
|------|------|-------------|
| `audible_preview` | M4L analyzer present + compiled plan has only valid remote commands | Apply → capture audio via M4L → analyze loudness/spectrum → undo → return before/after with spectral comparison |
| `analytical_preview` | No compiled plan, or plan has MCP-only steps | Pure-computation preview — describes expected impact without touching Ableton |
| `metadata_only_preview` | Compiled plan has valid commands but no M4L | Apply → capture session_info → undo → return metadata diff (current behavior, honestly labeled) |

The response must include `"preview_mode": "audible" | "analytical" | "metadata_only"` so the caller knows exactly what they got.

Exit: Users can tell what kind of preview they received. `bars` is used for audible preview capture duration. Tests cover all three modes.

### Task 2: Extend --doctor with capability reporting (E3)

Add to `bin/livepilot.js --doctor`:
- Remote Script parity check (command count matches expected)
- M4L bridge connectivity status
- Offline perception availability (numpy/FluCoMa)
- Persistence directory status (`~/.livepilot/` writable, taste.json exists)
- Summary: which capability tier the user is operating at

Exit: `npx livepilot --doctor` gives a clear, honest picture of what's available.

### Task 3: Rewrite docs around capability tiers (E4)

Restructure README and manual around five tiers:

| Tier | What's in it | Requires |
|------|-------------|----------|
| **Core Control** (210 tools) | Deterministic Ableton control, music theory, generative, MIDI I/O | Ableton Live 12 + Remote Script |
| **Analyzer-Enhanced** (30 tools) | Real-time spectrum, key detection, Simpler, warp, deep LOM | + M4L Analyzer |
| **Offline Analysis** (4 tools) | Loudness, spectrum, reference comparison | + numpy |
| **Creative Intelligence** (49 tools) | SongBrain, Wonder, HookHunter, engines, semantic moves | + Core Control (heuristic without Analyzer) |
| **Persistent Memory** | Technique library, taste graph, session continuity | + ~/.livepilot/ writable |

Every feature claim must say which tier it belongs to. "Hear it before committing" → Tier 2 (Analyzer-Enhanced). "Learns your preferences" → Tier 5 (Persistent Memory).

Exit: README and manual accurately describe what each tier provides. No aspirational claims without tier labels.

### Task 4: Integration tests (E5)

Add focused integration tests that cover the seams unit tests miss:

| Test file | What it covers |
|-----------|---------------|
| `test_integration_routing.py` | Execution router routes to correct backend; partial success handled; undo count matches |
| `test_integration_persistence.py` | Taste survives store restart; continuity threads persist; corrupt file recovery |
| `test_integration_degraded.py` | SongBrain without motif data; HookHunter without notes; Wonder without taste; Preview without M4L |

Exit: CI covers the wiring seams. Degraded modes produce useful output with capability labels.

### Task 5: Manual release smoke board (E6)

Create a checklist for manual validation against real Ableton sessions:

| Scenario | What to test |
|----------|-------------|
| Empty set | Wonder mode, stuckness detection, SongBrain with no data |
| Drum loop | Beat creation, hook detection, motif analysis |
| Arranged song | Section purposes, transition analysis, emotional arc |
| Plugin-heavy | Device loading, parameter control, plugin health |
| M4L absent | All core tools work, perception tools report unavailable |
| M4L active | Spectral analysis, key detection, audible preview |

Exit: Release requires someone to run through this board before tagging.

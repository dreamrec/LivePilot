# Lane D: Rich Musical Intelligence

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the intelligence layer from heuristic placeholders to evidence-weighted, musically grounded judgments — SongBrain backed by real motif data, Hook Hunter using section recurrence, and semantic moves ranked with full context.

**Architecture:** Build a shared motif service consumed by all intelligence tools. Upgrade SongBrain from track-name inference to weighted synthesis of motif, density, harmonic, and editorial evidence. Upgrade Hook Hunter to use motif recurrence and section placement. Strengthen semantic move ranking with taste, SongBrain, constraints, and capability state.

**Tech Stack:** Python 3.10+, pure computation engines, no new external dependencies.

**Depends on:** Lane A+B complete (execution routing must work before planning is enriched).
**Blocks:** Lane E (docs must reflect actual intelligence capabilities).

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `mcp_server/tools/motif_service.py` | **New** — shared motif service for all consumers |
| `mcp_server/song_brain/builder.py` | **Modify** — evidence-weighted identity inference |
| `mcp_server/song_brain/models.py` | **Modify** — add evidence weights to SacredElement, SectionPurpose |
| `mcp_server/hook_hunter/analyzer.py` | **Modify** — use motif recurrence, section placement |
| `mcp_server/musical_intelligence/detectors.py` | **Modify** — richer repetition fatigue and arc scoring |
| `mcp_server/wonder_mode/engine.py` | **Modify** — ranking uses capability state |
| `mcp_server/evaluation/fabric.py` | **Modify** — evidence quality in verdicts |
| `tests/test_motif_service.py` | **New** |
| `tests/test_song_brain_evidence.py` | **New** |

---

## Tasks

### Task 1: Shared motif service (D1)

Build `mcp_server/tools/motif_service.py` — a pure-Python function that accepts `session_info` and a `notes_fetcher` callback, returns structured motif data. All consumers (SongBrain, HookHunter, repetition analysis) import this instead of making ad-hoc calls.

Exit: SongBrain, HookHunter, and musical_intelligence all use one motif source. Tests pass.

### Task 2: Evidence-weighted SongBrain (D2)

Upgrade `builder.py` to weight identity evidence by source:
- Motif recurrence: weight 0.4 (strongest signal)
- Section density change: weight 0.2
- Clip reuse patterns: weight 0.15
- Harmonic stability: weight 0.15
- Accepted edits history: weight 0.1

Each SacredElement gets an `evidence_sources` list showing what data supported the inference.

Exit: SongBrain identity_confidence reflects actual evidence quality. Tests cover each weight.

### Task 3: Hook Hunter with motif evidence (D3)

Upgrade `analyzer.py` to:
- Use motif recurrence from the shared service
- Track section placement (hook in verse but not chorus = neglect signal)
- Compute payoff expectation (chorus arrives → hook should be present)

Exit: `find_primary_hook` returns evidence-backed salience. `detect_hook_neglect` uses section data.

### Task 4: Richer repetition/arc analysis (D4)

Upgrade `detectors.py` to combine:
- Motif reuse count per section
- Clip reuse (exact duplicates across scenes)
- Density shifts between sections
- Section-role changes

Exit: `detect_repetition_fatigue` and `score_emotional_arc` produce materially richer output with evidence.

### Task 5: Context-aware semantic move ranking (D5)

Modify `wonder_mode/engine.py` ranking to include:
- Capability state (downrank moves that require unavailable backends)
- SongBrain identity fit
- Active constraint compliance
- Taste graph depth (more evidence = more influence)

Exit: Wonder Mode recommendations feel context-aware in real sessions.

### Task 6: Evaluation fabric evidence quality (D6)

Modify `evaluation/fabric.py` to include:
- `evidence_quality`: what was actually measured vs inferred
- `measurable_dimensions`: which aspects had real data
- `degraded_verdict`: when evidence is too thin to trust

Exit: Evaluation results clearly separate measured from inferred claims.

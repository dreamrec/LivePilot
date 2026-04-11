# Lane D: Rich Musical Intelligence

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the intelligence layer from heuristic placeholders to evidence-weighted, musically grounded judgments.

**Architecture:** Build a shared motif service consumed by all intelligence tools. Upgrade SongBrain from track-name inference to weighted synthesis. Upgrade Hook Hunter to use motif recurrence and section placement.

**Tech Stack:** Python 3.10+, pure computation engines, no new external dependencies.

**Depends on:** PR4 (miswired calls fixed), PR3 (execution router exists).
**Blocks:** Lane E (PR10, PR12).

**PR sequence in this plan:** PR8 (after PR4), PR9 (after PR8).

---

## PR8: Shared Motif Service and SongBrain Evidence

**Goal:** SongBrain can explain not just what it thinks, but why — with evidence weights.

**Depends on:** PR4 (motif calls already fixed to use Python engine).

**Files:**
- Create: `mcp_server/services/__init__.py`
- Create: `mcp_server/services/motif_service.py` — shared motif data provider
- Modify: `mcp_server/tools/motif.py` — expose `get_motif_data_from_notes()` as importable function
- Modify: `mcp_server/song_brain/builder.py` — evidence-weighted identity inference
- Modify: `mcp_server/song_brain/models.py` — add evidence fields to dataclasses
- Modify: `mcp_server/song_brain/tools.py` — use shared motif service
- Create: `tests/test_motif_service.py`
- Modify: `tests/test_song_brain.py` — test evidence weights

**Acceptance criteria:**
- [ ] `MotifService` provides `get_motif_data(session_info, notes_fetcher_fn)` — one entry point for all motif consumers
- [ ] `mcp_server/tools/motif.py` exposes `get_motif_data_from_notes()` as a standalone importable function (not just MCP tool)
- [ ] SongBrain, HookHunter, musical_intelligence all import from `services.motif_service` instead of ad-hoc calls
- [ ] `SongBrain` identity inference weights evidence by source:
  - Motif recurrence: 0.4 (strongest)
  - Section density change: 0.2
  - Clip reuse: 0.15
  - Harmonic stability: 0.15
  - Accepted edits: 0.1
- [ ] `SacredElement` gains `evidence_sources: list[str]` field
- [ ] `SongBrain.identity_confidence` reflects weighted evidence quality
- [ ] `SongBrain.to_dict()` includes `evidence_breakdown` showing per-source contributions
- [ ] Tests: identity confidence scales with evidence count, sacred elements cite sources, missing motif data lowers confidence
- [ ] All existing tests pass

**Implementation notes:**
- The motif service is a thin wrapper. PR4 already moved the engine call to a helper — this PR makes it a proper service.
- SongBrain builder currently has `_infer_identity_core` which picks the best candidate. Upgrade it to weight candidates by evidence quality and return the weights.
- Evidence-weighted means: if motif data is missing, identity confidence drops by ~40%. If composition analysis is missing, drops by ~20%. This makes `capability.confidence` match `identity_confidence`.

---

## PR9: Hook Hunter and Repetition Intelligence

**Goal:** Hook and repetition tools produce musically grounded results, not just track-name heuristics.

**Depends on:** PR8 (shared motif service).

**Files:**
- Modify: `mcp_server/hook_hunter/analyzer.py` — use motif recurrence, section placement
- Modify: `mcp_server/hook_hunter/tools.py` — consume shared motif service
- Modify: `mcp_server/musical_intelligence/detectors.py` — richer repetition/arc scoring
- Modify: `mcp_server/musical_intelligence/tools.py` — consume shared motif service
- Modify: `tests/test_hook_hunter_engine.py` — evidence-based tests
- Create: `tests/test_repetition_intelligence.py`

**Acceptance criteria:**
- [ ] `find_primary_hook` uses motif recurrence data (not just track name heuristics) for salience scoring
- [ ] `detect_hook_neglect` checks section placement: hook present in verse but missing from chorus = neglect signal
- [ ] `score_phrase_impact` uses motif density, not just hardcoded weights
- [ ] `detect_repetition_fatigue` combines:
  - Motif reuse count per section
  - Clip reuse (exact duplicates across scenes)
  - Density shifts between sections
  - Section-role changes
- [ ] `score_emotional_arc` incorporates density shifts and role transitions
- [ ] All outputs include `evidence_sources` showing what data informed the result
- [ ] Tests: hook detection with motif data vs without (should differ), repetition with varying density, arc with contrasting sections
- [ ] All existing tests pass

**Implementation notes:**
- HookHunter `analyzer.py` currently scores hooks by name keywords, note count, and track role. Add motif recurrence as a signal: if the motif engine finds a recurring pattern on a track, that track's hook salience goes up.
- Repetition fatigue currently counts scene/clip reuse at a surface level. Add: identical motif appearing in >60% of sections = fatigue signal.
- These are additive improvements — existing heuristics stay, new signals layer on top.

---

## Dependency Map

```
PR4 (Miswired Calls) ──► PR8 (Motif Service + SongBrain Evidence) ──► PR9 (Hook Hunter + Repetition)
```

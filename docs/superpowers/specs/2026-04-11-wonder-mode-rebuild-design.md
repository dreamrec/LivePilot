# Wonder Mode Engine Rebuild — Design Spec

**Date:** 2026-04-11
**Status:** Approved
**Scope:** Full rebuild of `mcp_server/wonder_mode/` (engine.py, tools.py, tests)

## Problem

The Wonder Mode engine was designed to generate 3 conceptually distinct creative variants (safe / strong / unexpected) ranked by taste, identity, and impact. The audit found 5 issues (WM-1 through WM-5) revealing that the engine is a template printer, not a creative engine:

1. **WM-1 (shallow):** Variants are structurally identical templates with hardcoded novelty constants. `what_changed` is always empty. `intent` is just the request text with a prefix.
2. **WM-2 (shallow):** `_taste_fit` reads 2 of ~12 available TasteGraph fields. Defaults to pure distance-from-0.5 when empty.
3. **WM-3 (shallow):** Ranking is near-deterministic. `novelty_reward` is linear (higher = always better). Identity penalty for `contrasts` never fires (threshold 0.9, hardcoded variant is 0.85).
4. **WM-4 (bug):** `rank_wonder_variants` MCP tool drops `what_changed` during dict-to-PreviewVariant reconstruction.
5. **WM-5 (design gap):** `enter_wonder_mode` and `generate_wonder_variants` return identical data in incompatible shapes.

Additionally, `_get_available_moves` grabs the first 3 moves by Python dict insertion order, ignoring request relevance and novelty profiles.

## Goals

- Each variant is built from a real semantic move matched to the request
- Moves are assigned to variants by risk/novelty profile, not arbitrary order
- Taste scoring uses the full TasteGraph (family, dimensions, anti-preferences, novelty band)
- Ranking uses actual SongBrain data (sacred elements, energy arc, identity confidence)
- Ranking outcome varies by user taste and song context, not deterministic
- Tool API is clean: 2 tools with consistent output shapes
- All fields populated (no empty `what_changed`, no dropped data on round-trip)

## Non-Goals

- Changing the PreviewVariant model (in preview_studio/models.py)
- Modifying the SongBrain builder or TasteGraph internals
- Adding new semantic moves (the existing 20 across 5 families are sufficient)
- Changing the semantic move compiler

---

## Architecture

### File Changes

| File | Action |
|------|--------|
| `mcp_server/wonder_mode/engine.py` | Full rewrite |
| `mcp_server/wonder_mode/tools.py` | Full rewrite (3 tools -> 2) |
| `mcp_server/wonder_mode/__init__.py` | Update docstring |
| `tests/test_wonder_engine.py` | Full rewrite (11 tests -> 27) |
| `tests/test_tools_contract.py` | Remove `generate_wonder_variants` from expected set, update count |
| Tool count docs (CLAUDE.md, README.md, etc.) | Audit actual count after change, update all |
| Plugin manifests | Check for hardcoded `generate_wonder_variants` references |
| CHANGELOG.md | Document changes |

### Dependencies (read-only, not modified)

| Module | What Wonder Mode uses |
|--------|----------------------|
| `semantic_moves/registry` | `list_moves()` for discovery, `get_move(id)` for full move with compile_plan |
| `semantic_moves/models` | `SemanticMove` dataclass (move_id, family, intent, targets, protect, risk_level, compile_plan) |
| `memory/taste_graph` | `TasteGraph` object: `rank_moves()`, `novelty_band`, `evidence_count` |
| `song_brain/tools` | `_current_brain` (SongBrain with sacred_elements, identity_core, identity_confidence, energy_arc) |
| `preview_studio/models` | `PreviewVariant` dataclass |

**Critical implementation note:** `registry.list_moves()` returns `to_dict()` which **omits** `compile_plan`. After scoring/filtering, the engine MUST call `registry.get_move(move_id)` and then `move.to_full_dict()` to get the full move including `compile_plan`. Passing `list_moves()` output directly will produce `compile_plan_steps: int` instead of the actual plan list.

---

## Design

### 1. Move Discovery and Assignment

#### `discover_moves(request_text, taste_graph) -> list[dict]`

Finds moves relevant to the request using keyword + taste scoring:

1. Call `registry.list_moves()` to get all 20 registered moves (mix, arrangement, transition, sound_design, performance families). Note: `list_moves(domain=...)` filters on the `SemanticMove.family` field despite the parameter being named `domain`.
2. Score each move against the request:
   - Keyword overlap: `request_words & (move_id_words | intent_words)` -> +0.3 per match
   - Target dimension match: if a target dimension name appears in request -> +0.2
3. Filter to moves with score > 0.1
4. If the TasteGraph has evidence (`evidence_count > 0`), apply taste-based reranking. If `taste_graph` is a dict, construct a `TasteGraph` object from it first (same reconstruction pattern as `compute_taste_fit` step 1). Then call `tg.rank_moves(filtered_moves)` which returns `[{...move_dict, "taste_score": 0.xyz}]`.
5. For each surviving move, call `registry.get_move(move["move_id"])` and use `.to_full_dict()` to attach the full `compile_plan`
6. Return scored and sorted list with `compile_plan` included

#### `assign_moves_to_tiers(scored_moves) -> dict[str, dict]`

Assigns moves to safe / strong / unexpected by risk profile:

- Convert `risk_level` to numeric: `{"low": 0.2, "medium": 0.5, "high": 0.8}`
- Sort scored moves by risk numeric ascending
- Assign by index:
  - **3+ moves:** `safe = moves[0]`, `strong = moves[len//2]`, `unexpected = moves[-1]`
  - **2 moves:** `safe = moves[0]`, `strong = moves[0]` (with strong envelope), `unexpected = moves[1]`. If both moves share the same `risk_level`, tiers are assigned by position only — envelope scaling still produces novelty differentiation even though the underlying move risk is the same.
  - **1 move:** Reuse the single move with 3 novelty envelopes:
    - Safe envelope: scale all `targets` values by 0.7, keep `protect` as-is
    - Strong envelope: use targets as-is
    - Unexpected envelope: scale `targets` by 1.4, relax `protect` thresholds by 0.8x
  - **0 moves:** Return empty dict (analytical-only fallback)

**Note on envelope scaling:** Envelope scaling affects `what_changed` display values and taste scoring, but does NOT modify the `compile_plan` steps (which are natural-language tool descriptions, not parameterized). The `compile_plan` is carried as-is for all envelope levels. A future version may parameterize compile plans, but for now, envelope scaling is analytical.

### 2. Variant Building

#### `build_variant(label, move_full_dict, song_brain_dict, novelty_level, envelope) -> dict`

Constructs a variant dict (not a PreviewVariant object) from a real move + SongBrain context. Returns a plain dict because the output shape includes `score_breakdown` and `targets_snapshot` which are not PreviewVariant fields.

**`intent`:** From `move["intent"]`, not the request text.

**`what_changed`:** Derived from `move["targets"]`. Example: "Targets weight (+0.4), punch (+0.3), clarity (+0.3)". When envelope is applied, shows scaled values. Never empty.

**`what_preserved`:** First from `move["protect"]` keys + thresholds, then appended with `song_brain.sacred_elements` descriptions. Example: "Protects warmth (threshold 0.6) | Sacred: Bass groove, Main hook melody". Falls back to protect-only when no SongBrain, and "core elements" only when protect is also empty.

**`why_it_matters`:** Constructed from risk_level + identity_effect + song context.

**`compiled_plan`:** The move's full `compile_plan` list from `to_full_dict()`. `None` only for analytical fallback (0 moves matched).

**`move_id`:** The actual move_id string.

**`targets_snapshot`:** The move's `targets` dict (or envelope-scaled copy). Carried for the ranking step's sacred element penalty calculation.

**`novelty_level`:** 0.25 for safe, 0.55 for strong, 0.85 for unexpected.

**`identity_effect`:** Derived from risk_level: low -> "preserves", medium -> "evolves", high -> "contrasts". Only "resets" if the move explicitly targets dimensions overlapping with sacred elements at high weight.

### 3. Taste Fit Scoring

#### `compute_taste_fit(move_dict, taste_graph) -> float`

Replaces the 2-field `_taste_fit` proxy.

1. If `taste_graph` is a dict, build a `TasteGraph` object from it. If it has `evidence_count == 0`, return 0.5 (neutral).
2. Call `taste_graph.rank_moves([move_dict])` — note: single-element list, extract `[0]["taste_score"]`
3. Return the `taste_score` (0-1, already clamped by `rank_moves`)

The `rank_moves` method handles:
- Family preference: move family score * 0.3
- Dimension alignment: sum(dim_pref * target_weight) * 0.2
- Anti-preference penalty: -0.3 per dimension in avoidances
- Risk/novelty alignment: `1.0 - abs(risk_val - novelty_band)` * 0.1

### 4. Ranking

#### `rank_variants(variant_dicts, song_brain_dict, taste_graph) -> list[dict]`

Receives variant dicts (from `build_variant` or from external callers via the `rank_wonder_variants` tool). Each dict must include `targets_snapshot` for sacred element penalty calculation. If `targets_snapshot` is missing, sacred penalty is skipped (graceful degradation).

**Components:**

| Component | Source | Range |
|-----------|--------|-------|
| `taste` | `taste_fit` field on the variant (pre-computed) | 0-1 |
| `identity` | Base from identity_effect lookup + sacred element overlap penalty | 0-1 |
| `novelty` | Bell curve centered on `novelty_band`: `exp(-((novelty - band)^2) / (2 * 0.15^2))` | 0-1 |
| `coherence` | 1.0 minus penalties for: same move_id reuse (-0.15), same target dimensions (-0.1) | 0-1 |

**Identity component detail:**
```python
base = {"preserves": 0.9, "evolves": 0.7, "contrasts": 0.4, "resets": 0.15}[effect]
targets = variant.get("targets_snapshot", {})
sacred_penalty = sum(
    sacred["salience"] * 0.15
    for sacred in song_brain.get("sacred_elements", [])
    if sacred.get("element_type") in targets and effect != "preserves"
)
identity_score = max(0.0, base - sacred_penalty)
```

**Floor rule:** To ensure "resets" never outscores "preserves" regardless of other components, the identity base for "resets" (0.15) is low enough that even with perfect novelty and taste, the identity weight (minimum 0.30 in all weight profiles) creates an insurmountable gap. The test `test_resets_never_beats_preserves` uses equal novelty levels to verify this.

**Weight selection:**

| Condition | W_taste | W_identity | W_novelty | W_coherence |
|-----------|---------|------------|-----------|-------------|
| Default | 0.25 | 0.30 | 0.20 | 0.25 |
| identity_confidence > 0.7 | 0.20 | 0.40 | 0.10 | 0.30 |
| taste evidence_count = 0 | 0.00 | 0.40 | 0.25 | 0.35 |
| All moves same family | 0.25 | 0.25 | 0.15 | 0.35 |

**Output:** Each variant dict is augmented with `score`, `rank`, and `score_breakdown` (all 4 component scores + weights used). These are injected into the dict after scoring — no PreviewVariant modification needed.

### 5. Tool API

#### Tool 1: `enter_wonder_mode(ctx, request_text, kernel_id="")`

Full pipeline: discover moves -> assign to tiers -> build variants -> compute taste -> rank.

Returns:
```json
{
    "mode": "wonder",
    "request": "<request_text>",
    "variants": [
        {
            "variant_id": "wm_<hash>_safe",
            "label": "safe",
            "rank": 1,
            "score": 0.72,
            "move_id": "tighten_low_end",
            "intent": "Tighten the low end for more punch",
            "what_changed": "Targets weight (+0.4), punch (+0.3), clarity (+0.3)",
            "what_preserved": "Protects warmth (0.6) | Sacred: Bass groove",
            "why_it_matters": "Low risk — improves punch without touching sacred groove",
            "identity_effect": "preserves",
            "novelty_level": 0.25,
            "taste_fit": 0.68,
            "targets_snapshot": {"weight": 0.4, "punch": 0.3, "clarity": 0.3},
            "compiled_plan": [{"tool": "...", "params": {}, "description": "..."}],
            "score_breakdown": {
                "taste": 0.68, "identity": 0.85,
                "novelty": 0.62, "coherence": 0.90,
                "weights": {"taste": 0.25, "identity": 0.30, "novelty": 0.20, "coherence": 0.25}
            }
        }
    ],
    "recommended": "wm_<hash>_strong",
    "taste_evidence": 12,
    "identity_confidence": 0.65,
    "move_count_matched": 3
}
```

The `variant_id` is deterministic from `hash(request_text + kernel_id)` and does NOT include a timestamp. `rank_wonder_variants` preserves incoming `variant_id` values — it does not regenerate them.

#### Tool 2: `rank_wonder_variants(ctx, variants)`

Standalone re-ranker. Accepts a list of variant dicts and returns the same ranked shape. Preserves ALL input dict fields (including `what_changed`, `compiled_plan`, `move_id`, `targets_snapshot`). Uses live `_current_brain` and session-scoped `taste_graph` from context. Does not accept `kernel_id` — always uses the current brain snapshot (consistent with other Stage 2 tools).

When input dicts lack `targets_snapshot`, sacred element penalty is skipped (graceful degradation, not an error).

---

## Testing Strategy

### Variant Generation (8 tests)

1. `test_moves_matched_by_keyword_relevance` — request "make it punchier" finds `make_punchier` move
2. `test_moves_assigned_by_risk_tier` — lowest-risk move goes to safe, highest to unexpected
3. `test_novelty_envelopes_when_one_move` — 1 match: move reused with scaled targets for all 3 tiers
4. `test_two_moves_fills_three_tiers` — exactly 2 matches: safe=moves[0], strong=moves[0]+envelope, unexpected=moves[1]
5. `test_what_changed_populated_from_targets` — never empty, shows actual target dimensions and values
6. `test_what_preserved_references_sacred_and_protect` — includes both `move.protect` keys and SongBrain sacred elements
7. `test_compiled_plan_is_list_of_dicts` — each variant's `compiled_plan` is `list[dict]` (not int, not None) when a move was matched
8. `test_different_requests_different_moves` — "punchier" and "wider" produce different move selections

### Graceful Degradation (2 tests)

9. `test_no_matching_moves_analytical_fallback` — request with no keyword matches -> analytical-only variants, `compiled_plan` is None
10. `test_no_song_brain_still_works` — empty song_brain -> variants generated, `what_preserved` uses `move.protect` keys

### Taste Fit (5 tests)

11. `test_taste_fit_uses_full_taste_graph` — score differs when family/dimension preferences exist
12. `test_taste_fit_neutral_when_no_evidence` — evidence_count=0 -> 0.5 for all
13. `test_high_novelty_band_boosts_unexpected_taste` — novelty_band=0.8 -> unexpected variant taste_fit > safe
14. `test_anti_preference_reduces_taste_fit` — move targeting avoided dimension gets penalized
15. `test_family_preference_shifts_taste_fit` — user who favors mix moves sees mix variants scored higher

### Ranking (8 tests)

16. `test_bell_curve_moderate_user_strong_wins` — novelty_band=0.5 -> "strong" has highest novelty component
17. `test_bell_curve_experimental_user_unexpected_wins` — novelty_band=0.85 -> "unexpected" has highest novelty component
18. `test_sacred_element_overlap_penalty` — move with `targets_snapshot` overlapping sacred `element_type` + non-preserving effect -> reduced identity score
19. `test_coherence_penalty_same_move` — reused move_id variants score lower on coherence than distinct moves
20. `test_weight_shift_high_identity_confidence` — identity_confidence > 0.7 -> identity weight = 0.40
21. `test_weight_shift_no_taste_evidence` — evidence_count=0 -> taste weight = 0.00
22. `test_resets_never_beats_preserves_equal_novelty` — at equal novelty_level, "resets" composite < "preserves" composite
23. `test_score_breakdown_returned` — each variant has `score_breakdown` with taste, identity, novelty, coherence, weights

### Tool API (4 tests)

24. `test_enter_wonder_mode_full_output` — returns mode, variants, recommended, taste_evidence, identity_confidence, move_count_matched
25. `test_rank_preserves_all_fields` — input dict fields survive round-trip (what_changed, compiled_plan, move_id, targets_snapshot)
26. `test_empty_request_error` — empty string returns error
27. `test_empty_variants_error` — empty list returns error

**Tool-layer test infrastructure:** Tests 24-27 call engine functions directly (not MCP tools), avoiding the need for `ctx` / FastMCP mocking. The tool wrappers are thin enough that engine-level testing covers the logic. Registration is validated by the existing `test_tools_contract.py`.

### Contract Test Update

- `test_tools_contract.py`: expected wonder mode tools = `{"enter_wonder_mode", "rank_wonder_variants"}`
- Total tool count assertion: audit actual `@mcp.tool()` count post-change, update assertion

---

## Migration

1. Audit actual `@mcp.tool()` count before changes (baseline)
2. Check plugin manifests (`livepilot/.Codex-plugin/plugin.json`, `.claude-plugin/plugin.json`) for `generate_wonder_variants` references
3. Remove `generate_wonder_variants` tool from `tools.py`
4. Rewrite `engine.py` with new functions (`discover_moves`, `assign_moves_to_tiers`, `build_variant`, `compute_taste_fit`, `rank_variants`)
5. Rewrite `tools.py` with 2 tools (`enter_wonder_mode`, `rank_wonder_variants`)
6. Rewrite `tests/test_wonder_engine.py` (27 tests)
7. Update `test_tools_contract.py` (remove `generate_wonder_variants`, update count)
8. Audit final `@mcp.tool()` count, update all doc files per CLAUDE.md checklist
9. Update CHANGELOG.md

## Risks

- **Semantic move coverage:** 20 moves across 5 families (mix, arrangement, transition, sound_design, performance). Requests about harmony or abstract creative goals may produce 0 keyword matches and fall back to analytical-only variants. This is correct degradation behavior.
- **TasteGraph cold start:** Fresh sessions have `evidence_count=0`. Weight-zeroing handles this, but early interactions feel less personalized.
- **Sacred element vocabulary mismatch:** Sacred element `element_type` values ("motif", "texture", "groove") may not exactly match move `targets` dimension keys ("punch", "width", "warmth"). The overlap penalty catches clear matches but may miss subtle ones. This is acceptable — false negatives are safe (no penalty when unsure), and the penalty is a refinement, not a gate.
- **Envelope scaling is display-only:** Novelty envelopes scale `targets` values for scoring and `what_changed` display, but do not modify `compile_plan` steps. A future version could parameterize compile plans for true envelope effect.

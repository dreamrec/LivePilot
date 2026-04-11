# Wonder Mode V1.5 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Wonder Mode from a generic "surprise me" label into a preview-first stuck-rescue workflow with honest variant labeling, real diagnosis, and end-to-end lifecycle tracking.

**Architecture:** Surgical upgrade — add `WonderSession` thin coordinator and `WonderDiagnosis` builder as new files. Modify existing Wonder engine for distinctness enforcement and analytical honesty. Wire Preview Studio commit/discard paths to record outcomes. No architectural rewrite; modules stay independent.

**Tech Stack:** Python 3.10+, FastMCP, dataclasses, pytest. Pure computation engines (zero I/O). All Ableton interaction stays in existing tool wrappers.

**Spec:** `docs/specs/2026-04-11-wonder-mode-v1.5-design.md`

---

## Chunk 1: WonderSession + WonderDiagnosis Models

### Task 1: WonderSession and WonderDiagnosis dataclasses

**Files:**
- Create: `mcp_server/wonder_mode/session.py`
- Test: `tests/test_wonder_session.py`

- [ ] **Step 1: Write the test file for WonderSession**

```python
"""Unit tests for WonderSession and WonderDiagnosis models."""

from mcp_server.wonder_mode.session import (
    WonderDiagnosis,
    WonderSession,
    get_wonder_session,
    store_wonder_session,
    _wonder_sessions,
)


def setup_function():
    _wonder_sessions.clear()


# ── Creation and storage ─────────────────────────────────────────


def test_session_creation():
    ws = WonderSession(session_id="ws_001", request_text="make it magical")
    assert ws.session_id == "ws_001"
    assert ws.status == "diagnosing"
    assert ws.outcome == "pending"
    assert ws.variant_count_actual == 0
    assert ws.variants == []


def test_store_and_retrieve():
    ws = WonderSession(session_id="ws_002", request_text="test")
    store_wonder_session(ws)
    retrieved = get_wonder_session("ws_002")
    assert retrieved is ws


def test_retrieve_missing_returns_none():
    assert get_wonder_session("nonexistent") is None


def test_eviction_at_capacity():
    for i in range(12):
        store_wonder_session(
            WonderSession(session_id=f"ws_{i:03d}", request_text=f"req {i}")
        )
    # First 2 should be evicted (max 10)
    assert get_wonder_session("ws_000") is None
    assert get_wonder_session("ws_001") is None
    # Last 10 should remain
    assert get_wonder_session("ws_002") is not None
    assert get_wonder_session("ws_011") is not None


# ── Status transitions ───────────────────────────────────────────


def test_status_defaults_to_diagnosing():
    ws = WonderSession(session_id="ws_s", request_text="test")
    assert ws.status == "diagnosing"


def test_status_transitions():
    ws = WonderSession(session_id="ws_t", request_text="test")
    ws.status = "variants_ready"
    assert ws.status == "variants_ready"
    ws.status = "previewing"
    assert ws.status == "previewing"
    ws.status = "resolved"
    assert ws.status == "resolved"


# ── Degradation ──────────────────────────────────────────────────


def test_degraded_reason_set():
    ws = WonderSession(
        session_id="ws_d",
        request_text="test",
        variant_count_actual=1,
        degraded_reason="Only 1 distinct executable move found",
    )
    assert ws.degraded_reason != ""
    assert ws.variant_count_actual == 1


# ── WonderDiagnosis ──────────────────────────────────────────────


def test_diagnosis_creation():
    diag = WonderDiagnosis(
        trigger_reason="user_request",
        problem_class="exploration",
        current_identity="Dark minimal techno",
        sacred_elements=[{"element_type": "groove", "description": "808 kick"}],
        blocked_dimensions=[],
        candidate_domains=[],
    )
    assert diag.trigger_reason == "user_request"
    assert diag.problem_class == "exploration"
    assert diag.confidence == 0.0
    assert diag.variant_budget == 3
    assert diag.degraded_capabilities == []


def test_diagnosis_to_dict():
    diag = WonderDiagnosis(
        trigger_reason="stuckness_detected",
        problem_class="overpolished_loop",
        current_identity="Ambient drone",
        sacred_elements=[],
        blocked_dimensions=["energy"],
        candidate_domains=["arrangement", "transition"],
        confidence=0.7,
        degraded_capabilities=["song_brain"],
    )
    d = diag.to_dict()
    assert d["trigger_reason"] == "stuckness_detected"
    assert d["problem_class"] == "overpolished_loop"
    assert d["candidate_domains"] == ["arrangement", "transition"]
    assert d["confidence"] == 0.7
    assert "song_brain" in d["degraded_capabilities"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_session.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.wonder_mode.session'`

- [ ] **Step 3: Write the WonderSession and WonderDiagnosis implementation**

Create `mcp_server/wonder_mode/session.py`:

```python
"""WonderSession and WonderDiagnosis — thin lifecycle coordinator.

WonderSession ties the Wonder lifecycle together: diagnosis, variant
generation, preview, commit/discard, and outcome recording.

WonderDiagnosis is a structured diagnosis built from stuckness,
SongBrain, action ledger, and creative threads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


_MAX_WONDER_SESSIONS = 10


@dataclass
class WonderDiagnosis:
    """Structured diagnosis driving Wonder variant generation."""

    trigger_reason: str  # "user_request", "stuckness_detected", "repeated_undos"
    problem_class: str  # from RESCUE_TYPES + "exploration"
    current_identity: str  # from SongBrain.identity_core
    sacred_elements: list[dict] = field(default_factory=list)
    blocked_dimensions: list[str] = field(default_factory=list)
    candidate_domains: list[str] = field(default_factory=list)
    variant_budget: int = 3
    confidence: float = 0.0
    degraded_capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WonderSession:
    """Thin lifecycle coordinator for a Wonder Mode session."""

    session_id: str
    request_text: str
    kernel_id: str = ""

    # Diagnosis
    diagnosis: Optional[WonderDiagnosis] = None

    # Lifecycle references
    creative_thread_id: str = ""
    preview_set_id: str = ""

    # Variants
    variants: list[dict] = field(default_factory=list)
    recommended: str = ""
    variant_count_actual: int = 0

    # Outcome
    selected_variant_id: str = ""
    outcome: str = "pending"  # pending, committed, rejected_all, abandoned

    # Degradation
    degraded_reason: str = ""

    status: str = "diagnosing"  # diagnosing, variants_ready, previewing, resolved

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.diagnosis:
            d["diagnosis"] = self.diagnosis.to_dict()
        return d


# ── In-memory store ───────────────────────────────────────────────

_wonder_sessions: dict[str, WonderSession] = {}


def store_wonder_session(ws: WonderSession) -> None:
    """Store a WonderSession with FIFO eviction at capacity."""
    _wonder_sessions[ws.session_id] = ws
    while len(_wonder_sessions) > _MAX_WONDER_SESSIONS:
        oldest_key = next(iter(_wonder_sessions))
        evicted = _wonder_sessions.pop(oldest_key)
        if evicted.outcome == "pending":
            evicted.outcome = "abandoned"


def get_wonder_session(session_id: str) -> Optional[WonderSession]:
    """Retrieve a WonderSession by ID."""
    return _wonder_sessions.get(session_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_session.py -x -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add mcp_server/wonder_mode/session.py tests/test_wonder_session.py
git commit -m "feat(wonder_mode): add WonderSession and WonderDiagnosis models

Thin lifecycle coordinator for Wonder V1.5. In-memory store with
FIFO eviction at 10 sessions. WonderDiagnosis holds structured
diagnosis from stuckness + SongBrain + action ledger."
```

---

### Task 2: Diagnosis builder

**Files:**
- Create: `mcp_server/wonder_mode/diagnosis.py`
- Test: `tests/test_wonder_diagnosis.py`

- [ ] **Step 1: Write the test file for diagnosis builder**

```python
"""Unit tests for Wonder Mode diagnosis builder."""

from mcp_server.wonder_mode.diagnosis import build_diagnosis
from mcp_server.wonder_mode.session import WonderDiagnosis


# ── Problem class mapping ────────────────────────────────────────


def test_stuckness_drives_problem_class():
    """Stuckness report's primary_rescue_type becomes problem_class."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.7,
            "level": "stuck",
            "primary_rescue_type": "overpolished_loop",
            "secondary_rescue_types": ["contrast_needed"],
        },
    )
    assert diag.problem_class == "overpolished_loop"
    assert diag.trigger_reason == "stuckness_detected"
    assert diag.confidence == 0.7


def test_no_stuckness_gives_exploration():
    """Without stuckness data, problem_class defaults to exploration."""
    diag = build_diagnosis()
    assert diag.problem_class == "exploration"
    assert diag.trigger_reason == "user_request"
    assert diag.candidate_domains == []


def test_low_stuckness_still_user_request():
    """Stuckness confidence < 0.2 treated as user_request, not stuckness."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.1,
            "level": "flowing",
            "primary_rescue_type": "",
        },
    )
    assert diag.trigger_reason == "user_request"
    assert diag.problem_class == "exploration"


# ── Candidate domains ────────────────────────────────────────────


def test_overpolished_loop_domains():
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.6,
            "level": "stuck",
            "primary_rescue_type": "overpolished_loop",
        },
    )
    assert diag.candidate_domains == ["arrangement", "transition"]


def test_identity_unclear_domains():
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.5,
            "level": "stuck",
            "primary_rescue_type": "identity_unclear",
        },
    )
    assert diag.candidate_domains == ["sound_design", "mix"]


def test_exploration_has_no_domain_restriction():
    diag = build_diagnosis()
    assert diag.candidate_domains == []


def test_all_rescue_types_map_to_domains():
    """Every RESCUE_TYPE must map to at least one candidate domain."""
    from mcp_server.stuckness_detector.models import RESCUE_TYPES
    for rt in RESCUE_TYPES:
        diag = build_diagnosis(
            stuckness_report={
                "confidence": 0.6,
                "level": "stuck",
                "primary_rescue_type": rt,
            },
        )
        assert len(diag.candidate_domains) > 0, f"No domains for {rt}"


# ── SongBrain integration ────────────────────────────────────────


def test_song_brain_provides_identity():
    diag = build_diagnosis(
        song_brain={
            "identity_core": "Dark minimal techno",
            "identity_confidence": 0.8,
            "sacred_elements": [
                {"element_type": "groove", "description": "808 kick", "salience": 0.8},
            ],
        },
    )
    assert diag.current_identity == "Dark minimal techno"
    assert len(diag.sacred_elements) == 1
    assert diag.sacred_elements[0]["element_type"] == "groove"


def test_missing_song_brain_degrades():
    diag = build_diagnosis()
    assert diag.current_identity == ""
    assert diag.sacred_elements == []
    assert "song_brain" in diag.degraded_capabilities


def test_missing_stuckness_degrades():
    diag = build_diagnosis(
        song_brain={"identity_core": "test", "sacred_elements": []},
    )
    assert "stuckness" not in diag.degraded_capabilities  # no stuckness = user_request, not degraded
    # But if we explicitly pass None, it's still not degraded — just not available
    assert diag.trigger_reason == "user_request"


# ── Action ledger integration ────────────────────────────────────


def test_repeated_undos_trigger():
    """3+ undos in action ledger should set trigger_reason to repeated_undos."""
    ledger = [{"kept": False}] * 4 + [{"kept": True}] * 2
    diag = build_diagnosis(action_ledger=ledger)
    assert diag.trigger_reason == "repeated_undos"


# ── Return type ──────────────────────────────────────────────────


def test_returns_wonder_diagnosis():
    diag = build_diagnosis()
    assert isinstance(diag, WonderDiagnosis)


def test_to_dict_round_trip():
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.6,
            "level": "stuck",
            "primary_rescue_type": "contrast_needed",
        },
        song_brain={
            "identity_core": "Ambient",
            "sacred_elements": [{"element_type": "pad", "description": "Pad wash"}],
        },
    )
    d = diag.to_dict()
    assert d["problem_class"] == "contrast_needed"
    assert d["current_identity"] == "Ambient"
    assert isinstance(d["sacred_elements"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_diagnosis.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.wonder_mode.diagnosis'`

- [ ] **Step 3: Write the diagnosis builder**

Create `mcp_server/wonder_mode/diagnosis.py`:

```python
"""Wonder Mode diagnosis builder — pure computation, zero I/O.

Builds a WonderDiagnosis from stuckness report, SongBrain, action
ledger, and open creative threads. Each input is optional — the
builder degrades gracefully.
"""

from __future__ import annotations

from typing import Optional

from .session import WonderDiagnosis


# ── Problem class -> candidate domains mapping ────────────────────

_DOMAIN_MAP: dict[str, list[str]] = {
    "overpolished_loop": ["arrangement", "transition"],
    "identity_unclear": ["sound_design", "mix"],
    "contrast_needed": ["transition", "arrangement", "sound_design"],
    "hook_underdeveloped": ["sound_design", "mix"],
    "too_dense_to_progress": ["mix", "arrangement"],
    "too_safe_to_progress": ["sound_design", "transition"],
    "section_missing": ["arrangement", "transition"],
    "transition_not_earned": ["transition", "arrangement"],
}

_STUCKNESS_THRESHOLD = 0.2  # Below this, treat as user_request


def build_diagnosis(
    stuckness_report: Optional[dict] = None,
    song_brain: Optional[dict] = None,
    action_ledger: Optional[list[dict]] = None,
    open_threads: Optional[list[dict]] = None,
) -> WonderDiagnosis:
    """Build a WonderDiagnosis from available session state."""
    degraded: list[str] = []

    # 1. Determine trigger reason and problem class from stuckness
    trigger_reason = "user_request"
    problem_class = "exploration"
    confidence = 0.0

    # Check action ledger for repeated undos first
    if action_ledger:
        undo_count = sum(1 for a in action_ledger if a.get("kept") is False)
        if undo_count >= 3:
            trigger_reason = "repeated_undos"

    if stuckness_report and stuckness_report.get("confidence", 0) >= _STUCKNESS_THRESHOLD:
        trigger_reason = "stuckness_detected"
        problem_class = stuckness_report.get("primary_rescue_type", "exploration") or "exploration"
        confidence = stuckness_report.get("confidence", 0.0)

    # If trigger is repeated_undos but no stuckness, keep problem_class as exploration
    if trigger_reason == "repeated_undos" and problem_class == "exploration":
        confidence = max(confidence, 0.3)

    # 2. Read SongBrain
    current_identity = ""
    sacred_elements: list[dict] = []

    if song_brain:
        current_identity = song_brain.get("identity_core", "")
        sacred_elements = song_brain.get("sacred_elements", [])
    else:
        degraded.append("song_brain")

    # 3. Map problem_class to candidate domains
    candidate_domains = _DOMAIN_MAP.get(problem_class, [])

    return WonderDiagnosis(
        trigger_reason=trigger_reason,
        problem_class=problem_class,
        current_identity=current_identity,
        sacred_elements=sacred_elements,
        blocked_dimensions=[],
        candidate_domains=list(candidate_domains),  # copy
        confidence=confidence,
        degraded_capabilities=degraded,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_diagnosis.py -x -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add mcp_server/wonder_mode/diagnosis.py tests/test_wonder_diagnosis.py
git commit -m "feat(wonder_mode): add diagnosis builder

Maps stuckness problem_class to candidate move domains. Integrates
SongBrain identity and sacred elements. Degrades gracefully when
inputs are missing."
```

---

## Chunk 2: Distinctness Enforcement + Engine Refactor

### Task 3: `select_distinct_variants` and `analytical_only` field

**Files:**
- Modify: `mcp_server/wonder_mode/engine.py`
- Test: `tests/test_wonder_distinctness.py`

- [ ] **Step 1: Write the distinctness test file**

```python
"""Unit tests for Wonder Mode variant distinctness enforcement."""

from mcp_server.wonder_mode.engine import (
    build_analytical_variant,
    build_variant,
    select_distinct_variants,
)


# ── Helpers ──────────────────────────────────────────────────────


def _move(move_id, family, tools=None, risk="low"):
    return {
        "move_id": move_id,
        "family": family,
        "intent": f"Test move {move_id}",
        "targets": {"energy": 0.5},
        "protect": {"clarity": 0.7},
        "risk_level": risk,
        "compile_plan": [
            {"tool": t, "params": {}, "description": f"Do {t}"} for t in (tools or ["set_track_volume"])
        ],
        "relevance_score": 0.5,
        "confidence": 0.7,
    }


# ── Distinct selection ───────────────────────────────────────────


def test_three_different_families_gives_three():
    """3 moves from different families -> 3 distinct variants."""
    moves = [
        _move("punch", "mix"),
        _move("build_section", "arrangement"),
        _move("add_riser", "transition"),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 3
    families = {m["family"] for m in result}
    assert len(families) == 3


def test_two_families_gives_two():
    """2 distinct families -> only 2 moves returned."""
    moves = [
        _move("punch", "mix", tools=["set_track_volume"]),
        _move("widen", "mix", tools=["set_track_volume"]),  # same family AND same shape
        _move("build_section", "arrangement", tools=["create_clip"]),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 2
    ids = {m["move_id"] for m in result}
    assert "punch" in ids
    assert "build_section" in ids


def test_same_family_different_shape_is_distinct():
    """Same family but different compile_plan shapes = distinct."""
    moves = [
        _move("punch", "mix", tools=["set_track_volume", "set_track_send"]),
        _move("widen", "mix", tools=["set_device_parameter", "set_track_pan"]),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 2


def test_same_family_same_shape_not_distinct():
    """Same family + same tool set = NOT distinct."""
    moves = [
        _move("punch", "mix", tools=["set_track_volume"]),
        _move("louder", "mix", tools=["set_track_volume"]),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 1


def test_one_move_returns_one():
    """Single move -> 1 variant."""
    moves = [_move("punch", "mix")]
    result = select_distinct_variants(moves)
    assert len(result) == 1


def test_zero_moves_returns_empty():
    """No moves -> empty list."""
    result = select_distinct_variants([])
    assert result == []


def test_same_move_id_never_duplicated():
    """Same move_id must not appear twice."""
    moves = [
        _move("punch", "mix"),
        _move("punch", "mix"),
        _move("widen", "sound_design"),
    ]
    result = select_distinct_variants(moves)
    ids = [m["move_id"] for m in result]
    assert len(ids) == len(set(ids))


# ── analytical_only field ────────────────────────────────────────


def test_build_variant_has_analytical_only_false():
    move = _move("punch", "mix")
    v = build_variant(label="safe", move_dict=move, novelty_level=0.25, variant_id="v1")
    assert v["analytical_only"] is False


def test_build_analytical_variant_has_analytical_only_true():
    v = build_analytical_variant(label="safe", request_text="test", novelty_level=0.25, variant_id="v1")
    assert v["analytical_only"] is True
    assert v["compiled_plan"] is None


def test_build_variant_has_distinctness_reason():
    move = _move("punch", "mix")
    v = build_variant(label="safe", move_dict=move, novelty_level=0.25, variant_id="v1")
    assert "distinctness_reason" in v
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_distinctness.py -x -q`
Expected: FAIL — `ImportError: cannot import name 'select_distinct_variants'`

- [ ] **Step 3: Modify engine.py — add `select_distinct_variants`, update `build_variant` and `build_analytical_variant`**

In `mcp_server/wonder_mode/engine.py`:

1. Add `select_distinct_variants` function (replaces `assign_moves_to_tiers`)
2. Add `analytical_only` and `distinctness_reason` fields to `build_variant` return
3. Add `analytical_only: True` to `build_analytical_variant` return

```python
# Add after the _RISK_NUMERIC dict (line 108), replacing assign_moves_to_tiers:

def _compile_plan_shape(move: dict) -> frozenset[str]:
    """Extract the set of tool names from a move's compile_plan."""
    plan = move.get("compile_plan") or []
    return frozenset(step.get("tool", "") for step in plan if step.get("tool"))


def select_distinct_variants(scored_moves: list[dict]) -> list[dict]:
    """Select genuinely distinct moves for variant generation.

    Each selected move must differ from all previously selected moves by
    at least one of: move_id, family, or compile_plan shape.
    Returns 0-3 moves.
    """
    if not scored_moves:
        return []

    selected: list[dict] = []
    used_ids: set[str] = set()
    used_shapes: list[tuple[str, frozenset]] = []  # (family, shape) pairs

    for move in scored_moves:
        mid = move.get("move_id", "")
        family = move.get("family", "")
        shape = _compile_plan_shape(move)

        # Skip duplicate move_ids
        if mid in used_ids:
            continue

        # Check distinctness against already-selected moves
        is_distinct = True
        for sel_family, sel_shape in used_shapes:
            if family == sel_family and shape == sel_shape:
                is_distinct = False
                break

        if is_distinct:
            selected.append(move)
            used_ids.add(mid)
            used_shapes.append((family, shape))

        if len(selected) >= 3:
            break

    return selected
```

Update `build_variant` return dict (around line 208) — add two fields:

```python
        "analytical_only": False,
        "distinctness_reason": "",
```

Update `build_analytical_variant` return dict (around line 230) — add:

```python
        "analytical_only": True,
        "distinctness_reason": "No matching executable move — directional suggestion only",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_distinctness.py -x -q`
Expected: all pass

- [ ] **Step 5: Run existing wonder engine tests to check nothing broke**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_engine.py -x -q`
Expected: all pass (existing tests don't import `select_distinct_variants` yet)

- [ ] **Step 6: Commit**

```bash
git add mcp_server/wonder_mode/engine.py tests/test_wonder_distinctness.py
git commit -m "feat(wonder_mode): add select_distinct_variants and analytical_only field

Distinctness by move_id + family + compile_plan shape. Variants
honestly labeled analytical_only when no executable move matches."
```

---

### Task 4: Rename `generate_and_rank` to `generate_wonder_variants` with diagnosis integration

**Files:**
- Modify: `mcp_server/wonder_mode/engine.py`
- Modify: `tests/test_wonder_engine.py`

- [ ] **Step 1: Update engine.py — rename and integrate diagnosis**

In `mcp_server/wonder_mode/engine.py`, rename `generate_and_rank` to `generate_wonder_variants`. Update it to:
1. Accept `diagnosis: dict | None = None` parameter
2. Pass `candidate_domains` from diagnosis to `discover_moves`
3. Use `select_distinct_variants` instead of `assign_moves_to_tiers`
4. Build executable variants from distinct moves with labels + distinctness reasons
5. Pad with analytical variants up to 3
6. Return `variant_count_actual` and `degraded_reason`

Replace the entire `generate_and_rank` function (lines 371-427) with:

```python
def generate_wonder_variants(
    request_text: str,
    diagnosis: dict | None = None,
    kernel_id: str = "",
    song_brain: dict | None = None,
    taste_graph: object = None,
    active_constraints: object = None,
) -> dict:
    """Full wonder mode pipeline: discover -> select distinct -> build -> taste -> rank."""
    song_brain = song_brain or {}
    diagnosis = diagnosis or {}
    set_prefix = _wonder_id(request_text, kernel_id)

    candidate_domains = diagnosis.get("candidate_domains") or None
    moves = discover_moves(request_text, taste_graph, active_constraints, candidate_domains)
    distinct = select_distinct_variants(moves)

    labels = ["safe", "strong", "unexpected"]
    variants = []

    # Build executable variants from distinct moves
    for i, move in enumerate(distinct):
        label = labels[i]
        move_with_envelope = _with_envelope(move, label)
        v = build_variant(
            label=label,
            move_dict=move_with_envelope,
            song_brain=song_brain,
            novelty_level=_NOVELTY_LEVELS.get(label, 0.5),
            variant_id=f"{set_prefix}_{label}",
        )
        if taste_graph is not None:
            v["taste_fit"] = compute_taste_fit(move, taste_graph)
        v["distinctness_reason"] = _explain_distinctness(move, distinct, i)
        variants.append(v)

    executable_count = len(variants)

    # Pad with analytical variants
    while len(variants) < 3:
        idx = len(variants)
        v = build_analytical_variant(
            label=labels[idx],
            request_text=request_text,
            novelty_level=_NOVELTY_LEVELS.get(labels[idx], 0.5),
            variant_id=f"{set_prefix}_{labels[idx]}",
        )
        variants.append(v)

    novelty_band = 0.5
    taste_evidence = 0
    if taste_graph is not None and hasattr(taste_graph, "novelty_band"):
        novelty_band = taste_graph.novelty_band
        taste_evidence = getattr(taste_graph, "evidence_count", 0)

    ranked = rank_variants(
        variants,
        song_brain=song_brain,
        novelty_band=novelty_band,
        taste_evidence=taste_evidence,
    )

    degraded_reason = ""
    if executable_count == 0:
        degraded_reason = "No matching executable moves found"
    elif executable_count == 1:
        degraded_reason = "Only 1 distinct executable move found"

    return {
        "mode": "wonder",
        "request": request_text,
        "variants": ranked,
        "recommended": ranked[0]["variant_id"] if ranked else "",
        "taste_evidence": taste_evidence,
        "identity_confidence": song_brain.get("identity_confidence", 0.0),
        "move_count_matched": len(moves),
        "variant_count_actual": executable_count,
        "degraded_reason": degraded_reason,
    }


def _explain_distinctness(move: dict, all_moves: list[dict], index: int) -> str:
    """Explain why this variant is different from the others."""
    family = move.get("family", "")
    other_families = {m.get("family", "") for i, m in enumerate(all_moves) if i != index}

    if family not in other_families:
        return f"Different family: {family}"
    shape = _compile_plan_shape(move)
    return f"Different approach: {', '.join(sorted(shape))}"
```

Also update `discover_moves` to accept `candidate_domains` — add the parameter and filtering logic after keyword scoring but before taste reranking (around line 50):

```python
    # Domain filtering if provided
    if candidate_domains:
        domain_filtered = [(m, s) for m, s in scored if m.get("family") in candidate_domains]
        if domain_filtered:  # fall back to full list if filtering removes all
            scored = domain_filtered
```

- [ ] **Step 2: Run all wonder tests (existing tests should still pass — old functions still exist alongside new ones)**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_engine.py tests/test_wonder_distinctness.py tests/test_wonder_diagnosis.py tests/test_wonder_session.py -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add mcp_server/wonder_mode/engine.py
git commit -m "feat(wonder_mode): rename generate_and_rank to generate_wonder_variants

Integrates diagnosis for domain filtering. Uses select_distinct_variants
instead of assign_moves_to_tiers. Returns variant_count_actual and
degraded_reason."
```

---

## Chunk 3: Tool Layer Rewrite + New Tool

### Task 5: Rewrite `enter_wonder_mode` tool

**Files:**
- Modify: `mcp_server/wonder_mode/tools.py`

- [ ] **Step 1: Rewrite `enter_wonder_mode` in tools.py**

The tool now:
1. Gathers stuckness report, song brain, action ledger, open threads
2. Builds diagnosis via `build_diagnosis`
3. Calls `engine.generate_wonder_variants` with diagnosis
4. Creates and stores a WonderSession
5. Opens a creative thread (NOT a turn resolution)
6. Returns full response with `wonder_session_id`, `diagnosis`, `variants`

Key changes:
- Remove the `record_turn_resolution("proposed")` block (lines 88-103)
- Add stuckness and ledger gathering helpers
- Create WonderSession and store it

```python
@mcp.tool()
def enter_wonder_mode(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
) -> dict:
    """Activate Wonder Mode — stuck-rescue workflow with real diagnosis.

    Diagnoses why the session needs creative rescue, generates 1-3
    genuinely distinct executable variants (plus honest analytical
    fallbacks), and opens a creative thread for tracking.

    Returns wonder_session_id for use with create_preview_set,
    commit_preview_variant, and discard_wonder_session.

    request_text: the creative request or description of being stuck
    kernel_id: optional session kernel reference
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    from .diagnosis import build_diagnosis
    from .session import WonderSession, store_wonder_session

    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph(ctx)
    active_constraints = _get_active_constraints()
    action_ledger = _get_ledger_entries(ctx)
    stuckness_report = _get_stuckness_report(ctx, song_brain)

    # 1. Build diagnosis
    diagnosis = build_diagnosis(
        stuckness_report=stuckness_report,
        song_brain=song_brain,
        action_ledger=action_ledger,
    )

    # 2. Generate variants
    result = engine.generate_wonder_variants(
        request_text=request_text,
        diagnosis=diagnosis.to_dict(),
        kernel_id=kernel_id,
        song_brain=song_brain,
        taste_graph=taste_graph,
        active_constraints=active_constraints,
    )

    # 3. Create WonderSession (use _wonder_id for stable session ID)
    from .engine import _wonder_id
    session_id = _wonder_id(request_text, kernel_id)
    ws = WonderSession(
        session_id=session_id,
        request_text=request_text,
        kernel_id=kernel_id,
        diagnosis=diagnosis,
        variants=result["variants"],
        recommended=result.get("recommended", ""),
        variant_count_actual=result.get("variant_count_actual", 0),
        degraded_reason=result.get("degraded_reason", ""),
        status="variants_ready",
    )

    # 4. Open creative thread (exploration, NOT turn resolution)
    #    domain uses the first candidate_domain (move family), not problem_class
    try:
        from ..session_continuity.tracker import open_thread
        thread_domain = diagnosis.candidate_domains[0] if diagnosis.candidate_domains else "exploration"
        thread = open_thread(
            description=f"Wonder: {request_text}",
            domain=thread_domain,
        )
        ws.creative_thread_id = thread.thread_id
    except Exception:
        pass

    # 5. Store session
    store_wonder_session(ws)

    # 6. Return full response
    return {
        "wonder_session_id": ws.session_id,
        "creative_thread_id": ws.creative_thread_id,
        "diagnosis": diagnosis.to_dict(),
        "variants": result["variants"],
        "recommended": result.get("recommended", ""),
        "variant_count_actual": result.get("variant_count_actual", 0),
        "degraded_reason": ws.degraded_reason,
        "mode": "wonder",
    }
```

Add helper functions:

```python
def _get_ledger_entries(ctx: Context) -> list[dict]:
    """Get recent action ledger entries as dicts.

    The ledger is stored on ctx.lifespan_context as a SessionLedger.
    Returns list of LedgerEntry.to_dict() dicts (newest first).
    """
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger: SessionLedger = ctx.lifespan_context.setdefault(
            "action_ledger", SessionLedger()
        )
        entries = ledger.get_recent_moves(limit=20)
        return [e.to_dict() for e in entries]
    except Exception:
        return []


def _get_stuckness_report(ctx: Context, song_brain: dict) -> dict | None:
    """Run stuckness detection on recent actions if available."""
    try:
        from ..stuckness_detector.detector import detect_stuckness
        action_ledger = _get_ledger_entries(ctx)
        if not action_ledger:
            return None
        report = detect_stuckness(
            action_history=action_ledger,
            song_brain=song_brain,
        )
        return report.to_dict()
    except Exception:
        return None
```

- [ ] **Step 2: Update the docstring tool count at top of file**

Change from "2 tools" to "3 tools" and add `discard_wonder_session` to the list.

- [ ] **Step 3: Run existing tests to check nothing broke**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_tools_contract.py -x -q`
Expected: pass (tool count still 292 — we haven't added the new tool yet)

- [ ] **Step 4: Commit**

```bash
git add mcp_server/wonder_mode/tools.py
git commit -m "feat(wonder_mode): rewrite enter_wonder_mode with diagnosis lifecycle

Builds diagnosis from stuckness + SongBrain + action ledger. Creates
WonderSession. Opens creative thread. Removes premature turn recording."
```

---

### Task 6: Add `discard_wonder_session` tool

**Files:**
- Modify: `mcp_server/wonder_mode/tools.py`
- Modify: `tests/test_tools_contract.py`

- [ ] **Step 1: Add the `discard_wonder_session` tool to tools.py**

```python
@mcp.tool()
def discard_wonder_session(
    ctx: Context,
    wonder_session_id: str,
) -> dict:
    """Reject all Wonder variants and close the session.

    The creative thread stays open — the problem isn't solved.
    Records a rejected turn resolution and updates taste.

    wonder_session_id: the session to discard
    """
    from .session import get_wonder_session
    import time

    ws = get_wonder_session(wonder_session_id)
    if not ws:
        return {"error": "Wonder session not found", "wonder_session_id": wonder_session_id}

    if ws.status == "resolved":
        return {"error": "Session already resolved", "wonder_session_id": wonder_session_id}

    ws.outcome = "rejected_all"
    ws.status = "resolved"

    # Record rejected turn
    try:
        from ..session_continuity.tracker import record_turn_resolution
        record_turn_resolution(
            request_text=ws.request_text,
            outcome="rejected",
            move_applied="",
            identity_effect="",
            user_sentiment="disliked",
        )
    except Exception:
        pass

    # Discard linked preview set
    if ws.preview_set_id:
        try:
            from ..preview_studio.engine import discard_set
            discard_set(ws.preview_set_id)
        except Exception:
            pass

    return {
        "discarded": True,
        "wonder_session_id": wonder_session_id,
        "thread_still_open": bool(ws.creative_thread_id),
    }
```

- [ ] **Step 2: Update tool count in test_tools_contract.py**

Change `assert len(tools) == 292` to `assert len(tools) == 293`

- [ ] **Step 3: Run contract test**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_tools_contract.py::test_total_tool_count -x -q`
Expected: pass with 293

- [ ] **Step 4: Commit**

```bash
git add mcp_server/wonder_mode/tools.py tests/test_tools_contract.py
git commit -m "feat(wonder_mode): add discard_wonder_session tool (292->293)

Rejects all variants, keeps creative thread open, records rejected
turn resolution. Tool count now 293."
```

---

## Chunk 4: Preview Studio Integration

### Task 7: Wire Preview Studio to WonderSession

**Files:**
- Modify: `mcp_server/preview_studio/tools.py`
- Modify: `tests/test_preview_studio.py`

- [ ] **Step 1: Add test for Wonder-linked preview creation and analytical refusal**

Add to `tests/test_preview_studio.py`:

```python
from mcp_server.wonder_mode.session import (
    WonderSession,
    store_wonder_session,
    _wonder_sessions,
)
from mcp_server.preview_studio.engine import get_preview_set


def test_analytical_variant_refused_in_wonder_context():
    """Wonder-linked analytical variant should be refused by render."""
    # This tests the tool-level contract — analytical variants from Wonder
    # must not be treated as previewable. The actual render_preview_variant
    # tool requires Ableton context, so we test the guard logic directly.
    from mcp_server.preview_studio.tools import _should_refuse_analytical
    assert _should_refuse_analytical(compiled_plan=None, wonder_linked=True) is True
    assert _should_refuse_analytical(compiled_plan=None, wonder_linked=False) is False
    assert _should_refuse_analytical(compiled_plan=[{"tool": "x"}], wonder_linked=True) is False
```

- [ ] **Step 2: Modify `preview_studio/tools.py`**

Add a helper function for the analytical refusal check:

```python
def _should_refuse_analytical(compiled_plan, wonder_linked: bool) -> bool:
    """Check if an analytical variant should be refused."""
    return compiled_plan is None and wonder_linked
```

Modify `create_preview_set` to accept `wonder_session_id`:
- When provided, read executable variants from WonderSession
- Filter out `analytical_only` variants
- Create PreviewVariants using the adapter mapping from the spec
- Set `ws.preview_set_id` and `ws.status = "previewing"`

Modify `commit_preview_variant`:
- After committing, check if linked to WonderSession
- If so: record turn resolution, update taste, resolve thread, update WonderSession

Modify `render_preview_variant`:
- Add check: if Wonder-linked and `compiled_plan is None`, return error

- [ ] **Step 3: Run preview studio tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_preview_studio.py -x -q`
Expected: all pass

- [ ] **Step 4: Run full test suite**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/ -x -q --timeout=30`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add mcp_server/preview_studio/tools.py tests/test_preview_studio.py
git commit -m "feat(preview_studio): integrate WonderSession lifecycle

create_preview_set accepts wonder_session_id. commit_preview_variant
records outcome to session continuity and taste. Analytical variants
refused in Wonder context."
```

---

## Chunk 5: Existing Test Updates + Lifecycle Test

### Task 8: Update existing wonder engine tests and remove dead code

**Files:**
- Modify: `mcp_server/wonder_mode/engine.py`
- Modify: `tests/test_wonder_engine.py`

- [ ] **Step 1: Remove `assign_moves_to_tiers` and `generate_and_rank` from engine.py**

These old functions are now dead code — replaced by `select_distinct_variants` and `generate_wonder_variants`. Remove the old functions entirely.

- [ ] **Step 2: Update test imports and function references**

In `tests/test_wonder_engine.py`:
- Remove `assign_moves_to_tiers` and `generate_and_rank` from imports
- Add `select_distinct_variants` and `generate_wonder_variants` to imports
- Replace all `assign_moves_to_tiers(...)` calls with `select_distinct_variants(...)`
- Replace all `generate_and_rank(...)` calls with `generate_wonder_variants(...)`
- Add `analytical_only` field assertions to variant creation tests
- Add `variant_count_actual` assertions to pipeline tests
- Update any tests that checked `assign_moves_to_tiers` returning a dict with "safe"/"strong"/"unexpected" keys — `select_distinct_variants` returns a flat list instead

- [ ] **Step 2: Run updated tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_engine.py -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_wonder_engine.py
git commit -m "test(wonder_mode): update tests for V1.5 API changes

Rename generate_and_rank -> generate_wonder_variants, replace
assign_moves_to_tiers with select_distinct_variants, add
analytical_only and variant_count_actual assertions."
```

---

### Task 9: Wonder lifecycle integration test

**Files:**
- Create: `tests/test_wonder_lifecycle.py`

- [ ] **Step 1: Write lifecycle integration test**

```python
"""End-to-end Wonder Mode lifecycle tests — pure computation, no Ableton."""

from mcp_server.wonder_mode.session import (
    WonderSession,
    WonderDiagnosis,
    get_wonder_session,
    store_wonder_session,
    _wonder_sessions,
)
from mcp_server.wonder_mode.diagnosis import build_diagnosis
from mcp_server.wonder_mode.engine import generate_wonder_variants
from mcp_server.session_continuity.tracker import (
    reset_story,
    _turns,
    _threads,
    open_thread,
    list_open_threads,
    record_turn_resolution,
    resolve_thread,
)


def setup_function():
    _wonder_sessions.clear()
    reset_story()


# ── Full lifecycle ───────────────────────────────────────────────


def test_lifecycle_diagnosis_to_variants():
    """Diagnosis -> variant generation -> session creation."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.6,
            "level": "stuck",
            "primary_rescue_type": "contrast_needed",
        },
        song_brain={
            "identity_core": "Dark techno",
            "sacred_elements": [{"element_type": "groove", "description": "kick"}],
        },
    )

    result = generate_wonder_variants(
        request_text="make it more interesting",
        diagnosis=diag.to_dict(),
        song_brain={"identity_core": "Dark techno", "sacred_elements": []},
    )

    assert "variants" in result
    assert len(result["variants"]) == 3
    assert "variant_count_actual" in result
    assert "degraded_reason" in result

    # At least some should have analytical_only field
    for v in result["variants"]:
        assert "analytical_only" in v


def test_no_turn_resolution_at_generation():
    """Generating variants must NOT record a turn resolution."""
    initial_turn_count = len(_turns)

    diag = build_diagnosis()
    generate_wonder_variants(
        request_text="surprise me",
        diagnosis=diag.to_dict(),
    )

    # No turns should have been added
    assert len(_turns) == initial_turn_count


def test_commit_records_turn():
    """Committing a variant should record a turn resolution."""
    initial_turn_count = len(_turns)

    record_turn_resolution(
        request_text="test commit",
        outcome="accepted",
        move_applied="test_move",
        identity_effect="evolves",
        user_sentiment="liked",
    )

    assert len(_turns) == initial_turn_count + 1
    assert _turns[-1].outcome == "accepted"


def test_reject_records_turn_thread_stays_open():
    """Rejecting all variants should record rejection and keep thread open."""
    thread = open_thread(description="Wonder: test", domain="exploration")
    thread_id = thread.thread_id

    record_turn_resolution(
        request_text="test reject",
        outcome="rejected",
        user_sentiment="disliked",
    )

    assert _turns[-1].outcome == "rejected"
    # Thread should still be open
    open = list_open_threads()
    assert any(t.thread_id == thread_id for t in open)


def test_commit_resolves_thread():
    """Committing should resolve the creative thread."""
    thread = open_thread(description="Wonder: test", domain="exploration")
    resolve_thread(thread.thread_id)

    open = list_open_threads()
    assert not any(t.thread_id == thread.thread_id for t in open)


def test_wonder_session_stores_diagnosis():
    """WonderSession must preserve the diagnosis object."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.7,
            "level": "stuck",
            "primary_rescue_type": "overpolished_loop",
        },
    )
    ws = WonderSession(
        session_id="ws_lc_1",
        request_text="test",
        diagnosis=diag,
        status="variants_ready",
    )
    store_wonder_session(ws)

    retrieved = get_wonder_session("ws_lc_1")
    assert retrieved.diagnosis.problem_class == "overpolished_loop"


def test_analytical_only_variants_flagged():
    """Variants with no compiled_plan must be analytical_only=True."""
    result = generate_wonder_variants(
        request_text="completely nonexistent request xyz123",
    )
    for v in result["variants"]:
        if v.get("compiled_plan") is None:
            assert v["analytical_only"] is True
        else:
            assert v["analytical_only"] is False
```

- [ ] **Step 2: Run lifecycle tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_lifecycle.py -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_wonder_lifecycle.py
git commit -m "test(wonder_mode): add lifecycle integration tests

Covers diagnosis->variants, no premature turn recording, commit
records turns, reject keeps thread open, analytical_only flagging."
```

---

## Chunk 6: Skills, Docs, and Tool Count Sync

### Task 10: Create Wonder skill

**Files:**
- Create: `livepilot/skills/livepilot-wonder/SKILL.md`

- [ ] **Step 1: Write the Wonder skill**

```markdown
---
name: livepilot-wonder
description: >
  This skill should be used when the user asks to "surprise me",
  "make it magical", "I'm stuck", "give me options", "take it somewhere",
  or when stuckness confidence is high. Provides the Wonder Mode
  stuck-rescue workflow with honest variant labeling and preview-first UX.
---

# Wonder Mode — Stuck-Rescue Workflow

Wonder Mode is a **preview-first stuck-rescue workflow**. It diagnoses
why a session is stuck, generates genuinely distinct executable options,
and lets the user preview, compare, and commit.

## When to Trigger

- User says "I'm stuck", "surprise me", "make it magical", "give me options"
- `detect_stuckness` confidence > 0.5
- 3+ consecutive undos in action ledger
- Multiple plausible next moves with no clear winner

## When NOT to Trigger

- Exact operational requests ("set track 3 volume to -6dB")
- Narrow deterministic edits ("quantize this clip")
- Performance-safe-only context (unless explicitly requested)

## The Workflow

1. `enter_wonder_mode` — get diagnosis + 1-3 variants
2. Explain the diagnosis in **musical language**, not tool language
3. Present variants honestly:
   - Executable variants: can be previewed and committed
   - Analytical variants (`analytical_only: true`): directional ideas only
4. `create_preview_set` with `wonder_session_id` for executable variants
5. `render_preview_variant` for each executable variant
6. `compare_preview_variants` — present recommendation with reasons
7. User chooses:
   - `commit_preview_variant` — applies the variant, records outcome
   - `discard_wonder_session` — rejects all, keeps creative thread open

## Honesty Rules

- **Never describe an analytical variant as previewable**
- **Never fabricate distinctness** by relabeling the same move
- **Fewer than 3 variants is correct** when fewer distinct moves exist
- 1 executable + 2 analytical is an honest, useful result
- The `variant_count_actual` field tells you how many are real

## Presenting Results

For each variant, explain:
- What it changes (in musical terms)
- What it preserves (sacred elements)
- Why it matters for this specific session
- Whether it's executable or analytical-only

For the recommendation, explain:
- Why this one over the others
- What risk it introduces
- What sacred elements it preserves
```

- [ ] **Step 2: Update core skill with Wonder routing section**

Add to `livepilot/skills/livepilot-core/SKILL.md` in the appropriate section:

```markdown
## Wonder Mode — Stuck-Rescue Routing

- Use Wonder for creative ambiguity and session rescue
- Do not fabricate three variants when only one real option exists
- Do not describe a branch as previewable unless it has a valid `compiled_plan`
- Prefer Wonder when `detect_stuckness` confidence > 0.5
- Prefer Wonder when the user's request is emotionally-shaped, not parametric
```

- [ ] **Step 3: Commit**

```bash
git add livepilot/skills/livepilot-wonder/SKILL.md livepilot/skills/livepilot-core/SKILL.md
git commit -m "feat(skills): add Wonder skill, update core skill with routing

Dedicated Wonder skill defines trigger conditions, workflow steps,
and honesty rules. Core skill adds Wonder routing guidance."
```

---

### Task 11: Sync tool count 292 -> 293 across all manifests

**Files:** (per CLAUDE.md checklist)
- Modify: `README.md`
- Modify: `package.json`
- Modify: `livepilot/.Codex-plugin/plugin.json`
- Modify: `livepilot/.claude-plugin/plugin.json`
- Modify: `server.json`
- Modify: `livepilot/skills/livepilot-core/SKILL.md`
- Modify: `livepilot/skills/livepilot-core/references/overview.md`
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/manual/index.md`
- Modify: `docs/manual/tool-reference.md`

- [ ] **Step 1: Find and replace 292 -> 293 in all listed files**

Use grep to find all occurrences of "292" in the listed files. Replace each with "293". Be careful to only replace tool count references, not other numbers.

- [ ] **Step 2: Update CHANGELOG.md with V1.5 section**

Add a new changelog entry above the existing 1.9.23 entry:

```markdown
## 1.9.24 — Wonder Mode V1.5: Stuck-Rescue Workflow (April 2026)

### Wonder Mode Redesign
- **feat(wonder_mode):** Diagnosis-first workflow — stuckness detection drives variant generation
- **feat(wonder_mode):** Honest variant labeling — `analytical_only: true` for non-executable variants
- **feat(wonder_mode):** Real distinctness enforcement — variants must differ by move, family, or plan shape
- **feat(wonder_mode):** WonderSession lifecycle — diagnosis → variants → preview → commit/discard
- **feat(wonder_mode):** `discard_wonder_session` tool — reject all variants, keep creative thread open
- **feat(preview_studio):** Wonder-aware preview — accepts `wonder_session_id`, refuses analytical variants
- **feat(preview_studio):** Commit lifecycle hooks — records outcome to continuity and taste
- **feat(session_continuity):** No more premature turn recording — only commit/reject record turns
- **feat(skills):** New `livepilot-wonder` skill with trigger conditions and honesty rules

### New Tools (1 new, 292→293)
- **feat(wonder_mode):** `discard_wonder_session` — reject all Wonder variants, keep thread open
```

- [ ] **Step 3: Update CLAUDE.md tool count**

Change `292 tools across 39 domains` to `293 tools across 39 domains`.

**Note:** Version bump (1.9.23 -> 1.9.24) is deferred — only bump when this branch is ready to merge. Tool count sync is independent of version.

**Note:** Command surface updates (mix, arrange, sounddesign, performance, evaluation skills) from spec Section 4 are deferred to a follow-up PR — they are guidance-only changes that don't affect tool behavior.

- [ ] **Step 4: Run contract test to verify**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_tools_contract.py::test_total_tool_count -x -q`
Expected: pass with 293

- [ ] **Step 5: Commit**

```bash
git add README.md package.json server.json CLAUDE.md CHANGELOG.md \
  livepilot/.Codex-plugin/plugin.json livepilot/.claude-plugin/plugin.json \
  livepilot/skills/livepilot-core/SKILL.md \
  livepilot/skills/livepilot-core/references/overview.md \
  docs/manual/index.md docs/manual/tool-reference.md
git commit -m "chore: sync tool count 292->293 across all manifests

Wonder Mode V1.5 adds discard_wonder_session. Updated all 12
manifest/doc locations per CLAUDE.md checklist."
```

---

### Task 12: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/ -x -q --timeout=30`
Expected: all pass

- [ ] **Step 2: Verify no import cycles**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -c "from mcp_server.wonder_mode.session import WonderSession; from mcp_server.wonder_mode.diagnosis import build_diagnosis; from mcp_server.wonder_mode.engine import generate_wonder_variants; print('All imports OK')"` 
Expected: "All imports OK"

- [ ] **Step 3: Verify tool count matches**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_tools_contract.py -x -q`
Expected: all pass with 293

- [ ] **Step 4: Final commit (if any remaining changes)**

Only if there are uncommitted fixes from verification.

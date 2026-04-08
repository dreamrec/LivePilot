# LivePilot V2 Engine Architecture — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared substrate layer (Project Brain, Capability State, Action Ledger, Evaluation Fabric, Memory Fabric V2) and the first domain engine (Mix Engine V1) on top of LivePilot's existing 200-tool MCP server.

**Architecture:** Five infrastructure modules provide shared state, capability awareness, action tracking, evaluation, and memory to all engines. Each module is pure Python (zero I/O) with MCP tool wrappers. The Mix Engine is the first domain engine built on top, proving the architecture works end-to-end.

**Tech Stack:** Python 3.9+, FastMCP, dataclasses, JSON serialization, pytest

**Source specs (in `/tmp/LivePilot-audit/docs/`):**
- PROJECT_BRAIN_V1.md
- CAPABILITY_STATE_V1.md
- ACTION_LEDGER_V1.md
- EVALUATION_FABRIC_V1.md
- MEMORY_FABRIC_V2.md
- MIX_ENGINE_V1.md
- LIVEPILOT_IMPLEMENTATION_ROADMAP_V1.md

**Shipped code baseline:** 200 MCP tools, 21 domains, 10 engine files in `mcp_server/tools/`

---

## Phase Map

| Phase | Name | Spec | New Files | New Tools | Depends On |
|-------|------|------|-----------|-----------|------------|
| 0 | Agent OS Hardening | AGENT_OS_PHASE0_HARDENING_PLAN | 2 | 0 | nothing |
| 1A | Project Brain | PROJECT_BRAIN_V1 | 8 | 3 | Phase 0 |
| 1B | Capability State | CAPABILITY_STATE_V1 | 3 | 1 | nothing |
| 1C | Action Ledger | ACTION_LEDGER_V1 | 2 | 2 | Phase 1A |
| 1D | Evaluation Fabric | EVALUATION_FABRIC_V1 | 6 | 2 | Phase 1C |
| 1E | Memory Fabric V2 | MEMORY_FABRIC_V2 | 3 | 3 | Phase 1D |
| 2A | Mix Engine | MIX_ENGINE_V1 | 6 | 6 | Phase 1A-1E |

**Total new:** ~30 files, ~17 new MCP tools (200 → ~217)

Each phase is a self-contained deliverable with its own tests, commit, and exit criteria. A new session can pick up any phase by reading this plan + the relevant spec.

---

## File Structure Overview

```
mcp_server/
  tools/
    _agent_os_engine.py          # Phase 0: hardening fixes
    agent_os.py                  # Phase 0: tool wrapper fixes
    _snapshot_normalizer.py      # Phase 0: new — canonical snapshot normalization
    _evaluation_contracts.py     # Phase 0: new — shared evaluation types

  project_brain/
    __init__.py                  # Phase 1A
    models.py                    # Phase 1A: ProjectState, subgraph dataclasses
    session_graph.py             # Phase 1A: build SessionGraph from get_session_info
    arrangement_graph.py         # Phase 1A: build ArrangementGraph from clips/sections
    role_graph.py                # Phase 1A: build RoleGraph (reuse _composition_engine)
    automation_graph.py          # Phase 1A: build AutomationGraph
    builder.py                   # Phase 1A: orchestrate full build pipeline
    freshness.py                 # Phase 1A: freshness/confidence tracking
    tools.py                     # Phase 1A: MCP tool wrappers

  runtime/
    __init__.py                  # Phase 1B
    capability_state.py          # Phase 1B: CapabilityDomain model + builder
    capability_checks.py         # Phase 1B: probe functions for each domain
    tools.py                     # Phase 1B: MCP tool wrapper (get_capability_state)
    action_ledger.py             # Phase 1C: SessionLedger, LedgerEntry, UndoGroup
    action_ledger_models.py      # Phase 1C: data models
    action_tools.py              # Phase 1C: MCP tool wrappers

  evaluation/
    __init__.py                  # Phase 1D
    contracts.py                 # Phase 1D: EvaluationRequest, EvaluationResult
    snapshot_normalizer.py       # Phase 1D: consolidate from Phase 0
    feature_extractors.py        # Phase 1D: dimension → value extraction
    policy.py                    # Phase 1D: hard rules, keep/undo logic
    composition_evaluator.py     # Phase 1D: composition-specific scoring
    tools.py                     # Phase 1D: MCP tool wrappers

  memory/
    fabric.py                    # Phase 1E: MemoryFabric class (extends existing)
    anti_memory.py               # Phase 1E: AntiMemory tracking
    promotion.py                 # Phase 1E: ledger → memory promotion rules
    tools.py                     # Phase 1E: new MCP tools

  mix_engine/
    __init__.py                  # Phase 2A
    models.py                    # Phase 2A: BalanceState, MaskingMap, etc.
    state_builder.py             # Phase 2A: build mix state from session
    critics.py                   # Phase 2A: 6 mix critics
    planner.py                   # Phase 2A: move ranking + selection
    evaluator.py                 # Phase 2A: mix-specific evaluation
    tools.py                     # Phase 2A: MCP tool wrappers

tests/
  test_snapshot_normalizer.py    # Phase 0
  test_evaluation_contracts.py   # Phase 0
  test_project_brain.py          # Phase 1A
  test_capability_state.py       # Phase 1B
  test_action_ledger.py          # Phase 1C
  test_evaluation_fabric.py      # Phase 1D
  test_memory_fabric_v2.py       # Phase 1E
  test_mix_engine.py             # Phase 2A
```

---

## Chunk 1: Phase 0 — Agent OS Hardening

**Goal:** Fix 5 known issues in the evaluation/world-model loop before building new engines on top.

**Spec:** AGENT_OS_PHASE0_HARDENING_PLAN.md

**What's already fixed (Rounds 1-4):**
- Issue A (protection override): Fixed — `protection_violated` now checked before unmeasurable fallback
- Issue E (crest factor): Fixed — uses `20*log10(peak/rms)` correctly
- Snapshot normalization: Partially fixed — `_extract_dimension_value` accepts both `spectrum` and `bands` keys

**What still needs fixing:**
- Issue C: `width` is NOT in MEASURABLE_PROXIES but the prompt/docs may imply it is
- Issue D: `build_world_model` in agent_os.py doesn't fetch device health unless `track_infos` passed
- Snapshot normalizer should be a standalone reusable module (not inline in evaluator)
- Evaluation contracts should be formalized for future engines

### Task 0.1: Snapshot Normalizer Module

**Files:**
- Create: `mcp_server/tools/_snapshot_normalizer.py`
- Test: `tests/test_snapshot_normalizer.py`

- [ ] **Step 1: Write failing test for spectrum normalization**

```python
# tests/test_snapshot_normalizer.py
"""Tests for snapshot normalizer — canonical input normalization."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._snapshot_normalizer import normalize_sonic_snapshot


class TestNormalizeSonicSnapshot:
    def test_accepts_bands_key(self):
        raw = {"bands": {"sub": 0.1, "low": 0.2}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw)
        assert result["spectrum"]["sub"] == 0.1
        assert result["rms"] == 0.5

    def test_accepts_spectrum_key(self):
        raw = {"spectrum": {"sub": 0.1}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw)
        assert result["spectrum"]["sub"] == 0.1

    def test_none_input(self):
        result = normalize_sonic_snapshot(None)
        assert result is None

    def test_empty_input(self):
        result = normalize_sonic_snapshot({})
        assert result is None

    def test_adds_source_metadata(self):
        raw = {"bands": {"sub": 0.1}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw, source="analyzer")
        assert result["source"] == "analyzer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_snapshot_normalizer.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement normalizer**

```python
# mcp_server/tools/_snapshot_normalizer.py
"""Snapshot Normalizer — canonical input normalization for all evaluators.

Ensures analyzer outputs are in a consistent schema regardless of
which tool produced them. All evaluators should consume normalized
snapshots, never raw tool outputs.

Design: AGENT_OS_PHASE0_HARDENING_PLAN.md, section 3.2
"""
from __future__ import annotations
from typing import Optional
import time


def normalize_sonic_snapshot(
    raw: Optional[dict],
    source: str = "unknown",
) -> Optional[dict]:
    """Normalize a raw analyzer/perception output into canonical snapshot form.

    Accepts both {"bands": {...}} and {"spectrum": {...}} shapes.
    Returns None if input is empty or None.

    Canonical form:
    {
        "spectrum": {band: value, ...},
        "rms": float or None,
        "peak": float or None,
        "detected_key": str or None,
        "source": str,
        "normalized_at_ms": int,
    }
    """
    if not raw or not isinstance(raw, dict):
        return None

    bands = raw.get("spectrum") or raw.get("bands")
    if not bands:
        return None

    return {
        "spectrum": bands,
        "rms": raw.get("rms"),
        "peak": raw.get("peak"),
        "detected_key": raw.get("key") or raw.get("detected_key"),
        "source": source,
        "normalized_at_ms": int(time.time() * 1000),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_snapshot_normalizer.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tools/_snapshot_normalizer.py tests/test_snapshot_normalizer.py
git commit -m "feat(phase0): add snapshot normalizer module"
```

### Task 0.2: Evaluation Contracts Module

**Files:**
- Create: `mcp_server/tools/_evaluation_contracts.py`
- Test: `tests/test_evaluation_contracts.py`

- [ ] **Step 1: Write failing test for evaluation contracts**

```python
# tests/test_evaluation_contracts.py
"""Tests for shared evaluation contract types."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._evaluation_contracts import (
    EvaluationRequest,
    EvaluationResult,
    MEASURABLE_DIMENSIONS,
    is_dimension_measurable,
)


class TestMeasurableDimensions:
    def test_brightness_is_measurable(self):
        assert is_dimension_measurable("brightness")

    def test_width_is_not_measurable(self):
        assert not is_dimension_measurable("width")

    def test_groove_is_not_measurable(self):
        assert not is_dimension_measurable("groove")

    def test_energy_is_measurable(self):
        assert is_dimension_measurable("energy")


class TestEvaluationRequest:
    def test_creates_valid_request(self):
        req = EvaluationRequest(
            engine="mix",
            goal={"targets": {"clarity": 0.5}},
            before={"spectrum": {"sub": 0.1}},
            after={"spectrum": {"sub": 0.2}},
        )
        assert req.engine == "mix"

    def test_to_dict(self):
        req = EvaluationRequest(engine="composition", goal={}, before={}, after={})
        d = req.to_dict()
        assert d["engine"] == "composition"


class TestEvaluationResult:
    def test_creates_valid_result(self):
        res = EvaluationResult(
            engine="mix", score=0.7, keep_change=True,
            goal_progress=0.5, collateral_damage=0.1,
        )
        assert res.keep_change is True

    def test_to_dict(self):
        res = EvaluationResult(engine="mix", score=0.5, keep_change=False)
        d = res.to_dict()
        assert d["score"] == 0.5
        assert d["keep_change"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_evaluation_contracts.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement evaluation contracts**

```python
# mcp_server/tools/_evaluation_contracts.py
"""Evaluation Contracts — shared types for all engine evaluators.

Defines the canonical evaluation request/result types and the
authoritative registry of which quality dimensions are measurable.

Design: EVALUATION_FABRIC_V1.md, section 6
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# Authoritative registry: dimensions with working spectral proxies.
# If it's not here, it's unmeasurable in current phase and the evaluator
# must report confidence=0.0 for that dimension.
MEASURABLE_DIMENSIONS: frozenset[str] = frozenset({
    "brightness", "warmth", "weight", "clarity",
    "density", "energy", "punch",
})

# All valid quality dimensions (measurable + unmeasurable).
ALL_DIMENSIONS: frozenset[str] = frozenset({
    "energy", "punch", "weight", "density", "brightness", "warmth",
    "width", "depth", "motion", "contrast", "clarity", "cohesion",
    "groove", "tension", "novelty", "polish", "emotion",
})


def is_dimension_measurable(dim: str) -> bool:
    """Check if a dimension has a working spectral proxy."""
    return dim in MEASURABLE_DIMENSIONS


@dataclass
class EvaluationRequest:
    """Canonical evaluation request — engine-agnostic."""
    engine: str
    goal: dict = field(default_factory=dict)
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    protect: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    """Canonical evaluation result — all engines produce this shape."""
    engine: str
    score: float = 0.0
    keep_change: bool = True
    goal_progress: float = 0.0
    collateral_damage: float = 0.0
    hard_rule_failures: list[str] = field(default_factory=list)
    dimension_changes: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    decision_mode: str = "measured"  # measured, judgment, deferred
    memory_candidate: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_evaluation_contracts.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tools/_evaluation_contracts.py tests/test_evaluation_contracts.py
git commit -m "feat(phase0): add evaluation contracts module"
```

### Task 0.3: Wire normalizer into existing evaluator

**Files:**
- Modify: `mcp_server/tools/agent_os.py` (the `evaluate_move` tool)
- Modify: `mcp_server/tools/_agent_os_engine.py` (import contracts)

- [ ] **Step 1: Add test that evaluate_move normalizes snapshots**

Add to `tests/test_agent_os_engine.py`:

```python
class TestSnapshotNormalization:
    def test_evaluator_accepts_bands_key_directly(self):
        """Regression: raw analyzer output with 'bands' key should work."""
        from mcp_server.tools._agent_os_engine import compute_evaluation_score, validate_goal_vector
        goal = validate_goal_vector("test", {"energy": 1.0}, {}, "improve", 0.5, "none")
        before = {"bands": {"sub": 0.1, "low": 0.2, "low_mid": 0.3,
                            "mid": 0.2, "presence": 0.1, "high": 0.1}, "rms": 0.3, "peak": 0.5}
        after = {"bands": {"sub": 0.15, "low": 0.25, "low_mid": 0.3,
                           "mid": 0.2, "presence": 0.1, "high": 0.1}, "rms": 0.4, "peak": 0.6}
        result = compute_evaluation_score(goal, before, after)
        assert result["measurable_dimensions"] > 0
```

- [ ] **Step 2: Run to verify it passes (existing fix)**

Run: `python3 -m pytest tests/test_agent_os_engine.py::TestSnapshotNormalization -v`
Expected: PASS (already working due to Round 1 fix)

- [ ] **Step 3: Commit**

```bash
git add tests/test_agent_os_engine.py
git commit -m "test(phase0): add regression test for snapshot normalization"
```

### Task 0.4: Verify world model honesty

**Files:**
- Modify: `mcp_server/tools/agent_os.py` (build_world_model tool)

- [ ] **Step 1: Read current build_world_model implementation**

Check: `mcp_server/tools/agent_os.py` — the `build_world_model` tool
Verify: Does it actually fetch device health? Or does it only use data if `track_infos` is provided by the caller?

- [ ] **Step 2: Add test for world model without track infos**

```python
class TestWorldModelHonesty:
    def test_no_unhealthy_devices_when_no_track_infos(self):
        """World model should not claim device health when no track data fetched."""
        from mcp_server.tools._agent_os_engine import build_world_model_from_data
        wm = build_world_model_from_data(
            {"tracks": [{"index": 0, "name": "Kick"}], "tempo": 120},
            track_infos=None,
        )
        assert wm.technical["unhealthy_devices"] == []
```

- [ ] **Step 3: Run test**

Run: `python3 -m pytest tests/test_agent_os_engine.py::TestWorldModelHonesty -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_agent_os_engine.py
git commit -m "test(phase0): verify world model honesty without track data"
```

### Phase 0 Exit Criteria

Run: `python3 -m pytest tests/test_snapshot_normalizer.py tests/test_evaluation_contracts.py tests/test_agent_os_engine.py -v`
Expected: All pass

```bash
git tag phase0-hardening-complete
```

---

## Chunk 2: Phase 1A — Project Brain

**Goal:** Single canonical project state object that all engines read from instead of each rebuilding partial state.

**Spec:** PROJECT_BRAIN_V1.md

**Key decision:** The spec suggests `mcp_server/project_brain/` as a package. We follow this — it's the first engine big enough to warrant its own package.

### Task 1A.1: Project Brain Models

**Files:**
- Create: `mcp_server/project_brain/__init__.py`
- Create: `mcp_server/project_brain/models.py`
- Test: `tests/test_project_brain.py`

- [ ] **Step 1: Write failing tests for core models**

```python
# tests/test_project_brain.py
"""Tests for Project Brain — shared state substrate."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.project_brain.models import (
    ProjectState, SessionGraph, ArrangementGraph,
    RoleGraph, AutomationGraph, CapabilityGraph,
    FreshnessInfo, ConfidenceInfo,
    TrackNode, SectionNode, RoleNode,
)


class TestProjectState:
    def test_creates_empty_state(self):
        ps = ProjectState()
        assert ps.revision == 0
        assert ps.session_graph is not None
        assert ps.arrangement_graph is not None

    def test_to_dict(self):
        ps = ProjectState()
        d = ps.to_dict()
        assert "session_graph" in d
        assert "revision" in d

    def test_is_stale_when_no_data(self):
        ps = ProjectState()
        assert ps.is_stale()


class TestFreshnessInfo:
    def test_fresh_by_default(self):
        fi = FreshnessInfo()
        assert fi.stale is True  # stale until built

    def test_mark_fresh(self):
        fi = FreshnessInfo()
        fi.mark_fresh(source_revision=1)
        assert fi.stale is False


class TestSessionGraph:
    def test_adds_track(self):
        sg = SessionGraph()
        sg.add_track(TrackNode(index=0, name="Kick"))
        assert len(sg.tracks) == 1


class TestRoleGraph:
    def test_adds_role(self):
        rg = RoleGraph()
        rg.add_role(RoleNode(track_index=0, section_id="sec_00",
                             role="kick_anchor", confidence=0.9))
        assert len(rg.roles) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_project_brain.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement models**

```python
# mcp_server/project_brain/__init__.py
"""Project Brain — shared state substrate for all LivePilot engines."""

# mcp_server/project_brain/models.py
"""Project Brain data models — subgraphs and state container."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Optional
import time


@dataclass
class FreshnessInfo:
    """Tracks when a subgraph was built and whether it's stale."""
    built_at_ms: int = 0
    source_revision: int = 0
    stale: bool = True
    stale_reason: Optional[str] = "not yet built"

    def mark_fresh(self, source_revision: int = 0):
        self.built_at_ms = int(time.time() * 1000)
        self.source_revision = source_revision
        self.stale = False
        self.stale_reason = None

    def mark_stale(self, reason: str = "external mutation"):
        self.stale = True
        self.stale_reason = reason

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfidenceInfo:
    """Confidence summary for an inference-bearing graph."""
    overall: float = 0.0
    low_confidence_nodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Session Graph ────────────────────────────────────────────────

@dataclass
class TrackNode:
    index: int
    name: str = ""
    has_midi: bool = False
    has_audio: bool = False
    mute: bool = False
    solo: bool = False
    arm: bool = False
    group_index: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionGraph:
    tracks: list[TrackNode] = field(default_factory=list)
    return_tracks: list[dict] = field(default_factory=list)
    scenes: list[dict] = field(default_factory=list)
    tempo: float = 120.0
    time_signature: str = "4/4"
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def add_track(self, track: TrackNode):
        self.tracks.append(track)

    def to_dict(self) -> dict:
        return {
            "tracks": [t.to_dict() for t in self.tracks],
            "return_tracks": self.return_tracks,
            "scenes": self.scenes,
            "tempo": self.tempo,
            "time_signature": self.time_signature,
            "freshness": self.freshness.to_dict(),
        }


# ── Arrangement Graph ────────────────────────────────────────────

@dataclass
class SectionNode:
    section_id: str = ""
    start_bar: int = 0
    end_bar: int = 0
    section_type: str = "unknown"
    energy: float = 0.0
    density: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArrangementGraph:
    sections: list[SectionNode] = field(default_factory=list)
    boundaries: list[dict] = field(default_factory=list)
    cue_points: list[dict] = field(default_factory=list)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def to_dict(self) -> dict:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "boundaries": self.boundaries,
            "cue_points": self.cue_points,
            "freshness": self.freshness.to_dict(),
        }


# ── Role Graph ───────────────────────────────────────────────────

@dataclass
class RoleNode:
    track_index: int = 0
    section_id: str = ""
    role: str = "unknown"
    confidence: float = 0.0
    foreground: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoleGraph:
    roles: list[RoleNode] = field(default_factory=list)
    confidence: ConfidenceInfo = field(default_factory=ConfidenceInfo)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def add_role(self, role: RoleNode):
        self.roles.append(role)

    def to_dict(self) -> dict:
        return {
            "roles": [r.to_dict() for r in self.roles],
            "confidence": self.confidence.to_dict(),
            "freshness": self.freshness.to_dict(),
        }


# ── Automation Graph ─────────────────────────────────────────────

@dataclass
class AutomationGraph:
    automated_params: list[dict] = field(default_factory=list)
    density_by_section: dict[str, float] = field(default_factory=dict)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def to_dict(self) -> dict:
        return {
            "automated_params": self.automated_params,
            "density_by_section": self.density_by_section,
            "freshness": self.freshness.to_dict(),
        }


# ── Capability Graph ─────────────────────────────────────────────

@dataclass
class CapabilityGraph:
    analyzer_available: bool = False
    flucoma_available: bool = False
    plugin_health: list[dict] = field(default_factory=list)
    research_providers: list[str] = field(default_factory=list)
    freshness: FreshnessInfo = field(default_factory=FreshnessInfo)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Project State Container ──────────────────────────────────────

@dataclass
class ProjectState:
    """Canonical project state — the one object all engines read from."""
    project_id: str = "current"
    revision: int = 0
    session_graph: SessionGraph = field(default_factory=SessionGraph)
    arrangement_graph: ArrangementGraph = field(default_factory=ArrangementGraph)
    role_graph: RoleGraph = field(default_factory=RoleGraph)
    automation_graph: AutomationGraph = field(default_factory=AutomationGraph)
    capability_graph: CapabilityGraph = field(default_factory=CapabilityGraph)
    active_issues: list[dict] = field(default_factory=list)

    def is_stale(self) -> bool:
        return (
            self.session_graph.freshness.stale
            or self.arrangement_graph.freshness.stale
        )

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "revision": self.revision,
            "session_graph": self.session_graph.to_dict(),
            "arrangement_graph": self.arrangement_graph.to_dict(),
            "role_graph": self.role_graph.to_dict(),
            "automation_graph": self.automation_graph.to_dict(),
            "capability_graph": self.capability_graph.to_dict(),
            "active_issues": self.active_issues,
            "stale": self.is_stale(),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_project_brain.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add mcp_server/project_brain/ tests/test_project_brain.py
git commit -m "feat(phase1a): add Project Brain models"
```

### Task 1A.2: Project Brain Builder

**Files:**
- Create: `mcp_server/project_brain/builder.py`
- Create: `mcp_server/project_brain/session_graph.py`
- Extend: `tests/test_project_brain.py`

- [ ] **Step 1: Write failing test for session graph builder**

Add to `tests/test_project_brain.py`:

```python
from mcp_server.project_brain.session_graph import build_session_graph


class TestSessionGraphBuilder:
    def test_builds_from_session_info(self):
        session_info = {
            "tempo": 128.0,
            "signature_numerator": 4,
            "signature_denominator": 4,
            "tracks": [
                {"index": 0, "name": "Kick", "has_midi_input": True},
                {"index": 1, "name": "Bass", "has_midi_input": True},
            ],
            "scenes": [{"index": 0, "name": "Intro"}],
            "return_track_count": 2,
        }
        sg = build_session_graph(session_info)
        assert len(sg.tracks) == 2
        assert sg.tempo == 128.0
        assert sg.freshness.stale is False

    def test_empty_session(self):
        sg = build_session_graph({"tracks": [], "scenes": []})
        assert len(sg.tracks) == 0
        assert sg.freshness.stale is False
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement session_graph.py**

```python
# mcp_server/project_brain/session_graph.py
"""Build SessionGraph from get_session_info output."""
from __future__ import annotations
from .models import SessionGraph, TrackNode


def build_session_graph(session_info: dict) -> SessionGraph:
    """Build a SessionGraph from raw get_session_info output."""
    sg = SessionGraph()
    sg.tempo = session_info.get("tempo", 120.0)
    num = session_info.get("signature_numerator", 4)
    den = session_info.get("signature_denominator", 4)
    sg.time_signature = f"{num}/{den}"
    sg.scenes = session_info.get("scenes", [])

    for t in session_info.get("tracks", []):
        sg.add_track(TrackNode(
            index=t.get("index", 0),
            name=t.get("name", ""),
            has_midi=t.get("has_midi_input", False),
            has_audio=t.get("has_audio_input", False),
            mute=t.get("mute", False),
            solo=t.get("solo", False),
            arm=t.get("arm", False),
        ))

    sg.freshness.mark_fresh(source_revision=0)
    return sg
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add mcp_server/project_brain/session_graph.py tests/test_project_brain.py
git commit -m "feat(phase1a): add session graph builder"
```

### Task 1A.3: Full Brain Builder + MCP Tools

**Files:**
- Create: `mcp_server/project_brain/builder.py`
- Create: `mcp_server/project_brain/tools.py`
- Modify: `mcp_server/server.py` (register tools)
- Extend: `tests/test_project_brain.py`
- Modify: `tests/test_tools_contract.py`

- [ ] **Step 1: Write test for full brain build**

```python
from mcp_server.project_brain.builder import build_project_state_from_data


class TestBrainBuilder:
    def test_builds_full_state(self):
        session = {"tempo": 120, "tracks": [{"index": 0, "name": "Kick"}], "scenes": []}
        ps = build_project_state_from_data(session_info=session)
        assert ps.revision == 1
        assert not ps.session_graph.freshness.stale

    def test_increments_revision(self):
        session = {"tempo": 120, "tracks": [], "scenes": []}
        ps1 = build_project_state_from_data(session_info=session)
        ps2 = build_project_state_from_data(session_info=session, previous_revision=ps1.revision)
        assert ps2.revision == 2
```

- [ ] **Step 2: Implement builder.py**

```python
# mcp_server/project_brain/builder.py
"""Orchestrate full Project Brain build pipeline."""
from __future__ import annotations
from typing import Optional
from .models import ProjectState
from .session_graph import build_session_graph


def build_project_state_from_data(
    session_info: dict,
    arrangement_clips: Optional[dict] = None,
    track_infos: Optional[list] = None,
    previous_revision: int = 0,
) -> ProjectState:
    """Build a complete ProjectState from raw tool outputs."""
    ps = ProjectState()
    ps.revision = previous_revision + 1

    # 1. Session graph (always available)
    ps.session_graph = build_session_graph(session_info)

    # 2-5. Other graphs built incrementally as data available
    # (Phase 1A starts with session graph; arrangement/role/automation
    #  builders added in Tasks 1A.4+)

    return ps
```

- [ ] **Step 3: Create MCP tool wrapper**

```python
# mcp_server/project_brain/tools.py
"""Project Brain MCP tools."""
from __future__ import annotations
from fastmcp import Context
from ..server import mcp
from . import builder


@mcp.tool()
def build_project_brain(ctx: Context) -> dict:
    """Build or refresh the canonical project state snapshot.

    Creates a ProjectState with session topology, arrangement structure,
    role assignments, automation map, and capability status.
    All other engines should read from this instead of rebuilding state.

    Returns: full ProjectState with freshness and confidence metadata.
    """
    ableton = ctx.lifespan_context["ableton"]
    session = ableton.send_command("get_session_info")
    ps = builder.build_project_state_from_data(session_info=session)
    return ps.to_dict()


@mcp.tool()
def get_project_brain_summary(ctx: Context) -> dict:
    """Get a lightweight summary of the current project state.

    Returns: track count, section count, role summary, staleness status.
    """
    ableton = ctx.lifespan_context["ableton"]
    session = ableton.send_command("get_session_info")
    ps = builder.build_project_state_from_data(session_info=session)
    return {
        "track_count": len(ps.session_graph.tracks),
        "section_count": len(ps.arrangement_graph.sections),
        "role_count": len(ps.role_graph.roles),
        "stale": ps.is_stale(),
        "revision": ps.revision,
    }
```

- [ ] **Step 4: Register in server.py**

Add to `mcp_server/server.py` after the planner import:
```python
from .project_brain import tools as project_brain_tools  # noqa: F401, E402
```

- [ ] **Step 5: Update contract test + tool count**

Update `tests/test_tools_contract.py`:
- Add `test_project_brain_tools_registered` checking for `build_project_brain`, `get_project_brain_summary`
- Update total tool count assertion

- [ ] **Step 6: Run all tests**

Run: `python3 -m pytest tests/test_project_brain.py tests/test_tools_contract.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add mcp_server/project_brain/ mcp_server/server.py tests/
git commit -m "feat(phase1a): Project Brain builder + MCP tools"
```

### Phase 1A Exit Criteria

- `ProjectState` exists with 5 subgraphs
- `build_project_brain` and `get_project_brain_summary` MCP tools work
- Freshness tracking works
- All tests pass

```bash
git tag phase1a-project-brain-complete
```

---

## Chunk 3: Phase 1B — Capability State

**Goal:** Unified runtime capability model — what can/can't be trusted right now.

**Spec:** CAPABILITY_STATE_V1.md

### Task 1B.1: Capability State Models + Builder

**Files:**
- Create: `mcp_server/runtime/__init__.py`
- Create: `mcp_server/runtime/capability_state.py`
- Create: `mcp_server/runtime/capability_checks.py`
- Create: `mcp_server/runtime/tools.py`
- Test: `tests/test_capability_state.py`
- Modify: `mcp_server/server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_capability_state.py
"""Tests for Capability State — runtime capability model."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.capability_state import (
    CapabilityDomain, CapabilityState, build_capability_state,
)


class TestCapabilityDomain:
    def test_healthy_domain(self):
        d = CapabilityDomain(name="analyzer", available=True, confidence=0.9)
        assert d.available
        assert d.mode == "normal"

    def test_degraded_domain(self):
        d = CapabilityDomain(name="analyzer", available=False, confidence=0.0,
                             mode="unavailable", reasons=["bridge_offline"])
        assert not d.available
        assert "bridge_offline" in d.reasons


class TestCapabilityState:
    def test_builds_from_probes(self):
        cs = build_capability_state(
            session_ok=True,
            analyzer_ok=True,
            analyzer_fresh=True,
            memory_ok=True,
            web_ok=False,
        )
        assert cs.domains["session_access"].available
        assert cs.domains["analyzer"].available
        assert not cs.domains["web"].available
        assert cs.overall_mode in ("normal", "measured_degraded")

    def test_degraded_mode_without_analyzer(self):
        cs = build_capability_state(
            session_ok=True, analyzer_ok=False, analyzer_fresh=False,
            memory_ok=True, web_ok=False,
        )
        assert cs.overall_mode == "measured_degraded"

    def test_to_dict(self):
        cs = build_capability_state(session_ok=True)
        d = cs.to_dict()
        assert "overall_mode" in d
        assert "domains" in d

    def test_can_use_measured_evaluation(self):
        cs = build_capability_state(session_ok=True, analyzer_ok=True, analyzer_fresh=True)
        assert cs.can_use_measured_evaluation()

    def test_cannot_use_measured_without_analyzer(self):
        cs = build_capability_state(session_ok=True, analyzer_ok=False)
        assert not cs.can_use_measured_evaluation()
```

- [ ] **Step 2: Run to verify failure**
- [ ] **Step 3: Implement capability_state.py**

```python
# mcp_server/runtime/__init__.py
"""Runtime subsystem — capability state, action ledger."""

# mcp_server/runtime/capability_state.py
"""Capability State — what can/can't be trusted right now."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Optional
import time


@dataclass
class CapabilityDomain:
    name: str
    available: bool = False
    confidence: float = 0.0
    freshness_ms: Optional[int] = None
    mode: str = "normal"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CapabilityState:
    generated_at_ms: int = 0
    overall_mode: str = "normal"
    domains: dict[str, CapabilityDomain] = field(default_factory=dict)

    def can_use_measured_evaluation(self) -> bool:
        analyzer = self.domains.get("analyzer")
        return analyzer is not None and analyzer.available and analyzer.confidence > 0.5

    def can_run_research(self, mode: str = "targeted") -> bool:
        if mode == "deep":
            web = self.domains.get("web")
            return web is not None and web.available
        return True  # targeted always works with local sources

    def to_dict(self) -> dict:
        return {
            "generated_at_ms": self.generated_at_ms,
            "overall_mode": self.overall_mode,
            "domains": {k: v.to_dict() for k, v in self.domains.items()},
        }


def build_capability_state(
    session_ok: bool = False,
    analyzer_ok: bool = False,
    analyzer_fresh: bool = False,
    memory_ok: bool = True,
    web_ok: bool = False,
    flucoma_ok: bool = False,
) -> CapabilityState:
    """Build capability state from probe results."""
    cs = CapabilityState(generated_at_ms=int(time.time() * 1000))

    cs.domains["session_access"] = CapabilityDomain(
        name="session_access", available=session_ok,
        confidence=0.95 if session_ok else 0.0,
        mode="normal" if session_ok else "unavailable",
    )
    cs.domains["analyzer"] = CapabilityDomain(
        name="analyzer", available=analyzer_ok and analyzer_fresh,
        confidence=0.9 if (analyzer_ok and analyzer_fresh) else 0.0,
        mode="measured" if analyzer_ok else "unavailable",
        reasons=[] if analyzer_ok else ["analyzer_offline"],
    )
    cs.domains["memory"] = CapabilityDomain(
        name="memory", available=memory_ok,
        confidence=0.8 if memory_ok else 0.0,
    )
    cs.domains["web"] = CapabilityDomain(
        name="web", available=web_ok,
        confidence=0.6 if web_ok else 0.0,
        mode="normal" if web_ok else "unavailable",
        reasons=[] if web_ok else ["web_unavailable"],
    )
    cs.domains["research"] = CapabilityDomain(
        name="research", available=True,  # always available at local level
        confidence=0.7 if memory_ok else 0.4,
        mode="targeted_only" if not web_ok else "full",
    )

    # Determine overall mode
    if session_ok and analyzer_ok and analyzer_fresh:
        cs.overall_mode = "normal"
    elif session_ok and not analyzer_ok:
        cs.overall_mode = "measured_degraded"
    elif session_ok:
        cs.overall_mode = "judgment_only"
    else:
        cs.overall_mode = "read_only"

    return cs
```

- [ ] **Step 4: Run tests**
- [ ] **Step 5: Add MCP tool + register in server**

```python
# mcp_server/runtime/tools.py
"""Runtime MCP tools — capability state."""
from __future__ import annotations
from fastmcp import Context
from ..server import mcp
from .capability_state import build_capability_state


@mcp.tool()
def get_capability_state(ctx: Context) -> dict:
    """Get current runtime capability state — what can/can't be trusted.

    Probes analyzer, session, memory, and research availability.
    Returns operating mode and per-domain status.
    Use before planning moves to know what evidence is available.
    """
    ableton = ctx.lifespan_context["ableton"]

    session_ok = False
    analyzer_ok = False
    analyzer_fresh = False
    memory_ok = True

    try:
        ableton.send_command("get_session_info")
        session_ok = True
    except Exception:
        pass

    try:
        spec = ableton.send_command("get_master_spectrum")
        analyzer_ok = bool(spec and spec.get("bands"))
        analyzer_fresh = analyzer_ok  # If we just got it, it's fresh
    except Exception:
        pass

    cs = build_capability_state(
        session_ok=session_ok,
        analyzer_ok=analyzer_ok,
        analyzer_fresh=analyzer_fresh,
        memory_ok=memory_ok,
    )
    return cs.to_dict()
```

Register in server.py:
```python
from .runtime import tools as runtime_tools  # noqa: F401, E402
```

- [ ] **Step 6: Commit**

```bash
git add mcp_server/runtime/ tests/test_capability_state.py mcp_server/server.py
git commit -m "feat(phase1b): Capability State module + MCP tool"
```

---

## Chunk 4: Phase 1C — Action Ledger

**Goal:** Durable per-session record of semantic moves for debugging, undo, and memory promotion.

**Spec:** ACTION_LEDGER_V1.md

### Task 1C.1: Action Ledger Models + Store

**Files:**
- Create: `mcp_server/runtime/action_ledger.py`
- Create: `mcp_server/runtime/action_ledger_models.py`
- Test: `tests/test_action_ledger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_action_ledger.py
"""Tests for Action Ledger — semantic move tracking."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.action_ledger_models import LedgerEntry, UndoGroup
from mcp_server.runtime.action_ledger import SessionLedger


class TestLedgerEntry:
    def test_creates_entry(self):
        entry = LedgerEntry(
            engine="composition",
            move_class="transition_gesture",
            intent="make the drop feel earned",
        )
        assert entry.engine == "composition"
        assert entry.id.startswith("move_")

    def test_to_dict(self):
        entry = LedgerEntry(engine="mix", move_class="eq_correction", intent="reduce mud")
        d = entry.to_dict()
        assert d["engine"] == "mix"


class TestSessionLedger:
    def test_start_and_finalize_move(self):
        ledger = SessionLedger()
        entry_id = ledger.start_move("composition", "section_expand", "make verse longer")
        ledger.append_action(entry_id, "create_clip", "created clip at bar 16")
        ledger.finalize_move(entry_id, kept=True, score=0.7)

        entry = ledger.get_entry(entry_id)
        assert entry.kept is True
        assert len(entry.actions) == 1

    def test_get_recent_moves(self):
        ledger = SessionLedger()
        id1 = ledger.start_move("mix", "eq", "fix mud")
        ledger.finalize_move(id1, kept=True)
        id2 = ledger.start_move("composition", "gesture", "add reveal")
        ledger.finalize_move(id2, kept=False)

        recent = ledger.get_recent_moves(limit=10)
        assert len(recent) == 2

    def test_filter_by_engine(self):
        ledger = SessionLedger()
        id1 = ledger.start_move("mix", "eq", "fix")
        ledger.finalize_move(id1, kept=True)
        id2 = ledger.start_move("composition", "gesture", "add")
        ledger.finalize_move(id2, kept=True)

        mix_moves = ledger.get_recent_moves(engine="mix")
        assert len(mix_moves) == 1

    def test_memory_candidates(self):
        ledger = SessionLedger()
        id1 = ledger.start_move("mix", "eq", "fix mud")
        ledger.finalize_move(id1, kept=True, score=0.8, memory_candidate=True)

        candidates = ledger.get_memory_candidates()
        assert len(candidates) == 1

    def test_undo_group(self):
        ledger = SessionLedger()
        id1 = ledger.start_move("mix", "eq", "fix", undo_scope="mix")
        ledger.finalize_move(id1, kept=True)
        id2 = ledger.start_move("mix", "comp", "glue", undo_scope="mix")
        ledger.finalize_move(id2, kept=True)

        groups = ledger.get_undo_groups()
        assert any(g.scope == "mix" for g in groups)
```

- [ ] **Step 2-5: Implement, test, commit** (same TDD pattern)

- [ ] **Step 6: Add MCP tools**

Tools to add: `get_action_ledger_summary`, `get_last_move`

- [ ] **Step 7: Commit**

```bash
git add mcp_server/runtime/action_ledger*.py tests/test_action_ledger.py
git commit -m "feat(phase1c): Action Ledger module + MCP tools"
```

---

## Chunk 5: Phase 1D — Evaluation Fabric

**Goal:** Unified evaluation layer that all engines use instead of custom scoring logic.

**Spec:** EVALUATION_FABRIC_V1.md

### Task 1D.1: Evaluation Fabric Core

**Files:**
- Create: `mcp_server/evaluation/__init__.py`
- Create: `mcp_server/evaluation/contracts.py` (move from Phase 0)
- Create: `mcp_server/evaluation/snapshot_normalizer.py` (move from Phase 0)
- Create: `mcp_server/evaluation/feature_extractors.py`
- Create: `mcp_server/evaluation/policy.py`
- Create: `mcp_server/evaluation/composition_evaluator.py`
- Create: `mcp_server/evaluation/tools.py`
- Test: `tests/test_evaluation_fabric.py`

This phase refactors the existing evaluators into the fabric pattern. Key steps:

- [ ] **Step 1:** Extract feature extraction from `_agent_os_engine._extract_dimension_value` into `evaluation/feature_extractors.py`
- [ ] **Step 2:** Extract hard-rule policy from `compute_evaluation_score` into `evaluation/policy.py`
- [ ] **Step 3:** Create `evaluate_with_fabric(request: EvaluationRequest) -> EvaluationResult` as the unified entry point
- [ ] **Step 4:** Wire existing `evaluate_move` MCP tool to use the fabric internally
- [ ] **Step 5:** Add `evaluate_composition_with_fabric` for composition-specific scoring
- [ ] **Step 6:** Tests covering all evaluator paths
- [ ] **Step 7:** Commit

```bash
git commit -m "feat(phase1d): Evaluation Fabric — unified evaluation layer"
```

---

## Chunk 6: Phase 1E — Memory Fabric V2

**Goal:** Evolve memory beyond technique-only storage to include session memory, anti-memory, and promotion rules.

**Spec:** MEMORY_FABRIC_V2.md

### Task 1E.1: Memory Fabric Extensions

**Files:**
- Create: `mcp_server/memory/fabric.py`
- Create: `mcp_server/memory/anti_memory.py`
- Create: `mcp_server/memory/promotion.py`
- Test: `tests/test_memory_fabric_v2.py`

Key additions:
- `AntiMemory` — tracks what the user dislikes (undone moves, explicit negatives)
- `PromotionRule` — when should a ledger entry become a permanent memory?
- New memory types: `anti_preference`, `session_outcome`

- [ ] **Steps 1-6:** TDD cycle for anti-memory, promotion rules, new memory types
- [ ] **Step 7:** Add MCP tools: `get_anti_preferences`, `promote_outcome_to_memory`, `get_session_memory`
- [ ] **Step 8:** Commit

```bash
git commit -m "feat(phase1e): Memory Fabric V2 — anti-memory, promotion, session memory"
```

---

## Chunk 7: Phase 2A — Mix Engine V1

**Goal:** First domain engine — dedicated mixing intelligence with balance, masking, dynamics, stereo, and depth analysis.

**Spec:** MIX_ENGINE_V1.md

### Task 2A.1: Mix Engine Models

**Files:**
- Create: `mcp_server/mix_engine/__init__.py`
- Create: `mcp_server/mix_engine/models.py`
- Test: `tests/test_mix_engine.py`

Data structures: `BalanceState`, `MaskingMap`, `DynamicsState`, `StereoState`, `DepthState`, `MixHypothesis`

### Task 2A.2: Mix State Builder

**Files:**
- Create: `mcp_server/mix_engine/state_builder.py`

Builds mix state from: track meters, master spectrum, role graph, device chain info.

### Task 2A.3: Mix Critics

**Files:**
- Create: `mcp_server/mix_engine/critics.py`

6 critics: balance, masking, dynamics, stereo, depth, translation

### Task 2A.4: Mix Planner

**Files:**
- Create: `mcp_server/mix_engine/planner.py`

Move ranking: EQ correction, transient shaping, saturation, width, send rebalance

### Task 2A.5: Mix Evaluator

**Files:**
- Create: `mcp_server/mix_engine/evaluator.py`

Uses Evaluation Fabric to score: masking reduction, punch change, headroom, stereo stability

### Task 2A.6: MCP Tools + Integration

**Files:**
- Create: `mcp_server/mix_engine/tools.py`
- Modify: `mcp_server/server.py`

6 new tools:
- `analyze_mix` — full mix state analysis
- `get_mix_issues` — critic findings
- `plan_mix_move` — ranked move suggestions
- `evaluate_mix_move` — before/after mix scoring
- `get_masking_report` — frequency collision map
- `get_mix_summary` — lightweight overview

- [ ] **Steps 1-8:** Full TDD cycle for each sub-task
- [ ] **Step 9:** Update tool count (→ ~217)
- [ ] **Step 10:** Commit

```bash
git commit -m "feat(phase2a): Mix Engine V1 — 6 critics, move planner, evaluator"
git tag phase2a-mix-engine-complete
```

---

## Future Phases (Specs Ready, Not Yet Planned)

These specs are written and ready for implementation planning when needed:

| Phase | Engine | Spec | Prerequisites |
|-------|--------|------|---------------|
| 3A | Sound Design Engine | SOUND_DESIGN_ENGINE_V1.md | Project Brain, Eval Fabric |
| 3B | Transition Engine | TRANSITION_ENGINE_V1.md | Composition Engine |
| 3C | Reference Engine | REFERENCE_ENGINE_V1.md | Perception, Taste Model |
| 3D | Research Engine (extend) | RESEARCH_ENGINE_V1.md | Memory Fabric V2 |
| 4A | Translation Engine | TRANSLATION_ENGINE_V1.md | Mix Engine |
| 4B | Performance Engine | PERFORMANCE_ENGINE_V1.md | Capability State |
| 4C | Taste Model (extend) | TASTE_MODEL_V1.md | Memory Fabric V2 |

Each future phase should get its own implementation plan document following this same structure.

---

## Session Handoff Protocol

When starting a new session to continue this work:

1. **Read this plan:** `docs/superpowers/plans/2026-04-08-v2-engine-architecture.md`
2. **Check progress:** Look for `git tag` markers (`phase0-hardening-complete`, `phase1a-project-brain-complete`, etc.)
3. **Read the relevant spec:** `/tmp/LivePilot-audit/docs/<SPEC_NAME>.md` (or copy specs into repo)
4. **Resume from the next uncompleted task** in the active phase
5. **Run existing tests first** to verify baseline: `python3 -m pytest tests/ -q`

Each phase is fully self-contained. You don't need context from previous sessions — just this plan + the spec + the code.

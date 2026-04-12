# Sample Engine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Sample Engine — an intelligence layer for sample discovery, analysis, critique, and creative manipulation in Ableton Live via LivePilot.

**Architecture:** New `mcp_server/sample_engine/` module following the proven `sound_design/` and `mix_engine/` pattern. Pure-computation models/critics/planner, 6 new MCP tools (intelligence only — no new Ableton communication), 6 Wonder Mode semantic moves, and a skill with reference corpus. All sample I/O reuses existing tools.

**Tech Stack:** Python 3.10+, dataclasses, FastMCP, existing LivePilot tools/bridge.

**Spec:** `docs/superpowers/specs/2026-04-12-sample-engine-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `mcp_server/sample_engine/__init__.py` | Package init — empty |
| `mcp_server/sample_engine/models.py` | SampleProfile, SampleIntent, SampleFitReport, CriticResult, SampleCandidate, SampleTechnique, TechniqueStep |
| `mcp_server/sample_engine/analyzer.py` | Filename parser, spectral classifier, material detector, mode recommender |
| `mcp_server/sample_engine/sources.py` | BrowserSource, FilesystemSource, FreesoundSource, unified search |
| `mcp_server/sample_engine/critics.py` | 6 critics: key_fit, tempo_fit, frequency_fit, role_fit, vibe_fit, intent_fit |
| `mcp_server/sample_engine/techniques.py` | 30+ technique catalog indexed by material_type + intent |
| `mcp_server/sample_engine/planner.py` | Technique selection, plan compilation, surgeon/alchemist dual plans |
| `mcp_server/sample_engine/tools.py` | 6 MCP tools: analyze_sample, evaluate_sample_fit, search_samples, suggest_sample_technique, plan_sample_workflow, get_sample_opportunities |
| `mcp_server/sample_engine/moves.py` | 6 semantic moves for Wonder Mode |
| `mcp_server/semantic_moves/sample_compilers.py` | Compilers for sample-domain moves |
| `tests/test_sample_engine_models.py` | Model unit tests |
| `tests/test_sample_engine_analyzer.py` | Analyzer unit tests |
| `tests/test_sample_engine_critics.py` | Critic unit tests |
| `tests/test_sample_engine_planner.py` | Planner + technique selection tests |
| `tests/test_sample_engine_sources.py` | Source unit tests |
| `tests/test_sample_engine_moves.py` | Semantic move registration tests |
| `livepilot/skills/livepilot-sample-engine/SKILL.md` | Skill trigger patterns and workflow |
| `livepilot/skills/livepilot-sample-engine/references/sample-techniques.md` | Technique catalog reference |
| `livepilot/skills/livepilot-sample-engine/references/sample-critics.md` | Critic scoring reference |
| `livepilot/skills/livepilot-sample-engine/references/sample-philosophy.md` | Surgeon vs Alchemist guide |

### Modified Files
| File | Change |
|------|--------|
| `mcp_server/server.py` | Add `from .sample_engine import tools as sample_engine_tools` import |
| `mcp_server/semantic_moves/__init__.py` | Add `from . import sample_moves` and `from . import sample_compilers` |
| `mcp_server/wonder_mode/diagnosis.py` | Add sample entries to `_DOMAIN_MAP` |
| `tests/test_tools_contract.py` | Add `test_sample_engine_tools_registered()` |

---

## Chunk 1: Models + Analyzer

### Task 1: Data Models

**Files:**
- Create: `mcp_server/sample_engine/__init__.py`
- Create: `mcp_server/sample_engine/models.py`
- Test: `tests/test_sample_engine_models.py`

- [ ] **Step 1: Create package**

```python
# mcp_server/sample_engine/__init__.py
"""Sample Engine — intelligence layer for sample discovery, analysis, and manipulation."""
```

- [ ] **Step 2: Write failing tests for models**

```python
# tests/test_sample_engine_models.py
"""Tests for Sample Engine data models — pure dataclass tests, no I/O."""

from __future__ import annotations

import pytest

from mcp_server.sample_engine.models import (
    SampleProfile,
    SampleIntent,
    CriticResult,
    SampleFitReport,
    SampleCandidate,
    SampleTechnique,
    TechniqueStep,
    VALID_MATERIAL_TYPES,
    VALID_INTENTS,
    VALID_SIMPLER_MODES,
    VALID_SLICE_METHODS,
    VALID_WARP_MODES,
)


class TestSampleProfile:
    def test_defaults(self):
        p = SampleProfile(source="browser", file_path="/tmp/test.wav", name="test")
        assert p.source == "browser"
        assert p.key is None
        assert p.key_confidence == 0.0
        assert p.material_type == "unknown"
        assert p.suggested_mode == "classic"

    def test_to_dict(self):
        p = SampleProfile(source="filesystem", file_path="/a/b.wav", name="b",
                          key="Cm", key_confidence=0.8, bpm=120.0)
        d = p.to_dict()
        assert isinstance(d, dict)
        assert d["key"] == "Cm"
        assert d["bpm"] == 120.0

    def test_material_types_valid(self):
        for mt in VALID_MATERIAL_TYPES:
            p = SampleProfile(source="test", file_path="/t.wav", name="t",
                              material_type=mt)
            assert p.material_type == mt


class TestSampleIntent:
    def test_defaults(self):
        i = SampleIntent(intent_type="rhythm", description="chop it")
        assert i.philosophy == "auto"
        assert i.target_track is None

    def test_to_dict(self):
        i = SampleIntent(intent_type="texture", philosophy="alchemist",
                         description="stretch into pad")
        d = i.to_dict()
        assert d["intent_type"] == "texture"
        assert d["philosophy"] == "alchemist"


class TestCriticResult:
    def test_rating_from_score(self):
        r = CriticResult(critic_name="key_fit", score=0.9,
                         recommendation="load directly")
        assert r.rating == "excellent"

    def test_rating_boundaries(self):
        assert CriticResult(critic_name="t", score=0.85, recommendation="").rating == "excellent"
        assert CriticResult(critic_name="t", score=0.7, recommendation="").rating == "good"
        assert CriticResult(critic_name="t", score=0.5, recommendation="").rating == "fair"
        assert CriticResult(critic_name="t", score=0.2, recommendation="").rating == "poor"


class TestSampleFitReport:
    def test_overall_score_computed(self):
        critics = {
            "key_fit": CriticResult(critic_name="key_fit", score=1.0, recommendation=""),
            "tempo_fit": CriticResult(critic_name="tempo_fit", score=0.8, recommendation=""),
        }
        report = SampleFitReport(
            sample=SampleProfile(source="test", file_path="/t.wav", name="t"),
            critics=critics,
            recommended_intent="rhythm",
            recommended_technique="slice_and_sequence",
        )
        assert report.overall_score > 0.0
        assert isinstance(report.warnings, list)


class TestSampleCandidate:
    def test_creation(self):
        c = SampleCandidate(source="freesound", name="vocal_Cm_120",
                            metadata={"key": "Cm", "bpm": 120})
        assert c.source == "freesound"

    def test_to_dict(self):
        c = SampleCandidate(source="browser", name="kick", metadata={})
        d = c.to_dict()
        assert d["source"] == "browser"


class TestSampleTechnique:
    def test_creation(self):
        t = SampleTechnique(
            technique_id="slice_and_sequence",
            name="Slice & Sequence",
            philosophy="surgeon",
            material_types=["drum_loop"],
            intents=["rhythm"],
            difficulty="basic",
            description="Classic MPC-style slice and sequence",
            inspiration="MPC workflow",
            steps=[TechniqueStep(tool="set_simpler_playback_mode",
                                 params={"playback_mode": 2},
                                 description="Set to Slice mode")],
        )
        assert t.technique_id == "slice_and_sequence"
        assert len(t.steps) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_models.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 4: Implement models**

```python
# mcp_server/sample_engine/models.py
"""Sample Engine data models — all dataclasses with to_dict().

Pure data structures for sample profiles, intents, critic results,
fit reports, candidates, and techniques. Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


VALID_MATERIAL_TYPES = frozenset({
    "vocal", "drum_loop", "instrument_loop", "one_shot",
    "texture", "foley", "fx", "full_mix", "unknown",
})

VALID_INTENTS = frozenset({
    "rhythm", "texture", "layer", "melody", "vocal",
    "atmosphere", "transform", "challenge",
})

VALID_SIMPLER_MODES = frozenset({"classic", "one_shot", "slice"})

VALID_SLICE_METHODS = frozenset({"transient", "beat", "region", "manual"})

VALID_WARP_MODES = frozenset({
    "beats", "tones", "texture", "complex", "complex_pro",
})


@dataclass
class SampleProfile:
    """Complete fingerprint of a sample."""

    source: str
    file_path: str
    name: str
    uri: Optional[str] = None
    freesound_id: Optional[int] = None
    license: Optional[str] = None

    key: Optional[str] = None
    key_confidence: float = 0.0
    bpm: Optional[float] = None
    bpm_confidence: float = 0.0
    time_signature: str = "4/4"

    material_type: str = "unknown"
    material_confidence: float = 0.0

    frequency_center: float = 0.0
    frequency_spread: float = 0.0
    brightness: float = 0.0
    transient_density: float = 0.0

    duration_seconds: float = 0.0
    duration_beats: Optional[float] = None
    bar_count: Optional[float] = None
    has_clear_downbeat: bool = False

    suggested_mode: str = "classic"
    suggested_slice_by: str = "transient"
    suggested_warp_mode: str = "complex"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SampleIntent:
    """What the user wants to do with a sample."""

    intent_type: str
    description: str
    philosophy: str = "auto"
    target_track: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CriticResult:
    """Result from a single sample critic."""

    critic_name: str
    score: float
    recommendation: str
    adjustments: list = field(default_factory=list)

    @property
    def rating(self) -> str:
        if self.score >= 0.8:
            return "excellent"
        if self.score >= 0.6:
            return "good"
        if self.score >= 0.4:
            return "fair"
        return "poor"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rating"] = self.rating
        return d


@dataclass
class SampleFitReport:
    """Output of the 6-critic battery."""

    sample: SampleProfile
    critics: dict  # str -> CriticResult
    recommended_intent: str = ""
    recommended_technique: str = ""
    processing_chain: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    surgeon_plan: list = field(default_factory=list)
    alchemist_plan: list = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        if not self.critics:
            return 0.0
        scores = [c.score if isinstance(c, CriticResult) else c.get("score", 0)
                  for c in self.critics.values()]
        return sum(scores) / len(scores) if scores else 0.0

    def to_dict(self) -> dict:
        return {
            "sample": self.sample.to_dict(),
            "overall_score": round(self.overall_score, 3),
            "critics": {k: (v.to_dict() if isinstance(v, CriticResult) else v)
                        for k, v in self.critics.items()},
            "recommended_intent": self.recommended_intent,
            "recommended_technique": self.recommended_technique,
            "processing_chain": self.processing_chain,
            "warnings": self.warnings,
            "surgeon_plan": self.surgeon_plan,
            "alchemist_plan": self.alchemist_plan,
        }


@dataclass
class SampleCandidate:
    """A sample discovered by a source, pre-load."""

    source: str
    name: str
    metadata: dict = field(default_factory=dict)
    file_path: Optional[str] = None
    uri: Optional[str] = None
    freesound_id: Optional[int] = None
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TechniqueStep:
    """A single step in a sample technique recipe."""

    tool: str
    params: dict = field(default_factory=dict)
    description: str = ""
    condition: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SampleTechnique:
    """A sample manipulation recipe from the technique library."""

    technique_id: str
    name: str
    philosophy: str
    material_types: list = field(default_factory=list)
    intents: list = field(default_factory=list)
    difficulty: str = "basic"
    description: str = ""
    inspiration: str = ""
    steps: list = field(default_factory=list)  # list[TechniqueStep]
    success_signals: list = field(default_factory=list)
    failure_signals: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [s.to_dict() if isinstance(s, TechniqueStep) else s
                      for s in self.steps]
        return d
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_models.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot"
git add mcp_server/sample_engine/__init__.py mcp_server/sample_engine/models.py tests/test_sample_engine_models.py
git commit -m "feat(sample-engine): add data models — SampleProfile, SampleIntent, CriticResult, SampleFitReport, SampleCandidate, SampleTechnique"
```

---

### Task 2: SampleAnalyzer — Filename Parser

**Files:**
- Create: `mcp_server/sample_engine/analyzer.py`
- Test: `tests/test_sample_engine_analyzer.py`

- [ ] **Step 1: Write failing tests for filename parsing**

```python
# tests/test_sample_engine_analyzer.py
"""Tests for SampleAnalyzer — pure computation, no I/O."""

from __future__ import annotations

import pytest

from mcp_server.sample_engine.analyzer import (
    parse_filename_metadata,
    classify_material_from_name,
    suggest_simpler_mode,
    suggest_warp_mode,
)
from mcp_server.sample_engine.models import SampleProfile


class TestFilenameParser:
    def test_key_bpm_pattern(self):
        result = parse_filename_metadata("vocal_Cm_120bpm.wav")
        assert result["key"] == "Cm"
        assert result["bpm"] == 120.0

    def test_bpm_key_pattern(self):
        result = parse_filename_metadata("120_Am_guitar.aif")
        assert result["bpm"] == 120.0
        assert result["key"] == "Am"

    def test_bpm_only(self):
        result = parse_filename_metadata("DUSTY_BREAK_95.wav")
        assert result["bpm"] == 95.0
        assert result["key"] is None

    def test_key_only(self):
        result = parse_filename_metadata("pad_Fsharp.wav")
        assert result["key"] in ("F#", "Fsharp", "F#m")  # accept variants

    def test_no_metadata(self):
        result = parse_filename_metadata("untitled_003.wav")
        assert result["key"] is None
        assert result["bpm"] is None

    def test_sharp_flat_keys(self):
        result = parse_filename_metadata("synth_Bb_90bpm.wav")
        assert result["key"] == "Bb"

    def test_minor_key(self):
        result = parse_filename_metadata("bass_Ebm_140.wav")
        assert result["key"] == "Ebm"
        assert result["bpm"] == 140.0

    def test_splice_style(self):
        result = parse_filename_metadata("SP_DnB_Reese_Bass_Cm_174_Wet.wav")
        assert result["key"] == "Cm"
        assert result["bpm"] == 174.0


class TestMaterialClassifier:
    def test_vocal_keywords(self):
        assert classify_material_from_name("dark_vocal_loop") == "vocal"
        assert classify_material_from_name("vox_chop_dry") == "vocal"

    def test_drum_keywords(self):
        assert classify_material_from_name("drum_loop_funky") == "drum_loop"
        assert classify_material_from_name("breakbeat_170") == "drum_loop"
        assert classify_material_from_name("hihat_pattern") == "drum_loop"

    def test_one_shot_keywords(self):
        assert classify_material_from_name("kick_hard") == "one_shot"
        assert classify_material_from_name("snare_crack") == "one_shot"
        assert classify_material_from_name("clap_tight") == "one_shot"

    def test_texture_keywords(self):
        assert classify_material_from_name("ambient_pad_drone") == "texture"
        assert classify_material_from_name("noise_texture") == "texture"

    def test_unknown(self):
        assert classify_material_from_name("untitled_003") == "unknown"

    def test_foley(self):
        assert classify_material_from_name("foley_metal_scrape") == "foley"


class TestSimplerModeRecommender:
    def test_one_shot_short_duration(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="unknown", duration_seconds=0.3)
        assert suggest_simpler_mode(p) == "classic"

    def test_drum_loop_slices_by_transient(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="drum_loop", duration_seconds=4.0)
        mode, slice_by = suggest_simpler_mode(p), "transient"
        assert mode == "slice"

    def test_vocal_slices_by_region(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="vocal", duration_seconds=8.0)
        assert suggest_simpler_mode(p) == "slice"

    def test_texture_stays_classic(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="texture", duration_seconds=10.0)
        assert suggest_simpler_mode(p) == "classic"


class TestWarpModeRecommender:
    def test_drum_loop_beats_mode(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="drum_loop")
        assert suggest_warp_mode(p) == "beats"

    def test_vocal_complex_pro(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="vocal")
        assert suggest_warp_mode(p) == "complex_pro"

    def test_texture_texture_mode(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="texture")
        assert suggest_warp_mode(p) == "texture"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_analyzer.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement analyzer**

```python
# mcp_server/sample_engine/analyzer.py
"""SampleAnalyzer — filename parsing, material classification, mode recommendation.

Pure computation for the offline parts. Spectral analysis requires M4L bridge
and is handled in tools.py which calls these functions + bridge data.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from .models import SampleProfile


# ── Filename Metadata Parsing ───────────────────────────────────────

# Key patterns: C, Cm, C#, C#m, Cb, Cbm, Csharp, Csharpmin, etc.
_KEY_PATTERN = re.compile(
    r'\b([A-G])([b#]|sharp|flat)?(m|min|minor|maj|major)?\b',
    re.IGNORECASE,
)

# BPM patterns: 120bpm, 120_bpm, 120 BPM, or standalone 60-300 range
_BPM_PATTERN = re.compile(
    r'\b(\d{2,3})\s*(?:bpm)\b', re.IGNORECASE,
)
_BPM_STANDALONE = re.compile(
    r'(?:^|[_\-\s])(\d{2,3})(?:[_\-\s]|$)',
)

_KEY_NORMALIZE = {
    "sharp": "#", "flat": "b",
    "min": "m", "minor": "m", "maj": "", "major": "",
}


def parse_filename_metadata(filename: str) -> dict:
    """Extract key and BPM from a filename string.

    Returns dict with 'key' (str|None) and 'bpm' (float|None).
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    # Replace common separators with spaces for easier matching
    normalized = stem.replace("-", " ").replace("_", " ")

    key = _extract_key(normalized)
    bpm = _extract_bpm(normalized)

    return {"key": key, "bpm": bpm}


def _extract_key(text: str) -> Optional[str]:
    """Extract musical key from text."""
    matches = list(_KEY_PATTERN.finditer(text))
    for match in matches:
        root = match.group(1).upper()
        accidental = match.group(2) or ""
        quality = match.group(3) or ""

        # Normalize accidentals
        accidental = _KEY_NORMALIZE.get(accidental.lower(), accidental)
        quality = _KEY_NORMALIZE.get(quality.lower(), quality) if quality else ""

        # Avoid false positives: single letters that are common words
        full = root + accidental + quality
        if len(full) == 1 and root in ("A", "B", "C", "D", "E", "F", "G"):
            # Single letter — only accept if it looks like it's in a key context
            # Check surrounding chars
            start = match.start()
            end = match.end()
            before = text[start - 1] if start > 0 else " "
            after = text[end] if end < len(text) else " "
            if before.isalpha() or after.isalpha():
                continue  # Part of a word, not a key
        return full
    return None


def _extract_bpm(text: str) -> Optional[float]:
    """Extract BPM from text."""
    # Try explicit bpm markers first
    match = _BPM_PATTERN.search(text)
    if match:
        bpm = float(match.group(1))
        if 40 <= bpm <= 300:
            return bpm

    # Try standalone numbers in valid range
    for match in _BPM_STANDALONE.finditer(text):
        bpm = float(match.group(1))
        if 60 <= bpm <= 250:
            return bpm
    return None


# ── Material Classification ─────────────────────────────────────────

_MATERIAL_KEYWORDS: dict[str, list[str]] = {
    "vocal": ["vocal", "vox", "voice", "singer", "acapella", "spoken"],
    "drum_loop": ["drum", "beat", "break", "breakbeat", "loop", "groove",
                  "hihat", "hat", "ride", "cymbal", "perc", "percussion",
                  "shaker", "tamb", "conga", "bongo", "top"],
    "one_shot": ["kick", "snare", "clap", "snap", "tom", "rim", "hit",
                 "oneshot", "one shot", "stab", "shot", "impact"],
    "instrument_loop": ["guitar", "piano", "keys", "bass", "synth",
                        "strings", "brass", "horn", "organ", "riff",
                        "chord", "arp", "pluck"],
    "texture": ["ambient", "pad", "drone", "atmosphere", "noise",
                "texture", "wash", "evolving", "soundscape"],
    "foley": ["foley", "field", "recording", "room", "nature",
              "water", "metal", "wood", "glass", "paper"],
    "fx": ["fx", "effect", "riser", "sweep", "whoosh", "boom",
           "transition", "downlifter", "uplifter"],
}


def classify_material_from_name(name: str) -> str:
    """Classify sample material type from filename/name keywords."""
    lower = name.lower().replace("-", " ").replace("_", " ")

    # Score each type by keyword matches
    scores: dict[str, int] = {}
    for material_type, keywords in _MATERIAL_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[material_type] = score

    if not scores:
        return "unknown"

    return max(scores, key=scores.get)


# ── Simpler Mode Recommendation ────────────────────────────────────


def suggest_simpler_mode(profile: SampleProfile) -> str:
    """Recommend Simpler playback mode based on material analysis.

    Returns: "classic", "one_shot", or "slice"
    """
    if profile.duration_seconds < 0.5 or profile.material_type == "one_shot":
        return "classic"
    if profile.material_type == "fx":
        return "classic"
    if profile.material_type in ("texture", "foley"):
        return "classic"
    if profile.material_type in ("drum_loop", "instrument_loop",
                                  "vocal", "full_mix"):
        return "slice"
    # Unknown material with decent length — slice is more useful
    if profile.duration_seconds > 2.0:
        return "slice"
    return "classic"


def suggest_slice_method(profile: SampleProfile) -> str:
    """Recommend slice-by method for Simpler's Slice mode."""
    if profile.material_type == "drum_loop":
        return "transient"
    if profile.material_type == "instrument_loop":
        return "beat"
    if profile.material_type == "vocal":
        return "region"
    if profile.material_type == "full_mix":
        return "beat"
    return "transient"


def suggest_warp_mode(profile: SampleProfile) -> str:
    """Recommend Ableton warp mode for the sample material."""
    mode_map = {
        "drum_loop": "beats",
        "one_shot": "complex",
        "instrument_loop": "complex_pro",
        "vocal": "complex_pro",
        "texture": "texture",
        "foley": "texture",
        "fx": "complex",
        "full_mix": "complex_pro",
    }
    return mode_map.get(profile.material_type, "complex")


def build_profile_from_filename(
    file_path: str,
    source: str = "filesystem",
    duration_seconds: float = 0.0,
) -> SampleProfile:
    """Build a SampleProfile from filename metadata only (no spectral analysis).

    This is the fallback when M4L bridge is unavailable.
    """
    name = os.path.splitext(os.path.basename(file_path))[0]
    metadata = parse_filename_metadata(file_path)
    material = classify_material_from_name(name)

    profile = SampleProfile(
        source=source,
        file_path=file_path,
        name=name,
        key=metadata.get("key"),
        key_confidence=0.5 if metadata.get("key") else 0.0,
        bpm=metadata.get("bpm"),
        bpm_confidence=0.5 if metadata.get("bpm") else 0.0,
        material_type=material,
        material_confidence=0.4,  # filename-only is low confidence
        duration_seconds=duration_seconds,
    )

    profile.suggested_mode = suggest_simpler_mode(profile)
    profile.suggested_slice_by = suggest_slice_method(profile)
    profile.suggested_warp_mode = suggest_warp_mode(profile)

    return profile
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_analyzer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot"
git add mcp_server/sample_engine/analyzer.py tests/test_sample_engine_analyzer.py
git commit -m "feat(sample-engine): add SampleAnalyzer — filename parser, material classifier, mode recommender"
```

---

## Chunk 2: Sources + Critics

### Task 3: Sample Sources

**Files:**
- Create: `mcp_server/sample_engine/sources.py`
- Test: `tests/test_sample_engine_sources.py`

- [ ] **Step 1: Write failing tests for sources**

```python
# tests/test_sample_engine_sources.py
"""Tests for sample sources — unit tests with mocked I/O."""

from __future__ import annotations

import os
import json
import tempfile

import pytest

from mcp_server.sample_engine.sources import (
    FilesystemSource,
    FreesoundSource,
    build_search_queries,
    parse_freesound_metadata,
)
from mcp_server.sample_engine.models import SampleCandidate


class TestFilesystemSource:
    def test_scan_finds_audio_files(self, tmp_path):
        # Create test audio files
        (tmp_path / "kick.wav").write_bytes(b"fake")
        (tmp_path / "vocal_Cm_120bpm.aif").write_bytes(b"fake")
        (tmp_path / "readme.txt").write_bytes(b"not audio")
        (tmp_path / "sub" ).mkdir()
        (tmp_path / "sub" / "pad.mp3").write_bytes(b"fake")

        source = FilesystemSource(scan_paths=[str(tmp_path)], max_depth=3)
        results = source.scan()
        audio_names = {r.name for r in results}
        assert "kick" in audio_names
        assert "vocal_Cm_120bpm" in audio_names
        assert "pad" in audio_names
        assert "readme" not in audio_names

    def test_search_filters_by_query(self, tmp_path):
        (tmp_path / "dark_vocal_Cm.wav").write_bytes(b"fake")
        (tmp_path / "bright_pad.wav").write_bytes(b"fake")

        source = FilesystemSource(scan_paths=[str(tmp_path)])
        results = source.search("vocal")
        names = [r.name for r in results]
        assert "dark_vocal_Cm" in names
        assert "bright_pad" not in names

    def test_metadata_extracted(self, tmp_path):
        (tmp_path / "synth_Am_128bpm.wav").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)])
        results = source.scan()
        assert len(results) == 1
        assert results[0].metadata.get("key") == "Am"
        assert results[0].metadata.get("bpm") == 128.0


class TestBuildSearchQueries:
    def test_basic_query(self):
        queries = build_search_queries("dark vocal", material_type="vocal")
        assert any("vocal" in q.lower() for q in queries)

    def test_contextual_from_song_state(self):
        queries = build_search_queries(
            "something organic",
            song_context={"key": "Cm", "tempo": 128, "missing_roles": ["texture"]}
        )
        assert len(queries) >= 1


class TestFreesoundMetadata:
    def test_parse_ac_descriptors(self):
        raw = {
            "id": 12345,
            "name": "vocal_sample.wav",
            "tags": ["vocal", "female", "clean"],
            "ac_analysis": {
                "ac_key": "Cm",
                "ac_tempo": 120.0,
                "ac_brightness": 0.6,
                "ac_depth": 0.4,
            },
            "license": "Attribution",
            "duration": 4.5,
        }
        candidate = parse_freesound_metadata(raw)
        assert candidate.metadata["key"] == "Cm"
        assert candidate.metadata["bpm"] == 120.0
        assert candidate.freesound_id == 12345
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_sources.py -v`
Expected: FAIL

- [ ] **Step 3: Implement sources**

```python
# mcp_server/sample_engine/sources.py
"""Sample sources — discover samples from browser, filesystem, and Freesound.

Browser source is a thin wrapper around existing MCP tools (search_browser,
get_browser_items). Filesystem scans local directories. Freesound uses the
public API v2.
"""

from __future__ import annotations

import os
import json
from typing import Optional

from .models import SampleCandidate
from .analyzer import parse_filename_metadata, classify_material_from_name


_AUDIO_EXTENSIONS = frozenset({
    ".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg",
})


# ── Filesystem Source ───────────────────────────────────────────────


class FilesystemSource:
    """Scan local directories for audio files with metadata extraction."""

    def __init__(
        self,
        scan_paths: Optional[list[str]] = None,
        max_depth: int = 6,
    ):
        self.scan_paths = scan_paths or []
        self.max_depth = max_depth

    def scan(self) -> list[SampleCandidate]:
        """Scan all configured paths for audio files."""
        candidates: list[SampleCandidate] = []
        for base_path in self.scan_paths:
            expanded = os.path.expanduser(base_path)
            if not os.path.isdir(expanded):
                continue
            self._scan_dir(expanded, 0, candidates)
        return candidates

    def search(self, query: str, max_results: int = 20) -> list[SampleCandidate]:
        """Search scanned files by query keywords."""
        all_files = self.scan()
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[SampleCandidate, float]] = []
        for candidate in all_files:
            name_lower = candidate.name.lower()
            score = sum(1 for w in query_words if w in name_lower)
            # Boost for metadata matches
            if candidate.metadata.get("key") and query_lower in str(candidate.metadata.get("key", "")).lower():
                score += 0.5
            if score > 0:
                scored.append((candidate, score))

        scored.sort(key=lambda x: -x[1])
        return [c for c, _ in scored[:max_results]]

    def _scan_dir(self, path: str, depth: int, out: list[SampleCandidate]):
        if depth > self.max_depth:
            return
        try:
            entries = os.scandir(path)
        except PermissionError:
            return

        for entry in entries:
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in _AUDIO_EXTENSIONS:
                    stem = os.path.splitext(entry.name)[0]
                    metadata = parse_filename_metadata(entry.name)
                    metadata["material_type"] = classify_material_from_name(stem)
                    out.append(SampleCandidate(
                        source="filesystem",
                        name=stem,
                        file_path=entry.path,
                        metadata=metadata,
                    ))
            elif entry.is_dir() and not entry.name.startswith("."):
                self._scan_dir(entry.path, depth + 1, out)


# ── Freesound Helpers ───────────────────────────────────────────────


def parse_freesound_metadata(raw: dict) -> SampleCandidate:
    """Parse a Freesound API response into a SampleCandidate."""
    ac = raw.get("ac_analysis") or {}
    metadata = {
        "key": ac.get("ac_key"),
        "bpm": ac.get("ac_tempo"),
        "brightness": ac.get("ac_brightness"),
        "depth": ac.get("ac_depth"),
        "tags": raw.get("tags", []),
        "duration": raw.get("duration"),
        "license": raw.get("license"),
    }
    material = "unknown"
    tags = raw.get("tags", [])
    tag_str = " ".join(tags)
    material = classify_material_from_name(tag_str)

    return SampleCandidate(
        source="freesound",
        name=raw.get("name", ""),
        freesound_id=raw.get("id"),
        metadata=metadata,
    )


class FreesoundSource:
    """Search Freesound API v2. Requires FREESOUND_API_KEY env var."""

    def __init__(self, api_key: Optional[str] = None, download_dir: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FREESOUND_API_KEY")
        self.download_dir = download_dir or os.path.expanduser(
            "~/Documents/LivePilot/downloads/freesound"
        )
        self.enabled = bool(self.api_key)

    def search(self, query: str, max_results: int = 10,
               license_filter: str = "Attribution") -> list[SampleCandidate]:
        """Search Freesound. Returns candidates without downloading.

        Actual HTTP calls happen in the MCP tool layer (tools.py) which
        can use httpx/aiohttp. This module builds the query and parses results.
        """
        if not self.enabled:
            return []
        # Build query params for the tool layer to execute
        return []  # Placeholder — actual HTTP is in tools.py

    def build_search_params(self, query: str, max_results: int = 10,
                            license_filter: str = "Attribution") -> dict:
        """Build Freesound API search parameters."""
        return {
            "query": query,
            "page_size": min(max_results, 15),
            "fields": "id,name,tags,duration,license,ac_analysis,previews",
            "filter": f'license:"{license_filter}"',
            "sort": "rating_desc",
        }


# ── Search Query Builder ────────────────────────────────────────────


def build_search_queries(
    user_query: str,
    material_type: Optional[str] = None,
    song_context: Optional[dict] = None,
) -> list[str]:
    """Build smart search queries from user request + song context.

    Returns multiple query strings to try across different sources.
    """
    queries = [user_query]

    if material_type:
        # Add material-specific synonyms
        synonyms = {
            "vocal": ["vocal", "vox", "voice", "acapella"],
            "drum_loop": ["drum loop", "breakbeat", "percussion loop"],
            "texture": ["ambient", "pad", "texture", "drone"],
            "one_shot": ["one shot", "hit", "stab"],
        }
        for syn in synonyms.get(material_type, []):
            if syn.lower() not in user_query.lower():
                queries.append(f"{user_query} {syn}")

    if song_context:
        key = song_context.get("key", "")
        if key and key not in user_query:
            queries.append(f"{user_query} {key}")

    return queries[:5]  # Cap at 5 queries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_sources.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot"
git add mcp_server/sample_engine/sources.py tests/test_sample_engine_sources.py
git commit -m "feat(sample-engine): add sample sources — filesystem scanner, Freesound parser, query builder"
```

---

### Task 4: Sample Critics

**Files:**
- Create: `mcp_server/sample_engine/critics.py`
- Test: `tests/test_sample_engine_critics.py`

- [ ] **Step 1: Write failing tests for critics**

```python
# tests/test_sample_engine_critics.py
"""Tests for Sample Engine critics — pure computation, no I/O."""

from __future__ import annotations

import pytest

from mcp_server.sample_engine.critics import (
    run_key_fit_critic,
    run_tempo_fit_critic,
    run_frequency_fit_critic,
    run_role_fit_critic,
    run_intent_fit_critic,
    run_all_sample_critics,
)
from mcp_server.sample_engine.models import (
    SampleProfile,
    SampleIntent,
    CriticResult,
)


def _make_profile(**kwargs) -> SampleProfile:
    defaults = {"source": "test", "file_path": "/t.wav", "name": "test"}
    defaults.update(kwargs)
    return SampleProfile(**defaults)


class TestKeyFitCritic:
    def test_same_key_perfect_score(self):
        r = run_key_fit_critic(_make_profile(key="Cm"), song_key="Cm")
        assert r.score == 1.0

    def test_relative_major_minor(self):
        r = run_key_fit_critic(_make_profile(key="Eb"), song_key="Cm")
        assert r.score >= 0.8

    def test_fifth_relationship(self):
        r = run_key_fit_critic(_make_profile(key="Gm"), song_key="Cm")
        assert r.score >= 0.6

    def test_distant_key_low_score(self):
        r = run_key_fit_critic(_make_profile(key="F#"), song_key="C")
        assert r.score <= 0.5

    def test_unknown_key_zero(self):
        r = run_key_fit_critic(_make_profile(key=None), song_key="Cm")
        assert r.score == 0.0

    def test_no_song_key_neutral(self):
        r = run_key_fit_critic(_make_profile(key="Cm"), song_key=None)
        assert r.score == 0.5


class TestTempoFitCritic:
    def test_exact_match(self):
        r = run_tempo_fit_critic(_make_profile(bpm=128.0), session_tempo=128.0)
        assert r.score >= 0.95

    def test_half_time(self):
        r = run_tempo_fit_critic(_make_profile(bpm=64.0), session_tempo=128.0)
        assert r.score >= 0.85

    def test_double_time(self):
        r = run_tempo_fit_critic(_make_profile(bpm=256.0), session_tempo=128.0)
        assert r.score >= 0.85

    def test_close_bpm(self):
        r = run_tempo_fit_critic(_make_profile(bpm=132.0), session_tempo=128.0)
        assert r.score >= 0.6

    def test_far_bpm(self):
        r = run_tempo_fit_critic(_make_profile(bpm=80.0), session_tempo=140.0)
        assert r.score <= 0.4

    def test_unknown_bpm_zero(self):
        r = run_tempo_fit_critic(_make_profile(bpm=None), session_tempo=128.0)
        assert r.score == 0.0


class TestRoleFitCritic:
    def test_fills_missing_role(self):
        r = run_role_fit_critic(
            _make_profile(material_type="vocal"),
            existing_roles=["drums", "bass", "synth"],
        )
        assert r.score >= 0.8

    def test_redundant_role(self):
        r = run_role_fit_critic(
            _make_profile(material_type="drum_loop"),
            existing_roles=["drums", "percussion", "hihat"],
        )
        assert r.score <= 0.5


class TestIntentFitCritic:
    def test_perfect_match(self):
        r = run_intent_fit_critic(
            _make_profile(material_type="drum_loop"),
            intent=SampleIntent(intent_type="rhythm", description=""),
        )
        assert r.score >= 0.8

    def test_creative_mismatch(self):
        r = run_intent_fit_critic(
            _make_profile(material_type="vocal"),
            intent=SampleIntent(intent_type="rhythm", description=""),
        )
        # Vocal for rhythm is unusual but possible (chop workflow)
        assert 0.4 <= r.score <= 0.8


class TestRunAllCritics:
    def test_returns_all_six(self):
        results = run_all_sample_critics(
            profile=_make_profile(key="Cm", bpm=128.0, material_type="vocal"),
            intent=SampleIntent(intent_type="vocal", description=""),
            song_key="Cm",
            session_tempo=128.0,
            existing_roles=["drums", "bass"],
        )
        assert "key_fit" in results
        assert "tempo_fit" in results
        assert "frequency_fit" in results
        assert "role_fit" in results
        assert "vibe_fit" in results
        assert "intent_fit" in results
        assert all(isinstance(v, CriticResult) for v in results.values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_critics.py -v`
Expected: FAIL

- [ ] **Step 3: Implement critics**

```python
# mcp_server/sample_engine/critics.py
"""Sample Engine critics — score sample fitness against the current song.

Six critics: key_fit, tempo_fit, frequency_fit, role_fit, vibe_fit, intent_fit.
All pure computation, zero I/O. Scores are 0.0-1.0 continuous (not issue-detection).
"""

from __future__ import annotations

from typing import Optional

from .models import CriticResult, SampleProfile, SampleIntent


# ── Music Theory Helpers ────────────────────────────────────────────

_NOTE_TO_NUM = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


def _parse_key_to_num(key_str: str) -> tuple[int, bool]:
    """Parse key string to (pitch_class, is_minor)."""
    if not key_str:
        return (-1, False)
    is_minor = key_str.endswith("m") and not key_str.endswith("maj")
    root = key_str.rstrip("m").rstrip("inor").rstrip("aj").rstrip("ajor")
    num = _NOTE_TO_NUM.get(root, -1)
    return (num, is_minor)


def _key_distance(key_a: str, key_b: str) -> int:
    """Compute musical distance between two keys (0-6 on circle of fifths)."""
    num_a, minor_a = _parse_key_to_num(key_a)
    num_b, minor_b = _parse_key_to_num(key_b)
    if num_a < 0 or num_b < 0:
        return 7  # unknown

    # Convert minor to relative major for comparison
    if minor_a:
        num_a = (num_a + 3) % 12
    if minor_b:
        num_b = (num_b + 3) % 12

    # Circle of fifths distance
    diff = (num_a - num_b) % 12
    fifths = min(
        _count_fifths(diff),
        _count_fifths(12 - diff),
    )
    return fifths


def _count_fifths(semitones: int) -> int:
    """Count steps on circle of fifths for a given semitone interval."""
    # Map: 0->0, 7->1, 2->2, 9->3, 4->4, 11->5, 6->6
    fifths_map = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6,
                  5: 1, 10: 2, 3: 3, 8: 4, 1: 5}
    return fifths_map.get(semitones % 12, 6)


# ── Critics ─────────────────────────────────────────────────────────


def run_key_fit_critic(
    profile: SampleProfile,
    song_key: Optional[str] = None,
) -> CriticResult:
    """Score how well the sample's key fits the song."""
    if profile.key is None:
        return CriticResult(
            critic_name="key_fit", score=0.0,
            recommendation="Key unknown — verify by ear",
        )
    if song_key is None:
        return CriticResult(
            critic_name="key_fit", score=0.5,
            recommendation="Song key unknown — cannot evaluate fit",
        )

    dist = _key_distance(profile.key, song_key)
    # Score: 0 fifths = 1.0, 1 = 0.85, 2 = 0.7, 3 = 0.55, 4 = 0.4, 5+ = 0.3
    score_map = {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.55, 4: 0.4, 5: 0.3, 6: 0.25}
    score = score_map.get(dist, 0.2)

    if score >= 0.8:
        rec = "Key matches well — load directly"
    elif score >= 0.6:
        rec = f"Closely related key — works for most intents"
    elif score >= 0.4:
        semitones = _suggest_transpose(profile.key, song_key)
        rec = f"Distant key — transpose {semitones:+d} semitones or use as texture"
    else:
        rec = "Chromatic clash — use with heavy filtering or as intentional tension"

    return CriticResult(critic_name="key_fit", score=score, recommendation=rec)


def _suggest_transpose(from_key: str, to_key: str) -> int:
    """Suggest semitone transpose to match target key."""
    num_from, _ = _parse_key_to_num(from_key)
    num_to, _ = _parse_key_to_num(to_key)
    if num_from < 0 or num_to < 0:
        return 0
    diff = (num_to - num_from) % 12
    return diff if diff <= 6 else diff - 12


def run_tempo_fit_critic(
    profile: SampleProfile,
    session_tempo: float = 120.0,
) -> CriticResult:
    """Score how well the sample's BPM fits the session tempo."""
    if profile.bpm is None:
        return CriticResult(
            critic_name="tempo_fit", score=0.0,
            recommendation="BPM unknown — estimate from onsets or verify manually",
        )

    bpm = profile.bpm
    # Check exact, half, double
    ratios = [bpm / session_tempo, bpm / (session_tempo * 2), bpm / (session_tempo / 2)]
    best_ratio = min(ratios, key=lambda r: abs(r - 1.0))
    deviation = abs(best_ratio - 1.0)

    if deviation < 0.01:
        score, rec = 1.0, "Exact tempo match — no warping needed"
    elif deviation < 0.02:
        score, rec = 0.95, f"Near-exact match — minimal warping"
    elif deviation < 0.05:
        score, rec = 0.8, f"Within 5% — light warp preserves quality"
    elif deviation < 0.10:
        score, rec = 0.6, f"Within 10% — moderate warp, choose mode carefully"
    elif deviation < 0.15:
        score, rec = 0.4, f"Within 15% — significant warp, use Texture mode for ambient"
    else:
        score, rec = 0.2, f"Extreme tempo mismatch — use as texture, not rhythmically"

    # Check if half/double time is the best match
    if abs(bpm / session_tempo - 0.5) < 0.05:
        score = max(score, 0.9)
        rec = "Half-time match — set warp accordingly"
    elif abs(bpm / session_tempo - 2.0) < 0.1:
        score = max(score, 0.9)
        rec = "Double-time match — set warp accordingly"

    return CriticResult(critic_name="tempo_fit", score=score, recommendation=rec)


def run_frequency_fit_critic(
    profile: SampleProfile,
    mix_snapshot: Optional[dict] = None,
) -> CriticResult:
    """Score frequency fit against existing mix.

    Without mix_snapshot (no M4L bridge), returns neutral 0.5.
    """
    if mix_snapshot is None:
        return CriticResult(
            critic_name="frequency_fit", score=0.5,
            recommendation="No spectral data — verify frequency fit by ear",
        )

    # With mix data: check where sample energy sits vs existing tracks
    # This is a simplified version — real implementation uses spectral overlap
    score = 0.5
    rec = "Frequency analysis requires spectral data from M4L bridge"
    return CriticResult(critic_name="frequency_fit", score=score, recommendation=rec)


def run_role_fit_critic(
    profile: SampleProfile,
    existing_roles: Optional[list[str]] = None,
) -> CriticResult:
    """Score whether this sample fills a missing role in the song."""
    if existing_roles is None:
        return CriticResult(
            critic_name="role_fit", score=0.5,
            recommendation="No role data available",
        )

    # Map material types to roles they fill
    role_map = {
        "vocal": ["vocal", "voice", "melody"],
        "drum_loop": ["drums", "percussion", "rhythm", "beat"],
        "one_shot": ["drums", "percussion", "hit"],
        "instrument_loop": ["synth", "keys", "guitar", "melody"],
        "texture": ["texture", "pad", "ambient", "atmosphere"],
        "foley": ["texture", "foley", "sfx"],
        "fx": ["fx", "transition", "riser"],
        "full_mix": [],
    }

    sample_roles = role_map.get(profile.material_type, [])
    existing_lower = [r.lower() for r in existing_roles]

    # Check for overlap
    overlap = sum(1 for r in sample_roles if any(r in e for e in existing_lower))

    if overlap == 0 and sample_roles:
        score = 1.0
        rec = f"Fills missing role — no existing {profile.material_type} in track"
    elif overlap == 0:
        score = 0.5
        rec = "Material type unclear for role analysis"
    elif overlap < len(sample_roles):
        score = 0.7
        rec = "Some role overlap — complements existing elements"
    else:
        score = 0.3
        rec = f"Redundant — already have {', '.join(existing_lower[:3])}. Use as texture instead"

    return CriticResult(critic_name="role_fit", score=score, recommendation=rec)


def run_vibe_fit_critic(
    profile: SampleProfile,
    taste_graph: object = None,
) -> CriticResult:
    """Score vibe fit using TasteGraph if available."""
    if taste_graph is None or not hasattr(taste_graph, "evidence_count"):
        return CriticResult(
            critic_name="vibe_fit", score=0.5,
            recommendation="No taste data — neutral score",
        )

    if taste_graph.evidence_count == 0:
        return CriticResult(
            critic_name="vibe_fit", score=0.5,
            recommendation="No taste evidence yet — neutral score",
        )

    # Use brightness and density as vibe indicators
    score = 0.5  # Enhanced in future with real taste comparison
    rec = "Taste comparison requires more evidence"
    return CriticResult(critic_name="vibe_fit", score=score, recommendation=rec)


def run_intent_fit_critic(
    profile: SampleProfile,
    intent: Optional[SampleIntent] = None,
) -> CriticResult:
    """Score how well the material serves the stated intent."""
    if intent is None:
        return CriticResult(
            critic_name="intent_fit", score=0.5,
            recommendation="No intent specified",
        )

    # Intent-material compatibility matrix
    compat: dict[str, dict[str, float]] = {
        "rhythm": {
            "drum_loop": 1.0, "one_shot": 0.9, "vocal": 0.6,
            "instrument_loop": 0.5, "full_mix": 0.4,
            "texture": 0.2, "foley": 0.5, "fx": 0.3,
        },
        "texture": {
            "texture": 1.0, "foley": 0.8, "vocal": 0.6,
            "drum_loop": 0.5, "instrument_loop": 0.6,
            "one_shot": 0.4, "fx": 0.7, "full_mix": 0.5,
        },
        "layer": {
            "instrument_loop": 1.0, "vocal": 0.8, "texture": 0.7,
            "drum_loop": 0.6, "one_shot": 0.3, "foley": 0.4,
        },
        "melody": {
            "instrument_loop": 1.0, "vocal": 0.9, "one_shot": 0.5,
            "texture": 0.3, "drum_loop": 0.2,
        },
        "vocal": {
            "vocal": 1.0, "instrument_loop": 0.3, "texture": 0.2,
        },
        "atmosphere": {
            "texture": 1.0, "foley": 0.9, "vocal": 0.5,
            "fx": 0.8, "full_mix": 0.4,
        },
        "transform": {
            # Everything is transformable — alchemist territory
            "vocal": 0.9, "drum_loop": 0.9, "instrument_loop": 0.9,
            "one_shot": 0.8, "texture": 0.8, "foley": 0.8,
            "fx": 0.7, "full_mix": 0.7,
        },
    }

    intent_scores = compat.get(intent.intent_type, {})
    score = intent_scores.get(profile.material_type, 0.4)

    if score >= 0.8:
        rec = f"Natural fit for {intent.intent_type}"
    elif score >= 0.6:
        rec = f"Works for {intent.intent_type} with some processing"
    elif score >= 0.4:
        rec = f"Creative use required for {intent.intent_type} — consider alchemist approach"
    else:
        rec = f"Unusual match — would need heavy transformation"

    return CriticResult(critic_name="intent_fit", score=score, recommendation=rec)


# ── Composite Runner ────────────────────────────────────────────────


def run_all_sample_critics(
    profile: SampleProfile,
    intent: Optional[SampleIntent] = None,
    song_key: Optional[str] = None,
    session_tempo: float = 120.0,
    existing_roles: Optional[list[str]] = None,
    mix_snapshot: Optional[dict] = None,
    taste_graph: object = None,
) -> dict[str, CriticResult]:
    """Run the full 6-critic battery. Returns dict keyed by critic name."""
    return {
        "key_fit": run_key_fit_critic(profile, song_key),
        "tempo_fit": run_tempo_fit_critic(profile, session_tempo),
        "frequency_fit": run_frequency_fit_critic(profile, mix_snapshot),
        "role_fit": run_role_fit_critic(profile, existing_roles),
        "vibe_fit": run_vibe_fit_critic(profile, taste_graph),
        "intent_fit": run_intent_fit_critic(profile, intent),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_critics.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot"
git add mcp_server/sample_engine/critics.py tests/test_sample_engine_critics.py
git commit -m "feat(sample-engine): add 6 sample critics — key, tempo, frequency, role, vibe, intent fit"
```

---

## Chunk 3: Techniques + Planner + MCP Tools

### Task 5: Technique Library

**Files:**
- Create: `mcp_server/sample_engine/techniques.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_sample_engine_planner.py (partial — techniques part)
"""Tests for Sample Engine techniques and planner."""

from __future__ import annotations

import pytest

from mcp_server.sample_engine.techniques import (
    get_technique,
    list_techniques,
    find_techniques,
)
from mcp_server.sample_engine.models import SampleProfile, SampleIntent


class TestTechniqueLibrary:
    def test_list_all(self):
        all_t = list_techniques()
        assert len(all_t) >= 20  # at least 20 techniques

    def test_get_by_id(self):
        t = get_technique("slice_and_sequence")
        assert t is not None
        assert t.technique_id == "slice_and_sequence"
        assert len(t.steps) > 0

    def test_find_by_material_and_intent(self):
        results = find_techniques(material_type="vocal", intent="rhythm")
        assert len(results) > 0
        assert any("vocal" in t.technique_id or "chop" in t.technique_id
                    for t in results)

    def test_find_texture_techniques(self):
        results = find_techniques(intent="texture")
        assert len(results) > 0

    def test_surgeon_vs_alchemist(self):
        surgeon = find_techniques(philosophy="surgeon")
        alchemist = find_techniques(philosophy="alchemist")
        assert len(surgeon) > 0
        assert len(alchemist) > 0
```

- [ ] **Step 2: Implement technique library**

Create `mcp_server/sample_engine/techniques.py` with all 30+ techniques. Each technique has real `TechniqueStep`s mapping to existing MCP tools. I'll include the full implementation inline — this is the craft knowledge corpus.

The file should define all techniques as module-level constants, register them in a `_CATALOG` dict, and expose `get_technique()`, `list_techniques()`, `find_techniques()`.

Key techniques to implement (all with real tool steps):
- `slice_and_sequence` — load → slice by transient → get slices → program MIDI
- `vocal_chop_rhythm` — load → slice by region → program staccato MIDI
- `micro_chop` — load → manual slices at 1/32 → random velocity MIDI
- `extreme_stretch` — load → set warp mode texture → slow down drastically
- `drum_to_pad` — load → reverse → stretch → add reverb
- `reverse_layer` — load → reverse → add delay tail
- `key_matched_layer` — analyze key → transpose → layer at -8dB
- `break_layering` — search browser → load → filter → blend under existing
- `serial_resample` — capture → re-load → process → capture → re-load (chain)
- `one_sample_challenge` — slice → extract kick/snare/hat/bass/pad from one sample

Each step references real tools: `load_sample_to_simpler`, `set_simpler_playback_mode`, `get_simpler_slices`, `add_notes`, `find_and_load_device`, `set_device_parameter`, `crop_simpler`, `reverse_simpler`, `warp_simpler`, etc.

- [ ] **Step 3: Run tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_planner.py::TestTechniqueLibrary -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add mcp_server/sample_engine/techniques.py
git commit -m "feat(sample-engine): add 30+ technique library — rhythmic, textural, melodic, vocal, resampling, constraints"
```

---

### Task 6: SamplePlanner

**Files:**
- Create: `mcp_server/sample_engine/planner.py`
- Test: `tests/test_sample_engine_planner.py` (add planner tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_sample_engine_planner.py`:

```python
from mcp_server.sample_engine.planner import (
    select_technique,
    compile_sample_plan,
)
from mcp_server.sample_engine.models import SampleProfile, SampleIntent, SampleFitReport
from mcp_server.sample_engine.critics import CriticResult


class TestSamplePlanner:
    def test_select_technique_drum_rhythm(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="drum_loop")
        intent = SampleIntent(intent_type="rhythm", description="chop it")
        technique = select_technique(profile, intent)
        assert technique is not None
        assert "rhythm" in technique.intents or "drum_loop" in technique.material_types

    def test_select_technique_vocal_texture(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="vocal")
        intent = SampleIntent(intent_type="texture", philosophy="alchemist",
                              description="stretch into pad")
        technique = select_technique(profile, intent)
        assert technique is not None
        assert technique.philosophy in ("alchemist", "both")

    def test_compile_plan_returns_tool_steps(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="drum_loop", bpm=128.0)
        intent = SampleIntent(intent_type="rhythm", description="")
        plan = compile_sample_plan(profile, intent, target_track=0)
        assert len(plan) > 0
        assert all("tool" in step for step in plan)

    def test_surgeon_vs_alchemist_plans_differ(self):
        profile = SampleProfile(source="t", file_path="/t.wav", name="t",
                                material_type="vocal")
        surgeon = compile_sample_plan(
            profile,
            SampleIntent(intent_type="layer", philosophy="surgeon", description=""),
            target_track=0,
        )
        alchemist = compile_sample_plan(
            profile,
            SampleIntent(intent_type="layer", philosophy="alchemist", description=""),
            target_track=0,
        )
        # Plans should differ in approach
        surgeon_tools = [s["tool"] for s in surgeon]
        alchemist_tools = [s["tool"] for s in alchemist]
        assert surgeon_tools != alchemist_tools or len(surgeon) != len(alchemist)
```

- [ ] **Step 2: Implement planner**

```python
# mcp_server/sample_engine/planner.py
"""SamplePlanner — technique selection and plan compilation.

Pure computation. Selects the best technique for a given sample + intent,
then compiles it into a concrete sequence of MCP tool calls.
"""

from __future__ import annotations

from typing import Optional

from .models import SampleProfile, SampleIntent, SampleTechnique
from .techniques import find_techniques, get_technique


def select_technique(
    profile: SampleProfile,
    intent: SampleIntent,
    taste_graph: object = None,
    recent_techniques: Optional[list[str]] = None,
) -> Optional[SampleTechnique]:
    """Select the best technique for this sample + intent.

    Scoring: material_match(0.3) + intent_match(0.3) + philosophy_match(0.2) +
             novelty_bonus(0.1) + taste_fit(0.1)
    """
    candidates = find_techniques(
        material_type=profile.material_type,
        intent=intent.intent_type,
        philosophy=intent.philosophy if intent.philosophy != "auto" else None,
    )

    if not candidates:
        # Broaden search — try without material filter
        candidates = find_techniques(intent=intent.intent_type)

    if not candidates:
        return None

    recent = set(recent_techniques or [])

    scored: list[tuple[SampleTechnique, float]] = []
    for t in candidates:
        score = 0.0

        # Material match
        if profile.material_type in t.material_types:
            score += 0.3
        elif "any" in t.material_types or not t.material_types:
            score += 0.15

        # Intent match
        if intent.intent_type in t.intents:
            score += 0.3
        elif any(i in t.intents for i in _related_intents(intent.intent_type)):
            score += 0.15

        # Philosophy match
        if intent.philosophy == "auto" or intent.philosophy == t.philosophy or t.philosophy == "both":
            score += 0.2
        elif intent.philosophy != t.philosophy:
            score += 0.05

        # Novelty bonus
        if t.technique_id not in recent:
            score += 0.1

        scored.append((t, score))

    scored.sort(key=lambda x: -x[1])
    return scored[0][0] if scored else None


def _related_intents(intent_type: str) -> list[str]:
    """Get related intents for broader matching."""
    relations = {
        "rhythm": ["layer", "transform"],
        "texture": ["atmosphere", "transform"],
        "layer": ["melody", "rhythm"],
        "melody": ["layer", "vocal"],
        "vocal": ["melody", "texture"],
        "atmosphere": ["texture"],
        "transform": ["texture", "rhythm", "atmosphere"],
        "challenge": ["transform"],
    }
    return relations.get(intent_type, [])


def compile_sample_plan(
    profile: SampleProfile,
    intent: SampleIntent,
    target_track: Optional[int] = None,
    technique: Optional[SampleTechnique] = None,
) -> list[dict]:
    """Compile a concrete tool-call plan for sample manipulation.

    Returns list of {tool, params, description} dicts ready for execution.
    """
    if technique is None:
        technique = select_technique(profile, intent)
    if technique is None:
        return _fallback_plan(profile, intent, target_track)

    plan: list[dict] = []

    for step in technique.steps:
        compiled_step = {
            "tool": step.tool,
            "params": _resolve_params(step.params, profile, intent, target_track),
            "description": step.description,
        }
        if step.condition:
            if not _evaluate_condition(step.condition, profile, intent):
                continue
        plan.append(compiled_step)

    return plan


def _resolve_params(
    params: dict,
    profile: SampleProfile,
    intent: SampleIntent,
    target_track: Optional[int],
) -> dict:
    """Resolve template variables in technique step params."""
    resolved = dict(params)
    replacements = {
        "{file_path}": profile.file_path,
        "{track_index}": target_track if target_track is not None else 0,
        "{material_type}": profile.material_type,
        "{key}": profile.key or "",
        "{bpm}": profile.bpm or 120.0,
        "{name}": profile.name,
    }
    for k, v in resolved.items():
        if isinstance(v, str):
            for template, value in replacements.items():
                v = v.replace(template, str(value))
            resolved[k] = v
        elif v == "{track_index}":
            resolved[k] = replacements["{track_index}"]
        elif v == "{file_path}":
            resolved[k] = replacements["{file_path}"]
    return resolved


def _evaluate_condition(condition: str, profile: SampleProfile,
                        intent: SampleIntent) -> bool:
    """Evaluate a simple condition string."""
    if "material_type" in condition:
        for mt in ("vocal", "drum_loop", "instrument_loop", "one_shot",
                   "texture", "foley", "fx", "full_mix"):
            if f'material_type == "{mt}"' in condition:
                return profile.material_type == mt
    if "philosophy" in condition:
        for p in ("surgeon", "alchemist"):
            if f'philosophy == "{p}"' in condition:
                return intent.philosophy == p
    return True


def _fallback_plan(
    profile: SampleProfile,
    intent: SampleIntent,
    target_track: Optional[int],
) -> list[dict]:
    """Generic fallback when no technique matches."""
    track = target_track if target_track is not None else 0
    return [
        {"tool": "load_sample_to_simpler",
         "params": {"track_index": track, "file_path": profile.file_path},
         "description": f"Load {profile.name} into Simpler"},
        {"tool": "set_simpler_playback_mode",
         "params": {"track_index": track, "device_index": 0,
                     "playback_mode": 2 if profile.suggested_mode == "slice" else 0},
         "description": f"Set Simpler to {profile.suggested_mode} mode"},
    ]
```

- [ ] **Step 3: Run tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_planner.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add mcp_server/sample_engine/planner.py tests/test_sample_engine_planner.py
git commit -m "feat(sample-engine): add SamplePlanner — technique selection and plan compilation"
```

---

### Task 7: MCP Tools

**Files:**
- Create: `mcp_server/sample_engine/tools.py`
- Modify: `mcp_server/server.py`
- Modify: `tests/test_tools_contract.py`

- [ ] **Step 1: Implement 6 MCP tools**

```python
# mcp_server/sample_engine/tools.py
"""Sample Engine MCP tools — 6 intelligence-layer tools.

No new Ableton communication — these orchestrate existing tools
through the analyzer, critics, planner, and technique library.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from .models import SampleProfile, SampleIntent, SampleFitReport, SampleCandidate
from .analyzer import build_profile_from_filename, parse_filename_metadata, classify_material_from_name
from .critics import run_all_sample_critics
from .planner import select_technique, compile_sample_plan
from .techniques import find_techniques, list_techniques, get_technique
from .sources import FilesystemSource, FreesoundSource, build_search_queries


@mcp.tool()
def analyze_sample(
    ctx: Context,
    file_path: Optional[str] = None,
    track_index: Optional[int] = None,
    clip_index: Optional[int] = None,
) -> dict:
    """Analyze a sample and build a complete SampleProfile.

    Detects material type, key, BPM, spectral character, and recommends
    Simpler mode, slice method, and warp mode. Provide either file_path
    OR track_index + clip_index to analyze a clip in the session.

    Falls back to filename-only analysis if M4L bridge unavailable.
    """
    if file_path is None and track_index is None:
        return {"error": "Provide either file_path or track_index + clip_index"}

    if track_index is not None:
        # Get file path from session clip
        try:
            ableton = ctx.lifespan_context["ableton"]
            clip_info = ableton.send_command("get_clip_info", {
                "track_index": track_index,
                "clip_index": clip_index or 0,
            })
            # Try to get file path via M4L bridge
            try:
                bridge = ctx.lifespan_context.get("m4l")
                if bridge:
                    import asyncio
                    result = asyncio.get_event_loop().run_until_complete(
                        bridge.send_command("get_clip_file_path", track_index, clip_index or 0)
                    )
                    if not result.get("error"):
                        file_path = result.get("file_path")
            except Exception:
                pass
        except Exception as exc:
            return {"error": f"Failed to read clip: {exc}"}

    if file_path is None:
        return {"error": "Could not determine file path — provide file_path directly"}

    profile = build_profile_from_filename(file_path, source="session_clip" if track_index is not None else "filesystem")
    return profile.to_dict()


@mcp.tool()
def evaluate_sample_fit(
    ctx: Context,
    file_path: str,
    intent: str = "layer",
    philosophy: str = "auto",
) -> dict:
    """Run the 6-critic battery to evaluate how well a sample fits the current song.

    Returns overall score, per-critic scores, recommendations, and
    both surgeon (precise) and alchemist (transformative) plans.

    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform
    philosophy: surgeon, alchemist, auto (context-decides)
    """
    profile = build_profile_from_filename(file_path)
    sample_intent = SampleIntent(
        intent_type=intent, philosophy=philosophy,
        description=f"Evaluate fitness for {intent}",
    )

    # Gather song context
    song_key = None
    session_tempo = 120.0
    existing_roles: list[str] = []

    try:
        ableton = ctx.lifespan_context["ableton"]
        info = ableton.send_command("get_session_info", {})
        session_tempo = info.get("tempo", 120.0)
    except Exception:
        pass

    try:
        ableton = ctx.lifespan_context["ableton"]
        # Get key from existing MIDI tracks
        from ..tools._theory_engine import detect_key
        for i in range(min(info.get("track_count", 0), 8)):
            try:
                clip_info = ableton.send_command("get_clip_info", {
                    "track_index": i, "clip_index": 0,
                })
                if clip_info.get("is_midi"):
                    notes = ableton.send_command("get_notes", {
                        "track_index": i, "clip_index": 0,
                    }).get("notes", [])
                    if notes:
                        key_result = detect_key(notes)
                        song_key = f"{key_result['tonic_name']}{key_result.get('mode', '')}"
                        break
            except Exception:
                continue
    except Exception:
        pass

    # Get existing track roles
    try:
        ableton = ctx.lifespan_context["ableton"]
        for i in range(min(info.get("track_count", 0), 16)):
            try:
                track_info = ableton.send_command("get_track_info", {"track_index": i})
                name = track_info.get("name", "").lower()
                if name:
                    existing_roles.append(name)
            except Exception:
                continue
    except Exception:
        pass

    critics = run_all_sample_critics(
        profile=profile,
        intent=sample_intent,
        song_key=song_key,
        session_tempo=session_tempo,
        existing_roles=existing_roles,
    )

    # Build surgeon and alchemist plans
    surgeon_plan = compile_sample_plan(
        profile,
        SampleIntent(intent_type=intent, philosophy="surgeon", description=""),
    )
    alchemist_plan = compile_sample_plan(
        profile,
        SampleIntent(intent_type=intent, philosophy="alchemist", description=""),
    )

    report = SampleFitReport(
        sample=profile,
        critics=critics,
        recommended_intent=intent,
        surgeon_plan=surgeon_plan,
        alchemist_plan=alchemist_plan,
        warnings=[c.recommendation for c in critics.values() if c.score < 0.5],
    )
    return report.to_dict()


@mcp.tool()
def search_samples(
    ctx: Context,
    query: str,
    material_type: Optional[str] = None,
    source: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """Search for samples across Ableton browser, local filesystem, and Freesound.

    query: search text like "dark vocal", "breakbeat", "foley metal"
    material_type: filter by type (vocal, drum_loop, texture, etc.)
    source: "browser", "filesystem", "freesound", or None for all
    max_results: maximum results to return (default 10)
    """
    results: list[dict] = []

    # Browser search
    if source in (None, "browser"):
        try:
            ableton = ctx.lifespan_context["ableton"]
            for path in ["samples", "drums", "user_library"]:
                try:
                    search_result = ableton.send_command("search_browser", {
                        "path": path,
                        "name_filter": query,
                        "loadable_only": True,
                        "max_results": max_results,
                    })
                    for item in search_result.get("results", []):
                        results.append({
                            "source": "browser",
                            "name": item.get("name", ""),
                            "uri": item.get("uri", ""),
                            "path": f"{path}/{item.get('name', '')}",
                        })
                except Exception:
                    continue
        except Exception:
            pass

    # Filesystem search
    if source in (None, "filesystem"):
        fs = FilesystemSource(scan_paths=[
            "~/Music", "~/Documents/Samples",
            "~/Documents/LivePilot/downloads",
        ])
        fs_results = fs.search(query, max_results=max_results)
        for candidate in fs_results:
            results.append(candidate.to_dict())

    # Freesound (metadata only — no download)
    if source in (None, "freesound"):
        fs_source = FreesoundSource()
        if fs_source.enabled:
            params = fs_source.build_search_params(query, max_results)
            results.append({
                "source": "freesound",
                "note": "Freesound search available — use API params to query",
                "search_params": params,
            })

    return {
        "query": query,
        "result_count": len(results),
        "results": results[:max_results],
    }


@mcp.tool()
def suggest_sample_technique(
    ctx: Context,
    file_path: str,
    intent: str = "rhythm",
    philosophy: str = "auto",
    max_suggestions: int = 3,
) -> dict:
    """Suggest sample manipulation techniques from the library.

    Returns ranked techniques with executable step outlines.

    file_path: path to the sample
    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform, challenge
    philosophy: surgeon, alchemist, auto
    """
    profile = build_profile_from_filename(file_path)
    sample_intent = SampleIntent(
        intent_type=intent, philosophy=philosophy, description="",
    )

    candidates = find_techniques(
        material_type=profile.material_type,
        intent=intent,
        philosophy=philosophy if philosophy != "auto" else None,
    )

    if not candidates:
        candidates = find_techniques(intent=intent)

    suggestions = []
    for t in candidates[:max_suggestions]:
        steps = compile_sample_plan(profile, sample_intent, technique=t)
        suggestions.append({
            "technique_id": t.technique_id,
            "name": t.name,
            "philosophy": t.philosophy,
            "difficulty": t.difficulty,
            "description": t.description,
            "inspiration": t.inspiration,
            "step_count": len(steps),
            "steps_preview": [s["description"] for s in steps[:5]],
        })

    return {
        "sample": profile.name,
        "material_type": profile.material_type,
        "intent": intent,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
    }


@mcp.tool()
def plan_sample_workflow(
    ctx: Context,
    file_path: Optional[str] = None,
    search_query: Optional[str] = None,
    intent: str = "rhythm",
    philosophy: str = "auto",
    target_track: Optional[int] = None,
) -> dict:
    """Full end-to-end sample workflow: analyze + critique + plan.

    Provide file_path for a known sample, or search_query to find one.
    Returns a complete compiled plan ready for execution.

    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform
    philosophy: surgeon, alchemist, auto
    target_track: existing track index, or None for new track
    """
    if file_path is None and search_query is None:
        return {"error": "Provide either file_path or search_query"}

    profile = None
    if file_path:
        profile = build_profile_from_filename(file_path)

    sample_intent = SampleIntent(
        intent_type=intent, philosophy=philosophy,
        description=search_query or f"Process {file_path} for {intent}",
        target_track=target_track,
    )

    plan = compile_sample_plan(
        profile or SampleProfile(source="search", file_path="", name=search_query or ""),
        sample_intent,
        target_track=target_track,
    )

    return {
        "sample": profile.to_dict() if profile else {"search_query": search_query},
        "intent": intent,
        "philosophy": philosophy,
        "technique": plan[0].get("description", "") if plan else "No technique found",
        "step_count": len(plan),
        "compiled_plan": plan,
    }


@mcp.tool()
def get_sample_opportunities(ctx: Context) -> dict:
    """Analyze current song and identify where samples could improve it.

    Returns opportunities with suggested material types and techniques.
    Used by Wonder Mode diagnosis for sample-aware creative rescue.
    """
    opportunities: list[dict] = []

    try:
        ableton = ctx.lifespan_context["ableton"]
        info = ableton.send_command("get_session_info", {})
    except Exception:
        return {"opportunities": [], "note": "Cannot read session — Ableton not connected"}

    track_count = info.get("track_count", 0)
    track_names: list[str] = []
    has_sampler = False

    for i in range(min(track_count, 16)):
        try:
            track_info = ableton.send_command("get_track_info", {"track_index": i})
            name = track_info.get("name", "").lower()
            track_names.append(name)
            devices = track_info.get("devices", [])
            for d in devices:
                if d.get("class_name") in ("OriginalSimpler", "MultiSampler"):
                    has_sampler = True
        except Exception:
            continue

    # Check for missing organic texture
    has_organic = any(
        kw in name for name in track_names
        for kw in ("vocal", "sample", "foley", "field", "organic", "found")
    )
    if not has_organic and track_count >= 3:
        opportunities.append({
            "type": "missing_organic_texture",
            "description": "No organic/sampled textures — all tracks appear synthesized",
            "suggested_material": ["vocal", "foley", "texture"],
            "suggested_techniques": ["vocal_chop_rhythm", "phone_recording_texture", "tail_harvest"],
            "confidence": 0.6,
        })

    # Check for drum variety
    drum_tracks = [n for n in track_names if any(
        kw in n for kw in ("drum", "beat", "perc", "kick", "snare")
    )]
    if len(drum_tracks) <= 1 and track_count >= 4:
        opportunities.append({
            "type": "drum_variety_needed",
            "description": "Limited percussion variety — try layering a break or adding ghost notes",
            "suggested_material": ["drum_loop"],
            "suggested_techniques": ["break_layering", "ghost_note_texture"],
            "confidence": 0.5,
        })

    # Check for no sampler usage
    if not has_sampler and track_count >= 2:
        opportunities.append({
            "type": "no_sample_instruments",
            "description": "No Simpler/Sampler devices — samples could add character",
            "suggested_material": ["vocal", "instrument_loop", "one_shot"],
            "suggested_techniques": ["syllable_instrument", "slice_and_sequence"],
            "confidence": 0.4,
        })

    return {
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
        "track_count": track_count,
    }
```

- [ ] **Step 2: Register in server.py**

Add to `mcp_server/server.py` after the sound_design import:

```python
from .sample_engine import tools as sample_engine_tools  # noqa: F401, E402
```

- [ ] **Step 3: Add tool contract test**

Add to `tests/test_tools_contract.py`:

```python
def test_sample_engine_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_sample",
        "evaluate_sample_fit",
        "search_samples",
        "suggest_sample_technique",
        "plan_sample_workflow",
        "get_sample_opportunities",
    }
    missing = expected - names
    assert not missing, f"Missing sample engine tools: {missing}"
```

- [ ] **Step 4: Run contract test**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_tools_contract.py::test_sample_engine_tools_registered -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/sample_engine/tools.py mcp_server/server.py tests/test_tools_contract.py
git commit -m "feat(sample-engine): add 6 MCP tools and register in server"
```

---

## Chunk 4: Semantic Moves + Wonder Mode + Skill Files

### Task 8: Semantic Moves for Wonder Mode

**Files:**
- Create: `mcp_server/sample_engine/moves.py`
- Create: `mcp_server/semantic_moves/sample_compilers.py`
- Modify: `mcp_server/semantic_moves/__init__.py`
- Test: `tests/test_sample_engine_moves.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_sample_engine_moves.py
"""Tests for sample-domain semantic moves."""

from __future__ import annotations

from mcp_server.semantic_moves.registry import list_moves, get_move


class TestSampleMoves:
    def test_sample_moves_registered(self):
        sample_moves = list_moves(domain="sample")
        assert len(sample_moves) >= 6

    def test_chop_rhythm_exists(self):
        m = get_move("sample_chop_rhythm")
        assert m is not None
        assert m.family == "sample"
        assert len(m.compile_plan) > 0

    def test_texture_layer_exists(self):
        m = get_move("sample_texture_layer")
        assert m is not None

    def test_vocal_ghost_exists(self):
        m = get_move("sample_vocal_ghost")
        assert m is not None

    def test_all_sample_moves_have_compile_plans(self):
        sample_moves = list_moves(domain="sample")
        for move_dict in sample_moves:
            full = get_move(move_dict["move_id"])
            assert full is not None
            assert full.compile_plan, f"{move_dict['move_id']} has no compile_plan"
```

- [ ] **Step 2: Implement moves**

Create `mcp_server/sample_engine/moves.py` with 6 SemanticMove definitions following `sound_design_moves.py` pattern.

Create `mcp_server/semantic_moves/sample_compilers.py` following `sound_design_compilers.py` pattern — compilers that read session state and produce concrete tool steps.

- [ ] **Step 3: Register in semantic_moves/__init__.py**

Add to `mcp_server/semantic_moves/__init__.py`:

```python
from ..sample_engine import moves as sample_moves  # noqa: F401
from . import sample_compilers  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_moves.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/sample_engine/moves.py mcp_server/semantic_moves/sample_compilers.py mcp_server/semantic_moves/__init__.py tests/test_sample_engine_moves.py
git commit -m "feat(sample-engine): add 6 Wonder Mode semantic moves + compilers"
```

---

### Task 9: Wonder Mode Diagnosis Patches

**Files:**
- Modify: `mcp_server/wonder_mode/diagnosis.py`

- [ ] **Step 1: Add sample entries to _DOMAIN_MAP**

Add to `_DOMAIN_MAP` dict in `mcp_server/wonder_mode/diagnosis.py`:

```python
"no_organic_texture": ["sample", "sound_design"],
"stale_drums": ["sample", "arrangement"],
"vocal_processing_monotony": ["sample", "sound_design"],
"dense_but_static": ["sample", "mix"],
```

- [ ] **Step 2: Run existing wonder mode tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_wonder_diagnosis.py -v`
Expected: ALL PASS (no regression)

- [ ] **Step 3: Commit**

```bash
git add mcp_server/wonder_mode/diagnosis.py
git commit -m "feat(wonder-mode): add sample domain to diagnosis _DOMAIN_MAP"
```

---

### Task 10: Skill Files

**Files:**
- Create: `livepilot/skills/livepilot-sample-engine/SKILL.md`
- Create: `livepilot/skills/livepilot-sample-engine/references/sample-techniques.md`
- Create: `livepilot/skills/livepilot-sample-engine/references/sample-critics.md`
- Create: `livepilot/skills/livepilot-sample-engine/references/sample-philosophy.md`

- [ ] **Step 1: Create SKILL.md**

The skill triggers on sample-related keywords and describes the full workflow. Follow the pattern of `livepilot-sound-design-engine/SKILL.md`.

- [ ] **Step 2: Create reference docs**

Move the technique catalog, critic details, and philosophy guide from the spec into the reference files.

- [ ] **Step 3: Commit**

```bash
git add livepilot/skills/livepilot-sample-engine/
git commit -m "feat(skills): add livepilot-sample-engine skill with technique/critic/philosophy references"
```

---

### Task 11: Tool Count Updates + Final Cleanup

**Files:**
- Multiple per CLAUDE.md tool count rules

- [ ] **Step 1: Update tool count from 297 to 303 (297 + 6) in all locations**

Per CLAUDE.md, update these files:
- `README.md`
- `package.json` description
- `livepilot/.Codex-plugin/plugin.json`
- `livepilot/.claude-plugin/plugin.json`
- `server.json`
- `livepilot/skills/livepilot-core/SKILL.md`
- `livepilot/skills/livepilot-core/references/overview.md`
- `CLAUDE.md`
- `CHANGELOG.md`
- `tests/test_tools_contract.py` (first line docstring)
- `docs/manual/index.md`
- `docs/manual/tool-reference.md`

Also update domain count if 40 → 41 (new "sample_engine" domain).

- [ ] **Step 2: Update CHANGELOG.md**

Add entry for the sample engine feature.

- [ ] **Step 3: Run full test suite**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_sample_engine_*.py tests/test_tools_contract.py -v`
Expected: ALL PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(sample-engine): update tool count 297→303, add domain, update changelog"
```

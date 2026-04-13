# Device Atlas v2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an embedded JSON device database with 1400+ entries covering every device in Live 12.3.6, with curated sonic intelligence for stock devices, and 6 new MCP query tools.

**Architecture:** Scanner walks Ableton's browser tree via a new Remote Script command, producing a raw inventory. YAML enrichment files add sonic descriptions, parameter guides, and recipes for stock devices. Both merge into `device_atlas.json`, loaded at startup by `AtlasManager`. Six new MCP tools expose search, suggest, and compare capabilities.

**Tech Stack:** Python, FastMCP, PyYAML, JSON. No new external dependencies.

**Spec:** `docs/superpowers/specs/2026-04-13-device-atlas-v2-design.md`

---

## Chunk 1: AtlasManager Core + Tests

### Task 1: AtlasManager data loading and indexing

**Files:**
- Create: `mcp_server/atlas/__init__.py`
- Create: `tests/test_atlas_manager.py`

- [ ] **Step 1: Write test for AtlasManager loading**

```python
# tests/test_atlas_manager.py
"""Tests for AtlasManager — in-memory device atlas with indexed lookups."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.atlas import AtlasManager


SAMPLE_ATLAS = {
    "version": "2.0.0",
    "live_version": "12.3.6",
    "scanned_at": "2026-04-13T12:00:00Z",
    "stats": {"total_devices": 3, "instruments": 2, "audio_effects": 1},
    "devices": [
        {
            "id": "drift",
            "name": "Drift",
            "uri": "query:Synths#Drift",
            "category": "instruments",
            "subcategory": "synths",
            "source": "native",
            "enriched": True,
            "sonic_description": "Analog-modeled synth with built-in instability",
            "character_tags": ["warm", "organic", "analog"],
            "use_cases": ["bass", "leads", "pads"],
            "genre_affinity": {"primary": ["techno", "house"], "secondary": ["ambient"]},
            "complexity": "beginner",
            "self_contained": True,
            "key_parameters": [
                {"name": "Shape", "range": [0.0, 1.0], "type": "float"},
                {"name": "Drift", "range": [0.0, 1.0], "type": "float"},
            ],
            "pairs_well_with": [{"device": "Chorus-Ensemble", "reason": "width"}],
            "starter_recipes": [
                {"name": "Deep Sub", "params": {"Shape": 0.0, "Drift": 0.1}, "genre": "techno"}
            ],
            "gotchas": ["High Drift = unpredictable pitch"],
            "health_flags": [],
        },
        {
            "id": "wavetable",
            "name": "Wavetable",
            "uri": "query:Synths#Wavetable",
            "category": "instruments",
            "subcategory": "synths",
            "source": "native",
            "enriched": True,
            "sonic_description": "Versatile wavetable synth with morphing",
            "character_tags": ["versatile", "modern", "bright"],
            "use_cases": ["bass", "leads", "pads", "keys"],
            "genre_affinity": {"primary": ["edm", "pop"], "secondary": ["techno"]},
            "complexity": "intermediate",
            "self_contained": True,
            "key_parameters": [],
            "pairs_well_with": [],
            "starter_recipes": [],
            "gotchas": [],
            "health_flags": [],
        },
        {
            "id": "compressor",
            "name": "Compressor",
            "uri": "query:AudioFx#Compressor",
            "category": "audio_effects",
            "subcategory": "dynamics",
            "source": "native",
            "enriched": True,
            "sonic_description": "Transparent dynamics control",
            "character_tags": ["dynamics", "transparent", "punchy"],
            "use_cases": ["mixing", "mastering", "sidechain"],
            "genre_affinity": {"primary": ["all"], "secondary": []},
            "complexity": "beginner",
            "self_contained": True,
            "key_parameters": [],
            "pairs_well_with": [],
            "starter_recipes": [],
            "gotchas": [],
            "health_flags": [],
        },
    ],
    "packs": [],
}


def _write_atlas(data=None):
    """Write sample atlas to a temp file and return path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data or SAMPLE_ATLAS, f)
    f.close()
    return f.name


def test_load_atlas():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        assert mgr.stats["total_devices"] == 3
        assert mgr.stats["instruments"] == 2
    finally:
        os.unlink(path)


def test_lookup_by_id():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        entry = mgr.lookup("drift")
        assert entry is not None
        assert entry["name"] == "Drift"
    finally:
        os.unlink(path)


def test_lookup_by_name_case_insensitive():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        entry = mgr.lookup("DRIFT")
        assert entry is not None
        assert entry["id"] == "drift"
    finally:
        os.unlink(path)


def test_lookup_miss_returns_none():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        assert mgr.lookup("nonexistent") is None
    finally:
        os.unlink(path)


def test_lookup_by_uri():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        entry = mgr.by_uri.get("query:Synths#Drift")
        assert entry is not None
        assert entry["id"] == "drift"
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.atlas'`

- [ ] **Step 3: Implement AtlasManager**

```python
# mcp_server/atlas/__init__.py
"""Device Atlas v2 — embedded knowledge database for LivePilot.

Loads device_atlas.json at startup, builds in-memory indexes for fast
name/category/tag/genre lookups. Pure data — no I/O after __init__.
"""

from __future__ import annotations

import json
import os
from typing import Optional


class AtlasManager:
    """In-memory device atlas with indexed lookups."""

    def __init__(self, atlas_path: str):
        with open(atlas_path, "r") as f:
            self.data = json.load(f)
        self._devices: list[dict] = self.data.get("devices", [])
        self._packs: list[dict] = self.data.get("packs", [])
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes from device list."""
        self.by_id: dict[str, dict] = {}
        self.by_name: dict[str, list[dict]] = {}
        self.by_category: dict[str, list[dict]] = {}
        self.by_tag: dict[str, list[dict]] = {}
        self.by_genre: dict[str, list[dict]] = {}
        self.by_uri: dict[str, dict] = {}

        for device in self._devices:
            did = device.get("id", "")
            name = device.get("name", "")
            uri = device.get("uri", "")
            category = device.get("category", "")

            if did:
                self.by_id[did] = device
            if name:
                key = name.lower()
                self.by_name.setdefault(key, []).append(device)
            if uri:
                self.by_uri[uri] = device
            if category:
                self.by_category.setdefault(category, []).append(device)

            for tag in device.get("character_tags", []):
                self.by_tag.setdefault(tag.lower(), []).append(device)

            affinity = device.get("genre_affinity", {})
            for genre in affinity.get("primary", []) + affinity.get("secondary", []):
                self.by_genre.setdefault(genre.lower(), []).append(device)

    def lookup(self, name_or_id: str) -> Optional[dict]:
        """Exact lookup by ID or name (case-insensitive). Returns None on miss."""
        lowered = name_or_id.strip().lower()
        # Try ID first
        if lowered in self.by_id:
            return self.by_id[lowered]
        # Try name
        matches = self.by_name.get(lowered)
        if matches:
            return matches[0]
        return None

    @property
    def stats(self) -> dict:
        """Atlas statistics from the header."""
        return self.data.get("stats", {})

    @property
    def version(self) -> str:
        return self.data.get("version", "0.0.0")

    @property
    def device_count(self) -> int:
        return len(self._devices)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_manager.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```
git add mcp_server/atlas/__init__.py tests/test_atlas_manager.py
git commit -m "feat(atlas): add AtlasManager with indexed lookups and tests"
```

### Task 2: AtlasManager search method

**Files:**
- Modify: `mcp_server/atlas/__init__.py`
- Modify: `tests/test_atlas_manager.py`

- [ ] **Step 1: Write search tests**

Append to `tests/test_atlas_manager.py`:

```python
def test_search_by_name():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("drift")
        assert len(results) >= 1
        assert results[0]["id"] == "drift"
    finally:
        os.unlink(path)


def test_search_by_tag():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("warm")
        assert any(r["id"] == "drift" for r in results)
    finally:
        os.unlink(path)


def test_search_by_use_case():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("bass")
        ids = [r["id"] for r in results]
        assert "drift" in ids
        assert "wavetable" in ids
    finally:
        os.unlink(path)


def test_search_by_genre():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("techno")
        assert any(r["id"] == "drift" for r in results)
    finally:
        os.unlink(path)


def test_search_by_category_filter():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("dynamics", category="audio_effects")
        assert all(r["category"] == "audio_effects" for r in results)
    finally:
        os.unlink(path)


def test_search_respects_limit():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("bass", limit=1)
        assert len(results) == 1
    finally:
        os.unlink(path)


def test_search_no_results():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("zzzznonexistent")
        assert results == []
    finally:
        os.unlink(path)


def test_search_description_match():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.search("instability")
        assert any(r["id"] == "drift" for r in results)
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_manager.py::test_search_by_name -v`
Expected: FAIL — `AttributeError: 'AtlasManager' object has no attribute 'search'`

- [ ] **Step 3: Implement search method**

Add to `AtlasManager` class in `mcp_server/atlas/__init__.py`:

```python
    def search(self, query: str, category: str = "all", limit: int = 10) -> list[dict]:
        """Multi-signal search: name, tags, description, use cases, genre.

        Returns devices ranked by relevance score, highest first.
        """
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        scored: list[tuple[float, dict]] = []
        query_words = query_lower.split()

        for device in self._devices:
            if category != "all" and device.get("category") != category:
                continue

            score = 0.0
            name_lower = device.get("name", "").lower()
            did = device.get("id", "").lower()

            # Exact name match
            if name_lower == query_lower or did == query_lower:
                score += 100.0
            # Name substring
            elif query_lower in name_lower or query_lower in did:
                score += 50.0

            # Character tag match
            tags = [t.lower() for t in device.get("character_tags", [])]
            for word in query_words:
                if word in tags:
                    score += 30.0

            # Use case match
            use_cases = [u.lower() for u in device.get("use_cases", [])]
            for word in query_words:
                if word in use_cases:
                    score += 25.0

            # Genre match
            affinity = device.get("genre_affinity", {})
            primary = [g.lower() for g in affinity.get("primary", [])]
            secondary = [g.lower() for g in affinity.get("secondary", [])]
            for word in query_words:
                if word in primary:
                    score += 20.0
                elif word in secondary:
                    score += 10.0

            # Sonic description keyword
            desc = device.get("sonic_description", "").lower()
            for word in query_words:
                if word in desc:
                    score += 15.0

            # Subcategory match
            subcat = device.get("subcategory", "").lower()
            if query_lower in subcat:
                score += 10.0

            if score > 0:
                scored.append((score, device))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [device for _, device in scored[:limit]]
```

- [ ] **Step 4: Run all search tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_manager.py -v`
Expected: 13 PASSED

- [ ] **Step 5: Commit**

```
git add mcp_server/atlas/__init__.py tests/test_atlas_manager.py
git commit -m "feat(atlas): add multi-signal search to AtlasManager"
```

### Task 3: AtlasManager suggest and chain_suggest methods

**Files:**
- Modify: `mcp_server/atlas/__init__.py`
- Modify: `tests/test_atlas_manager.py`

- [ ] **Step 1: Write suggest tests**

Append to `tests/test_atlas_manager.py`:

```python
def test_suggest_returns_ranked_devices():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.suggest("warm bass", genre="techno")
        assert len(results) >= 1
        # Drift should rank high for warm bass in techno
        assert results[0]["device"]["id"] == "drift"
        assert "rationale" in results[0]
    finally:
        os.unlink(path)


def test_suggest_includes_recipe_when_available():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        results = mgr.suggest("bass", genre="techno")
        drift_result = next((r for r in results if r["device"]["id"] == "drift"), None)
        assert drift_result is not None
        assert drift_result.get("recipe") is not None
    finally:
        os.unlink(path)


def test_chain_suggest_returns_ordered_chain():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        result = mgr.chain_suggest("bass", genre="techno")
        assert "chain" in result
        assert len(result["chain"]) >= 1
        # Should have at least an instrument
        positions = [c["position"] for c in result["chain"]]
        assert "instrument" in positions
    finally:
        os.unlink(path)


def test_compare_returns_comparison():
    path = _write_atlas()
    try:
        mgr = AtlasManager(path)
        result = mgr.compare("drift", "wavetable", role="bass")
        assert "device_a" in result
        assert "device_b" in result
        assert "recommendation" in result
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_manager.py::test_suggest_returns_ranked_devices -v`
Expected: FAIL — `AttributeError: 'AtlasManager' object has no attribute 'suggest'`

- [ ] **Step 3: Implement suggest, chain_suggest, and compare**

Add to `AtlasManager` in `mcp_server/atlas/__init__.py`:

```python
    def suggest(self, intent: str, genre: str = "", energy: str = "medium", limit: int = 5) -> list[dict]:
        """Intent-driven device suggestion with rationale and recipe matching.

        Returns list of {device, rationale, recipe (if available)}.
        """
        # Search for matching devices
        query_parts = intent.split()
        if genre:
            query_parts.append(genre)
        candidates = self.search(" ".join(query_parts), limit=limit * 2)

        results = []
        for device in candidates[:limit]:
            entry: dict = {"device": device, "rationale": "", "recipe": None}

            # Build rationale
            reasons = []
            name = device.get("name", "")
            desc = device.get("sonic_description", "")
            if desc:
                reasons.append(desc.split(".")[0])
            tags = device.get("character_tags", [])
            if tags:
                reasons.append(f"Character: {', '.join(tags[:3])}")
            entry["rationale"] = ". ".join(reasons) if reasons else f"{name} matches your intent"

            # Find best matching recipe
            intent_lower = intent.lower()
            genre_lower = genre.lower()
            for recipe in device.get("starter_recipes", []):
                recipe_name = recipe.get("name", "").lower()
                recipe_genre = recipe.get("genre", "").lower()
                if (any(w in recipe_name for w in intent_lower.split())
                        or recipe_genre == genre_lower):
                    entry["recipe"] = recipe
                    break
            # Fallback: first recipe if any exist
            if entry["recipe"] is None and device.get("starter_recipes"):
                entry["recipe"] = device["starter_recipes"][0]

            results.append(entry)

        return results

    def chain_suggest(self, role: str, genre: str = "") -> dict:
        """Suggest a full device chain for a track role.

        Returns {role, genre, chain: [{position, device, reason}]}.
        """
        chain: list[dict] = []

        # Find instrument for the role
        instrument_candidates = self.search(
            f"{role} {genre}".strip(), category="instruments", limit=3
        )
        if instrument_candidates:
            best = instrument_candidates[0]
            chain.append({
                "position": "instrument",
                "device": best["name"],
                "device_id": best["id"],
                "reason": best.get("sonic_description", "Best match for role")[:80],
            })

        # Find complementary effects
        # Use pairs_well_with from the instrument if available
        if instrument_candidates:
            pairs = instrument_candidates[0].get("pairs_well_with", [])
            for pair in pairs[:3]:
                chain.append({
                    "position": "effect",
                    "device": pair["device"],
                    "reason": pair.get("reason", "Complements instrument"),
                })

        # Fallback: suggest common effects for the role
        if len(chain) < 2:
            role_effects = {
                "bass": ["Compressor", "Saturator", "EQ Eight"],
                "lead": ["Reverb", "Delay", "Compressor"],
                "pad": ["Reverb", "Chorus-Ensemble", "EQ Eight"],
                "drums": ["Drum Buss", "Compressor", "EQ Eight"],
                "percussion": ["Compressor", "Saturator", "Delay"],
                "texture": ["Reverb", "Spectral Blur", "Auto Filter"],
            }
            for fx_name in role_effects.get(role.lower(), ["Compressor", "EQ Eight"]):
                fx = self.lookup(fx_name)
                if fx:
                    chain.append({
                        "position": "effect",
                        "device": fx["name"],
                        "device_id": fx["id"],
                        "reason": f"Standard {role} processing",
                    })

        return {"role": role, "genre": genre, "chain": chain}

    def compare(self, device_a: str, device_b: str, role: str = "") -> dict:
        """Side-by-side comparison of two devices."""
        a = self.lookup(device_a)
        b = self.lookup(device_b)

        result: dict = {
            "device_a": {"name": device_a, "found": a is not None},
            "device_b": {"name": device_b, "found": b is not None},
            "recommendation": "",
        }

        if a:
            result["device_a"].update({
                "sonic_description": a.get("sonic_description", ""),
                "character_tags": a.get("character_tags", []),
                "use_cases": a.get("use_cases", []),
                "complexity": a.get("complexity", ""),
                "genre_affinity": a.get("genre_affinity", {}),
            })
        if b:
            result["device_b"].update({
                "sonic_description": b.get("sonic_description", ""),
                "character_tags": b.get("character_tags", []),
                "use_cases": b.get("use_cases", []),
                "complexity": b.get("complexity", ""),
                "genre_affinity": b.get("genre_affinity", {}),
            })

        # Recommendation based on role match
        if a and b and role:
            role_lower = role.lower()
            a_score = 1 if role_lower in [u.lower() for u in a.get("use_cases", [])] else 0
            b_score = 1 if role_lower in [u.lower() for u in b.get("use_cases", [])] else 0
            if a_score > b_score:
                result["recommendation"] = f"{a['name']} is better suited for {role}"
            elif b_score > a_score:
                result["recommendation"] = f"{b['name']} is better suited for {role}"
            else:
                result["recommendation"] = f"Both work for {role} — choose by character preference"
        elif a and b:
            result["recommendation"] = "Both are viable — depends on the sonic character you want"

        return result
```

- [ ] **Step 4: Run all tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_manager.py -v`
Expected: 17 PASSED

- [ ] **Step 5: Commit**

```
git add mcp_server/atlas/__init__.py tests/test_atlas_manager.py
git commit -m "feat(atlas): add suggest, chain_suggest, and compare methods"
```

---

## Chunk 2: Browser Scanner + Remote Script

### Task 4: Remote Script `scan_browser_deep` command

**Files:**
- Modify: `remote_script/LivePilot/browser.py`

- [ ] **Step 1: Add scan_browser_deep handler**

Add to `remote_script/LivePilot/browser.py` after the existing `search_browser` handler:

```python
@register("scan_browser_deep")
def scan_browser_deep(song, params):
    """Walk the entire browser tree and return all loadable items.

    Returns a flat list of items per category for atlas building.
    max_per_category limits items per category (default 1000).
    """
    browser = _get_browser()
    categories = _get_categories(browser)
    max_per_cat = int(params.get("max_per_category", 1000))

    result = {}
    for cat_name, cat_item in categories.items():
        items = []
        _scan_recursive(cat_item, items, depth=0, max_depth=4,
                        max_items=max_per_cat)
        result[cat_name] = items

    return {"categories": result}


def _scan_recursive(item, results, depth, max_depth, max_items, _counter=None):
    """Recursively collect all loadable items under a browser node."""
    if _counter is None:
        _counter = [0]
    if depth > max_depth or len(results) >= max_items:
        return
    try:
        children = list(item.children)
    except (AttributeError, RuntimeError):
        return
    for child in children:
        _counter[0] += 1
        if _counter[0] > 100000 or len(results) >= max_items:
            return
        if child.is_loadable:
            results.append({
                "name": child.name,
                "uri": child.uri if hasattr(child, "uri") else "",
                "is_loadable": True,
            })
        _scan_recursive(child, results, depth + 1, max_depth, max_items, _counter)
```

- [ ] **Step 2: Commit**

```
git add remote_script/LivePilot/browser.py
git commit -m "feat(remote): add scan_browser_deep command for atlas scanning"
```

### Task 5: MCP scanner module

**Files:**
- Create: `mcp_server/atlas/scanner.py`
- Create: `tests/test_atlas_scanner.py`

- [ ] **Step 1: Write scanner test**

```python
# tests/test_atlas_scanner.py
"""Tests for atlas scanner — transforms raw browser data into atlas format."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.atlas.scanner import normalize_scan_results, make_device_id


def test_make_device_id_simple():
    assert make_device_id("Drift") == "drift"


def test_make_device_id_spaces():
    assert make_device_id("EQ Eight") == "eq_eight"


def test_make_device_id_special_chars():
    assert make_device_id("Chorus-Ensemble") == "chorus_ensemble"


def test_make_device_id_plugin():
    assert make_device_id("Model D", prefix="auv3_moog") == "auv3_moog_model_d"


def test_normalize_instruments():
    raw = {
        "categories": {
            "instruments": [
                {"name": "Drift", "uri": "query:Synths#Drift", "is_loadable": True},
                {"name": "Analog", "uri": "query:Synths#Analog", "is_loadable": True},
            ],
            "audio_effects": [],
        }
    }
    devices = normalize_scan_results(raw)
    assert len(devices) == 2
    drift = next(d for d in devices if d["id"] == "drift")
    assert drift["category"] == "instruments"
    assert drift["uri"] == "query:Synths#Drift"
    assert drift["enriched"] is False


def test_normalize_audio_effects():
    raw = {
        "categories": {
            "instruments": [],
            "audio_effects": [
                {"name": "Compressor", "uri": "query:AudioFx#Compressor", "is_loadable": True},
            ],
        }
    }
    devices = normalize_scan_results(raw)
    assert len(devices) == 1
    assert devices[0]["category"] == "audio_effects"


def test_normalize_deduplicates_by_uri():
    raw = {
        "categories": {
            "instruments": [
                {"name": "Drift", "uri": "query:Synths#Drift", "is_loadable": True},
                {"name": "Drift", "uri": "query:Synths#Drift", "is_loadable": True},
            ],
        }
    }
    devices = normalize_scan_results(raw)
    assert len(devices) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.atlas.scanner'`

- [ ] **Step 3: Implement scanner module**

```python
# mcp_server/atlas/scanner.py
"""Atlas scanner — transforms raw browser scan data into atlas device entries."""

from __future__ import annotations

import re
from typing import Optional


def make_device_id(name: str, prefix: str = "") -> str:
    """Convert a device name to a lowercase snake_case ID."""
    # Replace non-alphanumeric with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if prefix:
        return f"{prefix}_{cleaned}"
    return cleaned


# Subcategory classification by known device names
_INSTRUMENT_SUBCATS = {
    "analog": "synths", "wavetable": "synths", "operator": "synths",
    "drift": "synths", "meld": "synths", "emit": "synths",
    "poli": "synths", "tree_tone": "synths", "vector_fm": "synths",
    "vector_grain": "synths", "bass": "synths",
    "collision": "physical_modeling", "tension": "physical_modeling",
    "electric": "physical_modeling",
    "simpler": "samplers", "sampler": "samplers",
    "drum_rack": "drums", "drum_sampler": "drums",
    "instrument_rack": "racks", "external_instrument": "routing",
    "granulator_iii": "granular", "impulse": "drums",
}

_EFFECT_SUBCATS = {
    "compressor": "dynamics", "glue_compressor": "dynamics",
    "limiter": "dynamics", "color_limiter": "dynamics",
    "multiband_dynamics": "dynamics", "gate": "dynamics", "drum_buss": "dynamics",
    "eq_eight": "eq", "eq_three": "eq", "channel_eq": "eq",
    "auto_filter": "filter", "spectral_resonator": "filter",
    "delay": "delay", "echo": "delay", "grain_delay": "delay",
    "filter_delay": "delay", "gated_delay": "delay", "vector_delay": "delay",
    "beat_repeat": "delay", "spectral_time": "delay", "align_delay": "delay",
    "reverb": "reverb", "hybrid_reverb": "reverb",
    "convolution_reverb": "reverb", "convolution_reverb_pro": "reverb",
    "saturator": "distortion", "overdrive": "distortion", "pedal": "distortion",
    "roar": "distortion", "dynamic_tube": "distortion", "erosion": "distortion",
    "redux": "distortion", "vinyl_distortion": "distortion", "amp": "distortion",
    "cabinet": "distortion",
    "chorus_ensemble": "modulation", "phaser_flanger": "modulation",
    "shifter": "modulation", "auto_pan_tremolo": "modulation",
    "auto_shift": "modulation",
    "utility": "utility", "spectrum": "utility", "tuner": "utility",
    "external_audio_effect": "routing", "surround_panner": "spatial",
    "corpus": "physical_modeling", "resonators": "physical_modeling",
    "vocoder": "special", "looper": "performance",
    "spectral_blur": "spectral", "pitch_hack": "pitch",
    "pitchloop89": "pitch", "re_enveloper": "dynamics",
    "shaper": "modulation", "variations": "utility",
    "vector_map": "modulation", "prearranger": "utility",
    "arrangement_looper": "performance", "performer": "performance",
    "lfo": "modulation", "envelope_follower": "modulation",
    "audio_effect_rack": "racks",
}


def _classify_subcategory(device_id: str, category: str) -> str:
    """Assign a subcategory based on device ID and category."""
    if category == "instruments":
        return _INSTRUMENT_SUBCATS.get(device_id, "other")
    if category == "audio_effects":
        return _EFFECT_SUBCATS.get(device_id, "other")
    if category == "midi_effects":
        return "midi"
    if category == "drum_kits":
        return "kits"
    return "other"


def _base_device_entry(
    name: str,
    uri: str,
    category: str,
    source: str = "native",
) -> dict:
    """Create a base (unenriched) device entry."""
    did = make_device_id(name)
    return {
        "id": did,
        "name": name,
        "uri": uri,
        "category": category,
        "subcategory": _classify_subcategory(did, category),
        "source": source,
        "enriched": False,
        "character_tags": [],
        "use_cases": [],
        "genre_affinity": {"primary": [], "secondary": []},
        "self_contained": True,
        "key_parameters": [],
        "pairs_well_with": [],
        "starter_recipes": [],
        "gotchas": [],
        "health_flags": [],
    }


# Categories that map to device atlas categories
_CATEGORY_MAP = {
    "instruments": "instruments",
    "audio_effects": "audio_effects",
    "midi_effects": "midi_effects",
    "drums": "drum_kits",
    "max_for_live": "max_for_live",
    "plugins": "plugins",
    "sounds": "sounds",
}


def normalize_scan_results(raw_scan: dict) -> list[dict]:
    """Convert raw scan_browser_deep output into atlas device entries.

    Deduplicates by URI. Returns flat list of device dicts.
    """
    categories = raw_scan.get("categories", {})
    seen_uris: set[str] = set()
    devices: list[dict] = []

    for scan_cat, items in categories.items():
        atlas_cat = _CATEGORY_MAP.get(scan_cat, scan_cat)
        source = "native" if scan_cat in ("instruments", "audio_effects", "midi_effects") else scan_cat

        for item in items:
            uri = item.get("uri", "")
            if not uri or uri in seen_uris:
                continue
            seen_uris.add(uri)

            entry = _base_device_entry(
                name=item["name"],
                uri=uri,
                category=atlas_cat,
                source=source,
            )
            devices.append(entry)

    return devices
```

- [ ] **Step 4: Run scanner tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_scanner.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```
git add mcp_server/atlas/scanner.py tests/test_atlas_scanner.py
git commit -m "feat(atlas): add scanner with normalize and ID generation"
```

---

## Chunk 3: Enrichment Loader + YAML Files

### Task 6: Enrichment merger

**Files:**
- Create: `mcp_server/atlas/enrichments/__init__.py`
- Modify: `tests/test_atlas_scanner.py`

- [ ] **Step 1: Write enrichment merger test**

Append to `tests/test_atlas_scanner.py`:

```python
from mcp_server.atlas.enrichments import load_enrichments, merge_enrichments


def test_load_enrichments_from_dir(tmp_path):
    import yaml
    instr_dir = tmp_path / "instruments"
    instr_dir.mkdir()
    drift_yaml = {
        "id": "drift",
        "sonic_description": "Warm analog synth",
        "character_tags": ["warm", "analog"],
        "use_cases": ["bass", "pads"],
        "key_parameters": [{"name": "Shape", "range": [0.0, 1.0]}],
        "starter_recipes": [{"name": "Sub Bass", "params": {"Shape": 0.0}}],
    }
    (instr_dir / "drift.yaml").write_text(yaml.dump(drift_yaml))

    enrichments = load_enrichments(str(tmp_path))
    assert "drift" in enrichments
    assert enrichments["drift"]["sonic_description"] == "Warm analog synth"


def test_merge_enrichments():
    devices = [
        {"id": "drift", "name": "Drift", "enriched": False, "character_tags": [],
         "sonic_description": "", "key_parameters": [], "starter_recipes": []},
    ]
    enrichments = {
        "drift": {
            "sonic_description": "Warm analog synth",
            "character_tags": ["warm"],
            "key_parameters": [{"name": "Shape"}],
            "starter_recipes": [{"name": "Sub"}],
        }
    }
    merged = merge_enrichments(devices, enrichments)
    drift = next(d for d in merged if d["id"] == "drift")
    assert drift["enriched"] is True
    assert drift["sonic_description"] == "Warm analog synth"
    assert len(drift["key_parameters"]) == 1


def test_merge_enrichments_skips_unknown():
    devices = [{"id": "drift", "name": "Drift", "enriched": False}]
    enrichments = {"nonexistent": {"sonic_description": "Ghost"}}
    merged = merge_enrichments(devices, enrichments)
    assert len(merged) == 1
    assert merged[0]["id"] == "drift"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_scanner.py::test_load_enrichments_from_dir -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement enrichment loader**

```python
# mcp_server/atlas/enrichments/__init__.py
"""Enrichment loader — reads YAML files and merges into atlas devices."""

from __future__ import annotations

import os
from typing import Optional

import yaml


def load_enrichments(enrichments_dir: str) -> dict[str, dict]:
    """Load all YAML enrichment files from subdirectories.

    Returns {device_id: enrichment_data}.
    """
    enrichments: dict[str, dict] = {}

    if not os.path.isdir(enrichments_dir):
        return enrichments

    for subdir in os.listdir(enrichments_dir):
        subdir_path = os.path.join(enrichments_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue
        for filename in os.listdir(subdir_path):
            if not filename.endswith((".yaml", ".yml")):
                continue
            if filename.startswith("_"):
                continue  # skip index files
            filepath = os.path.join(subdir_path, filename)
            try:
                with open(filepath, "r") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and "id" in data:
                    enrichments[data["id"]] = data
            except (yaml.YAMLError, OSError):
                continue

    return enrichments


# Fields that get overwritten from enrichment (not merged)
_ENRICHMENT_FIELDS = [
    "sonic_description", "synthesis_type", "character_tags",
    "use_cases", "genre_affinity", "complexity", "self_contained",
    "mcp_controllable", "key_parameters", "pairs_well_with",
    "starter_recipes", "gotchas", "health_flags", "introduced_in",
]


def merge_enrichments(devices: list[dict], enrichments: dict[str, dict]) -> list[dict]:
    """Merge enrichment data into device entries. Modifies in place and returns."""
    for device in devices:
        did = device.get("id", "")
        if did in enrichments:
            enrichment = enrichments[did]
            for field in _ENRICHMENT_FIELDS:
                if field in enrichment:
                    device[field] = enrichment[field]
            device["enriched"] = True
    return devices
```

- [ ] **Step 4: Run enrichment tests**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_scanner.py -v -k enrichment`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```
git add mcp_server/atlas/enrichments/__init__.py tests/test_atlas_scanner.py
git commit -m "feat(atlas): add YAML enrichment loader and merger"
```

### Task 7: Write Tier 1 instrument enrichments (all 16)

**Files:**
- Create: `mcp_server/atlas/enrichments/instruments/*.yaml` (16 files)

- [ ] **Step 1: Create enrichment YAML files for all 16 stock instruments**

Write all 16 YAML files. Each file follows the enrichment format from the spec. The agent should write complete files for: `analog.yaml`, `wavetable.yaml`, `operator.yaml`, `drift.yaml`, `meld.yaml`, `collision.yaml`, `tension.yaml`, `electric.yaml`, `emit.yaml`, `poli.yaml`, `tree_tone.yaml`, `vector_fm.yaml`, `vector_grain.yaml`, `simpler.yaml`, `sampler.yaml`, `bass.yaml`.

Sonic descriptions, parameter guides, recipes, and genre affinity should come from domain knowledge of each instrument. Reference the existing `sound-design.md` and `m4l-devices.md` for known parameter names.

Key guidance:
- `analog.yaml`: Two oscs + noise → two filters → two amps. Classic subtractive.
- `wavetable.yaml`: Continuous wavetable morphing, sub osc, mod matrix, unison.
- `operator.yaml`: 4-op FM, 11 algorithms, complex timbres.
- `drift.yaml`: Single osc with shape morph, built-in instability.
- `meld.yaml`: MPE-ready, two engines (additive + wavetable).
- `collision.yaml`: Physical modeling, mallet hits resonating surfaces.
- `tension.yaml`: Physical modeling, exciter + string/body.
- `electric.yaml`: Electric piano modeling with tine/tone bar.
- `emit.yaml`: New in 12.x — spectral/additive synth, partial control.
- `poli.yaml`: New in 12.x — polyphonic analog-style, MPE.
- `tree_tone.yaml`: New in 12.x — layered tonal textures.
- `vector_fm.yaml`: New in 12.x — vector-controlled FM synthesis.
- `vector_grain.yaml`: New in 12.x — vector-controlled granular.
- `simpler.yaml`: Sample player with classic/one-shot/slice modes.
- `sampler.yaml`: Multi-zone sample playback with complex modulation.
- `bass.yaml`: Dedicated bass synth (Live 12).

- [ ] **Step 2: Commit**

```
git add mcp_server/atlas/enrichments/instruments/
git commit -m "feat(atlas): add Tier 1 instrument enrichments (16 instruments)"
```

### Task 8: Write Tier 1 audio effect enrichments (35 effects)

**Files:**
- Create: `mcp_server/atlas/enrichments/audio_effects/*.yaml` (35 files)

- [ ] **Step 1: Create enrichment YAML files for all 35 Tier 1 audio effects**

Write YAML files for: `compressor.yaml`, `glue_compressor.yaml`, `limiter.yaml`, `color_limiter.yaml`, `multiband_dynamics.yaml`, `gate.yaml`, `drum_buss.yaml`, `eq_eight.yaml`, `eq_three.yaml`, `channel_eq.yaml`, `auto_filter.yaml`, `spectral_resonator.yaml`, `delay.yaml`, `echo.yaml`, `grain_delay.yaml`, `filter_delay.yaml`, `gated_delay.yaml`, `vector_delay.yaml`, `beat_repeat.yaml`, `spectral_time.yaml`, `reverb.yaml`, `hybrid_reverb.yaml`, `convolution_reverb.yaml`, `convolution_reverb_pro.yaml`, `saturator.yaml`, `overdrive.yaml`, `pedal.yaml`, `roar.yaml`, `dynamic_tube.yaml`, `erosion.yaml`, `redux.yaml`, `vinyl_distortion.yaml`, `chorus_ensemble.yaml`, `phaser_flanger.yaml`, `shifter.yaml`.

Each should have: sonic description, key parameters with sweet spots, 2-3 starter recipes, pairs_well_with, gotchas, genre affinity.

- [ ] **Step 2: Commit**

```
git add mcp_server/atlas/enrichments/audio_effects/
git commit -m "feat(atlas): add Tier 1 audio effect enrichments (35 effects)"
```

### Task 9: Write Tier 1 MIDI effect + utility enrichments (20 devices)

**Files:**
- Create: `mcp_server/atlas/enrichments/midi_effects/*.yaml` (12 files)
- Create: `mcp_server/atlas/enrichments/utility/*.yaml` (8 files)

- [ ] **Step 1: Create MIDI effect enrichments**

Write YAML files for: `arpeggiator.yaml`, `chord.yaml`, `scale.yaml`, `random.yaml`, `note_echo.yaml`, `note_length.yaml`, `pitch.yaml`, `velocity.yaml`, `bouncy_notes.yaml`, `melodic_steps.yaml`, `rhythmic_steps.yaml`, `step_arp.yaml`.

- [ ] **Step 2: Create utility device enrichments**

Write YAML files for: `utility.yaml`, `spectrum.yaml`, `tuner.yaml`, `amp.yaml`, `cabinet.yaml`, `corpus.yaml`, `resonators.yaml`, `vocoder.yaml`.

- [ ] **Step 3: Commit**

```
git add mcp_server/atlas/enrichments/midi_effects/ mcp_server/atlas/enrichments/utility/
git commit -m "feat(atlas): add Tier 1 MIDI and utility enrichments (20 devices)"
```

---

## Chunk 4: MCP Tools + Server Registration

### Task 10: Atlas MCP tools

**Files:**
- Create: `mcp_server/atlas/tools.py`
- Create: `tests/test_atlas_tools.py`

- [ ] **Step 1: Write tool registration test**

```python
# tests/test_atlas_tools.py
"""Verify atlas MCP tools are registered."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_atlas_tools_registered():
    names = _get_tool_names()
    expected = {
        "atlas_search",
        "atlas_device_info",
        "atlas_suggest",
        "atlas_chain_suggest",
        "atlas_compare",
        "scan_full_library",
    }
    missing = expected - names
    assert not missing, f"Missing atlas tools: {missing}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_tools.py -v`
Expected: FAIL — missing tools

- [ ] **Step 3: Implement atlas tools**

```python
# mcp_server/atlas/tools.py
"""Atlas MCP tools — search, suggest, compare, and scan the device database.

6 tools for the device atlas domain.
"""

from __future__ import annotations

import json
import os
import time

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_atlas():
    """Get the global AtlasManager instance, loading lazily if needed."""
    from . import _atlas_instance, _load_atlas
    if _atlas_instance is None:
        _load_atlas()
    return _atlas_instance


@mcp.tool()
def atlas_search(ctx: Context, query: str, category: str = "all", limit: int = 10) -> dict:
    """Search the device atlas for instruments, effects, kits, or plugins.

    query:    natural language search — name, sonic character, use case, or genre
              Examples: "warm analog bass", "reverb", "808 kit", "granular"
    category: filter by category (all, instruments, audio_effects, midi_effects,
              max_for_live, drum_kits, plugins)
    limit:    max results (default 10)
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first.", "results": []}

    results = atlas.search(query, category=category, limit=limit)
    # Return compact summaries, not full entries
    return {
        "query": query,
        "category": category,
        "count": len(results),
        "results": [
            {
                "id": r["id"],
                "name": r["name"],
                "uri": r.get("uri", ""),
                "category": r.get("category", ""),
                "sonic_description": r.get("sonic_description", "")[:120],
                "character_tags": r.get("character_tags", [])[:5],
                "enriched": r.get("enriched", False),
            }
            for r in results
        ],
    }


@mcp.tool()
def atlas_device_info(ctx: Context, device_id: str) -> dict:
    """Get complete atlas knowledge about a device — parameters, recipes, pairings, gotchas.

    device_id: the atlas ID or device name (e.g., "drift", "Compressor", "808_core_kit")
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    entry = atlas.lookup(device_id)
    if entry is None:
        return {"error": f"Device '{device_id}' not found in atlas", "suggestion": "Use atlas_search to find devices"}
    return entry


@mcp.tool()
def atlas_suggest(
    ctx: Context,
    intent: str,
    genre: str = "",
    energy: str = "medium",
    key: str = "",
) -> dict:
    """Suggest devices for a production intent.

    intent: what you're trying to achieve — "warm bass", "crispy hi-hats", "evolving texture"
    genre:  target genre for better recommendations
    energy: low/medium/high — affects sonic character suggestions
    key:    musical key context (e.g., "Cm") for tuned percussion suggestions
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    results = atlas.suggest(intent, genre=genre, energy=energy)
    return {
        "intent": intent,
        "genre": genre,
        "energy": energy,
        "suggestions": [
            {
                "device_id": r["device"]["id"],
                "device_name": r["device"]["name"],
                "uri": r["device"].get("uri", ""),
                "rationale": r["rationale"],
                "recipe": r.get("recipe"),
            }
            for r in results
        ],
    }


@mcp.tool()
def atlas_chain_suggest(ctx: Context, role: str, genre: str = "") -> dict:
    """Suggest a full device chain for a track role.

    role:  the musical role — "bass", "lead", "pad", "drums", "percussion", "texture"
    genre: target genre for style-appropriate choices
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    return atlas.chain_suggest(role, genre=genre)


@mcp.tool()
def atlas_compare(ctx: Context, device_a: str, device_b: str, role: str = "") -> dict:
    """Compare two devices — strengths, weaknesses, and recommendation for a role.

    device_a: first device name or ID
    device_b: second device name or ID
    role:     optional role context (e.g., "bass", "pad")
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    return atlas.compare(device_a, device_b, role=role)


@mcp.tool()
def scan_full_library(ctx: Context, force: bool = False) -> dict:
    """Scan the full Ableton browser and rebuild the device atlas.

    Walks every category (instruments, audio_effects, midi_effects, max_for_live,
    drums, plugins, packs) and records every loadable item with its URI.
    Results are merged with curated enrichments and saved to device_atlas.json.

    force: if True, rescan even if atlas already exists (default False)
    """
    from .scanner import normalize_scan_results
    from .enrichments import load_enrichments, merge_enrichments

    atlas_dir = os.path.dirname(os.path.abspath(__file__))
    atlas_path = os.path.join(atlas_dir, "device_atlas.json")
    enrichments_dir = os.path.join(atlas_dir, "enrichments")

    if not force and os.path.exists(atlas_path):
        # Check if recent (less than 24h old)
        age = time.time() - os.path.getmtime(atlas_path)
        if age < 86400:
            from . import _load_atlas
            _load_atlas()
            atlas = _get_atlas()
            return {
                "status": "already_exists",
                "age_hours": round(age / 3600, 1),
                "device_count": atlas.device_count if atlas else 0,
                "message": "Atlas is recent. Use force=True to rescan.",
            }

    # Scan browser
    ableton = _get_ableton(ctx)
    raw = ableton.send_command("scan_browser_deep", {"max_per_category": 1000})

    # Normalize
    devices = normalize_scan_results(raw)

    # Load and merge enrichments
    enrichments = load_enrichments(enrichments_dir)
    devices = merge_enrichments(devices, enrichments)

    # Count stats
    stats = {"total_devices": len(devices)}
    for device in devices:
        cat = device.get("category", "other")
        stats[cat] = stats.get(cat, 0) + 1
    stats["enriched_devices"] = sum(1 for d in devices if d.get("enriched"))

    # Build atlas
    atlas_data = {
        "version": "2.0.0",
        "live_version": "12.3.6",
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": stats,
        "devices": devices,
        "packs": [],
    }

    # Write
    with open(atlas_path, "w") as f:
        json.dump(atlas_data, f, indent=2)

    # Reload
    from . import _load_atlas
    _load_atlas()

    return {
        "status": "scanned",
        "device_count": len(devices),
        "enriched_count": stats["enriched_devices"],
        "stats": stats,
        "atlas_path": atlas_path,
    }
```

- [ ] **Step 4: Add lazy loading to atlas __init__.py**

Add to the top of `mcp_server/atlas/__init__.py` (before the class):

```python
import os as _os

_atlas_instance: "AtlasManager | None" = None

def _load_atlas():
    """Load or reload the atlas from disk."""
    global _atlas_instance
    atlas_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "device_atlas.json")
    if _os.path.exists(atlas_path):
        _atlas_instance = AtlasManager(atlas_path)
    else:
        _atlas_instance = None
```

- [ ] **Step 5: Register atlas tools in server.py**

Add to `mcp_server/server.py` after the last import:

```python
from .atlas import tools as atlas_tools  # noqa: F401, E402
```

- [ ] **Step 6: Run tool registration test**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_atlas_tools.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```
git add mcp_server/atlas/tools.py tests/test_atlas_tools.py mcp_server/atlas/__init__.py mcp_server/server.py
git commit -m "feat(atlas): add 6 MCP tools — search, suggest, compare, scan"
```

---

## Chunk 5: Initial Scan + Integration

### Task 11: Run initial scan and generate atlas JSON

This task requires a running Ableton instance.

- [ ] **Step 1: Start LivePilot server and trigger scan**

Via MCP client, call:
```
scan_full_library(force=True)
```

This walks the browser, merges enrichments, and writes `mcp_server/atlas/device_atlas.json`.

- [ ] **Step 2: Verify atlas JSON was written**

```bash
python3 -c "
import json
with open('mcp_server/atlas/device_atlas.json') as f:
    d = json.load(f)
print(f'Version: {d[\"version\"]}')
print(f'Devices: {d[\"stats\"][\"total_devices\"]}')
print(f'Enriched: {d[\"stats\"][\"enriched_devices\"]}')
for k, v in d['stats'].items():
    print(f'  {k}: {v}')
"
```

Expected: 1400+ devices, 71+ enriched (16 instruments + 35 effects + 12 MIDI + 8 utility)

- [ ] **Step 3: Commit atlas JSON**

```
git add mcp_server/atlas/device_atlas.json
git commit -m "data(atlas): initial scan — Live 12.3.6 full library"
```

### Task 12: Update tool count and version references

**Files:**
- Modify: `CLAUDE.md` — tool count 307 → 313, update device atlas description
- Modify: `package.json` — description with 313 tools
- Modify: `server.json` — description with 313 tools
- Modify: `livepilot/.Codex-plugin/plugin.json` — 313 tools
- Modify: `livepilot/.claude-plugin/plugin.json` — 313 tools
- Modify: `livepilot/skills/livepilot-core/SKILL.md` — 313 tools
- Modify: `livepilot/skills/livepilot-core/references/overview.md` — 313 tools, 42 domains
- Modify: `tests/test_tools_contract.py` — add atlas tool assertions, update count to 313
- Modify: `CHANGELOG.md` — add atlas v2 entry

- [ ] **Step 1: Update all tool count references from 307 to 313 (307 + 6 atlas tools)**

Update every file listed above. Change "307 tools" to "313 tools" and "41 domains" to "42 domains" (adding the `atlas` domain).

- [ ] **Step 2: Add atlas tool contract test**

Append to `tests/test_tools_contract.py`:

```python
def test_atlas_tools_registered():
    names = _get_tool_names()
    expected = {
        "atlas_search",
        "atlas_device_info",
        "atlas_suggest",
        "atlas_chain_suggest",
        "atlas_compare",
        "scan_full_library",
    }
    missing = expected - names
    assert not missing, f"Missing atlas tools: {missing}"
```

- [ ] **Step 3: Add CHANGELOG entry**

Prepend to `CHANGELOG.md`:

```markdown
## 1.10.0 — Device Atlas v2 (April 2026)

### The Big Picture
LivePilot now has a real device atlas — an embedded JSON database covering every device in Ableton Live 12.3.6. 1400+ devices with URIs, categories, and searchable metadata. 71+ stock devices have deep sonic intelligence: parameter guides, starter recipes, genre affinity, and device pairing recommendations.

### New Tools (6)
- **`atlas_search`** — fuzzy search across all devices by name, sonic character, use case, or genre
- **`atlas_device_info`** — full knowledge entry for any device — parameters, recipes, gotchas
- **`atlas_suggest`** — intent-driven recommendation: "warm bass for techno" → Drift + recipe
- **`atlas_chain_suggest`** — full device chain for a track role: instrument + effects with rationale
- **`atlas_compare`** — side-by-side comparison of two devices for a given role
- **`scan_full_library`** — deep browser scan to build/refresh the atlas

### Device Coverage
- 32 instruments (all stock instruments with URIs)
- 70 audio effects (all stock effects with URIs)
- 23 MIDI effects (all stock MIDI effects with URIs)
- 469 Max for Live devices
- 683 drum kit presets
- 141 AU/VST plugins
- 44 packs indexed
```

- [ ] **Step 4: Run contract test**

Run: `cd "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot" && python -m pytest tests/test_tools_contract.py -v`
Expected: All PASSED with 313 tools across 42 domains

- [ ] **Step 5: Commit**

```
git add CLAUDE.md package.json server.json CHANGELOG.md tests/test_tools_contract.py \
  livepilot/.Codex-plugin/plugin.json livepilot/.claude-plugin/plugin.json \
  livepilot/skills/livepilot-core/SKILL.md livepilot/skills/livepilot-core/references/overview.md
git commit -m "chore: bump to v1.10.0 — 313 tools, Device Atlas v2"
```

### Task 13: Update livepilot-devices skill

**Files:**
- Modify: `livepilot/skills/livepilot-devices/SKILL.md`

- [ ] **Step 1: Update the skill to reference atlas-driven workflow**

Add a new primary section at the top of the skill, keeping the existing browser workflow as a fallback:

```markdown
## Primary Workflow — Atlas-Driven

The device atlas contains every device in your Ableton library with sonic descriptions, recipes, and recommendations. Always start here:

1. **Discover:** `atlas_search(query)` — find devices by name, sound character, or genre
2. **Learn:** `atlas_device_info(device_id)` — full parameters, recipes, gotchas
3. **Suggest:** `atlas_suggest(intent, genre)` — "I need a warm pad" → ranked recommendations
4. **Chain:** `atlas_chain_suggest(role, genre)` — full device chain for a track role
5. **Load:** Use the URI from atlas results → `load_browser_item(uri)` or `find_and_load_device(name)`
6. **Recipe:** Apply starter recipe params → `batch_set_parameters(params)`
7. **Verify:** `get_device_info(track_index, device_index)` — check health

If the atlas doesn't have a device (new plugin, user sample), fall back to the browser workflow below.
```

- [ ] **Step 2: Commit**

```
git add livepilot/skills/livepilot-devices/SKILL.md
git commit -m "docs: update devices skill with atlas-driven workflow"
```

---

## Summary

| Chunk | Tasks | New Files | Modified Files | Tests |
|-------|-------|-----------|----------------|-------|
| 1: AtlasManager Core | 1-3 | `mcp_server/atlas/__init__.py` | — | `tests/test_atlas_manager.py` (17 tests) |
| 2: Scanner + Remote | 4-5 | `mcp_server/atlas/scanner.py` | `remote_script/LivePilot/browser.py` | `tests/test_atlas_scanner.py` (7 tests) |
| 3: Enrichments | 6-9 | `mcp_server/atlas/enrichments/` (71+ YAML files) | — | 3 enrichment tests |
| 4: MCP Tools | 10 | `mcp_server/atlas/tools.py` | `mcp_server/server.py` | `tests/test_atlas_tools.py` |
| 5: Scan + Integration | 11-13 | `mcp_server/atlas/device_atlas.json` | 9+ files (counts, skill, changelog) | contract test update |

**Total: 13 tasks, ~10 new files + 71 YAML enrichments, ~10 modified files, ~30 tests**

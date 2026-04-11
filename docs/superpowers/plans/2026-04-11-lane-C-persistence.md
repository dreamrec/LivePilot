# Lane C: Persistence and Meaning

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "across sessions" and "return to a project" actually true — persist taste graph inputs, session continuity state, and Wonder session outcomes so they survive server restart.

**Architecture:** Follow the TechniqueStore pattern (atomic JSON write, lazy init, corruption recovery, threading.Lock) for three new stores: TasteStore, ContinuityStore, and ProjectStore. Define four memory layers: session (ephemeral), project (per-song), global taste (cross-session), and techniques (reusable knowledge).

**Tech Stack:** Python 3.10+, JSON files at `~/.livepilot/`, threading.Lock, atomic tmp+rename.

**Depends on:** Nothing — independent lane, can run in parallel with A+B.
**Blocks:** Lane E (docs must not claim persistence until it exists).

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `mcp_server/memory/persistent_store.py` | **New** — base class for persistent JSON stores with atomic write + recovery |
| `mcp_server/memory/taste_store.py` | **New** — persistent taste: move outcomes, novelty pref, device affinity, anti-prefs |
| `mcp_server/memory/taste_memory.py` | **Modify** — wire into persistent taste store |
| `mcp_server/memory/anti_memory.py` | **Modify** — wire into persistent taste store |
| `mcp_server/memory/taste_graph.py` | **Modify** — `build_taste_graph` reads from persistent store; `record_move_outcome` writes back |
| `mcp_server/memory/tools.py` | **Modify** — fix record_positive_preference (if not done in Lane A) |
| `mcp_server/session_continuity/persistence.py` | **New** — persist threads/turns per project |
| `mcp_server/session_continuity/tracker.py` | **Modify** — wire persistence on write operations |
| `tests/test_persistent_store.py` | **New** — base store tests |
| `tests/test_taste_persistence.py` | **New** — taste survives restart |
| `tests/test_continuity_persistence.py` | **New** — threads/turns survive restart |

---

## Chunk 1: Persistent Store Base + Taste Persistence (C1, C3, C4)

### Task 1: Build the persistent store base class

**Files:**
- Create: `mcp_server/memory/persistent_store.py`
- Test: `tests/test_persistent_store.py`

The base class follows the TechniqueStore pattern exactly: lazy init, atomic tmp+rename with fsync, corruption recovery, threading.Lock.

- [ ] **Step 1: Write tests for the base store**

```python
"""Tests for the persistent JSON store base class."""

import json
import os
import tempfile
from pathlib import Path

from mcp_server.memory.persistent_store import PersistentJsonStore


def test_write_and_read_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentJsonStore(Path(tmpdir) / "test.json")
        store.write({"key": "value", "count": 42})
        data = store.read()
        assert data == {"key": "value", "count": 42}


def test_read_nonexistent_returns_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentJsonStore(Path(tmpdir) / "missing.json")
        data = store.read()
        assert data == {}


def test_corrupt_file_recovers():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "corrupt.json"
        path.write_text("not valid json {{{")
        store = PersistentJsonStore(path)
        data = store.read()
        assert data == {}
        # Corrupt file should be renamed
        assert (Path(tmpdir) / "corrupt.json.corrupt").exists()


def test_atomic_write_survives_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentJsonStore(Path(tmpdir) / "atomic.json")
        store.write({"first": True})
        store.write({"second": True})
        data = store.read()
        assert data == {"second": True}
        # No .tmp file should remain
        assert not (Path(tmpdir) / "atomic.tmp").exists()
```

- [ ] **Step 2: Implement the base store**

```python
"""Persistent JSON store with atomic writes and corruption recovery.

Follows the TechniqueStore pattern: lazy init, atomic tmp+rename,
fsync to disk, corruption recovery via .corrupt rename.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class PersistentJsonStore:
    """Thread-safe, crash-safe JSON file store."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def read(self) -> dict:
        """Read the store. Returns {} if missing or corrupt."""
        with self._lock:
            if not self._path.exists():
                return {}
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # Corruption recovery — rename and start fresh
                corrupt = self._path.with_suffix(".json.corrupt")
                try:
                    self._path.rename(corrupt)
                except OSError:
                    pass
                return {}

    def write(self, data: dict) -> None:
        """Atomically write data to disk."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(str(tmp), str(self._path))
            except OSError:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
```

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

---

### Task 2: Build persistent taste store (C3)

**Files:**
- Create: `mcp_server/memory/taste_store.py`
- Test: `tests/test_taste_persistence.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for persistent taste state."""

import tempfile
from pathlib import Path

from mcp_server.memory.taste_store import PersistentTasteStore


def test_move_outcome_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentTasteStore(Path(tmpdir) / "taste.json")
        store.record_move_outcome("make_punchier", "mix", kept=True, score=0.8)
        
        # Create a new store instance reading from same file
        store2 = PersistentTasteStore(Path(tmpdir) / "taste.json")
        data = store2.get_all()
        assert data["move_outcomes"]["make_punchier"]["kept_count"] == 1


def test_novelty_preference_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentTasteStore(Path(tmpdir) / "taste.json")
        store.update_novelty(chose_bold=True)
        store.update_novelty(chose_bold=True)
        
        store2 = PersistentTasteStore(Path(tmpdir) / "taste.json")
        data = store2.get_all()
        assert data["novelty_band"] > 0.5


def test_device_affinity_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentTasteStore(Path(tmpdir) / "taste.json")
        store.record_device_use("Wavetable", positive=True)
        
        store2 = PersistentTasteStore(Path(tmpdir) / "taste.json")
        data = store2.get_all()
        assert "Wavetable" in data["device_affinities"]


def test_anti_preference_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = PersistentTasteStore(Path(tmpdir) / "taste.json")
        store.record_anti_preference("width", "increase")
        
        store2 = PersistentTasteStore(Path(tmpdir) / "taste.json")
        data = store2.get_all()
        assert ("width", "increase") in [
            (a["dimension"], a["direction"]) for a in data["anti_preferences"]
        ]
```

- [ ] **Step 2: Implement PersistentTasteStore**

Wraps `PersistentJsonStore`. Schema:
```json
{
  "version": 1,
  "move_outcomes": { "move_id": { "family": "...", "kept_count": N, "undone_count": N, "score": 0.0 } },
  "novelty_band": 0.5,
  "device_affinities": { "device_name": { "affinity": 0.0, "use_count": N } },
  "anti_preferences": [ { "dimension": "...", "direction": "...", "strength": 0.0, "count": N } ],
  "dimension_weights": { "dim_name": 0.0 },
  "evidence_count": 0
}
```

- [ ] **Step 3: Wire into TasteGraph build**

Modify `mcp_server/memory/taste_graph.py` `build_taste_graph` to accept an optional `persistent_store` and hydrate the graph from it. Modify `TasteGraph.record_move_outcome` to write back to the persistent store.

- [ ] **Step 4: Wire into Wonder/Preview commit paths**

In `wonder_mode/tools.py` and `preview_studio/tools.py`, when calling `graph.record_move_outcome()`, ensure the persistent store is passed through so the update persists.

- [ ] **Step 5: Run tests**

- [ ] **Step 6: Commit**

---

### Task 3: Persist session continuity per project (C5, C6)

**Files:**
- Create: `mcp_server/session_continuity/persistence.py`
- Modify: `mcp_server/session_continuity/tracker.py`
- Test: `tests/test_continuity_persistence.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for persistent session continuity."""

import tempfile
from pathlib import Path

from mcp_server.session_continuity.persistence import ContinuityStore


def test_thread_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ContinuityStore(Path(tmpdir) / "continuity.json")
        store.save_thread({"thread_id": "t1", "description": "Make chorus bigger", "status": "open"})
        
        store2 = ContinuityStore(Path(tmpdir) / "continuity.json")
        threads = store2.get_threads()
        assert any(t["thread_id"] == "t1" for t in threads)


def test_turn_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ContinuityStore(Path(tmpdir) / "continuity.json")
        store.save_turn({"turn_id": "tr1", "outcome": "accepted"})
        
        store2 = ContinuityStore(Path(tmpdir) / "continuity.json")
        turns = store2.get_turns()
        assert any(t["turn_id"] == "tr1" for t in turns)
```

- [ ] **Step 2: Implement ContinuityStore**

- [ ] **Step 3: Wire into tracker.py**

Modify `record_turn_resolution` and `open_thread` to flush to persistent store.

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

---

## Chunk 2: Memory Layer Definitions (C2)

### Task 4: Document and enforce memory layers

- [ ] **Step 1: Add a memory architecture reference**

Define the four layers in a reference file:

| Layer | Scope | Storage | Survives restart? |
|-------|-------|---------|-------------------|
| Session | Current MCP process | `ctx.lifespan_context` | No |
| Project | Per Ableton set | `~/.livepilot/projects/<hash>/` | Yes |
| Global Taste | Cross-session | `~/.livepilot/taste.json` | Yes |
| Techniques | Reusable knowledge | `~/.livepilot/memory/techniques.json` | Yes (already works) |

- [ ] **Step 2: Run full test suite**

- [ ] **Step 3: Commit**

---

## What This Plan Does NOT Cover

| Deferred | Why | Plan |
|----------|-----|------|
| Project identity from set path | Requires Ableton connection to read set file path — deferred to Lane E integration | Plan 4 |
| Full Wonder session persistence | Wonder sessions are short-lived; taste+continuity persistence covers the meaningful state | Follow-up |
| Preview set persistence | Preview sets are ephemeral by design — commit/discard resolves them | N/A |

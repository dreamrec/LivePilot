"""Tests for Memory Extensions — session memory and taste memory."""

from __future__ import annotations

import pytest

from mcp_server.memory.session_memory import (
    SessionMemoryEntry,
    SessionMemoryStore,
)
from mcp_server.memory.taste_memory import (
    EXTENDED_TASTE_DIMENSIONS,
    TasteDimension,
    TasteMemoryStore,
)


# ── SessionMemoryEntry ──────────────────────────────────────────────


class TestSessionMemoryEntry:
    def test_creates(self):
        e = SessionMemoryEntry(
            id="smem_001",
            timestamp_ms=1000,
            category="observation",
            content="bass is muddy",
            engine="analyzer",
            confidence=0.8,
            related_tracks=[0, 1],
        )
        assert e.category == "observation"
        assert e.confidence == 0.8
        assert e.expires_with_session is True

    def test_to_dict(self):
        e = SessionMemoryEntry(
            id="smem_002",
            timestamp_ms=2000,
            category="decision",
            content="cut 200Hz on bass",
            engine="agent_os",
            confidence=0.7,
            related_tracks=[2],
        )
        d = e.to_dict()
        assert d["id"] == "smem_002"
        assert d["category"] == "decision"
        assert d["related_tracks"] == [2]
        assert d["expires_with_session"] is True


# ── SessionMemoryStore ──────────────────────────────────────────────


class TestSessionMemoryStore:
    def test_add_returns_id(self):
        store = SessionMemoryStore()
        entry_id = store.add("observation", "test content", "analyzer")
        assert entry_id.startswith("smem_")

    def test_add_invalid_category_raises(self):
        store = SessionMemoryStore()
        with pytest.raises(ValueError, match="category must be one of"):
            store.add("invalid_cat", "content", "engine")

    def test_get_recent_returns_newest_first(self):
        store = SessionMemoryStore()
        id1 = store.add("observation", "first", "engine")
        id2 = store.add("observation", "second", "engine")
        recent = store.get_recent(limit=10)
        assert len(recent) == 2
        assert recent[0].id == id2
        assert recent[1].id == id1

    def test_get_recent_with_category_filter(self):
        store = SessionMemoryStore()
        store.add("observation", "obs1", "engine")
        store.add("decision", "dec1", "engine")
        store.add("observation", "obs2", "engine")
        recent = store.get_recent(category="observation")
        assert len(recent) == 2
        assert all(e.category == "observation" for e in recent)

    def test_get_recent_with_engine_filter(self):
        store = SessionMemoryStore()
        store.add("observation", "a", "analyzer")
        store.add("observation", "b", "composition")
        store.add("observation", "c", "analyzer")
        recent = store.get_recent(engine="analyzer")
        assert len(recent) == 2

    def test_get_recent_limit(self):
        store = SessionMemoryStore()
        for i in range(5):
            store.add("observation", f"entry {i}", "engine")
        recent = store.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_by_tracks(self):
        store = SessionMemoryStore()
        store.add("observation", "bass muddy", "analyzer", tracks=[0])
        store.add("observation", "kick ok", "analyzer", tracks=[1])
        store.add("observation", "bass-kick clash", "analyzer", tracks=[0, 1])
        results = store.get_by_tracks([0])
        assert len(results) == 2  # entry 0 and entry 2

    def test_get_by_tracks_no_match(self):
        store = SessionMemoryStore()
        store.add("observation", "something", "engine", tracks=[0])
        results = store.get_by_tracks([99])
        assert len(results) == 0

    def test_clear(self):
        store = SessionMemoryStore()
        store.add("observation", "a", "engine")
        store.add("decision", "b", "engine")
        store.clear()
        assert store.get_recent() == []
        assert store.to_dict()["count"] == 0

    def test_to_dict(self):
        store = SessionMemoryStore()
        store.add("observation", "test", "engine")
        d = store.to_dict()
        assert d["count"] == 1
        assert len(d["entries"]) == 1

    def test_confidence_clamped(self):
        store = SessionMemoryStore()
        store.add("observation", "high", "engine", confidence=5.0)
        store.add("observation", "low", "engine", confidence=-2.0)
        entries = store.get_recent()
        assert entries[0].confidence == 0.0  # -2.0 clamped (most recent = low)
        assert entries[1].confidence == 1.0  # 5.0 clamped


# ── TasteDimension ──────────────────────────────────────────────────


class TestTasteDimension:
    def test_creates(self):
        d = TasteDimension(
            name="transition_boldness",
            value=0.3,
            evidence_count=2,
            last_updated_ms=1000,
        )
        assert d.name == "transition_boldness"
        assert d.value == 0.3

    def test_to_dict_rounds_value(self):
        d = TasteDimension(
            name="fx_intensity",
            value=0.12345,
            evidence_count=1,
            last_updated_ms=2000,
        )
        result = d.to_dict()
        assert result["value"] == 0.123
        assert result["name"] == "fx_intensity"


# ── TasteMemoryStore ───────────────────────────────────────────────


class TestTasteMemoryStore:
    def test_initializes_all_dimensions(self):
        store = TasteMemoryStore()
        dims = store.get_taste_dimensions()
        assert len(dims) == len(EXTENDED_TASTE_DIMENSIONS)
        for d in dims:
            assert d.value == 0.0
            assert d.evidence_count == 0

    def test_update_from_outcome_adjusts_value(self):
        store = TasteMemoryStore()
        store.update_from_outcome({
            "kept": True,
            "signals": ["bold_transition_kept"],
        })
        dim = store.get_dimension("transition_boldness")
        assert dim is not None
        assert dim.value > 0.0
        assert dim.evidence_count == 1

    def test_update_from_outcome_multiple_signals(self):
        store = TasteMemoryStore()
        store.update_from_outcome({
            "kept": True,
            "signals": ["bold_transition_kept", "wide_mix_kept"],
        })
        bold = store.get_dimension("transition_boldness")
        width = store.get_dimension("width_preference")
        assert bold is not None and bold.value > 0.0
        assert width is not None and width.value > 0.0

    def test_update_from_outcome_no_signals(self):
        store = TasteMemoryStore()
        store.update_from_outcome({"kept": True, "signals": []})
        # All should still be at zero
        for d in store.get_taste_dimensions():
            assert d.evidence_count == 0

    def test_value_clamped_at_bounds(self):
        store = TasteMemoryStore()
        # Push the same signal many times to hit the cap
        for _ in range(20):
            store.update_from_outcome({"signals": ["bold_transition_kept"]})
        dim = store.get_dimension("transition_boldness")
        assert dim is not None
        assert dim.value <= 1.0

    def test_should_prefer_requires_evidence(self):
        store = TasteMemoryStore()
        # Only one evidence point — should not prefer yet
        store.update_from_outcome({"signals": ["bold_transition_kept"]})
        assert store.should_prefer("transition_boldness", "more") is False

    def test_should_prefer_with_enough_evidence(self):
        store = TasteMemoryStore()
        store.update_from_outcome({"signals": ["bold_transition_kept"]})
        store.update_from_outcome({"signals": ["bold_transition_kept"]})
        assert store.should_prefer("transition_boldness", "more") is True
        assert store.should_prefer("transition_boldness", "less") is False

    def test_should_prefer_unknown_dimension(self):
        store = TasteMemoryStore()
        assert store.should_prefer("nonexistent", "more") is False

    def test_to_dict(self):
        store = TasteMemoryStore()
        d = store.to_dict()
        assert d["count"] == len(EXTENDED_TASTE_DIMENSIONS)
        assert len(d["dimensions"]) == len(EXTENDED_TASTE_DIMENSIONS)

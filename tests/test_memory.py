"""Tests for TechniqueStore — persistent technique memory."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mcp_server.memory.technique_store import TechniqueStore
from mcp_server.tools.memory import _generate_replay_steps


@pytest.fixture
def store(tmp_path):
    return TechniqueStore(base_dir=str(tmp_path))


@pytest.fixture
def sample_beat():
    return {
        "name": "Boom-Bap Groove",
        "type": "beat_pattern",
        "qualities": {
            "summary": "Classic boom-bap with swing",
            "mood": ["chill", "nostalgic"],
            "genre_tags": ["hip-hop", "lo-fi"],
            "tempo_range": "85-95 BPM",
        },
        "payload": {
            "notes": [
                {"pitch": 36, "start": 0.0, "duration": 0.25, "velocity": 100},
                {"pitch": 38, "start": 1.0, "duration": 0.25, "velocity": 90},
            ],
            "swing": 0.62,
        },
        "tags": ["drums", "boom-bap", "swing"],
    }


# ── TestSaveAndGet ───────────────────────────────────────────────


class TestSaveAndGet:
    def test_save_returns_id_and_name(self, store, sample_beat):
        result = store.save(**sample_beat)
        assert "id" in result
        assert result["name"] == "Boom-Bap Groove"
        assert result["type"] == "beat_pattern"
        assert result["summary"] == "Classic boom-bap with swing"

    def test_get_returns_full_technique(self, store, sample_beat):
        saved = store.save(**sample_beat)
        t = store.get(saved["id"])
        assert t["id"] == saved["id"]
        assert t["name"] == "Boom-Bap Groove"
        assert t["payload"]["swing"] == 0.62
        assert t["qualities"]["mood"] == ["chill", "nostalgic"]
        assert t["favorite"] is False
        assert t["rating"] == 0
        assert t["replay_count"] == 0

    def test_get_nonexistent_raises(self, store):
        with pytest.raises(ValueError, match="NOT_FOUND"):
            store.get("nonexistent-id")

    def test_save_requires_summary(self, store):
        with pytest.raises(ValueError, match="summary"):
            store.save(
                name="No Summary",
                type="beat_pattern",
                qualities={"mood": ["dark"]},
                payload={},
            )

    def test_save_validates_type(self, store):
        with pytest.raises(ValueError, match="INVALID_PARAM"):
            store.save(
                name="Bad Type",
                type="invalid_type",
                qualities={"summary": "test"},
                payload={},
            )

    def test_save_persists_to_disk(self, tmp_path, sample_beat):
        store1 = TechniqueStore(base_dir=str(tmp_path))
        saved = store1.save(**sample_beat)

        # New store instance reads from same dir
        store2 = TechniqueStore(base_dir=str(tmp_path))
        t = store2.get(saved["id"])
        assert t["name"] == "Boom-Bap Groove"


# ── TestSearch ───────────────────────────────────────────────────


class TestSearch:
    def _populate(self, store):
        """Add several techniques for search tests."""
        ids = {}
        ids["beat"] = store.save(
            name="Boom-Bap Groove",
            type="beat_pattern",
            qualities={
                "summary": "Classic boom-bap",
                "mood": ["chill", "nostalgic"],
            },
            payload={"notes": []},
            tags=["drums", "hip-hop"],
        )["id"]
        ids["chain"] = store.save(
            name="Warm Tape Saturator",
            type="device_chain",
            qualities={
                "summary": "Analog warmth chain",
                "character": "vintage saturation",
            },
            payload={"devices": []},
            tags=["fx", "saturation"],
        )["id"]
        ids["mix"] = store.save(
            name="Lo-Fi Mix Bus",
            type="mix_template",
            qualities={
                "summary": "Lo-fi master bus",
                "mood": ["dreamy", "nostalgic"],
            },
            payload={"settings": {}},
            tags=["mixing", "lo-fi"],
        )["id"]
        return ids

    def test_search_by_name(self, store):
        self._populate(store)
        results = store.search(query="boom-bap")
        assert len(results) == 1
        assert results[0]["name"] == "Boom-Bap Groove"

    def test_search_matches_qualities(self, store):
        self._populate(store)
        results = store.search(query="vintage saturation")
        assert len(results) == 1
        assert results[0]["name"] == "Warm Tape Saturator"

    def test_search_matches_mood_list(self, store):
        self._populate(store)
        results = store.search(query="nostalgic")
        assert len(results) == 2

    def test_filter_by_type(self, store):
        self._populate(store)
        results = store.search(type_filter="device_chain")
        assert len(results) == 1
        assert results[0]["type"] == "device_chain"

    def test_filter_by_tags(self, store):
        self._populate(store)
        results = store.search(tags=["drums"])
        assert len(results) == 1
        assert results[0]["name"] == "Boom-Bap Groove"

    def test_excludes_payload(self, store):
        self._populate(store)
        results = store.search()
        for r in results:
            assert "payload" not in r

    def test_favorites_sort_first(self, store):
        ids = self._populate(store)
        store.favorite(ids["chain"], favorite=True)
        results = store.search()
        assert results[0]["name"] == "Warm Tape Saturator"

    def test_respects_limit(self, store):
        self._populate(store)
        results = store.search(limit=1)
        assert len(results) == 1


# ── TestList ─────────────────────────────────────────────────────


class TestList:
    def _populate(self, store):
        store.save(
            name="Alpha Beat",
            type="beat_pattern",
            qualities={"summary": "First"},
            payload={},
            tags=["drums"],
        )
        store.save(
            name="Zeta Chain",
            type="device_chain",
            qualities={"summary": "Last"},
            payload={},
            tags=["fx"],
        )

    def test_returns_compact_summaries(self, store):
        self._populate(store)
        results = store.list_techniques()
        for r in results:
            assert "payload" not in r
            assert "qualities" not in r
            assert "summary" in r
            assert "id" in r

    def test_filter_by_type(self, store):
        self._populate(store)
        results = store.list_techniques(type_filter="beat_pattern")
        assert len(results) == 1
        assert results[0]["type"] == "beat_pattern"

    def test_sort_by_name(self, store):
        self._populate(store)
        results = store.list_techniques(sort_by="name")
        assert results[0]["name"] == "Alpha Beat"
        assert results[1]["name"] == "Zeta Chain"

    def test_invalid_sort_raises(self, store):
        with pytest.raises(ValueError, match="INVALID_PARAM"):
            store.list_techniques(sort_by="invalid_field")


# ── TestFavorite ─────────────────────────────────────────────────


class TestFavorite:
    def _make(self, store):
        return store.save(
            name="Test",
            type="beat_pattern",
            qualities={"summary": "test"},
            payload={},
        )["id"]

    def test_sets_favorite_flag(self, store):
        tid = self._make(store)
        result = store.favorite(tid, favorite=True)
        assert result["favorite"] is True

    def test_sets_rating(self, store):
        tid = self._make(store)
        result = store.favorite(tid, rating=4)
        assert result["rating"] == 4

    def test_validates_rating_range(self, store):
        tid = self._make(store)
        with pytest.raises(ValueError, match="rating"):
            store.favorite(tid, rating=6)
        with pytest.raises(ValueError, match="rating"):
            store.favorite(tid, rating=-1)


# ── TestUpdate ───────────────────────────────────────────────────


class TestUpdate:
    def _make(self, store):
        return store.save(
            name="Original",
            type="beat_pattern",
            qualities={
                "summary": "Original summary",
                "mood": ["dark"],
                "tempo_range": "120 BPM",
            },
            payload={"data": 1},
            tags=["old-tag"],
        )["id"]

    def test_update_name(self, store):
        tid = self._make(store)
        result = store.update(tid, name="Renamed")
        assert result["name"] == "Renamed"

    def test_tags_replace(self, store):
        tid = self._make(store)
        store.update(tid, tags=["new-tag-1", "new-tag-2"])
        t = store.get(tid)
        assert t["tags"] == ["new-tag-1", "new-tag-2"]

    def test_qualities_merge_preserves_existing(self, store):
        tid = self._make(store)
        store.update(tid, qualities={"character": "punchy"})
        t = store.get(tid)
        assert t["qualities"]["tempo_range"] == "120 BPM"
        assert t["qualities"]["character"] == "punchy"

    def test_list_fields_replace(self, store):
        tid = self._make(store)
        store.update(tid, qualities={"mood": ["bright", "energetic"]})
        t = store.get(tid)
        assert t["qualities"]["mood"] == ["bright", "energetic"]
        assert "dark" not in t["qualities"]["mood"]


# ── TestDelete ───────────────────────────────────────────────────


class TestDelete:
    def _make(self, store):
        return store.save(
            name="Doomed",
            type="beat_pattern",
            qualities={"summary": "will be deleted"},
            payload={},
        )["id"]

    def test_removes_technique(self, store):
        tid = self._make(store)
        store.delete(tid)
        with pytest.raises(ValueError, match="NOT_FOUND"):
            store.get(tid)

    def test_creates_backup_file(self, store, tmp_path):
        tid = self._make(store)
        store.delete(tid)
        backups = list((tmp_path / "backups").glob("*.json"))
        assert len(backups) == 1
        backup_data = json.loads(backups[0].read_text())
        assert backup_data["id"] == tid

    def test_nonexistent_raises(self, store):
        with pytest.raises(ValueError, match="NOT_FOUND"):
            store.delete("nonexistent-id")


# ── TestReplayCounter ────────────────────────────────────────────


class TestReplayCounter:
    def _make(self, store):
        return store.save(
            name="Replayable",
            type="beat_pattern",
            qualities={"summary": "test"},
            payload={},
        )["id"]

    def test_increment_works(self, store):
        tid = self._make(store)
        store.increment_replay(tid)
        t = store.get(tid)
        assert t["replay_count"] == 1
        assert "last_replayed_at" in t

    def test_accumulates(self, store):
        tid = self._make(store)
        store.increment_replay(tid)
        store.increment_replay(tid)
        store.increment_replay(tid)
        t = store.get(tid)
        assert t["replay_count"] == 3


# ── TestReplaySteps ─────────────────────────────────────────────


class TestReplaySteps:
    def test_beat_pattern_exact_steps(self):
        technique = {
            "type": "beat_pattern",
            "payload": {
                "notes": [{"pitch": 36}, {"pitch": 38}],
                "tempo": 85,
                "clip_length": 8.0,
                "kit_name": "Boom Bap Kit",
                "kit_uri": "query:Drums#Kit",
            },
        }
        steps = _generate_replay_steps(technique)
        assert any("Boom Bap Kit" in s for s in steps)
        assert any("8.0" in s for s in steps)
        assert any("2 notes" in s for s in steps)
        assert any("85" in s for s in steps)

    def test_beat_pattern_without_kit_uri(self):
        technique = {
            "type": "beat_pattern",
            "payload": {"notes": [], "kit_name": "Some Kit", "clip_length": 4.0},
        }
        steps = _generate_replay_steps(technique)
        assert any("Some Kit" in s for s in steps)

    def test_device_chain_steps(self):
        technique = {
            "type": "device_chain",
            "payload": {
                "devices": [
                    {"name": "Saturator", "params": {"Drive": 4.2}},
                    {"name": "Reverb", "params": {"Decay": 2.5, "Dry/Wet": 0.5}},
                ]
            },
        }
        steps = _generate_replay_steps(technique)
        # Each device gets a load step + a params step
        assert any("Saturator" in s for s in steps)
        assert any("Reverb" in s for s in steps)
        assert len(steps) == 4  # load + params for each device

    def test_mix_template_steps(self):
        technique = {
            "type": "mix_template",
            "payload": {
                "returns": [
                    {
                        "name": "Room Verb",
                        "devices": [{"name": "Reverb", "params": {}}],
                    }
                ],
                "sends_pattern": {"drums": {"reverb": 0.3}},
            },
        }
        steps = _generate_replay_steps(technique)
        assert any("return" in s.lower() for s in steps)
        assert any("Reverb" in s for s in steps)
        assert any("send" in s.lower() for s in steps)

    def test_browser_pin_steps(self):
        technique = {
            "type": "browser_pin",
            "payload": {"uri": "query:Drums#808"},
        }
        steps = _generate_replay_steps(technique)
        assert any("query:Drums#808" in s for s in steps)

    def test_preference_steps(self):
        technique = {
            "type": "preference",
            "payload": {"key": "default_reverb", "value": "Valhalla"},
        }
        steps = _generate_replay_steps(technique)
        assert any("default_reverb" in s for s in steps)

    def test_adapt_mode_returns_inspiration_steps(self):
        """The adapt path lives in memory_replay, not _generate_replay_steps.
        Verify _generate_replay_steps returns a fallback for empty payload."""
        technique = {"type": "beat_pattern", "payload": {}}
        steps = _generate_replay_steps(technique)
        assert len(steps) >= 1  # fallback step

    def test_unknown_type_returns_fallback(self):
        technique = {"type": "unknown_thing", "payload": {}}
        steps = _generate_replay_steps(technique)
        assert len(steps) >= 1  # should have a fallback message


# ── TestEdgeCases ───────────────────────────────────────────────


class TestEdgeCases:
    def test_save_empty_name_is_allowed(self, store):
        """Empty name is technically valid — agent should provide a good one but we don't block it."""
        result = store.save(
            name="", type="beat_pattern", qualities={"summary": "test"}, payload={}
        )
        assert result["name"] == ""

    def test_save_empty_summary_raises(self, store):
        with pytest.raises(ValueError, match="summary"):
            store.save(
                name="Test",
                type="beat_pattern",
                qualities={"summary": ""},
                payload={},
            )

    def test_search_empty_query_returns_all(self, store, sample_beat):
        store.save(**sample_beat)
        results = store.search(query="")
        assert len(results) == 1  # empty string query should match everything

    def test_search_combined_filters(self, store):
        store.save(
            name="Beat A",
            type="beat_pattern",
            tags=["trap"],
            qualities={"summary": "dark trap beat"},
            payload={},
        )
        store.save(
            name="Chain B",
            type="device_chain",
            tags=["trap"],
            qualities={"summary": "trap chain"},
            payload={},
        )
        # Combined: type + tags + query
        results = store.search(query="dark", type_filter="beat_pattern", tags=["trap"])
        assert len(results) == 1
        assert results[0]["name"] == "Beat A"

    def test_favorite_with_both_params(self, store, sample_beat):
        tid = store.save(**sample_beat)["id"]
        store.favorite(tid, favorite=True, rating=5)
        t = store.get(tid)
        assert t["favorite"] is True
        assert t["rating"] == 5

    def test_favorite_with_no_params(self, store, sample_beat):
        """Calling favorite with neither param still updates updated_at."""
        tid = store.save(**sample_beat)["id"]
        old_updated = store.get(tid)["updated_at"]
        import time

        time.sleep(0.01)  # ensure timestamp differs
        store.favorite(tid)
        assert store.get(tid)["updated_at"] >= old_updated

    def test_update_empty_qualities_is_noop(self, store, sample_beat):
        tid = store.save(**sample_beat)["id"]
        original = store.get(tid)["qualities"]
        store.update(tid, qualities={})
        assert store.get(tid)["qualities"] == original

    def test_delete_last_technique_leaves_empty_store(self, store, sample_beat):
        tid = store.save(**sample_beat)["id"]
        store.delete(tid)
        assert store.list_techniques() == []

    def test_increment_replay_nonexistent_raises(self, store):
        with pytest.raises(ValueError, match="NOT_FOUND"):
            store.increment_replay("nonexistent-id")

    def test_list_sort_by_rating(self, store):
        store.save(
            name="Low",
            type="beat_pattern",
            qualities={"summary": "low"},
            payload={},
        )
        id_high = store.save(
            name="High",
            type="beat_pattern",
            qualities={"summary": "high"},
            payload={},
        )["id"]
        store.favorite(id_high, rating=5)
        results = store.list_techniques(sort_by="rating")
        assert results[0]["name"] == "High"

    def test_list_sort_by_replay_count(self, store):
        id1 = store.save(
            name="A",
            type="beat_pattern",
            qualities={"summary": "a"},
            payload={},
        )["id"]
        store.save(
            name="B",
            type="beat_pattern",
            qualities={"summary": "b"},
            payload={},
        )
        store.increment_replay(id1)
        store.increment_replay(id1)
        results = store.list_techniques(sort_by="replay_count")
        assert results[0]["name"] == "A"

    def test_list_invalid_sort_by_raises(self, store):
        with pytest.raises(ValueError, match="sort_by"):
            store.list_techniques(sort_by="invalid")

    def test_corrupted_json_recovery(self, tmp_path):
        """Store recovers gracefully from corrupted JSON file."""
        filepath = tmp_path / "techniques.json"
        filepath.write_text("{corrupted json!!")
        store = TechniqueStore(base_dir=str(tmp_path))
        # Should start with empty store
        assert store.list_techniques() == []
        # Corrupt file should be renamed
        assert (tmp_path / "techniques.json.corrupt").exists()

    def test_persistence_after_update(self, store, sample_beat, tmp_path):
        tid = store.save(**sample_beat)["id"]
        store.update(tid, name="Updated Name")
        # Create new store instance from same directory
        store2 = TechniqueStore(base_dir=str(tmp_path))
        assert store2.get(tid)["name"] == "Updated Name"

    def test_persistence_after_delete(self, store, sample_beat, tmp_path):
        tid = store.save(**sample_beat)["id"]
        store.save(
            name="Other",
            type="beat_pattern",
            qualities={"summary": "x"},
            payload={},
        )
        store.delete(tid)
        store2 = TechniqueStore(base_dir=str(tmp_path))
        assert len(store2.list_techniques()) == 1
        assert store2.list_techniques()[0]["name"] == "Other"

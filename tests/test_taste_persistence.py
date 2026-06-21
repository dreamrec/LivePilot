"""Tests for persistent taste state — survives restart."""

import tempfile
from pathlib import Path

from mcp_server.persistence.base_store import PersistentJsonStore
from mcp_server.persistence.taste_store import PersistentTasteStore


# ── Base store tests ─────────────────────────────────────────────


def test_base_write_and_read():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentJsonStore(Path(d) / "test.json")
        store.write({"key": "value", "count": 42})
        assert store.read() == {"key": "value", "count": 42}


def test_base_read_nonexistent():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentJsonStore(Path(d) / "missing.json")
        assert store.read() == {}


def test_base_corrupt_recovery():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "corrupt.json"
        path.write_text("not valid json {{{")
        store = PersistentJsonStore(path)
        assert store.read() == {}
        assert (Path(d) / "corrupt.json.corrupt").exists()


def test_base_atomic_overwrite():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentJsonStore(Path(d) / "atomic.json")
        store.write({"first": True})
        store.write({"second": True})
        assert store.read() == {"second": True}
        assert not (Path(d) / "atomic.tmp").exists()


def test_base_update():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentJsonStore(Path(d) / "upd.json")
        store.write({"count": 1})
        store.update(lambda data: {**data, "count": data.get("count", 0) + 1})
        assert store.read()["count"] == 2


# ── Taste store tests ────────────────────────────────────────────


def test_move_outcome_persists():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.record_move_outcome("make_punchier", "mix", kept=True)

        store2 = PersistentTasteStore(Path(d) / "taste.json")
        data = store2.get_all()
        assert data["move_outcomes"]["make_punchier"]["kept_count"] == 1
        assert data["move_outcomes"]["make_punchier"]["family"] == "mix"
        assert data["evidence_count"] >= 1


def test_move_outcome_undone():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.record_move_outcome("widen_stereo", "mix", kept=False)

        data = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert data["move_outcomes"]["widen_stereo"]["undone_count"] == 1


def test_novelty_persists():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.update_novelty(chose_bold=True)
        store.update_novelty(chose_bold=True)

        data = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert data["novelty_band"] > 0.5


def test_device_affinity_persists():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.record_device_use("Wavetable", positive=True)

        data = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert "Wavetable" in data["device_affinities"]
        assert data["device_affinities"]["Wavetable"]["use_count"] == 1


def test_anti_preference_persists():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.record_anti_preference("width", "increase")

        data = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert any(
            a["dimension"] == "width" and a["direction"] == "increase"
            for a in data["anti_preferences"]
        )


def test_anti_preference_strength_grows():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.record_anti_preference("width", "increase")
        store.record_anti_preference("width", "increase")
        store.record_anti_preference("width", "increase")

        data = PersistentTasteStore(Path(d) / "taste.json").get_all()
        pref = next(a for a in data["anti_preferences"] if a["dimension"] == "width")
        assert pref["count"] == 3
        assert abs(pref["strength"] - 0.6) < 0.01  # 3 * 0.2


def test_dimension_weight_persists():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        store.record_dimension_weight("transition_boldness", 0.35)

        data = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert data["dimension_weights"]["transition_boldness"] == 0.35


def test_empty_store_returns_default():
    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        data = store.get_all()
        assert data["version"] == 1
        assert data["novelty_band"] == 0.5
        assert data["evidence_count"] == 0

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


# ── Tool-surface wiring (P2-29) ──────────────────────────────────────


def test_record_anti_preference_tool_persists_when_store_in_context():
    """P2-29 wiring: the record_anti_preference MCP tool must write through to
    the persistent taste store when the live context provides one, so the
    anti-preference survives a restart — not just the ephemeral session store."""
    from types import SimpleNamespace
    from mcp_server.memory.tools import record_anti_preference

    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        ctx = SimpleNamespace(lifespan_context={"persistent_taste": store})

        result = record_anti_preference(ctx, "brightness", "increase")
        assert result["persisted"] is True

        # A fresh store handle on the same file sees the persisted anti-pref.
        persisted = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert any(
            a["dimension"] == "brightness" and a["direction"] == "increase"
            for a in persisted.get("anti_preferences", [])
        )


def test_record_anti_preference_tool_session_only_without_store():
    """Hermetic fallback: with no persistent store in context (the test/headless
    case), the tool still works and reports persisted=False — it does NOT touch
    the real ~/.livepilot taste file."""
    from types import SimpleNamespace
    from mcp_server.memory.tools import record_anti_preference

    ctx = SimpleNamespace(lifespan_context={})
    result = record_anti_preference(ctx, "width", "decrease")
    assert result["persisted"] is False
    assert result["recorded"]["dimension"] == "width"


def test_record_anti_preference_tool_rejects_bad_direction():
    from types import SimpleNamespace
    from mcp_server.memory.tools import record_anti_preference

    ctx = SimpleNamespace(lifespan_context={})
    result = record_anti_preference(ctx, "width", "sideways")
    assert result.get("code") == "INVALID_PARAM"
def test_taste_graph_writes_back_device_use_and_novelty():
    """TasteGraph.record_device_use / update_novelty_from_experiment must
    persist through the attached PersistentTasteStore so they survive restart.
    Regression: previously only record_move_outcome wrote back."""
    import tempfile
    from pathlib import Path
    from mcp_server.persistence.taste_store import PersistentTasteStore
    from mcp_server.memory.taste_graph import build_taste_graph

    with tempfile.TemporaryDirectory() as d:
        store_path = Path(d) / "taste.json"
        store = PersistentTasteStore(store_path)
        graph = build_taste_graph(persistent_store=store)

        graph.record_device_use("Granulator III", positive=True)
        graph.update_novelty_from_experiment(chose_bold=True, goal_mode="explore")

        # New process / store handle reading the same file must see the writes.
        store2 = PersistentTasteStore(store_path)
        persisted = store2.get_all()

        assert "Granulator III" in persisted.get("device_affinities", {})
        assert persisted["device_affinities"]["Granulator III"]["use_count"] == 1
        assert persisted["device_affinities"]["Granulator III"]["affinity"] > 0.0

        # explore band shifted up from default 0.5
        assert persisted.get("novelty_bands", {}).get("explore", 0.5) > 0.5

        # And a freshly built graph hydrates those persisted values.
        graph2 = build_taste_graph(persistent_store=store2)
        assert "Granulator III" in graph2.device_affinities
        assert graph2.novelty_bands.get("explore", 0.5) > 0.5


def test_taste_graph_writes_back_anti_pref_and_dimension_weight():
    """P2-29: TasteGraph.record_anti_preference / record_dimension_weight must
    persist through the attached PersistentTasteStore so dimension taste and
    avoidances survive a restart. Regression: previously the persisted
    anti_preferences / dimension_weights read branches in build_taste_graph
    were dead because nothing ever wrote those fields."""
    import tempfile
    from pathlib import Path
    from mcp_server.persistence.taste_store import PersistentTasteStore
    from mcp_server.memory.taste_graph import build_taste_graph

    with tempfile.TemporaryDirectory() as d:
        store_path = Path(d) / "taste.json"
        store = PersistentTasteStore(store_path)
        graph = build_taste_graph(persistent_store=store)

        graph.record_anti_preference("brightness", "increase")
        graph.record_dimension_weight("transition_boldness", 0.35)

        # In-memory state reflects the writes immediately.
        assert graph.dimension_avoidances["brightness"] == "increase"
        assert graph.dimension_weights["transition_boldness"] == 0.35

        # A separate store handle reading the same file must see the writes.
        store2 = PersistentTasteStore(store_path)
        persisted = store2.get_all()
        assert any(
            a["dimension"] == "brightness" and a["direction"] == "increase"
            for a in persisted.get("anti_preferences", [])
        )
        assert persisted.get("dimension_weights", {})["transition_boldness"] == 0.35

        # A freshly built graph (no session stores) hydrates the persisted
        # dimension weight and anti-preference from disk — proving the read
        # branches are no longer dead.
        graph2 = build_taste_graph(persistent_store=store2)
        assert graph2.dimension_avoidances.get("brightness") == "increase"
        assert graph2.dimension_weights.get("transition_boldness") == 0.35

def test_record_positive_preference_persists_dimension_weight():
    """P2-29 (dimension-weight half): the record_positive_preference MCP tool
    must persist the updated dimension weight through the lifespan taste store so
    it survives a restart — previously the write-back was dead (no caller)."""
    from types import SimpleNamespace
    from mcp_server.memory.tools import record_positive_preference

    with tempfile.TemporaryDirectory() as d:
        store = PersistentTasteStore(Path(d) / "taste.json")
        ctx = SimpleNamespace(lifespan_context={"persistent_taste": store})

        result = record_positive_preference(ctx, "warmth", "increase")
        assert result.get("recorded") is True
        assert result.get("persisted") is True
        persisted = PersistentTasteStore(Path(d) / "taste.json").get_all()
        assert persisted.get("dimension_weights", {})["warmth"] > 0


def test_record_positive_preference_session_only_without_store():
    """Hermetic fallback: no persistent store in context → persisted False, no
    write to the real ~/.livepilot taste file."""
    from types import SimpleNamespace
    from mcp_server.memory.tools import record_positive_preference

    ctx = SimpleNamespace(lifespan_context={})
    result = record_positive_preference(ctx, "warmth", "increase")
    assert result.get("recorded") is True
    assert result.get("persisted") is False


def test_record_positive_preference_accepts_open_quality_dimensions():
    from types import SimpleNamespace
    from mcp_server.memory.tools import record_positive_preference

    ctx = SimpleNamespace(lifespan_context={})
    for dimension in ("warmth", "width", "punch"):
        result = record_positive_preference(ctx, dimension, "increase")
        assert result["recorded"] is True
        assert result["dimension"] == dimension
        assert result["value"] > 0

    invalid = record_positive_preference(ctx, "warmth", "sideways")
    assert invalid["code"] == "INVALID_PARAM"

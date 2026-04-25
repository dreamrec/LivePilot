# tests/test_overlay_loader.py
"""Tests for mcp_server/atlas/overlays.py — user-local atlas overlay loader.

Per spec: docs/superpowers/specs/2026-04-25-user-local-extensions-design.md §8.1
"""
from __future__ import annotations
from pathlib import Path
import pytest


def test_overlay_entry_dataclass_has_required_fields():
    """OverlayEntry must expose namespace, entity_type, entity_id, name,
    description, tags, artists, requires_box, body. The field name is
    `entity_id` (NOT `id` — avoids shadowing the Python builtin)."""
    from mcp_server.atlas.overlays import OverlayEntry

    entry = OverlayEntry(
        namespace="elektron",
        entity_type="signature_chain",
        entity_id="sophie_ponyboy_kick",
        name="SOPHIE — Ponyboy kick",
        description="3-track recipe",
        tags=["kick", "sophie"],
        artists=["sophie_xeon"],
        requires_box="monomachine",
        body={"foo": "bar"},
    )
    assert entry.namespace == "elektron"
    assert entry.entity_type == "signature_chain"
    assert entry.entity_id == "sophie_ponyboy_kick"
    assert entry.body == {"foo": "bar"}


def test_overlay_index_get_returns_entry_by_namespace_and_id():
    from mcp_server.atlas.overlays import OverlayEntry, OverlayIndex
    idx = OverlayIndex()
    e = OverlayEntry(
        namespace="elektron", entity_type="machine",
        entity_id="mm_sid_6581", name="SID 6581",
        description="Commodore 64 SID emulation",
        tags=["sid", "monomachine"], artists=[],
        requires_box="monomachine", body={"family": "SID"},
    )
    idx.add(e)
    assert idx.get("elektron", "mm_sid_6581") is e
    assert idx.get("elektron", "nonexistent") is None
    assert idx.get("nonexistent_ns", "mm_sid_6581") is None


def test_overlay_index_list_namespaces():
    from mcp_server.atlas.overlays import OverlayEntry, OverlayIndex
    idx = OverlayIndex()
    idx.add(OverlayEntry(namespace="elektron", entity_type="machine",
                         entity_id="a", name="A", description="",
                         tags=[], artists=[], requires_box=None, body={}))
    idx.add(OverlayEntry(namespace="prophet", entity_type="patch",
                         entity_id="b", name="B", description="",
                         tags=[], artists=[], requires_box=None, body={}))
    assert sorted(idx.list_namespaces()) == ["elektron", "prophet"]


def test_overlay_index_list_entity_types_in_namespace():
    from mcp_server.atlas.overlays import OverlayEntry, OverlayIndex
    idx = OverlayIndex()
    idx.add(OverlayEntry(namespace="elektron", entity_type="machine",
                         entity_id="a", name="A", description="",
                         tags=[], artists=[], requires_box=None, body={}))
    idx.add(OverlayEntry(namespace="elektron", entity_type="signature_chain",
                         entity_id="b", name="B", description="",
                         tags=["x"], artists=["y"], requires_box=None, body={}))
    assert sorted(idx.list_entity_types("elektron")) == ["machine", "signature_chain"]
    assert idx.list_entity_types("nonexistent") == []


def _mk_entry(*, namespace="ns", entity_type="machine", entity_id="x",
              name="X", description="", tags=None, artists=None,
              requires_box=None, body=None):
    """Test helper — keyword-only construction so failures point at the missing field.

    Introduced in Task 5 to reduce test duplication. Earlier Tasks 1+3 tests
    intentionally use the verbose form to document the OverlayEntry contract;
    new tests use this helper.
    """
    from mcp_server.atlas.overlays import OverlayEntry
    return OverlayEntry(
        namespace=namespace, entity_type=entity_type, entity_id=entity_id,
        name=name, description=description,
        tags=tags or [], artists=artists or [],
        requires_box=requires_box, body=body or {},
    )


def test_overlay_index_search_substring_in_name():
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    idx.add(_mk_entry(entity_id="a", name="SOPHIE Ponyboy kick"))
    idx.add(_mk_entry(entity_id="b", name="Jimmy Edgar metallic perc"))
    results = idx.search("sophie")
    assert len(results) == 1 and results[0].entity_id == "a"


def test_overlay_index_search_substring_in_tags():
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    idx.add(_mk_entry(entity_id="a", name="X", tags=["dub_techno"]))
    idx.add(_mk_entry(entity_id="b", name="Y", tags=["hyperpop"]))
    results = idx.search("dub")
    assert len(results) == 1 and results[0].entity_id == "a"


def test_overlay_index_search_namespace_filter():
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    idx.add(_mk_entry(namespace="elektron", entity_id="a", name="thing"))
    idx.add(_mk_entry(namespace="prophet", entity_id="b", name="thing"))
    results = idx.search("thing", namespace="elektron")
    assert len(results) == 1 and results[0].namespace == "elektron"


def test_overlay_index_search_entity_type_filter():
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    idx.add(_mk_entry(entity_type="machine", entity_id="a", name="thing"))
    idx.add(_mk_entry(entity_type="signature_chain", entity_id="b",
                      name="thing", tags=["t"], artists=["x"]))
    results = idx.search("thing", entity_type="machine")
    assert len(results) == 1 and results[0].entity_type == "machine"


def test_overlay_index_search_exact_id_scores_highest():
    """Per spec §5.1: exact entity_id match scores highest, then name, then tags/artists, then description."""
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    idx.add(_mk_entry(entity_id="other_thing", name="contains exact_match in name"))
    idx.add(_mk_entry(entity_id="exact_match", name="other name"))
    results = idx.search("exact_match")
    assert results[0].entity_id == "exact_match"


def test_overlay_index_search_limit():
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    for i in range(20):
        idx.add(_mk_entry(entity_id=f"e{i}", name=f"thing {i}"))
    assert len(idx.search("thing", limit=5)) == 5
    assert len(idx.search("thing", limit=10)) == 10


def test_overlay_index_stats_smoke():
    """stats() returns nested {namespace: {entity_type: count}} per spec §5.3."""
    from mcp_server.atlas.overlays import OverlayIndex
    idx = OverlayIndex()
    idx.add(_mk_entry(namespace="elektron", entity_type="machine", entity_id="a"))
    idx.add(_mk_entry(namespace="elektron", entity_type="machine", entity_id="b"))
    idx.add(_mk_entry(namespace="elektron", entity_type="signature_chain",
                      entity_id="c", tags=["t"], artists=["x"]))
    s = idx.stats()
    assert s == {"elektron": {"machine": 2, "signature_chain": 1}}


def test_resolve_overlay_root_uses_path_home(monkeypatch, tmp_path):
    """Critical: _resolve_overlay_root() evaluates Path.home() at CALL time,
    not import time. Tests must be able to monkeypatch Path.home() and
    expect the new value (no module-level capture). Per spec §5.1."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    from mcp_server.atlas.overlays import _resolve_overlay_root
    root = _resolve_overlay_root()
    assert root == fake_home / ".livepilot" / "atlas-overlays"


def test_load_overlays_missing_root_returns_empty_index(tmp_path):
    """Missing root → empty index, NO exception. Per spec §7."""
    from mcp_server.atlas.overlays import load_overlays
    idx = load_overlays(root=tmp_path / "does-not-exist")
    assert idx.list_namespaces() == []


def test_load_overlays_loads_simple_yaml(tmp_path):
    from mcp_server.atlas.overlays import load_overlays
    ns_dir = tmp_path / "elektron"
    ns_dir.mkdir(parents=True)
    (ns_dir / "machines.yaml").write_text(
        "entity_id: mm_sid_6581\n"
        "entity_type: machine\n"
        "name: SID 6581\n"
        "description: SID emulation\n"
        "tags: [sid, monomachine]\n"
    )
    idx = load_overlays(root=tmp_path)
    assert idx.list_namespaces() == ["elektron"]
    assert idx.get("elektron", "mm_sid_6581").name == "SID 6581"


def test_load_overlays_loads_list_form(tmp_path):
    from mcp_server.atlas.overlays import load_overlays
    ns_dir = tmp_path / "elektron"
    ns_dir.mkdir(parents=True)
    (ns_dir / "things.yaml").write_text(
        "- entity_id: a\n  entity_type: machine\n  name: A\n  description: x\n"
        "- entity_id: b\n  entity_type: machine\n  name: B\n  description: y\n"
    )
    idx = load_overlays(root=tmp_path)
    assert idx.get("elektron", "a") is not None
    assert idx.get("elektron", "b") is not None


def test_load_overlays_idempotent(tmp_path):
    """Calling load_overlays twice with same root produces identical singleton state."""
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "x.yaml").write_text("entity_id: a\nentity_type: machine\nname: A\ndescription: x\n")

    idx1 = load_overlays(root=tmp_path)
    snap1 = sorted([(e.namespace, e.entity_type, e.entity_id) for e in idx1.all_entries()])
    idx2 = load_overlays(root=tmp_path)
    snap2 = sorted([(e.namespace, e.entity_type, e.entity_id) for e in idx2.all_entries()])
    assert snap1 == snap2 and idx1 is idx2  # same singleton


def test_load_overlays_skips_invalid_yaml(tmp_path, caplog):
    """Bad YAML → file skipped, others continue, WARN logged."""
    import logging
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "good.yaml").write_text("entity_id: a\nentity_type: machine\nname: A\ndescription: x\n")
    (ns / "bad.yaml").write_text(": : : not valid yaml : :\n")

    with caplog.at_level(logging.WARNING):
        idx = load_overlays(root=tmp_path)

    assert idx.get("elektron", "a") is not None
    assert any("bad.yaml" in r.message for r in caplog.records)


def test_load_overlays_rejects_unsafe_yaml_tags(tmp_path, caplog):
    """YAML with !!python tags is rejected by safe_load. Per spec §7.

    Key behavior: ANY !!python/* tag is rejected by safe_load, regardless of
    whether the underlying object would be benign or harmful. We use a benign
    Python tag here just to demonstrate the rejection — the loader treats all
    !!python/* tags identically (logged + skipped).

    This test also defends against a future maintainer naively swapping
    yaml.safe_load for yaml.load(Loader=yaml.FullLoader) — that swap would
    break security and this test would catch it.
    """
    import logging
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "tagged.yaml").write_text(
        "entity_id: x\n"
        "entity_type: machine\n"
        "name: !!python/name:datetime.datetime\n"
        "description: hax\n"
    )
    with caplog.at_level(logging.WARNING):
        idx = load_overlays(root=tmp_path)
    assert idx.get("elektron", "x") is None
    assert any("tagged.yaml" in r.message for r in caplog.records)


def test_load_overlays_missing_required_field(tmp_path, caplog):
    """Entry missing entity_id → skipped + WARN logged."""
    import logging
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "x.yaml").write_text("entity_type: machine\nname: A\ndescription: x\n")

    with caplog.at_level(logging.WARNING):
        idx = load_overlays(root=tmp_path)

    assert idx.list_namespaces() == []
    assert any("entity_id" in r.message for r in caplog.records)


def test_signature_chain_required_fields(tmp_path, caplog):
    """signature_chain entries missing tags or artists → skipped. Per spec §5.1."""
    import logging
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "missing_tags.yaml").write_text(
        "entity_id: a\nentity_type: signature_chain\nname: A\ndescription: x\nartists: [sophie]\n"
    )
    (ns / "missing_artists.yaml").write_text(
        "entity_id: b\nentity_type: signature_chain\nname: B\ndescription: x\ntags: [k]\n"
    )
    (ns / "machine_no_tags_ok.yaml").write_text(
        "entity_id: c\nentity_type: machine\nname: C\ndescription: x\n"
    )
    with caplog.at_level(logging.WARNING):
        idx = load_overlays(root=tmp_path)

    assert idx.get("elektron", "a") is None  # skipped
    assert idx.get("elektron", "b") is None  # skipped
    assert idx.get("elektron", "c") is not None  # machine OK without tags/artists


def test_load_overlays_duplicate_id_last_wins(tmp_path, caplog):
    """Two YAMLs with same (namespace, entity_type, entity_id) → second overwrites; WARN logged."""
    import logging
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "01_first.yaml").write_text(
        "entity_id: dup\nentity_type: machine\nname: First\ndescription: x\n"
    )
    (ns / "02_second.yaml").write_text(
        "entity_id: dup\nentity_type: machine\nname: Second\ndescription: x\n"
    )
    with caplog.at_level(logging.WARNING):
        idx = load_overlays(root=tmp_path)
    assert idx.get("elektron", "dup").name == "Second"
    assert any("duplicate" in r.message.lower() for r in caplog.records)


def test_load_overlays_coerces_entity_id_and_type_to_str(tmp_path):
    """Defends against integer entity_ids (e.g., YAML `entity_id: 42`)
    breaking downstream search() which calls .lower() on the field.
    Per Tasks 7+8 code reviewer M1 (folded into Task 9)."""
    from mcp_server.atlas.overlays import load_overlays
    ns = tmp_path / "elektron"
    ns.mkdir(parents=True)
    (ns / "int_id.yaml").write_text(
        "entity_id: 42\nentity_type: machine\nname: AnswerMachine\ndescription: x\n"
    )
    idx = load_overlays(root=tmp_path)
    entry = idx.get("elektron", "42")
    assert entry is not None
    assert entry.entity_id == "42"
    assert isinstance(entry.entity_id, str)
    assert isinstance(entry.entity_type, str)
    # Downstream sanity: search must not raise AttributeError
    results = idx.search("answer")
    assert len(results) == 1

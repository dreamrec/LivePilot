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


def _mk_entry(namespace="ns", entity_type="machine", entity_id="x",
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

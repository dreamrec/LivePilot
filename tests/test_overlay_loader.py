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

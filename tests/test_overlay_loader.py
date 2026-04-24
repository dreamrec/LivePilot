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

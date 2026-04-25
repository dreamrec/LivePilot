# tests/test_extension_atlas_tools.py
"""Tests for the 3 new MCP tools added in v1.23.0 by atlas overlays.

Per spec: docs/superpowers/specs/2026-04-25-user-local-extensions-design.md §5.3, §8.1
"""
from __future__ import annotations
from pathlib import Path
import pytest


def _seed_overlay(monkeypatch, tmp_path: Path):
    """Helper: monkeypatch Path.home(), drop a fixture overlay, force load_overlays()."""
    fake_home = tmp_path / "fake_home"
    overlay_root = fake_home / ".livepilot" / "atlas-overlays" / "elektron"
    overlay_root.mkdir(parents=True)
    (overlay_root / "fixture.yaml").write_text(
        "- entity_id: sophie_ponyboy_kick\n"
        "  entity_type: signature_chain\n"
        "  name: SOPHIE Ponyboy kick\n"
        "  description: 3-track recipe\n"
        "  tags: [kick, sophie]\n"
        "  artists: [sophie_xeon]\n"
        "  requires_box: monomachine\n"
        "  requires_firmware: { monomachine: '1.32' }\n"
        "- entity_id: mm_sid_6581\n"
        "  entity_type: machine\n"
        "  name: SID 6581\n"
        "  description: SID emulation\n"
        "  tags: [sid, monomachine]\n"
    )
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    from mcp_server.atlas.overlays import load_overlays
    load_overlays()


def test_extension_atlas_search_returns_overlay_results(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_search
    result = extension_atlas_search(ctx=None, query="sophie")
    assert result["count"] == 1
    assert result["results"][0]["entity_id"] == "sophie_ponyboy_kick"


def test_extension_atlas_search_namespace_filter(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_search
    result = extension_atlas_search(ctx=None, query="sid", namespace="prophet")
    assert result["count"] == 0


def test_extension_atlas_search_entity_type_filter(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_search
    result = extension_atlas_search(ctx=None, query="sid", entity_type="signature_chain")
    assert result["count"] == 0  # mm_sid_6581 is entity_type=machine


def test_extension_atlas_get_returns_full_entry(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_get
    entry = extension_atlas_get(ctx=None, namespace="elektron",
                                entity_id="sophie_ponyboy_kick")
    assert entry["entity_id"] == "sophie_ponyboy_kick"
    assert entry["body"]["requires_box"] == "monomachine"


def test_extension_atlas_get_returns_requires_firmware(monkeypatch, tmp_path):
    """Per spec §7: get must surface requires_firmware so Claude can warn."""
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_get
    entry = extension_atlas_get(ctx=None, namespace="elektron",
                                entity_id="sophie_ponyboy_kick")
    assert entry["body"]["requires_firmware"] == {"monomachine": "1.32"}


def test_extension_atlas_get_returns_error_for_missing(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_get
    entry = extension_atlas_get(ctx=None, namespace="elektron",
                                entity_id="does_not_exist")
    assert "error" in entry


def test_extension_atlas_list_enumerates_namespaces(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_list
    result = extension_atlas_list(ctx=None)
    assert "elektron" in result["namespaces"]
    assert result["counts"]["elektron"]["signature_chain"] == 1
    assert result["counts"]["elektron"]["machine"] == 1


def test_extension_atlas_list_namespace_filter(monkeypatch, tmp_path):
    _seed_overlay(monkeypatch, tmp_path)
    from mcp_server.atlas.tools import extension_atlas_list
    result = extension_atlas_list(ctx=None, namespace="elektron")
    assert result["entity_types"] == ["machine", "signature_chain"]

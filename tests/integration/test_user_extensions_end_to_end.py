# tests/integration/test_user_extensions_end_to_end.py
"""End-to-end integration test for v1.23.0 user-local atlas overlays.

Verifies the full path: overlay YAML on disk → load_overlays() →
OverlayIndex singleton → extension_atlas_search MCP tool → expected JSON shape.
"""
from __future__ import annotations
from pathlib import Path
import pytest


def test_full_overlay_pipeline(monkeypatch, tmp_path):
    """Drop a YAML, point Path.home() at the tmp dir, call load_overlays(),
    then call extension_atlas_search and verify the returned shape."""
    # 1. Set up the overlay tree
    fake_home = tmp_path / "fake_home"
    overlay_dir = fake_home / ".livepilot" / "atlas-overlays" / "elektron" / "signature_chains"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "sophie_ponyboy_kick.yaml").write_text("""
entity_id: sophie_ponyboy_kick
entity_type: signature_chain
name: "SOPHIE — Ponyboy kick (3-track Monomachine recipe)"
description: |
  The signature mechanical-animal kick from Ponyboy.
artists: [sophie_xeon]
tags: [kick, distorted, mechanical, sophie]
requires_box: monomachine
requires_machines: [SID, GND-NOIS, FX-THRU]
architecture:
  tracks:
    T1:
      machine: SID
      waveform: TRIANGLE
""".strip())

    # 2. Monkeypatch Path.home() so the loader sees our fake tree
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # 3. Force a load (mirrors what server.py boot does)
    from mcp_server.atlas.overlays import load_overlays
    load_overlays()

    # 4. Call the MCP tool
    from mcp_server.atlas.tools import extension_atlas_search
    result = extension_atlas_search(ctx=None, query="ponyboy")

    # 5. Assert the shape and content
    assert result["count"] == 1
    entry = result["results"][0]
    assert entry["entity_id"] == "sophie_ponyboy_kick"
    assert entry["entity_type"] == "signature_chain"
    assert entry["namespace"] == "elektron"
    assert entry["requires_box"] == "monomachine"
    assert entry["body"]["architecture"]["tracks"]["T1"]["machine"] == "SID"


def test_full_pipeline_handles_missing_overlay_dir(monkeypatch, tmp_path):
    """No overlay dir → load_overlays() succeeds, search returns nothing."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    from mcp_server.atlas.overlays import load_overlays
    load_overlays()  # must not raise

    from mcp_server.atlas.tools import extension_atlas_search
    result = extension_atlas_search(ctx=None, query="anything")
    assert result["count"] == 0

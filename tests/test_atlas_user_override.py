"""User atlas override — v1.22.0.

Personal scans written by ``scan_full_library`` land in
``~/.livepilot/atlas/device_atlas.json`` (the user-data convention shared
with ``~/.livepilot/memory/``), not in the package directory. The atlas
resolver prefers the user path when it exists, falling back to the
bundled baseline otherwise.

This split solves three prior problems:

1. **npm-update-wipes-scan** — previously every ``npm install livepilot``
   overwrote the installed package's ``device_atlas.json``, blowing away
   any personalized scan.
2. **Repo pollution from dev installs** — contributors running the dev
   checkout would accidentally commit their personal scan (pack names,
   user-library previews) to the repo.
3. **Ambiguous "enriched" semantic** — having a single atlas file serve
   as bundled baseline, personal scan, and runtime cache made the
   "how many devices are enriched?" number mean three different things.

Tests mirror the real resolver + write path without requiring a live
Ableton session (which is why ``scan_full_library``'s live-scan branch
is not end-to-end tested here — we test the write-target resolution
directly).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def atlas_module():
    """Reload ``mcp_server.atlas`` on each use so monkeypatched HOME env
    vars are honored by the fresh module's path computations."""
    # Drop any cached copy so module-level constants are recomputed.
    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        mod = importlib.import_module("mcp_server.atlas")
    finally:
        sys.path.remove(str(REPO_ROOT))
    return mod


def test_bundled_path_is_in_package_dir(atlas_module):
    """``BUNDLED_ATLAS_PATH`` must live inside ``mcp_server/atlas/`` so
    the npm-published package ships with a usable baseline."""
    assert atlas_module.BUNDLED_ATLAS_PATH.name == "device_atlas.json"
    assert atlas_module.BUNDLED_ATLAS_PATH.parent.name == "atlas"
    assert atlas_module.BUNDLED_ATLAS_PATH.parent.parent.name == "mcp_server"


def test_user_path_is_in_home_dir(atlas_module):
    """``USER_ATLAS_PATH`` must live under ``~/.livepilot/atlas/`` —
    same convention as memory/technique stores. Checks the pattern,
    not an absolute path (the real HOME varies across machines and
    CI environments)."""
    parts = atlas_module.USER_ATLAS_PATH.parts
    assert ".livepilot" in parts
    assert "atlas" in parts
    assert parts[-1] == "device_atlas.json"


def test_resolver_returns_user_path_when_present(tmp_path, monkeypatch):
    """When the user atlas exists, the resolver must return it —
    not the bundled path. This is the "personalized scan wins"
    invariant."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows: Path.home() reads USERPROFILE, not HOME. Patch both so the
    # test works on POSIX + Windows. (Production code has nothing to do —
    # Path.home() is already cross-platform; this is a pytest concern only.)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    user_atlas = tmp_path / ".livepilot" / "atlas" / "device_atlas.json"
    user_atlas.parent.mkdir(parents=True)
    user_atlas.write_text(json.dumps({
        "version": "2.0.0",
        "live_version": "12.4.0",
        "scanned_at": "2026-04-25T00:00:00Z",
        "stats": {"total_devices": 99, "enriched_devices": 7},
        "devices": [],
        "packs": [],
    }))

    # Reload the atlas module AFTER HOME is patched so USER_ATLAS_PATH
    # resolves to the tmp_path copy.
    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        mod = importlib.import_module("mcp_server.atlas")
    finally:
        sys.path.remove(str(REPO_ROOT))

    assert mod._resolve_atlas_path() == mod.USER_ATLAS_PATH
    assert mod._resolve_atlas_path() == user_atlas


def test_resolver_falls_back_to_bundled_when_user_atlas_missing(
    tmp_path, monkeypatch
):
    """When ``~/.livepilot/atlas/device_atlas.json`` doesn't exist,
    the resolver falls back to the bundled baseline. This is the
    fresh-install case."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows: Path.home() reads USERPROFILE, not HOME. Patch both so the
    # test works on POSIX + Windows. (Production code has nothing to do —
    # Path.home() is already cross-platform; this is a pytest concern only.)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # Deliberately do NOT create the user atlas.

    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        mod = importlib.import_module("mcp_server.atlas")
    finally:
        sys.path.remove(str(REPO_ROOT))

    assert mod._resolve_atlas_path() == mod.BUNDLED_ATLAS_PATH
    # Sanity: the bundled path must actually exist for the fallback to
    # be meaningful (the repo must ship a baseline).
    assert mod.BUNDLED_ATLAS_PATH.exists()


def test_atlas_manager_loads_from_user_path_when_present(tmp_path, monkeypatch):
    """Integration: with HOME pointed at a tmp dir containing a user
    atlas, ``get_atlas()`` must return an AtlasManager whose data
    reflects the user atlas — not the bundled baseline."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows: Path.home() reads USERPROFILE, not HOME. Patch both so the
    # test works on POSIX + Windows. (Production code has nothing to do —
    # Path.home() is already cross-platform; this is a pytest concern only.)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    user_atlas = tmp_path / ".livepilot" / "atlas" / "device_atlas.json"
    user_atlas.parent.mkdir(parents=True)
    user_atlas.write_text(json.dumps({
        "version": "2.0.0",
        "live_version": "12.4.0",
        "scanned_at": "2026-04-25T00:00:00Z",
        "stats": {"total_devices": 99, "enriched_devices": 7},
        "devices": [
            {"id": "fake", "name": "Fake", "uri": None, "category": "instruments",
             "subcategory": "other", "source": "native", "enriched": False,
             "character_tags": [], "use_cases": [], "self_contained": True,
             "key_parameters": [], "pairs_well_with": [], "starter_recipes": [],
             "gotchas": [], "health_flags": []}
        ],
        "packs": [],
    }))

    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        mod = importlib.import_module("mcp_server.atlas")
    finally:
        sys.path.remove(str(REPO_ROOT))

    atlas = mod.get_atlas()
    # User atlas has exactly 1 device named "Fake" — the bundled baseline
    # has thousands. If the resolver picked the wrong one, this fails.
    assert atlas.device_count == 1
    fake = atlas.lookup("fake")
    assert fake is not None
    assert fake["name"] == "Fake"


def test_atlas_manager_falls_back_to_bundled_when_user_atlas_missing(
    tmp_path, monkeypatch
):
    """Integration: with HOME pointed at an empty tmp dir (no user
    atlas), ``get_atlas()`` loads the bundled baseline. Device count
    should match the shipped v1.21.4 baseline (5264)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows: Path.home() reads USERPROFILE, not HOME. Patch both so the
    # test works on POSIX + Windows. (Production code has nothing to do —
    # Path.home() is already cross-platform; this is a pytest concern only.)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        mod = importlib.import_module("mcp_server.atlas")
    finally:
        sys.path.remove(str(REPO_ROOT))

    atlas = mod.get_atlas()
    # Bundled baseline is the repo's own device_atlas.json — whatever
    # count it currently reports should match, not 1.
    expected = json.loads(mod.BUNDLED_ATLAS_PATH.read_text())
    assert atlas.device_count == expected["stats"]["total_devices"]
    # Loose upper-bound sanity: the bundled baseline is NOT the tiny
    # user-atlas fixture.
    assert atlas.device_count > 100


def test_scan_full_library_writes_to_user_path(tmp_path, monkeypatch):
    """The ``scan_full_library`` MCP tool must write to the user atlas
    path, NOT the bundled baseline. Full live-scan path requires Ableton
    so we short-circuit by mocking ``ableton.send_command`` and
    asserting the write target.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows: Path.home() reads USERPROFILE, not HOME. Patch both so the
    # test works on POSIX + Windows. (Production code has nothing to do —
    # Path.home() is already cross-platform; this is a pytest concern only.)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    # Fresh import after HOME change.
    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        atlas_mod = importlib.import_module("mcp_server.atlas")
        tools_mod = importlib.import_module("mcp_server.atlas.tools")
    finally:
        sys.path.remove(str(REPO_ROOT))

    # Fake Ableton client — returns an empty but well-shaped browser payload.
    class _FakeAbleton:
        def send_command(self, cmd, payload=None):
            if cmd == "scan_browser_deep":
                return {"categories": {
                    "instruments": [
                        {"name": "Operator", "uri": "ableton:operator",
                         "is_loadable": True},
                    ]
                }, "counts": {"instruments": 1}}
            if cmd == "get_session_info":
                return {"live_version": "12.4.0"}
            return {}

    # Mock _get_ableton — returns our fake client.
    monkeypatch.setattr(tools_mod, "_get_ableton", lambda ctx: _FakeAbleton())

    result = tools_mod.scan_full_library(
        ctx=None, force=True, max_per_category=10
    )

    # 1. Expect the scan to succeed and report the user atlas path.
    assert result["status"] == "scanned"
    assert result["atlas_path"] == str(atlas_mod.USER_ATLAS_PATH)

    # 2. Expect the bundled path NOT to be modified by the scan. (We
    # can't compare mtimes here because a prior test may have loaded it,
    # but we can confirm the user atlas was written.)
    assert atlas_mod.USER_ATLAS_PATH.exists()

    # 3. The written file should contain the fake device.
    written = json.loads(atlas_mod.USER_ATLAS_PATH.read_text())
    assert written["stats"]["total_devices"] == 1
    assert written["devices"][0]["name"] == "Operator"


def test_user_atlas_dir_created_if_missing(tmp_path, monkeypatch):
    """First-run scenario: no ``~/.livepilot/atlas/`` directory yet.
    ``scan_full_library`` must create it before writing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows: Path.home() reads USERPROFILE, not HOME. Patch both so the
    # test works on POSIX + Windows. (Production code has nothing to do —
    # Path.home() is already cross-platform; this is a pytest concern only.)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # Explicitly: HOME/.livepilot does not exist yet.
    assert not (tmp_path / ".livepilot").exists()

    for name in list(sys.modules):
        if name == "mcp_server.atlas" or name.startswith("mcp_server.atlas."):
            del sys.modules[name]
    sys.path.insert(0, str(REPO_ROOT))
    try:
        atlas_mod = importlib.import_module("mcp_server.atlas")
        tools_mod = importlib.import_module("mcp_server.atlas.tools")
    finally:
        sys.path.remove(str(REPO_ROOT))

    class _FakeAbleton:
        def send_command(self, cmd, payload=None):
            if cmd == "scan_browser_deep":
                return {"categories": {"instruments": []}, "counts": {}}
            if cmd == "get_session_info":
                return {"live_version": "12.4.0"}
            return {}

    monkeypatch.setattr(tools_mod, "_get_ableton", lambda ctx: _FakeAbleton())

    tools_mod.scan_full_library(ctx=None, force=True, max_per_category=10)

    # Directory was auto-created
    assert (tmp_path / ".livepilot" / "atlas").is_dir()
    assert atlas_mod.USER_ATLAS_PATH.exists()

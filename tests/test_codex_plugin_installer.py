"""Tests for the bundled Codex plugin installer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


NODE = shutil.which("node")


pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_node(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [NODE, *args],
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_install_codex_plugin_updates_temp_marketplace(tmp_path: Path):
    expected_manifest = json.loads((_repo_root() / "livepilot" / ".Codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    plugin_dir = tmp_path / "plugins" / "livepilot"
    cache_dir = tmp_path / ".codex" / "plugins" / "cache" / "local-plugins" / "livepilot" / expected_manifest["version"]
    marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"
    env = os.environ.copy()
    env["LIVEPILOT_CODEX_PLUGIN_PATH"] = str(plugin_dir)
    env["LIVEPILOT_CODEX_CACHE_PATH"] = str(cache_dir)
    env["LIVEPILOT_CODEX_MARKETPLACE_PATH"] = str(marketplace)

    _run_node(["-e", "require('./installer/codex.js').installCodexPlugin()"], env=env)

    manifest = json.loads((plugin_dir / ".Codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == expected_manifest["name"]
    assert manifest["version"] == expected_manifest["version"]
    canonical_manifest = json.loads((plugin_dir / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert canonical_manifest["name"] == expected_manifest["name"]
    cached_manifest = json.loads((cache_dir / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert cached_manifest["version"] == expected_manifest["version"]

    mcp_config = json.loads((plugin_dir / ".mcp.json").read_text(encoding="utf-8"))
    # `process.execPath` (used by installer/codex.js) returns the canonical
    # node path (e.g. /opt/homebrew/Cellar/node/X.Y.Z/bin/node), while
    # `shutil.which("node")` returns the PATH-resolved symlink
    # (/opt/homebrew/bin/node). Compare `os.path.realpath` of both so the
    # test passes regardless of which form the installer wrote.
    # (os is already imported at module top — do NOT re-import here or
    # Python's function-scope rules will shadow the module-level os for
    # the entire function, breaking earlier os.environ usage.)
    actual = os.path.realpath(mcp_config["mcpServers"]["livepilot"]["command"])
    expected = os.path.realpath(NODE) if NODE else NODE
    assert actual == expected
    assert mcp_config["mcpServers"]["livepilot"]["args"] == [
        str(_repo_root() / "bin" / "livepilot.js")
    ]
    assert (cache_dir / ".mcp.json").exists()
    assert (cache_dir / "skills" / "livepilot-creative-director" / "SKILL.md").exists()

    marketplace_data = json.loads(marketplace.read_text(encoding="utf-8"))
    entry = next(plugin for plugin in marketplace_data["plugins"] if plugin["name"] == "livepilot")
    assert entry["source"]["path"] == "./plugins/livepilot"
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"


def test_uninstall_codex_plugin_removes_plugin_and_marketplace_entry(tmp_path: Path):
    expected_manifest = json.loads((_repo_root() / "livepilot" / ".Codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    plugin_dir = tmp_path / "plugins" / "livepilot"
    cache_dir = tmp_path / ".codex" / "plugins" / "cache" / "local-plugins" / "livepilot" / expected_manifest["version"]
    marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"
    env = os.environ.copy()
    env["LIVEPILOT_CODEX_PLUGIN_PATH"] = str(plugin_dir)
    env["LIVEPILOT_CODEX_CACHE_PATH"] = str(cache_dir)
    env["LIVEPILOT_CODEX_MARKETPLACE_PATH"] = str(marketplace)

    _run_node(["-e", "const m = require('./installer/codex.js'); m.installCodexPlugin(); m.uninstallCodexPlugin();"], env=env)

    assert not plugin_dir.exists()
    assert not cache_dir.exists()
    marketplace_data = json.loads(marketplace.read_text(encoding="utf-8"))
    assert all(plugin["name"] != "livepilot" for plugin in marketplace_data["plugins"])


def test_install_codex_plugin_prunes_stale_cache_versions(tmp_path: Path):
    expected_manifest = json.loads((_repo_root() / "livepilot" / ".Codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    plugin_dir = tmp_path / "plugins" / "livepilot"
    cache_root = tmp_path / ".codex" / "plugins" / "cache" / "local-plugins"
    stale_dir = cache_root / "livepilot" / "1.17.0"
    stale_dir.mkdir(parents=True)
    (stale_dir / "stale.txt").write_text("old", encoding="utf-8")
    marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"

    env = os.environ.copy()
    env["LIVEPILOT_CODEX_PLUGIN_PATH"] = str(plugin_dir)
    env["LIVEPILOT_CODEX_CACHE_ROOT"] = str(cache_root)
    env["LIVEPILOT_CODEX_MARKETPLACE_PATH"] = str(marketplace)

    _run_node(["-e", "require('./installer/codex.js').installCodexPlugin()"], env=env)

    assert not stale_dir.exists()
    assert (cache_root / "livepilot" / expected_manifest["version"] / "skills").is_dir()


def test_help_mentions_codex_plugin_installer():
    result = _run_node(["bin/livepilot.js", "--help"], env=os.environ.copy())
    assert "--install-codex-plugin" in result.stdout
    assert "--uninstall-codex-plugin" in result.stdout


def test_npm_package_includes_codex_plugin_payload():
    package_json = json.loads((_repo_root() / "package.json").read_text(encoding="utf-8"))
    assert "livepilot/**" in package_json["files"]

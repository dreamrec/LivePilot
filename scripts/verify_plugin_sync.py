#!/usr/bin/env python3
"""Verify the local LivePilot plugin install is complete.

Catches the v1.14.0 bug class: `.mcp.json` missing from the cache
version dir (~/.claude/plugins/cache/dreamrec-LivePilot/livepilot/VERSION/).
Without that file, Claude Code loads the plugin as "skills + commands only"
with zero MCP tools after its next restart.

## Checks

Active plugin dir (~/.claude/plugins/livepilot/):
  - plugin.json present + version matches repo
  - .mcp.json present + command is "npx livepilot"
  - commands/ and skills/ present

Cache version dir (~/.claude/plugins/cache/dreamrec-LivePilot/livepilot/<version>/):
  - plugin.json present
  - .mcp.json present (the v1.14.0 regression guard)
  - commands/ and skills/ present

Registry (~/.claude/plugins/installed_plugins.json):
  - livepilot@dreamrec-LivePilot entry exists
  - version matches repo
  - installPath points at the cache version dir

## Usage

    python3 scripts/verify_plugin_sync.py          # verify, print report, exit 0/1
    python3 scripts/verify_plugin_sync.py --quiet  # exit 0/1 with no stdout unless broken

## Exit codes

    0 — all checks pass
    1 — one or more files missing or mismatched; details in stdout
    2 — repo state unreadable (run from repo root)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_DIR = Path.home() / ".claude" / "plugins" / "livepilot"
CACHE_ROOT = Path.home() / ".claude" / "plugins" / "cache" / "dreamrec-LivePilot" / "livepilot"
REGISTRY_PATH = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
MARKETPLACE_SNAPSHOT = (
    Path.home()
    / ".claude"
    / "plugins"
    / "marketplaces"
    / "dreamrec-LivePilot"
    / "livepilot"
    / ".claude-plugin"
    / "plugin.json"
)
REGISTRY_KEY = "livepilot@dreamrec-LivePilot"


class Issue:
    """A single verification failure — location + what's wrong + how to fix."""

    __slots__ = ("location", "detail", "fix")

    def __init__(self, location: str, detail: str, fix: str = ""):
        self.location = location
        self.detail = detail
        self.fix = fix

    def format(self) -> str:
        lines = [f"  ✗ {self.location}", f"    {self.detail}"]
        if self.fix:
            lines.append(f"    fix: {self.fix}")
        return "\n".join(lines)


def read_repo_version() -> Optional[str]:
    """Pull the expected version from the repo's plugin.json."""
    plugin_json = REPO_ROOT / "livepilot" / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(plugin_json.read_text())["version"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None


def check_active_dir(expected_version: str) -> list[Issue]:
    issues: list[Issue] = []
    if not ACTIVE_DIR.exists():
        issues.append(Issue(
            str(ACTIVE_DIR),
            "directory missing — plugin never installed locally",
            "run the Step 1 block from feedback_sync_plugin.md",
        ))
        return issues

    # plugin.json present + version matches
    active_plugin = ACTIVE_DIR / "plugin.json"
    if not active_plugin.exists():
        issues.append(Issue(
            str(active_plugin),
            "plugin.json missing in active dir",
            "cp livepilot/.claude-plugin/plugin.json ~/.claude/plugins/livepilot/plugin.json",
        ))
    else:
        try:
            active_version = json.loads(active_plugin.read_text())["version"]
            if active_version != expected_version:
                issues.append(Issue(
                    str(active_plugin),
                    f"version mismatch: active={active_version}, repo={expected_version}",
                    "re-run the plugin sync procedure",
                ))
        except (KeyError, json.JSONDecodeError) as exc:
            issues.append(Issue(str(active_plugin), f"unreadable: {exc}"))

    # .mcp.json present + sane
    active_mcp = ACTIVE_DIR / ".mcp.json"
    if not active_mcp.exists():
        issues.append(Issue(
            str(active_mcp),
            ".mcp.json missing in active dir — MCP server won't spawn",
            "cp livepilot/.mcp.json ~/.claude/plugins/livepilot/.mcp.json",
        ))
    else:
        try:
            mcp_conf = json.loads(active_mcp.read_text())
            srv = mcp_conf.get("mcpServers", {}).get("livepilot", {})
            if srv.get("command") != "npx":
                issues.append(Issue(
                    str(active_mcp),
                    f"unexpected command: {srv.get('command')!r}, expected 'npx'",
                    "regenerate from repo's livepilot/.mcp.json",
                ))
        except json.JSONDecodeError as exc:
            issues.append(Issue(str(active_mcp), f"malformed JSON: {exc}"))

    # commands/ and skills/ dirs present
    for sub in ("commands", "skills"):
        if not (ACTIVE_DIR / sub).is_dir():
            issues.append(Issue(
                str(ACTIVE_DIR / sub),
                f"{sub}/ missing in active dir",
                f"cp -R livepilot/{sub}/ ~/.claude/plugins/livepilot/{sub}/",
            ))

    return issues


def check_cache_version_dir(expected_version: str) -> list[Issue]:
    """Check ~/.claude/plugins/cache/.../livepilot/<version>/ exists AND is complete.

    This is the v1.14.0 regression guard — `.mcp.json` absence here is what
    broke the release. Claude Code's --plugin-dir flag points HERE on startup,
    not at the active dir.
    """
    issues: list[Issue] = []
    version_dir = CACHE_ROOT / expected_version
    if not version_dir.exists():
        issues.append(Issue(
            str(version_dir),
            f"cache version dir for {expected_version} doesn't exist",
            "run the Step 2 (cache) block from feedback_sync_plugin.md",
        ))
        return issues

    # .mcp.json — the file that bit v1.14.0
    cache_mcp = version_dir / ".mcp.json"
    if not cache_mcp.exists():
        issues.append(Issue(
            str(cache_mcp),
            (
                ".mcp.json MISSING from cache version dir. This is the "
                "v1.14.0 bug class: Claude Code reads --plugin-dir/.mcp.json "
                "on startup, and without it the plugin loads as skills+commands "
                "only, zero MCP tools after next restart. Orphan MCP server "
                "processes may mask this in-session."
            ),
            f"cp livepilot/.mcp.json {cache_mcp}",
        ))

    # plugin.json — should match version
    cache_plugin = version_dir / "plugin.json"
    if not cache_plugin.exists():
        issues.append(Issue(
            str(cache_plugin),
            "plugin.json missing in cache version dir",
            f"cp livepilot/.claude-plugin/plugin.json {cache_plugin}",
        ))
    else:
        try:
            cache_version = json.loads(cache_plugin.read_text())["version"]
            if cache_version != expected_version:
                issues.append(Issue(
                    str(cache_plugin),
                    f"version mismatch: cache={cache_version}, repo={expected_version}",
                    "re-run the Step 2 block from feedback_sync_plugin.md",
                ))
        except (KeyError, json.JSONDecodeError) as exc:
            issues.append(Issue(str(cache_plugin), f"unreadable: {exc}"))

    # commands/ and skills/ dirs
    for sub in ("commands", "skills"):
        if not (version_dir / sub).is_dir():
            issues.append(Issue(
                str(version_dir / sub),
                f"{sub}/ missing in cache version dir",
                f"cp -R livepilot/{sub}/ {version_dir}/{sub}/",
            ))

    return issues


def check_marketplace_snapshot(expected_version: str) -> list[Issue]:
    issues: list[Issue] = []
    if not MARKETPLACE_SNAPSHOT.exists():
        issues.append(Issue(
            str(MARKETPLACE_SNAPSHOT),
            "marketplace snapshot plugin.json missing (UI compares against this for the 'Update' button)",
            f"cp livepilot/.claude-plugin/plugin.json {MARKETPLACE_SNAPSHOT}",
        ))
        return issues
    try:
        snap_version = json.loads(MARKETPLACE_SNAPSHOT.read_text())["version"]
        if snap_version != expected_version:
            issues.append(Issue(
                str(MARKETPLACE_SNAPSHOT),
                f"version mismatch: snapshot={snap_version}, repo={expected_version} — 'Update' button will lie about currency",
                "re-run the Step 3 block from feedback_sync_plugin.md",
            ))
    except (KeyError, json.JSONDecodeError) as exc:
        issues.append(Issue(str(MARKETPLACE_SNAPSHOT), f"unreadable: {exc}"))
    return issues


def check_registry(expected_version: str) -> list[Issue]:
    issues: list[Issue] = []
    if not REGISTRY_PATH.exists():
        issues.append(Issue(
            str(REGISTRY_PATH),
            "installed_plugins.json registry missing — Claude Code may not recognize plugin at all",
            "run the Step 4 block from feedback_sync_plugin.md",
        ))
        return issues
    try:
        registry = json.loads(REGISTRY_PATH.read_text())
        entries = registry.get("plugins", {}).get(REGISTRY_KEY, [])
        if not entries:
            issues.append(Issue(
                str(REGISTRY_PATH),
                f"no entry for {REGISTRY_KEY} in registry",
                "run the Step 4 block from feedback_sync_plugin.md",
            ))
            return issues
        entry = entries[0]
        if entry.get("version") != expected_version:
            issues.append(Issue(
                str(REGISTRY_PATH),
                f"registry version {entry.get('version')} != repo {expected_version}",
                "re-run the Step 4 block from feedback_sync_plugin.md",
            ))
        # installPath should resolve to the cache version dir for the CURRENT version
        expected_path = str(CACHE_ROOT / expected_version)
        if entry.get("installPath") != expected_path:
            issues.append(Issue(
                str(REGISTRY_PATH),
                (
                    f"installPath mismatch\n"
                    f"      got:      {entry.get('installPath')}\n"
                    f"      expected: {expected_path}"
                ),
                "re-run the Step 4 block from feedback_sync_plugin.md",
            ))
    except json.JSONDecodeError as exc:
        issues.append(Issue(str(REGISTRY_PATH), f"malformed JSON: {exc}"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0] if __doc__ else None)
    parser.add_argument("--quiet", action="store_true",
                        help="emit no stdout unless there are issues")
    args = parser.parse_args()

    expected_version = read_repo_version()
    if expected_version is None:
        print("ERROR: couldn't read version from livepilot/.claude-plugin/plugin.json", file=sys.stderr)
        print("       (run from repo root, or fix a broken plugin.json)", file=sys.stderr)
        return 2

    all_issues: list[tuple[str, list[Issue]]] = [
        ("Active plugin dir", check_active_dir(expected_version)),
        ("Cache version dir", check_cache_version_dir(expected_version)),
        ("Marketplace snapshot", check_marketplace_snapshot(expected_version)),
        ("Registry", check_registry(expected_version)),
    ]

    total_issues = sum(len(issues) for _, issues in all_issues)

    if total_issues == 0:
        if not args.quiet:
            print(f"LivePilot plugin sync check — v{expected_version}")
            print(f"  ✓ Active plugin dir       ({ACTIVE_DIR})")
            print(f"  ✓ Cache version dir       ({CACHE_ROOT}/{expected_version})")
            print(f"  ✓ Marketplace snapshot")
            print(f"  ✓ Registry")
            print(f"All checks pass. Claude Code will find the MCP server on next restart.")
        return 0

    # Print whether --quiet or not — broken state deserves visibility.
    print(f"LivePilot plugin sync check — v{expected_version}")
    print(f"FAILED: {total_issues} issue(s) found\n")
    for section, issues in all_issues:
        if not issues:
            print(f"  ✓ {section}")
            continue
        print(f"  ✗ {section} ({len(issues)} issue(s)):")
        for issue in issues:
            print(issue.format())
    print()
    print("After fixing, re-run: python3 scripts/verify_plugin_sync.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())

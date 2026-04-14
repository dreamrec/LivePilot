#!/usr/bin/env python3
"""Metadata sync — single source of truth for version and tool count.

Reads version from package.json, tool count from test_tools_contract.py,
and verifies all known locations are in sync.

Usage:
    python scripts/sync_metadata.py --check   # verify, exit 1 if stale
    python scripts/sync_metadata.py --fix     # auto-fix stale references
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def get_version() -> str:
    """Read version from package.json (source of truth)."""
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    return pkg["version"]


def get_tool_count() -> int:
    """Read tool count from test_tools_contract.py assertion."""
    src = (ROOT / "tests" / "test_tools_contract.py").read_text(encoding="utf-8")
    match = re.search(r"assert len\(tools\) == (\d+)", src)
    if match:
        return int(match.group(1))
    raise ValueError("Could not find tool count assertion in test_tools_contract.py")


# Files that must contain the version string
VERSION_FILES = [
    "package.json",
    "server.json",
    "manifest.json",
    "livepilot/.claude-plugin/plugin.json",
    "livepilot/.Codex-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "mcp_server/__init__.py",
    "remote_script/LivePilot/__init__.py",
    "CLAUDE.md",
    "AGENTS.md",
    "livepilot/skills/livepilot-core/references/overview.md",
    "docs/M4L_BRIDGE.md",
]

# Files that must contain the tool count
TOOL_COUNT_FILES = [
    "README.md",
    "package.json",
    "server.json",
    "CLAUDE.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "livepilot/.claude-plugin/plugin.json",
    "livepilot/.Codex-plugin/plugin.json",
    "livepilot/skills/livepilot-core/SKILL.md",
    "livepilot/skills/livepilot-core/references/overview.md",
    "docs/manual/index.md",
    "docs/manual/tool-reference.md",
    "docs/manual/tool-catalog.md",
]


def check_version(version: str) -> list[str]:
    """Check all version files for staleness."""
    issues = []
    for rel_path in VERSION_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if version not in content:
            # Find what version IS there
            old = re.search(r"1\.\d+\.\d+", content)
            old_ver = old.group(0) if old else "???"
            if old_ver != version:
                issues.append(f"  {rel_path}: has {old_ver}, expected {version}")
    return issues


def check_tool_count(count: int) -> list[str]:
    """Check all tool count files for staleness."""
    issues = []
    count_str = str(count)
    for rel_path in TOOL_COUNT_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        # Look for "N tools" pattern
        matches = re.findall(r"(\d+)\s+tools", content)
        for m in matches:
            if m != count_str and int(m) > 250:  # ignore subset counts like "210 tools"
                issues.append(f"  {rel_path}: has '{m} tools', expected '{count_str} tools'")
                break
    return issues


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"

    version = get_version()
    tool_count = get_tool_count()

    print(f"Source of truth: version={version}, tools={tool_count}")

    version_issues = check_version(version)
    count_issues = check_tool_count(tool_count)

    all_issues = version_issues + count_issues

    if all_issues:
        print(f"\nFound {len(all_issues)} stale reference(s):")
        for issue in all_issues:
            print(issue)
        if mode == "--check":
            sys.exit(1)
        elif mode == "--fix":
            print("\n--fix mode not yet implemented. Fix manually.")
            sys.exit(1)
    else:
        print("All metadata in sync.")
        sys.exit(0)


if __name__ == "__main__":
    main()

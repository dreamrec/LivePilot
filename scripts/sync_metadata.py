#!/usr/bin/env python3
"""Metadata sync — single source of truth for version, tool count, and domain count.

Reads version from package.json, tool count from test_tools_contract.py,
derives domain count + list from mcp_server source layout, and verifies all
known locations are in sync.

Usage:
    python scripts/sync_metadata.py --check   # verify, exit 1 if stale
    python scripts/sync_metadata.py --fix     # auto-fix stale references
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = ROOT / "mcp_server"


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


def get_domains() -> tuple[int, list[str]]:
    """Derive the set of tool domains from mcp_server source layout.

    A domain is:
    - the subdirectory name for ``mcp_server/<X>/...`` files containing ``@mcp.tool()``
    - the file stem for ``mcp_server/tools/<Y>.py`` files

    Returns (count, sorted list of names).
    """
    domains: set[str] = set()
    for py in TOOLS_ROOT.rglob("*.py"):
        try:
            content = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "@mcp.tool()" not in content:
            continue
        rel_parts = py.relative_to(TOOLS_ROOT).parts
        if len(rel_parts) < 2:
            # Top-level file (e.g., server.py). No such file currently registers
            # tools; if one does, it would need an explicit domain assignment.
            continue
        if rel_parts[0] == "tools":
            domains.add(py.stem)
        else:
            domains.add(rel_parts[0])
    return len(domains), sorted(domains)


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
    # CHANGELOG: must reference the current version in its most-recent entry.
    # The check_version() regex matches any 1.X.Y — so a CHANGELOG that still
    # says "## 1.10.6" at the top while the repo is 1.10.7 will now fail.
    "CHANGELOG.md",
    "livepilot/skills/livepilot-core/references/overview.md",
    # capability-modes.md ships example JSON with a version string that must
    # match the frozen bridge — caught during v1.10.7 audit.
    "livepilot/skills/livepilot-evaluation/references/capability-modes.md",
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

# Files that must contain the current domain count ("N domains").
DOMAIN_COUNT_FILES = [
    "README.md",
    "package.json",
    "manifest.json",
    "CLAUDE.md",
    "AGENTS.md",
    "livepilot/.claude-plugin/plugin.json",
    "livepilot/.Codex-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "livepilot/skills/livepilot-core/SKILL.md",
    "livepilot/skills/livepilot-core/references/overview.md",
    "livepilot/skills/livepilot-release/SKILL.md",
    "docs/manual/index.md",
    "docs/manual/tool-catalog.md",
    "docs/manual/tool-catalog-generated.md",
    "tests/test_tools_contract.py",
]

# Files that enumerate the domain list inline as ``N domains: a, b, c, ...``.
# Each file's enumeration must match the derived domain set exactly.
DOMAIN_LIST_FILES = [
    "CLAUDE.md",
    "livepilot/skills/livepilot-release/SKILL.md",
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


def check_domain_count(count: int) -> list[str]:
    """Check all domain-count files for stale numbers."""
    issues = []
    count_str = str(count)
    for rel_path in DOMAIN_COUNT_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        matches = re.findall(r"(\d+)\s+domains?\b", content)
        for m in matches:
            # Filter historical CHANGELOG-style subset counts (e.g., "5 domains",
            # "17 domains"). Active claim has always been >= 40.
            if m != count_str and int(m) > 35:
                issues.append(
                    f"  {rel_path}: has '{m} domains', expected '{count_str} domains'"
                )
                break
    return issues


def check_domain_list(domains: list[str]) -> list[str]:
    """Verify each DOMAIN_LIST_FILES file enumerates exactly the derived domain set."""
    issues = []
    domain_set = set(domains)
    for rel_path in DOMAIN_LIST_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        # Match "<N> domains: a, b, c, ..." up to the first period or newline.
        # Allow trailing markdown bold markers after "domains" (e.g. ``**43 domains**:``).
        match = re.search(r"\d+\s+domains?\**\s*[:\-]\s*([^.\n]+)", content)
        if not match:
            issues.append(
                f"  {rel_path}: no 'N domains: ...' inline list found to verify"
            )
            continue
        raw_names = (n.strip() for n in match.group(1).split(","))
        listed = {re.sub(r"[^a-z0-9_]", "", n.lower()) for n in raw_names}
        listed.discard("")
        missing = domain_set - listed
        extra = listed - domain_set
        if missing:
            issues.append(
                f"  {rel_path}: inline list missing {len(missing)} domain(s) — {', '.join(sorted(missing))}"
            )
        if extra:
            issues.append(
                f"  {rel_path}: inline list has {len(extra)} unknown domain(s) — {', '.join(sorted(extra))}"
            )
    return issues


def _fix_count(
    count: int, files: list[str], noun: str, threshold: int
) -> list[str]:
    """Replace every stale ``<N> <noun>(s)`` in *files* with ``<count> <noun>(s)``.

    Only substitutes where ``N != count`` and ``N > threshold``; this mirrors the
    filtering in the corresponding ``check_*`` function so historical/subset
    numbers are never rewritten.
    """
    fixed: list[str] = []
    count_str = str(count)
    pattern = re.compile(rf"(\d+)(\s+{re.escape(noun)}s?)\b")
    for rel_path in files:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        seen_old: list[str] = []

        def replace(match: "re.Match[str]") -> str:
            old = match.group(1)
            if old != count_str and int(old) > threshold:
                seen_old.append(old)
                return f"{count_str}{match.group(2)}"
            return match.group(0)

        new_content = pattern.sub(replace, content)
        if seen_old:
            path.write_text(new_content, encoding="utf-8")
            fixed.append(f"  {rel_path}: {noun} count {seen_old[0]} → {count_str}")
    return fixed


def fix_tool_count(count: int) -> list[str]:
    return _fix_count(count, TOOL_COUNT_FILES, "tool", threshold=250)


def fix_domain_count(count: int) -> list[str]:
    return _fix_count(count, DOMAIN_COUNT_FILES, "domain", threshold=35)


def fix_domain_list(domains: list[str]) -> list[str]:
    """Append missing domain names to each DOMAIN_LIST_FILES inline enumeration.

    Extra (unknown) entries are never auto-removed — the script only adds, so an
    accidental pattern miss can't silently delete a legitimate entry.
    """
    fixed: list[str] = []
    pattern = re.compile(r"(\d+\s+domains?\**\s*[:\-]\s*)([^.\n]+)(\.|\n)")
    for rel_path in DOMAIN_LIST_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        match = pattern.search(content)
        if not match:
            continue
        listed_raw = match.group(2)
        listed = {
            re.sub(r"[^a-z0-9_]", "", n.strip().lower())
            for n in listed_raw.split(",")
        }
        listed.discard("")
        missing = [d for d in domains if d not in listed]
        if not missing:
            continue
        new_list = listed_raw.rstrip() + ", " + ", ".join(missing)
        new_content = content[: match.start(2)] + new_list + content[match.end(2) :]
        path.write_text(new_content, encoding="utf-8")
        fixed.append(
            f"  {rel_path}: appended {len(missing)} domain(s) — {', '.join(missing)}"
        )
    return fixed


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"

    version = get_version()
    tool_count = get_tool_count()
    domain_count, domains = get_domains()

    print(
        f"Source of truth: version={version}, tools={tool_count}, domains={domain_count}"
    )

    if mode == "--fix":
        fixed = (
            fix_tool_count(tool_count)
            + fix_domain_count(domain_count)
            + fix_domain_list(domains)
        )
        if fixed:
            print(f"\nFixed {len(fixed)} reference(s):")
            for f in fixed:
                print(f)
        else:
            print("\nNothing to fix automatically.")

        remaining = (
            check_version(version)
            + check_tool_count(tool_count)
            + check_domain_count(domain_count)
            + check_domain_list(domains)
        )
        if remaining:
            print(f"\n{len(remaining)} issue(s) remain (manual fix required):")
            for issue in remaining:
                print(issue)
            print(
                "\nNote: --fix covers tool/domain counts and missing domain list entries. "
                "Version strings and extra list entries must be fixed by hand."
            )
            sys.exit(1)
        print("\nAll metadata in sync.")
        sys.exit(0)

    # --check mode (default)
    all_issues = (
        check_version(version)
        + check_tool_count(tool_count)
        + check_domain_count(domain_count)
        + check_domain_list(domains)
    )
    if all_issues:
        print(f"\nFound {len(all_issues)} stale reference(s):")
        for issue in all_issues:
            print(issue)
        sys.exit(1)
    print("All metadata in sync.")
    sys.exit(0)


if __name__ == "__main__":
    main()

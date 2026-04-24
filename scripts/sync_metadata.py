#!/usr/bin/env python3
"""Metadata sync — single source of truth for every repo-wide count.

Derives the truth from code (package.json version, contract-test tool count,
module layout for domains, bridge JS `case` count, atlas YAML count,
`GENRE_DEFAULTS` key count) and verifies every documented claim matches.

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


def get_bridge_command_count() -> int:
    """Count ``case "xxx":`` entries in livepilot_bridge.js.

    Source of truth for the M4L → Python bridge surface area. Prose like
    "28 bridge commands" in CLAUDE.md / M4L_BRIDGE.md must match this.
    """
    js = (ROOT / "m4l_device" / "livepilot_bridge.js").read_text(encoding="utf-8")
    return len(re.findall(r'^\s*case\s+"[a-z_]+":', js, flags=re.MULTILINE))


def get_enriched_device_count() -> int:
    """Count YAML enrichment profiles under mcp_server/atlas/enrichments.

    Source of truth for claims like "81 enriched with sonic intelligence".
    """
    enrichments = TOOLS_ROOT / "atlas" / "enrichments"
    if not enrichments.exists():
        return 0
    return sum(1 for p in enrichments.rglob("*.yaml")) + sum(
        1 for p in enrichments.rglob("*.yml")
    )


def get_bundled_enriched_device_count() -> int:
    """Read ``stats.enriched_devices`` from the bundled atlas JSON.

    Added in v1.22.1. This number reflects how many devices received
    enrichment during the scan_full_library run that produced the
    CURRENT ``mcp_server/atlas/device_atlas.json`` in the repo. It's
    orthogonal to ``get_enriched_device_count()`` which counts YAML
    files on disk:

    - YAML count = authoring effort (what's available)
    - Bundled count = runtime coverage at build time (what the last
      scan actually applied)

    The two can drift if someone adds a YAML without re-running the
    scan against a stock Ableton install. ``check_bundled_enrichment_
    coverage()`` surfaces the drift as a soft warning.

    Returns 0 on missing file, malformed JSON, or missing stats key —
    the soft gate catches these cases and warns, rather than crashing
    the whole sync_metadata run.
    """
    import json
    atlas_path = TOOLS_ROOT / "atlas" / "device_atlas.json"
    if not atlas_path.exists():
        return 0
    try:
        data = json.loads(atlas_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(data, dict):
        return 0
    stats = data.get("stats")
    if not isinstance(stats, dict):
        return 0
    count = stats.get("enriched_devices", 0)
    if not isinstance(count, int):
        return 0
    return count


def check_bundled_enrichment_coverage() -> list[str]:
    """Soft gate: warn if the bundled atlas's enrichment coverage looks
    broken relative to the YAML files on disk.

    Added in v1.22.1. Does NOT fail the sync_metadata run — warnings
    are printed alongside issues but the exit code is unchanged. The
    rationale: bundled count and YAML count MEASURE DIFFERENT THINGS
    (runtime coverage at build time vs authoring effort), so strict
    equality would produce false alarms whenever someone adds a YAML
    that targets a pack the scanner doesn't walk. But the SHAPE of the
    relationship — "bundled should be a non-trivial fraction of YAML"
    — catches the two real failure modes: scanner truncation
    (``bundled == 0``) and scanner partial-failure (``bundled ≪ yaml``).

    Threshold: warn if bundled < 50% of YAML count. Empirically, the
    v1.21.x-era bundled atlas shipped with ``87/120 = 72%`` coverage
    (healthy despite the orphan gap from 33 miditool-domain YAMLs that
    the browser scanner can't see); a truncated scan typically shows
    < 20% coverage.
    """
    yaml_count = get_enriched_device_count()
    bundled_count = get_bundled_enriched_device_count()
    if yaml_count == 0:
        # No YAMLs authored yet — nothing to compare against. Don't warn.
        return []
    warnings: list[str] = []
    if bundled_count == 0:
        warnings.append(
            f"  bundled atlas reports 0 enriched devices (YAML count: "
            f"{yaml_count}) — mcp_server/atlas/device_atlas.json may be "
            f"broken or never-scanned. Run scan_full_library against a "
            f"stock Ableton install and commit the updated baseline."
        )
        return warnings
    coverage = bundled_count / yaml_count
    if coverage < 0.5:
        warnings.append(
            f"  bundled atlas has {bundled_count}/{yaml_count} enrichment "
            f"coverage ({coverage:.0%}) — below the 50% soft threshold. "
            f"The bundled scan likely truncated or missed most YAMLs. "
            f"Re-run scan_full_library against a stock Ableton install "
            f"and commit the updated baseline."
        )
    return warnings


def get_genre_default_count() -> int:
    """Count keys in composer.prompt_parser.GENRE_DEFAULTS.

    Source of truth for claims like "7 genre defaults".
    """
    src = (ROOT / "mcp_server" / "composer" / "prompt_parser.py").read_text(encoding="utf-8")
    # Grab the dict body between ``GENRE_DEFAULTS: dict[...] = {`` and the
    # matching closing brace at column 0. Top-level ``"name":`` entries are
    # the genre keys; nested keys are indented.
    match = re.search(
        r"GENRE_DEFAULTS\s*(?::\s*[^=]+)?=\s*\{(.*?)^\}",
        src,
        flags=re.DOTALL | re.MULTILINE,
    )
    if not match:
        raise ValueError("Could not locate GENRE_DEFAULTS body in prompt_parser.py")
    body = match.group(1)
    return len(re.findall(r'^\s{4}"[a-z_]+"\s*:\s*\{', body, flags=re.MULTILINE))


def get_move_count() -> int:
    """Count of registered semantic moves via the Python registry.

    Added in v1.21.2 audit-response #2: v1.21.0 shipped with "43
    semantic moves" strings across 9 description fields even though the
    registry had 44 (configure_record_readiness was added). Post-ship
    hygiene sweep fixed the strings but sync_metadata didn't catch it.
    Adding this check closes the audit window.
    """
    import sys as _sys
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    import mcp_server.semantic_moves  # noqa: F401 — triggers registrations
    from mcp_server.semantic_moves import registry
    return registry.count()


def get_analyzer_tool_count() -> int:
    """Count of ``@mcp.tool`` decorators in mcp_server/tools/analyzer.py.

    Added in v1.21.2 audit-response #2: README/M4L_BRIDGE/manual had
    stale "32"/"33" claims while actual count is 38. Grepping the
    decorator is the authoritative measure — matches whatever the
    registry sees at import time.
    """
    path = ROOT / "mcp_server" / "tools" / "analyzer.py"
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    return len(re.findall(r"^\s*@mcp\.tool", content, re.MULTILINE))


def get_lockfile_version() -> str:
    """Project version as recorded in package-lock.json.

    Added in v1.21.2 audit-response #2: lockfile drifted at 1.17.5 from
    pre-v1.18 until v1.21.1 — invisible to previous sync_metadata scope
    because the lockfile wasn't checked. check_lockfile_version() now
    asserts it matches package.json.
    """
    path = ROOT / "package-lock.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return data.get("version", "")


def get_atlas_device_count() -> int:
    """Canonical device count from shipped ``device_atlas.json.stats``.

    Added in v1.21.3 audit-response #3: v1.21.2's CHANGELOG deferred this
    prose-claim check to v1.22, reasoning that the generic noun ``device``
    would false-positive on every historical "5 devices" mention. In
    practice, ``threshold=1000`` in the PROSE_CLAIM entry filters those
    out entirely — only 4-digit counts get compared, and those are
    always atlas references in this codebase. Enabling here instead of
    v1.22 based on audit #3 finding three manual files still claiming
    the stale 1305 count.

    Reads ``stats.total_devices`` from the shipped atlas JSON. Matches
    what ``AtlasManager.stats['total_devices']`` exposes at runtime.
    """
    path = ROOT / "mcp_server" / "atlas" / "device_atlas.json"
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return int(data.get("stats", {}).get("total_devices", 0))


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
        # Private/helper packages and files (Python underscore convention):
        # _analyzer_engine/, _composition_engine/, _conductor.py, etc. are
        # internal decomposition support, NOT public tool domains. They may
        # reference ``@mcp.tool()`` in docstrings or comments without actually
        # registering a tool; counting them as domains would be incorrect.
        if any(part.startswith("_") for part in rel_parts):
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

# Files that must contain the tool count.
#
# manifest.json and intelligence.md were missed in earlier releases because
# they weren't in this list. Adding them closes the false-green hole where
# sync_metadata --check would pass while public descriptors still advertised
# a stale count.
TOOL_COUNT_FILES = [
    "README.md",
    "package.json",
    "server.json",
    "manifest.json",
    ".claude-plugin/marketplace.json",
    "CLAUDE.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "livepilot/.claude-plugin/plugin.json",
    "livepilot/.Codex-plugin/plugin.json",
    "livepilot/skills/livepilot-core/SKILL.md",
    "livepilot/skills/livepilot-core/references/overview.md",
    "livepilot/skills/livepilot-release/SKILL.md",
    "docs/manual/index.md",
    "docs/manual/intelligence.md",
    "docs/manual/tool-reference.md",
    "docs/manual/tool-catalog.md",
]

# Prose-level claim files — derived counts that must match source.
#
# Each entry maps (noun in prose, derivation function, threshold) → files that
# contain the claim. Threshold guards against historical subset numbers being
# rewritten (e.g. a CHANGELOG that mentions "5 bridge commands" in a Batch 2
# entry shouldn't be touched).
PROSE_CLAIM_FILES = {
    "bridge command": {
        "getter": get_bridge_command_count,
        "threshold": 15,
        "files": [
            "README.md",
            "CLAUDE.md",
            "docs/M4L_BRIDGE.md",
            "livepilot/skills/livepilot-release/SKILL.md",
        ],
    },
    "enriched": {
        "getter": get_enriched_device_count,
        "threshold": 40,
        "files": [
            "README.md",
            "CLAUDE.md",
            "livepilot/skills/livepilot-core/references/overview.md",
            # v1.21.3 audit-response #3: manual pages were blind-spots
            # for this check because they weren't listed here. That let
            # "135 enriched" strings drift in manual docs while README
            # and CLAUDE showed "120 enriched".
            "docs/manual/device-atlas.md",
            "docs/manual/tool-reference.md",
        ],
    },
    "genre default": {
        "getter": get_genre_default_count,
        "threshold": 1,
        "files": [
            "README.md",
            "CLAUDE.md",
        ],
    },
    # v1.21.2 audit-response #2 additions:
    "semantic move": {
        "getter": get_move_count,
        "threshold": 30,  # below this is a historical subset mention
        "files": [
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
            "package.json",
            "server.json",
            "manifest.json",
            ".claude-plugin/marketplace.json",
            "livepilot/.Codex-plugin/plugin.json",
            "livepilot/.claude-plugin/plugin.json",
            "livepilot/skills/livepilot-core/references/overview.md",
            "livepilot/skills/livepilot-core/SKILL.md",
        ],
    },
    "analyzer tool": {
        # NOTE: this catches "38 analyzer tools" patterns but NOT
        # "38 spectral/analyzer tools" (the `/` breaks the check_prose_claim
        # regex's optional-word prefix). Those variants must be kept in
        # sync manually — or the regex broadened in a future patch.
        "getter": get_analyzer_tool_count,
        "threshold": 20,
        "files": [
            "README.md",
            "docs/M4L_BRIDGE.md",
            "docs/manual/getting-started.md",
            "livepilot/skills/livepilot-release/SKILL.md",
        ],
    },
    # v1.21.3 audit-response #3 addition:
    "device": {
        # Atlas total-device count (stats.total_devices in the shipped
        # atlas JSON). Threshold=1000 filters out historical "5 devices",
        # "2 devices" etc — only 4-digit claims are compared. In this
        # codebase, 4-digit ``N devices`` mentions are always atlas
        # references, so the false-positive risk is zero.
        #
        # Deferred from v1.21.2 CHANGELOG but pulled forward to v1.21.3
        # after the third audit surfaced docs/manual/device-atlas.md,
        # docs/manual/index.md, and docs/manual/tool-reference.md all
        # still claiming the stale 1305 count.
        "getter": get_atlas_device_count,
        "threshold": 1000,
        "files": [
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
            "package.json",
            "server.json",
            "manifest.json",
            ".claude-plugin/marketplace.json",
            "livepilot/.Codex-plugin/plugin.json",
            "livepilot/.claude-plugin/plugin.json",
            "livepilot/skills/livepilot-core/references/overview.md",
            "livepilot/skills/livepilot-core/SKILL.md",
            "docs/manual/device-atlas.md",
            "docs/manual/index.md",
            "docs/manual/tool-reference.md",
        ],
    },
}

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
    # v1.21.3 audit-response #3: tool-reference.md was a blind-spot —
    # it said "52 domains" at line 3400 while the rest of the repo
    # advertised 53. Missing from this list was the reason
    # sync_metadata --check never caught it.
    "docs/manual/tool-reference.md",
    "tests/test_tools_contract.py",
]

# Files that enumerate the domain list inline as ``N domains: a, b, c, ...``.
# Each file's enumeration must match the derived domain set exactly.
#
# AGENTS.md was missed in the v1.12.0 release — it claimed "51 domains"
# then listed 50 (missing ``miditool``). Adding it to the check set closes
# that false-green hole.
DOMAIN_LIST_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
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
    """Check all tool count files for staleness.

    Catches:
      - ``325 tools`` / ``325-tool``  (plain forms)
      - ``325 MCP Tools``             (one word between count and 'tools')
      - ``325 Tool``                  (capitalized)

    Older pattern ``(\\d+)[-\\s]+tools?\\b`` missed ``325 MCP Tools`` (in
    README's ASCII diagram) because ``MCP`` was between the number and the
    noun. Broadening to allow an optional capitalized word catches it.
    """
    issues = []
    count_str = str(count)
    # v1.21.3 audit-response #3: leading \b prevents the regex from
    # matching digits embedded in JSON unicode escapes (e.g. the "2014"
    # inside "\u2014"). Without \b, check_prose_claim(noun="device")
    # flagged manifest.json's em-dash \u2014 as a stale "2014 device"
    # claim — and --fix would have rewritten \u2014 to \u5264, corrupting
    # the JSON. The same fix is applied to all 4 regex patterns in
    # this file (check_tool_count, check_prose_claim, fix_tool_count,
    # _fix_count) for defensive uniformity.
    #
    # v1.21.4: filler group now has two branches and matches 0+ times:
    #   (a) [A-Z][A-Za-z\-]*\s+    — uppercase-anchored, space-joined
    #                                 (matches "MCP " in "430 MCP Tools";
    #                                  uppercase anchor guards against
    #                                  lowercase English articles like
    #                                  "the" producing false matches on
    #                                  prose such as "in 2020 the tool").
    #   (b) [A-Za-z][A-Za-z\-]*/   — any-case, slash-joined
    #                                 (matches "spectral/" in
    #                                  "38 spectral/analyzer tools"; the
    #                                  trailing slash is an explicit
    #                                  compound marker, safe for any case).
    # The ``*`` quantifier lets fillers chain, so "300 spectral/MCP tools"
    # parses as filler=(b)"spectral/" + (a)"MCP " + noun="tools". Before
    # v1.21.4, (b) didn't exist and the filler was single-only; slashed
    # and chained compounds escaped sync_metadata silently (surfaced
    # manually in v1.21.2 audit #2).
    pattern = re.compile(
        r"\b(\d+)[-\s]+(?:[A-Z][A-Za-z\-]*\s+|[A-Za-z][A-Za-z\-]*/)*[Tt]ools?\b"
    )
    for rel_path in TOOL_COUNT_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for m in pattern.findall(content):
            if m != count_str and int(m) > 250:  # ignore subset counts like "210 tools"
                issues.append(f"  {rel_path}: has '{m} tool(s)', expected '{count_str}'")
                break
    return issues


def check_lockfile_version(version: str) -> list[str]:
    """package-lock.json must match package.json's version.

    Added in v1.21.2 audit-response #2: previously the lockfile drifted
    silently (was at 1.17.5 for multiple releases) because sync_metadata
    didn't check it.
    """
    lock_version = get_lockfile_version()
    if lock_version and lock_version != version:
        return [
            f"  package-lock.json: has version={lock_version!r}, "
            f"expected {version!r} (must match package.json)"
        ]
    return []


def check_prose_claim(noun: str, spec: dict) -> list[str]:
    """Check a prose-level claim (bridge commands, enriched devices, genres).

    ``spec`` is the entry from ``PROSE_CLAIM_FILES``. Matches patterns like
    ``"28 bridge commands"``, ``"81 enriched"``, and ``"7 genre defaults"``.
    """
    issues: list[str] = []
    count = spec["getter"]()
    count_str = str(count)
    threshold = spec["threshold"]
    # Escape noun for regex, allow singular/plural and optional word between
    # the number and noun (e.g. "81 devices enriched", "81 enriched with ...").
    # Leading \b prevents matches against digits embedded in unicode escapes
    # like \u2014 (see check_tool_count for the full context).
    escaped = re.escape(noun)
    # v1.21.4: filler accepts slashed compounds like "spectral/" in
    # "38 spectral/analyzer tools" (noun="analyzer tool"), and chains
    # them via ``*`` so "32 new spectral/analyzer tools" also parses.
    # See check_tool_count's banner comment for the full rationale. For
    # prose-claim nouns the filler is not uppercase-anchored (pre-v1.21.4
    # behavior); the threshold filter above already guards drift against
    # legit prose like "in 2020 the bridge command was deprecated".
    pattern = re.compile(
        rf"\b(\d+)[-\s]+(?:[A-Za-z][A-Za-z\-]*(?:/|\s+))*{escaped}s?\b",
        flags=re.IGNORECASE,
    )
    for rel_path in spec["files"]:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for m in pattern.findall(content):
            if m != count_str and int(m) > threshold:
                issues.append(
                    f"  {rel_path}: has '{m} {noun}', expected '{count_str} {noun}'"
                )
                break
    return issues


def check_all_prose_claims() -> list[str]:
    """Run every entry in PROSE_CLAIM_FILES."""
    issues: list[str] = []
    for noun, spec in PROSE_CLAIM_FILES.items():
        issues.extend(check_prose_claim(noun, spec))
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
    # Leading \b matches check_prose_claim's — prevents --fix from
    # rewriting digits inside unicode escapes like \u2014.
    #
    # v1.21.4: filler must mirror check_prose_claim so --fix can rewrite
    # anything --check flags. Group 2 captures everything from the first
    # separator through the noun; replacement preserves group 2 verbatim
    # so a slashed prefix like "spectral/" (and chained fillers) survive
    # the rewrite.
    pattern = re.compile(
        rf"\b(\d+)([-\s]+(?:[A-Za-z][A-Za-z\-]*(?:/|\s+))*{re.escape(noun)}s?)\b",
        flags=re.IGNORECASE,
    )
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
    """Fix stale tool counts — catches both ``N tools`` and ``N-tool``."""
    fixed: list[str] = []
    count_str = str(count)
    # Matches ``323 tools``, ``323-tool`` (hyphenated variant), and
    # compound forms like ``323 MCP tools`` or ``323 spectral/MCP tools``.
    # Leading \b matches check_tool_count's — prevents --fix from
    # rewriting digits inside unicode escapes like \u2014.
    #
    # v1.21.4: filler mirrors check_tool_count (two-branch: uppercase
    # space-joined OR any-case slash-joined, 0+ iterations). Group 2
    # captures the entire separator+filler, group 3 captures the
    # "tools?" suffix. Replacement preserves groups 2 and 3 verbatim so
    # a slashed prefix like "spectral/" (and chained fillers) survive
    # the rewrite.
    pattern = re.compile(
        r"\b(\d+)([-\s]+(?:[A-Z][A-Za-z\-]*\s+|[A-Za-z][A-Za-z\-]*/)*)([Tt]ools?)\b"
    )
    for rel_path in TOOL_COUNT_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        seen_old: list[str] = []

        def replace(match: "re.Match[str]") -> str:
            old = match.group(1)
            if old != count_str and int(old) > 250:
                seen_old.append(old)
                return f"{count_str}{match.group(2)}{match.group(3)}"
            return match.group(0)

        new_content = pattern.sub(replace, content)
        if seen_old:
            path.write_text(new_content, encoding="utf-8")
            fixed.append(f"  {rel_path}: tool count {seen_old[0]} → {count_str}")
    return fixed


def fix_domain_count(count: int) -> list[str]:
    return _fix_count(count, DOMAIN_COUNT_FILES, "domain", threshold=35)


def fix_prose_claims() -> list[str]:
    """Rewrite stale ``<N> <noun>`` forms in every PROSE_CLAIM_FILES entry."""
    fixed: list[str] = []
    for noun, spec in PROSE_CLAIM_FILES.items():
        count = spec["getter"]()
        fixed.extend(_fix_count(count, spec["files"], noun, spec["threshold"]))
    return fixed


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
    bridge_count = get_bridge_command_count()
    enriched_count = get_enriched_device_count()
    genre_count = get_genre_default_count()
    # v1.21.2 audit-response #2 additions:
    move_count = get_move_count()
    analyzer_tool_count = get_analyzer_tool_count()
    # v1.21.3 audit-response #3 addition:
    atlas_device_count = get_atlas_device_count()
    # v1.22.1 addition:
    bundled_enriched_count = get_bundled_enriched_device_count()

    print(
        f"Source of truth: version={version}, tools={tool_count}, "
        f"domains={domain_count}, bridge_cmds={bridge_count}, "
        f"enriched={enriched_count}, bundled_enriched={bundled_enriched_count}, "
        f"genres={genre_count}, moves={move_count}, "
        f"analyzer_tools={analyzer_tool_count}, atlas_devices={atlas_device_count}"
    )

    # v1.22.1: soft coverage gate — warns (doesn't fail) if the bundled
    # atlas's runtime enrichment coverage is suspiciously low relative
    # to the YAML files on disk. Print warnings ABOVE the fail/pass line
    # so they're visible regardless of exit code.
    coverage_warnings = check_bundled_enrichment_coverage()
    if coverage_warnings:
        print(f"\n⚠️  {len(coverage_warnings)} soft warning(s):")
        for w in coverage_warnings:
            print(w)

    if mode == "--fix":
        fixed = (
            fix_tool_count(tool_count)
            + fix_domain_count(domain_count)
            + fix_domain_list(domains)
            + fix_prose_claims()
        )
        if fixed:
            print(f"\nFixed {len(fixed)} reference(s):")
            for f in fixed:
                print(f)
        else:
            print("\nNothing to fix automatically.")

        remaining = (
            check_version(version)
            + check_lockfile_version(version)
            + check_tool_count(tool_count)
            + check_domain_count(domain_count)
            + check_domain_list(domains)
            + check_all_prose_claims()
        )
        if remaining:
            print(f"\n{len(remaining)} issue(s) remain (manual fix required):")
            for issue in remaining:
                print(issue)
            print(
                "\nNote: --fix covers tool/domain/prose counts and missing domain list entries. "
                "Version strings and extra list entries must be fixed by hand."
            )
            sys.exit(1)
        print("\nAll metadata in sync.")
        sys.exit(0)

    # --check mode (default)
    all_issues = (
        check_version(version)
        + check_lockfile_version(version)
        + check_tool_count(tool_count)
        + check_domain_count(domain_count)
        + check_domain_list(domains)
        + check_all_prose_claims()
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

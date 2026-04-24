"""Claim-consistency guard.

For every numeric claim in user-facing prose (README, CLAUDE.md, docs/),
we derive the truth from code. If the two disagree, the test fails with
exactly which file + which claim drifted.

Before v1.10.9 each of these drifts shipped at least once in production:
  * manifest.json / server.json advertised stale tool counts because they
    were outside sync_metadata's file list, or used the hyphenated form
    ``323-tool`` that the regex missed.
  * README.md claimed ``81 enriched`` devices when only 71 YAML profiles
    existed; ``7 genre defaults`` when code shipped 4; ``28 bridge
    commands`` when the bridge had 30.
  * docs/manual/intelligence.md pinned the tool count at 323 across
    releases because no one had touched that page.

This test reuses the exact same derivation + check paths that
``scripts/sync_metadata.py --check`` uses, so a green test ≡ a green
sync_metadata run. CI already calls the script directly; this test
makes the guarantee visible from ``pytest`` too, which is what most
contributors run locally.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sync_metadata():
    """Import sync_metadata.py as a module so we can call its checkers directly."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        module = importlib.import_module("sync_metadata")
    finally:
        # Leave sys.path clean so later tests aren't polluted.
        try:
            sys.path.remove(str(REPO_ROOT / "scripts"))
        except ValueError:
            pass
    return module


def test_metadata_check_passes_from_pytest(sync_metadata):
    """The repo must satisfy every sync_metadata invariant.

    Running the script via subprocess rather than calling ``main()`` so the
    sys.exit(1) boundary behaves the way CI sees it.
    """
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_metadata.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        "sync_metadata --check reported drift:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_version_strings_in_sync(sync_metadata):
    """Every file in VERSION_FILES must name the current version."""
    version = sync_metadata.get_version()
    issues = sync_metadata.check_version(version)
    assert not issues, "Version drift:\n" + "\n".join(issues)


def test_tool_count_including_hyphenated_form(sync_metadata):
    """Tool count must match, including the hyphenated ``N-tool`` form.

    server.json historically shipped ``"323-tool agentic ..."`` and the
    old regex (``\\s+``) skipped it entirely. The test here exists to make
    sure a future contributor cannot regress to the hyphenated-gap bug.
    """
    count = sync_metadata.get_tool_count()
    issues = sync_metadata.check_tool_count(count)
    assert not issues, "Tool-count drift:\n" + "\n".join(issues)


def test_manifest_json_is_in_tool_count_files(sync_metadata):
    """Regression guard: manifest.json was missed in the first extension pass.

    If it ever falls out of ``TOOL_COUNT_FILES`` again, this fails before CI
    even runs the broader check.
    """
    assert "manifest.json" in sync_metadata.TOOL_COUNT_FILES


def test_intelligence_manual_is_in_tool_count_files(sync_metadata):
    """``docs/manual/intelligence.md`` pinned 323 for multiple releases before
    being added to the sweep. Keep it in the file list."""
    assert "docs/manual/intelligence.md" in sync_metadata.TOOL_COUNT_FILES


def test_domain_count_and_list_in_sync(sync_metadata):
    count, domains = sync_metadata.get_domains()
    assert count == len(domains)
    count_issues = sync_metadata.check_domain_count(count)
    list_issues = sync_metadata.check_domain_list(domains)
    assert not (count_issues or list_issues), (
        "Domain drift:\n" + "\n".join(count_issues + list_issues)
    )


@pytest.mark.parametrize(
    "noun",
    ["bridge command", "enriched", "genre default"],
)
def test_prose_claim_matches_code(sync_metadata, noun):
    """For every entry in PROSE_CLAIM_FILES, the derived count must match prose.

    This is the v1.10.9 fix for the broader "docs say X, code has Y" failure
    mode: before this, only the version/tool/domain triplet was enforced.
    """
    spec = sync_metadata.PROSE_CLAIM_FILES[noun]
    issues = sync_metadata.check_prose_claim(noun, spec)
    assert not issues, f"Prose drift for '{noun}':\n" + "\n".join(issues)


def test_bridge_command_count_matches_js(sync_metadata):
    """The derived bridge-command count must equal the number of ``case``
    entries in ``livepilot_bridge.js`` — anything else means the JS source
    shifted and the derivation fell behind."""
    js = (REPO_ROOT / "m4l_device" / "livepilot_bridge.js").read_text(encoding="utf-8")
    naive = js.count('case "')
    derived = sync_metadata.get_bridge_command_count()
    # naive >= derived (naive counts any ``case "`` even outside switch bodies,
    # though in practice livepilot_bridge.js only uses them at top level).
    assert derived <= naive
    assert derived > 0


def test_no_stale_release_tarballs_in_repo():
    """livepilot-*.tgz artifacts are release-only; shipping them tracked lets
    contributors ``npm install`` a stale version. The gitignore covers this,
    but if anyone ever force-adds one, fail loudly."""
    tarballs = [p.name for p in REPO_ROOT.glob("livepilot-*.tgz")]
    # Untracked on disk is fine; tracked is not. Using git to check.
    if not tarballs:
        return
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch"] + tarballs,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # returncode == 0 means at least one of the tarballs is tracked
    assert result.returncode != 0, (
        "Release tarball(s) are tracked in git; they must be gitignored:\n"
        + "\n".join(tarballs)
    )


def test_session_continuity_binder_is_wired():
    """bind_project_store_from_session must have at least one caller outside
    its own module and tests — otherwise we're back to the 'session
    continuity plumbed but never invoked' state that shipped unfixed across
    multiple releases."""
    binder = "bind_project_store_from_session"
    hits = list(REPO_ROOT.rglob("*.py"))
    call_sites: list[Path] = []
    skip = {"tracker.py", "models.py", "__pycache__"}
    for path in hits:
        # Skip the defining module, tests (we don't want the test file
        # itself to count as "wired"), and caches.
        if path.name in skip or "__pycache__" in path.parts:
            continue
        if path.is_relative_to(REPO_ROOT / "tests"):
            continue
        if path.is_relative_to(REPO_ROOT / ".venv"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if binder in text:
            call_sites.append(path)
    assert call_sites, (
        f"No non-test caller of {binder}() found. Session continuity is "
        "effectively in-memory again — wire it back into lifespan/startup."
    )


# ---------------------------------------------------------------------------
# v1.21.4 — slashed-compound filler detection
#
# Before v1.21.4, the filler group in check_prose_claim (and _fix_count)
# required trailing whitespace: `[A-Za-z]+\s+`. That rejected slashed
# compounds like "38 spectral/analyzer tools" even though "spectral/" is
# a meaningful compound-prefix on the noun "analyzer tool". The v1.21.2
# audit #2 noted this as an open item — documents could carry stale
# counts inside slashed compounds and sync_metadata would silently let
# them pass.
#
# v1.21.4 widens the filler to also permit a trailing slash (compound
# marker). The tests below lock the behavior in: drift inside slashed
# compounds must be caught by `--check` and rewritable by `--fix`.
# ---------------------------------------------------------------------------


def test_prose_claim_catches_slashed_compound(sync_metadata, tmp_path, monkeypatch):
    """check_prose_claim must flag drift inside slashed-compound forms.

    Regression test for the v1.21.2 audit #2 finding — "38 spectral/analyzer
    tools" would carry the wrong count past sync_metadata because the filler
    regex rejected the slash.
    """
    stale = tmp_path / "fake_doc.md"
    stale.write_text("The 38 spectral/analyzer tools require the bridge.\n")
    monkeypatch.setattr(sync_metadata, "ROOT", tmp_path)
    spec = {
        "getter": lambda: 40,  # drift: doc says 38, expected 40
        "threshold": 20,
        "files": ["fake_doc.md"],
    }
    issues = sync_metadata.check_prose_claim("analyzer tool", spec)
    assert issues, "Expected drift flag for '38 spectral/analyzer tools' vs 40"
    assert "fake_doc.md" in issues[0]
    assert "'38 analyzer tool'" in issues[0]
    assert "'40 analyzer tool'" in issues[0]


def test_fix_count_rewrites_slashed_compound(sync_metadata, tmp_path, monkeypatch):
    """_fix_count must rewrite the number inside a slashed compound,
    preserving the adjective ('spectral/') verbatim."""
    stale = tmp_path / "fake_doc.md"
    stale.write_text("The 38 spectral/analyzer tools require the bridge.\n")
    monkeypatch.setattr(sync_metadata, "ROOT", tmp_path)
    fixed = sync_metadata._fix_count(
        count=40,
        files=["fake_doc.md"],
        noun="analyzer tool",
        threshold=20,
    )
    assert fixed, "_fix_count must report at least one rewrite"
    new_content = stale.read_text()
    assert "40 spectral/analyzer tools" in new_content, (
        f"Rewrite must preserve the slashed prefix; got: {new_content!r}"
    )
    # Original "38" must be gone from the slashed context
    assert "38 spectral/" not in new_content


def test_tool_count_catches_slashed_compound(sync_metadata, tmp_path, monkeypatch):
    """check_tool_count's widened filler catches drift in slashed forms
    like '430 MCP/analyzer tools' too. The uppercase anchor is preserved
    for space-joined fillers (so 'the tools' can't false-positive), but
    the slash-joined branch allows any case (the slash itself is a clear
    compound marker)."""
    stale = tmp_path / "fake_doc.md"
    stale.write_text("Ships 300 spectral/MCP tools.\n")
    monkeypatch.setattr(sync_metadata, "ROOT", tmp_path)
    monkeypatch.setattr(sync_metadata, "TOOL_COUNT_FILES", ["fake_doc.md"])
    issues = sync_metadata.check_tool_count(430)
    assert issues, "Expected drift flag for '300 spectral/MCP tools' vs 430"
    assert "fake_doc.md" in issues[0]
    assert "'300 tool" in issues[0]


def test_tool_count_no_false_positive_on_year_prose(sync_metadata, tmp_path, monkeypatch):
    """Widening the filler must NOT admit 'In 2020 the tool was released'
    as drift. The uppercase anchor on the space-joined branch prevents
    matching 'the' (lowercase English article) as filler."""
    stale = tmp_path / "fake_doc.md"
    stale.write_text("Released in 2020 the tool was first previewed.\n")
    monkeypatch.setattr(sync_metadata, "ROOT", tmp_path)
    monkeypatch.setattr(sync_metadata, "TOOL_COUNT_FILES", ["fake_doc.md"])
    issues = sync_metadata.check_tool_count(430)
    assert not issues, (
        f"'the' filler must NOT match (false-positive guard); got: {issues}"
    )


# ---------------------------------------------------------------------------
# v1.22.1 — bundled enrichment coverage gate
#
# The bundled atlas file (mcp_server/atlas/device_atlas.json) self-reports
# ``stats.enriched_devices`` — how many devices received enrichment during
# the LAST scan_full_library run that produced the shipped atlas. This
# number can drift silently from the YAML file count on disk: somebody
# adds an enrichment YAML, nobody re-runs the scan, and the bundled JSON
# still reports the old tally.
#
# v1.22.1 adds get_bundled_enriched_device_count() + a soft coverage gate
# that surfaces both numbers in the banner and warns if the bundled count
# is suspiciously low (0, or < 50% of YAML count — strong signal the
# scanner truncated silently or failed altogether).
# ---------------------------------------------------------------------------


def test_get_bundled_enriched_device_count_reads_shipped_json(sync_metadata):
    """The getter reads stats.enriched_devices from the repo's bundled
    atlas. Must be a positive integer — if it's 0 the bundled atlas is
    broken or was never scanned (which the soft gate catches)."""
    count = sync_metadata.get_bundled_enriched_device_count()
    assert isinstance(count, int)
    assert count >= 0
    # Sanity: the current shipped atlas should report at least some
    # enriched devices (else someone shipped an empty/broken atlas).
    assert count > 0, (
        "bundled atlas reports 0 enriched devices — either "
        "mcp_server/atlas/device_atlas.json is broken or was never "
        "scanned. Run scan_full_library against a stock Ableton install "
        "and regenerate."
    )


def test_get_bundled_enriched_handles_missing_file(
    sync_metadata, tmp_path, monkeypatch
):
    """If the bundled atlas is missing entirely (e.g. pre-build state),
    the getter must return 0 — not crash. This lets the rest of
    sync_metadata still run usefully."""
    monkeypatch.setattr(sync_metadata, "TOOLS_ROOT", tmp_path)
    count = sync_metadata.get_bundled_enriched_device_count()
    assert count == 0


def test_get_bundled_enriched_handles_malformed_json(
    sync_metadata, tmp_path, monkeypatch
):
    """Malformed JSON in the atlas file: return 0, don't crash.
    Safety against mid-write crashes or manual edits."""
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()
    (atlas_dir / "device_atlas.json").write_text("{ not valid json")
    monkeypatch.setattr(sync_metadata, "TOOLS_ROOT", tmp_path)
    count = sync_metadata.get_bundled_enriched_device_count()
    assert count == 0


def test_check_bundled_enrichment_coverage_passes_when_healthy(
    sync_metadata, monkeypatch
):
    """When bundled enriched count is within a reasonable fraction of
    the YAML count, no warning is raised. 'Reasonable' is coverage
    >= 50% (empirically: bundled scans that missed more than half the
    YAMLs are the broken ones worth flagging)."""
    # Synthetic: 100 YAMLs, 80 bundled — 80% coverage, healthy.
    monkeypatch.setattr(sync_metadata, "get_enriched_device_count", lambda: 100)
    monkeypatch.setattr(sync_metadata, "get_bundled_enriched_device_count", lambda: 80)
    warnings = sync_metadata.check_bundled_enrichment_coverage()
    assert warnings == [], f"Expected no warnings for 80% coverage; got: {warnings}"


def test_check_bundled_enrichment_coverage_warns_on_zero(
    sync_metadata, monkeypatch
):
    """Bundled count of 0 means the scan never ran or failed completely.
    Raise a warning so CI surfaces it."""
    monkeypatch.setattr(sync_metadata, "get_enriched_device_count", lambda: 120)
    monkeypatch.setattr(sync_metadata, "get_bundled_enriched_device_count", lambda: 0)
    warnings = sync_metadata.check_bundled_enrichment_coverage()
    assert warnings, "Expected warning when bundled count is 0"
    assert "0" in warnings[0]


def test_check_bundled_enrichment_coverage_warns_on_low_coverage(
    sync_metadata, monkeypatch
):
    """If bundled matched < 50% of YAML count, the bundled scan was
    likely truncated or broken. Raise a warning."""
    # 120 YAMLs, 40 bundled — 33% coverage, suspicious.
    monkeypatch.setattr(sync_metadata, "get_enriched_device_count", lambda: 120)
    monkeypatch.setattr(sync_metadata, "get_bundled_enriched_device_count", lambda: 40)
    warnings = sync_metadata.check_bundled_enrichment_coverage()
    assert warnings, "Expected warning when coverage is below 50%"
    assert "40" in warnings[0] and "120" in warnings[0]


def test_check_bundled_enrichment_coverage_skips_when_yaml_count_zero(
    sync_metadata, monkeypatch
):
    """If YAML count is 0 (pre-authoring state), don't divide by zero
    and don't warn. The gate is meaningful only when YAMLs exist."""
    monkeypatch.setattr(sync_metadata, "get_enriched_device_count", lambda: 0)
    monkeypatch.setattr(sync_metadata, "get_bundled_enriched_device_count", lambda: 0)
    warnings = sync_metadata.check_bundled_enrichment_coverage()
    assert warnings == []

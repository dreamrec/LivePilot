"""Local mirror of the CI "npm pack" packaging-drift checks in
.github/workflows/ci.yml (job with the "Verify npm pack includes expected
files" / "Verify npm pack excludes dirty/local files" steps).

Runs `npm pack --dry-run` and asserts the same critical-files list CI
checks, so packaging drift (a critical file falling out of package.json's
`files` allowlist, or a personal/dirty artifact leaking in) is caught on a
local test run instead of only in CI.

Keep the file lists here in sync with .github/workflows/ci.yml if that
workflow's checks change.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


NPM = shutil.which("npm")

pytestmark = pytest.mark.skipif(NPM is None, reason="npm not available")


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]


def _npm_pack_dry_run() -> str:
    result = subprocess.run(
        [NPM, "pack", "--dry-run"],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    # npm pack --dry-run writes the file listing to stderr on some npm
    # versions and stdout on others — check both, same as the CI step
    # (which pipes through `tee /dev/stderr`).
    return result.stdout + "\n" + result.stderr


# Critical files CI requires present in the published tarball (mirrors the
# "Verify npm pack includes expected files" ci.yml step).
_REQUIRED_FILES = [
    "scripts/als_deep_parse.py",
    "livepilot_bridge.js",
    "LivePilot_Analyzer.amxd",
    "remote_script/LivePilot/__init__.py",
    "livepilot/skills/livepilot-core/SKILL.md",
    "livepilot/.Codex-plugin/plugin.json",
]

# Patterns of dirty/local/personal artifacts CI requires absent (mirrors the
# "Verify npm pack excludes dirty/local files" ci.yml step).
_FORBIDDEN_SUFFIXES = [".disabled", ".backup", ".bak", ".swp", ".orig"]
_FORBIDDEN_SUBSTRINGS = [
    ".DS_Store",
    ".pre-",
    "plugins-synths.md",
    "synths-m4l.md",
    "utility-and-workflow.md",
    "samples-and-irs.md",
    "presets-by-vibe.md",
    "m4l-vendor",
    "m4l-depth-pass",
    "m4l-library-deep",
    "m4l-master-reference",
    "m4l-technique-map",
]


def test_npm_pack_includes_critical_files():
    listing = _npm_pack_dry_run()
    missing = [f for f in _REQUIRED_FILES if f not in listing]
    assert not missing, f"npm pack --dry-run is missing critical file(s): {missing}"


def test_npm_pack_excludes_dirty_and_personal_files():
    listing = _npm_pack_dry_run()

    dirty_lines = [
        line
        for line in listing.splitlines()
        if any(line.rstrip().endswith(suf) for suf in _FORBIDDEN_SUFFIXES)
    ]
    assert not dirty_lines, f"npm pack --dry-run contains dirty/local artifacts: {dirty_lines}"

    personal_hits = [s for s in _FORBIDDEN_SUBSTRINGS if s in listing]
    assert not personal_hits, (
        f"npm pack --dry-run contains personal/user atlas file marker(s): {personal_hits}"
    )

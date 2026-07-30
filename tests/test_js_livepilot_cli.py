"""Tests for the bin/livepilot.js CLI entrypoint.

Mirrors the subprocess pattern used by test_codex_plugin_installer.py.
Covers:
  - `--help` exits 0 with usage text.
  - `--version` matches package.json.
  - the requirements-hash venv staleness decision, exercised as a pure
    function (`decideVenvAction`, extracted from `ensureVenv` for exactly
    this purpose — see bin/livepilot.js) rather than by faking a whole
    `.venv` + pip toolchain.

`bin/livepilot.js` guards its own `main()` invocation with
`require.main === module`, so requiring it as a module (to reach the
exported pure functions) does not start the MCP server / bootstrap a venv.
"""

from __future__ import annotations

import hashlib
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


def _run_cli(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(kwargs.pop("extra_env", {}))
    return subprocess.run(
        [NODE, str(_repo_root() / "bin" / "livepilot.js"), *args],
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        **kwargs,
    )


def test_help_exits_zero_with_usage_text():
    result = _run_cli(["--help"])
    assert result.returncode == 0, result.stderr
    assert "Usage: npx livepilot [command]" in result.stdout
    assert "--install" in result.stdout
    assert "--uninstall" in result.stdout
    assert "--doctor" in result.stdout


def test_help_short_flag_matches_long_flag():
    long_form = _run_cli(["--help"])
    short_form = _run_cli(["-h"])
    assert short_form.returncode == 0
    assert short_form.stdout == long_form.stdout


def test_version_matches_package_json():
    pkg = json.loads((_repo_root() / "package.json").read_text(encoding="utf-8"))
    result = _run_cli(["--version"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"livepilot v{pkg['version']}"


def test_version_short_flag_matches():
    result = _run_cli(["-v"])
    assert result.returncode == 0
    pkg = json.loads((_repo_root() / "package.json").read_text(encoding="utf-8"))
    assert result.stdout.strip() == f"livepilot v{pkg['version']}"


def test_requiring_cli_as_module_does_not_auto_run_main():
    """Guard regression: `require()`-ing bin/livepilot.js for its exported
    helpers must not start the MCP server or touch a venv — it should just
    export the pure functions and return."""
    result = subprocess.run(
        [NODE, "-e", "require('./bin/livepilot.js'); console.log('OK_NO_AUTORUN')"],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK_NO_AUTORUN"


def test_decide_venv_action_exported_and_pure():
    result = subprocess.run(
        [
            NODE,
            "-e",
            "console.log(JSON.stringify(require('./bin/livepilot.js').decideVenvAction))",
        ],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("venv_exists", "stored_stamp", "current_hash", "expected"),
    [
        (False, None, "abc123", "create"),
        (True, "abc123", "abc123", "reuse"),
        (True, "stale-hash", "abc123", "update"),
        (True, None, "abc123", "update"),  # stamp file missing/unreadable
    ],
)
def test_decide_venv_action_branches(venv_exists, stored_stamp, current_hash, expected):
    script = (
        "const { decideVenvAction } = require('./bin/livepilot.js');"
        f"console.log(decideVenvAction({json.dumps(venv_exists)}, "
        f"{json.dumps(stored_stamp)}, {json.dumps(current_hash)}));"
    )
    result = subprocess.run(
        [NODE, "-e", script],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_requirements_hash_matches_repo_requirements_txt():
    """requirementsHash() is the actual staleness signal ensureVenv hashes
    against — verify it's a plain sha256 of requirements.txt, not something
    that silently diverged (e.g. hashing a stale cached copy)."""
    reqs = (_repo_root() / "requirements.txt").read_bytes()
    expected = hashlib.sha256(reqs).hexdigest()

    result = subprocess.run(
        [NODE, "-e", "console.log(require('./bin/livepilot.js').requirementsHash())"],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_venv_stamp_path_no_doubling():
    """Regression guard for the 7977cff bug: venvStampPath() previously did
    path.join(ROOT, VENV_DIR, ...) with VENV_DIR already absolute, producing
    a doubled nonexistent path — the stamp was never readable/writable, so
    ensureVenv re-ran pip on EVERY launch (surfacing as MCP handshake
    timeouts once the dependency graph grew). Pin the real return value."""
    result = subprocess.run(
        [NODE, "-e", "console.log(require('./bin/livepilot.js').venvStampPath())"],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    stamp_path = Path(result.stdout.strip())
    assert stamp_path == _repo_root() / ".venv" / ".requirements-sha256"

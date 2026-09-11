"""Interpreter discovery in bin/livepilot.js.

`findPython()` used to take the first candidate at or above the 3.12 floor
from `["python3", "python"]`. Two things went wrong with that:

  - On a machine with several interpreters it could land on a bleeding-edge
    release whose numpy/scipy/librosa wheels do not exist yet, so pip
    compiles from source instead of downloading — minutes instead of seconds,
    sometimes failing outright.
  - Under a GUI-launched host (Claude Desktop) PATH is minimal and `python3`
    is macOS's /usr/bin/python3 (3.9.6, below the floor), so the CLI aborted
    with "Python >= 3.12 is required" on a machine that had three suitable
    interpreters installed.

These tests pin the ordering and the fallback search, exercising the
exported pure helper rather than the filesystem.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")

# The well-known-directory fallback exists only on macOS/Linux; Windows relies
# on the "py" launcher. Starting node with a stripped environment on Windows
# also aborts at startup (ncrypto::CSPRNG needs SystemRoot), so the
# minimal-PATH scenario cannot be reproduced there.
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only fallback search; Windows uses the py launcher",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidates(extra_env: dict[str, str] | None = None) -> list[str]:
    env = os.environ.copy()
    env.update(extra_env or {})
    shim = _repo_root() / "bin" / "livepilot.js"
    out = subprocess.run(
        [NODE, "-e", f"process.stdout.write(JSON.stringify(require({str(shim)!r}).pythonCandidates()))"],
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_versioned_interpreters_are_tried_before_generic_names():
    candidates = _candidates()
    assert candidates[:2] == ["python3.13", "python3.12"]
    assert candidates.index("python3.13") < candidates.index("python3")
    assert candidates.index("python3.12") < candidates.index("python3")


@POSIX_ONLY
def test_wellknown_directories_are_searched_after_path():
    candidates = _candidates()
    bare = [c for c in candidates if "/" not in c]
    absolute = [c for c in candidates if c.startswith("/")]
    assert bare, "expected bare command names to be tried first"
    assert absolute, "expected absolute fallbacks for a minimal PATH"
    assert candidates.index(bare[-1]) < candidates.index(absolute[0])
    assert any(c.startswith("/opt/homebrew/") for c in absolute)


def test_explicit_override_wins_outright():
    assert _candidates({"LIVEPILOT_PYTHON": "/custom/python3.12"}) == ["/custom/python3.12"]


@POSIX_ONLY
def test_minimal_path_still_finds_a_supported_interpreter():
    """The Claude Desktop GUI-launch case: PATH has only /usr/bin:/bin."""
    shim = _repo_root() / "bin" / "livepilot.js"
    out = subprocess.run(
        [NODE, "-e", f"process.stdout.write(JSON.stringify(require({str(shim)!r}).findPython()))"],
        cwd=_repo_root(),
        env={"HOME": os.environ.get("HOME", ""), "PATH": "/usr/bin:/bin"},
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    found = json.loads(out.stdout)
    if found is None or found.get("tooOld"):
        pytest.skip("no interpreter >= 3.12 installed in a well-known location")
    major, minor = (int(part) for part in found["version"].split()[1].split(".")[:2])
    assert (major, minor) >= (3, 12), found

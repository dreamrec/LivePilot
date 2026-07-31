"""Guards that the suite stays order-independent.

Two tests used to pass or fail purely on which other tests ran first
(found 2026-07-31, and invisible to a full-suite run):

  * `test_simpler_sample_native::test_rejects_non_simpler_device` — eight test
    files inject a fake `Live` module into sys.modules and most never remove
    it. `version_detect.py` does `import Live` at module scope, binding that
    module OBJECT permanently, so once `test_devices_duplicate_loading` left
    its 12.0.0 fake behind, a later 12.4.0 fake could not displace it. The
    version probe kept returning 12.0.0 and a 12.4-gated handler refused to
    run. Fixed by the `_restore_injected_modules` autouse fixture in
    conftest.py.

  * `test_research_engine::test_boosts_predicted_devices` — `targeted_research`
    enriches entries from the process-wide device-atlas singleton before
    scoring them, so the result depended on whether an earlier test had loaded
    the atlas. Fixed by that class declaring the dependency explicitly.

A green full-suite run does NOT prove either is fixed: the full run picks a
different, lucky ordering. These guards reproduce the unlucky ones directly.
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The `-k` slice under which both failures reproduced.
_FAILING_K = "device or analyzer or plugin or health"

# Minimal (leaker, victim) pairs found by delta-debugging the slice.
_ORDER_PAIRS = [
    pytest.param(
        "tests/test_devices_duplicate_loading.py",
        "tests/test_simpler_sample_native.py",
        id="fake-Live-leak",
    ),
    pytest.param(
        "tests/test_browser_device_index.py",
        "tests/test_research_engine.py",
        id="atlas-singleton-leak",
    ),
]


@pytest.mark.parametrize("leaker, victim", _ORDER_PAIRS)
def test_known_bad_orderings_now_pass(leaker, victim):
    """Run each unlucky ordering in a fresh interpreter."""
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q",
            "-p", "no:cacheprovider",
            "-k", _FAILING_K,
            leaker, victim,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"running {leaker} before {victim} reintroduced an order dependency:\n"
        f"{result.stdout[-3000:]}"
    )


# --- the fixture itself ------------------------------------------------------
#
# These two run in definition order (pytest preserves it within a file), so the
# second observes whether the first's injection survived.

_SENTINEL = "Live.__isolation_probe__"


def test_a_inject_fake_live_modules():
    """Simulate what the eight faking test files do."""
    sys.modules["Live"] = types.ModuleType("Live")
    sys.modules[_SENTINEL] = types.ModuleType(_SENTINEL)
    sys.modules["remote_script.LivePilot.__isolation_probe__"] = types.ModuleType("x")


def test_b_injection_did_not_leak():
    """...and confirm the autouse fixture reverted all of it."""
    leaked = [
        name for name in ("Live", _SENTINEL, "remote_script.LivePilot.__isolation_probe__")
        if name in sys.modules
    ]
    assert not leaked, (
        "conftest._restore_injected_modules did not clean up injected modules: "
        f"{leaked}. Without it, a faked `Live` reaches every later test."
    )


def test_fixture_restores_a_replaced_module_by_identity():
    """Replacing an existing entry must restore the ORIGINAL object.

    Restoring only by key would leave any module holding a
    `from Live import X` reference pointing at the impostor.
    """
    original = types.ModuleType("Live")
    original.marker = "original"
    sys.modules["Live"] = original

    # Simulate a nested test replacing it, then the fixture restoring.
    from tests.conftest import _is_injected_module

    saved = {k: v for k, v in sys.modules.items() if _is_injected_module(k)}
    sys.modules["Live"] = types.ModuleType("Live")  # impostor
    for key in [k for k in sys.modules if _is_injected_module(k)]:
        if key not in saved:
            del sys.modules[key]
    sys.modules.update(saved)

    assert sys.modules["Live"] is original, "restore must be by identity, not just key"

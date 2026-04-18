"""Bridge parity tests — Python BRIDGE_COMMANDS must align with the Max JS dispatch.

Catches drift like the load_sample_to_simpler misclassification that landed in
BRIDGE_COMMANDS despite having no JS case. Runs as a normal pytest — reads the
m4l_device/livepilot_bridge.js file directly and compares case labels to the
Python frozenset.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp_server.runtime.remote_commands import BRIDGE_COMMANDS


REPO = Path(__file__).resolve().parent.parent
BRIDGE_JS = REPO / "m4l_device" / "livepilot_bridge.js"


def _js_dispatch_cases() -> set[str]:
    """Extract every `case "<name>":` label from the JS dispatch switch.

    Read with explicit UTF-8 encoding. Without this, Windows (which defaults
    to cp1252 / Windows-1252) fails on the em-dash bytes in the file's
    header comment, breaking CI on windows-latest runners.
    """
    if not BRIDGE_JS.exists():
        return set()
    text = BRIDGE_JS.read_text(encoding="utf-8")
    return set(re.findall(r'case\s+"([^"]+)"\s*:', text))


def test_every_python_bridge_command_has_js_dispatch_case():
    """Every command in Python's BRIDGE_COMMANDS must have a JS `case`.

    If this fails, either:
      - remove the stray command from BRIDGE_COMMANDS if it's not actually
        bridge-implemented (e.g., it's really an MCP Python tool), OR
      - add a `case "<name>":` to livepilot_bridge.js that dispatches to a
        real JS handler.
    """
    js_cases = _js_dispatch_cases()
    assert js_cases, (
        f"Could not parse case labels from {BRIDGE_JS}. Check the file exists "
        f"and the switch statement uses quoted case labels."
    )

    missing = sorted(c for c in BRIDGE_COMMANDS if c not in js_cases)
    assert not missing, (
        f"Python BRIDGE_COMMANDS declares commands with no JS dispatch case: "
        f"{missing}. Either remove them from BRIDGE_COMMANDS (if they are not "
        f"actually bridge commands) or add matching cases in livepilot_bridge.js."
    )


def test_no_stray_js_cases_outside_whitelist():
    """Fail if the JS bridge has command cases not declared in BRIDGE_COMMANDS.

    Previously this test printed a warning and passed, which meant a new JS
    dispatch case added to livepilot_bridge.js without a matching Python
    registration would slip through CI. That's the exact shape of BUG-A3
    (the bridge/Python drift class). Now a hard failure — any JS-only case
    that isn't in ``internal_only`` must be registered in Python or
    whitelisted here with a justification.
    """
    js_cases = _js_dispatch_cases()
    # JS-internal commands that are never invoked through Python plans. Keep
    # this list tight — every addition here needs a code review.
    internal_only = {"ping"}
    stray = sorted(
        c for c in js_cases
        if c not in BRIDGE_COMMANDS and c not in internal_only
    )
    assert not stray, (
        f"JS dispatch has commands not in Python BRIDGE_COMMANDS: {stray}. "
        f"Add them to mcp_server/runtime/remote_commands.py:BRIDGE_COMMANDS "
        f"so plans can reference them, OR explicitly add to the "
        f"internal_only set in this test with a comment explaining why."
    )

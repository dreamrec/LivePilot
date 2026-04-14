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
    """Extract every `case "<name>":` label from the JS dispatch switch."""
    if not BRIDGE_JS.exists():
        return set()
    text = BRIDGE_JS.read_text()
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
    """Flag JS cases that are not in Python BRIDGE_COMMANDS (informational).

    Does not fail the suite — some JS cases (like `ping`) are internal health
    checks. Prints any stray cases so the maintainer notices new JS commands
    that forgot their Python registration.
    """
    js_cases = _js_dispatch_cases()
    internal_only = {"ping"}  # JS-internal, never called from Python plans
    stray = sorted(
        c for c in js_cases
        if c not in BRIDGE_COMMANDS and c not in internal_only
    )
    if stray:
        # Informational, not a failure — keep the suite green but surface drift.
        print(
            f"\nINFO: JS dispatch has commands not in Python BRIDGE_COMMANDS: "
            f"{stray}. If these are real bridge commands, add them to "
            f"mcp_server/runtime/remote_commands.py:BRIDGE_COMMANDS so plans "
            f"can reference them."
        )

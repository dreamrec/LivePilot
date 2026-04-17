"""Contract tests that enforce compiler safety invariants.

Walks every registered semantic-move compiler with a representative kernel
and asserts that no emitted CompiledStep contains a dangerous raw-index
target:

  - device_index=0 AND parameter_index=0 on set_device_parameter or
    apply_automation_shape, because parameter 0 on every Ableton device is
    "Device On" — a fractional write disables the device silently.

  - parameter_index=0 with value != 0/1 even on a resolver-confirmed device,
    for the same reason.

Safe patterns this test DOES allow:
  - device_index=0 on set_simpler_playback_mode against a freshly-inserted
    Simpler (which really is the only device on the new track).

If you add a compiler that targets device parameters, resolve the parameter
by name first (add a helper to resolvers.py) and explicitly whitelist it in
_ALLOWED_PARAM0_TOOLS below.
"""

from __future__ import annotations

import pytest

from mcp_server.semantic_moves import compiler as _compiler_mod

# Ensure all compiler modules are imported so they register with _COMPILERS.
from mcp_server.semantic_moves import (  # noqa: F401
    mix_compilers,
    sound_design_compilers,
    transition_compilers,
    sample_compilers,
)
from mcp_server.semantic_moves.models import SemanticMove


_REPRESENTATIVE_KERNEL = {
    "mode": "improve",
    "session_info": {
        "tempo": 120,
        "tracks": [
            {"index": 0, "name": "Drums", "volume": 0.7},
            {"index": 1, "name": "Bass", "volume": 0.65},
            {"index": 2, "name": "Chords", "volume": 0.6},
            {"index": 3, "name": "Pad", "volume": 0.55},
            {"index": 4, "name": "Lead", "volume": 0.6},
        ],
    },
}


# Tools where device_index=0 is legitimate because the device has just been
# inserted on a fresh track and is guaranteed to be at index 0.
_ALLOWED_PARAM0_TOOLS: set[str] = {
    "set_simpler_playback_mode",
}


def _iter_registered_moves():
    """Yield (move_id, SemanticMove) for every compiler in the registry."""
    for key, fn in _compiler_mod._COMPILERS.items():
        if key.startswith("__family__"):
            continue
        move = SemanticMove(
            move_id=key,
            family="mix",
            intent=f"test compile of {key}",
        )
        yield key, fn, move


def test_no_blind_parameter_index_0_in_any_compiler():
    offenders: list[str] = []
    for move_id, fn, move in _iter_registered_moves():
        try:
            plan = fn(move, _REPRESENTATIVE_KERNEL)
        except Exception as exc:
            pytest.fail(f"compiler for {move_id} raised: {exc}")
        for step in plan.steps:
            tool = step.tool
            params = step.params or {}
            if tool in _ALLOWED_PARAM0_TOOLS:
                continue
            if tool in ("set_device_parameter", "apply_automation_shape"):
                if (
                    params.get("device_index") == 0
                    and params.get("parameter_index") == 0
                ):
                    offenders.append(
                        f"{move_id}: {tool} with device_index=0, "
                        f"parameter_index=0 — that's 'Device On' on every "
                        f"Ableton device and will disable it."
                    )
    assert not offenders, "Blind parameter-0 targets reintroduced:\n" + "\n".join(offenders)


def test_no_device_parameter_writes_without_resolver_check():
    """No compiler should emit set_device_parameter OR apply_automation_shape
    against a device-type parameter without the kernel supplying device data.

    The representative kernel has no devices declared — so any compiler that
    still emits a device-param step is targeting a device it hasn't verified
    exists. That's the exact class of bug Finding 6 called out.
    """
    offenders: list[str] = []
    for move_id, fn, move in _iter_registered_moves():
        plan = fn(move, _REPRESENTATIVE_KERNEL)
        for step in plan.steps:
            tool = step.tool
            params = step.params or {}
            if tool == "set_device_parameter":
                offenders.append(
                    f"{move_id}: set_device_parameter emitted without any "
                    f"device info in the kernel — params={params}"
                )
            if tool == "apply_automation_shape":
                if params.get("parameter_type") == "device":
                    offenders.append(
                        f"{move_id}: apply_automation_shape(parameter_type="
                        f"'device') emitted without device resolution — "
                        f"params={params}"
                    )
    assert not offenders, "Unsafe device-param emits:\n" + "\n".join(offenders)

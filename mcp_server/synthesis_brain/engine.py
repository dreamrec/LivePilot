"""Synthesis-brain engine — dispatches to the right adapter based on device name.

Two primary entry points:
  analyze_synth_patch(device_name, ...) -> SynthProfile
  propose_synth_branches(device_name, ...) -> list[(BranchSeed, compiled_plan)]

Both are pure Python — no @mcp.tool() decorators in PR9. PR12 wires
dedicated MCP tools and does the tool-count metadata sweep.
"""

from __future__ import annotations

from typing import Optional

from ..branches import BranchSeed
from .adapters import get_adapter, registered_devices
from .models import SynthProfile, TimbralFingerprint, OPAQUE


def supported_devices() -> list[str]:
    """List devices that synthesis_brain has an adapter for."""
    return registered_devices()


def analyze_synth_patch(
    device_name: str,
    track_index: int,
    device_index: int,
    parameter_state: dict,
    display_values: Optional[dict] = None,
    role_hint: str = "",
) -> SynthProfile:
    """Extract a SynthProfile from live parameter state.

    When no adapter exists for the device, returns an opaque SynthProfile —
    the profile still carries parameter_state + display_values so callers
    can inspect the raw patch, but without device-specific structure.
    Opacity lets the composer / Wonder / user-facing layer decide how to
    handle unsupported devices.
    """
    adapter = get_adapter(device_name)
    if adapter is None:
        return SynthProfile(
            device_name=device_name,
            opacity=OPAQUE,
            track_index=track_index,
            device_index=device_index,
            parameter_state=dict(parameter_state or {}),
            display_values=dict(display_values or {}),
            role_hint=role_hint,
            notes=[
                f"No synthesis_brain adapter for '{device_name}'; "
                f"falling back to opaque profile"
            ],
        )
    return adapter.extract_profile(
        track_index=track_index,
        device_index=device_index,
        parameter_state=parameter_state or {},
        display_values=display_values or {},
        role_hint=role_hint,
    )


def propose_synth_branches(
    profile: SynthProfile,
    target: Optional[TimbralFingerprint] = None,
    kernel: Optional[dict] = None,
) -> list[tuple[BranchSeed, dict]]:
    """Emit synthesis-source branch seeds for the given profile.

    Returns a list of (seed, compiled_plan) tuples. Seeds carry
    source="synthesis" and a distinctness reason; compiled_plan is the
    execution_router-ready dict with pre-filled steps. Both can be
    handed to create_experiment(seeds=[seed_dicts], compiled_plans=[plans])
    with no further compilation needed.

    When the profile is opaque (no adapter), returns an empty list.
    Callers can fall back to analytical-only seeds in that case.
    """
    if profile.opacity != "native":
        return []
    adapter = get_adapter(profile.device_name)
    if adapter is None:
        return []
    target = target or TimbralFingerprint()
    return adapter.propose_branches(
        profile=profile,
        target=target,
        kernel=kernel or {},
    )

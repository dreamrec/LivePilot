"""SynthAdapter base protocol + registry infrastructure.

Adapters are plain classes that expose:
  - device_name (class attribute)
  - extract_profile(track_index, device_index, parameter_state, display_values,
                    role_hint) -> SynthProfile
  - propose_branches(profile, target, kernel) -> list[tuple[BranchSeed, dict]]
    (each tuple: (seed, compiled_plan_dict))

Adapters register themselves via ``register_adapter(cls)`` as a class
decorator at module-import time, so the registry is populated when
the adapters package is imported.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional

from ...branches import BranchSeed
from ..models import SynthProfile, TimbralFingerprint


# Adapter registry — populated by register_adapter at import time.
_REGISTRY: dict[str, "SynthAdapter"] = {}


@runtime_checkable
class SynthAdapter(Protocol):
    """Contract every native-synth adapter must satisfy."""

    device_name: str

    def extract_profile(
        self,
        track_index: int,
        device_index: int,
        parameter_state: dict,
        display_values: Optional[dict] = None,
        role_hint: str = "",
    ) -> SynthProfile:
        """Build a SynthProfile from raw device parameter state.

        Must be pure — no I/O. The caller has already fetched parameters
        via get_device_parameters / get_display_values and hands them here.
        """
        ...

    def propose_branches(
        self,
        profile: SynthProfile,
        target: TimbralFingerprint,
        kernel: Optional[dict] = None,
    ) -> list[tuple[BranchSeed, dict]]:
        """Emit seed + pre-compiled plan pairs.

        Each pair: (BranchSeed with source="synthesis", compiled_plan dict
        ready for execution_router.execute_plan_steps_async).

        The kernel dict may carry freshness / creativity_profile / synth_hints
        (see SessionKernel PR2 additions); adapters read these to bias
        proposals. Pre-PR10, adapters ship canned proposers; later PRs
        extend with render-based verification.
        """
        ...


def register_adapter(cls):
    """Class decorator — register an adapter under its device_name.

    Raises ValueError if the class lacks device_name or duplicates an
    existing registration.
    """
    device_name = getattr(cls, "device_name", None)
    if not device_name:
        raise ValueError(
            f"Adapter {cls.__name__} must define a class attribute "
            f"'device_name' to register"
        )
    if device_name in _REGISTRY:
        raise ValueError(
            f"Duplicate synth adapter registration for device '{device_name}' "
            f"(existing: {type(_REGISTRY[device_name]).__name__}, "
            f"new: {cls.__name__})"
        )
    _REGISTRY[device_name] = cls()
    return cls

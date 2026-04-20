"""Synth adapter registry.

Each adapter is a Python class implementing the SynthAdapter protocol.
Registration is explicit — adapters add themselves to ``_REGISTRY`` at
module import time. ``get_adapter(device_name)`` returns the registered
adapter or None.
"""

from __future__ import annotations

from .base import SynthAdapter, _REGISTRY, register_adapter
from . import wavetable as _wavetable  # noqa: F401 — import for registration
from . import operator as _operator  # noqa: F401
from . import analog as _analog  # noqa: F401
from . import drift as _drift  # noqa: F401
from . import meld as _meld  # noqa: F401


def get_adapter(device_name: str) -> SynthAdapter | None:
    """Return the adapter for a given Ableton device name, or None."""
    return _REGISTRY.get(device_name)


def registered_devices() -> list[str]:
    """List device names this package has an adapter for."""
    return sorted(_REGISTRY.keys())


__all__ = [
    "SynthAdapter",
    "get_adapter",
    "register_adapter",
    "registered_devices",
]

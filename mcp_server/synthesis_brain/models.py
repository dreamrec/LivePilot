"""Synthesis-brain data models.

Pure dataclasses — zero I/O. Shape is intentionally minimal in PR9;
later PRs firm up fields as adapters discover what's actually useful.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


# Device opacity markers — natives are inspectable via device parameters,
# opaque plugins (AU / VST) are not. Adapters are registered for natives only.
NATIVE = "native"
OPAQUE = "opaque"

DeviceOpacity = Literal["native", "opaque"]


@dataclass
class TimbralFingerprint:
    """A compact per-device timbre target.

    All dimensions are floats in [-1.0, 1.0]; 0.0 means "no change from
    whatever the source patch is". This intentionally mirrors the existing
    TimbralGoalVector in sound_design.models so the two subsystems can
    share goal inputs.
    """

    brightness: float = 0.0
    warmth: float = 0.0
    bite: float = 0.0
    softness: float = 0.0
    instability: float = 0.0
    width: float = 0.0
    texture_density: float = 0.0
    movement: float = 0.0
    polish: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModulationGraph:
    """Flat list of modulation routes on a single device.

    Each route: {source, target, amount, range}. Shape is deliberately
    loose because natives differ (Wavetable has LFO routing, Operator
    has a per-osc modulation matrix, Analog has FM + Envelope routing).
    Adapters populate it in a device-consistent way.
    """

    routes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"routes": list(self.routes)}


@dataclass
class ArticulationProfile:
    """How a patch responds to note-on / note-off / velocity.

    attack_ms / release_ms are envelope rough times; velocity_mapping is
    a tag ("linear", "exponential", "flat"); mono indicates mono-only
    mode (portamento hints live here in later PRs).
    """

    attack_ms: float = 0.0
    release_ms: float = 0.0
    velocity_mapping: str = "linear"
    mono: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SynthProfile:
    """Extracted per-device patch state.

    Fields:
      device_name: the Ableton device name ("Wavetable", "Operator", ...)
      opacity: NATIVE ⇒ adapter knows this device; OPAQUE ⇒ fallback path
      track_index / device_index: where the device lives in the session
      parameter_state: raw ``{name: value}`` dict from get_device_parameters;
        adapters translate this into structured knowledge
      display_values: parallel ``{name: value_string}`` when available
        (lets adapters reason about actual Hz / dB / % rather than 0-1 floats)
      role_hint: caller-supplied role ("pad", "lead", "bass", "perc", ...) or ""
      modulation: the device's current modulation graph
      articulation: envelope + velocity response
      notes: free-form observations the adapter wants to record for downstream
        reasoning (e.g. "voices=4, detune=0.12 — subtly rich already")
    """

    device_name: str = ""
    opacity: DeviceOpacity = OPAQUE
    track_index: int = -1
    device_index: int = -1
    parameter_state: dict = field(default_factory=dict)
    display_values: dict = field(default_factory=dict)
    role_hint: str = ""
    modulation: ModulationGraph = field(default_factory=ModulationGraph)
    articulation: ArticulationProfile = field(default_factory=ArticulationProfile)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "device_name": self.device_name,
            "opacity": self.opacity,
            "track_index": self.track_index,
            "device_index": self.device_index,
            "parameter_state": dict(self.parameter_state),
            "display_values": dict(self.display_values),
            "role_hint": self.role_hint,
            "modulation": self.modulation.to_dict(),
            "articulation": self.articulation.to_dict(),
            "notes": list(self.notes),
        }

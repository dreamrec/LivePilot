"""Sound Design Engine state models — all dataclasses with to_dict().

Pure data structures representing timbral goals, patch topology,
layer strategy, and the composite SoundDesignState container.

Zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Timbral Goal Vector ──────────────────────────────────────────────


@dataclass
class TimbralGoalVector:
    """Multi-dimensional timbral target compiled from natural language.

    Each dimension is a float in [-1.0, 1.0] where 0.0 means "no change".
    Positive values push toward more of that quality, negative toward less.
    ``protect`` is a dict of dimensions that must not regress, with threshold weights.
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
    protect: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Patch Block ──────────────────────────────────────────────────────


VALID_BLOCK_TYPES = frozenset({
    "oscillator",
    "filter",
    "envelope",
    "lfo",
    "spatial",
    "saturation",
    "effect",
})


@dataclass
class PatchBlock:
    """A single functional block within a device chain.

    ``block_type`` must be one of the VALID_BLOCK_TYPES.
    ``controllable`` indicates whether the block's parameters are exposed
    to automation (True for native devices, often False for opaque plugins).
    """

    block_type: str = "effect"
    device_name: str = ""
    controllable: bool = True

    def __post_init__(self) -> None:
        if self.block_type not in VALID_BLOCK_TYPES:
            raise ValueError(
                f"Invalid block_type '{self.block_type}'. "
                f"Must be one of {sorted(VALID_BLOCK_TYPES)}"
            )

    def to_dict(self) -> dict:
        return asdict(self)


# ── Patch Model ──────────────────────────────────────────────────────


@dataclass
class PatchModel:
    """Structural model of an instrument/effect chain on a single track.

    ``device_chain`` lists device names in signal-flow order.
    ``roles`` describes the musical role(s) this patch fills
    (e.g. ["lead"], ["sub_anchor", "body_layer"]).
    ``blocks`` lists the controllable functional blocks.
    ``opaque_blocks`` lists device names whose internals are not inspectable.
    """

    track_index: int = 0
    device_chain: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    blocks: list[PatchBlock] = field(default_factory=list)
    opaque_blocks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "track_index": self.track_index,
            "device_chain": list(self.device_chain),
            "roles": list(self.roles),
            "blocks": [b.to_dict() for b in self.blocks],
            "opaque_blocks": list(self.opaque_blocks),
        }


# ── Layer Strategy ───────────────────────────────────────────────────


@dataclass
class LayerStrategy:
    """Describes how multiple tracks/layers divide timbral labor.

    Each field is an optional track index indicating which track
    owns that layer role.  None means no track is assigned.
    """

    sub_anchor: Optional[int] = None
    body_layer: Optional[int] = None
    transient_layer: Optional[int] = None
    texture_layer: Optional[int] = None
    width_layer: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Composite State ──────────────────────────────────────────────────


@dataclass
class SoundDesignState:
    """Top-level container for sound design analysis of a track."""

    goal: TimbralGoalVector = field(default_factory=TimbralGoalVector)
    patch: PatchModel = field(default_factory=PatchModel)
    layers: LayerStrategy = field(default_factory=LayerStrategy)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal.to_dict(),
            "patch": self.patch.to_dict(),
            "layers": self.layers.to_dict(),
        }

"""Affordance-preset library — named presets per Ableton device class.

v1.21 (minimal): infrastructure + 3 seed presets proving the resolver
pattern:
  - reverb.yaml       → preset: dub-cathedral
  - delay.yaml        → preset: ping-pong-dub
  - auto-filter.yaml  → preset: slow-sweep

v1.22 (planned): full catalog coverage, class_name → slug inference,
taste-graph integration for preset ranking.

Public API (re-exported for ``from mcp_server.affordances import ...``):
  resolve_preset(device_slug, preset_name) -> dict[str, number|bool] | None
  list_devices() -> list[str]
  list_presets(device_slug) -> list[str]
  get_preset_metadata(device_slug, preset_name) -> dict | None
"""

from .presets import (
    resolve_preset,
    list_devices,
    list_presets,
    get_preset_metadata,
)

__all__ = [
    "resolve_preset",
    "list_devices",
    "list_presets",
    "get_preset_metadata",
]

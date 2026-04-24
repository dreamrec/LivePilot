"""Preset loader for affordance-device YAML files.

Runtime resolution only — schema validation lives in ``_schema.py`` and
fires at test-time. The loader is tolerant of malformed files (returns
None rather than raising) so production code never crashes on a bad
preset; the schema validator catches those pre-ship.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml


_AFFORDANCES_ROOT = Path(__file__).parent / "devices"


def _load_device_yaml(device_slug: str) -> Optional[dict]:
    """Load and parse a device's YAML file. Returns None on any error."""
    path = _AFFORDANCES_ROOT / f"{device_slug}.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def resolve_preset(device_slug: str, preset_name: str) -> Optional[dict[str, Any]]:
    """Return the ``param_overrides`` dict for a named preset, or None.

    Returns None on: missing device file, missing preset, unparseable YAML,
    or a preset record without ``param_overrides``.
    """
    data = _load_device_yaml(device_slug)
    if data is None:
        return None
    preset = data.get("presets", {}).get(preset_name)
    if not isinstance(preset, dict):
        return None
    overrides = preset.get("param_overrides")
    return dict(overrides) if isinstance(overrides, dict) else None


def get_preset_metadata(device_slug: str, preset_name: str) -> Optional[dict]:
    """Return the full preset record (description + pairings + risk_notes
    + param_overrides) or None."""
    data = _load_device_yaml(device_slug)
    if data is None:
        return None
    preset = data.get("presets", {}).get(preset_name)
    return dict(preset) if isinstance(preset, dict) else None


def list_devices() -> list[str]:
    """Return device slugs with available preset files, sorted."""
    if not _AFFORDANCES_ROOT.exists():
        return []
    return sorted(p.stem for p in _AFFORDANCES_ROOT.glob("*.yaml"))


def list_presets(device_slug: str) -> list[str]:
    """Return preset names for a given device slug, sorted. Empty list
    on missing device or malformed YAML."""
    data = _load_device_yaml(device_slug)
    if data is None:
        return []
    presets = data.get("presets", {})
    if not isinstance(presets, dict):
        return []
    return sorted(presets.keys())

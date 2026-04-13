"""
Enrichment loader — reads YAML files from subdirectories and merges them
into scanned device entries.

Directory layout::

    enrichments/
        instruments/
            analog.yaml
            wavetable.yaml
        audio_effects/
            compressor.yaml
            eq_eight.yaml
        _templates/       # skipped (leading underscore)
            ...
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_enrichments(enrichments_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Walk *enrichments_dir* and load every YAML file into a dict.

    Files whose name starts with ``_`` are skipped (convention for templates
    or drafts).  Each file must be named ``<device_id>.yaml`` and contain a
    mapping of enrichment fields.

    Returns
    -------
    dict[str, dict]
        ``{device_id: enrichment_data}``
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        # PyYAML not installed — return empty gracefully
        return {}

    enrichments_path = Path(enrichments_dir)
    result: dict[str, dict[str, Any]] = {}

    if not enrichments_path.is_dir():
        return result

    for root, _dirs, files in os.walk(enrichments_path):
        # Skip directories whose name starts with _
        root_name = os.path.basename(root)
        if root_name.startswith("_"):
            continue
        for fname in sorted(files):
            if fname.startswith("_"):
                continue
            if not fname.endswith((".yaml", ".yml")):
                continue
            device_id = fname.rsplit(".", 1)[0]
            filepath = os.path.join(root, fname)
            with open(filepath, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict):
                result[device_id] = data

    return result


# Fields that enrichment data can overwrite on a device entry
_ENRICHMENT_FIELDS = frozenset({
    "sonic_description",
    "synthesis_type",
    "effect_type",
    "character_tags",
    "use_cases",
    "genre_affinity",
    "complexity",
    "self_contained",
    "mcp_controllable",
    "key_parameters",
    "pairs_well_with",
    "starter_recipes",
    "gotchas",
    "health_flags",
    "introduced_in",
    "signal_type",
})


def merge_enrichments(
    devices: list[dict[str, Any]],
    enrichments: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge enrichment data into device entries **in place** and return the list.

    Only fields in ``_ENRICHMENT_FIELDS`` are written.  Sets ``enriched=True``
    on every device that receives at least one enrichment field.
    """
    for device in devices:
        device_id = device.get("id", "")
        if device_id not in enrichments:
            continue
        enrich = enrichments[device_id]
        touched = False
        for field in _ENRICHMENT_FIELDS:
            if field in enrich:
                device[field] = enrich[field]
                touched = True
        if touched:
            device["enriched"] = True
    return devices

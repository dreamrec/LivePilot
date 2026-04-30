"""ADG scanner — wraps scripts/als_deep_parse.parse_adg for one-file use.

Reuses the production-grade preset parser:
  - Macro display names via KeyMidi binding resolution (BUG-PARSER#2 fix)
  - Branch / chain extraction
  - Device summary

Same module as the .als parser; we share the lazy importer.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..scanner import Scanner, register_scanner
from .als import _als_parse  # share the lazy importer


@register_scanner
class AdgScanner(Scanner):
    type_id = "adg"
    file_extensions = [".adg", ".adv"]
    output_subdir = "racks"
    schema_version = 1

    def scan_one(self, path: Path) -> dict:
        parser = _als_parse()
        return parser.parse_adg(str(path))

    def derive_tags(self, sidecar: dict) -> list[str]:
        tags: list[str] = ["rack-preset"]
        rack_class = sidecar.get("rack_class")
        if rack_class:
            tags.append(_class_to_tag(rack_class))
        preset_type = sidecar.get("preset_type")
        if preset_type:
            tags.append(preset_type)

        # Top 3 named macros (already canonicalized by the parser)
        for m in (sidecar.get("macros") or [])[:8]:
            name = (m.get("name") or "").strip()
            if name and not name.startswith("Macro "):
                slug = _slug(name)
                if slug:
                    tags.append(f"macro:{slug}")

        if sidecar.get("chains"):
            tags.append("has-chains")
        bc = sidecar.get("branch_counts") or {}
        if isinstance(bc, dict) and sum(bc.values()) > 1:
            tags.append("multi-branch")
        return tags

    def derive_description(self, sidecar: dict) -> str:
        rack_class = sidecar.get("rack_class") or "rack"
        macros = sidecar.get("macros") or []
        n_named = sum(
            1 for m in macros
            if (m.get("name") or "").strip() and not (m.get("name") or "").startswith("Macro ")
        )
        n_branches = sum((sidecar.get("branch_counts") or {}).values())
        return (
            f"{rack_class} preset with {len(macros)} macros "
            f"({n_named} producer-named), {n_branches} branches"
        )


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _class_to_tag(rack_class: str) -> str:
    return {
        "InstrumentGroupDevice": "instrument-rack",
        "AudioEffectGroupDevice": "audio-effect-rack",
        "MidiEffectGroupDevice": "midi-effect-rack",
        "DrumGroupDevice": "drum-rack",
    }.get(rack_class, _slug(rack_class))

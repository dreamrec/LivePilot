"""Plugin preset scanner — captures identity metadata from VST/VST3/AU/NKS preset files.

Param VALUES are plugin-specific binary blobs and stay opaque (same constraint
as PluginDevice in .als). What we extract:
  - .aupreset: plist key/value (manufacturer, name, type)
  - .vstpreset: VST3 preset header (class id, plugin name)
  - .fxp/.fxb: VST2 chunk headers (manufacturer + plugin code)
  - .nksf: Native Instruments preset (NI metadata via JSON sidecar block)

For unknown formats we still produce a usable wrapper from the file path
(plugin name often = parent folder, manufacturer = grandparent folder).
"""

from __future__ import annotations

import plistlib
import re
import struct
from pathlib import Path
from typing import Any

from ..scanner import Scanner, register_scanner


@register_scanner
class PluginPresetScanner(Scanner):
    type_id = "plugin-preset"
    file_extensions = [".aupreset", ".vstpreset", ".fxp", ".fxb", ".nksf"]
    output_subdir = "plugin_presets"
    schema_version = 1

    def scan_one(self, path: Path) -> dict:
        ext = path.suffix.lower()
        if ext == ".aupreset":
            return _parse_aupreset(path)
        if ext == ".vstpreset":
            return _parse_vstpreset(path)
        if ext in (".fxp", ".fxb"):
            return _parse_vst2_chunk(path)
        if ext == ".nksf":
            return _parse_nksf(path)
        return _fallback_metadata(path)

    def derive_tags(self, sidecar: dict) -> list[str]:
        tags = ["plugin-preset"]
        fmt = sidecar.get("format")
        if fmt:
            tags.append(fmt.lower())
        man = sidecar.get("manufacturer")
        if man:
            tags.append(f"vendor:{_slug(man)}")
        plug = sidecar.get("plugin_name")
        if plug:
            tags.append(f"plugin:{_slug(plug)}")
        return tags

    def derive_description(self, sidecar: dict) -> str:
        fmt = sidecar.get("format") or "preset"
        plug = sidecar.get("plugin_name") or "unknown plugin"
        man = sidecar.get("manufacturer") or "unknown vendor"
        name = sidecar.get("preset_name") or sidecar.get("name") or ""
        suffix = f" — {name}" if name else ""
        return f"{fmt} preset for {plug} ({man}){suffix}"


# ─── Format-specific parsers ─────────────────────────────────────────────────


def _parse_aupreset(path: Path) -> dict:
    """AU preset = binary plist with metadata + opaque ParameterData blob."""
    out: dict[str, Any] = {
        "format": "AU",
        "name": path.stem,
        "preset_name": path.stem,
        "plugin_name": None,
        "manufacturer": None,
    }
    try:
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
        if isinstance(plist, dict):
            out["plugin_name"] = plist.get("name") or plist.get("manufacturer-name")
            out["manufacturer"] = _decode_au_id(plist.get("manufacturer"))
            out["subtype"] = _decode_au_id(plist.get("subtype"))
            out["type_code"] = _decode_au_id(plist.get("type"))
            if plist.get("name"):
                out["preset_name"] = str(plist["name"])
    except Exception:  # noqa: BLE001
        pass
    return out


def _parse_vstpreset(path: Path) -> dict:
    """VST3 .vstpreset has a binary header containing the plugin's class UID."""
    out: dict[str, Any] = {
        "format": "VST3",
        "name": path.stem,
        "preset_name": path.stem,
        "plugin_name": None,
        "manufacturer": None,
    }
    try:
        with path.open("rb") as fh:
            # VST3 preset starts with "VST3" magic + version + class id
            magic = fh.read(4)
            if magic == b"VST3":
                fh.read(4)  # version
                class_id = fh.read(32)
                out["class_uid"] = class_id.hex() if class_id else None
        # Plugin name often inferable from path: .../VST3 Presets/<vendor>/<plugin>/<preset>.vstpreset
        parts = list(path.parts)
        if len(parts) >= 3:
            out["plugin_name"] = parts[-2]
            out["manufacturer"] = parts[-3]
    except Exception:  # noqa: BLE001
        pass
    return out


def _parse_vst2_chunk(path: Path) -> dict:
    """VST2 .fxp/.fxb has a 'CcnK' chunk header with plugin code + name."""
    out: dict[str, Any] = {
        "format": "VST2",
        "name": path.stem,
        "preset_name": path.stem,
        "plugin_name": None,
        "manufacturer": None,
    }
    try:
        with path.open("rb") as fh:
            head = fh.read(60)
            if head[:4] == b"CcnK":
                # offset 16 (4 bytes) = plugin's unique fourCC
                if len(head) >= 20:
                    out["plugin_code"] = head[16:20].decode("ascii", errors="ignore").strip()
                # offset 28 (28-byte name) = preset/program name
                if len(head) >= 60:
                    name_bytes = head[28:60].split(b"\x00", 1)[0]
                    out["preset_name"] = name_bytes.decode("latin-1", errors="ignore").strip() or path.stem
    except Exception:  # noqa: BLE001
        pass
    return out


def _parse_nksf(path: Path) -> dict:
    """NKS preset is a riff-like container; try to find metadata JSON block."""
    out: dict[str, Any] = {
        "format": "NKS",
        "name": path.stem,
        "preset_name": path.stem,
        "plugin_name": None,
        "manufacturer": None,
    }
    try:
        raw = path.read_bytes()
        m = re.search(rb'\{[^}]*"vendor"[^}]*\}', raw)
        if m:
            import json
            try:
                meta = json.loads(m.group(0))
                if isinstance(meta, dict):
                    out["manufacturer"] = meta.get("vendor")
                    out["plugin_name"] = meta.get("product")
                    out["preset_name"] = meta.get("name") or path.stem
            except json.JSONDecodeError:
                pass
    except Exception:  # noqa: BLE001
        pass
    return out


def _fallback_metadata(path: Path) -> dict:
    """When format-specific parsing fails, infer from filesystem layout."""
    parts = list(path.parts)
    return {
        "format": "unknown",
        "name": path.stem,
        "preset_name": path.stem,
        "plugin_name": parts[-2] if len(parts) >= 2 else None,
        "manufacturer": parts[-3] if len(parts) >= 3 else None,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _decode_au_id(value: Any) -> str | None:
    """AU 4-char codes are stored as 32-bit big-endian ints. Decode → 'TDM!' etc."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        try:
            return struct.pack(">I", value).decode("ascii", errors="ignore").strip()
        except (ValueError, struct.error):
            return str(value)
    return str(value)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

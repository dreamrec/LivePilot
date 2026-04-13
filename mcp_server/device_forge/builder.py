"""Build .amxd binary files from DeviceSpec — pure Python, no dependencies.

Binary format (reverse-engineered from LivePilot_Analyzer.amxd):
  Offset 0x00: "ampf" + uint32_LE(4) + device_marker (4 bytes)
  Offset 0x0C: "meta" + uint32_LE(4) + uint32_LE(meta_value)
  Offset 0x18: "ptch" + uint32_LE(content_size)
  Offset 0x20: "mx@c" + uint32_BE(16) + uint32_BE(0) + uint32_BE(json_size)
  Offset 0x30: JSON patcher (UTF-8)
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .models import DeviceSpec, DeviceType, GenExprParam

ABLETON_USER_LIBRARY = Path.home() / "Music" / "Ableton" / "User Library"

_SUBDIR_MAP = {
    DeviceType.AUDIO_EFFECT: "Presets/Audio Effects/Max Audio Effect",
    DeviceType.MIDI_EFFECT: "Presets/MIDI Effects/Max MIDI Effect",
    DeviceType.INSTRUMENT: "Presets/Instruments/Max Instrument",
    DeviceType.MIDI_GENERATOR: "Presets/MIDI Effects/Max MIDI Effect",
    DeviceType.MIDI_TRANSFORMATION: "Presets/MIDI Effects/Max MIDI Effect",
}


# ── JSON Patcher Generation ─────────────────────────────────────────


def _make_box(obj_id: str, maxclass: str, text: str,
              numinlets: int, numoutlets: int,
              outlettype: list[str], rect: list[float],
              **extra) -> dict:
    """Create a single Max box dict."""
    box: dict = {
        "id": obj_id,
        "maxclass": maxclass,
        "text": text,
        "numinlets": numinlets,
        "numoutlets": numoutlets,
        "outlettype": outlettype,
        "patching_rect": rect,
    }
    box.update(extra)
    return {"box": box}


def _make_line(src_id: str, src_outlet: int,
               dst_id: str, dst_inlet: int) -> dict:
    return {"patchline": {"source": [src_id, src_outlet],
                          "destination": [dst_id, dst_inlet]}}


def _ensure_safety_clip(code: str) -> str:
    """Append safety clipping to gen~ code to prevent speaker damage."""
    safe = code.rstrip()
    if "clip(" in safe.lower():
        return safe

    # Find output assignments and wrap them
    lines = safe.split("\n")
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("out") and "=" in stripped:
            var = stripped.split("=")[0].strip()
            new_lines.append(line)
            new_lines.append(f"{var} = clip({var}, -1, 1);")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def _build_gen_patcher(spec: DeviceSpec) -> dict:
    """Build the gen~ sub-patcher with codebox containing user's GenExpr code."""
    safe_code = _ensure_safety_clip(spec.gen_code)

    boxes = []
    lines = []

    # Codebox — maxclass MUST be "codebox" (not "newobj" with text "codebox")
    # Canonical format verified against 18 factory codebox objects
    boxes.append({
        "box": {
            "id": "obj-codebox",
            "maxclass": "codebox",
            "numinlets": 1,
            "numoutlets": 1,
            "outlettype": [""],
            "patching_rect": [50.0, 100.0, 400.0, 200.0],
            "fontface": 0,
            "fontname": "<Monospaced>",
            "fontsize": 12.0,
            "code": safe_code,
        }
    })

    # in 1 (audio or data input)
    boxes.append(_make_box("obj-in1", "newobj", "in 1", 0, 1, [""], [50.0, 30.0, 30.0, 22.0]))
    lines.append(_make_line("obj-in1", 0, "obj-codebox", 0))

    # out 1
    boxes.append(_make_box("obj-out1", "newobj", "out 1", 1, 0, [], [50.0, 350.0, 35.0, 22.0]))
    lines.append(_make_line("obj-codebox", 0, "obj-out1", 0))

    # Param objects for each parameter
    for i, param in enumerate(spec.params):
        param_id = f"obj-param{i}"
        boxes.append(_make_box(
            param_id, "newobj",
            f"param {param.name} @default {param.default} @min {param.min_val} @max {param.max_val}",
            0, 1, [""], [200.0 + i * 120, 30.0, 150.0, 22.0],
        ))

    return {
        "fileversion": 1,
        "appversion": {"major": 9, "minor": 0, "revision": 5,
                       "architecture": "x64", "modernui": 1},
        "classnamespace": "dsp.gen",
        "rect": [100.0, 100.0, 600.0, 450.0],
        "boxes": boxes,
        "lines": lines,
    }


def _patcher_boilerplate(spec: DeviceSpec) -> dict:
    """Common patcher-level fields for all device types."""
    return {
        "fileversion": 1,
        "appversion": {"major": 9, "minor": 0, "revision": 5,
                       "architecture": "x64", "modernui": 1},
        "classnamespace": "box",
        "rect": [100.0, 100.0, 800.0, 600.0],
        "openinpresentation": 1,
        "default_fontsize": 12.0,
        "default_fontface": 0,
        "default_fontname": "Arial",
        "gridonopen": 1,
        "gridsize": [15.0, 15.0],
        "gridsnaponopen": 1,
        "objectsnaponopen": 1,
        "statusbarvisible": 2,
        "toolbarvisible": 1,
        "lefttoolbarpinned": 0,
        "toptoolbarpinned": 0,
        "righttoolbarpinned": 0,
        "bottomtoolbarpinned": 0,
        "toolbars_unpinned_last_save": 0,
        "tallnewobj": 0,
        "boxanimatetime": 200,
        "enablehscroll": 1,
        "enablevscroll": 1,
        "devicewidth": float(spec.width),
        "description": spec.description,
        "digest": spec.description,
        "tags": spec.tags,
        "style": "",
        "subpatcher_template": "",
        "assistshowspatchername": 0,
    }


def _build_audio_effect_patcher(spec: DeviceSpec) -> dict:
    """Build patcher for an audio effect: plugin~ -> gen~ -> plugout~."""
    boxes = []
    lines = []
    _counter = [0]

    def nid():
        _counter[0] += 1
        return f"obj-{_counter[0]}"

    # Background panel — background=1 sends it behind all other UI elements
    pid = nid()
    boxes.append({
        "box": {
            "id": pid, "maxclass": "panel", "numinlets": 1, "numoutlets": 0,
            "patching_rect": [0.0, 0.0, float(spec.width), float(spec.height)],
            "presentation": 1,
            "presentation_rect": [0.0, 0.0, float(spec.width), float(spec.height)],
            "bgcolor": [0.12, 0.12, 0.12, 1.0],
            "background": 1,
        }
    })

    # plugin~ — numinlets=2 so Live can feed audio into the device
    plugin_id = nid()
    boxes.append(_make_box(plugin_id, "newobj", "plugin~", 2, 2,
                           ["signal", "signal"], [50.0, 30.0, 65.0, 22.0]))

    # plugout~
    plugout_id = nid()
    boxes.append(_make_box(plugout_id, "newobj", "plugout~", 2, 2,
                           ["signal", "signal"], [50.0, 400.0, 70.0, 22.0]))

    # gen~ with embedded patcher
    gen_id = nid()
    boxes.append({
        "box": {
            "id": gen_id, "maxclass": "newobj", "text": "gen~",
            "numinlets": 1, "numoutlets": 1, "outlettype": ["signal"],
            "patching_rect": [50.0, 200.0, 300.0, 22.0],
            "patcher": _build_gen_patcher(spec),
        }
    })

    # Signal path: L channel through gen~, R channel direct passthrough
    # plugin~ L -> gen~ -> plugout~ L
    lines.append(_make_line(plugin_id, 0, gen_id, 0))
    lines.append(_make_line(gen_id, 0, plugout_id, 0))
    # plugin~ R -> plugout~ R (direct passthrough)
    lines.append(_make_line(plugin_id, 1, plugout_id, 1))

    # live.dial for each parameter
    for i, param in enumerate(spec.params):
        did = nid()
        x = 10.0 + i * 54.0
        boxes.append(param.to_live_dial_json(did, [x, 10.0, 44.0, 48.0]))

    # Title comment
    tid = nid()
    boxes.append({
        "box": {
            "id": tid, "maxclass": "comment", "text": spec.name,
            "numinlets": 1, "numoutlets": 0,
            "patching_rect": [50.0, 440.0, 200.0, 20.0],
            "presentation": 1,
            "presentation_rect": [10.0, float(spec.height - 20), 200.0, 18.0],
            "textcolor": [0.7, 0.7, 0.7, 1.0], "fontsize": 10.0,
        }
    })

    p = _patcher_boilerplate(spec)
    p["boxes"] = boxes
    p["lines"] = lines
    return {"patcher": p}


def _build_midi_effect_patcher(spec: DeviceSpec) -> dict:
    boxes = [
        _make_box("obj-1", "newobj", "midiin", 1, 1, ["int"], [50.0, 30.0, 50.0, 22.0]),
        _make_box("obj-2", "newobj", "midiout", 1, 0, [], [50.0, 300.0, 55.0, 22.0]),
    ]
    lines = [_make_line("obj-1", 0, "obj-2", 0)]
    p = _patcher_boilerplate(spec)
    p["boxes"] = boxes
    p["lines"] = lines
    return {"patcher": p}


def _build_instrument_patcher(spec: DeviceSpec) -> dict:
    boxes = [
        _make_box("obj-mi", "newobj", "midiin", 1, 1, ["int"], [50.0, 30.0, 50.0, 22.0]),
        _make_box("obj-mp", "newobj", "midiparse", 1, 8,
                   ["", "", "", "", "", "", "", ""], [50.0, 70.0, 100.0, 22.0]),
        _make_box("obj-mtof", "newobj", "mtof", 1, 1, [""], [50.0, 110.0, 40.0, 22.0]),
    ]

    gen_patcher = _build_gen_patcher(spec)
    boxes.append({
        "box": {
            "id": "obj-gen", "maxclass": "newobj", "text": "gen~",
            "numinlets": 1, "numoutlets": 1, "outlettype": ["signal"],
            "patching_rect": [50.0, 200.0, 300.0, 22.0],
            "patcher": gen_patcher,
        }
    })
    boxes.append(_make_box("obj-po", "newobj", "plugout~", 2, 2,
                           ["signal", "signal"], [50.0, 300.0, 70.0, 22.0]))

    lines = [
        _make_line("obj-mi", 0, "obj-mp", 0),
        _make_line("obj-mp", 0, "obj-mtof", 0),
        _make_line("obj-mtof", 0, "obj-gen", 0),
        _make_line("obj-gen", 0, "obj-po", 0),
        _make_line("obj-gen", 0, "obj-po", 1),
    ]

    p = _patcher_boilerplate(spec)
    p["boxes"] = boxes
    p["lines"] = lines
    return {"patcher": p}


_PATCHER_BUILDERS = {
    DeviceType.AUDIO_EFFECT: _build_audio_effect_patcher,
    DeviceType.MIDI_EFFECT: _build_midi_effect_patcher,
    DeviceType.INSTRUMENT: _build_instrument_patcher,
}


def build_patcher_json(spec: DeviceSpec) -> dict:
    """Build the complete .maxpat JSON patcher dict for a device spec."""
    return _PATCHER_BUILDERS[spec.device_type](spec)


def build_amxd_binary(spec: DeviceSpec) -> bytes:
    """Build the complete .amxd binary from a device spec.

    Unfrozen .amxd format (32-byte header + JSON):
      ampf(4) + uint32_LE(4) + device_marker(4)   = 12 bytes
      meta(4) + uint32_LE(4) + uint32_LE(0)        = 12 bytes
      ptch(4) + uint32_LE(json_size)                = 8 bytes
      JSON patcher (UTF-8)

    Note: The mx@c wrapper is only used for FROZEN devices with embedded
    dependencies. Unfrozen devices put JSON directly after the ptch header.
    """
    patcher = build_patcher_json(spec)
    json_bytes = json.dumps(patcher, indent="\t", separators=(",", " : "),
                            ensure_ascii=False).encode("utf-8")

    dt = spec.device_type

    # ampf header (12 bytes)
    header = b"ampf"
    header += struct.pack("<I", 4)
    header += dt.ampf_marker

    # meta chunk (12 bytes) — meta_value=0 for unfrozen devices
    header += b"meta"
    header += struct.pack("<I", 4)
    header += struct.pack("<I", 0)

    # ptch chunk (8 bytes) — size = JSON byte length
    header += b"ptch"
    header += struct.pack("<I", len(json_bytes))

    return header + json_bytes


def parse_amxd_header(data: bytes) -> dict:
    """Parse an .amxd binary header. Returns dict with metadata."""
    if len(data) < 32 or data[:4] != b"ampf":
        raise ValueError("Not a valid .amxd file")

    marker = data[8:12]
    type_map = {
        b"aaaa": "audio_effect", b"mmmm": "midi_effect", b"iiii": "instrument",
        b"nagg": "midi_generator", b"natt": "midi_transformation",
    }
    ptch_size = struct.unpack("<I", data[28:32])[0]

    # Detect frozen vs unfrozen: frozen has mx@c at offset 32
    frozen = data[32:36] == b"mx@c"
    json_offset = 48 if frozen else 32

    return {
        "device_type": type_map.get(marker, "unknown"),
        "meta_value": struct.unpack("<I", data[20:24])[0],
        "ptch_size": ptch_size,
        "json_offset": json_offset,
        "frozen": frozen,
    }


def build_device(spec: DeviceSpec, output_dir: str | Path | None = None) -> Path:
    """Build an .amxd file and write it to disk.

    If output_dir is None, writes to the Ableton User Library.
    Returns the path to the created file.
    """
    data = build_amxd_binary(spec)

    if output_dir is None:
        subdir = _SUBDIR_MAP[spec.device_type]
        output_dir = ABLETON_USER_LIBRARY / subdir

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / spec.safe_filename
    path.write_bytes(data)
    return path

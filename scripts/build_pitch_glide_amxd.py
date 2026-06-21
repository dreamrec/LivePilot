#!/usr/bin/env python3
"""Build and optionally install LivePilot Pitch Glide.

The builder repacks Ableton's bundled "Max MIDI Effect.amxd" template with a
small MPE-enabled MIDI patch that hosts ``livepilot_pitch_glide.js``. The .amxd
is intentionally not frozen; the JS is copied beside it in the User Library so
Max can resolve the relative ``js livepilot_pitch_glide.js`` object.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M4L_DIR = ROOT / "m4l_device"
DEVICE_NAME = "LivePilot_Pitch_Glide"
JS_NAME = "livepilot_pitch_glide.js"
DEFAULT_INSTALL_DIR = (
    Path.home()
    / "Music"
    / "Ableton"
    / "User Library"
    / "Presets"
    / "MIDI Effects"
    / "Max MIDI Effect"
)


def find_template(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    candidates = sorted(
        Path("/Applications").glob(
            "Ableton Live 12*.app/Contents/App-Resources/Misc/Max Devices/Max MIDI Effect.amxd"
        )
    )
    if not candidates:
        raise FileNotFoundError(
            "Could not find Ableton's Max MIDI Effect.amxd template under /Applications"
        )
    return candidates[0]


def extract_json(payload: bytes) -> dict:
    start = payload.find(b"{")
    if start < 0:
        raise ValueError("ptch payload does not contain JSON")
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(payload)):
        byte = payload[idx]
        if in_string:
            if escape:
                escape = False
            elif byte == 92:  # backslash
                escape = True
            elif byte == 34:  # quote
                in_string = False
            continue
        if byte == 34:
            in_string = True
        elif byte == 123:  # {
            depth += 1
        elif byte == 125:  # }
            depth -= 1
            if depth == 0:
                return json.loads(payload[start : idx + 1].decode("utf-8"))
    raise ValueError("ptch payload JSON did not terminate")


def parse_amxd(path: Path) -> tuple[bytes, int, int, dict]:
    data = path.read_bytes()
    ptch_idx = data.find(b"ptch")
    if ptch_idx < 0:
        raise ValueError(f"no ptch chunk in {path}")
    ptch_len = struct.unpack("<I", data[ptch_idx + 4 : ptch_idx + 8])[0]
    payload = data[ptch_idx + 8 : ptch_idx + 8 + ptch_len]
    return data, ptch_idx, ptch_len, extract_json(payload)


def write_amxd(path: Path, original_data: bytes, ptch_idx: int, old_len: int, patcher: dict) -> None:
    encoded = json.dumps(patcher, indent="\t", separators=(",", " : "), ensure_ascii=False).encode()
    chunk = b"ptch" + struct.pack("<I", len(encoded)) + encoded
    output = original_data[:ptch_idx] + chunk + original_data[ptch_idx + 8 + old_len :]
    path.write_bytes(output)


def param_attrs(
    longname: str,
    shortname: str,
    initial: float,
    minimum: float,
    maximum: float,
    unitstyle: int = 0,
    ptype: int = 0,
) -> dict:
    return {
        "valueof": {
            "parameter_initial": [initial],
            "parameter_initial_enable": 1,
            "parameter_linknames": 0,
            "parameter_longname": longname,
            "parameter_shortname": shortname,
            "parameter_mmin": minimum,
            "parameter_mmax": maximum,
            "parameter_modmin": minimum,
            "parameter_modmax": maximum,
            "parameter_type": ptype,
            "parameter_unitstyle": unitstyle,
        }
    }


def comment_box(box_id: str, text: str, x: float, y: float, w: float, h: float = 20.0) -> dict:
    return {
        "box": {
            "id": box_id,
            "maxclass": "comment",
            "text": text,
            "numinlets": 1,
            "numoutlets": 0,
            "fontsize": 10.0,
            "patching_rect": [x, y, w, h],
            "presentation": 1,
            "presentation_rect": [x - 20.0, y - 20.0, w, h],
        }
    }


def newobj(box_id: str, text: str, x: float, y: float, inlets: int = 1, outlets: int = 1) -> dict:
    return {
        "box": {
            "id": box_id,
            "maxclass": "newobj",
            "text": text,
            "numinlets": inlets,
            "numoutlets": outlets,
            "patching_rect": [x, y, max(60.0, len(text) * 7.0), 22.0],
        }
    }


def loadmess(box_id: str, value: float, x: float, y: float) -> dict:
    return newobj(box_id, f"loadmess {value:g}", x, y, 1, 1)


def live_numbox(box_id: str, name: str, x: float, y: float, initial: float, minimum: float, maximum: float) -> dict:
    return {
        "box": {
            "id": box_id,
            "maxclass": "live.numbox",
            "numinlets": 1,
            "numoutlets": 2,
            "outlettype": ["", "float"],
            "parameter_enable": 1,
            "patching_rect": [x, y, 58.0, 20.0],
            "presentation": 1,
            "presentation_rect": [x - 20.0, y - 20.0, 58.0, 20.0],
            "saved_attribute_attributes": param_attrs(name, name, initial, minimum, maximum),
            "varname": name.replace(" ", "_"),
        }
    }


def live_toggle(box_id: str, x: float, y: float) -> dict:
    return {
        "box": {
            "id": box_id,
            "maxclass": "live.toggle",
            "numinlets": 1,
            "numoutlets": 1,
            "outlettype": [""],
            "parameter_enable": 1,
            "patching_rect": [x, y, 20.0, 20.0],
            "presentation": 1,
            "presentation_rect": [x - 20.0, y - 20.0, 20.0, 20.0],
            "saved_attribute_attributes": param_attrs("Enabled", "Enabled", 1, 0, 1, ptype=2),
            "varname": "Enabled",
        }
    }


def prepend(box_id: str, name: str, x: float, y: float) -> dict:
    return newobj(box_id, f"prepend {name}", x, y, 1, 1)


def line(src: str, dst: str, src_outlet: int = 0, dst_inlet: int = 0) -> dict:
    return {"patchline": {"source": [src, src_outlet], "destination": [dst, dst_inlet]}}


def build_patcher(template_patcher: dict) -> dict:
    patcher = dict(template_patcher)
    patcher["rect"] = [100.0, 100.0, 740.0, 520.0]
    patcher["openinpresentation"] = 1
    patcher["devicewidth"] = 430.0
    patcher["description"] = (
        "LivePilot Pitch Glide — monophonic MIDI pitch-bend glide for sparse lead lines."
    )
    patcher["digest"] = "LivePilot Pitch Glide"
    patcher["tags"] = "livepilot pitch glide mpe midi effect"
    patcher["is_mpe"] = 1
    if "project" in patcher:
        patcher["project"] = dict(patcher["project"])
        patcher["project"]["readonly"] = 0

    controls = [
        ("Glide ms", "glide_ms", 140, 1, 2000, 40, 164),
        ("Bend Range", "bend_range", 2, 0.25, 96, 132, 164),
        ("Curve", "curve", 0.25, -1, 1, 224, 164),
        ("Max Int", "max_interval", 2, 0.25, 48, 316, 164),
        ("Window ms", "trigger_window_ms", 700, 1, 5000, 408, 164),
    ]

    boxes = [
        {
            "box": {
                "id": "obj-panel",
                "maxclass": "panel",
                "numinlets": 1,
                "numoutlets": 0,
                "patching_rect": [20.0, 20.0, 690.0, 460.0],
                "presentation": 1,
                "presentation_rect": [0.0, 0.0, 430.0, 172.0],
                "bgcolor": [0.11, 0.11, 0.12, 1.0],
                "bordercolor": [0.28, 0.28, 0.3, 1.0],
                "rounded": 4,
            }
        },
        comment_box("obj-title", "LivePilot Pitch Glide", 40, 42, 220, 22),
        comment_box(
            "obj-subtitle",
            "Monophonic note-to-note pitch bend. Match Bend Range to the instrument.",
            40,
            68,
            430,
            20,
        ),
        comment_box("obj-enabled-label", "On", 40, 116, 34, 20),
        live_toggle("obj-enabled", 74, 116),
        loadmess("obj-enabled-load", 1, 74, 84),
        prepend("obj-enabled-pre", "enabled", 74, 146),
        newobj("obj-midiin", "midiin", 40, 260, 0, 1),
        newobj("obj-js", f"js {JS_NAME}", 150, 260, 2, 1),
        newobj("obj-midiout", "midiout", 330, 260, 1, 0),
    ]

    x_label = {
        "Glide ms": 40,
        "Bend Range": 132,
        "Curve": 224,
        "Max Int": 316,
        "Window ms": 408,
    }
    lines = [
        line("obj-enabled-load", "obj-enabled"),
        line("obj-enabled", "obj-enabled-pre"),
        line("obj-enabled-pre", "obj-js", 0, 1),
        line("obj-midiin", "obj-js", 0, 0),
        line("obj-js", "obj-midiout", 0, 0),
    ]

    for label, param, initial, minimum, maximum, x, y in controls:
        clean = param.replace("_", "-")
        label_id = f"obj-{clean}-label"
        load_id = f"obj-{clean}-load"
        number_id = f"obj-{clean}"
        prepend_id = f"obj-{clean}-pre"
        boxes.append(comment_box(label_id, label, x_label[label], 116, 80, 20))
        boxes.append(loadmess(load_id, initial, x, 132))
        boxes.append(live_numbox(number_id, label, x, y, initial, minimum, maximum))
        boxes.append(prepend(prepend_id, param, x, y + 32))
        lines.append(line(load_id, number_id))
        lines.append(line(number_id, prepend_id))
        lines.append(line(prepend_id, "obj-js", 0, 1))

    patcher["boxes"] = boxes
    patcher["lines"] = lines
    return {"patcher": patcher}


def build(template: Path, out_amxd: Path, out_maxpat: Path) -> None:
    original, ptch_idx, old_len, parsed = parse_amxd(template)
    generated = build_patcher(parsed["patcher"])
    out_maxpat.write_text(json.dumps(generated, indent=2) + "\n")
    write_amxd(out_amxd, original, ptch_idx, old_len, generated)


def install(out_amxd: Path, install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_amxd, install_dir / out_amxd.name)
    shutil.copy2(M4L_DIR / JS_NAME, install_dir / JS_NAME)
    return install_dir / out_amxd.name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", default=None)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    args = parser.parse_args()

    template = find_template(args.template)
    out_amxd = M4L_DIR / f"{DEVICE_NAME}.amxd"
    out_maxpat = M4L_DIR / f"{DEVICE_NAME}.maxpat"
    build(template, out_amxd, out_maxpat)
    print(f"built {out_amxd}")
    print(f"wrote {out_maxpat}")
    if args.install:
        installed = install(out_amxd, Path(args.install_dir).expanduser())
        print(f"installed {installed}")
        print(f"installed {Path(args.install_dir).expanduser() / JS_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

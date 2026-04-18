"""Build LivePilot MIDI Tool .amxd files correctly.

Key findings:
- ampf/ptch chunk uses BIG-endian length field (IFF-style format)
- Device type lives in project.amxdtype (4-byte ASCII code):
    - 'nagg' (0x6E616767 = 1851877223) = Generator
    - 'natt' (0x6E617474 = 1851880564) = Transformation
- Live's MIDI Tool indexer keys off this field.

Strategy: take the factory template, preserve all project metadata
(especially amxdtype), replace boxes+lines with our bridge wiring,
repack with BE length field, install to ~/Music/Ableton/User Library/MIDI Tools/.
"""
import struct
import json
import shutil
import os


TEMPLATE_DIR = "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Misc/Max MIDI Tools"
PROJECT_M4L = "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot/m4l_device"
USER_LIB_GEN = os.path.expanduser("~/Music/Ableton/User Library/MIDI Tools/Max Generators")
USER_LIB_TRANS = os.path.expanduser("~/Music/Ableton/User Library/MIDI Tools/Max Transformations")

# The [js] object is referenced by ABSOLUTE PATH in the .amxd so Max can
# always find it regardless of its file-search behavior. We install the JS
# to a canonical location that's guaranteed to persist and stay writable.
_ABSOLUTE_JS_PATH = os.path.expanduser(
    "~/Music/Ableton/User Library/MIDI Tools/Max Generators/miditool_bridge.js"
)


def parse_amxd(path: str):
    """Parse a Max for Live .amxd.

    The ampf/ptch container is IFF-like but has TWO counter-intuitive quirks:
      - Chunk length field is LITTLE-endian (not BE as most IFF formats use)
      - Length field counts PAYLOAD BYTES ONLY, NOT including the 8-byte
        'ptch' + length header.

    So for the factory Generator template:
      file size = 3185 bytes
      ampf chunk: 8 header + 4 payload ('nagg')           = 12 bytes
      meta chunk: 8 header + 4 payload ('\\0\\0\\0\\0')    = 12 bytes
      ptch chunk: 8 header + 3153 payload (JSON)          = 3161 bytes
      Total: 12 + 12 + 3161 = 3185 ✓

    Writing ptch_len as BE makes Max read it as a little-endian number
    (e.g. BE 9550 = bytes 0x00002554 → LE 0x54250000 ≈ 1.4GB), triggering
    Max's "The device file exceeds the maximum size of one gigabyte" error.

    Returns (file_bytes, ptch_idx, ptch_len_payload_size, parsed_patcher_json).
    """
    data = open(path, "rb").read()
    ptch_idx = data.find(b"ptch")
    if ptch_idx < 0:
        raise ValueError("no ptch chunk in " + path)
    ptch_len = struct.unpack("<I", data[ptch_idx + 4:ptch_idx + 8])[0]  # LE, payload-only
    chunk_payload = data[ptch_idx + 8:ptch_idx + 8 + ptch_len]
    json_start = chunk_payload.find(b"{")
    s = chunk_payload[json_start:].decode("utf-8", errors="replace").rstrip("\x00\ufffd")
    parsed = json.loads(s)
    return data, ptch_idx, ptch_len, parsed


def write_amxd(path: str, original_data: bytes, ptch_idx: int, old_ptch_len: int, new_parsed: dict):
    """Write .amxd with a new patcher JSON. Preserves ampf header + trailing chunks.

    Critical: ptch_len field is little-endian and counts PAYLOAD BYTES ONLY
    (not the 8-byte 'ptch' + length header). Otherwise Max computes a huge
    size and rejects the file with 'exceeds maximum size of one gigabyte'.
    """
    new_json = json.dumps(new_parsed, indent="\t", separators=(",", " : "), ensure_ascii=False)
    new_json_bytes = new_json.encode("utf-8")

    new_payload = new_json_bytes
    new_ptch_len = len(new_payload)  # payload-only (no +8 for header)

    # Pack with LITTLE-endian length
    new_chunk = b"ptch" + struct.pack("<I", new_ptch_len) + new_payload

    prefix = original_data[:ptch_idx]
    # Old ptch chunk span: 8-byte header + old_ptch_len bytes of payload
    suffix = original_data[ptch_idx + 8 + old_ptch_len:]

    new_data = prefix + new_chunk + suffix
    with open(path, "wb") as f:
        f.write(new_data)
    return new_data


def bridge_objects(variant: str):
    """Return (boxes, lines) for our MIDI Tool bridge wiring.

    The template's existing live.miditool.in and live.miditool.out are kept
    by preserving their IDs (obj-2, obj-1). All other template objects (the
    decorative live.line, hidden comment, "Build your Generator here" comment)
    are REMOVED — our bridge objects replace them.
    """
    if variant == "generate":
        title_text = "LivePilot MIDI Tool (Generate)"
        subtitle_text = "Generates new notes via LivePilot server"
        hint_text = "Target: 'euclidean_rhythm'\nset via: set_miditool_target(tool_name, params)"
    else:
        title_text = "LivePilot MIDI Tool (Transform)"
        subtitle_text = "Transforms selected clip notes via LivePilot server"
        hint_text = "Target: 'humanize'  |  'tintinnabuli'\nset via: set_miditool_target(tool_name, params)"

    boxes = [
        # Presentation panel (background)
        {"box": {
            "id": "obj-panel", "maxclass": "panel",
            "numinlets": 1, "numoutlets": 0,
            "patching_rect": [20.0, 20.0, 680.0, 520.0],
            "presentation": 1,
            "presentation_rect": [0.0, 0.0, 350.0, 168.0],
            "bgcolor": [0.12, 0.12, 0.14, 1.0],
            "bordercolor": [0.22, 0.22, 0.25, 1.0],
            "border": 1, "rounded": 4,
        }},
        # Title
        {"box": {
            "id": "obj-title", "maxclass": "comment",
            "text": title_text,
            "numinlets": 1, "numoutlets": 0,
            "fontsize": 15.0, "fontface": 1,
            "textcolor": [0.88, 0.9, 0.94, 1.0],
            "patching_rect": [40.0, 40.0, 260.0, 24.0],
            "presentation": 1,
            "presentation_rect": [12.0, 10.0, 326.0, 22.0],
        }},
        # Subtitle
        {"box": {
            "id": "obj-subtitle", "maxclass": "comment",
            "text": subtitle_text,
            "numinlets": 1, "numoutlets": 0,
            "fontsize": 10.0,
            "textcolor": [0.55, 0.58, 0.64, 1.0],
            "patching_rect": [40.0, 66.0, 320.0, 20.0],
            "presentation": 1,
            "presentation_rect": [12.0, 34.0, 326.0, 18.0],
        }},
        # Status label
        {"box": {
            "id": "obj-status-label", "maxclass": "comment",
            "text": "Status:",
            "numinlets": 1, "numoutlets": 0,
            "fontsize": 10.0, "fontface": 1,
            "textcolor": [0.55, 0.58, 0.64, 1.0],
            "patching_rect": [40.0, 92.0, 60.0, 20.0],
            "presentation": 1,
            "presentation_rect": [12.0, 66.0, 46.0, 18.0],
        }},
        # Status value
        {"box": {
            "id": "obj-status", "maxclass": "comment",
            "text": "Initialising",
            "numinlets": 1, "numoutlets": 0,
            "fontsize": 10.0,
            "textcolor": [0.45, 0.78, 0.5, 1.0],
            "patching_rect": [100.0, 92.0, 260.0, 20.0],
            "presentation": 1,
            "presentation_rect": [60.0, 66.0, 278.0, 18.0],
            "varname": "status_display",
        }},
        # Hint
        {"box": {
            "id": "obj-hint", "maxclass": "comment",
            "text": hint_text,
            "numinlets": 1, "numoutlets": 0,
            "fontsize": 9.0,
            "textcolor": [0.5, 0.52, 0.56, 1.0],
            "patching_rect": [40.0, 114.0, 326.0, 34.0],
            "presentation": 1,
            "presentation_rect": [12.0, 100.0, 326.0, 34.0],
            "linecount": 2,
        }},
        # midiin / midiout (MIDI pass-through — required by M4L wrapper)
        {"box": {
            "id": "obj-midiin", "maxclass": "newobj",
            "text": "midiin",
            "numinlets": 0, "numoutlets": 1,
            "outlettype": ["int"],
            "patching_rect": [40.0, 160.0, 50.0, 22.0],
        }},
        {"box": {
            "id": "obj-midiout", "maxclass": "newobj",
            "text": "midiout",
            "numinlets": 1, "numoutlets": 0,
            "patching_rect": [40.0, 200.0, 55.0, 22.0],
        }},
        # live.thisdevice for init handshake
        {"box": {
            "id": "obj-thisdevice", "maxclass": "newobj",
            "text": "live.thisdevice",
            "numinlets": 1, "numoutlets": 3,
            "outlettype": ["bang", "bang", ""],
            "patching_rect": [520.0, 160.0, 110.0, 22.0],
        }},
        # live.miditool.in — KEEP TEMPLATE'S ID (obj-2)
        # IMPORTANT: this is what the template uses. By keeping the same ID
        # and maxclass, Max won't treat it as a new object — it matches the
        # template's existing miditool.in.
        {"box": {
            "id": "obj-2", "maxclass": "newobj",
            "text": "live.miditool.in",
            "numinlets": 1, "numoutlets": 2,
            "outlettype": ["", ""],
            "patching_rect": [140.0, 240.0, 115.0, 22.0],
        }},
        # UDP receive (from server)
        {"box": {
            "id": "obj-udpreceive", "maxclass": "newobj",
            "text": "udpreceive 9881",
            "numinlets": 0, "numoutlets": 1,
            "outlettype": [""],
            "patching_rect": [360.0, 240.0, 120.0, 22.0],
        }},
        # JS bridge
        # NOTE: use the ABSOLUTE PATH here. When Live instantiates a MIDI
        # Tool from the Generators dropdown, Max's [js] file-search doesn't
        # reliably find files in the Ableton User Library subfolders even
        # when they sit alongside the .amxd. An absolute path bypasses the
        # search. Trade-off: the .amxd is tied to this install location;
        # for redistribution, Max's File Preferences would need the JS
        # folder added to its search path instead.
        {"box": {
            "id": "obj-js", "maxclass": "newobj",
            "text": "js \"" + _ABSOLUTE_JS_PATH + "\"",
            "numinlets": 3, "numoutlets": 2,
            "outlettype": ["", ""],
            "patching_rect": [140.0, 320.0, 180.0, 22.0],
            "fontsize": 11.0,
            "bgcolor": [0.18, 0.22, 0.28, 1.0],
            "textcolor": [0.85, 0.87, 0.9, 1.0],
        }},
        # Status routing (/miditool/status -> prepend set -> status comment)
        {"box": {
            "id": "obj-status-route", "maxclass": "newobj",
            "text": "route /miditool/status",
            "numinlets": 1, "numoutlets": 2,
            "outlettype": ["", ""],
            "patching_rect": [420.0, 340.0, 160.0, 22.0],
        }},
        {"box": {
            "id": "obj-status-prepend", "maxclass": "newobj",
            "text": "prepend set",
            "numinlets": 2, "numoutlets": 1,
            "outlettype": [""],
            "patching_rect": [420.0, 380.0, 85.0, 22.0],
        }},
        # UDP send (to server)
        {"box": {
            "id": "obj-udpsend", "maxclass": "newobj",
            "text": "udpsend 127.0.0.1 9880",
            "numinlets": 1, "numoutlets": 0,
            "patching_rect": [40.0, 400.0, 170.0, 22.0],
        }},
        # live.miditool.out — KEEP TEMPLATE'S ID (obj-1)
        {"box": {
            "id": "obj-1", "maxclass": "newobj",
            "text": "live.miditool.out",
            "numinlets": 1, "numoutlets": 0,
            "patching_rect": [230.0, 440.0, 120.0, 22.0],
        }},
    ]

    lines = [
        {"patchline": {"source": ["obj-midiin", 0],        "destination": ["obj-midiout", 0]}},
        {"patchline": {"source": ["obj-thisdevice", 2],    "destination": ["obj-js", 0]}},
        {"patchline": {"source": ["obj-2", 0],             "destination": ["obj-js", 2]}},  # notes
        {"patchline": {"source": ["obj-2", 1],             "destination": ["obj-js", 1]}},  # context
        {"patchline": {"source": ["obj-udpreceive", 0],    "destination": ["obj-js", 0]}},
        {"patchline": {"source": ["obj-udpreceive", 0],    "destination": ["obj-status-route", 0]}},
        {"patchline": {"source": ["obj-status-route", 0],  "destination": ["obj-status-prepend", 1]}},
        {"patchline": {"source": ["obj-status-prepend", 0],"destination": ["obj-status", 0]}},
        {"patchline": {"source": ["obj-js", 0],            "destination": ["obj-udpsend", 0]}},
        {"patchline": {"source": ["obj-js", 1],            "destination": ["obj-1", 0]}},  # to miditool.out
    ]
    return boxes, lines


def build(template_path: str, output_path: str, variant: str):
    print(f"\n=== Building {variant} ===")
    print(f"  Template: {template_path}")
    data, ptch_idx, ptch_len, parsed = parse_amxd(template_path)
    patcher = parsed["patcher"]

    # Confirm device-type marker from template
    amxdtype = patcher.get("project", {}).get("amxdtype")
    print(f"  Template project.amxdtype: {amxdtype} = {amxdtype.to_bytes(4,'big') if amxdtype else '?'!r}")

    # Customize patcher-level UI
    patcher["openinpresentation"] = 1
    patcher["devicewidth"] = 350.0
    patcher["rect"] = [100.0, 100.0, 720.0, 560.0]

    if variant == "generate":
        patcher["description"] = ("LivePilot MIDI Tool (Generator) — bridges a clip's context to the "
                                  "LivePilot MCP server, which synthesises notes via a configured "
                                  "generator (euclidean_rhythm, ...). Call set_miditool_target before firing.")
        patcher["digest"] = "LivePilot Generator — server-side MIDI synthesis"
        patcher["tags"] = "livepilot miditool bridge generator"
    else:
        patcher["description"] = ("LivePilot MIDI Tool (Transformation) — bridges selected notes + "
                                  "clip context to the LivePilot MCP server, which rewrites them "
                                  "via a configured transformer (humanize, tintinnabuli). "
                                  "Call set_miditool_target before firing.")
        patcher["digest"] = "LivePilot Transformer — server-side MIDI rewriting"
        patcher["tags"] = "livepilot miditool bridge transformation"

    # Replace boxes and lines
    boxes, lines = bridge_objects(variant)
    patcher["boxes"] = boxes
    patcher["lines"] = lines

    # Reflect JS bridge dependency (best effort — Max will warn if the js
    # file isn't found adjacent to the .amxd)
    if "dependency_cache" in patcher:
        # Don't touch dependency_cache — it's keyed on the template's original
        # deps. Max will re-populate on next Freeze.
        pass

    write_amxd(output_path, data, ptch_idx, ptch_len, parsed)
    print(f"  Wrote {os.path.getsize(output_path)} bytes")


# ─── Run ────────────────────────────────────────────────────────────────────

os.makedirs(USER_LIB_GEN, exist_ok=True)
os.makedirs(USER_LIB_TRANS, exist_ok=True)

# Build in project
build(f"{TEMPLATE_DIR}/Max MIDI Generator.amxd",
      f"{PROJECT_M4L}/LivePilot_MIDITool_Generate.amxd",
      "generate")
build(f"{TEMPLATE_DIR}/Max MIDI Transformation.amxd",
      f"{PROJECT_M4L}/LivePilot_MIDITool_Transform.amxd",
      "transform")

# Install to User Library (correct paths)
shutil.copy2(f"{PROJECT_M4L}/LivePilot_MIDITool_Generate.amxd",
             f"{USER_LIB_GEN}/LivePilot_MIDITool_Generate.amxd")
shutil.copy2(f"{PROJECT_M4L}/LivePilot_MIDITool_Transform.amxd",
             f"{USER_LIB_TRANS}/LivePilot_MIDITool_Transform.amxd")

# Also copy the JS bridge alongside each (Max needs it in the same folder)
bridge_js = f"{PROJECT_M4L}/miditool_bridge.js"
shutil.copy2(bridge_js, f"{USER_LIB_GEN}/miditool_bridge.js")
shutil.copy2(bridge_js, f"{USER_LIB_TRANS}/miditool_bridge.js")

# Remove the broken ones from the wrong location
wrong_dir = os.path.expanduser("~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect")
for fn in ("LivePilot_MIDITool_Generate.amxd", "LivePilot_MIDITool_Transform.amxd"):
    wrong = f"{wrong_dir}/{fn}"
    if os.path.exists(wrong):
        os.remove(wrong)
        print(f"\n  Removed stale file: {wrong}")

print(f"\n✓ Installed to User Library:")
print(f"  {USER_LIB_GEN}/LivePilot_MIDITool_Generate.amxd")
print(f"  {USER_LIB_TRANS}/LivePilot_MIDITool_Transform.amxd")

# Final verify — parse each back and confirm amxdtype
print(f"\n=== Verification ===")
for variant, path in [
    ("Generator",      f"{USER_LIB_GEN}/LivePilot_MIDITool_Generate.amxd"),
    ("Transformation", f"{USER_LIB_TRANS}/LivePilot_MIDITool_Transform.amxd"),
]:
    _, _, _, parsed = parse_amxd(path)
    amxdtype = parsed["patcher"]["project"]["amxdtype"]
    marker = amxdtype.to_bytes(4, "big")
    expected = b"nagg" if variant == "Generator" else b"natt"
    status = "✓" if marker == expected else "✗"
    print(f"  {status} {variant}: amxdtype={amxdtype} = {marker!r} (expected {expected!r})")
    print(f"      boxes: {len(parsed['patcher']['boxes'])}, lines: {len(parsed['patcher']['lines'])}")
    print(f"      openinpresentation: {parsed['patcher']['openinpresentation']}, devicewidth: {parsed['patcher']['devicewidth']}")

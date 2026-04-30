#!/usr/bin/env python3
"""
Deep .als parser for the LivePilot pack-atlas-mapping project.

Extracts production ground truth from Ableton Live .als files:
- BPM, time signature, scale/key (project-level)
- Track names, types (audio/midi/return/master), grouping
- Per-track device chain in topological order
- Per-device parameter values (where the device exposes them as <Manual Value=...>)
- Macro mappings (rack macros → target parameters)
- Sends matrix
- Scene names (session view) + arrangement clip layout
- Automation envelope presence per parameter

Usage: python als_deep_parse.py <path-to-als> [--json | --markdown]

Schema notes (BUG-C#2 fix, 2026-04-30):
  Each device dict may include a "chains" key (Option A — nested structure).
  Schema:
    chains: [
      {
        "name": str,          # branch name (EffectiveName or empty string)
        "devices": [<recursive device dicts>]
      },
      ...
    ]
  Recursion is capped at max_depth=4 to guard against pathological nesting.
  Only rack types (InstrumentGroupDevice, AudioEffectGroupDevice,
  MidiEffectGroupDevice, DrumGroupDevice) produce a "chains" field.
  Non-rack devices never carry "chains".

  BUG-PARSER#2 fix (2026-04-30):
  For .adg files, outer-rack macro display names that are generic ("Macro N") are
  resolved by scanning nested racks' MacroControls KeyMidi bindings.  Ableton uses
  Channel=16 in KeyMidi to encode which outer-rack macro index (NoteOrController)
  an inner macro is bound to.  When the outer slot still shows "Macro N", the inner
  rack's named display name is adopted.
"""
import sys
import re
import gzip
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import OrderedDict


def load_als(path):
    """Decompress and parse an .als file. Returns the root <Ableton> element."""
    with gzip.open(path, "rb") as f:
        tree = ET.parse(f)
    return tree.getroot()


def find_first_value(elem, tag):
    """Find the first child <tag Value="..."/> attribute, recursively."""
    for child in elem.iter(tag):
        v = child.attrib.get("Value")
        if v is not None:
            return v
    return None


def get_project_bpm(root):
    """Project tempo. Live stores it as <Tempo><Manual Value="..."/></Tempo>.
    The Manual Value is the BPM directly (e.g. "80" for 80 BPM)."""
    # First Tempo element with a direct Manual child = project tempo
    for tempo in root.iter("Tempo"):
        for child in tempo:
            if child.tag == "Manual":
                v = child.attrib.get("Value")
                if v is not None:
                    try:
                        return float(v)
                    except ValueError:
                        pass
    return None


def get_time_signature(root):
    """Time-signature is encoded as Numerator * 99 + (Denominator - 1) in EnumEvent.Value
    on MasterTrack's TimeSignature. Decode."""
    for master in root.iter("MasterTrack"):
        for ts in master.iter("TimeSignature"):
            for event in ts.iter("EnumEvent"):
                v = event.attrib.get("Value")
                if v is not None:
                    try:
                        ival = int(v)
                        # Live encodes as: code = numerator + (denominator_index << 16) approximately
                        # But common signatures use specific codes.
                        # 4/4 = 201, 3/4 = 200, 6/8 = 405, 7/8 = 406, 5/4 = 202.
                        sig_map = {201: "4/4", 200: "3/4", 202: "5/4", 198: "1/4",
                                   199: "2/4", 405: "6/8", 406: "7/8", 404: "5/8",
                                   814: "12/16", 813: "11/16", 812: "10/16"}
                        return sig_map.get(ival, f"raw:{ival}")
                    except ValueError:
                        pass
    return None


# Live 9/10 stored scale mode as an integer index rather than a string name.
# Verified against Live 12 docs and cross-checked against the corpus.
_LIVE_MODE_INDEX_TO_NAME = {
    0: "Major",
    1: "Minor",
    2: "Dorian",
    3: "Mixolydian",
    4: "Lydian",
    5: "Phrygian",
    6: "Locrian",
    7: "Whole Tone",
    8: "Half-Whole Diminished",
    9: "Whole-Half Diminished",
    10: "Minor Blues",
    11: "Minor Pentatonic",
    12: "Major Pentatonic",
    13: "Harmonic Minor",
    14: "Melodic Minor",
}


def get_scale(root):
    """Project scale lives in LiveSet > ScaleInformation (Live 11+).
    Older .als files (Live 9/10) use <Root Value=...> instead of <RootNote Value=...>.
    We must read from the direct child of LiveSet, NOT via root.iter() which would
    find clip-level ScaleInformation first (those always default to C Major).

    BUG-PARSER#3 fix (2026-04-30): Live 9/10 stored the mode as a numeric index.
    When scale_name is a digit string, look it up in _LIVE_MODE_INDEX_TO_NAME."""
    liveset = root.find("LiveSet")
    if liveset is not None:
        scale = liveset.find("ScaleInformation")
        if scale is not None:
            # Live 11+ format: <RootNote Value="5"/>, <Name Value="Minor"/>
            rn_elem = scale.find("RootNote")
            root_note = rn_elem.attrib.get("Value") if rn_elem is not None else None
            # Live 9/10 format: <Root Value="0"/>
            if root_note is None:
                r_elem = scale.find("Root")
                root_note = r_elem.attrib.get("Value") if r_elem is not None else None
            nm_elem = scale.find("Name")
            scale_name = nm_elem.attrib.get("Value") if nm_elem is not None else None
            # Decode numeric mode index (Live 9/10 format)
            if scale_name is not None and scale_name.isdigit():
                idx = int(scale_name)
                decoded = _LIVE_MODE_INDEX_TO_NAME.get(idx)
                if decoded is not None:
                    scale_name = decoded
                else:
                    warnings.warn(
                        f"Unknown Live mode index {idx} — keeping as-is",
                        stacklevel=2,
                    )
            if root_note is not None or scale_name is not None:
                return {"root_note": root_note, "name": scale_name}
    return None


# Filename key fallback (BUG-PARSER#4 fix, 2026-04-30):
# Some construction-kit packs (e.g. Mood Reel) encode the key in the filename
# but leave the .als project scale at the C Major default.  When the .als
# reports C Major AND the filename matches the pattern, we override from the filename.
_FILENAME_KEY_RE = re.compile(r'\b([a-g][#b]?)(maj|min)\b', re.IGNORECASE)

# Root-note letter → integer (semitones from C)
_NOTE_NAME_TO_INT = {
    "c": 0, "c#": 1, "db": 1,
    "d": 2, "d#": 3, "eb": 3,
    "e": 4,
    "f": 5, "f#": 6, "gb": 6,
    "g": 7, "g#": 8, "ab": 8,
    "a": 9, "a#": 10, "bb": 10,
    "b": 11,
}


def _apply_filename_key_fallback(scale: dict | None, stem: str) -> dict | None:
    """Override a C-Major default scale with the key encoded in the filename stem.

    Only triggers when:
      - scale is exactly {root_note: "0", name: "Major"} (the .als default)
      - the stem matches \\b([a-g][#b]?)(maj|min)\\b (case-insensitive)

    Returns a new dict with source="filename-fallback", or the original dict
    unchanged (source="als-extract") if the fallback doesn't apply.
    """
    if scale is None:
        return scale
    # Stamp the source on a copy (always, so callers know the provenance)
    enriched = dict(scale)
    m = _FILENAME_KEY_RE.search(stem)
    is_c_major_default = (
        str(scale.get("root_note", "")) == "0"
        and scale.get("name") == "Major"
    )
    if is_c_major_default and m:
        letter = m.group(1).lower()
        mode_str = m.group(2).lower()
        root_int = _NOTE_NAME_TO_INT.get(letter)
        if root_int is not None:
            enriched["root_note"] = str(root_int)
            enriched["name"] = "Major" if mode_str == "maj" else "Minor"
            enriched["source"] = "filename-fallback"
            return enriched
    enriched["source"] = "als-extract"
    return enriched


def get_track_name(track_elem):
    """Track display name from EffectiveName."""
    name = find_first_value(track_elem, "EffectiveName")
    if not name:
        name = find_first_value(track_elem, "UserName")
    return name or "(unnamed)"


# Device classes Live can have on a track. The element TAG IS the device class.
KNOWN_DEVICE_CLASSES = {
    # instruments
    "Operator", "Wavetable", "Drift", "AnalogDevice", "Sampler", "Simpler",
    "Tension", "Collision", "Electric", "ImpulseDevice", "DrumGroupDevice",
    "InstrumentGroupDevice", "InstrumentImpulse", "InstrumentVector",
    "MultiSampler", "OriginalSimpler",
    # m4l devices (generic)
    "MaxAudioEffect", "MaxInstrument", "MaxMidiEffect",
    "PluginDevice",
    # audio effects
    "Compressor2", "GlueCompressor", "MultibandDynamics", "Saturator",
    "Erosion", "Vinyl", "Redux", "AutoFilter", "AutoPan",
    "Eq8", "EqEight", "Eq3", "EQ3", "Cabinet", "AmpDevice", "OverdriveDevice",
    "Reverb", "HybridReverb", "Echo", "Delay", "FilterDelay", "PingPongDelay",
    "GrainDelay", "Phaser", "Flanger", "Chorus", "Tremolo", "Tuner",
    "FrequencyShifter", "Resonators", "SpectralResonator", "SpectralBlur",
    "SpectralTime", "Vocoder", "Beat", "BeatRepeat", "Looper", "Limiter",
    "Gate", "Utility", "DrumBus", "Pedal", "Shifter", "Tape",
    # midi effects
    "MidiArpeggiator", "MidiNoteLength", "MidiPitcher", "MidiRandom",
    "MidiScale", "MidiVelocity", "MidiChord",
    # racks
    "AudioEffectGroupDevice", "MidiEffectGroupDevice",
}


def is_device_element(elem):
    """Heuristic: an element is a device if its tag is a known class."""
    return elem.tag in KNOWN_DEVICE_CLASSES


_MAX_CHAIN_DEPTH = 4  # guard against pathological nesting


def _extract_rack_chains(rack_elem, depth):
    """Walk a rack device's Branches and return a list of chain dicts.

    Each chain dict: {"name": str, "devices": [<recursive device summaries>]}.
    Path per branch:
        branch_elem → DeviceChain → *DeviceChain (Midi/Audio-to-Midi/Audio) → Devices
    We iterate over children of the inner DeviceChain looking for a tag
    containing "DeviceChain" (MidiToAudioDeviceChain, AudioToAudioDeviceChain,
    MidiToMidiDeviceChain, etc.) and take the first one found.
    """
    chains = []
    branches_elem = rack_elem.find("Branches")
    if branches_elem is None:
        return chains
    for branch in branches_elem:
        # Branch name from Name/EffectiveName
        branch_name = ""
        name_elem = branch.find("Name")
        if name_elem is not None:
            en = name_elem.find("EffectiveName")
            if en is not None:
                branch_name = en.attrib.get("Value", "")
            if not branch_name:
                un = name_elem.find("UserName")
                if un is not None:
                    branch_name = un.attrib.get("Value", "")

        devices_in_branch = []
        branch_dc = branch.find("DeviceChain")
        if branch_dc is not None:
            # Find the inner *DeviceChain wrapper (varies by rack type)
            inner_dc = None
            for child in branch_dc:
                if "DeviceChain" in child.tag:
                    inner_dc = child
                    break
            if inner_dc is not None:
                devices_cont = inner_dc.find("Devices")
                if devices_cont is not None:
                    for dev_elem in devices_cont:
                        if is_device_element(dev_elem):
                            devices_in_branch.append(
                                extract_device_summary(dev_elem, _chain_depth=depth)
                            )

        chains.append({"name": branch_name, "devices": devices_in_branch})
    return chains


def extract_device_summary(device_elem, _chain_depth=0):
    """Extract a summary of a single device."""
    name = device_elem.tag
    # Try to find a UserName for renamed devices
    user_name = None
    for child in device_elem:
        if child.tag == "UserName":
            user_name = child.attrib.get("Value", "")
            break
    # Class display name
    display = name
    # Loaded preset name (some devices store this)
    preset_ref = None
    for child in device_elem.iter("DeviceCategory"):
        # Sometimes there's metadata about loaded preset
        pass
    # Snapshot key parameters per device class (the most production-meaningful)
    params = OrderedDict()
    if name == "Compressor2":
        for k in ("Threshold", "Ratio", "Attack", "Release", "Knee", "DryWet",
                  "ExpansionRatio", "OutputGain", "Activator"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name in ("Eq8", "EqEight"):
        bands = []
        for band in device_elem.iter("Band"):
            mode = find_first_value(band, "Mode")
            freq = find_first_value(band, "Freq")
            gain = find_first_value(band, "Gain")
            q = find_first_value(band, "Q")
            on = find_first_value(band, "IsOn")
            if on == "true" and freq is not None:
                bands.append({"freq": freq, "gain": gain, "q": q, "mode": mode})
        if bands:
            params["bands"] = bands
    elif name == "Operator":
        for k in ("Algorithm", "PitchBendRange", "Voices", "Drift", "TransposeKey", "Volume"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Wavetable":
        for k in ("Mode", "Wt1Position", "Wt2Position", "Wt1ToWt2", "Wt1Detune", "Wt2Detune",
                  "FilterCutoff", "FilterRes", "FilterFreq", "Volume"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Drift":
        for k in ("Algorithm", "Cutoff", "Resonance", "Drive", "Volume", "Glide"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Reverb":
        for k in ("DecayTime", "PreDelay", "RoomSize", "DryWet", "DiffuseLevel"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "HybridReverb":
        for k in ("DecayTime", "PreDelay", "DryWet", "AlgorithmTypes"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Echo":
        for k in ("LeftDelay", "RightDelay", "Feedback", "DryWet", "FilterFrequency", "FilterMorph"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Delay":
        for k in ("LeftDelay", "RightDelay", "Feedback", "DryWet"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "AutoFilter":
        for k in ("Cutoff", "Resonance", "Type", "LfoAmount", "LfoFrequency", "Drive"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "AutoPan":
        for k in ("Frequency", "Phase", "Shape", "Amount", "DryWet"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Saturator":
        for k in ("Drive", "Type", "DryWet", "Output", "BaseLine"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Erosion":
        for k in ("Frequency", "Amount", "Width", "Mode"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Vinyl":
        for k in ("Crackle", "PitchEffect", "Tracing", "TraceDistortion", "Mechanics"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Limiter":
        for k in ("Ceiling", "GainCompensation", "LookAhead", "Release"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Utility":
        for k in ("Gain", "Width", "Pan", "Mute"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "GrainDelay":
        for k in ("Frequency", "Pitch", "Spray", "RandomPitch", "DryWet"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "FrequencyShifter":
        for k in ("Coarse", "Fine", "Mode", "DryWet", "Drive"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Chorus":
        for k in ("Rate", "Amount", "Feedback", "DryWet"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Phaser":
        for k in ("Frequency", "Resonance", "LfoFrequency", "DryWet"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v
    elif name == "Vocoder":
        for k in ("BandwidthHi", "BandwidthLow", "Formant", "DryWet"):
            v = find_first_value(device_elem, k)
            if v is not None:
                params[k] = v

    # Macro values for racks
    macros = []
    if name in ("AudioEffectGroupDevice", "MidiEffectGroupDevice", "InstrumentGroupDevice", "DrumGroupDevice"):
        # Macros are direct children named MacroControls.<i> with a <Manual Value=...> sub-element.
        # MUST use direct child iteration (not device_elem.iter()) — iter() descends into nested
        # sub-racks and finds their MacroControls.0 first, which are always 0 (the sub-rack defaults).
        for i in range(16):  # up to 16 macros in Live 11+
            for child in device_elem:
                if child.tag == f"MacroControls.{i}":
                    for gc in child:
                        if gc.tag == "Manual":
                            v = gc.attrib.get("Value")
                            if v is not None:
                                macros.append({"index": i, "value": v})
                            break
                    break

    # Nested chain recursion for rack devices (BUG-C#2 fix, 2026-04-30)
    # Walk Branches → each branch's DeviceChain → *DeviceChain → Devices recursively.
    chains = None
    rack_classes = ("AudioEffectGroupDevice", "MidiEffectGroupDevice",
                    "InstrumentGroupDevice", "DrumGroupDevice")
    if name in rack_classes and _chain_depth < _MAX_CHAIN_DEPTH:
        chains = _extract_rack_chains(device_elem, _chain_depth + 1)

    # PluginDevice metadata (third-party VST/AU/AAX). Param VALUES are stored in
    # an opaque per-plugin binary blob and aren't readable from XML, but the
    # plugin's identity metadata IS in plain XML — capture it so downstream
    # tools (extract_chain → manual_rebuild step) can give the agent enough to
    # locate the plugin via load_browser_item or vendor lookup.
    plugin = None
    if name == "PluginDevice":
        plugin = _extract_plugin_metadata(device_elem)

    result = {
        "class": display,
        "user_name": user_name or None,
        "params": dict(params) if params else None,
        "macros": macros if macros else None,
    }
    if chains is not None:
        result["chains"] = chains
    if plugin is not None:
        result["plugin"] = plugin
    return result


def _extract_plugin_metadata(device_elem):
    """Pull plugin identity from a PluginDevice XML element.

    The .als/.adg PluginDevice node has shape (varies by plugin format):
      <PluginDevice>
        <PluginDesc>
          <VstPluginInfo Id="...">
            <PlugName Value="Serum"/>
            <Manufacturer Value="Xfer Records"/>
            <Type Value="VST"/>
            <UniqueId Value="1397772120"/>
            <FileName Value="Serum.vst"/>
          </VstPluginInfo>
          <!-- OR -->
          <Vst3PluginInfo Id="..."> ... </Vst3PluginInfo>
          <!-- OR -->
          <AuPluginInfo Id="..."> ... </AuPluginInfo>
        </PluginDesc>
        <ParameterList>...</ParameterList>      <!-- exposed params (limited) -->
        <Buffer Value="..."/>                   <!-- opaque binary state -->
      </PluginDevice>

    Returns dict with whatever was found:
      {format: "VST"|"VST3"|"AU"|"AAX"|"unknown",
       name: str|None,                # plugin's display name (e.g. "Serum")
       manufacturer: str|None,        # vendor (e.g. "Xfer Records")
       file_name: str|None,           # .vst/.vst3/.component filename
       unique_id: str|None,           # plugin's stable identifier
       exposed_param_count: int}      # number of <ParameterList> entries (rough)

    Param VALUES inside <Buffer> are NOT extracted — those are plugin-specific
    binary state. Whether that becomes parseable is a separate workstream.
    """
    info_tags_to_format = {
        "VstPluginInfo": "VST",
        "Vst3PluginInfo": "VST3",
        "AuPluginInfo": "AU",
        "AaxPluginInfo": "AAX",
    }
    out = {
        "format": "unknown",
        "name": None,
        "manufacturer": None,
        "file_name": None,
        "unique_id": None,
        "exposed_param_count": 0,
    }
    desc = device_elem.find("PluginDesc")
    if desc is not None:
        for child in desc:
            fmt = info_tags_to_format.get(child.tag)
            if fmt:
                out["format"] = fmt
                # Multiple known field names depending on Live version + format
                for plug_field, target in (
                    (("PlugName", "Name"), "name"),
                    (("Manufacturer", "ManufacturerName"), "manufacturer"),
                    (("FileName", "FileRef"), "file_name"),
                    (("UniqueId", "ProductId", "PluginId"), "unique_id"),
                ):
                    for tag in plug_field:
                        v = find_first_value(child, tag)
                        if v is not None:
                            out[target] = v
                            break
                break
    # Count exposed parameters (the ones Live can map; not the plugin's full state)
    param_list = device_elem.find("ParameterList")
    if param_list is not None:
        out["exposed_param_count"] = sum(
            1 for ch in param_list if ch.tag.startswith("Parameter")
        )
    return out


def extract_track_devices(track_elem):
    """Walk the track's DeviceChain → Devices, in order."""
    devices = []
    # Find the immediate DeviceChain → Devices container
    for chain in track_elem.iter("DeviceChain"):
        # Inside DeviceChain there can be MainSequencer + DeviceChain.0 + ...
        # We want the inner DeviceChain that contains Devices
        for inner_chain in chain.iter("DeviceChain"):
            for devices_container in inner_chain.iter("Devices"):
                for elem in devices_container:
                    if is_device_element(elem):
                        devices.append(extract_device_summary(elem))
                if devices:
                    return devices
    return devices


def extract_track_routing(track_elem):
    """Track input/output routing summary."""
    routing = {}
    for cat, tag in [("input_routing", "AudioInputRouting"),
                     ("output_routing", "AudioOutputRouting"),
                     ("midi_input_routing", "MidiInputRouting"),
                     ("midi_output_routing", "MidiOutputRouting")]:
        for r in track_elem.iter(tag):
            target = find_first_value(r, "Target")
            upper = find_first_value(r, "UpperDisplayString")
            lower = find_first_value(r, "LowerDisplayString")
            if target or upper:
                routing[cat] = {"target": target, "upper": upper, "lower": lower}
            break
    return routing


def parse_als(path):
    """Top-level parse → structured dict."""
    root = load_als(path)
    stem = Path(path).stem
    raw_scale = get_scale(root)
    # BUG-PARSER#4 fix (2026-04-30): override C-Major default with filename key
    # for construction-kit packs that encode key in the filename.
    scale = _apply_filename_key_fallback(raw_scale, stem)
    out = {
        "file": str(path),
        "name": stem,
        "bpm": get_project_bpm(root),
        "time_signature": get_time_signature(root),
        "scale": scale,
        "tracks": [],
        "scenes": [],
    }

    # Iterate top-level tracks (MidiTrack, AudioTrack, ReturnTrack, GroupTrack)
    track_tags = ("MidiTrack", "AudioTrack", "ReturnTrack", "GroupTrack")
    seen_track_ids = set()
    for track_tag in track_tags:
        for track in root.iter(track_tag):
            tid = track.attrib.get("Id", "")
            if tid in seen_track_ids:
                continue
            seen_track_ids.add(tid)
            tname = get_track_name(track)
            tdevs = extract_track_devices(track)
            trouting = extract_track_routing(track)
            out["tracks"].append({
                "name": tname,
                "type": track_tag,
                "id": tid,
                "device_count": len(tdevs),
                "devices": tdevs,
                "routing": trouting if trouting else None,
            })

    # Scene names (session view)
    for scene in root.iter("Scene"):
        n = find_first_value(scene, "Name")
        if n:
            out["scenes"].append(n)

    return out


def render_markdown(parsed):
    """Render a parse result as a markdown subsection."""
    md = []
    md.append(f"### {parsed['name']} — deep parse\n")
    md.append(f"- **BPM:** {parsed['bpm'] if parsed['bpm'] is not None else '(not set)'}")
    md.append(f"- **Time signature:** {parsed['time_signature'] or '(not extracted)'}")
    if parsed["scale"]:
        md.append(f"- **Scale:** {parsed['scale']}")
    if parsed["scenes"]:
        scenes_str = ", ".join(parsed["scenes"][:8]) + (" ..." if len(parsed["scenes"]) > 8 else "")
        md.append(f"- **Scenes ({len(parsed['scenes'])}):** {scenes_str}")
    md.append(f"- **Tracks ({len(parsed['tracks'])}):**\n")

    for t in parsed["tracks"]:
        ttype = t["type"].replace("Track", "")
        head = f"  - **{t['name']}** [{ttype}]"
        if t["device_count"]:
            head += f" — {t['device_count']} devices"
        md.append(head)
        if t["routing"]:
            for cat, r in t["routing"].items():
                if r and (r.get("upper") or r.get("target")):
                    md.append(f"    - routing.{cat}: {r.get('upper')} → {r.get('lower')}")
        for i, dev in enumerate(t["devices"]):
            d_name = dev["user_name"] or dev["class"]
            line = f"    - device #{i+1}: `{dev['class']}`"
            if dev["user_name"]:
                line += f" (named: \"{dev['user_name']}\")"
            md.append(line)
            if dev["params"]:
                # Show key params compactly
                pstr = ", ".join(f"{k}={v}" for k, v in dev["params"].items() if not isinstance(v, list))
                if pstr:
                    md.append(f"      params: {pstr}")
                if dev["params"].get("bands"):
                    md.append(f"      EQ bands: {len(dev['params']['bands'])} active")
            if dev.get("macros"):
                macro_str = ", ".join(f"M{m['index']}={m['value']}" for m in dev["macros"])
                md.append(f"      macros: {macro_str}")
    return "\n".join(md)


# =============================================================================
# .adg parser — single rack preset (gzipped XML, same approach as .als)
# =============================================================================

def get_macro_display_names(elem):
    """Extract macro display names + values from a rack-shaped element."""
    macros = []
    for i in range(16):
        # Find MacroControls.<i> children at this rack's level (NOT recursive into nested racks)
        manual_value = None
        for child in elem:
            if child.tag == f"MacroControls.{i}":
                for gc in child:
                    if gc.tag == "Manual":
                        manual_value = gc.attrib.get("Value")
                        break
                break

        # Display name lives in MacroDisplayNames.<i>
        display_name = None
        for child in elem:
            if child.tag == f"MacroDisplayNames.{i}":
                v = child.attrib.get("Value")
                if v and v.strip():
                    display_name = v
                break

        if manual_value is not None:
            macros.append({
                "index": i,
                "value": manual_value,
                "name": display_name,
            })
    return macros


def extract_branch_preset_chain(bp_elem):
    """For a single <*BranchPreset> element, extract its DevicePresets list as a chain."""
    name = find_first_value(bp_elem, "Name") or ""
    devices = []
    for dp in bp_elem:
        if dp.tag == "DevicePresets":
            for entry in dp:
                # AbletonDevicePreset wraps a single device; GroupDevicePreset wraps a sub-rack
                if entry.tag in ("AbletonDevicePreset", "GroupDevicePreset"):
                    for dev_wrap in entry:
                        if dev_wrap.tag == "Device":
                            for actual in dev_wrap:
                                if is_device_element(actual) or actual.tag.endswith("GroupDevice"):
                                    devices.append(extract_device_summary(actual))
                                    break
                            break
            break
    return {"name": name, "devices": devices}


def extract_rack_chain(root_elem, rack_elem, limit=12):
    """Extract chain summary from a .adg.

    Branches in .adg live at the <BranchPresets> level (sibling of <Device>
    inside <GroupDevicePreset>), NOT inside <Device>.<rack>.<Branches>.
    """
    chains = []
    branch_counts = {}

    for bp_container in root_elem.iter("BranchPresets"):
        for branch in bp_container:
            btag = branch.tag
            if not (btag.endswith("BranchPreset")):
                continue
            branch_counts[btag] = branch_counts.get(btag, 0) + 1
            if len(chains) < limit:
                chains.append(extract_branch_preset_chain(branch))
        break  # only top-level BranchPresets

    return chains, branch_counts


def parse_adg(path):
    """Parse a .adg rack preset file. Returns structured dict."""
    root = load_als(path)  # same gunzip + parse
    out = {
        "file": str(path),
        "name": Path(path).stem,
        "preset_type": None,  # "audio_effect_rack" / "instrument_rack" / "midi_effect_rack" / "drum_rack"
        "rack_class": None,
        "macros": [],
        "chains": [],
        "device_summary": [],  # summary of all devices used inside the rack
    }

    # Find the root rack element (inside GroupDevicePreset > Device)
    rack = None
    for gdp in root.iter("GroupDevicePreset"):
        for device_wrapper in gdp:
            if device_wrapper.tag == "Device":
                # Inside Device is the actual rack class (AudioEffectGroupDevice etc.)
                for inner in device_wrapper:
                    if inner.tag in ("AudioEffectGroupDevice", "InstrumentGroupDevice",
                                    "MidiEffectGroupDevice", "DrumGroupDevice"):
                        rack = inner
                        break
                break
        break

    if rack is None:
        return out

    out["rack_class"] = rack.tag
    type_map = {
        "AudioEffectGroupDevice": "audio_effect_rack",
        "InstrumentGroupDevice": "instrument_rack",
        "MidiEffectGroupDevice": "midi_effect_rack",
        "DrumGroupDevice": "drum_rack",
    }
    out["preset_type"] = type_map.get(rack.tag, "rack")

    # Macros + display names (outer rack)
    out["macros"] = get_macro_display_names(rack)

    # BUG-PARSER#2 fix (2026-04-30): resolve generic "Macro N" names on the outer rack
    # by scanning all nested racks in BranchPresets.  Ableton stores the binding between
    # an inner macro and its outer rack slot in the inner MacroControls.<i>/KeyMidi element:
    #   Channel=16  (Ableton's internal macro-mapping channel)
    #   NoteOrController = the outer rack's macro index this inner macro is bound to.
    # If the inner macro has a real display name and the outer slot still says "Macro N",
    # we adopt the inner name.
    outer_gdp = root.find("GroupDevicePreset")
    if outer_gdp is not None:
        outer_bp = outer_gdp.find("BranchPresets")
        if outer_bp is not None:
            # Build a lookup: outer_index -> best_inner_name (first non-generic name wins)
            resolved_names = {}  # int -> str
            for branch_entry in outer_bp.iter():
                # Any nested GroupDevicePreset → Device → rack_class contains inner macros
                if branch_entry.tag != "GroupDevicePreset":
                    continue
                inner_dev_wrapper = branch_entry.find("Device")
                if inner_dev_wrapper is None:
                    continue
                for inner_rack in inner_dev_wrapper:
                    if inner_rack.tag not in ("AudioEffectGroupDevice", "InstrumentGroupDevice",
                                              "MidiEffectGroupDevice", "DrumGroupDevice"):
                        continue
                    # Scan each MacroControls.<i> for KeyMidi Channel=16 binding
                    for i in range(16):
                        inner_mc = None
                        inner_dn = None
                        for child in inner_rack:
                            if child.tag == f"MacroControls.{i}":
                                inner_mc = child
                            elif child.tag == f"MacroDisplayNames.{i}":
                                v = child.attrib.get("Value", "")
                                if v and not v.startswith("Macro "):
                                    inner_dn = v
                        if inner_mc is None or inner_dn is None:
                            continue
                        keymidi = inner_mc.find("KeyMidi")
                        if keymidi is None:
                            continue
                        ch_elem = keymidi.find("Channel")
                        noc_elem = keymidi.find("NoteOrController")
                        if ch_elem is None or noc_elem is None:
                            continue
                        if ch_elem.attrib.get("Value") != "16":
                            continue
                        try:
                            outer_idx = int(noc_elem.attrib.get("Value", "-1"))
                        except ValueError:
                            continue
                        if outer_idx < 0:
                            continue
                        # Only fill if the outer slot is still generic and not already resolved
                        if outer_idx not in resolved_names:
                            resolved_names[outer_idx] = inner_dn

            # Apply resolved names to the outer macro list
            if resolved_names:
                for macro in out["macros"]:
                    idx = macro.get("index")
                    if idx in resolved_names:
                        current_name = macro.get("name") or ""
                        if not current_name or current_name.startswith("Macro "):
                            macro["name"] = resolved_names[idx]

    # Chains (extract from BranchPresets at root level)
    chains, branch_counts = extract_rack_chain(root, rack)
    out["chains"] = chains
    out["branch_counts"] = branch_counts

    # Device summary — flatten all devices across all chains
    seen_classes = []
    for chain in out["chains"]:
        for dev in chain["devices"]:
            seen_classes.append(dev["class"])
    out["device_summary"] = list(seen_classes)

    return out


def render_adg_markdown(parsed):
    """Render an .adg parse as compact markdown."""
    md = []
    md.append(f"### {parsed['name']} — preset deep parse\n")
    md.append(f"- **Rack type:** {parsed['preset_type'] or '(unknown)'} ({parsed['rack_class']})")
    md.append(f"- **Chains:** {len(parsed['chains'])}")
    if parsed["device_summary"]:
        from collections import Counter
        c = Counter(parsed["device_summary"])
        chain_str = ", ".join(f"{k}×{v}" for k, v in c.most_common())
        md.append(f"- **Devices used (flat):** {chain_str}")
    if parsed["macros"]:
        # Show only macros with non-default values OR named display names
        md.append(f"- **Macros (with author-set values + display names):**")
        for m in parsed["macros"]:
            v = m["value"]
            n = m["name"]
            try:
                fv = float(v)
                is_default = abs(fv) < 0.001
            except (ValueError, TypeError):
                is_default = False
            tag = "(default)" if is_default else ""
            name_str = n if n and not n.startswith("Macro ") else "(unnamed)"
            md.append(f"  - **M{m['index']}** ({name_str}): {v} {tag}")
    if parsed["chains"]:
        for chain in parsed["chains"]:
            md.append(f"- **Chain `{chain['name']}`** ({len(chain['devices'])} devices):")
            for i, dev in enumerate(chain["devices"]):
                line = f"    - device #{i+1}: `{dev['class']}`"
                if dev.get("user_name"):
                    line += f" \"{dev['user_name']}\""
                md.append(line)
                if dev.get("params"):
                    pstr = ", ".join(f"{k}={v}" for k, v in dev["params"].items() if not isinstance(v, list))
                    if pstr:
                        md.append(f"      params: {pstr}")
    return "\n".join(md)


def parse_any(path):
    """Auto-detect .als vs .adg based on root structure."""
    p = Path(path)
    if p.suffix.lower() == ".adg":
        return parse_adg(path)
    return parse_als(path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: als_deep_parse.py <path-to-als-or-adg> [--json | --markdown]", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    parsed = parse_any(path)
    fmt = "--markdown" if "--markdown" in sys.argv else "--json"
    if fmt == "--markdown":
        if Path(path).suffix.lower() == ".adg":
            print(render_adg_markdown(parsed))
        else:
            print(render_markdown(parsed))
    else:
        import json
        print(json.dumps(parsed, indent=2, default=str))

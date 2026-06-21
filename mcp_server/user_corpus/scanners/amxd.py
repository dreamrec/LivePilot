"""AMXD scanner — extracts metadata from Max for Live device files.

.amxd structure (binary):
  24-byte 'ampf' header + ptch chunk + mx@c chunk + JSON patcher + frozen deps

We do a best-effort parse:
  - Read the 24-byte ampf header → device type byte (audio/instrument/midi)
  - Locate the JSON patcher block by scanning for "{ \"patcher\""
  - Parse the JSON, extract:
      - patcher.appversion (Max major.minor)
      - patcher.boxes[*].text (script names, used to infer "what's inside")
      - patcher.parameters (Live-exposed parameter names where stored as plain JSON)
  - Look for a `var VERSION = "..."` string in any embedded js (LivePilot ping pattern)

Param VALUES inside the frozen JS deps are NOT extracted (similar to PluginDevice
binary state — opaque without a Max runtime). Identity metadata is what we capture.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..scanner import Scanner, register_scanner


# ─── Scanner ────────────────────────────────────────────────────────────────


# Producer-vocabulary keywords that survive a substring match against a
# .amxd device's filename. Hits become "purpose:<keyword>" tags so the
# overlay index can answer "what's an arpeggiator in my user library".
# Order matters slightly — short keywords go last so longer matches win.
_PURPOSE_KEYWORDS: tuple[str, ...] = (
    # Sequencing / rhythm
    "arpeggiator", "arp", "sequencer", "euclidean", "polyrhythm", "polymeter",
    "groove", "humanize", "swing", "step",
    # Drum / percussion
    "drum", "kick", "snare", "hihat", "hat", "ride", "clap", "perc", "rim",
    "808", "cymbal",
    # Synthesis
    "synth", "instrument", "wavetable", "additive", "subtractive", "fm",
    "physical", "granular", "sample", "sampler", "looper", "operator", "drift",
    "wavefolder", "fold", "noise", "oscillator",
    # Filtering / EQ
    "filter", "lowpass", "highpass", "bandpass", "comb", "formant",
    "eq", "parametric", "shelving",
    # Time-based effects
    "delay", "echo", "reverb", "chorus", "phaser", "flanger", "tremolo",
    "vibrato", "shimmer", "convolution", "spectral",
    # Distortion / saturation
    "saturator", "saturation", "distort", "distortion", "bitcrush", "redux",
    "shaper", "warmth", "drive", "tube", "tape", "vinyl",
    # Modulation
    "lfo", "envelope", "modulator", "modulation", "morph", "macro",
    # Dynamics / mix
    "sidechain", "compressor", "compression", "gate", "limiter", "expander",
    "transient", "ducker", "pumper", "pump",
    # Pitch / tuning / harmony
    "vocoder", "harmonizer", "harmony", "pitch", "tuner", "tune",
    "chord", "scale", "transpose", "transposer", "key", "interval",
    # Glitch / experimental
    "stutter", "glitch", "freeze", "stretch", "skip",
    "feedback", "resonator", "ringmod",
    # Utility / routing
    "midi", "cc", "rack", "router", "splitter", "mixer", "send", "return",
    "matrix", "patch", "bus",
    # Common third-party device prefixes (J74, ML, mt., MT, K-Devices, fors)
    "ableton", "live", "j74", "mt.", "k-devices", "fors", "iftah", "monolake",
    # Visual / analyzer
    "analyzer", "scope", "spectrum", "meter", "tuner",
    # Sonic descriptors (where filename hints at character)
    "warm", "bright", "dark", "crisp", "lofi", "vintage", "modern",
    "ambient", "drone", "pad", "lead", "bass",
)


@register_scanner
class AmxdScanner(Scanner):
    type_id = "amxd"
    file_extensions = [".amxd"]
    output_subdir = "max_devices"
    schema_version = 1

    def scan_one(self, path: Path) -> dict:
        raw = path.read_bytes()
        return _parse_amxd(raw, path.name)

    def derive_tags(self, sidecar: dict) -> list[str]:
        tags = ["max-device"]
        dev_type = sidecar.get("device_type")
        if dev_type:
            tags.append(f"max-{dev_type}")
        max_version = sidecar.get("max_version")
        if max_version:
            tags.append(f"max-v{max_version}")
        if sidecar.get("livepilot_ping_version"):
            tags.append("livepilot-ping")
        for p in (sidecar.get("exposed_parameters") or [])[:5]:
            tags.append(f"param:{_slug(p)}")

        # Producer-vocabulary tagging — scans against:
        #   1. The filename (cheap, often diagnostic)
        #   2. The patcher keyword_corpus (annotations + parameter names + varnames +
        #      subpatcher names) — closes the gap for devices whose name doesn't
        #      contain producer-vocab words (e.g. Sie-Q has "EQ" in box annotations
        #      but not its filename).
        name_lower = (sidecar.get("name") or "").lower()
        keyword_corpus = (sidecar.get("keyword_corpus") or "").lower()
        seen_purposes: set[str] = set()
        for kw in _PURPOSE_KEYWORDS:
            if kw in seen_purposes:
                continue
            if kw in name_lower or kw in keyword_corpus:
                tags.append(f"purpose:{kw}")
                seen_purposes.add(kw)

        # Object-class signature — what kind of Max device this is by structure.
        # E.g., a device with many `live.dial` boxes is parameter-heavy; one
        # with `js` boxes is script-driven; one with `gen~` is DSP-graph.
        obj_classes = sidecar.get("object_classes") or {}
        for cls, n in obj_classes.items():
            cls_lower = cls.lower()
            if cls_lower.startswith("live.") and n >= 3:
                tags.append("rich-ui")
                break
        if "gen~" in obj_classes or "rnbo~" in obj_classes:
            tags.append("dsp-graph")
        if any(c.startswith("js") or c.startswith("v8") for c in obj_classes):
            tags.append("script-driven")

        return tags

    def derive_description(self, sidecar: dict) -> str:
        n_params = len(sidecar.get("exposed_parameters") or [])
        dev_type = sidecar.get("device_type") or "unknown"
        max_version = sidecar.get("max_version") or "?"
        return f"Max {dev_type} device, Max v{max_version}, {n_params} exposed params"


# ─── Parsing ─────────────────────────────────────────────────────────────────


# The ampf header carries device type as an ASCII letter at offset 8:
#   'a' (97) = audio effect
#   'i' (105) = instrument
#   'm' (109) = MIDI effect
# Earlier guess of 0/1/2 was wrong — verified against the user's 393-file
# real-world .amxd corpus where 388/393 devices reported as unknown-{97,109,105}.
_AMPF_DEVICE_TYPE_BYTE = 8
_DEVICE_TYPE_MAP = {
    ord("a"): "audio",
    ord("i"): "instrument",
    ord("m"): "midi",
}


def _parse_amxd(raw: bytes, filename: str) -> dict:
    """Best-effort .amxd metadata extractor.

    Never raises on malformed files — returns whatever we can recover with
    nulls for missing fields.
    """
    out: dict[str, Any] = {
        "name": filename.removesuffix(".amxd"),
        "device_type": None,
        "max_version": None,
        "exposed_parameters": [],
        "embedded_scripts": [],
        "livepilot_ping_version": None,
    }

    # 1. Device type from the ampf header
    if len(raw) > 24 and raw[:4] == b"ampf":
        try:
            tb = raw[_AMPF_DEVICE_TYPE_BYTE]
            out["device_type"] = _DEVICE_TYPE_MAP.get(tb, f"unknown-{tb}")
        except IndexError:
            pass

    # 2. Locate + parse the JSON patcher block
    json_blob = _extract_patcher_json(raw)
    if json_blob:
        try:
            patcher = json.loads(json_blob)
            if isinstance(patcher, dict):
                out.update(_extract_from_patcher(patcher))
        except json.JSONDecodeError:
            pass

    # 3. LivePilot-style ping version
    m = re.search(rb'var\s+VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', raw)
    if m:
        out["livepilot_ping_version"] = m.group(1).decode("ascii", errors="ignore")

    return out


def _extract_patcher_json(raw: bytes) -> bytes | None:
    """Find the embedded patcher JSON in a .amxd binary.

    Strategy: find the first occurrence of `{"patcher"` (whitespace-tolerant
    via a small loop), then walk braces with depth-counting until we hit
    matching close. Conservative — handles strings + escapes.
    """
    needle = re.search(rb'\{[\s\r\n]*"patcher"', raw)
    if not needle:
        return None
    start = needle.start()
    depth = 0
    in_str = False
    esc = False
    i = start
    while i < len(raw):
        ch = raw[i]
        if esc:
            esc = False
        elif ch == 0x5C and in_str:  # backslash
            esc = True
        elif ch == 0x22:  # double-quote
            in_str = not in_str
        elif not in_str:
            if ch == 0x7B:  # {
                depth += 1
            elif ch == 0x7D:  # }
                depth -= 1
                if depth == 0:
                    return raw[start:i + 1]
        i += 1
    return None


def _extract_from_patcher(patcher: dict) -> dict:
    """Pull useful fields out of the patcher JSON.

    Walks the patcher's box graph (recursively into subpatchers) and harvests:
      - max_version             (from appversion)
      - exposed_parameters      (live.dial / live.numbox / live.tab / etc.)
      - embedded_scripts        (js / jsui filenames)
      - parameter_longnames     (full Live-exposed parameter labels)
      - parameter_shortnames    (short labels, often producer-meaningful)
      - varnames                (author-assigned variable names)
      - annotations             (human-written box descriptions)
      - subpatcher_names        (`p <name>` boxes — common organizational hint)
      - object_classes          (count of each maxclass — device-shape signal)

    The keyword_corpus field at the bottom is the concatenation of all
    human-readable text we found (longnames + shortnames + varnames +
    annotations + subpatcher names) lower-cased — derive_tags scans that
    against the producer vocabulary.
    """
    info = patcher.get("patcher") if "patcher" in patcher else patcher
    if not isinstance(info, dict):
        return {}
    out: dict[str, Any] = {}

    appversion = info.get("appversion")
    if isinstance(appversion, dict):
        major = appversion.get("major")
        minor = appversion.get("minor")
        if major is not None and minor is not None:
            out["max_version"] = f"{major}.{minor}"

    state = {
        "scripts": [],
        "params": [],          # parameter_longnames (Live-exposed)
        "shortnames": [],
        "varnames": [],
        "annotations": [],
        "subpatcher_names": [],
        "maxclasses": {},      # class → count
    }
    _walk_patcher_boxes(info, state, depth=0)

    if state["params"]:
        out["exposed_parameters"] = state["params"][:64]
    if state["shortnames"]:
        out["parameter_shortnames"] = state["shortnames"][:64]
    if state["varnames"]:
        out["varnames"] = state["varnames"][:64]
    if state["annotations"]:
        out["annotations"] = state["annotations"][:32]
    if state["subpatcher_names"]:
        out["subpatcher_names"] = state["subpatcher_names"][:32]
    if state["scripts"]:
        out["embedded_scripts"] = state["scripts"][:32]
    if state["maxclasses"]:
        out["object_classes"] = dict(sorted(
            state["maxclasses"].items(), key=lambda kv: -kv[1])[:16])

    # The corpus of human-readable strings derive_tags() scans against
    # producer-vocabulary keywords. Lower-cased + space-joined for cheap
    # substring scanning.
    keyword_blob_parts: list[str] = []
    keyword_blob_parts.extend(state["params"])
    keyword_blob_parts.extend(state["shortnames"])
    keyword_blob_parts.extend(state["varnames"])
    keyword_blob_parts.extend(state["annotations"])
    keyword_blob_parts.extend(state["subpatcher_names"])
    if keyword_blob_parts:
        # 8KB cap — devices with massive parameter lists won't blow up the sidecar
        out["keyword_corpus"] = " ".join(keyword_blob_parts).lower()[:8192]
    return out


def _walk_patcher_boxes(info: dict, state: dict, depth: int) -> None:
    """Recurse through patcher.boxes — including subpatcher nodes — to collect signals.

    Cap depth at 4 to avoid pathological deeply-nested device graphs.
    """
    if depth > 4 or not isinstance(info, dict):
        return
    for box in (info.get("boxes") or []):
        if not isinstance(box, dict):
            continue
        b = box.get("box")
        if not isinstance(b, dict):
            continue
        maxclass = (b.get("maxclass") or "").strip()
        if maxclass:
            state["maxclasses"][maxclass] = state["maxclasses"].get(maxclass, 0) + 1
        text = b.get("text", "") or ""

        # Live-exposed UI elements — these are the dials/buttons producers see
        if isinstance(text, str) and ("live." in text or maxclass.startswith("live.")):
            longname = b.get("parameter_longname") or b.get("varname")
            if longname and longname not in state["params"]:
                state["params"].append(longname)
            shortname = b.get("parameter_shortname")
            if shortname and shortname not in state["shortnames"]:
                state["shortnames"].append(shortname)

        # Author varnames (whether or not the box is live.*)
        varname = b.get("varname")
        if varname and varname not in state["varnames"]:
            state["varnames"].append(varname)

        # Human-readable annotations (box.annotation or box.hint)
        for field in ("annotation", "hint", "comment"):
            anno = b.get(field)
            if isinstance(anno, str) and len(anno) >= 4:
                if anno not in state["annotations"]:
                    state["annotations"].append(anno)

        # Comment boxes — pure prose descriptions ("Section: Filters")
        if maxclass == "comment" and isinstance(text, str) and len(text) >= 4:
            if text not in state["annotations"]:
                state["annotations"].append(text)

        # Subpatcher boxes — text starts with "p <name>"
        if isinstance(text, str) and text.startswith("p "):
            sub_name = text[2:].strip()
            if sub_name and sub_name not in state["subpatcher_names"]:
                state["subpatcher_names"].append(sub_name)

        # Embedded JS / JSUI scripts
        if isinstance(text, str):
            for prefix in ("js ", "jsui ", "v8 ", "v8ui "):
                if text.startswith(prefix):
                    parts = text.split()
                    if len(parts) > 1:
                        state["scripts"].append(parts[1])
                    break

        # Recurse into the subpatcher's own boxes
        sub = b.get("patcher")
        if isinstance(sub, dict):
            _walk_patcher_boxes(sub, state, depth + 1)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

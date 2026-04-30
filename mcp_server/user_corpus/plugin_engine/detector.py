"""Phase 2.1 + 2.2 — Detect installed plugins on disk + extract identity.

Walks the OS-specific plugin folders and produces an inventory entry per
plugin. Identity extraction:
  - VST3:   parse Contents/Resources/moduleinfo.json (mandatory per VST3 SDK 3.7+)
  - AU v2:  parse .component bundle's Contents/Info.plist
  - AU v3:  enumerate via `auval -a` (catches iOS-ported Mac Catalyst apps
            whose .appex extensions live INSIDE app bundles at non-standard
            paths like /Applications/IOS audio/<App>.app/...). The auval-based
            scanner replaces the path-walker for AU on macOS — captures both
            v2 and v3 in one pass with manufacturer + name resolved.
  - VST2:   read CcnK chunk header from the binary

Never raises on a malformed bundle — logs + skips. On macOS, plugin "files"
are actually directory bundles (`.vst3`, `.component`, `.vst`, `.aaxplugin`).
"""

from __future__ import annotations

import json
import logging
import platform
import plistlib
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Default search paths per OS ────────────────────────────────────────────


def _macos_plugin_dirs() -> list[tuple[Path, str]]:
    home = Path.home()
    return [
        (Path("/Library/Audio/Plug-Ins/VST3"),                 "VST3"),
        (home / "Library/Audio/Plug-Ins/VST3",                 "VST3"),
        (Path("/Library/Audio/Plug-Ins/Components"),           "AU"),
        (home / "Library/Audio/Plug-Ins/Components",           "AU"),
        (Path("/Library/Audio/Plug-Ins/VST"),                  "VST2"),
        (home / "Library/Audio/Plug-Ins/VST",                  "VST2"),
        (Path("/Library/Application Support/Avid/Audio/Plug-Ins"), "AAX"),
    ]


def _windows_plugin_dirs() -> list[tuple[Path, str]]:
    program_files = Path("C:/Program Files")
    return [
        (program_files / "Common Files/VST3", "VST3"),
        (program_files / "VstPlugins",        "VST2"),
        (program_files / "Common Files/Avid/Audio/Plug-Ins", "AAX"),
    ]


def _linux_plugin_dirs() -> list[tuple[Path, str]]:
    home = Path.home()
    return [
        (Path("/usr/lib/vst3"),       "VST3"),
        (Path("/usr/local/lib/vst3"), "VST3"),
        (home / ".vst3",              "VST3"),
        (Path("/usr/lib/lv2"),        "LV2"),
        (Path("/usr/local/lib/lv2"),  "LV2"),
        (home / ".lv2",               "LV2"),
    ]


def default_plugin_dir() -> list[tuple[Path, str]]:
    """Return the default OS-appropriate plugin search paths.

    Each entry is (Path, format_label). Caller can extend or override.
    """
    sysname = platform.system()
    if sysname == "Darwin":
        return _macos_plugin_dirs()
    if sysname == "Windows":
        return _windows_plugin_dirs()
    return _linux_plugin_dirs()


# ─── Detected-plugin record ─────────────────────────────────────────────────


@dataclass
class DetectedPlugin:
    plugin_id: str          # stable slug: "<vendor-slug>-<plugin-slug>"
    name: str
    vendor: str | None
    format: str             # VST3 / AU / VST2 / AAX / LV2
    version: str | None
    bundle_path: str
    unique_id: str | None   # CID / AU subtype / VST plugin code
    file_size_kb: int | None = None
    sdk_metadata: dict[str, Any] | None = None  # raw moduleinfo / Info.plist

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Top-level entry ────────────────────────────────────────────────────────


def detect_installed_plugins(
    paths: list[tuple[Path, str]] | None = None,
    formats: list[str] | None = None,
    use_auval: bool = True,
) -> list[DetectedPlugin]:
    """Walk plugin folders + enumerate AUs via auval. Return all detected plugins.

    On macOS, this combines two strategies:
      - Path-based scanning of /Library/Audio/Plug-Ins/{VST3,VST,Components}
        and the AAX folder — catches v2 AUs and all VST/AAX bundles.
      - `auval -a` enumeration — catches AUv3 plugins whose .appex extensions
        live inside arbitrary .app bundles (iOS-ported Mac Catalyst apps,
        custom subdirectories like /Applications/IOS audio/, etc.).

    Both passes are deduplicated by (vendor, name, format).

    Parameters
    ----------
    paths      : explicit (Path, format) pairs to scan. Defaults to OS-appropriate.
    formats    : restrict to these formats (e.g. ["VST3", "AU"]). Default: all.
    use_auval  : when True (default) and on macOS, run `auval -a` as the AU
                 source of truth — much more reliable than path-walking. Set to
                 False to fall back to path-only scanning (mostly for tests
                 that don't want subprocess calls).
    """
    if paths is None:
        paths = default_plugin_dir()
    if formats:
        paths = [(p, f) for p, f in paths if f in formats]

    results: list[DetectedPlugin] = []
    seen_keys: set[tuple[str, str, str]] = set()   # (vendor_lc, name_lc, format)

    # 1. Path-based scan — covers VST3 / VST2 / AAX / LV2 + co-located AU v2
    for root, fmt in paths:
        if not root.exists():
            continue
        try:
            for entry in sorted(root.iterdir()):
                plugin = _identify_plugin(entry, fmt)
                if plugin:
                    key = ((plugin.vendor or "").lower(), plugin.name.lower(), plugin.format)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append(plugin)
        except (PermissionError, OSError) as e:
            logger.warning("Cannot read %s: %s", root, e)

    # 2. auval-based AU enumeration — captures AUv3 + arbitrary-location AUs
    want_au = formats is None or "AU" in (formats or [])
    if use_auval and want_au and platform.system() == "Darwin":
        for plugin in _detect_via_auval():
            key = ((plugin.vendor or "").lower(), plugin.name.lower(), plugin.format)
            if key not in seen_keys:
                seen_keys.add(key)
                results.append(plugin)

    return results


def _detect_via_auval() -> list[DetectedPlugin]:
    """Run macOS's `auval -a` and parse its output into DetectedPlugin records.

    auval is the system-shipped Audio Unit validator. `-a` enumerates every
    AU registered with the system (both v2 and v3, including those packaged
    as app extensions inside arbitrary .app bundles). This is the only
    reliable way to find iOS-ported Mac Catalyst plugins that don't live
    in /Library/Audio/Plug-Ins/Components/.

    Output line format:
      <typecode> <subtype> <manufacturer>  -  <vendor>: <plugin name>

    Where:
      typecode    'aufx'/'aumu'/'aumi' (effect/instrument/midi)
      subtype     4-char AU subtype code
      manufacturer 4-char manufacturer code (e.g. "Moog", "Chow")
      vendor      human-readable vendor string
      plugin name human-readable plugin name

    Returns empty list on any failure (auval missing, subprocess error,
    parse miss). Never raises.
    """
    auval_bin = shutil.which("auval")
    if not auval_bin:
        return []
    try:
        proc = subprocess.run(
            [auval_bin, "-a"],
            capture_output=True, text=True, timeout=120,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning("auval -a failed: %s", e)
        return []

    plugins: list[DetectedPlugin] = []
    line_re = re.compile(
        r"^(?P<typecode>aufx|aumu|aumi)\s+"
        r"(?P<subtype>\S{4})\s+"
        r"(?P<manuf>\S{4})\s*-\s*"
        r"(?P<vendor>[^:]+):\s*"
        r"(?P<name>.+?)$",
    )
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = line_re.match(line)
        if not m:
            continue
        typecode = m.group("typecode")
        subtype = m.group("subtype")
        manuf_code = m.group("manuf")
        vendor = m.group("vendor").strip()
        name = m.group("name").strip()

        # Skip "*deprecated" markers — Apple keeps legacy version registered
        # alongside the current one. The current entry comes through too.
        if "*deprecated" in name.lower():
            continue
        # Skip Apple's system AUs — they're system utility (AUDelay, AUFilter,
        # AUDistortion, etc.) that the user never thinks of as third-party
        # plugins. Add them back if you want comprehensive system-AU coverage.
        if vendor.lower() == "apple" and manuf_code == "appl":
            continue

        # Determine format via category heuristic. Most non-Apple AUs registered
        # on modern macOS are AUv3 (the only path forward since 10.13). True v2
        # plugins ALSO show up in this list because v2 is a registered AU type.
        # We can't distinguish v2 from v3 without inspecting the plugin's
        # executable architecture — so we tag all as "AU" and let downstream
        # consumers infer specifics from bundle_path when available.
        au_kind = {
            "aufx": "audio_effect",
            "aumu": "instrument",
            "aumi": "midi_effect",
        }.get(typecode, "unknown")

        plugin_id = _slug(f"{vendor}-{name}")
        unique_id = f"{typecode}.{subtype}.{manuf_code}"
        plugins.append(DetectedPlugin(
            plugin_id=plugin_id,
            name=name,
            vendor=vendor,
            format="AU",
            version=None,                    # auval doesn't surface version
            bundle_path="",                  # not available from auval; resolve later if needed
            unique_id=unique_id,
            file_size_kb=None,
            sdk_metadata={
                "auval_typecode": typecode,
                "auval_subtype": subtype,
                "auval_manufacturer_code": manuf_code,
                "au_role": au_kind,           # audio_effect / instrument / midi_effect
            },
        ))
    return plugins


def _identify_plugin(path: Path, fmt: str) -> DetectedPlugin | None:
    """Dispatch to the format-specific identity extractor."""
    if not path.exists():
        return None
    try:
        if fmt == "VST3" and path.suffix == ".vst3":
            return _identify_vst3(path)
        if fmt == "AU" and path.suffix == ".component":
            return _identify_au(path)
        if fmt == "VST2" and (path.suffix == ".vst" or path.suffix == ".dylib"):
            return _identify_vst2(path)
        if fmt == "AAX" and path.suffix == ".aaxplugin":
            return _identify_aax(path)
        if fmt == "LV2" and path.is_dir():
            return _identify_lv2(path)
    except Exception as e:  # noqa: BLE001 — never abort over one bad bundle
        logger.warning("Identity extraction failed for %s: %s", path, e)
    # If a format-specific parse failed, still emit a fallback record so the
    # plugin shows up in the inventory with whatever we can derive from the path
    return _fallback_identity(path, fmt)


# ─── VST3 ───────────────────────────────────────────────────────────────────


def _identify_vst3(bundle: Path) -> DetectedPlugin | None:
    info_path = bundle / "Contents" / "Resources" / "moduleinfo.json"
    plist_path = bundle / "Contents" / "Info.plist"
    name = bundle.stem
    vendor: str | None = None
    version: str | None = None
    unique_id: str | None = None
    sdk: dict[str, Any] | None = None
    if info_path.exists():
        try:
            sdk = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(sdk, dict):
                name = sdk.get("Name") or name
                vendor = sdk.get("Vendor")
                version = sdk.get("Version")
                classes = sdk.get("Classes") or []
                if classes and isinstance(classes[0], dict):
                    unique_id = classes[0].get("CID")
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("VST3 moduleinfo.json unreadable for %s: %s", bundle, e)
    # Pre-3.7 VST3 bundles don't have moduleinfo.json; fall back to Info.plist
    if not vendor and plist_path.exists():
        try:
            with plist_path.open("rb") as fh:
                plist = plistlib.load(fh)
            bundle_id = plist.get("CFBundleIdentifier") or ""
            copyright_text = plist.get("NSHumanReadableCopyright") or ""
            if not version:
                version = plist.get("CFBundleShortVersionString")
            if bundle_id:
                parts = bundle_id.split(".")
                if len(parts) >= 2 and parts[0].lower() in ("com", "net", "org", "io", "co"):
                    vendor = parts[1].title()
            if not vendor and copyright_text:
                m = re.search(r"\b(?:19|20)\d{2}\s+(?:by\s+)?([A-Za-z][\w&.\- ]{1,40})", copyright_text)
                if m:
                    vendor = m.group(1).strip().rstrip(".,;:")
            if sdk is None:
                sdk = {}
            sdk.setdefault("bundle_identifier", bundle_id)
        except (plistlib.InvalidFileException, OSError) as e:
            logger.debug("VST3 Info.plist unreadable for %s: %s", bundle, e)
    plugin_id = _slug(f"{vendor or 'unknown'}-{name}")
    return DetectedPlugin(
        plugin_id=plugin_id, name=name, vendor=vendor, format="VST3",
        version=version, bundle_path=str(bundle), unique_id=unique_id,
        file_size_kb=_bundle_size_kb(bundle),
        sdk_metadata=sdk,
    )


# ─── AU ─────────────────────────────────────────────────────────────────────


def _identify_au(bundle: Path) -> DetectedPlugin | None:
    info_path = bundle / "Contents" / "Info.plist"
    bundle_name = bundle.stem
    name = bundle_name
    vendor: str | None = None
    version: str | None = None
    unique_id: str | None = None
    sdk: dict[str, Any] | None = None
    manufacturer_code: str | None = None
    if info_path.exists():
        try:
            with info_path.open("rb") as fh:
                plist = plistlib.load(fh)
            if isinstance(plist, dict):
                sdk = _strip_unjsonable(plist)
                version = plist.get("CFBundleShortVersionString")
                bundle_id = plist.get("CFBundleIdentifier") or ""
                copyright_text = plist.get("NSHumanReadableCopyright") or ""

                comps = plist.get("AudioComponents") or []
                comp_name_raw: str = ""
                if comps and isinstance(comps[0], dict):
                    c0 = comps[0]
                    comp_name_raw = (c0.get("name") or "")
                    manufacturer_code = _decode_au_id(c0.get("manufacturer"))
                    unique_id = _decode_au_id(c0.get("subtype"))

                # Vendor + plugin name resolution — priority order:
                #   1. AudioComponents.name "Vendor: Plugin" → split
                #   2. Reverse-DNS from CFBundleIdentifier (com.<vendor>.<plugin>)
                #   3. Plain prose copyright string
                #   4. Fall back to 4-char manufacturer code as last resort
                if comp_name_raw and ":" in comp_name_raw:
                    v, n = (s.strip() for s in comp_name_raw.split(":", 1))
                    if v:
                        vendor = v
                    if n:
                        name = n
                if not name and comp_name_raw:
                    name = comp_name_raw
                if not name:
                    name = plist.get("CFBundleName") or bundle_name

                if not vendor and bundle_id:
                    parts = bundle_id.split(".")
                    if len(parts) >= 2 and parts[0].lower() in ("com", "net", "org", "io", "co"):
                        vendor = parts[1].title()  # com.spectrasonics.X → "Spectrasonics"
                if not vendor and copyright_text:
                    # "Copyright © 2024 u-he" → "u-he"; best-effort word grab after the year
                    m = re.search(r"\b(?:19|20)\d{2}\s+(?:by\s+)?([A-Za-z][\w&.\- ]{1,40})", copyright_text)
                    if m:
                        vendor = m.group(1).strip().rstrip(".,;:")
                if not vendor:
                    vendor = manufacturer_code   # last resort, the 4-char code

                # Stash both readable + code in sdk metadata for downstream debugging
                if sdk is None:
                    sdk = {}
                sdk.setdefault("manufacturer_code", manufacturer_code)
                sdk.setdefault("bundle_identifier", bundle_id)
        except (plistlib.InvalidFileException, OSError) as e:
            logger.debug("AU Info.plist unreadable for %s: %s", bundle, e)
    plugin_id = _slug(f"{vendor or 'unknown'}-{name}")
    return DetectedPlugin(
        plugin_id=plugin_id, name=name, vendor=vendor, format="AU",
        version=version, bundle_path=str(bundle), unique_id=unique_id,
        file_size_kb=_bundle_size_kb(bundle),
        sdk_metadata=sdk,
    )


# ─── VST2 ───────────────────────────────────────────────────────────────────


def _identify_vst2(path: Path) -> DetectedPlugin | None:
    # On macOS .vst is a bundle; on Windows/Linux it can be a single .dll/.so/.dylib
    binary_path = path
    if path.is_dir():
        # macOS bundle — look inside Contents/MacOS/
        macos_dir = path / "Contents" / "MacOS"
        if macos_dir.exists():
            execs = list(macos_dir.iterdir())
            if execs:
                binary_path = execs[0]
    name = path.stem
    plugin_code: str | None = None
    program_name: str | None = None
    try:
        with binary_path.open("rb") as fh:
            head = fh.read(60)
        if head[:4] == b"CcnK" and len(head) >= 60:
            plugin_code = head[16:20].decode("ascii", errors="ignore").strip()
            name_bytes = head[28:60].split(b"\x00", 1)[0]
            program_name = name_bytes.decode("latin-1", errors="ignore").strip()
    except OSError:
        pass
    # VST2 doesn't store vendor in the binary — infer from path
    vendor = path.parent.name if path.parent.name not in ("VST", "VstPlugins") else None
    plugin_id = _slug(f"{vendor or 'unknown'}-{name}")
    return DetectedPlugin(
        plugin_id=plugin_id, name=name, vendor=vendor, format="VST2",
        version=None, bundle_path=str(path), unique_id=plugin_code,
        file_size_kb=_bundle_size_kb(path),
        sdk_metadata={"program_name": program_name} if program_name else None,
    )


# ─── AAX ────────────────────────────────────────────────────────────────────


def _identify_aax(bundle: Path) -> DetectedPlugin | None:
    manifest = bundle / "Contents" / "Resources" / "PluginManifest.plist"
    name = bundle.stem
    vendor: str | None = None
    version: str | None = None
    unique_id: str | None = None
    sdk: dict[str, Any] | None = None
    if manifest.exists():
        try:
            with manifest.open("rb") as fh:
                plist = plistlib.load(fh)
            if isinstance(plist, dict):
                sdk = _strip_unjsonable(plist)
                name = plist.get("PluginName") or plist.get("CFBundleName") or name
                vendor = plist.get("ManufacturerName") or plist.get("Manufacturer")
                version = plist.get("PluginVersion") or plist.get("CFBundleShortVersionString")
                unique_id = plist.get("PluginID")
        except (plistlib.InvalidFileException, OSError) as e:
            logger.debug("AAX manifest unreadable for %s: %s", bundle, e)
    plugin_id = _slug(f"{vendor or 'unknown'}-{name}")
    return DetectedPlugin(
        plugin_id=plugin_id, name=name, vendor=vendor, format="AAX",
        version=version, bundle_path=str(bundle), unique_id=unique_id,
        file_size_kb=_bundle_size_kb(bundle),
        sdk_metadata=sdk,
    )


# ─── LV2 (Linux) ────────────────────────────────────────────────────────────


def _identify_lv2(plugin_dir: Path) -> DetectedPlugin | None:
    """LV2 plugins are RDF-described in .ttl files. Best-effort name + uri."""
    name = plugin_dir.name
    uri: str | None = None
    vendor: str | None = None
    for ttl in plugin_dir.glob("*.ttl"):
        try:
            text = ttl.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r'<([^>]+)>\s+a\s+lv2:Plugin', text)
        if m:
            uri = m.group(1)
        m = re.search(r'doap:name\s+"([^"]+)"', text)
        if m:
            name = m.group(1)
        m = re.search(r'doap:maintainer[^"]*"([^"]+)"', text)
        if m:
            vendor = m.group(1)
        if uri:
            break
    plugin_id = _slug(f"{vendor or 'unknown'}-{name}")
    return DetectedPlugin(
        plugin_id=plugin_id, name=name, vendor=vendor, format="LV2",
        version=None, bundle_path=str(plugin_dir), unique_id=uri,
        file_size_kb=_bundle_size_kb(plugin_dir),
        sdk_metadata=None,
    )


# ─── Fallback ───────────────────────────────────────────────────────────────


def _fallback_identity(path: Path, fmt: str) -> DetectedPlugin:
    name = path.stem
    return DetectedPlugin(
        plugin_id=_slug(f"unknown-{name}"),
        name=name, vendor=None, format=fmt,
        version=None, bundle_path=str(path), unique_id=None,
        file_size_kb=_bundle_size_kb(path),
        sdk_metadata=None,
    )


# ─── Helpers ────────────────────────────────────────────────────────────────


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "unknown"


def _decode_au_id(value: Any) -> str | None:
    """AU 4-char codes are 32-bit big-endian ints. Decode to ASCII."""
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


def _strip_unjsonable(d: Any) -> Any:
    """Recursively strip non-JSON-serializable values (bytes → hex, datetime → str)."""
    if isinstance(d, dict):
        return {k: _strip_unjsonable(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_strip_unjsonable(v) for v in d]
    if isinstance(d, bytes):
        return d.hex()
    if isinstance(d, (str, int, float, bool)) or d is None:
        return d
    return str(d)


def _bundle_size_kb(path: Path) -> int | None:
    """Total size of a plugin bundle / file in KB. None if unreadable."""
    try:
        if path.is_file():
            return int(path.stat().st_size / 1024)
        total = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
        return int(total / 1024)
    except OSError:
        return None

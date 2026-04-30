"""ALS scanner — wraps scripts/als_deep_parse.parse_als for one-file use.

Reuses the production-grade parser already used by the factory pack atlas:
  - Macro-value extraction (BUG-PARSER#1 fix: direct child scan, not recursive iter)
  - Numeric scale-mode decode for Live 9/10 files (BUG-PARSER#3)
  - Filename-key fallback for construction-kit packs (BUG-PARSER#4)
  - Nested chain recursion (BUG-C#2 schema A)
  - PluginDevice metadata (BUG-PARSER#5)

The user corpus inherits all of these for free.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

from ..scanner import Scanner, register_scanner


# ─── Lazy import of scripts/als_deep_parse.py ────────────────────────────────

_ALS_PARSE_MODULE = None


def _als_parse():
    """Load scripts/als_deep_parse.py once and cache it.

    Lives outside the mcp_server package, so we use importlib by path.
    """
    global _ALS_PARSE_MODULE
    if _ALS_PARSE_MODULE is not None:
        return _ALS_PARSE_MODULE
    repo_root = Path(__file__).resolve().parents[3]
    parser_path = repo_root / "scripts" / "als_deep_parse.py"
    if not parser_path.exists():
        raise ImportError(f"als_deep_parse.py not found at {parser_path}")
    spec = importlib.util.spec_from_file_location(
        "_als_deep_parse_user_corpus", parser_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {parser_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_als_deep_parse_user_corpus"] = module
    spec.loader.exec_module(module)
    _ALS_PARSE_MODULE = module
    return module


# ─── Scanner ────────────────────────────────────────────────────────────────


@register_scanner
class AlsScanner(Scanner):
    type_id = "als"
    file_extensions = [".als"]
    output_subdir = "projects"
    schema_version = 1

    def scan_one(self, path: Path) -> dict:
        parser = _als_parse()
        return parser.parse_als(str(path))

    def derive_tags(self, sidecar: dict) -> list[str]:
        tags: list[str] = ["als-project"]
        bpm = sidecar.get("bpm")
        if isinstance(bpm, (int, float)):
            tags.append(f"{int(round(bpm))}bpm")
        scale = sidecar.get("scale") or {}
        scale_name = scale.get("name")
        if scale_name and scale_name != "Major":  # don't add the default
            tags.append(scale_name.lower())
        if scale.get("source") == "filename-fallback":
            tags.append("filename-key")

        # Top device classes from track inventory (recursive into chains)
        seen: dict[str, int] = {}
        for cls in _walk_device_classes(sidecar.get("tracks") or []):
            seen[cls] = seen.get(cls, 0) + 1
        for cls, _ in sorted(seen.items(), key=lambda kv: -kv[1])[:5]:
            tags.append(f"has-{_slug(cls)}")

        # Track-count bucket
        n_tracks = len(sidecar.get("tracks") or [])
        if n_tracks > 0:
            if n_tracks < 5:
                tags.append("small-session")
            elif n_tracks < 16:
                tags.append("medium-session")
            else:
                tags.append("large-session")
        return tags

    def derive_description(self, sidecar: dict) -> str:
        bpm = sidecar.get("bpm")
        bpm_str = f"{int(round(bpm))} BPM" if isinstance(bpm, (int, float)) else "unknown BPM"
        scale = sidecar.get("scale") or {}
        root = scale.get("root_note", "")
        name = scale.get("name", "")
        scale_str = _format_scale(root, name)
        n_tracks = len(sidecar.get("tracks") or [])
        return f"{bpm_str}, {scale_str}, {n_tracks} tracks"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _format_scale(root: Any, name: str) -> str:
    root_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    try:
        i = int(str(root))
        if 0 <= i < 12:
            return f"{root_names[i]} {name}"
    except (ValueError, TypeError):
        pass
    return name or "unknown scale"


def _walk_device_classes(tracks: list[dict]) -> list[str]:
    """Yield every device class across tracks AND nested rack chains."""
    out: list[str] = []
    for t in tracks:
        out.extend(_walk_devices(t.get("devices") or []))
    return out


def _walk_devices(devices: list[dict], depth: int = 0) -> list[str]:
    if depth > 6:  # defensive cap
        return []
    out: list[str] = []
    for d in devices:
        cls = d.get("class") or ""
        if cls:
            out.append(cls)
        for chain in d.get("chains") or []:
            out.extend(_walk_devices(chain.get("devices") or [], depth + 1))
    return out

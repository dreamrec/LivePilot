"""User-corpus builder — scan your own .als / .adg / .amxd / plugin presets / samples
into queryable atlas overlays.

See docs/USER_CORPUS_GUIDE.md for the full architecture + user guide.

Public API:
    from mcp_server.user_corpus import (
        Scanner, register_scanner, get_scanner, list_scanners,
        Manifest, Source, load_manifest, save_manifest,
        run_scan, ScanResult,
    )
"""
from __future__ import annotations

from .scanner import Scanner, register_scanner, get_scanner, list_scanners
from .manifest import (
    Manifest,
    Source,
    load_manifest,
    save_manifest,
    init_default_manifest,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_ROOT,
)
from .runner import run_scan, ScanResult, SourceScanResult

# Eager-import the built-in scanners so their @register_scanner decorators fire.
from .scanners import als as _als  # noqa: F401
from .scanners import adg as _adg  # noqa: F401
from .scanners import amxd as _amxd  # noqa: F401
from .scanners import plugin_preset as _pp  # noqa: F401

__all__ = [
    "Scanner",
    "register_scanner",
    "get_scanner",
    "list_scanners",
    "Manifest",
    "Source",
    "load_manifest",
    "save_manifest",
    "init_default_manifest",
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "run_scan",
    "ScanResult",
    "SourceScanResult",
]

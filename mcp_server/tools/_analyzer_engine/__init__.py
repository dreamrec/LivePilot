"""Analyzer helpers — pure-computation + context accessors split out from analyzer.py.

The public tool surface (32 ``@mcp.tool()`` functions) still lives in
``mcp_server/tools/analyzer.py`` — moving decorators across files risks
reordering FastMCP's tool registration. This package only holds the
supporting code that ``analyzer.py`` used to carry inline:

- ``context``  — SpectralCache + M4LBridge accessors and the analyzer
                 health check that formats user-facing error messages.
- ``sample``   — Simpler post-load hygiene (Snap=0, warped-loop defaults,
                 sample-name verification) + filename helpers.
- ``flucoma``  — FluCoMa-specific hint formatting + pitch-name tables.

Re-exports the public-ish helpers (``_`` prefix is intentional — these
are implementation details of ``analyzer.py``, not tools in their own
right) so existing ``from .tools.analyzer import _foo`` imports in tests
continue to resolve via the thin analyzer module.
"""

from .context import _get_spectral, _get_m4l, _require_analyzer
from .sample import (
    _BPM_IN_FILENAME_RE,
    _DRUM_ROOT_MAP,
    _detect_drum_root_note,
    _filename_stem,
    _is_warped_loop,
    _simpler_post_load_hygiene,
)
from .flucoma import PITCH_NAMES, _flucoma_hint

__all__ = [
    "_get_spectral",
    "_get_m4l",
    "_require_analyzer",
    "_BPM_IN_FILENAME_RE",
    "_DRUM_ROOT_MAP",
    "_detect_drum_root_note",
    "_filename_stem",
    "_is_warped_loop",
    "_simpler_post_load_hygiene",
    "PITCH_NAMES",
    "_flucoma_hint",
]

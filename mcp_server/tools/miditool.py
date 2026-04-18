"""MIDI Tool bridge (Live 12.0+ MIDI Generators / Transformations).

4 tools that let LivePilot generators run inside a clip's native
MIDI Tool slot. Traffic rides the existing UDP 9880/9881 M4L bridge
with a new /miditool/* OSC prefix; the user drops one of the
companion .amxd files (LivePilot_MIDITool_Transform.amxd for
Transformations, LivePilot_MIDITool_Generate.amxd for Generators)
onto the clip and configures which generator handles the note list
via ``set_miditool_target``. Both .amxd files share the same
miditool_bridge.js logic — the only difference is whether
``live.miditool.in`` is in Transformation or Generator mode.

See ``m4l_device/MIDITOOL_BUILD_GUIDE.md`` for the Max build.
"""

from __future__ import annotations

import os
import platform
import shutil
from typing import Optional

from fastmcp import Context

from ..server import mcp
from .. import m4l_bridge as _bridge_module


# ── Install paths ───────────────────────────────────────────────────────────

_M4L_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "m4l_device",
    )
)

# Two .amxd variants. Live 12 classifies them as Generator or Transformation
# via the 'nagg' vs 'natt' amxdtype marker in project.amxdtype. They install
# into DIFFERENT User Library subfolders for each role — Live's MIDI Tool
# indexer treats the folder as the authoritative category.
_AMXD_VARIANTS = (
    ("LivePilot_MIDITool_Generate.amxd",  "MIDI Tools/Max Generators"),
    ("LivePilot_MIDITool_Transform.amxd", "MIDI Tools/Max Transformations"),
)

# Also copy the JS bridge alongside the .amxd so Max can find it — the
# device references `js miditool_bridge.js` and Max searches relative to
# the .amxd's location.
_BRIDGE_JS = "miditool_bridge.js"

_MACOS_USER_LIB = os.path.expanduser("~/Music/Ableton/User Library")

_BUILD_GUIDE_REL = "m4l_device/MIDITOOL_BUILD_GUIDE.md"


def _get_miditool_cache(ctx: Context):
    """Resolve the MidiToolCache from the lifespan context."""
    cache = ctx.lifespan_context.get("miditool")
    if cache is None:
        raise ValueError(
            "MIDI Tool cache not initialized — restart the MCP server"
        )
    return cache


def _get_m4l_bridge(ctx: Context):
    """Resolve the M4LBridge from the lifespan context."""
    bridge = ctx.lifespan_context.get("m4l")
    if bridge is None:
        raise ValueError("M4L bridge not initialized — restart the MCP server")
    return bridge


# ── Tool 1: install_miditool_device ────────────────────────────────────────

@mcp.tool()
def install_miditool_device(ctx: Context) -> dict:
    """Install LivePilot MIDI Tool .amxd files into Ableton's User Library.

    Copies both variants from ``m4l_device/`` to the correct MIDI Tools
    subfolders. Live 12 classifies a device as Generator vs Transformation
    via the ``project.amxdtype`` marker ('nagg' vs 'natt') inside the .amxd,
    AND indexes them from these specific folders:

      - ``Generate.amxd``  → ``User Library/MIDI Tools/Max Generators/``
      - ``Transform.amxd`` → ``User Library/MIDI Tools/Max Transformations/``

    Also copies ``miditool_bridge.js`` alongside each .amxd so the ``[js]``
    object can find it (Max searches relative to the .amxd's location).

    Build the .amxd files first with ``scripts/build_miditool_amxd.py``,
    which patches Live's factory Max MIDI Generator/Transformation
    templates with our bridge wiring while preserving the amxdtype marker.

    After running this, right-click User Library in Live's browser →
    Refresh. Then open a MIDI clip's Generators or Transformations
    dropdown — ``LivePilot MIDI Tool (Generate/Transform)`` will be listed
    under User:.

    Returns ``{installed: [...], skipped: [...], user_library}``.
    macOS-only for this chunk.
    """
    if platform.system() != "Darwin":
        raise NotImplementedError(
            "install_miditool_device currently supports macOS only. "
            "Windows install path is ~/Documents/Ableton/User Library/... "
            "— copy manually until Windows support ships."
        )

    bridge_src = os.path.join(_M4L_DIR, _BRIDGE_JS)
    if not os.path.isfile(bridge_src):
        raise FileNotFoundError(
            f"Bridge JS not found at {bridge_src}. Source tree is missing "
            "miditool_bridge.js — re-clone or check out the branch."
        )

    installed = []
    skipped = []
    for filename, subfolder in _AMXD_VARIANTS:
        src = os.path.join(_M4L_DIR, filename)
        if not os.path.isfile(src):
            skipped.append({
                "variant": filename,
                "reason": f"source not found at {src}. Run "
                          "scripts/build_miditool_amxd.py to build it.",
            })
            continue
        dest_dir = os.path.join(_MACOS_USER_LIB, subfolder)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        existed_before = os.path.isfile(dest)
        shutil.copy2(src, dest)
        # Also copy the bridge JS into the same folder so Max's [js] object
        # can find it at runtime.
        shutil.copy2(bridge_src, os.path.join(dest_dir, _BRIDGE_JS))
        installed.append({
            "variant": filename,
            "installed_path": dest,
            "existed_before": existed_before,
            "category": subfolder.split("/")[-1],
        })

    if not installed:
        raise FileNotFoundError(
            "No .amxd variants found in m4l_device/. Run "
            "scripts/build_miditool_amxd.py first to build them from "
            "Live's factory templates, then re-run install_miditool_device()."
        )

    return {
        "installed": installed,
        "skipped": skipped,
        "user_library": _MACOS_USER_LIB,
        "hint": (
            "Right-click User Library in Live's browser → Refresh, then "
            "open a MIDI clip's Generators (for Generate.amxd) or "
            "Transformations (for Transform.amxd) dropdown. The LivePilot "
            "devices appear in the User section. Call set_miditool_target() "
            "to configure which generator handles incoming requests "
            "before firing the tool on a clip."
        ),
    }


# ── Tool 2: set_miditool_target ────────────────────────────────────────────

@mcp.tool()
def set_miditool_target(
    ctx: Context,
    tool_name: str,
    params: Optional[dict] = None,
) -> dict:
    """Configure which LivePilot generator handles MIDI Tool requests.

    When Live fires the MIDI Tool on a clip, the bridge forwards
    ``(notes, context)`` to the server; the server invokes the configured
    generator and pushes transformed notes back for Live to write into
    the clip.

    Args:
        tool_name: One of the registered generators. Call
                   ``list_miditool_generators()`` to see names and
                   required params. v1.11.0 ships with
                   ``euclidean_rhythm``, ``tintinnabuli``, ``humanize``.
        params:    Generator-specific options (see
                   ``list_miditool_generators``). Pass ``None`` or ``{}``
                   to use defaults.

    Returns ``{tool_name, params, active}``.
    """
    known = _bridge_module.available_generators()
    if tool_name not in known:
        raise ValueError(
            f"Unknown generator '{tool_name}'. "
            f"Registered generators: {', '.join(known)}. "
            "Call list_miditool_generators() for descriptions."
        )

    params = dict(params or {})
    cache = _get_miditool_cache(ctx)
    cache.set_target(tool_name, params)

    # Tell the JS bridge too so it knows what's queued even if it wants to
    # show UI state. The bridge itself still asks the server to run the
    # generator — this is informational + future-proofing.
    bridge = _get_m4l_bridge(ctx)
    try:
        bridge.send_miditool_config(tool_name, params)
        config_sent = True
    except Exception:
        # Bridge may not be up yet; not fatal — the server-side target is set.
        config_sent = False

    return {
        "tool_name": tool_name,
        "params": params,
        "active": True,
        "config_pushed_to_bridge": config_sent,
    }


# ── Tool 3: get_miditool_context ───────────────────────────────────────────

@mcp.tool()
def get_miditool_context(ctx: Context) -> dict:
    """Return the most recent MIDI Tool context received from the bridge.

    Fields come from Live's ``live.miditool.in`` right outlet:
        grid:      current grid subdivision (float beats)
        selection: {start, end} clip time range Live will replace
        scale:     {root, name, mode} current Scale Mode state
        seed:      RNG seed Live passes to the tool for determinism
        tuning:    {name, reference_pitch} Tuning System info (12.1+)

    Also returns ``note_count`` (how many notes arrived in the last
    request) and ``connected`` (True once the bridge has pinged).

    If the bridge hasn't emitted a request in the last ~5 seconds,
    returns ``{"connected": False}`` — the analyzer/miditool .amxd
    may not be loaded, or no MIDI Tool fire has happened yet.
    """
    cache = _get_miditool_cache(ctx)
    if not cache.is_connected:
        return {"connected": False}

    ctx_data = cache.get_last_context() or {}
    notes = cache.get_last_notes() or []

    return {
        "connected": True,
        "grid": ctx_data.get("grid"),
        "selection": ctx_data.get("selection"),
        "scale": ctx_data.get("scale"),
        "seed": ctx_data.get("seed"),
        "tuning": ctx_data.get("tuning"),
        "note_count": len(notes),
    }


# ── Tool 4: list_miditool_generators ───────────────────────────────────────

@mcp.tool()
def list_miditool_generators(ctx: Context) -> dict:
    """Enumerate the generators available for MIDI Tool targets.

    Each entry reports ``name``, ``description``, ``required_params``,
    and ``optional_params``. Use the names with
    ``set_miditool_target(tool_name=...)`` to configure the bridge.
    """
    entries = []
    for name in _bridge_module.available_generators():
        meta = _bridge_module.GENERATOR_METADATA.get(name, {})
        entries.append({
            "name": name,
            "description": meta.get("description", ""),
            "required_params": list(meta.get("required_params", [])),
            "optional_params": list(meta.get("optional_params", [])),
        })
    return {"generators": entries, "count": len(entries)}

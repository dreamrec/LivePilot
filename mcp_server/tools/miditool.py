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

# Two .amxd variants — same JS bridge, different live.miditool.in @mode.
_AMXD_VARIANTS = (
    "LivePilot_MIDITool_Transform.amxd",
    "LivePilot_MIDITool_Generate.amxd",
)

_MACOS_DEST_DIR = os.path.expanduser(
    "~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect"
)

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

    Copies both variants from ``m4l_device/`` to the macOS MIDI Effects
    User Library:
      - ``LivePilot_MIDITool_Transform.amxd`` → Transformations menu
      - ``LivePilot_MIDITool_Generate.amxd``  → Generators menu

    Variants that aren't present on disk yet are skipped (reported in
    ``skipped``). Build them first by opening the matching ``.maxpat``
    files in Max 9, saving as ``.amxd``, and optionally freezing to
    bundle ``miditool_bridge.js`` — see ``m4l_device/MIDITOOL_BUILD_GUIDE.md``.

    Returns ``{installed: [...], skipped: [...], dest_dir}``. Raises
    ``FileNotFoundError`` only if NEITHER variant is present.

    macOS-only for this chunk. Windows support is pending.
    """
    if platform.system() != "Darwin":
        raise NotImplementedError(
            "install_miditool_device currently supports macOS only. "
            "Windows install path is ~/Documents/Ableton/User Library/... "
            "— copy manually until Windows support ships."
        )

    os.makedirs(_MACOS_DEST_DIR, exist_ok=True)
    installed = []
    skipped = []
    for variant in _AMXD_VARIANTS:
        src = os.path.join(_M4L_DIR, variant)
        if not os.path.isfile(src):
            skipped.append({
                "variant": variant,
                "reason": f"source not found at {src}",
            })
            continue
        dest = os.path.join(_MACOS_DEST_DIR, variant)
        existed_before = os.path.isfile(dest)
        shutil.copy2(src, dest)
        installed.append({
            "variant": variant,
            "installed_path": dest,
            "existed_before": existed_before,
        })

    if not installed:
        raise FileNotFoundError(
            "No .amxd variants found in m4l_device/. Build at least one "
            f"by following {_BUILD_GUIDE_REL}, then re-run "
            "install_miditool_device()."
        )

    return {
        "installed": installed,
        "skipped": skipped,
        "dest_dir": _MACOS_DEST_DIR,
        "hint": (
            "Devices now appear in Live's browser under MIDI Effects > "
            "Max MIDI Effect. Drop Transform onto an existing-notes clip "
            "(Transformations button), Generate onto an empty selection "
            "(Generators button), then call set_miditool_target() to "
            "configure which LivePilot generator handles the request."
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

"""Analyzer MCP tools — real-time spectral analysis and deep LOM access.

29 tools requiring the LivePilot Analyzer M4L device on the master track.
These tools are optional — all core tools work without the device.
"""

from __future__ import annotations

import os

from fastmcp import Context

from ..server import mcp, _identify_port_holder

CAPTURE_DIR = os.path.expanduser("~/Documents/LivePilot/captures")


def _get_spectral(ctx: Context):
    """Get SpectralCache from lifespan context."""
    cache = ctx.lifespan_context.get("spectral")
    if not cache:
        raise ValueError("Spectral cache not initialized — restart the MCP server")
    # Keep the active request context attached so analyzer error paths can
    # distinguish "device missing" from "bridge disconnected".
    setattr(cache, "_livepilot_ctx", ctx)
    return cache


def _get_m4l(ctx: Context):
    """Get M4LBridge from lifespan context."""
    bridge = ctx.lifespan_context.get("m4l")
    if not bridge:
        raise ValueError("M4L bridge not initialized — restart the MCP server")
    return bridge


def _require_analyzer(cache) -> None:
    """Raise a helpful error if the analyzer is not connected."""
    if not cache.is_connected:
        ctx = getattr(cache, "_livepilot_ctx", None)
        try:
            track = (
                ctx.lifespan_context["ableton"].send_command("get_master_track")
                if ctx else {}
            )
        except Exception:
            track = {}

        devices = track.get("devices", []) if isinstance(track, dict) else []
        analyzer_loaded = False
        for device in devices:
            normalized = " ".join(
                str(device.get("name") or "").replace("_", " ").replace("-", " ").lower().split()
            )
            if normalized == "livepilot analyzer":
                analyzer_loaded = True
                break

        if analyzer_loaded:
            holder = _identify_port_holder(9880)
            detail = (
                "LivePilot Analyzer is loaded on the master track, but its UDP bridge is not connected. "
            )
            if holder:
                detail += (
                    "UDP port 9880 is currently held by another LivePilot instance "
                    f"({holder}). Close the other client/server, then retry."
                )
            else:
                detail += "Reload the analyzer device or restart the MCP server."
            raise ValueError(detail)

        raise ValueError(
            "LivePilot Analyzer not detected. "
            "Drag 'LivePilot Analyzer' onto the master track from "
            "Audio Effects > Max Audio Effect."
        )


@mcp.tool()
async def reconnect_bridge(ctx: Context) -> dict:
    """Attempt to reconnect the M4L UDP bridge (port 9880).

    Use this when the bridge was unavailable at server startup (port
    conflict) but is now free. Binds the UDP listener so spectral
    analysis and bridge commands become available without restarting
    the MCP server.
    """
    import asyncio

    bridge_state = ctx.lifespan_context.get("_bridge_state")
    if not bridge_state:
        return {"error": "Bridge state not available — restart the MCP server"}

    if bridge_state["transport"] is not None:
        return {"ok": True, "message": "Bridge already connected on UDP 9880"}

    loop = bridge_state["loop"]
    receiver = bridge_state["receiver"]
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: receiver,
            local_addr=('127.0.0.1', 9880),
        )
        bridge_state["transport"] = transport
        return {"ok": True, "message": "Bridge reconnected on UDP 9880"}
    except OSError:
        holder = _identify_port_holder(9880)
        return {
            "ok": False,
            "error": f"UDP port 9880 still in use{f' (PID {holder})' if holder else ''}. "
                     "Close the other LivePilot instance first.",
        }


@mcp.tool()
def get_master_spectrum(ctx: Context) -> dict:
    """Get 8-band frequency analysis of the master bus.

    Returns band energies: sub (20-60Hz), low (60-200Hz), low_mid (200-500Hz),
    mid (500-2kHz), high_mid (2-4kHz), high (4-8kHz), presence (8-12kHz),
    air (12-20kHz). Values 0.0-1.0.

    Also returns detected key/scale if enough audio has been analyzed.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)

    result = {}
    spectrum = cache.get("spectrum")
    if spectrum:
        result["bands"] = spectrum["value"]
        result["age_ms"] = spectrum["age_ms"]

    key_data = cache.get("key")
    if key_data:
        result["detected_key"] = key_data["value"]

    return result


@mcp.tool()
def get_master_rms(ctx: Context) -> dict:
    """Get real-time RMS and peak levels from the master bus.

    More accurate than LOM meters — includes true RMS (not just peak hold).
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)

    result = {}
    rms = cache.get("rms")
    if rms:
        result["rms"] = rms["value"]
        result["age_ms"] = rms["age_ms"]

    peak = cache.get("peak")
    if peak:
        result["peak"] = peak["value"]

    pitch = cache.get("pitch")
    if pitch:
        result["pitch"] = pitch["value"]

    return result


@mcp.tool()
async def get_detected_key(ctx: Context) -> dict:
    """Get the detected musical key and scale of the current session.

    Uses the Krumhansl-Schmuckler key-finding algorithm on accumulated
    pitch data from the master bus. Needs 4-8 bars of audio to be reliable.
    Returns key (C, C#, D, etc.), scale (major/minor), and confidence
    (number of pitch samples collected).
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)

    # First check the streaming cache for a recent key detection
    key_data = cache.get("key")
    if key_data:
        return key_data["value"]

    # Fall back to querying the bridge directly (key detection runs in JS
    # and may not be forwarded via OSC streaming)
    bridge = _get_m4l(ctx)
    result = await bridge.send_command("get_key")
    if "error" in result:
        return result
    if not result.get("key"):
        return {"error": "Not enough audio analyzed yet. Play 4-8 bars for key detection."}
    return result


@mcp.tool()
async def get_hidden_parameters(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Get ALL parameters for a device, including hidden ones not accessible
    via the standard ControlSurface API.

    Returns parameter name, value, min, max, default, automation state,
    and value string for every parameter — even non-automatable ones.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_hidden_params", track_index, device_index, timeout=15.0)


@mcp.tool()
async def get_automation_state(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Get automation state for all parameters on a device.

    Returns only parameters that HAVE automation:
    - state 1 = automation active (envelope is playing)
    - state 2 = automation overridden (user moved knob manually)

    Use this before writing automation to avoid overwriting existing curves.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_auto_state", track_index, device_index, timeout=10.0)


@mcp.tool()
async def walk_device_tree(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
) -> dict:
    """Walk the full device chain tree including nested racks, drum pads,
    and grouped devices. Returns the complete hierarchy up to 6 levels deep.

    Use this to see inside Instrument Racks, Effect Racks, and Drum Racks
    that the standard get_device_info can't penetrate.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("walk_rack", track_index, device_index)


# ── Phase 2: Sample Operations ─────────────────────────────────────────


@mcp.tool()
async def get_clip_file_path(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """Get the audio file path of a clip on disk.

    Returns the absolute path to the audio file, clip name, and length.
    Only works on audio clips — MIDI clips have no file path.
    Use this to get a path for replace_simpler_sample.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_clip_file_path", track_index, clip_index)


@mcp.tool()
async def replace_simpler_sample(
    ctx: Context,
    track_index: int,
    device_index: int,
    file_path: str,
) -> dict:
    """Load an audio file into a Simpler device by absolute file path.

    Replaces the currently loaded sample. The Simpler must already have
    a sample loaded — this replaces it, it cannot load into an empty Simpler.
    If the Simpler is empty (freshly created with no sample), load a sample
    manually first or use find_and_load_device to load a preset that already
    contains a sample.

    Use get_clip_file_path to get the path of a resampled clip, then pass
    it here to load it into Simpler for slicing.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    result = await bridge.send_command(
        "replace_simpler_sample", track_index, device_index, file_path
    )

    # Validate the response — the bridge may report success even when the
    # sample silently failed to load (e.g., empty Simpler, bad path)
    if "error" in result:
        return result
    if not result.get("sample_loaded"):
        return {
            "error": "Sample may not have loaded. Ensure the Simpler already "
            "has a sample loaded — replace_sample silently fails on empty Simplers."
        }
    return result


@mcp.tool()
async def load_sample_to_simpler(
    ctx: Context,
    track_index: int,
    file_path: str,
    device_index: int = 0,
) -> dict:
    """Load an audio file into a NEW Simpler device on a track.

    This is the full workflow for programmatic sample loading:
    1. Loads a dummy sample via the browser (creates Simpler with a sample)
    2. Replaces the dummy with your audio file
    3. Returns the Simpler ready for slicing/warping

    Use this instead of replace_simpler_sample when the track has no Simpler
    or the Simpler is empty. Works with any audio file path.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)

    # Step 1: Load a sample from the browser to create Simpler with content
    ableton = ctx.lifespan_context["ableton"]
    try:
        search = ableton.send_command("search_browser", {
            "path": "samples",
            "name_filter": "kick",
            "loadable_only": True,
            "max_results": 1,
        })
    except Exception as exc:
        return {"error": f"Browser search failed: {exc}"}
    results = search.get("results", [])
    if not results:
        return {"error": "No samples found in browser to bootstrap Simpler"}

    # Load the dummy sample — Ableton auto-creates Simpler
    uri = results[0]["uri"]
    try:
        ableton.send_command("load_browser_item", {
            "track_index": track_index,
            "uri": uri,
        })
    except Exception as exc:
        return {"error": f"Failed to load bootstrap sample: {exc}"}

    # Step 2: Find the newly created device (it's at the end of the chain)
    try:
        track_info = ableton.send_command("get_track_info", {"track_index": track_index})
    except Exception as exc:
        return {"error": f"Failed to read track after loading sample: {exc}"}
    actual_device_index = len(track_info.get("devices", [])) - 1
    if actual_device_index < 0:
        actual_device_index = 0

    # Step 3: Replace with the desired sample via M4L bridge
    result = await bridge.send_command(
        "replace_simpler_sample", track_index, actual_device_index, file_path
    )
    if "error" in result:
        return result
    if not result.get("sample_loaded"):
        return {"error": "Sample replacement failed after bootstrap"}

    result["method"] = "bootstrap_and_replace"
    return result


@mcp.tool()
async def get_simpler_slices(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
) -> dict:
    """Get slice point positions from a Simpler device.

    Returns each slice's position in frames and seconds, plus sample metadata
    (sample rate, length, playback mode). Use this to understand the rhythmic
    structure of a sliced sample and program MIDI patterns targeting slices.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_simpler_slices", track_index, device_index)


@mcp.tool()
async def crop_simpler(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
) -> dict:
    """Crop a Simpler's sample to the currently active region.

    Destructive — removes audio outside the region. Use undo to revert.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("crop_simpler", track_index, device_index)


@mcp.tool()
async def reverse_simpler(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
) -> dict:
    """Reverse the sample loaded in a Simpler device.

    Can be called again to un-reverse.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("reverse_simpler", track_index, device_index)


@mcp.tool()
async def warp_simpler(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
    beats: int = 4,
) -> dict:
    """Warp a Simpler's sample to fit the specified number of beats.

    The sample will time-stretch to match the project tempo at the given
    beat count. E.g., beats=4 makes it exactly 1 bar at current tempo.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("warp_simpler", track_index, device_index, beats)


# ── Phase 2: Warp Markers ──────────────────────────────────────────────


@mcp.tool()
async def get_warp_markers(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """Get all warp markers from an audio clip.

    Returns each marker's beat_time (position in arrangement) and
    sample_time (position in the original audio file). Use this to
    understand timing, extract groove templates, or prepare for manipulation.
    Only works on audio clips. Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_warp_markers", track_index, clip_index)


@mcp.tool()
async def add_warp_marker(
    ctx: Context,
    track_index: int,
    clip_index: int,
    beat_time: float,
) -> dict:
    """Add a warp marker to an audio clip at the specified beat position.

    Warp markers pin audio to beats, enabling time-stretching of surrounding
    regions. Add at downbeats to lock timing, then move them for tempo changes.
    Only works on audio clips. Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command(
        "add_warp_marker", track_index, clip_index, beat_time
    )


@mcp.tool()
async def move_warp_marker(
    ctx: Context,
    track_index: int,
    clip_index: int,
    old_beat_time: float,
    new_beat_time: float,
) -> dict:
    """Move a warp marker from one beat position to another.

    Changes the tempo of the audio segment between this marker and its
    neighbors. Moving later = slower, moving earlier = faster. Use for
    tape-stop effects, tempo ramps, and groove manipulation.
    Only works on audio clips. Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command(
        "move_warp_marker", track_index, clip_index, old_beat_time, new_beat_time
    )


@mcp.tool()
async def remove_warp_marker(
    ctx: Context,
    track_index: int,
    clip_index: int,
    beat_time: float,
) -> dict:
    """Remove a warp marker from an audio clip at the specified beat.

    Only works on audio clips. Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command(
        "remove_warp_marker", track_index, clip_index, beat_time
    )


# ── Phase 2: Clip & Display ────────────────────────────────────────────


@mcp.tool()
async def scrub_clip(
    ctx: Context,
    track_index: int,
    clip_index: int,
    beat_time: float,
) -> dict:
    """Scrub/preview a clip at a specific beat position.

    Plays audio from that position until stop_scrub is called. Use to
    audition sections, preview slices, or find the right warp marker spot.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command(
        "scrub_clip", track_index, clip_index, beat_time
    )


@mcp.tool()
async def stop_scrub(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """Stop scrubbing a clip. Call after scrub_clip to stop preview.

    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("stop_scrub", track_index, clip_index)


@mcp.tool()
async def get_display_values(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Get human-readable display values for all device parameters.

    Returns the value as shown in Live's UI (e.g., '440 Hz', '-6.0 dB',
    '50 %') instead of raw normalized floats. Skips irrelevant parameters.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_display_values", track_index, device_index, timeout=15.0)


# ── Phase 3: Audio Capture ─────────────────────────────────────────────


@mcp.tool()
async def capture_audio(
    ctx: Context,
    duration_seconds: int = 10,
    source: str = "master",
    filename: str = "",
) -> dict:
    """Capture audio from Ableton Live to a WAV file on disk.

    Records from the specified source (currently 'master') for the given
    duration. Files are written to ~/Documents/LivePilot/captures/.
    If filename is empty, a timestamped name is generated automatically.

    Returns the path to the written file and capture metadata.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)

    if duration_seconds < 1 or duration_seconds > 300:
        raise ValueError("duration_seconds must be between 1 and 300")
    if source not in ("master",):
        raise ValueError(f"Unsupported source '{source}'. Valid: 'master'")

    # Sanitize filename — strip directory components to prevent path traversal
    if filename:
        safe_name = os.path.basename(filename)
        if not safe_name or safe_name != filename:
            raise ValueError(
                f"Filename must not contain path separators or '..' segments: {filename!r}"
            )
        filename = safe_name

    bridge = _get_m4l(ctx)
    # Ensure captures directory exists before sending to bridge
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    duration_ms = duration_seconds * 1000
    result = await bridge.send_capture(
        "capture_audio",
        duration_ms,
        filename,
        timeout=float(duration_seconds + 10),
    )

    # Move captured file from M4L device directory to CAPTURE_DIR
    if result.get("ok") and result.get("file_path"):
        src = result["file_path"]
        # Try common extensions the bridge might produce
        for ext in ("", ".aiff", ".wav", ".aif"):
            src_path = src + ext if not src.endswith(ext) else src
            if os.path.isfile(src_path):
                dst_name = os.path.basename(src_path)
                dst_path = os.path.join(CAPTURE_DIR, dst_name)
                try:
                    import shutil
                    shutil.move(src_path, dst_path)
                    result["file_path"] = dst_path
                except OSError:
                    pass  # Leave in original location if move fails
                break

    return result


@mcp.tool()
async def capture_stop(ctx: Context) -> dict:
    """Stop an in-progress audio capture early.

    Tells the M4L bridge to stop buffer~ recording and resolves the
    in-flight capture_audio call with a partial result (stopped_early=True).
    The partial file is still written to disk by the bridge.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    # Resolve the capture future so send_capture returns cleanly
    await bridge.cancel_capture_future()
    return await bridge.send_command("capture_stop")


# ── Phase 4: FluCoMa Real-Time ───────────────────────────────────────────

PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _flucoma_hint(cache) -> str:
    """Return an error hint if no FluCoMa data has arrived.

    If ANY stream has data, FluCoMa is working and the specific stream just
    hasn't updated yet — return a 'play audio' hint. If NO streams have data,
    FluCoMa may not be installed — return an install hint.
    """
    for key in ("spectral_shape", "mel_bands", "chroma", "loudness"):
        if cache.get(key):
            return "play some audio"
    return "FluCoMa may not be installed. Install via: npx livepilot --setup-flucoma"


@mcp.tool()
def get_spectral_shape(ctx: Context) -> dict:
    """Get 7 real-time spectral descriptors from FluCoMa.

    Returns centroid, spread, skewness, kurtosis, rolloff, flatness, crest.
    Requires FluCoMa package in Max.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    data = cache.get("spectral_shape")
    if not data:
        hint = _flucoma_hint(cache)
        return {"error": f"No spectral shape data — {hint}"}
    return {**data["value"], "age_ms": data["age_ms"]}


@mcp.tool()
def get_mel_spectrum(ctx: Context) -> dict:
    """Get 40-band mel spectrum from FluCoMa (5x resolution of get_master_spectrum).

    Requires FluCoMa package in Max.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    data = cache.get("mel_bands")
    if not data:
        hint = _flucoma_hint(cache)
        return {"error": f"No mel data — {hint}"}
    return {"mel_bands": data["value"], "band_count": len(data["value"]), "age_ms": data["age_ms"]}


@mcp.tool()
def get_chroma(ctx: Context) -> dict:
    """Get 12 pitch class energies from FluCoMa for real-time chord detection.

    Requires FluCoMa package in Max.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    data = cache.get("chroma")
    if not data:
        hint = _flucoma_hint(cache)
        return {"error": f"No chroma data — {hint}"}
    values = data["value"]
    chroma_dict = {PITCH_NAMES[i]: round(v, 3) for i, v in enumerate(values[:12])}
    max_val = max(values[:12]) if values else 0
    dominant = [PITCH_NAMES[i] for i, v in enumerate(values[:12])
                if v >= max_val * 0.5 and max_val > 0.01]
    return {"chroma": chroma_dict, "dominant_pitches": dominant, "age_ms": data["age_ms"]}


@mcp.tool()
def get_onsets(ctx: Context) -> dict:
    """Get real-time onset/transient detection from FluCoMa.

    Requires FluCoMa package in Max.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    data = cache.get("onset")
    if not data:
        hint = _flucoma_hint(cache)
        return {"error": f"No onset data — {hint}"}
    return {**data["value"], "age_ms": data["age_ms"]}


@mcp.tool()
def get_novelty(ctx: Context) -> dict:
    """Get real-time spectral novelty for section boundary detection from FluCoMa.

    Requires FluCoMa package in Max.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    data = cache.get("novelty")
    if not data:
        hint = _flucoma_hint(cache)
        return {"error": f"No novelty data — {hint}"}
    return {**data["value"], "age_ms": data["age_ms"]}


@mcp.tool()
def get_momentary_loudness(ctx: Context) -> dict:
    """Get EBU R128 momentary LUFS + true peak from FluCoMa.

    Real-time LUFS metering — industry standard. Complements get_master_rms.
    Requires FluCoMa package in Max.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    data = cache.get("loudness")
    if not data:
        hint = _flucoma_hint(cache)
        return {"error": f"No loudness data — {hint}"}
    return {**data["value"], "age_ms": data["age_ms"]}


@mcp.tool()
def check_flucoma(ctx: Context) -> dict:
    """Check if FluCoMa is installed and sending data."""
    cache = _get_spectral(ctx)
    streams = {}
    for key in ("spectral_shape", "mel_bands", "chroma", "onset", "novelty", "loudness"):
        streams[key] = cache.get(key) is not None
    active = sum(1 for v in streams.values() if v)
    return {"flucoma_available": active > 0, "active_streams": active, "streams": streams}

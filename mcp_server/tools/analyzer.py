"""Analyzer MCP tools — real-time spectral analysis and deep LOM access.

30 tools requiring the LivePilot Analyzer M4L device on the master track.
These tools are optional — all core tools work without the device.

Helpers live in ``_analyzer_engine/`` (context accessors, Simpler
post-load hygiene, FluCoMa hint formatting). This file contains the
``@mcp.tool()`` surface only — keeping decorator order stable was
important for BUG-C1's refactor.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from fastmcp import Context

from ..server import mcp, _identify_port_holder
from ._analyzer_engine import (
    PITCH_NAMES,
    _filename_stem,
    _flucoma_hint,
    _get_m4l,
    _get_spectral,
    _is_warped_loop,
    _require_analyzer,
    _simpler_post_load_hygiene,
)

logger = logging.getLogger(__name__)

CAPTURE_DIR = os.path.expanduser("~/Documents/LivePilot/captures")


# Live 12 Simpler Slice mode maps slice N to MIDI pitch 36+N (C1 base).
# This is NOT exposed by the Remote Script API and is a common source of
# silent audio bugs (BUG-F2). See feedback_analyze_slices_before_programming
# memory for context.
SIMPLER_SLICE_BASE_PITCH = 36


def _enrich_slice_response(response: Optional[dict]) -> Optional[dict]:
    """Add base_midi_pitch field + per-slice midi_pitch to bridge response (BUG-F2).

    The Remote Script returns slice indices only. Users then have to know
    that slice N plays at MIDI pitch 36+N — a fact that's undocumented in
    both Ableton's and LivePilot's public API. This enrichment makes the
    mapping explicit so MIDI pattern generation doesn't silently produce
    out-of-range notes.
    """
    if response is None:
        return None
    enriched = dict(response)
    enriched["base_midi_pitch"] = SIMPLER_SLICE_BASE_PITCH
    slices = enriched.get("slices") or []
    # BUG-audit-M2: fall back to positional index when the bridge response
    # omits the `index` field (protects against bridge version skew).
    enriched["slices"] = [
        {**s, "midi_pitch": SIMPLER_SLICE_BASE_PITCH + s.get("index", i)}
        for i, s in enumerate(slices)
    ]
    return enriched


def _live_caps(ctx, *, force_refresh: bool = False):
    """Read (or lazily compute + cache) LiveVersionCapabilities on the context.

    On first successful probe, caches the result in
    ``ctx.lifespan_context["_live_caps"]``. Subsequent calls short-circuit
    to the cache unless ``force_refresh=True``.

    If Ableton is unreachable OR returns no ``live_version`` field,
    returns a conservative (12, 0, 0) fallback BUT does NOT cache it.
    Caching the fallback pins the whole session to the oldest capability
    tier even after Live finishes initializing — mirrors the pattern in
    remote_script/LivePilot/version_detect.py::get_live_version, where
    the same bug was fixed on the Remote Script side.
    """
    from mcp_server.runtime.live_version import LiveVersionCapabilities

    lsc = ctx.lifespan_context
    if not force_refresh:
        cached = lsc.get("_live_caps")
        if cached is not None:
            return cached

    ableton = lsc.get("ableton")
    if ableton is None:
        logger.debug("_live_caps: no ableton in lifespan — returning 12.0.0 fallback (uncached)")
        return LiveVersionCapabilities.from_version_string("12.0.0")

    try:
        info = ableton.send_command("get_session_info") or {}
    except Exception as exc:
        logger.debug("_live_caps: get_session_info raised %s — returning 12.0.0 fallback (uncached)", exc)
        return LiveVersionCapabilities.from_version_string("12.0.0")

    version_str = info.get("live_version")
    if not version_str:
        logger.debug("_live_caps: get_session_info returned no live_version — returning 12.0.0 fallback (uncached)")
        return LiveVersionCapabilities.from_version_string("12.0.0")

    caps = LiveVersionCapabilities.from_version_string(version_str)
    lsc["_live_caps"] = caps
    logger.debug("_live_caps: cached %s (tier=%s)", version_str, caps.capability_tier)
    return caps


async def _try_native_replace_sample(
    ctx,
    track_index: int,
    device_index: int,
    file_path: str,
    chain_index: Optional[int] = None,
    nested_device_index: Optional[int] = None,
):
    """Attempt the Live 12.4+ native SimplerDevice.replace_sample path.

    Returns the remote-script response dict on success, or None if the
    native path is unavailable (pre-12.4) or failed (caller should fall
    back to the M4L-bridge path).

    When `chain_index` is provided, the remote script walks into
    `track.devices[device_index].chains[chain_index].devices[
    nested_device_index or 0]` — this is how Drum Rack pad-by-pad
    construction is unblocked (BUG-#1 in docs/2026-04-22-bugs-discovered.md).

    A native "failure" is any of: gate closed, dispatch exception, non-dict
    response, error field present, or missing sample_loaded flag. Each
    failure path records a skip reason on ``ctx.lifespan_context[
    "_native_replace_skip_reason"]`` so callers can surface it in the
    bridge-path response and logs at INFO for live debugging.
    """
    def _record_skip(reason: str) -> None:
        ctx.lifespan_context["_native_replace_skip_reason"] = reason
        logger.info("native replace_sample skipped — %s", reason)

    ctx.lifespan_context.pop("_native_replace_skip_reason", None)

    caps = _live_caps(ctx)
    if not caps.has_replace_sample_native:
        _record_skip("gate_closed: tier=%s (need collaborative/12.4+)" % caps.capability_tier)
        return None
    ableton = ctx.lifespan_context["ableton"]
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "file_path": file_path,
    }
    if chain_index is not None:
        params["chain_index"] = int(chain_index)
    if nested_device_index is not None:
        params["nested_device_index"] = int(nested_device_index)
    try:
        resp = ableton.send_command("replace_sample_native", params)
    except Exception as exc:
        _record_skip("dispatch_raised: %s: %s" % (type(exc).__name__, exc))
        return None
    if not isinstance(resp, dict):
        _record_skip("non_dict_response: type=%s" % type(resp).__name__)
        return None
    if "error" in resp:
        _record_skip("remote_error: code=%s msg=%s" % (resp.get("code"), resp.get("error")))
        return None
    if not resp.get("sample_loaded"):
        _record_skip("missing_sample_loaded: resp=%s" % resp)
        return None
    return resp


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
async def get_master_spectrum(
    ctx: Context,
    window_ms: int = 0,
    samples: int = 0,
    sub_detail: bool = False,
) -> dict:
    """Get 9-band frequency analysis of the master bus.

    Returns band energies (fffb~ center frequencies shown in parens):
      sub_low   20-60 Hz   (~35 Hz center)  — kick fundamentals, Villalobos subs
      sub       60-120 Hz  (~85 Hz)         — 808s, sub-bass body
      low       120-250 Hz (~175 Hz)        — bass body, warmth
      low_mid   250-500 Hz (~350 Hz)        — mud zone, male vocal lows
      mid       500-1 kHz  (~700 Hz)        — vocal presence, snare body
      high_mid  1-2 kHz    (~1.4 kHz)       — consonants, pick attack
      high      2-4 kHz    (~2.8 kHz)       — presence, vocal intelligibility
      presence  4-8 kHz    (~5.6 kHz)       — cymbal definition, air of breath
      air       8-20 kHz   (~12 kHz)        — shimmer, sparkle
    Values 0.0-1.0.

    Older .amxd builds (pre-v1.16) emit the legacy 8-band layout without the
    explicit `sub_low` split — the server auto-detects band count from the OSC
    payload and picks the right name set. Re-freeze the Max device to get the
    9-band resolution.

    Also returns detected key/scale if enough audio has been analyzed.
    Requires LivePilot Analyzer on master track.

    BUG-2026-04-22#6 fix — windowed averaging:
      Kick transients make single snapshots swing wildly (0.45 → 0.05 →
      0.16 within a bar). When mixing, you want a STABLE band profile,
      not an instantaneous frame. Pass `window_ms` to sample the cache
      over a time window and mean-pool:
        - window_ms=500 → sample over 500ms (common for mix reads)
        - window_ms=2000 → sample over 2 seconds (long-tail stability)
      When `window_ms=0` (default), returns a single instantaneous snapshot
      — the legacy behavior. `samples` overrides the auto-computed sample
      count (defaults to window_ms / 50, minimum 3).

    The sampled bands are also returned as `bands_min`, `bands_max` and
    `bands_std` so callers can see variance within the window — useful
    for detecting transient-heavy content vs. sustained material.

    BUG-2026-04-22#15 fix — sub-band resolution:
      Pass `sub_detail=True` to attach a `sub_detail` dict with three
      finer buckets: `sub_deep` (20-45 Hz), `sub_mid` (45-60 Hz),
      `sub_high` (60-80 Hz). Derived from the FluCoMa mel spectrum
      (40 bands) rather than the 9-band cache, so it requires FluCoMa
      to be active. When FluCoMa is unavailable, sub_detail is omitted
      with a `sub_detail_warning` field explaining why.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)

    if window_ms and window_ms > 0:
        # Windowed sampling — mean-pool N readings across the window.
        # Each cache read is ~free; we sleep between reads to let the
        # analyzer update its internal buffer.
        if window_ms > 10000:
            return {"error": "window_ms must be <= 10000 (10 seconds)"}
        n = samples if samples > 0 else max(3, window_ms // 50)
        n = min(n, 100)
        interval = (window_ms / 1000.0) / max(n - 1, 1)
        bands_acc: list[dict] = []
        for i in range(n):
            snap = cache.get("spectrum")
            if snap and snap.get("value"):
                bands_acc.append(snap["value"])
            if i < n - 1:
                await asyncio.sleep(interval)
        if not bands_acc:
            return {
                "error": "No spectrum data captured — analyzer may be stale",
                "analyzer_hint": "Ensure LivePilot_Analyzer is active on master",
            }
        # Aggregate: mean / min / max / stddev per band.
        keys = set()
        for s in bands_acc:
            keys.update(s.keys())
        bands_mean = {}
        bands_min = {}
        bands_max = {}
        bands_std = {}
        for k in keys:
            vals = [s.get(k, 0.0) for s in bands_acc]
            mean = sum(vals) / len(vals)
            bands_mean[k] = round(mean, 4)
            bands_min[k] = round(min(vals), 4)
            bands_max[k] = round(max(vals), 4)
            if len(vals) > 1:
                var = sum((v - mean) ** 2 for v in vals) / len(vals)
                bands_std[k] = round(var ** 0.5, 4)
            else:
                bands_std[k] = 0.0
        result = {
            "bands": bands_mean,
            "bands_min": bands_min,
            "bands_max": bands_max,
            "bands_std": bands_std,
            "window_ms": window_ms,
            "samples_collected": len(bands_acc),
        }
        key_data = cache.get("key")
        if key_data:
            result["detected_key"] = key_data["value"]
        if sub_detail:
            _attach_sub_detail(cache, result)
        return result

    # Legacy instantaneous path
    result = {}
    spectrum = cache.get("spectrum")
    if spectrum:
        result["bands"] = spectrum["value"]
        result["age_ms"] = spectrum["age_ms"]

    key_data = cache.get("key")
    if key_data:
        result["detected_key"] = key_data["value"]
    if sub_detail:
        _attach_sub_detail(cache, result)

    return result


def _attach_sub_detail(cache, result: dict) -> None:
    """Compute finer sub-band breakdown (20-45, 45-60, 60-80 Hz) from
    FluCoMa's 40-band mel spectrum and attach to the result dict.

    Mel band edges are perceptual, not linear Hz — we map approximately:
    with a standard 40-band mel filterbank from 0-20kHz, the first
    ~4 bands cover 0-80 Hz and are distributed roughly:
      band 0: ~0-25 Hz
      band 1: ~25-45 Hz
      band 2: ~45-65 Hz
      band 3: ~65-90 Hz
    We use these mappings as approximations; exact cutoffs depend on
    FluCoMa's filterbank config but this is tight enough for mixing
    decisions (the question is "is energy in the 30 Hz or 60 Hz range?").
    """
    mel_snap = cache.get("mel_bands")
    if not mel_snap or not mel_snap.get("value"):
        result["sub_detail_warning"] = (
            "FluCoMa mel spectrum not available — sub_detail requires "
            "FluCoMa active on the M4L analyzer. Use check_flucoma to diagnose."
        )
        return
    mel_bands = mel_snap["value"]
    if not isinstance(mel_bands, list) or len(mel_bands) < 4:
        result["sub_detail_warning"] = (
            f"Mel spectrum has {len(mel_bands) if isinstance(mel_bands, list) else 0} "
            "bands — need at least 4 for sub_detail decomposition."
        )
        return

    def _mean(indices):
        vals = [float(mel_bands[i]) for i in indices if i < len(mel_bands)]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    result["sub_detail"] = {
        "sub_deep": _mean([0, 1]),      # ~0-45 Hz (kick fundamental)
        "sub_mid": _mean([2]),          # ~45-60 Hz (808 body / kick upper)
        "sub_high": _mean([3]),         # ~60-80 Hz (bass guitar low, sub-bass crossover)
        "age_ms": mel_snap.get("age_ms"),
        "source": "flucoma_mel_40",
    }


def _sanitize_pitch(pitch: Optional[dict]) -> Optional[dict]:
    """Validate a pitch reading from the M4L analyzer (BUG-F1).

    The polyphonic pitch detector can emit out-of-range MIDI notes
    (e.g., 319, -50, 128+) when it can't latch onto a single
    fundamental — typical for dense mixes. The amplitude field is the
    reliable confidence signal: if the detector was sure of its
    reading, amplitude is non-zero.

    Returns the original dict if the reading is usable, None otherwise.
    """
    if not pitch:
        return None
    amplitude = pitch.get("amplitude")
    midi_note = pitch.get("midi_note")
    if amplitude is None or amplitude <= 0:
        return None
    if midi_note is None or midi_note < 0 or midi_note > 127:
        return None
    return pitch


@mcp.tool()
def get_master_rms(ctx: Context) -> dict:
    """Get real-time RMS and peak levels from the master bus.

    More accurate than LOM meters — includes true RMS (not just peak hold).
    Pitch readings are validated: the field is only present when the
    polyphonic pitch detector produced a reading with non-zero
    amplitude and a MIDI note in [0, 127] (BUG-F1).
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

    pitch_entry = cache.get("pitch")
    if pitch_entry:
        clean = _sanitize_pitch(pitch_entry.get("value"))
        if clean is not None:
            result["pitch"] = clean

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

# ── Sample loading helpers (P0-1, P1-1, P2-6 fixes) ────────────────────────
#
# Critical bug 2026-04-14 (see docs/2026-04-14-bugs-discovered.md):
#
# The M4L bridge's `replace_simpler_sample` command can report success even
# when the sample is still the bootstrap placeholder. The Simpler's display
# name also does NOT refresh after a replace. After loading, Simpler's Snap
# parameter is ON by default which causes the Sample Start position to
# snap to a location outside the new sample's valid audio — resulting in
# silent playback.
#
# The fixes below:
#   1. After replace, verify by reading the actual device name via
#      get_track_info and comparing to the expected filename stem. If the
#      name doesn't match, return a clear error so the caller doesn't
#      silently ship the wrong audio.
#   2. Auto-set Snap=0 to disarm the zero-crossing snap that breaks playback.
#   3. For WARPED LOOPS (detected by "NNbpm" in the filename), set
#      S Start=0, S Length=1, S Loop On=1 so the full loop plays in its
#      musical phrasing. For ONE-SHOTS, leave defaults alone.

# _BPM_IN_FILENAME_RE, _is_warped_loop, _filename_stem, and the
# _simpler_post_load_hygiene coroutine now live in
# ``_analyzer_engine/sample.py`` — re-exported via this module's imports
# at the top of the file so tests importing them by name still resolve.


@mcp.tool()
async def replace_simpler_sample(
    ctx: Context,
    track_index: int,
    device_index: int,
    file_path: str,
    chain_index: Optional[int] = None,
    nested_device_index: Optional[int] = None,
) -> dict:
    """Load an audio file into a Simpler device by absolute file path.

    Replaces the currently loaded sample. The Simpler must already have
    a sample loaded — this replaces it, it cannot load into an empty Simpler.
    If the Simpler is empty (freshly created with no sample), load a sample
    manually first or use find_and_load_device to load a preset that already
    contains a sample.

    **Prefer `load_browser_item(track, uri)` when possible** — see P0-1 in
    docs/2026-04-14-bugs-discovered.md. The M4L bridge's replace path can
    silently keep the bootstrap placeholder in some conditions; this tool
    now verifies by reading back the device name and will return an error
    if the replace didn't actually take effect.

    Nested addressing (Live 12.4+ only, BUG-#1 fix from 2026-04-22):
      - When `chain_index` is provided, the device is resolved at
        `track.devices[device_index].chains[chain_index]
         .devices[nested_device_index or 0]`. This is how Drum Rack
        pad-by-pad construction works — see `add_drum_rack_pad` for the
        high-level workflow.
      - chain_index is only honored by the native 12.4 path; the M4L
        bridge fallback cannot resolve nested paths.

    Also auto-applies post-load hygiene:
      - Sets Simpler Snap=0 (required for playback after replace)
      - For warped loops (filename contains 'NNbpm'), sets S Start=0,
        S Length=1, S Loop On=1

    Use get_clip_file_path to get the path of a resampled clip, then pass
    it here to load it into Simpler for slicing.
    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    ableton = ctx.lifespan_context["ableton"]

    # Live 12.4+: prefer the native SimplerDevice.replace_sample path.
    native = await _try_native_replace_sample(
        ctx, track_index, device_index, file_path,
        chain_index=chain_index, nested_device_index=nested_device_index,
    )
    if native is not None:
        hygiene = await _simpler_post_load_hygiene(
            bridge, ableton, track_index, device_index, file_path
        )
        if not hygiene.get("verified"):
            return hygiene
        result = dict(native)
        result.update(hygiene)
        result["method"] = "native_12_4"  # preserved in case hygiene ever adds its own key
        return result

    # Pre-12.4 fallback: M4L bridge path (unchanged behavior).
    skip_reason = ctx.lifespan_context.get("_native_replace_skip_reason")
    result = await bridge.send_command(
        "replace_simpler_sample", track_index, device_index, file_path
    )

    if "error" in result:
        return result
    if not result.get("sample_loaded"):
        return {
            "error": "Sample may not have loaded. Ensure the Simpler already "
            "has a sample loaded — replace_sample silently fails on empty Simplers."
        }

    hygiene = await _simpler_post_load_hygiene(
        bridge, ableton, track_index, device_index, file_path
    )
    if not hygiene.get("verified"):
        return hygiene

    result.update(hygiene)
    result["method"] = "bridge_m4l"
    if skip_reason:
        result["native_skip_reason"] = skip_reason
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
    3. Applies post-load hygiene (Snap=0, loop defaults for warped loops)
    4. Verifies by reading back the device name — returns an error if
       the Simpler still has the bootstrap placeholder (P0-1 guard)

    Use this instead of replace_simpler_sample when the track has no Simpler
    or the Simpler is empty. Works with any audio file path.

    **For files that exist in Ableton's browser index** (Samples, User Library,
    Packs), PREFER `load_browser_item(track, uri)` — it goes through Ableton's
    native loading path and is more reliable. This tool is a workaround for
    files that aren't browser-indexed.

    Requires LivePilot Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    ableton = ctx.lifespan_context["ableton"]

    # Live 12.4+: create an empty Simpler via insert_device, then use the
    # native replace_sample path. Skips the dummy-sample bootstrap entirely.
    caps = _live_caps(ctx)
    if caps.has_replace_sample_native:
        try:
            ins = ableton.send_command("insert_device", {
                "track_index": track_index,
                "device_name": "Simpler",
            })
        except Exception:
            ins = None
        if isinstance(ins, dict) and "error" not in ins:
            actual_device_index = ins.get("device_index", device_index)
            native = await _try_native_replace_sample(
                ctx, track_index, actual_device_index, file_path
            )
            if native is not None:
                hygiene = await _simpler_post_load_hygiene(
                    bridge, ableton, track_index, actual_device_index, file_path
                )
                if not hygiene.get("verified"):
                    return hygiene
                result = dict(native)
                result.update(hygiene)
                result["method"] = "native_12_4"
                result["device_index"] = actual_device_index
                result["track_index"] = track_index
                return result
        # Fall through to the legacy bootstrap path below on any failure.

    # Step 1: Load a sample from the browser to create Simpler with content
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

    # Step 4: Verify by reading back the device name (P0-1 guard)
    hygiene = await _simpler_post_load_hygiene(
        bridge, ableton, track_index, actual_device_index, file_path
    )
    if not hygiene.get("verified"):
        return hygiene

    result.update(hygiene)
    result["method"] = "bootstrap_and_replace"
    result["device_index"] = actual_device_index  # additive — for step-result binding
    result["track_index"] = track_index
    return result


@mcp.tool()
async def add_drum_rack_pad(
    ctx: Context,
    track_index: int,
    pad_note: int,
    file_path: str,
    rack_device_index: Optional[int] = None,
    chain_name: Optional[str] = None,
) -> dict:
    """Add a new pad (chain) to a Drum Rack and load a sample into it.

    **BUG-2026-04-22#1 FIX** — this is the tool that was missing.
    Previously `load_browser_item` replaced the existing chain on repeat
    calls, and `load_sample_to_simpler` couldn't address nested paths.
    This single tool does the full drum-rack pad build atomically:

      1. Locates the Drum Rack on the track (auto-finds if
         `rack_device_index` is None — searches for class_name containing
         "DrumGroupDevice").
      2. Inserts a new chain on the rack (`insert_rack_chain`).
      3. Assigns the chain's trigger note (`set_drum_chain_note`).
      4. Inserts an empty Simpler into the chain (`insert_device` with
         `chain_index`).
      5. Calls the native Live 12.4 `replace_sample_native` with nested
         addressing to load the sample.
      6. Sets Snap=0 post-load (playback hygiene).

    Requires Live 12.4+ for step 5. On earlier versions returns an error
    directing the caller to the bridge-based workaround.

    track_index:       track containing the Drum Rack
    pad_note:          MIDI note for the pad (0..127). Standard drum map:
                       36=Kick, 38=Snare, 42=Closed HH, 46=Open HH.
    file_path:         absolute path to the audio file
    rack_device_index: optional device_index of the Drum Rack on the track.
                       If None, auto-detects the first Drum Rack.
    chain_name:        optional display name for the new chain.

    Returns: {
      "ok": bool,
      "track_index": int,
      "rack_device_index": int,
      "chain_index": int,
      "pad_note": int,
      "nested_device_index": int,   # where the Simpler landed
      "device_name": str,
      "method": "native_12_4",
    }
    """
    # _simpler_post_load_hygiene is already imported at module scope
    # (line 29). Do not re-import inline — the earlier inline form used
    # the wrong relative path (..; should've been .) and crashed at
    # runtime with "No module named 'mcp_server._analyzer_engine'".
    ableton = ctx.lifespan_context["ableton"]
    caps = _live_caps(ctx)
    if not caps.has_replace_sample_native:
        return {
            "ok": False,
            "error": (
                "add_drum_rack_pad requires Live 12.4+ for native nested "
                "sample loading. Detected tier: " + caps.capability_tier +
                ". Upgrade to Live 12.4 or use the legacy separate-tracks "
                "workflow described in docs/2026-04-22-bugs-discovered.md."
            ),
        }

    if not (0 <= pad_note <= 127):
        return {"ok": False, "error": "pad_note must be 0..127"}
    if not file_path or not isinstance(file_path, str):
        return {"ok": False, "error": "file_path (absolute path) is required"}

    # Step 1: locate the Drum Rack if not provided.
    if rack_device_index is None:
        try:
            info = ableton.send_command(
                "get_track_info", {"track_index": track_index},
            )
        except Exception as exc:
            return {"ok": False, "error": f"get_track_info failed: {exc}"}
        devices = info.get("devices", []) if isinstance(info, dict) else []
        found_idx = None
        for idx, d in enumerate(devices):
            class_name = str(d.get("class_name") or "")
            if "DrumGroup" in class_name or class_name == "DrumGroupDevice":
                found_idx = idx
                break
        if found_idx is None:
            return {
                "ok": False,
                "error": (
                    "No Drum Rack found on track. Pass `rack_device_index` "
                    "explicitly, or use `insert_device('Drum Rack')` first."
                ),
            }
        rack_device_index = found_idx

    # Step 2: insert a new chain on the rack.
    try:
        chain_result = ableton.send_command("insert_rack_chain", {
            "track_index": track_index,
            "device_index": rack_device_index,
            "position": -1,  # append to end
        })
    except Exception as exc:
        return {"ok": False, "error": f"insert_rack_chain failed: {exc}"}
    if not isinstance(chain_result, dict) or "error" in chain_result:
        return {
            "ok": False,
            "error": f"insert_rack_chain returned: {chain_result}",
        }
    chain_index = int(chain_result.get("chain_index", chain_result.get("index", 0)))

    # Step 3: assign pad note to the new chain.
    try:
        note_result = ableton.send_command("set_drum_chain_note", {
            "track_index": track_index,
            "device_index": rack_device_index,
            "chain_index": chain_index,
            "note": pad_note,
        })
    except Exception as exc:
        return {"ok": False, "error": f"set_drum_chain_note failed: {exc}"}
    if isinstance(note_result, dict) and "error" in note_result:
        return {"ok": False, "error": f"set_drum_chain_note: {note_result['error']}"}

    # Step 4: insert an empty Simpler into the chain.
    try:
        insert_result = ableton.send_command("insert_device", {
            "track_index": track_index,
            "device_index": rack_device_index,
            "chain_index": chain_index,
            "device_name": "Simpler",
        })
    except Exception as exc:
        return {"ok": False, "error": f"insert_device(Simpler, chain) failed: {exc}"}
    if not isinstance(insert_result, dict) or "error" in insert_result:
        return {
            "ok": False,
            "error": f"insert_device into chain failed: {insert_result}",
        }
    nested_idx = int(insert_result.get("device_index", 0))

    # Step 5: replace_sample_native with nested addressing.
    native = await _try_native_replace_sample(
        ctx,
        track_index=track_index,
        device_index=rack_device_index,
        file_path=file_path,
        chain_index=chain_index,
        nested_device_index=nested_idx,
    )
    if native is None:
        return {
            "ok": False,
            "error": "Native replace_sample failed — see logs for reason",
            "track_index": track_index,
            "rack_device_index": rack_device_index,
            "chain_index": chain_index,
            "nested_device_index": nested_idx,
        }

    # Step 6: apply chain name (wired to the new set_chain_name handler)
    applied_name = None
    if chain_name:
        try:
            rename_result = ableton.send_command("set_chain_name", {
                "track_index": track_index,
                "device_index": rack_device_index,
                "chain_index": chain_index,
                "name": chain_name,
            })
            if isinstance(rename_result, dict) and "name" in rename_result:
                applied_name = rename_result["name"]
        except Exception as exc:
            logger.debug("set_chain_name skipped: %s", exc)

    return {
        "ok": True,
        "track_index": track_index,
        "rack_device_index": rack_device_index,
        "chain_index": chain_index,
        "pad_note": pad_note,
        "nested_device_index": nested_idx,
        "device_name": "Simpler",
        "method": native.get("method", "native_12_4"),
        "file_path": file_path,
        "chain_name": applied_name,
    }


@mcp.tool()
async def get_simpler_slices(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
) -> dict:
    """Get slice point positions from a Simpler device.

    Returns each slice's position in frames and seconds, the MIDI pitch
    that triggers it (slice 0 = C1 / MIDI 36, slice 1 = C#1 / MIDI 37, etc.
    per BUG-F2), plus sample metadata (sample rate, length, playback mode).

    **Always use the returned `midi_pitch` when programming MIDI notes to
    trigger slices.** The Live 12 Simpler Slice-mode base note is C1,
    NOT C3 — writing notes at pitch 60+ on a sample with <24 slices
    triggers nothing and produces silent output.

    Use this to understand the rhythmic structure of a sliced sample
    and program MIDI patterns targeting slices. Requires LivePilot
    Analyzer on master track.
    """
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    raw = await bridge.send_command("get_simpler_slices", track_index, device_index)
    return _enrich_slice_response(raw)


@mcp.tool()
async def classify_simpler_slices(
    ctx: Context,
    track_index: int,
    device_index: int = 0,
    file_path: Optional[str] = None,
) -> dict:
    """Classify each Simpler slice as KICK / SNARE / HAT / ghost via FFT analysis.

    Reads slice positions via ``get_simpler_slices``, loads the backing
    WAV file, and runs 4-band spectral classification on each segment.
    Returns the enriched slice list with a ``label`` field per entry
    plus feature breakdown (peak, rms, sub_pct, low_pct, mid_pct,
    high_pct).

    **Always run this before programming drum patterns on a sliced
    break.** Slice content depends on transient detection order in the
    source audio — slice 0 is NOT guaranteed to be a kick. Assuming
    drum-rack convention produces wrong grooves that take iterations to
    diagnose (see 2026-04-18 creative session for the canonical case).

    Classification rules (validated on "Break Ghosts 90 bpm"):
      - KICK: sub+low >= 45%, high < 40%
      - HAT: high >= 70% AND mid < 25% (thin metal disc = no drum body)
      - SNARE: mid >= 25% AND high >= 40% AND peak >= 0.6 (broadband loud)
      - ghost: peak < 0.35

    Parameters:
      track_index, device_index: the Simpler to analyze
      file_path: (optional) explicit WAV path. If omitted, the bridge
        resolves it automatically via ``get_simpler_file_path``
        (v1.23.3+). Pass explicitly only when running against an .amxd
        freeze that predates the case (returns the bridge error string
        in that case so the caller knows to re-freeze).

    Returns: dict with ``slices`` list. Each slice entry has:
      index, frame, seconds, midi_pitch (36+index), label, peak, rms,
      sub_pct, low_pct, mid_pct, high_pct.

    Requires LivePilot Analyzer on master track.
    """
    import soundfile as sf

    from ..sample_engine.slice_classifier import classify_slices

    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)

    # 1. Get slice positions
    raw_slices = await bridge.send_command(
        "get_simpler_slices", track_index, device_index
    )
    enriched = _enrich_slice_response(raw_slices)
    if enriched is None:
        return {"error": "Bridge returned no slice data"}

    # 2. Resolve file path via Remote Script TCP path (v1.23.3+ — closes
    # the v1.12 follow-up). Reads ``device.sample.file_path`` directly
    # via Python LOM, more reliable than the M4L bridge UDP round-trip
    # (which surfaced a chunked-response correlation issue under live
    # testing). The bridge case `get_simpler_file_path` is still
    # registered as a forward-compat fallback for environments where
    # Remote Script is unavailable.
    wav_path = file_path
    resolve_error: str | None = None
    if not wav_path:
        ableton = ctx.request_context.lifespan_context.get("ableton")
        if ableton is not None:
            try:
                rs_resp = ableton.send_command(
                    "get_simpler_file_path",
                    {"track_index": track_index, "device_index": device_index},
                )
                if isinstance(rs_resp, dict):
                    wav_path = rs_resp.get("file_path")
                    resolve_error = rs_resp.get("error")
            except Exception as exc:  # noqa: BLE001
                resolve_error = f"remote_script unreachable: {exc}"
                wav_path = None
        else:
            resolve_error = "no ableton TCP connection"

        # Fallback: try the M4L bridge if Remote Script didn't yield a path.
        # Useful if a stale Remote Script install lacks the new handler
        # (the user can call reload_handlers to refresh without restart).
        if not wav_path:
            try:
                bridge_resp = await bridge.send_command(
                    "get_simpler_file_path", track_index, device_index
                )
                if isinstance(bridge_resp, dict):
                    bridge_path = bridge_resp.get("file_path")
                    if bridge_path:
                        wav_path = bridge_path
                        resolve_error = None
            except Exception:  # noqa: BLE001 — defensive
                pass

    if not wav_path:
        return {
            **enriched,
            "error": (
                resolve_error
                or "No file_path available — pass file_path= explicitly."
            ),
        }

    # 3. Load WAV and build frame boundaries
    try:
        audio, sr = sf.read(wav_path)
    except (sf.LibsndfileError, sf.SoundFileError, RuntimeError, OSError) as exc:
        # BUG-audit-C3: corrupt / missing / non-audio files must return a
        # structured error dict instead of raising through the MCP framework
        # (inconsistent with every other tool in this module).
        return {
            **enriched,
            "error": f"Could not load WAV at {wav_path!r}: {exc}",
        }
    slices = enriched["slices"]
    frame_boundaries = [s["frame"] for s in slices] + [len(audio)]

    # 4. Classify
    classifications = classify_slices(audio, sr, frame_boundaries)

    # 5. Merge classification into each slice entry
    merged_slices = []
    for slice_entry, features in zip(slices, classifications):
        merged_slices.append({
            **slice_entry,
            "label": features["label"],
            "peak": features["peak"],
            "rms": features["rms"],
            "sub_pct": features["sub_pct"],
            "low_pct": features["low_pct"],
            "mid_pct": features["mid_pct"],
            "high_pct": features["high_pct"],
        })

    enriched["slices"] = merged_slices
    enriched["classifier_version"] = "v1.0"
    return enriched


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
#
# PITCH_NAMES + _flucoma_hint now live in ``_analyzer_engine/flucoma.py``
# and are re-exported via the top-of-file imports for tests/subclassers.


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
async def verify_device_health(
    ctx: Context,
    track_index: int,
    test_midi_note: int = 60,
    test_velocity: int = 100,
    test_duration_ms: int = 300,
    threshold: float = 0.005,
) -> dict:
    """Fire a test MIDI note at a track's instrument and check for output.

    BUG-2026-04-22#19 fix — parameter_count alone can't tell you whether
    an AU/VST is alive. Plenty of "loaded" plugins return 19 params and
    silence. This tool does the real-world check:

      1. Snapshot the track meter.
      2. Emit a MIDI note at the specified pitch/velocity.
      3. Sample the track meter for `test_duration_ms` (peak across samples).
      4. Compare the peak to a threshold; report alive vs dead.

    The meter readout is taken with `get_track_meters(samples=N)` so the
    BUG-#7 "left=right=0 while level>0" artifact can't cause false negatives.

    track_index:      track with the instrument to verify
    test_midi_note:   pitch to fire (default C3 / 60 — safe for most samples)
    test_velocity:    1-127 (default 100)
    test_duration_ms: capture window for the meter (default 300ms)
    threshold:        peak level below which the device is considered dead
                      (default 0.005 — roughly -46 dBFS)

    Returns: {
      "ok": bool,
      "alive": bool,
      "peak_level": float,
      "threshold": float,
      "samples_taken": int,
      "hint": str,     # actionable advice when dead
    }

    Requires LivePilot Analyzer on master track and a playable instrument
    on the target track. Prefer this over trying to eyeball parameter_count.
    """
    ableton = ctx.lifespan_context["ableton"]

    # Bound test_duration to something humane
    if test_duration_ms < 100:
        test_duration_ms = 100
    if test_duration_ms > 2000:
        test_duration_ms = 2000
    if not 1 <= test_velocity <= 127:
        return {"ok": False, "error": "test_velocity must be 1-127"}
    if not 0 <= test_midi_note <= 127:
        return {"ok": False, "error": "test_midi_note must be 0-127"}

    # Fire the test note via the remote script's play_note helper. Fall back
    # to a raw MIDI event if the helper isn't available.
    fired = False
    try:
        resp = ableton.send_command("fire_test_note", {
            "track_index": track_index,
            "midi_note": test_midi_note,
            "velocity": test_velocity,
            "duration_ms": test_duration_ms,
        })
        if isinstance(resp, dict) and not resp.get("error"):
            fired = True
    except Exception as exc:
        logger.debug("fire_test_note unavailable: %s", exc)

    if not fired:
        # Graceful degradation when the remote-script helper isn't present.
        return {
            "ok": False,
            "error": (
                "fire_test_note handler not available on this remote script. "
                "Update LivePilot's remote script (npx livepilot --install + "
                "reload_handlers) to enable verify_device_health."
            ),
            "alive": None,
        }

    # Sample the track meter over the duration of the note.
    sample_interval_ms = 50
    n = max(2, test_duration_ms // sample_interval_ms)
    peak = 0.0
    samples_taken = 0
    for i in range(n):
        try:
            snap = ableton.send_command("get_track_meters", {
                "track_index": track_index,
            })
        except Exception as exc:
            logger.debug("get_track_meters snapshot failed: %s", exc)
            continue
        samples_taken += 1
        if isinstance(snap, dict):
            tracks = snap.get("tracks") or []
            for t in tracks:
                if not isinstance(t, dict):
                    continue
                level = t.get("level") or 0
                try:
                    peak = max(peak, float(level))
                except (TypeError, ValueError):
                    pass
        if i < n - 1:
            await asyncio.sleep(sample_interval_ms / 1000.0)

    # Always clean up the scratch clip, even on errors.
    try:
        ableton.send_command("cleanup_test_note", {"track_index": track_index})
    except Exception as exc:
        logger.debug("cleanup_test_note failed: %s", exc)

    alive = peak >= threshold
    hint = ""
    if not alive:
        hint = (
            "Device produced no audible output. Common causes: "
            "(1) plugin waiting for preset/bank selection, "
            "(2) algorithm/envelope configured for zero output, "
            "(3) wrong MIDI channel or velocity curve, "
            "(4) dead VST (reinstall). "
            "Try opening the device UI and auditioning manually."
        )

    return {
        "ok": True,
        "alive": alive,
        "peak_level": round(peak, 4),
        "threshold": threshold,
        "samples_taken": samples_taken,
        "test_midi_note": test_midi_note,
        "test_velocity": test_velocity,
        "test_duration_ms": test_duration_ms,
        "hint": hint,
    }


@mcp.tool()
async def verify_all_devices_health(
    ctx: Context,
    test_midi_note: int = 60,
    test_velocity: int = 100,
    test_duration_ms: int = 250,
    threshold: float = 0.005,
    skip_audio_tracks: bool = True,
    skip_empty_tracks: bool = True,
) -> dict:
    """Run verify_device_health across every eligible track in one call.

    Session-wide silent-track detector. Useful right after opening a
    project to surface dead plugins before mixing. Serial execution —
    firing notes in parallel would make the meter readings ambiguous.

    skip_audio_tracks:  audio tracks have no MIDI input, skip them (default True)
    skip_empty_tracks:  tracks without any instrument also skip (default True)

    Returns: {
      "ok": bool,
      "tracks_tested": int,
      "alive": [track_index...],
      "dead": [{track_index, track_name, peak_level}...],
      "skipped": [{track_index, reason}...],
    }
    """
    ableton = ctx.lifespan_context["ableton"]
    try:
        session = ableton.send_command("get_session_info", {})
    except Exception as exc:
        return {"ok": False, "error": f"get_session_info failed: {exc}"}
    if not isinstance(session, dict):
        return {"ok": False, "error": "Unexpected get_session_info response"}

    tracks = session.get("tracks", []) or []
    alive: list = []
    dead: list = []
    skipped: list = []

    for t in tracks:
        tid = t.get("index")
        tname = t.get("name", f"Track {tid}")
        if tid is None:
            continue

        # BUG-2026-04-26#1: detect audio tracks via has_midi_input /
        # has_audio_input fields that get_session_info actually returns.
        # Pre-fix the code looked for `is_audio_track` / `type` fields which
        # don't exist on the session_info payload, so audio detection
        # silently always evaluated False and ALL tracks fell through to
        # the empty-tracks check below.
        has_midi = bool(t.get("has_midi_input"))
        has_audio = bool(t.get("has_audio_input"))
        is_audio = has_audio and not has_midi
        if skip_audio_tracks and is_audio:
            skipped.append({"track_index": tid, "track_name": tname,
                            "reason": "audio_track_no_midi_input"})
            continue

        # BUG-2026-04-26#1: get_session_info does NOT include per-track
        # `devices` arrays — only get_track_info does. Pre-fix,
        # `t.get("devices") or []` always returned [], so every MIDI track
        # was flagged "no_devices_on_track" even when a Simpler / Operator
        # / synth was loaded. Round-trip per track is the price of correct
        # detection; the alternative (extending get_session_info to embed
        # devices) would change a hot-path payload size for every caller.
        if skip_empty_tracks:
            try:
                track_info = ableton.send_command(
                    "get_track_info", {"track_index": tid},
                )
            except Exception:
                track_info = None
            devices = (
                (track_info or {}).get("devices") or []
                if isinstance(track_info, dict)
                else []
            )
            if not devices:
                skipped.append({"track_index": tid, "track_name": tname,
                                "reason": "no_devices_on_track"})
                continue

        # Run the per-track health check.
        result = await verify_device_health(
            ctx, track_index=tid,
            test_midi_note=test_midi_note,
            test_velocity=test_velocity,
            test_duration_ms=test_duration_ms,
            threshold=threshold,
        )
        if not result.get("ok"):
            skipped.append({"track_index": tid, "track_name": tname,
                            "reason": result.get("error", "health_check_failed")})
            continue
        if result.get("alive"):
            alive.append(tid)
        else:
            dead.append({
                "track_index": tid,
                "track_name": tname,
                "peak_level": result.get("peak_level", 0),
            })

    return {
        "ok": True,
        "tracks_tested": len(alive) + len(dead),
        "alive": alive,
        "dead": dead,
        "skipped": skipped,
        "summary": (
            f"{len(alive)} alive, {len(dead)} dead, "
            f"{len(skipped)} skipped out of {len(tracks)} total tracks"
        ),
    }


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
async def analyze_loudness_live(
    ctx: Context,
    window_sec: float = 10.0,
    sample_interval_ms: int = 200,
) -> dict:
    """Analyze the currently-playing master output's loudness over a window (LIVE).

    Use this tool during a session — no rendered file needed.
    For offline analysis of an exported audio file use analyze_loudness() instead.

    BUG-2026-04-22#8 fix — the offline `analyze_loudness` requires a
    rendered file. This tool samples the LivePilot analyzer's realtime
    momentary LUFS / true peak stream over `window_sec` and reports
    integrated + max statistics. No render required.

    Requires FluCoMa package in Max and playback to be running. Best
    called while the section you want to measure is actually playing.

    window_sec:         capture duration in seconds (default 10, max 120)
    sample_interval_ms: ms between samples (default 200 ≈ 5 Hz)

    Returns: {
      "integrated_lufs": float,      # mean momentary LUFS over window
      "max_momentary_lufs": float,   # peak momentary reading
      "min_momentary_lufs": float,   # quietest reading
      "range_lu": float,             # max - min (proxy for LRA)
      "max_true_peak_dbtp": float,   # max true peak across window
      "samples_collected": int,
      "window_sec": float,
      "is_playing": bool,
    }
    """
    if window_sec <= 0 or window_sec > 120:
        return {"error": "window_sec must be > 0 and <= 120"}
    if sample_interval_ms < 50 or sample_interval_ms > 5000:
        return {"error": "sample_interval_ms must be 50..5000"}

    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    ableton = ctx.lifespan_context["ableton"]

    # Verify FluCoMa is alive — otherwise there's no stream to sample.
    preview = cache.get("loudness")
    if not preview:
        hint = _flucoma_hint(cache)
        return {"error": f"No live loudness stream — {hint}"}

    try:
        session = ableton.send_command("get_session_info", {})
        is_playing = bool(session.get("is_playing", False))
    except Exception:
        is_playing = None

    interval_s = sample_interval_ms / 1000.0
    total_samples = max(1, int(window_sec / interval_s))
    lufs_vals: list[float] = []
    peak_vals: list[float] = []

    for i in range(total_samples):
        snap = cache.get("loudness")
        if snap and snap.get("value"):
            v = snap["value"]
            if "momentary_lufs" in v:
                lufs_vals.append(float(v["momentary_lufs"]))
            elif "lufs" in v:
                lufs_vals.append(float(v["lufs"]))
            if "true_peak_dbtp" in v:
                peak_vals.append(float(v["true_peak_dbtp"]))
            elif "peak_dbfs" in v:
                peak_vals.append(float(v["peak_dbfs"]))
        if i < total_samples - 1:
            await asyncio.sleep(interval_s)

    if not lufs_vals:
        return {"error": "No valid loudness samples captured over the window"}

    integrated = sum(lufs_vals) / len(lufs_vals)
    result = {
        "integrated_lufs": round(integrated, 2),
        "max_momentary_lufs": round(max(lufs_vals), 2),
        "min_momentary_lufs": round(min(lufs_vals), 2),
        "range_lu": round(max(lufs_vals) - min(lufs_vals), 2),
        "samples_collected": len(lufs_vals),
        "window_sec": window_sec,
        "sample_interval_ms": sample_interval_ms,
        "is_playing": is_playing,
    }
    if peak_vals:
        result["max_true_peak_dbtp"] = round(max(peak_vals), 2)
    if is_playing is False:
        result["warning"] = (
            "Playback was not running — readings reflect stale cache. "
            "Start playback and call again for accurate live analysis."
        )
    return result


@mcp.tool()
def check_flucoma(ctx: Context) -> dict:
    """Check if FluCoMa is installed and sending data."""
    cache = _get_spectral(ctx)
    streams = {}
    for key in ("spectral_shape", "mel_bands", "chroma", "onset", "novelty", "loudness"):
        streams[key] = cache.get(key) is not None
    active = sum(1 for v in streams.values() if v)
    return {"flucoma_available": active > 0, "active_streams": active, "streams": streams}


# ── BUG-A2 + A3: deep-LOM properties via M4L bridge ──────────────────


@mcp.tool()
async def simpler_set_warp(
    ctx: Context,
    track_index: int,
    device_index: int,
    warping: bool,
    warp_mode: Optional[int] = None,
) -> dict:
    """Toggle a Simpler's sample warping + set the warp algorithm (BUG-A2).

    Python's Remote Script ControlSurface API can't reach Simpler's
    `warping` or `warp_mode` — they live on the sample child object
    (SimplerDevice.sample.*) that only Max for Live's JavaScript LiveAPI
    can step into. This tool routes through the M4L bridge to do the
    write.

    When enabling warping, pass the desired warp_mode too so Live doesn't
    default to whatever was there last:

        warp_mode 0 = Beats      (good for drums / percussive loops)
        warp_mode 1 = Tones      (mono harmonic material)
        warp_mode 2 = Texture    (poly / ambient material)
        warp_mode 3 = Re-Pitch   (classic pitch-shift feel)
        warp_mode 4 = Complex    (music / full mixes — higher CPU)
        warp_mode 6 = Complex Pro (highest quality — highest CPU)

    Args:
        track_index: 0+ for regular tracks
        device_index: Simpler device's position in the chain
        warping: True → enable sample warp; False → disable
        warp_mode: 0-6 (omit to leave the current mode unchanged)

    Requires LivePilot Analyzer on master track.
    """
    if warp_mode is not None and warp_mode not in (0, 1, 2, 3, 4, 6):
        raise ValueError("warp_mode must be 0,1,2,3,4,6 (no 5 — Live skips it)")
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command(
        "simpler_set_warp",
        int(track_index),
        int(device_index),
        1 if warping else 0,
        -1 if warp_mode is None else int(warp_mode),
        timeout=10.0,
    )


@mcp.tool()
async def compressor_set_sidechain(
    ctx: Context,
    track_index: int,
    device_index: int,
    source_type: str = "",
    source_channel: str = "",
) -> dict:
    """Configure a Compressor's sidechain INPUT ROUTING (BUG-A3).

    Complements set_device_parameter's `S/C On` toggle: that enables the
    sidechain, this picks WHICH track/channel feeds the detector. The
    routing properties (`sidechain_input_routing_type`,
    `sidechain_input_routing_channel`) aren't in Compressor's automatable
    parameter list, but Python's Remote Script reaches them directly as
    device properties (same LOM pattern as set_track_routing).

    Args:
        track_index: 0+ regular, -1/-2 returns, -1000 master
        device_index: Compressor position in the chain
        source_type: sidechain source display name
            (e.g. "1-Kick", "Ext. In", "No Input")
        source_channel: tap point on the source
            (e.g. "Post FX", "Pre FX", "Post Mixer")

    Omit a param to leave that property unchanged. If a display name
    doesn't match, the error message includes the full list of available
    options from the running Live session.

    Routes through the Remote Script (TCP) — does NOT require the M4L
    analyzer. This is the Python-side path introduced after the M4L
    bridge approach hit LiveAPI shape issues in Live 12.3.6.
    """
    params: dict = {
        "track_index": int(track_index),
        "device_index": int(device_index),
    }
    if source_type:
        params["source_type"] = str(source_type)
    if source_channel:
        params["source_channel"] = str(source_channel)
    ableton = ctx.lifespan_context["ableton"]
    return ableton.send_command("set_compressor_sidechain", params)


# ──────────────────────────────────────────────────────────────────────
# v1.20.3 — ensure_analyzer_on_master
#
# Motivated by the v1.20.1 live-test campaign operator-error (see
# ~/Desktop/DREAM AI/demo Project/REPORT.md). The LLM operator had a
# clear global-memory instruction to load LivePilot_Analyzer on master
# proactively on a fresh session, and missed it — leaving analyzer-
# gated moves brittle. This tool closes that class of error by making
# the load idempotent + automatable.

_ANALYZER_DEVICE_NAME = "LivePilot_Analyzer"


def _load_analyzer_impl(ctx, track_index: int, device_name: str,
                        allow_duplicate: bool = False) -> dict:
    """Indirection so tests can monkeypatch the load call without having
    to fake the full find_and_load_device MCP-tool machinery. Production
    calls straight through to the existing tool."""
    from .devices import find_and_load_device
    return find_and_load_device(
        ctx,
        track_index=track_index,
        device_name=device_name,
        allow_duplicate=allow_duplicate,
    )


def _analyzer_amxd_installed_at_user_library() -> bool:
    """BUG-T#1: distinguish cold-browser-cache from genuinely-not-installed.

    On a fresh Live boot the User Library browser tree is uncached, and
    find_and_load_device can exceed the recv_timeout while doing the deep
    BFS for ``LivePilot_Analyzer.amxd``. The catch-block then surfaces
    ``install_required`` even though the .amxd is sitting at the canonical
    install path. This helper does a cheap filesystem check so the caller
    can return ``cache_cold`` (retry hint) instead of misleading the agent
    into a reinstall loop.

    Returns True iff a file named ``LivePilot_Analyzer.amxd`` exists under
    the User Library Max Audio Effect directory.
    """
    from pathlib import Path
    try:
        path = (Path.home()
                / "Music" / "Ableton" / "User Library"
                / "Presets" / "Audio Effects" / "Max Audio Effect"
                / f"{_ANALYZER_DEVICE_NAME}.amxd")
        return path.is_file()
    except Exception:
        return False


@mcp.tool()
def ensure_analyzer_on_master(ctx: Context) -> dict:
    """Idempotent pre-flight: load LivePilot_Analyzer on master if missing.

    Safe to call at the start of any session or before any move that
    declares analyzer dependency. Calling it repeatedly is cheap —
    subsequent calls short-circuit via a single get_master_track read.

    CLAUDE.md invariant: "LivePilot_Analyzer must be LAST on master."
    This tool reports whether the invariant holds via ``is_last_on_master``;
    it does NOT move the device (that's a user action in Ableton's GUI).

    Return shape:
    - status: one of {"already_loaded", "loaded", "install_required", "failed"}
    - device_index: int  — position of the analyzer on master (when present)
    - is_last_on_master: bool — True when analyzer is the last device
    - duplicate_count: int — 2+ when multiple analyzers exist (shouldn't)
    - warning: str | None — surfaces last-on-master violations
    - hint: str — actionable next step when status != "already_loaded"/"loaded"
    - error: str | None — present on status="failed"
    """
    ableton = ctx.lifespan_context["ableton"]

    # 1. Inspect the master chain for an existing analyzer.
    try:
        master = ableton.send_command("get_master_track")
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"Could not read master track: {exc}",
            "hint": "Verify MCP connection to Ableton; retry with get_session_info first.",
        }

    devices = (master or {}).get("devices") or []
    matches = [d for d in devices if d.get("name") == _ANALYZER_DEVICE_NAME]

    if matches:
        # 2. Already loaded — build a status report without side effects.
        first = matches[0]
        device_index = first.get("index")
        is_last = False
        if devices:
            last_name = devices[-1].get("name")
            is_last = (last_name == _ANALYZER_DEVICE_NAME)

        result: dict = {
            "status": "already_loaded",
            "device_index": device_index,
            "is_last_on_master": is_last,
            "duplicate_count": len(matches),
        }
        if len(matches) > 1:
            result["warning"] = (
                f"{len(matches)} instances of {_ANALYZER_DEVICE_NAME} on master — "
                "only one is needed. Remove extras in Ableton's GUI."
            )
        elif not is_last:
            result["warning"] = (
                f"{_ANALYZER_DEVICE_NAME} is not the LAST device on master. "
                "CLAUDE.md invariant requires it to come after ALL effects so "
                "it reads the final output, not pre-effect signal. "
                "Move it to the end of the master chain in Ableton's GUI."
            )
        return result

    # 3. Not on master — try loading from the Ableton browser.
    try:
        loaded = _load_analyzer_impl(
            ctx,
            track_index=-1000,  # master convention
            device_name=_ANALYZER_DEVICE_NAME,
            allow_duplicate=False,
        )
    except Exception as exc:
        # BUG-T#1: distinguish two failure modes that look identical here:
        #   (a) genuinely not installed — install_m4l_device path is right
        #   (b) installed but Ableton's browser cache is cold (first call
        #       after Live boot can exceed recv_timeout while BFS-ing the
        #       User Library tree). In (b), pointing the agent at
        #       install_m4l_device is wrong — the file is already there.
        if _analyzer_amxd_installed_at_user_library():
            return {
                "status": "cache_cold",
                "error": str(exc),
                "hint": (
                    "LivePilot_Analyzer.amxd is installed at "
                    "~/Music/Ableton/User Library/Presets/Audio Effects/"
                    "Max Audio Effect/, but the browser search timed out — "
                    "Ableton's User Library cache is typically cold on the "
                    "first call after a fresh Live boot. Retry "
                    "ensure_analyzer_on_master once; the second call usually "
                    "completes in <1s. If it keeps timing out, click any "
                    "User Library entry in Ableton's browser to warm the "
                    "cache, then retry."
                ),
            }
        return {
            "status": "install_required",
            "error": str(exc),
            "hint": (
                "LivePilot_Analyzer not found in Ableton's browser. Install "
                "first with install_m4l_device(source_path="
                "\"<repo>/m4l_device/LivePilot_Analyzer.amxd\") — that copies "
                "the .amxd into ~/Music/Ableton/User Library/Presets/Audio "
                "Effects/Max Audio Effect/. Then call ensure_analyzer_on_master "
                "again to complete the load."
            ),
        }

    device_index = (loaded or {}).get("device_index")
    return {
        "status": "loaded",
        "device_index": device_index,
        "is_last_on_master": True,  # fresh load always lands at the end
        "duplicate_count": 1,
    }

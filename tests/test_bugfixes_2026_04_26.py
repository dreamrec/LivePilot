"""Regression tests for the 5 bugs surfaced during the 2026-04-26
phonk-fusion production session.

BUG #1 — verify_all_devices_health falsely returned `no_devices_on_track`
        for every MIDI track because the function inspected the
        get_session_info `devices` field, which the Remote Script doesn't
        populate. Fix: round-trip get_track_info per track. Also fixed
        audio-detection that looked for non-existent `is_audio_track` /
        `type` fields instead of has_midi_input / has_audio_input.

BUG #2 — set_device_parameter raised generic `[STATE_ERROR] Invalid value`
        without surfacing the actual min/max from the parameter, forcing
        a follow-up get_device_parameters round-trip after every miss.
        Docstring also missed Compressor 2 and Saturator (both 0-1
        normalized despite the docstring listing only Compressor I as
        "pre-2010 units"). Fix: enrich the error response with the
        param's min/max/value_string + extend docstring.

BUG #3 — create_midi_track / create_audio_track accepted only `color`
        while set_track_color used `color_index`. Parallel-batch callers
        that consistently used the wrong name lost the entire batch.
        Fix: accept both keywords as aliases.

BUG #4 — CapabilityState.analyzer.available collapsed "device installed"
        and "fresh data ready" into one bit. After calling
        ensure_analyzer_on_master, the next concurrent get_capability_state
        could still report `analyzer_offline` because the device hadn't
        produced a frame yet. Fix: add `device_loaded` field on
        CapabilityDomain. Rename the warming-up reason from
        analyzer_stale → analyzer_warming_up for clarity.

BUG #5 — analyze_mix balance critic auto-classified VOX-GHOST as a
        "vocal" anchor and flagged it `anchor_too_weak` at vol 0.22 even
        though the name "GHOST" explicitly signals support, not anchor.
        Fix: substring-check track names against a non-anchor hint set
        before adding to anchor_indices.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────────────
# BUG #1 — verify_all_devices_health
# ──────────────────────────────────────────────────────────────────────


def _patch_send_command(session_payload: dict, track_info_by_index: dict) -> MagicMock:
    """Build an Ableton.send_command mock matching the v1 dispatch shape."""
    def dispatcher(cmd: str, args: dict = None):
        args = args or {}
        if cmd == "get_session_info":
            return session_payload
        if cmd == "get_track_info":
            tid = args.get("track_index")
            return track_info_by_index.get(tid, {})
        return {}

    mock_ableton = MagicMock()
    mock_ableton.send_command = MagicMock(side_effect=dispatcher)
    return mock_ableton


def test_bug26_verify_all_devices_health_uses_per_track_devices():
    """BUG #1: function MUST fetch get_track_info per track when checking
    skip_empty_tracks — get_session_info doesn't include `devices` arrays.
    """
    import asyncio

    from mcp_server.tools.analyzer import verify_all_devices_health

    # Session info as the Remote Script ACTUALLY returns it: no `devices`
    # field per track. Pre-fix `t.get("devices") or []` returned [] for
    # every track, so every MIDI track skipped with "no_devices_on_track".
    session = {
        "tracks": [
            {"index": 0, "name": "KICK", "has_midi_input": True, "has_audio_input": False},
            {"index": 1, "name": "VOX-AUDIO", "has_midi_input": False, "has_audio_input": True},
        ],
    }
    # get_track_info DOES return devices — that's the canonical source.
    track_infos = {
        0: {"index": 0, "name": "KICK", "devices": [{"name": "Simpler"}]},
        1: {"index": 1, "name": "VOX-AUDIO", "devices": []},
    }

    ableton = _patch_send_command(session, track_infos)

    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    # Mock verify_device_health to skip the bridge probe — we only want
    # to verify the empty-detection branch behaves correctly.
    async def fake_verify(ctx, track_index, **kw):
        return {"ok": True, "alive": True, "peak_level": 0.5}

    import mcp_server.tools.analyzer as analyzer_module
    original_verify = analyzer_module.verify_device_health
    analyzer_module.verify_device_health = fake_verify
    try:
        result = asyncio.run(verify_all_devices_health(
            ctx, skip_audio_tracks=True, skip_empty_tracks=True,
        ))
    finally:
        analyzer_module.verify_device_health = original_verify

    # Track 0 (KICK) has a device → tested, alive.
    # Track 1 (audio) → skipped because audio track.
    assert result["ok"] is True
    assert result["tracks_tested"] == 1, (
        f"Expected 1 track tested (KICK has Simpler loaded), got "
        f"{result['tracks_tested']}. Pre-fix this was 0 because every "
        f"MIDI track was wrongly skipped as no_devices_on_track."
    )
    assert 0 in result["alive"]

    # Confirm get_track_info was actually called for the KICK track —
    # this is what proves the new code path is exercised.
    track_info_calls = [
        c for c in ableton.send_command.mock_calls
        if c == call("get_track_info", {"track_index": 0})
    ]
    assert track_info_calls, (
        "verify_all_devices_health must call get_track_info per track "
        "to fetch the actual devices array — see BUG-2026-04-26#1."
    )


def test_bug26_verify_all_devices_health_audio_detection():
    """BUG #1: audio detection uses has_midi_input / has_audio_input
    rather than the non-existent is_audio_track / type fields.
    """
    import asyncio

    from mcp_server.tools.analyzer import verify_all_devices_health

    session = {
        "tracks": [
            # MIDI track — should not be skipped as audio.
            {"index": 0, "name": "DRUMS", "has_midi_input": True, "has_audio_input": False},
            # Audio track — should be skipped.
            {"index": 1, "name": "VOCAL-LOOP", "has_midi_input": False, "has_audio_input": True},
        ],
    }
    track_infos = {
        0: {"index": 0, "devices": [{"name": "Drum Rack"}]},
        1: {"index": 1, "devices": []},
    }
    ableton = _patch_send_command(session, track_infos)
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    async def fake_verify(ctx, track_index, **kw):
        return {"ok": True, "alive": True, "peak_level": 0.5}

    import mcp_server.tools.analyzer as analyzer_module
    original_verify = analyzer_module.verify_device_health
    analyzer_module.verify_device_health = fake_verify
    try:
        result = asyncio.run(verify_all_devices_health(
            ctx, skip_audio_tracks=True, skip_empty_tracks=True,
        ))
    finally:
        analyzer_module.verify_device_health = original_verify

    audio_skipped = [
        s for s in result["skipped"]
        if s["track_index"] == 1 and s["reason"] == "audio_track_no_midi_input"
    ]
    assert audio_skipped, (
        "Audio track (has_audio_input=True, has_midi_input=False) must be "
        "skipped with reason='audio_track_no_midi_input'. Pre-fix the audio "
        "check used non-existent is_audio_track / type fields, so audio "
        "tracks ALSO fell into the no_devices_on_track branch."
    )


# ──────────────────────────────────────────────────────────────────────
# BUG #2 — set_device_parameter error enrichment
# ──────────────────────────────────────────────────────────────────────


def test_bug26_set_device_parameter_enriches_range_error():
    """BUG #2: out-of-range errors must surface min/max/value_string
    fetched from get_device_parameters — the Remote Script's own error
    is generic and forces a follow-up probe.
    """
    import pytest

    from mcp_server.tools.devices import set_device_parameter

    def dispatcher(cmd: str, args: dict = None):
        args = args or {}
        if cmd == "set_device_parameter":
            # Mirror what the Remote Script raises.
            raise RuntimeError(
                "[STATE_ERROR] Invalid value. Check the parameters range "
                "with min/max (while running 'set_device_parameter')"
            )
        if cmd == "get_device_parameters":
            return {
                "parameters": [
                    {"index": 1, "name": "Drive", "value": 0.5,
                     "min": 0.0, "max": 1.0, "is_quantized": False,
                     "value_string": "0.0 dB"},
                ],
            }
        return None

    ableton = MagicMock()
    ableton.send_command = MagicMock(side_effect=dispatcher)
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    with pytest.raises(ValueError) as exc_info:
        # Drive on Saturator is 0-1 normalized; passing 6 (intended dB) errors.
        set_device_parameter(
            ctx, track_index=0, device_index=1,
            value=6, parameter_name="Drive",
        )

    msg = str(exc_info.value)
    assert "min=0" in msg or "min=0.0" in msg, (
        f"Enriched error must include min from get_device_parameters; got: {msg}"
    )
    assert "max=1" in msg or "max=1.0" in msg, (
        f"Enriched error must include max; got: {msg}"
    )
    assert "0.0 dB" in msg or "value_string" in msg, (
        f"Enriched error must include value_string; got: {msg}"
    )


def test_bug26_set_device_parameter_passes_through_non_range_errors():
    """BUG #2: only Range-shaped errors get enriched. Other failures
    (network, NOT_FOUND, etc.) should bubble up untouched.
    """
    import pytest

    from mcp_server.tools.devices import set_device_parameter

    def dispatcher(cmd: str, args: dict = None):
        if cmd == "set_device_parameter":
            raise RuntimeError("[NOT_FOUND] Track 99 does not exist")
        return None

    ableton = MagicMock()
    ableton.send_command = MagicMock(side_effect=dispatcher)
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    with pytest.raises(RuntimeError) as exc_info:
        set_device_parameter(
            ctx, track_index=0, device_index=0,
            value=0.5, parameter_name="Drive",
        )

    assert "NOT_FOUND" in str(exc_info.value)
    # Must not have called get_device_parameters for non-range error
    get_calls = [
        c for c in ableton.send_command.mock_calls
        if c.args and c.args[0] == "get_device_parameters"
    ]
    assert not get_calls, (
        "Non-range errors should pass through without spending a "
        "get_device_parameters round-trip."
    )


def test_bug26_set_device_parameter_docstring_includes_modern_devices():
    """BUG #2: docstring lists Compressor I as 'pre-2010 units' but
    omits Compressor 2 and Saturator (also 0-1 normalized). Both are
    the default loaded devices in Live 12.4.
    """
    from mcp_server.tools.devices import set_device_parameter

    doc = set_device_parameter.__doc__ or ""
    assert "Compressor 2" in doc, (
        "Docstring must explicitly mention Compressor 2 — it's the "
        "default Compressor returned by find_and_load_device('Compressor') "
        "in Live 12.4 and uses 0-1 normalized values like Threshold "
        "0.85≈0dB. Without this hint callers reach for absolute dB."
    )
    assert "Saturator" in doc, (
        "Docstring must explicitly mention Saturator — Drive/Output are "
        "0-1 normalized, not dB. Common mismatch."
    )


# ──────────────────────────────────────────────────────────────────────
# BUG #3 — color / color_index alias
# ──────────────────────────────────────────────────────────────────────


def test_bug26_create_midi_track_accepts_color_index():
    """BUG #3: callers consistently passed color_index (matching
    set_track_color) — both kwargs must be accepted.
    """
    from mcp_server.tools.tracks import create_midi_track

    sent_params = {}

    def dispatcher(cmd: str, args: dict = None):
        if cmd == "create_midi_track":
            sent_params.update(args or {})
            return {"index": 5, "name": "PIANO"}
        if cmd == "get_session_info":
            return {"tracks": []}
        return None

    ableton = MagicMock()
    ableton.send_command = MagicMock(side_effect=dispatcher)
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    create_midi_track(ctx, name="PIANO", color_index=14)

    assert sent_params.get("color_index") == 14, (
        "create_midi_track must accept the color_index kwarg as an alias "
        "for color and forward it to the Remote Script. "
        f"Got params: {sent_params}"
    )


def test_bug26_create_audio_track_accepts_color_index():
    from mcp_server.tools.tracks import create_audio_track

    sent_params = {}

    def dispatcher(cmd: str, args: dict = None):
        if cmd == "create_audio_track":
            sent_params.update(args or {})
            return {"index": 3, "name": "VOCAL"}
        if cmd == "get_session_info":
            return {"tracks": []}
        return None

    ableton = MagicMock()
    ableton.send_command = MagicMock(side_effect=dispatcher)
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    create_audio_track(ctx, name="VOCAL", color_index=22)
    assert sent_params.get("color_index") == 22


def test_bug26_create_midi_track_color_alias_conflict_raises():
    """If both color and color_index are passed AND they disagree,
    that's a caller bug — fail loud rather than silently picking one.
    """
    import pytest

    from mcp_server.tools.tracks import create_midi_track

    ableton = MagicMock()
    ableton.send_command = MagicMock(return_value={"tracks": []})
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    with pytest.raises(ValueError, match="color"):
        create_midi_track(ctx, name="X", color=14, color_index=22)


def test_bug26_create_midi_track_color_alias_agreement_ok():
    """If both are passed but agree, accept silently — that's the
    backward-compat case for callers passing both during transition.
    """
    from mcp_server.tools.tracks import create_midi_track

    ableton = MagicMock()
    ableton.send_command = MagicMock(side_effect=[
        {"tracks": []},  # get_session_info for collision check
        {"index": 0, "name": "X"},  # create_midi_track
    ])
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    # No exception
    create_midi_track(ctx, name="X", color=14, color_index=14)


# ──────────────────────────────────────────────────────────────────────
# BUG #4 — capability_state device_loaded field
# ──────────────────────────────────────────────────────────────────────


def test_bug26_capability_state_analyzer_device_loaded_when_warming():
    """BUG #4: device_loaded MUST be True when the .amxd is on the
    master even if no audio frame has been captured yet. Pre-fix
    callers had no way to distinguish 'just loaded' from 'never loaded'.
    """
    from mcp_server.runtime.capability_state import build_capability_state

    state = build_capability_state(
        session_ok=True,
        analyzer_ok=True,    # device IS on master
        analyzer_fresh=False,  # but no frame captured yet (warming up)
        memory_ok=True,
    )
    analyzer = state.domains["analyzer"]

    assert analyzer.device_loaded is True, (
        "device_loaded must reflect the .amxd presence even before the "
        "first frame is captured. See BUG-2026-04-26#4."
    )
    assert analyzer.available is False, (
        "available must remain False until a fresh frame is captured "
        "(end-to-end ready). The split between device_loaded and "
        "available is the whole point of the fix."
    )
    assert "analyzer_warming_up" in analyzer.reasons, (
        "Reasons should say 'analyzer_warming_up' (device present, "
        "data not ready yet) instead of 'analyzer_offline' which "
        "is the reason for genuinely-not-loaded."
    )


def test_bug26_capability_state_analyzer_device_loaded_false_when_offline():
    """When the device is not loaded at all, device_loaded must be False
    and the reason must remain 'analyzer_offline'.
    """
    from mcp_server.runtime.capability_state import build_capability_state

    state = build_capability_state(
        session_ok=True,
        analyzer_ok=False,
        analyzer_fresh=False,
        memory_ok=True,
    )
    analyzer = state.domains["analyzer"]

    assert analyzer.device_loaded is False
    assert analyzer.available is False
    assert "analyzer_offline" in analyzer.reasons


def test_bug26_capability_state_non_analyzer_domains_default_device_loaded():
    """Domains without an installable component (memory, web, session)
    should report device_loaded == available so existing consumers
    don't need to special-case None.
    """
    from mcp_server.runtime.capability_state import build_capability_state

    state = build_capability_state(
        session_ok=True,
        analyzer_ok=False,
        memory_ok=True,
        web_ok=True,
    )
    for domain_name in ("session_access", "memory", "web"):
        domain = state.domains[domain_name]
        assert domain.device_loaded == domain.available, (
            f"{domain_name}.device_loaded must mirror .available when "
            f"the domain has no installable component. "
            f"Got device_loaded={domain.device_loaded}, "
            f"available={domain.available}."
        )


# ──────────────────────────────────────────────────────────────────────
# BUG #5 — analyze_mix non-anchor name hints
# ──────────────────────────────────────────────────────────────────────


def test_bug26_balance_state_excludes_ghost_named_tracks_from_anchors():
    """BUG #5: a track named VOX-GHOST must NOT be classified as an
    anchor even though its inferred role is 'vocal'. Otherwise the
    balance critic flags `anchor_too_weak` for any volume below
    average — guaranteed false positive on every ghost wisp layer.
    """
    from mcp_server.mix_engine.state_builder import build_balance_state

    track_infos = [
        {
            "index": 0, "name": "KICK",
            "mixer": {"volume": 0.7, "panning": 0},
            "sends": [],
            "devices": [],
        },
        {
            "index": 1, "name": "BASS",
            "mixer": {"volume": 0.7, "panning": 0},
            "sends": [],
            "devices": [],
        },
        {
            "index": 2, "name": "VOX-GHOST",
            "mixer": {"volume": 0.22, "panning": 0.4},
            "sends": [],
            "devices": [],
        },
    ]

    bs = build_balance_state(track_infos)
    # KICK (index 0) and BASS (index 1) are anchors. VOX-GHOST is NOT.
    assert 0 in bs.anchor_tracks
    assert 1 in bs.anchor_tracks
    assert 2 not in bs.anchor_tracks, (
        "VOX-GHOST has 'GHOST' in its name and must be excluded from "
        "anchor_tracks even though role inference returns 'vocal'. "
        "See BUG-2026-04-26#5."
    )


def test_bug26_balance_state_excludes_atmos_drone_fx_named_tracks():
    """BUG #5: extended hint set covers the common support-layer naming
    conventions — atmos, drone, fx, texture, wash.
    """
    from mcp_server.mix_engine.state_builder import build_balance_state

    track_infos = [
        {"index": i, "name": name, "mixer": {"volume": 0.6}, "sends": [], "devices": []}
        for i, name in enumerate([
            "ATMOS",          # was role=pad, NOT in anchor_roles anyway
            "drone-bed",      # name hint should still apply if role inference grabs anchor
            "FX-rain",
            "vocal-wash",     # vocal + wash → not anchor
            "shimmer-pad",
            "back-vox",       # back-vocals are always supports
        ])
    ]
    bs = build_balance_state(track_infos)
    # vocal-wash is the cleanest test — role=vocal (anchor) but name
    # contains 'wash' which signals support.
    vocal_wash_idx = next(
        i for i, t in enumerate(track_infos) if t["name"] == "vocal-wash"
    )
    assert vocal_wash_idx not in bs.anchor_tracks, (
        "'vocal-wash' must be excluded from anchors via the name hint."
    )
    back_vox_idx = next(
        i for i, t in enumerate(track_infos) if t["name"] == "back-vox"
    )
    assert back_vox_idx not in bs.anchor_tracks, (
        "'back-vox' must be excluded from anchors via the name hint."
    )


def test_bug26_balance_state_real_anchors_still_anchored():
    """BUG #5 sanity check: properly-named anchor tracks remain anchors.
    Don't let the hint set over-filter."""
    from mcp_server.mix_engine.state_builder import build_balance_state

    track_infos = [
        {"index": 0, "name": "KICK", "mixer": {"volume": 0.8}, "sends": [], "devices": []},
        {"index": 1, "name": "Bass", "mixer": {"volume": 0.7}, "sends": [], "devices": []},
        {"index": 2, "name": "Lead Vocal", "mixer": {"volume": 0.65}, "sends": [], "devices": []},
        {"index": 3, "name": "Snare", "mixer": {"volume": 0.7}, "sends": [], "devices": []},
    ]
    bs = build_balance_state(track_infos)
    assert 0 in bs.anchor_tracks  # KICK
    assert 1 in bs.anchor_tracks  # Bass
    assert 2 in bs.anchor_tracks, (
        "'Lead Vocal' must remain anchor — no support-layer hint in name."
    )

"""§2 sound-design-depth rubric tests."""

from __future__ import annotations

from mcp_server.grader import evaluate, format_revision_brief


def _by_id(verdict: dict, criterion_id: str) -> dict:
    for c in verdict["criteria"]:
        if c["id"] == criterion_id:
            return c
    raise KeyError(criterion_id)


def _track(index: int, name: str, devices: list[dict], volume: float = 0.5) -> dict:
    return {
        "index": index,
        "name": name,
        "mixer": {"volume": volume, "panning": 0.0},
        "devices": devices,
    }


def _drift_default() -> dict:
    """Bare-default Drift — every fingerprint param at factory value.

    Factory values from live capture 2026-05-08. Drift escapes the generic
    _SUSPICIOUS_AT_ZERO check because all these are non-zero by default.
    The factory-fingerprint detection in audit/checks._check_drift_params
    catches it via deviation count == 0.
    """
    return {
        "class_name": "Drift",
        "name": "Drift",
        "parameters": [
            {"name": "Pitch Mod Amt 1", "value": 0.5},
            {"name": "Pitch Mod Amt 2", "value": 0.5},
            {"name": "Mod Matrix Amt 2", "value": 0.5},
            {"name": "Mod Matrix Amt 3", "value": 0.5},
            {"name": "Vel > Vol", "value": 0.5},
            {"name": "Spread", "value": 0.10},
            {"name": "Strength", "value": 0.05},
            {"name": "Drift", "value": 0.07},
            {"name": "Thickness", "value": 0.0},
            {"name": "LP Mod Amt 1", "value": 0.97},
            {"name": "LP Mod Amt 2", "value": 0.78},
            {"name": "LFO Amt", "value": 1.0},
        ],
    }


def _drift_programmed() -> dict:
    """User-programmed Drift — at least 2 fingerprint params deviated."""
    return {
        "class_name": "Drift",
        "name": "BoC Wash",
        "parameters": [
            {"name": "Pitch Mod Amt 1", "value": 0.7},   # deviated from 0.5
            {"name": "Pitch Mod Amt 2", "value": 0.5},
            {"name": "Mod Matrix Amt 2", "value": 0.5},
            {"name": "Mod Matrix Amt 3", "value": 0.5},
            {"name": "Vel > Vol", "value": 0.5},
            {"name": "Spread", "value": 0.45},            # deviated from 0.10
            {"name": "Strength", "value": 0.05},
            {"name": "Drift", "value": 0.07},
            {"name": "Thickness", "value": 0.0},
            {"name": "LP Mod Amt 1", "value": 0.97},
            {"name": "LP Mod Amt 2", "value": 0.78},
            {"name": "LFO Amt", "value": 1.0},
        ],
    }


# ── Pass cases ───────────────────────────────────────────────────────


def test_pass_when_pad_instrument_programmed():
    state = {"tracks": [_track(0, "Pad Drift", [_drift_programmed()])]}
    v = evaluate("sound_design_depth", state)
    assert v["passed"]
    assert _by_id(v, "params_per_track")["severity"] == "pass"


def test_pass_when_kick_uses_default_drift():
    """Drum roles suppressed — single-sample minimal-shaping is correct by design."""
    state = {"tracks": [_track(0, "Kick 808", [_drift_default()], volume=0.75)]}
    c = _by_id(evaluate("sound_design_depth", state), "params_per_track")
    assert c["severity"] == "pass"


def test_pass_when_no_native_instrument_present():
    state = {"tracks": [_track(0, "Pad Drift", [
        {"class_name": "ExternalInstrument", "name": "VST Pad"},
        {"class_name": "Reverb", "name": "Reverb"},
    ])]}
    c = _by_id(evaluate("sound_design_depth", state), "params_per_track")
    assert c["severity"] in ("n/a", "pass")


# ── Fail cases ───────────────────────────────────────────────────────


def test_fail_when_pad_drift_unprogrammed():
    state = {"tracks": [_track(0, "Pad Drift", [_drift_default()])]}
    v = evaluate("sound_design_depth", state)
    assert not v["passed"]
    c = _by_id(v, "params_per_track")
    assert c["severity"] == "fail"
    codes = {i["code"] for i in c["issues"]}
    assert "unprogrammed_instrument" in codes


def test_fail_when_bass_unprogrammed():
    state = {"tracks": [_track(0, "Sub Bass", [
        {
            "class_name": "Wavetable",
            "name": "Wavetable",
            "parameters": [
                {"name": "Filt < Env", "value": 0.0},
                {"name": "Spread", "value": 0.0},
                {"name": "Detune", "value": 0.0},
                {"name": "Unison", "value": 0.0},
            ],
        }
    ])]}
    v = evaluate("sound_design_depth", state)
    assert not v["passed"]


def test_fail_when_lead_unprogrammed():
    state = {"tracks": [_track(0, "Lead arp", [_drift_default()])]}
    v = evaluate("sound_design_depth", state)
    assert not v["passed"]


# ── Mixed scenes ─────────────────────────────────────────────────────


def test_mixed_scene_fails_on_any_unprogrammed_pad():
    state = {"tracks": [
        _track(0, "Kick 808", [_drift_default()], volume=0.75),
        _track(1, "Lead arp", [_drift_programmed()]),
        _track(2, "Pad Drift", [_drift_default()]),  # the one violation
    ]}
    v = evaluate("sound_design_depth", state)
    assert not v["passed"]
    c = _by_id(v, "params_per_track")
    assert c["severity"] == "fail"
    failing_indices = {i["track_index"] for i in c["issues"]}
    assert 2 in failing_indices
    assert 0 not in failing_indices  # drum suppressed
    assert 1 not in failing_indices  # programmed


# ── Edge cases ───────────────────────────────────────────────────────


def test_empty_session_passes_with_na():
    v = evaluate("sound_design_depth", {"tracks": []})
    assert v["passed"]
    assert _by_id(v, "params_per_track")["severity"] == "n/a"


def test_revision_brief_includes_track_ref():
    state = {"tracks": [_track(4, "Pad Drift", [_drift_default()])]}
    v = evaluate("sound_design_depth", state)
    brief = format_revision_brief(v)
    assert "params_per_track" in brief
    assert "track 4" in brief
    assert "Pad Drift" in brief

"""§5 layer-precision rubric tests — wraps audit/checks.py."""

from __future__ import annotations

from mcp_server.grader import evaluate, format_revision_brief


def _by_id(verdict: dict, criterion_id: str) -> dict:
    for c in verdict["criteria"]:
        if c["id"] == criterion_id:
            return c
    raise KeyError(criterion_id)


# ── Empty / missing data ─────────────────────────────────────────────


def test_empty_session_all_criteria_na():
    v = evaluate("layer_precision", {"tracks": []})
    assert v["passed"]  # no fail
    for c in v["criteria"]:
        assert c["severity"] == "n/a"


def test_no_data_signals_all_na():
    state = {"tracks": [
        {"index": 0, "name": "Track 1", "mixer": {"volume": 0.7, "panning": 0.0}, "devices": []},
    ]}
    v = evaluate("layer_precision", state)
    # Stereo will be checked (track present, role inferred), others n/a
    assert _by_id(v, "stereo_per_track")["severity"] == "pass"
    assert _by_id(v, "timbre_per_track")["severity"] == "n/a"
    assert _by_id(v, "sequence_per_track")["severity"] == "n/a"


# ── Timbre wrapper ───────────────────────────────────────────────────


def test_timbre_passes_when_kick_dominates_sub_low():
    state = {"tracks": [{
        "index": 0, "name": "Kick 808",
        "mixer": {"volume": 0.75, "panning": 0.0},
        "devices": [],
        "fingerprint": {"bands": {
            "SUB_LOW": 0.9, "LOW": 0.6, "LOW_MID": 0.3, "MID": 0.4,
            "PRESENCE": 0.2, "HIGH": 0.1, "AIR": 0.05,
        }},
    }]}
    c = _by_id(evaluate("layer_precision", state), "timbre_per_track")
    assert c["severity"] == "pass"


def test_timbre_fails_when_sample_is_wrong_for_role():
    state = {"tracks": [{
        "index": 0, "name": "Kick 808",
        "mixer": {"volume": 0.75, "panning": 0.0},
        "devices": [],
        "fingerprint": {"bands": {
            "SUB_LOW": 0.05, "LOW": 0.1, "LOW_MID": 0.2, "MID": 0.3,
            "PRESENCE": 0.95, "HIGH": 0.6, "AIR": 0.4,
        }},
    }]}
    v = evaluate("layer_precision", state)
    c = _by_id(v, "timbre_per_track")
    assert c["severity"] == "fail"
    assert not v["passed"]
    assert any(i["track_index"] == 0 for i in c["issues"])


# ── Sequence wrapper ────────────────────────────────────────────────


def test_sequence_warns_on_robotic_drums():
    notes = [{"pitch": 38, "velocity": 100, "duration": 0.25} for _ in range(8)]
    state = {"tracks": [{
        "index": 0, "name": "Snare",
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": [],
        "notes_per_clip": [notes],
    }]}
    c = _by_id(evaluate("layer_precision", state), "sequence_per_track")
    assert c["severity"] in ("warn", "fail")
    codes = {i["code"] for i in c["issues"]}
    assert "no_humanization" in codes


def test_sequence_na_on_audio_track_with_no_notes():
    state = {"tracks": [{
        "index": 0, "name": "Vocal sample",
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": [],
        # no notes_per_clip
    }]}
    c = _by_id(evaluate("layer_precision", state), "sequence_per_track")
    assert c["severity"] == "n/a"


# ── Stereo wrapper ───────────────────────────────────────────────────


def test_stereo_warns_on_panned_bass():
    state = {"tracks": [{
        "index": 0, "name": "Sub Bass",
        "mixer": {"volume": 0.7, "panning": 0.3},
        "devices": [],
    }]}
    c = _by_id(evaluate("layer_precision", state), "stereo_per_track")
    assert c["severity"] == "warn"
    assert c["issues"][0]["code"] == "panned_bass"


def test_stereo_pass_on_centered_bass():
    state = {"tracks": [{
        "index": 0, "name": "Sub Bass",
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": [],
    }]}
    c = _by_id(evaluate("layer_precision", state), "stereo_per_track")
    assert c["severity"] == "pass"


# ── Masking wrapper ──────────────────────────────────────────────────


def test_masking_na_without_session_report():
    state = {"tracks": [{
        "index": 0, "name": "Kick",
        "mixer": {"volume": 0.75, "panning": 0.0},
        "devices": [],
    }]}
    c = _by_id(evaluate("layer_precision", state), "masking_per_track")
    assert c["severity"] == "n/a"


def test_masking_fails_on_high_severity_collision():
    state = {
        "tracks": [
            {"index": 0, "name": "Kick", "mixer": {"volume": 0.75, "panning": 0.0}, "devices": []},
            {"index": 1, "name": "Sub Bass", "mixer": {"volume": 0.7, "panning": 0.0}, "devices": []},
        ],
        "masking_report": {
            "masking": {
                "entries": [
                    {"track_a": 0, "track_b": 1, "band": "SUB_LOW", "severity": "high"},
                ]
            }
        },
    }
    v = evaluate("layer_precision", state)
    c = _by_id(v, "masking_per_track")
    assert c["severity"] == "fail"
    assert not v["passed"]


# ── Params wrapper (§5.6 / §2) ───────────────────────────────────────


def _drift_with_default_params() -> dict:
    """Bare-default Drift — every fingerprint param at factory value.

    Factory values captured live 2026-05-08 via load_browser_item +
    get_track_info on a freshly-loaded Drift. Detection lives in
    audit/checks._check_drift_params (factory-fingerprint deviation count).
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


def _drift_with_programmed_params() -> dict:
    """User-programmed Drift — at least 2 fingerprint params deviated."""
    return {
        "class_name": "Drift",
        "name": "BoC Wash",
        "parameters": [
            {"name": "Pitch Mod Amt 1", "value": 0.7},   # deviated
            {"name": "Pitch Mod Amt 2", "value": 0.5},
            {"name": "Mod Matrix Amt 2", "value": 0.5},
            {"name": "Mod Matrix Amt 3", "value": 0.5},
            {"name": "Vel > Vol", "value": 0.5},
            {"name": "Spread", "value": 0.45},            # deviated
            {"name": "Strength", "value": 0.05},
            {"name": "Drift", "value": 0.07},
            {"name": "Thickness", "value": 0.0},
            {"name": "LP Mod Amt 1", "value": 0.97},
            {"name": "LP Mod Amt 2", "value": 0.78},
            {"name": "LFO Amt", "value": 1.0},
        ],
    }


def test_params_fails_unprogrammed_pad():
    state = {"tracks": [{
        "index": 0, "name": "Pad Drift",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [_drift_with_default_params()],
    }]}
    v = evaluate("layer_precision", state)
    c = _by_id(v, "params_per_track")
    assert c["severity"] == "fail"
    assert not v["passed"]
    assert any("unprogrammed_instrument" in i["code"] for i in c["issues"])


def test_params_passes_programmed_pad():
    state = {"tracks": [{
        "index": 0, "name": "Pad Drift",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [_drift_with_programmed_params()],
    }]}
    c = _by_id(evaluate("layer_precision", state), "params_per_track")
    assert c["severity"] == "pass"


def test_params_passes_drum_track_regardless():
    """Drum roles are suppressed in check_params — single-sample is correct."""
    state = {"tracks": [{
        "index": 0, "name": "Kick 808",
        "mixer": {"volume": 0.75, "panning": 0.0},
        "devices": [_drift_with_default_params()],
    }]}
    c = _by_id(evaluate("layer_precision", state), "params_per_track")
    assert c["severity"] == "pass"


# ── Effects wrapper ──────────────────────────────────────────────────


def test_effects_warns_when_pad_lacks_reverb():
    state = {"tracks": [{
        "index": 0, "name": "Pad Drift",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [
            {"class_name": "Drift", "name": "Drift"},
            {"class_name": "EQ Eight", "name": "EQ Eight"},
        ],
    }]}
    c = _by_id(evaluate("layer_precision", state), "effects_per_track")
    assert c["severity"] == "warn"
    codes = {i["code"] for i in c["issues"]}
    assert "no_space" in codes


def test_effects_pass_when_full_chain_present():
    state = {"tracks": [{
        "index": 0, "name": "Lead arp",
        "mixer": {"volume": 0.6, "panning": 0.0},
        "devices": [
            {"class_name": "Wavetable", "name": "Curated"},
            {"class_name": "EQ Eight", "name": "EQ Eight"},
            {"class_name": "Compressor", "name": "Compressor"},
            {"class_name": "Reverb", "name": "Reverb"},
        ],
    }]}
    c = _by_id(evaluate("layer_precision", state), "effects_per_track")
    assert c["severity"] == "pass"


# ── False-positive fix: modulation_per_track skips no-instrument tracks ──


def test_modulation_skips_empty_default_live_tracks():
    """Regression test for deep-test 2026-05-08: empty Live default tracks
    were flagged 'no_movement' because audit_checks.check_modulation returns
    warn whenever routings=0, even with zero devices."""
    state = {"tracks": [
        {"index": 0, "name": "1-MIDI", "mixer": {"volume": 0.85, "panning": 0.0}, "devices": []},
        {"index": 1, "name": "2-MIDI", "mixer": {"volume": 0.85, "panning": 0.0}, "devices": []},
    ]}
    c = _by_id(evaluate("layer_precision", state), "modulation_per_track")
    assert c["severity"] == "n/a"
    assert c["issues"] == []


def test_modulation_skips_audio_track_with_only_fx():
    """An audio track with EQ but no instrument has nothing to modulate."""
    state = {"tracks": [{
        "index": 0, "name": "Reverb send",
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": [
            {"class_name": "EQ Eight", "name": "EQ Eight"},
            {"class_name": "Reverb", "name": "Reverb"},
        ],
    }]}
    c = _by_id(evaluate("layer_precision", state), "modulation_per_track")
    assert c["severity"] == "n/a"


def test_modulation_still_checks_track_with_instrument():
    """Fix must NOT silence legitimate warnings on instrument-bearing tracks.

    audit_checks.check_modulation returns 'fail' (not 'warn') when a
    pad/lead/bass role has zero routings AND no automation — that's the
    existing audit semantic, more aggressive than the §4 advisory rubric.
    Test only that the criterion fires, not which specific severity.
    """
    state = {"tracks": [{
        "index": 0, "name": "Pad Drift",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [{"class_name": "Drift", "name": "Drift", "parameters": []}],
        "has_clip_automation": False,
        "wavetable_mod_routings": 0,
    }]}
    c = _by_id(evaluate("layer_precision", state), "modulation_per_track")
    assert c["severity"] in ("warn", "fail")
    issue_codes = {i["code"] for i in c["issues"]}
    assert "no_movement" in issue_codes or "static_layer" in issue_codes


def test_modulation_recognizes_ultraanalog_instrument():
    """Live's runtime class_name for Analog is UltraAnalog. Bug discovered
    2026-05-08 multi-violation test — UltraAnalog tracks were being skipped
    by the instrument-presence guard. Regression test."""
    state = {"tracks": [{
        "index": 0, "name": "Bass Analog",
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": [{"class_name": "UltraAnalog", "name": "Analog", "parameters": []}],
    }]}
    c = _by_id(evaluate("layer_precision", state), "modulation_per_track")
    # MUST not be n/a — the track has an instrument and should be checked
    assert c["severity"] in ("warn", "fail"), \
        f"UltraAnalog track skipped (severity={c['severity']}); should be checked"


def test_modulation_recognizes_m4l_instrument():
    """M4L instruments use the MxDeviceInstrument wrapper class. Without
    explicit recognition they were skipped by Fix #2's instrument-presence
    guard. Regression test."""
    state = {"tracks": [{
        "index": 0, "name": "Pad M4L",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [{"class_name": "MxDeviceInstrument", "name": "Poli", "parameters": []}],
    }]}
    c = _by_id(evaluate("layer_precision", state), "modulation_per_track")
    assert c["severity"] in ("warn", "fail"), \
        f"M4L instrument track skipped (severity={c['severity']}); should be checked"


def test_modulation_recognizes_instrumentmeld():
    """Meld's class_name is InstrumentMeld."""
    state = {"tracks": [{
        "index": 0, "name": "Pad Meld",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [{"class_name": "InstrumentMeld", "name": "Meld", "parameters": []}],
    }]}
    c = _by_id(evaluate("layer_precision", state), "modulation_per_track")
    assert c["severity"] in ("warn", "fail"), \
        f"InstrumentMeld track skipped (severity={c['severity']}); should be checked"


# ── Aggregation behavior ─────────────────────────────────────────────


def test_overall_verdict_fails_on_any_criterion_fail():
    state = {"tracks": [{
        "index": 0, "name": "Pad Drift",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [_drift_with_default_params()],
    }]}
    v = evaluate("layer_precision", state)
    assert not v["passed"]


def test_revision_brief_lists_failing_criterion_with_track_ref():
    state = {"tracks": [{
        "index": 7, "name": "Pad Drift",
        "mixer": {"volume": 0.4, "panning": 0.0},
        "devices": [_drift_with_default_params()],
    }]}
    v = evaluate("layer_precision", state)
    brief = format_revision_brief(v)
    assert "params_per_track" in brief
    assert "track 7" in brief
    assert "Pad Drift" in brief

"""§1 banned-default rubric tests."""

from __future__ import annotations

from mcp_server.grader import evaluate, format_revision_brief


def _track(index: int, name: str, devices: list[dict]) -> dict:
    return {
        "index": index,
        "name": name,
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": devices,
    }


def _by_id(verdict: dict, criterion_id: str) -> dict:
    for c in verdict["criteria"]:
        if c["id"] == criterion_id:
            return c
    raise KeyError(criterion_id)


# ── Banned default detection ─────────────────────────────────────────


def test_pass_when_no_melodic_track_uses_banned_default():
    state = {"tracks": [
        _track(0, "Kick 808", [{"class_name": "DrumGroup", "name": "Drum Rack"}]),
        _track(1, "Sub Bass", [{"class_name": "Wavetable", "name": "BoC Sub"}]),
        _track(2, "Pad Granular", [{"class_name": "Sampler", "name": "Pad Granular"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "pass"
    assert c["passed"]


def test_fail_when_pad_uses_default_drift():
    state = {"tracks": [
        _track(0, "Pad Drift", [{"class_name": "Drift", "name": "Drift"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "fail"
    assert not c["passed"]
    assert c["issues"][0]["code"] == "banned_default_instrument"
    assert c["issues"][0]["track_index"] == 0


def test_fail_when_bass_uses_default_analog():
    """Live's class_name for Analog is 'UltraAnalog' (verified live 2026-05-08).
    Fixture uses the real runtime class — the previous test fixture used
    the user-facing brand name, which never appears as class_name."""
    state = {"tracks": [
        _track(0, "Sub Bass", [{"class_name": "UltraAnalog", "name": "Analog"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "fail"


def test_fail_when_pad_uses_default_meld():
    """Live's class_name for Meld is 'InstrumentMeld' (verified live 2026-05-08)."""
    state = {"tracks": [
        _track(0, "Pad Meld", [{"class_name": "InstrumentMeld", "name": "Meld"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "fail"
    assert not c["passed"]


def test_fail_when_lead_uses_default_poli():
    """Poli is M4L — class_name is the generic 'MxDeviceInstrument' wrapper.
    Detection requires the (class, name) fingerprint, not class alone
    (verified live 2026-05-08)."""
    state = {"tracks": [
        _track(0, "Lead arp", [{"class_name": "MxDeviceInstrument", "name": "Poli"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "fail"
    assert not c["passed"]


def test_pass_when_other_m4l_instrument_loaded():
    """An M4L instrument that ISN'T Poli (e.g., Hatster Pro from M4L_trnr)
    must NOT be flagged — fingerprint requires both class AND name match."""
    state = {"tracks": [
        _track(0, "Pad Hatster", [{"class_name": "MxDeviceInstrument", "name": "Hatster Pro"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "pass"
    assert c["passed"]


def test_pass_when_drift_has_preset_name_applied():
    """Drift loaded with a preset is fine — only naked default Drift is banned."""
    state = {"tracks": [
        _track(0, "Pad Drift", [{"class_name": "Drift", "name": "BoC Wash"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "pass"
    assert c["passed"]


def test_pass_when_drum_track_uses_drift():
    """§1 only applies to bass/pad/lead — kick can use whatever (though weird)."""
    state = {"tracks": [
        _track(0, "Kick 808", [{"class_name": "Drift", "name": "Drift"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "pass"


def test_subtractive_keyword_in_track_name_is_exception():
    """Explicit 'subtractive' tag in track name skips the violation."""
    state = {"tracks": [
        _track(0, "Bass subtractive sweep", [{"class_name": "Drift", "name": "Drift"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "pass"
    assert c["passed"]
    assert len(c["evidence"]["subtractive_exceptions"]) == 1


def test_multiple_violations_listed_separately():
    """Real Live runtime class names — Analog→UltraAnalog, Wavetable stays Wavetable."""
    state = {"tracks": [
        _track(0, "Pad Drift", [{"class_name": "Drift", "name": "Drift"}]),
        _track(1, "Sub Bass", [{"class_name": "UltraAnalog", "name": "Analog"}]),
        _track(2, "Lead arp", [{"class_name": "Wavetable", "name": "Curated lead"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "fail"
    assert len(c["issues"]) == 2
    track_indices = {i["track_index"] for i in c["issues"]}
    assert track_indices == {0, 1}


def test_overall_verdict_fails_on_any_banned_default():
    state = {"tracks": [
        _track(0, "Pad Drift", [{"class_name": "Drift", "name": "Drift"}]),
    ]}
    v = evaluate("default_preset_check", state)
    assert not v["passed"]


def test_pass_when_melodic_track_has_no_instrument():
    """Audio-only track or empty track shouldn't flag — no instrument to check."""
    state = {"tracks": [
        _track(0, "Pad Drift", [{"class_name": "EQ Eight", "name": "EQ Eight"}]),
    ]}
    c = _by_id(evaluate("default_preset_check", state), "no_banned_default_instruments")
    assert c["severity"] == "pass"


# ── Edge cases ───────────────────────────────────────────────────────


def test_empty_session_passes():
    v = evaluate("default_preset_check", {"tracks": []})
    assert v["passed"]


def test_revision_brief_includes_track_name_and_class():
    state = {"tracks": [
        _track(3, "Pad Drift", [{"class_name": "Drift", "name": "Drift"}]),
    ]}
    v = evaluate("default_preset_check", state)
    brief = format_revision_brief(v)
    assert "track 3" in brief
    assert "Pad Drift" in brief
    assert "Drift" in brief

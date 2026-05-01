"""audit_layer report-shape tests.

These tests exercise the pure-computation `checks` module directly. The
@mcp.tool wrapper is integration-tested via the contract suite + live
session; here we verify each check's logic on synthetic inputs.
"""

from __future__ import annotations

from mcp_server.audit import checks


# ── Role inference ───────────────────────────────────────────────────


def test_infer_role_from_name():
    assert checks.infer_role("Kick", []) == "kick"
    assert checks.infer_role("BD 808", []) == "kick"
    assert checks.infer_role("Snare ghost", []) == "snare"
    assert checks.infer_role("Closed HH", []) == "hat"
    assert checks.infer_role("Sub Bass", []) == "bass"
    assert checks.infer_role("Pad Drift", []) == "pad"
    assert checks.infer_role("Atmos drone", []) == "atmos"
    assert checks.infer_role("Lead arp", []) == "lead"


def test_infer_role_falls_back_to_device_class():
    assert checks.infer_role("Track 7", [{"class_name": "DrumGroup"}]) == "perc"
    # Plain instrument -> lead is the conservative fallback
    assert checks.infer_role("Track 8", [{"class_name": "Operator"}]) == "lead"


def test_infer_role_unknown_when_nothing_matches():
    assert checks.infer_role("Group", [{"class_name": "AudioEffectGroupDevice"}]) == "unknown"


# ── §5.1 Timbre ──────────────────────────────────────────────────────


def test_timbre_n_a_when_no_fingerprint():
    result = checks.check_timbre("kick", None)
    assert result["severity"] == "n/a"


def test_timbre_pass_when_role_matches_dominant_band():
    fingerprint = {"bands": {"SUB_LOW": 0.9, "LOW": 0.7, "MID": 0.4, "HIGH": 0.1, "AIR": 0.05,
                              "LOW_MID": 0.3, "PRESENCE": 0.2}}
    result = checks.check_timbre("kick", fingerprint)
    assert result["severity"] == "pass"


def test_timbre_fail_when_role_mismatches():
    # A "kick" sample that's actually presence/air dominant — genuinely wrong
    fingerprint = {"bands": {"SUB_LOW": 0.05, "LOW": 0.1, "LOW_MID": 0.2, "MID": 0.3,
                              "PRESENCE": 0.95, "HIGH": 0.6, "AIR": 0.4}}
    result = checks.check_timbre("kick", fingerprint)
    assert result["severity"] == "fail"
    assert result["issues"]
    assert result["issues"][0]["code"] == "wrong_band_dominance"


def test_timbre_warn_when_secondary_in_expected():
    # Hat with PRESENCE secondary but MID dominant — close but off
    fingerprint = {"bands": {"SUB_LOW": 0.05, "LOW": 0.1, "LOW_MID": 0.2, "MID": 0.95,
                              "PRESENCE": 0.7, "HIGH": 0.3, "AIR": 0.2}}
    result = checks.check_timbre("hat", fingerprint)
    assert result["severity"] == "warn"
    assert result["issues"][0]["code"] == "off_band_dominance"


# ── §5.2 Sequence ────────────────────────────────────────────────────


def test_sequence_n_a_for_audio_track():
    result = checks.check_sequence("vox", [])
    assert result["severity"] == "n/a"


def test_sequence_flags_no_humanization():
    notes = [{"pitch": 60, "velocity": 100, "duration": 0.5} for _ in range(8)]
    result = checks.check_sequence("snare", [notes])
    codes = {i["code"] for i in result["issues"]}
    assert "no_humanization" in codes


def test_sequence_flags_no_ghosts_on_drums():
    # Snare with all hits at 100, no ghosts
    notes = [{"pitch": 38, "velocity": 100 + (i % 3) * 4, "duration": 0.25} for i in range(8)]
    result = checks.check_sequence("snare", [notes])
    codes = {i["code"] for i in result["issues"]}
    assert "no_ghost_notes" in codes


def test_sequence_passes_humanized_drum_with_ghosts():
    # Mix of accents (90-110) and ghosts (30-40)
    notes = []
    for i in range(16):
        v = 95 + (i % 5) * 3 if i % 4 == 0 else 35 + (i % 3) * 4
        notes.append({"pitch": 38, "velocity": v, "duration": 0.25 + (i % 3) * 0.05})
    result = checks.check_sequence("snare", [notes])
    assert result["severity"] in ("pass", "warn")  # humanized + ghosts present


def test_sequence_flags_low_pitch_variety_on_lead():
    notes = [{"pitch": 60, "velocity": 100 + i, "duration": 0.5 + i * 0.05} for i in range(8)]
    result = checks.check_sequence("lead", [notes])
    codes = {i["code"] for i in result["issues"]}
    assert "low_pitch_variety" in codes


# ── §5.3 Stereo ──────────────────────────────────────────────────────


def test_stereo_flags_panned_bass():
    track_info = {"mixer": {"panning": 0.3}}
    result = checks.check_stereo("bass", track_info)
    assert result["severity"] == "warn"
    assert result["issues"][0]["code"] == "panned_bass"


def test_stereo_passes_centered_bass():
    track_info = {"mixer": {"panning": 0.0}}
    result = checks.check_stereo("bass", track_info)
    assert result["severity"] == "pass"


# ── §5.4 Masking ─────────────────────────────────────────────────────


def test_masking_n_a_without_report():
    result = checks.check_masking(3, None)
    assert result["severity"] == "n/a"


def test_masking_filters_for_target_track():
    report = {"masking": {"entries": [
        {"track_a": 1, "track_b": 3, "band": "LOW", "severity": "high"},
        {"track_a": 2, "track_b": 5, "band": "MID", "severity": "warn"},
    ]}}
    result = checks.check_masking(3, report)
    assert result["severity"] == "fail"  # high severity triggers fail
    assert len(result["issues"]) == 1


# ── §5.5 Modulation ──────────────────────────────────────────────────


def test_modulation_fails_pad_with_zero_routings():
    devices = [{
        "class_name": "Drift",
        "parameters": [
            {"name": "Fil < Env", "value": 0.0},
            {"name": "Pe < Env", "value": 0.0},
            {"name": "LFO Amount", "value": 0.0},
        ],
    }]
    result = checks.check_modulation("pad", devices, clip_automation_present=False, wavetable_mod_routings=0)
    assert result["severity"] == "fail"
    assert result["issues"][0]["code"] == "static_layer"


def test_modulation_passes_with_routing():
    devices = [{
        "class_name": "Drift",
        "parameters": [
            {"name": "Fil < Env", "value": 0.5},
        ],
    }]
    result = checks.check_modulation("pad", devices, clip_automation_present=False, wavetable_mod_routings=0)
    assert result["severity"] == "pass"


def test_modulation_passes_with_automation_only():
    devices = [{"class_name": "Drift", "parameters": []}]
    result = checks.check_modulation("pad", devices, clip_automation_present=True, wavetable_mod_routings=0)
    assert result["severity"] == "pass"


# ── §5.6 Params ──────────────────────────────────────────────────────


def test_params_flags_unprogrammed_pad_synth():
    devices = [{
        "class_name": "Drift",
        "parameters": [
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Spread", "value": 0.0},
            {"name": "Detune", "value": 0.0},
            {"name": "Volume", "value": -6.0},
        ],
    }]
    result = checks.check_params("pad", devices)
    assert result["severity"] == "fail"
    assert result["issues"][0]["code"] == "unprogrammed_instrument"


def test_params_n_a_for_audio_track():
    result = checks.check_params("vox", [{"class_name": "Reverb", "parameters": []}])
    assert result["severity"] == "n/a"


# ── §5.8 Effects ─────────────────────────────────────────────────────


def test_effects_flags_kick_without_eq():
    devices = [{"class_name": "Simpler", "parameters": []}]
    result = checks.check_effects("kick", devices)
    codes = {i["code"] for i in result["issues"]}
    assert "no_eq" in codes


def test_effects_passes_when_chain_is_full():
    devices = [
        {"class_name": "Drift", "parameters": []},
        {"class_name": "EQ Eight", "parameters": []},
        {"class_name": "Compressor", "parameters": []},
        {"class_name": "Reverb", "parameters": []},
    ]
    result = checks.check_effects("lead", devices)
    assert result["severity"] == "pass"


# ── Severity rollup + fix ranking ───────────────────────────────────


def test_rollup_severity_picks_worst():
    check_dict = {
        "a": {"severity": "pass"},
        "b": {"severity": "warn"},
        "c": {"severity": "fail"},
        "d": {"severity": "n/a"},
    }
    assert checks.rollup_severity(check_dict) == "fail"


# ── Live-session shape regressions (validated 2026-05-01) ───────────


def test_multisampler_is_recognized_as_instrument():
    """Phantasm Pad uses class_name='MultiSampler', not 'Sampler'."""
    devices = [{
        "class_name": "MultiSampler",
        "parameters": [
            {"name": "Volume", "value": -16.3},
            {"name": "Filt < Vel", "value": 0.59},
            {"name": "Filt < Key", "value": 1.0},
        ],
    }]
    result = checks.check_params("pad", devices)
    assert result["severity"] != "n/a", "MultiSampler must be recognized as an instrument"


def test_originalsimpler_is_recognized_as_instrument():
    """Hihat 808 Close uses class_name='OriginalSimpler', not 'Simpler'."""
    devices = [{
        "class_name": "OriginalSimpler",
        "parameters": [{"name": "Volume", "value": 0.0}],
    }]
    result = checks.check_samples("hat", devices, slice_classifications=None)
    assert result["severity"] != "n/a", "OriginalSimpler must be recognized as Simpler"


def test_modulation_counts_native_velocity_routings():
    """Filt < Vel, Vol < Vel are real routings, not just envelope routings."""
    devices = [{
        "class_name": "MultiSampler",
        "parameters": [
            {"name": "Filt < Vel", "value": 0.59},
            {"name": "Vol < Vel", "value": 0.41},
            {"name": "Filt < Key", "value": 1.0},
            # No envelope amounts and no LFO routings
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Fe On", "value": 0.0},
            {"name": "Filt < LFO", "value": 0.0},
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Pe On", "value": 0.0},
        ],
    }]
    result = checks.check_modulation("pad", devices, clip_automation_present=False, wavetable_mod_routings=0)
    assert result["severity"] == "pass", \
        f"Pad with Filt<Vel + Vol<Vel + Filt<Key should pass §4. Got {result}"
    assert result["evidence"]["routings_count"] >= 2


def test_modulation_does_not_double_count_disabled_envelope():
    """Fe < Env: 0.5 with Fe On: 0 is functionally OFF — should not count."""
    devices = [{
        "class_name": "Drift",
        "parameters": [
            {"name": "Fe < Env", "value": 0.5},
            {"name": "Fe On", "value": 0.0},  # filter env disabled
        ],
    }]
    result = checks.check_modulation("pad", devices, clip_automation_present=False, wavetable_mod_routings=0)
    assert result["severity"] == "fail", \
        "Disabled filter env should not count as a routing"


def test_params_not_flagged_when_filter_env_intentionally_off():
    """Fe < Env: 0 + Fe On: 0 = deliberate, not lazy. Don't flag."""
    devices = [{
        "class_name": "MultiSampler",
        "parameters": [
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Fe On", "value": 0.0},  # explicitly off
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Pe On", "value": 0.0},  # explicitly off
            {"name": "Spread", "value": 30.0},  # programmed
            {"name": "Detune", "value": 5.0},   # programmed
        ],
    }]
    result = checks.check_params("pad", devices)
    # Fe<Env and Pe<Env should be excused. Only counts: nothing problematic.
    assert result["severity"] == "pass"


def test_params_still_flags_when_filter_env_on_but_amount_zero():
    """Fe On: 1 + Fe < Env: 0 IS the lazy case."""
    devices = [{
        "class_name": "Drift",
        "parameters": [
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Fe On", "value": 1.0},  # enabled but no amount
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Pe On", "value": 1.0},  # enabled but no amount
            {"name": "Spread", "value": 0.0},
        ],
    }]
    result = checks.check_params("pad", devices)
    # 3 zero shaping params on a pad = unprogrammed
    assert result["severity"] in ("warn", "fail")


def test_modulation_lfo_routing_requires_lfo_on():
    """Filt < LFO: 0.5 with L On: 0 doesn't actually move anything."""
    devices = [{
        "class_name": "OriginalSimpler",
        "parameters": [
            {"name": "Filt < LFO", "value": 0.5},
            {"name": "L On", "value": 0.0},  # LFO is off
        ],
    }]
    result = checks.check_modulation("pad", devices, clip_automation_present=False, wavetable_mod_routings=0)
    assert result["severity"] == "fail"


def test_modulation_lfo_routing_counts_when_lfo_on():
    devices = [{
        "class_name": "OriginalSimpler",
        "parameters": [
            {"name": "Filt < LFO", "value": 0.5},
            {"name": "L On", "value": 1.0},  # LFO on
        ],
    }]
    result = checks.check_modulation("pad", devices, clip_automation_present=False, wavetable_mod_routings=0)
    assert result["severity"] == "pass"


# ── BUG-E: drum role suppression for many_default_params ─────────────


def test_params_suppresses_default_warn_for_kick():
    """Kick with bare Simpler + default Spread/Detune/Pe<Env/Fe<Env is fine.
    HATS and KICK both falsely warned in 2026-05-01 live test."""
    devices = [{
        "class_name": "OriginalSimpler",
        "parameters": [
            {"name": "Spread", "value": 0.0},
            {"name": "Detune", "value": 0.0},
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Pe On", "value": 1.0},  # envelope on but not used — still fine for kick
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Fe On", "value": 1.0},
        ],
    }]
    result = checks.check_params("kick", devices)
    assert result["severity"] == "pass", \
        f"kick role should suppress many_default_params warn. Got {result}"
    assert result["evidence"].get("suppressed_for_role") == "kick"


def test_params_suppresses_default_warn_for_hat():
    devices = [{
        "class_name": "OriginalSimpler",
        "parameters": [
            {"name": "Spread", "value": 0.0},
            {"name": "Detune", "value": 0.0},
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Pe On", "value": 1.0},
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Fe On", "value": 1.0},
        ],
    }]
    result = checks.check_params("hat", devices)
    assert result["severity"] == "pass"


def test_params_still_strict_for_pad_with_simple_devices():
    """Pad with all defaults SHOULD still fail — pads are not simple-by-design."""
    devices = [{
        "class_name": "Drift",
        "parameters": [
            {"name": "Spread", "value": 0.0},
            {"name": "Detune", "value": 0.0},
            {"name": "Pe < Env", "value": 0.0},
            {"name": "Pe On", "value": 1.0},
            {"name": "Fe < Env", "value": 0.0},
            {"name": "Fe On", "value": 1.0},
        ],
    }]
    result = checks.check_params("pad", devices)
    assert result["severity"] == "fail"
    assert result["issues"][0]["code"] == "unprogrammed_instrument"


def test_rank_fixes_orders_by_priority():
    check_dict = {
        "modulation": {"severity": "fail", "issues": [{"code": "static_layer", "detail": "x"}]},
        "effects": {"severity": "warn", "issues": [{"code": "no_eq", "detail": "y"}]},
        "sequence": {"severity": "warn", "issues": [{"code": "uniform_durations", "detail": "z"}]},
    }
    fixes = checks.rank_fixes(check_dict)
    priorities = [f["priority"] for f in fixes]
    # high before medium before low
    assert priorities[0] == "high"
    assert priorities[-1] == "low"

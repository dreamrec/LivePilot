"""Phase 1 grader — §7.3 layer-accumulation rubric tests.

Pure-computation checks exercised on synthetic state.
"""

from __future__ import annotations

from mcp_server.grader import evaluate, format_revision_brief


def _track(index: int, name: str, volume: float, devices: list[dict] | None = None) -> dict:
    return {
        "index": index,
        "name": name,
        "mixer": {"volume": volume, "panning": 0.0},
        "devices": devices or [],
    }


def _by_id(verdict: dict, criterion_id: str) -> dict:
    for c in verdict["criteria"]:
        if c["id"] == criterion_id:
            return c
    raise KeyError(criterion_id)


# ── Track count ─────────────────────────────────────────────────────


def test_track_count_pass_when_under_warn_threshold():
    state = {"tracks": [_track(i, f"Track {i}", 0.7) for i in range(5)]}
    v = evaluate("layer_accumulation", state)
    c = _by_id(v, "track_count_within_limit")
    assert c["severity"] == "pass"
    assert c["passed"]


def test_track_count_warn_when_between_thresholds():
    state = {"tracks": [_track(i, f"Track {i}", 0.7) for i in range(10)]}
    v = evaluate("layer_accumulation", state)
    c = _by_id(v, "track_count_within_limit")
    assert c["severity"] == "warn"
    assert c["passed"]
    assert c["issues"][0]["code"] == "track_count_high"


def test_track_count_fail_when_at_or_above_fail_threshold():
    state = {"tracks": [_track(i, f"Track {i}", 0.7) for i in range(12)]}
    v = evaluate("layer_accumulation", state)
    c = _by_id(v, "track_count_within_limit")
    assert c["severity"] == "fail"
    assert not c["passed"]
    assert c["issues"][0]["code"] == "track_count_exceeded"


def test_overall_verdict_fails_when_any_blocking_check_fails():
    state = {"tracks": [_track(i, f"Track {i}", 0.7) for i in range(15)]}
    v = evaluate("layer_accumulation", state)
    assert not v["passed"]


# ── Buried tracks ────────────────────────────────────────────────────


def test_buried_check_passes_when_no_low_volume_tracks():
    state = {"tracks": [_track(0, "Kick", 0.7), _track(1, "Pad Drift", 0.4)]}
    c = _by_id(evaluate("layer_accumulation", state), "no_extreme_buried_track")
    assert c["severity"] == "pass"
    assert c["passed"]


def test_buried_check_fails_when_non_ghost_track_below_threshold():
    state = {
        "tracks": [
            _track(0, "Kick", 0.7),
            _track(1, "Buried lead", 0.10),
        ]
    }
    c = _by_id(evaluate("layer_accumulation", state), "no_extreme_buried_track")
    assert c["severity"] == "fail"
    assert not c["passed"]
    assert c["issues"][0]["code"] == "extreme_buried_track"
    assert c["issues"][0]["track_index"] == 1


def test_buried_check_passes_when_track_is_ghost_tagged():
    state = {
        "tracks": [
            _track(0, "Kick", 0.7),
            _track(1, "Snare ghost layer", 0.10),
        ]
    }
    c = _by_id(evaluate("layer_accumulation", state), "no_extreme_buried_track")
    assert c["severity"] == "pass"
    assert c["passed"]
    assert len(c["evidence"]["buried_ghost"]) == 1


def test_buried_check_fail_overrides_aggregate_pass():
    state = {
        "tracks": [
            _track(0, "Kick", 0.7),
            _track(1, "Mediocre vocal", 0.08),
        ]
    }
    v = evaluate("layer_accumulation", state)
    assert not v["passed"]


# ── Role volume hierarchy ────────────────────────────────────────────


def test_role_band_pass_when_kick_in_anchor_band():
    state = {"tracks": [_track(0, "Kick 808", 0.75)]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "pass"


def test_role_band_warns_when_kick_too_quiet():
    state = {"tracks": [_track(0, "Kick 808", 0.40)]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "warn"
    issue = c["issues"][0]
    assert issue["code"] == "role_volume_off_band"
    assert "Anchor role too quiet" in issue["detail"]


def test_role_band_warns_when_pad_too_loud():
    state = {"tracks": [_track(0, "Pad Drift", 0.80)]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "warn"
    assert "shouldn’t dominate" in c["issues"][0]["detail"]


def test_role_band_warn_does_not_fail_overall_verdict():
    state = {"tracks": [_track(0, "Pad Drift", 0.80)]}
    v = evaluate("layer_accumulation", state)
    assert v["passed"]


def test_role_band_pass_for_atmos_in_low_band():
    state = {"tracks": [_track(0, "Atmos drone", 0.30)]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "pass"


# ── §7.3 false-positive fix: unknown-role skip ────────────────────────


def test_role_band_skips_unknown_role_default_live_tracks():
    """Live default tracks ('1-MIDI' etc., 0.85 unity) should NOT fire false positives.

    Regression test for the deep-test finding 2026-05-08: empty default
    project had 4 tracks at default unity volume, all flagged as 'above
    expected band' because role inference returned 'unknown'.
    """
    state = {"tracks": [
        _track(0, "1-MIDI", 0.85),
        _track(1, "2-MIDI", 0.85),
        _track(2, "3-Audio", 0.85),
        _track(3, "4-Audio", 0.85),
    ]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "pass"
    assert c["evidence"]["skipped_unknown"] == 4
    assert c["evidence"]["in_band"] == 0
    assert c["evidence"]["out_of_band"] == []
    assert "skipped" in c["summary"]


def test_role_band_mixes_role_tagged_with_unknown():
    """A real session has some role-tagged + some default-named tracks."""
    state = {"tracks": [
        _track(0, "Kick 808", 0.75),     # known: kick → pass
        _track(1, "1-MIDI", 0.85),       # unknown → skip
        _track(2, "Pad Drift", 0.40),    # known: pad → pass
        _track(3, "2-Audio", 0.85),      # unknown → skip
    ]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "pass"
    assert c["evidence"]["in_band"] == 2
    assert c["evidence"]["skipped_unknown"] == 2


def test_role_band_warn_still_fires_on_role_tagged_violation():
    """Fix #1 must NOT silence legitimate warnings on role-tagged tracks."""
    state = {"tracks": [
        _track(0, "Pad Drift", 0.85),  # pad band [0.25, 0.50] → above
        _track(1, "1-MIDI", 0.85),     # unknown → skip
    ]}
    c = _by_id(evaluate("layer_accumulation", state), "role_volume_hierarchy")
    assert c["severity"] == "warn"
    assert len(c["issues"]) == 1
    assert c["issues"][0]["track_index"] == 0
    assert c["evidence"]["skipped_unknown"] == 1


# ── Realistic scenarios ──────────────────────────────────────────────


def test_clean_5_layer_session_passes_all_criteria():
    state = {
        "tracks": [
            _track(0, "Kick 808", 0.75),
            _track(1, "Sub Bass", 0.70),
            _track(2, "Closed HH", 0.55),
            _track(3, "Pad Drift", 0.40),
            _track(4, "Lead arp", 0.65),
        ]
    }
    v = evaluate("layer_accumulation", state)
    assert v["passed"]
    for c in v["criteria"]:
        assert c["severity"] in ("pass", "warn"), f"{c['id']} severity={c['severity']}"


def test_chronic_anti_pattern_12_buried_layers_fails():
    """The §7.3 antithesis — 12 tracks, half buried below threshold."""
    tracks = [
        _track(i, f"Layer {i}", 0.10 if i % 2 == 0 else 0.35)
        for i in range(12)
    ]
    v = evaluate("layer_accumulation", {"tracks": tracks})
    assert not v["passed"]
    failed_ids = {c["id"] for c in v["criteria"] if c["severity"] == "fail"}
    assert "track_count_within_limit" in failed_ids
    assert "no_extreme_buried_track" in failed_ids


# ── Revision brief formatting ────────────────────────────────────────


def test_revision_brief_empty_when_verdict_passes():
    state = {"tracks": [_track(0, "Kick 808", 0.75)]}
    v = evaluate("layer_accumulation", state)
    assert v["passed"]
    assert format_revision_brief(v) == ""


def test_revision_brief_lists_failures_with_track_refs():
    state = {
        "tracks": [
            _track(0, "Kick 808", 0.75),
            _track(1, "Buried wash", 0.08),
        ]
    }
    v = evaluate("layer_accumulation", state)
    brief = format_revision_brief(v)
    assert "Blocking failures" in brief
    assert "no_extreme_buried_track" in brief
    assert "track 1" in brief
    assert "Buried wash" in brief


def test_revision_brief_separates_blocking_from_advisory():
    state = {
        "tracks": [
            _track(i, f"Track {i}", 0.7) for i in range(15)
        ] + [_track(15, "Pad Drift", 0.80)]  # role band warn
    }
    v = evaluate("layer_accumulation", state)
    brief = format_revision_brief(v)
    assert "Blocking failures" in brief
    assert "Advisory" in brief
    assert brief.index("Blocking failures") < brief.index("Advisory")


# ── Edge cases ───────────────────────────────────────────────────────


def test_empty_session_passes_all_checks():
    v = evaluate("layer_accumulation", {"tracks": []})
    assert v["passed"]


def test_track_with_missing_volume_skipped_gracefully():
    state = {"tracks": [{"index": 0, "name": "Kick", "mixer": {}, "devices": []}]}
    v = evaluate("layer_accumulation", state)
    assert v["passed"]


def test_unknown_rubric_raises():
    import pytest as _pt
    with _pt.raises(KeyError):
        evaluate("does_not_exist", {"tracks": []})

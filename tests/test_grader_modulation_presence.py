"""§4 modulation-presence rubric tests."""

from __future__ import annotations

from mcp_server.grader import evaluate, format_revision_brief


def _track(
    index: int,
    name: str,
    *,
    modulation_count: int | None = None,
    has_clip_automation: bool | None = None,
    devices: list[dict] | None = None,
) -> dict:
    t = {
        "index": index,
        "name": name,
        "mixer": {"volume": 0.7, "panning": 0.0},
        "devices": devices or [],
    }
    if modulation_count is not None:
        t["modulation_count"] = modulation_count
    if has_clip_automation is not None:
        t["has_clip_automation"] = has_clip_automation
    return t


def _by_id(verdict: dict, criterion_id: str) -> dict:
    for c in verdict["criteria"]:
        if c["id"] == criterion_id:
            return c
    raise KeyError(criterion_id)


# ── Pass cases ───────────────────────────────────────────────────────


def test_pass_when_all_melodic_layers_have_modulation():
    state = {"tracks": [
        _track(0, "Pad Drift", modulation_count=3, has_clip_automation=False),
        _track(1, "Sub Bass", modulation_count=1, has_clip_automation=True),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "pass"
    assert c["passed"]


def test_pass_when_motion_via_automation_only():
    state = {"tracks": [
        _track(0, "Pad Drift", modulation_count=0, has_clip_automation=True),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "pass"


def test_pass_when_motion_via_modulation_only():
    state = {"tracks": [
        _track(0, "Lead arp", modulation_count=2, has_clip_automation=False),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "pass"


# ── Warn cases ───────────────────────────────────────────────────────


def test_warn_when_melodic_layer_static():
    state = {"tracks": [
        _track(0, "Pad Drift", modulation_count=0, has_clip_automation=False),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "warn"
    assert c["passed"]  # advisory, not blocking
    assert c["issues"][0]["code"] == "static_melodic_layer"
    assert c["issues"][0]["track_index"] == 0


def test_warn_lists_only_static_tracks():
    state = {"tracks": [
        _track(0, "Pad Drift", modulation_count=2, has_clip_automation=False),
        _track(1, "Lead static", modulation_count=0, has_clip_automation=False),
        _track(2, "Sub Bass", modulation_count=0, has_clip_automation=True),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "warn"
    assert len(c["issues"]) == 1
    assert c["issues"][0]["track_index"] == 1


def test_overall_verdict_passes_on_warn():
    state = {"tracks": [
        _track(0, "Pad Drift", modulation_count=0, has_clip_automation=False),
    ]}
    v = evaluate("modulation_presence", state)
    assert v["passed"]


# ── Role scoping ─────────────────────────────────────────────────────


def test_drum_tracks_excluded_from_modulation_check():
    state = {"tracks": [
        _track(0, "Kick 808", modulation_count=0, has_clip_automation=False),
        _track(1, "Closed HH", modulation_count=0, has_clip_automation=False),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "n/a"


def test_atmos_track_required_to_have_motion():
    state = {"tracks": [
        _track(0, "Atmos drone", modulation_count=0, has_clip_automation=False),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "warn"


# ── n/a cases ────────────────────────────────────────────────────────


def test_na_when_modulation_data_missing_on_all_tracks():
    state = {"tracks": [
        _track(0, "Pad Drift"),  # no modulation_count, no has_clip_automation
        _track(1, "Sub Bass"),
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "n/a"
    assert len(c["evidence"]["unknown"]) == 2


def test_partial_data_uses_only_populated_tracks():
    state = {"tracks": [
        _track(0, "Pad Drift", modulation_count=2),
        _track(1, "Sub Bass"),  # missing both — unknown
    ]}
    c = _by_id(evaluate("modulation_presence", state), "melodic_layers_have_motion")
    assert c["severity"] == "pass"
    assert len(c["evidence"]["unknown"]) == 1


def test_empty_session_returns_na():
    v = evaluate("modulation_presence", {"tracks": []})
    c = _by_id(v, "melodic_layers_have_motion")
    assert c["severity"] == "n/a"
    assert v["passed"]


def test_revision_brief_for_static_layers_lists_track_refs():
    state = {"tracks": [
        _track(2, "Lead arp", modulation_count=0, has_clip_automation=False),
    ]}
    v = evaluate("modulation_presence", state)
    brief = format_revision_brief(v)
    assert "Advisory" in brief
    assert "track 2" in brief
    assert "static_melodic_layer" in brief

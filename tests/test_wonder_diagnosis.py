"""Unit tests for Wonder Mode diagnosis builder."""

from mcp_server.wonder_mode.diagnosis import build_diagnosis
from mcp_server.wonder_mode.session import WonderDiagnosis


# ── Problem class mapping ────────────────────────────────────────


def test_stuckness_drives_problem_class():
    """Stuckness report's primary_rescue_type becomes problem_class."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.7,
            "level": "stuck",
            "primary_rescue_type": "overpolished_loop",
            "secondary_rescue_types": ["contrast_needed"],
        },
    )
    assert diag.problem_class == "overpolished_loop"
    assert diag.trigger_reason == "stuckness_detected"
    assert diag.confidence == 0.7


def test_no_stuckness_gives_exploration():
    """Without stuckness data, problem_class defaults to exploration."""
    diag = build_diagnosis()
    assert diag.problem_class == "exploration"
    assert diag.trigger_reason == "user_request"
    assert diag.candidate_domains == []


def test_low_stuckness_still_user_request():
    """Stuckness confidence < 0.2 treated as user_request, not stuckness."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.1,
            "level": "flowing",
            "primary_rescue_type": "",
        },
    )
    assert diag.trigger_reason == "user_request"
    assert diag.problem_class == "exploration"


# ── Candidate domains ────────────────────────────────────────────


def test_overpolished_loop_domains():
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.6,
            "level": "stuck",
            "primary_rescue_type": "overpolished_loop",
        },
    )
    assert diag.candidate_domains == ["arrangement", "transition"]


def test_identity_unclear_domains():
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.5,
            "level": "stuck",
            "primary_rescue_type": "identity_unclear",
        },
    )
    assert diag.candidate_domains == ["sound_design", "mix"]


def test_exploration_has_no_domain_restriction():
    diag = build_diagnosis()
    assert diag.candidate_domains == []


def test_all_rescue_types_map_to_domains():
    """Every RESCUE_TYPE must map to at least one candidate domain."""
    from mcp_server.stuckness_detector.models import RESCUE_TYPES
    for rt in RESCUE_TYPES:
        diag = build_diagnosis(
            stuckness_report={
                "confidence": 0.6,
                "level": "stuck",
                "primary_rescue_type": rt,
            },
        )
        assert len(diag.candidate_domains) > 0, f"No domains for {rt}"


# ── SongBrain integration ────────────────────────────────────────


def test_song_brain_provides_identity():
    diag = build_diagnosis(
        song_brain={
            "identity_core": "Dark minimal techno",
            "identity_confidence": 0.8,
            "sacred_elements": [
                {"element_type": "groove", "description": "808 kick", "salience": 0.8},
            ],
        },
    )
    assert diag.current_identity == "Dark minimal techno"
    assert len(diag.sacred_elements) == 1
    assert diag.sacred_elements[0]["element_type"] == "groove"


def test_missing_song_brain_degrades():
    diag = build_diagnosis()
    assert diag.current_identity == ""
    assert diag.sacred_elements == []
    assert "song_brain" in diag.degraded_capabilities


def test_missing_stuckness_not_degraded():
    """No stuckness = user_request trigger, not a degradation."""
    diag = build_diagnosis(
        song_brain={"identity_core": "test", "sacred_elements": []},
    )
    assert "stuckness" not in diag.degraded_capabilities
    assert diag.trigger_reason == "user_request"


# ── Action ledger integration ────────────────────────────────────


def test_repeated_undos_trigger():
    """3+ undos in action ledger should set trigger_reason to repeated_undos."""
    ledger = [{"kept": False}] * 4 + [{"kept": True}] * 2
    diag = build_diagnosis(action_ledger=ledger)
    assert diag.trigger_reason == "repeated_undos"


# ── Return type ──────────────────────────────────────────────────


def test_returns_wonder_diagnosis():
    diag = build_diagnosis()
    assert isinstance(diag, WonderDiagnosis)


def test_to_dict_round_trip():
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.6,
            "level": "stuck",
            "primary_rescue_type": "contrast_needed",
        },
        song_brain={
            "identity_core": "Ambient",
            "sacred_elements": [{"element_type": "pad", "description": "Pad wash"}],
        },
    )
    d = diag.to_dict()
    assert d["problem_class"] == "contrast_needed"
    assert d["current_identity"] == "Ambient"
    assert isinstance(d["sacred_elements"], list)

"""Unit tests for Stuckness Detector — uses real LedgerEntry.to_dict() format."""

from mcp_server.stuckness_detector.detector import detect_stuckness, suggest_rescue
from mcp_server.stuckness_detector.models import RESCUE_TYPES


def _undo_entry(n=1):
    """A ledger entry representing an undone move."""
    return {
        "id": f"move_abc_{n:04d}", "timestamp_ms": n * 1000,
        "engine": "mix", "move_class": "set_param", "intent": "tweak EQ",
        "actions": [{"tool": "set_device_parameter", "summary": "EQ boost"}],
        "kept": False, "score": 0.0, "scope": {"track": "EQ Eight"},
        "before_refs": {}, "after_refs": {}, "evaluation": {},
        "undo_scope": "micro", "memory_candidate": False,
    }


def _kept_entry(n=1, tool="set_device_parameter", scope_track="EQ Eight"):
    """A ledger entry representing a kept parameter tweak."""
    return {
        "id": f"move_abc_{n:04d}", "timestamp_ms": n * 1000,
        "engine": "mix", "move_class": "set_param", "intent": "tweak",
        "actions": [{"tool": tool, "summary": f"adjust {scope_track}"}],
        "kept": True, "score": 0.5, "scope": {"track": scope_track},
        "before_refs": {}, "after_refs": {}, "evaluation": {},
        "undo_scope": "micro", "memory_candidate": False,
    }


def _structural_entry(n=1):
    """A ledger entry representing a structural edit."""
    return {
        "id": f"move_abc_{n:04d}", "timestamp_ms": n * 1000,
        "engine": "arrangement", "move_class": "create", "intent": "add clip",
        "actions": [{"tool": "create_clip", "summary": "new clip in scene 2"}],
        "kept": True, "score": 0.5, "scope": {},
        "before_refs": {}, "after_refs": {}, "evaluation": {},
        "undo_scope": "micro", "memory_candidate": False,
    }


# ── Stuckness detection ──────────────────────────────────────────


def test_flowing_when_no_history():
    report = detect_stuckness(action_history=[])
    assert report.level == "flowing"
    assert report.confidence == 0.0


def test_stuck_from_repeated_undos():
    history = [_undo_entry(i) for i in range(6)]
    report = detect_stuckness(action_history=history)
    assert report.level in ("slowing", "stuck", "deeply_stuck")
    assert any(s.signal_type == "repeated_undo" for s in report.signals)


def test_stuck_from_local_tweaking():
    history = [_kept_entry(i, scope_track="EQ Eight") for i in range(8)]
    report = detect_stuckness(action_history=history)
    assert any(s.signal_type == "local_tweaking" for s in report.signals)


def test_flowing_with_varied_structural_edits():
    """Varied structural edits with different intents should report flowing."""
    history = [
        {**_structural_entry(1), "intent": "create intro clip"},
        {**_kept_entry(2), "intent": "adjust volume"},
        {**_structural_entry(3), "intent": "duplicate verse scene"},
        {**_structural_entry(4), "intent": "add chorus track"},
    ]
    report = detect_stuckness(action_history=history)
    assert report.level == "flowing"


def test_stuck_from_long_loop_no_structure():
    history = [_kept_entry(i) for i in range(20)]
    report = detect_stuckness(action_history=history)
    long_loop = [s for s in report.signals if "loop" in s.signal_type or "structure" in s.signal_type]
    assert len(long_loop) >= 1


def test_identity_unclear_signal():
    report = detect_stuckness(
        action_history=[_kept_entry(i) for i in range(5)],
        song_brain={"identity_confidence": 0.1},
    )
    assert any(s.signal_type == "identity_unclear" for s in report.signals)


def test_high_density_signal():
    report = detect_stuckness(
        action_history=[],
        session_info={"track_count": 24},
    )
    assert any(s.signal_type == "high_density" for s in report.signals)


# ── Rescue classification ────────────────────────────────────────


def test_rescue_type_from_identity_unclear():
    report = detect_stuckness(
        action_history=[_kept_entry(i) for i in range(5)],
        song_brain={"identity_confidence": 0.1},
    )
    assert report.primary_rescue_type == "identity_unclear"


def test_rescue_type_from_single_loop():
    report = detect_stuckness(
        action_history=[_kept_entry(i) for i in range(25)],
        section_count=1,
    )
    assert report.primary_rescue_type in ("overpolished_loop", "section_missing", "contrast_needed")


# ── Rescue suggestions ──────────────────────────────────────────


def test_gentle_mode_returns_one():
    report = detect_stuckness(action_history=[_undo_entry(i) for i in range(6)])
    suggestions = suggest_rescue(report, mode="gentle")
    assert len(suggestions) <= 1


def test_direct_mode_returns_up_to_three():
    report = detect_stuckness(action_history=[_undo_entry(i) for i in range(6)])
    suggestions = suggest_rescue(report, mode="direct")
    assert 1 <= len(suggestions) <= 3


def test_rescue_has_strategies():
    report = detect_stuckness(action_history=[_undo_entry(i) for i in range(6)])
    suggestions = suggest_rescue(report, mode="gentle")
    for s in suggestions:
        assert len(s.strategies) >= 2


def test_no_rescue_when_flowing():
    report = detect_stuckness(action_history=[])
    suggestions = suggest_rescue(report, mode="direct")
    assert len(suggestions) == 0


def test_multiple_signals_compound_confidence():
    """Multiple stuckness signals should increase confidence, not average."""
    history_single = [_undo_entry(i) for i in range(6)]
    report_single = detect_stuckness(action_history=history_single)

    report_multi = detect_stuckness(
        action_history=history_single,
        session_info={"track_count": 24},
        song_brain={"identity_confidence": 0.1},
    )
    assert report_multi.confidence > report_single.confidence


def test_all_rescue_types_valid():
    assert len(RESCUE_TYPES) == 8


def test_diagnosis_readable():
    report = detect_stuckness(action_history=[_undo_entry(i) for i in range(6)])
    assert report.diagnosis
    assert len(report.diagnosis) > 10

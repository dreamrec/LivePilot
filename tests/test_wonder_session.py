"""Unit tests for WonderSession and WonderDiagnosis models."""

from mcp_server.wonder_mode.session import (
    WonderDiagnosis,
    WonderSession,
    get_wonder_session,
    store_wonder_session,
    _wonder_sessions,
)


def setup_function():
    _wonder_sessions.clear()


# ── Creation and storage ─────────────────────────────────────────


def test_session_creation():
    ws = WonderSession(session_id="ws_001", request_text="make it magical")
    assert ws.session_id == "ws_001"
    assert ws.status == "diagnosing"
    assert ws.outcome == "pending"
    assert ws.variant_count_actual == 0
    assert ws.variants == []


def test_store_and_retrieve():
    ws = WonderSession(session_id="ws_002", request_text="test")
    store_wonder_session(ws)
    retrieved = get_wonder_session("ws_002")
    assert retrieved is ws


def test_retrieve_missing_returns_none():
    assert get_wonder_session("nonexistent") is None


def test_eviction_at_capacity():
    for i in range(12):
        store_wonder_session(
            WonderSession(session_id=f"ws_{i:03d}", request_text=f"req {i}")
        )
    # First 2 should be evicted (max 10)
    assert get_wonder_session("ws_000") is None
    assert get_wonder_session("ws_001") is None
    # Last 10 should remain
    assert get_wonder_session("ws_002") is not None
    assert get_wonder_session("ws_011") is not None


# ── Status transitions ───────────────────────────────────────────


def test_status_defaults_to_diagnosing():
    ws = WonderSession(session_id="ws_s", request_text="test")
    assert ws.status == "diagnosing"


def test_valid_transitions():
    ws = WonderSession(session_id="ws_t", request_text="test")
    assert ws.transition_to("variants_ready") is True
    assert ws.status == "variants_ready"
    assert ws.transition_to("previewing") is True
    assert ws.status == "previewing"
    assert ws.transition_to("resolved") is True
    assert ws.status == "resolved"


def test_invalid_transitions_rejected():
    ws = WonderSession(session_id="ws_inv", request_text="test")
    # Can't go from diagnosing to resolved directly
    assert ws.transition_to("resolved") is False
    assert ws.status == "diagnosing"
    # Can't go from diagnosing to previewing
    assert ws.transition_to("previewing") is False
    assert ws.status == "diagnosing"


def test_resolved_is_terminal():
    ws = WonderSession(session_id="ws_term", request_text="test")
    ws.transition_to("variants_ready")
    ws.transition_to("resolved")
    # Can't transition from resolved
    assert ws.transition_to("diagnosing") is False
    assert ws.transition_to("variants_ready") is False
    assert ws.status == "resolved"


# ── Degradation ──────────────────────────────────────────────────


def test_degraded_reason_set():
    ws = WonderSession(
        session_id="ws_d",
        request_text="test",
        variant_count_actual=1,
        degraded_reason="Only 1 distinct executable move found",
    )
    assert ws.degraded_reason != ""
    assert ws.variant_count_actual == 1


# ── WonderDiagnosis ──────────────────────────────────────────────


def test_diagnosis_creation():
    diag = WonderDiagnosis(
        trigger_reason="user_request",
        problem_class="exploration",
        current_identity="Dark minimal techno",
        sacred_elements=[{"element_type": "groove", "description": "808 kick"}],
        blocked_dimensions=[],
        candidate_domains=[],
    )
    assert diag.trigger_reason == "user_request"
    assert diag.problem_class == "exploration"
    assert diag.confidence == 0.0
    assert diag.variant_budget == 3
    assert diag.degraded_capabilities == []


def test_diagnosis_to_dict():
    diag = WonderDiagnosis(
        trigger_reason="stuckness_detected",
        problem_class="overpolished_loop",
        current_identity="Ambient drone",
        sacred_elements=[],
        blocked_dimensions=["energy"],
        candidate_domains=["arrangement", "transition"],
        confidence=0.7,
        degraded_capabilities=["song_brain"],
    )
    d = diag.to_dict()
    assert d["trigger_reason"] == "stuckness_detected"
    assert d["problem_class"] == "overpolished_loop"
    assert d["candidate_domains"] == ["arrangement", "transition"]
    assert d["confidence"] == 0.7
    assert "song_brain" in d["degraded_capabilities"]

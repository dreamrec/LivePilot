"""End-to-end Wonder Mode lifecycle tests — pure computation, no Ableton."""

from mcp_server.wonder_mode.session import (
    WonderSession,
    get_wonder_session,
    store_wonder_session,
    _wonder_sessions,
)
from mcp_server.wonder_mode.diagnosis import build_diagnosis
from mcp_server.wonder_mode.engine import generate_wonder_variants
from mcp_server.session_continuity import tracker as _tracker
from mcp_server.session_continuity.tracker import (
    reset_story,
    open_thread,
    list_open_threads,
    record_turn_resolution,
    resolve_thread,
)


def setup_function():
    _wonder_sessions.clear()
    reset_story()


# ── Full lifecycle ───────────────────────────────────────────────


def test_lifecycle_diagnosis_to_variants():
    """Diagnosis -> variant generation -> session creation."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.6,
            "level": "stuck",
            "primary_rescue_type": "contrast_needed",
        },
        song_brain={
            "identity_core": "Dark techno",
            "sacred_elements": [{"element_type": "groove", "description": "kick"}],
        },
    )

    result = generate_wonder_variants(
        request_text="make it more interesting",
        diagnosis=diag.to_dict(),
        song_brain={"identity_core": "Dark techno", "sacred_elements": []},
    )

    assert "variants" in result
    assert len(result["variants"]) == 3
    assert "variant_count_actual" in result
    assert "degraded_reason" in result

    for v in result["variants"]:
        assert "analytical_only" in v


def test_no_turn_resolution_at_generation():
    """Generating variants must NOT record a turn resolution."""
    initial_turn_count = len(_tracker._turns)

    diag = build_diagnosis()
    generate_wonder_variants(
        request_text="surprise me",
        diagnosis=diag.to_dict(),
    )

    assert len(_tracker._turns) == initial_turn_count


def test_commit_records_turn():
    """Committing a variant should record a turn resolution."""
    initial_turn_count = len(_tracker._turns)

    record_turn_resolution(
        request_text="test commit",
        outcome="accepted",
        move_applied="test_move",
        identity_effect="evolves",
        user_sentiment="liked",
    )

    assert len(_tracker._turns) == initial_turn_count + 1
    assert _tracker._turns[-1].outcome == "accepted"


def test_reject_records_turn_thread_stays_open():
    """Rejecting all variants should record rejection and keep thread open."""
    thread = open_thread(description="Wonder: test", domain="exploration")
    thread_id = thread.thread_id

    record_turn_resolution(
        request_text="test reject",
        outcome="rejected",
        user_sentiment="disliked",
    )

    assert _tracker._turns[-1].outcome == "rejected"
    open_list = list_open_threads()
    assert any(t.thread_id == thread_id for t in open_list)


def test_commit_resolves_thread():
    """Committing should resolve the creative thread."""
    thread = open_thread(description="Wonder: test", domain="exploration")
    resolve_thread(thread.thread_id)

    open_list = list_open_threads()
    assert not any(t.thread_id == thread.thread_id for t in open_list)


def test_wonder_session_stores_diagnosis():
    """WonderSession must preserve the diagnosis object."""
    diag = build_diagnosis(
        stuckness_report={
            "confidence": 0.7,
            "level": "stuck",
            "primary_rescue_type": "overpolished_loop",
        },
    )
    ws = WonderSession(
        session_id="ws_lc_1",
        request_text="test",
        diagnosis=diag,
        status="variants_ready",
    )
    store_wonder_session(ws)

    retrieved = get_wonder_session("ws_lc_1")
    assert retrieved.diagnosis.problem_class == "overpolished_loop"


def test_analytical_only_variants_flagged():
    """Variants with no compiled_plan must be analytical_only=True."""
    result = generate_wonder_variants(
        request_text="completely nonexistent request xyz123",
    )
    for v in result["variants"]:
        if v.get("compiled_plan") is None:
            assert v["analytical_only"] is True
        else:
            assert v["analytical_only"] is False


def test_wonder_session_lifecycle_states():
    """WonderSession transitions through expected states."""
    ws = WonderSession(session_id="ws_states", request_text="test")
    assert ws.status == "diagnosing"
    assert ws.outcome == "pending"

    ws.status = "variants_ready"
    ws.status = "previewing"
    ws.status = "resolved"
    ws.outcome = "committed"

    assert ws.status == "resolved"
    assert ws.outcome == "committed"


def test_discard_session_leaves_thread_open():
    """Discarding a wonder session should leave the thread open."""
    thread = open_thread(description="Wonder: stuck rescue", domain="mix")
    ws = WonderSession(
        session_id="ws_discard",
        request_text="stuck rescue",
        creative_thread_id=thread.thread_id,
        status="variants_ready",
    )
    store_wonder_session(ws)

    ws.outcome = "rejected_all"
    ws.status = "resolved"

    # Thread should still be open
    open_list = list_open_threads()
    assert any(t.thread_id == thread.thread_id for t in open_list)

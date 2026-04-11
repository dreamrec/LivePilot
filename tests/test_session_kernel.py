"""Tests for SessionKernel — the unified turn snapshot."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.action_ledger import SessionLedger
from mcp_server.runtime.session_kernel import SessionKernel, build_session_kernel


def test_kernel_has_required_fields():
    kernel = build_session_kernel(
        session_info={"tempo": 120, "track_count": 4, "tracks": []},
        capability_state={"overall_mode": "judgment_only"},
        request_text="make this punchier",
        mode="improve",
    )
    assert kernel.kernel_id is not None
    assert len(kernel.kernel_id) == 12
    assert kernel.request_text == "make this punchier"
    assert kernel.mode == "improve"
    assert kernel.capability_state["overall_mode"] == "judgment_only"
    assert kernel.tempo == 120


def test_kernel_degrades_gracefully_without_optional_data():
    kernel = build_session_kernel(
        session_info={"tempo": 82, "track_count": 6, "tracks": []},
        capability_state={"overall_mode": "judgment_only"},
    )
    assert kernel.taste_graph == {}
    assert kernel.anti_preferences == []
    assert kernel.ledger_summary == {}
    assert kernel.session_memory == []
    assert kernel.protected_dimensions == {}


def test_kernel_id_is_deterministic():
    args = dict(
        session_info={"tempo": 120, "track_count": 2, "tracks": []},
        capability_state={"overall_mode": "normal"},
        request_text="test",
        mode="improve",
    )
    k1 = build_session_kernel(**args)
    k2 = build_session_kernel(**args)
    assert k1.kernel_id == k2.kernel_id


def test_kernel_id_changes_with_different_inputs():
    base = dict(
        session_info={"tempo": 120, "track_count": 2, "tracks": []},
        capability_state={"overall_mode": "normal"},
        request_text="test",
        mode="improve",
    )
    k1 = build_session_kernel(**base)
    k2 = build_session_kernel(**{**base, "request_text": "different"})
    assert k1.kernel_id != k2.kernel_id


def test_kernel_to_dict_roundtrip():
    kernel = build_session_kernel(
        session_info={"tempo": 90, "track_count": 3, "tracks": []},
        capability_state={"overall_mode": "normal"},
        request_text="",
        mode="observe",
    )
    d = kernel.to_dict()
    assert d["mode"] == "observe"
    assert d["tempo"] == 90
    assert "kernel_id" in d
    assert isinstance(d["session_info"], dict)


def test_kernel_with_full_context():
    kernel = build_session_kernel(
        session_info={"tempo": 82, "track_count": 6, "tracks": [{"name": "Drums"}]},
        capability_state={"overall_mode": "normal", "domains": {}},
        request_text="make the beat feel more like Prefuse 73",
        mode="explore",
        aggression=0.7,
        ledger_summary={"action_count": 5, "kept": 3, "undone": 2},
        session_memory=[{"note": "user prefers dusty lo-fi aesthetic"}],
        taste_graph={"warmth": 0.6, "punch": 0.4},
        anti_preferences=[{"dimension": "brightness", "direction": "increase"}],
        protected_dimensions={"clarity": 0.7, "cohesion": 0.6},
    )
    assert kernel.mode == "explore"
    assert kernel.aggression == 0.7
    assert kernel.taste_graph["warmth"] == 0.6
    assert len(kernel.anti_preferences) == 1
    assert kernel.protected_dimensions["clarity"] == 0.7
    assert kernel.ledger_summary["action_count"] == 5


def test_get_session_kernel_includes_action_ledger_summary():
    from mcp_server.runtime.tools import get_session_kernel

    class _Ableton:
        def send_command(self, cmd, params=None):
            assert cmd == "get_session_info"
            return {"tempo": 120, "track_count": 2, "tracks": []}

    ledger = SessionLedger()
    entry_id = ledger.start_move(engine="mix", move_class="balance", intent="tighten low end")
    ledger.append_action(entry_id, "set_track_volume", "Lower bass track by 1 dB")
    ledger.finalize_move(entry_id, kept=True, score=0.8, memory_candidate=True)

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "action_ledger": ledger})
    result = get_session_kernel(ctx, request_text="make it tighter")

    assert result["ledger_summary"]["total_moves"] == 1
    assert result["ledger_summary"]["memory_candidate_count"] == 1
    assert result["ledger_summary"]["last_move"]["intent"] == "tighten low end"


def test_get_session_kernel_marks_analyzer_available_when_fresh():
    from mcp_server.runtime.tools import get_session_kernel

    class _Ableton:
        def send_command(self, cmd, params=None):
            assert cmd == "get_session_info"
            return {"tempo": 120, "track_count": 2, "tracks": []}

    class _Spectral:
        is_connected = True

        def get(self, key):
            assert key == "spectrum"
            return {"value": {"sub": 0.1}}

    ctx = SimpleNamespace(
        lifespan_context={
            "ableton": _Ableton(),
            "spectral": _Spectral(),
            "action_ledger": SessionLedger(),
        }
    )

    result = get_session_kernel(ctx, request_text="make it drift")
    analyzer = result["capability_state"]["capability_state"]["domains"]["analyzer"]

    assert analyzer["available"] is True
    assert analyzer["mode"] == "measured"
    assert analyzer["reasons"] == []

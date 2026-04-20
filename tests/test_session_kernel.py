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


def test_get_session_kernel_reads_shared_anti_preferences():
    """get_session_kernel must reflect anti-preferences recorded via the public tool.

    Previously it instantiated a fresh AntiMemoryStore and called a non-existent
    list_all() method wrapped in try/except: pass — so users always saw empty.
    """
    from mcp_server.runtime.tools import get_session_kernel
    from mcp_server.memory.anti_memory import AntiMemoryStore

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"tempo": 120, "track_count": 2, "tracks": []}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "action_ledger": SessionLedger()})
    store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
    store.record_dislike("brightness", "increase")
    store.record_dislike("brightness", "increase")

    result = get_session_kernel(ctx)
    anti = result.get("anti_preferences", [])
    assert any(p.get("dimension") == "brightness" for p in anti), \
        f"Expected brightness anti-pref; got {anti}"


def test_get_session_kernel_reads_shared_session_memory():
    """Same bug for session_memory — mem_store.recent() did not exist."""
    from mcp_server.runtime.tools import get_session_kernel
    from mcp_server.memory.session_memory import SessionMemoryStore

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"tempo": 120, "track_count": 2, "tracks": []}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "action_ledger": SessionLedger()})
    store = ctx.lifespan_context.setdefault("session_memory", SessionMemoryStore())
    store.add(category="observation", content="kick feels muddy", engine="mix")

    result = get_session_kernel(ctx)
    mem = result.get("session_memory", [])
    assert len(mem) >= 1, f"Expected 1+ session memory entries; got {mem}"
    assert mem[0]["content"] == "kick feels muddy"


def test_get_session_kernel_taste_graph_uses_canonical_shape():
    """Taste graph must be built via build_taste_graph() so dimension_weights exists."""
    from mcp_server.runtime.tools import get_session_kernel

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"tempo": 120, "track_count": 2, "tracks": []}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "action_ledger": SessionLedger()})
    result = get_session_kernel(ctx)
    tg = result.get("taste_graph", {})
    # Canonical TasteGraph.to_dict() always has dimension_weights (possibly empty)
    assert "dimension_weights" in tg, \
        f"Taste graph must have canonical shape (dimension_weights key); got keys {list(tg.keys())}"


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


# ── PR2 — creative controls on SessionKernel ────────────────────────────


def test_kernel_creative_controls_default_empty():
    """Back-compat: legacy callers leave creative controls untouched and
    see empty defaults — matches the pre-PR2 surface exactly."""
    kernel = build_session_kernel(
        session_info={"tempo": 120, "track_count": 4, "tracks": []},
        capability_state={"overall_mode": "normal"},
    )
    assert kernel.freshness == 0.5
    assert kernel.creativity_profile == ""
    assert kernel.sacred_elements == []
    assert kernel.synth_hints == {}


def test_kernel_accepts_freshness_and_creativity_profile():
    kernel = build_session_kernel(
        session_info={"tempo": 120, "track_count": 4, "tracks": []},
        capability_state={"overall_mode": "normal"},
        freshness=0.9,
        creativity_profile="alchemist",
    )
    assert kernel.freshness == 0.9
    assert kernel.creativity_profile == "alchemist"


def test_kernel_accepts_sacred_elements_and_synth_hints():
    sacred = [{"element_type": "hook", "description": "the filtered stab", "salience": 0.9}]
    synth = {
        "track_indices": [3],
        "target_timbre": {"brightness": 0.3, "width": 0.2},
        "preferred_devices": ["Wavetable"],
    }
    kernel = build_session_kernel(
        session_info={"tempo": 120, "track_count": 4, "tracks": []},
        capability_state={"overall_mode": "normal"},
        sacred_elements=sacred,
        synth_hints=synth,
    )
    assert kernel.sacred_elements == sacred
    assert kernel.synth_hints == synth


def test_kernel_id_unaffected_by_creative_fields():
    """Regression guard: kernel_id hash is intentionally frozen in PR2 so
    existing consumers see the same id for the same (tempo, track_count,
    request_text, mode) — even if freshness/creativity_profile differ."""
    base = dict(
        session_info={"tempo": 120, "track_count": 2, "tracks": []},
        capability_state={"overall_mode": "normal"},
        request_text="test",
        mode="improve",
    )
    k_low = build_session_kernel(**base, freshness=0.1, creativity_profile="surgeon")
    k_high = build_session_kernel(**base, freshness=0.9, creativity_profile="alchemist")
    assert k_low.kernel_id == k_high.kernel_id


def test_kernel_to_dict_roundtrip_includes_creative_fields():
    kernel = build_session_kernel(
        session_info={"tempo": 120, "track_count": 2, "tracks": []},
        capability_state={"overall_mode": "normal"},
        freshness=0.7,
        creativity_profile="sculptor",
        sacred_elements=[{"element_type": "pad", "description": "the chord bed"}],
        synth_hints={"track_indices": [2]},
    )
    d = kernel.to_dict()
    assert d["freshness"] == 0.7
    assert d["creativity_profile"] == "sculptor"
    assert d["sacred_elements"][0]["description"] == "the chord bed"
    assert d["synth_hints"]["track_indices"] == [2]


def test_get_session_kernel_mcp_tool_accepts_creative_params():
    """The public MCP tool must accept the new optional kwargs and thread
    them into the returned kernel dict."""
    from mcp_server.runtime.tools import get_session_kernel

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"tempo": 120, "track_count": 2, "tracks": []}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "action_ledger": SessionLedger()})

    result = get_session_kernel(
        ctx,
        request_text="surprise me",
        freshness=0.85,
        creativity_profile="alchemist",
        sacred_elements=[{"element_type": "hook", "description": "stab", "salience": 0.9}],
        synth_hints={"track_indices": [3]},
    )
    assert result["freshness"] == 0.85
    assert result["creativity_profile"] == "alchemist"
    assert result["sacred_elements"][0]["element_type"] == "hook"
    assert result["synth_hints"]["track_indices"] == [3]


def test_get_session_kernel_legacy_callers_unaffected():
    """Pre-PR2 call pattern still works and leaves creative fields at defaults."""
    from mcp_server.runtime.tools import get_session_kernel

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"tempo": 120, "track_count": 2, "tracks": []}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "action_ledger": SessionLedger()})
    # Exact same call shape as the pre-PR2 tests above.
    result = get_session_kernel(ctx, request_text="make it tighter")
    assert result["freshness"] == 0.5
    assert result["creativity_profile"] == ""
    assert result["sacred_elements"] == []
    assert result["synth_hints"] == {}

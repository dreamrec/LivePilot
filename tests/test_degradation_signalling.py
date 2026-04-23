"""Tests for explicit degradation signalling (PR-B tasks B3/B4/B5).

Before PR-B, two code paths silently substituted fallback values and
returned them as if they were real:

* ``song_brain/tools.py:70`` injects ``tempo=120.0, track_count=0`` on
  session-fetch failure.
* ``preview_studio/engine.py:128`` falls back to an empty-but-valid
  kernel when the caller didn't supply one.

Both now attach a ``DegradationInfo`` payload to their response so
downstream consumers can tell synthesized data from real data.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Task B3: DegradationInfo dataclass ───────────────────────────────────


class TestDegradationInfoDataclass:
    def test_degradation_info_default_is_clean(self):
        from mcp_server.runtime.degradation import DegradationInfo

        info = DegradationInfo()
        assert info.is_degraded is False
        assert info.reasons == []
        assert info.substituted_fields == []

    def test_degradation_info_flags_when_constructed_degraded(self):
        from mcp_server.runtime.degradation import DegradationInfo

        info = DegradationInfo(
            is_degraded=True,
            reasons=["session_fetch_failed"],
            substituted_fields=["tempo", "track_count"],
        )
        assert info.is_degraded is True
        assert "session_fetch_failed" in info.reasons
        assert "tempo" in info.substituted_fields

    def test_degradation_info_to_dict_is_json_shaped(self):
        from mcp_server.runtime.degradation import DegradationInfo

        info = DegradationInfo(
            is_degraded=True,
            reasons=["session_fetch_failed"],
            substituted_fields=["tempo"],
        )
        payload = info.to_dict()
        assert payload["is_degraded"] is True
        assert payload["reasons"] == ["session_fetch_failed"]
        assert payload["substituted_fields"] == ["tempo"]

    def test_reasons_and_substituted_default_to_independent_lists(self):
        """Defaulting via field(default_factory=list) — not shared across instances."""
        from mcp_server.runtime.degradation import DegradationInfo

        a = DegradationInfo()
        b = DegradationInfo()
        a.reasons.append("x")
        a.substituted_fields.append("y")
        assert b.reasons == []
        assert b.substituted_fields == []


# ── Task B4: SongBrain flags degraded on session fetch failure ───────────


class _AbletonRaising:
    """Fake ableton that raises on every send_command — simulates outage."""

    def send_command(self, cmd, params=None):
        raise ConnectionError("simulated session outage")


class _AbletonHealthy:
    """Fake ableton that returns minimal but valid session data."""

    def send_command(self, cmd, params=None):
        if cmd == "get_session_info":
            return {
                "tempo": 96.0,
                "track_count": 2,
                "tracks": [
                    {"name": "Drums", "index": 0},
                    {"name": "Bass", "index": 1},
                ],
            }
        if cmd == "get_scene_matrix":
            return {"scenes": [], "matrix": []}
        return {}


def test_song_brain_flags_degraded_when_session_unreachable():
    from mcp_server.song_brain.tools import build_song_brain

    ctx = SimpleNamespace(lifespan_context={"ableton": _AbletonRaising()})
    result = build_song_brain(ctx)

    assert "degradation" in result, (
        f"Expected 'degradation' key in build_song_brain response; got {sorted(result)}"
    )
    deg = result["degradation"]
    assert deg["is_degraded"] is True
    assert "session_fetch_failed" in deg["reasons"]
    assert "tempo" in deg["substituted_fields"]
    assert "track_count" in deg["substituted_fields"]


def test_song_brain_does_not_flag_when_session_healthy():
    from mcp_server.song_brain.tools import build_song_brain

    ctx = SimpleNamespace(lifespan_context={"ableton": _AbletonHealthy()})
    result = build_song_brain(ctx)

    assert "degradation" in result
    deg = result["degradation"]
    assert deg["is_degraded"] is False
    assert deg["reasons"] == []
    assert deg["substituted_fields"] == []


# ── Task B5: Preview Studio flags degraded when kernel is empty ──────────


def test_preview_flags_degraded_on_empty_kernel_fallback():
    """create_preview_set must mark a preview_set degraded when no kernel is supplied.

    This is the code path at preview_studio/engine.py:128 — the compiler
    receives a synthesized empty-but-valid kernel, and the variant is
    scored against that synthetic topology. Callers have no way today to
    tell that from a real kernel-backed compile — so attach degradation.
    """
    from mcp_server.preview_studio.engine import create_preview_set

    ps = create_preview_set(
        request_text="make it tighter",
        kernel_id="kern_missing",
        available_moves=[
            {"move_id": "m1", "plan_template": []},
        ],
        kernel=None,  # explicit: no kernel -> engine falls back to empty kernel
    )

    assert hasattr(ps, "degradation"), (
        "PreviewSet must expose a .degradation attribute when the kernel was synthesized"
    )
    deg = ps.degradation
    # ``degradation`` is a DegradationInfo dataclass; accept either the
    # object or its .to_dict() — both must signal is_degraded=True.
    is_degraded = getattr(deg, "is_degraded", None)
    if is_degraded is None and isinstance(deg, dict):
        is_degraded = deg.get("is_degraded")
    assert is_degraded is True
    reasons = getattr(deg, "reasons", None) or deg.get("reasons", [])
    assert "empty_kernel_fallback" in reasons


def test_preview_does_not_flag_when_real_kernel_supplied():
    from mcp_server.preview_studio.engine import create_preview_set

    real_kernel = {
        "session_info": {
            "tempo": 120,
            "tracks": [{"name": "Drums", "index": 0}],
        },
        "mode": "improve",
    }
    ps = create_preview_set(
        request_text="make it tighter",
        kernel_id="kern_ok",
        available_moves=[{"move_id": "m1", "plan_template": []}],
        kernel=real_kernel,
    )
    deg = getattr(ps, "degradation", None)
    assert deg is not None
    is_degraded = getattr(deg, "is_degraded", None)
    if is_degraded is None and isinstance(deg, dict):
        is_degraded = deg.get("is_degraded")
    assert is_degraded is False

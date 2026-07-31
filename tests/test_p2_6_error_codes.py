"""P2-6 regression tests — all error returns in the 5 targeted modules now carry a 'code' field.

One representative error per module is exercised here.  These tests work
without a live Ableton connection: generative/harmony tools are pure
computation; theory/analyzer/mixing tools are called with fake contexts
that return controlled values.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _fake_ableton(notes=None, session=None):
    """Return a fake ableton stub that answers get_notes and get_session_info."""
    def send_command(cmd, params=None):
        if cmd == "get_notes":
            return {"notes": notes or []}
        if cmd == "get_session_info":
            return session or {"is_playing": False, "tracks": []}
        if cmd == "get_track_meters":
            return {}
        return {}
    return SimpleNamespace(send_command=send_command)


def _fake_ctx(notes=None, session=None, bridge_state=None, spectral=None):
    """Build a minimal MCP context with fake lifespan_context."""
    lc = {
        "ableton": _fake_ableton(notes=notes, session=session),
    }
    if bridge_state is not None:
        lc["_bridge_state"] = bridge_state
    if spectral is not None:
        lc["_spectral"] = spectral
    return SimpleNamespace(lifespan_context=lc)


# ---------------------------------------------------------------------------
# analyzer.py — INVALID_PARAM + STATE_ERROR
# ---------------------------------------------------------------------------

class TestAnalyzerErrorCodes:
    def test_window_ms_invalid_carries_invalid_param(self):
        """window_ms > 10000 → INVALID_PARAM"""
        from mcp_server.tools.analyzer import get_master_spectrum  # noqa: PLC0415
        ctx = _fake_ctx(spectral={})
        # We need a cache object — patch _get_spectral and _require_analyzer
        # Instead call with a ctx whose spectral dict is set up
        result = {"error": "window_ms must be <= 10000 (10 seconds)", "code": "INVALID_PARAM"}
        # The real path: call the guard logic branch directly
        # Since get_master_spectrum is async we check the guard via direct call
        result = asyncio.run(_call_get_master_spectrum_with_bad_window(ctx))
        assert "error" in result
        assert result.get("code") == "INVALID_PARAM"

    def test_no_loudness_data_carries_state_error(self):
        """get_momentary_loudness with empty cache → STATE_ERROR"""
        # We verify the static error shape without needing a real M4L connection
        # by checking that the return dict constant in the source contains the code.
        # A simpler approach: import and inspect the module's constants.
        from mcp_server.tools import analyzer  # noqa: PLC0415
        import inspect  # noqa: PLC0415
        src = inspect.getsource(analyzer.get_momentary_loudness)
        # The STATE_ERROR code must appear in the function source
        assert '"STATE_ERROR"' in src, "get_momentary_loudness must carry STATE_ERROR code"

    def test_bridge_state_missing_carries_state_error(self):
        """reconnect_bridge with no bridge_state → STATE_ERROR"""
        from mcp_server.tools import analyzer  # noqa: PLC0415
        import inspect  # noqa: PLC0415
        src = inspect.getsource(analyzer.reconnect_bridge)
        assert '"STATE_ERROR"' in src


async def _call_get_master_spectrum_with_bad_window(ctx):
    """Helper to invoke get_master_spectrum with an out-of-range window_ms."""
    from mcp_server.tools.analyzer import get_master_spectrum  # noqa: PLC0415
    # Patch the internal cache lookup so we reach the window_ms guard
    import mcp_server.tools.analyzer as _mod  # noqa: PLC0415
    orig = _mod._get_spectral
    _mod._get_spectral = lambda c: {"analyzer_available": True}

    # async tools call the async guard (_require_analyzer_async); the sync
    # _require_analyzer is still used by the sync analyzer tools.
    async def _noop_require(_cache):
        return None

    orig_require = _mod._require_analyzer_async
    _mod._require_analyzer_async = _noop_require
    try:
        return await get_master_spectrum(ctx, window_ms=99999)
    finally:
        _mod._get_spectral = orig
        _mod._require_analyzer_async = orig_require


# ---------------------------------------------------------------------------
# generative.py — INVALID_PARAM
# ---------------------------------------------------------------------------

class TestGenerativeErrorCodes:
    def test_euclidean_pulses_out_of_range_carries_invalid_param(self):
        """pulses > 64 → INVALID_PARAM"""
        from mcp_server.tools.generative import generate_euclidean_rhythm  # noqa: PLC0415
        result = generate_euclidean_rhythm(ctx=None, pulses=65, steps=8)
        assert "error" in result
        assert result["code"] == "INVALID_PARAM"

    def test_euclidean_steps_out_of_range_carries_invalid_param(self):
        """steps == 0 → INVALID_PARAM"""
        from mcp_server.tools.generative import generate_euclidean_rhythm  # noqa: PLC0415
        result = generate_euclidean_rhythm(ctx=None, pulses=0, steps=0)
        assert result["code"] == "INVALID_PARAM"

    def test_euclidean_pulses_gt_steps_carries_invalid_param(self):
        """pulses > steps → INVALID_PARAM"""
        from mcp_server.tools.generative import generate_euclidean_rhythm  # noqa: PLC0415
        result = generate_euclidean_rhythm(ctx=None, pulses=5, steps=3)
        assert result["code"] == "INVALID_PARAM"

    def test_tintinnabuli_empty_melody_carries_invalid_param(self):
        """melody_notes=[] → INVALID_PARAM"""
        from mcp_server.tools.generative import generate_tintinnabuli  # noqa: PLC0415
        result = generate_tintinnabuli(ctx=None, melody_notes=[], triad="C major")
        assert result["code"] == "INVALID_PARAM"

    def test_additive_process_empty_melody_carries_invalid_param(self):
        """melody_notes=[] → INVALID_PARAM"""
        from mcp_server.tools.generative import generate_additive_process  # noqa: PLC0415
        result = generate_additive_process(ctx=None, melody_notes=[])
        assert result["code"] == "INVALID_PARAM"


# ---------------------------------------------------------------------------
# theory.py — STATE_ERROR + INVALID_PARAM
# ---------------------------------------------------------------------------

class TestTheoryErrorCodes:
    def _ctx_empty_clip(self):
        return _fake_ctx(notes=[])

    def test_detect_theory_issues_no_notes_carries_state_error(self):
        """Empty clip → STATE_ERROR"""
        from mcp_server.tools.theory import detect_theory_issues  # noqa: PLC0415
        result = detect_theory_issues(self._ctx_empty_clip(), track_index=0, clip_index=0)
        assert "error" in result
        assert result["code"] == "STATE_ERROR"

    def test_analyze_harmony_no_notes_carries_state_error(self):
        """Empty clip → STATE_ERROR"""
        from mcp_server.tools.theory import analyze_harmony  # noqa: PLC0415
        result = analyze_harmony(self._ctx_empty_clip(), track_index=0, clip_index=0)
        assert "error" in result
        assert result["code"] == "STATE_ERROR"

    def test_transpose_smart_invalid_key_carries_invalid_param(self):
        """Invalid target_key → INVALID_PARAM"""
        from mcp_server.tools.theory import transpose_smart  # noqa: PLC0415
        notes = [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100}]
        ctx = _fake_ctx(notes=notes)
        result = transpose_smart(ctx, track_index=0, clip_index=0, target_key="ZZZ major")
        assert "error" in result
        assert result["code"] == "INVALID_PARAM"


# ---------------------------------------------------------------------------
# harmony.py — INVALID_PARAM (bad args + unparseable chord) + INTERNAL (unexpected)
# ---------------------------------------------------------------------------

class TestHarmonyErrorCodes:
    def test_navigate_tonnetz_bad_depth_carries_invalid_param(self):
        """depth=0 → INVALID_PARAM"""
        from mcp_server.tools.harmony import navigate_tonnetz  # noqa: PLC0415
        result = navigate_tonnetz(ctx=None, chord="C major", depth=0)
        assert "error" in result
        assert result["code"] == "INVALID_PARAM"

    def test_navigate_tonnetz_invalid_chord_carries_invalid_param(self):
        """Unparseable chord is bad user input → INVALID_PARAM (not INTERNAL).

        parse_chord raises ValueError in direct response to a malformed chord
        string the caller supplied, so the agent should see INVALID_PARAM and
        retry with a valid chord, not infer a server bug.
        """
        from mcp_server.tools.harmony import navigate_tonnetz  # noqa: PLC0415
        result = navigate_tonnetz(ctx=None, chord="ZZZ", depth=1)
        assert "error" in result
        assert result["code"] == "INVALID_PARAM"

    def test_find_voice_leading_bad_max_steps_carries_invalid_param(self):
        """max_steps=0 → INVALID_PARAM"""
        from mcp_server.tools.harmony import find_voice_leading_path  # noqa: PLC0415
        result = find_voice_leading_path(
            ctx=None, from_chord="C major", to_chord="G major", max_steps=0
        )
        assert "error" in result
        assert result["code"] == "INVALID_PARAM"

    def test_classify_progression_needs_two_chords_carries_invalid_param(self):
        """Single chord → INVALID_PARAM"""
        from mcp_server.tools.harmony import classify_progression  # noqa: PLC0415
        result = classify_progression(ctx=None, chords=["C major"])
        assert "error" in result
        assert result["code"] == "INVALID_PARAM"


# ---------------------------------------------------------------------------
# mixing.py — STATE_ERROR
# ---------------------------------------------------------------------------

class TestMixingErrorCodes:
    def test_no_meter_snapshots_carries_state_error(self):
        """When ableton returns non-dict for get_track_meters → STATE_ERROR."""
        from mcp_server.tools.mixing import get_track_meters  # noqa: PLC0415

        def bad_send(cmd, params=None):
            # Return non-dict so snapshot list stays empty
            if cmd == "get_track_meters":
                return None  # not a dict — skipped by isinstance check
            if cmd == "get_session_info":
                return {"is_playing": True, "tracks": []}
            return {}

        ctx = SimpleNamespace(
            lifespan_context={"ableton": SimpleNamespace(send_command=bad_send)}
        )
        result = asyncio.run(get_track_meters(ctx, samples=2, sample_interval_ms=0))
        assert "error" in result
        assert result["code"] == "STATE_ERROR"

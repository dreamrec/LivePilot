"""Regression tests — windowed cache readers must detect duplicate frames.

Defect (review 2026-07-30): get_master_spectrum's window_ms mean-pooling
loop reads SpectralCache.get("spectrum") repeatedly but only enforces the
single 5s staleness ceiling. If the OSC /spectrum stream stalls for less
than 5s, every windowed sample is the same cached frame and the aggregate
reports bands_std=0 (false stability) with samples_collected counting
duplicates as real samples. analyze_loudness_live has the same loop shape
over the "loudness" key.

Fix under test:
  * SpectralCache.update() maintains a per-key generation counter,
    exposed by get() — "same value, new frame" stays distinguishable
    from "same frame re-read".
  * Windowed readers report distinct_frames and attach a warning when
    duplicates dominate the window.
  * The default single-read path (window_ms=0) is unchanged.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from mcp_server.m4l_bridge import SpectralCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BANDS = {
    "sub_low": 0.1, "sub": 0.3, "low": 0.4, "low_mid": 0.35,
    "mid": 0.5, "high_mid": 0.4, "high": 0.3, "presence": 0.2, "air": 0.15,
}


def _fake_ableton(is_playing=True):
    def send_command(cmd, params=None):
        if cmd == "get_session_info":
            return {"is_playing": is_playing, "tracks": []}
        return {}
    return SimpleNamespace(send_command=send_command)


def _ctx(cache, is_playing=True):
    return SimpleNamespace(lifespan_context={
        "spectral": cache,
        "ableton": _fake_ableton(is_playing=is_playing),
    })


async def _noop_sleep(_seconds):
    return None


# ---------------------------------------------------------------------------
# SpectralCache generation counter
# ---------------------------------------------------------------------------

class TestSpectralCacheGeneration:
    def test_get_exposes_generation(self):
        cache = SpectralCache()
        cache.update("spectrum", {"sub": 0.1})
        first = cache.get("spectrum")
        assert first["generation"] == 1

        cache.update("spectrum", {"sub": 0.2})
        second = cache.get("spectrum")
        assert second["generation"] == 2

    def test_generation_increments_even_for_identical_values(self):
        """A constant signal (test tone) is a NEW frame each update —
        generation must distinguish it from a stalled re-read."""
        cache = SpectralCache()
        cache.update("spectrum", {"sub": 0.1})
        cache.update("spectrum", {"sub": 0.1})
        assert cache.get("spectrum")["generation"] == 2

    def test_generation_is_per_key(self):
        cache = SpectralCache()
        cache.update("spectrum", {"sub": 0.1})
        cache.update("spectrum", {"sub": 0.2})
        cache.update("loudness", {"momentary_lufs": -14.0})
        assert cache.get("spectrum")["generation"] == 2
        assert cache.get("loudness")["generation"] == 1

    def test_repeated_get_does_not_advance_generation(self):
        cache = SpectralCache()
        cache.update("spectrum", {"sub": 0.1})
        for _ in range(5):
            snap = cache.get("spectrum")
        assert snap["generation"] == 1


# ---------------------------------------------------------------------------
# get_master_spectrum windowed path
# ---------------------------------------------------------------------------

class TestWindowedSpectrumDistinctFrames:
    def test_stalled_stream_reports_distinct_frames_and_warns(self, monkeypatch):
        """Stream stalls < 5s: every sample is the same cached frame.
        The result must expose distinct_frames=1 and carry a warning —
        bands_std=0 alone must no longer read as real stability."""
        from mcp_server.tools.analyzer import get_master_spectrum

        cache = SpectralCache()
        cache.update("spectrum", dict(_BANDS))
        monkeypatch.setattr("asyncio.sleep", _noop_sleep)

        result = asyncio.run(
            get_master_spectrum(_ctx(cache), window_ms=500, samples=5)
        )

        assert result["samples_collected"] == 5
        assert result["distinct_frames"] == 1
        assert "warning" in result
        assert "distinct" in result["warning"] or "stall" in result["warning"].lower()

    def test_live_stream_counts_distinct_frames_no_warning(self, monkeypatch):
        """Stream updating between reads: all frames distinct, no warning."""
        from mcp_server.tools.analyzer import get_master_spectrum

        cache = SpectralCache()
        cache.update("spectrum", dict(_BANDS))
        counter = {"n": 0}

        async def _streaming_sleep(_seconds):
            # Simulate the OSC stream delivering a fresh frame during
            # each inter-sample sleep.
            counter["n"] += 1
            fresh = dict(_BANDS)
            fresh["mid"] = 0.5 + counter["n"] * 0.01
            cache.update("spectrum", fresh)

        monkeypatch.setattr("asyncio.sleep", _streaming_sleep)

        result = asyncio.run(
            get_master_spectrum(_ctx(cache), window_ms=500, samples=5)
        )

        assert result["samples_collected"] == 5
        assert result["distinct_frames"] == 5
        assert "warning" not in result
        # Variance across genuinely distinct frames is real signal.
        assert result["bands_std"]["mid"] > 0

    def test_partial_stall_flags_when_duplicates_dominate(self, monkeypatch):
        """Only 2 distinct frames across 6 samples → duplicates dominate."""
        from mcp_server.tools.analyzer import get_master_spectrum

        cache = SpectralCache()
        cache.update("spectrum", dict(_BANDS))
        counter = {"n": 0}

        async def _slow_stream_sleep(_seconds):
            counter["n"] += 1
            if counter["n"] == 3:  # one fresh frame mid-window
                fresh = dict(_BANDS)
                fresh["mid"] = 0.9
                cache.update("spectrum", fresh)

        monkeypatch.setattr("asyncio.sleep", _slow_stream_sleep)

        result = asyncio.run(
            get_master_spectrum(_ctx(cache), window_ms=600, samples=6)
        )

        assert result["samples_collected"] == 6
        assert result["distinct_frames"] == 2
        assert "warning" in result

    def test_single_read_path_unchanged(self):
        """window_ms=0 must keep its exact pre-fix shape — no
        distinct_frames, no warning, no generation leak."""
        from mcp_server.tools.analyzer import get_master_spectrum

        cache = SpectralCache()
        cache.update("spectrum", dict(_BANDS))

        result = asyncio.run(get_master_spectrum(_ctx(cache)))

        assert result["bands"] == _BANDS
        assert "age_ms" in result
        assert "distinct_frames" not in result
        assert "warning" not in result
        assert "generation" not in result

    def test_duck_typed_cache_without_generation_not_flagged(self, monkeypatch):
        """Fakes/subclasses whose get() omits 'generation' keep the
        pre-fix behavior: every frame counts as distinct, no warning."""
        from mcp_server.tools.analyzer import get_master_spectrum

        class _LegacyCache:
            is_connected = True

            def get(self, key):
                if key == "spectrum":
                    return {"value": dict(_BANDS), "age_ms": 10}
                return None

        monkeypatch.setattr("asyncio.sleep", _noop_sleep)
        result = asyncio.run(
            get_master_spectrum(_ctx(_LegacyCache()), window_ms=500, samples=5)
        )

        assert result["samples_collected"] == 5
        assert result["distinct_frames"] == 5
        assert "warning" not in result


# ---------------------------------------------------------------------------
# analyze_loudness_live — sibling windowed reader
# ---------------------------------------------------------------------------

class TestLoudnessLiveDistinctFrames:
    _LOUDNESS = {"momentary_lufs": -14.0, "true_peak_dbtp": -1.2}

    def test_stalled_stream_reports_distinct_frames_and_warns(self, monkeypatch):
        from mcp_server.tools.analyzer import analyze_loudness_live

        cache = SpectralCache()
        cache.update("loudness", dict(self._LOUDNESS))
        monkeypatch.setattr("asyncio.sleep", _noop_sleep)

        result = asyncio.run(
            analyze_loudness_live(_ctx(cache), window_sec=1.0, sample_interval_ms=200)
        )

        assert result["samples_collected"] == 5
        assert result["distinct_frames"] == 1
        assert "warning" in result

    def test_live_stream_counts_distinct_frames_no_warning(self, monkeypatch):
        from mcp_server.tools.analyzer import analyze_loudness_live

        cache = SpectralCache()
        cache.update("loudness", dict(self._LOUDNESS))
        counter = {"n": 0}

        async def _streaming_sleep(_seconds):
            counter["n"] += 1
            cache.update("loudness", {
                "momentary_lufs": -14.0 - counter["n"] * 0.5,
                "true_peak_dbtp": -1.2,
            })

        monkeypatch.setattr("asyncio.sleep", _streaming_sleep)

        result = asyncio.run(
            analyze_loudness_live(_ctx(cache), window_sec=1.0, sample_interval_ms=200)
        )

        assert result["samples_collected"] == 5
        assert result["distinct_frames"] == 5
        assert "warning" not in result

    def test_stall_warning_coexists_with_not_playing_warning(self, monkeypatch):
        """is_playing=False already warns; a stall must not clobber it —
        both diagnostics belong in the warning field."""
        from mcp_server.tools.analyzer import analyze_loudness_live

        cache = SpectralCache()
        cache.update("loudness", dict(self._LOUDNESS))
        monkeypatch.setattr("asyncio.sleep", _noop_sleep)

        result = asyncio.run(
            analyze_loudness_live(
                _ctx(cache, is_playing=False), window_sec=1.0, sample_interval_ms=200
            )
        )

        assert result["distinct_frames"] == 1
        assert "warning" in result
        assert "Playback was not running" in result["warning"]
        assert "distinct" in result["warning"]

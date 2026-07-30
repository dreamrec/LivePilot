"""Duplicate-frame detection for windowed SpectralCache sampling loops.

``SpectralCache.get()`` returns the latest OSC frame until a new one
arrives, bounded only by the 5s staleness ceiling. A loop that samples
faster than the stream updates — or during a stall shorter than 5s —
re-reads the same frame, and statistics aggregated over the duplicates
report false stability (bands_std == 0) while samples_collected counts
duplicates as real samples.

``_WindowedFrameTracker`` consumes the per-key ``generation`` counter
that ``SpectralCache.update()`` maintains, so windowed readers
(``get_master_spectrum`` with window_ms > 0, ``analyze_loudness_live``)
can report ``distinct_frames`` and warn when duplicates dominate.
"""

from __future__ import annotations

from typing import Optional


class _WindowedFrameTracker:
    """Count distinct cache frames across a windowed sampling loop.

    Frames are distinguished by the ``generation`` field of
    ``SpectralCache.get()`` snapshots — value comparison would
    misclassify a genuinely constant signal (e.g. a test tone) as a
    stall. Snapshots without a generation (duck-typed fakes, subclasses
    predating the counter) each count as distinct, preserving the
    pre-generation behavior of never warning.
    """

    def __init__(self) -> None:
        self._last_generation: Optional[int] = None
        self._distinct = 0
        self._observed = 0

    def observe(self, snapshot: dict) -> None:
        """Record one windowed read of a valid cache snapshot."""
        self._observed += 1
        generation = snapshot.get("generation")
        if generation is None or generation != self._last_generation:
            self._distinct += 1
            self._last_generation = generation

    @property
    def distinct_frames(self) -> int:
        return self._distinct

    def stall_warning(self, stream_name: str) -> Optional[str]:
        """Warning text when duplicates dominate the window, else None.

        Threshold: at least half of the collected samples were re-reads
        of an already-seen frame. Single-sample windows never warn —
        there is nothing to deduplicate.
        """
        if self._observed < 2 or self._distinct * 2 > self._observed:
            return None
        return (
            f"{stream_name} stream stalled during the window: only "
            f"{self._distinct} distinct frame(s) across {self._observed} "
            f"samples (duplicates re-read from cache). Variance/stability "
            f"statistics understate real variation — check that playback "
            f"is running and the LivePilot analyzer is streaming."
        )

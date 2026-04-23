"""Experiment baseline transport state — capture once, restore between branches.

v1.19 Item A: running N branches sequentially produces inconsistent
``before_snapshot`` values because playback position, mute/solo/arm, and
playing-clip state drift across branches. ``undo()`` reverts command
history but doesn't guarantee transport state is identical at the start
of each branch's capture window.

Flow in ``run_experiment``:

1. Before the first branch: ``capture_baseline(ableton)`` and stash on
   the :class:`ExperimentSet`.
2. Between branches (before capturing the next before_snapshot): call
   ``restore_baseline(ableton, baseline)`` to stop transport, reset
   mute/solo/arm, and pause briefly for meters to settle.

The module is deliberately thin — no LOM subscription, no state
monitoring. Just a snapshot dataclass + two functions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BaselineTransportState:
    """Transport + per-track state captured before the first experiment branch.

    Kept deliberately shallow: we don't try to freeze automation or scene
    state. Those are out of scope (plan §2 "What NOT to do" — automation
    drift is an accepted limitation).
    """

    is_playing: bool = False
    song_time: float = 0.0
    track_states: list[dict] = field(default_factory=list)
    captured_at_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "is_playing": self.is_playing,
            "song_time": self.song_time,
            "track_states": list(self.track_states),
            "captured_at_ms": self.captured_at_ms,
        }


def capture_baseline(ableton) -> BaselineTransportState:
    """Capture current transport + per-track state.

    Uses ``get_session_info`` (single round-trip for all fields we need).
    Returns a frozen-in-time snapshot; subsequent state drift doesn't
    affect it.
    """
    info = ableton.send_command("get_session_info")
    if not isinstance(info, dict):
        info = {}

    tracks = info.get("tracks") or []
    track_states: list[dict] = []
    for i, t in enumerate(tracks):
        if not isinstance(t, dict):
            continue
        track_states.append({
            "index": int(t.get("index", i)),
            "mute": bool(t.get("mute", False)),
            "solo": bool(t.get("solo", False)),
            "arm": bool(t.get("arm", False)),
        })

    return BaselineTransportState(
        is_playing=bool(info.get("is_playing", False)),
        song_time=float(info.get("current_song_time", 0.0) or 0.0),
        track_states=track_states,
        captured_at_ms=int(time.time() * 1000),
    )


def restore_baseline(
    ableton,
    baseline: BaselineTransportState,
    stabilize_ms: int = 300,
) -> None:
    """Restore transport + per-track state to the captured baseline.

    Sequence:
      1. ``stop_playback`` (halt transport — also stops any live clips)
      2. For each track: ``set_track_mute`` / ``set_track_solo`` /
         ``set_track_arm`` (best-effort; per-track failure is logged,
         not fatal — a single flaky track should never abort restore
         for the rest).
      3. Sleep ``stabilize_ms`` milliseconds so meters settle before the
         next ``before_snapshot`` reads them. Pass ``0`` in tests.

    We deliberately do NOT seek the transport to ``baseline.song_time``.
    Returning from stopped transport is enough — re-seeking a stopped
    transport is equivalent to not moving, and on a playing transport it
    introduces its own stutter artefact. If a future branch needs timeline
    position consistency, add a ``jump_to_time`` call here.

    Return-track arms are skipped — ``set_track_arm`` on a negative index
    raises (return tracks aren't armable in Live).
    """
    try:
        ableton.send_command("stop_playback")
    except Exception as exc:
        logger.debug("restore_baseline stop_playback failed: %s", exc)

    for ts in baseline.track_states:
        idx = ts.get("index", -1)
        try:
            ableton.send_command("set_track_mute", {
                "track_index": idx, "mute": bool(ts.get("mute", False)),
            })
        except Exception as exc:
            logger.debug("restore_baseline set_track_mute(%s) failed: %s", idx, exc)
        try:
            ableton.send_command("set_track_solo", {
                "track_index": idx, "solo": bool(ts.get("solo", False)),
            })
        except Exception as exc:
            logger.debug("restore_baseline set_track_solo(%s) failed: %s", idx, exc)
        if idx >= 0:
            try:
                ableton.send_command("set_track_arm", {
                    "track_index": idx, "arm": bool(ts.get("arm", False)),
                })
            except Exception as exc:
                logger.debug("restore_baseline set_track_arm(%s) failed: %s", idx, exc)

    if stabilize_ms > 0:
        time.sleep(stabilize_ms / 1000.0)

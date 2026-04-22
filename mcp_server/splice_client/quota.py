"""Daily download quota tracker for the Splice x Ableton Live plan.

The plan grants 100 samples/day unmetered via drag-drop inside Ableton.
Samples downloaded through our `splice_download_sample` MCP tool count
against the SAME daily quota server-side — Splice doesn't distinguish
between in-Ableton drags and in-plugin drag/downloads, they all hit the
same `DownloadSample` RPC.

This tracker lets us:
  1. Warn the user before they approach the ceiling (default 90/100).
  2. Refuse downloads when the ceiling would be exceeded, turning a
     confusing server error into a clear "quota hit, resets at UTC
     midnight" message.
  3. Give the agent a running count so it can choose "audition via
     PreviewURL" instead of "download" when budget is tight.

State lives at ~/.livepilot/splice_quota.json. It's a small JSON file
because simplicity beats a DB for a single-digit-KB ledger.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Splice quota boundaries
DEFAULT_DAILY_LIMIT = 100
DEFAULT_WARN_THRESHOLD = 90

# Quota file location — one ledger per user, stored under ~/.livepilot.
_DEFAULT_QUOTA_PATH = os.path.expanduser("~/.livepilot/splice_quota.json")


def _today_utc() -> str:
    """ISO date string in UTC — matches Splice's server-side reset boundary.

    Splice documentation doesn't publish the reset timezone, but the
    desktop app's telemetry timestamps are UTC. Using UTC matches the
    server to avoid "quota reset at 11pm local" surprises. If we later
    discover Splice resets at local midnight we can swap the function.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class QuotaState:
    """On-disk record of sample downloads per UTC day.

    `counts` maps YYYY-MM-DD → number of samples downloaded that day.
    `downloads` is a bounded log of recent file_hashes (last 200) for
    debugging — never the source of truth, just a trail.
    """

    version: int = 1
    counts: dict[str, int] = field(default_factory=dict)
    downloads: list[dict] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> "QuotaState":
        try:
            raw = json.loads(data)
        except json.JSONDecodeError:
            return cls()
        if not isinstance(raw, dict):
            return cls()
        return cls(
            version=int(raw.get("version", 1)),
            counts={str(k): int(v) for k, v in (raw.get("counts") or {}).items()},
            downloads=list(raw.get("downloads") or [])[-200:],
        )


class DailyQuotaTracker:
    """Thread-safe persistent counter for Splice daily downloads.

    Thread-safety: the gRPC client is async but the quota file lives on
    a single process. A `threading.Lock` is enough — async callers can
    grab it synchronously because the critical section is I/O-free
    (read/modify/write a small JSON blob).
    """

    def __init__(
        self,
        path: Optional[str] = None,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        warn_threshold: int = DEFAULT_WARN_THRESHOLD,
    ):
        self.path = path or _DEFAULT_QUOTA_PATH
        self.daily_limit = daily_limit
        self.warn_threshold = warn_threshold
        self._lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create quota dir %s: %s", self.path, exc)

    def _load(self) -> QuotaState:
        if not os.path.isfile(self.path):
            return QuotaState()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return QuotaState.from_json(f.read())
        except OSError as exc:
            logger.warning("Could not read quota file %s: %s", self.path, exc)
            return QuotaState()

    def _save(self, state: QuotaState):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(state.to_json())
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.warning("Could not write quota file %s: %s", self.path, exc)

    # ── Queries ──────────────────────────────────────────────────────

    def current(self) -> tuple[int, int]:
        """Return (used_today, remaining_today)."""
        with self._lock:
            state = self._load()
            used = state.counts.get(_today_utc(), 0)
        remaining = max(0, self.daily_limit - used)
        return used, remaining

    def would_exceed(self, additional: int = 1) -> bool:
        """True iff `additional` more downloads would breach the daily limit."""
        used, _ = self.current()
        return (used + additional) > self.daily_limit

    def near_limit(self) -> bool:
        """True iff we're at or above the warn threshold."""
        used, _ = self.current()
        return used >= self.warn_threshold

    # ── Mutations ─────────────────────────────────────────────────────

    def record_download(self, file_hash: str, filename: str = "") -> dict:
        """Increment today's counter and append to the log.

        Returns a summary dict: {used_today, remaining_today, warning}.
        Safe to call concurrently — `threading.Lock` serializes I/O.
        """
        today = _today_utc()
        warning = None
        with self._lock:
            state = self._load()
            state.counts[today] = state.counts.get(today, 0) + 1
            state.downloads.append({
                "file_hash": file_hash,
                "filename": filename,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "day": today,
            })
            # Trim log to last 200 entries
            if len(state.downloads) > 200:
                state.downloads = state.downloads[-200:]
            # Prune old days (keep last 30) so the counts dict doesn't grow
            # unbounded. Splice's daily limit resets at UTC midnight so
            # anything older than a week is no longer useful.
            if len(state.counts) > 30:
                sorted_days = sorted(state.counts.keys())
                for day in sorted_days[:-30]:
                    state.counts.pop(day, None)
            self._save(state)
            used = state.counts[today]
        remaining = max(0, self.daily_limit - used)
        if used >= self.daily_limit:
            warning = (
                f"Daily quota of {self.daily_limit} samples reached. "
                "Resets at UTC midnight. Further downloads will be "
                "refused server-side."
            )
        elif used >= self.warn_threshold:
            warning = (
                f"Approaching daily quota ({used}/{self.daily_limit}). "
                "Consider previewing samples (splice_preview_sample) "
                "before committing to more downloads today."
            )
        return {
            "used_today": used,
            "remaining_today": remaining,
            "daily_limit": self.daily_limit,
            "warning": warning,
        }

    def summary(self) -> dict:
        """Read-only snapshot — used by get_splice_credits for reporting."""
        used, remaining = self.current()
        return {
            "used_today": used,
            "remaining_today": remaining,
            "daily_limit": self.daily_limit,
            "warn_threshold": self.warn_threshold,
            "near_limit": used >= self.warn_threshold,
            "at_limit": used >= self.daily_limit,
        }


# Process-wide singleton. The MCP server has exactly one event loop and
# one Splice gRPC client; sharing a tracker means all download sites
# observe the same counter.
_singleton: Optional[DailyQuotaTracker] = None


def get_tracker() -> DailyQuotaTracker:
    global _singleton
    if _singleton is None:
        _singleton = DailyQuotaTracker()
    return _singleton


def reset_singleton_for_tests():
    """Reset the module singleton — test-only helper."""
    global _singleton
    _singleton = None

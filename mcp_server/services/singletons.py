"""Thread-safe singleton helpers.

The server has several subsystems (atlas, corpus, sample-engine indexes)
that are loaded lazily into module-level globals via a check-then-set
pattern. Under FastMCP's async concurrency that pattern races: two
handlers can both observe ``None`` and both construct the (expensive)
object. Most of the time the GIL hides the race, but when it doesn't you
get redundant I/O and, worse, one thread's half-parsed state overwriting
the other's completed state.

This module provides a small helper that wraps a factory in a lock and
optionally tracks an on-disk mtime for cache invalidation. Use it in
place of hand-rolled ``_instance = None`` patterns.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Callable, TypeVar

T = TypeVar("T")


class Singleton:
    """Lazy, thread-safe singleton with optional mtime-based reload.

    Example:
        atlas_holder = Singleton(_load_atlas)

        def get_atlas():
            return atlas_holder.get(reload_if_newer=atlas_path)

        def on_atlas_rebuild():
            atlas_holder.invalidate()
    """

    def __init__(self, factory: Callable[[], T]):
        self._factory = factory
        self._instance: T | None = None
        self._mtime: float | None = None
        self._lock = Lock()

    def get(self, *, reload_if_newer: Path | None = None) -> T:
        with self._lock:
            if self._instance is None:
                self._instance = self._factory()
                if reload_if_newer is not None:
                    try:
                        self._mtime = reload_if_newer.stat().st_mtime
                    except OSError:
                        self._mtime = None
                return self._instance

            if reload_if_newer is not None:
                try:
                    current = reload_if_newer.stat().st_mtime
                except OSError:
                    return self._instance
                if self._mtime is None or current > self._mtime:
                    self._instance = self._factory()
                    self._mtime = current
            return self._instance

    def invalidate(self) -> None:
        """Discard the cached instance. Next .get() will re-run the factory."""
        with self._lock:
            self._instance = None
            self._mtime = None

"""Persistent JSON store with atomic writes and corruption recovery.

Follows the TechniqueStore pattern: lazy init, atomic tmp+rename,
fsync to disk, corruption recovery via .corrupt rename.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path


class PersistentJsonStore:
    """Thread-safe, crash-safe JSON file store."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> dict:
        """Read the store. Returns {} if missing or corrupt."""
        with self._lock:
            if not self._path.exists():
                return {}
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                corrupt = self._path.with_suffix(self._path.suffix + ".corrupt")
                try:
                    self._path.rename(corrupt)
                except OSError:
                    pass
                return {}

    def write(self, data: dict) -> None:
        """Atomically write data to disk."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(str(tmp), str(self._path))
            except OSError:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

    def update(self, updater) -> dict:
        """Read-modify-write atomically. updater(data) -> modified data."""
        with self._lock:
            data = self._read_unlocked()
            data = updater(data)
            self._write_unlocked(data)
            return data

    def _read_unlocked(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_unlocked(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(self._path))

"""Persistent JSON store for LivePilot techniques (beat patterns, device chains, etc.)."""

import copy
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


VALID_TYPES = frozenset(
    ["beat_pattern", "device_chain", "mix_template", "browser_pin", "preference",
     "outcome", "composition_outcome", "technique_card"]
)

VALID_SORT_FIELDS = frozenset(
    ["updated_at", "created_at", "rating", "replay_count", "name"]
)


class TechniqueStore:
    """Thread-safe JSON-backed store for techniques."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.expanduser("~"), ".livepilot", "memory")
        self._base_dir = Path(base_dir)
        self._file = self._base_dir / "techniques.json"
        self._lock = threading.Lock()
        self._initialized = False
        self._data: dict = {"version": 1, "techniques": []}

    def _ensure_initialized(self) -> None:
        """Lazily create directory and load data on first access.

        Deferred so that a read-only HOME doesn't crash the entire MCP
        server at import time — memory tools just return errors instead.
        """
        if self._initialized:
            return
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Cannot create memory directory {self._base_dir}: {exc}. "
                "Memory tools are unavailable."
            ) from exc
        if self._file.exists():
            try:
                with open(self._file, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                corrupt = self._file.with_suffix(".json.corrupt")
                self._file.rename(corrupt)
                self._data = {"version": 1, "techniques": []}
        else:
            self._data = {"version": 1, "techniques": []}
            self._flush()
        self._initialized = True

    # ── persistence ──────────────────────────────────────────────

    def _flush(self) -> None:
        """Atomic write: tmp file then rename."""
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(self._file))

    # ── public API ───────────────────────────────────────────────

    def save(
        self,
        name: str,
        type: str,
        qualities: dict,
        payload: dict,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """Create a new technique. Returns {id, name, type, summary}."""
        self._ensure_initialized()
        if type not in VALID_TYPES:
            raise ValueError(
                f"INVALID_PARAM: type must be one of {sorted(VALID_TYPES)}, got '{type}'"
            )
        if not qualities.get("summary"):
            raise ValueError("INVALID_PARAM: qualities must contain non-empty 'summary'")

        now = datetime.now(timezone.utc).isoformat()
        technique = {
            "id": str(uuid.uuid4()),
            "name": name,
            "type": type,
            "qualities": qualities,
            "payload": payload,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
            "favorite": False,
            "rating": 0,
            "replay_count": 0,
        }

        with self._lock:
            self._data["techniques"].append(technique)
            self._flush()

        return {
            "id": technique["id"],
            "name": technique["name"],
            "type": technique["type"],
            "summary": qualities["summary"],
        }

    def get(self, technique_id: str) -> dict:
        """Return full technique by id."""
        self._ensure_initialized()
        with self._lock:
            for t in self._data["techniques"]:
                if t["id"] == technique_id:
                    return copy.deepcopy(t)
        raise ValueError(f"NOT_FOUND: technique '{technique_id}' does not exist")

    def search(
        self,
        query: Optional[str] = None,
        type_filter: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search techniques. Returns summaries (no payload)."""
        self._ensure_initialized()
        if limit < 0:
            raise ValueError("INVALID_PARAM: limit must be >= 0")
        with self._lock:
            results = copy.deepcopy(self._data["techniques"])

        # filter by type
        if type_filter:
            results = [t for t in results if t["type"] == type_filter]

        # filter by tags (match any)
        if tags:
            tag_set = set(tags)
            results = [t for t in results if tag_set & set(t.get("tags", []))]

        # text search — all query words must appear somewhere in the technique
        if query:
            words = query.lower().split()
            filtered = []
            for t in results:
                searchable = self._searchable_text(t)
                if all(w in searchable for w in words):
                    filtered.append(t)
            results = filtered

        results = self._multi_sort(results)

        results = results[:limit]

        # strip payload
        return [self._summary(t) for t in results]

    def list_techniques(
        self,
        type_filter: Optional[str] = None,
        tags: Optional[list[str]] = None,
        sort_by: str = "updated_at",
        limit: int = 20,
    ) -> list[dict]:
        """List techniques as compact summaries."""
        self._ensure_initialized()
        if limit < 0:
            raise ValueError("INVALID_PARAM: limit must be >= 0")
        if sort_by not in VALID_SORT_FIELDS:
            raise ValueError(
                f"INVALID_PARAM: sort_by must be one of {sorted(VALID_SORT_FIELDS)}, got '{sort_by}'"
            )

        with self._lock:
            results = copy.deepcopy(self._data["techniques"])

        if type_filter:
            results = [t for t in results if t["type"] == type_filter]

        if tags:
            tag_set = set(tags)
            results = [t for t in results if tag_set & set(t.get("tags", []))]

        reverse = sort_by != "name"
        results.sort(key=lambda t: t.get(sort_by, ""), reverse=reverse)

        results = results[:limit]

        return [self._compact_summary(t) for t in results]

    def favorite(
        self,
        technique_id: str,
        favorite: Optional[bool] = None,
        rating: Optional[int] = None,
    ) -> dict:
        """Set favorite flag and/or rating."""
        self._ensure_initialized()
        if rating is not None and (rating < 0 or rating > 5):
            raise ValueError("INVALID_PARAM: rating must be between 0 and 5")

        with self._lock:
            t = self._find(technique_id)
            if favorite is not None:
                t["favorite"] = favorite
            if rating is not None:
                t["rating"] = rating
            t["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._flush()
            return self._compact_summary(t)

    def update(
        self,
        technique_id: str,
        name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        qualities: Optional[dict] = None,
    ) -> dict:
        """Update technique fields. Qualities are merged (lists replaced)."""
        self._ensure_initialized()
        with self._lock:
            t = self._find(technique_id)
            if name is not None:
                t["name"] = name
            if tags is not None:
                t["tags"] = tags
            if qualities is not None:
                existing = t.get("qualities", {})
                existing.update(qualities)
                t["qualities"] = existing
            t["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._flush()
            return self._compact_summary(t)

    def delete(self, technique_id: str) -> dict:
        """Delete technique after creating a timestamped backup."""
        self._ensure_initialized()
        with self._lock:
            t = self._find(technique_id)
            # backup
            backup_dir = self._base_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            backup_file = backup_dir / f"{technique_id}_{ts}.json"
            with open(backup_file, "w") as f:
                json.dump(t, f, indent=2)
            # remove
            self._data["techniques"] = [
                x for x in self._data["techniques"] if x["id"] != technique_id
            ]
            self._flush()
            return {"id": technique_id, "deleted": True}

    def increment_replay(self, technique_id: str) -> None:
        """Increment replay_count and set last_replayed_at."""
        with self._lock:
            t = self._find(technique_id)
            t["replay_count"] = t.get("replay_count", 0) + 1
            t["last_replayed_at"] = datetime.now(timezone.utc).isoformat()
            self._flush()

    # ── private helpers ──────────────────────────────────────────

    def _find(self, technique_id: str) -> dict:
        """Find technique by id (must hold lock). Returns mutable ref."""
        for t in self._data["techniques"]:
            if t["id"] == technique_id:
                return t
        raise ValueError(f"NOT_FOUND: technique '{technique_id}' does not exist")

    @staticmethod
    def _searchable_text(t: dict) -> str:
        """Build a single lowercase string from all searchable fields."""
        parts = [t.get("name", "")]
        parts.extend(t.get("tags", []))
        for v in t.get("qualities", {}).values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(item) for item in v)
        return " ".join(parts).lower()

    @staticmethod
    def _multi_sort(results: list[dict]) -> list[dict]:
        """Sort: favorites first, rating desc, replay_count desc, updated_at desc."""
        return sorted(
            results,
            key=lambda t: (
                t.get("favorite", False),
                t.get("rating", 0),
                t.get("replay_count", 0),
                t.get("updated_at", ""),
            ),
            reverse=True,
        )

    @staticmethod
    def _summary(t: dict) -> dict:
        """Everything except payload."""
        return {k: v for k, v in t.items() if k != "payload"}

    @staticmethod
    def _compact_summary(t: dict) -> dict:
        """Compact: id, name, type, tags, summary, favorite, rating, replay_count, timestamps."""
        return {
            "id": t["id"],
            "name": t["name"],
            "type": t["type"],
            "tags": t.get("tags", []),
            "summary": t.get("qualities", {}).get("summary", ""),
            "favorite": t.get("favorite", False),
            "rating": t.get("rating", 0),
            "replay_count": t.get("replay_count", 0),
            "created_at": t.get("created_at", ""),
            "updated_at": t.get("updated_at", ""),
        }

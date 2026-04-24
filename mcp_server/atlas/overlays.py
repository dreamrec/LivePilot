# mcp_server/atlas/overlays.py
"""User-local atlas overlay loader (v1.23.0).

Generalizes the v1.22.0 BUNDLED_ATLAS_PATH / USER_ATLAS_PATH pattern to
support arbitrary user-local namespaces of YAML overlay entries
(machines, signature chains, aesthetic lineages, techniques) under
~/.livepilot/atlas-overlays/<namespace>/.

Per spec: docs/superpowers/specs/2026-04-25-user-local-extensions-design.md
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class OverlayEntry:
    """A single overlay entity loaded from a YAML file under a namespace.

    Field names mirror the spec §5.1. `entity_id` (not `id`) avoids
    shadowing the Python `id()` builtin and matches the
    `OverlayIndex.get(namespace, entity_id)` accessor signature.

    For entity_type='signature_chain', `tags` and `artists` are required
    (the search ranker hits them). The loader enforces this — see
    `_validate_entry` (added in a later task).
    """
    namespace: str
    entity_type: str
    entity_id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    artists: list[str] = field(default_factory=list)
    requires_box: Optional[str] = None
    body: dict = field(default_factory=dict)


class OverlayIndex:
    """In-memory index of overlay entries, partitioned by (namespace, entity_type, entity_id).

    Mutated in place by load_overlays() (added in a later task). Tools call
    get_overlay_index() at request time to read the current state — never
    capture a reference at import time.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], OverlayEntry] = {}

    def add(self, entry: OverlayEntry) -> Optional[OverlayEntry]:
        """Insert or replace. Returns the previous entry on collision (or None
        on a fresh insert) so callers can log a duplicate-id warning per spec §7."""
        key = (entry.namespace, entry.entity_type, entry.entity_id)
        previous = self._entries.get(key)
        self._entries[key] = entry
        return previous

    def get(self, namespace: str, entity_id: str) -> Optional[OverlayEntry]:
        """Lookup by (namespace, entity_id), ignoring entity_type.

        If two entries share the same (namespace, entity_id) across different
        entity_types, returns whichever the dict iterator yields first
        (insertion order in CPython 3.7+). The loader (Tasks 7+8) is responsible
        for preventing such collisions via dup-id warnings.
        """
        for (ns, _et, eid), entry in self._entries.items():
            if ns == namespace and eid == entity_id:
                return entry
        return None

    def list_namespaces(self) -> list[str]:
        return sorted({ns for (ns, _, _) in self._entries.keys()})

    def list_entity_types(self, namespace: str) -> list[str]:
        return sorted({et for (ns, et, _) in self._entries.keys() if ns == namespace})

    def clear(self) -> None:
        """Reset for idempotency (used by load_overlays in a later task)."""
        self._entries.clear()

    def all_entries(self) -> list[OverlayEntry]:
        return list(self._entries.values())

    def search(self, query: str, namespace: Optional[str] = None,
               entity_type: Optional[str] = None,
               limit: int = 10) -> list[OverlayEntry]:
        """Weighted substring search.

        Scores per entry:
          +1000 if query == entity_id (case-insensitive exact)
          +100  per substring hit in name
          +50   per substring hit in tag or artist
          +10   per substring hit in description

        Sorts by descending score, then by entity_id for stable ties.
        Filters by namespace and/or entity_type if provided.
        Empty query returns empty list.
        """
        q = (query or "").strip().lower()
        if not q:
            return []

        scored: list[tuple[int, str, OverlayEntry]] = []
        for entry in self._entries.values():
            if namespace is not None and entry.namespace != namespace:
                continue
            if entity_type is not None and entry.entity_type != entity_type:
                continue
            score = 0
            if entry.entity_id.lower() == q:
                score += 1000
            if q in entry.name.lower():
                score += 100
            for tag in entry.tags:
                if q in str(tag).lower():
                    score += 50
            for artist in entry.artists:
                if q in str(artist).lower():
                    score += 50
            if q in entry.description.lower():
                score += 10
            if score > 0:
                scored.append((score, entry.entity_id, entry))

        scored.sort(key=lambda triple: (-triple[0], triple[1]))
        return [entry for (_, _, entry) in scored[:max(0, limit)]]

    def stats(self) -> dict:
        """Counts per namespace per entity_type (used by extension_atlas_list in Task 12)."""
        counts: dict[str, dict[str, int]] = {}
        for (ns, et, _eid) in self._entries.keys():
            counts.setdefault(ns, {}).setdefault(et, 0)
            counts[ns][et] += 1
        return counts

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
        """Insert or replace. Returns previous entry on collision so callers can log
        the duplicate-id warning."""
        key = (entry.namespace, entry.entity_type, entry.entity_id)
        previous = self._entries.get(key)
        self._entries[key] = entry
        return previous

    def get(self, namespace: str, entity_id: str) -> Optional[OverlayEntry]:
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

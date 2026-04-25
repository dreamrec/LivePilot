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
        """Weighted substring search with whitespace-tokenized AND semantics.

        The query is split on whitespace into tokens. Each token is scored
        against each entry independently:
          +1000 if token == entity_id (case-insensitive exact match)
          +100  per substring hit in name
          +50   per substring hit in tag or artist
          +10   per substring hit in description

        An entry matches only if EVERY token scores > 0 somewhere (AND
        semantics — prevents 'sophie ponyboy' from matching unrelated
        entries that contain only one of the two words). The entry's
        final score is the sum across all tokens.

        Sorts by descending score, then by entity_id for stable ties.
        Filters by namespace and/or entity_type if provided.
        Empty query returns empty list.
        """
        q = (query or "").strip().lower()
        if not q:
            return []
        tokens = q.split()
        if not tokens:
            return []

        scored: list[tuple[int, str, OverlayEntry]] = []
        for entry in self._entries.values():
            if namespace is not None and entry.namespace != namespace:
                continue
            if entity_type is not None and entry.entity_type != entity_type:
                continue

            name_lower = entry.name.lower()
            entity_id_lower = entry.entity_id.lower()
            description_lower = entry.description.lower()
            tags_lower = [str(t).lower() for t in entry.tags]
            artists_lower = [str(a).lower() for a in entry.artists]

            token_scores = []
            for tok in tokens:
                s = 0
                if entity_id_lower == tok:
                    s += 1000
                if tok in name_lower:
                    s += 100
                for tag in tags_lower:
                    if tok in tag:
                        s += 50
                for artist in artists_lower:
                    if tok in artist:
                        s += 50
                if tok in description_lower:
                    s += 10
                token_scores.append(s)

            # AND semantics — every token must match somewhere
            if all(s > 0 for s in token_scores):
                scored.append((sum(token_scores), entry.entity_id, entry))

        scored.sort(key=lambda triple: (-triple[0], triple[1]))
        return [entry for (_, _, entry) in scored[:max(0, limit)]]

    def stats(self) -> dict:
        """Counts per namespace per entity_type (used by extension_atlas_list in Task 12)."""
        counts: dict[str, dict[str, int]] = {}
        for (ns, et, _eid) in self._entries.keys():
            counts.setdefault(ns, {}).setdefault(et, 0)
            counts[ns][et] += 1
        return counts


def _resolve_overlay_root() -> Path:
    """Lazy resolver mirroring v1.22.0 _resolve_atlas_path() pattern.
    Tests monkeypatch Path.home() and expect this to re-evaluate."""
    return Path.home() / ".livepilot" / "atlas-overlays"


def _validate_entry(entry: dict, source_path: Path,
                    log: logging.Logger) -> bool:
    """True if entry has required fields. Log + return False otherwise.

    Per spec §5.1:
      - All entries: entity_id + entity_type required
      - entity_type=signature_chain: also tags + artists required
    """
    eid = entry.get("entity_id")
    etype = entry.get("entity_type")
    if not eid:
        log.warning(f"overlays: skipped entry in {source_path}: missing 'entity_id'")
        return False
    if not etype:
        log.warning(f"overlays: skipped {eid} in {source_path}: missing 'entity_type'")
        return False
    if etype == "signature_chain":
        if not entry.get("tags"):
            log.warning(f"overlays: skipped {eid} in {source_path}: signature_chain requires 'tags'")
            return False
        if not entry.get("artists"):
            log.warning(f"overlays: skipped {eid} in {source_path}: signature_chain requires 'artists'")
            return False
    return True


def _entry_from_dict(d: dict, namespace: str) -> OverlayEntry:
    """Build an OverlayEntry from a validated YAML dict.
    The full original dict is preserved as `body` so callers can read
    arbitrary extra fields (architecture, requires_machines, sources, etc.).

    Coerces entity_id and entity_type to str() defensively — guards against
    YAMLs that use non-string scalar values (e.g., `entity_id: 42`) which
    would otherwise break downstream search() (.lower() on int).
    """
    return OverlayEntry(
        namespace=namespace,
        entity_type=str(d["entity_type"]),
        entity_id=str(d["entity_id"]),
        name=d.get("name", ""),
        description=d.get("description", ""),
        tags=list(d.get("tags") or []),
        artists=list(d.get("artists") or []),
        requires_box=d.get("requires_box"),
        body=d,
    )


def load_overlays(root: Optional[Path] = None,
                  log: Optional[logging.Logger] = None) -> "OverlayIndex":
    """Scan root for namespace subdirs; load YAMLs; mutate the singleton; return it.

    Per spec §5.1:
      - Each immediate subdirectory of root is a namespace.
      - Within each namespace, *.yaml/*.yml files are loaded recursively.
      - File may contain a single dict OR a list of dicts.
      - yaml.safe_load ONLY (rejects Python tags).
      - Idempotent: clears the singleton first.
    """
    log = log or logger
    if root is None:
        root = _resolve_overlay_root()

    idx = get_overlay_index()
    idx.clear()

    if not root.exists():
        return idx

    for ns_dir in sorted(root.iterdir()):
        if not ns_dir.is_dir():
            continue
        namespace = ns_dir.name
        for yaml_path in sorted(list(ns_dir.rglob("*.yaml")) +
                                list(ns_dir.rglob("*.yml"))):
            try:
                with yaml_path.open("r") as f:
                    parsed = yaml.safe_load(f)
            except yaml.YAMLError as e:
                log.warning(f"overlays: skipped {yaml_path}: {e}")
                continue

            if parsed is None:
                continue
            entries = parsed if isinstance(parsed, list) else [parsed]
            for entry_dict in entries:
                if not isinstance(entry_dict, dict):
                    log.warning(f"overlays: skipped non-dict entry in {yaml_path}")
                    continue
                if not _validate_entry(entry_dict, yaml_path, log):
                    continue
                new_entry = _entry_from_dict(entry_dict, namespace)
                previous = idx.add(new_entry)
                if previous is not None:
                    log.warning(
                        f"overlays: duplicate ({new_entry.namespace}, "
                        f"{new_entry.entity_type}, {new_entry.entity_id}) "
                        f"in {yaml_path} — last-loaded wins"
                    )
    return idx


# Module-level singleton — initialized empty at import. Per spec §5.1, §6.1.
# load_overlays() mutates this in place. Tools call get_overlay_index() at
# request time so they always see current state (never capture a reference).
_overlay_index: "OverlayIndex" = OverlayIndex()


def get_overlay_index() -> "OverlayIndex":
    """Accessor for the live overlay singleton. Always returns the same
    instance — load_overlays() mutates it in place rather than replacing."""
    return _overlay_index

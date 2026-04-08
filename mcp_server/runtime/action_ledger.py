"""SessionLedger — in-memory store for semantic moves.

Pure Python, zero I/O.  The ledger tracks every agent-initiated mutation
as a *semantic move* that can be debugged, undone, or promoted to memory.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from .action_ledger_models import LedgerEntry, UndoGroup


class SessionLedger:
    """Per-session record of semantic moves."""

    def __init__(self) -> None:
        self._entries: OrderedDict[str, LedgerEntry] = OrderedDict()

    # ── lifecycle ──────────────────────────────────────────────────────

    def start_move(
        self,
        engine: str,
        move_class: str,
        intent: str,
        undo_scope: str = "micro",
    ) -> str:
        """Create a new LedgerEntry and return its id."""
        entry = LedgerEntry(
            engine=engine,
            move_class=move_class,
            intent=intent,
            undo_scope=undo_scope,
        )
        self._entries[entry.id] = entry
        return entry.id

    def append_action(
        self, entry_id: str, tool_name: str, summary: str
    ) -> None:
        """Add a tool-call record to an existing entry."""
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(f"No ledger entry with id {entry_id!r}")
        entry.actions.append({"tool": tool_name, "summary": summary})

    def set_before_refs(self, entry_id: str, refs: dict) -> None:
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(f"No ledger entry with id {entry_id!r}")
        entry.before_refs = refs

    def set_after_refs(self, entry_id: str, refs: dict) -> None:
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(f"No ledger entry with id {entry_id!r}")
        entry.after_refs = refs

    def finalize_move(
        self,
        entry_id: str,
        kept: bool = True,
        score: float = 0.0,
        memory_candidate: bool = False,
    ) -> None:
        """Seal a move with its evaluation outcome."""
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(f"No ledger entry with id {entry_id!r}")
        entry.kept = kept
        entry.score = score
        entry.memory_candidate = memory_candidate

    # ── queries ────────────────────────────────────────────────────────

    def get_entry(self, entry_id: str) -> Optional[LedgerEntry]:
        return self._entries.get(entry_id)

    def get_last_move(self) -> Optional[LedgerEntry]:
        if not self._entries:
            return None
        # OrderedDict preserves insertion order — last item is newest
        return next(reversed(self._entries.values()))

    def get_recent_moves(
        self,
        limit: int = 10,
        engine: Optional[str] = None,
        kept: Optional[bool] = None,
    ) -> list[LedgerEntry]:
        """Return recent moves, newest first, with optional filters."""
        results: list[LedgerEntry] = []
        for entry in reversed(self._entries.values()):
            if engine is not None and entry.engine != engine:
                continue
            if kept is not None and entry.kept != kept:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def get_memory_candidates(self) -> list[LedgerEntry]:
        """Return all entries flagged as memory promotion candidates."""
        return [e for e in self._entries.values() if e.memory_candidate]

    def get_undo_groups(self) -> list[UndoGroup]:
        """Group entries by undo_scope."""
        groups: dict[str, list[str]] = {}
        for entry in self._entries.values():
            groups.setdefault(entry.undo_scope, []).append(entry.id)
        return [
            UndoGroup(scope=scope, entry_ids=ids)
            for scope, ids in groups.items()
        ]

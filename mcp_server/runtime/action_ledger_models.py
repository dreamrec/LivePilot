"""Data models for the Action Ledger — semantic move tracking.

Classes:
  LedgerEntry — one semantic move with intent, scope, actions, evaluation
  UndoGroup   — group of entries sharing an undo scope
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


# Module-level counter for auto-generating IDs.
_counter: int = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"move_{_counter:04d}"


@dataclass
class LedgerEntry:
    """One semantic move in the session ledger."""

    engine: str
    move_class: str
    intent: str
    undo_scope: str = "micro"

    # Auto-generated
    id: str = field(default_factory=_next_id)
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    # Scope — which tracks / clips / devices are affected
    scope: dict = field(default_factory=dict)

    # Low-level tool calls within this move
    actions: list[dict] = field(default_factory=list)

    # Snapshot references
    before_refs: dict = field(default_factory=dict)
    after_refs: dict = field(default_factory=dict)

    # Evaluation
    evaluation: dict = field(default_factory=dict)
    kept: Optional[bool] = None
    score: float = 0.0
    memory_candidate: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp_ms": self.timestamp_ms,
            "engine": self.engine,
            "move_class": self.move_class,
            "intent": self.intent,
            "scope": self.scope,
            "actions": list(self.actions),
            "before_refs": dict(self.before_refs),
            "after_refs": dict(self.after_refs),
            "evaluation": dict(self.evaluation),
            "kept": self.kept,
            "score": self.score,
            "undo_scope": self.undo_scope,
            "memory_candidate": self.memory_candidate,
        }


@dataclass
class UndoGroup:
    """A group of ledger entries sharing an undo scope."""

    scope: str
    entry_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "entry_ids": list(self.entry_ids),
        }

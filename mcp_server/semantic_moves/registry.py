"""Semantic move registry — stable IDs, discoverable by domain and style."""

from __future__ import annotations

from typing import Optional

from .models import SemanticMove

_REGISTRY: dict[str, SemanticMove] = {}


def register(move: SemanticMove) -> None:
    """Register a semantic move. Duplicate IDs overwrite silently."""
    _REGISTRY[move.move_id] = move


def get_move(move_id: str) -> Optional[SemanticMove]:
    """Get a move by ID. Returns None if not found."""
    return _REGISTRY.get(move_id)


def list_moves(domain: str = "", style: str = "") -> list[dict]:
    """List all registered moves, optionally filtered by domain/style."""
    moves = list(_REGISTRY.values())
    if domain:
        moves = [m for m in moves if m.family == domain]
    return [m.to_dict() for m in moves]


def count() -> int:
    """Return total number of registered moves."""
    return len(_REGISTRY)

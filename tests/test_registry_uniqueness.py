"""Guard-rail: assert semantic_moves registry has no duplicate move_ids and every
move declares a canonical family. Protects v1.20+ additions from silently
overwriting existing moves (dict insertion would clobber without warning).

Kept small and deterministic — this file MUST always pass so future commits
can rely on it to reject accidental ID collisions.
"""

from __future__ import annotations

from collections import Counter

import mcp_server.semantic_moves  # noqa: F401 — triggers registration
from mcp_server.semantic_moves import registry


# 7 canonical families per v1.20 plan §7. No new families may be introduced.
CANONICAL_FAMILIES = frozenset({
    "mix",
    "arrangement",
    "transition",
    "sound_design",
    "performance",
    "device_creation",
    "sample",
})


def _all_moves() -> list:
    return list(registry._REGISTRY.values())


class TestRegistryUniqueness:
    def test_no_duplicate_move_ids(self):
        ids = [m.move_id for m in _all_moves()]
        counts = Counter(ids)
        dupes = {mid: n for mid, n in counts.items() if n > 1}
        assert not dupes, f"Duplicate move_ids would silently overwrite: {dupes}"

    def test_every_move_has_nonempty_id(self):
        for move in _all_moves():
            assert move.move_id, "move_id cannot be empty"
            assert isinstance(move.move_id, str)

    def test_every_move_declares_canonical_family(self):
        for move in _all_moves():
            assert move.family in CANONICAL_FAMILIES, (
                f"{move.move_id!r} has family {move.family!r}; "
                f"must be one of {sorted(CANONICAL_FAMILIES)}"
            )

    def test_registry_count_matches_module_inventory(self):
        """Catch out-of-sync imports — registry.count() must match len(_REGISTRY)."""
        assert registry.count() == len(registry._REGISTRY)
        assert registry.count() >= 33, (
            f"Registry dropped below v1.19 baseline (33 moves); got {registry.count()}"
        )

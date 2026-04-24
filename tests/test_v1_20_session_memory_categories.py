"""v1.20 session-memory category contract.

The creative director's Phase 6 escape hatch mandates two specific
memory categories (`move_executed` and `tech_debt`). Pre-v1.20, the
SessionMemoryStore's allowlist only accepted
{observation, hypothesis, decision, issue}, so the director's
mandatory logging would raise ValueError. This suite pins the
expanded v1.20 allowlist.

Also pins `override` — recorded when the user explicitly overrides a
check_brief_compliance violation (per SKILL.md Phase 6).
"""

from __future__ import annotations

import pytest

from mcp_server.memory.session_memory import (
    SessionMemoryStore,
    _VALID_CATEGORIES,
)


# Categories Phase 6 needs alongside the pre-v1.20 set.
_V1_20_REQUIRED_CATEGORIES = frozenset({"move_executed", "tech_debt", "override"})
# Pre-v1.20 categories that MUST still be accepted (backward compat).
_PRE_V1_20_CATEGORIES = frozenset({"observation", "hypothesis", "decision", "issue"})


class TestV120SessionMemoryCategories:
    def test_v1_20_categories_are_in_the_allowlist(self):
        missing = _V1_20_REQUIRED_CATEGORIES - _VALID_CATEGORIES
        assert not missing, (
            f"v1.20 director Phase 6 requires these categories but they "
            f"aren't in _VALID_CATEGORIES: {sorted(missing)}"
        )

    def test_pre_v1_20_categories_still_accepted_backward_compat(self):
        """Adding v1.20 categories must not silently drop the older ones."""
        missing = _PRE_V1_20_CATEGORIES - _VALID_CATEGORIES
        assert not missing, (
            f"pre-v1.20 categories disappeared: {sorted(missing)} — "
            "breaking change, not allowed"
        )

    def test_move_executed_write_succeeds(self):
        store = SessionMemoryStore()
        eid = store.add(
            category="move_executed",
            content="mix:track-0 rename to Dub — brief: dub architecture",
            engine="creative_director",
        )
        assert eid.startswith("smem_")
        recent = store.get_recent(category="move_executed")
        assert len(recent) == 1
        assert recent[0].category == "move_executed"

    def test_tech_debt_write_succeeds(self):
        store = SessionMemoryStore()
        eid = store.add(
            category="tech_debt",
            content=(
                "no semantic_move for: arm/disarm track. Suggested move: "
                "configure_record_readiness, family=performance, "
                "seed_args={track_index, armed}"
            ),
            engine="creative_director",
        )
        assert eid.startswith("smem_")

    def test_override_write_succeeds(self):
        store = SessionMemoryStore()
        store.add(
            category="override",
            content="user overrode check_brief_compliance bright-top-end violation",
            engine="creative_director",
        )
        assert len(store.get_recent(category="override")) == 1

    def test_filtering_by_v1_20_category(self):
        """get_recent(category='tech_debt') must return only tech_debt
        entries — anti-repetition reads rely on category filtering."""
        store = SessionMemoryStore()
        store.add(category="observation", content="noted a thing", engine="test")
        store.add(category="move_executed", content="m1", engine="test")
        store.add(category="tech_debt", content="gap1", engine="test")
        store.add(category="move_executed", content="m2", engine="test")
        store.add(category="tech_debt", content="gap2", engine="test")

        tech_debt = store.get_recent(category="tech_debt")
        assert len(tech_debt) == 2
        assert all(e.category == "tech_debt" for e in tech_debt)

        moves = store.get_recent(category="move_executed")
        assert len(moves) == 2
        assert all(e.category == "move_executed" for e in moves)

    def test_unknown_category_still_rejected(self):
        """Adding v1.20 categories must not loosen validation for arbitrary
        strings — that was the point of the allowlist in the first place."""
        store = SessionMemoryStore()
        with pytest.raises(ValueError, match="category must be one of"):
            store.add(category="made_up_category", content="x", engine="test")

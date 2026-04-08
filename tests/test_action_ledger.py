"""Comprehensive tests for the Action Ledger — models and session ledger."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.action_ledger_models import LedgerEntry, UndoGroup
from mcp_server.runtime.action_ledger import SessionLedger


# ---------------------------------------------------------------------------
# TestLedgerEntry
# ---------------------------------------------------------------------------

class TestLedgerEntry:

    def test_creates_entry_with_defaults(self):
        entry = LedgerEntry(
            engine="composition",
            move_class="transition_gesture",
            intent="make the drop feel earned",
        )
        assert entry.engine == "composition"
        assert entry.move_class == "transition_gesture"
        assert entry.intent == "make the drop feel earned"
        assert entry.id.startswith("move_")
        assert entry.timestamp_ms > 0
        assert entry.kept is None
        assert entry.score == 0.0
        assert entry.undo_scope == "micro"
        assert entry.memory_candidate is False
        assert entry.actions == []
        assert entry.scope == {}
        assert entry.before_refs == {}
        assert entry.after_refs == {}

    def test_auto_generates_unique_ids(self):
        a = LedgerEntry(engine="mix", move_class="eq", intent="a")
        b = LedgerEntry(engine="mix", move_class="eq", intent="b")
        assert a.id != b.id

    def test_to_dict(self):
        entry = LedgerEntry(
            engine="composition",
            move_class="transition_gesture",
            intent="test",
        )
        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["engine"] == "composition"
        assert d["move_class"] == "transition_gesture"
        assert d["intent"] == "test"
        assert d["kept"] is None
        assert d["score"] == 0.0
        assert d["undo_scope"] == "micro"
        assert d["memory_candidate"] is False
        assert "id" in d
        assert "timestamp_ms" in d


class TestUndoGroup:

    def test_to_dict(self):
        g = UndoGroup(scope="section", entry_ids=["move_0001", "move_0002"])
        d = g.to_dict()
        assert d["scope"] == "section"
        assert d["entry_ids"] == ["move_0001", "move_0002"]


# ---------------------------------------------------------------------------
# TestSessionLedger
# ---------------------------------------------------------------------------

class TestSessionLedger:

    def test_start_and_finalize_move(self):
        ledger = SessionLedger()
        mid = ledger.start_move(
            engine="composition",
            move_class="transition_gesture",
            intent="make the section arrival feel earned",
            undo_scope="phrase",
        )
        assert mid.startswith("move_")

        entry = ledger.get_entry(mid)
        assert entry is not None
        assert entry.kept is None

        ledger.finalize_move(mid, kept=True, score=0.85, memory_candidate=True)
        assert entry.kept is True
        assert entry.score == 0.85
        assert entry.memory_candidate is True

    def test_append_action(self):
        ledger = SessionLedger()
        mid = ledger.start_move(
            engine="mix", move_class="eq_correction", intent="clean low-mids"
        )
        ledger.append_action(mid, "set_device_parameter", "cut 250Hz by 3dB")
        ledger.append_action(mid, "set_device_parameter", "boost 4kHz shelf")

        entry = ledger.get_entry(mid)
        assert len(entry.actions) == 2
        assert entry.actions[0]["tool"] == "set_device_parameter"
        assert entry.actions[1]["summary"] == "boost 4kHz shelf"

    def test_set_before_and_after_refs(self):
        ledger = SessionLedger()
        mid = ledger.start_move(engine="mix", move_class="eq", intent="test")
        ledger.set_before_refs(mid, {"snapshot_id": "snap_01"})
        ledger.set_after_refs(mid, {"snapshot_id": "snap_02"})

        entry = ledger.get_entry(mid)
        assert entry.before_refs["snapshot_id"] == "snap_01"
        assert entry.after_refs["snapshot_id"] == "snap_02"

    def test_get_recent_moves(self):
        ledger = SessionLedger()
        for i in range(5):
            ledger.start_move(
                engine="composition", move_class="test", intent=f"move {i}"
            )
        recent = ledger.get_recent_moves(limit=3)
        assert len(recent) == 3
        # Newest first
        assert recent[0].intent == "move 4"
        assert recent[1].intent == "move 3"
        assert recent[2].intent == "move 2"

    def test_filter_by_engine(self):
        ledger = SessionLedger()
        ledger.start_move(engine="composition", move_class="a", intent="c1")
        ledger.start_move(engine="mix", move_class="b", intent="m1")
        ledger.start_move(engine="composition", move_class="c", intent="c2")

        comp = ledger.get_recent_moves(engine="composition")
        assert len(comp) == 2
        assert all(e.engine == "composition" for e in comp)

        mix = ledger.get_recent_moves(engine="mix")
        assert len(mix) == 1
        assert mix[0].engine == "mix"

    def test_filter_by_kept(self):
        ledger = SessionLedger()
        m1 = ledger.start_move(engine="mix", move_class="a", intent="kept")
        m2 = ledger.start_move(engine="mix", move_class="b", intent="undone")
        m3 = ledger.start_move(engine="mix", move_class="c", intent="pending")

        ledger.finalize_move(m1, kept=True)
        ledger.finalize_move(m2, kept=False)
        # m3 left unfinalized (kept=None)

        kept = ledger.get_recent_moves(kept=True)
        assert len(kept) == 1
        assert kept[0].intent == "kept"

        undone = ledger.get_recent_moves(kept=False)
        assert len(undone) == 1
        assert undone[0].intent == "undone"

    def test_memory_candidates(self):
        ledger = SessionLedger()
        m1 = ledger.start_move(engine="mix", move_class="a", intent="good")
        m2 = ledger.start_move(engine="mix", move_class="b", intent="meh")
        m3 = ledger.start_move(engine="mix", move_class="c", intent="great")

        ledger.finalize_move(m1, kept=True, memory_candidate=True)
        ledger.finalize_move(m2, kept=True, memory_candidate=False)
        ledger.finalize_move(m3, kept=True, score=0.9, memory_candidate=True)

        candidates = ledger.get_memory_candidates()
        assert len(candidates) == 2
        intents = {c.intent for c in candidates}
        assert intents == {"good", "great"}

    def test_undo_groups(self):
        ledger = SessionLedger()
        ledger.start_move(engine="mix", move_class="a", intent="1", undo_scope="micro")
        ledger.start_move(engine="mix", move_class="b", intent="2", undo_scope="micro")
        ledger.start_move(engine="comp", move_class="c", intent="3", undo_scope="section")
        ledger.start_move(engine="comp", move_class="d", intent="4", undo_scope="mix")

        groups = ledger.get_undo_groups()
        scopes = {g.scope for g in groups}
        assert scopes == {"micro", "section", "mix"}

        micro = [g for g in groups if g.scope == "micro"][0]
        assert len(micro.entry_ids) == 2

    def test_get_last_move(self):
        ledger = SessionLedger()
        ledger.start_move(engine="mix", move_class="a", intent="first")
        ledger.start_move(engine="mix", move_class="b", intent="second")
        ledger.start_move(engine="comp", move_class="c", intent="third")

        last = ledger.get_last_move()
        assert last is not None
        assert last.intent == "third"

    def test_empty_ledger(self):
        ledger = SessionLedger()
        assert ledger.get_last_move() is None
        assert ledger.get_recent_moves() == []
        assert ledger.get_memory_candidates() == []
        assert ledger.get_undo_groups() == []
        assert ledger.get_entry("move_9999") is None

    def test_multiple_moves_ordering(self):
        ledger = SessionLedger()
        ids = []
        for i in range(7):
            mid = ledger.start_move(
                engine="composition", move_class="test", intent=f"m{i}"
            )
            ids.append(mid)

        recent = ledger.get_recent_moves(limit=7)
        assert len(recent) == 7
        # Newest first
        assert recent[0].intent == "m6"
        assert recent[-1].intent == "m0"

    def test_interleaving_engines(self):
        """Composition and mix moves interleaved in one session."""
        ledger = SessionLedger()
        c1 = ledger.start_move(engine="composition", move_class="structure", intent="verse setup")
        m1 = ledger.start_move(engine="mix", move_class="eq", intent="bass cleanup")
        c2 = ledger.start_move(engine="composition", move_class="transition", intent="drop build")

        ledger.append_action(c1, "create_clip", "drums stripped")
        ledger.append_action(m1, "set_device_parameter", "low cut at 80Hz")
        ledger.append_action(c2, "set_clip_automation", "filter sweep 1 bar")

        ledger.finalize_move(c1, kept=True, score=0.7)
        ledger.finalize_move(m1, kept=True, score=0.8, memory_candidate=True)
        ledger.finalize_move(c2, kept=False, score=0.3)

        comp = ledger.get_recent_moves(engine="composition")
        assert len(comp) == 2

        mix = ledger.get_recent_moves(engine="mix")
        assert len(mix) == 1
        assert mix[0].memory_candidate is True

        kept = ledger.get_recent_moves(kept=True)
        assert len(kept) == 2

        candidates = ledger.get_memory_candidates()
        assert len(candidates) == 1
        assert candidates[0].engine == "mix"

    def test_append_action_raises_on_bad_id(self):
        ledger = SessionLedger()
        try:
            ledger.append_action("move_9999", "tool", "summary")
            assert False, "Expected KeyError"
        except KeyError:
            pass

    def test_finalize_raises_on_bad_id(self):
        ledger = SessionLedger()
        try:
            ledger.finalize_move("move_9999")
            assert False, "Expected KeyError"
        except KeyError:
            pass

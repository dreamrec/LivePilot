"""Tests for per-project persistent state."""

import tempfile
from pathlib import Path

from mcp_server.persistence.project_store import ProjectStore, project_hash


# ── Project identity ─────────────────────────────────────────────


def test_project_hash_stable():
    info = {"tempo": 120.0, "tracks": [{"name": "Drums"}, {"name": "Bass"}]}
    h1 = project_hash(info)
    h2 = project_hash(info)
    assert h1 == h2
    assert len(h1) == 12


def test_project_hash_differs():
    info1 = {"tempo": 120.0, "tracks": [{"name": "Drums"}]}
    info2 = {"tempo": 128.0, "tracks": [{"name": "Drums"}]}
    assert project_hash(info1) != project_hash(info2)


# ── v1.10.3 Truth Release: collision-resistance regressions ──

def test_project_hash_distinguishes_track_order():
    """Two sessions with the same tracks in different order must not collide.
    This was a real failure mode in the old hash (which sorted track names)."""
    info1 = {
        "tempo": 128.0,
        "tracks": [
            {"index": 0, "name": "Drums"},
            {"index": 1, "name": "Bass"},
            {"index": 2, "name": "Lead"},
        ],
    }
    info2 = {
        "tempo": 128.0,
        "tracks": [
            {"index": 0, "name": "Lead"},
            {"index": 1, "name": "Bass"},
            {"index": 2, "name": "Drums"},
        ],
    }
    assert project_hash(info1) != project_hash(info2), \
        "Track reordering should produce a different project hash"


def test_project_hash_distinguishes_by_song_length():
    """Two sessions with identical tempo + tracks but different arrangement
    lengths must not collide (common template-based project scenario)."""
    base = {
        "tempo": 128.0,
        "tracks": [{"index": 0, "name": "Drums"}, {"index": 1, "name": "Bass"}],
    }
    info1 = dict(base, song_length=64.0)
    info2 = dict(base, song_length=128.0)
    assert project_hash(info1) != project_hash(info2)


def test_project_hash_distinguishes_by_scene_list():
    """Two sessions with identical tempo + tracks but different scenes must
    not collide."""
    tracks = [{"index": 0, "name": "Drums"}, {"index": 1, "name": "Bass"}]
    info1 = {
        "tempo": 128.0,
        "tracks": tracks,
        "scenes": [{"index": 0, "name": "Intro"}, {"index": 1, "name": "Verse"}],
    }
    info2 = {
        "tempo": 128.0,
        "tracks": tracks,
        "scenes": [{"index": 0, "name": "Intro"}, {"index": 1, "name": "Chorus"}],
    }
    assert project_hash(info1) != project_hash(info2)


def test_project_hash_distinguishes_by_time_signature():
    """Two sessions at 128 BPM with different time signatures must not collide."""
    tracks = [{"index": 0, "name": "Drums"}]
    info1 = {"tempo": 128.0, "tracks": tracks,
             "signature_numerator": 4, "signature_denominator": 4}
    info2 = {"tempo": 128.0, "tracks": tracks,
             "signature_numerator": 7, "signature_denominator": 8}
    assert project_hash(info1) != project_hash(info2)


def test_project_hash_distinguishes_by_track_rename():
    """Renaming a track changes the project identity (honest: it's a real
    edit). This is the tradeoff documented in the function's docstring."""
    info1 = {
        "tempo": 128.0,
        "tracks": [{"index": 0, "name": "Drums"}, {"index": 1, "name": "Bass"}],
    }
    info2 = {
        "tempo": 128.0,
        "tracks": [{"index": 0, "name": "Drums"}, {"index": 1, "name": "Sub"}],
    }
    assert project_hash(info1) != project_hash(info2)


def test_project_hash_stable_for_identical_full_session():
    """Full session info produces a stable hash across multiple reads."""
    info = {
        "tempo": 128.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 192.0,
        "tracks": [
            {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
            {"index": 1, "name": "Bass", "color_index": 2, "has_midi_input": True},
        ],
        "return_tracks": [{"index": 0, "name": "Reverb"}],
        "scenes": [
            {"index": 0, "name": "Intro"},
            {"index": 1, "name": "Drop"},
        ],
    }
    h1 = project_hash(info)
    h2 = project_hash(info)
    h3 = project_hash(dict(info))  # copy, same content
    assert h1 == h2 == h3
    assert len(h1) == 12


# ── Thread persistence ───────────────────────────────────────────


def test_thread_persists():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_thread({"thread_id": "t1", "description": "Chorus lift", "status": "open"})

        store2 = ProjectStore("proj1", base_dir=Path(d))
        threads = store2.get_threads()
        assert any(t["thread_id"] == "t1" for t in threads)


def test_thread_update():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_thread({"thread_id": "t1", "description": "Chorus", "status": "open"})
        store.save_thread({"thread_id": "t1", "description": "Chorus", "status": "resolved"})

        threads = ProjectStore("proj1", base_dir=Path(d)).get_threads()
        t = next(t for t in threads if t["thread_id"] == "t1")
        assert t["status"] == "resolved"
        assert len(threads) == 1  # no duplicate


# ── Turn persistence ─────────────────────────────────────────────


def test_turn_persists():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_turn({"turn_id": "tr1", "outcome": "accepted"})

        turns = ProjectStore("proj1", base_dir=Path(d)).get_turns()
        assert any(t["turn_id"] == "tr1" for t in turns)


def test_turn_capped():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        for i in range(60):
            store.save_turn({"turn_id": f"tr_{i}", "outcome": "accepted"})

        turns = ProjectStore("proj1", base_dir=Path(d)).get_turns()
        assert len(turns) == 50  # capped


# ── Wonder outcomes ──────────────────────────────────────────────


def test_wonder_outcome_persists():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_wonder_outcome({"session_id": "ws1", "outcome": "committed"})

        outcomes = ProjectStore("proj1", base_dir=Path(d)).get_wonder_outcomes()
        assert any(o["session_id"] == "ws1" for o in outcomes)


# ── Project isolation ────────────────────────────────────────────


def test_different_projects_isolated():
    with tempfile.TemporaryDirectory() as d:
        s1 = ProjectStore("proj_a", base_dir=Path(d))
        s2 = ProjectStore("proj_b", base_dir=Path(d))

        s1.save_thread({"thread_id": "ta", "description": "A"})
        s2.save_thread({"thread_id": "tb", "description": "B"})

        assert len(ProjectStore("proj_a", base_dir=Path(d)).get_threads()) == 1
        assert len(ProjectStore("proj_b", base_dir=Path(d)).get_threads()) == 1
        assert ProjectStore("proj_a", base_dir=Path(d)).get_threads()[0]["thread_id"] == "ta"

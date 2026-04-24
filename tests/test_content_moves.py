"""Content-family semantic-moves tests (v1.20 commit 3).

Two new moves:
    load_chord_source     — sound_design, 3-step clip creation (create→add→name)
    create_drum_rack_pad  — device_creation, single add_drum_rack_pad call

load_chord_source is the Basic Channel / dub-chord workflow entry point —
drop a single chord voicing into a source clip slot that feeds a send
chain. create_drum_rack_pad is the Dilla-style kit-building primitive —
add one pad at a time from a sample URI / file path.
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


_DEFAULT_CHORD_NOTES = [
    {"pitch": 60, "start_time": 0.0, "duration": 4.0, "velocity": 80},
    {"pitch": 64, "start_time": 0.0, "duration": 4.0, "velocity": 75},
    {"pitch": 67, "start_time": 0.0, "duration": 4.0, "velocity": 70},
]


# ── load_chord_source ─────────────────────────────────────────────────────────


class TestLoadChordSourceMove:
    def test_move_registered(self):
        move = get_move("load_chord_source")
        assert move is not None
        assert move.family == "sound_design"

    def test_targets_favor_harmonic_dimension(self):
        move = get_move("load_chord_source")
        # A chord stab should at minimum claim the harmonic dimension.
        assert "harmonic" in move.targets
        assert move.targets["harmonic"] >= 0.3

    def test_compiler_emits_three_ordered_steps(self):
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_slot": 0,
                "notes": _DEFAULT_CHORD_NOTES,
                "name": "dub-chord stab",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        # Order is load-bearing: create before add, add before name.
        tools_in_order = [s.tool for s in plan.steps if s.tool in {
            "create_clip", "add_notes", "set_clip_name"
        }]
        assert tools_in_order == ["create_clip", "add_notes", "set_clip_name"]

    def test_compiler_defaults_length_to_four_beats(self):
        """Chord stabs default to 4 beats (one bar at 4/4) when caller
        omits length_beats. Keeps the move ergonomic for the common case."""
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_slot": 0,
                "notes": _DEFAULT_CHORD_NOTES,
                "name": "chord",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        create = [s for s in plan.steps if s.tool == "create_clip"][0]
        assert create.params["length"] == 4.0

    def test_compiler_respects_explicit_length(self):
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_slot": 0,
                "notes": _DEFAULT_CHORD_NOTES,
                "name": "long pad",
                "length_beats": 16.0,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        create = [s for s in plan.steps if s.tool == "create_clip"][0]
        assert create.params["length"] == 16.0

    def test_compiler_threads_notes_to_add_notes_step(self):
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 2,
                "clip_slot": 3,
                "notes": _DEFAULT_CHORD_NOTES,
                "name": "test",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        add = [s for s in plan.steps if s.tool == "add_notes"][0]
        assert add.params["track_index"] == 2
        assert add.params["clip_index"] == 3
        assert add.params["notes"] == _DEFAULT_CHORD_NOTES

    def test_compiler_rejects_empty_notes(self):
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_slot": 0,
                "notes": [],
                "name": "empty",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_missing_name(self):
        """A nameless chord clip would lose identity in the session; require name."""
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_slot": 0,
                "notes": _DEFAULT_CHORD_NOTES,
                # name missing
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_nonsensical_clip_slot(self):
        move = get_move("load_chord_source")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "clip_slot": -1,
                "notes": _DEFAULT_CHORD_NOTES,
                "name": "bad",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── create_drum_rack_pad (the move) ───────────────────────────────────────────


class TestCreateDrumRackPadMove:
    def test_move_registered(self):
        move = get_move("create_drum_rack_pad")
        assert move is not None
        assert move.family == "device_creation"

    def test_targets_favor_groove(self):
        move = get_move("create_drum_rack_pad")
        # Drum rack building is intrinsically groove-facing.
        assert "groove" in move.targets or "punch" in move.targets

    def test_compiler_emits_single_add_drum_rack_pad_step(self):
        move = get_move("create_drum_rack_pad")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "pad_note": 36,
                "file_path": "/Users/me/Samples/kick.wav",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        pad_steps = [s for s in plan.steps if s.tool == "add_drum_rack_pad"]
        assert len(pad_steps) == 1
        params = pad_steps[0].params
        assert params["track_index"] == 0
        assert params["pad_note"] == 36
        assert params["file_path"] == "/Users/me/Samples/kick.wav"

    def test_compiler_passes_optional_rack_device_index(self):
        move = get_move("create_drum_rack_pad")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "pad_note": 38,
                "file_path": "/samples/snare.wav",
                "rack_device_index": 2,
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        pad = [s for s in plan.steps if s.tool == "add_drum_rack_pad"][0]
        assert pad.params["rack_device_index"] == 2

    def test_compiler_passes_optional_chain_name(self):
        move = get_move("create_drum_rack_pad")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "pad_note": 42,
                "file_path": "/samples/hh.wav",
                "chain_name": "Closed Hat",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        pad = [s for s in plan.steps if s.tool == "add_drum_rack_pad"][0]
        assert pad.params["chain_name"] == "Closed Hat"

    def test_compiler_rejects_pad_note_out_of_midi_range(self):
        move = get_move("create_drum_rack_pad")
        for bad_note in (-1, 128, 200):
            kernel = {
                "seed_args": {
                    "track_index": 0,
                    "pad_note": bad_note,
                    "file_path": "/a.wav",
                },
                "session_info": {},
                "mode": "improve",
            }
            plan = move_compiler.compile(move, kernel)
            assert not plan.executable, f"pad_note={bad_note} should reject"

    def test_compiler_rejects_empty_file_path(self):
        move = get_move("create_drum_rack_pad")
        kernel = {
            "seed_args": {"track_index": 0, "pad_note": 36, "file_path": ""},
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable

    def test_compiler_rejects_missing_required_args(self):
        move = get_move("create_drum_rack_pad")
        kernel = {
            "seed_args": {"track_index": 0},  # pad_note + file_path missing
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable


# ── Cross-family ───────────────────────────────────────────────────────────────


def test_content_family_compilers_registered():
    for move_id in ("load_chord_source", "create_drum_rack_pad"):
        move = get_move(move_id)
        kernel = {"seed_args": {}, "session_info": {}, "mode": "improve"}
        plan = move_compiler.compile(move, kernel)
        fallback = [w for w in plan.warnings if "No compiler" in w]
        assert not fallback, f"{move_id}: {fallback}"

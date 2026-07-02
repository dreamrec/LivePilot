from __future__ import annotations

from mcp_server.persistence.session_snapshot import SessionSnapshotStore


def _session(tracks: list[dict]) -> dict:
    return {
        "project_identity": {
            "file_path": "/Users/me/Song.als",
        },
        "tempo": 120.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 64.0,
        "tracks": tracks,
        "return_tracks": [],
        "scenes": [],
    }


def _unsaved_session(tracks: list[dict]) -> dict:
    data = _session(tracks)
    data.pop("project_identity", None)
    return data


def test_plain_mcp_snapshot_preserves_section_track_clips(tmp_path):
    store = SessionSnapshotStore(tmp_path / "current_session.json")
    rich = _session([
        {
            "index": 0,
            "name": "SECTION MAP",
            "has_midi_input": True,
            "arrangement_clips": [
                {"name": "Intro", "start_time": 0.0, "end_time": 16.0},
            ],
        },
        {"index": 1, "name": "Drums", "has_audio_input": True},
    ])
    plain = _session([
        {"index": 0, "name": "SECTION MAP", "has_midi_input": True},
        {"index": 1, "name": "Drums", "has_audio_input": True},
    ])

    store.save(rich, source="focus_panel_probe")
    saved = store.save(plain, source="mcp")

    section_track = saved["session_info"]["tracks"][0]
    assert saved["source"] == "mcp"
    assert section_track["arrangement_clips"] == [
        {"name": "Intro", "start_time": 0.0, "end_time": 16.0},
    ]


def test_snapshot_does_not_preserve_section_clips_across_save_as(tmp_path):
    store = SessionSnapshotStore(tmp_path / "current_session.json")
    rich = _session([
        {
            "index": 0,
            "name": "SECTION MAP",
            "has_midi_input": True,
            "arrangement_clips": [
                {"name": "Intro", "start_time": 0.0, "end_time": 16.0},
            ],
        },
    ])
    save_as = _session([
        {"index": 0, "name": "SECTION MAP", "has_midi_input": True},
    ])
    save_as["project_identity"] = {"file_path": "/Users/me/Song B.als"}

    store.save(rich, source="focus_panel_probe")
    saved = store.save(save_as, source="mcp")

    assert "arrangement_clips" not in saved["session_info"]["tracks"][0]


def test_snapshot_preserves_cue_points_across_single_unsaved_track_rename(tmp_path):
    store = SessionSnapshotStore(tmp_path / "current_session.json")
    rich = _unsaved_session([
        {"index": 0, "name": "SECTION MAP", "has_midi_input": True},
        {"index": 1, "name": "Drums", "has_audio_input": True},
        {"index": 2, "name": "Bass", "has_midi_input": True},
        {"index": 3, "name": "Vox", "has_audio_input": True},
        {"index": 4, "name": "Guitar", "has_audio_input": True},
    ])
    rich["cue_points"] = [
        {"index": 0, "name": "Intro", "time": 0.0},
        {"index": 1, "name": "Verse", "time": 16.0},
    ]
    renamed = _unsaved_session([
        {"index": 0, "name": "SECTION MAP", "has_midi_input": True},
        {"index": 1, "name": "Drums", "has_audio_input": True},
        {"index": 2, "name": "Bass", "has_midi_input": True},
        {"index": 3, "name": "Lead Vox", "has_audio_input": True},
        {"index": 4, "name": "Guitar", "has_audio_input": True},
    ])

    store.save(rich, source="focus_panel_probe")
    saved = store.save(renamed, source="mcp")

    assert saved["session_info"]["cue_points"] == [
        {"index": 0, "name": "Intro", "time": 0.0},
        {"index": 1, "name": "Verse", "time": 16.0},
    ]

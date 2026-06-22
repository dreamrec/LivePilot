from __future__ import annotations

from types import SimpleNamespace

from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.persistence.track_annotations import annotation_project_hash
from mcp_server.tools.tracks import (
    build_track_intent_map,
    clear_track_annotation,
    get_track_annotations,
    get_track_info,
    set_track_annotation,
)


def _session(tracks: list[dict]) -> dict:
    return {
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 72.0,
        "tracks": tracks,
        "return_tracks": [{"index": 0, "name": "A"}],
        "scenes": [{"index": 0, "name": "Scene 1"}],
    }


class _Ableton:
    def __init__(self, session_info: dict):
        self.session_info = session_info

    def send_command(self, cmd, params=None):
        if cmd == "get_session_info":
            return self.session_info
        if cmd == "get_track_info":
            track_index = params["track_index"]
            track = next(t for t in self.session_info["tracks"] if t["index"] == track_index)
            return {
                "index": track_index,
                "name": track["name"],
                "devices": [{"name": "Utility", "class_name": "AudioEffect"}],
                "clips": [{"name": "main"}],
            }
        raise AssertionError(f"Unexpected command: {cmd}")


def _ctx(ableton: _Ableton):
    return SimpleNamespace(lifespan_context={"ableton": ableton})


def test_annotation_project_hash_ignores_track_reorder():
    first = _session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        {"index": 1, "name": "Vox 1", "color_index": 2, "has_audio_input": True},
    ])
    reordered = _session([
        {"index": 0, "name": "Vox 1", "color_index": 2, "has_audio_input": True},
        {"index": 1, "name": "Drums", "color_index": 1, "has_midi_input": True},
    ])

    assert annotation_project_hash(first) == annotation_project_hash(reordered)


def test_track_annotation_resolves_after_track_move(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ableton = _Ableton(_session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        {"index": 1, "name": "Vox 1", "color_index": 2, "has_audio_input": True},
        {"index": 2, "name": "Bass", "color_index": 3, "has_midi_input": True},
    ]))
    ctx = _ctx(ableton)

    saved = set_track_annotation(
        ctx,
        track_index=1,
        role="lead_vox",
        notes="Main lead vocal; keep up front.",
        tags=["vocal", "lead"],
        relationship="anchor for vocal doubles",
    )
    annotation_id = saved["annotation"]["annotation_id"]

    ableton.session_info = _session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        {"index": 1, "name": "Bass", "color_index": 3, "has_midi_input": True},
        {"index": 2, "name": "Vox 1", "color_index": 2, "has_audio_input": True},
    ])

    listed = get_track_annotations(ctx, track_index=2)
    assert listed["count"] == 1
    annotation = listed["annotations"][0]
    assert annotation["annotation_id"] == annotation_id
    assert annotation["role"] == "lead_vox"
    assert annotation["resolution"]["status"] == "resolved"
    assert annotation["resolution"]["resolved_track_index"] == 2

    track_info = get_track_info(ctx, track_index=2)
    assert track_info["track_annotation"]["annotation_id"] == annotation_id


def test_clear_track_annotation_by_id(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ableton = _Ableton(_session([
        {"index": 0, "name": "Vox 1", "color_index": 2, "has_audio_input": True},
    ]))
    ctx = _ctx(ableton)
    saved = set_track_annotation(ctx, track_index=0, role="lead_vox")

    cleared = clear_track_annotation(ctx, annotation_id=saved["annotation"]["annotation_id"])
    assert cleared["cleared_count"] == 1
    assert get_track_annotations(ctx)["count"] == 0


def test_open_track_options_surface_in_intent_map(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ableton = _Ableton(_session([
        {"index": 0, "name": "Vox Harmony", "color_index": 2, "has_audio_input": True},
    ]))
    ctx = _ctx(ableton)

    set_track_annotation(
        ctx,
        track_index=0,
        role="harmony_vocal",
        role_candidates=["support_harmony", "ensemble_harmony"],
        decision_state="open",
        priority="undecided",
        notes="Could be tucked or could become a communal harmony stack.",
        constraints=["preserve_timing"],
        decision_policy="audition_before_commit",
        options=[
            {
                "option_id": "tucked_support",
                "label": "barely-there support",
                "role": "support_harmony",
                "priority": "background",
            },
            {
                "option_id": "ensemble_harmony",
                "label": "Beatles-style ensemble",
                "role": "ensemble_harmony",
                "priority": "co_foreground",
            },
        ],
        references=[
            {
                "scope": "track",
                "artist": "The Beatles",
                "part": "ensemble harmony",
                "borrow": ["shared foreground"],
            }
        ],
    )

    intent_map = build_track_intent_map(ctx)
    track = intent_map["tracks"][0]
    assert track["decision_state"] == "open"
    assert track["effective_role"] is None
    assert track["role_source"] == "open_options"
    assert track["requires_audition"] is True
    assert "ensemble_harmony" in track["role_candidates"]
    assert track["constraints"] == ["preserve_timing"]
    assert track["references"][0]["artist"] == "The Beatles"


def test_committed_explicit_role_overrides_name_in_intent_map(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ableton = _Ableton(_session([
        {"index": 0, "name": "Texture Pad", "color_index": 4, "has_midi_input": True},
    ]))
    ctx = _ctx(ableton)

    set_track_annotation(
        ctx,
        track_index=0,
        role="bass",
        decision_state="committed",
        source="user_explicit",
        confidence=1.0,
    )

    track = build_track_intent_map(ctx)["tracks"][0]
    assert track["inferred_role"] == "pad"
    assert track["effective_role"] == "bass"
    assert track["role_source"] == "user_explicit"


def test_project_scope_annotation_without_track(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ableton = _Ableton(_session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
    ]))
    ctx = _ctx(ableton)

    set_track_annotation(
        ctx,
        track_index=None,
        scope="project",
        notes="Overall reference is The Suburbs: raw, communal, restrained.",
        references=[
            {
                "scope": "project",
                "artist": "Arcade Fire",
                "song": "The Suburbs",
                "borrow": ["raw ensemble glue"],
            }
        ],
    )

    intent_map = build_track_intent_map(ctx)
    assert intent_map["project_intents"][0]["notes"].startswith("Overall reference")
    assert intent_map["project_intents"][0]["references"][0]["song"] == "The Suburbs"

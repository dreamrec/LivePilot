from __future__ import annotations

import json

from mcp_server.persistence.production_context import (
    ProductionContextService,
    ProductionContextStore,
)
from mcp_server.persistence.track_annotations import annotation_project_id_for_session


def _session() -> dict:
    return {
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 72.0,
        "tracks": [
            {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        ],
        "return_tracks": [],
        "scenes": [],
    }


def _session_3_4() -> dict:
    session = _session()
    session["signature_numerator"] = 3
    return session


def test_section_object_round_trips(tmp_path):
    service = ProductionContextService(base_dir=tmp_path)
    saved = service.save_state(
        _session(),
        section={
            "section_id": "cue_points_64000_verse",
            "label": "Verse",
            "start_beat": 64.0,
            "end_beat": 128.0,
            "source": "cue_points",
        },
    )

    assert saved["state"]["section"] == {
        "section_id": "cue_points_64000_verse",
        "label": "Verse",
        "start_beat": 64.0,
        "end_beat": 128.0,
        "source": "cue_points",
    }
    assert service.get_state(_session())["state"]["section"]["section_id"] == (
        "cue_points_64000_verse"
    )


def test_whole_song_is_stored_as_null_section(tmp_path):
    service = ProductionContextService(base_dir=tmp_path)
    saved = service.save_state(
        _session(),
        section={
            "section_id": "ignored",
            "label": "Whole song",
            "source": "whole_song",
        },
    )

    assert saved["state"]["section"] is None


def test_v1_section_scope_migrates_on_read_without_rewriting(tmp_path):
    session = _session()
    project_id = annotation_project_id_for_session(session, tmp_path)
    store_path = tmp_path / project_id / "production_context.json"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps({
        "version": 1,
        "state": {
            "lane": "mix",
            "section_scope": "custom",
            "section_label": "Bars 5-9",
            "section_start_bar": 5,
            "section_end_bar": 9,
        },
        "last_updated_ms": 123,
    }))

    state = ProductionContextStore(project_id, base_dir=tmp_path).get_state()

    assert state["lane"] == "mix"
    assert state["section"] == {
        "section_id": "manual_16000_bars_5_9",
        "label": "Bars 5-9",
        "start_beat": 16.0,
        "end_beat": 32.0,
        "source": "manual",
    }
    assert json.loads(store_path.read_text())["version"] == 1


def test_v1_section_scope_migration_uses_session_meter(tmp_path):
    session = _session_3_4()
    project_id = annotation_project_id_for_session(session, tmp_path)
    store_path = tmp_path / project_id / "production_context.json"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps({
        "version": 1,
        "state": {
            "lane": "mix",
            "section_scope": "custom",
            "section_label": "Bars 5-9",
            "section_start_bar": 5,
            "section_end_bar": 9,
        },
        "last_updated_ms": 123,
    }))

    state = ProductionContextService(base_dir=tmp_path).get_state(session)["state"]

    assert state["lane"] == "mix"
    assert state["section"] == {
        "section_id": "manual_12000_bars_5_9",
        "label": "Bars 5-9",
        "start_beat": 12.0,
        "end_beat": 24.0,
        "source": "manual",
    }

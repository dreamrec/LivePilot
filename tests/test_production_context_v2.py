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


def test_working_thread_and_evidence_budget_round_trip_and_clear_semantics(tmp_path):
    service = ProductionContextService(base_dir=tmp_path)
    session = _session()
    saved = service.save_state(
        session,
        lane="mix",
        evidence_budget="deep",
        working_thread={
            "thread_id": "019f2903-7fd2-79b3-9ae0-e46a767c326d",
            "label": "Verse work",
            "pinned_at_ms": 123,
            "last_used_ms": 456,
        },
    )

    assert saved["state"]["evidence_budget"] == "deep"
    assert saved["state"]["working_thread"] == {
        "thread_id": "019f2903-7fd2-79b3-9ae0-e46a767c326d",
        "label": "Verse work",
        "pinned_at_ms": 123,
        "last_used_ms": 456,
    }

    cleared = service.clear_state(session)

    assert cleared["state"]["lane"] == "holistic"
    assert cleared["state"]["evidence_budget"] == "standard"
    assert cleared["state"]["working_thread"]["thread_id"] == (
        "019f2903-7fd2-79b3-9ae0-e46a767c326d"
    )

    removed = service.save_state(session, working_thread={})
    assert removed["state"]["working_thread"] is None


def test_evidence_budget_rejects_unknown_value(tmp_path):
    service = ProductionContextService(base_dir=tmp_path)

    try:
        service.save_state(_session(), evidence_budget="expensive")
    except ValueError as exc:
        assert "evidence_budget must be one of" in str(exc)
    else:
        raise AssertionError("expected evidence_budget validation error")


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

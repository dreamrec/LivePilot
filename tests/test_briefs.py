from __future__ import annotations

from types import SimpleNamespace

from mcp_server.persistence.agent_focus import AgentFocusService
from mcp_server.persistence.briefs import BriefService
from mcp_server.persistence.layer_groups import LayerGroupService
from mcp_server.persistence.orchestration_queue import OrchestrationService
from mcp_server.persistence.production_context import ProductionContextService
from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.production_cockpit import (
    get_production_context,
    list_cockpit_briefs,
    save_cockpit_layer_group,
    save_production_context,
    send_cockpit_brief,
)


def _track(index: int, name: str) -> dict:
    return {
        "index": index,
        "name": name,
        "color_index": index + 1,
        "has_audio_input": True,
        "has_midi_input": False,
    }


def _session(tracks: list[dict]) -> dict:
    return {
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 64.0,
        "project_identity": {"file_path": "/tmp/brief-test.als"},
        "track_count": len(tracks),
        "tracks": tracks,
        "return_tracks": [],
        "scenes": [],
    }


class _Ableton:
    def __init__(self, session_info: dict):
        self.session_info = session_info

    def send_command(self, command, params=None):
        if command == "get_session_info":
            return self.session_info
        if command == "get_cue_points":
            return {"cue_points": []}
        if command == "get_track_info":
            track_index = int(params["track_index"])
            track = next(
                item for item in self.session_info["tracks"]
                if item["index"] == track_index
            )
            return {
                "index": track_index,
                "name": track["name"],
                "devices": [],
                "clips": [],
            }
        raise AssertionError(f"Unexpected command: {command}")


def _ctx(tmp_path, session_info: dict):
    return SimpleNamespace(
        lifespan_context={
            "ableton": _Ableton(session_info),
            "agent_focus": AgentFocusService(base_dir=tmp_path),
            "briefs": BriefService(base_dir=tmp_path),
            "layer_groups": LayerGroupService(base_dir=tmp_path),
            "orchestration_queue": OrchestrationService(base_dir=tmp_path),
            "production_context": ProductionContextService(base_dir=tmp_path),
            "focus_panel_url": "http://127.0.0.1:9890/",
        }
    )


def test_send_brief_creates_linked_ledger_record_without_mutating_notes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(tmp_path, _session([_track(0, "el-guit-intro")]))
    save_production_context(
        ctx,
        target_mode="query",
        target_query="el-guit-intro",
        notes="Long-lived project note.",
    )

    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        request_text="make it pop out more",
        target_mode="query",
        target_query="el-guit-intro",
    )

    brief = context["orchestration_submission"]["brief"]
    task = context["orchestration_submission"]["task"]
    snapshot = context["orchestration_submission"]["snapshot"]

    assert brief["request_text"] == "make it pop out more"
    assert brief["snapshot_id"] == snapshot["snapshot_id"]
    assert brief["task_id"] == task["task_id"]
    assert task["constraints"]["brief_id"] == brief["brief_id"]
    assert task["scope"]["brief_id"] == brief["brief_id"]
    assert get_production_context(ctx)["production_context"]["state"]["notes"] == (
        "Long-lived project note."
    )


def test_brief_status_and_seen_stamp_progress_from_queue_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            _track(0, "el-guit-intro"),
            _track(1, "violins1-intro"),
        ]),
    )
    save_cockpit_layer_group(
        ctx,
        label="Intro Handoff",
        track_indices=[0, 1],
    )
    save_production_context(
        ctx,
        target_mode="layer",
        target_layer="intro_handoff",
        target_query="Intro Handoff",
    )

    sent = send_cockpit_brief(
        ctx,
        lane="sound_design",
        workflow_mode="audition",
        audition_required=True,
        audition_count=2,
        audition_scope="layer",
        request_text="make the handoff shimmer",
        target_mode="layer",
        target_layer="intro_handoff",
        target_query="Intro Handoff",
    )
    brief_id = sent["orchestration_submission"]["brief"]["brief_id"]
    job_id = sent["orchestration_submission"]["job"]["job_id"]

    raw = ctx.lifespan_context["briefs"].store_for_session(
        ctx.lifespan_context["ableton"].session_info
    ).list_briefs()[0]
    assert raw["seen_at_ms"] is None

    listed = list_cockpit_briefs(ctx)
    brief = listed["briefs"][0]
    assert brief["brief_id"] == brief_id
    assert brief["status"] == "queued"
    assert brief["seen_at_ms"] is not None
    assert brief["job_ids"] == [job_id]
    assert brief["related_job_count"] == 1

    store = ctx.lifespan_context["orchestration_queue"].store_for_session(
        ctx.lifespan_context["ableton"].session_info
    )
    store.update_job_status(job_id, "running")
    assert list_cockpit_briefs(ctx)["briefs"][0]["status"] == "running"

    store.update_job_status(job_id, "done")
    assert list_cockpit_briefs(ctx)["briefs"][0]["status"] == "done"


def test_brief_sequence_is_monotonic(tmp_path):
    service = BriefService(base_dir=tmp_path)
    session = _session([_track(0, "drums")])

    first = service.create_brief(
        session,
        request_text="first",
        context_digest={},
    )["brief"]
    second = service.create_brief(
        session,
        request_text="second",
        context_digest={},
    )["brief"]

    assert first["seq"] == 1
    assert second["seq"] == 2
    assert first["thread_id"] == first["brief_id"]
    assert second["parent_brief_id"] is None


def test_brief_dispatch_stamp_is_optional_and_round_trips(tmp_path):
    service = BriefService(base_dir=tmp_path)
    session = _session([_track(0, "drums")])

    created = service.create_brief(
        session,
        request_text="make this pop",
        context_digest={},
    )["brief"]

    assert "dispatch" not in created
    listed = service.list_briefs(session)["briefs"][0]
    assert "dispatch" not in listed

    dispatched = service.record_dispatch(
        session,
        created["brief_id"],
        method="copy_prompt",
    )["brief"]

    assert dispatched["dispatch"]["method"] == "copy_prompt"
    assert isinstance(dispatched["dispatch"]["at_ms"], int)
    listed = service.list_briefs(session)["briefs"][0]
    assert listed["dispatch"]["method"] == "copy_prompt"

    existing = service.record_dispatch(
        session,
        created["brief_id"],
        method="deeplink_existing",
        codex_thread_id="019f2903-7fd2-79b3-9ae0-e46a767c326d",
    )["brief"]

    assert existing["dispatch"]["method"] == "deeplink_existing"
    assert existing["dispatch"]["codex_thread_id"] == (
        "019f2903-7fd2-79b3-9ae0-e46a767c326d"
    )


def test_capture_dispatch_thread_id_preserves_dispatch_stamp(tmp_path):
    service = BriefService(base_dir=tmp_path)
    session = _session([_track(0, "drums")])
    created = service.create_brief(
        session,
        request_text="make this pop",
        context_digest={},
    )["brief"]
    dispatched = service.record_dispatch(
        session,
        created["brief_id"],
        method="deeplink",
    )["brief"]
    at_ms = dispatched["dispatch"]["at_ms"]

    captured = service.capture_dispatch_thread_id(
        session,
        created["brief_id"],
        codex_thread_id="019f2903-7fd2-79b3-9ae0-e46a767c326d",
    )["brief"]

    assert captured["dispatch"] == {
        "method": "deeplink",
        "at_ms": at_ms,
        "codex_thread_id": "019f2903-7fd2-79b3-9ae0-e46a767c326d",
    }

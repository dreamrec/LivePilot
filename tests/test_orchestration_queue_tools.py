from __future__ import annotations

from types import SimpleNamespace

from mcp_server.orchestration_queue_tools import (
    cancel_ableton_job,
    create_orchestration_snapshot,
    get_orchestration_state,
    list_ableton_jobs,
    list_agent_proposals,
    list_agent_tasks,
    submit_ableton_job,
    submit_agent_proposal,
    submit_agent_task,
)
from mcp_server.persistence.orchestration_queue import OrchestrationService


def _session() -> dict:
    return {
        "project_identity": {"file_path": "/Users/me/Song.als"},
        "tempo": 116.0,
        "tracks": [
            {"index": 0, "name": "Drums"},
            {"index": 1, "name": "Guitar"},
        ],
        "return_tracks": [],
        "scenes": [],
    }


class _Ableton:
    def __init__(self):
        self.session_info = _session()

    def send_command(self, command, params=None):
        if command == "get_session_info":
            return self.session_info
        raise AssertionError(f"Unexpected command: {command} {params}")


def _ctx(tmp_path):
    return SimpleNamespace(
        lifespan_context={
            "ableton": _Ableton(),
            "orchestration_queue": OrchestrationService(base_dir=tmp_path),
        }
    )


def test_orchestration_mcp_flow_round_trips(tmp_path, monkeypatch):
    import mcp_server.orchestration_queue_tools as tools

    monkeypatch.setattr(
        tools,
        "_build_production_context",
        lambda ctx, request_text: {
            "summary": {
                "target_mode": "layer",
                "target_layer": "intro_handoff",
                "audition_count": 3,
            },
            "section_map": [{"id": "intro", "start_bar": 1, "end_bar": 9}],
            "layer_groups": [{"id": "intro_handoff", "track_indices": [1]}],
            "track_intent_map": {"tracks": [{"index": 1, "role": "guitar"}]},
        },
    )
    monkeypatch.setattr(
        tools,
        "_build_session_kernel",
        lambda ctx, request_text, mode: {
            "kernel_id": "kern_1",
            "request_text": request_text,
            "mode": mode,
        },
    )

    ctx = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(
        ctx,
        request_text="make the guitar pop out",
        mode="audition",
    )["snapshot"]
    assert snapshot["brief"]["text"] == "make the guitar pop out"
    assert snapshot["brief"]["target_layer"] == "intro_handoff"
    assert snapshot["session_kernel"]["kernel_id"] == "kern_1"

    task = submit_agent_task(
        ctx,
        snapshot_id=snapshot["snapshot_id"],
        agent_role="sound_design",
        instruction="Propose variants.",
        scope={"track_indices": [1], "layer_id": "intro_handoff"},
    )["task"]
    assert list_agent_tasks(ctx)["task_count"] == 1
    assert list_agent_tasks(ctx, status="queued")["tasks"][0]["task_id"] == task["task_id"]

    proposal = submit_agent_proposal(
        ctx,
        task_id=task["task_id"],
        agent_role="sound_design",
        summary="Create three visible auditions.",
        confidence=0.7,
        risk="low",
        write_set=["track:1:devices"],
        suggested_jobs=[{"job_type": "mutation", "title": "Create auditions"}],
    )["proposal"]
    assert proposal["snapshot_id"] == snapshot["snapshot_id"]
    assert list_agent_proposals(ctx)["proposal_count"] == 1

    low = submit_ableton_job(ctx, job_type="mutation", title="Low", priority=10)["job"]
    high = submit_ableton_job(ctx, job_type="mutation", title="High", priority=90)["job"]
    jobs = list_ableton_jobs(ctx, status="queued")["jobs"]
    assert [job["job_id"] for job in jobs] == [high["job_id"], low["job_id"]]

    canceled = cancel_ableton_job(ctx, low["job_id"], reason="Not needed")["job"]
    assert canceled["status"] == "canceled"
    assert canceled["result"]["reason"] == "Not needed"

    state = get_orchestration_state(ctx)
    assert state["project_revision"] == 0
    assert state["task_count"] == 1
    assert state["proposal_count"] == 1
    assert state["job_count"] == 2
    assert state["next_queued_job"]["job_id"] == high["job_id"]

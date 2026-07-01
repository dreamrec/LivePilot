from __future__ import annotations

import asyncio
from types import SimpleNamespace

from mcp_server.orchestration_queue_tools import (
    cancel_ableton_job,
    create_orchestration_snapshot,
    get_orchestration_state,
    list_ableton_jobs,
    list_agent_proposals,
    list_agent_tasks,
    run_next_ableton_job,
    submit_ableton_job,
    submit_agent_proposal,
    submit_agent_task,
)
from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.persistence.orchestration_queue import OrchestrationService
from mcp_server.runtime.mcp_dispatch import build_mcp_dispatch_registry


def _session() -> dict:
    return {
        "project_identity": {"file_path": "/Users/me/Song.als"},
        "tempo": 116.0,
        "track_count": 2,
        "tracks": [
            {"index": 0, "name": "Drums"},
            {"index": 1, "name": "Guitar"},
        ],
        "return_tracks": [],
        "scenes": [],
    }


class _Ableton:
    def __init__(self, fail_on=None):
        self.session_info = _session()
        self.fail_on = set(fail_on or [])
        self.calls = []

    def send_command(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command in self.fail_on:
            raise RuntimeError(f"Fake failure on {command}")
        if command == "get_session_info":
            return self.session_info
        if command == "duplicate_track":
            track_index = int(params["track_index"])
            original = dict(self.session_info["tracks"][track_index])
            duplicate = dict(original)
            duplicate["name"] = f"{original.get('name', 'Track')} Copy"
            self.session_info["tracks"].insert(track_index + 1, duplicate)
            for index, track in enumerate(self.session_info["tracks"]):
                track["index"] = index
            self.session_info["track_count"] = len(self.session_info["tracks"])
            return {
                "index": track_index + 1,
                "name": duplicate["name"],
            }
        if command == "set_track_name":
            track = self.session_info["tracks"][int(params["track_index"])]
            track["name"] = params["name"]
            return {"index": track["index"], "name": track["name"]}
        if command == "set_track_mute":
            track = self.session_info["tracks"][int(params["track_index"])]
            track["mute"] = bool(params["mute"])
            return {"index": track["index"], "mute": track["mute"]}
        if command == "get_track_info":
            track = self.session_info["tracks"][int(params["track_index"])]
            return {
                "index": track["index"],
                "name": track["name"],
                "devices": [],
                "clips": [],
            }
        if command in {"set_track_volume", "set_track_pan"}:
            return {"ok": True, "command": command, "params": params}
        raise AssertionError(f"Unexpected command: {command} {params}")


def _ctx(tmp_path, fail_on=None):
    ableton = _Ableton(fail_on=fail_on)
    return SimpleNamespace(
        lifespan_context={
            "ableton": ableton,
            "orchestration_queue": OrchestrationService(base_dir=tmp_path),
            "mcp_dispatch": {},
        }
    ), ableton


def _patch_snapshot_builders(monkeypatch):
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


def test_orchestration_mcp_flow_round_trips(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, _ableton = _ctx(tmp_path)
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


def test_submit_audition_job_generates_visible_layer_plan(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, _ableton = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(
        ctx,
        request_text="make auditions",
        mode="audition",
    )["snapshot"]

    job = submit_ableton_job(
        ctx,
        job_type="audition",
        snapshot_id=snapshot["snapshot_id"],
        scope={
            "layer_id": "intro_handoff",
            "audition_count": 2,
            "variant_labels": ["edge sat", "wide tucked"],
        },
    )["job"]

    assert job["title"] == "Create 2 visible Intro Handoff auditions"
    assert job["requires_write"] is True
    assert job["requires_transport"] is False
    assert job["scope"]["source_track_indices"] == [1]
    assert job["audition_manifest"]["variant_count"] == 2
    assert job["write_set"] == ["track:1", "layer:intro_handoff", "project"]
    assert [step["tool"] for step in job["plan"]] == [
        "duplicate_track",
        "set_track_name",
        "set_track_mute",
        "set_track_annotation",
        "duplicate_track",
        "set_track_name",
        "set_track_mute",
        "set_track_annotation",
    ]
    assert job["plan"][1]["params"] == {
        "track_index": {"$from_step": "aud_a_src_1_duplicate", "path": "index"},
        "name": "AUD A Guitar edge sat",
    }
    assert job["plan"][2]["params"]["mute"] is True
    assert job["plan"][3]["backend"] == "mcp_tool"
    assert job["plan"][3]["params"]["role"] == "audition_variant"
    assert "variant:A" in job["plan"][3]["params"]["tags"]


def test_run_generated_audition_job_creates_muted_annotated_lane(
    tmp_path,
    monkeypatch,
):
    _patch_snapshot_builders(monkeypatch)
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx, ableton = _ctx(tmp_path)
    ctx.lifespan_context["mcp_dispatch"] = build_mcp_dispatch_registry()
    snapshot = create_orchestration_snapshot(
        ctx,
        request_text="make one audition",
        mode="audition",
    )["snapshot"]
    job = submit_ableton_job(
        ctx,
        job_type="audition",
        snapshot_id=snapshot["snapshot_id"],
        scope={"layer_id": "intro_handoff", "audition_count": 1},
    )["job"]

    result = asyncio.run(run_next_ableton_job(ctx, job_id=job["job_id"]))

    assert result["status"] == "done"
    assert result["job"]["result"]["project_revision"] == 1
    assert ("duplicate_track", {"track_index": 1}) in ableton.calls
    assert (
        "set_track_name",
        {"track_index": 2, "name": "AUD A Guitar lift"},
    ) in ableton.calls
    assert (
        "set_track_mute",
        {"track_index": 2, "mute": True},
    ) in ableton.calls
    assert ableton.session_info["tracks"][2]["name"] == "AUD A Guitar lift"
    assert ableton.session_info["tracks"][2]["mute"] is True

    from mcp_server.tools.tracks import get_track_annotations

    annotations = get_track_annotations(ctx)["annotations"]
    assert len(annotations) == 1
    assert annotations[0]["role"] == "audition_variant"
    assert annotations[0]["decision_state"] == "open"
    assert "layer:intro_handoff" in annotations[0]["tags"]


def test_run_next_ableton_job_executes_plan_and_increments_revision(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, ableton = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(ctx, request_text="apply it")["snapshot"]
    job = submit_ableton_job(
        ctx,
        job_type="mutation",
        snapshot_id=snapshot["snapshot_id"],
        write_set=["track:1:volume"],
        plan=[
            {
                "tool": "set_track_volume",
                "params": {"track_index": 1, "volume": 0.5},
            },
        ],
    )["job"]

    result = asyncio.run(run_next_ableton_job(ctx, job_id=job["job_id"]))

    assert result["status"] == "done"
    assert result["job"]["status"] == "done"
    assert result["job"]["result"]["project_revision"] == 1
    assert ("set_track_volume", {"track_index": 1, "volume": 0.5}) in ableton.calls
    state = get_orchestration_state(ctx)
    assert state["project_revision"] == 1
    assert state["leases"] == []


def test_run_next_ableton_job_blocks_stale_snapshot(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, _ableton = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(ctx, request_text="old idea")["snapshot"]
    store = ctx.lifespan_context["orchestration_queue"].store_for_session(_session())
    store.increment_revision(reason="manual_edit")
    job = submit_ableton_job(
        ctx,
        job_type="mutation",
        snapshot_id=snapshot["snapshot_id"],
        plan=[
            {
                "tool": "set_track_volume",
                "params": {"track_index": 1, "volume": 0.5},
            },
        ],
    )["job"]

    result = asyncio.run(run_next_ableton_job(ctx, job_id=job["job_id"]))

    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "stale_snapshot"
    assert result["job"]["status"] == "awaiting_decision"


def test_run_next_ableton_job_blocks_resource_conflict(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, _ableton = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(ctx, request_text="conflict")["snapshot"]
    store = ctx.lifespan_context["orchestration_queue"].store_for_session(_session())
    first = submit_ableton_job(
        ctx,
        job_type="mutation",
        snapshot_id=snapshot["snapshot_id"],
        write_set=["track:1:volume"],
        plan=[
            {
                "tool": "set_track_volume",
                "params": {"track_index": 1, "volume": 0.5},
            },
        ],
    )["job"]
    second = submit_ableton_job(
        ctx,
        job_type="mutation",
        snapshot_id=snapshot["snapshot_id"],
        write_set=["track:1:pan"],
        plan=[
            {
                "tool": "set_track_pan",
                "params": {"track_index": 1, "pan": 0.1},
            },
        ],
    )["job"]
    assert store.claim_resources_for_job(first["job_id"])["status"] == "claimed"

    result = asyncio.run(run_next_ableton_job(ctx, job_id=second["job_id"]))

    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "resource_conflict"
    assert result["conflicts"][0]["requested"] == "track:1"
    assert store.get_job(second["job_id"])["status"] == "queued"


def test_run_next_ableton_job_marks_failed_and_releases_leases(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, _ableton = _ctx(tmp_path, fail_on={"set_track_pan"})
    snapshot = create_orchestration_snapshot(ctx, request_text="bad move")["snapshot"]
    job = submit_ableton_job(
        ctx,
        job_type="mutation",
        snapshot_id=snapshot["snapshot_id"],
        write_set=["track:1:pan"],
        plan=[
            {
                "tool": "set_track_volume",
                "params": {"track_index": 1, "volume": 0.5},
            },
            {
                "tool": "set_track_pan",
                "params": {"track_index": 1, "pan": 0.1},
            },
        ],
    )["job"]

    result = asyncio.run(run_next_ableton_job(ctx, job_id=job["job_id"]))

    assert result["status"] == "failed"
    assert result["job"]["status"] == "failed"
    assert "Fake failure on set_track_pan" in result["error"]
    state = get_orchestration_state(ctx)
    assert state["project_revision"] == 0
    assert state["leases"] == []

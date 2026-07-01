from __future__ import annotations

import pytest

from mcp_server.persistence.orchestration_queue import (
    OrchestrationService,
    OrchestrationStore,
)


def _session(path: str = "/Users/me/Song.als") -> dict:
    return {
        "project_identity": {"file_path": path},
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 72.0,
        "tracks": [
            {"index": 0, "name": "Drums", "color_index": 1},
            {"index": 1, "name": "Guitar", "color_index": 2},
        ],
        "return_tracks": [],
        "scenes": [],
    }


def test_orchestration_service_creates_project_scoped_snapshot(tmp_path):
    service = OrchestrationService(base_dir=tmp_path)
    result = service.create_snapshot(
        _session(),
        brief={
            "text": "make the intro handoff guitar pop out",
            "target_layer": "intro_handoff",
            "audition_count": 3,
        },
        session_kernel={"kernel_id": "kern_1"},
        cockpit_context={"target_mode": "layer"},
        section_map=[{"id": "intro", "start_bar": 1, "end_bar": 9}],
        layer_groups=[{"id": "intro_handoff", "track_indices": [1]}],
        track_intent_map={"tracks": [{"index": 1, "role": "guitar"}]},
    )

    snapshot = result["snapshot"]
    assert result["status"] == "ok"
    assert snapshot["project_id"] == result["project_id"]
    assert snapshot["project_revision"] == 0
    assert snapshot["brief"]["audition_count"] == 3
    assert snapshot["session_kernel"]["kernel_id"] == "kern_1"
    assert snapshot["section_map"][0]["id"] == "intro"

    state = service.get_state(_session())["state"]
    assert state["snapshots"][0]["snapshot_id"] == snapshot["snapshot_id"]

    other = service.get_state(_session("/Users/me/Song B.als"))["state"]
    assert other["snapshots"] == []


def test_orchestration_store_persists_core_objects(tmp_path):
    store = OrchestrationStore("proj1", base_dir=tmp_path)
    snapshot = store.save_snapshot({
        "snapshot_id": "snap_1",
        "project_revision": 0,
        "brief": {"text": "try variants"},
    })
    task = store.save_task({
        "task_id": "task_1",
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "sound_design",
        "instruction": "Propose three variants.",
    })
    proposal = store.save_proposal({
        "proposal_id": "prop_1",
        "task_id": task["task_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "sound_design",
        "summary": "Create three AUD lanes.",
        "risk": "low",
        "write_set": ["track:1:devices"],
    })
    job = store.save_job({
        "job_id": "job_1",
        "snapshot_id": snapshot["snapshot_id"],
        "job_type": "mutation",
        "priority": 80,
        "requires_write": True,
        "write_set": ["track:1:devices"],
        "plan": [{"tool": "duplicate_track", "args": {"track_index": 1}}],
    })
    lease = store.save_lease({
        "lease_id": "lease_1",
        "resource": "track:1",
        "job_id": job["job_id"],
    })

    reopened = OrchestrationStore("proj1", base_dir=tmp_path)
    assert reopened.get_snapshot("snap_1")["brief"]["text"] == "try variants"
    assert reopened.list_tasks()[0]["task_id"] == "task_1"
    assert reopened.list_proposals()[0]["proposal_id"] == proposal["proposal_id"]
    assert reopened.list_jobs()[0]["job_id"] == "job_1"
    assert reopened.list_leases()[0]["lease_id"] == lease["lease_id"]


def test_revision_increment_marks_active_proposals_stale(tmp_path):
    store = OrchestrationStore("proj1", base_dir=tmp_path)
    snapshot = store.save_snapshot({
        "snapshot_id": "snap_1",
        "project_revision": 0,
    })
    active = store.save_proposal({
        "proposal_id": "prop_active",
        "snapshot_id": snapshot["snapshot_id"],
        "summary": "Still pending.",
    })
    rejected = store.save_proposal({
        "proposal_id": "prop_rejected",
        "snapshot_id": snapshot["snapshot_id"],
        "summary": "Already rejected.",
        "status": "rejected",
    })

    state = store.increment_revision(reason="mutation_done", source_id="job_1")

    assert state["project_revision"] == 1
    assert state["revision_history"][-1]["reason"] == "mutation_done"
    proposals = {
        item["proposal_id"]: item for item in state["proposals"]
    }
    assert proposals[active["proposal_id"]]["status"] == "stale_needs_revalidation"
    assert proposals[active["proposal_id"]]["stale_since_revision"] == 1
    assert proposals[rejected["proposal_id"]]["status"] == "rejected"


def test_queued_jobs_are_ordered_by_priority_then_fifo(tmp_path):
    store = OrchestrationStore("proj1", base_dir=tmp_path)
    low = store.save_job({"job_id": "job_low", "priority": 10})
    high_first = store.save_job({"job_id": "job_high_a", "priority": 90})
    high_second = store.save_job({"job_id": "job_high_b", "priority": 90})

    assert [job["job_id"] for job in store.list_jobs(status="queued", ordered=True)] == [
        high_first["job_id"],
        high_second["job_id"],
        low["job_id"],
    ]
    assert store.next_queued_job()["job_id"] == high_first["job_id"]

    updated = store.update_job_status(high_first["job_id"], "done",
                                      result={"verified": True})
    assert updated["result"]["verified"] is True
    assert store.next_queued_job()["job_id"] == high_second["job_id"]


def test_status_updates_preserve_created_at(tmp_path):
    store = OrchestrationStore("proj1", base_dir=tmp_path)
    task = store.save_task({"task_id": "task_1"})
    proposal = store.save_proposal({"proposal_id": "prop_1"})
    job = store.save_job({"job_id": "job_1"})

    assert store.update_task_status("task_1", "running")["created_at_ms"] == task["created_at_ms"]
    assert store.update_proposal_status("prop_1", "approved")["created_at_ms"] == proposal["created_at_ms"]
    assert store.update_job_status("job_1", "running")["created_at_ms"] == job["created_at_ms"]


def test_orchestration_store_rejects_invalid_values(tmp_path):
    store = OrchestrationStore("proj1", base_dir=tmp_path)

    with pytest.raises(ValueError, match="job_type must be one of"):
        store.save_job({"job_type": "telepathy"})

    with pytest.raises(ValueError, match="task status must be one of"):
        store.save_task({"status": "thinking_about_it"})

    with pytest.raises(ValueError, match="proposal status must be one of"):
        store.save_proposal({"status": "maybe"})

    with pytest.raises(ValueError, match="lease resource cannot be empty"):
        store.save_lease({"resource": ""})

    with pytest.raises(KeyError, match="job_id not found"):
        store.update_job_status("missing", "done")

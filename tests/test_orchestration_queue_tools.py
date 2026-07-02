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
    submit_audition_action_job,
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
        "is_playing": False,
        "current_song_time": 0.0,
        "loop": False,
        "loop_start": 0.0,
        "loop_length": 4.0,
        "arrangement_override": False,
        "track_count": 2,
        "tracks": [
            {"index": 0, "name": "Drums", "mute": False, "solo": False},
            {"index": 1, "name": "Guitar", "mute": False, "solo": False},
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
        if command == "force_arrangement":
            self.session_info["arrangement_override"] = False
            self.session_info["current_song_time"] = float(params.get("beat_time", 0.0))
            if "loop_length" in params:
                self.session_info["loop"] = True
                self.session_info["loop_start"] = float(params.get("loop_start", 0.0))
                self.session_info["loop_length"] = float(params["loop_length"])
            self.session_info["is_playing"] = bool(params.get("play", True))
            return {
                "arrangement_active": True,
                "position": self.session_info["current_song_time"],
                "loop": self.session_info["loop"],
                "is_playing": self.session_info["is_playing"],
            }
        if command == "back_to_arranger":
            self.session_info["arrangement_override"] = False
            return {"back_to_arranger": False}
        if command == "set_session_loop":
            self.session_info["loop"] = bool(params["enabled"])
            if "loop_start" in params:
                self.session_info["loop_start"] = float(params["loop_start"])
            if "loop_length" in params:
                self.session_info["loop_length"] = float(params["loop_length"])
            return {
                "loop": self.session_info["loop"],
                "loop_start": self.session_info["loop_start"],
                "loop_length": self.session_info["loop_length"],
            }
        if command == "jump_to_time":
            self.session_info["current_song_time"] = float(params["beat_time"])
            return {"current_song_time": self.session_info["current_song_time"]}
        if command == "continue_playback":
            self.session_info["is_playing"] = True
            return {"is_playing": True}
        if command == "start_playback":
            self.session_info["is_playing"] = True
            return {"is_playing": True}
        if command == "stop_playback":
            self.session_info["is_playing"] = False
            return {"is_playing": False}
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
        if command == "delete_track":
            track_index = int(params["track_index"])
            self.session_info["tracks"].pop(track_index)
            for index, track in enumerate(self.session_info["tracks"]):
                track["index"] = index
            self.session_info["track_count"] = len(self.session_info["tracks"])
            return {"deleted_index": track_index}
        if command == "set_track_solo":
            track = self.session_info["tracks"][int(params["track_index"])]
            track["solo"] = bool(params["solo"])
            return {"index": track["index"], "solo": track["solo"]}
        if command == "get_track_meters":
            return {
                "track_index": int(params["track_index"]),
                "left": 0.1,
                "right": 0.1,
            }
        if command == "get_master_meters":
            return {"left": 0.2, "right": 0.2}
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
        "get_track_meters",
        "get_master_meters",
    ]
    assert job["plan"][1]["params"] == {
        "track_index": {"$from_step": "aud_a_src_1_duplicate", "path": "index"},
        "name": "AUD A Guitar edge sat",
    }
    assert job["plan"][2]["params"]["mute"] is True
    assert job["plan"][3]["backend"] == "mcp_tool"
    assert job["plan"][3]["params"]["role"] == "audition_variant"
    assert "variant:A" in job["plan"][3]["params"]["tags"]
    assert job["plan"][-2]["summary"].startswith("Audibility verification")


def test_submit_audition_job_generates_visible_track_plan(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, _ableton = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(
        ctx,
        request_text="make track auditions",
        mode="audition",
    )["snapshot"]

    job = submit_ableton_job(
        ctx,
        job_type="audition",
        snapshot_id=snapshot["snapshot_id"],
        scope={
            "target_label": "Guitar",
            "track_indices": [1],
            "audition_count": 2,
            "variant_labels": ["edge sat", "wide tucked"],
        },
    )["job"]

    assert job["title"] == "Create 2 visible Guitar auditions"
    assert job["scope"]["target_mode"] == "track"
    assert job["scope"]["source_track_indices"] == [1]
    assert job["audition_manifest"]["scope_type"] == "track"
    assert job["audition_manifest"]["layer_id"] == ""
    assert job["write_set"] == ["track:1", "project"]
    assert "layer:intro_handoff" not in job["plan"][3]["params"]["tags"]
    assert job["audition_manifest"]["tracks"][0]["expected_track_name"] == (
        "AUD A Guitar edge sat"
    )


def test_audition_action_jobs_reference_manifest_tracks(tmp_path, monkeypatch):
    _patch_snapshot_builders(monkeypatch)
    ctx, ableton = _ctx(tmp_path)
    snapshot = create_orchestration_snapshot(
        ctx,
        request_text="make auditions",
        mode="audition",
    )["snapshot"]
    source_job = submit_ableton_job(
        ctx,
        job_type="audition",
        snapshot_id=snapshot["snapshot_id"],
        scope={
            "target_label": "Guitar",
            "track_indices": [1],
            "audition_count": 2,
            "variant_labels": ["edge sat", "wide tucked"],
        },
    )["job"]
    ableton.session_info["tracks"].append({
        "index": 2,
        "name": "AUD A Guitar edge sat",
        "mute": True,
        "solo": False,
    })
    ableton.session_info["tracks"].append({
        "index": 3,
        "name": "AUD B Guitar wide tucked",
        "mute": True,
        "solo": False,
    })
    ableton.session_info["track_count"] = 4

    play = submit_audition_action_job(
        ctx,
        source_job_id=source_job["job_id"],
        action="play",
        variant_letter="A",
    )["job"]
    promote = submit_audition_action_job(
        ctx,
        source_job_id=source_job["job_id"],
        action="promote",
        variant_letter="A",
    )["job"]
    discard = submit_audition_action_job(
        ctx,
        source_job_id=source_job["job_id"],
        action="discard",
        variant_letter="B",
    )["job"]

    assert play["job_type"] == "playback_analysis"
    assert play["requires_transport"] is True
    assert play["scope"]["track_names"] == ["AUD A Guitar edge sat"]
    assert [step["tool"] for step in play["plan"]] == [
        "set_track_mute",
        "set_track_solo",
    ]

    assert promote["job_type"] == "mutation"
    assert promote["scope"]["track_names"] == ["AUD A Guitar edge sat"]
    assert promote["scope"]["loser_expected_track_names"] == [
        "AUD B Guitar wide tucked",
    ]
    assert "set_track_annotation" in [step["tool"] for step in promote["plan"]]

    assert discard["job_type"] == "mutation"
    assert discard["scope"]["track_names"] == ["AUD B Guitar wide tucked"]
    assert discard["plan"][0]["tool"] == "delete_track"
    assert discard["plan"][0]["params"]["track_index"] == 3


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
    from mcp_server.session_continuity import tracker

    tracker.reset_story()
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
    logging = result["job"]["result"]["logging"]
    assert logging["status"] == "ok"
    assert logging["ledger_entry_id"]
    assert logging["session_memory_id"]
    assert logging["turn_id"]
    assert ("set_track_volume", {"track_index": 1, "volume": 0.5}) in ableton.calls
    state = get_orchestration_state(ctx)
    assert state["project_revision"] == 1
    assert state["leases"] == []
    ledger_entry = ctx.lifespan_context["action_ledger"].get_last_move()
    assert ledger_entry.engine == "orchestration"
    assert ledger_entry.move_class == "mutation"
    assert ledger_entry.kept is True
    assert ledger_entry.actions[0]["tool"] == "set_track_volume"
    memory = ctx.lifespan_context["session_memory"].get_recent(
        category="move_executed",
    )
    assert "done mutation job" in memory[0].content
    story = tracker.get_session_story()
    assert story.turns[-1].move_applied == "orchestration:mutation"
    tracker.reset_story()


def test_run_next_playback_job_preflights_and_restores_transport_state(
    tmp_path,
    monkeypatch,
):
    _patch_snapshot_builders(monkeypatch)
    ctx, ableton = _ctx(tmp_path)
    ableton.session_info.update({
        "is_playing": False,
        "current_song_time": 32.0,
        "loop": True,
        "loop_start": 8.0,
        "loop_length": 4.0,
        "arrangement_override": True,
    })
    snapshot = create_orchestration_snapshot(
        ctx,
        request_text="meter the intro",
        mode="audition",
    )["snapshot"]
    job = submit_ableton_job(
        ctx,
        job_type="playback_analysis",
        snapshot_id=snapshot["snapshot_id"],
        requires_transport=True,
        requires_write=False,
        scope={
            "loop_start": 16.0,
            "loop_length": 8.0,
            "play": True,
        },
        plan=[
            {
                "tool": "set_track_solo",
                "params": {"track_index": 1, "solo": True},
            },
        ],
    )["job"]

    result = asyncio.run(run_next_ableton_job(ctx, job_id=job["job_id"]))

    assert result["status"] == "done"
    job_result = result["job"]["result"]
    assert job_result["project_revision"] is None
    assert job_result["preflight"]["captured"]["transport"]["current_song_time"] == 32.0
    assert job_result["preflight"]["prepared"]["action"] == "force_arrangement"
    assert job_result["preflight"]["prepared"]["loop"] == {
        "start": 16.0,
        "length": 8.0,
    }
    assert job_result["restoration"]["status"] == "restored"
    assert ("force_arrangement", {
        "beat_time": 16.0,
        "loop_start": 16.0,
        "loop_length": 8.0,
        "play": True,
    }) in ableton.calls
    assert (
        "set_track_solo",
        {"track_index": 1, "solo": True},
    ) in ableton.calls
    assert (
        "set_session_loop",
        {"enabled": True, "loop_start": 8.0, "loop_length": 4.0},
    ) in ableton.calls
    assert ("jump_to_time", {"beat_time": 32.0}) in ableton.calls
    assert ("stop_playback", {}) in ableton.calls
    assert (
        "set_track_solo",
        {"track_index": 1, "solo": False},
    ) in ableton.calls
    assert ableton.session_info["current_song_time"] == 32.0
    assert ableton.session_info["loop"] is True
    assert ableton.session_info["loop_start"] == 8.0
    assert ableton.session_info["loop_length"] == 4.0
    assert ableton.session_info["is_playing"] is False
    assert ableton.session_info["tracks"][1]["solo"] is False
    assert get_orchestration_state(ctx)["project_revision"] == 0


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
    assert result["job"]["result"]["failed_step"]["tool"] == "set_track_pan"
    assert result["job"]["result"]["changes_applied"] is True
    assert result["job"]["result"]["restoration"]["status"] == "skipped"
    assert "Fix the failed step" in result["job"]["result"]["recommended_recovery"]
    logging = result["job"]["result"]["logging"]
    assert logging["status"] == "ok"
    assert logging["ledger_entry_id"]
    ledger_entry = ctx.lifespan_context["action_ledger"].get_last_move()
    assert ledger_entry.kept is False
    assert ledger_entry.score == 0.5
    issues = ctx.lifespan_context["session_memory"].get_recent(category="issue")
    assert "failed mutation job" in issues[0].content
    assert "Fake failure on set_track_pan" in issues[0].content
    state = get_orchestration_state(ctx)
    assert state["project_revision"] == 0
    assert state["leases"] == []

from __future__ import annotations

from types import SimpleNamespace

from mcp_server.persistence.agent_focus import AgentFocusService
from mcp_server.persistence.briefs import BriefService
from mcp_server.persistence.layer_groups import LayerGroupService
from mcp_server.persistence.orchestration_queue import OrchestrationService
from mcp_server.persistence.production_context import ProductionContextService
from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.production_cockpit import (
    _render_intent_first_cockpit_html,
    cancel_cockpit_queue_job,
    cancel_cockpit_queue_task,
    dismiss_cockpit_queue_proposal,
    get_production_context,
)


def _session(tracks: list[dict]) -> dict:
    return {
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 72.0,
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
        raise AssertionError(f"Unexpected command: {command}")


def _ctx(tmp_path, session_info: dict):
    return SimpleNamespace(
        lifespan_context={
            "ableton": _Ableton(session_info),
            "agent_focus": AgentFocusService(base_dir=tmp_path),
            "briefs": BriefService(base_dir=tmp_path),
            "layer_groups": LayerGroupService(base_dir=tmp_path),
            "production_context": ProductionContextService(base_dir=tmp_path),
            "orchestration_queue": OrchestrationService(base_dir=tmp_path),
            "focus_panel_url": "http://127.0.0.1:9890/",
        }
    )


def test_cockpit_context_includes_orchestration_queue_summary(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    session = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        {"index": 1, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
    ])
    ctx = _ctx(tmp_path, session)
    service = ctx.lifespan_context["orchestration_queue"]
    snapshot = service.create_snapshot(
        session,
        brief={"text": "make the guitar pop out"},
        section_map=[],
        layer_groups=[],
        track_intent_map={},
    )["snapshot"]
    store = service.store_for_session(session)
    store.save_task({
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "mix_critic",
        "instruction": "Analyze guitar audibility.",
        "status": "queued",
    })
    store.save_proposal({
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "sound_designer",
        "summary": "Use edge saturation on the intro guitar.",
        "confidence": 0.77,
        "risk": "low",
        "write_set": ["track:1"],
        "status": "proposed",
    })
    store.save_proposal({
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "mix_critic",
        "summary": "Older balance idea.",
        "confidence": 0.4,
        "risk": "medium",
        "status": "stale_needs_revalidation",
    })
    store.save_job({
        "snapshot_id": snapshot["snapshot_id"],
        "title": "Audition C edge saturation",
        "job_type": "audition",
        "priority": 90,
        "scope": {"track_indices": [1], "layer_id": "intro_handoff"},
        "requires_transport": True,
        "requires_write": True,
        "write_set": ["track:1"],
        "status": "queued",
    })
    store.save_job({
        "snapshot_id": snapshot["snapshot_id"],
        "title": "Playback meter check",
        "job_type": "playback_analysis",
        "priority": 40,
        "requires_transport": True,
        "requires_write": False,
        "status": "running",
    })
    store.save_job({
        "snapshot_id": snapshot["snapshot_id"],
        "title": "Choose guitar audition winner",
        "job_type": "audition",
        "priority": 95,
        "requires_transport": False,
        "requires_write": False,
        "status": "awaiting_decision",
    })

    context = get_production_context(ctx)
    orchestration = context["orchestration"]

    assert orchestration["status"] == "ok"
    assert orchestration["project_id"] == store.project_id
    assert orchestration["project_revision"] == 0
    assert orchestration["counts"]["queued_tasks"] == 1
    assert orchestration["counts"]["queued_jobs"] == 1
    assert orchestration["counts"]["running_jobs"] == 1
    assert orchestration["counts"]["awaiting_decision_jobs"] == 1
    assert orchestration["counts"]["pending_proposals"] == 2
    assert orchestration["counts"]["stale_proposals"] == 1
    assert orchestration["warnings"] == ["stale_proposals_need_revalidation"]
    assert orchestration["active_tasks"][0]["agent_role"] == "mix_critic"
    assert orchestration["next_queued_job"]["title"] == "Audition C edge saturation"
    assert [
        job["title"] for job in orchestration["active_jobs"]
    ] == [
        "Choose guitar audition winner",
        "Audition C edge saturation",
        "Playback meter check",
    ]
    assert [
        proposal["summary"] for proposal in orchestration["pending_proposals"]
    ] == [
        "Use edge saturation on the intro guitar.",
        "Older balance idea.",
    ]


def test_cockpit_queue_actions_cancel_and_dismiss_without_revision_bump(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    session = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
    ])
    ctx = _ctx(tmp_path, session)
    store = ctx.lifespan_context["orchestration_queue"].store_for_session(session)
    snapshot = store.save_snapshot({"brief": {"text": "queue cleanup"}})
    task = store.save_task({
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "mix_critic",
        "instruction": "Check the mix.",
        "status": "queued",
    })
    queued_job = store.save_job({
        "snapshot_id": snapshot["snapshot_id"],
        "title": "Queued audition",
        "job_type": "audition",
        "status": "queued",
    })
    running_job = store.save_job({
        "snapshot_id": snapshot["snapshot_id"],
        "title": "Running playback",
        "job_type": "playback_analysis",
        "status": "running",
    })
    proposal = store.save_proposal({
        "snapshot_id": snapshot["snapshot_id"],
        "agent_role": "sound_designer",
        "summary": "Try brighter saturation.",
        "status": "stale_needs_revalidation",
    })
    before_revision = store.get_revision()

    canceled_task = cancel_cockpit_queue_task(ctx, task["task_id"])
    canceled_job = cancel_cockpit_queue_job(ctx, queued_job["job_id"])
    blocked_running = cancel_cockpit_queue_job(ctx, running_job["job_id"])
    dismissed = dismiss_cockpit_queue_proposal(ctx, proposal["proposal_id"])

    assert store.get_revision() == before_revision
    assert canceled_task["queue_action"]["task"]["status"] == "canceled"
    assert canceled_job["queue_action"]["job"]["status"] == "canceled"
    assert blocked_running["queue_action"]["status"] == "blocked"
    assert blocked_running["queue_action"]["current_status"] == "running"
    assert dismissed["queue_action"]["proposal"]["status"] == "superseded"
    assert dismissed["queue_action"]["proposal"]["status_reason"] == (
        "dismissed from cockpit"
    )


def test_intent_cockpit_renders_orchestration_queue_card():
    html = _render_intent_first_cockpit_html(transport="http")

    assert "Agent Queue" in html
    assert "Needs you" in html
    assert "Pending" in html
    assert "Recent" in html
    assert "id=\"queueBadge\"" in html
    assert "id=\"queueItems\"" in html
    assert "id=\"needsYouBadge\"" in html
    assert "id=\"needsYouItems\"" in html
    assert "id=\"pendingBriefFeed\"" in html
    assert "id=\"recentBriefFeed\"" in html
    assert "function renderOrchestration()" in html
    assert "function renderNeedsYou()" in html
    assert "function renderBriefFeed()" in html
    assert "button.queue-action" in html
    assert "cancel_queue_task" in html
    assert "cancel_queue_job" in html
    assert "dismiss_queue_proposal" in html
    assert "function rerunBrief(" in html
    assert "function archiveBrief(" in html
    assert "awaiting_decision" in html
    assert "unresolved_members" in html
    assert "stale_needs_revalidation" in html

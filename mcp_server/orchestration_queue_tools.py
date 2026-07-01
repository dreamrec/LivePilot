"""MCP tool surface for LivePilot's multi-agent orchestration queue."""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from .persistence.orchestration_queue import OrchestrationService
from .server import mcp


def _lifespan(ctx: Context) -> dict:
    return getattr(ctx, "lifespan_context", {}) or {}


def _get_ableton(ctx: Context):
    return _lifespan(ctx)["ableton"]


def _require_session_info(ctx: Context) -> dict:
    info = _get_ableton(ctx).send_command("get_session_info")
    if not isinstance(info, dict) or info.get("error"):
        raise RuntimeError(f"Could not read session info: {info!r}")
    return info


def _service(ctx: Context) -> OrchestrationService:
    service = _lifespan(ctx).get("orchestration_queue")
    if isinstance(service, OrchestrationService):
        return service
    return OrchestrationService()


def _store(ctx: Context):
    session_info = _require_session_info(ctx)
    service = _service(ctx)
    return service.store_for_session(session_info), session_info


def _snapshot_inputs(ctx: Context, request_text: str, mode: str) -> dict:
    production_context = _build_production_context(ctx, request_text)
    session_kernel = _build_session_kernel(ctx, request_text, mode)
    summary = dict(production_context.get("summary") or {})
    if request_text:
        summary["text"] = str(request_text)
    if mode:
        summary["mode"] = str(mode)
    return {
        "brief": summary,
        "session_kernel": session_kernel,
        "cockpit_context": production_context,
        "section_map": production_context.get("section_map") or [],
        "layer_groups": production_context.get("layer_groups") or [],
        "track_intent_map": production_context.get("track_intent_map") or {},
    }


def _build_production_context(ctx: Context, request_text: str) -> dict:
    try:
        from .production_cockpit import get_production_context
        return get_production_context(ctx, request_text=request_text)
    except Exception as exc:  # noqa: BLE001 - snapshot should degrade.
        return {
            "status": "degraded",
            "warning": f"production_context_unavailable: {exc}",
        }


def _build_session_kernel(ctx: Context, request_text: str, mode: str) -> dict:
    try:
        from .runtime.tools import get_session_kernel
        return get_session_kernel(
            ctx,
            request_text=request_text,
            mode=mode or "observe",
        )
    except Exception as exc:  # noqa: BLE001 - snapshot should degrade.
        return {
            "status": "degraded",
            "warning": f"session_kernel_unavailable: {exc}",
        }


@mcp.tool()
def create_orchestration_snapshot(
    ctx: Context,
    request_text: str = "",
    mode: str = "observe",
) -> dict:
    """Create a project-scoped orchestration snapshot for parallel agents.

    Captures the current cockpit context, section map, layer groups, track
    intent map, and session kernel into a durable snapshot. Specialist agents
    should reason from this frozen snapshot instead of repeatedly querying
    Ableton.
    """
    session_info = _require_session_info(ctx)
    inputs = _snapshot_inputs(ctx, request_text=request_text, mode=mode)
    return _service(ctx).create_snapshot(session_info, **inputs)


@mcp.tool()
def submit_agent_task(
    ctx: Context,
    snapshot_id: str,
    agent_role: str,
    instruction: str,
    scope: Optional[dict] = None,
    constraints: Optional[dict] = None,
    status: str = "queued",
) -> dict:
    """Submit a read-mostly task for a specialist agent."""
    store, _session_info = _store(ctx)
    task = store.save_task({
        "snapshot_id": snapshot_id,
        "agent_role": agent_role,
        "instruction": instruction,
        "scope": scope or {},
        "constraints": constraints or {},
        "status": status,
    })
    return {"status": "ok", "project_id": store.project_id, "task": task}


@mcp.tool()
def list_agent_tasks(
    ctx: Context,
    status: str = "",
    snapshot_id: str = "",
) -> dict:
    """List orchestration tasks, optionally filtered by status or snapshot."""
    store, _session_info = _store(ctx)
    tasks = store.list_tasks(
        status=status or None,
        snapshot_id=snapshot_id or None,
    )
    return {
        "status": "ok",
        "project_id": store.project_id,
        "tasks": tasks,
        "task_count": len(tasks),
    }


@mcp.tool()
def submit_agent_proposal(
    ctx: Context,
    task_id: str = "",
    snapshot_id: str = "",
    agent_role: str = "",
    summary: str = "",
    confidence: float = 0.0,
    risk: str = "medium",
    write_set: Optional[list[str]] = None,
    transport_required: bool = False,
    suggested_jobs: Optional[list[dict]] = None,
    requires_user_decision: bool = False,
    status: str = "proposed",
) -> dict:
    """Submit a specialist-agent proposal for conductor review."""
    store, _session_info = _store(ctx)
    resolved_snapshot_id = snapshot_id or _snapshot_id_for_task(store, task_id)
    proposal = store.save_proposal({
        "task_id": task_id,
        "snapshot_id": resolved_snapshot_id,
        "agent_role": agent_role,
        "summary": summary,
        "confidence": confidence,
        "risk": risk,
        "write_set": write_set or [],
        "transport_required": transport_required,
        "suggested_jobs": suggested_jobs or [],
        "requires_user_decision": requires_user_decision,
        "status": status,
    })
    return {"status": "ok", "project_id": store.project_id, "proposal": proposal}


@mcp.tool()
def list_agent_proposals(
    ctx: Context,
    status: str = "",
    snapshot_id: str = "",
) -> dict:
    """List orchestration proposals, optionally filtered by status/snapshot."""
    store, _session_info = _store(ctx)
    proposals = store.list_proposals(
        status=status or None,
        snapshot_id=snapshot_id or None,
    )
    return {
        "status": "ok",
        "project_id": store.project_id,
        "proposals": proposals,
        "proposal_count": len(proposals),
    }


@mcp.tool()
def submit_ableton_job(
    ctx: Context,
    job_type: str,
    snapshot_id: str = "",
    title: str = "",
    priority: int = 50,
    scope: Optional[dict] = None,
    requires_transport: bool = False,
    requires_write: bool = True,
    write_set: Optional[list[str]] = None,
    leases: Optional[list[str]] = None,
    plan: Optional[list[dict]] = None,
    submitted_by: str = "conductor",
    status: str = "queued",
) -> dict:
    """Submit a serialized Ableton job for later conductor execution."""
    store, _session_info = _store(ctx)
    job = store.save_job({
        "snapshot_id": snapshot_id,
        "title": title,
        "submitted_by": submitted_by,
        "job_type": job_type,
        "priority": priority,
        "scope": scope or {},
        "requires_transport": requires_transport,
        "requires_write": requires_write,
        "write_set": write_set or [],
        "leases": leases or [],
        "plan": plan or [],
        "status": status,
    })
    return {"status": "ok", "project_id": store.project_id, "job": job}


@mcp.tool()
def list_ableton_jobs(
    ctx: Context,
    status: str = "",
    ordered: bool = True,
) -> dict:
    """List serialized Ableton jobs."""
    store, _session_info = _store(ctx)
    jobs = store.list_jobs(status=status or None, ordered=ordered)
    return {
        "status": "ok",
        "project_id": store.project_id,
        "jobs": jobs,
        "job_count": len(jobs),
        "next_queued_job": store.next_queued_job(),
    }


@mcp.tool()
def cancel_ableton_job(
    ctx: Context,
    job_id: str,
    reason: str = "",
) -> dict:
    """Cancel a queued or pending Ableton job."""
    store, _session_info = _store(ctx)
    job = store.update_job_status(
        job_id,
        "canceled",
        result={"reason": str(reason or "").strip()} if reason else {},
    )
    return {"status": "ok", "project_id": store.project_id, "job": job}


@mcp.tool()
def get_orchestration_state(
    ctx: Context,
    task_status: str = "",
    proposal_status: str = "",
    job_status: str = "",
    include_expired_leases: bool = False,
) -> dict:
    """Return the current project orchestration state for Codex/cockpit."""
    store, _session_info = _store(ctx)
    tasks = store.list_tasks(status=task_status or None)
    proposals = store.list_proposals(status=proposal_status or None)
    jobs = store.list_jobs(status=job_status or None, ordered=True)
    leases = store.list_leases(include_expired=include_expired_leases)
    return {
        "status": "ok",
        "project_id": store.project_id,
        "store_path": str(store.path),
        "project_revision": store.get_revision(),
        "snapshots": store.list_snapshots(),
        "tasks": tasks,
        "task_count": len(tasks),
        "proposals": proposals,
        "proposal_count": len(proposals),
        "jobs": jobs,
        "job_count": len(jobs),
        "leases": leases,
        "lease_count": len(leases),
        "next_queued_job": store.next_queued_job(),
    }


def _snapshot_id_for_task(store, task_id: str) -> str:
    if not task_id:
        return ""
    for task in store.list_tasks():
        if task.get("task_id") == task_id:
            return str(task.get("snapshot_id") or "")
    return ""

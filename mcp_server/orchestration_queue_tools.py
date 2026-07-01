"""MCP tool surface for LivePilot's multi-agent orchestration queue."""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from .persistence.orchestration_queue import OrchestrationService
from .runtime.execution_router import execute_plan_steps_async
from .server import mcp


_VARIANT_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DEFAULT_VARIANT_LABELS = [
    "lift",
    "edge color",
    "wide support",
    "darker",
    "brighter",
    "tucked",
    "raw",
    "polished",
]


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


def _normalize_layer_id(value) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _bounded_audition_count(value, fallback: int = 3) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = fallback
    return max(1, min(8, count))


def _track_lookup(session_info: dict, context: dict) -> dict[int, dict]:
    tracks = {}
    for track in session_info.get("tracks") or []:
        if isinstance(track, dict) and isinstance(track.get("index"), int):
            tracks[int(track["index"])] = dict(track)
    for track in context.get("tracks") or []:
        if isinstance(track, dict) and isinstance(track.get("index"), int):
            tracks[int(track["index"])] = dict(track)
    return tracks


def _find_layer_group(context: dict, layer_id: str) -> Optional[dict]:
    wanted = _normalize_layer_id(layer_id)
    if not wanted:
        return None
    for group in context.get("layer_groups") or []:
        if not isinstance(group, dict):
            continue
        keys = [
            group.get("key"),
            group.get("id"),
            group.get("layer_id"),
            group.get("label"),
        ]
        if any(_normalize_layer_id(value) == wanted for value in keys):
            return group
    return None


def _normalize_track_indices(values) -> list[int]:
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",")]
    if not isinstance(values, list):
        return []
    out: list[int] = []
    for value in values:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if index >= 0 and index not in out:
            out.append(index)
    return out


def _variant_letter(index: int) -> str:
    if index < len(_VARIANT_LETTERS):
        return _VARIANT_LETTERS[index]
    return f"V{index + 1}"


def _variant_label(scope: dict, index: int) -> str:
    raw = (
        scope.get("variant_labels")
        or scope.get("variant_concepts")
        or scope.get("concepts")
        or []
    )
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    if isinstance(raw, list) and index < len(raw):
        label = str(raw[index] or "").strip()
        if label:
            return label
    if index < len(_DEFAULT_VARIANT_LABELS):
        return _DEFAULT_VARIANT_LABELS[index]
    return f"variant {index + 1}"


def _audition_track_name(letter: str, source_name: str, label: str) -> str:
    source = " ".join(str(source_name or "track").split())
    concept = " ".join(str(label or "").split())
    name = f"AUD {letter} {source}"
    if concept:
        name = f"{name} {concept}"
    return name[:80].rstrip()


def _compile_visible_layer_audition_job(
    ctx: Context,
    session_info: dict,
    scope: dict,
    title: str,
) -> dict:
    """Compile duplicate/rename/mute/annotate steps for visible auditions."""
    scope = dict(scope or {})
    context = _build_production_context(
        ctx,
        request_text=str(scope.get("brief") or title or ""),
    )
    target = context.get("target") if isinstance(context.get("target"), dict) else {}
    summary = (
        context.get("summary")
        if isinstance(context.get("summary"), dict) else {}
    )
    layer_id = _normalize_layer_id(
        scope.get("layer_id")
        or target.get("matched_layer")
        or target.get("target_layer")
        or summary.get("target_layer")
    )
    if not layer_id:
        raise ValueError(
            "Layer audition jobs require scope.layer_id or an active cockpit "
            "Song Layer target."
        )

    layer = _find_layer_group(context, layer_id)
    track_indices = _normalize_track_indices(scope.get("track_indices"))
    if not track_indices and layer:
        track_indices = _normalize_track_indices(layer.get("track_indices"))
    if not track_indices:
        raise ValueError(
            f"Layer audition job could not resolve tracks for layer '{layer_id}'."
        )

    count = _bounded_audition_count(
        scope.get("audition_count"),
        fallback=_bounded_audition_count(summary.get("audition_count"), 3),
    )
    tracks = _track_lookup(session_info, context)
    layer_label = (
        str((layer or {}).get("label") or layer_id.replace("_", " ").title())
        if layer else layer_id.replace("_", " ").title()
    )
    generated_scope = dict(scope)
    generated_scope.update({
        "layer_id": layer_id,
        "layer_label": layer_label,
        "track_indices": track_indices,
        "source_track_indices": track_indices,
        "audition_count": count,
        "audition_style": "visible_muted_duplicate_lanes",
    })

    plan: list[dict] = []
    variants = []
    for variant_index in range(count):
        variants.append({
            "letter": _variant_letter(variant_index),
            "label": _variant_label(scope, variant_index),
        })

    # Duplicate all variants for a source before moving to lower source tracks.
    # Ableton inserts duplicates next to the source, so descending source order
    # preserves the original source indices until each source is finished.
    for source_index in sorted(track_indices, reverse=True):
        source_name = str(tracks.get(source_index, {}).get("name") or f"Track {source_index + 1}")
        for variant in variants:
            letter = variant["letter"]
            label = variant["label"]
            duplicate_step_id = f"aud_{letter.lower()}_src_{source_index}_duplicate"
            duplicate_index = {"$from_step": duplicate_step_id, "path": "index"}
            plan.extend([
                {
                    "step_id": duplicate_step_id,
                    "tool": "duplicate_track",
                    "params": {"track_index": source_index},
                    "summary": (
                        f"Duplicate source track {source_index} for "
                        f"audition {letter}."
                    ),
                },
                {
                    "tool": "set_track_name",
                    "params": {
                        "track_index": duplicate_index,
                        "name": _audition_track_name(letter, source_name, label),
                    },
                    "summary": f"Name audition {letter} duplicate.",
                },
                {
                    "tool": "set_track_mute",
                    "params": {
                        "track_index": duplicate_index,
                        "mute": True,
                    },
                    "summary": f"Mute audition {letter} duplicate by default.",
                },
                {
                    "tool": "set_track_annotation",
                    "backend": "mcp_tool",
                    "params": {
                        "track_index": duplicate_index,
                        "role": "audition_variant",
                        "decision_state": "open",
                        "source": "orchestration_layer_audition_job",
                        "notes": (
                            f"Visible audition {letter} for layer "
                            f"{layer_label}; source track {source_name}."
                        ),
                        "tags": [
                            "audition",
                            f"variant:{letter}",
                            f"layer:{layer_id}",
                            f"source_track:{source_index}",
                        ],
                        "relationships": [
                            {
                                "type": "variant_of",
                                "source_track_index": source_index,
                                "source_track_name": source_name,
                            },
                            {
                                "type": "audition_layer",
                                "layer_id": layer_id,
                                "layer_label": layer_label,
                            },
                            {
                                "type": "audition_variant",
                                "variant": letter,
                                "concept": label,
                            },
                        ],
                    },
                    "summary": f"Annotate audition {letter} duplicate.",
                },
            ])

    resources = [f"track:{index}" for index in track_indices]
    resources.extend([f"layer:{layer_id}", "project"])
    generated_title = title or (
        f"Create {count} visible {layer_label} audition"
        f"{'' if count == 1 else 's'}"
    )
    return {
        "title": generated_title,
        "scope": generated_scope,
        "requires_transport": False,
        "requires_write": True,
        "write_set": resources,
        "leases": resources,
        "plan": plan,
        "audition_manifest": {
            "style": "visible_muted_duplicate_lanes",
            "layer_id": layer_id,
            "layer_label": layer_label,
            "source_track_indices": track_indices,
            "variant_count": count,
            "variants": variants,
            "steps_per_duplicate": 4,
        },
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
    store, session_info = _store(ctx)
    resolved_scope = dict(scope or {})
    resolved_plan = plan or []
    resolved_write_set = write_set or []
    resolved_leases = leases or []
    resolved_title = title
    resolved_requires_transport = requires_transport
    resolved_requires_write = requires_write
    audition_manifest = None

    normalized_job_type = str(job_type or "").strip().lower().replace("-", "_")
    if normalized_job_type == "audition" and not resolved_plan:
        generated = _compile_visible_layer_audition_job(
            ctx,
            session_info,
            resolved_scope,
            title=title,
        )
        resolved_scope = generated["scope"]
        resolved_plan = generated["plan"]
        resolved_write_set = generated["write_set"]
        resolved_leases = generated["leases"]
        resolved_title = generated["title"]
        resolved_requires_transport = generated["requires_transport"]
        resolved_requires_write = generated["requires_write"]
        audition_manifest = generated["audition_manifest"]

    payload = {
        "snapshot_id": snapshot_id,
        "title": resolved_title,
        "submitted_by": submitted_by,
        "job_type": job_type,
        "priority": priority,
        "scope": resolved_scope,
        "requires_transport": resolved_requires_transport,
        "requires_write": resolved_requires_write,
        "write_set": resolved_write_set,
        "leases": resolved_leases,
        "plan": resolved_plan,
        "status": status,
    }
    if audition_manifest is not None:
        payload["audition_manifest"] = audition_manifest
    job = store.save_job(payload)
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
async def run_next_ableton_job(
    ctx: Context,
    job_id: str = "",
) -> dict:
    """Run one queued Ableton job through the serialized conductor path.

    This is manual by design: no background worker and no automatic queue
    drain. The first implementation supports the limited plan format already
    used by LivePilot compiled plans: a list of `{tool, params}` or
    `{command, args}` step dictionaries routed through the async execution
    router.
    """
    store, _session_info = _store(ctx)
    job = store.get_job(job_id) if job_id else store.next_queued_job()
    if job is None:
        return {
            "status": "idle",
            "project_id": store.project_id,
            "job": None,
            "message": "No queued Ableton job found.",
        }

    stale = store.job_staleness(job["job_id"])
    if stale.get("is_stale"):
        updated = store.update_job_status(
            job["job_id"],
            "awaiting_decision",
            result={"blocked_reason": "stale_snapshot", "staleness": stale},
        )
        return {
            "status": "blocked",
            "project_id": store.project_id,
            "job": updated,
            "blocked_reason": "stale_snapshot",
            "staleness": stale,
        }

    steps = _job_plan_steps(job)
    if not steps:
        failed = store.update_job_status(
            job["job_id"],
            "failed",
            result={"error": "Job has no executable plan steps."},
        )
        return {
            "status": "failed",
            "project_id": store.project_id,
            "job": failed,
            "error": "Job has no executable plan steps.",
        }

    claim = store.claim_resources_for_job(job["job_id"])
    if claim.get("status") == "blocked":
        return {
            "status": "blocked",
            "project_id": store.project_id,
            "job": job,
            "blocked_reason": "resource_conflict",
            "conflicts": claim.get("conflicts", []),
        }

    started = store.update_job_status(job["job_id"], "running")
    exec_results = []
    try:
        results = await execute_plan_steps_async(
            steps,
            ableton=_get_ableton(ctx),
            bridge=_lifespan(ctx).get("m4l"),
            mcp_registry=_lifespan(ctx).get("mcp_dispatch", {}),
            ctx=ctx,
            stop_on_failure=True,
        )
        exec_results = [result.to_dict() for result in results]
        ok = bool(results) and all(result.ok for result in results)
        if ok:
            revision = None
            if bool(started.get("requires_write")) or started.get("job_type") in {
                "audition",
                "mutation",
            }:
                revision_state = store.increment_revision(
                    reason=f"{started.get('job_type')}_job_done",
                    source_id=started["job_id"],
                )
                revision = revision_state.get("project_revision")
            done = store.update_job_status(
                started["job_id"],
                "done",
                result={
                    "execution_log": exec_results,
                    "project_revision": revision,
                },
            )
            return {
                "status": "done",
                "project_id": store.project_id,
                "job": done,
                "execution_log": exec_results,
            }

        failed = store.update_job_status(
            started["job_id"],
            "failed",
            result={
                "execution_log": exec_results,
                "error": _first_execution_error(exec_results),
            },
        )
        return {
            "status": "failed",
            "project_id": store.project_id,
            "job": failed,
            "execution_log": exec_results,
            "error": _first_execution_error(exec_results),
        }
    except Exception as exc:  # noqa: BLE001 - persist job failure details.
        failed = store.update_job_status(
            started["job_id"],
            "failed",
            result={
                "execution_log": exec_results,
                "error": str(exc),
            },
        )
        return {
            "status": "failed",
            "project_id": store.project_id,
            "job": failed,
            "execution_log": exec_results,
            "error": str(exc),
        }
    finally:
        store.release_leases_for_job(started["job_id"])


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


def _job_plan_steps(job: dict) -> list[dict]:
    plan = job.get("plan")
    if not isinstance(plan, list):
        return []
    steps = []
    for step in plan:
        if not isinstance(step, dict):
            continue
        tool = step.get("tool") or step.get("command")
        if not tool:
            continue
        steps.append(dict(step))
    return steps


def _first_execution_error(exec_results: list[dict]) -> str:
    for item in exec_results:
        if not item.get("ok"):
            return str(item.get("error") or "execution failed")
    return "execution failed"

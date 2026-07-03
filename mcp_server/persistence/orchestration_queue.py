"""Project-scoped orchestration state for multi-agent LivePilot work.

This module is persistence-only. It stores the durable objects that later MCP
tools, cockpit views, and executors will coordinate around: snapshots, tasks,
proposals, jobs, leases, and a lightweight project revision counter.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .paths import livepilot_projects_dir
from .track_annotations import annotation_project_id_for_session


_PROJECTS_DIR: Optional[Path] = None
_STORE_VERSION = 1
_REVISION_HISTORY_LIMIT = 100

_TASK_STATUSES = {"queued", "running", "done", "failed", "canceled"}
_PROPOSAL_STATUSES = {
    "proposed",
    "approved",
    "rejected",
    "stale_needs_revalidation",
    "superseded",
}
_JOB_TYPES = {"offline_analysis", "playback_analysis", "audition", "mutation"}
_JOB_STATUSES = {
    "queued",
    "running",
    "awaiting_decision",
    "done",
    "failed",
    "canceled",
}
_RISKS = {"low", "medium", "high"}
_TERMINAL_PROPOSAL_STATUSES = {"rejected", "superseded"}


class OrchestrationService:
    """Resolve a Live session to its project-scoped orchestration store."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _projects_dir()

    def get_state(self, session_info: dict) -> dict:
        store = self.store_for_session(session_info)
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "state": store.get_all(),
        }

    def create_snapshot(
        self,
        session_info: dict,
        brief: Optional[dict] = None,
        session_kernel: Optional[dict] = None,
        context_digest: Optional[dict] = None,
        production_context_state: Optional[dict] = None,
        cockpit_context: Optional[dict] = None,
        section_map: Optional[list[dict]] = None,
        layer_groups: Optional[list[dict]] = None,
        track_intent_map: Optional[dict] = None,
    ) -> dict:
        store = self.store_for_session(session_info)
        payload = {
            "project_id": store.project_id,
            "project_revision": store.get_revision(),
            "brief": brief or {},
            "session_kernel": session_kernel or {},
            "context_digest": context_digest or {},
            "production_context_state": production_context_state or {},
            "section_map": section_map or [],
            "layer_groups": layer_groups or [],
            "track_intent_map": track_intent_map or {},
        }
        if cockpit_context is not None:
            # Legacy/raw snapshot callers may still pass an embedded context.
            # New cockpit brief snapshots use context_digest + state instead.
            payload["cockpit_context"] = cockpit_context
        snapshot = store.save_snapshot(payload)
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "snapshot": snapshot,
        }

    def store_for_session(self, session_info: dict) -> "OrchestrationStore":
        return OrchestrationStore(
            annotation_project_id_for_session(session_info, self._base_dir),
            self._base_dir,
        )


class OrchestrationStore:
    """Atomic JSON store for one project's orchestration queue state."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _projects_dir()
        self._store = PersistentJsonStore(base / project_id / "orchestration.json")
        self._project_id = project_id

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def path(self) -> Path:
        return self._store.path

    def get_all(self) -> dict:
        data = self._store.read()
        return data if data.get("version") == _STORE_VERSION else self._default()

    def get_revision(self) -> int:
        return int(self.get_all().get("project_revision") or 0)

    def increment_revision(
        self,
        reason: str = "",
        source_id: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Increment the project revision and mark stale proposals."""
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            previous = int(data.get("project_revision") or 0)
            current = previous + 1
            data["project_revision"] = current
            entry = {
                "revision": current,
                "previous_revision": previous,
                "reason": str(reason or "").strip(),
                "source_id": str(source_id or "").strip(),
                "metadata": dict(metadata or {}),
                "created_at_ms": now,
            }
            history = data.setdefault("revision_history", [])
            history.append(entry)
            if len(history) > _REVISION_HISTORY_LIMIT:
                data["revision_history"] = history[-_REVISION_HISTORY_LIMIT:]

            snapshots_by_id = {
                item.get("snapshot_id"): item
                for item in data.get("snapshots", [])
                if isinstance(item, dict)
            }
            for proposal in data.get("proposals", []):
                if not isinstance(proposal, dict):
                    continue
                status = proposal.get("status")
                if status in _TERMINAL_PROPOSAL_STATUSES:
                    continue
                snapshot = snapshots_by_id.get(proposal.get("snapshot_id")) or {}
                proposal_revision = _as_int(
                    snapshot.get("project_revision"),
                    fallback=_as_int(proposal.get("project_revision"), 0),
                )
                if proposal_revision < current:
                    proposal["status"] = "stale_needs_revalidation"
                    proposal["stale_since_revision"] = current
                    proposal["updated_at_ms"] = now

            data["last_updated_ms"] = now
            return data

        return self._store.update(_update)

    def save_snapshot(self, snapshot: dict) -> dict:
        now = _now_ms()
        normalized = _normalize_snapshot(snapshot, self.project_id, now)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            _upsert_by_id(data.setdefault("snapshots", []), "snapshot_id", normalized)
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return _find_by_id(data.get("snapshots", []), "snapshot_id", normalized["snapshot_id"])

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        return _find_optional(
            self.get_all().get("snapshots", []),
            "snapshot_id",
            snapshot_id,
        )

    def list_snapshots(self) -> list[dict]:
        return list(self.get_all().get("snapshots", []))

    def snapshot_staleness(self, snapshot_id: str) -> dict:
        snapshot_id = str(snapshot_id or "").strip()
        current_revision = self.get_revision()
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            return {
                "snapshot_id": snapshot_id,
                "status": "missing",
                "is_stale": True,
                "snapshot_revision": None,
                "current_revision": current_revision,
                "reason": "snapshot_not_found",
            }
        snapshot_revision = _as_int(snapshot.get("project_revision"), 0)
        is_stale = snapshot_revision < current_revision
        return {
            "snapshot_id": snapshot_id,
            "status": "stale" if is_stale else "fresh",
            "is_stale": is_stale,
            "snapshot_revision": snapshot_revision,
            "current_revision": current_revision,
            "reason": (
                "snapshot_revision_behind_current"
                if is_stale else
                "snapshot_matches_current_revision"
            ),
        }

    def save_task(self, task: dict) -> dict:
        now = _now_ms()
        normalized = _normalize_task(task, now)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            _upsert_by_id(data.setdefault("tasks", []), "task_id", normalized)
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return _find_by_id(data.get("tasks", []), "task_id", normalized["task_id"])

    def list_tasks(
        self,
        status: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> list[dict]:
        items = list(self.get_all().get("tasks", []))
        if status:
            items = [item for item in items if item.get("status") == status]
        if snapshot_id:
            items = [item for item in items if item.get("snapshot_id") == snapshot_id]
        return items

    def update_task_status(self, task_id: str, status: str) -> dict:
        return self._update_item_status(
            collection="tasks",
            key="task_id",
            item_id=task_id,
            status=status,
            allowed=_TASK_STATUSES,
            label="task status",
        )

    def save_proposal(self, proposal: dict) -> dict:
        now = _now_ms()
        normalized = _normalize_proposal(proposal, now)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            snapshot = _find_optional(
                data.get("snapshots", []),
                "snapshot_id",
                normalized.get("snapshot_id"),
            )
            if snapshot and normalized.get("project_revision") is None:
                normalized["project_revision"] = snapshot.get("project_revision", 0)
            _upsert_by_id(
                data.setdefault("proposals", []),
                "proposal_id",
                normalized,
            )
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return _find_by_id(
            data.get("proposals", []),
            "proposal_id",
            normalized["proposal_id"],
        )

    def list_proposals(
        self,
        status: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> list[dict]:
        items = list(self.get_all().get("proposals", []))
        if status:
            items = [item for item in items if item.get("status") == status]
        if snapshot_id:
            items = [item for item in items if item.get("snapshot_id") == snapshot_id]
        return items

    def update_proposal_status(
        self,
        proposal_id: str,
        status: str,
        reason: str = "",
    ) -> dict:
        updates = {}
        if reason:
            updates["status_reason"] = str(reason).strip()
        return self._update_item_status(
            collection="proposals",
            key="proposal_id",
            item_id=proposal_id,
            status=status,
            allowed=_PROPOSAL_STATUSES,
            label="proposal status",
            updates=updates,
        )

    def save_job(self, job: dict) -> dict:
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            sequence = _as_int(data.get("next_job_sequence"), 1)
            normalized = _normalize_job(
                job,
                project_id=self.project_id,
                now=now,
                sequence=sequence,
            )
            existing = _find_optional(
                data.get("jobs", []),
                "job_id",
                normalized["job_id"],
            )
            if existing is None:
                data["next_job_sequence"] = sequence + 1
            else:
                normalized["sequence"] = existing.get("sequence", sequence)
            _upsert_by_id(data.setdefault("jobs", []), "job_id", normalized)
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        job_id = str(job.get("job_id") or data.get("jobs", [])[-1].get("job_id"))
        return _find_by_id(data.get("jobs", []), "job_id", job_id)

    def list_jobs(
        self,
        status: Optional[str] = None,
        ordered: bool = False,
    ) -> list[dict]:
        items = list(self.get_all().get("jobs", []))
        if status:
            items = [item for item in items if item.get("status") == status]
        if ordered:
            items.sort(key=_job_order_key)
        return items

    def next_queued_job(self) -> Optional[dict]:
        queued = self.list_jobs(status="queued", ordered=True)
        return queued[0] if queued else None

    def get_job(self, job_id: str) -> Optional[dict]:
        return _find_optional(self.get_all().get("jobs", []), "job_id", job_id)

    def job_staleness(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if job is None:
            return {
                "job_id": str(job_id or "").strip(),
                "status": "missing",
                "is_stale": True,
                "reason": "job_not_found",
            }
        result = self.snapshot_staleness(str(job.get("snapshot_id") or ""))
        result["job_id"] = job.get("job_id")
        return result

    def update_job_status(
        self,
        job_id: str,
        status: str,
        result=None,
    ) -> dict:
        updates = {}
        if result is not None:
            updates["result"] = result
        return self._update_item_status(
            collection="jobs",
            key="job_id",
            item_id=job_id,
            status=status,
            allowed=_JOB_STATUSES,
            label="job status",
            updates=updates,
        )

    def save_lease(self, lease: dict) -> dict:
        now = _now_ms()
        normalized = _normalize_lease(lease, now)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            _upsert_by_id(data.setdefault("leases", []), "lease_id", normalized)
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return _find_by_id(data.get("leases", []), "lease_id", normalized["lease_id"])

    def list_leases(self, include_expired: bool = False) -> list[dict]:
        now = _now_ms()
        leases = list(self.get_all().get("leases", []))
        if include_expired:
            return leases
        return [
            lease for lease in leases
            if _as_int(lease.get("expires_at_ms"), 0) <= 0
            or _as_int(lease.get("expires_at_ms"), 0) > now
        ]

    def resources_for_job(self, job_or_id) -> list[str]:
        if isinstance(job_or_id, dict):
            job = dict(job_or_id)
        else:
            job = self.get_job(str(job_or_id or ""))
            if job is None:
                raise KeyError(f"job_id not found: {job_or_id}")
        resources: list[str] = []
        if bool(job.get("requires_transport", False)):
            resources.append("transport")
        for item in job.get("leases") or []:
            _append_resource(resources, item)
        for item in job.get("write_set") or []:
            _append_resource(resources, _resource_from_write_set(item))
        scope = job.get("scope") if isinstance(job.get("scope"), dict) else {}
        for track_index in scope.get("track_indices") or []:
            _append_resource(resources, f"track:{track_index}")
        if scope.get("layer_id"):
            _append_resource(resources, f"layer:{scope.get('layer_id')}")
        if scope.get("section_id"):
            _append_resource(resources, f"section:{scope.get('section_id')}")
        return resources

    def find_resource_conflicts(
        self,
        resources: list[str],
        exclude_job_id: str = "",
    ) -> list[dict]:
        requested = [_normalize_resource(item) for item in resources]
        requested = [item for item in requested if item]
        exclude_job_id = str(exclude_job_id or "").strip()
        conflicts = []
        for lease in self.list_leases(include_expired=False):
            if exclude_job_id and lease.get("job_id") == exclude_job_id:
                continue
            held = _normalize_resource(lease.get("resource"))
            for resource in requested:
                if _resources_conflict(resource, held):
                    conflicts.append({
                        "requested": resource,
                        "held": held,
                        "lease": lease,
                    })
        return conflicts

    def claim_resources_for_job(
        self,
        job_id: str,
        resources: Optional[list[str]] = None,
        owner: str = "conductor",
        ttl_ms: int = 0,
    ) -> dict:
        """Atomically claim leases for a job unless active leases conflict."""
        job_id = str(job_id or "").strip()
        owner = str(owner or "conductor").strip() or "conductor"
        now = _now_ms()
        claim_result: dict = {}

        def _update(data: dict) -> dict:
            nonlocal claim_result
            data = data if data.get("version") == _STORE_VERSION else self._default()
            job = _find_optional(data.get("jobs", []), "job_id", job_id)
            if job is None:
                raise KeyError(f"job_id not found: {job_id}")
            requested = resources or self.resources_for_job(job)
            requested = [_normalize_resource(item) for item in requested]
            requested = [item for item in requested if item]
            active_leases = [
                lease for lease in data.get("leases", [])
                if not _lease_expired(lease, now)
                and lease.get("job_id") != job_id
            ]
            conflicts = []
            for resource in requested:
                for lease in active_leases:
                    held = _normalize_resource(lease.get("resource"))
                    if _resources_conflict(resource, held):
                        conflicts.append({
                            "requested": resource,
                            "held": held,
                            "lease": dict(lease),
                        })
            if conflicts:
                claim_result = {
                    "status": "blocked",
                    "job_id": job_id,
                    "claimed": [],
                    "conflicts": conflicts,
                }
                return data

            ttl = _as_int(ttl_ms, 0)
            expires_at_ms = now + ttl if ttl > 0 else 0
            existing = data.setdefault("leases", [])
            claimed = []
            for resource in requested:
                lease = _normalize_lease({
                    "lease_id": _new_id("lease"),
                    "resource": resource,
                    "job_id": job_id,
                    "owner": owner,
                    "expires_at_ms": expires_at_ms,
                }, now)
                existing.append(lease)
                claimed.append(lease)
            data["last_updated_ms"] = now
            claim_result = {
                "status": "claimed",
                "job_id": job_id,
                "claimed": claimed,
                "conflicts": [],
            }
            return data

        self._store.update(_update)
        return claim_result

    def claim_resource(
        self,
        resource: str,
        owner: str = "cockpit",
        ttl_ms: int = 15000,
    ) -> dict:
        """Atomically claim one resource for a short owner-scoped operation."""
        owner = str(owner or "cockpit").strip() or "cockpit"
        requested = _normalize_resource(resource)
        if not requested:
            raise ValueError("resource cannot be empty")
        now = _now_ms()
        claim_result: dict = {}

        def _update(data: dict) -> dict:
            nonlocal claim_result
            data = data if data.get("version") == _STORE_VERSION else self._default()
            active_leases = [
                lease for lease in data.get("leases", [])
                if not _lease_expired(lease, now)
            ]
            conflicts = []
            for lease in active_leases:
                held = _normalize_resource(lease.get("resource"))
                if _resources_conflict(requested, held):
                    conflicts.append({
                        "requested": requested,
                        "held": held,
                        "lease": dict(lease),
                    })
            if conflicts:
                claim_result = {
                    "status": "blocked",
                    "owner": owner,
                    "resource": requested,
                    "claimed": [],
                    "conflicts": conflicts,
                }
                return data

            ttl = _as_int(ttl_ms, 15000)
            expires_at_ms = now + ttl if ttl > 0 else 0
            lease = _normalize_lease({
                "lease_id": _new_id("lease"),
                "resource": requested,
                "job_id": "",
                "owner": owner,
                "expires_at_ms": expires_at_ms,
            }, now)
            data.setdefault("leases", []).append(lease)
            data["last_updated_ms"] = now
            claim_result = {
                "status": "claimed",
                "owner": owner,
                "resource": requested,
                "claimed": [lease],
                "conflicts": [],
            }
            return data

        self._store.update(_update)
        return claim_result

    def release_resource(
        self,
        resource: str,
        owner: str = "cockpit",
    ) -> dict:
        """Release non-job leases matching a resource and owner."""
        owner = str(owner or "cockpit").strip() or "cockpit"
        requested = _normalize_resource(resource)
        now = _now_ms()
        release_result: dict = {}

        def _update(data: dict) -> dict:
            nonlocal release_result
            data = data if data.get("version") == _STORE_VERSION else self._default()
            released = []
            kept = []
            for lease in data.get("leases", []):
                lease_resource = _normalize_resource(lease.get("resource"))
                if (
                    lease_resource == requested
                    and str(lease.get("owner") or "") == owner
                    and not str(lease.get("job_id") or "").strip()
                ):
                    released.append(lease)
                else:
                    kept.append(lease)
            data["leases"] = kept
            if released:
                data["last_updated_ms"] = now
            release_result = {
                "status": "ok",
                "owner": owner,
                "resource": requested,
                "released": released,
                "released_count": len(released),
            }
            return data

        self._store.update(_update)
        return release_result

    def release_leases_for_job(self, job_id: str) -> dict:
        job_id = str(job_id or "").strip()
        now = _now_ms()
        release_result: dict = {}

        def _update(data: dict) -> dict:
            nonlocal release_result
            data = data if data.get("version") == _STORE_VERSION else self._default()
            released = [
                lease for lease in data.get("leases", [])
                if lease.get("job_id") == job_id
            ]
            data["leases"] = [
                lease for lease in data.get("leases", [])
                if lease.get("job_id") != job_id
            ]
            if released:
                data["last_updated_ms"] = now
            release_result = {
                "status": "ok",
                "job_id": job_id,
                "released": released,
                "released_count": len(released),
            }
            return data

        self._store.update(_update)
        return release_result

    def remove_lease(self, lease_id: str) -> bool:
        lease_id = str(lease_id or "").strip()

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            before = len(data.get("leases", []))
            data["leases"] = [
                lease for lease in data.get("leases", [])
                if lease.get("lease_id") != lease_id
            ]
            if len(data["leases"]) != before:
                data["last_updated_ms"] = _now_ms()
            return data

        before = len(self.get_all().get("leases", []))
        self._store.update(_update)
        return len(self.get_all().get("leases", [])) != before

    def _update_item_status(
        self,
        collection: str,
        key: str,
        item_id: str,
        status: str,
        allowed: set[str],
        label: str,
        updates: Optional[dict] = None,
    ) -> dict:
        normalized_status = _normalize_choice(status, allowed, "", label)
        item_id = str(item_id or "").strip()
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            for item in data.get(collection, []):
                if isinstance(item, dict) and item.get(key) == item_id:
                    item["status"] = normalized_status
                    item["updated_at_ms"] = now
                    if updates:
                        item.update(updates)
                    data["last_updated_ms"] = now
                    return data
            raise KeyError(f"{key} not found: {item_id}")

        data = self._store.update(_update)
        return _find_by_id(data.get(collection, []), key, item_id)

    @staticmethod
    def _default() -> dict:
        return {
            "version": _STORE_VERSION,
            "project_revision": 0,
            "revision_history": [],
            "snapshots": [],
            "tasks": [],
            "proposals": [],
            "jobs": [],
            "leases": [],
            "next_job_sequence": 1,
            "last_updated_ms": 0,
        }


def _normalize_snapshot(snapshot: dict, project_id: str, now: int) -> dict:
    item = dict(snapshot or {})
    legacy_context = _as_dict(item.get("cockpit_context"))
    item.setdefault("snapshot_id", _new_id("snap"))
    item["snapshot_id"] = _normalize_required_id(item["snapshot_id"], "snapshot_id")
    item["project_id"] = str(item.get("project_id") or project_id)
    item["project_revision"] = _as_int(item.get("project_revision"), 0)
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = _as_int(item.get("created_at_ms"), now)
    item["brief"] = _as_dict(item.get("brief"))
    item["session_kernel"] = _as_dict(item.get("session_kernel"))
    item["context_digest"] = _as_dict(item.get("context_digest"))
    item["production_context_state"] = _as_dict(item.get("production_context_state"))
    if not item["context_digest"] and legacy_context:
        item["context_digest"] = _context_digest_from_legacy_context(legacy_context)
    if not item["production_context_state"] and legacy_context:
        item["production_context_state"] = _production_state_from_legacy_context(
            legacy_context
        )
    if "cockpit_context" in item:
        item["cockpit_context"] = legacy_context
    item["section_map"] = _as_list(item.get("section_map"))
    item["layer_groups"] = _as_list(item.get("layer_groups"))
    item["track_intent_map"] = _as_dict(item.get("track_intent_map"))
    return item


def _context_digest_from_legacy_context(context: dict) -> dict:
    target = _as_dict(context.get("target"))
    state = _production_state_from_legacy_context(context)
    return {
        "target_mode": target.get("target_mode", state.get("target_mode", "")),
        "target_label": (
            target.get("matched_layer_label")
            or target.get("matched_group_label")
            or target.get("query", "")
        ),
        "layer_id": target.get("matched_layer") or target.get("target_layer") or "",
        "track_indices": _as_list(target.get("track_indices")),
        "track_refs": [],
        "section": target.get("section") or state.get("section"),
        "lane": state.get("lane", "holistic"),
        "workflow_mode": state.get("workflow_mode", "guided"),
        "audition_count": _as_int(state.get("audition_count"), 3),
        "audition_scope": state.get("audition_scope", "layer"),
        "evidence_budget": state.get("evidence_budget", "standard"),
        "protect": _as_list(state.get("protect")),
        "reference": state.get("reference", ""),
        "fallback_source": "legacy_cockpit_context",
    }


def _production_state_from_legacy_context(context: dict) -> dict:
    state = _as_dict(context.get("production_state"))
    if state:
        return state
    production_context = _as_dict(context.get("production_context"))
    return _as_dict(production_context.get("state"))


def _normalize_task(task: dict, now: int) -> dict:
    item = dict(task or {})
    item.setdefault("task_id", _new_id("task"))
    item["task_id"] = _normalize_required_id(item["task_id"], "task_id")
    item["snapshot_id"] = str(item.get("snapshot_id") or "").strip()
    item["agent_role"] = str(item.get("agent_role") or "").strip()
    item["instruction"] = str(item.get("instruction") or "").strip()
    item["scope"] = _as_dict(item.get("scope"))
    item["constraints"] = _as_dict(item.get("constraints"))
    item["status"] = _normalize_choice(
        item.get("status"),
        _TASK_STATUSES,
        "queued",
        "task status",
    )
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = _as_int(item.get("created_at_ms"), now)
    item["updated_at_ms"] = now
    return item


def _normalize_proposal(proposal: dict, now: int) -> dict:
    item = dict(proposal or {})
    item.setdefault("proposal_id", _new_id("prop"))
    item["proposal_id"] = _normalize_required_id(item["proposal_id"], "proposal_id")
    item["task_id"] = str(item.get("task_id") or "").strip()
    item["snapshot_id"] = str(item.get("snapshot_id") or "").strip()
    item["agent_role"] = str(item.get("agent_role") or "").strip()
    item["summary"] = str(item.get("summary") or "").strip()
    item["confidence"] = _as_float(item.get("confidence"), 0.0, minimum=0.0, maximum=1.0)
    item["risk"] = _normalize_choice(item.get("risk"), _RISKS, "medium", "risk")
    item["write_set"] = _normalize_string_list(item.get("write_set"))
    item["transport_required"] = bool(item.get("transport_required", False))
    item["suggested_jobs"] = _as_list(item.get("suggested_jobs"))
    item["requires_user_decision"] = bool(item.get("requires_user_decision", False))
    item["status"] = _normalize_choice(
        item.get("status"),
        _PROPOSAL_STATUSES,
        "proposed",
        "proposal status",
    )
    item["project_revision"] = (
        None if item.get("project_revision") is None
        else _as_int(item.get("project_revision"), 0)
    )
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = _as_int(item.get("created_at_ms"), now)
    item["updated_at_ms"] = now
    return item


def _normalize_job(job: dict, project_id: str, now: int, sequence: int) -> dict:
    item = dict(job or {})
    item.setdefault("job_id", _new_id("job"))
    item["job_id"] = _normalize_required_id(item["job_id"], "job_id")
    item["project_id"] = str(item.get("project_id") or project_id)
    item["snapshot_id"] = str(item.get("snapshot_id") or "").strip()
    item["submitted_by"] = str(item.get("submitted_by") or "conductor").strip()
    item["job_type"] = _normalize_choice(
        item.get("job_type"),
        _JOB_TYPES,
        "mutation",
        "job_type",
    )
    item["priority"] = _as_int(item.get("priority"), 50)
    item["scope"] = _as_dict(item.get("scope"))
    item["requires_transport"] = bool(item.get("requires_transport", False))
    item["requires_write"] = bool(item.get("requires_write", False))
    item["write_set"] = _normalize_string_list(item.get("write_set"))
    item["leases"] = _normalize_string_list(item.get("leases"))
    item["plan"] = _as_list(item.get("plan"))
    item["status"] = _normalize_choice(
        item.get("status"),
        _JOB_STATUSES,
        "queued",
        "job status",
    )
    item["result"] = item.get("result")
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = _as_int(item.get("created_at_ms"), now)
    item["updated_at_ms"] = now
    item["sequence"] = _as_int(item.get("sequence"), sequence)
    return item


def _normalize_lease(lease: dict, now: int) -> dict:
    item = dict(lease or {})
    item.setdefault("lease_id", _new_id("lease"))
    item["lease_id"] = _normalize_required_id(item["lease_id"], "lease_id")
    item["resource"] = str(item.get("resource") or "").strip()
    if not item["resource"]:
        raise ValueError("lease resource cannot be empty")
    item["job_id"] = str(item.get("job_id") or "").strip()
    item["owner"] = str(item.get("owner") or "conductor").strip()
    item["expires_at_ms"] = _as_int(item.get("expires_at_ms"), 0)
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = _as_int(item.get("created_at_ms"), now)
    item["updated_at_ms"] = now
    return item


def _append_resource(resources: list[str], value) -> None:
    resource = _normalize_resource(value)
    if resource and resource not in resources:
        resources.append(resource)


def _normalize_resource(value) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if not text:
        return ""
    parts = [part for part in text.split(":") if part]
    if not parts:
        return ""
    head = parts[0]
    if head in {"transport", "master", "project"}:
        return head
    if head in {"track", "layer", "section"} and len(parts) >= 2:
        return f"{head}:{parts[1]}"
    return text


def _resource_from_write_set(value) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if not text:
        return ""
    if text.startswith("master"):
        return "master"
    if text.startswith("project"):
        return "project"
    if text.startswith("transport"):
        return "transport"
    return _normalize_resource(text)


def _resources_conflict(left: str, right: str) -> bool:
    left = _normalize_resource(left)
    right = _normalize_resource(right)
    if not left or not right:
        return False
    if left == right:
        return True
    if "project" in {left, right}:
        return True
    if {left, right} == {"master", "transport"}:
        return True
    return False


def _lease_expired(lease: dict, now: int) -> bool:
    expires_at_ms = _as_int(lease.get("expires_at_ms"), 0)
    return expires_at_ms > 0 and expires_at_ms <= now


def _upsert_by_id(items: list[dict], key: str, item: dict) -> None:
    for index, existing in enumerate(items):
        if existing.get(key) == item[key]:
            created_at_ms = existing.get("created_at_ms")
            merged = dict(existing)
            merged.update(item)
            if created_at_ms is not None:
                merged["created_at_ms"] = created_at_ms
            items[index] = merged
            return
    items.append(item)


def _find_by_id(items: list[dict], key: str, value: str) -> dict:
    found = _find_optional(items, key, value)
    if found is None:
        raise KeyError(f"{key} not found: {value}")
    return found


def _find_optional(items: list[dict], key: str, value: object) -> Optional[dict]:
    value = str(value or "").strip()
    for item in items:
        if isinstance(item, dict) and item.get(key) == value:
            return dict(item)
    return None


def _job_order_key(job: dict) -> tuple[int, int]:
    return (-_as_int(job.get("priority"), 50), _as_int(job.get("sequence"), 0))


def _normalize_required_id(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} cannot be empty")
    return text


def _normalize_choice(
    value: object,
    allowed: set[str],
    default: str,
    label: str,
) -> str:
    normalized = str(value or default).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in allowed:
        raise ValueError(f"{label} must be one of {sorted(allowed)}")
    return normalized


def _normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _as_dict(value) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value) -> list:
    return list(value) if isinstance(value, list) else []


def _as_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_float(
    value,
    fallback: float,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        out = fallback
    if minimum is not None:
        out = max(minimum, out)
    if maximum is not None:
        out = min(maximum, out)
    return out


def _projects_dir() -> Path:
    return Path(_PROJECTS_DIR) if _PROJECTS_DIR is not None else livepilot_projects_dir()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

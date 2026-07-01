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
from .track_annotations import annotation_project_id_for_session


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
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
        self._base_dir = base_dir or _PROJECTS_DIR

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
        cockpit_context: Optional[dict] = None,
        section_map: Optional[list[dict]] = None,
        layer_groups: Optional[list[dict]] = None,
        track_intent_map: Optional[dict] = None,
    ) -> dict:
        store = self.store_for_session(session_info)
        snapshot = store.save_snapshot({
            "project_id": store.project_id,
            "project_revision": store.get_revision(),
            "brief": brief or {},
            "session_kernel": session_kernel or {},
            "cockpit_context": cockpit_context or {},
            "section_map": section_map or [],
            "layer_groups": layer_groups or [],
            "track_intent_map": track_intent_map or {},
        })
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
        base = base_dir or _PROJECTS_DIR
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
    item.setdefault("snapshot_id", _new_id("snap"))
    item["snapshot_id"] = _normalize_required_id(item["snapshot_id"], "snapshot_id")
    item["project_id"] = str(item.get("project_id") or project_id)
    item["project_revision"] = _as_int(item.get("project_revision"), 0)
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = _as_int(item.get("created_at_ms"), now)
    item["brief"] = _as_dict(item.get("brief"))
    item["session_kernel"] = _as_dict(item.get("session_kernel"))
    item["cockpit_context"] = _as_dict(item.get("cockpit_context"))
    item["section_map"] = _as_list(item.get("section_map"))
    item["layer_groups"] = _as_list(item.get("layer_groups"))
    item["track_intent_map"] = _as_dict(item.get("track_intent_map"))
    return item


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


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

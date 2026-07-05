"""Project-scoped cockpit brief ledger and reader stamps."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .paths import livepilot_projects_dir
from .track_annotations import annotation_project_id_for_session


_PROJECTS_DIR: Optional[Path] = None
_BRIEF_STORE_VERSION = 1
_READER_STORE_VERSION = 1
_STATUS_ORDER = [
    "saved",
    "seen",
    "queued",
    "running",
    "awaiting_decision",
    "done",
    "abandoned",
    "deleted",
    "failed",
]
_TERMINAL_OUTCOME_STATUSES = {"done", "abandoned", "deleted"}


class BriefService:
    """Read/write cockpit briefs for one Live project."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _projects_dir()

    def store_for_session(self, session_info: dict) -> "BriefStore":
        return BriefStore(
            annotation_project_id_for_session(session_info, self._base_dir),
            self._base_dir,
        )

    def create_brief(
        self,
        session_info: dict,
        *,
        request_text: str,
        context_digest: Optional[dict] = None,
        source: str = "cockpit",
        parent_brief_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        store = self.store_for_session(session_info)
        brief = store.create_brief({
            "request_text": request_text,
            "context_digest": context_digest or {},
            "source": source,
            "parent_brief_id": parent_brief_id,
            "thread_id": thread_id,
        })
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "brief": brief,
        }

    def attach_artifacts(
        self,
        session_info: dict,
        brief_id: str,
        *,
        snapshot_id: str = "",
        task_id: str = "",
        job_ids: Optional[list[str]] = None,
    ) -> dict:
        store = self.store_for_session(session_info)
        brief = store.attach_artifacts(
            brief_id,
            snapshot_id=snapshot_id,
            task_id=task_id,
            job_ids=job_ids or [],
        )
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "brief": brief,
        }

    def delete_brief(self, session_info: dict, brief_id: str) -> dict:
        store = self.store_for_session(session_info)
        brief = store.delete_brief(brief_id)
        deleted = bool(brief)
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "brief_id": str(brief_id or "").strip(),
            "deleted": deleted,
            "brief": brief,
        }

    def record_dispatch(
        self,
        session_info: dict,
        brief_id: str,
        *,
        method: str,
        codex_thread_id: str = "",
    ) -> dict:
        store = self.store_for_session(session_info)
        brief = store.record_dispatch(
            brief_id,
            method=method,
            codex_thread_id=codex_thread_id,
        )
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "brief": brief,
        }

    def capture_dispatch_thread_id(
        self,
        session_info: dict,
        brief_id: str,
        *,
        codex_thread_id: str,
    ) -> dict:
        store = self.store_for_session(session_info)
        brief = store.capture_dispatch_thread_id(
            brief_id,
            codex_thread_id=codex_thread_id,
        )
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "brief": brief,
        }

    def complete_brief(
        self,
        session_info: dict,
        brief_id: str,
        *,
        status: str,
        summary: str = "",
        learnings_count: int = 0,
    ) -> dict:
        store = self.store_for_session(session_info)
        brief = store.complete_brief(
            brief_id,
            status=status,
            summary=summary,
            learnings_count=learnings_count,
        )
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "brief": brief,
        }

    def list_briefs(
        self,
        session_info: dict,
        *,
        limit: int = 20,
        status: str = "",
        orchestration_state: Optional[dict] = None,
    ) -> dict:
        store = self.store_for_session(session_info)
        items = store.list_briefs()
        tasks = []
        jobs = []
        if isinstance(orchestration_state, dict):
            tasks = list(orchestration_state.get("tasks") or [])
            jobs = list(orchestration_state.get("jobs") or [])
        enriched = [
            _with_status(brief, tasks=tasks, jobs=jobs)
            for brief in items
        ]
        if status:
            wanted = str(status).strip().lower()
            enriched = [item for item in enriched if item.get("status") == wanted]
        bounded = max(1, min(100, int(limit or 20)))
        enriched = sorted(
            enriched,
            key=lambda item: int(item.get("created_at_ms") or 0),
            reverse=True,
        )[:bounded]
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.briefs_path),
            "briefs": enriched,
            "brief_count": len(enriched),
            "codex_last_read_ms": store.reader_state().get("codex_last_read_ms", 0),
        }

    def stamp_reader(self, session_info: dict, reader: str) -> dict:
        store = self.store_for_session(session_info)
        return store.stamp_reader(reader)

    def reader_state(self, session_info: dict) -> dict:
        return self.store_for_session(session_info).reader_state()


class BriefStore:
    """Atomic JSON stores for one project's briefs and reader stamps."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _projects_dir()
        self._project_id = project_id
        self._briefs = PersistentJsonStore(base / project_id / "briefs.json")
        self._readers = PersistentJsonStore(base / project_id / "reader_stamps.json")

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def briefs_path(self) -> Path:
        return self._briefs.path

    @property
    def readers_path(self) -> Path:
        return self._readers.path

    def get_all(self) -> dict:
        data = self._briefs.read()
        return (
            data if data.get("version") == _BRIEF_STORE_VERSION
            else self._brief_default()
        )

    def list_briefs(self, *, include_hidden: bool = False) -> list[dict]:
        items = list(self.get_all().get("briefs") or [])
        if include_hidden:
            return items
        return [item for item in items if not item.get("hidden")]

    def create_brief(self, brief: dict) -> dict:
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            seq = int(data.get("next_seq") or 1)
            normalized = _normalize_brief(brief, now=now, seq=seq)
            data.setdefault("briefs", []).append(normalized)
            data["next_seq"] = seq + 1
            data["last_updated_ms"] = now
            return data

        data = self._briefs.update(_update)
        return data.get("briefs", [])[-1]

    def attach_artifacts(
        self,
        brief_id: str,
        *,
        snapshot_id: str = "",
        task_id: str = "",
        job_ids: Optional[list[str]] = None,
    ) -> dict:
        brief_id = str(brief_id or "").strip()
        if not brief_id:
            raise ValueError("brief_id is required")
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            for item in data.get("briefs", []):
                if item.get("brief_id") != brief_id:
                    continue
                if snapshot_id:
                    item["snapshot_id"] = str(snapshot_id)
                if task_id:
                    item["task_id"] = str(task_id)
                merged_job_ids = _normalize_string_list(item.get("job_ids"))
                for job_id in _normalize_string_list(job_ids):
                    if job_id not in merged_job_ids:
                        merged_job_ids.append(job_id)
                item["job_ids"] = merged_job_ids
                item["updated_at_ms"] = now
                data["last_updated_ms"] = now
                return data
            raise KeyError(f"brief_id not found: {brief_id}")

        data = self._briefs.update(_update)
        return _find_brief(data, brief_id)

    def delete_brief(self, brief_id: str) -> Optional[dict]:
        brief_id = str(brief_id or "").strip()
        if not brief_id:
            return None
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            for item in data.get("briefs", []):
                if item.get("brief_id") != brief_id:
                    continue
                item["hidden"] = True
                item["deleted_at_ms"] = now
                item["outcome"] = {
                    "status": "deleted",
                    "at_ms": now,
                    "summary": "deleted from cockpit",
                    "learnings_count": 0,
                }
                item["updated_at_ms"] = now
                data["last_updated_ms"] = now
                return data
            raise KeyError(f"brief_id not found: {brief_id}")

        data = self._briefs.update(_update)
        return _find_brief(data, brief_id)

    def record_dispatch(
        self,
        brief_id: str,
        *,
        method: str,
        codex_thread_id: str = "",
    ) -> dict:
        brief_id = str(brief_id or "").strip()
        method = _normalize_dispatch_method(method)
        codex_thread_id = str(codex_thread_id or "").strip()
        if not brief_id:
            raise ValueError("brief_id is required")
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            for item in data.get("briefs", []):
                if item.get("brief_id") != brief_id:
                    continue
                item["dispatch"] = {
                    "method": method,
                    "at_ms": now,
                }
                if codex_thread_id:
                    item["dispatch"]["codex_thread_id"] = codex_thread_id
                item["updated_at_ms"] = now
                data["last_updated_ms"] = now
                return data
            raise KeyError(f"brief_id not found: {brief_id}")

        data = self._briefs.update(_update)
        return _find_brief(data, brief_id)

    def capture_dispatch_thread_id(
        self,
        brief_id: str,
        *,
        codex_thread_id: str,
    ) -> dict:
        brief_id = str(brief_id or "").strip()
        codex_thread_id = str(codex_thread_id or "").strip()
        if not brief_id:
            raise ValueError("brief_id is required")
        if not codex_thread_id:
            raise ValueError("codex_thread_id is required")
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            for item in data.get("briefs", []):
                if item.get("brief_id") != brief_id:
                    continue
                dispatch = item.get("dispatch")
                if not isinstance(dispatch, dict):
                    raise ValueError(f"brief has no dispatch: {brief_id}")
                dispatch["codex_thread_id"] = codex_thread_id
                item["updated_at_ms"] = now
                data["last_updated_ms"] = now
                return data
            raise KeyError(f"brief_id not found: {brief_id}")

        data = self._briefs.update(_update)
        return _find_brief(data, brief_id)

    def complete_brief(
        self,
        brief_id: str,
        *,
        status: str,
        summary: str = "",
        learnings_count: int = 0,
    ) -> dict:
        brief_id = str(brief_id or "").strip()
        outcome_status = _normalize_outcome_status(status)
        if not brief_id:
            raise ValueError("brief_id is required")
        now = _now_ms()

        def _update(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            for item in data.get("briefs", []):
                if item.get("brief_id") != brief_id:
                    continue
                item["outcome"] = {
                    "status": outcome_status,
                    "at_ms": now,
                    "summary": str(summary or "").strip(),
                    "learnings_count": max(0, int(learnings_count or 0)),
                }
                item["updated_at_ms"] = now
                data["last_updated_ms"] = now
                return data
            raise KeyError(f"brief_id not found: {brief_id}")

        data = self._briefs.update(_update)
        return _find_brief(data, brief_id)

    def stamp_reader(self, reader: str) -> dict:
        now = _now_ms()
        reader = str(reader or "reader").strip() or "reader"

        def _update_readers(data: dict) -> dict:
            data = (
                data if data.get("version") == _READER_STORE_VERSION
                else self._reader_default()
            )
            readers = data.setdefault("readers", {})
            readers[reader] = now
            data["last_updated_ms"] = now
            return data

        self._readers.update(_update_readers)

        def _mark_seen(data: dict) -> dict:
            data = (
                data if data.get("version") == _BRIEF_STORE_VERSION
                else self._brief_default()
            )
            changed = False
            for item in data.get("briefs", []):
                if item.get("seen_at_ms") is None:
                    item["seen_at_ms"] = now
                    item["updated_at_ms"] = now
                    changed = True
            if changed:
                data["last_updated_ms"] = now
            return data

        self._briefs.update(_mark_seen)
        return self.reader_state()

    def reader_state(self) -> dict:
        data = self._readers.read()
        if data.get("version") != _READER_STORE_VERSION:
            data = self._reader_default()
        readers = dict(data.get("readers") or {})
        return {
            "status": "ok",
            "project_id": self.project_id,
            "store_path": str(self.readers_path),
            "readers": readers,
            "codex_last_read_ms": max(readers.values()) if readers else 0,
        }

    @staticmethod
    def _brief_default() -> dict:
        return {
            "version": _BRIEF_STORE_VERSION,
            "next_seq": 1,
            "briefs": [],
            "last_updated_ms": 0,
        }

    @staticmethod
    def _reader_default() -> dict:
        return {
            "version": _READER_STORE_VERSION,
            "readers": {},
            "last_updated_ms": 0,
        }


def stamp_reader_for_context(ctx, reader: str) -> dict:
    """Best-effort reader stamp helper for MCP read tools."""
    try:
        lifespan = getattr(ctx, "lifespan_context", {}) or {}
        if lifespan.get("_suppress_brief_reader_stamp"):
            return {}
        ableton = lifespan.get("ableton")
        if ableton is None:
            return {}
        session_info = ableton.send_command("get_session_info")
        if not isinstance(session_info, dict) or session_info.get("error"):
            return {}
        service = lifespan.get("briefs")
        if not isinstance(service, BriefService):
            service = BriefService()
        return service.stamp_reader(session_info, reader)
    except Exception:
        return {}


def brief_status(brief: dict, tasks: list[dict], jobs: list[dict]) -> dict:
    """Derive a cockpit brief status from linked queue objects."""
    brief_id = str(brief.get("brief_id") or "")
    linked_task_id = str(brief.get("task_id") or "")
    linked_job_ids = set(_normalize_string_list(brief.get("job_ids")))
    related_tasks = [
        task for task in tasks
        if _task_matches_brief(task, brief_id, linked_task_id)
    ]
    related_jobs = [
        job for job in jobs
        if _job_matches_brief(job, brief_id, linked_job_ids)
    ]
    outcome = _normalize_outcome(brief.get("outcome"))
    if outcome:
        trail = ["saved"]
        if brief.get("seen_at_ms") is not None:
            trail.append("seen")
        trail.append(outcome["status"])
        return {
            "status": outcome["status"],
            "status_trail": trail,
            "related_task_count": len(related_tasks),
            "related_job_count": len(related_jobs),
            "related_tasks": [
                _compact_task(task) for task in related_tasks
            ],
            "related_jobs": [
                _compact_job(job) for job in related_jobs
            ],
        }
    statuses = []
    if brief.get("seen_at_ms") is not None:
        statuses.append("seen")
    statuses.extend(_normalize_runtime_status(task.get("status")) for task in related_tasks)
    statuses.extend(_normalize_runtime_status(job.get("status")) for job in related_jobs)
    statuses = [status for status in statuses if status]
    status = _max_status(statuses) if statuses else "saved"
    trail = ["saved"]
    if brief.get("seen_at_ms") is not None:
        trail.append("seen")
    if status not in trail:
        trail.append(status)
    return {
        "status": status,
        "status_trail": trail,
        "related_task_count": len(related_tasks),
        "related_job_count": len(related_jobs),
        "related_tasks": [
            _compact_task(task) for task in related_tasks
        ],
        "related_jobs": [
            _compact_job(job) for job in related_jobs
        ],
    }


def _with_status(brief: dict, *, tasks: list[dict], jobs: list[dict]) -> dict:
    item = dict(brief)
    item.update(brief_status(brief, tasks, jobs))
    return item


def _normalize_brief(brief: dict, *, now: int, seq: int) -> dict:
    item = dict(brief or {})
    brief_id = str(item.get("brief_id") or f"brief_{uuid.uuid4().hex[:12]}")
    item["brief_id"] = brief_id
    item["seq"] = int(item.get("seq") or seq)
    item["thread_id"] = str(item.get("thread_id") or brief_id)
    item["parent_brief_id"] = (
        str(item.get("parent_brief_id")).strip()
        if item.get("parent_brief_id") else None
    )
    item["source"] = str(item.get("source") or "cockpit").strip()
    item["request_text"] = str(item.get("request_text") or "").strip()
    item["context_digest"] = (
        item.get("context_digest")
        if isinstance(item.get("context_digest"), dict) else {}
    )
    item["snapshot_id"] = str(item.get("snapshot_id") or "")
    item["task_id"] = str(item.get("task_id") or "")
    item["job_ids"] = _normalize_string_list(item.get("job_ids"))
    if isinstance(item.get("dispatch"), dict):
        dispatch = item["dispatch"]
        method = str(dispatch.get("method") or "").strip()
        at_ms = dispatch.get("at_ms")
        if method and isinstance(at_ms, int):
            item["dispatch"] = {"method": method, "at_ms": at_ms}
            codex_thread_id = str(dispatch.get("codex_thread_id") or "").strip()
            if codex_thread_id:
                item["dispatch"]["codex_thread_id"] = codex_thread_id
        else:
            item.pop("dispatch", None)
    else:
        item.pop("dispatch", None)
    outcome = _normalize_outcome(item.get("outcome"))
    if outcome:
        item["outcome"] = outcome
    else:
        item.pop("outcome", None)
    item["hidden"] = bool(item.get("hidden"))
    if item.get("deleted_at_ms") is not None:
        try:
            item["deleted_at_ms"] = int(item.get("deleted_at_ms") or 0)
        except (TypeError, ValueError):
            item.pop("deleted_at_ms", None)
    item.setdefault("created_at_ms", now)
    item["created_at_ms"] = int(item.get("created_at_ms") or now)
    item["updated_at_ms"] = now
    item["seen_at_ms"] = item.get("seen_at_ms")
    return item


def _task_matches_brief(task: dict, brief_id: str, linked_task_id: str) -> bool:
    if linked_task_id and task.get("task_id") == linked_task_id:
        return True
    return (
        _dict_has_brief_id(task.get("scope"), brief_id)
        or _dict_has_brief_id(task.get("constraints"), brief_id)
    )


def _job_matches_brief(job: dict, brief_id: str, linked_job_ids: set[str]) -> bool:
    if job.get("job_id") in linked_job_ids:
        return True
    return _dict_has_brief_id(job.get("scope"), brief_id)


def _dict_has_brief_id(value, brief_id: str) -> bool:
    return isinstance(value, dict) and bool(brief_id) and value.get("brief_id") == brief_id


def _normalize_runtime_status(value) -> str:
    status = str(value or "").strip().lower()
    if status == "awaiting_decision":
        return "awaiting_decision"
    if status in {"running", "queued", "failed"}:
        return status
    if status in {"done", "canceled"}:
        return "done"
    return ""


def _max_status(statuses: list[str]) -> str:
    if not statuses:
        return "saved"
    return max(
        statuses,
        key=lambda status: _STATUS_ORDER.index(status)
        if status in _STATUS_ORDER else 0,
    )


def _compact_task(task: dict) -> dict:
    return {
        "task_id": task.get("task_id", ""),
        "agent_role": task.get("agent_role", ""),
        "status": task.get("status", ""),
        "instruction": task.get("instruction", ""),
    }


def _compact_job(job: dict) -> dict:
    return {
        "job_id": job.get("job_id", ""),
        "title": job.get("title", ""),
        "job_type": job.get("job_type", ""),
        "status": job.get("status", ""),
        "audition_manifest": job.get("audition_manifest"),
        "plan": job.get("plan") or [],
    }


def _normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _normalize_dispatch_method(value: str) -> str:
    method = str(value or "").strip().lower()
    if method in {"deeplink", "copy_prompt", "deeplink_existing"}:
        return method
    raise ValueError(
        "dispatch method must be 'deeplink', 'copy_prompt', or 'deeplink_existing'"
    )


def _normalize_outcome_status(value: str) -> str:
    status = str(value or "").strip().lower()
    if status in _TERMINAL_OUTCOME_STATUSES:
        return status
    raise ValueError("brief outcome status must be 'done', 'abandoned', or 'deleted'")


def _normalize_outcome(value) -> Optional[dict]:
    if not isinstance(value, dict):
        return None
    try:
        status = _normalize_outcome_status(value.get("status"))
    except ValueError:
        return None
    try:
        at_ms = int(value.get("at_ms") or 0)
    except (TypeError, ValueError):
        at_ms = 0
    try:
        learnings_count = max(0, int(value.get("learnings_count") or 0))
    except (TypeError, ValueError):
        learnings_count = 0
    return {
        "status": status,
        "at_ms": at_ms,
        "summary": str(value.get("summary") or "").strip(),
        "learnings_count": learnings_count,
    }


def _projects_dir() -> Path:
    return Path(_PROJECTS_DIR) if _PROJECTS_DIR is not None else livepilot_projects_dir()


def _find_brief(data: dict, brief_id: str) -> dict:
    for item in data.get("briefs", []):
        if item.get("brief_id") == brief_id:
            return item
    raise KeyError(f"brief_id not found: {brief_id}")


def _now_ms() -> int:
    return int(time.time() * 1000)

"""Project-scoped production workflow context for the Codex cockpit.

Track annotations answer "what is this track for?". This store answers the
current human/agent working stance: which lane is active, whether audition is
required before committing, and which constraints should be treated as
session-level guardrails.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base_store import PersistentJsonStore
from .track_annotations import annotation_project_id_for_session


_PROJECTS_DIR = Path.home() / ".livepilot" / "projects"
_STORE_VERSION = 1

_VALID_LANES = {"holistic", "composition", "sound_design", "mix"}
_VALID_WORKFLOW_MODES = {"observe", "guided", "audition", "commit"}
_VALID_AUDITION_SCOPES = {"layer"}
_VALID_SECTION_SCOPES = {
    "whole_song",
    "intro",
    "verse_1",
    "verse_2",
    "chorus",
    "bridge",
    "custom",
}
_VALID_TARGET_MODES = {"instrument", "layer", "query"}
_VALID_PROTECT_FLAGS = {
    "preserve_arrangement",
    "preserve_notes",
    "preserve_timing",
    "preserve_sound",
    "preserve_level",
    "preserve_vocal",
    "preserve_groove",
}


class ProductionContextService:
    """Read/write project-scoped production cockpit state."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _PROJECTS_DIR

    def get_state(self, session_info: dict) -> dict:
        store = self._store_for_session(session_info)
        raw = store.get_state()
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "state": raw,
        }

    def save_state(
        self,
        session_info: dict,
        lane: Optional[str] = None,
        workflow_mode: Optional[str] = None,
        audition_required: Optional[bool] = None,
        audition_count: Optional[int] = None,
        audition_scope: Optional[str] = None,
        protect: Optional[list[str]] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        target_query: Optional[str] = None,
        target_group: Optional[str] = None,
        target_mode: Optional[str] = None,
        target_layer: Optional[str] = None,
        section_scope: Optional[str] = None,
        section_label: Optional[str] = None,
        section_start_bar: Optional[float] = None,
        section_end_bar: Optional[float] = None,
    ) -> dict:
        store = self._store_for_session(session_info)
        state = store.save_state(
            lane=lane,
            workflow_mode=workflow_mode,
            audition_required=audition_required,
            audition_count=audition_count,
            audition_scope=audition_scope,
            protect=protect,
            reference=reference,
            notes=notes,
            target_query=target_query,
            target_group=target_group,
            target_mode=target_mode,
            target_layer=target_layer,
            section_scope=section_scope,
            section_label=section_label,
            section_start_bar=section_start_bar,
            section_end_bar=section_end_bar,
        )
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "state": state,
        }

    def clear_state(self, session_info: dict) -> dict:
        store = self._store_for_session(session_info)
        state = store.clear_state()
        return {
            "status": "ok",
            "project_id": store.project_id,
            "store_path": str(store.path),
            "state": state,
        }

    def _store_for_session(self, session_info: dict) -> "ProductionContextStore":
        return ProductionContextStore(
            annotation_project_id_for_session(session_info, self._base_dir),
            self._base_dir,
        )


class ProductionContextStore:
    """Atomic JSON store for one project's production cockpit state."""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        base = base_dir or _PROJECTS_DIR
        self._store = PersistentJsonStore(base / project_id / "production_context.json")
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

    def get_state(self) -> dict:
        return dict(self.get_all().get("state") or self._default_state())

    def save_state(
        self,
        lane: Optional[str] = None,
        workflow_mode: Optional[str] = None,
        audition_required: Optional[bool] = None,
        audition_count: Optional[int] = None,
        audition_scope: Optional[str] = None,
        protect: Optional[list[str]] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        target_query: Optional[str] = None,
        target_group: Optional[str] = None,
        target_mode: Optional[str] = None,
        target_layer: Optional[str] = None,
        section_scope: Optional[str] = None,
        section_label: Optional[str] = None,
        section_start_bar: Optional[float] = None,
        section_end_bar: Optional[float] = None,
    ) -> dict:
        now = int(time.time() * 1000)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            state = dict(data.get("state") or self._default_state())
            if lane is not None:
                state["lane"] = _normalize_lane(lane)
            if workflow_mode is not None:
                state["workflow_mode"] = _normalize_workflow_mode(workflow_mode)
            if audition_required is not None:
                state["audition_required"] = bool(audition_required)
            if audition_count is not None:
                state["audition_count"] = _normalize_audition_count(audition_count)
            if audition_scope is not None:
                state["audition_scope"] = _normalize_audition_scope(audition_scope)
            if protect is not None:
                state["protect"] = _normalize_protect_flags(protect)
            if reference is not None:
                state["reference"] = str(reference).strip()
            if notes is not None:
                state["notes"] = str(notes).strip()
            if target_query is not None:
                state["target_query"] = str(target_query).strip()
            if target_group is not None:
                state["target_group"] = _normalize_key(target_group)
            if target_mode is not None:
                state["target_mode"] = _normalize_target_mode(target_mode)
            if target_layer is not None:
                state["target_layer"] = _normalize_key(target_layer)
            if section_scope is not None:
                normalized_scope = _normalize_section_scope(section_scope)
                state["section_scope"] = normalized_scope
                if normalized_scope != "custom":
                    state["section_start_bar"] = None
                    state["section_end_bar"] = None
            if section_label is not None:
                state["section_label"] = str(section_label).strip()
            if section_start_bar is not None:
                state["section_start_bar"] = _normalize_optional_float(section_start_bar)
            if section_end_bar is not None:
                state["section_end_bar"] = _normalize_optional_float(section_end_bar)
            state["updated_at_ms"] = now
            data["state"] = state
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return dict(data.get("state") or self._default_state())

    def clear_state(self) -> dict:
        now = int(time.time() * 1000)

        def _update(data: dict) -> dict:
            data = data if data.get("version") == _STORE_VERSION else self._default()
            data["state"] = self._default_state()
            data["last_updated_ms"] = now
            return data

        data = self._store.update(_update)
        return dict(data.get("state") or self._default_state())

    @staticmethod
    def _default_state() -> dict:
        return {
            "lane": "holistic",
            "workflow_mode": "guided",
            "audition_required": True,
            "audition_count": 3,
            "audition_scope": "layer",
            "protect": [],
            "reference": "",
            "notes": "",
            "target_query": "",
            "target_group": "",
            "target_mode": "instrument",
            "target_layer": "",
            "section_scope": "whole_song",
            "section_label": "Whole song",
            "section_start_bar": None,
            "section_end_bar": None,
            "updated_at_ms": 0,
        }

    @classmethod
    def _default(cls) -> dict:
        return {
            "version": _STORE_VERSION,
            "state": cls._default_state(),
            "last_updated_ms": 0,
        }


def _normalize_lane(value: str) -> str:
    lane = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if lane not in _VALID_LANES:
        raise ValueError(
            "lane must be one of: " + ", ".join(sorted(_VALID_LANES))
        )
    return lane


def _normalize_workflow_mode(value: str) -> str:
    mode = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if mode not in _VALID_WORKFLOW_MODES:
        raise ValueError(
            "workflow_mode must be one of: "
            + ", ".join(sorted(_VALID_WORKFLOW_MODES))
        )
    return mode


def _normalize_audition_count(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("audition_count must be an integer") from exc
    if count < 1 or count > 8:
        raise ValueError("audition_count must be between 1 and 8")
    return count


def _normalize_audition_scope(value: str) -> str:
    scope = _normalize_key(value)
    if scope not in _VALID_AUDITION_SCOPES:
        raise ValueError(
            "audition_scope must be one of: "
            + ", ".join(sorted(_VALID_AUDITION_SCOPES))
        )
    return scope


def _normalize_target_mode(value: str) -> str:
    mode = _normalize_key(value)
    if mode not in _VALID_TARGET_MODES:
        raise ValueError(
            "target_mode must be one of: "
            + ", ".join(sorted(_VALID_TARGET_MODES))
        )
    return mode


def _normalize_section_scope(value: str) -> str:
    scope = _normalize_key(value)
    if scope not in _VALID_SECTION_SCOPES:
        raise ValueError(
            "section_scope must be one of: "
            + ", ".join(sorted(_VALID_SECTION_SCOPES))
        )
    return scope


def _normalize_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_optional_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("section bar values must be numbers") from exc


def _normalize_protect_flags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, list):
        raise ValueError("protect must be a list or comma-separated string")
    out: list[str] = []
    for item in value:
        flag = str(item or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not flag:
            continue
        if flag not in _VALID_PROTECT_FLAGS:
            raise ValueError(
                "protect flags must be one of: "
                + ", ".join(sorted(_VALID_PROTECT_FLAGS))
            )
        if flag not in out:
            out.append(flag)
    return out

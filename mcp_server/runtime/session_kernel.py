"""SessionKernel — the canonical turn snapshot for V2 orchestration.

Assembles project brain, capability state, action ledger, taste profile,
anti-preferences, and session memory into one unified object. This is the
single source of truth for any complex agentic workflow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class SessionKernel:
    """Immutable turn snapshot. Built once per complex request."""

    kernel_id: str
    request_text: str = ""
    mode: str = "improve"  # observe | improve | explore | finish | diagnose
    aggression: float = 0.5

    # Session topology
    tempo: float = 120.0
    track_count: int = 0
    session_info: dict = field(default_factory=dict)

    # Capability state
    capability_state: dict = field(default_factory=dict)

    # Action ledger
    ledger_summary: dict = field(default_factory=dict)

    # Memory
    session_memory: list = field(default_factory=list)
    taste_graph: dict = field(default_factory=dict)
    anti_preferences: list = field(default_factory=list)

    # Protection
    protected_dimensions: dict = field(default_factory=dict)

    # Routing hints (filled by conductor)
    recommended_engines: list = field(default_factory=list)
    recommended_workflow: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_session_kernel(
    session_info: dict,
    capability_state: dict,
    request_text: str = "",
    mode: str = "improve",
    aggression: float = 0.5,
    ledger_summary: Optional[dict] = None,
    session_memory: Optional[list] = None,
    taste_graph: Optional[dict] = None,
    anti_preferences: Optional[list] = None,
    protected_dimensions: Optional[dict] = None,
) -> SessionKernel:
    """Build a SessionKernel from raw data.

    All optional fields degrade gracefully to empty defaults.
    The kernel_id is deterministic from the core inputs so it's stable
    within the same turn context.
    """
    # Deterministic kernel_id from inputs
    id_seed = json.dumps(
        {
            "tempo": session_info.get("tempo"),
            "track_count": session_info.get("track_count"),
            "request": request_text,
            "mode": mode,
        },
        sort_keys=True,
    )
    kernel_id = hashlib.sha256(id_seed.encode()).hexdigest()[:12]

    return SessionKernel(
        kernel_id=kernel_id,
        request_text=request_text,
        mode=mode,
        aggression=aggression,
        tempo=session_info.get("tempo", 120.0),
        track_count=session_info.get("track_count", 0),
        session_info=session_info,
        capability_state=capability_state,
        ledger_summary=ledger_summary or {},
        session_memory=session_memory or [],
        taste_graph=taste_graph or {},
        anti_preferences=anti_preferences or [],
        protected_dimensions=protected_dimensions or {},
    )

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

    # ── Creative controls (PR2 — branch-native migration) ──────────────
    # All optional. Producers (Wonder, synthesis_brain, composer) read these
    # to bias branch generation. Pre-PR2 callers leave them at defaults and
    # nothing changes. PR6 (Wonder refactor) and PR9 (synthesis_brain) start
    # reading them in earnest.

    # 0.0 = conservative / don't surprise me; 1.0 = surprise me.
    # Distinct from aggression (which is about execution boldness).
    freshness: float = 0.5

    # Shorthand producer philosophy tag. The sample_engine already uses
    # "surgeon" / "alchemist" (see livepilot-sample-engine); synth work
    # may add "sculptor". Empty string = producer picks a default.
    creativity_profile: str = ""

    # Caller-asserted sacred elements. Normally sacred elements come from
    # song_brain; this lets the user or a skill override. Shape matches
    # song_brain.sacred_elements entries: {element_type, description, salience}.
    sacred_elements: list = field(default_factory=list)

    # Hints for synthesis_brain: which tracks/devices to focus on and what
    # target timbre to aim for. Shape is open in PR2 and will be firmed up
    # when PR9 adds the first adapters.
    #   {
    #     "track_indices": [int, ...],
    #     "device_paths":  ["track/Wavetable", ...],
    #     "target_timbre": {"brightness": +0.3, "width": +0.2, ...},
    #     "preferred_devices": ["Wavetable", "Operator", ...],
    #   }
    synth_hints: dict = field(default_factory=dict)

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
    # PR2 — creative controls. All optional; legacy callers unaffected.
    freshness: float = 0.5,
    creativity_profile: str = "",
    sacred_elements: Optional[list] = None,
    synth_hints: Optional[dict] = None,
) -> SessionKernel:
    """Build a SessionKernel from raw data.

    All optional fields degrade gracefully to empty defaults.
    The kernel_id is deterministic from the core inputs so it's stable
    within the same turn context.

    The PR2 creative-control fields (freshness, creativity_profile,
    sacred_elements, synth_hints) are intentionally excluded from the
    kernel_id hash so existing callers see no identity changes. Producers
    that need these fields to influence identity can compose their own
    derived id downstream.
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
        freshness=freshness,
        creativity_profile=creativity_profile,
        sacred_elements=sacred_elements or [],
        synth_hints=synth_hints or {},
    )

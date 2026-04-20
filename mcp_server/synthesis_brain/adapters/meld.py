"""Meld adapter — Ableton 12's newest FM/granular hybrid.

Meld pairs two "Engines" with per-engine algorithms and a shared
modulation / amp / filter section. PR10 ships one canned proposer:
engine_algo_swap — changes Engine 1's algorithm to produce a
materially different core timbre without disturbing the envelope
or filter. Later PRs add engine-blend, unison, and modulation-matrix
variants.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from ...branches import BranchSeed, freeform_seed
from ..models import (
    SynthProfile,
    TimbralFingerprint,
    ModulationGraph,
    ArticulationProfile,
    NATIVE,
)
from .base import register_adapter


_KNOWN_PARAMS = {
    "Engine 1 Algorithm",
    "Engine 2 Algorithm",
    "Engine 1 Level",
    "Engine 2 Level",
    "Engine 1 Morph",
    "Engine 2 Morph",
    "Filter Freq",
    "Filter Res",
    "Amp A",
    "Amp D",
    "Amp S",
    "Amp R",
}


@register_adapter
class MeldAdapter:
    device_name: str = "Meld"

    def extract_profile(
        self,
        track_index: int,
        device_index: int,
        parameter_state: dict,
        display_values: Optional[dict] = None,
        role_hint: str = "",
    ) -> SynthProfile:
        notes: list[str] = []

        e1_algo = parameter_state.get("Engine 1 Algorithm")
        e2_algo = parameter_state.get("Engine 2 Algorithm")
        if e1_algo is not None and e2_algo is not None and e1_algo == e2_algo:
            notes.append(
                "Both Engines on same algorithm — consider differentiating for depth"
            )

        articulation = ArticulationProfile(
            attack_ms=float(parameter_state.get("Amp A", 0.0) or 0.0),
            release_ms=float(parameter_state.get("Amp R", 0.0) or 0.0),
        )

        mod = ModulationGraph()
        # Meld has many internal mod routes; PR10 just records engine levels
        # as rough "sources" so downstream can see the mix balance.
        e1_level = parameter_state.get("Engine 1 Level", 0.0)
        e2_level = parameter_state.get("Engine 2 Level", 0.0)
        if e1_level and e1_level > 0:
            mod.routes.append({"source": "Engine 1", "target": "output", "amount": e1_level})
        if e2_level and e2_level > 0:
            mod.routes.append({"source": "Engine 2", "target": "output", "amount": e2_level})

        focused_state = {k: v for k, v in parameter_state.items() if k in _KNOWN_PARAMS}
        focused_display = (
            {k: v for k, v in (display_values or {}).items() if k in _KNOWN_PARAMS}
            if display_values else {}
        )

        return SynthProfile(
            device_name=self.device_name,
            opacity=NATIVE,
            track_index=track_index,
            device_index=device_index,
            parameter_state=focused_state,
            display_values=focused_display,
            role_hint=role_hint,
            modulation=mod,
            articulation=articulation,
            notes=notes,
        )

    def propose_branches(
        self,
        profile: SynthProfile,
        target: TimbralFingerprint,
        kernel: Optional[dict] = None,
    ) -> list[tuple[BranchSeed, dict]]:
        kernel = kernel or {}
        freshness = float(kernel.get("freshness", 0.5) or 0.5)
        track = profile.track_index
        device = profile.device_index

        # Algorithm indices are device-internal; we propose a relative shift
        # by +1 (modulo a safe ceiling of 10 — Meld has 12 algos but we're
        # conservative). Freshness amplifies the shift to +3.
        current_algo = int(profile.parameter_state.get("Engine 1 Algorithm", 0) or 0)
        shift = 1 if freshness < 0.5 else 3
        new_algo = (current_algo + shift) % 10

        seed = freeform_seed(
            seed_id=_short_id("ml_algo", f"{track}:{device}:{new_algo}"),
            hypothesis=(
                f"Meld Engine 1 algorithm swap: {current_algo} → {new_algo} "
                f"for a materially different core timbre"
            ),
            source="synthesis",
            novelty_label="unexpected" if shift == 3 else "strong",
            risk_label="medium",
            affected_scope={
                "track_indices": [track],
                "device_paths": [f"track/{track}/device/{device}"],
            },
            distinctness_reason="only Meld seed that changes Engine 1 algorithm",
        )
        plan = {
            "steps": [
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "Engine 1 Algorithm",
                        "value": new_algo,
                    },
                },
            ],
            "step_count": 1,
            "summary": f"Engine 1 Algorithm {current_algo} → {new_algo}",
        }
        return [(seed, plan)]


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

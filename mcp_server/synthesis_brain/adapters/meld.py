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
        results: list[tuple[BranchSeed, dict]] = []
        for strategy_fn in (_strategy_engine_algo_swap, _strategy_engine_mix_shift):
            try:
                maybe = strategy_fn(profile, target, kernel, adapter=self)
            except Exception:
                continue
            if maybe is not None:
                results.append(maybe)
        return results


# ── Strategy registry ────────────────────────────────────────────────


def _strategy_engine_algo_swap(
    profile: SynthProfile,
    target: TimbralFingerprint,
    kernel: dict,
    adapter,
) -> Optional[tuple[BranchSeed, dict]]:
    """Shift Engine 1 Algorithm by +1 (low freshness) or +3 (high).

    Always applicable — algorithm swaps are guaranteed to change tone
    regardless of current state.
    """
    freshness = float(kernel.get("freshness", 0.5) or 0.5)
    track = profile.track_index
    device = profile.device_index
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
        distinctness_reason="changes Engine 1 algorithm",
        producer_payload={
            "device_name": adapter.device_name,
            "track_index": track,
            "device_index": device,
            "strategy": "engine_algo_swap",
            "topology_hint": {
                "role_hint": profile.role_hint,
                "current_algo": current_algo,
                "new_algo": new_algo,
            },
        },
    )
    plan = {
        "steps": [
            {"tool": "set_device_parameter",
             "params": {"track_index": track, "device_index": device,
                        "parameter_name": "Engine 1 Algorithm",
                        "value": new_algo}},
        ],
        "step_count": 1,
        "summary": f"Engine 1 Algorithm {current_algo} → {new_algo}",
    }
    return (seed, plan)


def _strategy_engine_mix_shift(
    profile: SynthProfile,
    target: TimbralFingerprint,
    kernel: dict,
    adapter,
) -> Optional[tuple[BranchSeed, dict]]:
    """Rebalance Engine 1 / Engine 2 Level for layered character.

    Gates: applicable when BOTH engines have non-zero Level (mix makes
    no sense if one engine is silent). Shifts the balance by 0.15-0.3
    depending on freshness.
    """
    e1 = float(profile.parameter_state.get("Engine 1 Level", 0.0) or 0.0)
    e2 = float(profile.parameter_state.get("Engine 2 Level", 0.0) or 0.0)
    if e1 < 0.05 or e2 < 0.05:
        return None  # one engine silent — mix shift is meaningless

    freshness = float(kernel.get("freshness", 0.5) or 0.5)
    track = profile.track_index
    device = profile.device_index

    # Push toward the engine with LESS level currently — highlights the
    # underused engine's character. When roughly equal, pick Engine 2.
    if e1 < e2:
        direction = "to_e1"
        delta = 0.15 if freshness < 0.5 else 0.3
        new_e1 = min(1.0, e1 + delta)
        new_e2 = max(0.0, e2 - delta / 2)
    else:
        direction = "to_e2"
        delta = 0.15 if freshness < 0.5 else 0.3
        new_e2 = min(1.0, e2 + delta)
        new_e1 = max(0.0, e1 - delta / 2)

    seed = freeform_seed(
        seed_id=_short_id(
            "ml_mix", f"{track}:{device}:{direction}:{new_e1:.2f}:{new_e2:.2f}"
        ),
        hypothesis=(
            f"Meld engine mix shift {direction}: E1 {e1:.2f} → {new_e1:.2f}, "
            f"E2 {e2:.2f} → {new_e2:.2f}"
        ),
        source="synthesis",
        novelty_label="strong",
        risk_label="low",
        affected_scope={
            "track_indices": [track],
            "device_paths": [f"track/{track}/device/{device}"],
        },
        distinctness_reason=(
            f"Meld mix rebalance {direction}; algorithm unchanged"
        ),
        producer_payload={
            "device_name": adapter.device_name,
            "track_index": track,
            "device_index": device,
            "strategy": f"engine_mix_shift_{direction}",
            "topology_hint": {
                "role_hint": profile.role_hint,
                "current_e1": e1,
                "current_e2": e2,
                "new_e1": round(new_e1, 3),
                "new_e2": round(new_e2, 3),
            },
        },
    )
    plan = {
        "steps": [
            {"tool": "set_device_parameter",
             "params": {"track_index": track, "device_index": device,
                        "parameter_name": "Engine 1 Level",
                        "value": round(new_e1, 3)}},
            {"tool": "set_device_parameter",
             "params": {"track_index": track, "device_index": device,
                        "parameter_name": "Engine 2 Level",
                        "value": round(new_e2, 3)}},
        ],
        "step_count": 2,
        "summary": f"E1 {e1:.2f}→{new_e1:.2f}, E2 {e2:.2f}→{new_e2:.2f}",
    }
    return (seed, plan)


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

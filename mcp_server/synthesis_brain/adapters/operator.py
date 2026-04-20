"""Operator adapter — native-synth-aware branch production for Ableton's Operator.

FM synthesis is defined by operator ratios + algorithm topology + per-op
envelopes. PR9 ships one canned proposer that shifts a carrier/modulator
ratio, which is the highest-leverage single parameter change for FM tone.
Later PRs add algorithm swaps, envelope reshaping, and feedback variants.
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
    "Algorithm",
    "Oscillator A Coarse",
    "Oscillator B Coarse",
    "Oscillator C Coarse",
    "Oscillator D Coarse",
    "Oscillator A Fine",
    "Oscillator B Fine",
    "Oscillator A Level",
    "Oscillator B Level",
    "Oscillator C Level",
    "Oscillator D Level",
    "Oscillator A Attack",
    "Oscillator A Release",
    "Filter Frequency",
    "Filter Resonance",
    "Time",  # global envelope time
}


@register_adapter
class OperatorAdapter:
    """Adapter for Ableton's native Operator."""

    device_name: str = "Operator"

    def extract_profile(
        self,
        track_index: int,
        device_index: int,
        parameter_state: dict,
        display_values: Optional[dict] = None,
        role_hint: str = "",
    ) -> SynthProfile:
        notes: list[str] = []

        algo = parameter_state.get("Algorithm", 0)
        if algo is not None:
            notes.append(f"Algorithm={algo} — topology governs which ops are carriers vs modulators")

        # Crude modulator-detection: any oscillator with Coarse > 1 and Level > 0
        # is acting as a modulator. Precise detection needs algorithm decoding,
        # which lands in PR10.
        mod_routes = []
        for op in ("A", "B", "C", "D"):
            coarse = parameter_state.get(f"Oscillator {op} Coarse", 1)
            level = parameter_state.get(f"Oscillator {op} Level", 0)
            if coarse and coarse > 1 and level and level > 0:
                mod_routes.append({
                    "source": f"Oscillator {op}",
                    "target": "(per algorithm)",
                    "amount": level,
                    "range": None,
                    "coarse": coarse,
                })
        mod = ModulationGraph(routes=mod_routes)

        articulation = ArticulationProfile(
            attack_ms=float(parameter_state.get("Oscillator A Attack", 0.0) or 0.0),
            release_ms=float(parameter_state.get("Oscillator A Release", 0.0) or 0.0),
        )

        focused_state = {k: v for k, v in parameter_state.items() if k in _KNOWN_PARAMS}
        focused_display = (
            {k: v for k, v in (display_values or {}).items() if k in _KNOWN_PARAMS}
            if display_values
            else {}
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

        results: list[tuple[BranchSeed, dict]] = []

        # ── Branch A: ratio_shift on modulator B ─────────────────────
        # Pick a new Coarse ratio for Oscillator B (a common modulator slot)
        # that contrasts with current. 2 → 3 is inharmonic, 1 → 2 is octave+,
        # 3 → 5 is bell-like. Default to +1 coarse step when freshness < 0.5,
        # +2 steps when higher.
        current_coarse = int(profile.parameter_state.get("Oscillator B Coarse", 1) or 1)
        step = 1 if freshness < 0.5 else 2
        new_coarse = min(24, current_coarse + step)
        if new_coarse == current_coarse:
            new_coarse = max(1, current_coarse - step)
        seed_a = freeform_seed(
            seed_id=_short_id("op_ratio", f"{track}:{device}:{new_coarse}"),
            hypothesis=(
                f"Shift Operator Osc B Coarse from {current_coarse} to {new_coarse} "
                f"for a {'subtle' if step == 1 else 'significant'} FM tone change"
            ),
            source="synthesis",
            novelty_label="strong" if step == 1 else "unexpected",
            risk_label="medium",
            affected_scope={
                "track_indices": [track],
                "device_paths": [f"track/{track}/device/{device}"],
            },
            distinctness_reason=(
                "only seed that changes the modulator/carrier ratio on Osc B"
            ),
        )
        plan_a = {
            "steps": [
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "Oscillator B Coarse",
                        "value": new_coarse,
                    },
                },
            ],
            "step_count": 1,
            "summary": f"Osc B Coarse {current_coarse} → {new_coarse}",
        }
        results.append((seed_a, plan_a))

        return results


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

"""Operator adapter — native-synth-aware branch production for Ableton's Operator.

FM synthesis is defined by operator ratios + algorithm topology + per-op
envelopes. PR9 always targeted Oscillator B because modulator role was
unknown; PR2/v2 decodes Algorithm → which oscillators are actually
carriers vs modulators, and targets the modulator with the highest Level
so the ratio shift produces a real timbral change rather than changing
an inaudible operator.

Strategy: ratio_shift_<operator>. Each seed's producer_payload captures:
  {schema_version, device_name, track_index, device_index,
   strategy: "ratio_shift_<op>",
   topology_hint: {algorithm, carriers, modulators, targeted_op,
                   current_coarse, new_coarse}}

so later render-verification can confirm the shift actually altered the
modulated carrier's spectrum.
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


# Static topology table for Ableton Operator's 11 algorithms. Each entry
# names the ops that act as carriers (audible) and modulators (FM sources).
# Source: Ableton Operator manual, DX7-compatible topologies. The exact
# modulation routing within an algorithm (who modulates whom) matters less
# for adapter targeting than the carrier/modulator role — what we need to
# know is "which op's Coarse, when shifted, produces an audible timbral
# change?" Answer: any op acting as a modulator.
#
# Algorithm numbering follows Ableton's 0-based display order.
_ALGO_TOPOLOGY: dict[int, dict] = {
    0:  {"carriers": ["D"],              "modulators": ["A", "B", "C"]},
    1:  {"carriers": ["B", "D"],         "modulators": ["A", "C"]},
    2:  {"carriers": ["B", "C", "D"],    "modulators": ["A"]},
    3:  {"carriers": ["D"],              "modulators": ["A", "B", "C"]},
    4:  {"carriers": ["C", "D"],         "modulators": ["A", "B"]},
    5:  {"carriers": ["A", "B", "C", "D"], "modulators": []},
    6:  {"carriers": ["B", "D"],         "modulators": ["A", "C"]},
    7:  {"carriers": ["D"],              "modulators": ["A", "B", "C"]},
    8:  {"carriers": ["B", "C", "D"],    "modulators": ["A"]},
    9:  {"carriers": ["A", "B", "C", "D"], "modulators": []},
    10: {"carriers": ["B", "C", "D"],    "modulators": ["A"]},
}


def _topology_for_algorithm(algorithm: int) -> dict:
    """Look up carrier/modulator roles for an Operator algorithm index."""
    # Default to algorithm 0 (classic serial chain) if unknown.
    return _ALGO_TOPOLOGY.get(int(algorithm or 0), _ALGO_TOPOLOGY[0])


def _pick_target_modulator(
    topology: dict,
    parameter_state: dict,
) -> Optional[str]:
    """Pick the modulator with the highest Level — the best shift target.

    Returns the operator letter ("A".."D") or None when the algorithm has
    no modulators (purely additive algos 5 and 9). Level-based selection
    ensures the Coarse shift produces an audible change; shifting an
    op whose Level is 0 is a no-op.
    """
    candidates = []
    for op in topology.get("modulators", []):
        level_key = f"Oscillator {op} Level"
        level = float(parameter_state.get(level_key, 0.0) or 0.0)
        candidates.append((level, op))
    if not candidates:
        return None
    candidates.sort(reverse=True)  # highest level first
    top_level, top_op = candidates[0]
    # If every modulator is silent, still return the first one — the shift
    # primes the patch for a future Level bump. Better than no branch.
    return top_op


def _fallback_carrier_target(
    topology: dict,
    parameter_state: dict,
) -> Optional[str]:
    """Fallback when algorithm has no modulators (additive algos).

    Picks the carrier with the highest Level; shifting its Coarse changes
    the fundamental spectrum rather than FM depth.
    """
    candidates = []
    for op in topology.get("carriers", []):
        level_key = f"Oscillator {op} Level"
        level = float(parameter_state.get(level_key, 0.0) or 0.0)
        candidates.append((level, op))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


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

        # ── Branch A: algorithm-aware ratio_shift ────────────────────
        # Decode the current Algorithm, pick the real modulator (highest
        # Level among the algorithm's modulator ops), and shift its
        # Coarse. When the algorithm is purely additive (no modulators),
        # fall back to shifting the dominant carrier — changes the
        # fundamental spectrum instead of FM depth.
        algorithm = int(profile.parameter_state.get("Algorithm", 0) or 0)
        topology = _topology_for_algorithm(algorithm)
        targeted_op = _pick_target_modulator(topology, profile.parameter_state)
        target_role = "modulator"

        if targeted_op is None:
            targeted_op = _fallback_carrier_target(topology, profile.parameter_state)
            target_role = "carrier"
            if targeted_op is None:
                # No usable operators — skip the branch rather than emit
                # something that can't produce a timbral change.
                return results

        coarse_key = f"Oscillator {targeted_op} Coarse"
        current_coarse = int(profile.parameter_state.get(coarse_key, 1) or 1)
        step = 1 if freshness < 0.5 else 2
        new_coarse = min(24, current_coarse + step)
        if new_coarse == current_coarse:
            new_coarse = max(1, current_coarse - step)

        strategy = f"ratio_shift_{targeted_op}"
        topology_hint = {
            "algorithm": algorithm,
            "carriers": list(topology.get("carriers", [])),
            "modulators": list(topology.get("modulators", [])),
            "targeted_op": targeted_op,
            "target_role": target_role,
            "current_coarse": current_coarse,
            "new_coarse": new_coarse,
        }

        seed_a = freeform_seed(
            seed_id=_short_id(
                "op_ratio", f"{track}:{device}:{algorithm}:{targeted_op}:{new_coarse}"
            ),
            hypothesis=(
                f"Shift Operator Osc {targeted_op} ({target_role}) Coarse "
                f"{current_coarse} → {new_coarse} under algorithm {algorithm} "
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
                f"algorithm-{algorithm} aware shift on {target_role} Osc {targeted_op}"
            ),
            producer_payload={
                "device_name": self.device_name,
                "track_index": track,
                "device_index": device,
                "strategy": strategy,
                "topology_hint": topology_hint,
            },
        )
        plan_a = {
            "steps": [
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": coarse_key,
                        "value": new_coarse,
                    },
                },
            ],
            "step_count": 1,
            "summary": f"Osc {targeted_op} Coarse {current_coarse} → {new_coarse} (algo {algorithm})",
        }
        results.append((seed_a, plan_a))

        return results


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

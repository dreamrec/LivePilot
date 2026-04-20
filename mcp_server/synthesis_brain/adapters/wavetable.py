"""Wavetable adapter — native-synth-aware branch production for Ableton's Wavetable.

Knows the relevant parameter names and proposes two canned variant
branches per call:
  - osc_position_shift: moves Osc 1 position to create a timbral contrast
  - voice_width_variant: increases unison voices and detune for width

Later PRs add: modulation-matrix inversion, filter-envelope reshaping,
tuning-table variants, sub/body-layer variants.
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


# Parameter names we know and care about. Extracted from the Wavetable
# corpus (see skills/livepilot-core/references/device-knowledge/
# instruments-synths.md). PR9 uses a small subset; later PRs extend.
_KNOWN_PARAMS = {
    "Osc 1 Position",
    "Osc 2 Position",
    "Osc 1 Transpose",
    "Osc 2 Transpose",
    "Voices",
    "Voices Detune",
    "Filter Freq",
    "Filter Res",
    "Filter Drive",
    "Amp Attack",
    "Amp Release",
    "LFO 1 Rate",
    "LFO 1 Amount",
}


@register_adapter
class WavetableAdapter:
    """Adapter for Ableton's native Wavetable."""

    device_name: str = "Wavetable"

    def extract_profile(
        self,
        track_index: int,
        device_index: int,
        parameter_state: dict,
        display_values: Optional[dict] = None,
        role_hint: str = "",
    ) -> SynthProfile:
        notes: list[str] = []

        voices = parameter_state.get("Voices", 0)
        detune = parameter_state.get("Voices Detune", 0.0)
        if voices and voices >= 4 and detune and detune > 0.1:
            notes.append(
                f"voices={voices}, detune={detune:.2f} — already rich, avoid over-thickening"
            )
        if voices and voices <= 1:
            notes.append("mono voice mode — width variants must add voices")

        # Articulation from amp envelope when present
        articulation = ArticulationProfile(
            attack_ms=float(parameter_state.get("Amp Attack", 0.0) or 0.0),
            release_ms=float(parameter_state.get("Amp Release", 0.0) or 0.0),
        )

        # Modulation graph — minimal in PR9, just LFO 1 if it has amount > 0
        mod = ModulationGraph()
        lfo_amount = parameter_state.get("LFO 1 Amount", 0.0)
        if lfo_amount and abs(lfo_amount) > 0.01:
            mod.routes.append({
                "source": "LFO 1",
                "target": "(destination inferred from patch)",
                "amount": lfo_amount,
                "range": None,
            })

        # Filter only the known parameters into parameter_state for a compact
        # profile — full state is available to callers via the raw dict they
        # already have. This keeps the profile focused on what adapters use.
        focused_state = {
            k: v for k, v in parameter_state.items() if k in _KNOWN_PARAMS
        }
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

        # ── Branch A: osc_position_shift ──────────────────────────────
        # Moves Osc 1 position to a contrasting point. Safe / incremental
        # when freshness < 0.5; more aggressive shift when higher.
        current_pos = float(profile.parameter_state.get("Osc 1 Position", 0.0) or 0.0)
        shift = 0.2 if freshness < 0.5 else 0.45
        # Wrap within [0, 1]; if the current position is high, shift down.
        if current_pos + shift > 1.0:
            new_pos = max(0.0, current_pos - shift)
        else:
            new_pos = min(1.0, current_pos + shift)
        seed_a = freeform_seed(
            seed_id=_short_id("wt_pos", f"{track}:{device}:{new_pos:.2f}"),
            hypothesis=(
                f"Shift Wavetable Osc 1 Position from {current_pos:.2f} to {new_pos:.2f} "
                f"for a contrasting harmonic spectrum"
            ),
            source="synthesis",
            novelty_label="strong" if freshness < 0.7 else "unexpected",
            risk_label="low",
            affected_scope={
                "track_indices": [track],
                "device_paths": [f"track/{track}/device/{device}"],
            },
            distinctness_reason="only seed that changes Osc 1 Position",
        )
        plan_a = {
            "steps": [
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "Osc 1 Position",
                        "value": round(new_pos, 3),
                    },
                },
            ],
            "step_count": 1,
            "summary": f"Osc 1 Position {current_pos:.2f} → {new_pos:.2f}",
        }
        results.append((seed_a, plan_a))

        # ── Branch B: voice_width_variant ─────────────────────────────
        # Push Voices + Detune for a richer stereo image — unless profile
        # notes flag that voices are already high (avoid over-thickening).
        skip_width = any("over-thickening" in n for n in profile.notes)
        if not skip_width:
            current_voices = float(profile.parameter_state.get("Voices", 1) or 1)
            current_detune = float(profile.parameter_state.get("Voices Detune", 0.0) or 0.0)
            new_voices = min(8.0, max(current_voices, 4.0))
            new_detune = min(0.5, max(current_detune + 0.1, 0.15))
            seed_b = freeform_seed(
                seed_id=_short_id("wt_width", f"{track}:{device}:{new_voices}:{new_detune:.2f}"),
                hypothesis=(
                    f"Increase Wavetable voices to {int(new_voices)} with detune "
                    f"{new_detune:.2f} for a wider, richer image"
                ),
                source="synthesis",
                novelty_label="safe",
                risk_label="low",
                affected_scope={
                    "track_indices": [track],
                    "device_paths": [f"track/{track}/device/{device}"],
                },
                distinctness_reason=(
                    "only seed that changes voice count + detune; focuses on "
                    "width rather than spectrum"
                ),
            )
            plan_b = {
                "steps": [
                    {
                        "tool": "set_device_parameter",
                        "params": {
                            "track_index": track,
                            "device_index": device,
                            "parameter_name": "Voices",
                            "value": new_voices,
                        },
                    },
                    {
                        "tool": "set_device_parameter",
                        "params": {
                            "track_index": track,
                            "device_index": device,
                            "parameter_name": "Voices Detune",
                            "value": round(new_detune, 3),
                        },
                    },
                ],
                "step_count": 2,
                "summary": f"Voices → {int(new_voices)}, Detune → {new_detune:.2f}",
            }
            results.append((seed_b, plan_b))

        return results


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

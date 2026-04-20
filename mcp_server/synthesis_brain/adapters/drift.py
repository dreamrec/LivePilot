"""Drift adapter — Ableton 12's modern subtractive synth.

Drift has a cleaner parameter set than Analog and pairs oscillator
shapes with a character wave + sub + noise blend. PR10 ships one
canned proposer: character_blend — shifts the oscillator wave + sub
balance to change core tone without touching the filter. Later PRs
add tuning-table variants and LFO-routing variants.
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
    "Wave",
    "Character",
    "Tune",
    "Sub Level",
    "Sub Tone",
    "Noise Level",
    "Noise Color",
    "Filter Freq",
    "Filter Res",
    "Filter Env",
    "LFO Rate",
    "LFO Amount",
    "Amp Env A",
    "Amp Env D",
    "Amp Env S",
    "Amp Env R",
}


@register_adapter
class DriftAdapter:
    device_name: str = "Drift"

    def extract_profile(
        self,
        track_index: int,
        device_index: int,
        parameter_state: dict,
        display_values: Optional[dict] = None,
        role_hint: str = "",
    ) -> SynthProfile:
        notes: list[str] = []

        sub = float(parameter_state.get("Sub Level", 0.0) or 0.0)
        noise = float(parameter_state.get("Noise Level", 0.0) or 0.0)
        if sub > 0.5 and role_hint in ("lead", "stab"):
            notes.append(f"Sub Level {sub:.2f} is high for a {role_hint} — check bass clash")
        if noise > 0.5:
            notes.append(f"Noise Level {noise:.2f} — significant noise content")

        articulation = ArticulationProfile(
            attack_ms=float(parameter_state.get("Amp Env A", 0.0) or 0.0),
            release_ms=float(parameter_state.get("Amp Env R", 0.0) or 0.0),
        )

        mod = ModulationGraph()
        lfo_amount = parameter_state.get("LFO Amount", 0.0)
        if lfo_amount and abs(lfo_amount) > 0.01:
            mod.routes.append({
                "source": "LFO",
                "target": "(inferred)",
                "amount": lfo_amount,
                "range": None,
            })

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

        current_char = float(profile.parameter_state.get("Character", 0.0) or 0.0)
        current_sub = float(profile.parameter_state.get("Sub Level", 0.0) or 0.0)

        # Toggle character in the opposite direction to create contrast.
        new_char = min(1.0, max(current_char + 0.3, 0.3)) if current_char <= 0.5 else max(0.0, current_char - 0.3)
        # Move sub slightly toward 0.3 if we're starting outside 0.2-0.4
        target_sub = 0.3
        new_sub = current_sub + (target_sub - current_sub) * (0.5 if freshness < 0.5 else 0.8)
        new_sub = round(max(0.0, min(1.0, new_sub)), 3)

        seed = freeform_seed(
            seed_id=_short_id("dr_chr", f"{track}:{device}:{new_char:.2f}:{new_sub:.2f}"),
            hypothesis=(
                f"Drift character blend: Character → {new_char:.2f}, "
                f"Sub Level → {new_sub:.2f} for a different core tone"
            ),
            source="synthesis",
            novelty_label="strong",
            risk_label="low",
            affected_scope={
                "track_indices": [track],
                "device_paths": [f"track/{track}/device/{device}"],
            },
            distinctness_reason="only Drift seed that shifts Character + Sub balance",
        )
        plan = {
            "steps": [
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "Character",
                        "value": round(new_char, 3),
                    },
                },
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "Sub Level",
                        "value": new_sub,
                    },
                },
            ],
            "step_count": 2,
            "summary": f"Character → {new_char:.2f}, Sub Level → {new_sub:.2f}",
        }
        return [(seed, plan)]


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

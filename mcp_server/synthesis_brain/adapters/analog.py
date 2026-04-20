"""Analog adapter — Ableton's classic two-oscillator subtractive synth.

PR10 ships one canned proposer: filter_envelope_variant — pushes Filter
Envelope Amount while shortening the Filter Decay, producing the
characteristic "plucked" attack that Analog excels at. Later PRs add
detune/unison variants and dual-filter variants.
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
    "Osc1 Shape",
    "Osc2 Shape",
    "Osc1 Tune",
    "Osc2 Tune",
    "F1 Freq",
    "F1 Reso",
    "F1 Env Amount",
    "F1 Env A",
    "F1 Env D",
    "F1 Env S",
    "F1 Env R",
    "A1 Attack",
    "A1 Decay",
    "A1 Sustain",
    "A1 Release",
    "Glide Mode",
    "Glide Time",
}


@register_adapter
class AnalogAdapter:
    device_name: str = "Analog"

    def extract_profile(
        self,
        track_index: int,
        device_index: int,
        parameter_state: dict,
        display_values: Optional[dict] = None,
        role_hint: str = "",
    ) -> SynthProfile:
        notes: list[str] = []

        # Filter-env coupling summary
        env_amount = parameter_state.get("F1 Env Amount", 0.0)
        env_decay = parameter_state.get("F1 Env D", 0.0)
        if env_amount and abs(env_amount) > 0.3 and env_decay and env_decay < 0.3:
            notes.append(
                f"Already plucky: F1 Env Amount={env_amount:.2f}, Decay={env_decay:.2f}"
            )

        articulation = ArticulationProfile(
            attack_ms=float(parameter_state.get("A1 Attack", 0.0) or 0.0),
            release_ms=float(parameter_state.get("A1 Release", 0.0) or 0.0),
        )

        mod = ModulationGraph()
        if env_amount and abs(env_amount) > 0.01:
            mod.routes.append({
                "source": "Filter Env",
                "target": "F1 Freq",
                "amount": env_amount,
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

        # Skip proposal if already plucky — avoids doubling-down on the
        # same treatment.
        if any("Already plucky" in n for n in profile.notes):
            return []

        current_env = float(profile.parameter_state.get("F1 Env Amount", 0.0) or 0.0)
        # Target filter-env amount scales with freshness.
        new_env = min(1.0, max(current_env, 0.45 if freshness < 0.5 else 0.65))
        current_decay = float(profile.parameter_state.get("F1 Env D", 0.5) or 0.5)
        new_decay = min(current_decay, 0.25 if freshness < 0.5 else 0.15)

        seed = freeform_seed(
            seed_id=_short_id("an_plk", f"{track}:{device}:{new_env:.2f}:{new_decay:.2f}"),
            hypothesis=(
                f"Analog filter-pluck: Env Amount → {new_env:.2f}, "
                f"Decay → {new_decay:.2f} for attack character"
            ),
            source="synthesis",
            novelty_label="strong" if freshness < 0.7 else "unexpected",
            risk_label="low",
            affected_scope={
                "track_indices": [track],
                "device_paths": [f"track/{track}/device/{device}"],
            },
            distinctness_reason="only Analog seed that couples Filter Env + Decay",
        )
        plan = {
            "steps": [
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "F1 Env Amount",
                        "value": round(new_env, 3),
                    },
                },
                {
                    "tool": "set_device_parameter",
                    "params": {
                        "track_index": track,
                        "device_index": device,
                        "parameter_name": "F1 Env D",
                        "value": round(new_decay, 3),
                    },
                },
            ],
            "step_count": 2,
            "summary": f"F1 Env Amount → {new_env:.2f}, F1 Env D → {new_decay:.2f}",
        }
        return [(seed, plan)]


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

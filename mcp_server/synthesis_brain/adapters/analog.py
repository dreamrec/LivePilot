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
        # Strategy registry — each candidate strategy's ``applicable()``
        # gates on profile+role+target, and ``build()`` emits (seed, plan).
        # Adapter returns ALL applicable strategies' proposals so Wonder /
        # create_experiment can offer them as branches. Callers cap total
        # via max_seeds.
        kernel = kernel or {}
        results: list[tuple[BranchSeed, dict]] = []
        for strategy_fn in (_strategy_filter_pluck, _strategy_detune_warmth):
            try:
                maybe = strategy_fn(profile, target, kernel, adapter=self)
            except Exception:
                # Never let one strategy's crash kill the rest.
                continue
            if maybe is not None:
                results.append(maybe)
        return results


# ── Strategy registry ────────────────────────────────────────────────
#
# Each strategy is a pure function (profile, target, kernel, adapter) →
# Optional[(BranchSeed, plan_dict)]. A strategy returns None when not
# applicable to the current profile+target+role combination. This lets
# the adapter stay thin while the intelligence lives in the strategies.


def _strategy_filter_pluck(
    profile: SynthProfile,
    target: TimbralFingerprint,
    kernel: dict,
    adapter,
) -> Optional[tuple[BranchSeed, dict]]:
    """Couple Filter Env Amount up + Filter Decay down → attack pluck.

    Gates: skip when profile already flags 'Already plucky'. Most useful
    when role_hint is "bass", "pluck", "lead", or when target.bite > 0.
    """
    if any("Already plucky" in n for n in profile.notes):
        return None

    role = (profile.role_hint or "").lower()
    want_bite = target.bite > 0.1 or role in {"bass", "pluck", "lead", "stab"}
    if not want_bite and role in {"pad", "drone"}:
        # Sustained roles actively fight this strategy.
        return None

    freshness = float(kernel.get("freshness", 0.5) or 0.5)
    track = profile.track_index
    device = profile.device_index
    current_env = float(profile.parameter_state.get("F1 Env Amount", 0.0) or 0.0)
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
        distinctness_reason="couples Filter Env Amount + Decay for attack character",
        producer_payload={
            "device_name": adapter.device_name,
            "track_index": track,
            "device_index": device,
            "strategy": "filter_pluck",
            "topology_hint": {
                "role_hint": profile.role_hint,
                "current_env": current_env,
                "new_env": new_env,
                "current_decay": current_decay,
                "new_decay": new_decay,
            },
        },
    )
    plan = {
        "steps": [
            {"tool": "set_device_parameter",
             "params": {"track_index": track, "device_index": device,
                        "parameter_name": "F1 Env Amount",
                        "value": round(new_env, 3)}},
            {"tool": "set_device_parameter",
             "params": {"track_index": track, "device_index": device,
                        "parameter_name": "F1 Env D",
                        "value": round(new_decay, 3)}},
        ],
        "step_count": 2,
        "summary": f"F1 Env Amount → {new_env:.2f}, F1 Env D → {new_decay:.2f}",
    }
    return (seed, plan)


def _strategy_detune_warmth(
    profile: SynthProfile,
    target: TimbralFingerprint,
    kernel: dict,
    adapter,
) -> Optional[tuple[BranchSeed, dict]]:
    """Detune Osc2 slightly + lean warmer tone.

    Gates: applicable when role_hint is "pad" / "lead" / "stab" / "drone"
    or target.warmth > 0. Skip on "pluck"/"bass" to avoid woofiness.
    """
    role = (profile.role_hint or "").lower()
    if role in {"bass", "pluck", "kick"}:
        return None
    want_warm = target.warmth > 0.1 or role in {"pad", "lead", "stab", "drone"}
    if not want_warm:
        return None

    freshness = float(kernel.get("freshness", 0.5) or 0.5)
    track = profile.track_index
    device = profile.device_index
    current_detune = float(profile.parameter_state.get("Osc2 Tune", 0.0) or 0.0)
    # Detune is in semitones by convention on Analog; keep shifts musical.
    step = 0.04 if freshness < 0.5 else 0.09
    new_detune = round(current_detune + step, 3)

    seed = freeform_seed(
        seed_id=_short_id("an_det", f"{track}:{device}:{new_detune:.3f}"),
        hypothesis=(
            f"Analog detune warmth: Osc2 Tune {current_detune:.3f} → "
            f"{new_detune:.3f} semitones for a wider, lusher body"
        ),
        source="synthesis",
        novelty_label="safe",
        risk_label="low",
        affected_scope={
            "track_indices": [track],
            "device_paths": [f"track/{track}/device/{device}"],
        },
        distinctness_reason="slight Osc2 detune for body, no filter changes",
        producer_payload={
            "device_name": adapter.device_name,
            "track_index": track,
            "device_index": device,
            "strategy": "detune_warmth",
            "topology_hint": {
                "role_hint": profile.role_hint,
                "current_detune": current_detune,
                "new_detune": new_detune,
            },
        },
    )
    plan = {
        "steps": [
            {"tool": "set_device_parameter",
             "params": {"track_index": track, "device_index": device,
                        "parameter_name": "Osc2 Tune",
                        "value": new_detune}},
        ],
        "step_count": 1,
        "summary": f"Osc2 Tune → {new_detune:.3f}",
    }
    return (seed, plan)


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"

"""Wavetable adapter — native-synth-aware branch production for Ableton's Wavetable.

Knows the relevant parameter names. PR9 shipped two canned proposers;
PR2/v2 adds position-region classification so the shift direction and
magnitude depend on *where* in the wavetable the patch currently sits,
not just freshness.

Strategies (selected based on profile + region):
  - osc_position_to_bright: shift toward the bright/complex end when
    the current position is sub_region or mid_region and the target
    timbre asks for brightness.
  - osc_position_to_dark: shift toward sub/mid when starting bright and
    the profile or target prefers warmth.
  - voice_width_variant: increase unison voices + detune for width,
    unless the patch is already over-thickened.

Each seed's producer_payload captures:
  {schema_version, device_name, track_index, device_index,
   strategy, topology_hint: {current_region, target_region,
   current_pos, new_pos}}
so PR4 render-verification and future position-to-spectrum mappings can
refine the heuristic without losing provenance.

Known limitation: region classification is a coarse heuristic on the
raw Osc 1 Pos float. Specific factory wavetables don't always follow
the "low value = simple, high value = complex" rule. PR4's render-based
mapping will refine per-wavetable — producer_payload's topology_hint
is the contract for that upgrade.
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


# Coarse position → region mapping. Most Ableton factory wavetables fade
# from low-harmonic (position 0) toward high-harmonic (position 1), but
# this is approximate. PR4 will refine with render-based spectral mapping.
_WAVETABLE_REGIONS: list[tuple[float, float, str]] = [
    (0.0, 0.25, "sub_region"),
    (0.25, 0.5, "mid_region"),
    (0.5, 0.75, "bright_region"),
    (0.75, 1.01, "complex_region"),
]


def _classify_position(pos: float) -> str:
    """Map an Osc 1 Pos float to a coarse spectral region name."""
    for lo, hi, region in _WAVETABLE_REGIONS:
        if lo <= pos < hi:
            return region
    return "complex_region"


def _choose_target_region(
    current_region: str,
    target: "TimbralFingerprint",
) -> str:
    """Pick a contrasting region based on the target fingerprint.

    When the target asks for more brightness, move toward
    bright_region/complex_region. When it asks for more warmth or less
    brightness (negative target.brightness), move toward
    sub_region/mid_region. When the target is neutral, shift one region
    away from current for contrast.
    """
    want_bright = target.brightness
    if abs(want_bright) < 0.1:
        # Neutral target — shift one region away for variety.
        fallback_map = {
            "sub_region": "mid_region",
            "mid_region": "bright_region",
            "bright_region": "mid_region",
            "complex_region": "bright_region",
        }
        return fallback_map.get(current_region, "mid_region")

    if want_bright > 0:
        # Bias brighter.
        upshift = {
            "sub_region": "mid_region",
            "mid_region": "bright_region",
            "bright_region": "complex_region",
            "complex_region": "complex_region",
        }
        return upshift.get(current_region, "bright_region")

    # want_bright < 0 — bias darker.
    downshift = {
        "complex_region": "bright_region",
        "bright_region": "mid_region",
        "mid_region": "sub_region",
        "sub_region": "sub_region",
    }
    return downshift.get(current_region, "sub_region")


def _region_center(region: str) -> float:
    """Middle of the region's position range — the target for a shift."""
    for lo, hi, name in _WAVETABLE_REGIONS:
        if name == region:
            return round((lo + min(hi, 1.0)) / 2.0, 3)
    return 0.5


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

        # ── Branch A: region-aware Osc 1 Position shift ──────────────
        # Classify current position into a spectral region, pick a
        # contrasting target region based on the timbral target, then
        # shift to that region's center. The actual shift magnitude
        # (how close to the center) scales with freshness — low
        # freshness stops partway, high freshness commits fully.
        current_pos = float(profile.parameter_state.get("Osc 1 Position", 0.0) or 0.0)
        current_region = _classify_position(current_pos)
        target_region = _choose_target_region(current_region, target)
        region_target_pos = _region_center(target_region)

        # Blend: low freshness only moves partway toward the target region,
        # high freshness commits fully.
        blend = 0.4 if freshness < 0.5 else 1.0
        new_pos = round(
            current_pos + (region_target_pos - current_pos) * blend, 3
        )
        new_pos = max(0.0, min(1.0, new_pos))

        # Strategy name reflects direction (pick name from target region).
        if target_region in ("bright_region", "complex_region"):
            strategy = "osc_position_to_bright"
        elif target_region in ("sub_region", "mid_region"):
            strategy = "osc_position_to_dark"
        else:
            strategy = "osc_position_shift"

        topology_hint = {
            "current_region": current_region,
            "target_region": target_region,
            "current_pos": current_pos,
            "new_pos": new_pos,
        }

        seed_a = freeform_seed(
            seed_id=_short_id(
                "wt_pos", f"{track}:{device}:{current_region}:{target_region}:{new_pos:.2f}"
            ),
            hypothesis=(
                f"Shift Wavetable Osc 1 Position {current_pos:.2f} ({current_region}) → "
                f"{new_pos:.2f} ({target_region}) for a {strategy.split('_to_')[-1]} spectrum"
            ),
            source="synthesis",
            novelty_label="strong" if freshness < 0.7 else "unexpected",
            risk_label="low",
            affected_scope={
                "track_indices": [track],
                "device_paths": [f"track/{track}/device/{device}"],
            },
            distinctness_reason=(
                f"moves Osc 1 Position from {current_region} to {target_region}"
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
                        "parameter_name": "Osc 1 Position",
                        "value": new_pos,
                    },
                },
            ],
            "step_count": 1,
            "summary": f"Osc 1 Position {current_pos:.2f} ({current_region}) → {new_pos:.2f} ({target_region})",
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
                producer_payload={
                    "device_name": self.device_name,
                    "track_index": track,
                    "device_index": device,
                    "strategy": "voice_width_variant",
                    "topology_hint": {
                        "current_voices": int(current_voices),
                        "current_detune": current_detune,
                        "new_voices": int(new_voices),
                        "new_detune": new_detune,
                    },
                },
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

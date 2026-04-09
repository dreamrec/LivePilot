"""Phrase-level evaluation — judges musical phrases, not just parameter deltas.

Operates on 8-16 bar windows. Analyzes arc clarity, contrast, fatigue risk,
payoff strength, and translation risk from audio captures and spectral data.

Pure computation — receives analysis data, returns structured critique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PhraseCritique:
    """Evaluation of a rendered musical phrase."""
    render_id: str = ""
    arc_clarity: float = 0.0      # How clear is the phrase's tension shape?
    contrast: float = 0.0         # How different are the beginning and end?
    fatigue_risk: float = 0.0     # How repetitive is the material?
    payoff_strength: float = 0.0  # Does the phrase deliver on its promise?
    identity_strength: float = 0.0  # How distinct is this from other phrases?
    translation_risk: float = 0.0   # How likely to sound bad on small speakers?
    notes: list[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        scores = [
            self.arc_clarity,
            self.contrast,
            1.0 - self.fatigue_risk,
            self.payoff_strength,
            self.identity_strength,
            1.0 - self.translation_risk,
        ]
        return round(sum(scores) / len(scores), 3)

    def to_dict(self) -> dict:
        return {
            "render_id": self.render_id,
            "overall": self.overall,
            "arc_clarity": round(self.arc_clarity, 3),
            "contrast": round(self.contrast, 3),
            "fatigue_risk": round(self.fatigue_risk, 3),
            "payoff_strength": round(self.payoff_strength, 3),
            "identity_strength": round(self.identity_strength, 3),
            "translation_risk": round(self.translation_risk, 3),
            "notes": self.notes,
        }


def analyze_phrase(
    loudness_data: Optional[dict] = None,
    spectrum_data: Optional[dict] = None,
    target: str = "loop",
) -> PhraseCritique:
    """Analyze a captured phrase from loudness and spectral data.

    loudness_data: output from analyze_loudness (LUFS, LRA, peak, short_term_lufs)
    spectrum_data: output from analyze_spectrum_offline (centroid, rolloff, balance)
    target: what the phrase is supposed to be: "loop", "drop", "chorus", "transition", "intro", "outro"
    """
    critique = PhraseCritique()

    if not loudness_data and not spectrum_data:
        critique.notes.append("No analysis data — capture audio first")
        return critique

    # Arc clarity from short-term LUFS variation
    if loudness_data:
        stl = loudness_data.get("short_term_lufs", [])
        if len(stl) >= 3:
            lufs_range = max(stl) - min(stl)
            # Good arc = variation between 2-8 LU
            if 2 <= lufs_range <= 8:
                critique.arc_clarity = 0.8
            elif lufs_range > 8:
                critique.arc_clarity = 0.5
                critique.notes.append("Loudness variation too extreme — may feel chaotic")
            else:
                critique.arc_clarity = 0.3 + lufs_range * 0.1
                if lufs_range < 1:
                    critique.notes.append("Very flat dynamics — phrase sounds static")

        # Fatigue risk from LRA
        lra = loudness_data.get("lra_lu", 0)
        if lra < 1:
            critique.fatigue_risk = 0.8
            critique.notes.append(f"LRA {lra:.1f} LU — extremely repetitive")
        elif lra < 3:
            critique.fatigue_risk = 0.5
        else:
            critique.fatigue_risk = max(0, 0.3 - lra * 0.03)

        # Translation risk from true peak
        peak = loudness_data.get("true_peak_dbtp", 0)
        if peak > -1:
            critique.translation_risk = 0.7
            critique.notes.append(f"True peak {peak:.1f} dBTP — clipping risk on playback")
        elif peak > -3:
            critique.translation_risk = 0.3
        else:
            critique.translation_risk = 0.1

    # Spectral analysis
    if spectrum_data:
        balance = spectrum_data.get("band_balance", {})
        sub = balance.get("sub_60hz", 0)
        mid = balance.get("mid_2khz", 0)
        high = balance.get("high_8khz", 0)

        # Identity strength: how distinctive is the spectral shape?
        if sub > 0.5:
            critique.identity_strength = 0.6
            critique.notes.append("Sub-heavy identity — bass-driven phrase")
        elif mid > 0.5:
            critique.identity_strength = 0.7
            critique.notes.append("Mid-focused — melodic/harmonic identity")
        elif high > 0.3:
            critique.identity_strength = 0.5
            critique.notes.append("Bright character — texture-driven")
        else:
            critique.identity_strength = 0.4

        # Contrast from centroid
        centroid = spectrum_data.get("centroid_hz", 500)
        if centroid < 200:
            critique.contrast = 0.3
            critique.notes.append("Very dark — limited spectral contrast")
        elif centroid > 2000:
            critique.contrast = 0.6
        else:
            critique.contrast = 0.5

    # Payoff strength depends on target type
    _payoff_targets = {
        "drop": 0.8,    # Drops need high payoff
        "chorus": 0.7,  # Choruses need good payoff
        "loop": 0.5,    # Loops are neutral
        "transition": 0.4,
        "intro": 0.3,
        "outro": 0.3,
    }
    critique.payoff_strength = _payoff_targets.get(target, 0.5)

    return critique


def compare_phrases(critiques: list[PhraseCritique]) -> list[dict]:
    """Rank multiple phrase critiques by overall score."""
    ranked = sorted(critiques, key=lambda c: -c.overall)
    return [
        {
            "rank": i + 1,
            "render_id": c.render_id,
            "overall": c.overall,
            "arc_clarity": c.arc_clarity,
            "fatigue_risk": c.fatigue_risk,
            "notes": c.notes[:3],
        }
        for i, c in enumerate(ranked)
    ]

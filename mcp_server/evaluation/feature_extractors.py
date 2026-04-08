"""Feature Extractors — derive measurable values from normalized snapshots.

Replicates the dimension-extraction logic from _agent_os_engine but operates
on the canonical normalized snapshot format (always has "spectrum" key).

All returned values are clamped to 0.0-1.0 for consistent scoring.
"""

from __future__ import annotations

import math
from typing import Optional

from ..tools._evaluation_contracts import MEASURABLE_DIMENSIONS


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi] range."""
    return max(lo, min(hi, value))


def extract_dimension_value(
    snapshot: dict,
    dimension: str,
) -> Optional[float]:
    """Extract a measurable dimension value from a normalized sonic snapshot.

    Args:
        snapshot: Normalized snapshot (from normalize_sonic_snapshot).
                  Must have a "spectrum" key with band values.
        dimension: One of the MEASURABLE_DIMENSIONS (brightness, warmth,
                   weight, clarity, density, energy, punch).

    Returns:
        Float in 0.0-1.0 for measurable dimensions, None otherwise.
    """
    if not snapshot or not isinstance(snapshot, dict):
        return None

    bands = snapshot.get("spectrum")
    if not bands:
        return None

    rms = snapshot.get("rms")
    peak = snapshot.get("peak")

    if dimension == "brightness":
        high = bands.get("high", 0)
        presence = bands.get("presence", 0)
        return _clamp((high + presence) / 2.0)

    elif dimension == "warmth":
        return _clamp(bands.get("low_mid", 0))

    elif dimension == "weight":
        sub = bands.get("sub", 0)
        low = bands.get("low", 0)
        return _clamp((sub + low) / 2.0)

    elif dimension == "clarity":
        low_mid = bands.get("low_mid", 0)
        return _clamp(1.0 - low_mid)

    elif dimension == "density":
        vals = [max(v, 1e-10) for v in bands.values()
                if isinstance(v, (int, float))]
        if not vals:
            return None
        geo_mean = math.exp(sum(math.log(v) for v in vals) / len(vals))
        arith_mean = sum(vals) / len(vals)
        return _clamp(geo_mean / max(arith_mean, 1e-10))

    elif dimension == "energy":
        return _clamp(rms) if rms is not None else None

    elif dimension == "punch":
        if rms and peak and rms > 0:
            crest_db = 20.0 * math.log10(max(peak / rms, 1.0))
            return _clamp(crest_db / 20.0)
        return None

    else:
        # Unmeasurable dimension
        return None

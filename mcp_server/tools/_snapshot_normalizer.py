"""Snapshot Normalizer — canonical input normalization for all evaluators.

Ensures analyzer outputs are in a consistent schema regardless of
which tool produced them. All evaluators should consume normalized
snapshots, never raw tool outputs.

Design: AGENT_OS_PHASE0_HARDENING_PLAN.md, section 3.2
"""

from __future__ import annotations

import time
from typing import Optional


def normalize_sonic_snapshot(
    raw: Optional[dict],
    source: str = "unknown",
) -> Optional[dict]:
    """Normalize a raw analyzer/perception output into canonical snapshot form.

    Accepts both {"bands": {...}} and {"spectrum": {...}} shapes.
    Returns None if input is empty or None.

    Canonical form:
    {
        "spectrum": {band: value, ...},
        "rms": float or None,
        "peak": float or None,
        "detected_key": str or None,
        "source": str,
        "normalized_at_ms": int,
    }
    """
    if not raw or not isinstance(raw, dict):
        return None

    bands = raw.get("spectrum") or raw.get("bands")
    if not bands:
        return None

    return {
        "spectrum": bands,
        "rms": raw.get("rms"),
        "peak": raw.get("peak"),
        "detected_key": raw.get("key") or raw.get("detected_key"),
        "source": source,
        "normalized_at_ms": int(time.time() * 1000),
    }

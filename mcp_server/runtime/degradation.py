"""Explicit degradation signalling for engines that fall back to synthesized data.

Before PR-B, several engines silently substituted defaults when a data
source failed — ``song_brain`` injected ``tempo=120.0, track_count=0``
on session-fetch failure, and ``preview_studio`` compiled variants
against an empty-but-valid kernel when the caller didn't supply one.
Downstream consumers had no way to tell synthesized data from real
data, so polished outputs were returned as if they were real.

``DegradationInfo`` is the shared payload engines attach to their
responses whenever they substitute fallback values. Consumers can
inspect ``is_degraded``, ``reasons``, and ``substituted_fields`` to
decide whether to trust the response or re-try the operation.

Usage::

    from mcp_server.runtime.degradation import DegradationInfo

    deg = DegradationInfo()
    try:
        data = fetch_real_data()
    except Exception:
        data = FALLBACK_DATA
        deg = DegradationInfo(
            is_degraded=True,
            reasons=["data_source_unreachable"],
            substituted_fields=["tempo", "track_count"],
        )
    return {..., "degradation": deg.to_dict()}
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DegradationInfo:
    """A structured signal that an engine substituted fallback data.

    Attributes:
        is_degraded: True when any field in the response was substituted
            with a synthesized/default value. False means the response
            is fully backed by real data sources.
        reasons: Short machine-readable tokens describing why degradation
            happened (e.g., ``"session_fetch_failed"``,
            ``"empty_kernel_fallback"``). Intentionally open-ended — the
            set grows as new fallback paths get flagged.
        substituted_fields: Names of top-level response fields whose
            values came from the fallback path, not the real source.
    """

    is_degraded: bool = False
    reasons: list[str] = field(default_factory=list)
    substituted_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_degraded": self.is_degraded,
            "reasons": list(self.reasons),
            "substituted_fields": list(self.substituted_fields),
        }

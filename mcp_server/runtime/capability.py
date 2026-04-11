"""Capability and degradation reporting for advanced tools.

Every advanced tool reports its operational state so callers know
what data was available, what was missing, and how much to trust
the result.

Levels:
  full — all required data sources available
  fallback — some data missing, result is degraded but useful
  analytical_only — no live data, pure heuristic
  unavailable — cannot operate at all
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityReport:
    """Operational state of an advanced tool invocation."""

    level: str = "full"  # full, fallback, analytical_only, unavailable
    confidence: float = 1.0
    available_sources: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    fallback_used: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        d = {"capability": self.level, "confidence": round(self.confidence, 2)}
        if self.missing_sources:
            d["missing"] = self.missing_sources
        if self.fallback_used:
            d["fallback"] = self.fallback_used
        if self.reason:
            d["reason"] = self.reason
        return d


def build_capability(
    required: list[str],
    available: dict[str, bool],
) -> CapabilityReport:
    """Build a capability report from required vs available data sources."""
    missing = [r for r in required if not available.get(r, False)]
    present = [r for r in required if available.get(r, False)]

    if not missing:
        return CapabilityReport(
            level="full", confidence=1.0, available_sources=present,
        )

    if len(missing) == len(required):
        return CapabilityReport(
            level="analytical_only", confidence=0.2,
            available_sources=[], missing_sources=missing,
            reason="No required data sources available",
        )

    ratio = len(present) / len(required)
    return CapabilityReport(
        level="fallback", confidence=round(ratio * 0.8, 2),
        available_sources=present, missing_sources=missing,
        fallback_used="degraded inference from partial data",
    )

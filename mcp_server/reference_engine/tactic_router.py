"""Tactic router — map gaps to target engines and rank tactics.

Pure functions, zero I/O.
"""

from __future__ import annotations

from .models import GapEntry, GapReport, ReferencePlan


# ── Domain -> Engine mapping ───────────────────────────────────────

_DOMAIN_ENGINE_MAP: dict[str, str] = {
    "spectral": "mix_engine",
    "loudness": "mix_engine",
    "width": "mix_engine",
    "density": "composition",
    "pacing": "composition",
    "harmonic": "composition",
}


# ── Routing ────────────────────────────────────────────────────────


def route_to_engines(gap_report: GapReport) -> list[dict]:
    """Map each relevant gap to a target engine with priority.

    Returns:
        list of {domain, engine, delta, tactic, priority} dicts,
        sorted by priority (highest first).
    """
    routes: list[dict] = []

    for gap in gap_report.relevant_gaps:
        engine = _DOMAIN_ENGINE_MAP.get(gap.domain, "mix_engine")
        priority = _compute_priority(gap)

        routes.append({
            "domain": gap.domain,
            "engine": engine,
            "delta": gap.delta,
            "tactic": gap.suggested_tactic,
            "priority": priority,
            "identity_warning": gap.identity_warning,
        })

    # Sort by priority descending
    routes.sort(key=lambda r: -r["priority"])
    return routes


def build_reference_plan(gap_report: GapReport) -> ReferencePlan:
    """Build a full ReferencePlan from a gap report.

    Combines routing with ranked tactics and target engine list.
    """
    routes = route_to_engines(gap_report)

    # Ranked tactics: each route is a tactic entry
    ranked_tactics = [
        {
            "rank": i + 1,
            "domain": r["domain"],
            "tactic": r["tactic"],
            "engine": r["engine"],
            "priority": r["priority"],
            "identity_warning": r["identity_warning"],
        }
        for i, r in enumerate(routes)
    ]

    # Unique target engines in priority order
    seen: set[str] = set()
    target_engines: list[str] = []
    for r in routes:
        if r["engine"] not in seen:
            target_engines.append(r["engine"])
            seen.add(r["engine"])

    return ReferencePlan(
        gap_report=gap_report,
        ranked_tactics=ranked_tactics,
        target_engines=target_engines,
    )


# ── Priority scoring ──────────────────────────────────────────────


def _compute_priority(gap: GapEntry) -> float:
    """Compute routing priority for a gap.

    Higher = more urgent. Identity-warned gaps get deprioritized
    to avoid flattening the project.
    """
    base = abs(gap.delta)

    # Normalize different domains to comparable scales
    scale = _DOMAIN_SCALE.get(gap.domain, 1.0)
    normalized = min(base * scale, 1.0)

    # Penalize identity-risky gaps
    if gap.identity_warning:
        normalized *= 0.5

    return round(normalized, 3)


_DOMAIN_SCALE: dict[str, float] = {
    "spectral": 10.0,   # band deltas are small (0.001-0.1)
    "loudness": 0.1,    # LUFS deltas are large (1-10)
    "width": 5.0,       # width deltas moderate (0.01-0.3)
    "density": 2.0,     # 0-1 range
    "pacing": 0.2,      # section count deltas
    "harmonic": 1.0,    # binary (0 or 1)
}

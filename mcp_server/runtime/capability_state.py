"""Capability State v1 — unified runtime capability model.

Defines the shared data model that tells engines what can and can't be
trusted right now.  Pure Python, zero I/O — all probing happens in the
MCP tool wrapper (runtime/tools.py).

Design: docs/specs/v2-engine-specs/CAPABILITY_STATE_V1.md
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Domain Model ────────────────────────────────────────────────────────

@dataclass
class CapabilityDomain:
    """A single capability domain's runtime status.

    BUG-2026-04-26#4: ``available`` collapses two distinct conditions
    into one bit (device installed AND data fresh). Callers that wanted
    "is the analyzer .amxd loaded?" had no way to ask without conflating
    it with "has the analyzer captured fresh data yet?". The
    ``device_loaded`` field separates these concerns:

      - ``device_loaded``: True when the optional .amxd / external
        dependency exists. Independent of data freshness. Defaults to
        ``available`` when the domain has no installable component
        (session_access / memory / web / research).
      - ``available``: True when the domain is ready for use end-to-end
        (device_loaded AND fresh data, where applicable).
    """

    name: str
    available: bool
    confidence: float  # 0.0–1.0
    freshness_ms: Optional[int] = None
    mode: str = "unavailable"
    reasons: list[str] = field(default_factory=list)
    device_loaded: Optional[bool] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0–1.0, got {self.confidence}")
        # Default device_loaded to mirror `available` for domains that
        # don't have a separate installable component (memory, web, etc.).
        # Domains that DO have one (analyzer, flucoma) override explicitly.
        if self.device_loaded is None:
            self.device_loaded = self.available

    def to_dict(self) -> dict:
        return asdict(self)


# ── Capability State ────────────────────────────────────────────────────

@dataclass
class CapabilityState:
    """Snapshot of all capability domains at a point in time."""

    generated_at_ms: int
    overall_mode: str  # normal | measured_degraded | judgment_only | read_only
    domains: dict[str, CapabilityDomain] = field(default_factory=dict)

    # ── Query helpers ───────────────────────────────────────────────

    def can_use_measured_evaluation(self) -> bool:
        """True when analyzer data is available and fresh enough to trust."""
        analyzer = self.domains.get("analyzer")
        if analyzer is None:
            return False
        return analyzer.available and analyzer.confidence >= 0.5

    def can_run_research(self, mode: str = "targeted") -> bool:
        """Check if the requested research mode is available.

        - 'targeted' — always true if session or memory is up
        - 'deep' — requires web access
        """
        if mode == "targeted":
            session = self.domains.get("session_access")
            memory = self.domains.get("memory")
            if session and session.available:
                return True
            if memory and memory.available:
                return True
            return False

        if mode == "deep":
            web = self.domains.get("web")
            return web is not None and web.available

        return False

    def to_dict(self) -> dict:
        return {
            "capability_state": {
                "generated_at_ms": self.generated_at_ms,
                "overall_mode": self.overall_mode,
                "domains": {
                    name: domain.to_dict()
                    for name, domain in self.domains.items()
                },
            }
        }


# ── Builder ─────────────────────────────────────────────────────────────

def build_capability_state(
    *,
    session_ok: bool = False,
    analyzer_ok: bool = False,
    analyzer_fresh: bool = False,
    memory_ok: bool = False,
    web_ok: bool = False,
    flucoma_ok: bool = False,
) -> CapabilityState:
    """Build a CapabilityState from simple boolean probes.

    Pure function — no I/O.  The caller is responsible for probing
    Ableton, the analyzer bridge, memory store, etc.
    """
    domains: dict[str, CapabilityDomain] = {}

    # ── session_access ──────────────────────────────────────────────
    session_reasons: list[str] = []
    if not session_ok:
        session_reasons.append("session_unreachable")
    domains["session_access"] = CapabilityDomain(
        name="session_access",
        available=session_ok,
        confidence=1.0 if session_ok else 0.0,
        mode="healthy" if session_ok else "unavailable",
        reasons=session_reasons,
    )

    # ── analyzer ────────────────────────────────────────────────────
    # BUG-2026-04-26#4: ``available`` requires both device-loaded AND
    # fresh data. The new ``device_loaded`` field exposes the .amxd
    # presence separately, so "I just loaded the analyzer, why does
    # capability_state still say offline?" can be answered correctly:
    # device_loaded=True, available=False, reasons=['analyzer_warming_up'].
    analyzer_reasons: list[str] = []
    if not analyzer_ok:
        analyzer_reasons.append("analyzer_offline")
    elif not analyzer_fresh:
        # Pre-fix this said `analyzer_stale` even immediately after the
        # device finished loading. ``analyzer_warming_up`` is more
        # accurate when the device is present but hasn't streamed a
        # frame yet — distinguishes cold-start from genuine staleness.
        analyzer_reasons.append("analyzer_warming_up")
    analyzer_available = analyzer_ok and analyzer_fresh
    if analyzer_available:
        analyzer_conf = 0.9
        analyzer_mode = "measured"
    elif analyzer_ok:
        analyzer_conf = 0.4
        analyzer_mode = "warming_up"
    else:
        analyzer_conf = 0.0
        analyzer_mode = "unavailable"
    domains["analyzer"] = CapabilityDomain(
        name="analyzer",
        available=analyzer_available,
        confidence=analyzer_conf,
        mode=analyzer_mode,
        reasons=analyzer_reasons,
        device_loaded=analyzer_ok,
    )

    # ── memory ──────────────────────────────────────────────────────
    memory_reasons: list[str] = []
    if not memory_ok:
        memory_reasons.append("memory_unavailable")
    domains["memory"] = CapabilityDomain(
        name="memory",
        available=memory_ok,
        confidence=1.0 if memory_ok else 0.0,
        mode="available" if memory_ok else "unavailable",
        reasons=memory_reasons,
    )

    # ── web ──────────────────────────────────────────────────────────
    # Server-side outbound HTTP capability.  True when the MCP host can
    # reach an arbitrary public URL.  Does NOT imply curated research
    # corpora are installed — see the ``research`` domain below.
    web_reasons: list[str] = []
    if not web_ok:
        web_reasons.append("web_unavailable")
    domains["web"] = CapabilityDomain(
        name="web",
        available=web_ok,
        confidence=0.7 if web_ok else 0.0,
        mode="available" if web_ok else "unavailable",
        reasons=web_reasons,
    )

    # ── flucoma ──────────────────────────────────────────────────────
    # Optional dependency (the ``flucoma`` Python package).  Emitted
    # unconditionally so consumers can distinguish "probed and missing"
    # from "probe not run yet".
    flucoma_reasons: list[str] = []
    if not flucoma_ok:
        flucoma_reasons.append("flucoma_not_installed")
    domains["flucoma"] = CapabilityDomain(
        name="flucoma",
        available=flucoma_ok,
        confidence=0.9 if flucoma_ok else 0.0,
        mode="available" if flucoma_ok else "unavailable",
        reasons=flucoma_reasons,
        device_loaded=flucoma_ok,
    )

    # ── research (composite) ────────────────────────────────────────
    research_reasons: list[str] = []
    research_sources = 0
    if session_ok:
        research_sources += 1
    else:
        research_reasons.append("session_unavailable")
    if memory_ok:
        research_sources += 1
    else:
        research_reasons.append("memory_unavailable")
    if web_ok:
        research_sources += 1
    else:
        research_reasons.append("web_unavailable")

    if research_sources >= 3:
        research_mode = "full"
        research_conf = 1.0
    elif research_sources >= 1:
        research_mode = "targeted_only"
        research_conf = 0.5 + 0.2 * research_sources
    else:
        research_mode = "unavailable"
        research_conf = 0.0

    domains["research"] = CapabilityDomain(
        name="research",
        available=research_sources >= 1,
        confidence=round(research_conf, 2),
        mode=research_mode,
        reasons=research_reasons,
    )

    # ── Overall mode ────────────────────────────────────────────────
    if session_ok and analyzer_ok and analyzer_fresh:
        overall_mode = "normal"
    elif session_ok and analyzer_ok:
        # Analyzer online but data is stale — degraded measurement
        overall_mode = "measured_degraded"
    elif session_ok:
        # Analyzer offline entirely — must rely on judgment alone
        overall_mode = "judgment_only"
    else:
        overall_mode = "read_only"

    return CapabilityState(
        generated_at_ms=int(time.time() * 1000),
        overall_mode=overall_mode,
        domains=domains,
    )

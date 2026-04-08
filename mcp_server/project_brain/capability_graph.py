"""Capability graph builder — maps runtime checks to CapabilityGraph fields.

Reuses runtime/capability_state.build_capability_state for the domain logic,
then maps results to the brain CapabilityGraph model.

Pure computation, zero I/O.
"""

from __future__ import annotations

from typing import Any

from ..runtime.capability_state import build_capability_state
from .models import CapabilityGraph


def build_capability_graph(
    analyzer_ok: bool = False,
    flucoma_ok: bool = False,
    plugin_health: dict[str, Any] | None = None,
    session_ok: bool = True,
    memory_ok: bool = False,
    web_ok: bool = False,
    analyzer_fresh: bool = False,
) -> CapabilityGraph:
    """Build a CapabilityGraph from runtime probe results.

    Args:
        analyzer_ok: whether the M4L analyzer bridge is responding.
        flucoma_ok: whether FluCoMa is available.
        plugin_health: dict of plugin_name -> health info (parameter_count, etc.).
        session_ok: whether Ableton session is reachable.
        memory_ok: whether technique memory is available.
        web_ok: whether web research is available.
        analyzer_fresh: whether analyzer data is fresh (< 5s old).

    Returns:
        CapabilityGraph with all fields populated (freshness unfreshed).
    """
    # Delegate to capability_state for domain reasoning
    cap_state = build_capability_state(
        session_ok=session_ok,
        analyzer_ok=analyzer_ok,
        analyzer_fresh=analyzer_fresh,
        memory_ok=memory_ok,
        web_ok=web_ok,
        flucoma_ok=flucoma_ok,
    )

    # Map to brain model
    graph = CapabilityGraph(
        analyzer_available=analyzer_ok and analyzer_fresh,
        flucoma_available=flucoma_ok,
        plugin_health=plugin_health or {},
    )

    # Populate research providers from capability state domains
    research_providers = []
    for domain_name, domain in cap_state.domains.items():
        if domain.available and domain_name in ("session_access", "memory", "web"):
            research_providers.append(domain_name)
    graph.research_providers = sorted(research_providers)

    return graph

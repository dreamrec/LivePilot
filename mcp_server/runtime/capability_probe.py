"""Runtime capability probe — detects what's available at startup.

Reports capability tiers: Core Control, Analyzer-Enhanced,
Offline Analysis, Creative Intelligence, Persistent Memory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def probe_capabilities(
    ableton: Any = None,
    ctx: Any = None,
) -> dict:
    """Probe runtime capabilities and return a structured report.

    Can be called at startup or on demand via --doctor.
    """
    report: dict[str, dict] = {}

    # 1. Ableton reachability
    ableton_ok = False
    if ableton is not None:
        try:
            info = ableton.send_command("ping")
            ableton_ok = info is not None
        except Exception:
            pass
    report["ableton"] = {
        "status": "ok" if ableton_ok else "unavailable",
        "detail": "TCP 9878 connection active" if ableton_ok else "Not connected",
    }

    # 2. Remote Script parity
    from .remote_commands import REMOTE_COMMANDS
    report["remote_script"] = {
        "status": "ok",
        "command_count": len(REMOTE_COMMANDS),
        "detail": f"{len(REMOTE_COMMANDS)} registered commands",
    }

    # 3. M4L bridge
    bridge_ok = False
    if ctx is not None:
        bridge = getattr(ctx, "lifespan_context", {}).get("m4l_bridge") if hasattr(ctx, "lifespan_context") else None
        bridge_ok = bridge is not None
    report["m4l_bridge"] = {
        "status": "ok" if bridge_ok else "unavailable",
        "detail": "UDP 9880 / OSC 9881 active" if bridge_ok else "Not connected — 30 analyzer tools unavailable",
    }

    # 4. Offline perception
    numpy_ok = False
    try:
        import numpy  # noqa: F401
        numpy_ok = True
    except ImportError:
        pass
    report["offline_perception"] = {
        "status": "ok" if numpy_ok else "degraded",
        "detail": "numpy available" if numpy_ok else "numpy not installed — offline analysis unavailable",
    }

    # 5. Persistence
    livepilot_dir = Path.home() / ".livepilot"
    persistence_ok = livepilot_dir.exists() and os.access(livepilot_dir, os.W_OK)
    taste_exists = (livepilot_dir / "taste.json").exists()
    techniques_exists = (livepilot_dir / "memory" / "techniques.json").exists()
    report["persistence"] = {
        "status": "ok" if persistence_ok else "unavailable",
        "detail": f"~/.livepilot/ {'writable' if persistence_ok else 'not found'}",
        "taste_store": taste_exists,
        "technique_store": techniques_exists,
    }

    # 6. Capability tier
    tier = "core_control"
    if ableton_ok and bridge_ok:
        tier = "analyzer_enhanced"
    elif ableton_ok:
        tier = "core_control"
    if numpy_ok:
        tier = tier  # offline adds to any tier
    report["tier"] = {
        "active": tier,
        "levels": {
            "core_control": ableton_ok,
            "analyzer_enhanced": ableton_ok and bridge_ok,
            "offline_analysis": numpy_ok,
            "creative_intelligence": True,  # always available (heuristic without analyzer)
            "persistent_memory": persistence_ok,
        },
    }

    return report


def format_doctor_report(report: dict) -> str:
    """Format capability report for --doctor output."""
    lines = ["LivePilot Capability Report", "=" * 40]

    icons = {"ok": "  PASS", "unavailable": "  FAIL", "degraded": "  WARN"}

    for area in ["ableton", "remote_script", "m4l_bridge", "offline_perception", "persistence"]:
        info = report.get(area, {})
        status = info.get("status", "unknown")
        icon = icons.get(status, "  ????")
        detail = info.get("detail", "")
        lines.append(f"{icon}  {area}: {detail}")

    tier = report.get("tier", {}).get("active", "unknown")
    lines.append("")
    lines.append(f"Active tier: {tier}")

    return "\n".join(lines)

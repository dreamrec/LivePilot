"""Automation graph builder — scans track devices for automation presence.

Pure computation, zero I/O.
"""

from __future__ import annotations

from .models import AutomationGraph


def build_automation_graph(
    track_infos: list[dict],
    sections: list[dict] | None = None,
) -> AutomationGraph:
    """Build an AutomationGraph by scanning track device info for automation.

    Args:
        track_infos: list of per-track info dicts.  Each may contain:
            - index: track index
            - name: track name
            - devices: [{name, class_name, parameters: [{name, value, is_automated, ...}]}]
        sections: optional list of section dicts (for density_by_section).

    Returns:
        AutomationGraph with automated_params and density_by_section.
    """
    graph = AutomationGraph()

    if not track_infos:
        return graph

    automated_params = []

    for track in track_infos:
        t_idx = track.get("index", 0)
        t_name = track.get("name", "")
        devices = track.get("devices", [])

        for device in devices:
            device_name = device.get("name", device.get("class_name", ""))
            parameters = device.get("parameters", [])

            for param in parameters:
                if param.get("is_automated", False) or param.get("automation_state", 0) > 0:
                    automated_params.append({
                        "track_index": t_idx,
                        "track_name": t_name,
                        "device_name": device_name,
                        "param_name": param.get("name", ""),
                        "param_value": param.get("value"),
                    })

    graph.automated_params = automated_params

    # Compute density_by_section if sections are provided
    if sections:
        total_automated = len(automated_params)
        for sec in sections:
            section_id = sec.get("section_id", "")
            # Without per-section automation data, distribute evenly
            # and weight by section density (more active tracks = more automation)
            sec_density = sec.get("density", 0.0)
            # Automation density approximation: section density * param count ratio
            if total_automated > 0:
                graph.density_by_section[section_id] = round(
                    sec_density * min(total_automated / max(len(track_infos), 1), 1.0),
                    3,
                )
            else:
                graph.density_by_section[section_id] = 0.0

    return graph

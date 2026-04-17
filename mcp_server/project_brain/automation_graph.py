"""Automation graph builder — scans track devices for automation presence.

Pure computation, zero I/O.
"""

from __future__ import annotations

from .models import AutomationGraph


def build_automation_graph(
    track_infos: list[dict],
    sections: list[dict] | None = None,
    clip_automation: list[dict] | None = None,
) -> AutomationGraph:
    """Build an AutomationGraph covering both device-parameter automation
    hints and real clip envelopes (BUG-E2).

    Args:
        track_infos: list of per-track info dicts.  Each may contain:
            - index: track index
            - name: track name
            - devices: [{name, class_name, parameters: [{name, value, is_automated, ...}]}]
        sections: optional list of section dicts (for density_by_section).
        clip_automation: optional list of per-clip envelope descriptors:
            [{section_id, track_index, track_name, clip_index,
              parameter_name, parameter_type, device_name}].
            This is the ground truth — `device.parameters[i].is_automated`
            only reflects mapping state, not the presence of an envelope.

    Returns:
        AutomationGraph with automated_params and density_by_section.
    """
    graph = AutomationGraph()

    if not track_infos and not clip_automation:
        return graph

    automated_params: list[dict] = []
    # Track which (track_index, device_name, param_name) we've already seen
    # so device-hint entries don't duplicate clip-envelope entries.
    seen: set[tuple[int, str, str]] = set()

    # 1) Seed with real clip envelopes. These are the source of truth.
    per_section_counts: dict[str, int] = {}
    for env in clip_automation or []:
        t_idx = int(env.get("track_index", 0))
        dev = str(env.get("device_name") or env.get("parameter_type") or "")
        name = str(env.get("parameter_name") or "")
        key = (t_idx, dev, name)
        if key in seen:
            continue
        seen.add(key)
        automated_params.append({
            "track_index": t_idx,
            "track_name": env.get("track_name", ""),
            "device_name": dev or None,
            "param_name": name,
            "parameter_type": env.get("parameter_type", ""),
            "clip_index": env.get("clip_index"),
            "section_id": env.get("section_id"),
            "source": "clip_envelope",
        })
        sec = env.get("section_id")
        if sec:
            per_section_counts[sec] = per_section_counts.get(sec, 0) + 1

    # 2) Add device-level hints (track-wide is_automated flags) that
    # aren't already covered by an envelope entry.
    for track in track_infos or []:
        t_idx = track.get("index", 0)
        t_name = track.get("name", "")
        devices = track.get("devices", [])

        for device in devices:
            device_name = device.get("name", device.get("class_name", ""))
            parameters = device.get("parameters", [])

            for param in parameters:
                is_flagged = (
                    param.get("is_automated", False)
                    or param.get("automation_state", 0) > 0
                )
                if not is_flagged:
                    continue
                p_name = param.get("name", "")
                key = (t_idx, str(device_name), str(p_name))
                if key in seen:
                    continue
                seen.add(key)
                automated_params.append({
                    "track_index": t_idx,
                    "track_name": t_name,
                    "device_name": device_name,
                    "param_name": p_name,
                    "param_value": param.get("value"),
                    "source": "device_hint",
                })

    graph.automated_params = automated_params

    # Compute density_by_section.
    if sections:
        total_automated = len(automated_params)
        for sec in sections:
            section_id = sec.get("section_id", "")
            if per_section_counts:
                # Use real per-section counts when we have them.
                count = per_section_counts.get(section_id, 0)
                # Normalize by max(1, largest section count) so the
                # densest section is 1.0 and others fall below.
                max_ct = max(per_section_counts.values()) or 1
                graph.density_by_section[section_id] = round(count / max_ct, 3)
            elif total_automated > 0:
                # Fallback: approximate from section density (old behavior)
                sec_density = sec.get("density", 0.0)
                graph.density_by_section[section_id] = round(
                    sec_density * min(total_automated / max(len(track_infos or []), 1), 1.0),
                    3,
                )
            else:
                graph.density_by_section[section_id] = 0.0

    return graph

"""Compilers for performance-safe semantic moves.

Critical rule: NEVER compile to blocked actions (delete, create, device load).
Only volume, pan, send, and automation are allowed.
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove
from . import resolvers


def _compile_recover_energy(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'recover_energy': bring drums+bass back gradually."""
    steps = []
    descriptions = []

    drum_tracks = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    bass_tracks = resolvers.find_tracks_by_role(kernel, ["bass"])

    for dt in drum_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": dt["index"], "volume": 0.70},
            description=f"Restore {dt['name']} to 0.70 for energy recovery",
        ))
        descriptions.append(f"Restore {dt['name']} to 0.70")

    for bt in bass_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": bt["index"], "volume": 0.60},
            description=f"Restore {bt['name']} to 0.60",
        ))
        descriptions.append(f"Restore {bt['name']} to 0.60")

    # Pull reverb back to tighten
    pad_tracks = resolvers.find_tracks_by_role(kernel, ["pad", "chords"])
    for pt in pad_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": pt["index"], "send_index": 0, "value": 0.15},
            description=f"Tighten reverb on {pt['name']} to 0.15",
        ))
        descriptions.append(f"Tighten reverb on {pt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify energy recovered",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No rhythm tracks found",
        requires_approval=False,  # Performance moves execute immediately
    )


def _compile_decompress_tension(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'decompress_tension': pull back energy, open space."""
    steps = []
    descriptions = []

    lead_tracks = resolvers.find_tracks_by_role(kernel, ["lead", "chords"])
    pad_tracks = resolvers.find_tracks_by_role(kernel, ["pad"])

    for lt in lead_tracks[:2]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": lt["index"], "volume": 0.35},
            description=f"Pull {lt['name']} to 0.35 for decompression",
        ))
        descriptions.append(f"Pull {lt['name']} to 0.35")

    for pt in pad_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": pt["index"], "send_index": 0, "value": 0.40},
            description=f"Open reverb on {pt['name']} to 0.40 for spaciousness",
        ))
        descriptions.append(f"Open reverb on {pt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify decompression — energy lower, space wider",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No tracks to decompress",
        requires_approval=False,
    )


def _compile_safe_spotlight(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'safe_spotlight': pull non-spotlight tracks, push one."""
    steps = []
    descriptions = []
    warnings = []

    all_tracks = kernel.get("session_info", {}).get("tracks", [])
    if not all_tracks:
        warnings.append("No tracks found")
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent, warnings=warnings,
            summary="No tracks to spotlight",
        )

    # Spotlight the first lead or melodic track; pull everything else
    lead_tracks = resolvers.find_tracks_by_role(kernel, ["lead", "chords"])
    spotlight = lead_tracks[0] if lead_tracks else all_tracks[0]
    spotlight_idx = spotlight.get("index", 0)
    spotlight_name = spotlight.get("name", f"Track {spotlight_idx}")

    # Pull non-spotlight audio tracks
    for track in all_tracks:
        idx = track.get("index", 0)
        name = track.get("name", "")
        if idx == spotlight_idx:
            continue
        if track.get("type") in ("return", "master"):
            continue
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.30},
            description=f"Pull {name} to 0.30 (background)",
        ))

    # Push spotlight
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": spotlight_idx, "volume": 0.82},
        description=f"Push spotlight {spotlight_name} to 0.82",
    ))
    descriptions.append(f"Spotlight {spotlight_name}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify spotlight dominant, others still audible",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=False,
    )


def _compile_emergency_simplify(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'emergency_simplify': strip to drums+bass only."""
    steps = []
    descriptions = []

    all_tracks = kernel.get("session_info", {}).get("tracks", [])
    drum_tracks = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    bass_tracks = resolvers.find_tracks_by_role(kernel, ["bass"])
    keep_indices = {t["index"] for t in drum_tracks + bass_tracks}

    for track in all_tracks:
        idx = track.get("index", 0)
        name = track.get("name", "")
        if track.get("type") in ("return", "master"):
            continue
        if idx in keep_indices:
            continue
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.10},
            description=f"Strip {name} to 0.10 (emergency simplify)",
        ))

    descriptions.append("Strip to drums+bass only")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify drums+bass dominant, others at background level",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=False,
    )


def _compile_configure_record_readiness(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile configure_record_readiness.

    seed_args:
      track_index: int   — required; must be >= 0 (return tracks can't be armed)
      armed: bool        — required
      exclusive: bool    — optional, default False

    Steps:
      exclusive=True + armed=True
          → N+1 steps: set_track_arm(other_idx, arm=False) for every
            regular track ≠ target, then set_track_arm(target, arm=True).
          — Emulates Ableton's exclusive-arm mode manually. Cannot use
            ``set_exclusive_arm`` directly: ``song.exclusive_arm`` has
            no Python setter in Live 12.4 (property getter only — a
            pre-existing v1.20.3 Remote Script bug surfaced during v1.21's
            live-test pre-flight). The manual disarm loop produces the
            same user-facing outcome (target is the single armed track)
            without depending on the broken toggle.
      else
          → [set_track_arm(track_index, arm=armed)]

    Wire-format discipline: emit `arm` (not `armed`). The remote_command
    backend bypasses the MCP tool rename layer (``tools/tracks.py:317``
    renames ``armed → arm`` before send_command), so the compiler must
    emit ``arm`` directly. See remote_script/LivePilot/tracks.py:263
    for the Remote Script handler.
    """
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    armed = args.get("armed")
    exclusive = args.get("exclusive", False)

    # Required-seed-args
    if track_index is None or armed is None:
        return CompiledPlan(
            move_id=move.move_id,
            intent=move.intent,
            summary="missing required seed_args",
            warnings=[
                "configure_record_readiness requires seed_args.track_index "
                "(int) and seed_args.armed (bool). Example: "
                "apply_semantic_move(\"configure_record_readiness\", "
                "mode=\"explore\", args={\"track_index\": 0, \"armed\": True})"
            ],
        )
    if not isinstance(track_index, int):
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent,
            summary="invalid track_index type",
            warnings=[f"track_index must be int, got {type(track_index).__name__}"],
        )
    if not isinstance(armed, bool):
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent,
            summary="invalid armed type",
            warnings=[f"armed must be bool, got {type(armed).__name__}"],
        )
    if not isinstance(exclusive, bool):
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent,
            summary="invalid exclusive type",
            warnings=[f"exclusive must be bool, got {type(exclusive).__name__}"],
        )

    # Contradiction: exclusive requires armed
    if exclusive and not armed:
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent,
            summary="contradictory exclusive+armed",
            warnings=[
                "exclusive=True requires armed=True (the point of exclusive "
                "is to become the single armed track); to disarm individually "
                "call configure_record_readiness with exclusive=False"
            ],
        )

    # Return-track constraint (Ableton's handler rejects negative indices)
    if track_index < 0:
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent,
            summary="return tracks cannot be armed",
            warnings=[
                f"Cannot arm a return track (track_index={track_index}). "
                "Ableton's set_track_arm handler rejects negative indices "
                "(remote_script/LivePilot/tracks.py:261). Provide a regular "
                "track index (>= 0)."
            ],
        )

    steps: list[CompiledStep] = []
    if exclusive and armed:
        # Manual emulation of Ableton's exclusive-arm mode (set_exclusive_arm
        # handler is broken in Live 12.4 per above docstring). Emit N+1
        # steps: disarm every other regular track, then arm target.
        all_tracks = kernel.get("session_info", {}).get("tracks", []) or []
        if not all_tracks:
            return CompiledPlan(
                move_id=move.move_id, intent=move.intent,
                summary="exclusive mode requires session_info.tracks",
                warnings=[
                    "configure_record_readiness exclusive=True requires "
                    "session_info.tracks to know which other tracks to disarm. "
                    "apply_semantic_move builds session_info automatically; "
                    "direct compiler callers must supply it explicitly."
                ],
            )
        for track in all_tracks:
            idx = track.get("index")
            if idx is None or idx == track_index:
                continue
            # Skip return / master — can't be armed anyway, and Ableton's
            # set_track_arm rejects negative indices (tracks.py:261).
            if track.get("type") in ("return", "master"):
                continue
            if isinstance(idx, int) and idx < 0:
                continue
            name = track.get("name", f"track {idx}")
            steps.append(CompiledStep(
                tool="set_track_arm",
                params={"track_index": idx, "arm": False},
                description=f"Disarm {name} (exclusive-arm emulation)",
                backend="remote_command",
            ))
        steps.append(CompiledStep(
            tool="set_track_arm",
            params={"track_index": track_index, "arm": True},
            description=(
                f"Arm track {track_index} "
                f"(exclusive — single-armed, {len(steps)} other(s) disarmed)"
            ),
            backend="remote_command",
        ))
        summary = (
            f"Exclusive-arm track {track_index} — "
            f"{len(steps)-1} other regular track(s) disarmed first"
        )
    else:
        steps.append(CompiledStep(
            tool="set_track_arm",
            params={"track_index": track_index, "arm": armed},
            description=f"{'Arm' if armed else 'Disarm'} track {track_index}",
            backend="remote_command",
        ))
        summary = f"{'Arm' if armed else 'Disarm'} track {track_index}"

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=summary,
        requires_approval=False,  # Performance moves execute immediately
    )


# ── Register ────────────────────────────────────────────────────────────────

register_compiler("recover_energy", _compile_recover_energy)
register_compiler("decompress_tension", _compile_decompress_tension)
register_compiler("safe_spotlight", _compile_safe_spotlight)
register_compiler("emergency_simplify", _compile_emergency_simplify)
register_compiler("configure_record_readiness", _compile_configure_record_readiness)

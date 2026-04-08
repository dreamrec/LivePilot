"""Performance Engine safety — move classification and policy.

Defines which move types are safe during live performance,
which require caution, and which are blocked entirely.

Zero I/O.
"""

from __future__ import annotations

from .models import EnergyWindow, LiveSafeMove, SceneRole


# ── Move classification sets ──────────────────────────────────────────

SAFE_MOVE_TYPES: frozenset = frozenset({
    "scene_launch",
    "send_nudge",
    "macro_nudge",
    "filter_sweep",
    "mute_toggle",
    "volume_nudge",
})

CAUTION_MOVE_TYPES: frozenset = frozenset({
    "tempo_nudge",
    "device_toggle",
    "pan_nudge",
})

BLOCKED_MOVE_TYPES: frozenset = frozenset({
    "device_chain_surgery",
    "arrangement_edit",
    "track_create_delete",
    "note_edit",
    "clip_create_delete",
})


# ── Classification ────────────────────────────────────────────────────


def classify_move_safety(move_type: str) -> str:
    """Classify a move type as 'safe', 'caution', or 'blocked'.

    Returns:
        'safe' if the move is in SAFE_MOVE_TYPES,
        'blocked' if in BLOCKED_MOVE_TYPES,
        'caution' otherwise (unknown or caution-class moves).
    """
    if move_type in SAFE_MOVE_TYPES:
        return "safe"
    if move_type in BLOCKED_MOVE_TYPES:
        return "blocked"
    return "caution"


# ── Safe move suggestions ─────────────────────────────────────────────


def get_safe_moves(
    scene_roles: list[SceneRole],
    current_scene: int,
    energy_window: EnergyWindow,
) -> list[LiveSafeMove]:
    """Suggest safe moves based on current scene and energy state.

    Returns a list of LiveSafeMove instances — only safe-class moves.
    """
    moves: list[LiveSafeMove] = []

    # Scene launch suggestions: suggest adjacent scenes
    for scene in scene_roles:
        if scene.scene_index == current_scene:
            continue
        energy_delta = scene.energy_level - energy_window.current_energy
        # Suggest scenes that move toward the target energy
        if energy_window.direction == "up" and energy_delta > 0:
            moves.append(LiveSafeMove(
                move_type="scene_launch",
                target=f"scene_{scene.scene_index}",
                description=f"Launch '{scene.name}' (energy {scene.energy_level:.1f}, role: {scene.role})",
                risk_level="safe",
                parameters={"scene_index": scene.scene_index},
                reversible=True,
            ))
        elif energy_window.direction == "down" and energy_delta < 0:
            moves.append(LiveSafeMove(
                move_type="scene_launch",
                target=f"scene_{scene.scene_index}",
                description=f"Launch '{scene.name}' (energy {scene.energy_level:.1f}, role: {scene.role})",
                risk_level="safe",
                parameters={"scene_index": scene.scene_index},
                reversible=True,
            ))
        elif energy_window.direction == "hold":
            # Suggest scenes with similar energy
            if abs(energy_delta) < 0.2:
                moves.append(LiveSafeMove(
                    move_type="scene_launch",
                    target=f"scene_{scene.scene_index}",
                    description=f"Launch '{scene.name}' (similar energy {scene.energy_level:.1f})",
                    risk_level="safe",
                    parameters={"scene_index": scene.scene_index},
                    reversible=True,
                ))

    # Energy-based nudge suggestions
    if energy_window.direction == "up":
        moves.append(LiveSafeMove(
            move_type="volume_nudge",
            target="master",
            description="Nudge master volume up for energy lift",
            risk_level="safe",
            parameters={"delta_db": 1.0},
            reversible=True,
        ))
        moves.append(LiveSafeMove(
            move_type="send_nudge",
            target="reverb_send",
            description="Increase reverb send for spatial expansion",
            risk_level="safe",
            parameters={"delta": 0.05},
            reversible=True,
        ))
    elif energy_window.direction == "down":
        moves.append(LiveSafeMove(
            move_type="filter_sweep",
            target="master",
            description="Low-pass filter sweep to reduce energy",
            risk_level="safe",
            parameters={"direction": "down", "range": [200, 8000]},
            reversible=True,
        ))
        moves.append(LiveSafeMove(
            move_type="mute_toggle",
            target="high_energy_track",
            description="Mute a high-energy layer to reduce intensity",
            risk_level="safe",
            parameters={},
            reversible=True,
        ))

    # Always offer macro nudge as a safe option
    moves.append(LiveSafeMove(
        move_type="macro_nudge",
        target="performance_macro",
        description="Adjust performance macro for subtle variation",
        risk_level="safe",
        parameters={"delta": 0.02},
        reversible=True,
    ))

    return moves


# ── Blocked move list ─────────────────────────────────────────────────


def get_blocked_moves() -> list[str]:
    """Return all blocked move types as a sorted list."""
    return sorted(BLOCKED_MOVE_TYPES)

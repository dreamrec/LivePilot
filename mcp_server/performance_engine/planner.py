"""Performance Engine planner — scene transitions and energy steering.

Pure computation — builds HandoffPlans and suggests energy-aware moves.

Zero I/O.
"""

from __future__ import annotations

from .models import (
    EnergyWindow,
    HandoffPlan,
    LiveSafeMove,
    PerformanceState,
    SceneRole,
)
from .safety import get_blocked_moves, get_safe_moves


# ── Scene transition planning ─────────────────────────────────────────


def plan_scene_transition(
    from_scene: SceneRole,
    to_scene: SceneRole,
) -> HandoffPlan:
    """Plan a transition from one scene to another.

    Generates an energy path (linear interpolation) and
    appropriate transition gestures based on the energy delta
    and role pairing.
    """
    energy_delta = to_scene.energy_level - from_scene.energy_level
    abs_delta = abs(energy_delta)

    # Determine number of steps based on energy distance
    if abs_delta < 0.2:
        steps = 2
    elif abs_delta < 0.5:
        steps = 4
    else:
        steps = 6

    # Build linear energy path
    energy_path: list[float] = []
    for i in range(steps + 1):
        t = i / steps
        energy = from_scene.energy_level + t * energy_delta
        energy_path.append(round(energy, 3))

    # Build gesture sequence
    gestures: list[dict] = []

    # Pre-transition: prepare
    gestures.append({
        "type": "prepare",
        "step": 0,
        "description": f"Prepare transition from '{from_scene.name}' to '{to_scene.name}'",
    })

    # Energy-based transition gestures
    if energy_delta > 0.3:
        # Building energy — use additive layering
        gestures.append({
            "type": "filter_sweep",
            "step": 1,
            "description": "Open filter to build energy",
            "parameters": {"direction": "up"},
        })
        gestures.append({
            "type": "send_nudge",
            "step": 2,
            "description": "Increase send levels for spatial build",
            "parameters": {"delta": 0.1},
        })
    elif energy_delta < -0.3:
        # Dropping energy — use subtractive approach
        gestures.append({
            "type": "filter_sweep",
            "step": 1,
            "description": "Close filter to reduce energy",
            "parameters": {"direction": "down"},
        })
        gestures.append({
            "type": "mute_toggle",
            "step": 2,
            "description": "Strip layers to reduce density",
            "parameters": {},
        })
    else:
        # Similar energy — smooth crossfade
        gestures.append({
            "type": "volume_nudge",
            "step": 1,
            "description": "Smooth crossfade between scenes",
            "parameters": {"delta_db": 0.0},
        })

    # Scene launch at the midpoint
    gestures.append({
        "type": "scene_launch",
        "step": steps // 2,
        "description": f"Launch scene {to_scene.scene_index} ('{to_scene.name}')",
        "parameters": {"scene_index": to_scene.scene_index},
    })

    # Post-transition: settle
    gestures.append({
        "type": "settle",
        "step": steps,
        "description": f"Settle into '{to_scene.name}' ({to_scene.role})",
    })

    return HandoffPlan(
        from_scene=from_scene.scene_index,
        to_scene=to_scene.scene_index,
        gestures=gestures,
        energy_path=energy_path,
    )


# ── Energy-aware move suggestions ─────────────────────────────────────


def suggest_energy_moves(
    energy_window: EnergyWindow,
    scene: SceneRole,
) -> list[LiveSafeMove]:
    """Suggest moves to steer energy toward the target.

    Considers the current scene's role to tailor suggestions.
    """
    moves: list[LiveSafeMove] = []
    gap = energy_window.target_energy - energy_window.current_energy

    if abs(gap) < 0.05:
        # Close enough — hold steady
        moves.append(LiveSafeMove(
            move_type="macro_nudge",
            target="performance_macro",
            description="Maintain current energy — micro-adjust macro for variation",
            risk_level="safe",
            parameters={"delta": 0.01},
            reversible=True,
        ))
        return moves

    if gap > 0:
        # Need more energy
        moves.append(LiveSafeMove(
            move_type="volume_nudge",
            target="master",
            description=f"Lift volume toward target energy ({energy_window.target_energy:.1f})",
            risk_level="safe",
            parameters={"delta_db": min(2.0, gap * 6.0)},
            reversible=True,
        ))
        if scene.role in ("build", "chorus", "drop"):
            moves.append(LiveSafeMove(
                move_type="send_nudge",
                target="delay_send",
                description="Add delay send for rhythmic energy boost",
                risk_level="safe",
                parameters={"delta": min(0.15, gap * 0.3)},
                reversible=True,
            ))
        moves.append(LiveSafeMove(
            move_type="filter_sweep",
            target="master_filter",
            description="Open high-pass for brightness lift",
            risk_level="safe",
            parameters={"direction": "up", "range": [2000, 16000]},
            reversible=True,
        ))
    else:
        # Need less energy
        moves.append(LiveSafeMove(
            move_type="filter_sweep",
            target="master_filter",
            description=f"Low-pass sweep toward target energy ({energy_window.target_energy:.1f})",
            risk_level="safe",
            parameters={"direction": "down", "range": [200, 8000]},
            reversible=True,
        ))
        if scene.role in ("breakdown", "outro", "intro"):
            moves.append(LiveSafeMove(
                move_type="mute_toggle",
                target="percussion_layer",
                description="Mute percussion to soften breakdown",
                risk_level="safe",
                parameters={},
                reversible=True,
            ))
        moves.append(LiveSafeMove(
            move_type="volume_nudge",
            target="master",
            description="Reduce volume toward target energy",
            risk_level="safe",
            parameters={"delta_db": max(-2.0, gap * 6.0)},
            reversible=True,
        ))

    return moves


# ── Build full performance state ──────────────────────────────────────


def build_performance_state(
    scenes: list[SceneRole],
    current_scene_index: int,
) -> PerformanceState:
    """Build a complete PerformanceState from scene roles.

    Computes energy window from current scene context and
    populates safe/blocked move lists.
    """
    # Find current scene
    current = None
    for s in scenes:
        if s.scene_index == current_scene_index:
            current = s
            break

    if current is None:
        # Fallback: use defaults
        current_energy = 0.5
        target_energy = 0.5
        direction = "hold"
    else:
        current_energy = current.energy_level

        # Infer target from adjacent scenes
        next_scenes = [s for s in scenes if s.scene_index > current_scene_index]
        if next_scenes:
            next_scene = min(next_scenes, key=lambda s: s.scene_index)
            target_energy = next_scene.energy_level
        else:
            target_energy = current_energy

        delta = target_energy - current_energy
        if delta > 0.05:
            direction = "up"
        elif delta < -0.05:
            direction = "down"
        else:
            direction = "hold"

    urgency = min(1.0, abs(target_energy - current_energy) * 2.0)

    energy_window = EnergyWindow(
        current_energy=current_energy,
        target_energy=target_energy,
        direction=direction,
        urgency=round(urgency, 3),
    )

    safe_moves = get_safe_moves(scenes, current_scene_index, energy_window)
    blocked = get_blocked_moves()

    return PerformanceState(
        scenes=scenes,
        current_scene=current_scene_index,
        energy_window=energy_window,
        safe_moves=safe_moves,
        blocked_moves=blocked,
    )

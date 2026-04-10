"""Performance-safe semantic moves — safe actions during live performance.

Every move in this family MUST compile only to safe or caution actions.
Blocked actions (delete, create, device load) are never used.
"""

from .models import SemanticMove
from .registry import register

RECOVER_ENERGY = SemanticMove(
    move_id="recover_energy",
    family="performance",
    intent="Recover energy after a breakdown — bring elements back in gradually",
    targets={"energy": 0.5, "cohesion": 0.3, "motion": 0.2},
    protect={"clarity": 0.7},
    risk_level="low",
    required_capabilities=["session"],
    compile_plan=[
        {"tool": "set_track_volume", "params": {"description": "Gradually restore drum volume"}, "description": "Bring drums back"},
        {"tool": "set_track_volume", "params": {"description": "Restore bass volume"}, "description": "Bring bass back"},
        {"tool": "set_track_send", "params": {"description": "Reduce reverb send to tighten mix"}, "description": "Tighten reverb"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "drum and bass tracks producing audio"},
    ],
)

DECOMPRESS_TENSION = SemanticMove(
    move_id="decompress_tension",
    family="performance",
    intent="Release built-up tension — open filters, reduce density, create space",
    targets={"clarity": 0.4, "depth": 0.3, "width": 0.3},
    protect={"cohesion": 0.6},
    risk_level="low",
    required_capabilities=["session"],
    compile_plan=[
        {"tool": "set_track_volume", "params": {"description": "Pull back high-energy elements 15-20%"}, "description": "Pull energy down"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb for spaciousness"}, "description": "Open space"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "all tracks still alive, overall energy decreased"},
    ],
)

SAFE_SPOTLIGHT = SemanticMove(
    move_id="safe_spotlight",
    family="performance",
    intent="Spotlight one element by pulling others back — no muting, just volume balance",
    targets={"contrast": 0.5, "clarity": 0.3, "motion": 0.2},
    protect={"cohesion": 0.7, "energy": 0.5},
    risk_level="low",
    required_capabilities=["session"],
    compile_plan=[
        {"tool": "set_track_volume", "params": {"description": "Pull non-spotlight tracks to 30-40%"}, "description": "Pull background"},
        {"tool": "set_track_volume", "params": {"description": "Push spotlight track to 80-85%"}, "description": "Push spotlight"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "spotlight track clearly dominant, others still audible"},
    ],
)

EMERGENCY_SIMPLIFY = SemanticMove(
    move_id="emergency_simplify",
    family="performance",
    intent="Emergency simplify — pull everything back to drums+bass only for recovery",
    targets={"clarity": 0.6, "cohesion": 0.4},
    protect={"energy": 0.3},
    risk_level="low",
    required_capabilities=["session"],
    compile_plan=[
        {"tool": "set_track_volume", "params": {"description": "Pull all non-rhythm tracks to 10-15%"}, "description": "Strip to essentials"},
        {"tool": "set_track_volume", "params": {"description": "Keep drums at current level"}, "description": "Maintain rhythm"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "drums producing audio, other tracks at low but nonzero level"},
    ],
)

# Register all performance moves
for _move in [RECOVER_ENERGY, DECOMPRESS_TENSION, SAFE_SPOTLIGHT, EMERGENCY_SIMPLIFY]:
    register(_move)

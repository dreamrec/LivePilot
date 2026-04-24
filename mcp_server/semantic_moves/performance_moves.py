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
    plan_template=[
        {"tool": "set_track_volume", "params": {"description": "Gradually restore drum volume"}, "description": "Bring drums back", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Restore bass volume"}, "description": "Bring bass back", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Reduce reverb send to tighten mix"}, "description": "Tighten reverb", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "drum and bass tracks producing audio", "backend": "remote_command"},
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
    plan_template=[
        {"tool": "set_track_volume", "params": {"description": "Pull back high-energy elements 15-20%"}, "description": "Pull energy down", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb for spaciousness"}, "description": "Open space", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "all tracks still alive, overall energy decreased", "backend": "remote_command"},
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
    plan_template=[
        {"tool": "set_track_volume", "params": {"description": "Pull non-spotlight tracks to 30-40%"}, "description": "Pull background", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Push spotlight track to 80-85%"}, "description": "Push spotlight", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "spotlight track clearly dominant, others still audible", "backend": "remote_command"},
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
    plan_template=[
        {"tool": "set_track_volume", "params": {"description": "Pull all non-rhythm tracks to 10-15%"}, "description": "Strip to essentials", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Keep drums at current level"}, "description": "Maintain rhythm", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "drums producing audio, other tracks at low but nonzero level", "backend": "remote_command"},
    ],
)

# v1.21: configure_record_readiness — closes the tech_debt entry from
# v1.20 live test 6 (raw set_track_arm without a semantic-move wrapper).
# seed_args: {track_index: int, armed: bool, exclusive?: bool = False}.
# Note: `armed` here is the *ergonomic* seed_arg name — the compiler
# translates it to the wire-format key `arm` per remote_script/LivePilot/
# tracks.py:263. See _compile_configure_record_readiness.
CONFIGURE_RECORD_READINESS = SemanticMove(
    move_id="configure_record_readiness",
    family="performance",
    intent=(
        "Arm or disarm a track for recording. When exclusive=True, enables "
        "Ableton's exclusive-arm mode so only the target track stays armed "
        "(other regular tracks auto-disarm) — the standard one-take setup."
    ),
    targets={},
    protect={"signal_integrity": 0.7},
    risk_level="low",
    required_capabilities=["session"],
    plan_template=[
        # Informational — compiler builds concrete steps from seed_args.
        {
            "tool": "set_track_arm",
            "params": {"description": "Arm or disarm the target track"},
            "description": "Toggle track arm",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_track_info",
            "check": "track's arm field matches requested value",
            "backend": "remote_command",
        },
    ],
)


# Register all performance moves
for _move in [
    RECOVER_ENERGY,
    DECOMPRESS_TENSION,
    SAFE_SPOTLIGHT,
    EMERGENCY_SIMPLIFY,
    CONFIGURE_RECORD_READINESS,  # v1.21
]:
    register(_move)

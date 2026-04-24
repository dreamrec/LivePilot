"""Device-mutation semantic moves (v1.20) — configure an existing device
in bulk, or remove one with an audit reason.

Both moves take user targets via ``kernel["seed_args"]``. configure_device
uses explicit ``param_overrides: dict`` rather than a preset library —
the preset-YAML infrastructure the original plan called for is deferred
to v1.21 so this commit can ship at-budget without widening blast radius.
Once a preset library lands, it can layer on top: the preset is just a
resolved param_overrides dict.
"""

from .models import SemanticMove
from .registry import register


CONFIGURE_DEVICE = SemanticMove(
    move_id="configure_device",
    family="sound_design",
    intent=(
        "Reconfigure an existing device in bulk — set multiple parameters "
        "in a single undoable move. Takes track_index, device_index, and "
        "a param_overrides dict ({param_name: value}) via seed_args."
    ),
    # Reconfiguring a device touches timbre + depth + clarity in a general
    # way; caller scopes intent through the specific param_overrides dict
    # they pass, and taste alignment happens per-dimension at rank time.
    targets={"timbre": 0.4, "depth": 0.3, "clarity": 0.3},
    protect={},
    risk_level="low",
    plan_template=[
        {
            "tool": "batch_set_parameters",
            "params": {
                "description": (
                    "Apply param_overrides dict as a single batch_set_parameters call"
                ),
            },
            "description": "Configure device parameters in one move",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_device_parameters",
            "check": "requested parameter values match the overrides",
            "backend": "remote_command",
        },
    ],
)

REMOVE_DEVICE = SemanticMove(
    move_id="remove_device",
    family="sound_design",
    intent=(
        "Remove a device from a track — destructive but undoable via Live's "
        "undo stack. Takes track_index, device_index, and a human-readable "
        "reason via seed_args. Reason is logged to session memory for audit."
    ),
    targets={},
    # Removing a device on an active signal path can silence audio entirely.
    # Caller is responsible for ensuring the device isn't load-bearing.
    protect={"signal_integrity": 0.9},
    risk_level="medium",
    plan_template=[
        {
            "tool": "delete_device",
            "params": {"description": "Delete the target device"},
            "description": "Remove the device",
            "backend": "remote_command",
        },
        {
            "tool": "add_session_memory",
            "params": {
                "description": (
                    "Log the reason under category=device_removal so the audit "
                    "trail survives anti-repetition scrubbing"
                ),
            },
            "description": "Log removal reason",
            "backend": "mcp_tool",
        },
    ],
    verification_plan=[
        {
            "tool": "get_track_info",
            "check": "device count on track decreased by 1",
            "backend": "remote_command",
        },
    ],
)


for _move in (CONFIGURE_DEVICE, REMOVE_DEVICE):
    register(_move)

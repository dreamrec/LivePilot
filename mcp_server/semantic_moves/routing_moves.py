"""Routing-domain semantic moves (v1.20) — build send chains, configure
send architectures, rewire track outputs.

These moves take user-supplied targets via ``kernel["seed_args"]`` (threaded
through by ``apply_semantic_move(args=...)`` / ``preview_semantic_move(args=...)``).
Compilers are pure and live in :mod:`routing_compilers`.

The routing family exists to give the Creative Director Phase 6 a
semantic_move path for three raw-tool patterns that previously required
the escape hatch:

    * Loading a chain of devices onto a return track (dub/ambient sends)
    * Setting send levels across a bunch of source tracks in one move
    * Rewiring a track's output routing (e.g., "Sends Only")
"""

from .models import SemanticMove
from .registry import register


BUILD_SEND_CHAIN = SemanticMove(
    move_id="build_send_chain",
    family="device_creation",
    intent=(
        "Build a device chain on a return track — e.g., a dub Echo → "
        "Auto Filter → Convolution Reverb send architecture. Takes the "
        "return_track_index and an ordered device_chain list via seed_args."
    ),
    targets={"space": 0.4, "depth": 0.3, "cohesion": 0.3},
    protect={"low_end": 0.6},
    risk_level="medium",
    plan_template=[
        {
            "tool": "find_and_load_device",
            "params": {"description": "Load each device in device_chain onto the return track, in order"},
            "description": "Load device chain onto return",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_track_info",
            "check": "return track now shows the loaded devices in the expected order",
            "backend": "remote_command",
        },
    ],
)

CONFIGURE_SEND_ARCHITECTURE = SemanticMove(
    move_id="configure_send_architecture",
    family="mix",
    intent=(
        "Set send levels across a set of source tracks in a single move — "
        "e.g., route three source tracks to the Reverb return at balanced "
        "levels. Takes source_track_indices, send_index, levels via seed_args."
    ),
    targets={"space": 0.5, "depth": 0.3, "cohesion": 0.2},
    protect={"clarity": 0.5},
    risk_level="low",
    plan_template=[
        {
            "tool": "set_track_send",
            "params": {"description": "One set_track_send call per (track, level) pair"},
            "description": "Apply send levels",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_track_info",
            "check": "each source track's send value matches the requested level",
            "backend": "remote_command",
        },
    ],
)

SET_TRACK_ROUTING_MOVE = SemanticMove(
    move_id="set_track_routing",
    family="mix",
    intent=(
        "Rewire a track's output routing — e.g., switch an intermediate "
        "track to 'Sends Only' for a bus architecture. Takes track_index "
        "plus output_routing_type/channel via seed_args."
    ),
    # Routing is topology, not a dimension claim; protect clarity because a
    # bad routing move can silence the track entirely.
    targets={},
    protect={"clarity": 0.5},
    risk_level="medium",
    plan_template=[
        {
            "tool": "set_track_routing",
            "params": {"description": "Single set_track_routing call with the provided output fields"},
            "description": "Rewire track output routing",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_track_routing",
            "check": "output_type and output_channel match the requested values",
            "backend": "remote_command",
        },
    ],
)


for _move in (BUILD_SEND_CHAIN, CONFIGURE_SEND_ARCHITECTURE, SET_TRACK_ROUTING_MOVE):
    register(_move)

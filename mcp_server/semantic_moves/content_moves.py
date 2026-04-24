"""Content-domain semantic moves (v1.20) — create MIDI chord-source clips
and build drum rack pads one at a time.

Both moves take user targets via ``kernel["seed_args"]``. Content moves
complement the routing family: load_chord_source produces the source clip
that a build_send_chain return chain processes; create_drum_rack_pad is
the one-pad-at-a-time primitive for programming kits à la Dilla's
isolated-voice workflow.
"""

from .models import SemanticMove
from .registry import register


LOAD_CHORD_SOURCE = SemanticMove(
    move_id="load_chord_source",
    family="sound_design",
    intent=(
        "Create a named MIDI chord clip in a specific slot — the single-source "
        "feed for dub / ambient send architectures. Takes track_index, "
        "clip_slot, notes (list of {pitch, start_time, duration, velocity}), "
        "name, and optional length_beats (default 4.0) via seed_args."
    ),
    targets={"harmonic": 0.4, "depth": 0.3, "clarity": 0.3},
    protect={"cohesion": 0.6},
    risk_level="low",
    plan_template=[
        {
            "tool": "create_clip",
            "params": {"description": "Empty MIDI clip of length_beats"},
            "description": "Create empty MIDI clip",
            "backend": "remote_command",
        },
        {
            "tool": "add_notes",
            "params": {"description": "Add the chord voicing notes"},
            "description": "Add chord voicing",
            "backend": "remote_command",
        },
        {
            "tool": "set_clip_name",
            "params": {"description": "Name the clip so it's identifiable"},
            "description": "Name the clip",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_clip_info",
            "check": "clip exists at track/slot, has expected name + note count",
            "backend": "remote_command",
        },
    ],
)

CREATE_DRUM_RACK_PAD_MOVE = SemanticMove(
    move_id="create_drum_rack_pad",
    family="device_creation",
    intent=(
        "Add one pad to a Drum Rack — kick, snare, hat, etc. Takes "
        "track_index, pad_note (MIDI 0-127), file_path (absolute), and "
        "optional rack_device_index + chain_name via seed_args. Wraps the "
        "Live 12.4 native replace_sample_native flow."
    ),
    targets={"groove": 0.5, "punch": 0.3, "contrast": 0.2},
    protect={"cohesion": 0.6},
    risk_level="low",
    plan_template=[
        {
            "tool": "add_drum_rack_pad",
            "params": {"description": "Single atomic pad build + sample load"},
            "description": "Build drum rack pad",
            "backend": "mcp_tool",
        },
    ],
    verification_plan=[
        {
            "tool": "get_rack_chains",
            "check": "new chain exists on the rack, trigger note matches pad_note",
            "backend": "remote_command",
        },
    ],
)


for _move in (LOAD_CHORD_SOURCE, CREATE_DRUM_RACK_PAD_MOVE):
    register(_move)

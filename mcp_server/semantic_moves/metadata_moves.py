"""Metadata-domain semantic moves (v1.20) — groove configuration, scene
metadata, and bundled track rename/color.

These moves collapse the most common "touch a few fields at once"
patterns from Phase 6 into single named intents. set_track_metadata
specifically bundles rename + color since they're always paired when a
director is labelling a new track.
"""

from .models import SemanticMove
from .registry import register


CONFIGURE_GROOVE = SemanticMove(
    move_id="configure_groove",
    family="arrangement",
    intent=(
        "Assign a groove to one or more clips and optionally tune its "
        "timing amount — the Dilla-swing primitive. Takes track_index, "
        "clip_indices (list), groove_id, and optional timing_amount "
        "(0.0-1.0) via seed_args. Agent pre-resolves groove_id via list_grooves()."
    ),
    targets={"groove": 0.6, "motion": 0.2, "contrast": 0.2},
    protect={"clarity": 0.5},
    risk_level="low",
    plan_template=[
        {
            "tool": "assign_clip_groove",
            "params": {"description": "Assign groove to each clip in clip_indices"},
            "description": "Assign groove to clips",
            "backend": "remote_command",
        },
        {
            "tool": "set_groove_params",
            "params": {"description": "Tune groove timing_amount if provided"},
            "description": "Tune groove timing",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_clip_groove",
            "check": "each clip now shows the expected groove_id",
            "backend": "remote_command",
        },
    ],
)

SET_SCENE_METADATA = SemanticMove(
    move_id="set_scene_metadata",
    family="arrangement",
    intent=(
        "Set scene metadata (name/color/tempo) in a single move. Each "
        "field is optional — the compiler emits one step per provided "
        "field. set_scene_tempo does affect playback timing when the "
        "scene is fired; caller should consider."
    ),
    targets={},
    protect={},
    risk_level="low",
    plan_template=[
        {
            "tool": "set_scene_name",
            "params": {"description": "When name is provided in seed_args"},
            "description": "Rename scene",
            "backend": "remote_command",
        },
        {
            "tool": "set_scene_color",
            "params": {"description": "When color_index is provided"},
            "description": "Color scene",
            "backend": "remote_command",
        },
        {
            "tool": "set_scene_tempo",
            "params": {"description": "When tempo is provided"},
            "description": "Set scene tempo",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_scenes_info",
            "check": "scene shows the new metadata fields",
            "backend": "remote_command",
        },
    ],
)

SET_TRACK_METADATA = SemanticMove(
    move_id="set_track_metadata",
    family="mix",
    intent=(
        "Set track name and/or color in a single bundled move. Both "
        "fields are optional; at least one required. The bundling is "
        "intentional — Phase 6 usage always pairs rename with color."
    ),
    targets={},
    protect={},
    risk_level="low",
    plan_template=[
        {
            "tool": "set_track_name",
            "params": {"description": "When name is provided"},
            "description": "Rename track",
            "backend": "remote_command",
        },
        {
            "tool": "set_track_color",
            "params": {"description": "When color_index is provided"},
            "description": "Color track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {
            "tool": "get_track_info",
            "check": "track name / color match the requested values",
            "backend": "remote_command",
        },
    ],
)


for _move in (CONFIGURE_GROOVE, SET_SCENE_METADATA, SET_TRACK_METADATA):
    register(_move)

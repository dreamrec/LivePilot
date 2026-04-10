"""Transition-domain semantic moves — musical intents for section transitions."""

from .models import SemanticMove
from .registry import register

INCREASE_FORWARD_MOTION = SemanticMove(
    move_id="increase_forward_motion",
    family="transition",
    intent="Increase forward motion and momentum toward the next section",
    targets={"motion": 0.5, "energy": 0.3, "tension": 0.2},
    protect={"clarity": 0.6},
    risk_level="low",
    compile_plan=[
        {"tool": "apply_automation_shape", "params": {"curve_type": "exponential", "description": "Rising filter cutoff over 4 bars"}, "description": "Rising filter sweep"},
        {"tool": "set_track_volume", "params": {"description": "Push rhythm elements +5-8%"}, "description": "Push rhythm forward"},
        {"tool": "apply_automation_shape", "params": {"curve_type": "linear", "description": "Rising reverb send for anticipation"}, "description": "Build reverb wash"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "energy increasing, all tracks alive"},
    ],
)

OPEN_CHORUS = SemanticMove(
    move_id="open_chorus",
    family="transition",
    intent="Open into a chorus — maximize width, energy, and brightness",
    targets={"energy": 0.4, "width": 0.3, "contrast": 0.3},
    protect={"clarity": 0.6, "cohesion": 0.5},
    risk_level="medium",
    compile_plan=[
        {"tool": "set_track_volume", "params": {"description": "Push all melodic tracks +10-15%"}, "description": "Push chorus energy"},
        {"tool": "set_track_pan", "params": {"description": "Widen stereo field on chords/pads"}, "description": "Widen stereo"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb/delay sends for spaciousness"}, "description": "Add space"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "overall energy increased, stereo field wider"},
        {"tool": "analyze_mix", "check": "no clipping, stereo.mono_risk is false"},
    ],
)

CREATE_BREAKDOWN = SemanticMove(
    move_id="create_breakdown",
    family="transition",
    intent="Create a breakdown — strip to minimal elements for contrast before rebuild",
    targets={"contrast": 0.5, "depth": 0.3, "clarity": 0.2},
    protect={"cohesion": 0.5},
    risk_level="medium",
    compile_plan=[
        {"tool": "set_track_volume", "params": {"description": "Pull drums to 20-30%"}, "description": "Strip drums"},
        {"tool": "set_track_volume", "params": {"description": "Pull bass to 30-40%"}, "description": "Reduce bass"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb send on remaining elements"}, "description": "Add reverb depth"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "energy significantly reduced, at least one element still prominent"},
    ],
)

BRIDGE_SECTIONS = SemanticMove(
    move_id="bridge_sections",
    family="transition",
    intent="Bridge between two sections with a transitional passage — filter sweep + density shift",
    targets={"motion": 0.4, "contrast": 0.3, "cohesion": 0.3},
    protect={"clarity": 0.6},
    risk_level="low",
    compile_plan=[
        {"tool": "apply_automation_shape", "params": {"curve_type": "cosine", "description": "Gentle filter sweep across bridge"}, "description": "Bridge filter motion"},
        {"tool": "set_track_volume", "params": {"description": "Gentle volume crossfade between section elements"}, "description": "Crossfade elements"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "smooth level transition, no dropouts"},
    ],
)

# Register all transition moves
for _move in [INCREASE_FORWARD_MOTION, OPEN_CHORUS, CREATE_BREAKDOWN, BRIDGE_SECTIONS]:
    register(_move)

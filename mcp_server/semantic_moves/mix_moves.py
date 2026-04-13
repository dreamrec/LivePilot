"""Mix-domain semantic moves — musical intents for mixing and balance."""

from .models import SemanticMove
from .registry import register

TIGHTEN_LOW_END = SemanticMove(
    move_id="tighten_low_end",
    family="mix",
    intent="Tighten the low end — reduce sub mud, add bass definition",
    targets={"weight": 0.4, "punch": 0.3, "clarity": 0.3},
    protect={"warmth": 0.6},
    risk_level="low",
    plan_template=[
        {"tool": "get_master_spectrum", "params": {}, "description": "Check current sub/low balance", "backend": "mcp_tool"},
        {"tool": "set_device_parameter", "params": {"description": "High-pass sub bass around 30-40 Hz"}, "description": "HP filter sub rumble", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Reduce sub bass volume 5-10% if sub > 50%"}, "description": "Reduce sub volume", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Gentle saturation drive +2-4dB for harmonic definition"}, "description": "Add bass harmonics", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_master_spectrum", "check": "sub band should decrease, low-mid stable", "backend": "mcp_tool"},
        {"tool": "get_track_meters", "check": "bass track still producing audio", "backend": "remote_command"},
    ],
)

WIDEN_STEREO = SemanticMove(
    move_id="widen_stereo",
    family="mix",
    intent="Widen the stereo field without losing center focus",
    targets={"width": 0.5, "clarity": 0.3, "depth": 0.2},
    protect={"cohesion": 0.7},
    risk_level="low",
    plan_template=[
        {"tool": "analyze_mix", "params": {}, "description": "Check current stereo state", "backend": "mcp_tool"},
        {"tool": "set_track_pan", "params": {"description": "Pan harmonic elements wider: +/-25-40%"}, "description": "Pan harmonics wider", "backend": "remote_command"},
        {"tool": "set_track_pan", "params": {"description": "Pan percussion subtly: +/-10-20%"}, "description": "Pan perc subtly", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb send on wide elements +10-15%"}, "description": "Add depth to wide elements", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "all tracks producing stereo output", "backend": "remote_command"},
        {"tool": "analyze_mix", "check": "stereo.mono_risk is false, side_activity > 0.1", "backend": "mcp_tool"},
    ],
)

MAKE_PUNCHIER = SemanticMove(
    move_id="make_punchier",
    family="mix",
    intent="Increase punch and transient impact across the mix",
    targets={"punch": 0.5, "energy": 0.3, "contrast": 0.2},
    protect={"clarity": 0.7, "warmth": 0.5},
    risk_level="low",
    plan_template=[
        {"tool": "get_track_meters", "params": {"include_stereo": True}, "description": "Read current levels", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Push drum track +5-8%"}, "description": "Push drum level", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Pull pad/texture -5-10%"}, "description": "Pull back pads", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Lower Glue Compressor threshold 2-3dB if on master"}, "description": "Tighten master bus", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_master_spectrum", "check": "mid and high-mid energy increased relative to before", "backend": "mcp_tool"},
        {"tool": "get_track_meters", "check": "all tracks still producing audio", "backend": "remote_command"},
    ],
)

DARKEN_MIX = SemanticMove(
    move_id="darken_without_losing_width",
    family="mix",
    intent="Darken the mix tone by rolling off highs without collapsing stereo",
    targets={"warmth": 0.5, "depth": 0.3, "width": 0.2},
    protect={"width": 0.7, "clarity": 0.5},
    risk_level="low",
    plan_template=[
        {"tool": "get_master_spectrum", "params": {}, "description": "Check current tonal balance", "backend": "mcp_tool"},
        {"tool": "set_device_parameter", "params": {"description": "Lower EQ/Auto Filter high shelf -2-4dB on bright tracks"}, "description": "Roll off highs", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb send on darkened elements for depth compensation"}, "description": "Compensate depth", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_master_spectrum", "check": "high and air bands decreased, low-mid stable or increased", "backend": "mcp_tool"},
        {"tool": "get_track_meters", "check": "all tracks producing audio (filter didn't kill signal)", "backend": "remote_command"},
    ],
)

REDUCE_REPETITION = SemanticMove(
    move_id="reduce_repetition_fatigue",
    family="mix",
    intent="Reduce repetition fatigue by adding organic movement and variation",
    targets={"motion": 0.4, "novelty": 0.3, "contrast": 0.3},
    protect={"cohesion": 0.6},
    risk_level="medium",
    plan_template=[
        {"tool": "apply_automation_shape", "params": {"curve_type": "perlin", "description": "Perlin noise on filter cutoff"}, "description": "Add organic filter drift", "backend": "mcp_tool"},
        {"tool": "apply_automation_shape", "params": {"curve_type": "perlin", "description": "Perlin noise on send levels"}, "description": "Add depth movement", "backend": "mcp_tool"},
        {"tool": "set_device_parameter", "params": {"description": "Increase Beat Repeat variation or chance"}, "description": "Add rhythmic variation", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "all tracks still producing audio", "backend": "remote_command"},
        {"tool": "capture_audio", "check": "LRA > 2 LU (dynamic range should increase)", "backend": "mcp_tool"},
    ],
)

MAKE_KICK_BASS_LOCK = SemanticMove(
    move_id="make_kick_bass_lock",
    family="mix",
    intent="Make kick and bass work together — frequency separation + timing",
    targets={"weight": 0.4, "punch": 0.3, "groove": 0.3},
    protect={"warmth": 0.6, "cohesion": 0.7},
    risk_level="low",
    plan_template=[
        {"tool": "get_device_parameters", "params": {"description": "Read bass EQ/filter state"}, "description": "Inspect bass chain", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "High-pass bass at 40-60 Hz to clear space for kick sub"}, "description": "HP bass for kick clearance", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Sidechain compressor or volume duck on bass from kick"}, "description": "Duck bass on kick hits", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_master_spectrum", "check": "sub and low bands balanced, no masking", "backend": "mcp_tool"},
        {"tool": "get_track_meters", "check": "both kick and bass tracks producing audio", "backend": "remote_command"},
    ],
)

CREATE_BUILDUP_TENSION = SemanticMove(
    move_id="create_buildup_tension",
    family="arrangement",
    intent="Create tension and energy buildup toward a drop or chorus",
    targets={"tension": 0.5, "energy": 0.3, "contrast": 0.2},
    protect={"clarity": 0.6},
    risk_level="medium",
    plan_template=[
        {"tool": "apply_gesture_template", "params": {"template_name": "tension_ratchet"}, "description": "Apply staged tension ratchet", "backend": "mcp_tool"},
        {"tool": "apply_automation_shape", "params": {"curve_type": "exponential", "description": "Rising HP filter over 4-8 bars"}, "description": "HP filter rise", "backend": "mcp_tool"},
        {"tool": "set_track_send", "params": {"description": "Increase reverb send for wash effect"}, "description": "Add reverb wash", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_emotional_arc", "check": "tension should increase before target section", "backend": "mcp_tool"},
        {"tool": "get_track_meters", "check": "all tracks still producing audio", "backend": "remote_command"},
    ],
)

SMOOTH_SCENE_HANDOFF = SemanticMove(
    move_id="smooth_scene_handoff",
    family="arrangement",
    intent="Create a smooth transition between two scenes",
    targets={"cohesion": 0.5, "motion": 0.3, "contrast": 0.2},
    protect={"clarity": 0.7},
    risk_level="low",
    plan_template=[
        {"tool": "apply_gesture_template", "params": {"template_name": "pre_arrival_vacuum"}, "description": "Pull energy back before transition", "backend": "mcp_tool"},
        {"tool": "apply_gesture_template", "params": {"template_name": "re_entry_spotlight"}, "description": "Spotlight returning elements", "backend": "mcp_tool"},
    ],
    verification_plan=[
        {"tool": "get_emotional_arc", "check": "transition point should show energy dip then recovery", "backend": "mcp_tool"},
    ],
)

# Register all moves
for _move in [
    TIGHTEN_LOW_END, WIDEN_STEREO, MAKE_PUNCHIER, DARKEN_MIX,
    REDUCE_REPETITION, MAKE_KICK_BASS_LOCK, CREATE_BUILDUP_TENSION,
    SMOOTH_SCENE_HANDOFF,
]:
    register(_move)

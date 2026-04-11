"""Sound-design-domain semantic moves — musical intents for timbre and texture.

These moves prefer native Ableton devices over third-party plugins.
"""

from .models import SemanticMove
from .registry import register

ADD_WARMTH = SemanticMove(
    move_id="add_warmth",
    family="sound_design",
    intent="Add warmth to a track or the mix — gentle saturation and low-mid boost",
    targets={"warmth": 0.5, "depth": 0.3, "cohesion": 0.2},
    protect={"clarity": 0.6, "punch": 0.5},
    risk_level="low",
    compile_plan=[
        {"tool": "set_device_parameter", "params": {"description": "Add Saturator drive +2-4dB for harmonic warmth"}, "description": "Add saturation", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Boost EQ low-mid shelf +1-2dB"}, "description": "Low-mid warmth", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_master_spectrum", "check": "low-mid energy increased, high-mid stable", "backend": "mcp_tool"},
        {"tool": "get_track_meters", "check": "target track producing audio", "backend": "remote_command"},
    ],
)

ADD_TEXTURE = SemanticMove(
    move_id="add_texture",
    family="sound_design",
    intent="Add texture and movement to a static sound — modulation and grain",
    targets={"motion": 0.4, "novelty": 0.3, "depth": 0.3},
    protect={"clarity": 0.6},
    risk_level="medium",
    compile_plan=[
        {"tool": "apply_automation_shape", "params": {"curve_type": "perlin", "description": "Perlin noise on filter cutoff for organic texture"}, "description": "Organic filter motion", "backend": "mcp_tool"},
        {"tool": "set_track_send", "params": {"description": "Increase delay send for spatial texture"}, "description": "Spatial texture via delay", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio with variation", "backend": "remote_command"},
    ],
)

SHAPE_TRANSIENTS = SemanticMove(
    move_id="shape_transients",
    family="sound_design",
    intent="Shape transient character — sharpen or soften attack for rhythmic clarity",
    targets={"punch": 0.5, "clarity": 0.3, "groove": 0.2},
    protect={"warmth": 0.5},
    risk_level="low",
    compile_plan=[
        {"tool": "set_device_parameter", "params": {"description": "Adjust Compressor attack time (faster = sharper transients, slower = rounder)"}, "description": "Shape attack", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Adjust Compressor release for rhythmic pumping"}, "description": "Shape release", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio with expected transient character", "backend": "remote_command"},
    ],
)

ADD_SPACE = SemanticMove(
    move_id="add_space",
    family="sound_design",
    intent="Add spatial depth — reverb, delay, and stereo enhancement without muddying",
    targets={"depth": 0.5, "width": 0.3, "clarity": 0.2},
    protect={"punch": 0.6, "clarity": 0.5},
    risk_level="low",
    compile_plan=[
        {"tool": "set_track_send", "params": {"description": "Increase reverb send to 25-35%"}, "description": "Add reverb depth", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Add subtle delay send 10-15%"}, "description": "Add delay texture", "backend": "remote_command"},
        {"tool": "set_track_pan", "params": {"description": "Widen pan slightly for spatial presence"}, "description": "Widen spatial field", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "stereo output present, no phase cancellation", "backend": "remote_command"},
        {"tool": "analyze_mix", "check": "stereo.mono_risk is false", "backend": "mcp_tool"},
    ],
)

# Register all sound design moves
for _move in [ADD_WARMTH, ADD_TEXTURE, SHAPE_TRANSIENTS, ADD_SPACE]:
    register(_move)

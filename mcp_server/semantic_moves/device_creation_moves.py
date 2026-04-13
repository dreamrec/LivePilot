"""Device-creation-domain semantic moves — generate custom M4L devices.

These moves create new instruments and effects on the fly using the
Device Forge. Each move specifies a gen~ template and parameters.
"""

from .models import SemanticMove
from .registry import register

CREATE_CHAOS_MODULATOR = SemanticMove(
    move_id="create_chaos_modulator",
    family="device_creation",
    intent="Generate a Lorenz attractor M4L device for chaotic modulation — "
           "smooth but unpredictable parameter movement",
    targets={"novelty": 0.8, "motion": 0.6, "surprise": 0.7},
    protect={"clarity": 0.5},
    risk_level="medium",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder Chaos Mod",
                "device_type": "audio_effect",
                "description": "Lorenz attractor chaotic modulation source",
            },
            "description": "Generate chaos modulator M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder Chaos Mod"},
            "description": "Load generated device onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio", "backend": "remote_command"},
    ],
)

CREATE_FEEDBACK_RESONATOR = SemanticMove(
    move_id="create_feedback_resonator",
    family="device_creation",
    intent="Generate a tuned comb resonator M4L device — feeds harmonic resonance "
           "at a specific frequency into the signal",
    targets={"depth": 0.6, "texture": 0.5, "novelty": 0.4},
    protect={"clarity": 0.6, "punch": 0.5},
    risk_level="low",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder Resonator",
                "device_type": "audio_effect",
                "description": "Tuned comb filter resonator",
            },
            "description": "Generate resonator M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder Resonator"},
            "description": "Load resonator onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio", "backend": "remote_command"},
    ],
)

CREATE_WAVEFOLDER_EFFECT = SemanticMove(
    move_id="create_wavefolder_effect",
    family="device_creation",
    intent="Generate a Buchla-style wavefolder M4L effect — rich harmonic series "
           "from waveform folding, great for adding edge and complexity",
    targets={"edge": 0.6, "novelty": 0.5, "energy": 0.4},
    protect={"warmth": 0.5},
    risk_level="medium",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder Wavefolder",
                "device_type": "audio_effect",
                "description": "Buchla-style harmonic wavefolder",
            },
            "description": "Generate wavefolder M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder Wavefolder"},
            "description": "Load wavefolder onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio with harmonic content", "backend": "remote_command"},
    ],
)

CREATE_BITCRUSHER_EFFECT = SemanticMove(
    move_id="create_bitcrusher_effect",
    family="device_creation",
    intent="Generate a bitcrusher M4L effect — sample-rate and bit-depth reduction "
           "from subtle aliasing to full digital destruction",
    targets={"edge": 0.5, "novelty": 0.4, "texture": 0.4},
    protect={"clarity": 0.4},
    risk_level="low",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder Bitcrusher",
                "device_type": "audio_effect",
                "description": "Sample-rate and bit-depth crusher",
            },
            "description": "Generate bitcrusher M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder Bitcrusher"},
            "description": "Load bitcrusher onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio", "backend": "remote_command"},
    ],
)

CREATE_KARPLUS_STRING = SemanticMove(
    move_id="create_karplus_string",
    family="device_creation",
    intent="Generate a Karplus-Strong string synth M4L instrument — plucked string "
           "physical model with excitation input",
    targets={"novelty": 0.5, "texture": 0.6, "depth": 0.4},
    protect={"clarity": 0.6},
    risk_level="low",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder String",
                "device_type": "audio_effect",
                "description": "Karplus-Strong plucked string physical model",
            },
            "description": "Generate string synth M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder String"},
            "description": "Load string synth onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio", "backend": "remote_command"},
    ],
)

CREATE_STOCHASTIC_TEXTURE = SemanticMove(
    move_id="create_stochastic_texture",
    family="device_creation",
    intent="Generate a stochastic resonance M4L effect — noise + threshold + feedback "
           "creates granular textures and organic movement",
    targets={"texture": 0.7, "novelty": 0.6, "motion": 0.5},
    protect={"clarity": 0.4},
    risk_level="medium",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder Stochastic",
                "device_type": "audio_effect",
                "description": "Stochastic resonance texture generator",
            },
            "description": "Generate stochastic texture M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder Stochastic"},
            "description": "Load stochastic texture device onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio", "backend": "remote_command"},
    ],
)

CREATE_FDN_REVERB = SemanticMove(
    move_id="create_fdn_reverb",
    family="device_creation",
    intent="Generate a feedback delay network M4L effect — dense, diffuse reverb "
           "with Hadamard-like cross-coupling. Tune delay times for harmonic reverb.",
    targets={"depth": 0.7, "width": 0.5, "novelty": 0.4},
    protect={"punch": 0.5, "clarity": 0.5},
    risk_level="low",
    plan_template=[
        {
            "tool": "generate_m4l_effect",
            "params": {
                "name": "Wonder FDN Verb",
                "device_type": "audio_effect",
                "description": "Feedback delay network reverb",
            },
            "description": "Generate FDN reverb M4L device",
            "backend": "mcp_tool",
        },
        {
            "tool": "find_and_load_device",
            "params": {"query": "Wonder FDN Verb"},
            "description": "Load FDN reverb onto target track",
            "backend": "remote_command",
        },
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio with reverb tail", "backend": "remote_command"},
    ],
)

# Register all device creation moves
for _move in [
    CREATE_CHAOS_MODULATOR,
    CREATE_FEEDBACK_RESONATOR,
    CREATE_WAVEFOLDER_EFFECT,
    CREATE_BITCRUSHER_EFFECT,
    CREATE_KARPLUS_STRING,
    CREATE_STOCHASTIC_TEXTURE,
    CREATE_FDN_REVERB,
]:
    register(_move)

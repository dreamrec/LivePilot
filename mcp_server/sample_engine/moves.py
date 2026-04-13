"""Sample-domain semantic moves — musical intents for sample manipulation.

These moves express creative sample-based intentions that compile to
deterministic tool sequences via the sample compilers.
"""

from ..semantic_moves.models import SemanticMove
from ..semantic_moves.registry import register

SAMPLE_CHOP_RHYTHM = SemanticMove(
    move_id="sample_chop_rhythm",
    family="sample",
    intent="Chop a sample into rhythmic slices — create a new groove from existing material",
    targets={"groove": 0.5, "novelty": 0.3, "punch": 0.2},
    protect={"clarity": 0.6, "coherence": 0.5},
    risk_level="medium",
    plan_template=[
        {"tool": "load_sample_to_simpler", "params": {"description": "Load sample into Simpler for slicing"}, "description": "Load into Simpler", "backend": "bridge_command"},
        {"tool": "set_simpler_playback_mode", "params": {"mode": "slice", "description": "Switch to slice mode for rhythmic chopping"}, "description": "Enable slice mode", "backend": "remote_command"},
        {"tool": "crop_simpler", "params": {"description": "Crop to rhythmically relevant region"}, "description": "Crop to useful region", "backend": "bridge_command"},
    ],
    verification_plan=[
        {"tool": "get_simpler_slices", "check": "slices present and evenly distributed", "backend": "bridge_command"},
        {"tool": "get_track_meters", "check": "track producing audio after slicing", "backend": "remote_command"},
    ],
)

SAMPLE_TEXTURE_LAYER = SemanticMove(
    move_id="sample_texture_layer",
    family="sample",
    intent="Layer a sample as background texture — stretching and filtering for atmosphere",
    targets={"depth": 0.4, "motion": 0.3, "warmth": 0.3},
    protect={"clarity": 0.7, "punch": 0.5},
    risk_level="low",
    plan_template=[
        {"tool": "load_sample_to_simpler", "params": {"description": "Load textural sample into Simpler"}, "description": "Load texture sample", "backend": "bridge_command"},
        {"tool": "set_simpler_playback_mode", "params": {"mode": "classic", "description": "Classic mode for sustained texture playback"}, "description": "Classic playback", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Lower filter cutoff to sit beneath main elements"}, "description": "Filter for background placement", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Add reverb send for spatial depth"}, "description": "Reverb for depth", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio at low level", "backend": "remote_command"},
    ],
)

SAMPLE_VOCAL_GHOST = SemanticMove(
    move_id="sample_vocal_ghost",
    family="sample",
    intent="Create ghostly vocal texture — pitch-shift, reverse, and wash a vocal sample",
    targets={"novelty": 0.4, "depth": 0.3, "motion": 0.3},
    protect={"clarity": 0.5},
    risk_level="medium",
    plan_template=[
        {"tool": "load_sample_to_simpler", "params": {"description": "Load vocal sample into Simpler"}, "description": "Load vocal", "backend": "bridge_command"},
        {"tool": "reverse_simpler", "params": {"description": "Reverse for ghostly character"}, "description": "Reverse vocal", "backend": "bridge_command"},
        {"tool": "set_device_parameter", "params": {"description": "Detune -5 to -12 semitones for haunting pitch"}, "description": "Pitch down for ghost effect", "backend": "remote_command"},
        {"tool": "set_track_send", "params": {"description": "Heavy reverb send 40-60% for wash"}, "description": "Reverb wash", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio with reverb tail", "backend": "remote_command"},
    ],
)

SAMPLE_BREAK_LAYER = SemanticMove(
    move_id="sample_break_layer",
    family="sample",
    intent="Layer a breakbeat over existing drums — slice and rearrange for energy",
    targets={"groove": 0.4, "punch": 0.3, "novelty": 0.3},
    protect={"coherence": 0.6, "clarity": 0.5},
    risk_level="medium",
    plan_template=[
        {"tool": "create_midi_track", "params": {"description": "New track for break layer"}, "description": "Create break track", "backend": "remote_command"},
        {"tool": "load_sample_to_simpler", "params": {"description": "Load breakbeat into Simpler"}, "description": "Load break", "backend": "bridge_command"},
        {"tool": "set_simpler_playback_mode", "params": {"mode": "slice", "slice_by": "transient", "description": "Slice by transients for individual hits"}, "description": "Slice break by transients", "backend": "remote_command"},
        {"tool": "set_track_volume", "params": {"description": "Set break layer volume below main drums"}, "description": "Balance break level", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_simpler_slices", "check": "break sliced into individual hits", "backend": "bridge_command"},
        {"tool": "get_track_meters", "check": "break track producing audio, not overpowering drums", "backend": "remote_command"},
    ],
)

SAMPLE_RESAMPLE_DESTROY = SemanticMove(
    move_id="sample_resample_destroy",
    family="sample",
    intent="Destructively resample — warp, bitcrush, and mangle for creative destruction",
    targets={"novelty": 0.5, "motion": 0.3, "groove": 0.2},
    protect={"coherence": 0.4},
    risk_level="high",
    plan_template=[
        {"tool": "load_sample_to_simpler", "params": {"description": "Load sample for destruction"}, "description": "Load source material", "backend": "bridge_command"},
        {"tool": "warp_simpler", "params": {"description": "Extreme warp settings for time-stretch artifacts"}, "description": "Warp for artifacts", "backend": "bridge_command"},
        {"tool": "set_device_parameter", "params": {"description": "Add Redux or bitcrusher for lo-fi destruction"}, "description": "Bitcrush/reduce", "backend": "remote_command"},
        {"tool": "set_device_parameter", "params": {"description": "Saturator drive to maximum for harmonic distortion"}, "description": "Saturate heavily", "backend": "remote_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "track producing audio, signal significantly transformed", "backend": "remote_command"},
    ],
)

SAMPLE_ONE_SHOT_ACCENT = SemanticMove(
    move_id="sample_one_shot_accent",
    family="sample",
    intent="Place a one-shot sample as rhythmic accent — trigger on key beats for punctuation",
    targets={"punch": 0.4, "groove": 0.3, "novelty": 0.3},
    protect={"clarity": 0.6, "coherence": 0.5},
    risk_level="low",
    plan_template=[
        {"tool": "load_sample_to_simpler", "params": {"description": "Load one-shot into Simpler"}, "description": "Load one-shot", "backend": "bridge_command"},
        {"tool": "set_simpler_playback_mode", "params": {"mode": "one_shot", "description": "One-shot mode for trigger playback"}, "description": "One-shot mode", "backend": "remote_command"},
        {"tool": "crop_simpler", "params": {"description": "Tight crop around the transient"}, "description": "Crop to transient", "backend": "bridge_command"},
    ],
    verification_plan=[
        {"tool": "get_track_meters", "check": "one-shot triggers cleanly on beat", "backend": "remote_command"},
    ],
)

# Register all sample moves
for _move in [
    SAMPLE_CHOP_RHYTHM,
    SAMPLE_TEXTURE_LAYER,
    SAMPLE_VOCAL_GHOST,
    SAMPLE_BREAK_LAYER,
    SAMPLE_RESAMPLE_DESTROY,
    SAMPLE_ONE_SHOT_ACCENT,
]:
    register(_move)

"""42-event structural lexicon — vocabulary of named primitives the agent
can schedule at phrase boundaries. Used by full + develop mode briefs.

Categories: filter, drums, layer, riser, dynamics, harmonic, space.
"""

from __future__ import annotations
from typing import Optional


EVENT_LEXICON: list[dict] = [
    # Filter gestures (5)
    {"name": "hpf_sweep_up", "category": "filter", "description": "HPF rises 80 Hz → 1-2 kHz over 16-32 bars before drop"},
    {"name": "lpf_close_slow", "category": "filter", "description": "LPF closes gradually over 64-128 bars (ambient texture removal)"},
    {"name": "filter_open_snap", "category": "filter", "description": "Sudden filter opening on bar 1 of new section (drop arrival)"},
    {"name": "band_pass_sweep", "category": "filter", "description": "Band-pass center sweeps up over 8 bars (microhouse)"},
    {"name": "filter_wobble_increase", "category": "filter", "description": "LFO-driven filter mod depth increases over 8 bars"},
    # Drum / Rhythm events (11)
    {"name": "kick_dropout", "category": "drums", "description": "Kick muted for 8-16 bars before reintroduction"},
    {"name": "kick_first_entry", "category": "drums", "description": "Kick appears for the first time after percussion-only intro"},
    {"name": "snare_roll_final_bars", "category": "drums", "description": "Snare roll accelerating over bars 15-16 of 16-bar phrase"},
    {"name": "hat_layer_entry", "category": "drums", "description": "Additional hat layer enters (closed → open, or second hat sample)"},
    {"name": "perc_dropout", "category": "drums", "description": "All percussion except kick removed for 4-8 bars (tension)"},
    {"name": "full_drum_dropout", "category": "drums", "description": "All drums including kick removed (breakdown)"},
    {"name": "drum_reintroduction", "category": "drums", "description": "Drums return after full dropout at full energy"},
    {"name": "clap_add", "category": "drums", "description": "Clap or snare enters where only kick existed before"},
    {"name": "ghost_density_increase", "category": "drums", "description": "Ghost note velocity raised across all hats"},
    {"name": "and_of_4_snare", "category": "drums", "description": "Extra snare hit on 'and of 4' on bar 16 (common fill marker)"},
    {"name": "ride_cymbal_add", "category": "drums", "description": "Ride cymbal enters (jazz/DnB open feel)"},
    # Layer entry / exit (9)
    {"name": "layer_fade_in", "category": "layer", "description": "Track volume automation 0 → nominal over 4-8 bars"},
    {"name": "layer_fade_out", "category": "layer", "description": "Track volume nominal → 0 over 8-16 bars"},
    {"name": "layer_hard_cut_in", "category": "layer", "description": "Track unmutes on bar 1 of new section"},
    {"name": "layer_hard_cut_out", "category": "layer", "description": "Track mutes on bar 1 of section change"},
    {"name": "melody_first_entry", "category": "layer", "description": "Lead/melody track introduces for the first time"},
    {"name": "texture_swell", "category": "layer", "description": "Atmosphere/pad rises from inaudible to audible over 32 bars"},
    {"name": "sub_bass_entry", "category": "layer", "description": "Sub-bass track appears for first time"},
    {"name": "pad_strip_to_silence", "category": "layer", "description": "Pad/harmonic layer removed for breakdown isolation"},
    {"name": "vocal_chop_entry", "category": "layer", "description": "Vocal chop track enters"},
    # Riser / Fall events (5)
    {"name": "riser_swell", "category": "riser", "description": "Riser sample triggered at bar 13 of 16-bar phrase (arrives at bar 17)"},
    {"name": "reverse_cymbal", "category": "riser", "description": "Reverse cymbal swell timed to arrive on bar 1 of next section"},
    {"name": "noise_swell", "category": "riser", "description": "White noise volume −inf → 0 dB over 8 bars then cut on drop"},
    {"name": "pitch_riser", "category": "riser", "description": "Sample or synth pitch automating upward over 4-8 bars"},
    {"name": "downlifter", "category": "riser", "description": "Reverse riser / falling pitch for energy drop or breakdown arrival"},
    # Sidechain / Dynamics (4)
    {"name": "sidechain_activate", "category": "dynamics", "description": "Sidechain compressor (pad vs. kick) switches on at section start"},
    {"name": "sidechain_deactivate", "category": "dynamics", "description": "Sidechain removed in breakdown, restoring pad sustain"},
    {"name": "compressor_release_lengthen", "category": "dynamics", "description": "Compressor release extended for swelling effect"},
    {"name": "drum_bus_saturation_increase", "category": "dynamics", "description": "Saturation drive increases during a build"},
    # Harmonic / Melodic (5)
    {"name": "chord_change", "category": "harmonic", "description": "Harmonic progression advances to next chord"},
    {"name": "motif_restatement", "category": "harmonic", "description": "Primary hook returns after absence (ABAB form)"},
    {"name": "motif_inversion", "category": "harmonic", "description": "Inverted motif (IDM/classical variation)"},
    {"name": "motif_fragmentation", "category": "harmonic", "description": "Motif shortened to 1-2 notes, repeated (pre-climax)"},
    {"name": "half_time_shift", "category": "harmonic", "description": "Note durations doubled (groove drops to half-time feel)"},
    # Space / Reverb (3)
    {"name": "reverb_send_increase", "category": "space", "description": "Send to reverb return increases over 4-8 bars"},
    {"name": "dub_throw", "category": "space", "description": "Single 1-beat send spike to delay/reverb"},
    {"name": "full_silence_bar", "category": "space", "description": "1-2 bars of total silence (highest-impact transition tool)"},
]


def get_event_lexicon(category: Optional[str] = None) -> list[dict]:
    """Return the lexicon, optionally filtered by category.

    category: 'filter', 'drums', 'layer', 'riser', 'dynamics', 'harmonic', 'space', or None for all.
    """
    if category is None:
        return list(EVENT_LEXICON)
    return [ev for ev in EVENT_LEXICON if ev["category"] == category]

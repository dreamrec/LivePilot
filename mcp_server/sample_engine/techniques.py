"""Sample Engine technique library — 30+ recipes indexed by material + intent.

Each technique is a named recipe with executable steps mapping to real MCP tools.
The steps use tool names that match LivePilot's existing 297 tools.

Zero I/O — pure data catalog.
"""

from __future__ import annotations

from .models import SampleTechnique, TechniqueStep


# ── Catalog ─────────────────────────────────────────────────────────

_CATALOG: dict[str, SampleTechnique] = {}


def _register(t: SampleTechnique) -> SampleTechnique:
    _CATALOG[t.technique_id] = t
    return t


# ── Category 1: Rhythmic Sampling ──────────────────────────────────

_register(SampleTechnique(
    technique_id="slice_and_sequence",
    name="Slice & Sequence",
    philosophy="surgeon",
    material_types=["drum_loop", "full_mix"],
    intents=["rhythm"],
    difficulty="basic",
    description="Classic MPC-style: load a loop, slice on transients, sequence the slices with MIDI",
    inspiration="MPC workflow — chop and flip",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load sample into new Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Set to Slice mode, slice by Transient"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Read slice positions to understand the rhythm"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 4.0},
                      description="Create a 1-bar MIDI clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program MIDI notes triggering slices (C1=slice1, C#1=slice2, etc.)"),
    ],
    success_signals=["rhythmic pattern audible", "slices trigger cleanly"],
    failure_signals=["silence", "timing drift", "wrong slices triggered"],
))

_register(SampleTechnique(
    technique_id="vocal_chop_rhythm",
    name="Vocal Chop → Rhythmic Instrument",
    philosophy="alchemist",
    material_types=["vocal"],
    intents=["rhythm", "vocal"],
    difficulty="intermediate",
    description="Chop a vocal into syllable-length slices, trigger as staccato rhythmic pattern",
    inspiration="Burial's staccato vocal stabs — ghostly, fragmented",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load vocal into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 2},
                      description="Set to Slice mode, slice by Region (preserves phrases)"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Read slice positions"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 4.0},
                      description="Create MIDI clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program short staccato notes on different slices"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Auto Filter"},
                      description="Add Auto Filter for movement"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Set filter cutoff ~2kHz, resonance ~30% for character"),
    ],
    success_signals=["staccato vocal pattern audible", "rhythmic energy added"],
    failure_signals=["vocals sound unnatural", "timing feels wrong"],
))

_register(SampleTechnique(
    technique_id="micro_chop",
    name="Micro-Chop",
    philosophy="alchemist",
    material_types=["drum_loop", "instrument_loop", "vocal", "full_mix"],
    intents=["rhythm", "transform"],
    difficulty="advanced",
    description="Slice at 1/32 resolution, rearrange fragments with varied velocity — J Dilla micro-timing",
    inspiration="J Dilla — 1/32 slices, disabled quantize, human swing",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load sample into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 3},
                      description="Set to Slice mode, Manual slicing"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 4.0},
                      description="Create MIDI clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program dense 1/32 notes, varied velocity 40-127, slight timing offsets"),
    ],
    success_signals=["choppy rhythmic texture", "organic swing feel"],
    failure_signals=["sounds like a glitch rather than groove"],
))

_register(SampleTechnique(
    technique_id="stab_isolation",
    name="Stab Isolation",
    philosophy="surgeon",
    material_types=["full_mix", "instrument_loop"],
    intents=["rhythm", "melody"],
    difficulty="intermediate",
    description="Isolate a single chord stab from a sample, trigger it rhythmically",
    inspiration="DJ Premier — single chord stab extraction and rhythmic sequencing",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 0},
                      description="Set to Classic mode (manual region selection)"),
        TechniqueStep(tool="crop_simpler",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Crop to just the stab region"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 4.0},
                      description="Create MIDI clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program rhythmic stab pattern"),
    ],
    success_signals=["clean stab playback", "rhythmic pattern feels musical"],
    failure_signals=["stab includes unwanted material", "clicks at boundaries"],
))

_register(SampleTechnique(
    technique_id="euclidean_slice_trigger",
    name="Euclidean Slice Trigger",
    philosophy="alchemist",
    material_types=["drum_loop", "vocal", "instrument_loop"],
    intents=["rhythm", "transform"],
    difficulty="intermediate",
    description="Map Simpler slices to a Euclidean rhythm pattern for polyrhythmic texture",
    inspiration="Euclidean rhythms meet sample chopping — mathematical groove",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load sample into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Slice by Transient"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Read slice count"),
        TechniqueStep(tool="generate_euclidean_rhythm",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Generate Euclidean pattern across slice pitches"),
    ],
    success_signals=["polyrhythmic pattern from sample slices"],
    failure_signals=["pattern too sparse or too dense for context"],
))

# ── Category 2: Textural Transformation ────────────────────────────

_register(SampleTechnique(
    technique_id="extreme_stretch",
    name="Extreme Stretch",
    philosophy="alchemist",
    material_types=["vocal", "drum_loop", "instrument_loop", "one_shot", "texture", "foley", "fx", "full_mix"],
    intents=["texture", "atmosphere"],
    difficulty="basic",
    description="Stretch a sample 10-50x using Texture warp mode — Paulstretch-style ambient wash",
    inspiration="Paulstretch / Stars of the Lid — time as raw material",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load sample into Simpler"),
        TechniqueStep(tool="warp_simpler",
                      params={"track_index": "{track_index}", "device_index": 0, "beats": 64},
                      description="Warp to 16 bars (extreme stretch)"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Add Reverb for space"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Set Reverb decay 8-15s, wet 60-80%"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Set volume -10 to -15dB for subtle layering"),
    ],
    success_signals=["ambient wash audible", "original material unrecognizable"],
    failure_signals=["artifacts or glitches", "too prominent in mix"],
))

_register(SampleTechnique(
    technique_id="drum_to_pad",
    name="Drum-to-Pad",
    philosophy="alchemist",
    material_types=["drum_loop", "one_shot"],
    intents=["texture", "atmosphere"],
    difficulty="intermediate",
    description="Transform a drum hit into an ambient pad via reverse + stretch + reverb",
    inspiration="Turning percussive energy into sustained atmosphere",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load drum sample into Simpler"),
        TechniqueStep(tool="reverse_simpler",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Reverse the sample"),
        TechniqueStep(tool="warp_simpler",
                      params={"track_index": "{track_index}", "device_index": 0, "beats": 32},
                      description="Stretch to 8 bars"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Add long reverb"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Long decay 10s+, wet 70%+"),
    ],
    success_signals=["sustained pad texture from percussion source"],
    failure_signals=["still sounds percussive", "harsh artifacts"],
))

_register(SampleTechnique(
    technique_id="reverse_layer",
    name="Reverse Layer",
    philosophy="alchemist",
    material_types=["vocal", "instrument_loop", "one_shot", "fx"],
    intents=["texture", "atmosphere"],
    difficulty="basic",
    description="Reverse a sample to create pre-echo swells and ghostly textures",
    inspiration="Reversed elements as anticipation and mystery",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load into Simpler"),
        TechniqueStep(tool="reverse_simpler",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Reverse the sample"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Delay"},
                      description="Add delay for tail"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Set volume -8 to -12dB for subtle presence"),
    ],
    success_signals=["reverse swell before downbeat", "ghostly quality"],
    failure_signals=["reverse element too prominent", "timing wrong"],
))

_register(SampleTechnique(
    technique_id="granular_scatter",
    name="Granular Scatter",
    philosophy="alchemist",
    material_types=["vocal", "instrument_loop", "texture", "foley"],
    intents=["texture", "transform"],
    difficulty="intermediate",
    description="Use Grain Delay as a granular engine — scatter grains for cloud textures",
    inspiration="Granular synthesis from existing material — Amon Tobin territory",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load source into Simpler"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Grain Delay"},
                      description="Add Grain Delay after Simpler"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Set spray 100-200ms, frequency random, pitch random ±12st"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Add reverb to smear grains"),
    ],
    success_signals=["granular cloud texture", "original material fragmented"],
    failure_signals=["too chaotic", "no musical quality"],
))

_register(SampleTechnique(
    technique_id="spectral_freeze",
    name="Spectral Freeze",
    philosophy="alchemist",
    material_types=["vocal", "instrument_loop", "full_mix", "texture"],
    intents=["texture", "atmosphere"],
    difficulty="advanced",
    description="Capture one spectral moment and sustain it as a drone/pad",
    inspiration="Spectral freezing — one moment becomes infinite",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load into Simpler"),
        TechniqueStep(tool="crop_simpler",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Crop to a tiny region (50-200ms)"),
        TechniqueStep(tool="warp_simpler",
                      params={"track_index": "{track_index}", "device_index": 0, "beats": 64},
                      description="Extreme stretch of tiny region — spectral freeze"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Reverb for sustain"),
    ],
    success_signals=["sustained spectral tone", "drone quality"],
    failure_signals=["pulsing artifacts", "too short to freeze"],
))

_register(SampleTechnique(
    technique_id="tail_harvest",
    name="Tail Harvest",
    philosophy="alchemist",
    material_types=["vocal", "instrument_loop", "one_shot", "drum_loop"],
    intents=["texture", "atmosphere"],
    difficulty="intermediate",
    description="Resample only the reverb/delay tail of processed material as a new texture",
    inspiration="Capturing the ghost of a sound — only the aftermath",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load source material"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Add reverb with long tail"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Set Reverb to 100% wet, decay 8-15s"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Level for subtle texture"),
    ],
    success_signals=["reverb tail as independent texture layer"],
    failure_signals=["original transient still audible", "tail too thin"],
))

# ── Category 3: Melodic/Harmonic ───────────────────────────────────

_register(SampleTechnique(
    technique_id="key_matched_layer",
    name="Key-Matched Layer",
    philosophy="surgeon",
    material_types=["instrument_loop"],
    intents=["layer", "melody"],
    difficulty="basic",
    description="Transpose sample to match song key, layer behind existing elements",
    inspiration="Seamless sample integration — should sound like it was always there",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load into Simpler"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Transpose to match song key (via Simpler transpose)"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "EQ Eight"},
                      description="Add EQ for frequency carving"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Carve EQ to avoid masking existing elements"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Set volume -6 to -10dB behind existing layers"),
    ],
    success_signals=["sample blends with existing material", "no frequency masking"],
    failure_signals=["key clash audible", "masking with other tracks"],
))

_register(SampleTechnique(
    technique_id="vocal_harmony_stack",
    name="Vocal Harmony Stack",
    philosophy="surgeon",
    material_types=["vocal"],
    intents=["vocal", "layer", "melody"],
    difficulty="advanced",
    description="Pitch-shift vocal to create harmony layers — Bon Iver 'Prismizer' approach",
    inspiration="Bon Iver — vocoder + harmonizer stacked vocal textures",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load vocal into Simpler"),
        TechniqueStep(tool="duplicate_track",
                      params={"track_index": "{track_index}"},
                      description="Duplicate for harmony layer"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Transpose duplicate +3, +5, or +7 semitones for harmony"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Blend harmony -4 to -6dB behind original"),
    ],
    success_signals=["harmonic vocal texture", "pitch layers blend"],
    failure_signals=["robotic artifacts", "dissonant pitch choice"],
))

_register(SampleTechnique(
    technique_id="counterpoint_from_chops",
    name="Counterpoint from Chops",
    philosophy="alchemist",
    material_types=["instrument_loop", "vocal", "full_mix"],
    intents=["melody", "layer"],
    difficulty="advanced",
    description="Create a countermelody by rearranging melodic fragments from a chopped sample",
    inspiration="Four Tet — found-sound countermelody, reorganized musical DNA",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load melodic source"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 1},
                      description="Slice by Beat for melodic fragments"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Read slice positions"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 8.0},
                      description="Create 2-bar clip for countermelody"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program a melodic pattern from slice fragments"),
    ],
    success_signals=["new melody from existing fragments", "musical coherence"],
    failure_signals=["random noise", "no melodic direction"],
))

_register(SampleTechnique(
    technique_id="chord_stab_extraction",
    name="Chord Stab Extraction",
    philosophy="surgeon",
    material_types=["full_mix", "instrument_loop"],
    intents=["melody", "rhythm"],
    difficulty="intermediate",
    description="Isolate chord hits from a full mix and retrigger them rhythmically",
    inspiration="Classic house/disco sample flipping — one chord, infinite groove",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load full mix into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Slice by Transient"),
        TechniqueStep(tool="crop_simpler",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Crop to single chord region"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 4.0},
                      description="Create clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Rhythmic chord stab pattern"),
    ],
    success_signals=["clean chord stab playback", "groovy retrigger pattern"],
    failure_signals=["stab includes drum bleed", "chord unclear"],
))

# ── Category 4: Drum Enhancement ───────────────────────────────────

_register(SampleTechnique(
    technique_id="break_layering",
    name="Break Layering",
    philosophy="surgeon",
    material_types=["drum_loop"],
    intents=["rhythm", "layer"],
    difficulty="basic",
    description="Layer a drum break underneath programmed drums for organic feel",
    inspiration="Classic hip-hop/jungle layering — break under the beat",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load break into Simpler"),
        TechniqueStep(tool="warp_simpler",
                      params={"track_index": "{track_index}", "device_index": 0, "beats": 16},
                      description="Warp to 4 bars to match song tempo"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "EQ Eight"},
                      description="Add EQ for frequency carving"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="High-pass at 200-400Hz to avoid kick clash"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Set volume -10 to -15dB for subtle layer"),
    ],
    success_signals=["break adds organic texture under drums", "no low-end clash"],
    failure_signals=["competing kick patterns", "break overpowers programmed drums"],
))

_register(SampleTechnique(
    technique_id="ghost_note_texture",
    name="Ghost Note Texture",
    philosophy="alchemist",
    material_types=["drum_loop"],
    intents=["rhythm", "texture"],
    difficulty="intermediate",
    description="Filter a drum loop heavily and layer at low volume for ghost-note texture",
    inspiration="Ghost notes in jazz/funk — barely there, adds life",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load loop into Simpler"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Auto Filter"},
                      description="Add Auto Filter"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Band-pass filter ~1-4kHz, narrow Q"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Set volume -18 to -24dB for ghost-level presence"),
    ],
    success_signals=["subtle rhythmic texture felt more than heard"],
    failure_signals=["too loud", "filtering removes all useful content"],
))

_register(SampleTechnique(
    technique_id="transient_replacement",
    name="Transient Replacement",
    philosophy="surgeon",
    material_types=["one_shot"],
    intents=["rhythm", "layer"],
    difficulty="basic",
    description="Layer a one-shot transient over existing drums for punch/character",
    inspiration="Drum layering for weight and impact",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load one-shot into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 0},
                      description="Classic mode for one-shot playback"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 4.0},
                      description="Create clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Trigger on same hits as existing kick/snare"),
    ],
    success_signals=["added punch and character to drums"],
    failure_signals=["phasing with original", "too much attack"],
))

_register(SampleTechnique(
    technique_id="shuffle_extract",
    name="Shuffle Extract",
    philosophy="alchemist",
    material_types=["drum_loop"],
    intents=["rhythm", "transform"],
    difficulty="advanced",
    description="Extract groove timing from a loop and apply it to programmed MIDI",
    inspiration="Stealing the human feel from vinyl breaks",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load break for groove analysis"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Slice by Transient to find hits"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Read slice positions (these are the groove template)"),
    ],
    success_signals=["groove timing captured", "swing values extracted"],
    failure_signals=["slice positions too irregular to use"],
))

# ── Category 5: Vocal Processing ───────────────────────────────────

_register(SampleTechnique(
    technique_id="syllable_instrument",
    name="Syllable Instrument",
    philosophy="alchemist",
    material_types=["vocal"],
    intents=["vocal", "rhythm", "melody"],
    difficulty="advanced",
    description="Chop vocal into individual syllables and play them as a melodic instrument",
    inspiration="Vocal as instrument — each syllable is a playable note",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load vocal into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 2},
                      description="Slice by Region for syllable boundaries"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Map slices to syllables"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 8.0},
                      description="Create 2-bar melodic clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program melody using syllable slices as pitches"),
    ],
    success_signals=["vocal syllables form coherent melody"],
    failure_signals=["syllables cut awkwardly", "no musical phrase"],
))

_register(SampleTechnique(
    technique_id="formant_shift_character",
    name="Formant Shift Character",
    philosophy="alchemist",
    material_types=["vocal"],
    intents=["vocal", "transform"],
    difficulty="intermediate",
    description="Shift vocal formants for alien/robotic/gender-shifted character",
    inspiration="Vocal processing as character creation — not correction",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load vocal into Simpler"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Transpose +5 to +12 semitones (chipmunk) or -5 to -12 (deep)"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Corpus"},
                      description="Add Corpus for resonant body character"),
    ],
    success_signals=["distinctive vocal character", "not obviously pitched"],
    failure_signals=["robotic artifacts", "unintelligible"],
))

_register(SampleTechnique(
    technique_id="vocal_freeze_drone",
    name="Vocal Freeze Drone",
    philosophy="alchemist",
    material_types=["vocal"],
    intents=["texture", "atmosphere"],
    difficulty="intermediate",
    description="Sustain one vowel from a vocal as an ambient pad/drone",
    inspiration="Freezing the human voice into pure tone",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load vocal"),
        TechniqueStep(tool="crop_simpler",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Crop to a single vowel sound (100-300ms)"),
        TechniqueStep(tool="warp_simpler",
                      params={"track_index": "{track_index}", "device_index": 0, "beats": 64},
                      description="Extreme stretch — vowel becomes drone"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Chorus-Ensemble"},
                      description="Add chorus for width"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Add reverb for sustain"),
    ],
    success_signals=["sustained vocal drone", "ethereal pad quality"],
    failure_signals=["pulsing from loop point", "harsh artifacts"],
))

_register(SampleTechnique(
    technique_id="phone_recording_texture",
    name="Phone Recording Texture",
    philosophy="alchemist",
    material_types=["vocal", "foley"],
    intents=["texture", "atmosphere"],
    difficulty="basic",
    description="Lo-fi vocal/field recording as ghostly background texture — Burial's signature",
    inspiration="Burial — phone recordings, pitched down, barely audible ghosts",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load recording into Simpler"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Pitch down -5 to -12 semitones"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Auto Filter"},
                      description="Add lo-pass filter"),
        TechniqueStep(tool="set_device_parameter",
                      params={"track_index": "{track_index}"},
                      description="Filter cutoff ~800Hz for lo-fi character"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Set volume -20 to -30dB — ghost level"),
    ],
    success_signals=["barely audible presence", "adds emotional depth"],
    failure_signals=["too prominent", "distracting from main elements"],
))

# ── Category 6: Resampling Chains ──────────────────────────────────

_register(SampleTechnique(
    technique_id="serial_resample",
    name="Serial Resample",
    philosophy="alchemist",
    material_types=["vocal", "drum_loop", "instrument_loop", "one_shot", "texture", "full_mix"],
    intents=["transform", "texture"],
    difficulty="advanced",
    description="Multi-pass destructive resampling — each pass adds character until unrecognizable",
    inspiration="Amon Tobin — 80+ samples per track, serial destruction",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load source material"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Saturator"},
                      description="Add Saturator for harmonic destruction"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Grain Delay"},
                      description="Add Grain Delay for fragmentation"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "Reverb"},
                      description="Add reverb for smearing"),
        TechniqueStep(tool="freeze_track",
                      params={"track_index": "{track_index}"},
                      description="Freeze to capture processed result"),
        TechniqueStep(tool="flatten_track",
                      params={"track_index": "{track_index}"},
                      description="Flatten — new audio is now the source for next pass"),
    ],
    success_signals=["material transformed beyond recognition", "new texture"],
    failure_signals=["just sounds distorted", "lost all musical quality"],
))

_register(SampleTechnique(
    technique_id="parallel_resample",
    name="Parallel Resample",
    philosophy="alchemist",
    material_types=["vocal", "instrument_loop", "drum_loop"],
    intents=["transform", "layer"],
    difficulty="intermediate",
    description="Process through parallel effect chains and blend for controlled destruction",
    inspiration="Wet/dry parallel processing for controlled chaos",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load into Simpler"),
        TechniqueStep(tool="duplicate_track",
                      params={"track_index": "{track_index}"},
                      description="Duplicate for parallel processing"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}"},
                      description="Add destructive effects to duplicate (distortion, pitch shift)"),
        TechniqueStep(tool="set_track_volume",
                      params={"track_index": "{track_index}"},
                      description="Blend wet/dry: original at 0dB, processed at -6 to -12dB"),
    ],
    success_signals=["controlled textural blend", "best of both worlds"],
    failure_signals=["phase issues between copies", "processed too dominant"],
))

_register(SampleTechnique(
    technique_id="freeze_flatten_rechop",
    name="Freeze-Flatten-Rechop",
    philosophy="alchemist",
    material_types=["vocal", "instrument_loop", "drum_loop", "texture"],
    intents=["transform", "rhythm"],
    difficulty="advanced",
    description="Freeze processed material, flatten to audio, then re-slice the result",
    inspiration="Recursive destruction — chop the chop",
    steps=[
        TechniqueStep(tool="freeze_track",
                      params={"track_index": "{track_index}"},
                      description="Freeze current state to audio"),
        TechniqueStep(tool="flatten_track",
                      params={"track_index": "{track_index}"},
                      description="Flatten to new audio clip"),
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load flattened audio back into Simpler"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Re-slice the processed material"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Read new slice positions"),
    ],
    success_signals=["new rhythmic material from processed audio"],
    failure_signals=["silence after flatten", "no useful slice points"],
))

# ── Category 7: Creative Constraints ───────────────────────────────

_register(SampleTechnique(
    technique_id="one_sample_challenge",
    name="One-Sample Challenge",
    philosophy="alchemist",
    material_types=["vocal", "drum_loop", "instrument_loop", "full_mix", "texture", "foley"],
    intents=["challenge", "transform"],
    difficulty="advanced",
    description="Build an entire beat from a single sample — kick, snare, hat, bass, pad all extracted",
    inspiration="One-sample challenge — constraint breeds creativity",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load the ONE sample"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Slice by Transient"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Map all available slices"),
        TechniqueStep(tool="create_clip",
                      params={"track_index": "{track_index}", "clip_index": 0, "length": 8.0},
                      description="Create 2-bar clip"),
        TechniqueStep(tool="add_notes",
                      params={"track_index": "{track_index}", "clip_index": 0},
                      description="Program full beat using different slices as different drums"),
    ],
    success_signals=["full beat from single source", "each element distinct"],
    failure_signals=["sounds monochromatic", "elements too similar"],
))

_register(SampleTechnique(
    technique_id="found_sound_only",
    name="Found Sound Only",
    philosophy="alchemist",
    material_types=["foley"],
    intents=["challenge", "texture", "rhythm"],
    difficulty="advanced",
    description="Use only non-musical field recordings to build a musical composition",
    inspiration="Musique concrete — all music is organized sound",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load found sound"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 0},
                      description="Slice for rhythmic extraction"),
        TechniqueStep(tool="find_and_load_device",
                      params={"track_index": "{track_index}", "device_name": "EQ Eight"},
                      description="EQ to isolate musical frequencies"),
    ],
    success_signals=["non-musical source produces musical result"],
    failure_signals=["just sounds like noise", "no rhythmic or tonal quality"],
))

_register(SampleTechnique(
    technique_id="reverse_engineering",
    name="Reverse Engineering",
    philosophy="both",
    material_types=["full_mix"],
    intents=["challenge", "layer"],
    difficulty="advanced",
    description="Recreate a reference track's texture by sampling and transforming similar elements",
    inspiration="Reverse engineering a sound — forensic production",
    steps=[
        TechniqueStep(tool="load_sample_to_simpler",
                      params={"track_index": "{track_index}", "file_path": "{file_path}"},
                      description="Load reference material"),
        TechniqueStep(tool="set_simpler_playback_mode",
                      params={"track_index": "{track_index}", "device_index": 0,
                              "playback_mode": 2, "slice_by": 1},
                      description="Slice by Beat to isolate sections"),
        TechniqueStep(tool="get_simpler_slices",
                      params={"track_index": "{track_index}", "device_index": 0},
                      description="Analyze structure via slices"),
    ],
    success_signals=["captured essence of reference sound"],
    failure_signals=["just copied rather than recreated"],
))


# ── Public API ──────────────────────────────────────────────────────


def get_technique(technique_id: str) -> SampleTechnique | None:
    """Get a technique by ID."""
    return _CATALOG.get(technique_id)


def list_techniques() -> list[SampleTechnique]:
    """Return all registered techniques."""
    return list(_CATALOG.values())


def find_techniques(
    material_type: str | None = None,
    intent: str | None = None,
    philosophy: str | None = None,
) -> list[SampleTechnique]:
    """Find techniques matching filters. All filters are AND'd."""
    results = list(_CATALOG.values())

    if material_type:
        results = [t for t in results if material_type in t.material_types]
    if intent:
        results = [t for t in results if intent in t.intents]
    if philosophy:
        results = [t for t in results
                   if t.philosophy == philosophy or t.philosophy == "both"]

    return results

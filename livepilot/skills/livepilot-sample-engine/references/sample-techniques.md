# Sample Technique Catalog — 29 Recipes

## Category 1: Rhythmic Sampling

### slice_and_sequence (Surgeon)
Classic MPC workflow: load loop, slice on transients, sequence with MIDI.
**Material:** drum_loop, full_mix | **Steps:** load -> slice -> get slices -> create clip -> add notes

### vocal_chop_rhythm (Alchemist)
Chop vocal into syllable-length slices, trigger as staccato rhythm. Burial-inspired.
**Material:** vocal | **Steps:** load -> slice by region -> MIDI staccato -> Auto Filter

### micro_chop (Alchemist)
1/32 slices, varied velocity, slight timing offsets. J Dilla micro-timing.
**Material:** any loop | **Steps:** load -> manual slice -> dense 1/32 MIDI

### stab_isolation (Surgeon)
Isolate single chord stab, crop, retrigger rhythmically. DJ Premier style.
**Material:** full_mix, instrument_loop | **Steps:** load -> classic mode -> crop -> MIDI

### euclidean_slice_trigger (Alchemist)
Map Simpler slices to Euclidean rhythm for polyrhythmic texture.
**Material:** drum_loop, vocal, instrument_loop | **Steps:** load -> slice -> Euclidean pattern

## Category 2: Textural Transformation

### extreme_stretch (Alchemist)
Paulstretch-style: Texture warp at 10-50x, reverb wash. Stars of the Lid territory.
**Material:** any | **Steps:** load -> warp 64 beats -> Reverb 60-80% wet

### drum_to_pad (Alchemist)
Reverse + extreme stretch + reverb = drum hit becomes ambient pad.
**Material:** drum_loop, one_shot | **Steps:** load -> reverse -> stretch -> Reverb

### reverse_layer (Alchemist)
Reversed sample as pre-echo swell or ghostly texture.
**Material:** vocal, instrument_loop, one_shot | **Steps:** load -> reverse -> Delay

### granular_scatter (Alchemist)
Grain Delay as granular engine — scatter grains for cloud textures. Amon Tobin.
**Material:** vocal, instrument_loop, texture | **Steps:** load -> Grain Delay -> Reverb

### spectral_freeze (Alchemist)
Crop to tiny region (50-200ms), extreme stretch = spectral freeze drone.
**Material:** vocal, instrument_loop, full_mix | **Steps:** load -> crop -> stretch 64 beats

### tail_harvest (Alchemist)
Resample only the reverb/delay tail as independent texture.
**Material:** any | **Steps:** load -> Reverb 100% wet -> level for subtle layer

## Category 3: Melodic/Harmonic

### key_matched_layer (Surgeon)
Transpose to song key, EQ carve, blend behind existing elements.
**Material:** instrument_loop | **Steps:** load -> transpose -> EQ -> volume -6 to -10dB

### vocal_harmony_stack (Surgeon)
Pitch-shifted vocal layers — Bon Iver Prismizer approach.
**Material:** vocal | **Steps:** load -> duplicate -> transpose +3/+5/+7 -> blend

### counterpoint_from_chops (Alchemist)
Create countermelody from rearranged melodic fragments. Four Tet.
**Material:** instrument_loop, vocal, full_mix | **Steps:** load -> slice by beat -> program melody

### chord_stab_extraction (Surgeon)
Isolate chord from full mix, crop, retrigger. Classic house/disco.
**Material:** full_mix, instrument_loop | **Steps:** load -> slice -> crop -> rhythmic pattern

## Category 4: Drum Enhancement

### break_layering (Surgeon)
Layer drum break under programmed drums. High-pass to avoid kick clash.
**Material:** drum_loop | **Steps:** load -> warp 16 beats -> EQ HP 200-400Hz -> volume -10 to -15dB

### ghost_note_texture (Alchemist)
Heavy filter + low volume = barely audible ghost-note layer.
**Material:** drum_loop | **Steps:** load -> Auto Filter BP 1-4kHz -> volume -18 to -24dB

### transient_replacement (Surgeon)
Layer one-shot transient over existing drums for punch.
**Material:** one_shot | **Steps:** load -> classic mode -> MIDI on kick/snare hits

### shuffle_extract (Alchemist)
Extract groove timing from loop via slice positions, apply to MIDI.
**Material:** drum_loop | **Steps:** load -> slice by transient -> read positions

## Category 5: Vocal Processing

### syllable_instrument (Alchemist)
Each syllable = playable note. Vocal becomes a melodic instrument.
**Material:** vocal | **Steps:** load -> slice by region -> program melody across slices

### formant_shift_character (Alchemist)
Shift formants for alien/robotic character. Transpose +/-12st.
**Material:** vocal | **Steps:** load -> transpose -> Corpus for resonant body

### vocal_freeze_drone (Alchemist)
Sustain one vowel as ambient pad. Crop tiny region, extreme stretch.
**Material:** vocal | **Steps:** load -> crop 100-300ms -> stretch 64 beats -> Chorus -> Reverb

### phone_recording_texture (Alchemist)
Burial signature: pitch down, lo-pass, ghost-level volume.
**Material:** vocal, foley | **Steps:** load -> pitch -5 to -12 -> LP 800Hz -> volume -20 to -30dB

## Category 6: Resampling Chains

### serial_resample (Alchemist)
Multi-pass destruction: Saturator + Grain Delay + Reverb, freeze, flatten, repeat.
**Material:** any | **Steps:** load -> Saturator -> Grain Delay -> Reverb -> freeze -> flatten

### parallel_resample (Alchemist)
Duplicate, process one copy destructively, blend wet/dry.
**Material:** any | **Steps:** load -> duplicate -> process duplicate -> blend -6 to -12dB

### freeze_flatten_rechop (Alchemist)
Freeze processed material, flatten to audio, re-slice the result. Recursive.
**Material:** any | **Steps:** freeze -> flatten -> re-load into Simpler -> slice again

## Category 7: Creative Constraints

### one_sample_challenge (Alchemist)
Build entire beat from one sample: kick, snare, hat, bass, pad all from slices.
**Material:** any | **Steps:** load -> slice -> program full beat across slice pitches

### found_sound_only (Alchemist)
Non-musical field recordings as sole source material. Musique concrete.
**Material:** foley | **Steps:** load -> slice -> EQ to isolate musical frequencies

### reverse_engineering (Both)
Recreate a reference track's texture by sampling and transforming similar elements.
**Material:** full_mix | **Steps:** load -> slice by beat -> analyze structure

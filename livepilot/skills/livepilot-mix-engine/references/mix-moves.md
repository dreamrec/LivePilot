# Mix Moves Reference

The move vocabulary used by `plan_mix_move`. Each move type has defined parameter ranges and constraints.

## gain_staging

Adjust track or bus volume to establish proper level hierarchy.

**Parameters:**
- `target_track`: track index (0-based)
- `target_value`: normalized volume 0.0-1.0 (0.85 = unity / 0 dB)
- `delta_db`: typical adjustment range -6 to +3 dB per move

**Constraints:**
- Never boost more than +3 dB in a single move
- Prefer cutting the louder track over boosting the quieter one
- Check master headroom after any gain change
- Group tracks (drums, synths, vocals) should be staged relative to each other first

**Tools:** `set_track_volume`, `set_master_volume`

## bus_compression

Apply or adjust glue compression on groups, return tracks, or master bus.

**Parameters:**
- `threshold_db`: -30 to 0 dB (start conservative at -15)
- `ratio`: 1.5:1 to 4:1 for glue, up to 8:1 for limiting
- `attack_ms`: 0.1 to 100 ms (10-30 ms for glue, <1 ms for limiting)
- `release_ms`: 50 to 500 ms (auto release preferred for master bus)
- `makeup_gain_db`: 0 to +6 dB

**Constraints:**
- Gain reduction should stay under 3-4 dB for glue compression
- Always capture before/after RMS to verify loudness is maintained
- On master bus, prefer ratio <= 2:1 and attack >= 10 ms

**Tools:** `set_device_parameter`, `find_and_load_device(track_index, "Compressor")`

## transient_shaping

Adjust attack and sustain characteristics to control punch and body.

**Parameters:**
- `attack`: -100% to +100% (negative softens, positive sharpens)
- `sustain`: -100% to +100% (negative tightens, positive lengthens)

**Constraints:**
- Apply to individual drum hits or drum bus, not full mix
- Check that transient shaping doesn't push peaks above headroom
- Often more effective than compression for punch problems

**Tools:** `set_device_parameter` on a transient shaper device

## eq_cut

Subtractive EQ to clear masking, remove resonances, or fix spectral balance.

**Parameters:**
- `frequency_hz`: 20 to 20000 Hz
- `gain_db`: -12 to 0 dB (never cut more than 12 dB in one move)
- `q`: 0.5 to 8.0 (narrow cuts 4-8 for resonances, wide cuts 0.5-2 for balance)
- `filter_type`: low_cut, high_cut, bell, notch

**Constraints:**
- Prefer EQ Eight for surgical work (8 bands available)
- For low cuts on non-bass tracks, use 18 or 24 dB/oct high-pass
- Cut on the less important track in a masking pair
- Verify after cut that the track still sounds full — over-cutting kills body

**Tools:** `set_device_parameter`, `find_and_load_device(track_index, "EQ Eight")`

## eq_boost

Additive EQ to bring out character frequencies. Use sparingly.

**Parameters:**
- `frequency_hz`: 20 to 20000 Hz
- `gain_db`: 0 to +4 dB (never boost more than 4 dB in one move)
- `q`: 0.5 to 4.0 (wide boosts sound more natural)

**Constraints:**
- Always try a cut on competing tracks before boosting
- Boosts above +4 dB usually indicate a source problem, not a mix problem
- Check master headroom after any boost — boosts add energy
- Wide Q (0.5-1.5) for tonal shaping, narrow Q (2-4) for emphasis

**Tools:** `set_device_parameter` on EQ device

## pan_spread

Stereo placement adjustments for width and separation.

**Parameters:**
- `pan`: -1.0 (full left) to 1.0 (full right), 0.0 = center
- `width`: 0.0 (mono) to 2.0 (extra wide) on Utility device

**Constraints:**
- Bass and kick stay centered (pan 0.0)
- Lead vocal stays centered or very slightly off-center (within -0.1 to 0.1)
- Stereo pairs (L/R guitars, synth layers) mirror symmetrically
- Check mono compatibility after spreading — call `check_translation` if available
- Never pan return tracks (reverb/delay should remain stereo)

**Tools:** `set_track_pan`, `set_device_parameter` on Utility for mid/side width

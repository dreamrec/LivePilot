# Sound Design Critics Reference

Each critic runs during `analyze_sound_design(track_index)` and produces an issue object with `critic`, `severity` (0.0-1.0), `block`, and `evidence`.

## static_timbre

Detects sounds that do not evolve over time. A static timbre lacks movement, making it sound flat and lifeless in a mix.

**Thresholds:**
- severity >= 0.7: No detectable spectral change over a 4-bar window. Crest factor of spectral flux < 0.5 dB
- severity >= 0.4: Minimal change (spectral flux < 1.5 dB). Some subtle movement present
- severity < 0.4: Adequate movement detected, likely intentional sustain character

**Evidence format:**
```json
{
  "spectral_flux_db": 0.3,
  "analysis_window_bars": 4,
  "brightest_moment_db": -8.2,
  "dullest_moment_db": -8.5
}
```

**Typical fix:** modulation_injection — add LFO to filter cutoff (rate 0.1-2 Hz, depth 20-40%).

## no_modulation_sources

Detects patches with zero modulation sources: no LFOs, no envelopes beyond amp/filter ADSR, no automation, no macro mappings.

**Thresholds:**
- severity >= 0.7: Zero modulation sources on a melodic/pad/lead instrument
- severity >= 0.4: No modulation on a bass or rhythmic element (some genres keep bass static intentionally)
- severity < 0.4: Drum hits and one-shots (modulation not expected)

**Evidence format:**
```json
{
  "lfo_count": 0,
  "envelope_count": 1,
  "automation_lanes": 0,
  "macro_mappings": 0,
  "instrument_type": "pad"
}
```

**Typical fix:** modulation_injection — enable device LFO if available, or add Auto Filter with LFO. For pads, map LFO to filter cutoff and/or oscillator pitch (subtle detune).

## modulation_flatness

Detects modulation sources that exist but operate with such narrow ranges they produce no audible effect.

**Thresholds:**
- severity >= 0.7: Modulation depth < 5% of parameter range on all targets
- severity >= 0.4: Modulation depth 5-15% — present but barely perceptible
- severity < 0.4: Depth > 15%, audible modulation

**Evidence format:**
```json
{
  "modulation_source": "LFO 1",
  "target_parameter": "Filter Cutoff",
  "depth_percent": 3.2,
  "parameter_range": [20, 20000],
  "effective_range": [850, 920]
}
```

**Typical fix:** Increase modulation depth to 20-40% for filter targets, 5-15% for pitch targets, 10-30% for amplitude targets.

## missing_filter

Detects raw oscillator output with no filter or spectral shaping in the signal path. Unfiltered signals often sound harsh and sit poorly in a mix.

**Thresholds:**
- severity >= 0.7: No filter device in the signal chain, and the source is a harmonically rich waveform (saw, square, FM)
- severity >= 0.4: Filter present but fully open (cutoff at maximum, no resonance)
- severity < 0.4: Filter active and shaping the spectrum

**Evidence format:**
```json
{
  "has_filter": false,
  "source_waveform": "sawtooth",
  "harmonic_content": "rich",
  "device_chain": ["Wavetable"]
}
```

**Typical fix:** filter_shaping — add Auto Filter (low-pass, cutoff around 2-5 kHz, resonance 20-40%) or enable the instrument's built-in filter.

## spectral_imbalance

Detects patches with too much energy concentrated in one frequency region, or significant spectral gaps.

**Thresholds:**
- severity >= 0.7: Single band > 12 dB above the mean, or a gap > 12 dB below
- severity >= 0.4: Imbalance 6-12 dB in one or more regions
- severity < 0.4: Balanced spectrum appropriate for the instrument role

**Evidence format:**
```json
{
  "peak_band": "high_mid",
  "peak_deviation_db": 14.2,
  "gap_band": "low_mid",
  "gap_deviation_db": -8.5,
  "band_levels_db": {
    "sub": -22.0,
    "low": -14.5,
    "low_mid": -20.1,
    "mid": -11.6,
    "high_mid": -2.4,
    "high": -8.9
  }
}
```

**Typical fix:** filter_shaping to tame the peak (EQ cut or filter sweep), or oscillator_tuning to fill the gap (add sub oscillator, adjust waveform).

# Mix Critics Reference

Each critic runs during `analyze_mix` or `get_mix_issues` and produces an issue object with `critic`, `severity` (0.0-1.0), `track_index`, and `evidence`.

## masking

Detects frequency collisions between tracks that occupy the same spectral range.

**Thresholds:**
- severity >= 0.7: Two tracks share > 60% spectral overlap in the same frequency band with both > -12 dB in that range
- severity >= 0.4: Partial overlap (30-60%) or one track is significantly quieter
- severity < 0.4: Minor overlap, likely intentional layering

**Evidence format:**
```json
{
  "track_a": 0,
  "track_b": 2,
  "collision_band": "low_mid",
  "frequency_range": [200, 500],
  "overlap_percent": 72.5,
  "a_level_db": -8.2,
  "b_level_db": -10.1
}
```

**Typical fix:** eq_cut on the less important track in the collision band, or pan_spread to separate spatially.

## over_compressed

Detects tracks or the master bus with excessive compression, indicated by very low crest factor (peak-to-RMS ratio).

**Thresholds:**
- severity >= 0.7: Crest factor < 3 dB on a dynamic source (vocals, drums, full mix)
- severity >= 0.4: Crest factor 3-6 dB on sources that should be more dynamic
- severity < 0.4: Mild compression, may be intentional for genre

**Evidence format:**
```json
{
  "track_index": 1,
  "crest_factor_db": 2.4,
  "rms_db": -12.3,
  "peak_db": -9.9,
  "compressor_device": "Compressor",
  "compressor_ratio": 8.0,
  "compressor_threshold_db": -20.0
}
```

**Typical fix:** Raise compressor threshold, reduce ratio, or increase attack time.

## flat_dynamics

Detects tracks or sections with insufficient volume variation, making the mix feel static across song sections.

**Thresholds:**
- severity >= 0.7: Volume variation < 2 dB across all sections
- severity >= 0.4: Volume variation 2-4 dB where genre expects more contrast
- severity < 0.4: Minimal variation but may suit the genre (EDM drops, ambient)

**Evidence format:**
```json
{
  "track_index": 3,
  "section_volumes_db": [-10.2, -10.5, -10.1, -10.4],
  "volume_range_db": 0.4,
  "expected_range_db": 6.0
}
```

**Typical fix:** Automation on track volume or device parameters between sections.

## low_headroom

Detects when the master bus peak is dangerously close to 0 dBFS, risking clipping.

**Thresholds:**
- severity >= 0.7: Master peak > -1 dBFS
- severity >= 0.4: Master peak between -3 and -1 dBFS
- severity < 0.4: Master peak between -6 and -3 dBFS (acceptable for mastered content)

**Evidence format:**
```json
{
  "master_peak_db": -0.3,
  "master_rms_db": -8.2,
  "headroom_db": 0.3,
  "clipping": false
}
```

**Typical fix:** gain_staging — reduce the loudest tracks by 1-3 dB, or apply a limiter on the master.

## stereo_width

Detects stereo problems: mono collapse (too narrow), excessive width (phase issues), or elements placed inappropriately in the stereo field.

**Thresholds:**
- severity >= 0.7: Correlation coefficient < 0.1 (phase issues) or > 0.95 (essentially mono)
- severity >= 0.4: Bass content with significant stereo width, or lead vocal panned away from center
- severity < 0.4: Minor width imbalance

**Evidence format:**
```json
{
  "track_index": 5,
  "correlation": 0.05,
  "width_estimate": 0.95,
  "issue_type": "phase_cancellation",
  "frequency_range": [100, 300]
}
```

**Typical fix:** Narrow bass to mono below 150 Hz (Utility mid/side), widen or narrow specific elements with pan_spread.

## spectral_balance

Detects overall tonal balance skew across the full mix — too bright, too dark, or mid-heavy compared to reference targets.

**Thresholds:**
- severity >= 0.7: Any band deviates > 6 dB from genre target curve
- severity >= 0.4: Deviation 3-6 dB in one or more bands
- severity < 0.4: Minor skew, within normal range

**Evidence format:**
```json
{
  "balance_type": "too_bright",
  "band_deviations_db": {
    "sub": -1.2,
    "low": 0.5,
    "low_mid": -0.8,
    "mid": -2.1,
    "high_mid": 4.2,
    "high": 7.1,
    "air": 5.8
  },
  "reference_curve": "electronic_modern"
}
```

**Typical fix:** eq_cut on the protruding bands, or eq_boost on deficient bands. Prefer cuts over boosts.

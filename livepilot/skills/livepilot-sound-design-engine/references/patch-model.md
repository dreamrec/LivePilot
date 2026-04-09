# Patch Model Reference

The PatchModel is returned by `get_patch_model(track_index)` and represents the complete signal processing structure of a track's device chain.

## PatchModel Structure

```json
{
  "track_index": 0,
  "track_name": "Lead Synth",
  "blocks": [
    {
      "device_index": 0,
      "device_name": "Wavetable",
      "block_type": "oscillator",
      "controllable": true,
      "parameters": ["Osc 1 Pos", "Osc 1 Gain", "Sub Gain", ...],
      "sub_blocks": [
        { "block_type": "filter", "parameters": ["Filter Freq", "Filter Res", ...] },
        { "block_type": "lfo", "parameters": ["LFO 1 Rate", "LFO 1 Amount", ...] },
        { "block_type": "envelope", "parameters": ["Amp Attack", "Amp Decay", ...] }
      ]
    },
    {
      "device_index": 1,
      "device_name": "Auto Filter",
      "block_type": "filter",
      "controllable": true,
      "parameters": ["Frequency", "Resonance", "Env. Modulation", ...]
    }
  ],
  "controllable_params": [...],
  "opaque_blocks": [],
  "modulation_sources": [
    { "type": "lfo", "device_index": 0, "rate": "0.5 Hz", "targets": ["Filter Freq"] }
  ],
  "signal_flow": "serial"
}
```

## Block Types

### oscillator
Sound source generators. Found in synth instruments (Wavetable, Operator, Analog, Drift, Simpler, Sampler).

Key parameters: waveform/position, pitch/tune/detune, unison voices/spread, sub oscillator level, FM amount/ratio.

### filter
Spectral shaping. Found as sub-blocks inside instruments or as standalone devices (Auto Filter, EQ Eight).

Key parameters: cutoff frequency, resonance, filter type (LP/HP/BP/Notch), slope (12/24 dB), envelope modulation amount, drive.

### envelope
Time-shaping contour generators. Usually ADSR controlling amplitude or filter cutoff.

Key parameters: attack, decay, sustain, release. Some instruments offer additional envelopes with arbitrary targets.

### lfo
Low-frequency oscillators for cyclic modulation.

Key parameters: rate (Hz or synced), waveform (sine, triangle, square, saw, random), amount/depth, target parameter, phase, offset.

### saturation
Waveshaping, distortion, and harmonic generation.

Devices: Saturator, Overdrive, Pedal, Amp, Erosion, Dynamic Tube. Key parameters: drive, tone, type/curve, dry/wet.

### spatial
Stereo field and space processing.

Devices: Reverb, Delay, Chorus, Phaser, Flanger, Echo, Hybrid Reverb. Key parameters: decay/time, pre-delay, size, damping, dry/wet, feedback.

### effect
Catch-all for utility and dynamics processing.

Devices: Compressor, Glue Compressor, Limiter, Gate, Utility, Tuner, Spectrum. Key parameters vary by device.

## Controllable vs Opaque

- **Controllable**: native Ableton devices and well-behaved plugins where `get_device_parameters` returns named, ranged parameters. All LivePilot set/get parameter tools work reliably.
- **Opaque**: third-party AU/VST plugins where parameter inspection fails or returns generic names (Parameter 1, Parameter 2). The sound design engine can detect the block exists but cannot reason about individual parameters.

Check `parameter_count` on opaque blocks. If <= 1, the plugin failed to load — delete it and replace with a native alternative.

## Native Device Block Map

Quick reference for which block types each native device provides:

| Device | Primary Block | Sub-blocks |
|--------|--------------|------------|
| Wavetable | oscillator | filter, lfo, envelope |
| Operator | oscillator | filter, lfo, envelope |
| Analog | oscillator | filter, lfo, envelope |
| Drift | oscillator | filter, lfo, envelope |
| Simpler | oscillator | filter, lfo, envelope |
| Sampler | oscillator | filter, lfo, envelope |
| Auto Filter | filter | lfo, envelope |
| EQ Eight | filter | — |
| Compressor | effect | envelope (sidechain) |
| Glue Compressor | effect | — |
| Saturator | saturation | — |
| Overdrive | saturation | — |
| Pedal | saturation | — |
| Reverb | spatial | — |
| Delay | spatial | filter |
| Echo | spatial | filter, lfo |
| Chorus-Ensemble | spatial | — |
| Phaser-Flanger | spatial | lfo |
| Hybrid Reverb | spatial | — |
| Corpus | spatial | — |
| Utility | effect | — |

## Rack Detection

If a track contains an Instrument Rack or Audio Effect Rack, the PatchModel reports:

- `signal_flow`: "parallel" (rack chains run in parallel)
- Each chain appears as a nested block list
- Use `get_rack_chains(track_index, device_index)` for per-chain detail

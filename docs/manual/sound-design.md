# Sound Design

This chapter covers how to find, load, and shape sounds using LivePilot. Everything here is a starting point — tweak relentlessly until it sounds right to your ears.

---

## Browsing Ableton's Library

Ableton ships with a massive library of instruments, effects, samples, and presets. LivePilot gives you four ways to navigate it without touching the mouse.

### See what's available

`get_browser_tree` shows you the top-level categories in Ableton's browser — Sounds, Drums, Instruments, Audio Effects, MIDI Effects, Max for Live, Plug-ins, Clips, Samples, and so on. Use this when you want to orient yourself or explore a category you haven't used before.

### Search by name

`search_browser` is your main workhorse. It takes a `path` (which category to search in) and an optional `name_filter` (what to look for). For example, searching in "Instruments" with the filter "Wavetable" gives you every Wavetable preset in the library.

This is the most reliable way to find things. The path narrows the search to the right category, and the name filter handles the rest.

### Load onto a track

Once you've found what you want, `load_browser_item` loads it onto a track using the item's URI. The URI comes from the search results — you don't need to memorize or construct them.

### Quick load by name

`find_and_load_device` is a convenience tool that searches and loads in one step. It works well for unambiguous names like "Analog" or "Compressor," but be careful with common names. For example, searching for "Drift" might match a sample file called "Drift" before it matches the Drift synthesizer. If you get unexpected results, fall back to `search_browser` with path filtering.

### Browse presets

`get_device_presets` lists every factory preset for a device that's already loaded on a track. `load_device_by_uri` loads a specific preset by its URI. This is great for auditioning starting points — load a preset, listen, then tweak from there.

### Best practice

For reliability, prefer `search_browser` with a path filter over `find_and_load_device`. The two-step approach (search, then load) gives you more control and avoids name collisions. Use `find_and_load_device` when speed matters and the name is unambiguous.

---

## Stock Instruments

Ableton's built-in instruments cover an enormous range of sounds. Here's what each one does well and the key parameters worth knowing.

### Drum Rack

128 pads, each holding its own instrument and effect chain. **Always load a preset kit** — never load a bare empty Drum Rack and try to fill it pad by pad. The factory kits (606, 707, 808, acoustic, etc.) give you a playable starting point immediately.

After loading, use `get_rack_chains` to see what's on each pad. This tells you which samples or instruments are mapped where, so you can reference them by name when making changes.

### Analog

Classic analog modeling synthesizer. Two oscillators plus a noise generator, two multimode filters, two LFOs, two envelopes. This is your go-to for basses, leads, and pads that need warmth and presence.

Key parameters: Osc 1/2 Shape, Filter Type, Filter Frequency, Filter Resonance, Amp Attack/Decay/Sustain/Release.

### Wavetable

Wavetable morphing synthesizer with a deep modulation matrix. Two oscillators that can sweep through wavetable positions, up to 8 unison voices per oscillator, and a flexible modulation system.

Key parameters: Osc 1/2 Wavetable Position, Unison Amount, Unison Voices, Sub Oscillator, Filter Frequency, Mod Matrix assignments.

### Operator

Four-operator FM synthesizer with 11 algorithms that determine how operators modulate each other. Ranges from clean electric pianos to harsh metallic textures. The learning curve is steep, but the sonic range is unmatched.

Key parameters: Algorithm (1-11), Operator Coarse/Fine tuning, Operator Level, Operator Feedback, Filter Frequency.

### Drift

A deliberately simple analog synth with built-in parameter drift (subtle random modulation). Two oscillators, one filter, one LFO. It sounds good almost immediately because the instability adds life to every patch.

Key parameters: Osc 1/2 Shape, Drift Amount, Filter Frequency, Filter Resonance, LFO Rate, LFO Amount.

### Simpler

Sample playback instrument with three modes. **Classic** loops a sample with full ADSR control. **One-Shot** plays the sample once (good for drums and hits). **Slice** chops the sample into segments you can trigger individually (good for breaks and loops).

Switch modes with `set_simpler_playback_mode`. After switching, the available parameters change, so run `get_device_parameters` to see what you're working with.

Key parameters: Mode (Classic/One-Shot/Slice), Sample Start, Sample End, Loop Start, Loop Length, Filter Frequency, Transpose, Gain.

---

## Sound Recipes

These are starting points. Every recipe below gets you in the neighborhood of a sound — your job is to listen and adjust until it fits your track. There is no "correct" setting for any of these.

### Sub Bass

**Instrument:** Analog
**Approach:** Single sine oscillator, low-pass filter around 200 Hz to kill harmonics, no unison, mono output. Keep it clean — sub bass should be felt, not heard as a distinct timbre.

Key settings to reach for: Osc 1 Shape (sine), Filter Type (LP24), Filter Freq (~200 Hz), Amp Sustain (full), Utility set to mono on the channel.

### Reese Bass

**Instrument:** Analog or Wavetable
**Approach:** Two detuned saw oscillators, low-pass filter with moderate resonance, slight unison. The movement comes from the phase interaction between the detuned oscillators. Automate the filter cutoff for classic DnB tension.

Key settings to reach for: Osc 1 + Osc 2 (saw), Osc 2 Fine detune (+5 to +15 cents), Filter Type (LP24), Filter Freq (~400-800 Hz), Unison (2-4 voices if using Wavetable).

### Warm Pad

**Instrument:** Wavetable
**Approach:** Soft wavetable shape, 4-8 unison voices with moderate detune, slow attack (200-500 ms), long release, low-pass filter around 2 kHz. Add a touch of reverb on a send.

Key settings to reach for: Wavetable Position (start with softer waves), Unison Voices (4-8), Unison Amount (~30-50%), Amp Attack (~300 ms), Filter Freq (~2 kHz), Filter Resonance (low).

### Pluck

**Instrument:** Analog or Wavetable
**Approach:** Saw or square oscillator, LP24 filter with a fast filter envelope — short attack, short decay, no sustain. The filter envelope snapping shut is what creates the pluck character. Short amp decay, no sustain.

Key settings to reach for: Osc Shape (saw or square), Filter Type (LP24), Filter Freq (~300 Hz base), Filter Env Amount (high), Filter Env Decay (~100-200 ms), Amp Decay (~200-400 ms), Amp Sustain (0).

### Lead

**Instrument:** Analog or Drift
**Approach:** Square or saw oscillator, low-pass filter around 3 kHz, portamento (glide) for legato phrasing. Add delay and reverb as send effects to give it space without muddying the dry signal.

Key settings to reach for: Osc Shape (square or saw), Filter Freq (~3 kHz), Glide/Portamento (50-200 ms), then add Delay and Reverb on return tracks.

### Supersaw

**Instrument:** Wavetable
**Approach:** Saw wavetable, 7-8 unison voices, high detune amount. This is the bread and butter of trance, future bass, and EDM buildups. Layer with a sub for low-end support since the heavy unison spreads the stereo image and thins out the center.

Key settings to reach for: Wavetable (saw), Unison Voices (7-8), Unison Amount (60-80%), Filter Freq (~4-6 kHz), Amp Attack (short for stabs, medium for pads).

### 808 Bass

**Instrument:** Simpler
**Approach:** Load a pitched 808 sample (search the library for "808"), set to One-Shot mode for long sustained notes or Classic mode if you need loop control. Long decay. Add a Saturator after the Simpler to add harmonics that translate on small speakers.

Key settings to reach for: `set_simpler_playback_mode` to One-Shot, Sample decay (long), then load a Saturator with Drive around 5-10 dB, Saturator Mode set to Analog Clip or Soft Sine.

---

## Audio Effects

Ableton's effects cover everything from subtle corrective processing to total sonic destruction. Here's an overview organized by what they do.

### Dynamics

- **Compressor** — General-purpose dynamics control. Use it on vocals, bass, drums, anything that needs a more consistent level. The Ratio, Threshold, Attack, and Release parameters are the ones that matter most.
- **Glue Compressor** — Modeled on a classic bus compressor. Better than Compressor for gluing groups of sounds together (drum bus, mix bus). The Soft Clip switch adds gentle saturation.
- **Limiter** — Catches peaks and prevents clipping. Put it last in the chain when you need a hard ceiling.
- **Drum Buss** — Purpose-built for drums. Combines drive, compression, transient shaping, and a tuned boom control in one device. Often all you need on a drum group.

### EQ and Filtering

- **EQ Eight** — Full parametric EQ with 8 bands. Your surgical tool — cut problem frequencies, boost character. The Audition (headphone) mode lets you solo a band to hear what it's affecting.
- **Auto Filter** — Resonant filter with LFO, envelope follower, and sidechain input. Use it for movement — sweeping pads, rhythmic filtering, sidechain pumping.
- **Channel EQ** — Simple 3-band EQ with a high-pass filter. Good for quick tone shaping when you don't need surgical precision.

### Time-Based

- **Reverb** — Algorithmic reverb with pre-delay, decay time, and tone shaping. Use on sends, not inserts, unless you want 100% wet on a specific sound.
- **Delay** — Tempo-synced delay with feedback and filtering. Good for rhythmic echoes, dub effects, and adding depth.
- **Echo** — Combines delay with modulation, reverb, and character controls. More creative and colored than Delay — better for effects, worse for transparent repeats.

### Distortion

- **Saturator** — The most versatile distortion in Ableton. Six modes, each with a different character:
  - *Soft Sine* — gentle warmth, good on almost anything
  - *Analog Clip* — harder edge, good for bass and drums
  - *Sinoid Fold* — wavefolder-style, gets wild at high drive
  - The Drive and Output knobs are your main controls.
- **Overdrive** — Amp-style distortion. Works well on bass and guitars, less useful on full mixes.
- **Erosion** — Adds digital artifacts and noise. Subtle amounts add air and grit, high amounts destroy the signal.
- **Corpus** — Physical modeling resonator. Puts any sound through a simulated resonating body (tube, membrane, plate). Unique textures when used on drums or noise.

### Modulation

- **Chorus-Ensemble** — Adds width and movement. Classic mode for subtle thickening, Ensemble mode for lush, wide chorusing. Use sparingly on bass (it can thin the low end).
- **Phaser-Flanger** — Phase cancellation effects. Phaser mode for sweepy, psychedelic movement; Flanger mode for jet-engine swooshes and metallic textures.

### Utility

- **Utility** — Gain, stereo width, phase inversion, mono switch, balance. Probably the most underrated device in Ableton. Put it at the end of any chain to fine-tune level and width. Set bass channels to mono. Check phase with the invert buttons.

---

## Building Effect Chains

Effects are most powerful in combination. Here are common chain patterns you can build with LivePilot.

### Standard insert chain

EQ Eight (subtractive cuts) --> Compressor --> Saturator --> EQ Eight (tonal shaping) --> Utility

Load each device in order using `find_and_load_device` or `search_browser` + `load_browser_item`. The order matters — cutting problem frequencies before compression means the compressor reacts to the musical content, not the problems.

### Drum bus chain

EQ Eight (high-pass around 30-40 Hz) --> Glue Compressor (2-4:1 ratio, medium attack) --> Saturator (Soft Sine, gentle drive) --> Drum Buss

The Glue Compressor ties the kit together, the Saturator adds warmth, and Drum Buss handles transient shaping and boom.

### Vocal-style chain

EQ Eight (high-pass at 80 Hz, cut mud around 200-300 Hz) --> Compressor (moderate ratio, fast-ish attack) --> EQ Eight (presence boost around 3-5 kHz) --> send to Reverb

Two EQs is not overkill. The first cleans up, the second shapes tone. They serve different purposes.

### Setting multiple parameters at once

Use `batch_set_parameters` when you want to dial in a device quickly. Instead of calling `set_device_parameter` seven times, you send all the parameter changes in one call. This is faster and keeps the changes atomic — everything updates together.

For example, after loading a Compressor, you might batch-set the Threshold, Ratio, Attack, Release, Output Gain, and Dry/Wet all at once. Run `get_device_parameters` first to see the exact parameter names and valid ranges.

---

## Working with Parameters

Every device in Ableton exposes its parameters through the Live Object Model. LivePilot gives you direct access.

### Reading parameters

`get_device_parameters` returns every parameter on a device with its current value, minimum, maximum, and a human-readable `value_string` (e.g., "2.50 kHz" instead of a raw float). Always read parameters before setting them — this tells you the exact names and valid ranges.

### Setting parameters

`set_device_parameter` sets a single parameter by name or index. Parameter names are **exact and case-sensitive**. "Filter Freq" is not the same as "filter freq" or "Filter Frequency." When in doubt, read the parameters first and copy the name exactly.

### Setting many at once

`batch_set_parameters` takes a list of parameter name/value pairs and applies them all in one call. Use this when you're dialing in a sound or configuring a newly loaded device. It's faster and produces a single undo step.

### Toggling devices

`toggle_device` turns a device on or off without removing it from the chain. This is your A/B comparison tool — toggle an effect off, listen, toggle it back on, decide if it's actually helping.

### Tips

- Always run `get_device_parameters` after loading a new device. Parameter names vary between devices and even between presets of the same device.
- When a parameter seems to have no effect, check if the device is enabled with `get_device_info`.
- Some parameters are quantized (e.g., filter type, algorithm number). The min/max and value_string from `get_device_parameters` will tell you what the valid options are.
- After making changes, trust your ears over the numbers. A parameter value of 0.65 means nothing on its own — what matters is how it sounds in context.

---

## MIDI Effects

MIDI effects process note data before it reaches the instrument. They go at the beginning of the device chain, before any instrument.

- **Arpeggiator** — Turns held chords into arpeggiated patterns. Set the rate, direction (up, down, random), and gate length. Instant rhythmic movement from static chords.
- **Chord** — Adds intervals to every incoming note. Play one key, hear a chord. Useful for quick harmonic sketching.
- **Scale** — Forces all notes into a specific scale. Load this when you want to stay in key no matter what notes you program. Especially useful with generative or random note tools.
- **Note Length** — Controls how long each note lasts regardless of the input. Good for making consistent staccato patterns or extending short triggers.
- **Pitch** — Transposes incoming notes by a fixed amount. Simple but useful for octave shifting or quick key changes.
- **Random** — Adds random pitch variation to incoming notes. At subtle settings it adds humanization; at extreme settings it becomes generative.
- **Velocity** — Reshapes the velocity curve of incoming notes. Use it to compress dynamics (make everything more consistent) or expand them (make soft notes softer and loud notes louder).

MIDI effects are powerful for generative patterns. Stack a Scale (to stay in key) with a Random (for variation) and an Arpeggiator (for rhythm), and a simple held chord becomes an evolving melodic sequence.

---

Next: [Mixing](mixing.md) | Back to [Manual](index.md)

# EQ & Filtering Device Atlas

> Signal-shaping tools for frequency sculpting, resonance, spectral manipulation, and vocoding.
> Covers 8 native Ableton devices + 5 user M4L devices from the CLX_02 collection.

---

## Native Ableton Devices

---

### EQ Eight

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "EQ Eight")`
- **What it does:** Surgical 8-band parametric EQ with real-time spectrum analyzer. Clean, transparent, and precise. The workhorse EQ for mixing and sound design. Supports stereo, L/R, and Mid/Side processing modes.
- **Signal flow:** Input -> 8 independent filter bands (series) -> Spectrum Analyzer -> Output. Each band has its own filter type, frequency, gain, and Q. In M/S mode the signal is encoded to mid+side, processed separately, then decoded back to stereo.
- **Key parameters:**
  - **Band 1-8 Frequency** -> sets center/cutoff frequency for each band -> 20 Hz to 20 kHz; place surgical cuts at problem frequencies (e.g., 250 Hz mud, 3 kHz harshness)
  - **Band 1-8 Gain** -> boost or cut at the set frequency -> +/-15 dB; gentle 1-3 dB moves for mixing, larger cuts for problem solving; gain is locked for Low Cut, High Cut, and Notch types
  - **Band 1-8 Q** -> bandwidth/resonance of each band -> narrow Q (4-8) for surgical notches, wide Q (0.5-1.5) for broad tonal shaping
  - **Band 1-8 Filter Type** -> selects filter shape -> choices: Low Cut 48, Low Cut 12, Low Shelf, Bell, Notch, High Shelf, High Cut 12, High Cut 48
  - **Mode** -> stereo processing mode -> Stereo (both channels linked), L/R (independent left/right), M/S (independent mid/side)
  - **Edit** -> toggles between L/R or M/S channel editing (only active when Mode is L/R or M/S)
  - **Adaptive Q** -> models analog EQ behavior; Q narrows as gain increases -> on by default; leave on for musical results, turn off for precise digital control
  - **Oversampling** -> 2x internal processing to smooth high-frequency filter curves -> enable for mastering or when shaping above 10 kHz; slight CPU increase
  - **Scale** -> scales all gain values proportionally -> useful for A/B comparison; dial down to 0% to hear the unprocessed signal, then back to 100%
  - **Output** -> trim output level after all EQ processing
- **Reach for this when:** You need precise frequency sculpting; cutting resonances; shaping tonal balance during mixing; working in mid/side; any situation requiring more than 3 bands or specific filter shapes.
- **Don't use when:** You just need a quick high/low shelf (use Channel EQ); you want analog DJ-style kills (use EQ Three); you want moving/modulated filtering (use Auto Filter).
- **Pairs well with:** Compressor (EQ before compression for tonal balance), Glue Compressor (EQ Eight on bus -> Glue for glue), Utility (for gain staging before EQ), Spectrum (for visual analysis alongside).
- **vs Channel EQ:** EQ Eight is surgical with 8 bands and multiple shapes; Channel EQ is quick and musical with 3 fixed bands. Use Channel EQ for fast broad strokes, EQ Eight when precision matters.
- **vs EQ Three:** EQ Eight is a mixing tool; EQ Three is a performance/DJ tool. EQ Eight has no kill switches but far more control.

---

### EQ Three

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "EQ Three")`
- **What it does:** Simple 3-band DJ-style EQ with kill switches. Modeled on mixer circuitry -- even at default settings it imparts a slight color. The gain knobs go to negative infinity (full kill). Designed for live performance, not surgical mixing.
- **Signal flow:** Input -> 3-band crossover (split at FreqLow and FreqHi) -> independent gain per band -> sum -> Output. Each band has a kill switch that fully mutes that range.
- **Key parameters:**
  - **GainLow** -> boost/cut low frequencies below FreqLow -> -inf to +6 dB; turn fully left to kill bass completely
  - **GainMid** -> boost/cut mid frequencies between FreqLow and FreqHi -> -inf to +6 dB; cut mids for "scooped" DJ transitions
  - **GainHi** -> boost/cut high frequencies above FreqHi -> -inf to +6 dB; kill highs to remove hats/cymbals during transitions
  - **FreqLow** -> crossover point between Low and Mid bands -> sweet spot 200-300 Hz for bass/mid separation
  - **FreqHi** -> crossover point between Mid and High bands -> sweet spot 2.5-4 kHz for mid/high separation
  - **L / M / H kill switches** -> instant mute of Low, Mid, or High band -> map to MIDI controller for live performance
  - **24 / 48 slope buttons** -> filter slope per crossover -> 24 dB/oct for smooth transitions, 48 dB/oct for sharp DJ-style cuts
- **Reach for this when:** DJing; live performance; quick frequency kills; drop buildups where you want to remove and reintroduce bass.
- **Don't use when:** Mixing (too coarse, adds coloration); mastering; any situation requiring precision. The analog modeling adds subtle artifacts even at neutral settings.
- **Pairs well with:** Beat Repeat (kill mids -> Beat Repeat on highs), Utility (gain after kills to compensate), any performance effect chain.
- **vs Channel EQ:** EQ Three has kill switches and DJ character; Channel EQ is cleaner and better for static mixing.
- **vs EQ Eight:** EQ Three is a blunt performance tool; EQ Eight is a precision mixing tool. They serve completely different purposes.

---

### Channel EQ

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Channel EQ")`
- **What it does:** Simple, musical 3-band EQ inspired by classic analog mixing consoles. Quick tonal shaping with minimal parameters. Built-in spectrum display. Very low CPU. Introduced in Live 10.
- **Signal flow:** Input -> HP 80 Hz filter (optional) -> Low shelf (100 Hz) -> Mid peak (sweepable 120 Hz - 7.5 kHz) -> High shelf (with built-in LP rolloff when attenuating) -> Output gain -> Output.
- **Key parameters:**
  - **HP 80 Hz** -> toggles a fixed high-pass filter at 80 Hz -> enable on every non-bass track to remove rumble; essential on vocals, guitars, keys
  - **Low** -> low shelf gain at 100 Hz -> +/-15 dB; boost 2-4 dB to warm up thin tracks; cut 2-4 dB to reduce muddiness
  - **Mid** -> sweepable peak filter gain -> +/-12 dB; the frequency slider (120 Hz - 7.5 kHz) lets you target the mid range; boost at 1-3 kHz for presence, cut at 300-500 Hz for clarity
  - **Mid Frequency** -> center frequency of the mid band -> 120 Hz to 7.5 kHz; sweep to find problem frequencies
  - **High** -> high shelf gain, with a special behavior: when boosting, pure shelf; when attenuating, combines shelf with a LP filter that rolls from 20 kHz down to 8 kHz -> +/-15 dB; cut 2-3 dB for de-harshness; boost 1-2 dB for air
  - **Output** -> gain compensation after EQ -> use to match loudness before/after EQ adjustments
  - **Spectrum** -> real-time frequency display overlaid on the EQ curves
- **Reach for this when:** Quick mix moves on individual tracks; you want console-style simplicity; shaping drum hits in a Drum Rack (one per pad); taming reverb tails.
- **Don't use when:** You need more than 3 bands; you need mid/side processing; you need precise notch filtering.
- **Pairs well with:** Compressor (Channel EQ first for tonal shaping, then compress), Saturator (EQ -> Saturator for focused harmonic drive), Drum Rack (one Channel EQ per pad).
- **vs EQ Eight:** Channel EQ is faster to dial in with fewer decisions; EQ Eight offers more bands, shapes, and modes. Channel EQ for tracking/rough mix, EQ Eight for detailed mixing.
- **vs EQ Three:** Channel EQ is cleaner and has a sweepable mid; EQ Three has kill switches for performance. Channel EQ for mixing, EQ Three for DJing.

---

### Auto Filter

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Auto Filter")`
- **What it does:** Feature-rich resonant filter with envelope follower, LFO, and sidechain modulation. Models multiple analog circuit types. Massive sonic range from subtle warmth to aggressive screaming sweeps. Completely overhauled in Live 12.2 with new filter types and circuit models.
- **Signal flow:** Input -> Drive/Saturation -> Filter (type + circuit model) -> Envelope Follower & LFO modulate cutoff -> Sidechain input (optional) -> Mix -> Output.

- **Key parameters:**

  *Filter Section:*
  - **Filter Type** -> selects the core filter behavior -> choices: Low-pass, High-pass, Band-pass, Notch, Morph, DJ, Comb, Resampling, Notch+LP, Vowel
  - **Freq (Cutoff)** -> filter cutoff frequency -> 20 Hz to 20 kHz; the single most important parameter; automate for sweeps. For DJ filter: replaced by "Control" knob. For Vowel: replaced by "Pitch" knob
  - **Res (Resonance)** -> emphasis at cutoff frequency -> 0-100%; subtle warmth at 20-30%, screaming at 70%+, self-oscillation near 100% on some circuits
  - **Morph** -> transforms the filter character depending on type -> on LP/HP/BP/Notch: morphs between filter shapes; on DJ: blends LP and HP; on Vowel: shifts vowel formant
  - **Circuit Type** -> analog filter model -> choices:
    - *SVF*: Clean state-variable filter, transparent, no coloration; best for surgical filtering
    - *DFM*: Feeds back distortion internally, warm to aggressive; new in 12.2
    - *MS2*: Modeled on Korg MS-20 filter; smashes resonant peaks, smooth limiting; great for synth-like character
    - *PRD*: Modeled on Moog Prodigy filter; pokiest resonance, wild harmonics at high res; most aggressive
    - *SMP*: Middle ground, crushes lows slightly more than highs; good default when unsure
    - *OSR*: Maintains signal contour, tasteful saturation; best for preserving top end
  - **Drive** -> input gain before filter (adds saturation/distortion) -> 0-24 dB; works on all filter types in Live 12.2; push to 6-12 dB for warmth, above for aggressive grit

  *Envelope Follower:*
  - **Env Amount** -> how much the input amplitude modulates cutoff -> positive values open filter on loud signals; negative values close it
  - **Attack** -> envelope rise time -> fast (1 ms) for percussive response, slow (50-200 ms) for smooth following
  - **Release** -> envelope fall time -> fast for rhythmic pumping, slow for gentle movement

  *LFO:*
  - **LFO Amount** -> modulation depth on cutoff -> subtle movement at 10-20%, dramatic sweeps at 50%+
  - **LFO Rate** -> frequency in Hz or synced to tempo -> sync to 1/4 or 1/8 for rhythmic filtering; free-running for evolving textures
  - **LFO Wave** -> shape of modulation -> Sine (smooth), Triangle, Saw, Square, Ramp Up, Ramp Down, Wander (random smooth), S&H (random stepped)
  - **Stereo Mode** -> Phase (LFO offset between L/R in degrees) or Spin (percentage detuning between L/R)

  *Sidechain:*
  - **External toggle** -> enables external sidechain input
  - **SC Source** -> selects sidechain track and tap point (Pre FX, Post FX, Post Mixer)
  - **SC Mix** -> blend of external vs internal sidechain -> 100% = fully external
  - **SC Filter** -> frequency-selective sidechain filter (LP/HP/BP/shelf)

  *Output:*
  - **Dry/Wet** -> blend processed and dry signal

- **Reach for this when:** Filter sweeps; envelope-following duck effects; rhythmic LFO filtering; sidechain-triggered filter effects; DJ-style crossfader filtering; comb filtering; vowel sounds; any situation where the filter needs to move.
- **Don't use when:** You need static EQ (use EQ Eight); you want tuned resonant bodies (use Corpus or Resonators).
- **Pairs well with:** Compressor (tame resonance peaks after filter), Reverb (filter sweep into reverb for builds), Delay (filtered delay textures), LFO MIDI effect (for complex modulation routing).
- **vs EQ Eight:** Auto Filter is a creative/performance effect with modulation; EQ Eight is a static mixing tool. Different purposes entirely.

---

### Spectral Resonator

- **Type:** Native (Live 11+ Suite only)
- **Load via:** `find_and_load_device(track_index, "Spectral Resonator")`
- **What it does:** Decomposes audio into spectral partials via FFT, then applies pitched resonance, stretching, and modulation in the frequency domain. Creates everything from shimmering harmonics to metallic drones to vocoder-like pitched effects. Can be played via MIDI sidechain for melodic control of the resonance.
- **Signal flow:** Input -> FFT analysis -> Spectral processing (resonance at Freq/MIDI pitch, with Decay, Stretch, Shift applied to partials) -> Modulation (Chorus/Wander/Granular) -> IFFT resynthesis -> Dry/Wet mix -> Output.
- **Key parameters:**
  - **Freq** -> fundamental frequency of the resonance in Hz mode -> lower values = darker, dirtier; higher = brighter, more tonal. In MIDI mode, pitch is determined by incoming MIDI notes
  - **MIDI toggle** -> switches from internal Freq knob to external MIDI pitch control -> enable to play the resonator melodically from a MIDI track
  - **Decay** -> how long partials ring after excitation -> short (50-200 ms) for percussive shimmer; medium (500-800 ms) for delay-like effects; long (2000+ ms) for infinite drones
  - **Unison** -> number of detuned voices -> 1-8 voices; more voices = thicker, darker, chorus-like
  - **Uni. Amt (Unison Amount)** -> detuning spread of unison voices -> 0-100%; high values with many voices create dense clouds
  - **Stretch** -> shifts the spacing of harmonic partials -> 0% = natural harmonic series; positive = stretched (inharmonic, metallic); negative = compressed (bell-like)
  - **Shift** -> shifts all partials up or down in frequency -> subtle shifts add shimmer; large shifts create alien textures
  - **Mod Type** -> modulation applied to partials -> Chorus (gentle detuning), Wander (random sawtooth modulation of partials), Granular (random amplitude modulation with exponential decay)
  - **Mod Rate** -> speed of the selected modulation -> Granular: controls density of grains; Wander: speed of random movement
  - **Mono/Poly** -> polyphony for MIDI input -> Mono, 2, 4, 8, or 16 voices; use Poly 4-8 for chords
  - **Dry/Wet** -> blend -> 20-40% for subtle harmonic enhancement; 60-100% for full spectral transformation
- **Reach for this when:** Adding harmonic shimmer to pads; turning percussion into melodic content via MIDI; creating spectral freezes and drones; vocoder-like effects without a carrier signal; build-ups and transitions.
- **Don't use when:** You want a simple filter sweep (use Auto Filter); you want transparent EQ (use EQ Eight); you need physical modeling resonance (use Corpus).
- **Pairs well with:** Spectral Time (spectral freeze + delay after resonance), Reverb (enormous washed-out spaces), Corpus (spectral into physical modeling for hybrid textures), Utility (tame output level).
- **vs Vocoder:** Spectral Resonator works on a single input using FFT partials; Vocoder requires carrier + modulator and uses filter banks. Spectral Resonator is better for transforming a single source; Vocoder is better for imposing one signal's character onto another.
- **vs Resonators:** Spectral Resonator works in the frequency domain (FFT); Resonators uses tuned delay lines. Spectral Resonator is more experimental and alien; Resonators is more musical and predictable.

---

### Corpus

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Corpus")`
- **What it does:** Physical modeling resonator that simulates the acoustic behavior of resonant bodies. Excites a virtual physical object (beam, string, membrane, plate, pipe, tube, marimba bar) with the input signal. Adds tuned resonant character -- from subtle wooden warmth to full metallic ringing.
- **Signal flow:** Input -> Band-pass filter (optional) -> Physical model resonator (left + right with independent listening positions) -> LFO modulation -> Bleed (dry signal mixed back) -> Gain/Limiter -> Dry/Wet -> Output.
- **Key parameters:**

  *Resonator:*
  - **Resonance Type** -> selects physical model -> Beam, Marimba, String, Membrane, Plate, Pipe, Tube. Each has fundamentally different harmonic structure and decay characteristics
  - **Quality** -> Eco or High -> Eco for performance, High for final rendering; High adds more overtones
  - **Decay** -> internal damping -> short (0.1-0.5 s) for percussive hits; long (2-5 s) for sustained ringing
  - **Material** -> how damping varies across frequency -> low values = higher frequencies damped first (warm, woody); high values = even damping (bright, metallic)
  - **Radius** -> size of Pipe/Tube models -> affects pitch and sustain characteristics
  - **Bright** -> amplitude of upper frequency components -> push for presence and shimmer
  - **Inharm (Inharmonics)** -> shifts overtone pitches relative to fundamental -> negative = compressed (bell-like); positive = stretched (metallic/industrial)
  - **Opening** -> how closed/open Pipe model is -> 0% = closed pipe (odd harmonics only, clarinet-like); 100% = open (all harmonics)
  - **Ratio** -> X/Y axis proportion for Membrane/Plate -> changes the modal frequency pattern
  - **Hit** -> where the excitation strikes the object -> 0% = center (fewer modes); higher = off-center (more complex overtones)

  *Listening Position:*
  - **Pos. L / Pos. R** -> where vibrations are measured on left/right resonators -> 0% = center of object; higher = closer to edge; different positions emphasize different overtones
  - **Width** -> stereo mix between L and R resonators -> 0% = mono; increase for stereo spread

  *Tuning:*
  - **Tune** -> resonator pitch in Hz
  - **MIDI Frequency** -> enables pitch control via MIDI sidechain -> allows playing the resonator melodically
  - **Fine** -> fine tuning in cents
  - **Spread** -> detunes L/R resonators -> positive = L higher, R lower; adds stereo width
  - **Transpose** -> coarse MIDI tuning offset in semitones
  - **PB Range** -> pitch bend range in semitones

  *Filter:*
  - **Filter toggle** -> band-pass filter on input -> narrow the excitation frequency range
  - **Freq** -> center frequency of input filter
  - **Bdwidth** -> bandwidth of input filter

  *LFO:*
  - **LFO Amount** -> modulation depth on resonant frequency
  - **LFO Rate** -> Hz or tempo-synced
  - **LFO Wave** -> Sine, Square, Triangle, Saw Up, Saw Down, Stepped Noise, Smooth Noise

  *Global:*
  - **Bleed** -> mixes unprocessed input back in -> restore transients and high frequencies lost in resonance
  - **Gain** -> output level (has automatic limiter)
  - **Dry/Wet** -> blend

- **Reach for this when:** Making drums sound like they're played on a resonant surface; adding pitched body resonance to percussion; creating tuned metallic textures; simulating marimbas, gongs, or struck objects from noise/clicks; MIDI-controlled resonant effects.
- **Don't use when:** You want a simple filter (use Auto Filter); you want parallel tuned delay lines (use Resonators); you want spectral-domain processing (use Spectral Resonator).
- **Pairs well with:** Drum Rack (Corpus on individual drum pads for tuned percussion), Operator/Simpler (excite Corpus with short clicks for synthetic instruments), Auto Filter (filter before Corpus to control excitation bandwidth), Reverb (after Corpus for resonant spaces).
- **vs Resonators:** Corpus uses physical modeling (real object simulation); Resonators uses tuned delay lines. Corpus sounds more organic and varied; Resonators is more musical and chord-oriented.
- **vs Spectral Resonator:** Corpus models physical objects; Spectral Resonator works in FFT domain. Corpus for realistic resonant body simulation; Spectral Resonator for otherworldly spectral effects.

---

### Resonators

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Resonators")`
- **What it does:** Five parallel tuned delay lines that ring at set pitches, creating tonal resonance from any input. The input passes through a multi-mode filter first, then feeds all five resonators simultaneously. Each resonator is tuned relative to the first, making it easy to set up chord voicings. Turns noise, drums, and speech into pitched, ringing tones.
- **Signal flow:** Input -> Multi-mode filter (LP/HP/BP/Notch) -> Resonator I (stereo) + Resonator II (left) + Resonator III (right) + Resonator IV (left) + Resonator V (right) in parallel -> Width control -> Output.
- **Key parameters:**

  *Input Filter:*
  - **Filter Type** -> LP, HP, BP, Notch -> shapes what frequencies excite the resonators; HP filters remove low rumble for cleaner resonance
  - **Filter Freq** -> cutoff frequency of input filter
  - **Filter Gain** -> gain of input filter (for shelf modes)

  *Resonator Controls:*
  - **Note (Resonator I)** -> root pitch of the resonator bank -> sets the fundamental; all other resonators are relative to this
  - **Fine (Resonator I)** -> fine tuning in cents
  - **Resonators II-V Pitch** -> semitone offset from Resonator I -> +/-24 semitones; set to chord intervals (e.g., +4, +7 for major triad; +3, +7 for minor)
  - **Resonators II-V Fine** -> cent offset for each
  - **Resonator I-V Gain** -> individual level per resonator -> balance the chord voicing
  - **Resonator II-V On/Off** -> enable/disable individual resonators

  *Global:*
  - **Mode A / B** -> two distinct tonal characters -> Mode A is brighter and more present; Mode B drops pitch by an octave and sounds darker, more muffled. Try both on every source
  - **Decay** -> feedback/ring time for all resonators -> short (0.1-1 s) for percussive pings; medium (2-5 s) for sustained chords; long (10+ s) for infinite drones
  - **Const (Constant)** -> keeps delay time constant regardless of pitch -> when off, higher pitches decay faster (natural behavior); when on, even decay across all pitches
  - **Color** -> brightness of the resonance -> low values roll off highs (warm, muffled); high values keep brightness (twangy, metallic)
  - **Width** -> stereo spread of resonators II-V -> 0% = mono center; 100% = full stereo panning

- **Reach for this when:** Turning drums or noise into pitched chords; creating drone/chord beds from any audio; sympathetic string resonance effects; adding pitched ringing to percussion; sound design where you want a specific chord to ring out.
- **Don't use when:** You need a single resonant body simulation (use Corpus); you want spectral processing (use Spectral Resonator); you need a clean EQ (use EQ Eight).
- **Pairs well with:** Drum Rack (Resonators on a bus creates pitched rhythm), Reverb (after Resonators for massive spaces), Compressor (tame resonant peaks), Auto Filter (modulated filter before Resonators for evolving excitation).
- **vs Corpus:** Resonators creates chord-based resonance via delay lines; Corpus simulates a single physical object. Resonators for harmonic/musical effects; Corpus for realistic physical modeling.
- **vs Spectral Resonator:** Resonators is simple and musical (5 pitched delay lines); Spectral Resonator is complex and experimental (FFT-based). Resonators for predictable pitched resonance; Spectral Resonator for alien transformations.

---

### Vocoder

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Vocoder")`
- **What it does:** Classic vocoder effect using parallel filter banks. Analyzes the modulator signal's spectral envelope and imposes it onto the carrier signal. The modulator provides the rhythm and articulation (typically voice or drums); the carrier provides the pitch and timbre (typically a synth). Creates robotic speech, harmonic rhythms, and spectral blending effects.
- **Signal flow:** Modulator input -> Analysis filter bank (4-40 bands) -> Envelope followers extract amplitude per band -> Carrier input (Noise/External/Modulator/Pitch Tracking) -> Synthesis filter bank (same band count) -> Envelope followers control synthesis band levels -> Sum -> Formant shift -> Output.
- **Key parameters:**

  *Carrier:*
  - **Carrier Type** -> source of the output's tonal content -> Noise (built-in filtered noise), External (audio from another track via sidechain), Modulator (signal vocodes itself), Pitch Tracking (monophonic oscillator follows modulator pitch)
  - **Noise** -> when Carrier = Noise, a built-in broadband noise source provides the harmonic material
  - **External** -> select sidechain source track (typically a synth playing sustained chords)
  - **Enhance** -> normalizes carrier volume and dynamics -> on = brighter, clearer vocoded output; off = more natural dynamics

  *Filter Bank:*
  - **Bands** -> number of analysis/synthesis filter bands -> 4-40; more bands = more intelligible/accurate; fewer = more smeared/abstract. Sweet spot: 16-24 for voice, 8-12 for drums
  - **Range (Low/High)** -> frequency range of the filter bank -> default covers full spectrum; narrow for focused effects (e.g., 200 Hz - 8 kHz for voice)
  - **BW (Bandwidth)** -> overlap between adjacent filter bands -> low % = narrow, precise; high % = blurred, smeared; 100% = natural overlap

  *Envelope:*
  - **Depth** -> how much modulator envelope shapes the carrier -> 0% = no modulation (pure carrier); 100% = classic vocoder; 200% = exaggerated peaks only. Sweet spot: 80-120% for voice
  - **Attack** -> how fast filter bands respond to rising modulator levels -> 1 ms for crisp articulation; 10-50 ms for smoother response
  - **Release** -> how fast filter bands respond to falling modulator levels -> 50-150 ms for speech clarity; 500+ ms for sustain and pad-like smoothing

  *Formant & Voicing:*
  - **Formant** -> shifts the synthesis filter bank up or down relative to analysis -> positive = smaller/brighter/female character; negative = larger/darker/male character; 0 = neutral
  - **Unvoiced** -> adds white noise layer for consonants and transients -> 0% = fully vocoded (muffled consonants); 10-30% restores sibilance and "s"/"t" sounds; essential for speech intelligibility
  - **Sens (Sensitivity)** -> threshold for the Unvoiced detector -> adjusts when consonant noise kicks in
  - **Gate** -> threshold below which output is silenced -> use to remove background noise between words/phrases

  *Output:*
  - **Processing Mode** -> Precise, Retro, Fast -> Precise = clean digital; Retro = vintage vocoder character; Fast = lowest latency
  - **Mono / Stereo / L/R** -> stereo processing mode
  - **Dry/Wet** -> blend

- **Reach for this when:** Robotic voice effects; making drums speak; imposing vocal rhythm onto synth pads; harmonic sound design; creating rhythmic textures from static sounds; Daft Punk-style vocal processing.
- **Don't use when:** You want pitched resonance without a carrier signal (use Spectral Resonator); you want a simple filter (use Auto Filter); you just need EQ (use EQ Eight).
- **Pairs well with:** Operator/Analog (as carrier synth), Reverb (after Vocoder for space), Compressor (tame dynamic range of vocoded output), Utility (gain staging before Vocoder input), Chorus (after Vocoder for width).
- **vs Spectral Resonator:** Vocoder uses filter banks and needs carrier + modulator; Spectral Resonator uses FFT on a single input. Vocoder for classic robotic effects; Spectral Resonator for spectral transformation.

---

## User M4L Devices (CLX_02 Collection)

---

### 3-Band EQ (M4L by TheM)

- **Type:** M4L User
- **Load via:** `find_and_load_device(track_index, "3-Band EQ")` (search user library)
- **What it does:** Zero-latency 3-band equalizer designed specifically for DJing. Fixes the phase distortion issues present in Ableton's native EQ Three (which can cause unwanted signal peaks at crossover points). Cleaner crossover behavior with adjustable frequency points.
- **Signal flow:** Input -> 3-band crossover (adjustable FreqLow and FreqHi) -> independent gain per band -> Volume fader with adjustable curve -> Output.
- **Key parameters:**
  - **Low / Mid / High Gain** -> per-band level control -> two modes: "-52 dB to 0 dB" (cut only, safer for DJ use) or "-42 to +10 dB" (cut + boost)
  - **FreqLow** -> low/mid crossover frequency -> adjustable; set to match your genre (e.g., 120 Hz for house, 200 Hz for hip-hop)
  - **FreqHi** -> mid/high crossover frequency -> adjustable
  - **Volume Fader** -> master output level
  - **Volume Curve** -> adjusts the response curve of the volume fader -> tailor to your controller's feel
- **Reach for this when:** DJing in Ableton and you want cleaner crossovers than EQ Three; you need phase-correct band separation; you want a cut-only DJ EQ.
- **Don't use when:** Mixing or mastering (use EQ Eight or Channel EQ); you need kill switches (use EQ Three natively or map buttons).
- **vs EQ Three:** Cleaner phase response, no coloration at neutral, adjustable crossover points. EQ Three has built-in kill switches and the familiar DJ mixer character.

---

### GMaudio VSEQ 1.0 (M4L by groovmekanik)

- **Type:** M4L User
- **Load via:** `find_and_load_device(track_index, "VSEQ")` or `find_and_load_device(track_index, "GMaudio VSEQ")` (search user library)
- **What it does:** Combines a dual-shelf EQ (the "V-Filter") with a 3-band multiband saturation engine. The V-Filter uses two first-order shelving filters centered at 700 Hz with automatic volume compensation. The saturation splits the signal into 3 bands, each feeding a separate wave-shaper to generate distinct overtones. Includes 4x oversampling to minimize aliasing. Designed as a "tone + harmonics" channel strip tool.
- **Signal flow:** Input -> V-Filter (low shelf + high shelf at 700 Hz pivot, with auto-gain compensation) -> [EQ Mode switch: filter can apply to original signal OR to saturation input only] -> 3-band multiband saturation (3 independent wave-shapers) -> Colour control (harmonic balance) -> Output.
- **Key parameters:**
  - **V-Filter Low** -> low shelf gain around 700 Hz -> positive = boost lows; negative = cut lows (emphasizes mids/highs)
  - **V-Filter High** -> high shelf gain around 700 Hz -> positive = boost highs; negative = cut highs (emphasizes lows/mids)
  - **EQ Mode** -> where the V-Filter is applied -> "Signal" = filters the output; "Sat Input" = filters only the saturation input (focus harmonics where needed)
  - **Amount** -> saturation intensity -> gentle at low values, aggressive distortion at high values
  - **Colour** -> harmonic balance of the 3-band saturation -> shapes which overtones are emphasized
- **Reach for this when:** You want quick tonal shaping plus harmonic enhancement in one device; adding warmth and presence to a mix bus; focusing saturation harmonics on specific frequency ranges.
- **Don't use when:** You need precise surgical EQ (use EQ Eight); you want clean transparent EQ without saturation (use Channel EQ).
- **vs Channel EQ:** VSEQ adds multiband saturation that Channel EQ lacks; Channel EQ has a sweepable mid that VSEQ lacks. VSEQ for "tone + grit", Channel EQ for "tone only".

---

### REW EQ by Iftah (M4L)

- **Type:** M4L User
- **Load via:** `find_and_load_device(track_index, "REW EQ")` (search user library)
- **What it does:** Imports filter settings from Room EQ Wizard (.txt export files) and applies them as parametric EQ corrections inside Ableton. Visualizes the imported EQ curve. Designed for studio monitoring correction -- measure your room with REW, export the correction filters, import into this device on your master bus to hear a corrected response while mixing.
- **Signal flow:** Import REW .txt filter file -> Parse PK (peak) filter parameters -> Apply as parametric EQ bands -> Output with corrected frequency response.
- **Key parameters:**
  - **Import** -> loads a REW filter export file (.txt format)
  - **EQ Curve Display** -> visual representation of the imported correction curve
  - **Filter bands** -> automatically set from the imported REW data; supports PK (peak/parametric) filter type, which covers 99.9% of room correction use cases
- **Reach for this when:** You've measured your room with Room EQ Wizard and want to apply correction directly in Ableton on the master bus; monitoring correction without external software; comparing corrected vs uncorrected monitoring.
- **Don't use when:** Creative EQ work (this is purely corrective); you haven't measured your room with REW first; you need filter types other than PK (peak).
- **Pairs well with:** Utility (place before REW EQ for monitoring level control), Spectrum (verify correction is working as expected).
- **Note:** Only supports PK (peak) filter type from REW exports. Other filter types (shelf, etc.) are not currently supported but rarely needed for room correction.

---

### Cat Growl Filter (M4L by Nick Holiday)

- **Type:** M4L User
- **Load via:** `find_and_load_device(track_index, "Cat Growl Filter")` (search user library)
- **What it does:** Multi-purpose FX rack designed for aggressive, characterful filter sweeps. Features a custom dual-channel filter (independent L/R) with 8 interchangeable filter types per channel. The channels can move in sync or independently. Built for bass music, dubstep growls, and aggressive sound design. Includes 10 pre-mapped macros for quick performance control.
- **Signal flow:** Input -> Dual-channel filter (L and R processed independently or synced) -> FX modules (series of carefully tuned processors that enhance the "growl" character) -> Macro-controlled parameters -> Output.
- **Key parameters:**
  - **Filter Type L / Filter Type R** -> independent filter type per channel -> 8 types each: Lowpass, Highpass, Bandpass, Bandstop, Peaknotch, Low Shelf, High Shelf, Resonant
  - **Filter Frequency** -> cutoff frequency for filter sweep -> the core performance parameter; automate or map to a controller
  - **L/R Sync** -> whether both channels move together or independently -> sync for standard sweeps; independent for stereo movement and phase effects
  - **Macro 1-10** -> pre-programmed control mappings -> each macro affects multiple internal parameters for instant sonic variation; turning any one can produce subtle or drastic effects
  - **Resonance** -> filter emphasis -> push for more aggressive growl character
- **Reach for this when:** Bass music sound design; aggressive dubstep/riddim growl effects; you want stereo filter effects with independent L/R processing; performance-oriented filter sweeps with macro control.
- **Don't use when:** You need clean, transparent filtering (use Auto Filter with SVF circuit); you want simple EQ (use EQ Eight); subtle mix work.
- **vs Auto Filter:** Cat Growl Filter is purpose-built for aggressive character with dual-channel and macro FX chain; Auto Filter is more versatile and transparent. Cat Growl Filter for bass music growls; Auto Filter for everything else.

---

### Stretta Filter Sequencer (M4L by Matthew Davidson / stretta)

- **Type:** M4L User
- **Load via:** `find_and_load_device(track_index, "Filter Sequencer")` or `find_and_load_device(track_index, "Step Filter")` (search user library)
- **What it does:** Eight independent step sequencers, each controlling a bandpass filter. Originally designed as a monome controller app for a Doepfer vocoder filter bank, now has the filter bank built-in. Each of the 8 bandpass filters can have a different loop length, creating polymetric rhythmic filtering patterns. Essentially a rhythmic vocoder-like effect driven by step sequencing rather than a modulator signal.
- **Signal flow:** Input -> 8 parallel bandpass filters -> each filter's amplitude is sequenced by its own step sequencer (independent loop lengths) -> Sum of filtered outputs -> Output.
- **Key parameters:**
  - **Step Sequences 1-8** -> each row is an independent step sequencer controlling one bandpass filter's amplitude -> edit steps to create rhythmic filter patterns
  - **Loop Length per filter** -> independent loop length for each of the 8 sequencers -> set different lengths for polymetric patterns (e.g., 5, 7, 8, 11 steps)
  - **Band Frequencies** -> center frequency for each of the 8 bandpass filters -> spread across the spectrum for full vocoder-like coverage
  - **Rate/Clock** -> sequencer speed, typically synced to tempo
- **Reach for this when:** Rhythmic spectral effects; polymetric filter patterns; vocoder-like rhythmic gating without needing a modulator signal; experimental sequenced filtering; glitch and IDM production.
- **Don't use when:** You need a standard filter sweep (use Auto Filter); you need static EQ (use EQ Eight); you want standard vocoding with speech (use Vocoder).
- **vs Vocoder:** Stretta Filter Sequencer uses step-sequenced bandpass filters; Vocoder uses a modulator signal's envelope. Filter Sequencer for precise rhythmic control; Vocoder for real-time spectral imprinting.
- **Note:** Originally designed for monome hardware controllers but works without one. Best experience is with the monome surface for direct tactile sequence editing.

---

## Quick Decision Matrix

| I want to... | Use this | Why |
|---|---|---|
| Surgically shape frequency balance | **EQ Eight** | 8 bands, multiple filter shapes, M/S mode |
| Quick console-style tone shaping | **Channel EQ** | 3 musical bands, fast, low CPU |
| DJ-style frequency kills | **EQ Three** | Kill switches, -inf gain, DJ mixer character |
| Phase-correct DJ EQ | **3-Band EQ (M4L)** | Cleaner crossovers than EQ Three |
| Moving filter sweeps | **Auto Filter** | LFO, envelope follower, sidechain, 10 filter types, 6 circuits |
| Aggressive bass growl filter | **Cat Growl Filter (M4L)** | Dual-channel, 8 types, macro FX, purpose-built for growl |
| Tuned resonant body on drums | **Corpus** | Physical modeling of beams, plates, strings, pipes |
| Chord-based pitched resonance | **Resonators** | 5 parallel tuned delay lines, easy chord voicing |
| Spectral shimmer and harmonics | **Spectral Resonator** | FFT-based, MIDI-playable, unison/stretch/modulation |
| Robotic voice / speech on synth | **Vocoder** | Classic carrier/modulator filter bank vocoding |
| Rhythmic sequenced filtering | **Stretta Filter Sequencer (M4L)** | 8 independent step-sequenced bandpass filters |
| Tone shaping + saturation in one | **GMaudio VSEQ (M4L)** | V-Filter shelves + 3-band multiband saturation |
| Room correction from REW | **REW EQ (M4L)** | Direct import of Room EQ Wizard correction curves |
| Transparent static EQ, no color | **EQ Eight** (Oversampling on) | Cleanest native EQ, adaptive Q off for digital precision |
| Warm analog-modeled filter | **Auto Filter** (MS2 or PRD circuit) | Korg/Moog circuit models with drive |
| Turn anything into a pitched drone | **Resonators** (long Decay) or **Spectral Resonator** (long Decay) | Both can create infinite sustain from transient input |

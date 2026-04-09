# Dynamics & Punch — Device Atlas

> Deep reference for every dynamics processor available in this Ableton Live 12 installation.
> Covers native devices, Creative Extensions M4L, Transient Machines pack, and user CLX_02 collection.

---

## Native Ableton Devices

---

### Compressor

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Compressor")`
- **What it does:** General-purpose dynamics processor that attenuates signals above a threshold. Extremely versatile — can be transparent glue or aggressive pumping depending on settings. Clean, digital character with no inherent coloration.
- **Signal flow:** Input -> Sidechain EQ (optional) -> Envelope Follower (Peak/RMS/Expand) -> Gain Reduction -> Makeup/Output -> Dry/Wet
- **Key parameters:**
  - **Threshold** (-inf to 0 dB) -> where compression begins -> start at -20 dB for gentle, -10 dB for moderate
  - **Ratio** (1:1 to inf:1) -> compression intensity -> 2:1-4:1 for bus glue, 6:1-10:1 for peak control, inf:1 for limiting
  - **Attack** (0.01 ms to 1000 ms) -> how fast compression engages -> 0.1-1 ms for peak catching, 10-30 ms to let transients through, 50+ ms for transparent leveling
  - **Release** (1 ms to 3000 ms + Auto) -> recovery time -> 50-100 ms for transparent, 25 ms for pumping, Auto for adaptive behavior
  - **Knee** (0 dB to 36+ dB) -> compression gradient -> 0 dB = hard knee (aggressive), 6-10 dB for vocals, 36 dB for ultra-transparent
  - **Output/Makeup** -> compensates for volume loss -> use Makeup button for auto-compensation
  - **Lookahead** (0 ms, 1 ms, 10 ms) -> anticipates peaks -> 10 ms for true peak limiting, 0 ms for zero latency
  - **Dry/Wet** (0-100%) -> parallel compression blend -> 30-50% for parallel on drums, 100% for insert
  - **Mode:** Peak (reacts to short peaks, aggressive), RMS (averages level, more musical), Expand (upward expansion, ratio inverted e.g. 1:2)
  - **Envelope:** Lin (linear) vs Log (logarithmic) -> Lin for fast transient response, Log for smoother behavior
  - **Sidechain EQ:** low-shelf, peak, high-shelf, low-pass, band-pass, notch -> use HP sidechain at 80-100 Hz to prevent bass pumping
- **Presets:** Acoustic Guitar, Bass, Drums Bus, Kick, Mastering, Vocal, Slow Attack, Fast Attack, Limiter, NY Compression (parallel)
- **Reach for this when:** you need precise, surgical control over dynamics; sidechain pumping; transparent bus compression; any situation where you want maximum flexibility
- **Don't use when:** you want analog warmth/color (use Glue Compressor), you want a quick one-knob solution (use Drum Buss or Squeeze), you need multiband processing (use Multiband Dynamics)
- **Pairs well with:** Saturator before it for warmth, EQ Eight after for tonal shaping, Utility for gain staging
- **vs Glue Compressor:** Compressor is more flexible and clinical; Glue adds SSL-style analog character. Use Compressor for surgical control, Glue for musical bus processing.

---

### Glue Compressor

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Glue Compressor")`
- **What it does:** SSL 4000 G Bus Compressor emulation by Cytomic. Adds analog warmth, glues elements together on buses. Has inherent musical character — slightly rounds transients and adds subtle harmonic content. The "gel" compressor.
- **Signal flow:** Input -> Sidechain EQ (optional) -> VCA-style Compression -> Soft Clip (optional) -> Makeup -> Dry/Wet
- **Key parameters:**
  - **Threshold** (-40 to 0 dB) -> where compression starts -> -20 to -15 dB for gentle bus glue, -30 dB for aggressive
  - **Ratio** (2:1, 4:1, 10:1 — fixed steps, SSL-style) -> 2:1 for bus glue, 4:1 for moderate taming, 10:1 for aggressive limiting
  - **Attack** (0.01, 0.1, 0.3, 1, 3, 10, 30 ms — fixed steps) -> 0.3 ms for punchy drums, 1-3 ms for bus, 10-30 ms for transparent
  - **Release** (0.1, 0.2, 0.4, 0.6, 0.8, 1.2 s + Auto — fixed steps) -> 0.2-0.4 s for rhythmic pumping, Auto for adaptive, 0.1 s for aggressive
  - **Range** (-40 to 0 dB) -> limits maximum gain reduction -> -6 dB for gentle bus (prevents over-compression), -3 dB for subtle glue
  - **Makeup** (0 to +36 dB) -> volume compensation
  - **Soft Clip** (on/off) -> analog-style waveshaping at -0.5 dB -> always ON for bus processing, adds subtle warmth
  - **Dry/Wet** (0-100%) -> parallel compression -> 60-70% for parallel drum bus, 100% for insert
  - **Sidechain:** external source + EQ (same filter types as Compressor)
- **Presets:** Bus Glue, Master Glue, Drum Bus, Parallel Drum, Bass Control
- **Reach for this when:** mixing buses (drum bus, music bus, master), you want elements to "gel" together, you need musical compression with character, drum group processing
- **Don't use when:** you need precise surgical control (use Compressor), you need per-band processing (use Multiband Dynamics), processing individual elements that need transparency
- **Pairs well with:** EQ Eight before for problem solving, Limiter after on master, Drum Buss before it on drum groups
- **vs Compressor:** Glue has fixed SSL-style attack/release/ratio steps (less flexible, more musical). Compressor has continuous ranges (more flexible, more clinical). Glue adds character; Compressor is transparent.
- **vs Drum Buss:** Glue is a pure compressor; Drum Buss combines saturation, transient shaping, and resonant bass. Use Glue for bus-level cohesion, Drum Buss for color and punch on drums.

---

### Limiter

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Limiter")`
- **What it does:** Brickwall limiter — no signal passes above the ceiling. Completely redesigned in Live 12.1 with True Peak, Soft Clip, and Maximize modes. The safety net. Ensures nothing clips, or pushes loudness when used as a maximizer.
- **Signal flow:** Input -> Gain -> Lookahead Peak Detection -> Gain Reduction -> Ceiling -> Output
- **Key parameters:**
  - **Gain** -> boosts input level before limiting -> push into limiter for louder output, keep at 0 dB for safety limiting
  - **Ceiling** -> maximum output level -> -1.0 dB for streaming (Spotify/YouTube standard), -0.3 dB for CD, 0 dB only for intermediate processing
  - **Lookahead** (1.5 ms, 3 ms, 6 ms) -> anticipation time -> 6 ms for cleanest limiting (least distortion), 1.5 ms for minimal latency
  - **Release** (0.01 ms to 3 s + Auto) -> recovery speed -> Auto for most situations, short for aggressive/pumping, long for transparent
  - **Stereo Link:** Linked (both channels reduced equally, preserves stereo image) vs L/R (independent, can shift stereo image) vs Mid/Side (12.1+)
  - **Mode (12.1+):** Standard (light limiting, open sound), True Peak (prevents inter-sample peaks, streaming-ready), Soft Clip (adds crunch/character, great for aggressive mixes)
  - **Maximize (12.1+):** boosts output by amount of gain reduction -> single-knob loudness control via Threshold
- **Presets:** Mastering, Safety, Loudness, Streaming
- **Reach for this when:** final device on master chain, preventing clipping, maximizing loudness for delivery, safety limiting on live performance
- **Don't use when:** you want dynamics shaping (use Compressor), you want warmth (use Color Limiter or Glue Compressor), you need the sound to breathe
- **Pairs well with:** Compressor or Glue Compressor before it for dynamics shaping, EQ Eight before for final tonal balance, Utility before for gain staging
- **vs Color Limiter:** Limiter is clinical and transparent; Color Limiter adds saturation and harmonic character. Limiter for mastering precision, Color Limiter for lo-fi/vintage vibe.

---

### Gate

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Gate")`
- **What it does:** Noise gate that silences audio below a threshold. Cleans up recordings, shapes drum tails, creates rhythmic effects via sidechain. The "bouncer" — only lets loud enough signals through.
- **Signal flow:** Input -> Sidechain EQ (optional) -> Envelope Follower -> Gate Open/Close -> Floor Attenuation -> Output
- **Key parameters:**
  - **Threshold** (-80 to 0 dB) -> level that opens the gate -> set just above noise floor, -40 to -30 dB for mic cleanup
  - **Return/Hysteresis** -> dB difference between open and close thresholds -> prevents rapid open/close chattering, 2-6 dB typical
  - **Attack** (0.01 to 100 ms) -> how fast gate opens -> 0.01-0.5 ms for drums (preserve transient), 5-10 ms for vocals (avoid clicks)
  - **Hold** (0 to 500 ms) -> minimum open time -> 20-50 ms for drums, 100+ ms for vocals
  - **Release** (1 to 1000 ms) -> how fast gate closes -> 20-50 ms for tight drums, 100-200 ms for natural vocal tails
  - **Floor** (-inf to 0 dB) -> attenuation when closed -> -inf for complete silence, -20 to -10 dB for natural bleed reduction
  - **Flip** (on/off) -> inverts behavior: gate closes above threshold -> creative tremolo/chopping effects
  - **Lookahead** (0 to 10 ms) -> anticipates transients -> 1-5 ms to catch drum attacks cleanly
  - **Sidechain EQ:** LP/HP/BP/Notch/Shelf filters -> HP at 5 kHz to trigger on hi-hats only, LP at 200 Hz to trigger on kicks only
- **Presets:** Drum Gate, Noise Reduction, Vocal Cleanup, Rhythmic Gate
- **Reach for this when:** cleaning drum bleed, gating noisy recordings, removing amp hum, creating rhythmic chopping effects via sidechain, tightening drum tails
- **Don't use when:** you need smooth dynamics control (use Compressor), the source has complex dynamics that need riding (use Gain Rider), you want creative envelope reshaping (use Re-Enveloper)
- **Pairs well with:** Compressor after for dynamics control, EQ Eight before to shape what the gate "hears", Corpus/Reverb after gated drums for big room sound
- **vs Re-Enveloper:** Gate is binary (open/close); Re-Enveloper reshapes the amplitude envelope continuously per frequency band. Gate for cleanup, Re-Enveloper for creative reshaping.

---

### Multiband Dynamics

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Multiband Dynamics")`
- **What it does:** Three-band dynamics processor that can independently compress, expand, or gate each frequency band. The Swiss Army knife of dynamics — can do OTT, multiband compression, frequency-selective gating, and upward/downward processing. Home of the legendary OTT preset.
- **Signal flow:** Input -> 3-Band Crossover -> Per-Band Above/Below Threshold Processing -> Per-Band Output Gain -> Output
- **Key parameters:**
  - **Crossover Frequencies** (2 adjustable points) -> split into Low/Mid/High -> default ~120 Hz and ~2.5 kHz, adjust per material
  - **Above Threshold** (per band) -> downward compression when signal is above -> ratio + threshold control
  - **Below Threshold** (per band) -> upward compression when signal is below -> ratio + threshold control -> this is the OTT magic
  - **Above Ratio** (1:1 to inf) -> downward compression intensity -> 3:1 for gentle, 10:1 for aggressive
  - **Below Ratio** (1:1 to inf) -> upward compression intensity -> 2:1 for subtle detail enhancement, 10:1 for extreme OTT
  - **Attack** (per band, 0.01 to 1000 ms) -> 10-30 ms for kicks, 1-5 ms for snares
  - **Release** (per band, 1 to 3000 ms) -> 150-300 ms for drums, 500+ ms for pads
  - **Soft Knee** (on/off) -> gradual compression onset
  - **Peak/RMS** (per band) -> Peak for transient control, RMS for level averaging
  - **Output Gain** (per band) -> post-processing level control
  - **Time** scaling -> global multiplier for all attack/release times
  - **Amount** -> global depth control for all dynamics processing
- **Presets:** OTT (extreme multiband upward+downward), Multiband Comp, Bass Tightener, De-Esser, Mastering
- **Reach for this when:** you need frequency-selective dynamics (tighten bass without affecting highs), OTT effect, de-essing, creative multiband squashing, mastering where specific bands need different treatment
- **Don't use when:** simple compression suffices (use Compressor), you want quick one-knob results (use Squeeze or Drum Buss), you need more than 3 bands (use PentaComp)
- **Pairs well with:** EQ Eight before for pre-shaping, Saturator after for warmth, Limiter after for final peak control
- **vs PentaComp:** Multiband Dynamics has 3 bands with upward+downward processing; PentaComp has 5 bands but only downward. Multiband Dynamics for creative OTT-style processing, PentaComp for transparent multiband mixing.
- **vs Squeeze:** Both do upward compression. Multiband Dynamics is surgical with per-band control. Squeeze is simpler and more extreme. Multiband Dynamics for precision, Squeeze for vibe.

---

### Drum Buss

- **Type:** Native
- **Load via:** `find_and_load_device(track_index, "Drum Buss")`
- **What it does:** All-in-one drum processor combining compression, distortion, transient shaping, and low-end enhancement. Designed to add body, punch, and character to drum groups. The "instant drums sound better" device. Analog-modeled throughout.
- **Signal flow:** Input -> Trim -> Fixed Compressor (optional) -> Distortion (Soft/Medium/Hard) -> Drive -> Crunch (mid-high distortion) -> Damp (LP filter) -> Transients (above 100 Hz) -> Boom (resonant LP filter below 100 Hz) -> Dry/Wet -> Output
- **Key parameters:**
  - **Trim** -> input level reduction -> use to prevent internal clipping on hot signals
  - **Comp** (on/off) -> fixed compressor: fast attack, medium release, moderate ratio, ample makeup -> always try ON first for drum groups
  - **Distortion Type:** Soft (waveshaping, subtle warmth), Medium (limiting distortion, moderate grit), Hard (clipping + bass boost, aggressive)
  - **Drive** (0 to max) -> input drive into distortion -> 20-40% for warmth, 50-80% for crunch, 100% for destruction
  - **Crunch** -> sine-shaped distortion on mid-high frequencies -> adds presence and bite to snares/hats -> 0-30% for subtle, 50%+ for aggressive
  - **Damp** -> low-pass filter -> removes harsh high-frequency artifacts from distortion -> adjust to taste, lower = darker
  - **Transients** (-100 to +100) -> emphasizes (positive) or de-emphasizes (negative) transients above 100 Hz -> +30-50 for punch, -20 for smoothing, 0 for neutral
  - **Boom** -> resonant low-pass filter boost amount below 100 Hz -> adds sub-bass weight -> 20-40% for warmth, 60%+ for booming sub
  - **Boom Freq** -> center frequency of low-end enhancer -> tune to track's key frequency
  - **Force To Note** -> snaps Boom frequency to nearest MIDI note -> ensures low-end is tuned
  - **Boom Decay** -> fade rate of low frequencies -> short for tight kick, long for rumble
  - **Boom Audition** (headphone icon) -> solo the Boom signal to tune it
  - **Dry/Wet** (0-100%) -> blend -> 30-50% for subtle enhancement, 100% for full processing
  - **Output Gain** -> final level control
- **Presets:** Big Beat, Boom Box, Crunch, Lo-Fi, Punchy, Sub, Warm, Wide
- **Reach for this when:** processing drum groups or loops, you want instant punch and character, you need low-end enhancement on kicks, you want one device instead of a chain of compressor+saturator+transient shaper+EQ
- **Don't use when:** you need transparent compression (use Compressor), you're processing non-drum material (though it can work on bass and synths), you need precise per-parameter control (use dedicated devices)
- **Pairs well with:** Glue Compressor after for bus cohesion, EQ Eight after for surgical fixes, Reverb send for processed drum ambience
- **vs Compressor + Saturator chain:** Drum Buss is faster to dial in but less flexible. The dedicated chain gives more control. Use Drum Buss for "good enough fast", the chain for surgical mixing.

---

## Creative Extensions (M4L Stock)

---

### Color Limiter

- **Type:** M4L Stock (Creative Extensions pack — free with Live Suite)
- **Load via:** `find_and_load_device(track_index, "Color Limiter")` or `search_browser(path="audio_effects", name_filter="Color Limiter")`
- **What it does:** Hardware-inspired limiter that adds saturation and harmonic coloration while limiting. Unlike the clean native Limiter, Color Limiter is designed to add grit, pressure, and vintage character. Think: tube limiter behavior in a digital box.
- **Signal flow:** Input -> Loudness (input gain) -> Lookahead Detection -> Ceiling Limiting + Saturation/Color Processing -> Release Recovery -> Output
- **Key parameters:**
  - **Loudness** -> input amplification before limiting -> push harder for more color and compression
  - **Ceiling** -> maximum output threshold -> same concept as Limiter but with colored limiting behavior
  - **Lookahead** -> anticipation time for peak detection -> longer = cleaner, shorter = more character
  - **Release** -> recovery time after limiting -> short for aggressive pumping, long for transparent
  - **Saturation** -> amount of harmonic distortion -> 0% for clean limiting, 30-50% for warmth, 80%+ for aggressive crunch
  - **Color** -> selects saturation type/character -> the "flavor" knob — experiment per source
- **Presets:** Various, explore the Creative Extensions presets
- **Reach for this when:** you want limiting WITH character, processing breaks and beats that need pressure, putting a vintage stamp on drum loops, lo-fi mastering, when the native Limiter sounds too clean
- **Don't use when:** you need transparent mastering (use Limiter), you need True Peak compliance (use Limiter in True Peak mode), you need precise metering
- **Pairs well with:** Drum Buss before for drum processing chains, EQ Eight after for tonal cleanup, Saturator before for stacking coloration
- **vs Limiter:** Limiter is surgical transparency; Color Limiter is musical coloration. Never use Color Limiter for final mastering delivery — use it for creative processing and intermediate bus limiting.

---

### Re-Enveloper

- **Type:** M4L Stock (Creative Extensions pack — free with Live Suite)
- **Load via:** `find_and_load_device(track_index, "Re-Enveloper")` or `search_browser(path="audio_effects", name_filter="Re-Enveloper")`
- **What it does:** Multiband envelope reshaper. Splits audio into three adjustable frequency bands and lets you compress OR expand the amplitude envelope of each independently. Goes far beyond gating — it literally redraws the volume shape of the sound per frequency band. Can highlight transients, extend sustain, destroy dynamics, or surgically carve elements.
- **Signal flow:** Input -> 3-Band Frequency Split -> Per-Band Envelope Detection -> Per-Band C/E (Compression/Expansion) Processing -> Per-Band Gain -> Output
- **Key parameters:**
  - **Crossover Frequencies** (2 points) -> split into Low/Mid/High bands
  - **C/E Factor** (per band) -> Compression/Expansion control -> positive values = compress envelope (reduce dynamics), negative values = expand envelope (exaggerate dynamics)
  - **Attack** (per band) -> envelope follower attack time
  - **Release** (per band) -> envelope follower release time
  - **Gain** (per band) -> output level per band
  - **Sensitivity** -> how responsive the envelope follower is
- **Reach for this when:** you need to reshape transients per frequency band, cleaning up frequency-specific dynamics (e.g., tighten low-end sustain while keeping high-end snap), creative envelope destruction, making sustained sounds percussive or percussive sounds sustained
- **Don't use when:** you need standard compression ratios (use Compressor), you need simple gating (use Gate), the task is basic level control
- **Pairs well with:** Compressor after for overall dynamics control, Reverb before for creative envelope reshaping of ambience, Multiband Dynamics for combined approach
- **vs Gate:** Gate is binary on/off; Re-Enveloper continuously reshapes the envelope. Re-Enveloper for creative work, Gate for cleanup.
- **vs Multiband Dynamics:** Multiband Dynamics uses traditional threshold/ratio; Re-Enveloper uses envelope compression/expansion factor. Different mental models, complementary tools.

---

## Transient Machines Pack (M4L)

---

### Crack

- **Type:** M4L (Transient Machines pack by Surreal Machines)
- **Load via:** `find_and_load_device(track_index, "Crack")` or `search_browser(path="audio_effects", name_filter="Crack")`
- **What it does:** Compact single-band transient shaper designed for individual sounds and loops. The "contrast dial for your sound" — makes transients pop or fade, and tails extend or shrink. Includes analog-modeled output processing (limiter, soft clip, maximizer) tuned specifically for transient material.
- **Signal flow:** Input -> Transient Detection -> Attack/Sustain Shaping -> Dry/Wet Mix -> Output Stage (Clipper/Limiter/Maximizer selectable)
- **Key parameters:**
  - **Attack** -> transient emphasis/reduction -> positive = more punch, negative = softer
  - **Sustain** -> tail emphasis/reduction -> positive = longer sustain, negative = tighter
  - **Dry/Wet** -> blend processed with original
  - **Output Mode:** Custom Limiter (peak reduction), Soft Clip (analog-modeled clipping), Maximizer (tuned for transients)
- **Reach for this when:** shaping individual drum hits, loop processing, adding punch to a single element, quick "more/less attack" adjustments
- **Don't use when:** you need multiband transient control (use Impact), you need frequency-specific processing (use Re-Enveloper), you need compression rather than transient shaping
- **Pairs well with:** EQ Eight before to focus source, Compressor after for overall dynamics, Drum Buss for combined character
- **vs Carver:** Crack is simpler (fewer controls, single-band). Carver has more features (curve types, sensitivity, M/S, distortion routing). Crack for quick utility, Carver for detailed sculpting.

---

### Impact

- **Type:** M4L (Transient Machines pack by Surreal Machines)
- **Load via:** `find_and_load_device(track_index, "Impact")` or `search_browser(path="audio_effects", name_filter="Impact")`
- **What it does:** Multi-band drum processing channel strip combining up to 3 bands of transient shaping, 4-band EQ, 4 saturation types, and output processing (clipper/limiter/maximizer). The "big brother" of Crack — a complete drum dynamics workstation in one device.
- **Signal flow:** Input -> 1/2/3 Band Split -> Per-Band Attack + Sustain Shaping -> 4-Band EQ -> Saturation (4 types) -> Output Stage (Clipper/Limiter/Maximizer)
- **Key parameters:**
  - **Band Count** (1, 2, or 3) -> independent frequency bands for transient processing
  - **Attack** (per band) -> transient emphasis/reduction per frequency range
  - **Sustain** (per band) -> tail control per frequency range
  - **EQ** (4 bands) -> tonal shaping integrated into processing chain
  - **Saturation Type** (4 analog-modeled styles) -> selectable harmonic character
  - **Output Stage:** Clipper, Limiter, or Maximizer -> final peak management
- **Reach for this when:** processing drum groups that need frequency-specific transient control, you want a complete drum processing chain in one device, multiband transient shaping with integrated saturation and EQ
- **Don't use when:** processing simple single hits (use Crack), you need transparent compression (use Compressor), the processing chain is already complex and you need a single-purpose tool
- **Pairs well with:** Glue Compressor after for bus cohesion, Reverb send for processed ambience, Drum Buss for additional coloration (use sparingly — both are opinionated)
- **vs Drum Buss:** Impact is transient-focused with multiband precision; Drum Buss is saturation-focused with resonant bass enhancement. Impact for surgical drum work, Drum Buss for quick vibe.

---

## User M4L (CLX_02 Collection)

---

### doomCompressor_v1.0

- **Type:** M4L User (CLX_02) — by poulhoi
- **Load via:** `search_browser(path="audio_effects", name_filter="doomCompressor")`
- **What it does:** Extreme upward compressor inspired by Mick Gordon's DOOM soundtrack technique. Instead of reducing loud signals, it amplifies quiet ones to near 0 dBFS. Makes everything audible — even the faintest noise floor becomes as loud as the transients. Creates a hyper-compressed, "everything is at maximum volume" effect. Used for aggressive sound design, industrial textures, and extreme effects.
- **Signal flow:** Input -> Envelope Follower -> Compare to Threshold -> Calculate normalization factor -> Apply multiplication to bring signal to 0 dBFS -> Attack/Release Smoothing -> Output
- **Key parameters:**
  - **Threshold** -> sets the level above which compression is calculated -> lower = more extreme, brings up more quiet detail
  - **Attack** -> smoothing time for compression onset
  - **Release** -> smoothing time for compression release
- **Reach for this when:** DOOM-style industrial sound design, extreme effect processing, making reverb tails and noise floors as loud as transients, aggressive experimental music, creating "wall of sound" textures
- **Don't use when:** you want musical compression (use Compressor), you want dynamics preservation (this destroys ALL dynamics), mixing or mastering conventional music
- **Pairs well with:** Reverb/Delay before (gets amplified dramatically), Saturator before (harmonics get pushed up), Limiter after (tame the chaos), EQ Eight after (surgical cleanup of amplified noise)
- **vs Raw Doom Compressor:** doomCompressor has adjustable attack/release (more control). Raw Doom Compressor has hard-coded timing but adds Floor and Output controls. doomCompressor for tweakability, Raw Doom for "set and destroy."
- **vs Squeeze:** Both do upward compression. Doom is extreme single-band normalization. Squeeze is multiband with more musical range. Doom for destruction, Squeeze for enhancement.

---

### RawDoomCompressor_v1.0.0

- **Type:** M4L User (CLX_02) — by geoffreyday
- **Load via:** `search_browser(path="audio_effects", name_filter="RawDoomCompressor")`
- **What it does:** Stripped-down DOOM compressor with hard-coded attack/release. Single-band extreme upward compressor designed as a building block for creating custom multiband doom compression chains. The raw, no-frills version.
- **Signal flow:** Input -> Hard-coded Envelope Detection -> Upward Normalization -> Floor Gate -> Output Level
- **Key parameters:**
  - **Dynamics Removed** -> intensifies compression amount -> higher = more extreme, can introduce distortion (non-mappable by design)
  - **Floor** (-200 dB to -30 dB) -> boost threshold -> signals below this are not amplified -> higher values create abrupt cutoff when source drops below threshold, effectively adding a gate
  - **Output** (0 dB to -30 dB) -> output volume control -> essential for taming the extreme levels
- **Reach for this when:** building custom multiband doom compression chains (use multiple instances with band-splitting), sound design where you need the simplest doom compressor as a building block, quick extreme upward compression without fiddling with attack/release
- **Don't use when:** you need adjustable timing (use doomCompressor), you want musical compression, you need multiband in a single device (use Squeeze)
- **Pairs well with:** EQ Eight before for band-splitting into multiple instances, Limiter after, Saturator before for harmonics to amplify
- **vs doomCompressor:** Raw has hard-coded timing (less control, but "tested for optimal doom compression"). doomCompressor has adjustable attack/release. Raw is simpler and better as a chain building block.

---

### Carver 1.2

- **Type:** M4L User (CLX_02) — by Noir Labs
- **Load via:** `search_browser(path="audio_effects", name_filter="Carver")`
- **What it does:** Advanced transient shaper with the most accurate real-time transient detection on the market. Shapes attacks and sustain without changing perceived volume. Features three curve types, M/S processing, and the unique ability to apply distortion only to the transient or only to the body of the sound. Shows detected transient in real-time waveform display.
- **Signal flow:** Input -> Transient Detection (with Sensitivity control) -> Attack/Sustain Shaping (with Curve selection) -> Distortion (routable to full/transient/body) -> Input/Output Clipping (anti-aliased) -> Output
- **Key parameters:**
  - **Attack** (-100 to +100) -> transient emphasis/reduction -> +50 for punchy drums, -30 for softer, smoother attacks
  - **Attack Length** (slider) -> defines how long the "transient" portion lasts -> short for snappy, long for more of the initial hit
  - **Sustain** (-100 to +100) -> tail emphasis/reduction -> +30 for fuller sound, -50 for tighter, gated feel
  - **Sustain Length** (slider) -> defines sustain window duration
  - **Presence** -> transient-driven high-frequency boost -> adds air and sparkle without static EQ
  - **Sensitivity** (0-100) -> detection sensitivity -> 100 captures even the quietest transients, lower values only process louder hits
  - **Curve Type:** Natural (smooth, transparent), Punchy (aggressive, more impact), Classic (traditional transient shaper behavior)
  - **Processing Mode:** Stereo, Mid/Side, Mid only, Side only
  - **Distortion Routing:** Full signal, Transient only, Body only -> unique creative control
- **Reach for this when:** detailed transient sculpting with visual feedback, M/S transient processing, adding punch without volume change, applying distortion only to attack portion, precise drum and loop shaping
- **Don't use when:** you need multiband transient control (use Impact), you want compression rather than transient shaping, simple one-knob processing (use Crack or Drum Buss transient knob)
- **Pairs well with:** Compressor after for dynamics control, EQ Eight for tonal shaping, Reverb (transient-shape before reverb for cleaner tails)
- **vs Crack:** Carver has curves, sensitivity, M/S, presence, distortion routing — much more detailed. Crack is simpler and faster. Carver for surgical work, Crack for utility.
- **vs Impact:** Impact is multiband with integrated EQ/saturation. Carver is single-band but with more transient detection options and distortion routing. Impact for drum buses, Carver for individual elements.

---

### Gain Rider

- **Type:** M4L User (CLX_02) — by John Darque
- **Load via:** `search_browser(path="audio_effects", name_filter="Gain Rider")`
- **What it does:** Automatic gain riding plugin that continuously adjusts volume to maintain a target level. Like having an assistant moving the fader in real-time. Unlike compression, it uses slower, more natural-sounding level adjustment — no attack/release artifacts, no transient modification. Just smooth, consistent level.
- **Signal flow:** Input -> Level Detection (LUFS or Peak) -> Calculate Compensation -> Apply Gain Adjustment -> Output
- **Key parameters:**
  - **Target** -> desired output level to ride toward
  - **Range** (6 dB to 24 dB) -> maximum gain adjustment range -> ±3 dB at 6 dB setting, ±12 dB at 24 dB -> start with 6-12 dB
  - **Threshold** -> ignore signals below this level (fader returns to 0 dB) -> prevents riding up noise floor during silence
  - **Speed** (ms) -> time to reach compensated values -> slow for transparent riding, fast for tighter control
  - **Mode:** LUFS (perceptual loudness, recommended for most uses) vs Peak (signal peaks)
  - **Rider Fader** -> visual feedback of current gain adjustment
- **Reach for this when:** vocal level consistency without compression artifacts, maintaining consistent dialog levels, smoothing out dynamic performances, gain staging before compression (even out levels first, then compress), any source with wide dynamic range that needs transparent leveling
- **Don't use when:** you need fast transient control (use Compressor), you want coloration/character (use Glue Compressor), the source is already consistent
- **Pairs well with:** Compressor after (Gain Rider first for leveling, then gentle compression for character), EQ Eight before for tonal prep, De-esser after for vocals
- **vs Compressor:** Gain Rider moves the fader slowly and naturally — no transient modification, no pumping, no artifacts. Compressor shapes dynamics faster but introduces its own character. Use Gain Rider BEFORE Compressor for best results on vocals.

---

### GMaudio Ducker 1.2

- **Type:** M4L User (CLX_02) — by Groov Mekanik / Fixation Studios
- **Load via:** `search_browser(path="audio_effects", name_filter="GMaudio Ducker")`
- **What it does:** Sample-accurate sidechain ducking tool specifically designed for bass/kick interaction. Uses transient detection (not traditional sidechain compression) to trigger an envelope that ducks bass during kick hits. Completely mutes bass during the kick transient for maximum clarity, then crossfades back. The precision tool for low-end management.
- **Signal flow:** Input (Bass) -> Transient Detection (from Kick via sidechain or self) -> Envelope Generation -> Volume Duck with Adjustable Curve -> Release Crossfade -> Output
- **Key parameters:**
  - **Attack Curve** -> fixed by design to prevent pops/clicks
  - **Release Curve** -> adjustable from logarithmic to exponential -> logarithmic for smooth bass return, exponential for tighter/snappier transitions
  - **Hold** -> duration of bass muting during kick transient
  - **Invert Signal** -> flips polarity of bass signal
  - **Scope** -> visual display with freeze, zoom, position controls
  - **Absolute Envelope Mode** -> visualizes combined envelope of both signals
- **Reach for this when:** kick/bass separation is the #1 problem, you need sample-accurate ducking (standard sidechain compression is too sloppy), the low end needs to be pristine and clear, electronic music with prominent kick and bass
- **Don't use when:** you need general sidechain compression (use Compressor sidechain), the bass and kick don't compete (no need), you want the pumping character of sidechain compression (Ducker is transparent)
- **Pairs well with:** EQ Eight on kick/bass for pre-shaping, Compressor on bass for additional dynamics, Glue Compressor on the combined bus after
- **Note:** Does not work nested inside Drum Racks (Ableton API limitation). Place on a regular track.
- **vs Compressor sidechain:** Ducker uses transient detection for sample-accurate timing. Compressor sidechain has inherent attack/release lag. Ducker for surgical precision, Compressor sidechain for musical pumping.

---

### GMaudio PentaComp 1.0

- **Type:** M4L User (CLX_02) — by Groov Mekanik / Fixation Studios
- **Load via:** `search_browser(path="audio_effects", name_filter="GMaudio PentaComp")`
- **What it does:** 5-band adaptive multiband compressor with 24 dB Linkwitz-Riley crossover network. Program-dependent algorithm automatically adjusts attack/release based on signal dynamics. Designed for transparent gain reduction across the full frequency spectrum. The precision multiband tool for mixing and mastering.
- **Signal flow:** Input -> 5-Band Linkwitz-Riley Crossover (160 Hz, 800 Hz, 4 kHz, 11 kHz) -> Per-Band Program-Dependent Compression -> Per-Band Output Gain -> Sum -> Output
- **Key parameters:**
  - **Input/Output** (linked control available) -> global gain staging
  - **Ratio** (per band) -> compression intensity per frequency range
  - **Speed Multiply** -> scales program-dependent attack/release -> lower = faster response, higher = slower/smoother
  - **Peak/RMS** -> detection method -> Peak for transient control, RMS for level averaging
  - **Band Linking** -> reduces phase artifacts between bands
  - **Stereo Linking** -> reduces stereo image steering from unequal compression
  - **Knee** -> 10 dB fixed soft knee on all bands -> always smooth, never harsh
  - **Metering:** green = input, red = gain reduction (simplified to save CPU)
- **Reach for this when:** multiband compression for mixing buses and mastering, you need more than 3 bands (vs Multiband Dynamics), transparent frequency balancing, taming resonances across the spectrum, demo mastering
- **Don't use when:** you need upward compression (use Squeeze or Multiband Dynamics), you need extreme OTT-style processing (use Multiband Dynamics), you need parallel processing (v1 limitation, v2 will fix)
- **Pairs well with:** EQ Eight before for surgical fixes, Limiter after for final peak control, Glue Compressor before for bus glue then PentaComp for frequency balance
- **vs Multiband Dynamics:** PentaComp has 5 bands (vs 3), Linkwitz-Riley crossovers (cleaner), program-dependent timing (less tweaking), but lacks upward compression. Multiband Dynamics has OTT/upward compression but only 3 bands with simpler crossovers. PentaComp for transparent mixing, Multiband Dynamics for creative processing.

---

### GMaudio Squeeze 1.1

- **Type:** M4L User (CLX_02) — by Groov Mekanik / Fixation Studios
- **Load via:** `search_browser(path="audio_effects", name_filter="GMaudio Squeeze")`
- **What it does:** Multiband upward compressor/limiter. Normalizes audio by dividing incoming signals by detected peak levels. Ranges from subtle loudness enhancement to complete sonic destruction. Uses 6 dB dynamic phase crossovers for in-phase parallel processing. The "detail enhancer" — reveals hidden textures and micro-dynamics in any source.
- **Signal flow:** Input -> 3-Band Split (6 dB crossovers at 300 Hz and 5 kHz) -> Per-Band Peak Detection -> Per-Band Upward Normalization (Floor to Ceiling) -> Style blending (single vs multiband) -> Mix (dry/wet) -> Output
- **Key parameters:**
  - **Floor** -> threshold below which signals are not processed -> prevents amplifying silence/noise -> set above noise floor
  - **Squeeze** -> amount of upward compression (ratio equivalent) -> 0 = none, max = extreme squashing
  - **Ceiling** -> target normalization level -> signals are pushed toward this level
  - **Style** -> morphs between single-band and multiband operation -> single-band for uniform processing, multiband for frequency-aware enhancement
  - **Time** -> compression window/release -> high = normalization (smooth), low = extreme upward compression (sausage)
  - **Mix** (0-100%) -> dry/wet blend -> 20-40% for subtle enhancement, 50-70% for obvious effect, 100% for destruction
- **Reach for this when:** revealing hidden details in sounds, enhancing time-based effects (reverb tails, delay feedback), sound design exploration, making virtual analog synths sound more alive, adding loudness and presence without traditional compression, DOOM-style processing but more controllable
- **Don't use when:** you need transparent level control (use Compressor), the source is already loud and dense, you want to preserve dynamics (this specifically destroys them in a controlled way)
- **Pairs well with:** Saturator/Distortion before (harmonics get amplified), Reverb/Delay before (tails become huge), Limiter or Clipper after (tame the output), should be LAST in the effects chain before limiting
- **vs Multiband Dynamics (OTT):** Both do multiband upward compression. Squeeze is simpler (6 controls vs many) and has in-phase crossovers for better parallel processing. OTT has per-band control and downward compression too. Squeeze for quick vibe, OTT for detailed control.
- **vs doomCompressor:** Both amplify quiet signals. Squeeze is multiband and more controllable. Doom is single-band and more extreme. Squeeze for musical enhancement, Doom for destruction.

---

### jL3v3ll3r v1.2

- **Type:** M4L User (CLX_02) — by jaspermarsalis (based on Dan Worrall's L3V3LL3R)
- **Load via:** `search_browser(path="audio_effects", name_filter="jL3v3ll3r")`
- **What it does:** Recreation of a rare 1960s "Leveller" compressor. A leveling amplifier that works nearly all the time — not just when a threshold is reached. Offers two distinct response curves: logarithmic (standard) and opto/vactrol (photo-resistor simulation). Produces smooth, musical compression with vintage character. The "always-on, always-smoothing" compressor.
- **Signal flow:** Input -> Highpass Filter (optional) -> Level Detection -> Response Curve (Log or Opto) -> Gain Reduction -> Output
- **Key parameters:**
  - **Compression Amount** -> how much leveling is applied
  - **Response Curve:** Logarithmic (standard mathematical compression, predictable) vs Opto/Vactrol (simulates photo-resistor behavior with nonlinear, program-dependent response — slower release on sustained signals, faster on transients)
  - **Highpass Filter** -> removes low frequencies from detection path -> prevents bass from triggering excessive compression (similar to sidechain HP on other compressors)
  - **Mode I** -> standard stereo compression
  - **Mode II** -> routes left channel into right channel (creative/experimental)
- **Reach for this when:** you want smooth, vintage-style leveling on vocals, bass, or full mixes; you want opto-style compression character; subtle "always-on" dynamics smoothing; the source needs to be evened out without aggressive pumping
- **Don't use when:** you need fast transient control (use Compressor with fast attack), you need precise ratio/threshold control (use Compressor), you need multiband processing
- **Pairs well with:** EQ Eight before for tonal prep, Compressor after for additional shaping, Gain Rider before for pre-leveling, Reverb after for vintage vocal chain
- **vs Compressor (RMS mode):** jL3v3ll3r is always compressing (leveling amplifier behavior) and has vintage character. Compressor only engages above threshold. jL3v3ll3r for vintage vibe, Compressor for precision.
- **vs LA2A:** Both are opto-style compressors. jL3v3ll3r is a native M4L implementation; LA2A is a wrapper for an external VST. jL3v3ll3r is simpler and more reliable.

---

### LA2A

- **Type:** M4L User (CLX_02) — by OspreyInstruments
- **Load via:** `search_browser(path="audio_effects", name_filter="LA2A")`
- **What it does:** M4L wrapper for the BPB Dirty LA optical compressor VST3 plugin. Emulates the classic Teletronix LA-2A leveling amplifier with its program-dependent opto compression behavior. Includes an approximate VU meter with realistic ballistics and deliberate harmonic distortion. Requires the free BPB Dirty LA plugin to be installed separately.
- **Signal flow:** Input -> BPB Dirty LA VST3 (opto compression + tube saturation) -> Approximate VU Metering -> Output
- **Key parameters:**
  - **Gain** -> output level / makeup gain (like the original LA-2A)
  - **Peak Reduction** -> compression amount (like the original LA-2A)
  - **Compress/Limit** mode switch -> Compress for gentle leveling, Limit for more aggressive peak control
  - **VU Meter** -> approximate, not scientifically precise — use as rough guide only
- **Reach for this when:** you specifically want LA-2A character (smooth opto compression with tube warmth), vocal processing that needs that "classic" sound, bass leveling with harmonic enhancement
- **Don't use when:** you don't have BPB Dirty LA installed (will not work), you need precise metering (VU is approximate), you need reliable cross-platform behavior (tested primarily on Mac)
- **Pairs well with:** EQ Eight before for pre-compression tonal shaping, Compressor after for additional peak control (LA-2A first for leveling, then surgical compression), De-esser before for vocals
- **vs jL3v3ll3r:** Both are opto-style compressors. LA2A requires external VST dependency; jL3v3ll3r is self-contained. LA2A has tube saturation character from the VST; jL3v3ll3r is cleaner. Use jL3v3ll3r for reliability, LA2A for the specific Dirty LA sound.
- **IMPORTANT:** Requires BPB Dirty LA VST3 installed from bedroomproducersblog.com. Mac-tested only.

---

### N-CLIP

- **Type:** M4L User (CLX_02) — by Nasko
- **Load via:** `search_browser(path="audio_effects", name_filter="N-CLIP")`
- **What it does:** Lightweight variable soft clipper with adjustable ceiling. Shaves off transient peaks using soft clipping rather than limiting — faster than a limiter, more transparent on transients, adds subtle harmonic content. The "invisible loudness" tool that lets you clip peaks before they hit a limiter, reducing the limiter's workload and preserving transient punch.
- **Signal flow:** Input -> Drive -> Soft Clipping at Ceiling Threshold (variable knee) -> Output
- **Key parameters:**
  - **Ceiling/Threshold** (+6 dB to -inf dB) -> sets the clipping point -> -1 to -0.5 dB for mastering chain before limiter, -3 dB for more aggressive clipping
  - **Soft Knee** (adjustable) -> controls how gradually clipping engages -> soft for transparent, hard for more aggressive harmonic content
  - **Drive** (-32 dB to +32 dB, bipolar) -> input gain before clipping -> positive for louder into clipper, negative for gentler clipping
- **Reach for this when:** pre-limiter clipping to reduce limiter workload, getting extra loudness without limiter pumping, taming drum transients transparently (clipping is faster than limiting), mixing into a clipper for "hot" mixes
- **Don't use when:** you need True Peak compliance (clipping can create inter-sample peaks), you want completely clean/transparent processing, the source has no transient peaks to clip
- **Pairs well with:** Limiter after (clip peaks first, then limit — less work for the limiter = cleaner result), Compressor before for dynamics shaping, Drum Buss before for combined processing
- **vs Limiter:** Clipper is instantaneous (zero attack); Limiter has lookahead and shaped release. Clipper adds harmonics; Limiter is transparent. Use clipper BEFORE limiter in mastering chain for best results.
- **vs Color Limiter:** Both add harmonic character. N-CLIP is a pure clipper; Color Limiter is a full limiter with saturation. N-CLIP for transparent peak shaving, Color Limiter for characterful limiting.

---

### Thomash Amplitude Receiver/Sender

- **Type:** M4L User (CLX_02) — by voodoohop (thomash)
- **Load via:** `search_browser(path="audio_effects", name_filter="Thomash Amplitude")` (load both Sender and Receiver)
- **What it does:** Two-device system that preserves the original amplitude envelope across an effects chain. The Sender captures the volume at one point; the Receiver (placed downstream after effects) adjusts gain to match the original level. Eliminates volume changes caused by effects — you can process audio through filters, delays, and EQs while maintaining the original dynamics. Like having an automatic "undo" for volume changes from effects.
- **Signal flow:** [Sender captures level] -> Effects Chain (any number of effects) -> [Receiver restores original level with 512-sample latency]
- **Key parameters:**
  - **Channel ID** (both devices) -> must match between Sender and Receiver pairs -> unique per instance
  - **Latency:** Fixed 512 samples — the Receiver anticipates by receiving events 512 samples early
- **Reach for this when:** you want to apply heavy EQ/filter processing without volume changes, maintaining vocal dynamics through a complex effects chain, ensuring reverb/delay effects don't change the overall level, any time you want "the effect but not the volume change"
- **Don't use when:** you WANT the volume changes from effects (most of the time, level changes are part of the effect's character), the 512-sample latency is unacceptable, you need to use it with other M4L devices in the chain (only works reliably with native Ableton effects)
- **Pairs well with:** Any native Ableton effects between the Sender and Receiver — EQ Eight, Auto Filter, delays, reverbs
- **IMPORTANT:** Only works with native Ableton effects. Does NOT work reliably with other M4L devices in between. Requires unique Channel IDs when using multiple instances.

---

## Quick Decision Matrix

| Scenario | First Choice | Why | Second Choice |
|---|---|---|---|
| **Bus glue (drums, music, master)** | Glue Compressor | SSL character, musical fixed steps, Soft Clip | Compressor (Dry/Wet for parallel) |
| **Surgical single-track compression** | Compressor | Maximum flexibility, all modes | jL3v3ll3r (if vintage leveling wanted) |
| **Drum group instant punch** | Drum Buss | All-in-one: comp + saturation + transients + boom | Impact (if multiband transient control needed) |
| **Transient shaping (single element)** | Carver 1.2 | Precise detection, curves, M/S, distortion routing | Crack (simpler, faster) |
| **Transient shaping (drum bus)** | Impact | Multiband, EQ, saturation, output stage | Drum Buss (simpler, more coloration) |
| **Kick/bass separation** | GMaudio Ducker | Sample-accurate ducking, purpose-built | Compressor sidechain (if pumping character wanted) |
| **Multiband compression (mixing)** | PentaComp | 5 bands, Linkwitz-Riley, program-dependent | Multiband Dynamics (if 3 bands sufficient) |
| **Multiband compression (creative/OTT)** | Multiband Dynamics | OTT preset, upward+downward, per-band control | Squeeze (simpler, more extreme) |
| **Upward compression (detail reveal)** | GMaudio Squeeze | Multiband, controllable, musical range | Multiband Dynamics Below threshold |
| **Extreme upward compression (destruction)** | doomCompressor | Infinite upward ratio, adjustable timing | RawDoomCompressor (simpler, hard-coded) |
| **Vocal leveling (transparent)** | Gain Rider | No transient artifacts, LUFS mode, natural | jL3v3ll3r (if vintage character wanted) |
| **Vintage opto compression** | jL3v3ll3r | Self-contained, vactrol curve, reliable | LA2A (if BPB Dirty LA installed, tube character) |
| **Pre-limiter peak clipping** | N-CLIP | Fast, transparent, adjustable knee | Color Limiter (if saturation character wanted) |
| **Mastering limiter (transparent)** | Limiter | True Peak, Maximize, clinical precision | Glue Compressor -> Limiter chain |
| **Mastering limiter (colored)** | Color Limiter | Saturation + Color parameters, vintage vibe | Limiter in Soft Clip mode (12.1+) |
| **Noise/bleed cleanup** | Gate | Purpose-built, sidechain EQ, Flip mode | Re-Enveloper (if frequency-selective needed) |
| **Envelope reshaping (creative)** | Re-Enveloper | Multiband C/E factor, beyond gating | Multiband Dynamics (if ratio-based control preferred) |
| **Preserve dynamics through FX chain** | Thomash Amplitude Sender/Receiver | Automatic level restoration, 512-sample latency | Utility (manual gain compensation) |
| **Sidechain pumping (musical)** | Compressor (sidechain) | Classic pump, adjustable attack/release/ratio | Glue Compressor sidechain (SSL pump character) |
| **Loudness maximizing** | Limiter (Maximize mode) | Single-knob loudness, True Peak safe | N-CLIP -> Limiter chain (clip then limit) |

---

## Signal Chain Recipes

**Clean Mastering Chain:**
EQ Eight -> Glue Compressor (gentle bus glue) -> N-CLIP (peak shaving) -> Limiter (True Peak, Ceiling -1 dB)

**Aggressive Drum Bus:**
Drum Buss (Comp ON, Medium distortion, Transients +40, Boom 30%) -> Glue Compressor (4:1, Soft Clip ON)

**Vocal Chain (Natural):**
Gain Rider (LUFS, 12 dB range) -> Compressor (RMS, 3:1, 10 ms attack, 50 ms release) -> EQ Eight

**Vocal Chain (Vintage):**
jL3v3ll3r (Opto mode) -> Compressor (gentle 2:1) -> Color Limiter (subtle Saturation)

**Sound Design (Extreme):**
Reverb -> doomCompressor -> Saturator -> Limiter

**Electronic Low-End (Kick + Bass):**
GMaudio Ducker on Bass track (sidechained to Kick) -> Compressor on Bass -> Glue Compressor on Low-End Bus

**Detail Enhancement:**
GMaudio Squeeze (Style multiband, Squeeze 50%, Time medium, Mix 30-50%) -> Limiter

**Drum Transient Sculpting:**
Carver (Punchy curve, Attack +50, Sensitivity 80) -> Compressor (fast attack to catch shaped transients) -> N-CLIP

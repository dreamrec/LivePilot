# Distortion & Character Devices — Deep Reference

Complete sonic atlas for every distortion, saturation, and coloration device available in this Ableton Live 12 installation. Covers native effects, stock M4L (Creative Extensions), user M4L (CLX_02 collection), and the Encoder Audio Mojo IR library.

---

## Native Ableton Devices

---

### Saturator

- **Type:** Native (all editions)
- **Load via:** `find_and_load_device("Saturator")`
- **What it does:** General-purpose waveshaping distortion. Pushes audio through a transfer curve that reshapes the waveform, adding harmonics. Ranges from imperceptible warmth to aggressive folding distortion depending on curve and drive. The most versatile single distortion device in Live.

- **Signal flow:** Input -> Drive (gain stage) -> Waveshaper (selected curve) -> Color section (2-band post-EQ) -> Soft Clip (optional) -> Output gain -> Dry/Wet mix

- **Key parameters:**
  - `Drive` (dB) -> Input gain into the waveshaper. 0 dB = unity, gentle coloring starts around 3-6 dB, obvious distortion at 12+ dB. **Sweet spot: 3-10 dB** for warmth, 15-24 dB for aggressive.
  - `Type` (curve selector) -> The waveshaping transfer function:
    - **Analog Clip** -> Soft-knee clipping that mimics analog tape/console saturation. Adds mostly odd harmonics, warm and musical. Best all-rounder. **Reach for this first.**
    - **Soft Sine** -> Gentlest curve. Rounds peaks very subtly, adds minimal harmonics. Barely audible at low drive. Good for transparent loudness on master bus. **Sweet spot: Drive 5-10 dB.**
    - **Medium Curve** -> Moderate saturation, balanced harmonic content. Between Soft Sine and Hard Curve in aggressiveness.
    - **Hard Curve** -> Aggressive clipping with sharper knee. More upper harmonics, more audible distortion at same drive levels. Good for bass and drums that need bite.
    - **Sinoid Fold** -> Wavefolder that wraps the signal back on itself instead of clipping. Creates dense, inharmonic, almost metallic upper harmonics. **Unique and wild.** Low drive = subtle shimmer; high drive = aggressive ring-mod-like textures. **Sweet spot: Drive 3-8 dB for shimmer, 15+ dB for destruction.**
    - **Digital Clip** -> Hard digital clipping at 0 dBFS. Harsh, square-wave-like distortion at high drives. Adds strong odd harmonics. Use deliberately for lo-fi or aggressive digital destruction.
  - `Color` (on/off toggle) -> Enables the 2-band post-shaper EQ.
  - `Base` (-inf to +inf) -> Bass boost/cut after the waveshaper. Positive values add low-end warmth.
  - `Width` (Hz) -> Controls the bandwidth of the Color EQ. Narrower = more surgical, wider = broader tonal shift.
  - `Depth` -> Depth of the Color effect. Controls how much the color EQ affects the sound.
  - `Output` (dB) -> Post-saturation gain trim. Essential for gain-matching (distortion adds perceived loudness). **Always compensate: if Drive is +10 dB, Output should be roughly -6 to -10 dB.**
  - `Soft Clip` (on/off) -> Additional gentle clipping stage after Output. Prevents harsh overs. **Leave on for bus/master use.**
  - `Dry/Wet` (%) -> Parallel blend. **Sweet spot: 30-60%** for transparent warmth. 100% for full effect.

- **Presets:** "A Bit Warmer" (subtle analog clip), "Bass Boost" (drive + bass color), "Burn It Down" (high drive sinoid fold), "Warm Up Sines" (gentle soft sine for synths)

- **Reach for this when:** "Add some warmth," "make it warmer," "saturate the bus," "add harmonics," "fatten the bass," "make it thicker," "analog character," "tape-like warmth." Saturator is the Swiss Army knife -- if unsure which distortion to use, start here.

- **Don't use when:** You need guitar-amp realism (use Pedal/Amp instead), you want multi-stage/feedback distortion (use Roar), you need sample-rate reduction/bitcrushing (use Redux), or you need vinyl-specific artifacts (use Vinyl Distortion).

- **Pairs well with:** EQ Eight before (shape what gets distorted), Compressor after (tame transients that distortion makes louder), Utility after (gain match), Glue Compressor on the same bus. Saturator into Auto Filter is a classic for moving distortion tones.

- **vs Overdrive:** Saturator is more transparent and controllable. Overdrive has a built-in bandpass that colors the tone more -- better for guitar/bass, worse for transparent bus saturation.
- **vs Roar:** Saturator is simpler, one-stage, zero-feedback. Roar is a full distortion synthesizer with routing, feedback, and modulation. Use Saturator for quick warmth, Roar for complex distortion design.
- **vs Dynamic Tube:** Dynamic Tube responds to input dynamics (louder = more distortion). Saturator is static. Dynamic Tube is better for material with wide dynamic range where you want distortion to breathe.

---

### Overdrive

- **Type:** Native (all editions)
- **Load via:** `find_and_load_device("Overdrive")`
- **What it does:** Warm overdrive effect with a built-in bandpass filter that shapes the frequency range being distorted. Models the behavior of a guitar overdrive pedal: the bandpass focuses the distortion on the mids, preventing fizzy highs and muddy lows. Less versatile than Saturator but more immediately musical on guitars, bass, and keys.

- **Signal flow:** Input -> Bandpass Filter (pre-distortion frequency focus) -> Distortion stage -> Tone control (post-distortion brightness) -> Dynamics control -> Output -> Dry/Wet

- **Key parameters:**
  - `Filter` (Hz) -> Center frequency of the pre-distortion bandpass. Determines which frequencies get distorted most. Low values (~200-400 Hz) = warm, tubby. Mid values (~800-2 kHz) = honky, guitar-like. High values (~3-6 kHz) = bright, cutting. **Sweet spot: 500-2000 Hz.**
  - `Width` (%) -> Bandwidth of the bandpass. Narrow = focused, nasal. Wide = more of the frequency spectrum gets distorted. **Sweet spot: 40-70%.**
  - `Drive` (%) -> Amount of distortion. 0% still has some coloration. **Sweet spot: 20-50%** for warmth, 60-90% for obvious distortion, 100% for full crunch.
  - `Tone` (%) -> Post-distortion brightness. 0% = dark, muffled. 100% = bright, cutting, potentially harsh. **Sweet spot: 40-65%.**
  - `Dynamics` (%) -> How much the distortion responds to input level. 0% = heavily compressed (consistent distortion). 100% = dynamic (soft passages stay cleaner, loud passages distort more). **Sweet spot: 50-80%** for musical response.
  - `Dry/Wet` (%) -> Parallel blend.

- **Presets:** Fewer presets than Saturator. "Blues" (moderate drive, mid-focused), "Crunch" (higher drive, wider band), "Funk Bass" (low filter, tight width).

- **Reach for this when:** "Guitar-style warmth," "tube overdrive," "gritty bass," "mid-range crunch," "warm up the keys," "add some grit." Especially when you want distortion focused on the mids without touching the lows or highs.

- **Don't use when:** You need transparent full-bandwidth saturation (use Saturator), you need high-gain distortion (use Pedal or Amp), or you need frequency-specific processing (use Roar multiband mode).

- **Pairs well with:** Cabinet after (adds speaker coloration for amp-like tone), Auto Filter before (shape the input), EQ Eight after (clean up any harshness). Bass -> Overdrive -> Cabinet is a classic tone chain.

- **vs Saturator:** Overdrive is a character effect with a built-in bandpass that shapes the tone. Saturator is more neutral/transparent. Overdrive on bass guitar; Saturator on a drum bus.
- **vs Pedal:** Pedal is more aggressive with three distinct voicings. Overdrive is subtler and more focused. Pedal replaces Overdrive when you need more gain.

---

### Erosion

- **Type:** Native (all editions)
- **Load via:** `find_and_load_device("Erosion")`
- **What it does:** Digital degradation effect. Modulates the audio signal with noise or a sine wave to create aliasing, digital artifacts, and high-frequency grit. Unlike analog-modeled distortion, Erosion sounds intentionally digital and broken. It creates artifacts that don't exist in the analog domain -- frequency-shifted noise clouds, aliasing products, digital "fuzz."

- **Signal flow:** Input signal is ring-modulated/multiplied with a noise source or sine oscillator, creating sum-and-difference frequencies (aliasing artifacts). The result is mixed with the dry signal.

- **Key parameters:**
  - `Mode` selector:
    - **Wide Noise** -> Broadband noise modulation, stereo. Creates a washy, degraded character across the spectrum. Sounds like playing through a broken radio or degraded digital connection.
    - **Noise** -> Mono noise modulation. Similar to Wide Noise but centered. More focused degradation.
    - **Sine** -> Single sine oscillator modulation. Creates specific aliasing frequencies related to the Frequency parameter. More tonal/pitched artifacts. At low frequencies, creates tremolo-like effects; at high frequencies, creates metallic ring-mod artifacts.
  - `Frequency` (Hz) -> Center frequency of the noise band or pitch of the sine modulator. In Noise modes, determines where the degradation is focused. In Sine mode, sets the modulation frequency. **Sweet spot: 2-6 kHz for subtle digital haze, 500-1500 Hz for obvious degradation.**
  - `Amount` (%) -> Intensity of the effect. Low values = subtle digital sheen. High values = heavily degraded. **Sweet spot: 5-20%** for subtle texture, 40-80% for obvious lo-fi.
  - `Width` -> Bandwidth/spread of the noise modulation. Wider = more frequencies affected.

- **Reach for this when:** "Lo-fi digital," "make it sound broken," "add digital artifacts," "8-bit texture," "radio interference," "glitchy," "corrupted signal." Erosion is the go-to when you want something to sound like it's coming through a degraded digital channel.

- **Don't use when:** You want warm/analog distortion (use Saturator), you want musical overdrive (use Overdrive/Pedal), or you're working on the master bus (Erosion is rarely subtle enough for mastering).

- **Pairs well with:** Redux (double down on digital destruction), Auto Filter (filter the artifacts for rhythmic lo-fi), Beat Repeat (glitch + degradation), Reverb after (diffuse the artifacts into atmosphere).

- **vs Redux:** Redux does sample-rate and bit-depth reduction (quantization). Erosion does frequency-domain degradation (modulation/aliasing). They create different types of digital artifacts and combine well together.
- **vs Vinyl Distortion:** Vinyl Distortion emulates analog vinyl artifacts. Erosion creates purely digital artifacts. Opposite ends of the lo-fi spectrum.

---

### Redux

- **Type:** Native (all editions, updated in Live 12)
- **Load via:** `find_and_load_device("Redux")`
- **What it does:** Bit crusher and sample rate reducer. Reduces the bit depth (fewer amplitude steps = quantization noise) and/or sample rate (fewer samples per second = aliasing) of the audio signal. The Live 12 update added new filter modes, jitter controls, and a modernized interface that makes it significantly more musical than the old version.

- **Signal flow:** Input -> Downsample (sample rate reduction with selectable filter/interpolation) -> Bit Reduction (bit depth quantization) -> Output

- **Key parameters (Live 12 version):**
  - `Downsample` -> Sample rate reduction factor. 1x = no reduction. Higher values = more aliasing and lower fidelity. **Sweet spot: 2-8x for lo-fi flavor, 20-50x for extreme retro/8-bit.**
  - `Downsample Mode` -> How the resampling is performed:
    - **Soft** -> Interpolated, smoother aliasing. More musical.
    - **Hard** -> Zero-order hold, classic staircase. Harsher, more obviously digital.
  - `Bit Depth` -> Number of bits. 16 = CD quality (no audible effect). 8 = retro console. 4 = very crunchy. 1 = square wave. **Sweet spot: 6-10 bits for character, 2-4 bits for extreme.**
  - `Jitter` -> Adds randomness to the bit reduction. Makes the quantization noise less uniform and more organic. Higher values = noisier, more unpredictable. **New in Live 12.**
  - `Filter` section (new in Live 12) -> Post-processing filter to shape the artifacts:
    - Various filter types to tame or shape the aliasing products
    - Useful for making extreme settings more usable in a mix
  - `Dry/Wet` (%) -> Parallel blend. **Sweet spot: 20-50%** for subtle retro character, 100% for full effect.

- **Reach for this when:** "8-bit," "retro," "lo-fi," "chiptune," "degrade it," "sample rate reduction," "bit crush," "make it sound old," "NES/Game Boy sound." Also useful at subtle settings for adding grit to drums.

- **Don't use when:** You want warm analog saturation (use Saturator), you want frequency-domain artifacts (use Erosion), or you're processing vocals that need to remain intelligible (bitcrushing destroys formant detail quickly).

- **Pairs well with:** Erosion (different digital degradation flavors stack well), Auto Filter after (filter the aliasing), Saturator before (drive into the bitcrusher for more harmonics to crush), Pedal Fuzz mode (fuzz + bitcrush = extreme).

- **vs Erosion:** Redux works in the time/amplitude domain (fewer samples, fewer bits). Erosion works in the frequency domain (noise/sine modulation). Both are "digital degradation" but sound very different. Use both together for maximum destruction.
- **vs Roar's Bit Crush shaper:** Roar can bitcrush within its multi-stage architecture with feedback. Redux is simpler but has the dedicated filter section and jitter that Roar's bitcrush shaper lacks.

---

### Pedal

- **Type:** Native (Standard/Suite, or as add-on)
- **Load via:** `find_and_load_device("Pedal")`
- **What it does:** Guitar pedal emulation with three distinct distortion voicings. Designed to feel like stepping on a real stompbox. Each mode models a different class of guitar pedal circuit. More aggressive than Overdrive, more focused than Saturator, with a musical 3-band EQ.

- **Signal flow:** Input -> Sub switch (optional low shelf boost) -> Gain stage (mode-dependent clipping circuit) -> 3-band EQ (Bass/Mid/Treble) -> Output gain -> Dry/Wet

- **Key parameters:**
  - `Mode` selector:
    - **OD (Overdrive)** -> Warm, smooth, touch-responsive. Models a Tube Screamer-style circuit with soft clipping. Low-gain, mid-forward character. Good for blues, indie, adding edge. **The gentlest mode.**
    - **Dist (Distortion)** -> Tight, aggressive, compressed. Models a hard-clipping distortion pedal (think Boss DS-1 or ProCo RAT style). More gain, more sustain, tighter low end. Good for rock, punk, aggressive synths. **The workhorse mode.**
    - **Fuzz** -> Unstable, broken-amp character. Models vintage fuzz circuits (think Fuzz Face or Big Muff). Sputtery, gated, thick. Cleans up at low gain, explodes at high gain. Interacts with input level dynamically. **The wildest mode.**
  - `Gain` (%) -> Distortion amount. Even at 0% there is some inherent coloration. **Sweet spot: OD 30-60%, Dist 40-70%, Fuzz 50-90%.**
  - `Output` (dB) -> Master volume. Use to gain-match. Distortion adds a lot of perceived loudness.
  - `Bass` -> Peak EQ at 100 Hz. Boost for punch, cut to tighten.
  - `Mid` -> Three-way switchable mid EQ with adjustable frequency. The mid control is key to Pedal's character. Boost for presence and cut-through, scoop for modern metal tone.
  - `Treble` -> Shelving EQ at 3.3 kHz. Cut to tame fizz, boost for brightness.
  - `Sub` (on/off) -> Low shelf boost below 250 Hz. Adds bass weight. **Useful on bass guitar, heavy on kicks.**
  - `Dry/Wet` (%) -> Parallel blend.

- **Presets:** Each mode has tailored presets. "Blues Driver" (OD, moderate gain), "Classic Fuzz" (Fuzz, mid gain), "Wall of Sound" (Dist, high gain).

- **Reach for this when:** "Guitar pedal sound," "stomp box," "fuzz," "crunch," "heavy distortion," "broken amp," "make it fuzzy," "add some dirt." Pedal is the best choice when you want the feel of a real pedalboard.

- **Don't use when:** You need transparent saturation (use Saturator), you need complex multi-stage distortion (use Roar), or you need amp/cabinet modeling (add Amp + Cabinet after Pedal).

- **Pairs well with:** Amp + Cabinet after (full guitar rig), Compressor before (consistent input = consistent distortion), Auto Filter before (wah pedal -> distortion), EQ Eight after (surgical cleanup).

- **vs Overdrive:** Pedal's OD mode is similar to Overdrive but with a better EQ section. Pedal's Dist and Fuzz modes go much further than Overdrive can. Pedal replaces Overdrive in most guitar scenarios.
- **vs Amp:** Pedal is a stompbox (pre-amp distortion). Amp is an amplifier model. In a real guitar rig, the pedal comes before the amp. Same in Live: Pedal -> Amp -> Cabinet.

---

### Amp

- **Type:** Native (Standard/Suite, or as add-on, developed with Softube)
- **Load via:** `find_and_load_device("Amp")`
- **What it does:** Physical modeling of seven classic guitar amplifier circuits. Each model captures the nonlinear behavior, EQ voicing, and breakup character of a real amp. Unlike Pedal (which is a pre-amp stompbox), Amp models the full amplifier including preamp gain stage, tone stack, and power amp saturation.

- **Signal flow:** Input -> Gain (preamp drive) -> Tone Stack (Bass/Middle/Treble - interactive like real amps) -> Power Amp (Volume - controls power amp saturation) -> Presence (post-power-amp HF control) -> Output -> Dry/Wet

- **Seven amp models:**
  - **Clean** -> Based on the "Brilliant" channel of a 1960s Vox AC30. Chimey, glassy, jangly clean tones with subtle harmonic richness. British Invasion, indie, jazz. Breaks up gently at high gain.
  - **Boost** -> Based on the "Tremolo" channel of the same AC30. Slightly more driven than Clean, edgier. Good for punchy rhythm guitar.
  - **Blues** -> Based on a 1970s Fender Twin Reverb-style amp. Bright, scooped mids, lots of headroom. Classic American clean-to-crunch. Country, blues, classic rock.
  - **Rock** -> Based on a 1960s Marshall JTM45/Plexi. The most iconic rock amp tone: mid-forward, crunchy, harmonically rich. Responds beautifully to playing dynamics.
  - **Lead** -> Based on the "Modern" channel of a Mesa Boogie Dual/Triple Rectifier. High gain, tight, scooped. Metal, hard rock. Lots of sustain.
  - **Heavy** -> Based on the "Vintage" channel of the same Rectifier. Looser, darker, more sludgy than Lead. Metal, grunge, stoner rock.
  - **Bass** -> Based on a rare 1970s Hiwatt-style PA head. Strong low end, natural fuzz at high volumes. Purpose-built for bass guitar but also great for synths that need weight.

- **Key parameters:**
  - `Gain` -> Preamp drive. Controls how hard the preamp is driven. Low = clean, high = distorted. The character of the distortion depends entirely on the selected model. **Sweet spot: varies by model. Clean/Blues 30-60%, Rock 40-70%, Lead/Heavy 50-80%.**
  - `Bass` -> Low-frequency EQ in the tone stack. Note: amp tone stacks are interactive -- changing Bass affects Mid and Treble perception.
  - `Middle` -> Mid-frequency EQ. The most important tone control for guitar. Boost for presence, cut for "scooped" modern metal.
  - `Treble` -> High-frequency EQ. Boost for sparkle and cut, reduce to tame fizz.
  - `Volume` -> Power amp level. In real amps, cranking the volume drives the power amp into saturation, adding compression and harmonics even at low preamp gain. **Key insight: Gain controls distortion character, Volume controls power amp fatness.**
  - `Presence` -> Post-power-amp high-frequency control. Affects the very top end differently from Treble. Adds air and definition.
  - `Bright` (on/off) -> Presence boost switch. Adds a high-frequency emphasis before the gain stage.
  - `Output` -> Master output level.
  - `Dry/Wet` (%) -> Parallel blend.

- **Reach for this when:** "Guitar amp," "amp simulation," "amp modeling," "rock tone," "clean guitar," "metal guitar," "bass amp." Always pair with Cabinet for realistic results.

- **Don't use when:** You want subtle saturation on non-guitar material (use Saturator), you want standalone distortion without amp modeling (use Pedal or Saturator), or you're processing a full mix (Amp is designed for individual instruments).

- **Pairs well with:** **Cabinet after (essential -- Amp without Cabinet sounds harsh and unrealistic)**, Pedal before (stompbox into amp), EQ Eight before (input shaping), Compressor after (tame dynamics), Delay/Reverb after Cabinet (effects loop). The canonical chain: Pedal -> Amp -> Cabinet -> EQ Eight -> Delay/Reverb.

- **vs Pedal:** Pedal is a stompbox. Amp is an amplifier. They serve different roles and work best together. Pedal colors the signal, Amp amplifies and shapes it.

---

### Cabinet

- **Type:** Native (Standard/Suite, or as add-on, developed with Softube)
- **Load via:** `find_and_load_device("Cabinet")`
- **What it does:** Convolution-based speaker cabinet emulation. Models the frequency response and resonance of classic guitar/bass speaker cabinets with selectable virtual microphones and mic positions. Transforms the raw, harsh output of Amp into a natural, speaker-shaped tone. Essential companion to Amp.

- **Signal flow:** Input -> Cabinet impulse response (convolution) -> Microphone model -> Mic Position -> Output -> Dry/Wet

- **Key parameters:**
  - `Speaker` -> Cabinet model selector:
    - **1x12** -> Small combo cabinet. Tight, focused, mid-forward. Good for blues, jazz, recording tones.
    - **2x12** -> Medium cabinet. Balanced, wider, good all-rounder.
    - **4x10** -> Four 10-inch speakers. Punchy, focused mids, classic bass amp or vintage rock sound (Fender Bassman style).
    - **4x12** -> Classic rock/metal full stack. Wide, powerful, full frequency range. The default for heavy tones.
    - **4x12 Bass** -> Optimized for bass guitar. Extended low end, controlled highs.
  - `Microphone` -> Virtual mic type:
    - **Dynamic** -> Shure SM57-style. Tight, mid-forward, rejects bleed. The studio standard for guitar cabs.
    - **Condenser** -> Brighter, wider frequency response, more detail and air. More hi-fi.
    - **Ribbon** -> Warm, smooth, rolled-off top end. Vintage character.
  - `Mic Position` (Near/Far) -> Simulates mic distance from the speaker cone. **Near** (on-axis) = brighter, more direct, more proximity effect. **Far** (off-axis) = darker, more room, smoother.
  - `Output` -> Level control.
  - `Dry/Wet` (%) -> Parallel blend. Usually 100% when used with Amp.

- **Reach for this when:** Using Amp (always), after Pedal for speaker coloration, after any distortion to "warm" and "round" the harsh edges, for lo-fi speaker simulation (1x12 with far mic position).

- **Don't use when:** You want clean, transparent processing. Cabinet always adds coloration.

- **Pairs well with:** Amp before (essential pairing), Pedal before, any distortion device before. EQ Eight after to fine-tune the cab-shaped tone.

---

### Dynamic Tube

- **Type:** Native (Standard/Suite)
- **Load via:** `find_and_load_device("Dynamic Tube")`
- **What it does:** Tube saturation with an input-following envelope. The distortion amount responds dynamically to the signal level -- louder passages get more saturation, quiet passages stay cleaner. This mimics how real tube circuits behave: they saturate progressively as the signal increases. Three tube models offer different saturation colors.

- **Signal flow:** Input -> Envelope Follower (detects input level) -> Tube saturation stage (model-dependent, amount modulated by envelope) -> Tone control -> Output -> Dry/Wet

- **Key parameters:**
  - `Tube` model selector:
    - **A** -> Clean tube. Least distortion, most transparent. Adds subtle even harmonics. Best for gentle warming on buses and vocals.
    - **B** -> Medium tube. More obvious saturation, mid-focused harmonic generation. General-purpose tube character.
    - **C** -> Aggressive tube. Most distortion, brightest character. Good for screaming leads, aggressive bass.
  - `Drive` -> Base saturation amount before envelope modulation. Sets the minimum distortion level.
  - `Bias` -> DC offset control. Shifts the signal's operating point on the tube's transfer curve. At extreme settings creates asymmetric distortion (adds even harmonics). Subtle at center, increasingly colored toward extremes. **Sweet spot: slight offset (+/- 0.1-0.3) for warmth.**
  - `Envelope` -> How much the envelope follower modulates the tube drive. Positive values = louder input = more distortion. Negative values = louder input = less distortion (ducking saturation). **Sweet spot: 20-50% for natural tube response.**
  - `Attack` -> Envelope follower attack time. Fast = responsive to transients. Slow = smoothed, average-level following.
  - `Release` -> Envelope follower release time.
  - `Tone` -> Post-saturation brightness control.
  - `Output` -> Level trim.
  - `Dry/Wet` (%) -> Parallel blend.

- **Reach for this when:** "Tube warmth," "tube saturation," "dynamic distortion," "make it breathe," "responsive saturation," "tube preamp." Best when you want the distortion to follow the music's energy -- more grit on loud notes, cleaner on quiet passages.

- **Don't use when:** You want consistent, static distortion (use Saturator), you want digital artifacts (use Erosion/Redux), or you need amp modeling (use Amp).

- **Pairs well with:** Compressor before (controls the dynamic range feeding the tube), EQ Eight after (shape the tube's harmonic output), Utility after (gain match). On vocals: Compressor -> Dynamic Tube (A) -> EQ Eight is a classic warmth chain.

- **vs Saturator:** Saturator is static -- same distortion regardless of input level. Dynamic Tube responds to dynamics. Dynamic Tube is more musical on expressive material (vocals, live instruments). Saturator is more predictable on programmed material (drums, synths).
- **vs Amp:** Both model tubes, but Amp models a complete guitar amplifier with tone stack and power amp. Dynamic Tube is a pure tube saturation stage with envelope following. Use Amp for guitar, Dynamic Tube for everything else that needs tube character.

---

### Vinyl Distortion

- **Type:** Native (Standard/Suite)
- **Load via:** `find_and_load_device("Vinyl Distortion")`
- **What it does:** Emulates the physical artifacts of vinyl record playback. Two independent distortion models (Tracing and Pinch) simulate different aspects of needle-on-groove behavior, plus a Crackle generator for surface noise. Creates that "sampled from vinyl" character heard in lo-fi hip-hop, downtempo, and sample-based production.

- **Signal flow:** Input -> Tracing Model (simulates needle tracking distortion) + Pinch Effect (simulates pinch distortion) -> Crackle generator (added noise) -> Output -> Dry/Wet

- **Key parameters:**
  - `Tracing Model`:
    - `Drive` -> Amount of tracing distortion. Simulates the nonlinear distortion caused by the stylus tracing the groove. Adds even harmonics, soft, warm distortion that increases with frequency. **Sweet spot: 20-50% for subtle vinyl warmth.**
    - `Freq` (Hz) -> Tracing model frequency. Controls where the tracing distortion is most prominent.
    - `Tracking` -> Controls the tracking behavior.
  - `Pinch Effect`:
    - `Drive` -> Amount of pinch distortion. Simulates the "pinch effect" where the stylus is squeezed between groove walls, creating odd harmonics. More aggressive than tracing. Creates a mid-range growl.
    - `Freq` (Hz) -> Pinch frequency focus.
    - `Width` -> Stereo width of the pinch effect.
  - `Crackle`:
    - `Volume` -> Amount of vinyl surface noise. Adds pops, clicks, and continuous surface hiss. **Sweet spot: 5-15%** for subtle atmosphere, 30-50% for obvious vinyl character.
    - `Density` -> How frequent the crackle events are.
  - `Dry/Wet` (%) -> Parallel blend.

- **Reach for this when:** "Vinyl sound," "lo-fi hip-hop," "sampled-from-vinyl character," "add crackle," "make it sound like a record," "vinyl warmth." The definitive vinyl emulation in Live.

- **Don't use when:** You want clean transparent saturation (use Saturator), you want digital lo-fi (use Erosion/Redux), or you need distortion for live instruments (use Overdrive/Pedal).

- **Pairs well with:** Redux (vinyl + bitcrush = ultimate lo-fi), Auto Filter (LP filter for "through a speaker" effect), EQ Eight (roll off highs to enhance the vintage feel), Utility (Bass Mono to mimic vinyl's mono bass).

- **vs Erosion:** Erosion is digital degradation. Vinyl Distortion is analog vinyl emulation. Opposite aesthetic approaches to lo-fi.

---

### Roar

- **Type:** Native (Live 12 add-on, EUR 99)
- **Load via:** `find_and_load_device("Roar")`
- **What it does:** Live 12's flagship distortion -- a multi-stage distortion synthesizer with flexible routing, feedback loops, modulation, and compression. Three independent gain stages (each with its own shaper and filter), six routing topologies, four modulation sources, and a feedback section with delay. Roar can do everything from subtle tape warming to screaming feedback distortion to multi-band destruction. It is a distortion design environment, not just an effect.

- **Signal flow:** Input -> Drive/Tone (global input shaping) -> Routing topology (distributes signal to gain stages) -> Gain Stage(s) (each: shaper + pre/post filter) -> Feedback section (delay with compressor) -> Global Compressor -> Output -> Dry/Wet

- **Six routing modes:**
  - **Single** -> One gain stage. Simplest mode. Use for basic distortion.
  - **Serial** -> Two gain stages in sequence. Cascading distortion for progressive harmonic building.
  - **Parallel** -> Two independent gain stages mixed together. Each can have different shapers/filters for complex tones.
  - **Multi Band** -> Splits into Low/Mid/High frequency bands with adjustable crossovers. Each band gets its own shaper. **Extremely powerful** for frequency-specific distortion (e.g., distort the mids while keeping clean lows).
  - **Mid Side** -> Processes Mid (mono center) and Side (stereo width) separately. Distort the center differently from the sides. Great for stereo-aware processing.
  - **Feedback** -> Processes the dry signal and the feedback signal through separate gain stages. The feedback creates its own tonal character that interacts with the input.

- **Twelve shaper types:**
  - **Soft Sine** -> Gentle waveshaping. Analog warmth.
  - **Hard Sine** -> Harder clipping. More aggressive than Soft Sine.
  - **Asymmetric** -> Uneven clipping that adds even harmonics. Tube-like.
  - **Bit Crush** -> Sample-rate/bit-depth reduction within the gain stage.
  - **Digital Clip** -> Hard 0 dBFS clipping. Harsh, digital.
  - **Fractal** -> Complex wavefolder with chaotic harmonic generation. Unique to Roar.
  - **Noise** -> Adds noise modulation to the signal.
  - **Preamp** -> Models preamp-style saturation. Clean at low levels, overdriven at high.
  - **Rectify** -> Full-wave rectification. Octave-up effect, buzzy, synthy.
  - **Sine Fold** -> Wavefolder similar to Saturator's Sinoid Fold.
  - **Tube** -> Tube-style saturation with characteristic even harmonics.
  - **Tape** -> Tape saturation with head compression and gentle HF rolloff.

- **Eight filter types:** LP (low-pass), HP (high-pass), BP (band-pass), Notch, Peak, Tilt, Comb+, Comb-. Each gain stage has pre and post filter slots.

- **Key parameters per gain stage:**
  - `Shaper Type` -> One of the 12 types above.
  - `Shaper Amount` -> Drive into the shaper.
  - `Shaper Bias` -> DC offset for asymmetric clipping.
  - `Pre Filter Type/Freq` -> Filter before the shaper (shapes what gets distorted).
  - `Post Filter Type/Freq` -> Filter after the shaper (shapes the distorted output).

- **Feedback section:**
  - `Feedback Amount` -> How much output feeds back to the input.
  - `Time mode` -> Time, Synced, Triplet, Dotted, Note. Synced modes = rhythmic feedback. Note mode = pitched feedback that rings at a specific note.
  - `Feedback Compressor` -> Tames the feedback to prevent runaway oscillation.

- **Modulation (4 sources):**
  - `LFO 1 / LFO 2` -> 5 waveforms each, free/synced/triplet/dotted/sixteenth rates.
  - `Envelope Follower` -> Input-responsive modulation with Attack, Release, Threshold, Gain.
  - `Noise` -> 4 types: Simplex, Wander, S&H, Brown.
  - `Matrix` -> Route any modulation source to any parameter.

- **Global controls:**
  - `Drive` -> Global input gain into the routing.
  - `Tone Amount` -> Pre-routing tonal shaping. Positive = attenuates lows.
  - `Color Compensation` -> Balances tone changes.
  - `Compression Amount` -> Post-routing output compression.
  - `Compressor Sidechain HP` -> Reduces pumping from bass.
  - `Output` -> Final gain.
  - `Dry/Wet` (%) -> Parallel blend.

- **Reach for this when:** "Complex distortion," "feedback distortion," "multi-band distortion," "distortion with modulation," "screaming," "self-oscillating distortion," "experimental distortion," "aggressive processing," "distortion design." Roar is the nuclear option -- reach for it when simpler devices can't get the sound.

- **Don't use when:** You need quick, simple warmth (use Saturator -- faster to dial in), you need amp realism (use Amp + Cabinet), or you want classic pedal tones (use Pedal). Roar has a learning curve.

- **Pairs well with:** Compressor before (controls input dynamics), EQ Eight after (surgical cleanup), Utility after (gain matching). Roar can replace entire distortion chains -- it doesn't need much help.

- **vs Saturator:** Saturator = one curve, one stage, simple. Roar = 12 curves, up to 3 stages, 6 routing modes, modulation, feedback. Use Saturator for quick tasks, Roar for distortion design.
- **vs Pedal:** Pedal models specific guitar pedal circuits. Roar is a distortion synthesizer. Pedal for "guitar pedal sound," Roar for "custom distortion from scratch."

---

### Drum Buss (Distortion Aspect)

- **Type:** Native (Standard/Suite)
- **Load via:** `find_and_load_device("Drum Buss")`
- **What it does:** All-in-one drum processing combining drive/distortion, transient shaping, bass enhancement, and damping. The distortion section specifically adds harmonic density and aggression to drum buses. While it's a multi-function device, the Drive section alone makes it worth including here.

- **Signal flow:** Input -> Trim -> Drive section (distortion with 3 types) -> Crunch (compressive distortion) -> Transients -> Boom (resonant bass boost) -> Damping (HF control) -> Output -> Dry/Wet

- **Key distortion parameters:**
  - `Drive` -> Amount of distortion applied. 0% = clean. **Sweet spot: 10-30%** for warmth and glue, 40-70% for aggressive pumping drums.
  - `Drive Type` selector:
    - **Soft** -> Gentle saturation, warm. Adds subtle harmonics without changing the drum character significantly. Good for "warming up" a clean drum bus.
    - **Medium** -> Moderate distortion with more obvious harmonic content. Good balance of aggression and musicality.
    - **Hard** -> Aggressive clipping. Pumping, compressed, loud. Makes drums sound huge and in-your-face. Classic for EDM and hip-hop drum processing.
  - `Crunch` -> Additional compressive distortion stage. Acts like a secondary distortion that also compresses. Adds density and sustain to the drum tail. **Sweet spot: 15-40%.**
  - `Trim` -> Input gain. Feed more level for more drive saturation.

- **Reach for this when:** "Drum bus processing," "fatten the drums," "add punch," "drum distortion," "make drums hit harder," "glue the drums." Drum Buss is the first thing to reach for on a drum group.

- **Don't use when:** Processing non-drum material (it's tuned specifically for drums -- the Boom resonance and transient shaper won't behave well on melodic content), or when you need precise control over the distortion character (use Saturator or Roar instead).

- **Pairs well with:** Glue Compressor before or after (bus compression + drive = massive drums), EQ Eight after (surgical cleanup of any harshness), Utility after (final trim).

---

## M4L Stock (Creative Extensions)

---

### Pitch Hack

- **Type:** M4L Stock (Creative Extensions pack, free with Suite)
- **Load via:** `search_browser("Pitch Hack")` (in Creative Extensions) or browse to CLX_02/Creative Ext/
- **What it does:** A pitch-shifting delay line that can create transposition, reverse audio, and feed shifted signal back into itself. Not a traditional "distortion" device, but its feedback and pitch-shifting create harmonic destruction, metallic textures, and glitchy artifacts that qualify it as a character/mangling tool. When feedback is high with non-octave transposition, it creates cascading inharmonic tones that build into chaos.

- **Signal flow:** Input -> Delay line with pitch transposition -> Reverse option -> Feedback (transposed signal feeds back, shifting further each pass) -> Output -> Dry/Wet

- **Key parameters:**
  - `Transpose` (semitones) -> Pitch shift amount. 0 = no shift (acts as plain delay). +12/-12 = octave up/down. Non-integer values create inharmonic, beating textures. **Sweet spot for chaos: +5 or +7 semitones with high feedback.**
  - `Fine` (cents) -> Fine pitch adjustment. Small detuning values create chorus-like textures in the feedback.
  - `Delay Time` -> Length of the delay buffer.
  - `Reverse` (on/off) -> Reverses the audio in the delay buffer. Creates backward tape-like effects.
  - `Random` -> Randomizes transposition interval. Creates unpredictable pitch jumping.
  - `Feedback` (%) -> How much of the pitched output feeds back. Low = single shifted repeat. High = cascading pitch shifts that spiral up or down. **Sweet spot: 40-70% for musical feedback, 80%+ for self-oscillation.**
  - `Dry/Wet` (%) -> Parallel blend.

- **Reach for this when:** "Pitch shifting," "shimmer," "cascading harmonics," "glitch pitch," "reverse effect," "mangled textures," "alien sounds," "pitch feedback." Pitch Hack is the go-to for creative pitch-based destruction.

- **Don't use when:** You need traditional distortion/saturation (use Saturator), you need amp modeling (use Amp), or you need clean pitch shifting (use a proper pitch shifter -- Pitch Hack always has delay-line artifacts).

- **Pairs well with:** Reverb after (diffuse the pitch chaos into atmosphere), Auto Filter (filter the cascading harmonics), Roar before (distort, then pitch-shift the distortion), Grain Delay (double up on granular/pitch textures).

---

## M4L User (CLX_02 Collection)

All devices below are in: `User Library/MAX MONTY/m4l_2024/_CLX_02 (FX AND SHIT/02 Coloration/`

---

### FUZZ-A-ME

- **Type:** M4L User (CLX_02 / 02 Coloration)
- **Load via:** `search_browser("FUZZ-A-ME")` or browse to CLX_02/02 Coloration/
- **What it does:** Fuzz distortion effect for Max for Live. Based on the name and category placement, this is a fuzz pedal emulation that generates thick, sustaining, harmonically rich distortion characteristic of classic fuzz circuits. Fuzz effects work by heavily clipping the signal (often to near-square-wave) and typically add significant odd harmonics with a raw, unrefined character distinct from overdrive or clean saturation.

- **Signal flow:** Input -> Fuzz circuit emulation (hard clipping with tone shaping) -> Output (likely with tone/level controls)

- **Key parameters (inferred from fuzz circuit design):**
  - `Fuzz` / `Drive` / `Amount` -> Controls distortion intensity. Fuzz circuits typically go from slightly broken to fully saturated square-wave clipping.
  - `Tone` / `Filter` -> Shapes the brightness of the fuzz output. Classic fuzz circuits have a simple tone control that sweeps between dark/muffled and bright/cutting.
  - `Volume` / `Level` -> Output gain.
  - Possibly `Gate`/`Bias` controls for sputtery, dying-battery fuzz textures.

- **Presets:** Inspect with `get_device_parameters` after loading -- M4L device parameters vary.

- **Reach for this when:** "Thick fuzz," "vintage fuzz," "sputtery distortion," "Hendrix fuzz," "stoner rock." When Pedal's Fuzz mode doesn't have the right character, or you want a different fuzz voicing.

- **Don't use when:** You need subtle warmth (too aggressive), you need clean saturation (this is a fuzz), or you need transparent processing.

- **Pairs well with:** Cabinet after (round off the harsh fuzz edges), EQ Eight after (tame fizzy highs), Compressor before (consistent input), Auto Filter before (wah -> fuzz is a classic combo).

- **vs Pedal Fuzz:** Different circuit emulation = different harmonic character. Pedal's Fuzz is built into a multi-mode device with EQ. FUZZ-A-ME is a dedicated fuzz with potentially more authentic vintage fuzz behavior. Try both and pick by ear.

- **Documentation status:** No public documentation found. Parameters must be inspected with `get_device_parameters` after loading.

---

### jRat v1.2

- **Type:** M4L User (CLX_02 / 02 Coloration)
- **Load via:** `search_browser("jRat")` or browse to CLX_02/02 Coloration/
- **What it does:** Max for Live emulation of the ProCo RAT distortion pedal -- one of the most iconic and versatile distortion pedals ever made. The original RAT is known for its unique clipping circuit (using an LM308 op-amp with diode clipping) that produces a thick, mid-forward distortion that sits between overdrive and fuzz. The RAT's Filter control is unique: it's a low-pass filter that sweeps from bright (fully clockwise) to dark (fully counter-clockwise), opposite of most tone controls.

- **Signal flow:** Input -> Op-amp gain stage with diode clipping (RAT circuit emulation) -> Filter (LPF, reversed polarity) -> Volume -> Output

- **Key parameters (based on ProCo RAT circuit):**
  - `Distortion` -> Controls the gain/clipping amount. Low settings = light overdrive. Mid settings = classic RAT crunch. High settings = massive, thick, almost fuzz-like. **Sweet spot: 40-65%** for the classic RAT sound (thick but articulate).
  - `Filter` -> Low-pass filter cutoff. **Reversed from typical tone controls**: high values = darker, low values = brighter. This is a defining RAT characteristic. **Sweet spot: 30-50%** (balanced), lower for cutting leads, higher for thick rhythm.
  - `Volume` / `Level` -> Output gain.

- **Presets:** Inspect with `get_device_parameters` after loading.

- **Reach for this when:** "RAT distortion," "thick mid-range distortion," "versatile distortion pedal," "punk rock guitar," "shoegaze," "grunge bass." The RAT is famous for working on everything -- guitar, bass, synths, drums. It's the "desert island" distortion pedal for many producers.

- **Don't use when:** You need pristine clean saturation (RAT is always characterful), you need amp-like breakup (use Amp), or you need subtle warming (use Saturator).

- **Pairs well with:** Cabinet after (essential for guitar use), Amp after (RAT into a clean amp is a classic combo), Compressor before (tightens the RAT's response), EQ Eight after (the reversed filter can be supplemented with precise EQ).

- **vs Pedal Dist:** Pedal's Distortion mode is a generic hard-clipping model. jRat specifically models the RAT's unique LM308 + diode clipping circuit and reversed filter. The RAT has a distinctive mid-forward growl that generic distortion doesn't capture. jRat for RAT authenticity, Pedal Dist for versatility.

- **Documentation status:** No public documentation found. Parameters must be inspected with `get_device_parameters` after loading.

---

### Cat Growl Filter

- **Type:** M4L User (CLX_02 / 02 Coloration)
- **Load via:** `search_browser("Cat Growl Filter")` or browse to CLX_02/02 Coloration/
- **What it does:** A filter-based distortion/character device. Based on the name, this is likely a resonant filter with aggressive feedback or waveshaping that creates "growling" tones -- the kind of aggressive, vocal, animalistic resonance you hear in acid basslines, dubstep basses, and aggressive synth leads. "Growl" in audio typically refers to a resonant filter pushed into self-oscillation or a formant-like filter that creates vowel/animal-like tones.

- **Signal flow:** Input -> Resonant filter (likely with feedback/distortion in the feedback path) -> Output

- **Key parameters (inferred from name and category):**
  - `Frequency` / `Cutoff` -> Filter frequency. Sweeping this creates the "growl" -- the moving resonant peak.
  - `Resonance` / `Feedback` -> How much the filter resonates. High resonance = more aggressive growl, potentially self-oscillating.
  - `Drive` / `Distortion` -> Distortion in or around the filter, adding harmonic content to the resonant peak.
  - `Mix` / `Dry/Wet` -> Blend control.

- **Reach for this when:** "Growling filter," "acid bass," "aggressive resonance," "vocal/animal-like filter," "dubstep bass processing," "resonant distortion." When Auto Filter isn't aggressive enough and you need something that truly snarls.

- **Don't use when:** You need subtle saturation, transparent EQ-style filtering, or clean processing.

- **Pairs well with:** Saturator before (more harmonics for the filter to resonate), Compressor after (tame the resonant peaks), Auto Filter in parallel (layer the growl with a cleaner sweep).

- **Documentation status:** No public documentation found. Parameters must be inspected with `get_device_parameters` after loading.

---

### N-CHAOS

- **Type:** M4L User (CLX_02 / 02 Coloration)
- **Load via:** `search_browser("N-CHAOS")` or browse to CLX_02/02 Coloration/
- **What it does:** A chaotic/experimental distortion and audio mangling device. The name "N-CHAOS" strongly suggests a noise-based or chaos-theory-driven audio processor. This likely generates unpredictable, evolving distortion textures -- possibly using chaotic oscillators, random modulation, or noise injection to create constantly shifting, unstable distortion character. The 4.5 MB file size suggests significant DSP complexity.

- **Signal flow:** Input -> Chaos-driven processing (likely involving noise modulation, chaotic oscillators, or stochastic processing) -> Output

- **Key parameters (inferred from name and typical chaos processors):**
  - `Chaos` / `Amount` -> Controls the intensity of chaotic processing. Low = subtle instability. High = full chaos.
  - `Rate` / `Speed` -> How fast the chaotic modulation evolves.
  - `Noise` / `Density` -> Amount of noise injection or stochastic elements.
  - `Mix` / `Dry/Wet` -> Blend control.
  - Possibly `Feedback` -> Chaotic processors often use feedback for self-exciting behavior.

- **Reach for this when:** "Chaos," "unpredictable," "evolving distortion," "experimental," "glitch," "noise-based processing," "random destruction." For when you want distortion that moves and shifts on its own.

- **Don't use when:** You need predictable, repeatable distortion. Chaos processors by definition are non-deterministic.

- **Pairs well with:** Compressor after (tame the chaotic dynamics), Auto Filter after (focus the chaos into a frequency band), Reverb after (diffuse chaotic textures into ambience), Utility (kill switch for when it gets out of hand).

- **Documentation status:** No public documentation found. Parameters must be inspected with `get_device_parameters` after loading.

---

## Encoder Audio Mojo IR Library

---

### Mojo (Convolution Character Processor)

- **Type:** M4L User (CLX_02 / Encoder Audio Mojo)
- **Load via:** `search_browser("Mojo")` or browse to CLX_02/Encoder Audio Mojo/
- **What it does:** A convolution-based character processor that uses impulse responses captured from real analog equipment to impart their frequency response and harmonic coloration onto your audio. Unlike traditional distortion that generates new harmonics through waveshaping, Mojo works through convolution: it multiplies your signal with a captured IR (impulse response) of a real piece of hardware, transferring that hardware's frequency curve, phase response, and resonant characteristics to your signal.

  This is fundamentally different from distortion -- Mojo doesn't add new harmonics through clipping. Instead, it applies the EQ curve, phase coloration, and subtle resonances that make audio "sound like it went through" a specific piece of gear. Think of it as "character transplant" rather than "distortion."

- **Signal flow:** Input -> Convolution engine (signal * impulse response) -> Mix/Output

- **The IR Library (350+ impulse responses across 14 categories):**

  **Compressors (22 IRs):** Character from classic dynamics processors.
  - API 525, BBE Sonic Maximiser, EMT156 (x4), Fairchild 670, Glennsound Compressor, JoeMeek SC2, Manley Vari Mu (x2), Neve Portico 5043, Oram Sonicomp, Symetrix 528 (x2), Universal Audio 1176, Urei 1176 (x2), dbx 160SL (x4)
  - **Best for:** Adding the "glue" and tonal weight of hardware compression without actual dynamics processing. The Fairchild 670 IR adds warmth and low-mid density. The 1176 IRs add aggressive midrange presence. The Manley Vari Mu adds smooth, wide warmth.

  **Consoles (8 IRs):** Character from mixing desks.
  - BBC Mixer (x2), Neve 8014 (x2), SSL 4000E (x2), SSL 9000K
  - **Best for:** "Mix bus" coloration. The Neve 8014 adds thick, warm midrange. SSL 4000E adds tight, punchy definition. SSL 9000K is cleaner/wider. BBC Mixer has a unique vintage broadcast character.

  **Tapes (109 IRs):** Largest category. Character from tape machines.
  - Akai 4000DS MKII (x8), Ampex ATR102 (x6), Empirical Labs Fatso (x4), Lafayette Radio RK-142 (x4), NAG Tape, Neve Portico 5042 (x3), Otari MTR-10 (x5), Revox B77 (x23), Revox PR99 (x4), Sony TC-640 (x5), Studer A80 (x5), Studer A800 MKIII (x6), Studer A801 (x2), TEAC W-6004 (x4), Tape Warmth (x7), Technics 671 (x2), Technics RS-B405 (x5), Telefunken V72 (x3), Telefunken V76 (x4), Vintage Tape, Wollensak 1515 (x6)
  - **Best for:** Tape warmth, HF rolloff, low-end thickening, "vintage" character. The Ampex ATR102 is the studio standard for mastering tape character. Studer A800 for tracking warmth. Revox B77 for lo-fi consumer tape feel. Multiple IRs per machine capture different tape speeds, bias settings, and saturation levels.

  **Guitar Pedals (24 IRs):** Character from distortion/fuzz pedals.
  - BYOC Screamer (x4), Boss FZ-2 (x15), Boss HM-2 (x5)
  - **Best for:** Adding the frequency curve of specific pedals without the actual distortion. The Boss HM-2 IR imparts the famous "chainsaw" Swedish death metal scoop. The Boss FZ-2 captures the fuzz voicing. BYOC Screamer (Tube Screamer clone) adds the classic mid hump.

  **Preamps (25 IRs):** Character from mic preamps.
  - API 512, Avalon VT-737SP (x2), Drawmer 1960, Focusrite Red 8, Manley VoxBox (x4), Neve 1272 (x4), Neve 33114 (x2), Neve 33619, Neve Portico 5012, SPL Gainstation, SPL GoldMike (x2), SSL Logic FX G383, Teletronix LA-2A (x2), Teletronix LA-3A, True Systems Precision 8
  - **Best for:** Adding mic preamp coloration to DI or digitally recorded signals. Neve 1272 adds fat, warm midrange. API 512 adds punchy definition. Avalon adds crystalline clarity with warmth.

  **Equalizers (13 IRs):** Character from hardware EQs.
  - API 5500 (x2), BBC EQ, Calrec 1061 (x2), Neuman EQ (x4), Neve 1073 (x2), TC Electronics 2240 (x2)
  - **Best for:** The Neve 1073 IR adds the famous "Neve sound" (warm, thick, musical mids). API 5500 adds punchy American clarity.

  **Tubes (10 IRs):** Character from tube stages.
  - SPL Charisma, SPL Tube Warm, SPL TubeVitalizer, Tube Buffer Bass (x2), Tube DI, Tube Drive, Tube Preamp, Tube Warmth, Tubetech CL1B
  - **Best for:** Tube warmth without Dynamic Tube's envelope following. The Tubetech CL1B adds smooth, creamy tube compression character.

  **Microphones (69 IRs):** Character from classic mics.
  - AKG D12, Altec 639/670A/670B, BBC Marconi B, Coles 4038, EV RE20, RCA 44BX/77DX/74B, Shure 315/510C, Sony C37Fet, Telefunken M201, and many rare/vintage models.
  - **Best for:** Adding mic coloration. The Coles 4038 adds ribbon warmth. RCA 44BX adds classic broadcast character. EV RE20 adds radio voice presence.

  **Samplers (22 IRs):** Character from hardware samplers.
  - Akai MPC2500, Akai MPC60 (x7), Akai S3000, Akai S3200XL (x2), Akai S950 (x7), Roland S-10, Yamaha VSS-100 (x3)
  - **Best for:** "Sampled from an MPC" character. The MPC60 IRs add the famous gritty warmth. S950 adds the lo-fi crunch. These capture the DA converter character and output stage coloration of vintage samplers.

  **Speakers (40 IRs):** Character from speaker systems.
  - 70s Philips box, 80s UK/US (multiple), Modern UK/US (multiple), Radio, Small intercom, Vintage UK/US, numbered speakers
  - **Best for:** "Through a speaker" effect. Great for lo-fi, telephone, radio, and small-speaker simulation.

  **Enhancers (7 IRs):** Character from signal enhancers.
  - Aphex Aural Exciter Type C, Dolby A/SR encode/decode (x5), SPL Vitalizer
  - **Best for:** Subtle presence and air. The Aphex adds high-frequency shimmer. The Dolby encode/decode pairs create interesting phase artifacts.

  **Others (19 IRs):** Miscellaneous character.
  - 90s telephone, AKG K240 (headphones), Car radio (x2), Erres tube radio, Macbook Pro 2008 Mic, Roland RE-201 Space Echo, Sennheiser HD480, Sony TwinTurbo, Telephone horn T65, Vinyl (x6), Walkman (x2)
  - **Best for:** Special effects. Telephone, radio, vinyl coloration, lo-fi walkman character.

- **Key parameters (M4L device):**
  - `IR Select` / `Category` / `File` -> Navigate and select impulse responses from the library.
  - `Dry/Wet` / `Mix` -> Blend convolved signal with dry. **Sweet spot: 30-70%** for subtle character, 100% for full effect.
  - Likely includes basic `EQ` or `Tone` controls for shaping the convolution output.
  - Inspect with `get_device_parameters` after loading for exact parameter names.

- **Reach for this when:** "Analog character," "console sound," "tape warmth," "make it sound like it went through a Neve," "MPC crunch," "SSL character," "vintage coloration," "add hardware mojo." Mojo is unique -- no other device in this collection can add the specific frequency/phase character of real hardware through convolution.

- **Don't use when:** You need actual distortion/harmonics (convolution IRs capture frequency response, not nonlinear harmonic generation -- for harmonics, use Saturator/Dynamic Tube), you need dynamics processing (IRs don't compress), or you need modulated/evolving effects (convolution is static).

- **Pairs well with:** Saturator after (add harmonics to the colored signal), Compressor before (consistent level into the convolution), EQ Eight after (fine-tune the IR's frequency curve), Utility after (gain match -- some IRs change level significantly). **Power combo: Mojo (tape IR) -> Saturator (Analog Clip, light drive) -> Glue Compressor for the ultimate "mixed through an analog desk" sound.**

- **vs Saturator:** Completely different. Saturator adds harmonics through waveshaping. Mojo applies a frequency/phase response through convolution. They complement each other -- Mojo for character, Saturator for harmonics.
- **vs Vinyl Distortion:** Vinyl Distortion models the physics of vinyl playback. Mojo's Vinyl IRs capture the actual frequency response of real vinyl playback systems. Mojo is more authentic but less controllable.

---

## Quick Decision Matrix

| Scenario | First Choice | Why | Second Choice |
|----------|-------------|-----|---------------|
| Subtle bus warmth | **Saturator** (Analog Clip, Drive 3-6 dB, Dry/Wet 40-60%) | Transparent, controllable | Dynamic Tube (A) |
| Fatten a bass | **Saturator** (Hard Curve or Analog Clip) | Full-bandwidth harmonics | Overdrive (for mid grit) |
| Guitar pedal tone | **Pedal** (select OD/Dist/Fuzz mode) | Built for this purpose | jRat v1.2 (RAT character) |
| Full guitar rig | **Pedal -> Amp -> Cabinet** | Complete signal chain | Just Amp -> Cabinet |
| Drum bus drive | **Drum Buss** (Soft/Med/Hard drive) | Designed for drums, has transient/boom | Saturator on drum group |
| Multi-band distortion | **Roar** (Multi Band mode) | Only native option for this | Audio Effect Rack + Saturators |
| Experimental feedback distortion | **Roar** (Feedback mode) | Unique feedback architecture | Pitch Hack (pitch feedback) |
| Lo-fi digital | **Redux** + **Erosion** | Bitcrush + digital degradation | Roar (Bit Crush shaper) |
| Lo-fi vinyl | **Vinyl Distortion** | Purpose-built for vinyl artifacts | Mojo (Vinyl IRs) |
| Tube warmth | **Dynamic Tube** | Dynamic tube response | Mojo (Tube IRs) + Saturator |
| "Analog console" character | **Mojo** (Console IRs) | Real hardware character via convolution | Saturator (Analog Clip, gentle) |
| "Tape" character | **Mojo** (Tape IRs) | Real tape machine character | Saturator (Analog Clip) + EQ rolloff |
| "Hardware compressor" color | **Mojo** (Compressor IRs) | Real compressor character | Glue Compressor (SSL emulation) |
| MPC/sampler crunch | **Mojo** (Sampler IRs) | Captures real DA converter character | Redux (downsample) |
| RAT pedal distortion | **jRat v1.2** | Dedicated RAT emulation | Pedal (Dist mode) |
| Fuzz (classic) | **FUZZ-A-ME** or **Pedal Fuzz** | Dedicated fuzz circuits | Roar (Tube shaper, high drive) |
| Aggressive resonant filter | **Cat Growl Filter** | Dedicated growl filter | Auto Filter (high resonance + drive) |
| Chaotic/random distortion | **N-CHAOS** | Purpose-built for chaos | Roar (with noise modulation) |
| Pitch-based destruction | **Pitch Hack** | Pitch-shifting feedback | Grain Delay (pitch + scatter) |
| Speaker/radio simulation | **Cabinet** or **Mojo** (Speaker IRs) | Physical speaker modeling | EQ Eight (LP + HP band) |
| Gentle mastering saturation | **Saturator** (Soft Sine, Drive 3-5 dB, Soft Clip on) | Most transparent option | Mojo (tape IR, low mix) |
| "Make it heavier" | **Roar** (Serial mode, Tube + Tape shapers) | Cascading stages for density | Pedal (Dist) -> Saturator |
| Subtle analog character on everything | **Mojo** (Neve 1073 or SSL 4000E IR) | Real hardware frequency response | Saturator (Analog Clip, Dry/Wet 20%) |

---

## Signal Chain Templates

### The "Analog Warmth" Chain
```
Mojo (Tape: Ampex ATR102) -> Saturator (Analog Clip, Drive 4 dB, Soft Clip on, Dry/Wet 50%) -> Utility (gain match)
```
Adds tape frequency response + gentle harmonic saturation. Use on buses or master.

### The "Guitar Rig" Chain
```
jRat v1.2 (or Pedal) -> Amp (Rock or Lead) -> Cabinet (4x12, Dynamic mic, Near) -> EQ Eight (cleanup) -> Delay/Reverb
```
Full guitar processing from pedal to cabinet.

### The "Lo-Fi Everything" Chain
```
Mojo (Sampler: Akai S950) -> Redux (Downsample 4x, Bit Depth 10) -> Vinyl Distortion (Crackle 10%, subtle Tracing) -> EQ Eight (LP at 8 kHz)
```
Instant vintage sampled-from-vinyl character.

### The "Drum Destruction" Chain
```
Drum Buss (Hard drive 40%, Crunch 30%) -> Roar (Single, Tape shaper, moderate drive) -> Glue Compressor (4:1, fast attack)
```
Aggressive, pumping, characterful drums.

### The "Subtle Mix Bus" Chain
```
Mojo (Console: SSL 4000E) -> Saturator (Soft Sine, Drive 2 dB, Soft Clip on) -> Glue Compressor (2:1, slow attack, Dry/Wet 70%)
```
Professional bus processing with analog character.

### The "Experimental Texture" Chain
```
N-CHAOS (moderate settings) -> Roar (Feedback mode, Fractal shaper) -> Pitch Hack (feedback 60%, +7 semitones) -> Reverb (long tail, 80% wet)
```
For ambient, experimental, and sound design contexts.

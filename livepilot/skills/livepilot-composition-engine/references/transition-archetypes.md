# Transition Archetypes Reference

Common transition patterns returned by `plan_transition` and usable with `apply_gesture_template`.

## Energy-Up Transitions

### riser_sweep
A filter or noise sweep that builds energy into the next section.

- Duration: 2-8 bars
- Implementation: ascending automation on filter cutoff (20% to 100%) plus optional white noise riser
- Best for: verse-to-chorus, breakdown-to-drop
- Tools: `set_clip_automation`, `apply_automation_shape(shape="exponential_rise")`

### drum_build
Progressive addition of percussion layers leading to the downbeat.

- Duration: 2-4 bars
- Implementation: add hi-hat rolls (increasing density), snare fills, kick pattern intensification
- Best for: pre-chorus builds, intro-to-verse
- Tools: `add_notes` for fill patterns, `set_track_volume` automation for gradual volume increase

### harmonic_tension
Build tension through suspended or unresolved harmony before resolving at the section boundary.

- Duration: 1-4 bars
- Implementation: sus4 or dominant 7th chord sustained over the transition, resolving on beat 1 of the new section
- Best for: verse-to-chorus, bridge-to-final-chorus
- Tools: `modify_notes` to alter chord voicings, `add_notes` for tension tones

### stacking
Gradually add instrumental layers, one per bar or phrase, building density.

- Duration: 4-16 bars
- Implementation: unmute tracks in sequence (percussion first, then bass, then harmony, then leads)
- Best for: intro builds, post-breakdown rebuilds
- Tools: `set_clip_automation` on track volume, `set_track_mute` for discrete layer adds

## Energy-Down Transitions

### strip_down
Remove elements one by one to reduce energy before a quieter section.

- Duration: 2-8 bars
- Implementation: mute layers in reverse order of importance (effects first, then leads, then harmony, keeping bass and kick last)
- Best for: chorus-to-verse, pre-breakdown
- Tools: `set_track_mute`, `set_track_volume` automation with gradual decrease

### filter_close
Low-pass filter sweep closing down to muffle the sound.

- Duration: 2-4 bars
- Implementation: descending automation on master or bus filter cutoff (100% to 20-30%)
- Best for: section endings, transitions to breakdowns
- Tools: `set_clip_automation`, `apply_automation_shape(shape="exponential_fall")`

### reverb_wash
Increase reverb wet level to blur the previous section into the next.

- Duration: 1-2 bars
- Implementation: automate send level to reverb return (0% to 60-80%), then cut dry signal on beat 1
- Best for: hard section changes where you want continuity of space
- Tools: `set_track_send` automation, `set_clip_automation`

## Neutral Transitions

### hard_cut
Instant transition with no preparation. The contrast itself creates impact.

- Duration: 0 bars (instantaneous)
- Implementation: no transition processing — the sections simply abut
- Best for: drop entries after silence, genre-specific style (punk, some electronic)
- Constraint: works best when the energy delta is extreme (silence to loud, or vice versa)

### crossfade
Gradual overlap of outgoing and incoming sections.

- Duration: 1-4 bars
- Implementation: outgoing section fades out while incoming fades in, overlapping by the crossfade duration
- Best for: ambient, cinematic, smooth genre transitions
- Tools: `set_clip_automation` on track volumes with opposing curves

### fill_break
A drum fill followed by a brief silence (1-2 beats) before the new section.

- Duration: 1 bar
- Implementation: drum fill on the last bar, then all instruments drop for 1-2 beats, new section enters on beat 3 or 4
- Best for: rock, pop, funk section transitions
- Tools: `add_notes` for the fill, `set_track_mute` or volume automation for the gap

## Choosing the Right Archetype

| From -> To | Recommended | Alternative |
|------------|-------------|-------------|
| Intro -> Verse | stacking | drum_build |
| Verse -> Chorus | riser_sweep, drum_build | harmonic_tension |
| Chorus -> Verse | strip_down | filter_close |
| Verse -> Bridge | harmonic_tension | strip_down |
| Bridge -> Final Chorus | riser_sweep + drum_build | harmonic_tension |
| Chorus -> Breakdown | strip_down, hard_cut | filter_close |
| Breakdown -> Drop | riser_sweep | drum_build + stacking |
| Any -> Outro | strip_down, reverb_wash | filter_close |

# Technique Memory Guide — Qualities Template & Examples

How to write rich, searchable stylistic analyses when saving techniques.

## The Qualities Template

Every technique gets an agent-written `qualities` object. All fields are optional
except `summary` (required). Fill what's relevant to the technique type.

| Field | What to write | Example |
|-------|--------------|---------|
| summary | One sentence — what this is and why it's good | "Dusty boom bap groove with lazy swing and ghost snares" |
| mood | 2-4 mood/feeling words | ["laid-back", "dusty", "head-nodding"] |
| genre_tags | Genre associations | ["boom-bap", "hip-hop", "lo-fi"] |
| rhythm_feel | How the groove feels — swing, syncopation, density | "Syncopated kick with lazy hat swing, ghost snares anticipate the backbeat" |
| harmonic_character | Key, scale, chord quality, movement | "C minor dorian, jazzy 7th chords, descending bass line" |
| sonic_texture | Timbral character — warm/bright/gritty/clean | "Dusty vinyl-crackle hats, boomy 808 kick, dry snare with room verb" |
| production_notes | When/how to use this, what it pairs with | "Works as verse beat, needs sparse melody on top — Rhodes or muted guitar" |
| reference_points | Artists, songs, styles it evokes | "J Dilla 'Donuts' era meets Madlib 'Madvillainy' drums" |

## Good vs Bad Qualities

### Beat Pattern

**GOOD:**
```json
{
  "summary": "Dusty boom bap groove — lazy swing on the hats, ghost snares anticipate the backbeat, 85 BPM slow-roll energy",
  "mood": ["laid-back", "dusty", "head-nodding"],
  "genre_tags": ["boom-bap", "hip-hop"],
  "rhythm_feel": "Syncopated kick at 0 and the 'and' of 1. Hi-hats on 8ths with +0.02 swing on offbeats. Ghost snares (vel 30) on 16ths before beats 2 and 4. The whole thing leans back.",
  "production_notes": "Works as a verse beat. Needs sparse melody on top — Rhodes, muted guitar, or pitched sample. Leave headroom in low-mids for vocals.",
  "reference_points": "J Dilla 'Donuts' era meets Madlib on 'Madvillainy'"
}
```

**BAD:**
```json
{
  "summary": "Hip hop beat at 85 BPM with kick, snare, and hi-hats"
}
```
The bad version is factual but tells the agent nothing about *feel*. It can't distinguish this from any other hip-hop beat.

### Device Chain

**GOOD:**
```json
{
  "summary": "Warm tape-style lo-fi chain — subtle saturation into gentle filtering, makes anything sound like it's playing through a dusty speaker",
  "mood": ["warm", "nostalgic", "lo-fi"],
  "sonic_texture": "Soft Sine saturation adds even harmonics without harshness. Auto Filter rolls off highs gently around 3kHz. Erosion adds subtle digital artifacts like worn tape. The chain darkens and warms without killing presence.",
  "production_notes": "Put this on Rhodes, guitar samples, or pads. Not great for drums — kills transients. Works beautifully on chord progressions.",
  "reference_points": "Lo-fi hip-hop study beats aesthetic, Nujabes-style warmth"
}
```

**BAD:**
```json
{
  "summary": "Saturator then Auto Filter then Erosion"
}
```

### Mix Template

**GOOD:**
```json
{
  "summary": "Deep house return setup — long lush reverb on A, filtered ping-pong delay on B, subtle parallel compression on C",
  "mood": ["spacious", "deep", "hypnotic"],
  "genre_tags": ["deep-house", "tech-house"],
  "sonic_texture": "Reverb is dark and long (4s decay, heavy high-cut) for depth without brightness. Delay is filtered (LP at 3kHz) so echoes sit behind the mix. Parallel compression adds density to drums without crushing transients.",
  "production_notes": "Send drums to C at 0.3, pads to A at 0.5, synth stabs to B at 0.3. Keep kick dry (no sends). Return levels around -8dB for subtlety."
}
```

### Preference

**GOOD:**
```json
{
  "summary": "Always use Valhalla VintageVerb instead of stock Reverb on return tracks — stock Reverb sounds too metallic in the highs for my taste"
}
```

### Browser Pin

**GOOD:**
```json
{
  "summary": "808 Core Kit — my go-to drum kit for trap and hip-hop. Has a punchy kick that sits well with Saturator, crispy hats, and a tight clap."
}
```

## When to Save

- User says "save this" / "remember this" / "I like this"
- A beat, sound, or chain turns out particularly well
- User discovers a browser item they want to use again
- User states a preference about how they work

## When NOT to Save

- Generic, unfinished, or placeholder work
- Things that are already in the shipped reference corpus
- Exact duplicates of existing saved techniques

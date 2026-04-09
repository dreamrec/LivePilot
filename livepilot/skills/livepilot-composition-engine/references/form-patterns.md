# Form Patterns Reference

Common song forms and energy curves used by `plan_arrangement` and `get_emotional_arc`.

## Standard Forms

### verse_chorus (Pop / Rock / R&B)
```
Intro (4-8 bars) -> Verse 1 (8-16) -> Pre-Chorus (4-8) -> Chorus 1 (8-16)
-> Verse 2 (8-16) -> Pre-Chorus (4-8) -> Chorus 2 (8-16)
-> Bridge (8) -> Final Chorus (8-16) -> Outro (4-8)
```
Energy curve: low -> medium -> high -> medium -> high -> peak -> fade

### drop_form (EDM / House / Techno)
```
Intro (16-32 bars) -> Build 1 (8-16) -> Drop 1 (16-32)
-> Breakdown (8-16) -> Build 2 (8-16) -> Drop 2 (16-32)
-> Outro (8-16)
```
Energy curve: building -> peak -> valley -> building -> peak -> fade

### through_composed (Ambient / Cinematic / Experimental)
```
Section A (variable) -> Section B (variable) -> Section C (variable) -> ...
```
No repeating sections. Energy curve follows the narrative arc. Each section introduces new material.

### aaba (Jazz / Classic Pop)
```
A (8 bars) -> A (8) -> B (8) -> A (8)
```
Energy curve: establish -> reinforce -> contrast -> resolve

### rondo (Classical-influenced / Progressive)
```
A -> B -> A -> C -> A -> D -> A
```
Recurring theme (A) alternates with contrasting episodes. Energy varies per episode.

### loop_form (Hip-Hop / Trap / Lo-Fi)
```
Intro (4-8) -> Loop (4-8 bars, repeated throughout)
Verse 1 over loop -> Hook over loop -> Verse 2 over loop -> Hook -> Outro
```
Energy modulation through vocal density and arrangement layering, not harmonic progression.

## Energy Curve Targets

The emotional arc maps energy on a 0.0-1.0 scale across the track duration.

### Peak-Valley Model
Most effective for dance and pop music:
- At least one peak reaching 0.8-1.0
- At least one valley dropping to 0.2-0.4
- Energy delta between adjacent sections: 0.15-0.4
- Gradual builds (4+ bars) feel more natural than instant jumps

### Plateau Model
For ambient, drone, and minimalist music:
- Energy stays within a narrow band (0.3-0.6)
- Changes are subtle: timbral, textural, not dynamic
- Slow evolution over minutes, not bars

### Escalation Model
For builds, film scoring, and progressive tracks:
- Monotonically increasing energy from 0.1 to 1.0
- Each section is louder, denser, or brighter than the previous
- No significant drops until the final resolution

## Section Energy Targets by Genre

| Section | Pop | EDM | Hip-Hop | Ambient |
|---------|-----|-----|---------|---------|
| Intro | 0.2 | 0.3 | 0.3 | 0.2 |
| Verse | 0.4 | 0.4 | 0.5 | 0.3 |
| Pre-Chorus | 0.6 | 0.6 | — | — |
| Chorus/Drop | 0.8 | 1.0 | 0.7 | 0.5 |
| Bridge | 0.5 | — | 0.4 | 0.4 |
| Breakdown | — | 0.2 | — | 0.3 |
| Outro | 0.3 | 0.2 | 0.2 | 0.1 |

## Section Length Guidelines

- **4 bars**: minimum for a recognizable section (short intros, transitions)
- **8 bars**: standard phrase length, feels complete for most sections
- **16 bars**: full development, typical for verses and choruses in electronic music
- **32 bars**: extended development for drops, long builds, or ambient passages
- **Odd lengths** (6, 10, 12 bars): create subtle tension and asymmetry — use intentionally

## Arrangement Planning Rules

1. Start from the emotional peak and work backwards — place the climax first, then build toward it
2. Every section serves one of five functions: introduce, develop, contrast, climax, resolve
3. Do not repeat a section more than 3 times without significant variation
4. The first 30 seconds determine whether the listener stays — make them count
5. Endings matter — an abrupt end can be intentional, but a trailing reverb wash is rarely wrong

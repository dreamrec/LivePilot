"""Music theory tools powered by music21.

7 tools for harmonic analysis, chord suggestion, voice leading detection,
counterpoint generation, scale identification, harmonization, and intelligent
transposition — all working directly on live session clip data via get_notes.

Design principle: tools compute from data, the LLM interprets and explains.
Returns precise musical data (Roman numerals, pitch names, intervals), never
explanations the LLM already knows from training.

Requires: pip install music21 (lazy-imported, never at module level)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from fastmcp import Context

from ..server import mcp


# -- Shared utilities --------------------------------------------------------

def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_clip_notes(ctx: Context, track_index: int, clip_index: int) -> list[dict]:
    """Fetch notes from a session clip via the remote script."""
    result = _get_ableton(ctx).send_command("get_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    return result.get("notes", [])


def _parse_key_string(key_str: str):
    """Parse a human-friendly key string into a music21 Key object.

    Accepts: "C", "c", "C major", "A minor", "g minor", "F# major", etc.
    music21's Key() wants: uppercase tonic = major, lowercase = minor.
    """
    from music21 import key
    hint = key_str.strip()
    if ' ' in hint:
        parts = hint.split()
        tonic = parts[0]
        mode = parts[1].lower() if len(parts) > 1 else 'major'
        if mode == 'minor':
            tonic = tonic[0].lower() + tonic[1:]
        return key.Key(tonic)
    return key.Key(hint)


def _notes_to_stream(notes: list[dict], key_hint: str | None = None):
    """Convert LivePilot note dicts to a music21 Stream.

    This is the bridge between Ableton's note format and music21's
    analysis engine. Groups simultaneous notes into Chord objects.
    Quantizes start_times to 1/32 note resolution to avoid chordify
    fragmentation from micro-timing variations.
    """
    from music21 import stream, note, chord, meter

    s = stream.Part()
    s.append(meter.TimeSignature('4/4'))

    if key_hint:
        try:
            k = _parse_key_string(key_hint)
            s.insert(0, k)
        except Exception:
            pass

    # Quantize to 1/32 note (0.125 beats) to group near-simultaneous notes
    QUANT = 0.125

    time_groups: dict[float, list[dict]] = defaultdict(list)
    for n in notes:
        if n.get("mute", False):
            continue
        q_time = round(n["start_time"] / QUANT) * QUANT
        time_groups[q_time].append(n)

    for t in sorted(time_groups.keys()):
        group = time_groups[t]
        if len(group) == 1:
            n = group[0]
            m21_note = note.Note(n["pitch"])
            m21_note.quarterLength = max(QUANT, n["duration"])
            m21_note.volume.velocity = n.get("velocity", 100)
            s.insert(t, m21_note)
        else:
            pitches = sorted(set(n["pitch"] for n in group))
            dur = max(n["duration"] for n in group)
            m21_chord = chord.Chord(pitches)
            m21_chord.quarterLength = max(QUANT, dur)
            s.insert(t, m21_chord)

    return s


def _detect_key(s):
    """Detect key from a music21 stream. Uses Krumhansl-Schmuckler algorithm."""
    from music21 import key as m21key

    # Check if key was already set by the user
    existing = list(s.recurse().getElementsByClass(m21key.Key))
    if existing:
        return existing[0]

    return s.analyze('key')


def _pitch_name(midi_num: int) -> str:
    """MIDI number to note name (e.g., 60 → 'C4')."""
    from music21 import pitch
    return str(pitch.Pitch(midi_num))


def _require_music21():
    """Verify music21 is installed, raise clear error if not."""
    try:
        import music21  # noqa: F401
    except ImportError:
        raise ImportError(
            "music21 is required for theory tools. "
            "Install with: pip install 'music21>=9.3'"
        )


# -- Tool 1: analyze_harmony ------------------------------------------------

@mcp.tool()
def analyze_harmony(
    ctx: Context,
    track_index: int,
    clip_index: int,
    key: Optional[str] = None,
) -> dict:
    """Analyze harmony of a MIDI clip: chords, Roman numerals, progression.

    Reads notes directly from a session clip — no bouncing needed.
    Auto-detects key if not provided.

    Returns chord progression with Roman numeral analysis. The tool computes
    the data; interpret the musical meaning yourself.
    """
    _require_music21()
    from music21 import roman

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip", "suggestion": "Add notes first"}

    s = _notes_to_stream(notes, key_hint=key)
    detected_key = _detect_key(s)

    chordified = s.chordify()
    chords = []

    for c in chordified.recurse().getElementsByClass('Chord'):
        entry = {
            "beat": round(float(c.offset), 3),
            "duration": round(float(c.quarterLength), 3),
            "pitches": [str(p) for p in c.pitches],
            "midi_pitches": [p.midi for p in c.pitches],
            "chord_name": c.pitchedCommonName,
        }
        try:
            rn = roman.romanNumeralFromChord(c, detected_key)
            entry["roman_numeral"] = rn.romanNumeral
            entry["figure"] = rn.figure
            entry["quality"] = rn.quality
            entry["inversion"] = rn.inversion()
            entry["scale_degree"] = rn.scaleDegree
        except Exception:
            entry["roman_numeral"] = "?"
            entry["figure"] = "?"

        chords.append(entry)

    progression = " - ".join(c.get("figure", "?") for c in chords[:24])

    # Key confidence
    key_info = {"key": str(detected_key)}
    if hasattr(detected_key, 'correlationCoefficient'):
        key_info["confidence"] = round(detected_key.correlationCoefficient, 3)
    if hasattr(detected_key, 'alternateInterpretations'):
        alts = detected_key.alternateInterpretations[:3]
        key_info["alternatives"] = [str(k) for k in alts]

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        **key_info,
        "chord_count": len(chords),
        "progression": progression,
        "chords": chords[:32],
    }


# -- Tool 2: suggest_next_chord ---------------------------------------------

@mcp.tool()
def suggest_next_chord(
    ctx: Context,
    track_index: int,
    clip_index: int,
    key: Optional[str] = None,
    style: str = "common_practice",
) -> dict:
    """Suggest the next chord based on the current progression.

    Analyzes existing chords and suggests theory-valid continuations.
    style: common_practice, jazz, modal, pop — affects which progressions
    are preferred.

    Returns concrete chord suggestions with pitches ready for add_notes.
    """
    _require_music21()
    from music21 import roman

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    s = _notes_to_stream(notes, key_hint=key)
    detected_key = _detect_key(s)

    # Find the last chord
    chordified = s.chordify()
    chord_list = list(chordified.recurse().getElementsByClass('Chord'))
    if not chord_list:
        return {"error": "No chords detected in clip"}

    last_chord = chord_list[-1]
    last_figure = "I"
    try:
        last_rn = roman.romanNumeralFromChord(last_chord, detected_key)
        last_figure = last_rn.romanNumeral
    except Exception:
        last_rn = None

    # Progression maps by style
    _progressions = {
        "common_practice": {
            "I": ["IV", "V", "vi", "ii"],
            "ii": ["V", "viio", "IV"],
            "iii": ["vi", "IV", "ii"],
            "IV": ["V", "I", "ii"],
            "V": ["I", "vi", "IV"],
            "vi": ["ii", "IV", "V", "I"],
            "viio": ["I", "iii"],
        },
        "jazz": {
            "I": ["IV7", "ii7", "vi7", "bVII7"],
            "ii7": ["V7", "bII7"],
            "IV7": ["V7", "#ivo7", "bVII7"],
            "V7": ["I", "vi", "bVI"],
            "vi7": ["ii7", "IV7"],
        },
        "modal": {
            "I": ["bVII", "IV", "v", "bIII"],
            "IV": ["I", "bVII", "v"],
            "v": ["bVII", "IV", "I"],
            "bVII": ["I", "IV", "v"],
            "bIII": ["IV", "bVII"],
        },
        "pop": {
            "I": ["V", "vi", "IV"],
            "ii": ["V", "IV"],
            "IV": ["I", "V", "vi"],
            "V": ["I", "vi", "IV"],
            "vi": ["IV", "V", "I"],
        },
    }

    style_map = _progressions.get(style, _progressions["common_practice"])

    # Match the last chord to the closest key in the map
    candidates = style_map.get(last_figure)
    if not candidates:
        # Try uppercase/lowercase variants
        for k in style_map:
            if k.upper() == last_figure.upper():
                candidates = style_map[k]
                break
    if not candidates:
        candidates = style_map.get("I", ["IV", "V"])

    # Build concrete suggestions with MIDI pitches
    suggestions = []
    for fig in candidates:
        try:
            rn = roman.RomanNumeral(fig, detected_key)
            suggestions.append({
                "figure": fig,
                "chord_name": rn.pitchedCommonName,
                "pitches": [str(p) for p in rn.pitches],
                "midi_pitches": [p.midi for p in rn.pitches],
                "quality": rn.quality,
            })
        except Exception:
            suggestions.append({"figure": fig, "chord_name": fig})

    return {
        "key": str(detected_key),
        "last_chord": last_rn.figure if last_rn else "unknown",
        "style": style,
        "suggestions": suggestions,
    }


# -- Tool 3: detect_theory_issues -------------------------------------------

@mcp.tool()
def detect_theory_issues(
    ctx: Context,
    track_index: int,
    clip_index: int,
    key: Optional[str] = None,
    strict: bool = False,
) -> dict:
    """Detect music theory issues: parallel fifths/octaves, out-of-key notes,
    voice crossing, unresolved dominants.

    strict=False: Only clear errors (parallels, out-of-key).
    strict=True: Also flag style issues (large leaps, missing resolution).

    Uses music21's VoiceLeadingQuartet for accurate parallel detection.
    Returns ranked issues with beat positions.
    """
    _require_music21()
    from music21 import roman, voiceLeading, note as m21note

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    s = _notes_to_stream(notes, key_hint=key)
    detected_key = _detect_key(s)
    scale_pitch_classes = set(
        p.midi % 12 for p in detected_key.getScale().getPitches()
    )

    issues = []

    # 1. Out-of-key notes
    for n in notes:
        if n.get("mute", False):
            continue
        if n["pitch"] % 12 not in scale_pitch_classes:
            issues.append({
                "type": "out_of_key",
                "severity": "warning",
                "beat": round(n["start_time"], 3),
                "detail": f"{_pitch_name(n['pitch'])} not in {detected_key}",
            })

    # 2. Parallel fifths/octaves using VoiceLeadingQuartet
    chordified = s.chordify()
    chord_list = list(chordified.recurse().getElementsByClass('Chord'))

    for i in range(1, len(chord_list)):
        prev_c = chord_list[i - 1]
        curr_c = chord_list[i]
        prev_pitches = sorted(prev_c.pitches, key=lambda p: p.midi)
        curr_pitches = sorted(curr_c.pitches, key=lambda p: p.midi)

        if len(prev_pitches) < 2 or len(curr_pitches) < 2:
            continue

        # Check outer voices (bass and soprano)
        try:
            vlq = voiceLeading.VoiceLeadingQuartet(
                prev_pitches[-1], curr_pitches[-1],  # soprano
                prev_pitches[0], curr_pitches[0],     # bass
            )
            if vlq.parallelFifth():
                issues.append({
                    "type": "parallel_fifths",
                    "severity": "error",
                    "beat": round(float(curr_c.offset), 3),
                    "detail": "Parallel fifths in outer voices",
                })
            if vlq.parallelOctave():
                issues.append({
                    "type": "parallel_octaves",
                    "severity": "error",
                    "beat": round(float(curr_c.offset), 3),
                    "detail": "Parallel octaves in outer voices",
                })
            if vlq.voiceCrossing():
                issues.append({
                    "type": "voice_crossing",
                    "severity": "warning",
                    "beat": round(float(curr_c.offset), 3),
                    "detail": "Voice crossing detected",
                })
            if strict and vlq.hiddenFifth():
                issues.append({
                    "type": "hidden_fifth",
                    "severity": "info",
                    "beat": round(float(curr_c.offset), 3),
                    "detail": "Hidden fifth in outer voices",
                })
        except Exception:
            pass

    # 3. Unresolved dominant (strict mode)
    if strict:
        for i in range(len(chord_list) - 1):
            try:
                rn = roman.romanNumeralFromChord(chord_list[i], detected_key)
                next_rn = roman.romanNumeralFromChord(
                    chord_list[i + 1], detected_key
                )
                if rn.romanNumeral in ('V', 'V7') and next_rn.romanNumeral not in (
                    'I', 'i', 'vi', 'VI'
                ):
                    issues.append({
                        "type": "unresolved_dominant",
                        "severity": "info",
                        "beat": round(float(chord_list[i].offset), 3),
                        "detail": (
                            f"{rn.figure} resolves to {next_rn.figure} "
                            f"instead of tonic"
                        ),
                    })
            except Exception:
                pass

    # 4. Large leaps without resolution (strict mode)
    if strict:
        sorted_notes = sorted(
            [n for n in notes if not n.get("mute", False)],
            key=lambda n: n["start_time"],
        )
        for i in range(1, len(sorted_notes)):
            leap = abs(sorted_notes[i]["pitch"] - sorted_notes[i - 1]["pitch"])
            if leap > 7:
                issues.append({
                    "type": "large_leap",
                    "severity": "info",
                    "beat": round(sorted_notes[i]["start_time"], 3),
                    "detail": f"{leap} semitone leap",
                })

    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda x: (severity_order.get(x["severity"], 3), x.get("beat", 0)))

    return {
        "key": str(detected_key),
        "strict_mode": strict,
        "issue_count": len(issues),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "issues": issues[:30],
    }


# -- Tool 4: identify_scale -------------------------------------------------

@mcp.tool()
def identify_scale(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """Identify the scale/mode of a MIDI clip beyond basic major/minor.

    Goes deeper than get_detected_key — uses music21's Krumhansl-Schmuckler
    algorithm with alternateInterpretations for modes (Dorian, Phrygian,
    Lydian, Mixolydian) and exotic scales.

    Returns ranked key matches with confidence scores.
    """
    _require_music21()

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    s = _notes_to_stream(notes)

    # music21's key analysis returns the best match and alternatives
    detected = s.analyze('key')

    results = [{
        "key": str(detected),
        "confidence": round(detected.correlationCoefficient, 3)
        if hasattr(detected, 'correlationCoefficient') else None,
        "mode": detected.mode,
        "tonic": str(detected.tonic),
    }]

    # Add alternatives
    if hasattr(detected, 'alternateInterpretations'):
        for alt in detected.alternateInterpretations[:7]:
            results.append({
                "key": str(alt),
                "confidence": round(alt.correlationCoefficient, 3)
                if hasattr(alt, 'correlationCoefficient') else None,
                "mode": alt.mode,
                "tonic": str(alt.tonic),
            })

    # Pitch class usage for context
    pitch_classes = defaultdict(float)
    for n in notes:
        if not n.get("mute", False):
            pitch_classes[n["pitch"] % 12] += n["duration"]

    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    pc_usage = {
        note_names[pc]: round(dur, 3)
        for pc, dur in sorted(pitch_classes.items())
    }

    return {
        "top_match": results[0] if results else None,
        "alternatives": results[1:],
        "pitch_classes_used": len(pitch_classes),
        "pitch_class_weights": pc_usage,
    }


# -- Tool 5: harmonize_melody -----------------------------------------------

@mcp.tool()
def harmonize_melody(
    ctx: Context,
    track_index: int,
    clip_index: int,
    key: Optional[str] = None,
    voices: int = 4,
) -> dict:
    """Generate a multi-voice harmonization of a melody from a MIDI clip.

    Finds diatonic chords containing each melody note and voices them
    following basic voice leading rules (smooth bass motion, no crossing).

    voices: 2 (melody + bass) or 4 (SATB). Default 4.
    Returns note data ready for add_notes on new tracks.

    Processing time: 2-5s.
    """
    _require_music21()
    from music21 import roman

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    # Use only non-muted, sorted by time
    melody = sorted(
        [n for n in notes if not n.get("mute", False)],
        key=lambda n: n["start_time"],
    )

    s = _notes_to_stream(melody, key_hint=key)
    detected_key = _detect_key(s)

    result_voices = {"soprano": [], "bass": []}
    if voices == 4:
        result_voices["alto"] = []
        result_voices["tenor"] = []

    prev_bass_midi = None

    for n in melody:
        from music21 import pitch as m21pitch
        melody_pitch = n["pitch"]
        beat = n["start_time"]
        dur = n["duration"]
        mel_pc = melody_pitch % 12

        # Find the best diatonic chord containing this pitch
        best_rn = None
        for degree in [1, 4, 5, 6, 2, 3, 7]:
            try:
                rn = roman.RomanNumeral(degree, detected_key)
                chord_pcs = [p.midi % 12 for p in rn.pitches]
                if mel_pc in chord_pcs:
                    best_rn = rn
                    break
            except Exception:
                continue

        if best_rn is None:
            # Fallback: use tonic triad
            best_rn = roman.RomanNumeral(1, detected_key)

        chord_midis = sorted([p.midi for p in best_rn.pitches])

        # Bass: root in low octave, smooth motion preferred
        bass = chord_midis[0]
        while bass > 52:
            bass -= 12
        while bass < 36:
            bass += 12
        if prev_bass_midi is not None:
            # Try octave that's closest to previous bass
            options = [bass, bass - 12, bass + 12]
            options = [b for b in options if 33 <= b <= 55]
            if options:
                bass = min(options, key=lambda b: abs(b - prev_bass_midi))
        prev_bass_midi = bass

        vel = n.get("velocity", 100)

        result_voices["soprano"].append({
            "pitch": melody_pitch, "start_time": beat,
            "duration": dur, "velocity": vel,
        })
        result_voices["bass"].append({
            "pitch": bass, "start_time": beat,
            "duration": dur, "velocity": int(vel * 0.8),
        })

        if voices == 4 and len(chord_midis) >= 2:
            # Alto: chord tone near soprano
            alto = chord_midis[1] if len(chord_midis) > 1 else chord_midis[0]
            while alto < melody_pitch - 14:
                alto += 12
            while alto >= melody_pitch:
                alto -= 12
            if alto < bass:
                alto += 12

            # Tenor: chord tone between bass and alto
            tenor = chord_midis[2] if len(chord_midis) > 2 else chord_midis[0]
            while tenor < bass:
                tenor += 12
            while tenor >= alto:
                tenor -= 12
            if tenor < bass:
                tenor = bass + (alto - bass) // 2

            result_voices["alto"].append({
                "pitch": max(36, min(96, alto)), "start_time": beat,
                "duration": dur, "velocity": int(vel * 0.7),
            })
            result_voices["tenor"].append({
                "pitch": max(36, min(96, tenor)), "start_time": beat,
                "duration": dur, "velocity": int(vel * 0.7),
            })

    result = {
        "key": str(detected_key),
        "voices": voices,
        "melody_notes": len(melody),
    }
    for voice_name, voice_notes in result_voices.items():
        if voice_notes:
            result[voice_name] = voice_notes

    return result


# -- Tool 6: generate_countermelody -----------------------------------------

@mcp.tool()
def generate_countermelody(
    ctx: Context,
    track_index: int,
    clip_index: int,
    key: Optional[str] = None,
    species: int = 1,
    range_low: int = 48,
    range_high: int = 72,
    seed: int = 0,
) -> dict:
    """Generate a countermelody using species counterpoint rules.

    species: 1 (note-against-note), 2 (2 notes per melody note).
    Follows strict rules: no parallel fifths/octaves, contrary motion
    preferred, consonant intervals on strong beats.

    Returns note data ready for add_notes on a new track.
    Processing time: 2-5s.
    """
    _require_music21()
    import random
    random.seed(seed)

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    melody = sorted(
        [n for n in notes if not n.get("mute", False)],
        key=lambda n: n["start_time"],
    )

    s = _notes_to_stream(melody, key_hint=key)
    detected_key = _detect_key(s)
    scale_pcs = [p.midi % 12 for p in detected_key.getScale().getPitches()]

    # Build pool of scale pitches in range
    pool = []
    for p in range(range_low, range_high + 1):
        if p % 12 in scale_pcs:
            pool.append(p)
    if not pool:
        return {"error": "No scale pitches in given range"}

    # Consonant intervals (semitones mod 12): P1, m3, M3, P4, P5, m6, M6, P8
    consonant = {0, 3, 4, 5, 7, 8, 9}

    counter_notes = []
    prev_cp = None

    for i, n in enumerate(melody):
        mel_pitch = n["pitch"]
        beat = n["start_time"]
        dur = n["duration"] / species

        for s_idx in range(species):
            # Score candidates
            scored = []
            for cp in pool:
                iv = abs(cp - mel_pitch) % 12
                if iv not in consonant:
                    continue

                score = 0.0

                # Contrary motion bonus
                if prev_cp is not None and i > 0:
                    mel_dir = mel_pitch - melody[i - 1]["pitch"]
                    cp_dir = cp - prev_cp
                    if (mel_dir > 0 and cp_dir < 0) or (mel_dir < 0 and cp_dir > 0):
                        score += 10
                    # Penalize parallel perfect intervals
                    if prev_cp is not None and i > 0:
                        prev_iv = abs(prev_cp - melody[i - 1]["pitch"]) % 12
                        if prev_iv == iv and iv in (0, 7):
                            score -= 50  # Hard penalty for parallel P5/P8

                # Stepwise motion bonus
                if prev_cp is not None:
                    step = abs(cp - prev_cp)
                    if step <= 2:
                        score += 5
                    elif step <= 4:
                        score += 2
                    elif step > 7:
                        score -= 3
                else:
                    score += 3

                # Small random variation for musicality
                score += random.uniform(0, 2)
                scored.append((cp, score))

            if not scored:
                # Fallback: pick any pool note
                scored = [(random.choice(pool), 0)]

            scored.sort(key=lambda x: -x[1])
            chosen = scored[0][0]

            counter_notes.append({
                "pitch": chosen,
                "start_time": round(beat + s_idx * dur, 4),
                "duration": round(dur, 4),
                "velocity": 80 if s_idx == 0 else 65,
            })
            prev_cp = chosen

    return {
        "key": str(detected_key),
        "species": species,
        "melody_notes": len(melody),
        "counter_notes": counter_notes,
        "counter_note_count": len(counter_notes),
        "range": f"{_pitch_name(range_low)}-{_pitch_name(range_high)}",
        "seed": seed,
    }


# -- Tool 7: transpose_smart ------------------------------------------------

@mcp.tool()
def transpose_smart(
    ctx: Context,
    track_index: int,
    clip_index: int,
    target_key: str,
    mode: str = "diatonic",
) -> dict:
    """Transpose a MIDI clip to a new key with musical intelligence.

    mode:
    - diatonic: Maps scale degrees (C major -> G major keeps intervals
      relative to the scale). Chromatic notes shift by tonic distance.
    - chromatic: Simple semitone shift (preserves exact intervals).

    Returns transposed note data ready for add_notes or modify_notes.
    """
    _require_music21()
    from music21 import pitch as m21pitch

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    s = _notes_to_stream(notes)
    source_key = _detect_key(s)

    try:
        target = _parse_key_string(target_key)
    except Exception:
        return {"error": f"Invalid target key: {target_key}"}

    source_tonic = m21pitch.Pitch(str(source_key.tonic))
    target_tonic = m21pitch.Pitch(str(target.tonic))
    semitone_shift = target_tonic.midi - source_tonic.midi

    if mode == "chromatic":
        transposed = []
        for n in notes:
            tn = dict(n)
            new_pitch = n["pitch"] + semitone_shift
            tn["pitch"] = max(0, min(127, new_pitch))
            transposed.append(tn)
    else:
        # Diatonic: map scale degrees
        source_scale = source_key.getScale().getPitches()
        target_scale = target.getScale().getPitches()
        source_pcs = [p.midi % 12 for p in source_scale]
        target_pcs = [p.midi % 12 for p in target_scale]

        degree_map = {}
        for i in range(min(len(source_pcs), len(target_pcs))):
            degree_map[source_pcs[i]] = target_pcs[i]

        transposed = []
        for n in notes:
            tn = dict(n)
            pc = n["pitch"] % 12
            octave = n["pitch"] // 12

            if pc in degree_map:
                new_pc = degree_map[pc]
                # Calculate octave adjustment from tonic shift
                new_pitch = octave * 12 + new_pc
                # Adjust if the shift crossed an octave boundary
                if abs(new_pitch - (n["pitch"] + semitone_shift)) > 6:
                    if new_pitch < n["pitch"] + semitone_shift:
                        new_pitch += 12
                    else:
                        new_pitch -= 12
            else:
                # Chromatic note: shift by tonic distance
                new_pitch = n["pitch"] + semitone_shift

            tn["pitch"] = max(0, min(127, new_pitch))
            transposed.append(tn)

    return {
        "source_key": str(source_key),
        "target_key": str(target),
        "mode": mode,
        "semitone_shift": semitone_shift,
        "note_count": len(transposed),
        "notes": transposed,
    }

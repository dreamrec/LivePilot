"""Music theory tools — pure Python, zero dependencies.

7 tools for harmonic analysis, chord suggestion, voice leading detection,
counterpoint generation, scale identification, harmonization, and intelligent
transposition — all working directly on live session clip data via get_notes.

Design principle: tools compute from data, the LLM interprets and explains.
Returns precise musical data (Roman numerals, pitch names, intervals), never
explanations the LLM already knows from training.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import _theory_engine as engine


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


def _detect_or_parse_key(notes: list[dict], key_hint: str | None = None) -> dict:
    """Detect key from notes, or parse the user's hint."""
    if key_hint:
        try:
            return engine.parse_key(key_hint)
        except ValueError:
            pass
    return engine.detect_key(notes)


def _key_display(key_info: dict) -> str:
    """Format key info as 'C major' string."""
    return f"{key_info['tonic_name']} {key_info['mode'].replace('_', ' ')}"


def _mode_display(mode: str) -> str:
    """Format a canonical mode id for user-facing output."""
    return mode.replace("_", " ")


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
    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip", "suggestion": "Add notes first"}

    key_info = _detect_or_parse_key(notes, key_hint=key)
    tonic = key_info["tonic"]
    mode = key_info["mode"]

    chord_groups = engine.chordify(notes)
    chords = []

    for group in chord_groups:
        pitches = group["pitches"]
        pcs = group["pitch_classes"]

        rn = engine.roman_numeral(pcs, tonic, mode)
        cn = engine.chord_name(pitches)

        entry = {
            "beat": group["beat"],
            "duration": group["duration"],
            "pitches": [engine.pitch_name(p) for p in pitches],
            "midi_pitches": pitches,
            "chord_name": cn,
            "roman_numeral": rn["figure"],
            "figure": rn["figure"],
            "quality": rn["quality"],
            "inversion": rn["inversion"],
            "scale_degree": rn["degree"] + 1,
        }
        chords.append(entry)

    progression = " - ".join(c.get("figure", "?") for c in chords[:24])

    key_result = {
        "key": _key_display(key_info),
        "confidence": key_info.get("confidence"),
    }
    if "alternatives" in key_info:
        key_result["alternatives"] = [
            f"{a['tonic_name']} {a['mode']}" for a in key_info["alternatives"][:3]
        ]

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        **key_result,
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
    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    key_info = _detect_or_parse_key(notes, key_hint=key)
    tonic = key_info["tonic"]
    mode = key_info["mode"]

    chord_groups = engine.chordify(notes)
    if not chord_groups:
        return {"error": "No chords detected in clip"}

    # Analyze last chord
    last_group = chord_groups[-1]
    last_rn = engine.roman_numeral(last_group["pitch_classes"], tonic, mode)
    last_figure = last_rn["figure"]

    # Progression maps by style — separate major/minor variants where needed.
    # Minor key maps use lowercase i for tonic and scale-derived numerals.
    _progressions_major = {
        "common_practice": {
            "I": ["IV", "V", "vi", "ii"],
            "ii": ["V", "vii\u00b0", "IV"],
            "iii": ["vi", "IV", "ii"],
            "IV": ["V", "I", "ii"],
            "V": ["I", "vi", "IV"],
            "vi": ["ii", "IV", "V", "I"],
            "vii\u00b0": ["I", "iii"],
        },
        "jazz": {
            "I": ["IV7", "ii7", "vi7", "V7"],
            "ii7": ["V7", "IV7"],
            "IV7": ["V7", "I", "ii7"],
            "V7": ["I", "vi", "IV"],
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
    _progressions_minor = {
        "common_practice": {
            "i": ["iv", "v", "VI", "III"],
            "ii\u00b0": ["v", "VII", "iv"],
            "III": ["VI", "iv", "VII"],
            "iv": ["v", "i", "VII"],
            "v": ["i", "VI", "iv"],
            "VI": ["iv", "ii\u00b0", "v", "VII"],
            "VII": ["III", "i"],
        },
        "jazz": {
            "i": ["iv7", "v", "VI7", "VII7"],
            "i7": ["iv7", "v", "VI7", "VII7"],
            "ii\u00b07": ["v", "VII7"],
            "iv7": ["VII7", "v", "i"],
            "v": ["i", "VI", "iv"],
            "VI7": ["ii\u00b07", "iv7", "VII7"],
            "VImaj7": ["ii\u00b07", "iv7", "VII7"],
            "VII7": ["III", "i", "VI"],
        },
        "modal": {
            "i": ["VII", "iv", "v", "III"],
            "iv": ["i", "VII", "v"],
            "v": ["VII", "iv", "i"],
            "VII": ["i", "iv", "v"],
            "III": ["iv", "VII"],
        },
        "pop": {
            "i": ["VII", "VI", "iv"],
            "iv": ["i", "VII", "VI"],
            "v": ["i", "VI", "iv"],
            "VI": ["iv", "VII", "i"],
            "VII": ["i", "VI", "III"],
        },
    }

    # Select the right map based on mode
    is_minor = mode in ("minor", "dorian", "phrygian", "aeolian",
                        "phrygian_dominant")
    prog_set = _progressions_minor if is_minor else _progressions_major
    style_map = prog_set.get(style, prog_set.get("common_practice", {}))

    # Match the last chord to the closest key in the map
    candidates = style_map.get(last_figure)
    if not candidates:
        for k in style_map:
            if k.upper() == last_figure.upper():
                candidates = style_map[k]
                break
    if not candidates:
        # BUG-B23: the old fallback hard-coded ["IV", "V"] — uppercase
        # literals that lie about chord quality in a minor key (where
        # both iv and v are minor triads). Pick the tonic key ("i" in
        # minor, "I" in major) and let the style_map's own conventions
        # populate a minor-appropriate default when available.
        tonic_key = "i" if is_minor else "I"
        candidates = style_map.get(tonic_key)
        if not candidates:
            candidates = ["iv", "v"] if is_minor else ["IV", "V"]

    # Build concrete suggestions with MIDI pitches
    suggestions = []
    for fig in candidates:
        result = engine.roman_figure_to_pitches(fig, tonic, mode)
        if "error" not in result:
            suggestions.append({
                "figure": fig,
                "chord_name": engine.chord_name(result["midi_pitches"]),
                "pitches": result["pitches"],
                "midi_pitches": result["midi_pitches"],
                "quality": result["quality"],
            })
        else:
            suggestions.append({"figure": fig, "chord_name": fig})

    return {
        "key": _key_display(key_info),
        "last_chord": last_figure,
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

    Returns ranked issues with beat positions.
    """
    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    key_info = _detect_or_parse_key(notes, key_hint=key)
    tonic = key_info["tonic"]
    mode = key_info["mode"]
    scale_pcs = set(engine.get_scale_pitches(tonic, mode))

    issues = []

    # 1. Out-of-key notes
    for n in notes:
        if n.get("mute", False):
            continue
        if n["pitch"] % 12 not in scale_pcs:
            issues.append({
                "type": "out_of_key",
                "severity": "warning",
                "beat": round(n["start_time"], 3),
                "detail": f"{engine.pitch_name(n['pitch'])} not in {_key_display(key_info)}",
            })

    # 2. Parallel fifths/octaves and voice crossing
    chord_groups = engine.chordify(notes)
    for i in range(1, len(chord_groups)):
        prev_pitches = chord_groups[i - 1]["pitches"]
        curr_pitches = chord_groups[i]["pitches"]
        beat = chord_groups[i]["beat"]

        vl_issues = engine.check_voice_leading(prev_pitches, curr_pitches)
        for vl in vl_issues:
            severity = "error" if vl["type"] in ("parallel_fifths", "parallel_octaves") else "warning"
            if vl["type"] == "hidden_fifth":
                severity = "info"
                if not strict:
                    continue
            detail_map = {
                "parallel_fifths": "Parallel fifths in outer voices",
                "parallel_octaves": "Parallel octaves in outer voices",
                "voice_crossing": "Voice crossing detected",
                "hidden_fifth": "Hidden fifth in outer voices",
            }
            issues.append({
                "type": vl["type"],
                "severity": severity,
                "beat": round(beat, 3),
                "detail": detail_map.get(vl["type"], vl["type"]),
            })

    # 3. Unresolved dominant (strict mode)
    if strict:
        for i in range(len(chord_groups) - 1):
            rn = engine.roman_numeral(chord_groups[i]["pitch_classes"], tonic, mode)
            next_rn = engine.roman_numeral(chord_groups[i + 1]["pitch_classes"], tonic, mode)
            if rn["figure"] in ('V', 'V7') and next_rn["figure"] not in ('I', 'i', 'vi', 'VI'):
                issues.append({
                    "type": "unresolved_dominant",
                    "severity": "info",
                    "beat": round(chord_groups[i]["beat"], 3),
                    "detail": f"{rn['figure']} resolves to {next_rn['figure']} instead of tonic",
                })

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
        "key": _key_display(key_info),
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

    Uses Krumhansl-Schmuckler-style profiles with 8 mode profiles (major,
    minor, dorian, phrygian, lydian, mixolydian, locrian, and phrygian
    dominant / Hijaz).

    Returns ranked key matches with confidence scores.
    """
    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    detected = engine.detect_key(notes, mode_detection=True)

    results = [{
        "key": f"{detected['tonic_name']} {_mode_display(detected['mode'])}",
        "confidence": detected["confidence"],
        "mode": _mode_display(detected["mode"]),
        "mode_id": detected["mode"],
        "tonic": detected["tonic_name"],
    }]

    for alt in detected.get("alternatives", [])[:7]:
        results.append({
            "key": f"{alt['tonic_name']} {_mode_display(alt['mode'])}",
            "confidence": alt["confidence"],
            "mode": _mode_display(alt["mode"]),
            "mode_id": alt["mode"],
            "tonic": alt["tonic_name"],
        })

    # Pitch class usage for context
    pitch_classes = defaultdict(float)
    for n in notes:
        if not n.get("mute", False):
            pitch_classes[n["pitch"] % 12] += n["duration"]

    pc_usage = {
        engine.NOTE_NAMES[pc]: round(dur, 3)
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
    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    melody = sorted(
        [n for n in notes if not n.get("mute", False)],
        key=lambda n: n["start_time"],
    )

    key_info = _detect_or_parse_key(melody, key_hint=key)
    tonic = key_info["tonic"]
    mode = key_info["mode"]

    result_voices = {"soprano": [], "bass": []}
    if voices == 4:
        result_voices["alto"] = []
        result_voices["tenor"] = []

    prev_bass_midi = None

    for n in melody:
        melody_pitch = n["pitch"]
        beat = n["start_time"]
        dur = n["duration"]
        mel_pc = melody_pitch % 12

        # Find the best diatonic chord containing this pitch
        best_chord = None
        for degree in [0, 3, 4, 5, 1, 2, 6]:  # I, IV, V, vi, ii, iii, vii
            chord = engine.build_chord(degree, tonic, mode)
            if mel_pc in chord["pitch_classes"]:
                best_chord = chord
                break

        if best_chord is None:
            best_chord = engine.build_chord(0, tonic, mode)

        # Build MIDI pitches for the chord
        chord_midis = sorted([
            60 + ((pc - best_chord["root_pc"]) % 12) + best_chord["root_pc"]
            for pc in best_chord["pitch_classes"]
        ])

        # Bass: root in low octave, smooth motion preferred
        bass = 36 + best_chord["root_pc"]
        if bass > 52:
            bass -= 12
        if bass < 36:
            bass += 12
        if prev_bass_midi is not None:
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
        "key": _key_display(key_info),
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
    random.seed(seed)

    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    melody = sorted(
        [n for n in notes if not n.get("mute", False)],
        key=lambda n: n["start_time"],
    )

    key_info = _detect_or_parse_key(melody, key_hint=key)
    scale_pcs = set(engine.get_scale_pitches(key_info["tonic"], key_info["mode"]))

    # Build pool of scale pitches in range
    pool = [p for p in range(range_low, range_high + 1) if p % 12 in scale_pcs]
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
                    prev_iv = abs(prev_cp - melody[i - 1]["pitch"]) % 12
                    if prev_iv == iv and iv in (0, 7):
                        score -= 50

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

                score += random.uniform(0, 2)
                scored.append((cp, score))

            if not scored:
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
        "key": _key_display(key_info),
        "species": species,
        "melody_notes": len(melody),
        "counter_notes": counter_notes,
        "counter_note_count": len(counter_notes),
        "range": f"{engine.pitch_name(range_low)}-{engine.pitch_name(range_high)}",
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
    notes = _get_clip_notes(ctx, track_index, clip_index)
    if not notes:
        return {"error": "No notes in clip"}

    source_key = engine.detect_key(notes)

    try:
        target = engine.parse_key(target_key)
    except ValueError:
        return {"error": f"Invalid target key: {target_key}"}

    source_tonic = source_key["tonic"]
    target_tonic = target["tonic"]
    # Compute nearest-path semitone shift (never more than ±6)
    raw_shift = target_tonic - source_tonic
    if raw_shift > 6:
        semitone_shift = raw_shift - 12
    elif raw_shift < -6:
        semitone_shift = raw_shift + 12
    else:
        semitone_shift = raw_shift

    if mode == "chromatic":
        transposed = []
        for n in notes:
            tn = dict(n)
            new_pitch = n["pitch"] + semitone_shift
            tn["pitch"] = max(0, min(127, new_pitch))
            transposed.append(tn)
    else:
        # Diatonic: map scale degrees
        source_mode = source_key["mode"]
        target_mode = target.get("mode", source_mode)
        source_pcs = engine.get_scale_pitches(source_tonic, source_mode)
        target_pcs = engine.get_scale_pitches(target_tonic, target_mode)

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
                new_pitch = octave * 12 + new_pc
                # Adjust if the shift crossed an octave boundary
                if abs(new_pitch - (n["pitch"] + semitone_shift)) > 6:
                    if new_pitch < n["pitch"] + semitone_shift:
                        new_pitch += 12
                    else:
                        new_pitch -= 12
            else:
                new_pitch = n["pitch"] + semitone_shift

            tn["pitch"] = max(0, min(127, new_pitch))
            transposed.append(tn)

    return {
        "source_key": _key_display(source_key),
        "target_key": f"{engine.NOTE_NAMES[target_tonic]} {target.get('mode', 'major')}",
        "mode": mode,
        "semitone_shift": semitone_shift,
        "note_count": len(transposed),
        "notes": transposed,
    }

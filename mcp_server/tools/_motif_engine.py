"""Motif Engine — pattern detection and transformation for musical motifs.

Detects recurring melodic and rhythmic patterns across clips, scores them
for salience and fatigue risk, and provides transformation operations
(inversion, augmentation, register shift, fragmentation).

Zero external dependencies beyond stdlib.
Design: spec at docs/COMPOSITION_ENGINE_V1.md, sections 7.5, 10.4, 11.3.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Motif Data Structures ─────────────────────────────────────────────

@dataclass
class MotifUnit:
    """A recurring musical pattern detected across clips."""
    motif_id: str
    kind: str  # "melodic", "rhythmic", "intervallic"
    intervals: list[int]  # relative intervals (semitones between consecutive notes)
    rhythm: list[float]  # relative durations (ratios)
    representative_pitches: list[int]  # first occurrence's actual pitches
    occurrences: list[dict] = field(default_factory=list)  # [{track, clip, start_bar}]
    salience: float = 0.0  # 0-1, how distinctive/memorable
    fatigue_risk: float = 0.0  # 0-1, risk of overuse
    suggested_developments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Pattern Extraction ────────────────────────────────────────────────

def _extract_intervals(notes: list[dict]) -> list[int]:
    """Extract pitch intervals between consecutive notes (sorted by start_time)."""
    if len(notes) < 2:
        return []
    sorted_notes = sorted(notes, key=lambda n: n.get("start_time", 0))
    return [
        sorted_notes[i + 1].get("pitch", 0) - sorted_notes[i].get("pitch", 0)
        for i in range(len(sorted_notes) - 1)
    ]


def _extract_rhythm(notes: list[dict]) -> list[float]:
    """Extract rhythm pattern as duration ratios (normalized to first note)."""
    if not notes:
        return []
    sorted_notes = sorted(notes, key=lambda n: n.get("start_time", 0))
    durations = [n.get("duration", 0.5) for n in sorted_notes]
    base = durations[0] if durations[0] > 0 else 0.5
    return [round(d / base, 2) for d in durations]


def _find_recurring_subsequences(
    intervals: list[int],
    min_length: int = 3,
    max_length: int = 8,
) -> list[tuple[tuple[int, ...], list[int]]]:
    """Find recurring interval subsequences and their start positions.

    Returns list of (pattern_tuple, [start_indices]).
    """
    if len(intervals) < min_length:
        return []

    pattern_positions: dict[tuple[int, ...], list[int]] = {}

    for length in range(min_length, min(max_length + 1, len(intervals) + 1)):
        for start in range(len(intervals) - length + 1):
            pattern = tuple(intervals[start:start + length])
            pattern_positions.setdefault(pattern, []).append(start)

    # Filter to patterns that occur at least twice
    return [
        (pattern, positions)
        for pattern, positions in pattern_positions.items()
        if len(positions) >= 2
    ]


def _score_salience(pattern: tuple[int, ...], occurrence_count: int, total_notes: int) -> float:
    """Score how memorable/distinctive a pattern is.

    Higher salience for: longer patterns, more variety, moderate occurrence count.
    """
    length_score = min(1.0, len(pattern) / 8.0)

    # Interval variety (unique intervals / total intervals)
    unique_intervals = len(set(pattern))
    variety_score = unique_intervals / max(len(pattern), 1)

    # Occurrence: too few = obscure, too many = boring
    occurrence_ratio = occurrence_count / max(total_notes / len(pattern), 1)
    occurrence_score = min(1.0, occurrence_ratio * 2) * (1.0 - min(1.0, occurrence_ratio * 0.5))

    return round(min(1.0, (length_score * 0.3 + variety_score * 0.4 + occurrence_score * 0.3)), 3)


def _score_fatigue(occurrence_count: int, total_bars: int) -> float:
    """Score risk of listener fatigue from repetition.

    Higher fatigue for: high occurrence count relative to total length.
    """
    if total_bars <= 0:
        return 0.0
    density = occurrence_count / total_bars
    return round(min(1.0, density * 2), 3)


def _suggest_developments(motif: MotifUnit) -> list[str]:
    """Suggest musical transformations based on motif properties."""
    suggestions = []

    if motif.fatigue_risk > 0.5:
        suggestions.append("rhythmic_variation")
        suggestions.append("register_shift")

    if len(motif.intervals) >= 4:
        suggestions.append("fragmentation")
        suggestions.append("inversion")

    if all(abs(i) <= 2 for i in motif.intervals):
        suggestions.append("register_shift_up")  # Stepwise motion → try a leap

    if any(abs(i) >= 5 for i in motif.intervals):
        suggestions.append("augmentation")  # Has leaps → try slowing down

    if motif.salience > 0.6:
        suggestions.append("answer_phrase")
        suggestions.append("orchestral_reassignment")

    if not suggestions:
        suggestions.append("register_shift")

    return suggestions


# ── Motif Detection ───────────────────────────────────────────────────

def detect_motifs(
    notes_by_track: dict[int, list[dict]],
    total_bars: int = 32,
    min_pattern_length: int = 3,
    max_pattern_length: int = 8,
) -> list[MotifUnit]:
    """Detect recurring musical patterns across all tracks.

    notes_by_track: {track_index: [note dicts with pitch, start_time, duration]}
    total_bars: approximate total length for fatigue scoring
    Returns: list of MotifUnit sorted by salience (most memorable first)
    """
    # Collect all intervals per track
    all_patterns: dict[tuple[int, ...], list[dict]] = {}
    total_note_count = 0

    for track_idx, notes in notes_by_track.items():
        if not notes:
            continue
        total_note_count += len(notes)
        intervals = _extract_intervals(notes)

        # Find recurring subsequences in this track
        recurring = _find_recurring_subsequences(
            intervals, min_pattern_length, max_pattern_length,
        )

        for pattern, positions in recurring:
            if pattern not in all_patterns:
                all_patterns[pattern] = []
            sorted_notes = sorted(notes, key=lambda n: n.get("start_time", 0))
            for pos in positions:
                start_time = sorted_notes[pos].get("start_time", 0) if pos < len(sorted_notes) else 0
                all_patterns[pattern].append({
                    "track": track_idx,
                    "start_position": pos,
                    "start_time": start_time,
                })

    # Also check for cross-track patterns
    all_intervals_flat: list[tuple[int, list[int], int]] = []
    for track_idx, notes in notes_by_track.items():
        intervals = _extract_intervals(notes)
        if intervals:
            all_intervals_flat.append((track_idx, intervals, len(notes)))

    # Build motif objects
    motifs = []
    seen_patterns: set[tuple[int, ...]] = set()

    for pattern, occurrences in sorted(all_patterns.items(), key=lambda x: -len(x[1])):
        # Skip sub-patterns of already-found patterns
        if any(pattern != seen and _is_subsequence(pattern, seen) for seen in seen_patterns):
            continue

        salience = _score_salience(pattern, len(occurrences), total_note_count)
        fatigue = _score_fatigue(len(occurrences), total_bars)

        # Get representative pitches + inter-onset intervals from first occurrence.
        # Rhythm is the list of start_time deltas between successive notes in
        # the pattern window; until v1.10.9 this field was left empty with a
        # "TODO: Phase 3" marker, which is what forced Hook Hunter's rhythm
        # side to fall back to drum-track-name regex. Populating it here lets
        # downstream code actually reason about rhythmic distinctiveness.
        first_occ = occurrences[0] if occurrences else {}
        first_track = first_occ.get("track", 0)
        first_pos = first_occ.get("start_position", 0)
        rep_pitches: list[int] = []
        rhythm_intervals: list[float] = []
        if first_track in notes_by_track:
            sorted_notes = sorted(notes_by_track[first_track],
                                  key=lambda n: n.get("start_time", 0))
            span = min(len(pattern) + 1, len(sorted_notes) - first_pos)
            rep_pitches = [
                sorted_notes[first_pos + j].get("pitch", 60)
                for j in range(span)
            ]
            rhythm_intervals = [
                round(
                    float(sorted_notes[first_pos + j + 1].get("start_time", 0.0))
                    - float(sorted_notes[first_pos + j].get("start_time", 0.0)),
                    4,
                )
                for j in range(span - 1)
            ]

        motif = MotifUnit(
            motif_id=f"motif_{len(motifs):03d}",
            kind="melodic" if any(abs(i) > 0 for i in pattern) else "rhythmic",
            intervals=list(pattern),
            rhythm=rhythm_intervals,
            representative_pitches=rep_pitches,
            occurrences=occurrences,
            salience=salience,
            fatigue_risk=fatigue,
        )
        motif.suggested_developments = _suggest_developments(motif)
        motifs.append(motif)
        seen_patterns.add(pattern)

        if len(motifs) >= 10:
            break  # Cap at 10 most significant motifs

    # Sort by salience
    motifs.sort(key=lambda m: -m.salience)
    return motifs


def _is_subsequence(short: tuple, long: tuple) -> bool:
    """Check if short is a contiguous subsequence of long."""
    if len(short) >= len(long):
        return False
    for i in range(len(long) - len(short) + 1):
        if long[i:i + len(short)] == short:
            return True
    return False


# ── Motif Transformations ─────────────────────────────────────────────

def transform_motif(
    motif: MotifUnit,
    transformation: str,
    reference_pitch: int = 60,
) -> list[dict]:
    """Apply a musical transformation to a motif, returning new notes.

    transformation: "inversion", "augmentation", "diminution",
                    "fragmentation", "register_shift_up", "register_shift_down",
                    "retrograde"
    reference_pitch: base pitch for the output (default: C4=60)
    Returns: list of note dicts ready for add_notes
    """
    if not motif.representative_pitches:
        return []

    pitches = motif.representative_pitches
    intervals = motif.intervals

    if transformation == "inversion":
        # Flip intervals: up becomes down
        new_intervals = [-i for i in intervals]
        return _intervals_to_notes(new_intervals, reference_pitch)

    elif transformation == "retrograde":
        # Reverse the interval sequence
        new_intervals = list(reversed(intervals))
        return _intervals_to_notes(new_intervals, reference_pitch)

    elif transformation == "augmentation":
        # Double the duration of each note
        return _intervals_to_notes(intervals, reference_pitch, duration_multiplier=2.0)

    elif transformation == "diminution":
        # Halve the duration
        return _intervals_to_notes(intervals, reference_pitch, duration_multiplier=0.5)

    elif transformation == "fragmentation":
        # Take only the first half of the motif
        half = max(1, len(intervals) // 2)
        return _intervals_to_notes(intervals[:half], reference_pitch)

    elif transformation == "register_shift_up":
        # Transpose up an octave
        return _intervals_to_notes(intervals, reference_pitch + 12)

    elif transformation == "register_shift_down":
        # Transpose down an octave
        return _intervals_to_notes(intervals, reference_pitch - 12)

    elif transformation == "orchestral_reassignment":
        # Redistribute across a wider register — odd notes up, even notes down
        # Creates an interleaved texture from a single-voice motif
        notes = _intervals_to_notes(intervals, reference_pitch)
        for i, note in enumerate(notes):
            if i % 2 == 0:
                note["pitch"] = max(0, min(127, note["pitch"] + 7))  # Up a fifth
            else:
                note["pitch"] = max(0, min(127, note["pitch"] - 5))  # Down a fourth
            note["velocity"] = max(40, min(127, note["velocity"] + (10 if i % 2 == 0 else -10)))
        return notes

    else:
        raise ValueError(
            f"Unknown transformation '{transformation}'. Valid: "
            "inversion, retrograde, augmentation, diminution, fragmentation, "
            "register_shift_up, register_shift_down, orchestral_reassignment"
        )


def _intervals_to_notes(
    intervals: list[int],
    start_pitch: int = 60,
    duration_multiplier: float = 1.0,
    base_duration: float = 0.5,
    base_velocity: int = 80,
) -> list[dict]:
    """Convert interval sequence to note dicts."""
    notes = []
    current_pitch = start_pitch
    current_time = 0.0
    duration = base_duration * duration_multiplier

    notes.append({
        "pitch": current_pitch,
        "start_time": current_time,
        "duration": duration,
        "velocity": base_velocity,
    })

    for interval in intervals:
        current_pitch += interval
        current_time += duration
        notes.append({
            "pitch": max(0, min(127, current_pitch)),
            "start_time": round(current_time, 4),
            "duration": duration,
            "velocity": base_velocity,
        })

    return notes

"""Pure-Python helpers for clip-length and note-range invariants.

Importable outside Ableton (no `_Framework` dependency, no `import Live`).
The main `clips.py` and `notes.py` modules re-import these helpers so
both the live handler and the contract tests run identical logic.

Bug context: `clip_slot.create_clip(length)` in Live 12 sets the clip's
*length* but defaults `loop_end` to length/2 in some configurations
(depends on time signature defaults). Downstream tools that add notes
beyond the implicit half-length loop see them silently dropped — silent
data corruption. These helpers centralize the "loop_end must equal
intent" rule so it can't drift back.
"""

from __future__ import annotations


def _required_loop_end(notes) -> float:
    """Return the largest start_time + duration across the notes list.

    Pure function. Used by `add_notes` to decide whether to extend the
    clip's loop_end before adding the notes — Live silently drops notes
    that fall outside [loop_start, loop_end).

    Returns 0.0 for an empty list. Defensively treats missing duration
    as 0 so a malformed note (start_time only) doesn't raise.
    """
    if not notes:
        return 0.0
    return max(
        float(n.get("start_time", 0.0)) + float(n.get("duration", 0.0))
        for n in notes
    )


def _apply_clip_length_invariants(clip, length: float) -> dict:
    """Force a freshly-created clip's loop_end + end_marker to match length.

    Mutates `clip` in place. Returns a dict suitable for inclusion in a
    handler response (`{loop_end, end_marker}`). Catches AttributeError
    and RuntimeError defensively — some Live builds enforce
    `loop_end <= sample_length` on audio clips, but for MIDI this should
    always succeed. On failure, returns the actual current values so the
    caller can surface the discrepancy.
    """
    try:
        clip.loop_end = length
    except (AttributeError, RuntimeError):
        pass
    try:
        clip.end_marker = length
    except (AttributeError, RuntimeError):
        pass

    return {
        "loop_end": getattr(clip, "loop_end", None),
        "end_marker": getattr(clip, "end_marker", None),
    }


def _extend_loop_end_for_notes(clip, notes) -> float | None:
    """If any incoming note exceeds clip.loop_end, extend it to fit.

    Returns the new loop_end value if extended, or None if no extension
    was needed. Also updates `end_marker` to keep them aligned (Live
    treats end_marker as the "stop reading" marker when looping is off).
    """
    required = _required_loop_end(notes)
    current = getattr(clip, "loop_end", 0.0)
    if required <= current:
        return None

    try:
        clip.loop_end = required
    except (AttributeError, RuntimeError):
        return None

    try:
        # Keep end_marker at least as far out as loop_end. Don't shrink
        # it if the user has set it further out manually.
        existing_end = getattr(clip, "end_marker", required)
        clip.end_marker = max(existing_end, required)
    except (AttributeError, RuntimeError):
        pass

    return required

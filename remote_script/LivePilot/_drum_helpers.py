"""Pure-Python helpers for Drum Rack chain operations.

Importable outside Ableton (no `_Framework` dependency, no `import Live`).
The main `devices.py` module re-imports these helpers so the live
handler and contract tests run identical logic.

BUG-2026-04-22 #13 context: Live's `RackDevice.insert_chain()` always
defaults the new chain's `in_note` to 36 — same as every previous chain.
Repeated inserts pile up multiple chains on note 36 ("Multi") and they
can't be triggered independently from a MIDI pattern. The helper here
picks the next free MIDI slot above any existing chain so each
insert_rack_chain call lands on a distinct pad.
"""

from __future__ import annotations


def _next_drum_chain_note(device):
    """Pick the next MIDI note for a new Drum Rack chain.

    Walks existing drum-rack chains, returns max(in_note) + 1 clamped to
    127. Returns 36 (standard kick slot) if the rack has no chains yet.
    Returns None if the device is not a drum rack — chains without an
    `in_note` attribute mean it's an Instrument or Audio Effect Rack,
    where pad-note assignment doesn't apply.

    Pure function — `device` only needs `.chains` (iterable) and each
    chain only needs `.in_note` (int). Tests pass plain Python objects.
    """
    chains = list(getattr(device, "chains", []) or [])
    in_notes = []
    for chain in chains:
        try:
            in_notes.append(int(chain.in_note))
        except (AttributeError, TypeError, ValueError):
            # Non-drum rack chains don't have in_note — bail.
            return None
    if not in_notes:
        return 36  # standard kick slot for the first chain
    return min(127, max(in_notes) + 1)

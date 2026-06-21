# Logic to Ableton MIDI Sanitizer

Use this outside Logic when a Logic-exported `.mid` imports into Ableton with
an empty lead-in bar, missing notes, tiny notes, or zero-length repeated notes.

## One File

```bash
python3 ableton-tutor/scripts/sanitize_logic_midi_for_ableton.py /path/to/file.mid
```

This writes a cleaned copy next to the original:

```text
file-ableton.mid
```

Drag the `-ableton.mid` copy into Ableton.

By default, the cleaned copy also trims leading silence before the first note.
This removes the common one-empty-bar Logic export offset.

## Folder of MIDI Exports

```bash
python3 ableton-tutor/scripts/sanitize_logic_midi_for_ableton.py /path/to/midi-folder --output-dir /path/to/cleaned-midi
```

For folders inside folders:

```bash
python3 ableton-tutor/scripts/sanitize_logic_midi_for_ableton.py /path/to/midi-folder --recursive --output-dir /path/to/cleaned-midi
```

## What It Fixes

- Repeated notes where Logic writes same-pitch Note On and Note Off events at
  the same tick.
- Cases where the Note On is written before the previous Note Off.
- Same-pitch overlaps on the same MIDI channel.
- The empty lead-in before the first note.

By default it shortens repeated notes by `1` MIDI tick. That is enough to make
Ableton import them as separate notes without changing the feel.

To keep the original lead-in bar:

```bash
python3 ableton-tutor/scripts/sanitize_logic_midi_for_ableton.py /path/to/file.mid --preserve-leading-silence
```

Use this only on copies or exported MIDI files. The script does not overwrite
the input unless you explicitly choose the same output path, which it refuses.

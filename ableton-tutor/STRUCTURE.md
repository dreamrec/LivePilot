# Ableton Tutor Structure

This folder is a macOS-only lookup wiki generated from `../live12-manual-en.pdf`.

## Lookup flow

1. Search `index.md` and `lookups/where-to-look.md` for the topic.
2. Search `lookups/mac-keyboard-shortcuts.md` for key commands.
3. Search `lookups/topic-index.md` for manual section names and source pages.
4. Read the relevant file in `chapters/`.
5. Answer with macOS commands only. Omit other-platform shortcuts.

## Folders

- `chapters/` - generated chapter-level Markdown, macOS-normalized.
- `lookups/` - compact answer surfaces for fast question answering.
- `data/` - machine-readable helper indexes.
- `sources/` - source notes and generation metadata.
- `scripts/` - repeatable extraction scripts.

## Regeneration

Run:

```bash
python3 ableton-tutor/scripts/build_ableton_tutor.py
```

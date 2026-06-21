# Arrangement Window Fast Guide

Mac-only notes for fast editing in Arrangement View.

## Get Oriented

| Task | Action |
|---|---|
| Switch Session/Arrangement | `Tab` |
| Focus Arrangement for key commands | `Option 2` |
| Fit whole arrangement width | `W` |
| Fit track height | `H` |
| Zoom to selection | `Z` |
| Zoom back | `X` |
| Zoom time in/out | `+` / `-` |
| Return play position to start | double-click Stop |

## Select Quickly

| Task | Action |
|---|---|
| Select all in focused area | `Cmd A` |
| Add individual clips | `Shift-click` |
| Add non-adjacent clips | `Cmd-click` |
| Select time across one lane | drag in a track lane |
| Select time across all tracks | hold `Shift` while selecting time |

`Cmd A` depends on focus. If it selects notes, the MIDI editor is focused. Click the Arrangement or press `Option 2`, then try again.

## Drag Without Fighting Live

| Goal | Action |
|---|---|
| Move a whole clip | drag the colored clip title bar |
| Select time inside a clip | drag inside the waveform/MIDI display |
| Copy a clip while dragging | hold `Option` while dragging |
| Temporarily ignore the grid | hold `Cmd` while dragging |
| Keep clean bar alignment | do not hold `Cmd`; let the grid snap |
| Add clips to a group selection | `Shift-click` clips before dragging |

If a clip is not moving, you are probably dragging inside the clip content instead of the top colored bar.

## Merge, Split, Duplicate

| Task | Mac command |
|---|---|
| Merge adjacent MIDI clips/regions | select them, then `Cmd J` |
| Merge a time span into one clip | drag a time selection, then `Cmd J` |
| Split clip at cursor/selection | `Cmd E` |
| Duplicate selected clip/time | `Cmd D` |
| Cut/copy/paste selection | `Cmd X` / `Cmd C` / `Cmd V` |

In Arrangement View, `Cmd J` is Consolidate. For MIDI, it creates one new MIDI clip from the selected clips or time range.

## Move MIDI To Bar 1

1. Press `Tab` for Arrangement View.
2. Press `W` if you need to see the start.
3. Select the MIDI clips you want to move.
4. Drag the selected clips by their colored top bars to `1.1.1`.
5. Press `Space` to test from the beginning.

If the clip starts at `1.1.1` but notes inside it are late, double-click the clip, press `Cmd A` in the MIDI editor, then drag the notes left to the clip start.


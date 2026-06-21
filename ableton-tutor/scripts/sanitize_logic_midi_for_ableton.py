#!/usr/bin/env python3
"""Sanitize Logic-exported MIDI files before importing them into Ableton Live.

Logic can export repeated notes where a Note On and the previous Note Off for
the same pitch/channel share the same tick. Some DAWs tolerate this and draw
normal adjacent notes; Ableton can interpret parts of it as zero-length notes.
Logic exports from Session Player regions can also include an empty lead-in bar
before the first note. By default this script trims that leading silence so the
cleaned MIDI starts at beat 0 in Ableton.

This script rewrites note events so same-pitch repeats are unambiguous:

- note-offs are emitted before note-ons at the same tick;
- touching/overlapping repeated notes are shortened by a tiny gap;
- leading silence before the first note is removed by default;
- non-note MIDI events such as tempo, CC, program changes, and names are kept.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


NOTE_OFF = 0x80
NOTE_ON = 0x90
META = 0xFF
SYSEX_START = 0xF0
SYSEX_CONTINUE = 0xF7
END_OF_TRACK = 0x2F
SETUP_META_TOLERANCE_TICKS = 10


class MidiError(RuntimeError):
    """Raised when a file cannot be parsed as a Standard MIDI file."""


@dataclass(frozen=True)
class NoteMessage:
    tick: int
    seq: int
    kind: str
    channel: int
    pitch: int
    velocity: int


@dataclass(frozen=True)
class KeptEvent:
    tick: int
    seq: int
    data: bytes
    kind: str


@dataclass
class ActiveNote:
    start_tick: int
    channel: int
    pitch: int
    velocity: int
    seq: int


@dataclass(frozen=True)
class Note:
    start_tick: int
    end_tick: int
    channel: int
    pitch: int
    velocity: int
    off_velocity: int = 64


@dataclass
class TrackData:
    kept_events: list[KeptEvent]
    note_messages: list[NoteMessage]
    end_tick: int
    raw_note_ons: int


@dataclass
class TrackResult:
    events: list[KeptEvent]
    stats: Counter


@dataclass
class MidiFile:
    header: bytes
    chunks: list[tuple[bytes, bytes | TrackData]]
    format_type: int
    division: int


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise MidiError("Unexpected EOF while reading variable-length value")
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, pos
    raise MidiError("Invalid variable-length value")


def write_vlq(value: int) -> bytes:
    if value < 0:
        raise MidiError(f"Negative delta time: {value}")
    stack = [value & 0x7F]
    value >>= 7
    while value:
        stack.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(stack))


def event_payload_length(status: int) -> int:
    status_type = status & 0xF0
    if status_type in (0xC0, 0xD0):
        return 1
    if 0x80 <= status_type <= 0xE0:
        return 2
    raise MidiError(f"Unsupported channel status byte: 0x{status:02x}")


def parse_track(payload: bytes) -> TrackData:
    pos = 0
    tick = 0
    seq = 0
    running_status: int | None = None
    kept: list[KeptEvent] = []
    notes: list[NoteMessage] = []
    end_tick = 0
    raw_note_ons = 0

    while pos < len(payload):
        delta, pos = read_vlq(payload, pos)
        tick += delta
        if pos >= len(payload):
            raise MidiError("Unexpected EOF after delta time")

        first = payload[pos]
        if first < 0x80:
            if running_status is None:
                raise MidiError("Running status used before any status byte")
            status = running_status
        else:
            status = first
            pos += 1
            if status < 0xF0:
                running_status = status

        if status == META:
            if pos >= len(payload):
                raise MidiError("Unexpected EOF in meta event")
            meta_type = payload[pos]
            pos += 1
            length, pos = read_vlq(payload, pos)
            body = payload[pos : pos + length]
            if len(body) != length:
                raise MidiError("Unexpected EOF in meta event body")
            pos += length
            encoded = bytes([META, meta_type]) + write_vlq(length) + body
            if meta_type == END_OF_TRACK:
                end_tick = max(end_tick, tick)
            else:
                kept.append(KeptEvent(tick, seq, encoded, "meta"))
            seq += 1
            continue

        if status in (SYSEX_START, SYSEX_CONTINUE):
            length, pos = read_vlq(payload, pos)
            body = payload[pos : pos + length]
            if len(body) != length:
                raise MidiError("Unexpected EOF in sysex event body")
            pos += length
            encoded = bytes([status]) + write_vlq(length) + body
            kept.append(KeptEvent(tick, seq, encoded, "sysex"))
            seq += 1
            continue

        length = event_payload_length(status)
        body = payload[pos : pos + length]
        if len(body) != length:
            raise MidiError("Unexpected EOF in channel event")
        pos += length

        status_type = status & 0xF0
        channel = status & 0x0F
        encoded = bytes([status]) + body
        if status_type == NOTE_ON and body[1] > 0:
            notes.append(
                NoteMessage(tick, seq, "on", channel, body[0], body[1])
            )
            raw_note_ons += 1
        elif status_type == NOTE_OFF or (status_type == NOTE_ON and body[1] == 0):
            notes.append(
                NoteMessage(tick, seq, "off", channel, body[0], body[1] or 64)
            )
        else:
            kept.append(KeptEvent(tick, seq, encoded, "channel"))
        seq += 1

    return TrackData(kept, notes, end_tick, raw_note_ons)


def parse_midi(path: Path) -> MidiFile:
    data = path.read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiError("Missing MIDI header chunk")

    header_len = struct.unpack(">I", data[4:8])[0]
    header_end = 8 + header_len
    if header_len < 6 or len(data) < header_end:
        raise MidiError("Invalid MIDI header length")

    format_type, track_count, division = struct.unpack(">HHH", data[8:14])
    pos = header_end
    chunks: list[tuple[bytes, bytes | TrackData]] = []

    while pos < len(data):
        if pos + 8 > len(data):
            raise MidiError("Truncated MIDI chunk header")
        chunk_type = data[pos : pos + 4]
        chunk_len = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        pos += 8
        payload = data[pos : pos + chunk_len]
        if len(payload) != chunk_len:
            raise MidiError(f"Truncated {chunk_type!r} chunk")
        pos += chunk_len
        if chunk_type == b"MTrk":
            chunks.append((chunk_type, parse_track(payload)))
        else:
            chunks.append((chunk_type, payload))

    parsed_track_count = sum(1 for chunk_type, _ in chunks if chunk_type == b"MTrk")
    if parsed_track_count != track_count:
        raise MidiError(
            f"Header says {track_count} tracks, found {parsed_track_count}"
        )

    return MidiFile(data[:header_end], chunks, format_type, division)


def close_active_note(
    active: ActiveNote,
    requested_end_tick: int,
    output: list[Note],
    stats: Counter,
    reason: str,
) -> None:
    if requested_end_tick <= active.start_tick:
        stats["dropped_zero_or_negative_notes"] += 1
        return
    output.append(
        Note(
            start_tick=active.start_tick,
            end_tick=requested_end_tick,
            channel=active.channel,
            pitch=active.pitch,
            velocity=active.velocity,
        )
    )
    if reason:
        stats[reason] += 1


def build_clean_notes(
    messages: list[NoteMessage], end_tick: int, gap_ticks: int
) -> tuple[list[Note], Counter]:
    stats: Counter = Counter()
    active: dict[tuple[int, int], list[ActiveNote]] = defaultdict(list)
    output: list[Note] = []
    by_tick: dict[int, list[NoteMessage]] = defaultdict(list)

    for message in messages:
        by_tick[message.tick].append(message)

    for tick in sorted(by_tick):
        group = sorted(by_tick[tick], key=lambda m: m.seq)
        by_key: dict[tuple[int, int], list[NoteMessage]] = defaultdict(list)
        for message in group:
            by_key[(message.channel, message.pitch)].append(message)

        same_tick_keys_with_on = {
            key
            for key, key_messages in by_key.items()
            if any(m.kind == "on" for m in key_messages)
            and any(m.kind == "off" for m in key_messages)
        }
        for key, key_messages in by_key.items():
            if key in same_tick_keys_with_on:
                stats["same_tick_on_off"] += 1
                first = min(key_messages, key=lambda m: m.seq)
                if first.kind == "on":
                    stats["same_tick_first_on"] += 1
                else:
                    stats["same_tick_first_off"] += 1

        # Process note-offs first at each tick. This makes adjacent repeated
        # notes deterministic even if Logic wrote note-on before note-off.
        for message in sorted((m for m in group if m.kind == "off"), key=lambda m: m.seq):
            key = (message.channel, message.pitch)
            stack = active[key]
            if not stack:
                stats["ignored_unmatched_note_offs"] += 1
                continue
            active_note = stack.pop(0)
            trim_for_next_on = key in same_tick_keys_with_on and gap_ticks > 0
            close_tick = tick - gap_ticks if trim_for_next_on else tick
            close_active_note(
                active_note,
                close_tick,
                output,
                stats,
                "gap_trims" if trim_for_next_on else "",
            )

        # Then process note-ons. If a same-pitch note is still active, close it
        # before starting the new one; this fixes genuine overlaps too.
        for message in sorted((m for m in group if m.kind == "on"), key=lambda m: m.seq):
            key = (message.channel, message.pitch)
            stack = active[key]
            if stack:
                close_tick = message.tick - gap_ticks if gap_ticks > 0 else message.tick
                while stack:
                    active_note = stack.pop(0)
                    close_active_note(
                        active_note,
                        close_tick,
                        output,
                        stats,
                        "overlap_trims",
                    )
            stack.append(
                ActiveNote(
                    start_tick=message.tick,
                    channel=message.channel,
                    pitch=message.pitch,
                    velocity=message.velocity,
                    seq=message.seq,
                )
            )

    final_tick = max(end_tick, max((m.tick for m in messages), default=0))
    for stack in active.values():
        while stack:
            active_note = stack.pop(0)
            close_active_note(
                active_note,
                max(final_tick, active_note.start_tick + 1),
                output,
                stats,
                "open_notes_closed_at_end",
            )

    output.sort(key=lambda n: (n.start_tick, n.channel, n.pitch, n.end_tick))
    stats["notes_written"] = len(output)
    return output, stats


def note_events_from_notes(notes: list[Note]) -> list[KeptEvent]:
    events: list[KeptEvent] = []
    seq = 0
    for note in notes:
        on_data = bytes([NOTE_ON | note.channel, note.pitch, note.velocity])
        off_data = bytes([NOTE_OFF | note.channel, note.pitch, note.off_velocity])
        events.append(KeptEvent(note.start_tick, seq, on_data, "note_on"))
        seq += 1
        events.append(KeptEvent(note.end_tick, seq, off_data, "note_off"))
        seq += 1
    return events


def earliest_note_start(midi: MidiFile) -> int:
    starts: list[int] = []
    for chunk_type, payload in midi.chunks:
        if chunk_type != b"MTrk":
            continue
        assert isinstance(payload, TrackData)
        starts.extend(
            message.tick for message in payload.note_messages if message.kind == "on"
        )
    return min(starts, default=0)


def is_setup_meta(event: KeptEvent) -> bool:
    if event.kind != "meta" or len(event.data) < 2 or event.data[0] != META:
        return False
    return event.data[1] in {
        0x03,  # track name
        0x04,  # instrument name
        0x20,  # MIDI channel prefix
        0x51,  # tempo
        0x54,  # SMPTE offset
        0x58,  # time signature
        0x59,  # key signature
    }


def shifted_tick(event: KeptEvent, trim_ticks: int) -> int:
    if trim_ticks <= 0:
        return event.tick
    if is_setup_meta(event) and event.tick <= trim_ticks + SETUP_META_TOLERANCE_TICKS:
        return 0
    return max(0, event.tick - trim_ticks)


def shift_event(event: KeptEvent, trim_ticks: int) -> KeptEvent:
    return KeptEvent(shifted_tick(event, trim_ticks), event.seq, event.data, event.kind)


def shift_note(note: Note, trim_ticks: int) -> Note:
    if trim_ticks <= 0:
        return note
    start_tick = max(0, note.start_tick - trim_ticks)
    end_tick = max(start_tick + 1, note.end_tick - trim_ticks)
    return Note(
        start_tick=start_tick,
        end_tick=end_tick,
        channel=note.channel,
        pitch=note.pitch,
        velocity=note.velocity,
        off_velocity=note.off_velocity,
    )


def event_priority(event: KeptEvent) -> tuple[int, int, bytes]:
    if event.kind == "meta":
        priority = 0
    elif event.kind == "sysex":
        priority = 10
    elif event.kind == "channel":
        priority = 20
    elif event.kind == "note_off":
        priority = 30
    elif event.kind == "note_on":
        priority = 40
    elif event.kind == "eot":
        priority = 1000
    else:
        priority = 50
    return priority, event.seq, event.data


def render_track(events: list[KeptEvent]) -> bytes:
    sorted_events = sorted(events, key=lambda e: (e.tick, *event_priority(e)))
    payload = bytearray()
    previous_tick = 0
    for event in sorted_events:
        payload.extend(write_vlq(event.tick - previous_tick))
        payload.extend(event.data)
        previous_tick = event.tick
    return bytes(payload)


def sanitize_track(track: TrackData, gap_ticks: int, trim_ticks: int) -> TrackResult:
    notes, stats = build_clean_notes(track.note_messages, track.end_tick, gap_ticks)
    stats["raw_note_ons"] = track.raw_note_ons
    stats["raw_note_messages"] = len(track.note_messages)

    shifted_notes = [shift_note(note, trim_ticks) for note in notes]
    events = [shift_event(event, trim_ticks) for event in track.kept_events]
    events.extend(note_events_from_notes(shifted_notes))

    last_tick = max(
        [max(0, track.end_tick - trim_ticks)]
        + [event.tick for event in events]
        + [note.end_tick for note in shifted_notes],
        default=max(0, track.end_tick - trim_ticks),
    )
    events.append(KeptEvent(last_tick, 1_000_000_000, b"\xff\x2f\x00", "eot"))
    return TrackResult(events, stats)


def sanitize_midi(
    path: Path, output_path: Path, gap_ticks: int, trim_leading_silence: bool
) -> dict:
    midi = parse_midi(path)
    trim_ticks = earliest_note_start(midi) if trim_leading_silence else 0
    out = bytearray(midi.header)
    total: Counter = Counter()
    track_reports: list[dict] = []
    track_index = 0

    for chunk_type, payload in midi.chunks:
        if chunk_type != b"MTrk":
            assert isinstance(payload, bytes)
            out.extend(chunk_type)
            out.extend(struct.pack(">I", len(payload)))
            out.extend(payload)
            continue

        assert isinstance(payload, TrackData)
        result = sanitize_track(payload, gap_ticks, trim_ticks)
        rendered = render_track(result.events)
        out.extend(chunk_type)
        out.extend(struct.pack(">I", len(rendered)))
        out.extend(rendered)
        total.update(result.stats)
        track_reports.append({"track": track_index, **dict(result.stats)})
        track_index += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(out)

    return {
        "input": str(path),
        "output": str(output_path),
        "format": midi.format_type,
        "division": midi.division,
        "gap_ticks": gap_ticks,
        "trim_leading_silence": trim_leading_silence,
        "trim_ticks": trim_ticks,
        "trim_beats": trim_ticks / midi.division if midi.division else 0,
        "tracks": track_reports,
        "totals": dict(total),
    }


def expand_inputs(paths: list[Path], recursive: bool) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            expanded.extend(
                p
                for p in path.glob(pattern)
                if p.is_file() and p.suffix.lower() in {".mid", ".midi", ".smf"}
            )
        else:
            expanded.append(path)
    return sorted(dict.fromkeys(expanded))


def output_for(
    input_path: Path,
    output: Path | None,
    output_dir: Path | None,
    suffix: str,
) -> Path:
    if output is not None:
        return output
    extension = ".mid" if input_path.suffix.lower() == ".midi" else input_path.suffix
    filename = f"{input_path.stem}{suffix}{extension or '.mid'}"
    if output_dir is not None:
        return output_dir / filename
    return input_path.with_name(filename)


def print_report(report: dict) -> None:
    totals = Counter(report["totals"])
    print(f"Wrote: {report['output']}")
    print(f"  format: SMF{report['format']}  ppq: {report['division']}")
    if report["trim_leading_silence"] and report["trim_ticks"]:
        print(
            "  trimmed leading silence: "
            f"{report['trim_ticks']} ticks ({report['trim_beats']:.6g} beats)"
        )
    elif not report["trim_leading_silence"]:
        print("  preserved leading silence")
    print(f"  raw note-ons: {totals['raw_note_ons']}  notes written: {totals['notes_written']}")
    print(
        "  fixed: "
        f"{totals['same_tick_on_off']} same-tick repeats, "
        f"{totals['same_tick_first_on']} note-on-before-off cases, "
        f"{totals['overlap_trims']} overlaps"
    )
    if totals["gap_trims"]:
        print(f"  shortened repeated notes by {report['gap_ticks']} tick(s): {totals['gap_trims']}")
    if totals["ignored_unmatched_note_offs"] or totals["dropped_zero_or_negative_notes"]:
        print(
            "  warnings: "
            f"{totals['ignored_unmatched_note_offs']} unmatched note-offs ignored, "
            f"{totals['dropped_zero_or_negative_notes']} zero/negative notes dropped"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clean Logic-exported MIDI so Ableton imports repeated notes without "
            "zero-length artifacts. Leading silence is trimmed by default."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="MIDI file(s) or folder(s)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path. Only valid with one input file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Folder for cleaned copies. Defaults beside each input file.",
    )
    parser.add_argument(
        "--suffix",
        default="-ableton",
        help="Suffix for cleaned copies when --output is not used.",
    )
    parser.add_argument(
        "--gap-ticks",
        type=int,
        default=1,
        help="Tiny gap inserted before repeated same-pitch notes. Use 0 to only reorder events.",
    )
    parser.add_argument(
        "--preserve-leading-silence",
        "--keep-leading-silence",
        dest="preserve_leading_silence",
        action="store_true",
        help="Keep the original leading empty bars. Default trims the first note to beat 0.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When an input is a folder, process MIDI files recursively.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.gap_ticks < 0:
        parser.error("--gap-ticks must be >= 0")

    inputs = expand_inputs(args.inputs, args.recursive)
    if not inputs:
        parser.error("No MIDI files found")
    if args.output is not None and len(inputs) != 1:
        parser.error("--output can only be used with one input file")

    reports = []
    for input_path in inputs:
        if not input_path.exists():
            print(f"Missing input: {input_path}", file=sys.stderr)
            return 2
        output_path = output_for(input_path, args.output, args.output_dir, args.suffix)
        if output_path.resolve() == input_path.resolve():
            print(f"Refusing to overwrite input: {input_path}", file=sys.stderr)
            return 2
        try:
            report = sanitize_midi(
                input_path,
                output_path,
                args.gap_ticks,
                trim_leading_silence=not args.preserve_leading_silence,
            )
        except MidiError as exc:
            print(f"{input_path}: {exc}", file=sys.stderr)
            return 1
        reports.append(report)

    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for index, report in enumerate(reports):
            if index:
                print()
            print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

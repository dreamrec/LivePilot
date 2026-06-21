#!/usr/bin/env python3
"""Build a macOS-only Ableton Live tutor wiki from the local Live 12 PDF.

The output is intentionally separate from the LivePilot plugin code. It is a
lookup layer for fast answers while learning Ableton Live on macOS.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ableton-tutor"
PDF = ROOT / "live12-manual-en.pdf"


@dataclass(frozen=True)
class TocEntry:
    number: str
    title: str
    page: int
    level: int


KEY_TOKEN = (
    r"Ctrl|Alt|Shift|Cmd|Option|VO|Function|Enter|Delete|Backspace|Tab|Esc|Space|"
    r"Home|End|Page|Up|Down|F\d+|left|right|up|down|arrow|arrows|keys|key|"
    r"click|drag|then|with|VoiceOver|or|\+|-|,|\.|/|[A-Z0-9]"
)
KEY_SEQUENCE = rf"(?:(?:{KEY_TOKEN})\s*){{1,12}}"
WIN_MAC_SHORTCUT_RE = re.compile(
    rf"(?P<win>{KEY_SEQUENCE})\s*\(Win\)\s*/\s*(?P<mac>{KEY_SEQUENCE})\s*\(Mac\)",
    re.IGNORECASE,
)
WIN_MAC_PHRASE_RE = re.compile(
    r"(?P<prefix>\b(?:on|for|in)\s+)Windows\s*/\s*Mac", re.IGNORECASE
)


def run_pdftotext(*args: str) -> str:
    if not PDF.exists():
        raise SystemExit(f"Missing source PDF: {PDF}")
    if shutil.which("pdftotext") is None:
        raise SystemExit("pdftotext is required but was not found on PATH.")
    cmd = ["pdftotext", *args, str(PDF), "-"]
    return subprocess.check_output(cmd, text=True, errors="replace")


def slugify(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "untitled"


def parse_toc() -> list[TocEntry]:
    text = run_pdftotext("-f", "2", "-l", "21", "-layout")
    entries: list[TocEntry] = []
    pattern = re.compile(r"^\s*(\d+(?:\.\d+)*\.?)\s+(.+?)\s+(\d{1,4})\s*$")
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = pattern.match(line)
        if not match:
            continue
        number, title, page = match.groups()
        number = number.rstrip(".")
        entries.append(
            TocEntry(
                number=number,
                title=re.sub(r"\s+", " ", title).strip(),
                page=int(page),
                level=number.count(".") + 1,
            )
        )
    return entries


def split_pdf_pages() -> list[str]:
    text = run_pdftotext("-layout")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def strip_windows_only_line(line: str) -> str | None:
    """Drop residual Windows-only guidance after shortcut normalization."""
    if re.search(r"\bWindows\b|\bWin\b|\(Win\)", line, re.IGNORECASE):
        has_mac = re.search(r"\bmacOS\b|\bMac\b|\(Mac\)|Cmd|Option|VoiceOver", line)
        if not has_mac:
            return None
        line = re.sub(r"\b(on|for|in) Windows\s+and\s+macOS\b", r"\1 macOS", line, flags=re.I)
        line = re.sub(r"\b(on|for|in) macOS\s+and\s+Windows\b", r"\1 macOS", line, flags=re.I)
        line = re.sub(r"\bboth macOS and Windows\b", "macOS", line, flags=re.I)
        line = re.sub(r"\bboth Windows and macOS\b", "macOS", line, flags=re.I)
        line = re.sub(r"\bWindows and Mac\b", "macOS", line, flags=re.I)
        line = re.sub(r"\bMac and Windows\b", "macOS", line, flags=re.I)
        line = re.sub(r"\bWindows\b", "", line, flags=re.I)
        line = re.sub(r"\(Win\)", "", line, flags=re.I)
    return re.sub(r"\s{2,}", " ", line).strip()


def normalize_mac_shortcuts(text: str) -> str:
    text = text.replace("Live‘s", "Live's").replace("Live’s", "Live's")
    text = re.sub(r"\bcommand\b", "Command", text)

    def repl(match: re.Match[str]) -> str:
        return re.sub(r"\s+", " ", match.group("mac")).strip()

    # Keep this line-based. The keyboard-shortcut chapter contains dense tables,
    # and whole-chapter regex passes are needlessly expensive there.
    lines = []
    for line in text.splitlines():
        for _ in range(2):
            line = WIN_MAC_SHORTCUT_RE.sub(repl, line)
        lines.append(line)
    text = "\n".join(lines)

    text = re.sub(r"\bCtrl\b\s*\(Win\)\s*/\s*\bCmd\b\s*\(Mac\)", "Cmd", text)
    text = re.sub(r"\bAlt\b\s*\(Win\)\s*/\s*\bOption\b\s*\(Mac\)", "Option", text)
    text = re.sub(r"\bCtrl\b\s*/\s*\bCmd\b", "Cmd", text)
    text = re.sub(r"\bAlt\b\s*/\s*\bOption\b", "Option", text)
    text = re.sub(r"\bCtrl\s+Alt\s*\n\s*/?\s*(?:Cmd|Ctrl)\s+Option\b", "Cmd Option", text)
    text = re.sub(r"\bCtrl\s+Shift\s*\n\s*/?\s*Cmd\s+Shift\b", "Cmd Shift", text)
    text = re.sub(r"\bCtrl\s*\n\s*/?\s*Cmd\b", "Cmd", text)
    text = re.sub(r"\bAlt\s*\n\s*/?\s*Option\b", "Option", text)
    text = re.sub(r"\bCtrl\s*,\s*/\s*Cmd\s*,", "Cmd ,", text)
    text = re.sub(r"\bCtrl\s+Alt\s+([A-Za-z0-9?\[\]]+)\s*/\s*(?:Cmd|Ctrl)\s+Option\s+\1", r"Cmd Option \1", text)
    text = re.sub(r"\bCtrl\s+Shift\s+([A-Za-z0-9?\[\]]+)\s*/\s*Cmd\s+Shift\s+\1", r"Cmd Shift \1", text)
    text = re.sub(r"\bCtrl\s+([A-Za-z0-9?\[\]]+)\s*/\s*Cmd\s+\1", r"Cmd \1", text)
    text = re.sub(r"\bCtrl\s+Alt\s*/\s*Cmd\s+Option\b", "Cmd Option", text)
    text = re.sub(r"\bAlt\s*/\s*Cmd\b", "Cmd", text)
    text = re.sub(r"\bCtrl\s+Option\b", "Cmd Option", text)
    text = text.replace("Options menu on and in the Live menu on macOS", "Live menu on macOS")
    text = re.sub(r"\(Mac\)", "", text)
    text = re.sub(r"\s+/", " /", text)
    text = re.sub(r"/\s+", "/ ", text)
    return text


def to_markdown(text: str, title: str, source_pages: str) -> str:
    text = normalize_mac_shortcuts(text)
    out: list[str] = [
        "---",
        f"title: {json.dumps(title)[1:-1]}",
        f"source_pdf: ../live12-manual-en.pdf",
        f"source_pages: {source_pages}",
        "platform: macOS",
        "generated: true",
        "---",
        "",
        f"# {title}",
        "",
    ]
    blank = False
    heading_re = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(.+?)\s*$")
    for raw in text.splitlines():
        line = raw.rstrip().replace("\f", "")
        if re.fullmatch(r"\s*\d{1,4}\s*", line):
            continue
        line = strip_windows_only_line(line)
        if line is None:
            continue
        line = line.strip()
        if not line:
            if not blank:
                out.append("")
                blank = True
            continue
        blank = False
        heading = heading_re.match(line)
        if heading and "." in heading.group(1):
            number = heading.group(1).rstrip(".")
            level = min(number.count(".") + 1, 6)
            hashes = "#" * level
            out.append(f"{hashes} {number} {heading.group(2)}")
            out.append("")
        elif line.startswith("•"):
            out.append("- " + line[1:].strip())
        else:
            out.append(re.sub(r"\s{2,}", " ", line))
    return scrub_residual_platform_shortcuts("\n".join(out).strip() + "\n")


def scrub_residual_platform_shortcuts(markdown: str) -> str:
    """Convert leftover split shortcut pairs in chapter prose to macOS form.

    Chapter prose is not the source of truth for shortcut tables; the generated
    lookup table is. Here, favor a clean macOS-only reading surface.
    """
    markdown = re.sub(
        r"\bCtrl(?:\s+(?:Alt|Shift))*\s+[A-Za-z0-9?,\[\]]+(?:\s*,\s*[0-9])*(?:\s*,?\s*and\s*[0-9])?\s*\n\s*/\s*(Cmd(?:\s+(?:Option|Shift|Ctrl))*\s+[A-Za-z0-9?,\[\]]+)",
        r"\1",
        markdown,
    )
    markdown = re.sub(
        r"\bCtrl(?:\s+(?:Alt|Shift))*\s+[A-Za-z0-9?,\[\]]+(?:\s*,\s*[0-9])*(?:\s*,?\s*and\s*[0-9])?\s*/\s*(Cmd(?:\s+(?:Option|Shift|Ctrl))*\s+[A-Za-z0-9?,\[\]]+)",
        r"\1",
        markdown,
    )
    markdown = re.sub(r"\bCmd\s+([A-Za-z0-9?,\[\]-]+)\s*/\s*Cmd\s+\1", r"Cmd \1", markdown)
    markdown = re.sub(r"\bCmd\s+([A-Za-z0-9?,\[\]-]+)\s*\n\s*/\s*Cmd\s+\1", r"Cmd \1", markdown)
    markdown = re.sub(r"\bAlt\s+([A-Za-z0-9?,\[\]-]+)\s*/\s*Option\s+\1", r"Option \1", markdown)
    markdown = re.sub(r"\bAlt\s+([A-Za-z0-9?,\[\]-]+)\s*\n\s*/\s*Option\s+\1", r"Option \1", markdown)
    markdown = re.sub(r"\bCmd\s+Shift\s+Tab\s*/\s*Option\s+Shift\s+Tab\b", "Option Shift Tab", markdown)
    markdown = re.sub(r"\bCmd\s+Tab\s*/\s*Option\s+Tab\b", "Option Tab", markdown)
    markdown = re.sub(r"\bCmd\s*/\s*Option\b", "Option", markdown)
    markdown = re.sub(r"\bCtrl\s*/\s*Option\b", "Option", markdown)
    markdown = re.sub(r"\bCtrl and ([^/\n]+?)\s*/\s*Option and", r"Option and", markdown)
    markdown = re.sub(r"\bAlt\s*/\s*Cmd\b", "Cmd", markdown)
    markdown = re.sub(r"\bCtrl\s+Alt\b", "Cmd Option", markdown)
    markdown = re.sub(r"\bCtrl\s+Shift\b", "Cmd Shift", markdown)
    markdown = re.sub(r"\bCtrl\s+([A-Z0-9,\[\]?])", r"Cmd \1", markdown)
    markdown = re.sub(r"\bthCmd\b", "the Cmd", markdown)
    markdown = re.sub(r"\bsnCmd\b", "Snap to Grid options menu entry or the Cmd", markdown)
    markdown = re.sub(r"\btOption\b", "Option", markdown)
    markdown = re.sub(r"\bCmd\s+Shift\s+Tab\s*/\s*Option\s+Shift\s+Tab\b", "Option Shift Tab", markdown)
    markdown = re.sub(r"\bCmd\s+Tab\s*/\s*Option\s+Tab\b", "Option Tab", markdown)
    markdown = re.sub(r"\bkeys\s*/\s*Option and\b", "Option and", markdown)
    markdown = markdown.replace("furthCmd modifier is held down", "further while the Cmd modifier is held down")
    markdown = markdown.replace("grCmd.", "grid, hold Cmd.")
    markdown = markdown.replace("amountOption", "amount; hold Option")
    markdown = markdown.replace("seOption together with", "select; press Option together with")
    markdown = markdown.replace("in the same Option while", "in the same key track, hold Option while")
    markdown = markdown.replace("use Option Tab Option Shift Tab or", "use Option Tab or Option Shift Tab, or")
    markdown = markdown.replace("shortcuts Option Tab\nOption Shift Tab", "shortcuts Option Tab or Option Shift Tab")
    markdown = re.sub(r"\s+,\s+then", ", then", markdown)
    return markdown


def chapter_entries(toc: list[TocEntry]) -> list[TocEntry]:
    return [entry for entry in toc if entry.level == 1]


def chapter_filename(entry: TocEntry) -> str:
    return f"{int(entry.number):02d}-{slugify(entry.title)}.md"


def chapter_for_page(chapters: list[TocEntry], page: int) -> TocEntry:
    current = chapters[0]
    for chapter in chapters:
        if chapter.page <= page:
            current = chapter
        else:
            break
    return current


def build_chapters(toc: list[TocEntry], pages: list[str]) -> dict[str, str]:
    chapters = chapter_entries(toc)
    chapter_dir = OUT / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for index, chapter in enumerate(chapters):
        start = chapter.page
        end = (chapters[index + 1].page - 1) if index + 1 < len(chapters) else len(pages)
        filename = chapter_filename(chapter)
        if chapter.number == "41":
            md = "\n".join(
                [
                    "---",
                    f"title: {json.dumps(chapter.title)[1:-1]}",
                    "source_pdf: ../live12-manual-en.pdf",
                    f"source_pages: {start}-{end}",
                    "platform: macOS",
                    "generated: true",
                    "---",
                    "",
                    f"# {chapter.title}",
                    "",
                    "Use [Mac Keyboard Shortcuts](../lookups/mac-keyboard-shortcuts.md) for the macOS-only shortcut table generated from this chapter.",
                    "",
                    "Use [Quick Commands](../lookups/quick-commands.md) for the most common learning commands.",
                    "",
                ]
            )
        else:
            text = "\n\f\n".join(pages[start - 1 : end])
            md = to_markdown(text, chapter.title, f"{start}-{end}")
        (chapter_dir / filename).write_text(md, encoding="utf-8")
        mapping[chapter.number] = f"chapters/{filename}"
    return mapping


def build_toc_files(toc: list[TocEntry], chapter_paths: dict[str, str]) -> None:
    chapters = chapter_entries(toc)
    lines = [
        "# Ableton Live 12 Tutor",
        "",
        "Mac-only lookup wiki generated from the local Ableton Live 12 reference manual.",
        "",
        "Start here:",
        "",
        "- [Structure](STRUCTURE.md) explains the folder layout and lookup flow.",
        "- [Where To Look](lookups/where-to-look.md) maps common learning questions to chapters.",
        "- [Quick Commands](lookups/quick-commands.md) collects common Mac actions.",
        "- [Mac Keyboard Shortcuts](lookups/mac-keyboard-shortcuts.md) is the shortcut-first reference.",
        "- [Topic Index](lookups/topic-index.md) lists every manual section with source pages.",
        "",
        "## Chapters",
        "",
    ]
    for chapter in chapters:
        path = chapter_paths[chapter.number]
        lines.append(f"- [{chapter.number}. {chapter.title}]({path}) - source page {chapter.page}")
    (OUT / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    topic_lines = [
        "# Topic Index",
        "",
        "Every section from the Ableton Live 12 manual table of contents. Links point to the generated chapter file; page numbers point back to the source PDF.",
        "",
        "| Section | Topic | Source page | Chapter file |",
        "|---:|---|---:|---|",
    ]
    for entry in toc:
        chapter = chapter_for_page(chapters, entry.page)
        path = chapter_paths[chapter.number]
        topic_lines.append(
            f"| {entry.number} | {entry.title} | {entry.page} | [{chapter.title}](../{path}) |"
        )
    (OUT / "lookups" / "topic-index.md").write_text("\n".join(topic_lines) + "\n", encoding="utf-8")


def compact_key_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bCmd\s+,\b", "Cmd ,", text)
    return text


def parse_chapter_41_shortcuts(pages: list[str], toc: list[TocEntry]) -> list[dict[str, str]]:
    chapter_41 = next(entry for entry in chapter_entries(toc) if entry.number == "41")
    chapters = chapter_entries(toc)
    idx = chapters.index(chapter_41)
    end = (chapters[idx + 1].page - 1) if idx + 1 < len(chapters) else len(pages)
    text = "\n".join(pages[chapter_41.page - 1 : end])

    shortcuts: list[dict[str, str]] = []
    section = ""
    win_col = 30
    mac_col = 65
    current: dict[str, str] | None = None

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if re.fullmatch(r"\s*\d{1,4}\s*", line) or not line.strip():
            continue
        heading = re.match(r"^(41\.\d+)\s+(.+?)\s*$", line.strip())
        if heading:
            section = f"{heading.group(1)} {heading.group(2)}"
            current = None
            continue
        if "Windows" in line and "Mac" in line:
            win_col = line.index("Windows")
            mac_col = line.index("Mac")
            current = None
            continue
        if not section:
            continue

        if len(line) < mac_col:
            continuation = line.strip()
            if (
                current is not None
                and continuation
                and not re.match(r"^41\.\d+", continuation)
                and "Windows" not in continuation
                and "Mac" not in continuation
            ):
                current["action"] = compact_key_text(current["action"] + " " + continuation)
            continue

        action = line[:win_col].strip()
        mac = line[mac_col:].strip()
        middle = line[win_col:mac_col].strip()

        if action and mac:
            should_merge = (
                current is not None
                and (
                    current["shortcut"].endswith((" on", " to", " with", " left", " right", " up/", "down/"))
                    or current["action"].endswith((" the", " with", " of", " in", " Start", " End"))
                    or action in {"Marker", "Beginning", "Selection", "Same Key Track", "Devices in Group"}
                )
            )
            if should_merge:
                current["action"] = compact_key_text(current["action"] + " " + action)
                current["shortcut"] = compact_key_text(current["shortcut"] + " " + mac)
            else:
                current = {"section": section, "action": compact_key_text(action), "shortcut": compact_key_text(mac)}
                shortcuts.append(current)
        elif action and not mac and current is not None and not middle:
            current["action"] = compact_key_text(current["action"] + " " + action)
        elif mac and current is not None:
            current["shortcut"] = compact_key_text(current["shortcut"] + " " + mac)

    cleaned: list[dict[str, str]] = []
    bad_action_prefixes = ("The following", "Some of the", "The loop brace", "If Use", "On Windows")
    bad_shortcut_fragments = (
        "Win)",
        "Windows",
        "Live’s",
        "Live's",
        "enabled",
        "available",
        "control in",
        "Settings",
        "letter of the menu",
        "etter of the menu",
    )
    for row in shortcuts:
        action = row["action"].replace("Multiple Windows", "Multiple Plug-in Panels")
        shortcut = row["shortcut"].replace(" / ", "/")
        shortcut = shortcut.replace("up/ down", "up/down").replace("down/ up", "down/up")
        if not shortcut:
            continue
        if action.startswith(bad_action_prefixes):
            continue
        if any(fragment in shortcut for fragment in bad_shortcut_fragments):
            continue
        if "Ctrl Tab (Win)" in shortcut or "Alt F" in shortcut:
            continue
        cleaned.append({**row, "action": compact_key_text(action), "shortcut": compact_key_text(shortcut)})
    return cleaned


def build_shortcuts(pages: list[str], toc: list[TocEntry]) -> None:
    shortcuts = parse_chapter_41_shortcuts(pages, toc)
    lookup_dir = OUT / "lookups"
    data_dir = OUT / "data"
    lookup_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in shortcuts:
        grouped.setdefault(row["section"], []).append(row)

    lines = [
        "# Mac Keyboard Shortcuts",
        "",
        "Generated from the Live Keyboard Shortcuts chapter. Other-platform shortcuts are intentionally omitted.",
        "",
    ]
    for section, rows in grouped.items():
        lines.extend([f"## {section}", "", "| Action | Mac shortcut |", "|---|---|"])
        for row in rows:
            lines.append(f"| {row['action']} | `{row['shortcut']}` |")
        lines.append("")
    (lookup_dir / "mac-keyboard-shortcuts.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    with (data_dir / "mac-keyboard-shortcuts.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "action", "shortcut"], delimiter="\t")
        writer.writeheader()
        writer.writerows(shortcuts)


def build_lookup_guides() -> None:
    lookup_dir = OUT / "lookups"
    source_dir = OUT / "sources"
    lookup_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    (OUT / "STRUCTURE.md").write_text(
        """# Ableton Tutor Structure

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
""",
        encoding="utf-8",
    )

    (OUT / "AGENTS.md").write_text(
        """# Ableton Tutor Agent Instructions

This directory is a macOS-only learning and lookup layer for Ableton Live 12.

When answering user questions:

- Use this folder before searching the wider LivePilot repo.
- Read `index.md`, then search `lookups/` and the relevant chapter files.
- Give macOS steps and macOS key commands only.
- If the source mentions multiple platforms, translate to the Mac command and omit the rest.
- Prefer concise numbered steps for "how do I" questions.
- Include the relevant generated file path or source page when it helps future lookup.
- Do not edit LivePilot plugin code from this folder.
""",
        encoding="utf-8",
    )

    (lookup_dir / "where-to-look.md").write_text(
        """# Where To Look

Use this as the first routing page for Ableton questions.

| If you ask about... | Start with |
|---|---|
| opening settings, interface basics, Learn View, Info View | `chapters/02-first-steps.md` |
| what Session View vs Arrangement View means | `chapters/03-live-concepts.md` |
| finding sounds, samples, devices, Packs, Splice, User Library | `chapters/04-working-with-the-browser.md` |
| saving sets, projects, missing files, collecting files | `chapters/05-managing-files-and-sets.md` |
| timeline editing, locators, splitting, consolidating, fades | `chapters/06-arrangement-view.md` |
| launching clips and scenes | `chapters/07-session-view.md` and `chapters/16-launching-clips.md` |
| Clip View controls, loops, clip gain, sample details | `chapters/08-clip-view.md` |
| warping, tempo, warp modes, audio quantize | `chapters/09-audio-clips-tempo-and-warping.md` |
| MIDI notes, piano roll, velocity, probability, quantize | `chapters/10-editing-midi.md` |
| MIDI Transform and Generate tools | `chapters/11-midi-tools.md` |
| MPE | `chapters/12-editing-mpe.md` |
| audio-to-MIDI conversion | `chapters/13-converting-audio-to-midi.md` |
| grooves and swing | `chapters/14-using-grooves.md` |
| tuning systems and scales | `chapters/15-using-tuning-systems.md` |
| audio/MIDI routing, monitoring, resampling | `chapters/17-routing-and-i-o.md` |
| mixer, groups, returns, cueing, crossfader | `chapters/18-mixing.md` |
| recording audio or MIDI | `chapters/19-recording-new-clips.md` |
| bouncing tracks to audio | `chapters/20-bounce-to-audio.md` |
| comping and take lanes | `chapters/21-comping.md` |
| stem separation | `chapters/22-stem-separation.md` |
| instruments, effects, plug-ins, Audio Units | `chapters/23-working-with-instruments-and-effects.md` |
| racks and macros | `chapters/24-instrument-drum-and-effect-racks.md` |
| automation and modulation | `chapters/25-automation-and-editing-envelopes.md` |
| clip envelopes | `chapters/26-clip-envelopes.md` |
| video | `chapters/27-working-with-video.md` |
| audio effects | `chapters/28-live-audio-effect-reference.md` |
| MIDI effects | `chapters/29-live-midi-effect-reference.md` |
| Live's built-in instruments | `chapters/30-live-instrument-reference.md` |
| Max for Live | `chapters/31-max-for-live.md` and `chapters/32-max-for-live-devices.md` |
| control surfaces, MIDI/key mapping | `chapters/33-midi-and-key-remote-control.md` |
| synchronization and Link | `chapters/36-synchronizing-with-link-tempo-follower-and-midi.md` |
| CPU, latency, performance | `chapters/37-computer-audio-resources-and-strategies.md` and `chapters/39-midi-fact-sheet.md` |
| accessibility and keyboard navigation | `chapters/40-accessibility-and-keyboard-navigation.md` |
| keyboard shortcuts | `lookups/mac-keyboard-shortcuts.md` |
""",
        encoding="utf-8",
    )

    (lookup_dir / "quick-commands.md").write_text(
        """# Quick Commands

Common macOS actions to check first before reading the full shortcut table.

| Task | Mac command |
|---|---|
| Open Settings | `Cmd ,` |
| Switch Session/Arrangement View | `Tab` |
| Toggle Browser | `Cmd Option B` or `Cmd Option 5` |
| Search Browser | `Cmd F` |
| Focus Browser | `Option 5` |
| Focus Arrangement View | `Option 2` |
| Focus Session View | `Option 1` |
| Focus Clip View | `Option 3` |
| Focus Device View | `Option 4` |
| Insert MIDI clip | `Cmd Shift M` |
| Quantize | `Cmd U` |
| Quantize Settings | `Cmd Shift U` |
| Cut | `Cmd X` |
| Copy | `Cmd C` |
| Paste | `Cmd V` |
| Duplicate | `Cmd D` |
| Undo | `Cmd Z` |
| Redo | `Cmd Shift Z` |
| Rename | `Cmd R` |
| Group devices or tracks | `Cmd G` |
| Ungroup devices or tracks | `Cmd Shift G` |
| Split clip or notes | `Cmd E` |
| Consolidate selection | `Cmd J` |
| Export audio/video | `Cmd Shift R` |
| Export MIDI file | `Cmd Shift E` |
| Toggle automation mode | `A` |
| Toggle draw mode | `B` |
| Narrow grid | `Cmd 1` |
| Widen grid | `Cmd 2` |
| Triplet grid | `Cmd 3` |
| Snap to grid | `Cmd 4` |
| Fixed/adaptive grid | `Cmd 5` |
| Capture MIDI | `Cmd Shift C` |
| Record to Session View | `Cmd Shift F9` |
| Start/stop playback | `Space` |
| Continue playback from stop point | `Shift Space` |
| Toggle computer MIDI keyboard | `M` |
| Enter Key Map Mode | `Cmd K` |
| Enter MIDI Map Mode | `Cmd M` |
""",
        encoding="utf-8",
    )

    (lookup_dir / "answer-style.md").write_text(
        """# Answer Style

For future Ableton tutoring answers:

- Lead with the direct action.
- Use numbered steps for procedures.
- Put Mac shortcuts inline, for example `Cmd Shift M`.
- Mention menu paths when they are clearer than shortcuts.
- Keep non-macOS platform guidance out of the answer entirely.
- If a task depends on Session vs Arrangement View, say which view first.
- If a setting can change behavior, name the setting and where to find it.
""",
        encoding="utf-8",
    )

    (source_dir / "source.md").write_text(
        f"""# Source

- Source PDF: `../live12-manual-en.pdf`
- PDF title: Ableton Reference Manual Version 12
- Generated: {today}
- Platform policy: macOS-only extraction and answers.

The generated chapter Markdown is a study and lookup layer. Keep the PDF as the source of truth when exact phrasing or diagrams matter.
""",
        encoding="utf-8",
    )


def build_machine_indexes(toc: list[TocEntry], chapter_paths: dict[str, str]) -> None:
    data_dir = OUT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "section": entry.number,
            "title": entry.title,
            "page": entry.page,
            "level": entry.level,
            "chapter_file": chapter_paths[chapter_for_page(chapter_entries(toc), entry.page).number],
        }
        for entry in toc
    ]
    (data_dir / "toc.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (data_dir / "toc.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "title", "page", "level", "chapter_file"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def clean_generated_dirs() -> None:
    for name in ["chapters", "lookups", "data", "sources"]:
        path = OUT / name
        if path.exists():
            shutil.rmtree(path)
    OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    clean_generated_dirs()
    toc = parse_toc()
    if not toc:
        raise SystemExit("Could not parse table of contents from PDF.")
    pages = split_pdf_pages()
    chapter_paths = build_chapters(toc, pages)
    build_lookup_guides()
    build_toc_files(toc, chapter_paths)
    build_shortcuts(pages, toc)
    build_machine_indexes(toc, chapter_paths)
    print(f"Built Ableton Tutor in {OUT}")
    print(f"Chapters: {len(chapter_paths)}")
    print(f"TOC entries: {len(toc)}")


if __name__ == "__main__":
    main()

"""First-run setup wizard — detects sensible scan candidates on the user's
filesystem and returns approval prompts the agent (in Claude Code) drives
through conversation.

The wizard does NOT scan anything. It surveys, returns candidates with
file counts, and lets the calling agent confirm each with the user before
adding to the manifest.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


# ─── Candidate categories the wizard offers ─────────────────────────────────


@dataclass
class WizardCandidate:
    """One scannable folder the wizard surfaces for approval."""
    category: str              # "user_library_racks", "max_devices", "plugins", ...
    suggested_id: str          # e.g. "user-library-racks"
    type: str                  # scanner type_id
    path: str
    file_count: int            # estimated files (capped during enumeration)
    sample_filenames: list[str]
    description: str           # 1-2 sentence prompt the agent reads to the user
    recommended_default: bool  # whether to auto-confirm (false = always ask)


def survey_filesystem() -> list[WizardCandidate]:
    """Inspect the OS-standard locations + return candidates for approval.

    Does not write anything. Caller (skill/agent) walks each candidate and asks
    the user "scan this? y/n", then calls corpus_add_source for each yes.
    """
    candidates: list[WizardCandidate] = []
    if platform.system() == "Darwin":
        candidates.extend(_macos_candidates())
    elif platform.system() == "Windows":
        candidates.extend(_windows_candidates())
    else:
        candidates.extend(_linux_candidates())
    return [c for c in candidates if c.file_count > 0]


def _count_files(root: Path, extensions: Iterable[str], cap: int = 5000) -> tuple[int, list[str]]:
    """Count files matching any of the extensions under root. Return (count, samples).

    Cap prevents pathological scans during the survey. Caller should still rescan
    for real (the wizard is just for sizing + showing the user what's there).
    """
    if not root.exists():
        return 0, []
    exts = tuple(e.lower() for e in extensions)
    count = 0
    samples: list[str] = []
    try:
        for p in root.rglob("*"):
            try:
                if not p.is_file() and not p.is_dir():
                    continue
                # Bundle-style "files" (.amxd, .vst3) appear as dirs OR files
                # depending on OS — count both
                if p.suffix.lower() in exts:
                    count += 1
                    if len(samples) < 5:
                        samples.append(p.name)
                    if count >= cap:
                        break
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return count, samples


def _macos_candidates() -> list[WizardCandidate]:
    home = Path.home()
    out: list[WizardCandidate] = []

    # 1. User Library racks (.adg / .adv)
    user_lib = home / "Music/Ableton/User Library/Presets"
    if user_lib.exists():
        n, samples = _count_files(user_lib, [".adg", ".adv"])
        if n > 0:
            out.append(WizardCandidate(
                category="user_library_racks", suggested_id="user-library-racks",
                type="adg", path=str(user_lib), file_count=n, sample_filenames=samples,
                description=(
                    f"Ableton User Library — {n} rack/effect presets (.adg/.adv). "
                    "Indexes every saved chain you've made + third-party racks under "
                    "your User Library. Good first scan."
                ),
                recommended_default=True,
            ))

    # 2. Max for Live devices (.amxd) — multiple plausible locations
    for label, p in (
        ("max_for_live_devices", home / "Documents/Max 9/Max for Live Devices"),
        ("max_for_live_devices_v8", home / "Documents/Max 8/Max for Live Devices"),
        ("user_library_m4l", home / "Music/Ableton/User Library/MAX MONTY/m4l_2024"),
        ("user_library_m4l_alt", home / "Music/Ableton/User Library/Presets/Audio Effects/Max Audio Effect"),
    ):
        if p.exists():
            n, samples = _count_files(p, [".amxd"])
            if n > 0:
                out.append(WizardCandidate(
                    category="max_devices", suggested_id=label.replace("_", "-"),
                    type="amxd", path=str(p), file_count=n, sample_filenames=samples,
                    description=(
                        f"Max for Live devices at {p.name} — {n} .amxd files. "
                        "Captures device type (audio/instrument/midi), Max version, "
                        "and any Live-exposed parameters."
                    ),
                    recommended_default=True,
                ))

    # 3. Plugin presets (.aupreset / .vstpreset / .fxp / .nksf)
    for label, p in (
        ("au_presets", home / "Library/Audio/Presets"),
        ("vst3_presets", home / "Library/Audio/VST3 Presets"),
    ):
        if p.exists():
            n, samples = _count_files(p, [".aupreset", ".vstpreset", ".fxp", ".fxb", ".nksf"])
            if n > 0:
                out.append(WizardCandidate(
                    category="plugin_presets", suggested_id=label.replace("_", "-"),
                    type="plugin-preset", path=str(p), file_count=n, sample_filenames=samples,
                    description=(
                        f"Plugin presets at {p.name} — {n} preset files. Captures "
                        "plugin name + vendor + format. Param values are opaque per-plugin "
                        "binary (same as PluginDevice in .als)."
                    ),
                    recommended_default=False,  # often noisy — opt-in
                ))

    # 4. Sample library (audio files) — .wav/.aif/.flac
    # Note: corpus has no built-in sample scanner yet; these are advisory.
    for label, p in (
        ("apple_loops", Path("/Library/Audio/Apple Loops")),
        ("user_apple_loops", home / "Library/Audio/Apple Loops"),
        ("user_samples", home / "Music/Samples"),
    ):
        if p.exists():
            n, _ = _count_files(p, [".wav", ".aif", ".aiff", ".flac"])
            if n > 0:
                out.append(WizardCandidate(
                    category="samples_advisory", suggested_id=label.replace("_", "-"),
                    type="sample",  # NOTE: scanner not yet implemented
                    path=str(p), file_count=n, sample_filenames=[],
                    description=(
                        f"Sample library at {p.name} — {n} audio files. "
                        "(Sample scanner is not yet implemented — this is a survey "
                        "preview only. Skip for now or wait for the next build.)"
                    ),
                    recommended_default=False,
                ))

    # 5. Plugins are NOT a corpus_add_source — they're handled by
    # corpus_detect_plugins. Surface as a separate "want to detect plugins?" step.
    return out


def _windows_candidates() -> list[WizardCandidate]:
    home = Path.home()
    out: list[WizardCandidate] = []
    user_lib = home / "Documents" / "Ableton" / "User Library" / "Presets"
    if user_lib.exists():
        n, samples = _count_files(user_lib, [".adg", ".adv"])
        if n > 0:
            out.append(WizardCandidate(
                category="user_library_racks", suggested_id="user-library-racks",
                type="adg", path=str(user_lib), file_count=n, sample_filenames=samples,
                description=f"Ableton User Library racks — {n} .adg/.adv presets.",
                recommended_default=True,
            ))
    return out


def _linux_candidates() -> list[WizardCandidate]:
    return []  # Ableton Live isn't supported on Linux; corpus is mostly empty there


# ─── Aggregate decision packet ──────────────────────────────────────────────


def build_setup_proposal() -> dict:
    """Return the full first-run setup proposal: candidates + plugin-detection prompt.

    Caller (skill/agent) walks each item, confirms with user, then dispatches
    corpus_add_source / corpus_detect_plugins as approved.
    """
    candidates = survey_filesystem()
    return {
        "candidates": [asdict(c) for c in candidates],
        "candidate_count": len(candidates),
        "categories": sorted({c.category for c in candidates}),
        "plugin_detection_offer": {
            "prompt": (
                "Also detect installed VST3/AU/VST2/AAX plugins via "
                "corpus_detect_plugins? This walks the OS-standard plugin "
                "folders, parses each bundle's identity metadata, and writes "
                "_inventory.json. Independent of the file scans above."
            ),
            "tool": "corpus_detect_plugins",
            "recommended_default": True,
        },
        "instructions": (
            "Walk the user through each candidate one at a time. For each, "
            "summarize file_count + path + description, then ASK 'add this?' "
            "and only call corpus_add_source on yes. After all candidates are "
            "decided, ask about plugin_detection_offer separately. Finally "
            "call corpus_scan() to index everything they approved."
        ),
        "do_not_scan": [
            "Personal .als project folders unless the user explicitly points at one — "
            "they're sensitive content that the user should opt into per-folder."
        ],
        "schema_version": 1,
    }

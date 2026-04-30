"""Phase 2.3 + 2.4 — Manual discovery + extraction.

Given a DetectedPlugin, glob the standard manual locations + extract text from
the most promising file. Supports .pdf (pypdf with pdfplumber fallback), .html
(bs4), .md / .txt / .rtf (raw read).

Section splitter recognizes common chapter heading patterns and produces a
sections.json mapping section title → text range.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .detector import DetectedPlugin

logger = logging.getLogger(__name__)


_MANUAL_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".txt", ".rtf"}
_MANUAL_NAME_HINTS = (
    "manual", "guide", "reference", "documentation", "user", "handbook", "readme",
)
# Anti-hints: filenames containing these are NOT plugin manuals even if the
# extension matches. Filters out the log/cache/preset noise that lives in
# Application Support directories.
_MANUAL_NAME_ANTIHINTS = (
    "log", "cache", "settings", "prefs", "preferences", "tmp", "temp",
    "crash", "error", "debug", "trace", "history", "registry", "license",
    "credits", "thirdparty", "third-party", "third_party", "uninstall",
    "lockfile", "lock-file", ".lock",
)
# Non-extension names we also reject (case-insensitive substring on the stem)
_MANUAL_REJECT_STEMS = (
    "package-info", "buildinfo", "version", "checksum",
)


@dataclass
class ManualCandidate:
    path: str
    extension: str
    size_kb: int
    name_score: float          # higher = filename more clearly a manual
    location_score: int        # higher = more authoritative location

    def __lt__(self, other: "ManualCandidate") -> bool:
        # sort: location first, then name score, then size descending
        return (
            self.location_score, self.name_score, self.size_kb,
        ) > (
            other.location_score, other.name_score, other.size_kb,
        )


@dataclass
class ManualExtraction:
    plugin_id: str
    source_path: str
    source_kind: str               # pdf | html | md | txt | rtf
    text: str
    char_count: int
    page_count: int | None = None
    sections: list[dict] = field(default_factory=list)  # [{title, start, end}]
    truncated: bool = False
    error: str | None = None


# ─── Discovery ──────────────────────────────────────────────────────────────


def discover_manuals_for_plugin(
    plugin: DetectedPlugin,
    extra_search_dirs: list[Path] | None = None,
    max_candidates: int = 20,
) -> list[ManualCandidate]:
    """Glob the standard manual locations and return ranked candidates.

    Search priority (high to low):
      1. Inside the bundle: <bundle>/Contents/Resources/
      2. /Applications/<vendor>*.app/Contents/Resources/
      3. /Library/Audio/Plug-Ins/<format>/<vendor>/Documentation/
      4. ~/Documents/<vendor>/, ~/Documents/<plugin>/
      5. /Library/Application Support/<vendor>/
    """
    candidates: list[ManualCandidate] = []
    bundle = Path(plugin.bundle_path)
    vendor = plugin.vendor or ""
    name = plugin.name

    search_locations = _enumerate_search_locations(bundle, vendor, name)
    for extra in (extra_search_dirs or []):
        search_locations.append((extra, 1))  # extras get baseline location score

    for loc, loc_score in search_locations:
        if not loc.exists():
            continue
        try:
            for path in _walk_for_manuals(loc, max_depth=4):
                cand = _score_candidate(path, loc_score)
                if cand:
                    candidates.append(cand)
                if len(candidates) >= max_candidates * 3:
                    break
        except (PermissionError, OSError):
            continue

    # Dedupe by path; sort
    seen: dict[str, ManualCandidate] = {}
    for c in candidates:
        if c.path not in seen or c < seen[c.path]:
            seen[c.path] = c
    ranked = sorted(seen.values())
    return ranked[:max_candidates]


def _enumerate_search_locations(
    bundle: Path, vendor: str, name: str,
) -> list[tuple[Path, int]]:
    """Build the (path, location_score) list to search. Higher score = more authoritative."""
    home = Path.home()
    out: list[tuple[Path, int]] = []
    # Score 5: inside the bundle
    out.append((bundle / "Contents" / "Resources", 5))
    # Score 4: vendor app + format-specific docs folder
    if vendor:
        for slug in (vendor, vendor.replace(" ", ""), vendor.lower()):
            apps = Path("/Applications").glob(f"*{slug}*.app")
            for app in apps:
                out.append((app / "Contents" / "Resources", 4))
            out.append((Path(f"/Library/Audio/Plug-Ins/VST3/{slug}/Documentation"), 4))
            out.append((Path(f"/Library/Audio/Plug-Ins/Components/{slug}/Documentation"), 4))
    # Score 3: ~/Documents/<vendor>/, ~/Documents/<plugin>/
    if vendor:
        out.append((home / "Documents" / vendor, 3))
    out.append((home / "Documents" / name, 3))
    # Score 2: /Library/Application Support/<vendor>/
    if vendor:
        out.append((Path("/Library/Application Support") / vendor, 2))
        out.append((home / "Library" / "Application Support" / vendor, 2))
    return out


def _walk_for_manuals(root: Path, max_depth: int = 4):
    """Yield manual-extension files within a directory tree (depth-bounded)."""
    if not root.exists():
        return
    base_depth = len(root.parts)
    try:
        for path in root.rglob("*"):
            try:
                if not path.is_file():
                    continue
                if (len(path.parts) - base_depth) > max_depth:
                    continue
                if path.suffix.lower() in _MANUAL_EXTENSIONS:
                    yield path
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        return


def _score_candidate(path: Path, location_score: int) -> ManualCandidate | None:
    try:
        size_kb = int(path.stat().st_size / 1024)
    except OSError:
        return None
    if size_kb < 1:
        return None  # 0-byte files
    name_lower = path.name.lower()
    stem_lower = path.stem.lower()

    # Reject if any anti-hint matches — these are logs/caches/settings, not manuals
    for anti in _MANUAL_NAME_ANTIHINTS:
        if anti in name_lower:
            return None
    for anti in _MANUAL_REJECT_STEMS:
        if anti in stem_lower:
            return None
    # Reject any path whose immediate parent dir is named "logs", "cache", "tmp"
    parent_lower = path.parent.name.lower()
    if parent_lower in ("logs", "cache", "tmp", "temp", "crash", "trash"):
        return None

    name_score = 0.0
    for hint in _MANUAL_NAME_HINTS:
        if hint in name_lower:
            name_score += 1.0
    # Strong prior for "manual" specifically
    if "manual" in name_lower:
        name_score += 1.5
    if path.suffix.lower() == ".pdf":
        name_score += 0.5
    # Require at least SOME positive signal: a name hint OR a PDF in a
    # high-priority location. This blocks generic .txt files that aren't manuals.
    if name_score == 0.0 and location_score < 4:
        return None
    return ManualCandidate(
        path=str(path), extension=path.suffix.lower(),
        size_kb=size_kb, name_score=name_score, location_score=location_score,
    )


# ─── Extraction ─────────────────────────────────────────────────────────────


_MAX_CHAR_OUTPUT = 1_000_000   # cap so a 5000-page manual doesn't blow context


def extract_manual_text(
    plugin: DetectedPlugin, candidate: ManualCandidate,
) -> ManualExtraction:
    """Extract text from a manual candidate. Never raises."""
    path = Path(candidate.path)
    ext = candidate.extension
    try:
        if ext == ".pdf":
            text, pages = _extract_pdf(path)
            kind = "pdf"
        elif ext in (".html", ".htm"):
            text = _extract_html(path)
            pages = None
            kind = "html"
        elif ext == ".rtf":
            text = _extract_rtf(path)
            pages = None
            kind = "rtf"
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
            pages = None
            kind = ext.lstrip(".")
    except Exception as e:  # noqa: BLE001
        return ManualExtraction(
            plugin_id=plugin.plugin_id, source_path=str(path),
            source_kind=ext.lstrip("."), text="", char_count=0,
            page_count=None, sections=[], truncated=False,
            error=f"{type(e).__name__}: {e}",
        )

    truncated = False
    if len(text) > _MAX_CHAR_OUTPUT:
        text = text[:_MAX_CHAR_OUTPUT]
        truncated = True

    sections = _detect_sections(text)
    return ManualExtraction(
        plugin_id=plugin.plugin_id, source_path=str(path),
        source_kind=kind, text=text, char_count=len(text),
        page_count=pages, sections=sections, truncated=truncated,
    )


def _extract_pdf(path: Path) -> tuple[str, int]:
    """Extract text from a PDF. Try pypdf first, fall back to pdfplumber."""
    pages = 0
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        chunks: list[str] = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                continue
            pages += 1
        text = "\n\n".join(chunks)
        if text.strip():
            return text, pages
    except Exception as e:  # noqa: BLE001
        logger.debug("pypdf failed on %s: %s; trying pdfplumber", path, e)
    # Fallback
    try:
        import pdfplumber
        chunks: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                try:
                    chunks.append(page.extract_text() or "")
                except Exception:  # noqa: BLE001
                    continue
                pages += 1
        return "\n\n".join(chunks), pages
    except Exception as e:  # noqa: BLE001
        logger.warning("pdfplumber also failed on %s: %s", path, e)
        raise


def _extract_html(path: Path) -> str:
    from bs4 import BeautifulSoup
    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _extract_rtf(path: Path) -> str:
    """Crude RTF stripper — drops control words + groups."""
    raw = path.read_text(encoding="latin-1", errors="ignore")
    # Strip control words like \word123 and groups
    text = re.sub(r"\\[a-z]+-?\d* ?", "", raw)
    text = re.sub(r"[{}]", "", text)
    return text


# ─── Section detection ──────────────────────────────────────────────────────


_HEADING_PATTERNS = [
    re.compile(r"^\s*(?:CHAPTER\s+\d+\s*[:.\s-]+)?([A-Z][A-Z0-9 \-&,'/]{3,60})\s*$",
               re.MULTILINE),
    re.compile(r"^\s*\d+(?:\.\d+)?\s+([A-Z][\w\s\-&,'/]{3,60})\s*$", re.MULTILINE),
    re.compile(r"^#{1,3}\s+(.{3,80}?)\s*$", re.MULTILINE),  # markdown
]

_KNOWN_SECTION_KEYWORDS = (
    "parameters", "controls", "modulation", "matrix", "envelopes", "lfo",
    "filter", "filters", "oscillator", "oscillators", "effects", "fx",
    "presets", "tutorials", "tutorial", "introduction", "overview",
    "installation", "getting started", "performance", "automation",
    "midi", "macros", "global", "interface", "browser", "library",
)


def _detect_sections(text: str) -> list[dict]:
    """Best-effort section splitter. Returns at most 50 sections."""
    headings: list[tuple[int, str]] = []
    for pat in _HEADING_PATTERNS:
        for m in pat.finditer(text):
            title = m.group(1).strip()
            start = m.start()
            if 4 <= len(title) <= 60 and title not in (h[1] for h in headings):
                # Bias toward known section keywords
                low = title.lower()
                score = sum(1 for kw in _KNOWN_SECTION_KEYWORDS if kw in low)
                if score > 0 or len(headings) < 30:
                    headings.append((start, title))
    headings.sort()
    sections: list[dict] = []
    for i, (start, title) in enumerate(headings[:50]):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        sections.append({"title": title, "start": start, "end": end})
    return sections

"""Local-first sample resolution for composer plans.

Moves sample resolution from execution time (where the old pseudo-tool
_agent_pick_best_sample was supposed to "figure it out") to plan time.

Async because splice_remote downloads real samples over gRPC. Filesystem-only
callers still work synchronously from an async perspective — the function
only awaits when it actually has to hit the network.

Returns (local_path, source) where source is one of:
  'filesystem'    — hit in a provided search_root directory (no network)
  'splice_local'  — Splice catalog hit that's already downloaded (no credit spend)
  'splice_remote' — Splice catalog hit that required download (1 credit)
  'browser'       — Ableton browser match with a local path
  'unresolved'    — no match; caller drops the layer from the plan and warns

Preference order is fixed: filesystem > splice_local > splice_remote > browser.
Filesystem wins even if Splice has a faster hit — local files are free.

Role-aware filesystem ranking (v1.10.3)
----------------------------------------
Filesystem matching used to return the first file whose name contained the
role OR any query token. This caused obvious musical mistakes — a `lead`
layer would get matched to `drums_techno.wav` because both share the genre
token "techno". The Truth Release (v1.10.3) replaces that with a scored
ranker that considers:

  * role word in filename                 (+3.0)
  * filename's primary role == layer role (+1.5 bonus)
  * filename's primary role == a DIFFERENT role (-5.0 penalty)
  * role-adjacent hint words (e.g. kick/snare for drums) (+2.0)
  * query token overlap, excluding the role word itself (+0.5 per token)
  * tempo token (e.g. "128bpm") shared between filename and query (+1.0)

A candidate must score strictly above 0.0 to be returned. This blocks the
obvious failure mode where genre-only matches override role matches or
where unrelated files with no signal get returned just because they're
the first audio file found.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from .layer_planner import LayerSpec


_AUDIO_EXTENSIONS = (".wav", ".aif", ".aiff", ".flac")

# Role-adjacent hint words (NOT the role itself — that's scored separately).
# These are words commonly found in filenames that indicate the layer role
# without using the literal role name.
_ROLE_HINTS: dict[str, frozenset[str]] = {
    "drums":      frozenset(["kick", "snare", "hat", "clap", "perc", "break", "beat", "loop", "hihat"]),
    "bass":       frozenset(["sub", "808", "low", "deep", "bassline"]),
    "lead":       frozenset(["synth", "arp", "mel", "melody", "riff", "hook"]),
    "pad":        frozenset(["ambient", "atmos", "drone", "string", "warm"]),
    "texture":    frozenset(["atmos", "ambient", "drone", "swell", "noise"]),
    "vocal":      frozenset(["vox", "voice", "chop", "phrase", "acapella"]),
    "percussion": frozenset(["shaker", "tamb", "bongo", "conga", "tom", "ride", "cowbell"]),
    "fx":         frozenset(["sfx", "riser", "impact", "sweep", "whoosh", "rise", "fall", "hit"]),
}

# Flat set of every known "primary role word" that might appear at the start
# of a filename. Used to classify a filename's dominant role.
_ALL_ROLE_WORDS: frozenset[str] = frozenset(
    {role for role in _ROLE_HINTS}
    | {"drum"}  # singular form of "drums"
    | {h for hints in _ROLE_HINTS.values() for h in hints}
)

# Tempo token pattern — matches 2-3 digit BPM values in filenames like
# "kick_128bpm.wav", "drums_120_loop.wav", "bass128.wav".
_TEMPO_RE = re.compile(r"(\d{2,3})")


def _query_tokens(query: str) -> list[str]:
    """Return lowercase query tokens meaningful for matching (len > 2)."""
    return [t.lower() for t in query.split() if len(t) > 2]


def _iter_candidates(root: Path):
    """Yield all audio-format files beneath root."""
    if not root.exists():
        return
    for ext in _AUDIO_EXTENSIONS:
        yield from root.rglob(f"*{ext}")


def _primary_role_of(filename_stem: str) -> Optional[str]:
    """Identify the dominant 'role' of a filename based on its first token.

    Example: "drums_techno_128.wav" -> "drums". "bass_sub_808.aif" -> "bass".
    Returns None if the first token isn't a known role word.
    """
    # Split on underscores, hyphens, spaces, dots
    parts = re.split(r"[_\-\s.]+", filename_stem.lower())
    for p in parts:
        if p in _ALL_ROLE_WORDS:
            return p
    return None


def _role_matches(primary: str, role: str) -> bool:
    """True if the filename's primary role belongs to the same role family
    as the layer's role (handles role == 'drums' vs primary == 'kick')."""
    if primary == role:
        return True
    # "drum" is the singular of "drums"
    if primary == "drum" and role == "drums":
        return True
    # primary is one of the role's hints (e.g. "kick" is a drum hint)
    hints = _ROLE_HINTS.get(role, frozenset())
    return primary in hints


def _score_candidate(path: Path, layer: LayerSpec, query_tempos: set[str]) -> float:
    """Return a ranking score for this candidate file.

    Scores combine role fit, role hints, query tokens, and tempo match.
    A negative score is possible (and disqualifying) when the filename's
    primary role is clearly a DIFFERENT role family — that blocks the
    "lead layer grabs drums via shared genre token" failure pattern.
    """
    name = path.stem.lower()
    role = (layer.role or "").lower()
    score = 0.0

    # 1. Role word literally in filename
    if role and role in name:
        score += 3.0

    # 2. Primary-role classification of the filename
    primary = _primary_role_of(name)
    if primary:
        if _role_matches(primary, role):
            score += 1.5  # bonus: filename is "about" this layer's role
        else:
            score -= 5.0  # heavy penalty: filename is about a different role

    # 3. Role-adjacent hint words in filename
    hints = _ROLE_HINTS.get(role, frozenset())
    for hint in hints:
        if hint in name:
            score += 2.0
            break  # count at most once

    # 4. Query token overlap (excluding the role word — already scored above)
    tokens = _query_tokens(layer.search_query)
    for tok in tokens:
        if tok == role:
            continue
        if tok in name:
            score += 0.5

    # 5. Tempo match — if query mentions e.g. "128bpm" and filename has "128"
    if query_tempos:
        filename_tempos = set(_TEMPO_RE.findall(name))
        # Only count digits that are plausible BPMs (60-200)
        filename_tempos = {t for t in filename_tempos if 60 <= int(t) <= 200}
        if query_tempos & filename_tempos:
            score += 1.0

    return score


def _extract_query_tempos(query: str) -> set[str]:
    """Pull tempo tokens (e.g. '128bpm', '120') out of a search query."""
    tempos = set()
    for match in _TEMPO_RE.findall(query.lower()):
        if 60 <= int(match) <= 200:
            tempos.add(match)
    return tempos


def _filesystem_match(layer: LayerSpec, search_roots: list[Path]) -> Optional[str]:
    """Score every audio file across the search_roots and return the best.

    Returns None if no file scores above zero. "Above zero" is the
    threshold for "has any role or token signal" — anything at or below
    zero is considered unresolved (to avoid returning arbitrary files
    that happen to be first in alphabetical order).
    """
    query_tempos = _extract_query_tempos(layer.search_query)

    best_path: Optional[Path] = None
    best_score: float = 0.0  # must strictly exceed this to win

    for root in search_roots:
        for path in _iter_candidates(Path(root)):
            score = _score_candidate(path, layer, query_tempos)
            if score > best_score:
                best_score = score
                best_path = path

    return str(best_path) if best_path is not None else None


async def _splice_resolve(
    layer: LayerSpec,
    splice_client: object,
    credit_budget: int,
) -> Tuple[Optional[str], str]:
    """Query Splice for the layer. Returns (path, source) or (None, 'unresolved').

    Tries local hits first (free), then remote downloads (1 credit each,
    respecting the hard floor). Stops on first success.
    """
    if splice_client is None or not getattr(splice_client, "connected", False):
        return None, "unresolved"

    try:
        result = await splice_client.search_samples(
            query=layer.search_query,
            per_page=5,
        )
    except Exception:
        return None, "unresolved"

    samples = list(result.samples) if result and hasattr(result, "samples") else []
    if not samples:
        return None, "unresolved"

    # 1. Prefer already-local Splice hits (zero credit spend)
    for sample in samples:
        lp = getattr(sample, "local_path", "") or ""
        if lp and Path(lp).exists():
            return lp, "splice_local"

    # 2. Remote download — respect the credit hard floor
    for sample in samples:
        if getattr(sample, "local_path", ""):
            continue  # already handled above
        file_hash = getattr(sample, "file_hash", "")
        if not file_hash:
            continue
        try:
            can, _remaining = await splice_client.can_afford(1, credit_budget)
            if not can:
                break  # credit floor hit — stop trying, don't try next sample
            downloaded = await splice_client.download_sample(file_hash)
            if downloaded and Path(downloaded).exists():
                return downloaded, "splice_remote"
        except Exception:
            continue  # try next hit

    return None, "unresolved"


async def resolve_sample_for_layer(
    layer: LayerSpec,
    search_roots: Optional[list] = None,
    splice_client: object = None,
    browser_client: object = None,
    credit_budget: int = 1,
) -> Tuple[Optional[str], str]:
    """Resolve a layer's sample to a concrete local file path.

    Preference order: filesystem > splice_local > splice_remote > browser.
    Unresolved layers return (None, 'unresolved'); callers drop them from
    the plan and surface a warning.

    search_roots accepts Path or str entries. Missing dirs are silently
    skipped. None entries are filtered out.
    """
    roots = [Path(r) for r in (search_roots or []) if r]

    # 1. Filesystem — always try first, no network. Scored ranking since v1.10.3.
    fs_hit = _filesystem_match(layer, roots)
    if fs_hit:
        return fs_hit, "filesystem"

    # 2 & 3. Splice (local hits + remote download)
    path, source = await _splice_resolve(layer, splice_client, credit_budget)
    if path is not None:
        return path, source

    # 4. Browser (sync, optional)
    if browser_client is not None:
        try:
            search = getattr(browser_client, "search", None)
            hits = search(layer.search_query, limit=5) if callable(search) else []
            for hit in hits or []:
                lp = hit.get("file_path") if isinstance(hit, dict) else None
                if lp and Path(lp).exists():
                    return lp, "browser"
        except Exception:
            pass

    return None, "unresolved"

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
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from .layer_planner import LayerSpec


_AUDIO_EXTENSIONS = (".wav", ".aif", ".aiff", ".flac")


def _query_tokens(query: str) -> list[str]:
    """Return lowercase query tokens meaningful for matching (len > 2)."""
    return [t.lower() for t in query.split() if len(t) > 2]


def _iter_candidates(root: Path):
    """Yield all audio-format files beneath root."""
    if not root.exists():
        return
    for ext in _AUDIO_EXTENSIONS:
        yield from root.rglob(f"*{ext}")


def _filesystem_match(layer: LayerSpec, search_roots: list[Path]) -> Optional[str]:
    """First filename-substring match on role or any query token.

    Sync helper — no network, no async needed.
    """
    tokens = _query_tokens(layer.search_query)
    role = layer.role.lower()
    for root in search_roots:
        for path in _iter_candidates(Path(root)):
            name = path.name.lower()
            if role and role in name:
                return str(path)
            if any(tok in name for tok in tokens):
                return str(path)
    return None


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

    # 1. Filesystem — always try first, no network
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

"""Local-first sample resolution for composer plans.

Moves sample resolution from execution time (where the old pseudo-tool
_agent_pick_best_sample was supposed to "figure it out") to plan time.
Returns (local_path, source) where source is one of:
  'filesystem'   — hit in a provided search_root directory
  'splice_local' — hit in the Splice catalog that maps to a local file
  'browser'      — Ableton browser match with a local path
  'unresolved'   — no match; caller drops the layer from the plan and warns

The composer uses the returned path to emit a concrete load_sample_to_simpler
step instead of a {downloaded_path} placeholder. Layers that can't be
resolved are kept in the descriptive 'layers' field but omitted from 'plan'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from .layer_planner import LayerSpec


_AUDIO_EXTENSIONS = (".wav", ".aif", ".aiff", ".flac")


def _query_tokens(query: str) -> list[str]:
    """Return lowercase query tokens that are meaningful for matching (len > 2)."""
    return [t.lower() for t in query.split() if len(t) > 2]


def _iter_candidates(root: Path):
    """Yield all audio-format files beneath root."""
    if not root.exists():
        return
    for ext in _AUDIO_EXTENSIONS:
        yield from root.rglob(f"*{ext}")


def _filesystem_match(layer: LayerSpec, search_roots: list[Path]) -> Optional[str]:
    """Walk search_roots looking for a file whose name contains any query token
    or the layer's role. Returns the first hit's path as a string, or None.
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


def resolve_sample_for_layer(
    layer: LayerSpec,
    search_roots: Optional[list] = None,
    splice_client: object = None,
    browser_client: object = None,
) -> Tuple[Optional[str], str]:
    """Resolve a layer's sample to a concrete local file path.

    Order of preference:
      1. filesystem  — caller-provided sample directories (fastest, no API)
      2. splice_local — local hits in Splice catalog (if client supplied)
      3. browser      — Ableton browser match (if client supplied)
      4. unresolved

    search_roots accepts Path or str entries. None and missing dirs are ignored.
    """
    roots = [Path(r) for r in (search_roots or []) if r]

    # 1. Filesystem
    fs_hit = _filesystem_match(layer, roots)
    if fs_hit:
        return fs_hit, "filesystem"

    # 2. Splice local (optional — no crash if client missing or fails)
    if splice_client is not None:
        try:
            search = getattr(splice_client, "search_local", None)
            hits = search(layer.search_query, limit=5) if callable(search) else []
            for hit in hits or []:
                lp = hit.get("local_path") if isinstance(hit, dict) else None
                if lp and Path(lp).exists():
                    return lp, "splice_local"
        except Exception:
            pass

    # 3. Browser (optional)
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

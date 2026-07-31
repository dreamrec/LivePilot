"""MCP surface for the learned taste head.

The loop this closes:

    capture_audio(before) -> move -> capture_audio(after)
    listen_ab(...)                              # did it change, and how
    <you or the agent decide: keep or undo>
    taste_record_pair(kept, discarded)          # <- the decision becomes data
    taste_train()                               # once you have enough
    taste_rank([candidates...])                 # future moves ranked by taste

Every kept/undone decision is a pairwise preference. Recorded, they train a
Bradley-Terry head over CLAP embeddings — a model of what YOU keep, learned
from audio rather than from named qualities. It complements the symbolic taste
system in `memory/` (dimension weights, device affinities); that side explains
*why*, this side notices *that*.

Needs the optional embedding extra (``pip install torch transformers``); every
tool degrades to an install hint without it.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ..server import mcp
from . import taste_head
from .tools import _analyze_ex

_EXTRA_HINT = (
    "Optional embedding backend not installed. "
    "pip install torch transformers  (~2 GB; weights download from "
    "HuggingFace on first use and are not redistributed by LivePilot)"
)

_store: Optional[taste_head.TasteHeadStore] = None


def _get_store() -> taste_head.TasteHeadStore:
    global _store
    if _store is None:
        _store = taste_head.TasteHeadStore()
    return _store


def _embed_file(file: str) -> tuple[Optional[np.ndarray], Optional[str]]:
    """(embedding, model_id) for a capture, or (None, None)."""
    from . import embedding  # noqa: PLC0415

    if not embedding.is_available():
        return None, None
    _features, audio, sr = _analyze_ex(file, None, None)
    return embedding.embed_audio(audio, sr), embedding.DEFAULT_MODEL


def _derive_group(preferred_file: str, rejected_file: str) -> str:
    """Best-effort session id from the two capture names: their longest common
    run of leading underscore-separated tokens.

    Real capture families look like ``set3_bright_bass_take.wav`` /
    ``..._final.wav`` / ``..._headroom.wav``, so a shared prefix is a good proxy
    for shared material.

    Common prefix rather than each name's own prefix, because a pair compares
    two DIFFERENT renders by construction. Keying off each name separately gives
    ``set3_bright|set3_darker`` — unique to that pair — and a corpus of such
    pairs puts every pair in its own group, which turns leave-one-group-out back
    into the leave-one-pair-out leak it exists to prevent. The common prefix
    collapses both to ``set3``.

    Erring toward FEWER, larger groups is deliberate: over-merging makes the
    reported accuracy pessimistic, under-merging makes it a lie.
    """
    import os  # noqa: PLC0415

    def toks(f: str) -> list[str]:
        return os.path.splitext(os.path.basename(f))[0].split("_")

    a, b = toks(preferred_file), toks(rejected_file)
    shared: list[str] = []
    for x, y in zip(a, b):
        if x != y:
            break
        shared.append(x)
    if shared:
        return "_".join(shared)
    # Nothing in common — no basis for claiming shared material.
    return f"{'_'.join(a)}|{'_'.join(b)}"


@mcp.tool()
def taste_record_pair(
    preferred_file: str,
    rejected_file: str,
    note: str = "",
    group: str = "",
) -> dict[str, Any]:
    """Record one kept-over-discarded decision as training data.

    ``preferred_file`` is the capture you KEPT, ``rejected_file`` the one you
    moved on from — both capture names or absolute paths. Order matters: it is
    the label.

    Call this at the moment of decision, when you know which render survived.
    A pair is cheap and reversible; the model is only as good as the honesty of
    these labels, so record what you actually preferred rather than what you
    think you should have.

    ``group`` marks which session/material the pair came from, and defaults to
    the shared prefix of the two filenames. It matters more than it looks:
    cross-validation holds out whole groups, because several pairs from one
    session make each other trivially easy to predict. On real captures that
    difference was 100% versus 57%. Set it explicitly if the filenames do not
    reflect the true grouping.

    Two things about HOW you compare, which matter more than how many pairs you
    record. Do not A/B every candidate against one fixed baseline — not even a
    re-captured one, since ``capture_audio`` records live playback and produces
    a different file each time for the same material. Pairs sharing a reference
    are one piece of evidence, not several, and a corpus built that way cannot
    be certified at all (see ``anchor_asymmetry`` in the train report). Compare
    candidates against EACH OTHER. And record from at least
    ``taste_head.MIN_GROUPS_FOR_SIGNIFICANCE`` separate sessions — significance
    counts sessions, not pairs, so more pairs from the sessions you already have
    will not move it.

    Recording invalidates any previously fitted head — rerun ``taste_train``.
    """
    pv, model = _embed_file(preferred_file)
    if pv is None:
        return {"recorded": False, "reason": _EXTRA_HINT}
    rv, _ = _embed_file(rejected_file)
    if rv is None:
        return {"recorded": False, "reason": _EXTRA_HINT}

    grp = group or _derive_group(preferred_file, rejected_file)
    try:
        data = _get_store().add_pair(pv, rv, model, note, group=grp)
    except ValueError as exc:
        return {"recorded": False, "reason": str(exc)}

    pairs = data.get("pairs", [])
    n = len(pairs)
    n_groups = len({p.get("group") or "" for p in pairs})
    remaining = max(0, taste_head.MIN_PAIRS - n)
    if remaining:
        nxt = f"{remaining} more pair(s) before training says anything"
    elif n_groups < 2:
        nxt = ("ready to train, but all pairs share one group — the score will "
               "be flagged OPTIMISTIC until a second session is recorded")
    else:
        nxt = "ready — run taste_train"
    return {
        "recorded": True,
        "n_pairs": n,
        "n_groups": n_groups,
        "group": grp,
        "model": model,
        "next": nxt,
    }


@mcp.tool()
def taste_train(l2: float = taste_head.DEFAULT_L2) -> dict[str, Any]:
    """Fit the taste head and report how much it actually learned.

    Returns cross-validated accuracy, a p-value against chance, and a
    plain-language verdict.

    Read the verdict, not the accuracy. Training accuracy is deliberately NOT
    reported: CLAP embeddings are 512-dimensional and a realistic corpus is
    tens of pairs, so a linear head fits ~100% of the training data whether or
    not it learned anything — including on random labels. Even held-out
    accuracy needs the significance test: measured on synthetic data, 20 pairs
    of pure noise produced 65% leave-one-out accuracy, indistinguishable from a
    genuinely learnable signal at that sample size.

    ``significant`` has three states and they are not interchangeable.
    ``true`` is earned. ``false`` means tested and failed. ``null`` means it
    could not be tested at all — too few independent sessions, or the pairs
    turned out to share captures. Treat ``null`` exactly as you would
    ``false``: as no evidence.

    ``groups_merged`` and ``shared_reference_detected`` are worth reading. They
    fire when sessions you recorded separately turn out to share a reference —
    byte-identical for the first, merely the same material for the second —
    which is the single most common way a corpus looks bigger than the evidence
    in it.

    ``l2`` raises or lowers regularisation. The default is strong on purpose —
    with far more dimensions than pairs, the penalty is what stops the head
    memorising rather than generalising.
    """
    return taste_head.train(_get_store(), l2=l2)


@mcp.tool()
def taste_rank(files: list[str]) -> dict[str, Any]:
    """Rank captures by the learned taste head — best first.

    Pass two or more captures (names or absolute paths) to order them by
    predicted preference. For exactly two, a ``probability`` is included:
    P(first preferred over second) under the fitted head.

    Ranking, not scoring, is the honest interface. Bradley-Terry is
    shift-invariant, so an individual score has no absolute meaning — only
    differences between candidates do. Never threshold a single value.

    Returns an untrained/insufficient state rather than guessing if the head
    has not been fitted, and carries the head's ``cv_accuracy``, ``cv_scheme``
    and ``significant`` flag alongside the ranking so a weak model cannot be
    mistaken for a confident one.
    """
    if not files:
        raise ValueError("files must contain at least one capture")

    store = _get_store()
    data = store.get_all()
    if not data.get("weights"):
        return {
            "ranked": False,
            "reason": (
                f"Taste head not trained ({len(data.get('pairs', []))} pair(s) "
                f"recorded, {taste_head.MIN_PAIRS} needed). Record decisions "
                "with taste_record_pair, then run taste_train."
            ),
        }

    trained = data.get("trained") or {}
    scored = []
    embeddings: dict[str, np.ndarray] = {}
    for f in files:
        vec, _model = _embed_file(f)
        if vec is None:
            return {"ranked": False, "reason": _EXTRA_HINT}
        embeddings[f] = vec
        entry = taste_head.score(store, vec)
        if entry is None:
            return {"ranked": False,
                    "reason": "stored head does not match this embedding model"}
        scored.append({"file": f, "score": entry["score"]})

    scored.sort(key=lambda r: r["score"], reverse=True)
    out: dict[str, Any] = {
        "ranked": True,
        "order": scored,
        "best": scored[0]["file"],
        "cv_accuracy": trained.get("cv_accuracy"),
        "cv_scheme": trained.get("cv_scheme"),
        "significant": trained.get("significant"),
        "n_pairs": trained.get("n_pairs"),
        "note": ("Scores are comparable to each other only — Bradley-Terry is "
                 "shift-invariant. Rank, do not threshold."),
    }
    if not trained.get("significant"):
        out["warning"] = (
            "The head is NOT significantly better than chance on held-out "
            "pairs. This ranking is not trustworthy — record more decisions."
        )
    if len(files) == 2:
        p = taste_head.preference_probability(
            store, embeddings[files[0]], embeddings[files[1]])
        if p is not None:
            out["probability"] = {
                "statement": f"P({files[0]} preferred over {files[1]})",
                "value": round(p, 4),
            }
    return out

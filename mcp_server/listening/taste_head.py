"""Learned taste head — a Bradley-Terry preference model over CLAP embeddings.

WHAT IT IS
----------
Every kept/undone decision is a pairwise preference: this render beat that one.
Bradley-Terry turns a pile of those into a scoring function.

    s(x) = w . x                        (linear head on a frozen embedding)
    P(A preferred over B) = sigmoid(s(A) - s(B)) = sigmoid(w . (x_A - x_B))

Because the head is linear, fitting it is logistic regression on the DIFFERENCE
vectors — convex, no GPU, milliseconds on tens of pairs. There is deliberately
no bias term: Bradley-Terry is shift-invariant, so a bias is unidentifiable.

HOW IT RELATES TO THE EXISTING TASTE SYSTEM
-------------------------------------------
`memory/taste_memory.py` and `_agent_os_engine/taste.py` model taste
*symbolically* — dimension weights, device affinities, anti-preferences, all
keyed off named qualities. This is the complement: it works on the audio
itself, so it can capture preferences nobody has a word for. Neither replaces
the other; the symbolic side explains *why*, this side notices *that*.

THE HONESTY PROBLEM (read this before trusting a score)
--------------------------------------------------------
CLAP embeddings are 512-dimensional and a realistic corpus is tens of pairs.
In that regime a linear model can perfectly separate almost ANY labelling,
including random noise. Training accuracy is therefore meaningless — it will
read ~100% whether or not the head learned anything real.

So this module never reports training accuracy. It reports cross-validated
accuracy, plus an exact binomial p-value against chance, plus a verdict in
words. Two corrections make that honest:

1. GROUPED cross-validation. A session yields several pairs from the same
   material, so holding out one PAIR leaves its siblings in training and the
   held-out pair becomes trivial. Measured on 7 real capture pairs from 3
   sessions: leave-one-pair-out 100%, leave-one-session-out 57%. Whole groups
   are held out whenever there are >= 2 of them; the single-group fallback is
   labelled OPTIMISTIC rather than quietly substituted.

2. Significance. Accuracy alone is uninterpretable at this sample size: 20
   pairs of RANDOM labels produced 65% leave-one-out, matching a genuinely
   learnable signal at the same n. `significant: false` means the number
   carries no information however high it looks.

Regularisation is strong by default for the same reason: with n << d the
penalty is what stops the head memorising.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from ..persistence.base_store import PersistentJsonStore

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".livepilot" / "taste_pairs.json"

# Below this, leave-one-out is not worth reporting — the estimate itself is
# noisier than the thing it measures.
MIN_PAIRS = 5
# n << d, so the penalty is doing the work. Tuned to keep LOO stable rather
# than to minimise training loss (which is always ~0 here anyway).
DEFAULT_L2 = 1.0
_MAX_ITERS = 400
_LR = 0.5
STORE_VERSION = 1


class TasteHeadStore:
    """Persisted preference pairs and the fitted head."""

    def __init__(self, path: Optional[Path] = None):
        self._store = PersistentJsonStore(path or _DEFAULT_PATH)

    @staticmethod
    def _default() -> dict:
        return {"version": STORE_VERSION, "model": None, "pairs": [],
                "weights": None, "trained": None}

    def get_all(self) -> dict:
        data = self._store.read()
        return data if data else self._default()

    def add_pair(self, preferred: np.ndarray, rejected: np.ndarray,
                 model: str, note: str = "", group: str = "") -> dict:
        """Append one preference. Refuses to mix embedding models, because
        vectors from different models are not comparable and silently blending
        them would poison every later fit."""
        def _update(data: dict) -> dict:
            if not data:
                data = self._default()
            existing = data.get("model")
            if existing and existing != model:
                raise ValueError(
                    f"Stored pairs use embedding model {existing!r} but this "
                    f"one is {model!r}. Vectors from different models are not "
                    "comparable — start a new store or re-embed the corpus."
                )
            data["model"] = model
            data.setdefault("pairs", []).append({
                "preferred": [round(float(x), 6) for x in preferred],
                "rejected": [round(float(x), 6) for x in rejected],
                "note": note,
                # Session/material identity. Cross-validation holds out
                # whole groups, so this is what keeps the reported skill
                # honest — see _cv_accuracy.
                "group": group,
                "ts": int(time.time()),
            })
            # Any new evidence invalidates the fitted head.
            data["weights"] = None
            data["trained"] = None
            return data
        return self._store.update(_update)

    def save_fit(self, weights: np.ndarray, report: dict) -> None:
        def _update(data: dict) -> dict:
            data["weights"] = [round(float(x), 8) for x in weights]
            data["trained"] = report
            return data
        self._store.update(_update)


# --- model -------------------------------------------------------------------

def _fit_weights(diffs: np.ndarray, l2: float) -> np.ndarray:
    """Logistic regression on difference vectors, all labels positive.

    Minimises  -sum(log sigmoid(w.d)) + l2*||w||^2  by gradient descent.
    Convex, so the optimum is unique and plain GD is sufficient at this size.
    """
    w = np.zeros(diffs.shape[1], dtype=np.float64)
    n = len(diffs)
    for _ in range(_MAX_ITERS):
        z = diffs @ w
        # sigmoid(-z) = 1 - sigmoid(z), computed stably
        p_wrong = 1.0 / (1.0 + np.exp(np.clip(z, -60, 60)))
        grad = -(diffs * p_wrong[:, None]).sum(axis=0) / n + 2.0 * l2 * w
        w -= _LR * grad
        if np.linalg.norm(grad) < 1e-7:
            break
    return w


def _cv_accuracy(diffs: np.ndarray, groups: list[str],
                 l2: float) -> tuple[Optional[float], str]:
    """Cross-validated accuracy, holding out whole GROUPS where possible.

    Returns (accuracy, scheme).

    Why grouping is not optional. A session yields several pairs from the same
    material, and plain leave-one-pair-out leaves siblings from that session in
    the training set — so the held-out pair is trivially easy and the score
    measures memorised session identity, not transferable taste.

    Measured on 7 real capture pairs from 3 sessions:

        leave-one-pair-out    100%   <- looks like a strong signal
        leave-one-session-out  57%   <- actually chance

    A 43-point gap. The optimistic number would have reported "the head has
    learned a real preference signal" about a head that generalises to nothing.
    So leave-one-group-out is used whenever there are >= 2 groups, and the
    fallback is labelled as optimistic rather than quietly substituted.
    """
    n = len(diffs)
    if n < MIN_PAIRS:
        return None, "insufficient"

    distinct = sorted(set(groups))
    if len(distinct) >= 2:
        correct = total = 0
        for g in distinct:
            train_idx = [i for i, gg in enumerate(groups) if gg != g]
            test_idx = [i for i, gg in enumerate(groups) if gg == g]
            if not train_idx:
                continue
            w = _fit_weights(diffs[train_idx], l2)
            correct += int(((diffs[test_idx] @ w) > 0).sum())
            total += len(test_idx)
        if total:
            # Degenerate case: every group holds exactly one pair, so holding
            # out a group IS holding out a pair and the grouping constrains
            # nothing. That is honest only if the pairs really do come from
            # that many separate sessions — which we cannot verify, and which
            # a sloppy auto-derived group label would fake. Say so rather than
            # let the reassuring name stand.
            if len(distinct) == n:
                return correct / total, ("leave-one-group-out (DEGENERATE — "
                                         "every pair is its own group, so this "
                                         "equals leave-one-pair-out)")
            return correct / total, "leave-one-group-out"

    # Single group (or none recorded): no honest generalisation estimate is
    # available. Report the optimistic number, clearly labelled.
    correct = 0
    for i in range(n):
        rest = np.delete(diffs, i, axis=0)
        w = _fit_weights(rest, l2)
        if float(diffs[i] @ w) > 0:
            correct += 1
    return correct / n, "leave-one-pair-out (OPTIMISTIC — single group)"


def _binomial_p_value(correct: int, n: int) -> float:
    """One-sided exact P(X >= correct) under the null that the head is guessing.

    Accuracy alone is NOT interpretable at this sample size. Measured on
    synthetic data: 20 pairs of RANDOM labels produced a leave-one-out accuracy
    of 65% — identical to a genuinely learnable signal at the same n. Without
    this test the head reports "a weak but real signal" for pure noise, which
    is the single most dangerous thing a preference model can do.
    """
    from math import comb  # noqa: PLC0415
    return sum(comb(n, i) for i in range(correct, n + 1)) / (2 ** n)


SIGNIFICANCE_ALPHA = 0.05


def _verdict(loo: Optional[float], n_pairs: int, scheme: str = "",
             n_groups: int = 0) -> str:
    if loo is None:
        return (f"Only {n_pairs} pair(s). Need at least {MIN_PAIRS} before "
                "cross-validation says anything; the head is not usable yet.")

    optimistic = "OPTIMISTIC" in scheme
    prefix = ""
    if optimistic:
        prefix = (f"All pairs share one group, so this is leave-one-pair-out "
                  f"and is OPTIMISTIC — on real data that read 100% where "
                  f"leave-one-group-out read 57%. Record pairs from a second "
                  f"session before believing it. ")

    correct = int(round(loo * n_pairs))
    p = _binomial_p_value(correct, n_pairs)
    if optimistic:
        return prefix + (f"Uncorrected held-out accuracy {loo:.0%} on "
                         f"{n_pairs} pairs.")

    if "DEGENERATE" in scheme:
        # Valid if the pairs really are from that many sessions; inflated if
        # the group labels merely failed to notice shared material. The user
        # is the only one who can tell, so hand them the check.
        prefix = (f"Each of the {n_pairs} pairs sits in its own group, so no "
                  "siblings were held out and this equals leave-one-pair-out. "
                  "Trust it only if these really are that many separate "
                  "sessions; if any share material, set `group` explicitly and "
                  "retrain. ")

    # Significance first, accuracy second. A high score on few pairs is luck
    # far more often than skill, and saying so is the whole job here.
    if p > SIGNIFICANCE_ALPHA:
        needed = _pairs_for_significance(loo)
        return prefix + (
            f"Held-out accuracy {loo:.0%} on {n_pairs} pairs, but that is "
            f"NOT distinguishable from chance (p={p:.2f}). At this sample "
            "size the number carries no information — do not use these "
            f"scores. Sustaining this accuracy would need ~{needed} pairs "
            "to become significant.")
    if loo >= 0.80:
        return prefix + (
            f"Held-out accuracy {loo:.0%} on {n_pairs} pairs, significantly "
            f"above chance (p={p:.3f}) — the head has learned a real "
            "preference signal.")
    return prefix + (
        f"Held-out accuracy {loo:.0%} on {n_pairs} pairs, above chance "
        f"(p={p:.3f}) but modest. Treat scores as a tiebreaker between "
        "close candidates, not as a verdict.")


def _pairs_for_significance(accuracy: float, alpha: float = SIGNIFICANCE_ALPHA,
                            cap: int = 400) -> int:
    """Smallest n at which this accuracy would beat chance. Turns 'add more
    pairs' into an actionable number instead of vague encouragement."""
    if accuracy <= 0.5:
        return cap
    n = MIN_PAIRS
    while n < cap:
        if _binomial_p_value(int(round(accuracy * n)), n) <= alpha:
            return n
        n += 1
    return cap


def train(store: TasteHeadStore, l2: float = DEFAULT_L2) -> dict:
    """Fit the head and report cross-validated skill (never training fit)."""
    data = store.get_all()
    pairs = data.get("pairs", [])
    n = len(pairs)
    if n == 0:
        return {"trained": False, "n_pairs": 0,
                "verdict": "No preference pairs recorded yet.",
                "cv_accuracy": None}

    diffs = np.array([np.array(p["preferred"], dtype=np.float64)
                      - np.array(p["rejected"], dtype=np.float64)
                      for p in pairs])
    groups = [p.get("group") or "" for p in pairs]
    n_groups = len({g for g in groups if g})
    weights = _fit_weights(diffs, l2)
    loo, scheme = _cv_accuracy(diffs, groups, l2)
    # A p-value computed on the optimistic (single-group) accuracy would be a
    # significance test of leakage, and `significant: true` is exactly what
    # suppresses the untrustworthy-ranking warning downstream. Withhold both
    # until whole groups can be held out.
    if loo is None or "OPTIMISTIC" in scheme:
        p_value = None
    else:
        p_value = _binomial_p_value(int(round(loo * n)), n)
    report = {
        "trained": True,
        "n_pairs": n,
        "model": data.get("model"),
        "l2": l2,
        "cv_accuracy": None if loo is None else round(loo, 4),
        "cv_scheme": scheme,
        "n_groups": n_groups,
        "baseline_accuracy": 0.5,
        "p_value": None if p_value is None else round(p_value, 4),
        "significant": None if p_value is None else bool(p_value <= SIGNIFICANCE_ALPHA),
        "verdict": _verdict(loo, n, scheme, n_groups),
        "trained_at": int(time.time()),
    }
    # Training accuracy is deliberately absent: with n << d it is ~100%
    # regardless of whether anything was learned, so reporting it would only
    # invite the wrong conclusion.
    if loo is not None:
        store.save_fit(weights, report)
    return report


def score(store: TasteHeadStore, embedding: np.ndarray) -> Optional[dict]:
    """Preference score for one embedding, or None if the head is untrained.

    The absolute value is meaningless — Bradley-Terry is shift-invariant, so
    only DIFFERENCES between scores carry information. Compare candidates;
    never threshold a single score.
    """
    data = store.get_all()
    w = data.get("weights")
    if not w:
        return None
    weights = np.array(w, dtype=np.float64)
    if weights.shape[0] != embedding.shape[0]:
        return None
    s = float(np.dot(weights, embedding))
    trained = data.get("trained") or {}
    return {
        "score": round(s, 6),
        "comparable_only": True,
        "cv_accuracy": trained.get("cv_accuracy"),
        "cv_scheme": trained.get("cv_scheme"),
        "significant": trained.get("significant"),
        "n_pairs": trained.get("n_pairs"),
        "note": ("Scores are comparable to each other, not to zero. "
                 "Bradley-Terry is shift-invariant: rank candidates, do not "
                 "threshold a single value."),
    }


def preference_probability(store: TasteHeadStore, a: np.ndarray,
                           b: np.ndarray) -> Optional[float]:
    """P(a preferred over b) under the fitted head."""
    data = store.get_all()
    w = data.get("weights")
    if not w:
        return None
    weights = np.array(w, dtype=np.float64)
    if weights.shape[0] != a.shape[0] or weights.shape[0] != b.shape[0]:
        return None
    z = float(np.dot(weights, a - b))
    return float(1.0 / (1.0 + np.exp(-np.clip(z, -60, 60))))

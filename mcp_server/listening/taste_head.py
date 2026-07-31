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
accuracy, a p-value against chance, and a verdict in words. Five corrections
make that honest, each added after it was caught misreporting:

1. GROUPED cross-validation. A session yields several pairs from the same
   material, so holding out one PAIR leaves its siblings in training and the
   held-out pair becomes trivial. Measured on 7 real capture pairs from 3
   sessions: leave-one-pair-out 100%, leave-one-session-out 57%. Whole groups
   are held out whenever there are >= 2 of them; the single-group fallback is
   labelled OPTIMISTIC rather than quietly substituted.

2. Significance at all. Accuracy alone is uninterpretable at this sample size:
   20 pairs of RANDOM labels produced 65% leave-one-out, matching a genuinely
   learnable signal at the same n. `significant: false` means the number
   carries no information however high it looks.

3. SHARED-REFERENCE detection, before the split. Grouping trusts a label, and
   no label can say "these pairs share a baseline". Keep one reference render
   and A/B candidates against it — the most natural way anyone compares
   anything — and every pair carries the same anchor, so every fold learns "not
   the anchor" and scores perfectly. Two guards, because the obvious one closes
   only a quarter of it: `_merge_groups_sharing_a_capture` catches a re-USED
   file, and `_anchor_asymmetry` catches a re-RECORDED one, which is what
   `capture_audio` actually produces. Measured at production geometry, 6
   sessions x 2 pairs, before the second guard existed:

       re-recorded anchor cosine   0.98  0.95  0.90  0.85  0.80  0.70
       certified as real taste     100%  100%  100%  100%  100%  100%
       captures merged                0     0     0     0     0     0

   (honest control, own reference per session: 1%.) After: 0% certified at
   every cosine, control untouched, and a genuine quality signal still
   certifies at 100%.

4. Significance over SESSIONS. Correction 1 grouped the cross-validation split
   but left the test counting pairs as independent trials. False-positive rate
   on corpora with no transferable signal, nominal 5%: 25% counting pairs, ~9%
   counting sessions. See `_group_sign_test`, which also records why the
   textbook permutation fix was built and rejected.

5. Measuring any of this in the geometry the code ACTUALLY RUNS IN. Real CLAP
   embeddings are L2-normalised, so a difference vector has norm 0.3-1.4. The
   first two rounds of measurement used raw gaussians at norm ~30, where
   `_fit_weights` returns near-zero and every corpus looks clean. That is how a
   guard closing a quarter of its defect passed a full green suite with a
   docstring claiming it was measured. The test helpers now generate unit-norm
   captures at production dimension; see `_unit` in the test module.

The cost of 3 and 4 is a higher bar: significance needs decisions from
MIN_GROUPS_FOR_SIGNIFICANCE separate sessions with no shared captures, and below
that nothing can be certified however good it looks. That bar is derived from
how much evidence that many sessions carry, not chosen.

Regularisation is strong by default for the same reason as all of the above:
with n << d the penalty is what stops the head memorising.
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

    Targets  -sum(log sigmoid(w.d)) + l2*||w||^2, which is convex.

    Note what the iteration actually is at the default settings. The update
    w -= _LR * (-mean(d*p_wrong) + 2*l2*w) has memory coefficient
    (1 - _LR*2*l2), which is EXACTLY 0 at _LR=0.5 and l2=1.0 — so w is
    discarded and recomputed each step rather than accumulated. It is a fixed
    point iteration, not gradient descent, and it converges in one step for
    well-scaled inputs.

    That is fine in the deployed regime (unit-norm CLAP embeddings, ||d|| in
    0.3-1.4, giving ||w|| ~ 0.03-0.26 and clean margins) but it is fragile: at
    ||d|| ~ 30 the same code returns ~1e-8 and every corpus scores at chance.
    Anything that changes _LR or DEFAULT_L2 changes the character of this
    function, not just its speed. Measure in production geometry — see
    correction 5 in the module docstring for what happens when you do not.
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
                 l2: float) -> tuple[Optional[float], str, list[tuple[int, int]]]:
    """Cross-validated accuracy, holding out whole GROUPS where possible.

    Returns (accuracy, scheme, per_group), where per_group is one
    (correct, total) tuple per held-out group. The caller needs that breakdown
    because the SESSION, not the pair, is the independent unit — see
    `_group_sign_test`.

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
        return None, "insufficient", []

    distinct = sorted(set(groups))
    if len(distinct) >= 2:
        correct = total = 0
        per_group: list[tuple[int, int]] = []
        for g in distinct:
            train_idx = [i for i, gg in enumerate(groups) if gg != g]
            test_idx = [i for i, gg in enumerate(groups) if gg == g]
            if not train_idx:
                continue
            w = _fit_weights(diffs[train_idx], l2)
            hits = int(((diffs[test_idx] @ w) > 0).sum())
            per_group.append((hits, len(test_idx)))
            correct += hits
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
                                         "equals leave-one-pair-out)"), per_group
            return correct / total, "leave-one-group-out", per_group

    # Single group (or none recorded): no honest generalisation estimate is
    # available. Report the optimistic number, clearly labelled.
    correct = 0
    for i in range(n):
        rest = np.delete(diffs, i, axis=0)
        w = _fit_weights(rest, l2)
        if float(diffs[i] @ w) > 0:
            correct += 1
    return correct / n, "leave-one-pair-out (OPTIMISTIC — single group)", []


SIGNIFICANCE_ALPHA = 0.05

def _sessions_for_significance(alpha: float = SIGNIFICANCE_ALPHA) -> int:
    """Fewest sessions at which a flawless result could clear alpha.

    A clean sweep of G sessions gives p = 2**-G, so below the G this returns NO
    result — not even a perfect one — can clear alpha. That is a property of how
    much evidence G sessions carry, not a threshold anyone picked.
    """
    n = 1
    while 0.5 ** n > alpha:
        n += 1
    return n


MIN_GROUPS_FOR_SIGNIFICANCE = _sessions_for_significance()


def _binomial_p_value(correct: int, n: int) -> float:
    """One-sided exact P(X >= correct) under the null that the head is guessing."""
    from math import comb  # noqa: PLC0415
    return sum(comb(n, i) for i in range(correct, n + 1)) / (2 ** n)


def _group_sign_test(per_group: list[tuple[int, int]]) -> Optional[float]:
    """Significance counting SESSIONS, not pairs — the independent unit.

    Guard 3 grouped the cross-validation split but left significance counting
    every PAIR as an independent coin flip. It is not: all pairs in a held-out
    session are scored by one fitted `w` against correlated material, so a
    session is ONE observation, not k. Counting them individually inflates
    confidence in proportion to how alike a session's pairs are.

    Measured false-positive rate on corpora built to contain NO transferable
    signal (each session gets its own direction), nominal alpha = 0.05:

        within-session diff cosine   1.00   0.92   0.67   0.41   0.20   0.06
        pair-level binomial (old)     25%    28%    22%    18%    11%     6%

    It was only honest at the right edge, where a session's pairs are unrelated
    to each other — precisely what real sessions are not, and the reason guard 3
    exists. Counting sessions instead brings this to ~9%.

    A session counts once, as a win or a loss depending on whether the head beat
    chance on it. Ties carry no directional evidence and are dropped.

    KNOWN RESIDUAL, re-measured at production geometry (unit-norm CLAP, 512-d):
    5.8% at 6 sessions x 4 pairs, 6.7% at 5 x 4, and 12.5% at 8 x 3 — against a
    nominal 5%. It degrades as sessions get thinner, because the CV folds share
    training data so sessions are not fully independent either. Power is
    unaffected: 100% on a genuine shared direction at >= 5 sessions, 0% at 4
    (structurally impossible, not a failure).
    The textbook fix — a group sign-flip permutation test — was built and
    REJECTED: `_fit_weights` is deliberately robust (`p_wrong` downweights
    already-correct points), so on the bimodal +/-d data that sign-flipping
    creates it settles on the MINORITY direction. CV accuracy then stops being
    monotone in the sign pattern, 20 of 64 flip patterns score a perfect 1.0,
    and the test loses essentially all power (a clean synthetic signal over 6-8
    sessions measured p=0.17-0.34 regardless of how many pairs were added).
    A test that cannot certify anything is not conservative, it is broken —
    and it would have looked more rigorous than what it replaced. Prefer the
    honest 9% until the estimator itself is revisited.
    """
    wins = sum(1 for c, t in per_group if t and c / t > 0.5)
    losses = sum(1 for c, t in per_group if t and c / t < 0.5)
    decisive = wins + losses
    if decisive == 0:
        return None
    return _binomial_p_value(wins, decisive)


def _verdict(loo: Optional[float], n_pairs: int, scheme: str = "",
             n_groups: int = 0, p: Optional[float] = None,
             n_decisive: int = 0, merged: int = 0, anchored: bool = False,
             asymmetry: float = 0.0) -> str:
    if loo is None:
        return (f"Only {n_pairs} pair(s). Need at least {MIN_PAIRS} before "
                "cross-validation says anything; the head is not usable yet.")

    prefix = ""
    if anchored:
        side = "rejected" if asymmetry > 0 else "preferred"
        prefix = (f"Every session's {side} captures are far more alike than "
                  f"chance (asymmetry {asymmetry:+.2f} against ~0.00 for "
                  "independent material), which is the signature of one shared "
                  "reference compared against over and over. Those decisions are "
                  "one piece of evidence, not several, so they were scored as a "
                  "single session. Compare candidates against EACH OTHER, not "
                  "against a fixed baseline. ")
    elif merged:
        prefix = (f"{merged + 1} of the recorded groups share a capture — a "
                  "reused baseline makes those pairs one piece of evidence, not "
                  "several — so they were merged before scoring. ")

    if "OPTIMISTIC" in scheme:
        return prefix + (
            "All pairs now sit in one group, so this is leave-one-pair-out and "
            "is OPTIMISTIC — on real data that read 100% where "
            "leave-one-group-out read 57%. Uncorrected held-out accuracy "
            f"{loo:.0%} on {n_pairs} pairs. Record pairs from a genuinely "
            "separate session, with no capture in common, before believing it.")

    if "DEGENERATE" in scheme:
        prefix += (f"Each of the {n_pairs} pairs sits in its own group, so no "
                   "siblings were held out and this equals leave-one-pair-out. "
                   "Trust it only if these really are that many separate "
                   "sessions. ")

    # Significance counts SESSIONS, so too few sessions means nothing can be
    # certified — however good the accuracy looks. Say that plainly instead of
    # reporting an un-clearable p-value.
    if p is None or n_decisive < MIN_GROUPS_FOR_SIGNIFICANCE:
        need = MIN_GROUPS_FOR_SIGNIFICANCE
        return prefix + (
            f"Held-out accuracy {loo:.0%} across {n_groups} session(s), but "
            f"nothing can be certified yet: significance counts SESSIONS, not "
            f"pairs, and {n_decisive} gave a decisive result where {need} are "
            "needed. Even a flawless score over four sessions cannot clear "
            "p<0.05. Record decisions from more separate sessions — more pairs "
            "from the ones you have will not help.")

    if p > SIGNIFICANCE_ALPHA:
        return prefix + (
            f"Held-out accuracy {loo:.0%} across {n_groups} session(s), but "
            f"that is NOT distinguishable from chance (p={p:.2f} over "
            f"{n_decisive} sessions). The number carries no information — do "
            "not use these scores.")
    if loo >= 0.80:
        return prefix + (
            f"Held-out accuracy {loo:.0%} across {n_groups} session(s), "
            f"significantly above chance (p={p:.3f} over {n_decisive} "
            "sessions) — the head has learned a real preference signal.")
    return prefix + (
        f"Held-out accuracy {loo:.0%} across {n_groups} session(s), above "
        f"chance (p={p:.3f} over {n_decisive} sessions) but modest. Treat "
        "scores as a tiebreaker between close candidates, not as a verdict.")


def _merge_groups_sharing_a_capture(pairs: list[dict],
                                    groups: list[str]) -> tuple[list[str], int]:
    """Union any groups that share a capture. Returns (groups, n_merged).

    GUARD #4, and the one the group *labels* cannot express. Grouping trusts a
    string; this checks the vectors underneath it.

    The failure it closes is the most natural way anyone A/Bs anything: keep one
    baseline and run candidates against it. Every pair then carries the same
    anchor on the rejected side, so the mean difference vector is dominated by
    "not-the-anchor", every fold learns that, and every fold predicts perfectly
    — no matter which session labels the pairs carry. Grouped CV cannot see it,
    because the anchor is inside every group.

    Measured, 512-d, 6 pairs across 3 explicitly-labelled sessions sharing one
    anchor: cv_accuracy 1.0, leave-one-group-out, p=0.0156, significant TRUE,
    verdict "the head has learned a real preference signal" — in 40 of 40 runs.
    That same fitted head scores 0.507 on fresh candidate-vs-candidate pairs.
    The identical corpus without a shared anchor: significant in 3 of 40.

    Merging is the honest response rather than refusing outright: the pairs are
    real evidence, they are just not independent evidence. Collapsed into one
    group they take the existing OPTIMISTIC path, which withholds the p-value
    and makes `taste_rank` warn.
    """
    key_to_groups: dict[tuple, set[str]] = {}
    for p, g in zip(pairs, groups):
        for side in ("preferred", "rejected"):
            key_to_groups.setdefault(tuple(p[side]), set()).add(g)

    parent = {g: g for g in set(groups)}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    merged = 0
    for shared in key_to_groups.values():
        if len(shared) < 2:
            continue
        it = iter(shared)
        root = find(next(it))
        for other in it:
            r2 = find(other)
            if r2 != root:
                parent[r2] = root
                merged += 1
    return [find(g) for g in groups], merged


# Honest corpora measure 0.000 +/- 0.008 (max 0.030 over 60 runs, including
# corpora carrying a genuine quality signal). The weakest anchoring that still
# certified at 100% measures 0.473. This sits >13 sd above honest and far below
# the weakest real offender — a gap wide enough that the exact value is not
# load-bearing.
ANCHOR_ASYMMETRY_LIMIT = 0.15


def _anchor_asymmetry(pairs: list[dict], groups: list[str]) -> float:
    """How much more alike the REJECTED captures are than the preferred ones,
    measured only ACROSS sessions, using the groups AS RECORDED. Positive means a shared reference on the
    rejected side; negative means one on the preferred side.

    Guard 4 keyed on exact vector equality, which turned out to close a far
    narrower hole than it claimed. `capture_audio` records live playback, so a
    producer who re-captures their reference each session produces a NEW file
    every time — never byte-identical, always the same material. Measured at
    realistic CLAP geometry, 6 sessions x 2 pairs, no genuine quality signal:

        re-recorded anchor cosine   0.98  0.95  0.90  0.85  0.80  0.70
        certified as real taste     100%  100%  100%  100%  100%  100%
        captures merged by guard 4     0     0     0     0     0     0
        (honest control, own anchor per session: 1%)

    A cosine threshold cannot fix that: at anchor cosine 0.70 the two anchors are
    less alike (0.49) than two independent captures from one project, so any
    cutoff strict enough to catch it merges every real corpus. This statistic is
    relative instead, so it needs no notion of "how similar is one project":

        anchored 0.70 .. 1.00            +0.473 .. +1.000  (sd ~0.006)
        honest, own anchor per session   -0.000            (sd  0.008)
        honest + a real quality signal   +0.002            (sd  0.011)
        anchor on the PREFERRED side     -0.810            (sd  0.005)

    A real preference direction moves preferred and rejected captures APART
    symmetrically, leaving this near zero — which is why a genuine signal does
    not trip it.
    """
    def mean_cross(key: str) -> float:
        vs = np.array([p[key] for p in pairs], dtype=np.float64)
        norms = np.linalg.norm(vs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vs = vs / norms
        sims = []
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                if groups[i] != groups[j]:
                    sims.append(float(vs[i] @ vs[j]))
        return float(np.mean(sims)) if sims else 0.0

    return mean_cross("rejected") - mean_cross("preferred")


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
    raw_groups = [p.get("group") or "" for p in pairs]
    # Guard #4 runs BEFORE the split: a label cannot express "these pairs share
    # a baseline capture", and grouped CV is blind to it.
    groups, merged = _merge_groups_sharing_a_capture(pairs, raw_groups)
    # ...and exact equality only catches a re-USED file, not a re-RECORDED one,
    # which is what capture_audio actually produces. This catches the rest.
    # Measured against the groups as RECORDED, not the merged ones: the merge
    # can already have collapsed everything into a single group, leaving no
    # cross-group pairs and a statistic of 0.0 that would read as "clean".
    asymmetry = _anchor_asymmetry(pairs, raw_groups)
    anchored = abs(asymmetry) > ANCHOR_ASYMMETRY_LIMIT
    if anchored:
        groups = ["_shared_reference"] * n
    n_groups = len(set(groups))
    weights = _fit_weights(diffs, l2)
    loo, scheme, per_group = _cv_accuracy(diffs, groups, l2)
    # A p-value computed on the optimistic (single-group) accuracy would be a
    # significance test of leakage, and `significant: true` is exactly what
    # suppresses the untrustworthy-ranking warning downstream. Withhold both
    # until whole groups can be held out.
    if loo is None or "OPTIMISTIC" in scheme:
        p_value = None
        n_decisive = 0
    else:
        # Sessions, not pairs — see _group_sign_test.
        p_value = _group_sign_test(per_group)
        n_decisive = sum(1 for c, t in per_group if t and c / t != 0.5)
    certifiable = (p_value is not None
                   and n_decisive >= MIN_GROUPS_FOR_SIGNIFICANCE)
    report = {
        "trained": True,
        "n_pairs": n,
        "model": data.get("model"),
        "l2": l2,
        "cv_accuracy": None if loo is None else round(loo, 4),
        "cv_scheme": scheme,
        "n_groups": n_groups,
        "n_groups_recorded": len({g for g in raw_groups if g}),
        "groups_merged": merged,
        "anchor_asymmetry": round(asymmetry, 4),
        "shared_reference_detected": bool(anchored),
        "n_decisive_groups": n_decisive,
        "sessions_needed_for_significance": MIN_GROUPS_FOR_SIGNIFICANCE,
        "baseline_accuracy": 0.5,
        "p_value": None if not certifiable else round(p_value, 4),
        "significant": (None if not certifiable
                        else bool(p_value <= SIGNIFICANCE_ALPHA)),
        "verdict": _verdict(loo, n, scheme, n_groups, p_value, n_decisive,
                            merged, anchored, asymmetry),
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

"""Bradley-Terry taste head — the model, and its honesty guarantees.

These run WITHOUT torch/transformers. The head itself is pure numpy over
already-computed embeddings, so everything except the embed step is testable in
CI; the embed step is monkeypatched.

Most of this file is not testing "does it fit" — a convex logistic regression
fits. It is testing that the head cannot OVERSTATE what it learned, which is
the only way a preference model does real damage. Two live regression guards:

  * random labels must not be reported as signal (test_random_labels_*)
  * a single-group corpus must not be reported as generalisation
    (test_single_group_*), because leave-one-pair-out read 100% on real
    captures where leave-one-group-out read 57%.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server.listening import taste_head  # noqa: E402
from mcp_server.listening import taste_tools  # noqa: E402

DIM = 32


def _store(tmp_path, name="taste.json"):
    return taste_head.TasteHeadStore(tmp_path / name)


def _add(store, pref, rej, group="g", model="test-model"):
    return store.add_pair(np.asarray(pref, dtype=float),
                          np.asarray(rej, dtype=float), model, group=group)


def _signal_pairs(store, n=8, groups=2, seed=0):
    """Pairs where dimension 0 alone decides the preference — a signal any
    linear head should generalise across groups."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        base = rng.normal(size=DIM)
        pref, rej = base.copy(), base.copy()
        pref[0] += 3.0
        rej[0] -= 3.0
        _add(store, pref, rej, group=f"g{i % groups}")


def _noise_pairs(store, n=20, groups=2, seed=1):
    """Pairs with no consistent direction — pure noise, correctly labelled as
    a preference. Anything the head 'learns' here is memorisation."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        _add(store, rng.normal(size=DIM), rng.normal(size=DIM),
             group=f"g{i % groups}")


# --- store contract ----------------------------------------------------------

def test_store_starts_empty_and_reports_it(tmp_path):
    report = taste_head.train(_store(tmp_path))
    assert report["trained"] is False
    assert report["n_pairs"] == 0
    assert report["cv_accuracy"] is None


def test_store_refuses_to_mix_embedding_models(tmp_path):
    """Vectors from different models are not comparable; blending them would
    silently poison every later fit, so this must raise rather than coerce."""
    s = _store(tmp_path)
    _add(s, np.ones(DIM), np.zeros(DIM), model="clap")
    with pytest.raises(ValueError, match="not\n?\\s*comparable|comparable"):
        _add(s, np.ones(DIM), np.zeros(DIM), model="mert")


def test_new_pair_invalidates_the_fitted_head(tmp_path):
    """Stale weights next to fresh pairs is a silent-wrongness trap."""
    s = _store(tmp_path)
    _signal_pairs(s)
    taste_head.train(s)
    assert s.get_all()["weights"] is not None

    _add(s, np.ones(DIM), np.zeros(DIM), group="g9")
    data = s.get_all()
    assert data["weights"] is None
    assert data["trained"] is None


def test_pairs_survive_a_reopened_store(tmp_path):
    _signal_pairs(_store(tmp_path))
    assert len(_store(tmp_path).get_all()["pairs"]) == 8


# --- the honesty guarantees --------------------------------------------------

def test_training_accuracy_is_never_reported(tmp_path):
    """With n << d a linear head fits ~100% of training data whether or not it
    learned anything. Reporting that number invites exactly the wrong
    conclusion, so no key may carry it."""
    s = _store(tmp_path)
    _signal_pairs(s)
    report = taste_head.train(s)
    assert not [k for k in report if "train" in k and k != "trained"
                and k != "trained_at"]


def test_real_signal_is_recognised_across_groups(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=10, groups=2)
    r = taste_head.train(s)
    assert r["cv_scheme"] == "leave-one-group-out"
    assert r["cv_accuracy"] == 1.0
    assert r["significant"] is True
    assert r["p_value"] < taste_head.SIGNIFICANCE_ALPHA


def test_random_labels_are_not_reported_as_signal(tmp_path):
    """THE regression guard. Before the binomial test, 20 pairs of pure noise
    produced 65% held-out accuracy and a verdict of 'a weak but real signal'."""
    s = _store(tmp_path)
    _noise_pairs(s, n=20, groups=4)
    r = taste_head.train(s)
    assert r["significant"] is False
    assert "not distinguishable from chance" in r["verdict"].lower()


def test_random_labels_verdict_says_do_not_use(tmp_path):
    s = _store(tmp_path)
    _noise_pairs(s, n=20, groups=4)
    verdict = taste_head.train(s)["verdict"]
    assert "do not use" in verdict.lower()
    assert "pairs to become significant" in verdict


def test_single_group_is_labelled_optimistic(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=8, groups=1)
    r = taste_head.train(s)
    assert r["n_groups"] == 1
    assert "OPTIMISTIC" in r["cv_scheme"]
    assert "OPTIMISTIC" in r["verdict"]


def test_single_group_withholds_significance(tmp_path):
    """A p-value computed on the leaky accuracy is a significance test OF the
    leak — and `significant: true` is what suppresses the untrustworthy-ranking
    warning downstream. Both must be withheld until groups can be held out."""
    s = _store(tmp_path)
    _signal_pairs(s, n=8, groups=1)
    r = taste_head.train(s)
    assert r["p_value"] is None
    assert r["significant"] is None


def test_grouped_cv_is_stricter_than_leave_one_pair_out(tmp_path):
    """The leakage this whole design exists to prevent. Same pairs, same
    labels — the only difference is whether siblings from a session stay in the
    training set. On real captures this gap was 100% vs 57%."""
    rng = np.random.default_rng(7)
    diffs, groups = [], []
    for g in range(3):
        # A per-session nuisance direction, ORTHOGONAL across sessions: within
        # a session it predicts perfectly, across sessions it carries nothing.
        # Orthogonal rather than merely random — random directions in 32-d land
        # partly anti-correlated, which makes the corpus unlearnable under BOTH
        # schemes and hides the very gap under test.
        direction = np.zeros(DIM)
        direction[g] = 4.0
        for _ in range(4):
            diffs.append(direction + rng.normal(size=DIM) * 0.05)
            groups.append(f"session{g}")
    diffs = np.array(diffs)

    grouped, grouped_scheme = taste_head._cv_accuracy(
        diffs, groups, taste_head.DEFAULT_L2)
    leaky, leaky_scheme = taste_head._cv_accuracy(
        diffs, ["one"] * len(diffs), taste_head.DEFAULT_L2)

    assert grouped_scheme == "leave-one-group-out"
    assert "OPTIMISTIC" in leaky_scheme
    assert leaky > grouped


def test_degenerate_grouping_is_called_out(tmp_path):
    """Backstop for a bad grouping. If every pair lands in its own group,
    holding out a group IS holding out a pair — the grouping constrains
    nothing, and the reassuring "leave-one-group-out" label would be doing all
    the reassuring by itself."""
    s = _store(tmp_path)
    _signal_pairs(s, n=8, groups=8)
    r = taste_head.train(s)
    assert r["n_groups"] == 8
    assert "DEGENERATE" in r["cv_scheme"]
    assert "equals leave-one-pair-out" in r["cv_scheme"]


def test_degenerate_verdict_hands_the_check_to_the_user(tmp_path):
    """It is genuinely valid IF the pairs really are that many sessions, and we
    cannot tell — so the verdict states the condition instead of silently
    picking an answer."""
    s = _store(tmp_path)
    _signal_pairs(s, n=8, groups=8)
    verdict = taste_head.train(s)["verdict"]
    assert "own group" in verdict
    assert "set `group` explicitly" in verdict
    # still reports the underlying result, not just the caveat
    assert "%" in verdict


def test_healthy_grouping_carries_no_degenerate_warning(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=10, groups=2)
    r = taste_head.train(s)
    assert r["cv_scheme"] == "leave-one-group-out"
    assert "DEGENERATE" not in r["verdict"]


def test_below_minimum_pairs_reports_nothing(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=taste_head.MIN_PAIRS - 1, groups=2)
    r = taste_head.train(s)
    assert r["cv_accuracy"] is None
    assert r["cv_scheme"] == "insufficient"
    assert str(taste_head.MIN_PAIRS) in r["verdict"]


def test_head_is_not_persisted_when_unmeasurable(tmp_path):
    """No cross-validated number means no basis for scoring anything."""
    s = _store(tmp_path)
    _signal_pairs(s, n=taste_head.MIN_PAIRS - 1, groups=2)
    taste_head.train(s)
    assert s.get_all()["weights"] is None
    assert taste_head.score(s, np.ones(DIM)) is None


# --- statistics --------------------------------------------------------------

def test_binomial_p_value_matches_hand_computation():
    # P(X >= 5 | n=5, p=0.5) = 1/32
    assert taste_head._binomial_p_value(5, 5) == pytest.approx(1 / 32)
    # P(X >= 0) is the whole distribution
    assert taste_head._binomial_p_value(0, 10) == pytest.approx(1.0)
    # Chance itself is never significant
    assert taste_head._binomial_p_value(5, 10) > taste_head.SIGNIFICANCE_ALPHA


def test_pairs_for_significance_is_monotone_in_accuracy():
    strong = taste_head._pairs_for_significance(0.95)
    weak = taste_head._pairs_for_significance(0.60)
    assert strong < weak
    # Chance can never become significant, however many pairs.
    assert taste_head._pairs_for_significance(0.5) == 400


# --- scoring -----------------------------------------------------------------

def test_score_is_none_until_trained(tmp_path):
    assert taste_head.score(_store(tmp_path), np.ones(DIM)) is None


def test_score_rejects_dimension_mismatch(tmp_path):
    """A different embedding model produces a different width; scoring it
    against these weights would be meaningless numbers, not an error."""
    s = _store(tmp_path)
    _signal_pairs(s)
    taste_head.train(s)
    assert taste_head.score(s, np.ones(DIM + 1)) is None


def test_score_carries_the_heads_own_confidence(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=10, groups=2)
    taste_head.train(s)
    entry = taste_head.score(s, np.ones(DIM))
    assert entry["comparable_only"] is True
    assert entry["cv_accuracy"] == 1.0
    assert entry["significant"] is True
    assert "shift-invariant" in entry["note"]


def test_score_ordering_follows_the_learned_direction(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=10, groups=2)
    taste_head.train(s)
    high, low = np.zeros(DIM), np.zeros(DIM)
    high[0], low[0] = 5.0, -5.0
    assert taste_head.score(s, high)["score"] > taste_head.score(s, low)["score"]


def test_preference_probability_is_symmetric(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=10, groups=2)
    taste_head.train(s)
    a, b = np.zeros(DIM), np.zeros(DIM)
    a[0], b[0] = 4.0, -4.0
    p = taste_head.preference_probability(s, a, b)
    q = taste_head.preference_probability(s, b, a)
    assert p > 0.5 > q
    assert p + q == pytest.approx(1.0)


def test_preference_probability_is_none_until_trained(tmp_path):
    s = _store(tmp_path)
    assert taste_head.preference_probability(
        s, np.ones(DIM), np.zeros(DIM)) is None


def test_shift_invariance_leaves_the_comparison_unchanged(tmp_path):
    """Bradley-Terry has no bias term because it is unidentifiable — adding a
    constant to both candidates must not move the probability."""
    s = _store(tmp_path)
    _signal_pairs(s, n=10, groups=2)
    taste_head.train(s)
    a, b = np.zeros(DIM), np.zeros(DIM)
    a[0], b[0] = 4.0, -4.0
    shift = np.full(DIM, 2.5)
    assert taste_head.preference_probability(s, a, b) == pytest.approx(
        taste_head.preference_probability(s, a + shift, b + shift))


# --- the MCP tool surface ----------------------------------------------------

def _use_store(monkeypatch, store):
    monkeypatch.setattr(taste_tools, "_store", store)


def _fake_embeddings(monkeypatch, table, model="test-model"):
    """Stand in for CLAP: a fixed filename -> vector table, so the tool layer
    is exercised without the 2 GB optional extra."""
    monkeypatch.setattr(taste_tools, "_embed_file",
                        lambda f: (np.asarray(table[f], dtype=float), model))


def test_derive_group_shares_a_key_within_one_family():
    """Two renders of the same idea must land in ONE group, or grouped CV
    degrades back into the leave-one-pair-out leak it exists to prevent."""
    g = taste_tools._derive_group("bass_take_v1.wav", "bass_take_v2.wav")
    assert g == "bass_take"


def test_derive_group_marks_cross_family_pairs():
    """Nothing shared means no basis for claiming shared material."""
    g = taste_tools._derive_group("bass_take_v1.wav", "pad_wide_v3.wav")
    assert "|" in g
    assert "bass_take" in g and "pad_wide" in g


def test_derive_group_collapses_iterations_of_one_session():
    """Real capture names. Keying off each name's own prefix would give
    `set3_bright|set3_darker` — unique to this pair — and a corpus of such
    pairs puts every pair in its own group, resurrecting the leak. The COMMON
    prefix collapses them to one session."""
    g = taste_tools._derive_group("set3_bright_bass_take_final.wav",
                                  "set3_darker_pad_take_rough.wav")
    assert g == "set3"


def test_derive_group_handles_names_without_separators():
    assert taste_tools._derive_group("kick.wav", "kick.wav") == "kick"


def test_record_pair_degrades_to_an_install_hint(monkeypatch, tmp_path):
    """The optional extra is absent for most users; that must read as a
    missing feature, not a crash."""
    _use_store(monkeypatch, _store(tmp_path))
    monkeypatch.setattr(taste_tools, "_embed_file", lambda f: (None, None))
    out = taste_tools.taste_record_pair("a.wav", "b.wav")
    assert out["recorded"] is False
    assert "pip install torch transformers" in out["reason"]


def test_record_pair_reports_group_and_readiness(monkeypatch, tmp_path):
    _use_store(monkeypatch, _store(tmp_path))
    _fake_embeddings(monkeypatch, {"s1_a.wav": np.ones(DIM),
                                   "s1_b.wav": np.zeros(DIM)})
    out = taste_tools.taste_record_pair("s1_a.wav", "s1_b.wav")
    assert out["recorded"] is True
    assert out["group"] == "s1"
    assert out["n_pairs"] == 1 and out["n_groups"] == 1
    assert "more pair" in out["next"]


def test_record_pair_warns_while_a_single_group_dominates(monkeypatch, tmp_path):
    """Reaching MIN_PAIRS is not the same as being trustworthy. If every pair
    came from one session the tool must say so BEFORE the user trains and
    reads a leaky 100%."""
    _use_store(monkeypatch, _store(tmp_path))
    table = {}
    for i in range(taste_head.MIN_PAIRS):
        table[f"same_sess_{i}a.wav"] = np.ones(DIM) * (i + 1)
        table[f"same_sess_{i}b.wav"] = np.zeros(DIM)
    _fake_embeddings(monkeypatch, table)
    for i in range(taste_head.MIN_PAIRS):
        out = taste_tools.taste_record_pair(f"same_sess_{i}a.wav",
                                            f"same_sess_{i}b.wav")
    assert out["n_groups"] == 1
    assert "OPTIMISTIC" in out["next"]


def test_explicit_group_overrides_the_filename_guess(monkeypatch, tmp_path):
    _use_store(monkeypatch, _store(tmp_path))
    _fake_embeddings(monkeypatch, {"x_1.wav": np.ones(DIM),
                                   "y_2.wav": np.zeros(DIM)})
    out = taste_tools.taste_record_pair("x_1.wav", "y_2.wav", group="mine")
    assert out["group"] == "mine"


def test_rank_refuses_before_training(monkeypatch, tmp_path):
    _use_store(monkeypatch, _store(tmp_path))
    out = taste_tools.taste_rank(["a.wav", "b.wav"])
    assert out["ranked"] is False
    assert "taste_record_pair" in out["reason"]
    assert str(taste_head.MIN_PAIRS) in out["reason"]


def test_rank_rejects_an_empty_request(monkeypatch, tmp_path):
    _use_store(monkeypatch, _store(tmp_path))
    with pytest.raises(ValueError):
        taste_tools.taste_rank([])


def _trained(monkeypatch, tmp_path, kind="signal"):
    s = _store(tmp_path)
    (_signal_pairs if kind == "signal" else _noise_pairs)(s, n=10, groups=2)
    taste_head.train(s)
    _use_store(monkeypatch, s)
    high, low = np.zeros(DIM), np.zeros(DIM)
    high[0], low[0] = 5.0, -5.0
    _fake_embeddings(monkeypatch, {"good.wav": high, "bad.wav": low})
    return s


def test_rank_orders_by_the_learned_direction(monkeypatch, tmp_path):
    _trained(monkeypatch, tmp_path)
    out = taste_tools.taste_rank(["bad.wav", "good.wav"])
    assert out["ranked"] is True
    assert out["best"] == "good.wav"
    assert [r["file"] for r in out["order"]] == ["good.wav", "bad.wav"]


def test_rank_reports_a_probability_for_exactly_two(monkeypatch, tmp_path):
    _trained(monkeypatch, tmp_path)
    out = taste_tools.taste_rank(["good.wav", "bad.wav"])
    assert out["probability"]["value"] > 0.5
    assert "good.wav" in out["probability"]["statement"]


def test_rank_carries_the_confidence_and_stays_quiet_when_earned(
        monkeypatch, tmp_path):
    _trained(monkeypatch, tmp_path, kind="signal")
    out = taste_tools.taste_rank(["good.wav", "bad.wav"])
    assert out["significant"] is True
    assert out["cv_scheme"] == "leave-one-group-out"
    assert "warning" not in out


def test_rank_warns_when_the_head_is_not_better_than_chance(
        monkeypatch, tmp_path):
    """A ranking from a chance-level head looks exactly like a real one. The
    warning is the only thing standing between the two."""
    _trained(monkeypatch, tmp_path, kind="noise")
    out = taste_tools.taste_rank(["good.wav", "bad.wav"])
    assert out["significant"] is False
    assert "not trustworthy" in out["warning"].lower()


def test_rank_refuses_a_mismatched_embedding_width(monkeypatch, tmp_path):
    """Weights from one model against vectors from another produce numbers,
    not meaning — the tool must decline rather than rank noise."""
    _trained(monkeypatch, tmp_path)
    monkeypatch.setattr(taste_tools, "_embed_file",
                        lambda f: (np.ones(DIM + 5), "test-model"))
    out = taste_tools.taste_rank(["good.wav", "bad.wav"])
    assert out["ranked"] is False
    assert "embedding model" in out["reason"]

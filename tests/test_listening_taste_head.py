"""Bradley-Terry taste head — the model, and its honesty guarantees.

These run WITHOUT torch/transformers. The head itself is pure numpy over
already-computed embeddings, so everything except the embed step is testable in
CI; the embed step is monkeypatched.

Most of this file is not testing "does it fit" — a convex logistic regression
fits. It is testing that the head cannot OVERSTATE what it learned, which is
the only way a preference model does real damage. Four live regression guards,
each pinning a way it was caught doing exactly that:

  * random labels must not be reported as signal (test_random_labels_*) —
    20 pairs of noise once measured 65% held-out.
  * a single-group corpus must not be reported as generalisation
    (test_single_group_*) — leave-one-pair-out read 100% on real captures
    where leave-one-group-out read 57%.
  * a reused baseline capture must not be certified
    (test_reused_baseline_*) — 6 pairs over 3 labelled sessions sharing one
    anchor reported "a real preference signal" in 40 of 40 runs, for a head
    scoring 0.507 on fresh pairs.
  * significance must count sessions, not pairs
    (test_significance_counts_sessions_not_pairs) — counting pairs put the
    false-positive rate at ~25% against a nominal 5%.
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

# Match production: CLAP is 512-dim and L2-NORMALISED (embedding.py). Both
# matter. An earlier version of this file used 32 dims of raw gaussian, giving
# difference vectors of norm ~6.7 where real ones are 0.3-1.4 — a regime the
# deployed code never enters, and the reason a guard that closed only a quarter
# of its defect passed a full green suite.
DIM = 512


def _unit(rng, n=None):
    v = rng.normal(size=DIM if n is None else (n, DIM))
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _store(tmp_path, name="taste.json"):
    return taste_head.TasteHeadStore(tmp_path / name)


def _add(store, pref, rej, group="g", model="test-model"):
    return store.add_pair(np.asarray(pref, dtype=float),
                          np.asarray(rej, dtype=float), model, group=group)


def _signal_pairs(store, n=12, groups=6, seed=0):
    """One preference direction shared across sessions, in production geometry.

    Every capture is an independent unit vector pushed along a shared quality
    direction — so the pairs differ from each other (n observations, not one
    repeated), no capture is reused, and the difference vectors land in the
    0.3-1.4 norm band real CLAP produces.
    """
    rng = np.random.default_rng(seed)
    quality = _unit(rng)
    for i in range(n):
        base = _unit(rng)
        pref = base + quality * 0.3
        rej = base - quality * 0.3
        _add(store, pref / np.linalg.norm(pref), rej / np.linalg.norm(rej),
             group=f"g{i % groups}")


def _noise_pairs(store, n=18, groups=6, seed=1):
    """Pairs with no consistent direction — pure noise, correctly labelled as
    a preference. Anything the head 'learns' here is memorisation."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        _add(store, _unit(rng), _unit(rng), group=f"g{i % groups}")


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
    assert len(_store(tmp_path).get_all()["pairs"]) == 12


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
    _signal_pairs(s, n=12, groups=6)
    r = taste_head.train(s)
    assert r["cv_scheme"] == "leave-one-group-out"
    assert r["cv_accuracy"] == 1.0
    assert r["significant"] is True
    assert r["p_value"] < taste_head.SIGNIFICANCE_ALPHA


def test_random_labels_are_not_reported_as_signal(tmp_path):
    """THE regression guard. Before the binomial test, 20 pairs of pure noise
    produced 65% held-out accuracy and a verdict of 'a weak but real signal'."""
    s = _store(tmp_path)
    _noise_pairs(s, n=18, groups=6)
    r = taste_head.train(s)
    assert r["significant"] is not True
    assert "chance" in r["verdict"].lower()


def test_random_labels_verdict_says_do_not_use(tmp_path):
    s = _store(tmp_path)
    _noise_pairs(s, n=18, groups=6)
    verdict = taste_head.train(s)["verdict"]
    assert "do not use" in verdict.lower()
    assert "no information" in verdict.lower()


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
        direction[g] = 0.6                     # realistic ||diff||
        for _ in range(4):
            diffs.append(direction + _unit(rng) * 0.02)
            groups.append(f"session{g}")
    diffs = np.array(diffs)

    grouped, grouped_scheme, _pg = taste_head._cv_accuracy(
        diffs, groups, taste_head.DEFAULT_L2)
    leaky, leaky_scheme, _pg2 = taste_head._cv_accuracy(
        diffs, ["one"] * len(diffs), taste_head.DEFAULT_L2)

    assert grouped_scheme == "leave-one-group-out"
    assert "OPTIMISTIC" in leaky_scheme
    assert leaky > grouped


def test_reused_baseline_capture_cannot_be_certified(tmp_path):
    """GUARD #4, and the whole reason for the audit that found it.

    Keep one reference render and A/B candidates against it — the most natural
    way anyone compares anything — and every pair carries the same anchor on the
    rejected side. Every fold then learns "not the anchor" and scores perfectly,
    no matter which session labels the pairs carry. Grouped CV is blind to it
    because the anchor sits inside every group.

    Measured before the fix, 512-d: 100% accuracy, leave-one-group-out,
    p=0.0156, significant TRUE, "the head has learned a real preference signal"
    — in 40 of 40 runs, for a head scoring 0.507 on fresh pairs.
    """
    rng = np.random.default_rng(3)
    s = _store(tmp_path)
    anchor = _unit(rng)                               # ONE baseline, reused
    for i in range(6):
        _add(s, _unit(rng), anchor, group=f"session{i % 3}")

    r = taste_head.train(s)
    assert r["n_groups_recorded"] == 3, "three sessions were genuinely recorded"
    assert r["groups_merged"] >= 1
    assert r["n_groups"] == 1, "sharing an anchor makes them one piece of evidence"
    assert r["significant"] is not True
    assert r["p_value"] is None


def test_reused_baseline_surfaces_in_the_verdict(tmp_path):
    """Silently merging would be its own dishonesty — the user recorded three
    sessions and must be told why they scored as one."""
    rng = np.random.default_rng(4)
    s = _store(tmp_path)
    anchor = _unit(rng)
    for i in range(6):
        _add(s, _unit(rng), anchor, group=f"session{i % 3}")
    r = taste_head.train(s)
    # A byte-identical anchor trips BOTH guards; the asymmetry message wins
    # because it is the one that names the remedy.
    assert r["groups_merged"] >= 1 and r["shared_reference_detected"] is True
    assert "against EACH OTHER" in r["verdict"]
    assert "one piece of evidence" in r["verdict"]


def test_distinct_captures_are_never_merged(tmp_path):
    """The guard must not fire on healthy corpora, or it would quietly destroy
    every legitimate grouping."""
    s = _store(tmp_path)
    _signal_pairs(s, n=12, groups=6)
    r = taste_head.train(s)
    assert r["groups_merged"] == 0
    assert r["n_groups"] == r["n_groups_recorded"] == 6


def test_shared_capture_merges_only_the_groups_that_share(tmp_path):
    """Merging is surgical: two sessions sharing a capture collapse, the rest
    stay separate evidence."""
    rng = np.random.default_rng(5)
    s = _store(tmp_path)
    shared = _unit(rng)
    _add(s, _unit(rng), shared, group="a")
    _add(s, _unit(rng), shared, group="b")
    for g in ("c", "d", "e", "f"):
        _add(s, _unit(rng), _unit(rng), group=g)
    r = taste_head.train(s)
    assert r["n_groups_recorded"] == 6
    assert r["n_groups"] == 5, "only a and b collapse"
    assert r["groups_merged"] == 1


def test_rerecorded_reference_is_caught_by_asymmetry(tmp_path):
    """The half of guard 4 that exact matching misses, and the reason there was
    a round 3.

    `capture_audio` records live playback, so a producer who re-captures their
    reference each session produces a NEW file every time — never byte-identical,
    always the same material. Measured at production geometry before this guard,
    6 sessions x 2 pairs, no genuine quality signal:

        re-recorded anchor cosine   0.98  0.95  0.90  0.85  0.80  0.70
        certified as real taste     100%  100%  100%  100%  100%  100%
        captures merged                0     0     0     0     0     0

    versus 1% for a control with an independent reference per session.
    """
    rng = np.random.default_rng(11)
    s = _store(tmp_path)
    base = _unit(rng)
    for g in range(6):
        # a re-recording of the same reference: same material, different file
        perp = _unit(rng)
        perp = perp - (perp @ base) * base
        perp /= np.linalg.norm(perp)
        anchor = 0.9 * base + np.sqrt(1 - 0.81) * perp
        for _ in range(2):
            _add(s, _unit(rng), anchor, group=f"s{g}")

    r = taste_head.train(s)
    assert r["groups_merged"] == 0, "not byte-identical — exact matching cannot see it"
    assert r["shared_reference_detected"] is True
    assert r["anchor_asymmetry"] > taste_head.ANCHOR_ASYMMETRY_LIMIT
    assert r["significant"] is not True


def test_asymmetry_guard_names_the_side_and_the_remedy(tmp_path):
    rng = np.random.default_rng(12)
    s = _store(tmp_path)
    anchor = _unit(rng)
    for g in range(6):
        for _ in range(2):
            _add(s, _unit(rng), anchor, group=f"s{g}")
    verdict = taste_head.train(s)["verdict"]
    assert "rejected" in verdict
    assert "against EACH OTHER" in verdict


def test_asymmetry_guard_is_symmetric_in_which_side_is_anchored(tmp_path):
    """A shared reference on the PREFERRED side is the same defect mirrored, and
    measured the same magnitude with the opposite sign (-0.81)."""
    rng = np.random.default_rng(13)
    s = _store(tmp_path)
    anchor = _unit(rng)
    for g in range(6):
        for _ in range(2):
            _add(s, anchor, _unit(rng), group=f"s{g}")
    r = taste_head.train(s)
    assert r["shared_reference_detected"] is True
    assert r["anchor_asymmetry"] < -taste_head.ANCHOR_ASYMMETRY_LIMIT
    assert "preferred" in r["verdict"]


def test_a_real_preference_signal_does_not_trip_the_asymmetry_guard(tmp_path):
    """The guard must not cost the tool its purpose. A genuine direction moves
    preferred and rejected captures APART symmetrically, leaving the statistic
    near zero — measured +0.002 (sd 0.011) against +0.47 or worse for anchored
    corpora."""
    s = _store(tmp_path)
    _signal_pairs(s, n=12, groups=6)
    r = taste_head.train(s)
    assert r["shared_reference_detected"] is False
    assert abs(r["anchor_asymmetry"]) < taste_head.ANCHOR_ASYMMETRY_LIMIT
    assert r["significant"] is True, "a real signal must still certify"


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
    assert "separate sessions" in verdict
    # still reports the underlying result, not just the caveat
    assert "%" in verdict


def test_healthy_grouping_carries_no_degenerate_warning(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=12, groups=6)
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

def test_sessions_for_significance_is_derived_not_chosen():
    """A clean sweep of G sessions gives p = 2**-G, so the session bar falls
    out of how much evidence G sessions carry rather than being picked."""
    n = taste_head._sessions_for_significance(0.05)
    assert 0.5 ** n <= 0.05
    assert 0.5 ** (n - 1) > 0.05
    assert taste_head.MIN_GROUPS_FOR_SIGNIFICANCE == n
    # a stricter alpha demands more sessions
    assert taste_head._sessions_for_significance(0.01) > n


def test_significance_counts_sessions_not_pairs():
    """The correction itself. Ten pairs from four sessions cannot be certified
    however perfect, because four sessions is four observations — while the
    superseded pair-level test would have read p=0.001 on the same data."""
    per_group = [(3, 3), (3, 3), (3, 3), (3, 3)]          # flawless, 4 sessions
    assert taste_head._group_sign_test(per_group) == pytest.approx(1 / 16)
    assert taste_head._group_sign_test(per_group) > taste_head.SIGNIFICANCE_ALPHA
    # one more session is what buys significance, not more pairs per session
    assert taste_head._group_sign_test(per_group + [(3, 3)]) <= \
        taste_head.SIGNIFICANCE_ALPHA
    assert taste_head._group_sign_test([(30, 30)] * 4) > \
        taste_head.SIGNIFICANCE_ALPHA


def test_split_sessions_are_dropped_not_credited():
    """A session the head got exactly half right carries no directional
    evidence. Counting it as a win would manufacture confidence."""
    assert taste_head._group_sign_test([(1, 2), (1, 2)]) is None
    # ties reduce the observation count rather than padding it
    decisive = taste_head._group_sign_test([(2, 2)] * 5 + [(1, 2)] * 3)
    assert decisive == pytest.approx(1 / 32)


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
    _signal_pairs(s, n=12, groups=6)
    taste_head.train(s)
    entry = taste_head.score(s, np.ones(DIM))
    assert entry["comparable_only"] is True
    assert entry["cv_accuracy"] == 1.0
    assert entry["significant"] is True
    assert "shift-invariant" in entry["note"]


def test_score_ordering_follows_the_learned_direction(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=12, groups=6)
    taste_head.train(s)
    high, low = np.zeros(DIM), np.zeros(DIM)
    high[0], low[0] = 5.0, -5.0
    assert taste_head.score(s, high)["score"] > taste_head.score(s, low)["score"]


def test_preference_probability_is_symmetric(tmp_path):
    s = _store(tmp_path)
    _signal_pairs(s, n=12, groups=6)
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
    _signal_pairs(s, n=12, groups=6)
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
    (_signal_pairs if kind == "signal" else _noise_pairs)(s, n=12, groups=6)
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
    assert out["significant"] is not True
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

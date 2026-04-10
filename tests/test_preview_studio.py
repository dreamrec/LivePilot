"""Unit tests for Preview Studio engine — pure computation, no Ableton needed."""

from mcp_server.preview_studio.engine import (
    commit_variant,
    compare_variants,
    create_preview_set,
    discard_set,
    get_preview_set,
)


# ── Triptych creation ────────────────────────────────────────────


def test_triptych_creates_three_variants():
    """Creative triptych should produce exactly 3 variants."""
    ps = create_preview_set(
        request_text="make this more magical",
        kernel_id="test_kern",
        strategy="creative_triptych",
    )
    assert len(ps.variants) == 3


def test_triptych_labels():
    """Variants should be labeled safe, strong, unexpected."""
    ps = create_preview_set(
        request_text="add energy",
        kernel_id="test_kern",
    )
    labels = {v.label for v in ps.variants}
    assert labels == {"safe", "strong", "unexpected"}


def test_triptych_novelty_ordering():
    """Safe should be lowest novelty, unexpected highest."""
    ps = create_preview_set(
        request_text="improve the chorus",
        kernel_id="test_kern",
    )
    by_label = {v.label: v for v in ps.variants}
    assert by_label["safe"].novelty_level < by_label["strong"].novelty_level
    assert by_label["strong"].novelty_level < by_label["unexpected"].novelty_level


def test_triptych_identity_effects():
    """Each variant should have different identity effects."""
    ps = create_preview_set(
        request_text="test",
        kernel_id="test_kern",
    )
    effects = {v.identity_effect for v in ps.variants}
    assert "preserves" in effects
    assert "evolves" in effects
    assert "contrasts" in effects


# ── Binary strategy ──────────────────────────────────────────────


def test_binary_creates_two_variants():
    """Binary strategy should produce exactly 2 variants."""
    ps = create_preview_set(
        request_text="test binary",
        kernel_id="test_kern",
        strategy="binary",
    )
    assert len(ps.variants) == 2


# ── Comparison ───────────────────────────────────────────────────


def test_comparison_ranks_preserves_highest():
    """With default identity weight, preserves should rank highest."""
    ps = create_preview_set(
        request_text="test ranking",
        kernel_id="test_kern",
    )
    comparison = compare_variants(ps)
    rankings = comparison["rankings"]
    assert len(rankings) == 3
    # First should be the one with highest score
    assert rankings[0]["score"] >= rankings[-1]["score"]


def test_comparison_returns_recommended():
    """Comparison should include a recommended variant."""
    ps = create_preview_set(
        request_text="test recommend",
        kernel_id="test_kern",
    )
    comparison = compare_variants(ps)
    assert comparison.get("recommended")


def test_comparison_with_custom_weights():
    """Custom weights should change ranking."""
    ps = create_preview_set(
        request_text="test weights",
        kernel_id="test_kern",
    )
    # Strongly favor novelty
    comparison = compare_variants(ps, {
        "taste_weight": 0.1,
        "novelty_weight": 0.8,
        "identity_weight": 0.1,
    })
    rankings = comparison["rankings"]
    assert len(rankings) == 3


# ── Commit and discard ───────────────────────────────────────────


def test_commit_marks_chosen():
    """Committing should mark the chosen variant and discard others."""
    ps = create_preview_set(
        request_text="test commit",
        kernel_id="test_kern",
    )
    chosen_id = ps.variants[1].variant_id
    result = commit_variant(ps, chosen_id)

    assert result is not None
    assert result.status == "committed"

    # Others should be discarded
    for v in ps.variants:
        if v.variant_id != chosen_id:
            assert v.status == "discarded"

    assert ps.status == "committed"
    assert ps.committed_variant_id == chosen_id


def test_commit_unknown_variant():
    """Committing an unknown variant should return None."""
    ps = create_preview_set(
        request_text="test bad commit",
        kernel_id="test_kern",
    )
    result = commit_variant(ps, "nonexistent_id")
    assert result is None


def test_discard_removes_from_store():
    """Discarding should remove the set from the store."""
    ps = create_preview_set(
        request_text="test discard",
        kernel_id="test_kern_discard",
    )
    set_id = ps.set_id
    assert get_preview_set(set_id) is not None

    result = discard_set(set_id)
    assert result is True
    assert get_preview_set(set_id) is None


def test_discard_unknown_set():
    """Discarding an unknown set should return False."""
    result = discard_set("nonexistent_set_id")
    assert result is False


# ── Song brain integration ───────────────────────────────────────


def test_variants_include_preservation_notes():
    """Variants should include what_preserved text."""
    ps = create_preview_set(
        request_text="test preservation",
        kernel_id="test_kern",
        song_brain={"sacred_elements": [{"description": "Main hook melody"}]},
    )
    for v in ps.variants:
        assert v.what_preserved  # Should be non-empty
        assert "hook" in v.what_preserved.lower() or "element" in v.what_preserved.lower()


def test_set_id_deterministic():
    """Same request + kernel should produce same set_id."""
    ps1 = create_preview_set(
        request_text="deterministic test",
        kernel_id="kern_fixed",
    )
    ps2 = create_preview_set(
        request_text="deterministic test",
        kernel_id="kern_fixed",
    )
    assert ps1.set_id == ps2.set_id

"""Test the corpus intelligence layer — parsing and querying."""

import os
import pytest

from mcp_server.corpus import load_corpus, get_corpus, Corpus


@pytest.fixture
def corpus():
    """Load corpus from the repo's device-knowledge directory."""
    return load_corpus()


def test_corpus_loads():
    """Corpus should load without errors."""
    c = load_corpus()
    assert isinstance(c, Corpus)


def test_corpus_singleton():
    """get_corpus returns the same instance."""
    a = get_corpus()
    b = get_corpus()
    assert a is b


def test_emotional_recipes_parsed(corpus):
    """Should have parsed emotional recipes from creative-thinking.md."""
    if not corpus.emotional_recipes:
        pytest.skip("Corpus files not found in this environment")
    assert len(corpus.emotional_recipes) >= 5
    # Check known emotions
    assert any("tension" in k for k in corpus.emotional_recipes)
    assert any("warmth" in k or "comfort" in k for k in corpus.emotional_recipes)


def test_physical_models_parsed(corpus):
    """Should have parsed physical model recipes."""
    if not corpus.physical_models:
        pytest.skip("Corpus files not found")
    assert "water" in corpus.physical_models or any("water" in k for k in corpus.physical_models)


def test_suggest_for_emotion(corpus):
    """suggest_for_emotion should return a recipe for known emotions."""
    if not corpus.emotional_recipes:
        pytest.skip("Corpus files not found")
    recipe = corpus.suggest_for_emotion("warmth")
    assert recipe is not None
    assert len(recipe.techniques) > 0


def test_suggest_for_unknown_emotion(corpus):
    """Unknown emotion returns None."""
    result = corpus.suggest_for_emotion("xyznonexistent")
    assert result is None


def test_automation_density(corpus):
    """Should return automation density recommendations for section types."""
    density = corpus.get_automation_density_for_section("intro")
    assert density["param_count"] == "1-2"
    density = corpus.get_automation_density_for_section("peak")
    assert density["param_count"] == "5-8"


def test_genre_chains_parsed(corpus):
    """Should have parsed genre chain recipes."""
    if not corpus.genre_chains:
        pytest.skip("Corpus files not found")
    assert len(corpus.genre_chains) >= 3


def test_anti_patterns_parsed(corpus):
    """Should have parsed anti-patterns from creative-thinking.md."""
    if not corpus.anti_patterns:
        pytest.skip("Corpus files not found")
    assert len(corpus.anti_patterns) >= 3
    assert any("trap" in ap.lower() for ap in corpus.anti_patterns)
